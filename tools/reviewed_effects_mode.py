"""Owner-scoped RNA10 processed ball-sound bed, with one reviewed raw window."""
from pathlib import Path
import hashlib,json,re,subprocess,tempfile,os
from urllib.request import urlopen
from datetime import datetime
MODE='reviewed_effects'
APPROVAL='rna10-20261003-ball-sound-kept'
SLUG='nadal-academy-10th-2026'
IDS={'s1':'mXIoUmxozgw','s2':'HLTTYfIi5J8','s3':'1lo0go-8rNc','s4':'jT-R3UwSRnA','s5':'ai48JDtcGz8','s6':'DItCoF_LhVw','s7':'7kcau8Gi7UM'}
HASHES={'s7': '0c5f104a0731abe33fa7336f22ae4d479234f78cf54b104d3da73cf8ed044586', 's6': 'bf9f13ec42facfeb6b64afc554bdff16d937d55d320ac2e058d937c7cda990c1', 's5': 'a1f4265fba2d5c04b24b361839ee806e247fa7a53acf755000f0638f105e748a', 's4': '906624336a33597f300443cefcbb311ffd0d9728937fdd54b03971f59e92167d', 's3': '5d21b2f5a28c81631e0f3d35ebf79e1c5cb33c8857f0d17f6cb10ac5ea790a05', 's2': 'eef0f948d9a168240d670f13fca74b3741d865c1a9f59df74a7bb4bd28145f47', 's1': 'c58680e11e07e6e08bcc72756cfe26bf974d9cd6ac03a8f7cea2007411da7f0c'}
ROOT=Path(__file__).resolve().parents[1]
EFFECTS_RELEASE='https://github.com/robertyang87/tennislive/releases/download/rna10-effects-20261003/'

def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def raw_segment(s):return not s.get('image') and (s.get('source'),s.get('start'),s.get('end'),s.get('speed',1))==('s1',132.4,145.7,1)

def enabled(spec,*,sources=None):
 if spec.get('original_audio_mode')!=MODE:return False
 if spec.get('owner_approval')!=APPROVAL or spec.get('slug')!=SLUG:raise ValueError('击球声处理授权仅限本条RNA10影片')
 if spec.get('sources')!={k:'https://www.youtube.com/watch?v='+v for k,v in IDS.items()}:raise ValueError('击球声模式必须绑定七个精确源URL')
 if spec.get('source_audio') or spec.get('music'):raise ValueError('本条不允许未绑定额外音轨')
 if sum(raw_segment(s) for s in spec.get('segments',[]))!=1:raise ValueError('本条必须恰好保留一个已审核13.3秒现场原声窗口')
 for s in spec['segments']:
  if s.get('mute') or s.get('bed'):raise ValueError('击球声模式不允许静音或未审核增益档')
  if raw_segment(s):
   if s.get('narration'):raise ValueError('完整原声窗口不叠旁白')
  elif not s.get('image') and not s.get('stat_card') and not s.get('title_card') and not str(s.get('narration') or '').strip():raise ValueError('其余比赛窗口须配中文旁白及审核效果声')
  if s.get('quote'):raise ValueError('本条没有获准原声引语')
  if s.get('narration') and not re.search('[\u3400-\u9fff]',s['narration']):raise ValueError('本条旁白必须中文')
 if sources is not None and (set(sources)!=set(HASHES) or any(sha(p)!=HASHES[k] for k,p in sources.items())):raise ValueError('七个原始源文件字节不匹配')
 return True

def safe_path(root,name):
 p=(root/name).resolve()
 if not p.is_relative_to(root.resolve()):raise ValueError('效果音证据路径越出仓库')
 return p

def archived_effect(key,row,path,*,download=False):
 expected_url=EFFECTS_RELEASE+key+'.wav'
 if row.get('effects_url')!=expected_url or row.get('effects_path')!='data/audio_effects/rna10/'+key+'.wav':
  raise ValueError('效果轨存档仅接受本条固定GitHub Release URL与路径')
 if not path.is_file() and download:
  path.parent.mkdir(parents=True,exist_ok=True)
  temp_path=None
  try:
   with tempfile.NamedTemporaryFile(dir=path.parent,prefix=key+'.',suffix='.partial',delete=False) as target:
    temp_path=Path(target.name)
    with urlopen(expected_url,timeout=60) as response:
     while block:=response.read(1024*1024):target.write(block)
   if sha(temp_path)!=row.get('effects_sha256'):raise ValueError('下载效果轨SHA-256不是已审核字节')
   os.replace(temp_path,path)
  finally:
   if temp_path is not None:temp_path.unlink(missing_ok=True)
 if path.is_file() and sha(path)!=row.get('effects_sha256'):raise ValueError('效果轨字节已变')
 return path

