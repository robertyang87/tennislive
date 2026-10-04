"""Owner-approved, exactly bounded Chinese-narration-only October 1 ATP cuts.

No source-speech absence is claimed. The undecidable original soundtrack is
excluded from the mixer, including transitions, cover, cards and outro. Other
reels keep the existing original-audio and silence gates unchanged.
"""
from __future__ import annotations
import hashlib
import base64
import os
import json
import math
import re
import subprocess
from pathlib import Path

APPROVAL = "atp-20261002-narrated-three"
MODE = "muted_narrated"
APPROVED = {
 "nishikori-tiafoe-tokyo-2026-r1": {
  "windows":[[170.8, 179.8], [0.0, 10.8], [10.8, 20.4], [20.4, 23.7], [31.95, 50.95], [50.95, 57.35], [85.8, 95.3], [99.66, 105.5], [105.5, 110.02], [137.0, 161.5], [161.5, 166.6], [166.6, 170.8], [170.8, 179.8]],
  "asset":"source-tennistv-4584955/4584955.mp4",
  "sha256":"108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02",
  "bytes":144247263},
 "shang-baez-beijing-2026-r1": {
  "windows":[[144.0, 147.85], [138.2, 143.9], [12.2, 23.7], [52.2, 66.9], [86.0, 99.6], [116.5, 124.8], [125.5, 132.3], [132.3, 147.85]],
  "asset":"source-tennistv-4585070/4585070.mp4",
  "sha256":"f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f",
  "bytes":120347402},
 "zverev-norrie-beijing-2026-r1": {
  "windows":[[222.38, 233.48], [0.0, 12.9], [12.9, 19.1], [101.84, 118.2], [118.2, 123.98], [123.98, 140.5], [140.5, 156.26], [181.82, 188.72], [188.72, 190.72], [191.78, 195.98], [195.98, 199.8], [199.8, 205.98], [205.98, 214.08], [214.08, 215.66], [215.86, 233.68]],
  "asset":"source-eciSHiQTzN8/eciSHiQTzN8.mp4",
  "sha256":"dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee",
  "bytes":40607227},
}


def sha(path: Path) -> str:
 with path.open('rb') as f:
  return hashlib.file_digest(f,'sha256').hexdigest()


def enabled(spec: dict, *, sources: dict | None = None) -> bool:
 import reviewed_effects_mode
 if reviewed_effects_mode.enabled(spec,sources=sources):
  return False
 mode=spec.get('original_audio_mode')
 if mode is None:
  if 'owner_approval' in spec:
   raise ValueError('旁白模式授权不能脱离显式 original_audio_mode')
  return False
 if mode!=MODE or spec.get('owner_approval')!=APPROVAL:
  raise ValueError('未授权的原声替换模式')
 record=APPROVED.get(spec.get('slug'))
 if record is None:
  raise ValueError('中文旁白例外仅限本次三条ATP影片')
 url='https://github.com/robertyang87/tennislive/releases/download/'+record['asset']
 urls=spec.get('sources') or {'':spec.get('source_url')}
 if len(urls)!=1 or list(urls.values())!=[url]:
  raise ValueError('旁白例外没有绑定获准的精确源片存档')
 if spec.get('source_audio') or spec.get('music'):
  raise ValueError('旁白例外不允许额外原声音轨或背景音乐')
 segments=spec.get('segments') or []
 if not segments or not str(segments[0].get('narration') or '').strip():
  raise ValueError('中文旁白模式必须有本人TTS冷开场')
 if any(s.get('quote') for s in segments):
  raise ValueError('已移除的原声不能再显示未核准的英文引语')
 if 'track' in spec and spec['track'] is not False:
  raise ValueError('本模式顶层track只接受布尔false')
 if any(s.get('track') or s.get('square_pan') or s.get('cx',.5) not in (None,.5) for s in segments):
  raise ValueError('本次影片必须固定居中')
 if spec.get('layout','full')!='full':
  raise ValueError('本次影片必须3:4全画布')
 if any(s.get('image') and not s.get('stat_card') and not s.get('title_card') for s in segments):
  raise ValueError('本次影片不能用照片填补比赛画面')
 if any(str(s.get('narration') or '').strip() and not re.search('[\u3400-\u9fff]',s['narration']) for s in segments):
  raise ValueError('本人TTS必须为中文')
 windows=[[float(s['start']),float(s['end'])] for s in segments if 'start' in s and not s.get('image')]
 if 'windows' in record and windows!=record['windows']:
  raise ValueError('旁白授权不能改变已核验的完整比赛窗口')
 if sources is not None:
  if set(sources)!=set(urls):
   raise ValueError('旁白模式源文件映射不匹配')
  for path in sources.values():
   path=Path(path)
   if path.stat().st_size!=record['bytes'] or sha(path)!=record['sha256']:
    raise ValueError('旁白模式下载源文件不是获准的精确字节')
 return True


