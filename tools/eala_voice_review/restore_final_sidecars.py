import hashlib,json,sys,zipfile,os
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'src')]
from tennislive.video import tts
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
ROOT=Path(__file__).resolve().parents[2];slug='eala-shi';OD=Path(sys.argv[1]);E=ROOT/'data/evidence'/slug/'voice';sp=json.loads((ROOT/'specs/reels'/f'{slug}.json').read_text());rd=json.loads((OD/'render.json').read_text());rows=[]
items=[(f'第 {i+1} 段',s['narration'],OD/f'voice_{i:02}.mp3',s.get('voice')or{})for i,s in enumerate(sp['segments'])if s.get('narration')]+([('片尾',NARRATION,OD/'voice_outro.mp3',{})] if sp.get('outro',True) else [])
sha=lambda x:hashlib.sha256(x).hexdigest()
for label,text,p,v in items:
 key=tts.tts_content_key(speakable(text),rd['narration_voice'],v.get('rate')or rd['narration_rate'],v.get('pitch')or'+0Hz',v.get('style')or'',v.get('styledegree')or'',float(v.get('lead_pause')or 0));cache=Path(os.environ.get('TENNISLIVE_TTS_CACHE',str(Path.home()/'.cache/tennislive-tts')))/f'{key}-edge-v2.zip'
 with zipfile.ZipFile(cache)as z:audio=z.read('audio.mp3');raw=z.read('marks.json')
 assert p.read_bytes()==audio,f'Wrong current native cache {label}'
 q=p.with_suffix('.words.json');before=q.read_bytes()if q.exists()else None
 if before!=raw:q.write_bytes(raw)
 assert q.read_bytes()==raw
 rows.append({'label':label,'actual_voice_path':str(p),'actual_mp3_sha256':sha(audio),'cache_key':key,'paired_marks_path':str(q),'paired_marks_sha256':sha(raw),'sidecar_previous_sha256':sha(before)if before is not None else None,'restored':before!=raw,'restoration_source':'Exact marks.json bytes from matching native ZIP audio; metadata repair, no speech or movie change.'})
p=E/'voice-word-sidecar-restoration.json';history=json.loads(p.read_text())if p.exists()else None
r={'schema':'tennislive.native-word-sidecar-restoration.v1','final_spec_sha256':sha((ROOT/'specs/reels'/f'{slug}.json').read_bytes()),'items':rows,'previous_restoration_history':history,'method':'Verify exact final actual MP3 against corresponding text/voice/rate/style native ZIP, then preserve or restore exact ZIP marks.json to physical voice.words.json. Native cache-hit materializes audio and returns marks but may leave sidecar missing or stale. No MP4/QC/input bytes modified.','human_listening_claimed':False}
p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'count':len(rows),'restored_count':sum(x['restored']for x in rows)}))
