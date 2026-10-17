import json,hashlib,zipfile
from pathlib import Path
r=Path('/workspace/tennislive');out=Path('/workspace/research-kartal/voice');out.mkdir(exist_ok=True)
s=json.load(open(r/'specs/reels/kartal-ostapenko-wuhan-2026-sf.json'));rows=[]
from pypinyin import Style,pinyin
with zipfile.ZipFile('/workspace/research-kartal/tts-v2.zip')as z:
 m=json.loads(z.read('manifest.json'))
 for ent in m['entries']:
  req=ent['request'];id=ent['request_id'];text=req['text'];seg=next((x for x in s['segments']if x.get('narration')==text),None);eid=seg['_edit_id']if seg else'outro';i=s['segments'].index(seg)if seg else None
  d=out/'native-speech';d.mkdir(exist_ok=True);a=d/f'{id}.mp3';a.write_bytes(z.read(f'requests/{id}/audio.mp3'));b=d/f'{id}.marks.json';b.write_bytes(z.read(f'requests/{id}/marks.json'));marks=json.loads(b.read_text());zp=d/f'{id}.native.zip'
  with zipfile.ZipFile(zp,'w')as zz:zz.writestr('audio.mp3',a.read_bytes());zz.writestr('marks.json',b.read_bytes())
  rows.append({'label':eid,'index':i,'edit_id':eid,'display_text':seg['narration']if seg else'关注网球时差，时差归我，好球归你。','text':text,'voice':req['voice'],'rate':req['rate'],'pitch':req['pitch'],'cache_key':req['cache_key'],'actual_mp3_sha256':ent['audio_sha256'],'bound_snapshot_path':str(a),'marks_snapshot_path':str(b),'mp3_duration_seconds':ent['duration_seconds'],'native_zip_snapshot_path':str(zp),'native_zip_sha256':hashlib.sha256(zp.read_bytes()).hexdigest(),'native_zip_marks_raw_sha256':ent['marks_sha256'],'actual_marks_sha256':ent['marks_sha256'],'word_boundary_tokens':[x['text']for x in marks]})
(out/'native-bindings.json').write_text(json.dumps({'schema':'tennislive.native-prepared-speech.v1','bindings':rows,'frozen_bundle_sha256':hashlib.sha256(Path('/workspace/research-kartal/tts-v2.zip').read_bytes()).hexdigest(),'human_listening_claimed':False},ensure_ascii=False,indent=2)+'\n')
names={n:[x[0]for x in pinyin(n,style=Style.TONE3,neutral_tone_with_five=True)]for n in ['卡尔塔尔','奥斯塔彭科','斯瓦泰克','武汉']};(out/'names.json').write_text(json.dumps(names,ensure_ascii=False,indent=2)+'\n')
print('actual frozen utterances',len(rows))
