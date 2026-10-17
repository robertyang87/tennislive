from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess,json,base64,hashlib,time,zipfile,sys
ROOT=Path('/workspace/scratch');REPO='robertyang87/tennislive';SLUG='swiatek-li-wuhan-2026-qf';BUNDLE='14af885578f8b30a96654521ae767a50c26b5e59bd70cd9881ca3322ebdf5258';TAG='reel-review-'+SLUG+'-'+BUNDLE[:16];BRANCH='codex/iga-qf-final-review-archive'
CONFIG=ROOT/'iga-qf-final-review-transport-config.json';CACHE=ROOT/'iga-qf-final-review-blob-cache.json';JOURNAL=ROOT/'iga-qf-final-review-transport.json'

def api(route,payload=None,method='POST'):
 for attempt in range(3):
  cmd=['gh','api','repos/'+REPO+'/'+route+('?'if'?'not in route else'&')+'transport_nonce='+str(time.time_ns()),'-H','Cache-Control: no-cache']
  if payload is not None:cmd+=['--method',method,'--input','-']
  p=subprocess.run(cmd,input=json.dumps(payload)if payload is not None else None,text=True,capture_output=True)
  if p.returncode==0:return json.loads(p.stdout)
  if attempt==2 or not any(x in p.stderr for x in ['401','403','500','502','503','504']):raise RuntimeError(p.stderr[-700:])
  if '401'in p.stderr:subprocess.run(['gh','api','user','--jq','.login'],capture_output=True,check=False)
 raise RuntimeError('bounded GitAPI attempts exhausted')

def prepare():
 config=json.loads(CONFIG.read_text());assert config['all_final_bytes_confirmed'] is True;assert config['bundle_sha256']==BUNDLE;MOVIE=config['movie_sha256'];assert isinstance(MOVIE,str) and len(MOVIE)==64 and all(c in '0123456789abcdef'for c in MOVIE)
 assert len(config['artifacts'])==2;assert {e['name']for e in config['artifacts']}=={'pronunciation-evidence.zip','visual-qc-evidence.zip'}
 cache=json.loads(CACHE.read_text())if CACHE.exists()else{};items=[]
 for entry in config['artifacts']:
  p=Path(entry['path']);raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==entry['sha256'] and len(raw)==entry['bytes'];assert entry['name']in['pronunciation-evidence.zip','visual-qc-evidence.zip']
  with zipfile.ZipFile(p)as z:
   assert z.testzip()is None;assert not any(x.lower().endswith('.mp4')for x in z.namelist())
  parts=[raw[i:i+16*1024*1024]for i in range(0,len(raw),16*1024*1024)]
  def blob(part):
   key=hashlib.sha256(part).hexdigest()
   if key in cache:return key,cache[key]
   return key,api('git/blobs',{'encoding':'base64','content':base64.b64encode(part).decode()})['sha']
  with ThreadPoolExecutor(max_workers=3)as pool:results=list(pool.map(blob,parts))
  for key,value in results:cache[key]=value
  CACHE.write_text(json.dumps(cache,indent=2)+'\n')
  items.append({**entry,'sha256':sha,'parts':[{'sha256':key,'blob':value}for key,value in results],'url':'https://github.com/'+REPO+'/releases/download/'+TAG+'/'+entry['name']})
 w='''name: Preserve finite actual Swiatek Wuhan QF review evidence (isolated)
on:
  workflow_dispatch:
permissions:
  contents: write
jobs:
  preserve:
    runs-on: ubuntu-latest
    timeout-minutes: 8
    steps:
      - name: Preserve exact finite reviewed archives (transport only)
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
'''
 entries=[]
 for i,item in enumerate(items):
  for j,part in enumerate(item['parts']):
   entries.append({'path':f'.codex-review-transport/iga-qf-final-review/{i}/part-{j:02d}.bin','mode':'100644','type':'blob','sha':part['blob']})
   w+=f"          gh api repos/{REPO}/git/blobs/{part['blob']} > /tmp/blob-{i}-{j}.json\n"
  w+=f"          python - <<'PY_ARCHIVE_{i}'\n          from pathlib import Path\n          import json,base64,hashlib\n          parts=[]\n"
  for j,part in enumerate(item['parts']):w+=f"          b=base64.b64decode(json.loads(Path('/tmp/blob-{i}-{j}.json').read_text())['content'])\n          assert hashlib.sha256(b).hexdigest()=='{part['sha256']}'\n          parts.append(b)\n"
  w+=f"          b=b''.join(parts)\n          assert len(b)=={item['bytes']} and hashlib.sha256(b).hexdigest()=='{item['sha256']}'\n          Path('/tmp/{item['name']}').write_bytes(b)\n          print('Exact archive bytes verified',len(b),'{item['sha256']}')\n          PY_ARCHIVE_{i}\n"
 w+=f"          gh release view {TAG} >/dev/null 2>&1 || gh release create {TAG} --target '${{{{ github.sha }}}}' --title 'Swiatek Wuhan QF finite actual review evidence' --notes 'Actual frozen native pronunciation and sampled actual movie evidence. Transport success is not a review/QC approval or delivery receipt.' --latest=false\n"
 w+=f"          gh release upload {TAG} /tmp/pronunciation-evidence.zip /tmp/visual-qc-evidence.zip\n"
 base=api('git/ref/heads/codex/iga-qf-o8f')['object']['sha'];tree=api('git/commits/'+base)['tree']['sha'];entries.append({'path':'.github/workflows/frame-grab.yml','mode':'100644','type':'blob','content':w});newtree=api('git/trees',{'base_tree':tree,'tree':entries})['sha'];commit=api('git/commits',{'message':'transport: preserve finite exact Swiatek Wuhan QF actual review archives','tree':newtree,'parents':[base]})['sha'];api('git/refs',{'ref':'refs/heads/'+BRANCH,'sha':commit});JOURNAL.write_text(json.dumps({'branch':BRANCH,'head':commit,'tag':TAG,'bundle_sha256':BUNDLE,'movie_sha256':MOVIE,'artifacts':items},indent=2)+'\n');print('REACHABLE_PARTS_BRANCH_READY',BRANCH,commit,flush=True)
 subprocess.run(['gh','workflow','run','frame-grab.yml','--ref',BRANCH],check=True)

