import argparse,json,hashlib,subprocess,math
from pathlib import Path
from fractions import Fraction
from PIL import Image,ImageDraw,ImageFont
ap=argparse.ArgumentParser();ap.add_argument('--movie',required=True);ap.add_argument('--metadata-dir',required=True);a=ap.parse_args()
movie=Path(a.movie);md=Path(a.metadata_dir);out=Path('/workspace/scratch/zverev-sf-final-qc');frames=out/'frames';frames.mkdir(parents=True,exist_ok=True)
repo=Path('/workspace/tennislive-efficiency');specpath=repo/'specs/reels/davidovich-zverev-shanghai-2026-sf.json';spec=json.loads(specpath.read_text());ass=md/'subtitles.ass';inputs=json.loads((md/'render_inputs.json').read_text());render=json.loads((md/'render.json').read_text());binding=json.loads((md/'audio_review_binding.json').read_text());qc=json.loads((md/'qc_attestation.json').read_text());selected={0,2,4,6}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
moviehash=sha(movie);assert moviehash==inputs['film_sha256']==render['film_sha256']==qc['film_sha256'];assert movie.stat().st_size==inputs['film_bytes'];assert sha(ass)==inputs['artifacts']['subtitles.ass']==qc['ass_sha256'];assert sha(md/'render_inputs.json')==render['render_inputs_sha256'];assert sha(md/'qc_attestation.json')==render['qc_attestation_sha256'];assert qc['status']=='pass';assert spec['sources']==inputs['projection']['sources'];assert 'NKFVL_lELNE' in str(spec['sources'])
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(movie)]));(out/'movie-probe.json').write_text(json.dumps(probe,indent=2));v=next(s for s in probe['streams'] if s['codec_type']=='video');n=int(v['nb_frames']);fps=float(Fraction(v['r_frame_rate']));dur=float(probe['format']['duration']);samples={};segments=[]
def add(t,reason):
 k=max(0,min(n-1,round(t*fps)));samples.setdefault(k,[]).append(reason)
def at(s):
 h,m,v=s.split(':');return int(h)*3600+int(m)*60+float(v)
for i,s in enumerate(spec['segments']):
 actual=inputs['projection']['segments'][i]
 for k in ['start','end','seconds','quote','narration','score_inset','score_inset_windows','subtitle_bottom_windows']:
  assert s.get(k)==actual.get(k),(i,k,'current spec differs from actual render')
 offset=binding['timeline']['offsets'][i];length=binding['timeline']['lengths'][i]
 segments.append({'index':i,'edit_id':s.get('_edit_id',str(i)),'film_start_s':offset,'film_end_s':offset+length,'source_start_s':s.get('start'),'source_end_s':s.get('end'),'assigned_to_this_reviewer':i in selected})
 if i in selected:
  assert 'source' in s
  for off in [.24,length/2,max(.24,length-.28)]:add(offset+off,{'kind':'source_segment_start_middle_end','segment_index':i,'edit_id':s.get('_edit_id',str(i)),'nominal_source_s':s['start']+off})
  for w in s.get('score_inset_windows',[]):
   for st in w:
    for delta in [-.16,.16]:
     t=st+delta
     if s['start']<t<s['end']:add(offset+t-s['start'],{'kind':'scoreboard_visibility_window_boundary','segment_index':i,'nominal_source_s':t})
cues=[];excluded=[]
for line in ass.read_text().splitlines():
 if not line.startswith('Dialogue:'):continue
 x=line.split(',',9);start,end=at(x[1]),at(x[2]);mid=(start+end)/2;cue={'global_cue':len(cues)+len(excluded)+1,'cue_start_s':start,'cue_end_s':end,'cue_text':x[9]};seg=next((s for s in segments if s['film_start_s']<=mid<s['film_end_s']),None)
 if seg and seg['index'] in selected:
  cue['segment_index']=seg['index'];cues.append(cue);add(mid,{'kind':'assigned_ass_cue_midpoint',**cue})
 else:excluded.append(cue)
# Finite actual-final windows chosen against this exact source's verified action boundaries.
# Cold starts after match has ended; second set's dramatic winner is a set point.
key_source={0:[142.54,143,144,145,146,147,148,149,150,151,152.6],2:[54.64,55,55.96,56.5,57.48,57.96,58.48,59,60.5,61.88],4:[106.48,107,108,109,110,111,112,113,114,115,116,117,118,119.2,119.6,120.16,121.2,122,123,124,125,126,128,130,132,134,135.64,135.96],6:[137.44,137.8,138.2,139,139.4,140,140.6,141,141.4,141.8,142.04,143,144,146,148,150,152,154,155,156,158,160,162,164,166,168,170,172,173.48,175,177,179.6,179.96]}
for i,times in key_source.items():
 s=segments[i]
 for t in times:
  if s['source_start_s']<=t<s['source_end_s']:add(s['film_start_s']+t-s['source_start_s'],{'kind':'key_action_or_native_board_sample','segment_index':i,'nominal_source_s':t})
