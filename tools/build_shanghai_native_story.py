#!/usr/bin/env python3
"""Rebuild Shanghai from clean official sources and preserved actual narration.

The approved E story template owns all typography, cards, badge and subtitles.
Never uses a burned review master; never publishes; listening stays pending.
"""
from pathlib import Path
import argparse, hashlib, json, math, os, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from tennislive.video import explainer as E, outro_page
from tennislive.design_tokens import MOTION
from PIL import Image
W,H,FPS=1080,1440,30
FADE=float(MOTION['video_dissolve_s'])

def run(cmd): subprocess.run([str(x) for x in cmd],check=True)
def probe(p): return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def sha(p): return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def duration(p): return float(probe(p)['format']['duration'])
def esc(p): return str(p).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
def encode(): return ['-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-ac','2']

def native_slide(row,index,out,topic):
    # No independently invented SVG or title layout: the repository story card.
    seg=E.ExplainerSegment(kind='cover' if row.get('_cover') else 'cause',
        label=row.get('kicker','上海网球记忆'),title=row.get('title_card',''),
        narration=row.get('narration',''),image=row.get('image',''),
        diagram='' if row.get('image') else '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 500"></svg>',
        gloss=row.get('gloss',''))
    # render_explainer_slides is the exact native CSS/font/card entrypoint.
    path=E.render_explainer_slides([seg],out/f'slide-{index:03}',topic=topic,column='网球有故事',height=H)[0]
    actual=out/f'slide-{index:03}.jpg'
    Image.open(path).resize((W,H),Image.Resampling.LANCZOS).save(actual,quality=94)
    return actual

def join(parts,lengths,out):
    if len(parts)==1:return parts[0]
    if len(parts)>7:
        batches=[];lens=[]
        for start in range(0,len(parts),7):
            dest=out/f'batch-{start//7:02}';dest.mkdir(exist_ok=True)
            batches.append(join(parts[start:start+7],lengths[start:start+7],dest));lens.append(sum(lengths[start:start+7]))
        return join(batches,lens,out)
    cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1']
    for p in parts:cmd+=['-threads','1','-i',p]
    graph=[];v=[];a=[]
    for i,length in enumerate(lengths):
        graph += [f'[{i}:v]settb=1/{FPS},setpts=PTS-STARTPTS,fps={FPS},tpad=stop_mode=clone:stop_duration={FADE+.1}[v{i}]',f'[{i}:a]apad,atrim=duration={length:.6f},asetpts=PTS-STARTPTS[a{i}]']
        v.append(f'[v{i}]');a.append(f'[a{i}]')
    graph+=E.dissolve_chain(v,lengths,FADE)
    graph+=[''.join(a)+f'concat=n={len(a)}:v=0:a=1[outa]']
    target=out/'joined.mp4'
    run(cmd+['-filter_complex',';'.join(graph),'-map','[outv]','-map','[outa]','-t',str(sum(lengths))]+encode()+[target])
    return target

