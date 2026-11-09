"""Inspection-only cut. Does not write render.json, QC passes, audio approvals or publication state."""
import json,sys,subprocess,threading,tempfile,functools,dataclasses
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from playwright.sync_api import Page
sys.path.insert(0,'tools')
import build_match_reel as b
from scoreboard_mask_cache import resolve_masks_cached
from tennislive.video.explainer import write_subtitles
root=Path('/workspace/scratch/5yZN0py5qSk');tempfile.tempdir=str(root/'native-tmp')
srv=ThreadingHTTPServer(('127.0.0.1',8765),functools.partial(SimpleHTTPRequestHandler,directory=str(root)));threading.Thread(target=srv.serve_forever,daemon=True).start();goto=Page.goto
def visit(self,url,*a,**k):
 if url.startswith(root.as_uri()):url='http://127.0.0.1:8765/'+url[len(root.as_uri())+1:]
 return goto(self,url,*a,**k)
Page.goto=visit
p=Path('specs/reels/pending/noskova-kostyuk-wta-finals-2026-rr.draft.json');s=b.load_spec(p);o=Path('/workspace/scratch/5yZN0py5qSk/review-cut');o.mkdir(exist_ok=True)
def run(cmd):
 print('run',cmd[0],str(cmd[-1]),flush=True)
 if (Path(str(cmd[-1])).name.startswith('part-') or Path(str(cmd[-1])).name=='assembly.mp4') and Path(str(cmd[-1])).is_file(): return
 subprocess.run(cmd,check=True)
def ff(*args):run(['ffmpeg','-y','-hide_banner','-loglevel','error','-filter_complex_threads','1','-threads','2',*map(str,args)])
urls=b.spec_sources(s);primary=next(iter(urls));sources={primary:Path('/workspace/scratch/5yZN0py5qSk/5yZN0py5qSk.mp4')};b.FPS_EXPR='25';b.FPS=25;b.resolve_crop(1920,1080,None,'',layout='full');segments=b.parse_segments(s,urls,primary)
for i in [1,6,9]:segments[i]=dataclasses.replace(segments[i],image=f'/workspace/scratch/5yZN0py5qSk/final-cards/card-{i}.mp4',full_bleed=True,subtitle_bottom=96)
for i,x in enumerate(segments):
 if not x.image and x.end>=300.4:segments[i]=dataclasses.replace(x,tail_hold=.5)
print('native masks',flush=True);resolve_masks_cached('wta',sources,segments,o,'25',.5,spec_path=p)
# Native cover preview from the actual photo and match data; no production acceptance is asserted.
payload,layout=b.resolve_cover_payload(s['cover'],o,sources=None,primary=primary,spec=s);b.render_poster(payload,o/'cover.jpg',layout)
parts=[];durations=[]
ff('-loop','1','-i',o/'cover.jpg','-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t','1.7','-vf','fps=25,format=yuv420p','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac',o/'part-cover.mp4');parts.append(o/'part-cover.mp4');durations.append(1.2)
voice_inputs=[];cues=[];cardwindows=[];offset=1.2
for i,seg in enumerate(segments):
 dest=o/f'part-{i:02d}.mp4';print('segment',i,seg.length,flush=True)
 if seg.image:
  ff('-i',seg.image,'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-t',seg.length+.5,'-vf','tpad=stop_mode=clone:stop_duration=0.5,fps=25,format=yuv420p','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac',dest)
  v=Path(f'/workspace/scratch/5yZN0py5qSk/tts/voice_{i:02d}.mp3');marks=json.load(open(v.with_suffix('.words.json')));cues+=b.subtitle_cues(b.readable(seg.narration),b.probe_duration(v),boundaries=marks,offset=offset);cardwindows.append((offset,offset+seg.length,96));voice_inputs.append((v,offset))
 else:
  if not dest.is_file(): b.cut_segment(sources[primary],seg,dest,1920,tail=.5,threads=2)
  cues+=b.explicit_quote_cues(seg.quote_cues,seg.length,offset)
 parts.append(dest);durations.append(seg.length);offset+=seg.length
outro=Path('assets/brand/outro_match.mp4');od=b.probe_duration(outro)
ff('-i',outro,'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-map','0:v:0','-map','1:a:0','-t',od,'-vf','fps=25,format=yuv420p','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac',o/'part-outro.mp4');ff('-i',outro,'-vn','-c:a','pcm_s16le',o/'brand.wav');voice_inputs.append((o/'brand.wav',offset));parts.append(o/'part-outro.mp4');durations.append(od)
ass=write_subtitles(cues,o/'draft-subtitles.ass',height=1440,bottom_margin=b.subtitle_bottom_for_boards(segments,column='赛场之上'),bottom_margin_windows=cardwindows)
b.write_segment_topbar_ass(s,segments,1.2,o/'topbar.ass',default_lines=(s['topbar']['line1'],s['topbar']['line2']))
# Compose raw audio with native source levels. Chinese voices are mixed separately without a transition fade.
inputs=[]
for p in parts:inputs+=['-i',p]
filters=[]
for i in range(len(parts)):filters += [f'[{i}:v]setsar=1,format=yuv420p,settb=1/25,setpts=N,fps=25[v{i}]',f'[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,asetpts=PTS-STARTPTS[a{i}]']
v='v0';a='a0';at=durations[0]
for i in range(1,len(parts)):
 nv=f'vx{i}';na=f'ax{i}';filters += [f'[{v}][v{i}]xfade=transition=fade:duration=0.5:offset={at:.6f},settb=1/25,fps=25[{nv}]',f'[{a}][a{i}]acrossfade=d=0.5:c1=tri:c2=tri[{na}]'];v=nv;a=na;at+=durations[i]
ff(*inputs,'-filter_complex',';'.join(filters),'-map',f'[{v}]','-map',f'[{a}]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',o/'assembly.mp4')
ins=['-i',o/'assembly.mp4'];mix=[]
for k,(v,t) in enumerate(voice_inputs,1):ins+=['-i',v];mix.append(f'[{k}:a]adelay={round(t*1000)}|{round(t*1000)}[voice{k}]')
names=''.join(f'[voice{k}]' for k in range(1,len(voice_inputs)+1));mix.append(f'[0:a]{names}amix=inputs={len(voice_inputs)+1}:normalize=0:duration=first[a]')
fontdir=Path('assets/fonts').resolve();vf=f"ass={ass}:fontsdir={fontdir},ass={o/'topbar.ass'}:fontsdir={fontdir},drawtext=fontfile=assets/fonts/NotoSansSC-Regular-sub.ttf:text='审片版':fontsize=24:fontcolor=white@0.7:x=w-tw-24:y=112:shadowx=1:shadowy=1"
ff(*ins,'-filter_complex',';'.join(mix),'-map','0:v','-map','[a]','-vf',vf,'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',o/'review.mp4')
(o/'review-status.json').write_text(json.dumps({'kind':'inspection_only','production_ready':False,'reason':'One short source commentary prefix remains unverified; draft subtitle uses an ellipsis. No production QC or publish acceptance claimed.','pending':s.get('_caption_pending'),'source_sha256':'2ba2e09bd528c6e411480389c6c7603bff17c3e6a19adf17b4f9408940f2135b','duration_expected':sum(durations)},ensure_ascii=False,indent=2)+'\n')
srv.shutdown();print('REVIEW READY',o/'review.mp4',flush=True)
