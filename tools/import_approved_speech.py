#!/usr/bin/env python3
"""Import the exact locally approved RNA10 master and preserve its native QC evidence.

Input data/approved_reel_imports/nadal-academy-10th-2026-championship-speech/request.json:
  {"slug": "nadal-academy-10th-2026-championship-speech", "date": "2026-09-22",
   "bytes": <approved-master-bytes>, "sha256": "<approved-master-sha256>",
   "chunks": [{"sha": "<Git blob SHA>", "bytes": 3145728}, ...]}
Adjacent inputs: spec.json, render.json, subtitles.ass, poster.jpg, copy.txt.
Unreferenced Git blobs are transfer objects; no movie bytes enter the Git tree.
"""
from __future__ import annotations
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import requests

SLUG = 'nadal-academy-10th-2026-championship-speech'
REPOSITORY = 'robertyang87/tennislive'
EXPECTED_EVIDENCE_SHA = '3717a72f4c91788867da3b20b62763e2347e53631841571ce64a4b86bd30a0e3'
EXPECTED_BYTES = 69347277
EXPECTED_SHA = '4d182944319b68b4bd79f5bdb7195b0c966e7c71c8768a771f40d03517dc933f'

def run(*args):
    subprocess.run(args, check=True)

def json_read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def json_write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def manifest(path):
    if EXPECTED_BYTES <= 0 or not re.fullmatch(r'[a-f0-9]{64}', EXPECTED_SHA):
        raise RuntimeError('Importer not armed: approved RNA10 master QC identity is not pinned')
    m = json_read(path)
    if m['slug'] != SLUG or m['sha256'] != EXPECTED_SHA or m['bytes'] != EXPECTED_BYTES:
        raise ValueError('Request does not identify the approved master')
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', m['date']):
        raise ValueError('Invalid output date')
    chunks = m['chunks']
    if not chunks or sum(c['bytes'] for c in chunks) != EXPECTED_BYTES:
        raise ValueError('Chunk byte totals do not match master')
    for c in chunks:
        if not re.fullmatch(r'[a-f0-9]{40}', c['sha']) or not 0 < c['bytes'] <= 3*1024*1024:
            raise ValueError('Invalid chunk descriptor')
    return m

def git_blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()

def download_chunk(c, cache):
    target = cache / c['sha']
    def valid(data):
        return len(data) == c['bytes'] and git_blob_sha(data) == c['sha']
    if target.exists() and valid(target.read_bytes()):
        return target
    token = os.environ['GH_TOKEN']
    error = None
    for attempt in range(3):
        try:
            response = requests.get(
                f'https://api.github.com/repos/{REPOSITORY}/git/blobs/{c["sha"]}',
                headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'},
                timeout=(15, 90))
            response.raise_for_status()
            data = base64.b64decode(response.json()['content'])
            if not valid(data):
                raise ValueError(f'Chunk integrity failure: {c["sha"]}')
            temporary = target.with_suffix('.part')
            temporary.write_bytes(data)
            temporary.replace(target)
            return target
        except (requests.RequestException, ValueError, KeyError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(3 * (attempt+1))
    raise RuntimeError(f'Could not restore chunk {c["sha"]}') from error

def assemble(request):
    m = manifest(request)
    source = request.parent
    outdir = Path('output/interviews') / SLUG
    if Path(f'data/interview_publish_ledger/{SLUG}.json').exists() or (outdir/'pushed.json').exists():
        raise RuntimeError('Existing publication record: do not overwrite or resend')
    proof_bytes = (source/'evidence-manifest.json').read_bytes()
    if hashlib.sha256(proof_bytes).hexdigest() != EXPECTED_EVIDENCE_SHA:
        raise RuntimeError('Pinned original evidence manifest changed')
    evidence = json.loads(proof_bytes)
    for name, expected in evidence['files'].items():
        if Path(name).name != name or hashlib.sha256((source/name).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Original evidence changed: {name}')
    cache = Path(os.environ.get('RUNNER_TEMP','.'))/'approved-speech-chunks'
    cache.mkdir(parents=True,exist_ok=True); outdir.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        paths=list(pool.map(lambda c:download_chunk(c,cache),m['chunks']))
    film=outdir/f'{SLUG}.mp4'; digest=hashlib.sha256()
    with film.open('wb') as stream:
        for p in paths:
            data=p.read_bytes(); digest.update(data); stream.write(data)
    if film.stat().st_size != EXPECTED_BYTES or digest.hexdigest() != EXPECTED_SHA:
        raise RuntimeError('Assembled approved interview master differs')
    spec=Path('specs/interviews')/f'{SLUG}.json';spec.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source/'spec.json',spec);shutil.copyfile(source/'copy.txt',spec.with_suffix('.xhs.txt'))
    for name in evidence['files']:
        if name not in ('spec.json','copy.txt'):shutil.copyfile(source/name,outdir/name)
    qc=json_read(outdir/'qc_attestation.json');render=json_read(outdir/'render.json')
    if qc['status']!='pass' or qc['film_sha256']!=EXPECTED_SHA or qc['film_bytes']!=EXPECTED_BYTES or qc['spec_sha256']!=evidence['files']['spec.json']:
        raise RuntimeError('Original native QC does not identify this master')
    # Local native QC is written separately; release workflow binds its real
    # bytes into render.json only after the Release asset has been verified.
    if (render.get('qc_attestation_sha256') not in (None,evidence['files']['qc_attestation.json'])
            or render['film_sha256']!=EXPECTED_SHA):
        raise RuntimeError('Original native render/QC binding differs')
    for name,key in [('poster.jpg','poster_sha256'),('cover_visual_attestation.json','cover_visual_attestation_sha256'),(f'{SLUG}.ass','ass_sha256')]:
        if qc[key]!=evidence['files'][name]:raise RuntimeError(f'Native QC artifact identity differs: {name}')
    run(sys.executable,'tools/push_reel.py','--stage','check','--outdir',str(outdir),'--copy',str(spec.with_suffix('.xhs.txt')))
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(film)],text=True))
    if (probe['streams'][0]['width'],probe['streams'][0]['height'])!=(1080,1440):raise RuntimeError('Canvas changed')
    json_write(outdir/'import-provenance.json',{'film_sha256':EXPECTED_SHA,'film_bytes':EXPECTED_BYTES,'original_native_qc_sha256':evidence['files']['qc_attestation.json'],'qc_status':'original-local-pass-preserved','new_audio_review':False,'user_authorization':'User explicitly requested completion of this speech WeChat publication.'})
    output=os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output,'a') as f:f.write(f'outdir={outdir}\nslug={SLUG}\n')
    print('Exact speech master and original native QC bytes verified',flush=True)

