#!/usr/bin/env python3
"""Draft importer. Run inside the tennislive repository; refuses placeholder manifests.
Does not fabricate QC, bypass gates, overwrite published assets, or send PushPlus.
"""
import argparse, base64, hashlib, json, os, re, shutil, subprocess
from pathlib import Path

REPO = 'robertyang87/tennislive'
def run(*args):
    subprocess.run(list(map(str,args)), check=True)
def capture(*args):
    return subprocess.check_output(list(map(str,args)), text=True)
def read(p):
    return json.loads(Path(p).read_text())
def write(p,d):
    Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def load(path):
    m=read(path)
    if os.environ.get('GITHUB_REPOSITORY',REPO)!=REPO: raise ValueError('Wrong repository')
    if m['column'] not in ('reel','interview'): raise ValueError('Unknown column')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',m['slug']): raise ValueError('Set a concrete slug')
    if m['date']!='2026-09-29': raise ValueError('This import is scoped to Hangzhou final date')
    if not re.fullmatch(r'[a-f0-9]{64}',m['sha256']) or not isinstance(m['bytes'],int) or m['bytes']<=0: raise ValueError('Set real master hash and size')
    slug=m['slug']; col=m['column']
    out=Path('output') / (Path('interviews')/slug if col=='interview' else Path(m['date'])/'reel'/slug)
    spec=Path('specs')/('interviews' if col=='interview' else 'reels')/(slug+'.json')
    if str(out)!=m['outdir'] or str(spec)!=m['spec']: raise ValueError('Noncanonical artifact paths')
    if (out/'pushed.json').exists() or Path(f'data/{col}_publish_ledger/{slug}.json').exists(): raise ValueError('Existing publication ledger: review, do not overwrite or resend')
    return m,out,spec

def assemble(path):
    m,out,spec=load(path); chunks=m['chunks']
    if not chunks or sum(c['bytes'] for c in chunks)!=m['bytes']: raise ValueError('Incomplete chunks')
    out.mkdir(parents=True,exist_ok=True)
    film=out/(m['slug']+'.mp4'); partial=film.with_suffix('.mp4.part')
    with partial.open('wb') as f:
        for c in chunks:
            if not re.fullmatch(r'[a-f0-9]{40}',c['sha']) or not 0<c['bytes']<=3145728: raise ValueError('Invalid chunk')
            j=json.loads(capture('gh','api',f"repos/{REPO}/git/blobs/{c['sha']}"))
            b=base64.b64decode(j['content'])
            sha=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()
            if len(b)!=c['bytes'] or sha!=c['sha']: raise ValueError('Chunk mismatch')
            f.write(b)
    if partial.stat().st_size!=m['bytes'] or digest(partial)!=m['sha256']: raise ValueError('Master integrity failure')
    partial.replace(film)
    # Spec, cover, subtitles and true render/provenance proofs must already be staged
    # in their native paths by the reviewed metadata commit. No proof synthesis.
    for p in (spec,spec.with_suffix('.xhs.txt'),out/'poster.jpg',out/'render.json'):
        if not p.is_file(): raise FileNotFoundError(p)
    run('python','tools/push_reel.py','--stage','check','--outdir',out,'--copy',spec.with_suffix('.xhs.txt'),'--date',m['date'])
    if m['column']=='reel':
        run('python','tools/check_reel_landed.py','--slug',m['slug'],'--date',m['date'],'--film',film,'--spec',spec)
    else:
        run('python','tools/audit_interview_cover.py','--spec',spec,'--poster',out/'poster.jpg','--out',out/'cover_visual_attestation.json','--render-json',out/'render.json')
        run('python','tools/check_interview_landed.py','--slug',m['slug'],'--film',film,'--write-attestation')
    qc=read(out/'qc_attestation.json')
    if qc.get('status')!='pass' or qc.get('film_sha256')!=m['sha256'] or qc.get('film_bytes')!=m['bytes']: raise ValueError('Native QC does not attest this master')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:
            f.write(f"outdir={out}\nslug={m['slug']}\nspec={spec}\ncolumn={m['column']}\n")

def release(path):
    m,out,spec=load(path); film=out/(m['slug']+'.mp4'); qc=read(out/'qc_attestation.json')
    if qc.get('status')!='pass' or qc.get('film_sha256')!=digest(film) or digest(film)!=m['sha256']: raise ValueError('QC/master mismatch')
    tag=f"{m['column']}-{m['slug']}"
    exists=subprocess.run(['gh','release','view',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if not exists: run('gh','release','create',tag,'--title',m['title'],'--notes','杭州决赛原生质检通过母版；MP4 不进入 Git tree。')
    data=json.loads(capture('gh','api',f'repos/{REPO}/releases/tags/{tag}'))
    asset=next((a for a in data['assets'] if a['name']==film.name),None)
    if asset is None:
        run('gh','release','upload',tag,film)
        data=json.loads(capture('gh','api',f'repos/{REPO}/releases/tags/{tag}'))
        asset=next(a for a in data['assets'] if a['name']==film.name)
    if asset.get('digest')!='sha256:'+m['sha256'] or asset['size']!=m['bytes']: raise ValueError('Remote master mismatch; never clobber')
    url=asset['browser_download_url']+'?v='+m['sha256'][:16]
    run('curl','--fail','--location','--silent','--show-error','--range','0-99','--output',os.devnull,url)
    r=read(out/'render.json')
    r.update(video_url=url,video_bytes=m['bytes'],film_sha256=m['sha256'],release_asset_digest=asset['digest'],qc_attestation_sha256=digest(out/'qc_attestation.json'))
    write(out/'render.json',r)
    run('python','tools/push_reel.py','--stage','page','--outdir',out,'--copy',spec.with_suffix('.xhs.txt'),'--date',m['date'])
    film.unlink() # verified Release contains exact bytes; keeps movie out of git

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('stage',choices=['assemble','release']); ap.add_argument('--request',type=Path,required=True)
    args=ap.parse_args(); {'assemble':assemble,'release':release}[args.stage](args.request)
