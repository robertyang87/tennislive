#!/usr/bin/env python3
"""Render the approved Sun Xinran story; no publication or synthetic QC approval.

Global voice_tracks use FINAL timeline seconds (including 0.18s overlaps).
Scene quote start/end are relative to scene start. crop_rect_xyxy is source pixels.
No video looping/freezing: duration must fit the selected source interval.
"""
from __future__ import annotations
import argparse
import hashlib
import inspect
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from PIL import Image
from tennislive.video import explainer as E, outro_page
from tennislive.design_tokens import DARK
ROOT = Path(__file__).resolve().parents[1]
W, H, FPS, FADE = 1080, 1440, 25, .20
REQUESTED_FADE = .18

def run(args):
    subprocess.run([str(x) for x in args], check=True)

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def resolve(value, base):
    p = Path(value)
    return p if p.is_absolute() else (base/p).resolve()

def escape_filter(path):
    return str(path).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")

def encode(crf, preset):
    return ['-c:v','libx264','-preset',preset,'-crf',str(crf),'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-movflags','+faststart']

def overlay(scene, dest, fonts, logo):
    # No editorial cards or invented typography in the film. Native small badge only.
    kind=scene.get('kind','video')
    if kind in ('card','data','chapter') or not scene.get('source'):
        raise ValueError('Main film is source video/photo assembly: text cards and sourceless scenes are forbidden')
    im=Image.new('RGBA',(W,H),(0,0,0,0))
    if scene.get('precomposed',False):
        if kind!='cover':raise ValueError('precomposed is restricted to the separate cover asset')
        im.save(dest);return
    stage=dest.parent/'native-assets';(stage/'assets/logo/brand').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(logo,stage/'assets/logo/brand/icon.png')
    topic=scene.get('event_label') or scene.get('chapter','')
    old=E._REPO
    try:
        E._REPO=stage;badge=E._render_intro_badge(topic,'网球有故事',dest.parent/(dest.stem+'-badge'))
    finally:E._REPO=old
    if not badge:raise RuntimeError('Native small brand badge could not render')
    im.alpha_composite(Image.open(badge).convert('RGBA'),(0,0));im.save(dest)

def original_audio_filter(scene):
    value=scene.get('source_loudnorm')
    if not value:return ''
    if not isinstance(value,dict):raise ValueError('source_loudnorm must be an explicit parameter object')
    if float(scene.get('source_gain',1))!=1:raise ValueError('Original speech loudnorm requires source_gain=1')
    allowed={'I','TP','LRA','measured_I','measured_TP','measured_LRA','measured_thresh','offset','linear'}
    if set(value)-allowed:raise ValueError('Unknown loudnorm parameter')
    values={'I':-18,'TP':-1.5,'LRA':11,**value}
    for k,v in values.items():
        if k!='linear' and (not isinstance(v,(int,float)) or not math.isfinite(v)):raise ValueError('Loudnorm parameters must be finite numbers')
    return 'loudnorm='+':'.join(f"{k}={str(v).lower() if isinstance(v,bool) else v}" for k,v in values.items())+','

