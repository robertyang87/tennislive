from pathlib import Path
import json,subprocess,sys
R=Path('/workspace/pegula-finals-production');REPO=Path('/workspace/tennislive');s=json.loads((REPO/'specs/reels/pegula-finals-2026.json').read_text());sources=json.loads((R/'native-source-paths.json').read_text());group=sys.argv[1];tag=sys.argv[2] if len(sys.argv)>2 else 'v2';out=R/f'native-preview-{group}-{tag}';rows={};cur=1.2
for i,seg in enumerate(s['segments']):
 length=seg.get('seconds',seg.get('end',0)-seg.get('start',0));rows[seg['_id']]=(cur,length,seg);cur+=length
samples=[]
def add(key,relative,why):
 offset,length,seg=rows[key];relative=max(.05,min(length-.06,relative));samples.append({'id':key,'film_time':round(offset+relative,3),'why':why})
if group=='early':
 for key in ['ao','dubai-final','miami-qf','charleston-final','berlin-sf']:
  _,_,seg=rows[key];a=seg['inset'];lo=a['show_after'];hi=lo+a['show_for']
  for t,why in [(lo-.08,'before-label'),((lo+hi)/2,'label-middle'),(hi-.08,'label-last'),(hi+.08,'after-label')]:add(key,t,why)
 for key in ['cold-quote','dubai-speech','card-intro','card-clay']:add(key,rows[key][1]/2,'person-or-plain-title')
elif group in ['late','late-end']:
 for key in (['dc-final','cincy-sf','cincy-final','us-qf','us-sf','wuhan-mp3'] if group=='late' else []):
  _,_,seg=rows[key];a=seg['inset'];lo=a['show_after'];hi=lo+a['show_for']
  for t,why in [(lo-.08,'before-label'),((lo+hi)/2,'label-middle'),(hi-.08,'label-last'),(hi+.08,'after-label')]:add(key,t,why)
 for key,t in ([] if group=='late' else [('us-qf-interview',2),('us-qf-interview',12),('us-qf-reaction',6),('card-qualification',5),('card-ending',4),('wuhan-final',18)]):add(key,t,'person-english-evidence-or-plain-title')
else:raise ValueError(group)
assert len(samples)<=24
(R/f'preview-{group}-{tag}-requested.json').write_text(json.dumps(samples,ensure_ascii=False,indent=2)+'\n')
args=[sys.executable,'tools/preview_reel_captions.py','--spec','specs/reels/pegula-finals-2026.json','--outdir',str(out),'--max-frames','24','--at',','.join(str(x['film_time']) for x in samples)]
for k,p in sources.items():args+=['--source',f'{k}={p}']
log=(R/f'preview-{group}-{tag}.txt').open('w');result=subprocess.run(args,cwd=REPO,stdout=log,stderr=subprocess.STDOUT);print(group,result.returncode,out);raise SystemExit(result.returncode)
