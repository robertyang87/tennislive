from pathlib import Path
import argparse,json,hashlib,subprocess
from fractions import Fraction
from PIL import Image,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('--film',type=Path,required=True);p.add_argument('--metadata',type=Path,required=True);a=p.parse_args();R=Path('/workspace/tennislive-efficiency');S=R/'specs/reels/davidovich-zverev-shanghai-2026-sf.json';O=Path('/workspace/scratch/zverev-sf-outlook-final-qc/root');O.mkdir(parents=True,exist_ok=True);F=O/'frames';F.mkdir(exist_ok=True);sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec=json.loads(S.read_text());inp=json.loads((a.metadata/'render_inputs.json').read_text());binding=json.loads((a.metadata/'audio_review_binding.json').read_text());rd=json.loads((a.metadata/'render.json').read_text());qc=json.loads((a.metadata/'qc_attestation.json').read_text());assert sha(a.film)==inp['film_sha256']==rd['film_sha256']==qc['film_sha256'];assert sha(S)==inp['spec_sha256'];ass=a.metadata/'subtitles.ass';assert sha(ass)==inp['artifacts']['subtitles.ass']==qc['ass_sha256'];assert qc['status']=='pass';pb=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(a.film)]));v=next(x for x in pb['streams']if x['codec_type']=='video');fps=float(Fraction(v['r_frame_rate']));nf=int(v['nb_frames']);dur=float(pb['format']['duration']);rows={};tl=binding['timeline'];offsets=tl['offsets'];lengths=tl['lengths']
def add(t,reason,**extra):
 k=max(0,min(nf-1,round(t*fps)));rows.setdefault(k,[]).append({'kind':reason,**extra})
def tc(s):
 h,m,x=s.split(':');return int(h)*3600+int(m)*60+float(x)
cues=[]
for line in ass.read_text().splitlines():
 if not line.startswith('Dialogue:'):continue
 x=line.split(',',9);start,end=tc(x[1]),tc(x[2]);mid=(start+end)/2;i=next((i for i,(o,n)in enumerate(zip(offsets,lengths))if o<=mid<o+n),None)
 if i is not None and 'source'not in spec['segments'][i]:
  c={'cue_global_index':sum(1 for l in ass.read_text().splitlines()[:ass.read_text().splitlines().index(line)+1]if l.startswith('Dialogue:')),'start':start,'end':end,'text':x[9],'segment':i};cues.append(c);add(mid,'non_source_ass_midpoint',**c)
for t in [.12,.6,tl['cover_seconds']-.12]:add(t,'cover')
for i,(off,ln)in enumerate(zip(offsets,lengths)):
 if 'source'not in spec['segments'][i]:add(off+ln/2,'card_midpoint',segment=i)
 for delta in [-.08,.04]:add(off+ln+delta,'segment_seam',segment=i,delta=delta)
end7=offsets[6]+lengths[6]
for j in range(-7,8):
 k=round(end7*fps)+j;rows.setdefault(k,[]).append({'kind':'ending_to_stat_card_exact_tail','relative_frames':j,'boundary':end7,'integer_frame_sampling':True})
for t in [dur-4,dur-1.5,dur-.12]:add(t,'outro')
keys=sorted(rows);expr='+'.join(f'eq(n\\,{k})'for k in keys);subprocess.run(['ffmpeg','-v','error','-threads','2','-i',str(a.film),'-vf','select='+expr,'-fps_mode','vfr',str(F/'sample-%03d.png')],check=True);items=[]
for j,k in enumerate(keys,1):
 dest=F/f'frame-{k:05}.png';(F/f'sample-{j:03}.png').rename(dest);items.append({'frame_index':k,'film_time_s':k/fps,'image':str(dest),'image_sha256':sha(dest),'reasons':rows[k],'actually_viewed_on_contact_sheet':False,'original_png_actually_viewed':False})
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16);walls=[]
for b in range(0,len(items),6):
 sub=items[b:b+6];im=Image.new('RGB',(1080,1030),'#14181e');dr=ImageDraw.Draw(im)
 for j,x in enumerate(sub):
  xx=j%3*360;yy=j//3*515;small=Image.open(x['image']);small.thumbnail((342,456));im.paste(small,(xx+9,yy+45));dr.text((xx+9,yy+5),f"#{x['frame_index']} {x['film_time_s']:.2f}s",font=font);dr.text((xx+9,yy+25),x['reasons'][0]['kind'][:34],font=font)
 pp=O/f'wall-{b//6:02}.jpg';im.save(pp,quality=94);walls.append({'image':str(pp),'sha256':sha(pp),'frame_indices':[x['frame_index']for x in sub],'actually_viewed':False})
manifest={'schema':'tennislive.partitioned-final-movie-visual-frame-manifest.v1','partition':'cover_cards_outro_seams_and_exact_ending_tail','movie':str(a.film),'movie_sha256':sha(a.film),'movie_bytes':a.film.stat().st_size,'spec_sha256':sha(S),'ass_sha256':sha(ass),'render_inputs_sha256':sha(a.metadata/'render_inputs.json'),'native_qc_sha256':sha(a.metadata/'qc_attestation.json'),'fps':fps,'canvas':[v['width'],v['height']],'film_seconds':dur,'total_movie_frames':nf,'assigned_ass_cues':cues,'samples':items,'walls':walls,'ending_source_tail_boundary':end7,'limitations':['Finite root partition only; source/action partner review is separate.','No humanlistening/allframes/fullhorizontalcourt claims.','No loudness/gain/threshold silence/PCM checks.']};(O/'frame_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'samples':len(items),'walls':len(walls),'assigned_ass':len(cues),'movie_sha256':manifest['movie_sha256'],'ending_boundary':end7}))