# Additional exact adjacency samples at native source cuts and final chosen tail.
for i,ts in {4:[126.64,126.72,126.8,126.84],6:[179.92,180.0,180.08,180.12]}.items():
 for t in ts:
  if not segments[i]['source_start_s']<=t<segments[i]['source_end_s']:continue
  add(segments[i]['film_start_s']+t-segments[i]['source_start_s'],{'kind':'critical_source_cut_or_tail','segment_index':i,'nominal_source_s':t})
# Keep every assigned caption midpoint and every native visibility boundary.
# Coalesce nearby discretionary action samples to avoid redundant tiles.
protected={k for k,rs in samples.items() if any(r['kind'] in {'assigned_ass_cue_midpoint','scoreboard_visibility_window_boundary','critical_source_cut_or_tail'} for r in rs)}
kept=set(protected)
for k in sorted(samples):
 if k in kept:continue
 nearest=min(kept,key=lambda x:abs(x-k)) if kept else None
 if nearest is not None and abs(nearest-k)<=round(.28*fps):
  samples[nearest].extend([{**r,'coalesced_request_frame_index':k,'actual_sample_minus_requested_seconds':(nearest-k)/fps} for r in samples[k]]);continue
 kept.add(k)
samples={k:samples[k] for k in sorted(kept)}
indices=sorted(samples);expr='+'.join('eq(n\\,%d)'%k for k in indices)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-threads','2','-i',str(movie),'-vf','select='+expr,'-vsync','0',str(frames/'extract-%03d.png')],check=True)
items=[]
for j,k in enumerate(indices,1):
 p=frames/f'frame-{k:05}.png';(frames/f'extract-{j:03d}.png').rename(p);items.append({'frame_index':k,'film_time_s':k/fps,'reasons':samples[k],'image':str(p),'image_sha256':sha(p),'actually_viewed_on_contact_sheet':False,'original_png_actually_viewed':False})
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15);walls=[]
for b in range(0,len(items),6):
 subset=items[b:b+6];wall=Image.new('RGB',(1080,1020),'#10131a');d=ImageDraw.Draw(wall)
 for j,item in enumerate(subset):
  xx=(j%3)*360;yy=(j//3)*510;im=Image.open(item['image']).convert('RGB').resize((342,456),Image.Resampling.LANCZOS);wall.paste(im,(xx+9,yy+42));labels=' / '.join('cue%d'%r['global_cue'] if r['kind']=='assigned_ass_cue_midpoint' else 's%d'%r['segment_index'] for r in item['reasons']);d.text((xx+9,yy+4),f"#{item['frame_index']} {item['film_time_s']:.2f}s",font=font,fill='white');d.text((xx+9,yy+23),labels[:39],font=font,fill='#c6f65a')
 p=out/f'wall-{b//6+1:02d}.jpg';wall.save(p,quality=94);walls.append({'path':str(p),'sha256':sha(p),'frame_indices':[i['frame_index'] for i in subset],'actually_viewed':False})
manifest={'schema':'tennislive.partitioned-final-movie-visual-frame-manifest.v1','partition':'source_action_segments_0_2_4_6','movie':str(movie),'movie_sha256':moviehash,'movie_bytes':movie.stat().st_size,'spec':str(specpath),'spec_file_sha256':sha(specpath),'native_spec_sha256':inputs['spec_sha256'],'ass':str(ass),'ass_sha256':sha(ass),'render_inputs_sha256':sha(md/'render_inputs.json'),'native_qc_sha256':sha(md/'qc_attestation.json'),'source_sha256':binding['sources'],'tts_bundle':render.get('tts_bundle'),'fps':fps,'canvas':[v['width'],v['height']],'film_seconds':dur,'total_movie_frames':n,'segments':segments,'assigned_ass_cues':cues,'other_partition_ass_cues_not_reviewed_here':excluded,'samples':items,'walls':walls,'source_mapping_limit':'Nominal source times only; original final-movie frame index/PNG is authoritative near source cuts. Source/action partition only; root separately reviews cover/cards/outro/seams/publisher tail. No whole-frame or whole-court claim.'}
(out/'frame_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2));print(json.dumps({'samples':len(items),'assigned_cues':len(cues),'walls':len(walls),'movie_sha256':moviehash,'manifest':str(out/'frame_manifest.json')},ensure_ascii=False))
