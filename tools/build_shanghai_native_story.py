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
import story_reference_style as R
from story_triptych_cover import render_cover
W,H,FPS=1080,1440,30
FADE=float(MOTION['video_dissolve_s'])

def run(cmd): subprocess.run([str(x) for x in cmd],check=True)
def probe(p): return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
def sha(p): return hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def duration(p): return float(probe(p)['format']['duration'])
def esc(p): return str(p).replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
def encode(): return ['-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-ar','48000','-ac','2']

def history_photo(row):
    import re
    title=row.get('title_card','');kicker=row.get('kicker','')
    text=kicker+' '+title
    base=ROOT/'assets/reel/shanghai-masters-history-2026'
    context=''
    if kicker=='01' or '2005' in text:
        name='2005-nalbandian-champion-smile.jpg'
        if kicker=='01':context='2005大师杯 · 纳尔班迪安'
    elif kicker=='02' or '2017' in text:name='federer-2017-trophy-portrait.jpg'
    elif '2012' in text or '德约救下' in text:name='2012-djokovic-champion-celebration.jpg'
    elif '2014' in text:name='2014-federer-r2-relief.jpg'
    elif '2024' in text:name='2024-sinner-winner-reaction.jpg'
    elif kicker=='03' or '2025' in text:name='2025-cousins-awards-portrait.jpg'
    else:
        name='qizhong-portrait.jpg'
        context='旗忠网球中心 · 当代实拍'
    return base/name,context

def native_slide(row,index,out,topic):
    actual=out/f'slide-{index:03}.jpg'
    if row.get('_cover'):
        base=ROOT/'assets/reel/shanghai-masters-history-2026'
        return render_cover([base/'2005-nalbandian-champion-smile.jpg',base/'federer-2017-trophy-portrait.jpg',base/'2025-cousins-awards-portrait.jpg'],
            row['title_card'].split('\n'),[('SHANGHAI 2005','大师杯逆转'),('SHANGHAI 2017','费纳决赛'),('SHANGHAI 2025','亲人相逢')],topic,actual)
    picture,context=history_photo(row)
    return R.render_photo_stage(picture,topic,row.get('kicker','历史节点'),row.get('title_card',''),actual,photo_context=context)

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
        badge=R.render_stage_overlay(topic,row.get('_story_stage','上海大师赛'),row.get('_story_detail','从大师杯到大师1000'),out/f'badge-{index:03}.png')
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
    ass=out/f'sub-{index:03}.ass';R.write_subtitles(cues,ass)
    graph+=[f"[picture]subtitles=filename='{esc(ass)}':fontsdir='{esc(fonts)}',format=yuv420p,tpad=stop_mode=clone:stop_duration={FADE+.1}[v]"]
    if is_video and audio:
        graph+=[f'[0:a]volume=0.33,aresample=48000,aformat=channel_layouts=stereo[bed]',f'[{audio_index}:a]aresample=48000,aformat=channel_layouts=stereo[voice]','[bed][voice]amix=inputs=2:duration=longest:normalize=0[mixed]']
        label='[mixed]'
    else:label=f'[{audio_index}:a]'
    graph+=[f'{label}apad,atrim=duration={seconds},asetpts=PTS-STARTPTS[a]']
    final=out/f'clip-{index:03}.mp4';run(cmd+['-filter_complex',';'.join(graph),'-map','[v]','-map','[a]','-t',str(seconds+FADE)]+encode()+[final])
    original_media=[]
    if card and row.get('_cover'):
        base=ROOT/'assets/reel/shanghai-masters-history-2026'
        original_media=[base/name for name in ['2005-nalbandian-champion-smile.jpg','federer-2017-trophy-portrait.jpg','2025-cousins-awards-portrait.jpg']]
    elif card:original_media=[history_photo(row)[0]]
    else:original_media=[picture]
    return final,seconds,{'original_media':[{'path':str(p),'sha256':sha(p)} for p in original_media],'crop':'reference triptych' if row.get('_cover') else 'center object-fit cover' if card else 'center 1080x1440; photo zoom 1.00 to 1.03' if not is_video else {'center':True,'start':row['start'],'end':row['end']},'index':index,'duration':seconds,'source':str(picture),'source_sha256':sha(picture),'voice_sha256':sha(audio) if audio else None,'subtitle_sha256':sha(ass),'kind':'native_card' if card else 'clean_video' if is_video else 'clean_photo'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--spec',type=Path,required=True);ap.add_argument('--sources',type=Path,required=True);ap.add_argument('--audio',type=Path,required=True);ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--preview',action='store_true');args=ap.parse_args()
    out=args.outdir.resolve();out.mkdir(parents=True,exist_ok=True);spec=json.loads(args.spec.read_text());topic='上海大师赛 · 白玉兰下的传奇'
    # Recover raw MP3/words by basename, not the old runner absolute path.
    voices={p.name:p for p in args.audio.rglob('voice_*.mp3')}
    fonts=E._ASS_EN_FONT_FILE.parent
    font_evidence=R.font_manifest()
    for item in json.loads((args.sources/'sources.json').read_text()):
        assert sha(args.sources/('source_'+item['source']+'.mp4'))==item['sha256']
    cover={'_cover':True,'image':spec['cover']['portrait']['image'],'title_card':spec['cover']['hook'],'narration':spec['cover']['narration'],'gloss':'从大师杯到大师1000','seconds':duration(voices['voice_cover.mp3'])+.5}
    rows=[cover]+spec['segments'];parts=[];lengths=[];evidence=[]
    stage,detail='上海大师赛','从大师杯到大师1000'
    for row in rows[1:]:
        if row.get('title_card'):stage,detail=row.get('kicker','历史节点'),row['title_card']
        row['_story_stage'],row['_story_detail']=stage,detail
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
    report={'status':'rendered_requires_visual_and_audio_review','human_listened':False,'audio_review_pass':None,'visual_review_pass':None,'font_manifest':font_evidence,'actual_words_manifest':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in args.audio.rglob('voice_*.words.json')},'source_photo_manifest':{path.name:sha(path) for path in (ROOT/'assets/reel/shanghai-masters-history-2026').glob('*.jpg')},'actual_voice_manifest':{name:{'sha256':sha(path),'bytes':path.stat().st_size} for name,path in sorted(voices.items())},'reference_style':R.reference_record(),'spec_sha256':sha(args.spec),'template':'tools/story_reference_style.py','template_sha256':sha(R.__file__),'native_core_sha256':sha(E.__file__),'cover_compositor_sha256':sha(ROOT/'tools/story_triptych_cover.py'),'native_calls':['R.render_photo_stage','R.render_stage_overlay','R.write_subtitles','story_triptych_cover.render_cover','E.dissolve_chain','outro_page.render_clip'],'reference':'output/2026-09-30/reel/medvedev-24-titles-23-cities/poster.jpg','reference_blob':'5fecda6fe1bffac7cd04794b05b99cc8247db7d6','film':str(dest),'film_sha256':sha(dest),'film_bytes':dest.stat().st_size,'probe':probe(dest),'rows':evidence,'preview':args.preview}
    (out/'native-story-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(dest)
if __name__=='__main__':main()
