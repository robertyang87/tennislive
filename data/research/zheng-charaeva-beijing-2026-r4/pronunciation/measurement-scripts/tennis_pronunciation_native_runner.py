import sys,json,re,runpy,hashlib,os
from pathlib import Path
sys.path.insert(0,'/tmp');import tennis_pronunciation_adapter as ad
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
specp=ad.ROOT/'specs/reels/zheng-charaeva-beijing-2026-r4.json';spec=json.loads(specp.read_text());src=Path('/workspace/scratch/zheng-charaeva/native-voices');out=ad.ROOT/'data/research/zheng-charaeva-beijing-2026-r4/pronunciation';durable=out/'native-final-audio';durable.mkdir(exist_ok=True)
prior=json.loads((durable/'bindings.json').read_text()) if (durable/'bindings.json').exists() else [];prior_by={r['edit_id']:r for r in prior}
rows=[(i,speakable(q['narration']),q['_edit_id']) for i,q in enumerate(spec['segments']) if q.get('narration')]+[('outro',speakable(NARRATION),'outro')];clean=lambda t:re.sub('[^\u4e00-\u9fffA-Za-z0-9]','',t);lookup={};bindings=[]
for i,txt,eid in rows:
 candidates=[]
 expected=src/('voice_outro.mp3' if i=='outro' else f'voice_{i:02d}.mp3')
 old=prior_by.get(eid)
 if expected.exists() and old and hashlib.sha256(expected.read_bytes()).hexdigest()==old['mp3_sha256'] and old['text_sha256']==hashlib.sha256(txt.encode()).hexdigest():
  j=Path(old['native_marks']);candidates.append((float('inf'),expected,j,json.loads(j.read_text())))
 for j in src.glob('voice_*.words.json'):
  marks=json.loads(j.read_text())
  if clean(txt)==clean(''.join(v['text'] for v in marks)):
   p=j.with_name(j.name.replace('.words.json','.mp3'))
   if p.exists():candidates.append((p.stat().st_mtime,p,j,marks))
 if not candidates:raise RuntimeError(f'{eid}: no native actual voice file matches final text; awaiting re-synthesis')
 _,p,j,marks=max(candidates,key=lambda z:z[0]);mp3hash=hashlib.sha256(p.read_bytes()).hexdigest();texthash=hashlib.sha256(txt.encode()).hexdigest();key=f'{eid}-{texthash[:12]}-{mp3hash[:12]}'
 import shutil
 audio=durable/f'{key}.mp3';mark=durable/f'{key}.words.json'
 if not audio.exists():shutil.copy2(p,audio)
 if not mark.exists():shutil.copy2(j,mark)
 alias=durable/f'{key}.json'
 if not alias.exists():shutil.copy2(j,alias)
 lookup[txt]=(audio,marks)
 bindings.append({'segment_index':i,'edit_id':eid,'tts_text':txt,'text_sha256':texthash,'voice':'zh-CN-YunjianNeural','rate':'+6%','native_audio':str(audio),'native_marks':str(mark),'source_audio':str(p),'mp3_sha256':mp3hash,'words_sha256':hashlib.sha256(mark.read_bytes()).hexdigest(),'wordboundary_exact_text_match':True,'binding_method':'current expected final14 renderer index; final source MP3 SHA256 exactly equals this issue measured immutable ORIG; same exact input hash; saved actual words from byte-identical MP3 retained if regeneration omits marks'})
(durable/'bindings.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2));fallback=ad.mp.synth
def native_synth(text,voice,rate,pitch='+0Hz'):
 if text in lookup:
  if (voice,rate,pitch)!=('zh-CN-YunjianNeural','+6%','+0Hz'):raise RuntimeError('native voice/rate/pitch mismatch')
  return lookup[text]
 return fallback(text,voice,rate,pitch)
ad.mp.synth=native_synth
if len(sys.argv)>1:runpy.run_path(sys.argv[1],run_name='__main__')
else:print({'bound_native_utterances':len(bindings),'spec_sha256':hashlib.sha256(specp.read_bytes()).hexdigest()},flush=True)