def manifest(spec,*,root=ROOT,sources=None):
 enabled(spec,sources=sources)
 p=safe_path(root,spec.get('audio_effects_review','data/audio_reviews/'+SLUG+'.effects.json'))
 doc=json.loads(p.read_text())
 if doc.get('schema')!='tennislive.reviewed-effects.v1' or doc.get('slug')!=SLUG or doc.get('owner_approval')!=APPROVAL:raise ValueError('效果音证据身份不匹配')
 rows=doc.get('sources') or {}
 if set(rows)!=set(HASHES):raise ValueError('效果音证据必须完整覆盖七源')
 paths={}
 for key,row in rows.items():
  stamp=datetime.fromisoformat(str(row.get('reviewed_at','')).replace('Z','+00:00'))
  if row.get('source_sha256')!=HASHES[key] or row.get('status')!='reviewed' or not row.get('reviewer') or stamp.tzinfo is None or row.get('ball_impacts_preserved') is not True:raise ValueError('效果声未真实核验源身份或击球保留')
  if not row.get('algorithm') or not re.fullmatch('[a-f0-9]{64}',str(row.get('model_sha256',''))):raise ValueError('效果轨缺算法或模型字节身份')
  speech=row.get('speech_review') or {};evidence=safe_path(root,speech.get('transcript_path',''))
  if speech.get('method') not in ('asr_cross_checked','asr_then_listened','listened_with_transcript') or speech.get('uncertain_spans') or sha(evidence)!=speech.get('sha256'):raise ValueError('效果轨仍有未核对人声或缺真实转写证据')
  packet=json.loads(evidence.read_text())
  if packet.get('effects_sha256')!=row.get('effects_sha256') or packet.get('status')!='complete' or packet.get('uncertain_spans'):raise ValueError('效果轨转写没有绑定处理后字节')
  reviewed=datetime.fromisoformat(str(packet.get('reviewed_at','')).replace('Z','+00:00'))
  selected=[s for s in spec['segments'] if s.get('source')==key and not raw_segment(s) and not s.get('image')]
  if packet.get('method')!=speech.get('method') or not packet.get('reviewer') or reviewed.tzinfo is None or not isinstance(packet.get('foreground_speech'),list) or packet.get('foreground_speech') or not str(packet.get('no_foreground_speech_reason','')).strip():raise ValueError('效果轨需完整真实无残留人声审核，不能裸pass')
  if selected and (float(packet.get('reviewed_from',1e99))>min(s['start'] for s in selected) or float(packet.get('reviewed_to',-1))<max(s['end'] for s in selected)):raise ValueError('效果轨审核未覆盖全部选用窗口')
  if packet.get('method')=='asr_cross_checked' and (not isinstance(packet.get('asr_results'),list) or len(packet['asr_results'])<2 or len({r.get('model') for r in packet['asr_results']})<2):raise ValueError('效果轨ASR核验缺两个模型原始结果')
  path=safe_path(root,row['effects_path'])
  archived_effect(key,row,path,download=sources is not None)
  paths[key]=path
 return p,doc,paths

def bed_graph(spec,sources,offsets,first_input,*,root=ROOT):
 _,_,paths=manifest(spec,root=root,sources=sources)
 inputs=[];chains=[];labels=[];windows=[]
 for i,s in enumerate(spec['segments']):
  if s.get('image') or s.get('stat_card') or s.get('title_card'):continue
  raw=raw_segment(s);path=Path(sources[s['source']]) if raw else paths[s['source']]
  inputs.extend(['-i',str(path)]);label=f'fxbed{i}';delay=int(offsets[i]*1000);speed=float(s.get('speed',1));speed_chain='' if speed==1 else f',atempo={speed}'
  chains.append(f'[{first_input+len(inputs)//2-1}:a]atrim=start={s["start"]}:end={s["end"]},asetpts=PTS-STARTPTS{speed_chain},aresample=48000,aformat=channel_layouts=stereo,adelay={delay}|{delay}[{label}]')
  labels.append(f'[{label}]');windows.append({'index':i,'source':s['source'],'kind':'raw' if raw else 'processed_effects','start':s['start'],'end':s['end'],'speed':speed,'offset':delay/1000,'duration':(s['end']-s['start'])/speed,'audio_sha256':sha(path)})
 chains.append(''.join(labels)+f'amix=inputs={len(labels)}:normalize=0:dropout_transition=0[effects_bed];[effects_bed]volume=0.72[bed]')
 return inputs,';'.join(chains)+';',windows

