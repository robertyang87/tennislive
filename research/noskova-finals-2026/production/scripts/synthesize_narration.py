from pathlib import Path
import sys,json,subprocess
P=Path('/workspace/tennislive-noskova');R=Path('/workspace/noskova-finals-production');sys.path[:0]=[str(P/'src'),str(P/'tools')]
from tennislive.video.tts import tts_one,tts_bundle_session,tts_request
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION as OUTRO_NARRATION
from tennislive.localca import trust_local_proxy_ca
trust_local_proxy_ca()
plan=json.loads((R/'production/narration-plan.json').read_text());o=R/'production/tts';o.mkdir(exist_ok=True);req=[tts_request(speakable(x['text']),'zh-CN-YunjianNeural','+6%','+0Hz','','',0.0)for x in plan]
req.append(tts_request(speakable(OUTRO_NARRATION),'zh-CN-YunjianNeural','+6%','+0Hz','','',0.0))
(R/'production/tts-requests.json').write_text(json.dumps(req,ensure_ascii=False,indent=2)+'\n')
with tts_bundle_session(output_path=R/'production/frozen-tts.zip',expected_requests=req,metadata={'slug':'noskova-finals-2026','scope':'complete semantic units; not voice-quality approval'}):
 for x,r in zip(plan,req):
  p=o/(x['id']+'.mp3');marks=tts_one(r['text'],p,r['voice'],r['rate'],r['pitch'],lead_pause=0.0);p.with_suffix('.words.json').write_text(json.dumps(marks,ensure_ascii=False));dur=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)]));x.update(tts_path=str(p),audio_seconds=dur,seconds=round(dur+.2,2),voice={'pitch':'+0Hz','_why':'完整语义、自然云健+6%，未人工拉伸。'});print(x['id'],dur,flush=True)
 p=o/'outro-brand.mp3';r=req[-1];marks=tts_one(r['text'],p,r['voice'],r['rate'],r['pitch'],lead_pause=0.0);p.with_suffix('.words.json').write_text(json.dumps(marks,ensure_ascii=False));print('brand outro actual',float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(p)])),flush=True)
(R/'production/narration-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');print('Total narration',sum(x['seconds']for x in plan),flush=True)
