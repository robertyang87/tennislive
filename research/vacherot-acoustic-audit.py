#!/usr/bin/env python3
"""Episode-local full-context acoustic evidence, never an approval bypass.
Run through the authorized HTTP proxy wrapper. Native measure_polyphone
algorithm is used unchanged, with complete production speakable paragraphs.
Every polyphonic position is inventoried, including static-default positions.
One common contrasting reading is measured per position; other live readings
are explicitly listed as unmeasured. Tone-neutral positions without reliable
single-reading references remain pending. No outcome is coerced to pass.
"""
import concurrent.futures as cf
import hashlib,json,pathlib,shutil,sys,threading,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import check_polyphones as cp
import measure_polyphone as mp
from tennislive.video.explainer import speakable
VOICE='zh-CN-YunjianNeural';RATE='+6%'
DEST=ROOT/'research/vacherot-acoustic';DEST.mkdir(parents=True,exist_ok=True)
SPEC=ROOT/'specs/reels/vacherot-shanghai-one-year.json'
texts=cp.spoken_texts(spec_path=SPEC)
# Only stable material shared with production: snapshot exact voice inputs.
manifest={'voice':VOICE,'rate':RATE,'method':'Native measure_polyphone MFCC+delta, full-utterance DTW, F0, leave-one-out references. Exact complete speakable paragraphs; no ASR claim.','human_listening':'not performed','status':'running','segments':[],'targets':[]}
for sp in texts:
 spoken=speakable(sp.text)
 assert len(spoken)==len(sp.text)
 manifest['segments'].append({'label':sp.label,'display_text':sp.text,'tts_text':spoken,'sha256':hashlib.sha256(spoken.encode()).hexdigest()})
 readings,words,lex,touched=cp._readings(sp.text)
 for i,ch in enumerate(sp.text):
  yes,defaults,live=cp.poly_info(ch)
  if not yes or ch in cp._SANDHI|cp._FREE or not readings[i]:continue
  intended=readings[i];override=None
  if ch=='都' and sp.text[max(0,i-1):i+1]!='成都':intended='dou1';override='Context: universal 都, not capital city 都.'
  if ch=='得' and '仍得救下' in sp.text:intended='dei3';override='Context: modal requirement, not 得救 compound.'
  others=[r for r in live if r!=intended and not r.endswith('5')]
  if not others:continue
  manifest['targets'].append({'id':f'target-{len(manifest["targets"])+1:03}','label':sp.label,'display_char':ch,'actual_tts_char':spoken[i],'position':i,'context':sp.text[max(0,i-6):i+7],'word':words[i] or ch,'intended':intended,'common_contrast':others[0],'unmeasured_other_readings':others[1:],'semantic_override':override,'tts_text':spoken})
manifest['target_count']=len(manifest['targets'])
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
# Persist a playable copy of every exact final paragraph before measuring.
def original_audio(seg):
 try:
  p,marks=mp.synth(seg['tts_text'],VOICE,RATE)
  name=seg['label'].replace(' ','-')
  out=DEST/(name+'.mp3');shutil.copy2(p,out)
  (DEST/(name+'.marks.json')).write_text(json.dumps(marks,ensure_ascii=False,indent=2)+'\n')
  return {'label':seg['label'],'audio':str(out),'marks':str(DEST/(name+'.marks.json')),'status':'synthesised'}
 except Exception as e:return {'label':seg['label'],'status':'error','error':str(e)}
with cf.ThreadPoolExecutor(max_workers=4) as pool:audio=list(pool.map(original_audio,manifest['segments']))
manifest['audio']=audio
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('Whole-paragraph synthesis',len(audio),'segments;',manifest['target_count'],'polyphonic positions',flush=True)
def target_run(t):
 try:
  ok,_=mp.suggest_homophones(t['intended'],exclude=t['actual_tts_char'],k=2)
  bad,_=mp.suggest_homophones(t['common_contrast'],exclude=t['actual_tts_char'],k=2)
  if not ok or not bad:
   out={**t,'verdict':'skipped','reason':'No usable single-reading reference for one side','ok_refs':ok,'bad_refs':bad}
  else:
   m=mp.measure(t['actual_tts_char'],t['tts_text'],ok,bad,VOICE,RATE,char=t['actual_tts_char'],at=t['position'])
   out={**t,'verdict':m['verdict'],'measurement':m}
 except Exception as e:out={**t,'verdict':'error','reason':f'{type(e).__name__}: {e}'}
 (DEST/(t['id']+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
 return out
results=[];start=time.time()
with cf.ThreadPoolExecutor(max_workers=4) as pool:
 fs={pool.submit(target_run,t):t for t in manifest['targets']}
 for fut in cf.as_completed(fs):
  r=fut.result();results.append(r)
  summary={'completed':len(results),'total':len(fs),'counts':{v:sum(x['verdict']==v for x in results) for v in sorted(set(x['verdict'] for x in results))},'seconds':round(time.time()-start,1)}
  (DEST/'progress.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
  print(r['id'],r['label'],r['context'],r['verdict'],len(results),'/',len(fs),flush=True)
manifest['status']='complete';manifest['summary']=summary
manifest['publication_acoustic_status']='pending: uncertain/unreliable/skipped/error remain pending; unmeasured alternatives, numbers, acronym and proper-name listening need review. A completed run is not blanket approval.'
(DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False),flush=True)