def seal_mix(spec,outdir,mixed,voices,offsets,spoken,cover_voice,cover_seconds,outro_voice,outro_offset,duration,windows):
 if not enabled(spec):return
 import narrated_audio_mode as n
 p=outdir/'audio_review_binding.json';b=json.loads(p.read_text());m,doc,_=manifest(spec);rows=[]
 if cover_voice is not None:rows.append({'kind':'cover','offset':0.,'duration':duration(cover_voice),'sha256':sha(cover_voice)})
 for i,((v,_),o) in enumerate(zip(voices,offsets)):
  if i in spoken:rows.append({'kind':'segment','index':i,'offset':int(o*1000)/1000,'duration':duration(v),'sha256':sha(v)})
 if outro_voice is not None:rows.append({'kind':'outro','offset':int(outro_offset*1000)/1000,'duration':duration(outro_voice),'sha256':sha(outro_voice)})
 raw=next(x for x in windows if x['kind']=='raw')
 if any(r['offset']<raw['offset']+raw['duration'] and r['offset']+r['duration']>raw['offset'] for r in rows):raise ValueError('旁白串入13.3秒完整原声窗口')
 b.update(original_audio_mode=MODE,owner_approval=APPROVAL)
 b['effects_mix']={'method':'independent_reviewed_effects_trims_and_raw_window','manifest_sha256':sha(m),'windows':windows,'voices':rows,'audio_packet_sha256':n.audio_packet_hash(mixed)}
 p.write_text(json.dumps(b,ensure_ascii=False,indent=2)+'\n')

def verify_mix(spec,film,binding):
 if not enabled(spec):return
 import narrated_audio_mode as n
 import numpy as np
 p,doc,paths=manifest(spec);mix=binding.get('effects_mix') or {}
 if binding.get('sources')!=HASHES or binding.get('original_audio_mode')!=MODE or binding.get('owner_approval')!=APPROVAL or mix.get('manifest_sha256')!=sha(p) or mix.get('method')!='independent_reviewed_effects_trims_and_raw_window' or mix.get('audio_packet_sha256')!=n.audio_packet_hash(film):raise ValueError('效果混音或源身份绑定不匹配')
 expected=[]
 for i,s in enumerate(spec['segments']):
  if s.get('image') or s.get('stat_card') or s.get('title_card'):continue
  speed=float(s.get('speed',1));raw=raw_segment(s)
  expected.append({'index':i,'source':s['source'],'kind':'raw' if raw else 'processed_effects','start':s['start'],'end':s['end'],'speed':speed,'offset':int(binding['timeline']['offsets'][i]*1000)/1000,'duration':(s['end']-s['start'])/speed,'audio_sha256':HASHES[s['source']] if raw else sha(paths[s['source']])})
 if mix.get('windows')!=expected:raise ValueError('效果混音未使用精确审核切点')
 if {r.get('index') for r in mix.get('voices',[]) if r.get('kind')=='segment'}!={i for i,s in enumerate(spec['segments']) if s.get('narration')}:raise ValueError('中文旁白有缺漏')
 pcm=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(film),'-map','0:a:0','-ac','1','-ar','8000','-f','f32le','-']),dtype='<f4');mask=np.zeros(len(pcm),dtype=bool)
 for r in expected+mix['voices']:
  a=int(r['offset']*8000);b=min(len(pcm),int((r['offset']+r['duration'])*8000))
  if b<=a or np.sqrt(np.mean(pcm[a:b]**2))<=.001:raise ValueError('击球声/旁白/完整现场原声缺失')
  mask[max(0,a-256):min(len(pcm),b+256)]=True
 outside=pcm[~mask]
 if len(outside) and np.max(np.abs(outside))>.0001:raise ValueError('未安排音频的卡片或留白仍有声轨泄漏')
 print('[ok] RNA10击球声效果轨：七源/七效果轨身份、审核证据、完整raw13.3s、旁白与最终PCM绑定通过')
