from pathlib import Path
import subprocess,json,hashlib,time,requests,zipfile,io,stat
R=Path('/workspace/tennislive-efficiency');S='swiatek-li-wuhan-2026-qf';OUT=R/'output/2026-10-16/reel'/S;D=Path('/workspace/scratch/iga-qf-final');D.mkdir(exist_ok=True);sha=lambda b:hashlib.sha256(b).hexdigest();deadline=time.monotonic()+600
while True:
 p=subprocess.run(['gh','api',f'repos/robertyang87/tennislive/releases/tags/reel-{S}?review_nonce={time.time_ns()}','-H','Cache-Control: no-cache'],text=True,capture_output=True)
 if p.returncode==0:
  rel=json.loads(p.stdout);assets=[x for x in rel['assets']if x['name']=='recovered-native-metadata.zip'and x['state']=='uploaded']
  if len(assets)==1:break
 elif '401'in p.stderr:subprocess.run(['gh','api','user','--jq','.login'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 elif '404'not in p.stderr:raise RuntimeError(p.stderr[-500:])
 if time.monotonic()>deadline:raise RuntimeError('Bounded waiting window finished, not a QC verdict')
 time.sleep(10)
a=assets[0];res=requests.get(a['browser_download_url']+'?review='+str(time.time_ns()),timeout=(20,180));res.raise_for_status();b=res.content;assert len(b)==a['size']and'sha256:'+sha(b)==a['digest'];(D/a['name']).write_bytes(b)
with zipfile.ZipFile(io.BytesIO(b))as z:
 assert z.testzip()is None
 for x in z.infolist():
  q=Path(x.filename);assert not q.is_absolute()and'..'not in q.parts and not stat.S_ISLNK(x.external_attr>>16)
 inp=json.loads(z.read('render_inputs.json'));assert inp['spec_sha256']==sha((R/f'specs/reels/{S}.json').read_bytes());qc=json.loads(z.read('qc_attestation.json'));assert qc['status']=='pass'and qc['film_sha256']==inp['film_sha256'];pr=json.loads(z.read('recovery_provenance.json'));assert pr['original_run_id']==38912186473 and pr['recovery_run_id']==38913697827 and pr['same_movie_bytes_no_reencoding']is True
 OUT.mkdir(parents=True,exist_ok=True);z.extractall(OUT)
(D/'metadata-download-receipt.json').write_text(json.dumps({'service_asset':a,'sha256':sha(b),'bytes':len(b),'native_original_run':38912186473,'recovery_run':38913697827,'film_sha256':inp['film_sha256'],'extracted_to':str(OUT)},ensure_ascii=False,indent=2)+'\n')
print('EXACT_RECOVERED_METADATA_READY',inp['film_sha256'],inp['film_bytes'],flush=True)
subprocess.run(['python','/workspace/scratch/iga-qf-download-current.py','--run','38912186473','--dest',str(D)],check=True)