def audio_packet_hash(path: Path) -> str:
 output=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0',
   '-c:a','copy','-f','hash','-hash','sha256','-'],text=True).strip()
 if not re.fullmatch('SHA256=[a-f0-9]{64}',output):
  raise ValueError('无法核验最终音轨')
 return output.split('=')[1]


def seal_mix(spec: dict, outdir: Path, mixed: Path, voices: list,
             offsets: list, spoken: dict, cover_voice, cover_seconds: float,
             outro_voice, outro_offset: float, duration) -> None:
 if not enabled(spec):
  return
 binding_path=outdir/'audio_review_binding.json'
 binding=json.loads(binding_path.read_text())
 rows=[]
 if cover_voice is not None:
  rows.append({'kind':'cover','offset':0.,'duration':duration(cover_voice),'sha256':sha(cover_voice)})
 for i,((path,_marks),offset) in enumerate(zip(voices,offsets)):
  if i in spoken:
   rows.append({'kind':'segment','index':i,'offset':int(offset*1000)/1000,
    'duration':duration(path),'sha256':sha(path)})
 if outro_voice is not None:
  rows.append({'kind':'outro','offset':int(outro_offset*1000)/1000,
   'duration':duration(outro_voice),'sha256':sha(outro_voice)})
 binding['narrated_mix']={'method':'anullsrc_before_tts_mix','original_audio_gain':0,
  'audio_packet_sha256':audio_packet_hash(mixed),'voices':rows}
 binding_path.write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')


def verify_mix(spec: dict, film: Path, binding: dict) -> None:
 import reviewed_effects_mode
 if reviewed_effects_mode.enabled(spec):
  reviewed_effects_mode.verify_mix(spec,film,binding)
  return
 if not enabled(spec):
  return
 record=APPROVED[spec['slug']]
 if binding.get('original_audio_mode')!=MODE or binding.get('owner_approval')!=APPROVAL:
  raise ValueError('缺本次获准的原声移除绑定')
 if set(binding.get('sources',{}).values())!={record['sha256']}:
  raise ValueError('缺获准源片实际字节绑定')
 mix=binding.get('narrated_mix') or {}
 if mix.get('method')!='anullsrc_before_tts_mix' or mix.get('original_audio_gain')!=0:
  raise ValueError('源片音轨没有被真实移除；mute地板不是静音')
 if mix.get('audio_packet_sha256')!=audio_packet_hash(film):
  raise ValueError('成片不是已核验的本人TTS音轨')
 indices={r.get('index') for r in mix.get('voices',[]) if r.get('kind')=='segment'}
 expected={i for i,s in enumerate(spec['segments']) if str(s.get('narration') or '').strip()}
 if indices!=expected:
  raise ValueError('本人中文TTS有缺漏')
 # This validates actual PCM, not an ASR pass or guessed original-speech absence.
 import numpy as np
 raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(film),'-map','0:a:0',
   '-ac','1','-ar','8000','-f','f32le','-'])
 pcm=np.frombuffer(raw,dtype='<f4')
 scheduled=np.zeros(len(pcm),dtype=bool)
 for row in mix['voices']:
  lo=max(0,int(float(row['offset'])*8000));hi=min(len(pcm),int((float(row['offset'])+float(row['duration']))*8000))
  if hi<=lo or float(np.sqrt(np.mean(pcm[lo:hi]**2)))<=.001:
   raise ValueError('成片缺少清晰可听的本人中文TTS')
  scheduled[max(0,lo-1200):min(len(pcm),hi+1200)]=True
 outside=pcm[~scheduled]
 if len(outside) and float(np.max(np.abs(outside)))>0.0001:
  raise ValueError('已约定静音的留白仍有音频，可能泄漏源片原声')
 print('[ok] 授权旁白模式：原声输入为anullsrc；最终音轨哈希与本人TTS混音一致；实际PCM留白为零，无ASR通过声明')


