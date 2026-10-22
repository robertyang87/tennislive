from pathlib import Path
import json,hashlib,subprocess,sys
R=Path('/workspace/svitolina-finals-production');P=Path('/workspace/tennislive-svitolina');S=P/'specs/reels/svitolina-finals-2026.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
spec=json.load(open(S));cursor=1.2;rows={}
for i,s in enumerate(spec['segments']):
 d=s.get('seconds',s.get('end',0)-s.get('start',0));rows[s['_id']]={'s':s,'offset':cursor,'length':d,'index':i};cursor+=d
mode=sys.argv[1];tag=sys.argv[2];samples=[]
def add(key,t,why):
 r=rows[key];t=max(.08,min(r['length']-.08,t));samples.append({'id':key,'film_time':round(r['offset']+t,4),'segment_time':round(t,4),'why':why})
for k,r in rows.items():
 s=r['s']
 if mode=='labels':
  if s.get('inset'):
   lo=s['inset']['show_after'];hi=lo+s['inset']['show_for']
   for t,w in [(lo+.36,'label-first-full'),((lo+hi)/2,'label-middle'),(hi-.40,'label-last-full'),(hi+.08,'label-after')]:add(k,t,w)
  if k=='wimbledon-r1':add(k,379.10-s['start'],'critical-white-hat-below-label')
  elif k=='cold-rome':
   for j in range(9):add(k,.3+j*(r['length']-.6)/8,'person-nine')
  elif k=='card-qualification':add(k,r['length']/2,'poster-full')
 elif mode=='cues':
  if 'start'in s:
   for j,c in enumerate(s.get('quote',[])):add(k,(c['at']+c['end'])/2,'cue-'+str(j+1))
  else:add(k,r['length']/2,'narration-static')
args=[]
for key,path in json.load(open(R/'production/native-source-paths.json')).items():args+=['--source',key+'='+path]
ph=sha(S);batches=[]
for n in range(0,len(samples),24):
 chunk=samples[n:n+24];out=R/f'native-preview-{mode}-{tag}-batch{n//24+1}';log=R/f'production/preview-{mode}-{tag}-{n//24+1}.log';assert not out.exists();assert sha(S)==ph
 cmd=[sys.executable,'tools/preview_reel_captions.py','--spec',str(S),'--outdir',str(out),'--max-frames','24','--at',','.join(str(x['film_time'])for x in chunk),*args]
 with log.open('w')as f:subprocess.run(cmd,cwd=P,stdout=f,stderr=subprocess.STDOUT,check=True)
 m=out/'preview_manifest.json';batches.append({'manifest':str(m),'manifest_sha256':sha(m),'requests':chunk});print(out,flush=True)
(R/f'production/native-{mode}-{tag}-index.json').write_text(json.dumps({'spec_sha256':ph,'final_film_qc':False,'batches':batches},ensure_ascii=False,indent=2)+'\n')
