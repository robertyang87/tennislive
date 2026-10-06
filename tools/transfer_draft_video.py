#!/usr/bin/env python3
"""Pinned Git-blob transfer into an existing draft. No publishing or Git writes."""
import argparse,base64,hashlib,json,os,re,subprocess
from pathlib import Path
import requests
REPO='robertyang87/tennislive'
MAX_CHUNK=3*1024*1024
HEX64=re.compile(r'^[0-9a-f]{64}$')
HEX40=re.compile(r'^[0-9a-f]{40}$')
def sha(data):return hashlib.sha256(data).hexdigest()

def validate_request(path, pinned, expected_release_id):
    raw=Path(path).read_bytes()
    if not HEX64.fullmatch(pinned) or sha(raw)!=pinned:raise ValueError('Request SHA mismatch')
    r=json.loads(raw);slug=r.get('slug','')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug):raise ValueError('Invalid slug')
    if Path(path).as_posix()!=f'data/draft_video_transfers/{slug}/request.json':raise ValueError('Request path/slug mismatch')
    if r.get('repo')!=REPO or r.get('release_id')!=expected_release_id:raise ValueError('Repository/release identity mismatch')
    if r.get('tag')!=f"{r.get('kind')}-{slug}" or r.get('kind') not in ['explainer','reel','interview']:raise ValueError('Tag/slug mismatch')
    if r.get('asset_name')!=slug+'.mp4':raise ValueError('Asset/slug mismatch')
    if not HEX64.fullmatch(r.get('movie_sha256','')) or not isinstance(r.get('movie_bytes'),int) or r['movie_bytes']<=0:raise ValueError('Invalid movie identity')
    chunks=r.get('chunks',[])
    if not chunks or [c.get('index') for c in chunks]!=list(range(len(chunks))):raise ValueError('Ordered chunks required')
    if sum(c.get('bytes',0) for c in chunks)!=r['movie_bytes']:raise ValueError('Chunk total size mismatch')
    for c in chunks:
        if not isinstance(c.get('bytes'),int) or not 0<c['bytes']<=MAX_CHUNK or not HEX40.fullmatch(c.get('git_blob_sha','')) or not HEX64.fullmatch(c.get('sha256','')):raise ValueError('Invalid chunk binding')
    return r

def require_draft(release,r):
    if release.get('id')!=r['release_id'] or release.get('tag_name')!=r['tag'] or release.get('draft') is not True:raise ValueError('Existing release is not the pinned draft')

def validate_chunk(data,c):
    gitsha=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if len(data)!=c['bytes'] or sha(data)!=c['sha256'] or gitsha!=c['git_blob_sha']:raise ValueError('Chunk actual bytes/SHA mismatch')

def validate_master(path,r):
    if path.stat().st_size!=r['movie_bytes'] or sha(path.read_bytes())!=r['movie_sha256']:raise ValueError('Assembled movie actual bytes/SHA mismatch')

def verify_asset_metadata(asset,r):
    if asset.get("size")!=r["movie_bytes"] or asset.get("digest")!="sha256:"+r["movie_sha256"]:
        raise ValueError("Existing/uploaded same-name asset identity differs; refuse clobber")

def run(a,receipt):
    receipt['phase']='validate_request'
    r=validate_request(a.request,a.request_sha256,a.expected_release_id)
    token=os.environ.get('GH_TOKEN')
    if not token:raise ValueError('Runner GH_TOKEN required')
    session=requests.Session();session.headers.update({'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
    base=f'https://api.github.com/repos/{REPO}'
    def get_json(path):
        response=session.get(base+path,timeout=60);response.raise_for_status();return response.json()
    receipt['phase']='verify_existing_draft'
    release=get_json(f"/releases/{r['release_id']}");require_draft(release,r)
    receipt['phase']='assemble_pinned_blobs'
    a.workdir.mkdir(parents=True,exist_ok=True);movie=a.workdir/r['asset_name']
    with movie.open('wb') as output:
        for c in r['chunks']:
            blob=get_json('/git/blobs/'+c['git_blob_sha'])
            if blob.get('sha')!=c['git_blob_sha'] or blob.get('encoding')!='base64':raise ValueError('Unexpected Git blob identity/encoding')
            data=base64.b64decode(blob['content']);validate_chunk(data,c);output.write(data)
    validate_master(movie,r)
    # Recheck state immediately before mutation; never create or publish.
    release=get_json(f"/releases/{r['release_id']}");require_draft(release,r)
    same=[x for x in release.get('assets',[]) if x['name']==r['asset_name']]
    if len(same)>1:raise ValueError('Duplicate asset names')
    if same:
        asset=same[0]
        verify_asset_metadata(asset,r)
    else:
        receipt['phase']='upload_to_existing_draft'
        subprocess.run(['gh','release','upload',r['tag'],str(movie),'--repo',REPO],check=True)
        release=get_json(f"/releases/{r['release_id']}");require_draft(release,r)
        assets=[x for x in release.get('assets',[]) if x['name']==r['asset_name']]
        if len(assets)!=1:raise ValueError('Uploaded asset absent/ambiguous')
        asset=assets[0]
    verify_asset_metadata(asset,r)
    receipt['phase']='verify_complete_remote_streaming_GET'
    digest=hashlib.sha256();count=0
    with session.get(base+f"/releases/assets/{asset['id']}",headers={'Accept':'application/octet-stream'},stream=True,timeout=120) as response:
        response.raise_for_status()
        for block in response.iter_content(1024*1024):digest.update(block);count+=len(block)
    if count!=r['movie_bytes'] or digest.hexdigest()!=r['movie_sha256']:raise ValueError('Remote streaming GET SHA/bytes mismatch')
    require_draft(get_json(f"/releases/{r['release_id']}"),r)
    receipt.update(phase='verified_existing_draft_asset',status='PASS_DRAFT_ONLY',request_sha256=a.request_sha256,repo=REPO,release_id=r['release_id'],tag=r['tag'],asset_id=asset['id'],asset_name=r['asset_name'],movie_sha256=digest.hexdigest(),movie_bytes=count,asset_digest=asset['digest'],draft=True,published=False,git_written=False,wechat_sent=False)

def main():
    p=argparse.ArgumentParser();p.add_argument('--request',required=True);p.add_argument('--request-sha256',required=True);p.add_argument('--expected-release-id',required=True,type=int);p.add_argument('--workdir',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path);a=p.parse_args()
    receipt={'status':'FAIL','published':False,'git_written':False,'wechat_sent':False}
    try:run(a,receipt)
    except Exception as error:
        # No token, signed URLs or response request headers enter the receipt.
        receipt['error_type']=type(error).__name__;receipt['error']='Transfer failed; inspect Actions step for phase. No publication attempted.'
        raise SystemExit('Draft transfer failed at '+receipt.get('phase','startup')+' ('+type(error).__name__+'). No publication attempted.') from None
    finally:a.receipt.parent.mkdir(parents=True,exist_ok=True);a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':main()