def declared_pause_seconds(spec: dict, film: Path, levels: list, after: int) -> list[int]:
 import reviewed_effects_mode
 if reviewed_effects_mode.enabled(spec):
  binding=json.loads((film.parent/'audio_review_binding.json').read_text())
  reviewed_effects_mode.verify_mix(spec,film,binding)
  return [i for i,db in enumerate(levels) if i>=after and db<=-60]
 if not enabled(spec):
  return []
 binding=json.loads((film.parent/'audio_review_binding.json').read_text())
 # MP3 containers include trailing padding and ordinary spoken pauses. A
 # duration rectangle is not a speech-activity mask (Zverev native run2429).
 # Require the full real-film proof before accepting *any* measured silence:
 # exact sealed TTS packet hash, every expected voice audible, and zero bed.
 # Wholly missing narration therefore remains a hard failure, even when this
 # helper is called independently of foreground_audio_gate.verify_final.
 verify_mix(spec,film,binding)
 return [i for i,db in enumerate(levels) if i>=after and db<=-60]


def preload_tts(spec: dict, *, voice: str, rate: str, root: Path | None = None) -> None:
 """Restore reviewed voice bytes into the existing native TTS content cache."""
 if not enabled(spec):
  return
 root = root or Path(__file__).resolve().parents[1]
 seed_path = root/'data/narrated_tts'/f"{spec['slug']}.json"
 expected_seed = {
  "nishikori-tiafoe-tokyo-2026-r1":"e5ff9c9d33d7a9ae80d5b133578aad76cd36c290624e2b24157c1b41ca709deb",
  "shang-baez-beijing-2026-r1":"d7f3d92eb17af19875f3df1569f0a71ca4f8f938b84b7cbdf16a7349305a63c5",
  "zverev-norrie-beijing-2026-r1":"e699ee222ecd6e2f89362d5401133e15449b60f4709294143271baa7eacba318",
 }[spec["slug"]]
 if sha(seed_path) != expected_seed:
  raise ValueError("缓存种子不是已核验的本期配音文件")
 seed = json.loads(seed_path.read_text())
 if (seed.get('schema')!='tennislive.prepared-tts-cache.v1' or seed.get('slug')!=spec['slug']
     or seed.get('voice')!=voice or seed.get('rate')!=rate):
  raise ValueError('已核验TTS缓存的影片、音色或速率不匹配')
 decoded = {}
 for row in seed['files']:
  name = row.get('name','')
  if not re.fullmatch(r'[a-f0-9]{32}\.(mp3|json)',name) or name in decoded:
   raise ValueError('非法或重复的TTS内容缓存路径')
  raw = base64.b64decode(row['content_base64'],validate=True)
  if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
   raise ValueError('TTS缓存大小或哈希不匹配')
  decoded[name]=raw
 from build_match_reel import speakable, OUTRO_NARRATION
 from tennislive.video.tts import tts_content_key
 texts=[s['narration'] for s in spec['segments'] if str(s.get('narration') or '').strip()]
 if (spec.get('cover') or {}).get('narration'):
  texts.append(spec['cover']['narration'])
 if spec.get('outro',True) is not False:
  texts.append(OUTRO_NARRATION)
 for text in texts:
  key=tts_content_key(speakable(text),voice,rate,'+0Hz','','',0.0)
  if any(key+suffix not in decoded for suffix in ('.mp3','.json')):
   raise ValueError('当前旁白没有已核验缓存；不得静默发起重合成')
 cache=Path(os.environ.get('TENNISLIVE_TTS_CACHE',str(Path.home()/'.cache/tennislive-tts')))
 cache.mkdir(parents=True,exist_ok=True)
 for name,raw in decoded.items():
  (cache/name).write_bytes(raw)
 print(f'[TTS] 恢复{len(decoded)}份已核验原始配音缓存；不重合成')


def validate_root_tracking(spec: dict) -> None:
 """Consume root track=false as a real fixed-camera/no-pan constraint."""
 if 'track' not in spec:
  return
 if spec['track'] is not False:
  raise ValueError('顶层track只接受布尔false；追踪必须按受支持的分段合同声明')
 if any(segment.get('track') or segment.get('square_pan') for segment in spec.get('segments') or []):
  raise ValueError('顶层track=false与分段追踪或平移冲突')
 # Camera control is independent of audio mode. Existing ordinary reels may
 # use a static off-centre crop; the bounded narrated mode separately requires
 # exact centre, source identity and complete original-audio exclusion.
 enabled(spec)


def no_quote_reason(spec: dict) -> str:
 """A verified mode declaration is a structured editorial reason, not ASR."""
 import reviewed_effects_mode
 if reviewed_effects_mode.enabled(spec):
  return ('Exact owner-approved RNA10 effects mode retains reviewed ball sounds and '
          'one complete raw window; it forbids broadcast quotes. Native audio identity '
          'and foreground-speech review remain required.')
 if not enabled(spec):
  return ''
 return ('Exact source-bound Chinese-narrated mode excludes original audio and quotes; '
         'native final QA still requires every TTS voice, sealed audio identity and zero source PCM.')
