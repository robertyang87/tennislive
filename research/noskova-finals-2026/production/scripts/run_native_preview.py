from pathlib import Path
import sys,json,hashlib,os,argparse
P=Path('/workspace/tennislive-noskova');R=Path('/workspace/noskova-finals-production');sys.path[:0]=[str(P/'src'),str(P/'tools')]
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca();os.environ['TENNISLIVE_TTS_BACKEND']='edge'
import preview_reel_captions as pv
from tennislive.video.tts import tts_bundle_session
ap=argparse.ArgumentParser();ap.add_argument('batch',choices=['labels','quotes1','quotes2','chapters','tails','madrid']);ap.add_argument('--expect-sha');args=ap.parse_args();sp=P/'specs/reels/noskova-finals-2026.json';spec=json.load(open(sp));sha=hashlib.sha256(sp.read_bytes()).hexdigest()
if args.expect_sha:assert sha==args.expect_sha,(sha,args.expect_sha)
source_paths=json.load(open(R/'production/native-source-paths.json'));offsets=[];t=1.2
for s in spec['segments']:offsets.append(t);t+=s.get('seconds',s.get('end',0)-s.get('start',0))
labels=[];quotes=[];chapters=[];tails=[]
for i,s in enumerate(spec['segments']):
 base=offsets[i]
 if 'inset'in s:
  a=s['inset']['show_after'];b=a+s['inset']['show_for'];labels += [base+a+.2,base+(a+b)/2,base+b-.12,base+b+.16]
 if 'quote'in s:
  tails.append(base+s['quote'][-1]['end']-.04)
  for q in s['quote']:quotes.append(base+(q['at']+q['end'])/2)
 if 'title_card'in s:chapters.append(base+s['seconds']/2)
 elif s.get('frame')=='court':
  chapters.append(base+.16);pd=s['_point_evidence']['dead_by'];chapters.append(base+(pd-s['start'])+.2)
frames={'labels':labels,'quotes1':quotes[:23],'quotes2':quotes[23:],'chapters':chapters,'tails':tails,'madrid':[offsets[7]+v for v in [29.56,32.5,33.5,34.98]]}[args.batch];assert len(frames)<=24,len(frames);out=R/('native-preview-freeze-'+args.batch);sys.argv=['preview_reel_captions.py','--spec',str(sp),'--outdir',str(out),'--max-frames','24','--at',','.join(f'{x:.3f}'for x in frames)]
for key,path in source_paths.items():sys.argv+=['--source',f'{key}={path}']
req=json.load(open(R/'production/tts-requests.json'));print('Native partial preview',args.batch,'frames',len(frames),'spec',sha,flush=True)
with tts_bundle_session(input_path=R/'production/frozen-tts.zip',expected_requests=req):pv.main()
