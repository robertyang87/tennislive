import sys,json,hashlib,collections
from pathlib import Path
R=Path('/workspace/tennislive-efficiency');sys.path[:0]=[str(R/'tools'),str(R/'src')]
import build_match_reel as reel
import preview_reel_captions as preview
S=R/'specs/reels/chwalinska-sakkari-wuhan-2026-qf.json';spec=json.loads(S.read_text());O=Path('/workspace/scratch/moon-qf-caption-preview-fullscreen');O.mkdir(exist_ok=True)
p=O/'source_main.mp4'
if not p.exists():p.symlink_to('/workspace/scratch/moon-qf-source/source.mp4')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def callback(**kw):
 segments=kw['segments'];offsets=[];cur=kw['cover_secs'];times=[]
 for raw,seg in zip(spec['segments'],segments):
  offsets.append(cur)
  if raw.get('quote'):
   times.extend(cur+(float(q['at'])+float(q['end']))/2 for q in raw['quote'])
   extra={'cold_open':[.15],'first_set':[2.5,38,59.65],'second_break':[2.5,31.5,39.5],'second_finish':[1.5,25.5,48.4],'ending':[1.5,17,24.4,55.9]}
   times.extend(cur+t for t in extra.get(raw['_edit_id'],[]))
  else:times.append(cur+min(5,seg.length/2))
  cur+=seg.length
 samples=[]
 for start in range(0,len(times),24):
  for sample in preview.sample_frames(kw['cues'],segments,kw['cover_secs'],maximum=24,at=tuple(times[start:start+24])):
   if not any((q['segment'],q['frame'])==(sample['segment'],sample['frame']) for q in samples):samples.append(sample)
 groups=collections.defaultdict(list)
 for n,s in enumerate(samples,1):groups[s['segment']].append((n,s))
 rows=[];sourcehash={k:sha(p)for k,p in kw['sources'].items()}
 for idx,group in groups.items():
  seg=segments[idx];unique=sorted({x['frame']for n,x in group});pattern=O/f'group-{idx:02d}-%03d.png';record={}
  def sink(*native):
   extras,graph=preview.visual_graph(spec,segments,kw['cover_secs'],kw['ass'],O,list(native).count('-i'))
   cmd=preview.frame_command(native,graph,extras,offsets[idx],unique[0],pattern)
   pos=cmd.index('-filter_complex')+1;old=f"select='eq(n,{unique[0]})'";new="select='"+'+'.join(f'eq(n,{n})'for n in unique)+"'";assert old in cmd[pos];cmd[pos]=cmd[pos].replace(old,new);cmd[cmd.index('-frames:v')+1]=str(len(unique));cmd[-1:-1]=['-fps_mode','vfr'];record.update(native=list(native),grouped_preview=cmd);reel.run(*cmd)
  if seg.image:reel.cut_still_segment(seg,O/f'native-still-{idx:02d}.png',threads=1,command_sink=sink)
  else:reel.cut_segment(kw['sources'][seg.source],seg,pattern,kw['source_w'],threads=1,command_sink=sink)
  from PIL import Image
  images={f:O/f'group-{idx:02d}-{n:03d}.png'for n,f in enumerate(unique,1)}
  for n,sample in group:
   src=images[sample['frame']];dest=O/f'caption-{n:02d}.png';dest.write_bytes(src.read_bytes())
   with Image.open(dest)as im:assert im.size==(1080,1440)
   rows.append({**sample,'image':dest.name,'image_sha256':sha(dest),'source':seg.source,'source_time':None if seg.image else seg.start+sample['segment_time']*seg.speed,'source_sha256':None if seg.image else sourcehash[seg.source],'still_sha256':sha(seg.image)if seg.image else None,'resolved_scorebox':seg.score_inset,'native_command':record['native'],'grouped_preview_command':record['grouped_preview']})
  print('Verified grouped native segment',idx,len(group),flush=True)
 manifest={'schema':'tennislive.native-caption-frame-preview.v1','kind':'visual_preview_only','publication_approved':False,'spec_file_sha256':sha(S),'ass_sha256':sha(kw['ass']),'fps':reel.FPS_EXPR,'canvas':[1080,1440],'cover_seconds':kw['cover_secs'],'method':'Same native segment/frame_command/visual_graph; finite frame selections grouped by segment to decode once; -fps_mode vfr prevents frame repetition.','limitations':['No final QC or publication approval','Interior samples exclude dissolves/final H264','Audio not produced or evaluated','Finite sampling does not prove all board-width transitions'],'samples':sorted(rows,key=lambda x:x['image'])};p=O/'preview_manifest.json';p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');return p
reel.apply_tts_backend(spec)
print(reel.render(spec,O,voice='zh-CN-YunjianNeural',rate='+6%',tts_bundle_in=Path('/workspace/scratch/moon-qf-tts.zip'),preview_callback=callback))
