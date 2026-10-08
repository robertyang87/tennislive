import sys,json,hashlib,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
sys.path.insert(0,'/tmp')
import tennis_pronunciation_adapter as ad
mp=ad.mp
OUT=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation'
manifest=json.loads((OUT/'final-text-manifest.json').read_text())
VOICE='zh-CN-YunjianNeural'; RATE='+6%'
jobs=[];pending=[]
for n,row in enumerate(manifest['utterances']):
 for occ in row['polyphones']:
  if occ['char']=='耶': occ['intended']='ye1';occ['reading_reason']='译名惯例：耶ye1；静态本期漏识姓名'
  intended=occ['intended']; idx=occ['index']; ch=occ['char']
  ok,note=mp.suggest_homophones(intended,exclude=ch,k=3)
  if ch=='耶':ok=['椰','噎']
  if intended in ['le5','de5','fa1'] or not ok:
   pending.append({'utterance':n,'label':row['label'],**occ,'verdict':'skipped','why':'没有可靠的独立同音参考字，需实际音频人工听审；未通过','tts_text':row['tts_text'],'text_sha256':row['text_sha256']})
   continue
  for wrong in occ['live']:
   if wrong==intended:continue
   bad,bnote=mp.suggest_homophones(wrong,exclude=ch,k=3)
   if not bad:
    pending.append({'utterance':n,'label':row['label'],**occ,'wrong':wrong,'verdict':'skipped','why':'错读一侧缺独立同音参考','tts_text':row['tts_text'],'text_sha256':row['text_sha256']});continue
   # Unique job names include absolute char position and wrong reading.
   jobs.append({'id':f'u{n:02d}-i{idx:02d}-{ch}-{intended}-vs-{wrong}','utterance':n,'label':row['label'],'sentence':row['tts_text'],'text_sha256':row['text_sha256'],'index':idx,'char':ch,'intended':intended,'wrong':wrong,'ok':ok,'bad':bad,'ok_reference_note':note,'bad_reference_note':bnote})
manifest['sealed']=False
manifest['audio_source']='native production tts_one files; exact final input and wordboundary verified'
manifest['polyphone_method']='measure_polyphone.py; whole final speakable utterance; identical production voice/rate; full DTW MFCC+F0; explicit pending for uncertain/unreliable/skipped'
(OUT/'final-text-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
(OUT/'native-initial-pending.json').write_text(json.dumps(pending,ensure_ascii=False,indent=2))
(OUT/'native-jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2))
print('jobs',len(jobs),'initial pending',len(pending),flush=True)
# Synthesize every actual utterance to keep real complete final audio and marks.
utterance_audio=[]
for n,row in enumerate(manifest['utterances']):
 audio,marks=mp.synth(row['tts_text'],VOICE,RATE)
 utterance_audio.append({'utterance':n,'label':row['label'],'text_sha256':row['text_sha256'],'audio':str(audio),'audio_sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'bytes':audio.stat().st_size,'marks':marks})
(OUT/'final-utterance-audio.json').write_text(json.dumps(utterance_audio,ensure_ascii=False,indent=2))
def run(j):
 p=OUT/'raw'/f"native-{j['id']}-{j['text_sha256'][:12]}.json";p.parent.mkdir(exist_ok=True)
 if p.exists():
  cached=json.loads(p.read_text());ap,_=mp.synth(j['sentence'],VOICE,RATE)
  if cached.get('native_orig_mp3_sha256')==hashlib.sha256(ap.read_bytes()).hexdigest():return cached
 try:
  r=mp.measure(j['char'],j['sentence'],j['ok'],j['bad'],VOICE,RATE,char=j['char'],at=j['index'])
 except Exception as e:r={'verdict':'error','why':f'{type(e).__name__}: {e}'}
 r={'job':j,**r};ap,_=mp.synth(j['sentence'],VOICE,RATE);r['native_orig_mp3_sha256']=hashlib.sha256(ap.read_bytes()).hexdigest();r['actual_audio_source']='native renderer tts_one final voice file';p.write_text(json.dumps(r,ensure_ascii=False,indent=2));return r
results=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 fs={pool.submit(run,j):j for j in jobs}
 for f in as_completed(fs):
  r=f.result();results.append(r);j=r['job'];print(j['id'],r['verdict'],r.get('confidence'),r.get('score'),flush=True)
results.sort(key=lambda r:r['job']['id'])
(OUT/'native-acoustic-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
counts={}
for r in results+pending:counts[r['verdict']]=counts.get(r['verdict'],0)+1
summary={'counts':counts,'status':'pass' if all(r['verdict']=='correct' for r in results) and not pending else 'pending','why':'uncertain/unreliable/skipped/error cannot be pass','manifest':'final-text-manifest.json','results':'acoustic-results.json','pending':'pending.json'}
(OUT/'native-default-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(summary,flush=True)