def render_scene(scene, dest, overlaypath, crf, preset, base):
    if scene.get('crop_schedule'):
        schedule=scene['crop_schedule'];start=float(scene.get('start',0));duration=float(scene['duration']);finish=start+duration
        if not isinstance(schedule,list) or not schedule:raise ValueError('crop_schedule must be a nonempty list')
        work=dest.parent/(dest.stem+'-crop-schedule');work.mkdir(exist_ok=True)
        parts=[];durations=[];evidence=[];previous=start;previous_frame=0
        for i,item in enumerate(schedule):
            lo=float(item['start']);hi=float(item['end'])
            if abs(lo-previous)>.002 or hi<=lo or lo<start-.002 or hi>finish+.04:raise ValueError('crop_schedule must cover the selected source window contiguously')
            frame_end=int(math.floor((hi-start)*FPS+.5)) if i<len(schedule)-1 else int(round(duration*FPS))
            subduration=(frame_end-previous_frame)/FPS
            if subduration<1/FPS:raise ValueError('crop_schedule segment shorter than one output frame')
            sub=dict(scene);sub.pop('crop_schedule');sub.pop('source_loudnorm',None)
            sub.update(start=lo,end=hi,duration=subduration,crop_rect_xyxy=item['crop_rect_xyxy'],fit=item.get('fit',scene.get('fit','contain')))
            part=work/f'crop-{i:03}.mp4';render_scene(sub,part,overlaypath,crf,preset,base)
            encoded=float(next(v for v in probe(part)['streams'] if v['codec_type']=='video')['duration'])
            if abs(encoded-subduration)>.011:raise ValueError(f"Crop interval {i} duration drift {encoded-subduration:+.6f}s")
            parts.append(part);durations.append(encoded)
            evidence.append({'source_start':lo,'source_end':hi,'crop_rect_xyxy':item['crop_rect_xyxy'],'fit':sub['fit'],'output_start_relative':previous_frame/FPS,'output_end_relative':frame_end/FPS,'encoded_duration':encoded,'part_sha256':sha(part)})
            previous=hi;previous_frame=frame_end
        if abs(previous-finish)>.04 or abs(sum(durations)-duration)>.011:raise ValueError('crop_schedule duration must equal the unchanged logical scene duration')
        cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1']
        for part in parts:cmd+=['-threads','1','-i',part]
        graph=[];labels=[]
        for i,d in enumerate(durations):
            graph.extend([f'[{i}:v]setpts=PTS-STARTPTS,fps={FPS},setsar=1[v{i}]',f'[{i}:a]apad,atrim=duration={d},asetpts=PTS-STARTPTS[a{i}]']);labels.extend([f'[v{i}]',f'[a{i}]'])
        graph.append(''.join(labels)+f'concat=n={len(parts)}:v=1:a=1[cv][ca]');graph.append(f'[cv]fps=fps={FPS}:eof_action=pass:round=near[v]')
        norm=original_audio_filter(scene)
        if norm:graph.append('[ca]'+norm.rstrip(',')+'[a]');audio='[a]'
        else:audio='[ca]'
        run(cmd+['-filter_complex',';'.join(graph),'-map','[v]','-map',audio,'-t',str(duration)]+encode(crf,preset)+[dest])
        scene['_crop_schedule_actual']=evidence
        return
    dur=float(scene['duration']);kind=scene.get('kind','video')
    if scene.get('quotes') and float(scene.get('source_gain',1))!=1:raise ValueError('Original quote must preserve gain 1')
    cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1']
    source=resolve(scene['source'],base) if scene.get('source') else None
    if not source and dur>7: raise ValueError('No-source static cards must not exceed 7 seconds')
    photo=kind in ('photo','image','cover')
    audio=False;panel_width=W
    if source:
        if not source.is_file():raise FileNotFoundError(source)
        if photo:cmd+=['-loop','1','-framerate',str(FPS),'-i',source]
        else:
            pr=probe(source); audio=any(s['codec_type']=='audio' for s in pr['streams'])
            native_width=next(s['width'] for s in pr['streams'] if s['codec_type']=='video')
            if native_width<=640:panel_width=native_width
            panel_width=min(panel_width,int(scene.get('max_display_width',W)))
            start=float(scene.get('start',0));end=float(scene.get('end',start+dur))
            if dur>end-start+.04 or end>float(pr['format']['duration'])+.04:raise ValueError(f"{scene['id']}: duration exceeds source window; looping/freezing forbidden")
            cmd+=['-ss',str(start),'-t',str(dur),'-i',source]
    else:cmd+=['-f','lavfi','-i',f'color=c={DARK["background"]}:s={W}x{H}:r={FPS}:d={dur}']
    if scene.get('quotes') and not audio:raise ValueError('Original quote source must contain its native audio stream')
    cmd+=['-loop','1','-framerate',str(FPS),'-i',overlaypath]
    if not audio:cmd+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    rect=scene.get('crop_rect_xyxy');vf=''
    if rect:
        x0,y0,x1,y1=map(int,rect)
        if x1<=x0 or y1<=y0:raise ValueError('Invalid crop rectangle')
        vf+=f'crop={x1-x0}:{y1-y0}:{x0}:{y0},'
    fit=scene.get('fit','contain')
    if fit not in {'contain','portraitcontain','fill','imagefill','cover','centerCrop','wholewidthcrop'}:raise ValueError(f'Unsupported fit: {fit}')
    # portraitcontain and contain use the complete 1080x1440 canvas, never a 920px panel.
    fill=fit in ('fill','imagefill','cover','centerCrop')
    if fill and not photo and panel_width<W:raise ValueError('Low-resolution archive video cannot fill the canvas')
    if fill and not photo and not rect:raise ValueError('Video fill requires approved crop_rect_xyxy; no automatic tracking/cropping')
    if photo:
        zoom=float(scene.get('photo_zoom',1.04)) if not scene.get('precomposed') else 1
        if not 1<=zoom<=1.04:raise ValueError('Photo zoom must remain <=1.04')
        if fill:
            vf+=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},'
        else:
            vf+=f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={DARK["background"]},'
        vf+=f"zoompan=z='1+{zoom-1}*on/{max(1,int(dur*FPS)-1)}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS},"
    elif fill:
        vf+=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},'
    else:
        vf+=f'scale={panel_width}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={DARK["background"]},'
    vf+=f'setpts=PTS-STARTPTS,fps=fps={FPS}:eof_action=pass:round=near,setsar=1'
    gain=float(scene.get('source_gain',1))
    if audio and gain<=0:raise ValueError('Source video audio cannot be muted')
    af=f'[0:a]{original_audio_filter(scene)}aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={gain},apad,atrim=duration={dur},asetpts=PTS-STARTPTS[a]' if audio else f'[2:a]atrim=duration={dur},asetpts=PTS-STARTPTS[a]'
    graph=f'[0:v]{vf}[base];[base][1:v]overlay=0:0:shortest=1,format=yuv420p[v];{af}'
    cmd+=['-filter_complex',graph,'-map','[v]','-map','[a]','-t',str(dur)]+encode(crf,preset)+[dest];run(cmd)

