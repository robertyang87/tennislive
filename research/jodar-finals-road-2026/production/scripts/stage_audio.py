import json,hashlib,shutil,sys
from pathlib import Path
R=Path('/dev/shm/jodar-production/native');B=Path('/workspace/jodar-finals-production');slug='jodar-finals-road-2026';sys.path.insert(0,str(R/'tools'));from foreground_audio_gate import plan_hash,require
dest=R/f'research/{slug}/audio';shutil.copytree(B/'research/audio',dest,dirs_exist_ok=True)
p=R/f'specs/reels/{slug}.json';spec=json.load(open(p));rows=[];changes=[]
def relative(v):
 if isinstance(v,dict):
  return {k:(f'research/{slug}/audio/'+x.split('/research/audio/',1)[1] if k in ['path','script_path'] and isinstance(x,str) and '/research/audio/' in x else relative(x)) for k,x in v.items()}
 if isinstance(v,list):return [relative(x) for x in v]
 return v
for i,s in enumerate(spec['segments']):
 if not s.get('source'):continue
 source=s['source'];src=B/f'research/audio/transcripts/{source}.json'
 if not src.exists():raise FileNotFoundError(src)
 raw=src.read_bytes();packet=json.loads(raw);native=relative(packet);out=R/f'data/audio_transcripts/{slug}/{source}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(native,ensure_ascii=False,indent=2)+'\n')
 handoff=json.load(open(B/f'research/audio/{source}-native-handoff.json'));s['quote']=packet.get('native_quote',handoff.get('quote',[]));s.pop('_quote_skip_why',None)
 rows.append({'index':i,'transcript_path':str(out.relative_to(R)),'transcript_sha256':hashlib.sha256(out.read_bytes()).hexdigest()});changes.append({'source':source,'original_packet_sha256':hashlib.sha256(raw).hexdigest(),'native_packet_sha256':rows[-1]['transcript_sha256'],'change':'Only raw/script path relocation to actual preserved repository evidence; conclusions/sourceSHA/rawSHA/utterances unchanged.'})
p.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n');review={'schema':'tennislive.foreground-audio-review.v1','plan_sha256':plan_hash(spec),'segments':rows,'method_note':'Five true selected source windows with fourteen source caption cues; AO court-only window and RG explicitly nonverbatim result announcement preserve lexical limits. Marrakech and Wimbledon use approved same-event photo/native-card fallbacks and are not selected video sources. No human listening claimed.'};o=R/f'data/audio_reviews/{slug}.json';o.parent.mkdir(parents=True,exist_ok=True);o.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n');(B/'production/audio-native-staging-proof.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n');print('foreground gate PASS',len(require(spec,root=R)))