def release(request):
    manifest(request);outdir=Path('output/interviews')/SLUG;film=outdir/f'{SLUG}.mp4';tag=f'interview-{SLUG}'
    q=json_read(outdir/'qc_attestation.json')
    if q['film_sha256']!=EXPECTED_SHA or q['status']!='pass':raise RuntimeError('QC identity differs')
    exists=subprocess.run(['gh','release','view',tag,'--json','assets'],capture_output=True,text=True)
    if exists.returncode:
        run('gh','release','create',tag,'--title','赛后开麦 · 纳达尔学院十周年冠军致辞','--notes','用户授权；已验收竖版母版及原生QC原字节导入。')
        assets=[]
    else:assets=json.loads(exists.stdout)['assets']
    asset=next((x for x in assets if x['name']==film.name),None)
    if not asset:run('gh','release','upload',tag,str(film))
    response=requests.get(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'},timeout=60);response.raise_for_status()
    asset=next(x for x in response.json()['assets'] if x['name']==film.name)
    if asset['size']!=EXPECTED_BYTES or asset.get('digest')!=f'sha256:{EXPECTED_SHA}':raise RuntimeError('GitHub asset size/digest differs')
    url=asset['browser_download_url'];remote=requests.get(url,stream=True,timeout=(15,120));remote.raise_for_status();digest=hashlib.sha256();size=0
    for block in remote.iter_content(1024*1024):digest.update(block);size+=len(block)
    if size!=EXPECTED_BYTES or digest.hexdigest()!=EXPECTED_SHA:raise RuntimeError('Release remote GET differs from approved master')
    json_write(outdir/'release-verification.json',{'video_url':url,'bytes':size,'sha256':digest.hexdigest(),'asset_digest':asset['digest'],'method':'remote-streaming-GET'})
    render=json_read(outdir/'render.json');render.update(video_url=url,video_bytes=size,film_sha256=q['film_sha256'],release_asset_digest=asset['digest'],qc_attestation_sha256=hashlib.sha256((outdir/'qc_attestation.json').read_bytes()).hexdigest());json_write(outdir/'render.json',render)
    run(sys.executable,'tools/push_reel.py','--stage','page','--outdir',str(outdir),'--copy',f'specs/interviews/{SLUG}.xhs.txt')
    print(f'Release verified and copy page generated: {url}',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['assemble','release']);p.add_argument('--request',type=Path,required=True);a=p.parse_args()
    if os.environ.get('GITHUB_REPOSITORY',REPOSITORY)!=REPOSITORY:raise SystemExit('Wrong repository')
    {'assemble':assemble,'release':release}[a.stage](a.request)