def render_row(row,index,audio,out,sources,topic,fonts):
    seconds=max(float(row.get('seconds',row.get('end',0)-row.get('start',0))),duration(audio)+.5 if audio else 0)
    seconds=math.ceil(seconds*FPS)/FPS
    is_video=bool(row.get('source'))
    if is_video:
        seconds=math.ceil((float(row['end'])-float(row['start']))*FPS)/FPS
        if audio and duration(audio)>seconds+.04:
            raise ValueError(f'Source window does not fit narration: {index}')
    card=bool(row.get('title_card')) or row.get('_cover')
    if card:
        picture=native_slide(row,index,out,topic);cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1','-loop','1','-framerate',str(FPS),'-i',picture]
    elif is_video:
        picture=sources/('source_'+row['source']+'.mp4')
        cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1','-ss',str(row['start']),'-t',str(float(row['end'])-float(row['start'])),'-i',picture]
    else:
        picture=ROOT/row['image'];cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1','-loop','1','-framerate',str(FPS),'-i',picture]
    if card:
        vf=f'scale={W}:{H},setsar=1,fps={FPS}'
    else:
        badge=E._render_intro_badge(topic,'网球有故事',out/f'badge-{index:03}')
        if not badge:raise RuntimeError('Native badge rendering failed')
        cmd+=['-loop','1','-framerate',str(FPS),'-i',badge]
        if is_video:
            vf=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS}'
        else:
            vf=f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},zoompan=z=1+0.03*on/{max(1,round(seconds*FPS))}:x=iw/2-iw/zoom/2:y=ih/2-ih/zoom/2:d=1:s={W}x{H}:fps={FPS}'
    audio_index=1 if card else 2
    if audio:cmd+=['-i',audio]
    elif is_video:audio_index=0
    else:cmd+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    graph=[]
    if card:graph+=[f'[0:v]{vf}[picture]']
    else:graph+=[f'[0:v]{vf}[bg]',f'[bg][1:v]overlay=0:0:shortest=1[picture]']
    cues=[]
    if audio and not row.get('_cover'):
        marks=json.loads(audio.with_suffix('.words.json').read_text()) if audio.with_suffix('.words.json').exists() else []
        cues=E.subtitle_cues(E.readable(row['narration']),duration(audio),boundaries=marks)
    elif row.get('quote'):
        cues=[(q['at'],q['end'],q['text']) for q in row['quote']]
    if card:cues=E.drop_printed_cues(cues,row.get('title_card',''))
    ass=out/f'sub-{index:03}.ass';E.write_subtitles(cues,ass,height=H,margin_v=1284)
    graph+=[f"[picture]subtitles=filename='{esc(ass)}':fontsdir='{esc(fonts)}',format=yuv420p,tpad=stop_mode=clone:stop_duration={FADE+.1}[v]"]
    if is_video and audio:
        graph+=[f'[0:a]volume=0.33,aresample=48000,aformat=channel_layouts=stereo[bed]',f'[{audio_index}:a]aresample=48000,aformat=channel_layouts=stereo[voice]','[bed][voice]amix=inputs=2:duration=longest:normalize=0[mixed]']
        label='[mixed]'
    else:label=f'[{audio_index}:a]'
    graph+=[f'{label}apad,atrim=duration={seconds},asetpts=PTS-STARTPTS[a]']
    final=out/f'clip-{index:03}.mp4';run(cmd+['-filter_complex',';'.join(graph),'-map','[v]','-map','[a]','-t',str(seconds+FADE)]+encode()+[final])
    return final,seconds,{'index':index,'duration':seconds,'source':str(picture),'source_sha256':sha(picture),'voice_sha256':sha(audio) if audio else None,'subtitle_sha256':sha(ass),'kind':'native_card' if card else 'clean_video' if is_video else 'clean_photo'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--sources',type=Path,required=True);ap.add_argument('--audio',type=Path,required=True);ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--preview',action='store_true');args=ap.parse_args()
    out=args.outdir.resolve();out.mkdir(parents=True,exist_ok=True);spec=json.loads(args.spec.read_text());topic='上海大师赛 · 白玉兰下的传奇'
    # Recover raw MP3/words by basename, not the old runner absolute path.
    voices={p.name:p for p in args.audio.rglob('voice_*.mp3')}
    fonts=E._ASS_EN_FONT_FILE.parent
    for item in json.loads((args.sources/'sources.json').read_text()):
        assert sha(args.sources/('source_'+item['source']+'.mp4'))==item['sha256']
    cover={'_cover':True,'image':spec['cover']['portrait']['image'],'title_card':spec['cover']['hook'],'narration':spec['cover']['narration'],'gloss':'从大师杯到大师1000','seconds':duration(voices['voice_cover.mp3'])+.5}
    rows=[cover]+spec['segments'];parts=[];lengths=[];evidence=[]
    selected=rows[:4] if args.preview else rows
    for index,row in enumerate(selected):
        print(f'[native story {index+1}/{len(selected)}]',flush=True)
        audio=voices.get('voice_cover.mp3' if index==0 else f'voice_{index-1:02}.mp3') if row.get('narration') else None
        if row.get('narration') and not audio:raise ValueError(f'Missing preserved actual voice {index}')
        part,length,record=render_row(row,index,audio,out,args.sources,topic,fonts);parts.append(part);lengths.append(length);evidence.append(record)
    # Preview includes exact native chapter cards for inspection, never auto-pass.
    for i,row in enumerate(spec['segments']):
        if row.get('kicker') in {'01','02','03'}:native_slide(row,100+i,out,topic)
    if not args.preview:
        tail=out/'native-outro.mp4';seconds=duration(voices['voice_outro.mp3'])+.3
        chromium=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser')
        if not chromium:raise RuntimeError('Chromium required for real native outro')
        outro_page.render_clip(out,seconds,fps_expr=str(FPS),fps=FPS,chromium=chromium,dest=tail,audio_rate='48000',preset='veryfast',crf='21',audio_bitrate='160k',audio_channels=2)
        # Preserve the already synthesized actual outro, never synthesize fresh TTS.
        replaced=out/'outro-preserved-voice.mp4';run(['ffmpeg','-y','-v','error','-i',tail,'-i',voices['voice_outro.mp3'],'-map','0:v','-map','1:a','-c:v','copy','-af','apad','-t',str(seconds)]+['-c:a','aac','-b:a','160k',replaced]);parts.append(replaced);lengths.append(seconds)
    final=join(parts,lengths,out);dest=out/('shanghai-native-story-preview.mp4' if args.preview else 'shanghai-native-story.mp4');shutil.copyfile(final,dest)
    run(['ffmpeg','-v','error','-i',dest,'-f','null','-'])
    report={'status':'rendered_requires_visual_and_audio_review','human_listened':False,'audio_review_pass':None,'visual_review_pass':None,'template':'src/tennislive/video/explainer.py','template_sha256':sha(E.__file__),'native_calls':['E.render_explainer_slides','E._render_intro_badge','E.write_subtitles','E.dissolve_chain','outro_page.render_clip'],'reference':'output/2026-10-06/explainer/medvedev-beijing-default-2026/slide_00.jpg','reference_blob':'11bab41c1cd1a5dc228f6b1a632d3453d82ff486','film':str(dest),'film_sha256':sha(dest),'film_bytes':dest.stat().st_size,'probe':probe(dest),'rows':evidence,'preview':args.preview}
    (out/'native-story-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(dest)
if __name__=='__main__':main()