def join(parts, lengths, outdir, crf, preset):
    if len(parts)==1:return parts[0],lengths[0]
    if len(parts)>8:
        batches=[];durations=[]
        for i in range(0,len(parts),8):
            stage=outdir/f'join-batch-{i//8:03}';stage.mkdir(exist_ok=True)
            movie,duration=join(parts[i:i+8],lengths[i:i+8],stage,crf,preset)
            batches.append(movie);durations.append(duration)
        return join(batches,durations,outdir,crf,preset)
    target=outdir/'joined-master.mp4';cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1']
    for part in parts:cmd+=['-threads','1','-i',part]
    graph=[]
    for i in range(len(parts)):
        graph.append(f'[{i}:v]settb=1/{FPS},setpts=PTS-STARTPTS,fps={FPS}[v{i}]')
        # AAC decoding includes packet padding. Trim each input before joining;
        # otherwise those tails accumulate and shift later native source sound.
        tail=0.0
        if i==len(parts)-1:
            streams=probe(parts[i])['streams']
            native_audio=float(next(s for s in streams if s['codec_type']=='audio')['duration'])
            if 0<native_audio-lengths[i]<=.01:tail=native_audio-lengths[i]
        graph.append(f'[{i}:a]apad,atrim=duration={lengths[i]+tail:.9f},asetpts=PTS-STARTPTS[a{i}]')
    v='v0';audio='a0';total=lengths[0]
    for i,length in enumerate(lengths[1:],1):
        nv=f'xv{i}';na=f'xa{i}'
        graph.append(f'[{v}][v{i}]xfade=transition=fade:duration={FADE}:offset={total-FADE}[{nv}]')
        graph.append(f'[{audio}][a{i}]acrossfade=d={FADE}:c1=tri:c2=tri[{na}]')
        v,audio=nv,na;total+=length-FADE
    run(cmd+['-filter_complex',';'.join(graph),'-map',f'[{v}]','-map',f'[{audio}]']+encode(16,preset)+[target])
    measured=probe(target)
    encoded=float(next(s for s in measured['streams'] if s['codec_type']=='video')['duration'])
    if abs(encoded-total)>.011:raise ValueError(f'Joined video timeline drift: expected {total:.6f}, encoded {encoded:.6f}')
    return target,encoded