def finalize(run_id):
 journal=json.loads(JOURNAL.read_text());run=json.loads(subprocess.check_output(['gh','run','view',str(run_id),'--repo',REPO,'--json','status,conclusion,headSha'],text=True));assert run['status']=='completed'and run['conclusion']=='success'and run['headSha']==journal['head'];release=api('releases/tags/'+TAG);assert release['tag_name']==TAG
 for item in journal['artifacts']:
  asset=next(a for a in release['assets']if a['name']==item['name']);assert asset['state']=='uploaded'and asset['size']==item['bytes']and asset['digest']=='sha256:'+item['sha256'];p=Path(item['manifest_path']);d=json.loads(p.read_text());assert d.get('film_sha256',journal['movie_sha256'])==journal['movie_sha256'];assert d.get('bundle_sha256',BUNDLE)==BUNDLE;assert d.get('sha256',item['sha256'])==item['sha256']and d.get('bytes',item['bytes'])==item['bytes'];d.update(release_tag=TAG,file_name=item['name'],url=item['url'],sha256=item['sha256'],bytes=item['bytes']);d['publication_upload_pending']=False;d['transport']={'status':'uploaded_exact_bytes_verified','run_url':'https://github.com/'+REPO+'/actions/runs/'+str(run_id),'asset_api_url':asset['url'],'asset_id':asset['id'],'service_digest':asset['digest'],'service_state':asset['state'],'service_size_bytes':asset['size'],'quality_approval':False,'note':'Transport verifies exact archive bytes only. Existing editorial/audio/visual review status is preserved.'};p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');item['release_asset']=asset
 journal['transport_run']='https://github.com/'+REPO+'/actions/runs/'+str(run_id);journal['transport_status']='uploaded_exact_bytes_verified_not_quality_approval';JOURNAL.write_text(json.dumps(journal,indent=2)+'\n');print('BOTH_FINAL_REVIEW_ARCHIVES_SERVICE_DIGEST_SIZE_VERIFIED',flush=True)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='finalize':finalize(int(sys.argv[2]))
 elif len(sys.argv)==2 and sys.argv[1]=='prepare':prepare()
 else:raise SystemExit('Explicit command required: prepare (only with both final sealed artifacts) or finalize RUN_ID')