def part_input_key(scene, base, logo, fonts):
    # Only the local assembly cache: no QC/auditory approval is carried forward.
    clean={k:v for k,v in scene.items() if not k.startswith('_')}
    src=resolve(scene['source'],base)
    fingerprint={'scene':clean,'source':{'path':str(src),'bytes':src.stat().st_size,'sha256':sha(src)},'logo':sha(logo),'fonts':{f.name:sha(f) for f in fonts.glob('*.ttf')},'native_subtitle_badge':sha(Path(E.__file__)),'constants':[W,H,FPS,FADE],'render_core':hashlib.sha256((''.join(inspect.getsource(f) for f in (encode,overlay,original_audio_filter,render_scene))).encode()).hexdigest()}
    return hashlib.sha256(json.dumps(fingerprint,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def main():
    a=argparse.ArgumentParser();a.add_argument('--project',type=Path,required=True);a.add_argument('--outdir',type=Path);a.add_argument('--fontsdir',type=Path,required=True);a.add_argument('--preview',action='store_true');a.add_argument('--reuse-parts',action='store_true');a.add_argument('--scene');a.add_argument('--preset',default='medium');a.add_argument('--crf',type=int,default=21);args=a.parse_args()
    if not os.environ.get('CHROMIUM_PATH') and shutil.which('chromium'):os.environ['CHROMIUM_PATH']=shutil.which('chromium')
    if not 20<=args.crf<=22:raise ValueError('Final CRF must be 20–22')
    project=args.project.resolve();base=project.parent;project_bytes=project.read_bytes();p=json.loads(project_bytes);out=(args.outdir or base/'render').resolve();out.mkdir(parents=True,exist_ok=True);(out/'project-used.json').write_bytes(project_bytes);fonts=args.fontsdir.resolve()
    for font in ['NotoSansSC-Regular-sub.ttf','NotoSansSC-Bold-sub.ttf','Inter-SemiBold.ttf']:
        if not (fonts/font).is_file():raise FileNotFoundError(fonts/font)
    logo=resolve(p.get('brand_logo',str(ROOT/'assets/logo/brand/icon-512.png')),base)
    if not logo.is_file():raise FileNotFoundError(f'True brand logo required: {logo}')
    scenes=p['scenes'];timeline=[];offset=0.;selected=[]
    for scene in scenes:
        s=dict(scene);dur=float(s.get('duration',float(s.get('end',0))-float(s.get('start',0))))
        if dur<=FADE:raise ValueError('Scene too short for dissolve')
        s['duration']=dur;s['_offset']=offset;timeline.append({'id':s['id'],'start':offset,'end':offset+dur,'duration':dur,'chapter':s.get('chapter'),'source':s.get('source')})
        if (not args.scene or args.scene==s['id']) and (not args.preview or offset<20):
            if args.preview:s['duration']=min(dur,20-offset)
            selected.append(s)
        offset+=dur-FADE
    if not selected:raise ValueError('No selected scenes')
    if args.scene:
        selected[0]['_offset']=0.;timeline=[dict(timeline[scenes.index(next(s for s in scenes if s['id']==args.scene))],start=0,end=selected[0]['duration'])]
    (out/'scene-time-map.json').write_text(json.dumps({'requested_fade_seconds':REQUESTED_FADE,'fade_seconds':FADE,'fade_frames':5,'fps':FPS,'scenes':timeline,'voice_start_semantics':'final timeline after overlaps'},ensure_ascii=False,indent=2))
    parts=[];lengths=[];cues=[];voices=list(p.get('voice_tracks',[]));timeline=[];actual_offset=0.
    for i,s in enumerate(selected):
        print(f"[scene {i+1}/{len(selected)}] {s['id']}",flush=True)
        ov=out/f'overlay-{i:03}.png';part=out/f'part-{i:03}.mp4';cache=out/f'part-{i:03}.cache.json'
        signature=part_input_key(s,base,logo,fonts)
        cached=json.loads(cache.read_text()) if args.reuse_parts and cache.is_file() and part.is_file() else None
        if cached and cached.get('input_key')==signature and cached.get('part_sha256')==sha(part):
            print(f"[cache identity verified] {s['id']}",flush=True)
            s['_crop_schedule_actual']=cached.get('crop_schedule_actual',[])
        else:
            s['_resolved_source']=str(resolve(s['source'],base));overlay(s,ov,fonts,logo);render_scene(s,part,ov,16,args.preset,base)
            cache.write_text(json.dumps({'input_key':signature,'part_sha256':sha(part),'crop_schedule_actual':s.get('_crop_schedule_actual',[]),'attestation':'actual render, local bytes identity; no QC approval'},ensure_ascii=False,indent=2))
        encoded=float(next(v for v in probe(part)['streams'] if v['codec_type']=='video')['duration'])
        if abs(encoded-s['duration'])>.011:raise ValueError(f"{s['id']}: encoded duration drift {encoded-s['duration']:+.6f}s; stop before silently shifting global narration")
        if abs(actual_offset-s['_offset'])>.011:raise ValueError(f"{s['id']}: scene start drift {actual_offset-s['_offset']:+.6f}s")
        s['_offset']=actual_offset;s['duration']=encoded
        timeline.append({'id':s['id'],'start':actual_offset,'end':actual_offset+encoded,'duration':encoded,'chapter':s.get('chapter'),'source':s.get('source'),'part_sha256':sha(part),'crop_schedule_actual':s.get('_crop_schedule_actual',[])})
        parts.append(part);lengths.append(encoded);actual_offset+=encoded-FADE
        for q in s.get('quotes',[]):
            lo=s['_offset']+float(q['start']);hi=s['_offset']+float(q['end'])
            if hi>s['_offset']+s['duration']+.02:raise ValueError('Quote exceeds its shot')
            cues.append((lo,hi,str(q['en'])+'\n'+E.readable(q['zh'])))
        if s.get('tts'):
            t=s['tts'];voices.append({'file':t.get('audio') or t.get('file'),'start':s['_offset'],'marks':t.get('marks',[]),'text':t.get('text','')})
    if not args.preview and not args.scene and p.get('outro',True):
        seconds=float(p.get('outro_seconds',4));part=out/'part-outro.mp4'
        if p.get('outro_source'):
            src=resolve(p['outro_source'],base)
            if seconds>float(probe(src)['format']['duration'])+.04:raise ValueError('Outro master shorter than requested duration')
            run(['ffmpeg','-y','-v','error','-i',src,'-t',str(seconds),'-vf',f'scale={W}:{H},setpts=PTS-STARTPTS,fps=fps={FPS}:eof_action=pass:round=near,setsar=1']+encode(args.crf,args.preset)+[part])
        else:
            chromium=shutil.which('chromium') or shutil.which('chromium-browser')
            if not chromium:raise ValueError('Existing outro asset or Chromium for native outro renderer required')
            outro_page.render_clip(out,seconds,fps_expr=str(FPS),fps=FPS,chromium=chromium,dest=part,audio_rate='48000',preset=args.preset,crf=str(args.crf),audio_bitrate='192k',audio_channels=2)
        encoded=float(next(v for v in probe(part)['streams'] if v['codec_type']=='video')['duration'])
        timeline.append({'id':'native-outro','start':actual_offset,'end':actual_offset+encoded,'duration':encoded,'source':str(src) if p.get('outro_source') else 'native outro_page','part_sha256':sha(part)});parts.append(part);lengths.append(encoded)
    joined,total=join(parts,lengths,out,args.crf,args.preset)
    # Preserve complete native-outro speech, including sub-frame audio tail.
    total=max(total,float(probe(joined)['format']['duration']))
    active=[]
    for v in voices:
        start=float(v['start']);audio=resolve(v['file'],base);duration=float(probe(audio)['format']['duration'])
        if start>=total:continue
        if args.scene:continue # Individual visual testing excludes unrelated global narration.
        text=str(v.get('text',''));E.speakable(text) # Reuse native pronunciation validation without altering approved script.
        marks=v.get('marks',[])
        if isinstance(marks,str):marks=json.loads(resolve(marks,base).read_text())
        if isinstance(marks,dict):marks=marks.get('boundaries',marks.get('marks',[]))
        cues+=E.subtitle_cues(E.readable(text),duration,boundaries=marks,offset=start)
        active.append((audio,start,duration))
    ordered=sorted(active,key=lambda v:v[1])
    for first,second in zip(ordered,ordered[1:]):
        if second[1]<first[1]+first[2]-.04:raise ValueError('Global spoken voice tracks overlap; author a non-overlapping timeline')
    if not args.preview and not args.scene and any(start+duration>total+.04 for _,start,duration in active):raise ValueError('Narration extends beyond the finished film; do not truncate speech')
    cues=[(lo,min(hi,total),txt) for lo,hi,txt in cues if lo<total and hi>lo]
    cues.sort()
    for audio,start,duration in active:
        for s in selected:
            if s.get('quotes') and start<s['_offset']+s['duration'] and start+duration>s['_offset']:raise ValueError('Narration overlaps original quote shot')
            if s.get('source') and s.get('kind','video') not in ('photo','image','cover') and not s.get('quotes') and start<s['_offset']+s['duration'] and start+duration>s['_offset'] and not .28<=float(s.get('source_gain',1))<=.4:raise ValueError('Narrated source gain must be explicitly 0.28–0.4')
    ass=out/'subtitles.ass';E.write_subtitles(cues,ass,height=H,margin_v=1284)
    cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1','-i',joined]
    for audio,_,_ in active:cmd+=['-i',audio]
    graphs=[f"[0:v]subtitles=filename='{escape_filter(ass)}':fontsdir='{escape_filter(fonts)}'[v]"];labels=['[0:a]']
    for i,(_,start,_) in enumerate(active,1):
        graphs.append(f'[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={round(start*1000)}:all=1[voice{i}]');labels.append(f'[voice{i}]')
    graphs.append(''.join(labels)+f'amix=inputs={len(labels)}:duration=first:normalize=0,alimiter=limit=0.95[a]')
    final=out/(p.get('slug','sun-xinran-story')+('-preview' if args.preview or args.scene else '')+'.mp4')
    run(cmd+['-filter_complex',';'.join(graphs),'-map','[v]','-map','[a]','-t',str(total)]+encode(args.crf,args.preset)+[final])
    (out/'scene-time-map.json').write_text(json.dumps({'requested_fade_seconds':REQUESTED_FADE,'fade_seconds':FADE,'fade_frames':5,'fps':FPS,'scenes':timeline,'voice_start_semantics':'final timeline after overlaps'},ensure_ascii=False,indent=2))
    run(['ffmpeg','-y','-v','error','-i',final,'-vf',f'fps={12/max(.1,total)},scale=270:-1,tile=4x3','-frames:v','1',out/'preview-wall.jpg'])
    source_paths=sorted({resolve(s['source'],base) for s in selected if s.get('source')})
    report={'scene_audio_filters':[{'id':s['id'],'source_gain':s.get('source_gain',1),'source_filter':original_audio_filter(s).rstrip(',')} for s in selected],'requested_fade_seconds':REQUESTED_FADE,'actual_fade_seconds':FADE,'fade_frames':5,'layout_policy':'clean source video/photo, native small badge, E.write_subtitles height1440 margin_v1284 default outline3; no editorial text cards','sources':[{'file':str(f),'bytes':f.stat().st_size,'sha256':sha(f)} for f in source_paths],'status':'rendered_requires_visual_and_audio_review','file':str(final),'bytes':final.stat().st_size,'sha256':sha(final),'probe':probe(final),'project_sha256':hashlib.sha256(project_bytes).hexdigest(),'project_matches_current':sha(project)==hashlib.sha256(project_bytes).hexdigest(),'renderer_sha256':sha(Path(__file__)),'brand_logo_sha256':sha(logo),'native_templates':{'badge':sha(Path(E.__file__)),'subtitle_and_badge':sha(Path(E.__file__))},'fontsdir':str(fonts),'fonts_sha256':{f.name:sha(f) for f in fonts.glob('*.ttf')},'subtitles_sha256':sha(ass),'scene_time_map_sha256':sha(out/'scene-time-map.json'),'voice_tracks':[{'file':str(f),'start':s,'duration':d,'sha256':sha(f)} for f,s,d in active],'audio_review_pass':None,'visual_review_pass':None,'preview':bool(args.preview or args.scene)}
    (out/'render.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(final)
if __name__=='__main__':main()
