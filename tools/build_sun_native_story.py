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
    visual=row.get('visual')
    seg=E.ExplainerSegment(kind='cover' if row.get('_cover') else 'cause',label=row.get('kicker','孙心然的来时路'),title=row.get('title_card',''),narration=row.get('narration',''),image=row.get('image',''),points=tuple(row.get('points',[])),gloss=row.get('gloss',''),visual=visual)
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
    seconds=max(float(row.get('seconds',row.get('end',0)-row.get('start',0))),duration(audio) if audio else 0)
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
        cmd=['ffmpeg','-y','-v','error','-filter_complex_threads','1','-ss',str(row['start']),'-t',str(seconds+FADE),'-i',picture]
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
    ap=argparse.ArgumentParser();ap.add_argument('--audio',type=Path,required=True);ap.add_argument('--sources',type=Path,required=True);ap.add_argument('--outdir',type=Path,required=True);ap.add_argument('--preview',action='store_true');a=ap.parse_args()
    out=a.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    spec=json.loads((ROOT/'specs/explainers/sun-xinran-coming-of-age-2026.production.json').read_text())
    sources=a.sources.resolve();audio=a.audio.resolve();topic='孙心然的来时路';fonts=E._ASS_EN_FONT_FILE.parent
    locked={r['id']:r for r in json.loads((audio/'locked-manifest.json').read_text())['chapters']}
    for chapter in spec['chapters']:
        r=locked[chapter['id']];assert r['narration']==chapter['narration'] and sha(audio/r['audio'])==r['sha256']
    # Actual original S01: first sentence ends at 3.052041s; next begins 3.514333s.
    # Cover speaks that sentence, and holds across its natural pause; no silence prepend.
    cut=101/FPS;first=out/'S01-cover.wav';rest=out/'S01-body.wav'
    run(['ffmpeg','-y','-v','error','-i',audio/'S01.mp3','-af',f'atrim=end={cut},asetpts=PTS-STARTPTS','-c:a','pcm_s16le',first])
    run(['ffmpeg','-y','-v','error','-i',audio/'S01.mp3','-af',f'atrim=start={cut},asetpts=PTS-STARTPTS','-c:a','pcm_s16le',rest])
    marks=json.loads((audio/'S01.words.json').read_text());shifted=[]
    for m in marks:
        if m['offset']/1e7 >= cut:
            shifted.append(dict(m,offset=round(m['offset']-cut*1e7)))
    rest.with_suffix('.words.json').write_text(json.dumps(shifted,ensure_ascii=False))
    first_sentence='十六岁的孙心然，把名字写进了中网历史。'
    assert spec['chapters'][0]['narration'].startswith(first_sentence)
    cover_image=str(sources/'sun-usopen-trophy.jpg');portrait=str(sources/'sun-beijing-photo.jpg')
    cover=dict(_cover=True,image=cover_image,title_card='16岁写进中网历史\n这一步，她走了很多年',narration=first_sentence,seconds=cut,gloss='孙心然的来时路')
    rows=[(cover,first),(dict(source='lys',start=76.12,end=76.12+duration(rest),narration=spec['chapters'][0]['narration'][len(first_sentence):]),rest)]
    # Preserve a complete official key rally and native bilingual commentary.
    quote=dict(source='lys',start=49,end=74.4,quote=[dict(at=21.66,end=22.94,text="Oh, you're kidding me.\n噢，简直不可思议！"),dict(at=23.86,end=25.06,text="Is there anything she can't do?\n她还有什么做不到的？")])
    rows.append((quote,None))
    chapter_cards={1:('01','从深圳出发'),3:('02','在青少年赛场积累'),6:('03','把积累带进成人赛场')}
    contexts=['中网年龄纪录','从深圳，到贝尔格莱德','2025年11月 · 埃及两站W15','2025橘子碗 · 2026米兰','2026法网、温网 · 两次亚军','2026美网 · 青少年女单冠军','2026中网 · 首次巡回赛正赛','肯定已经取得的成绩，让成长继续']
    takeaways=['两场胜利，写进中网历史','家人、教练与训练，一路相伴','连续两项W15冠军，积累职业胜场','两项J500冠军，阶段成绩继续向前','两次进入决赛，首冠仍在前方','连续第三次决赛，终于拿到首冠','两胜、首场Top50胜利，以及新的挑战','保持健康，也保有探索自己网球的空间']
    def split_chapter(ch, sentence_count):
        text=ch['narration'];stops=[m.end() for m in __import__('re').finditer('[。！？]',text)];at=stops[sentence_count-1]
        marks=json.loads((audio/f"{ch['id']}.words.json").read_text());spans=E.token_spans(text,[m['text'] for m in marks]);left=[j for j,(lo,hi,_) in enumerate(spans) if hi<=at];last=left[-1];end=(marks[last]['offset']+marks[last]['duration'])/1e7;next_start=marks[last+1]['offset']/1e7
        cut=round(((end+next_start)/2)*FPS)/FPS
        first=out/f"{ch['id']}-chapter.wav";rest=out/f"{ch['id']}-body.wav"
        for target,filt in [(first,f'atrim=end={cut}'),(rest,f'atrim=start={cut}')]:run(['ffmpeg','-y','-v','error','-i',audio/f"{ch['id']}.mp3",'-af',filt+',asetpts=PTS-STARTPTS','-c:a','pcm_s16le',target])
        leftmarks=marks[:last+1];rightmarks=[dict(m,offset=round(m['offset']-cut*1e7)) for m in marks[last+1:]]
        first.with_suffix('.words.json').write_text(json.dumps(leftmarks,ensure_ascii=False));rest.with_suffix('.words.json').write_text(json.dumps(rightmarks,ensure_ascii=False))
        return text[:at],first,text[at:],rest,cut
    for i,ch in enumerate(spec['chapters'][1:],1):
        chapter_text=ch['narration'];chapter_audio=audio/f"{ch['id']}.mp3"
        if i in chapter_cards:
            number,title=chapter_cards[i]
            first_text,first_audio,chapter_text,chapter_audio,chapter_cut=split_chapter(ch,2 if ch['id'] in {'S02','S07'} else 1)
            rows.append((dict(title_card=title,kicker=number,image=portrait,narration=first_text,seconds=chapter_cut,points=()),first_audio))
        if ch['id']=='S07':
            # Source WTA R2: exact native clip window; no pasted scoreboard.
            row=dict(source='bucsa',start=50,end=50+duration(chapter_audio),narration=chapter_text)
        else:
            image=cover_image if ch['id']=='S06' else portrait
            caption='孙心然 · 2026美网夺冠后（Getty Images / WTA）' if ch['id']=='S06' else '孙心然 · 2026中网实拍（Jimmie48 / WTA）'
            row=dict(title_card=ch['title'],kicker=ch['id'],image=image,narration=chapter_text,visual=dict(layout='case',photo=image,context=contexts[i],caption=caption,takeaway=takeaways[i]))
        rows.append((row,chapter_audio))
    selected=rows[:5] if a.preview else rows;parts=[];lengths=[];records=[]
    for i,(row,voice) in enumerate(selected):
        print(f'[Sun native {i+1}/{len(selected)}]',flush=True)
        part,length,record=render_row(row,i,voice,out,sources,topic,fonts);parts.append(part);lengths.append(length);records.append(record)
    # Explicit native chapters are generated in preview for visual review too.
    for i,(row,_) in enumerate(rows):
        if row.get('kicker') in {'01','02','03'}:native_slide(row,100+i,out,topic)
    final=join(parts,lengths,out);dest=out/('sun-native-story-preview.mp4' if a.preview else 'sun-native-story.mp4');shutil.copyfile(final,dest)
    run(['ffmpeg','-v','error','-i',dest,'-f','null','-'])
    report=dict(status='review_only_not_published',human_listened=False,audio_review_pass=None,visual_review_pass=None,template='src/tennislive/video/explainer.py',template_sha256=sha(E.__file__),native_calls=['E.render_explainer_slides','E._render_intro_badge','E.write_subtitles','E.dissolve_chain'],reference='output/2026-10-06/explainer/medvedev-beijing-default-2026/slide_00.jpg',film_sha256=sha(dest),film_bytes=dest.stat().st_size,probe=probe(dest),rows=records,preview=a.preview,cover_spoken_source='S01 actual original',cover_spoken_seconds=cut,scoreboard_overlays=0,source_constraints=['No childhood or Egyptian W15 dynamic source was restored. Current portraits are explicitly dated 2026; they do not impersonate childhood, training, or the W15 event.','Full source audio and new final mix still require actual listening.'])
    (out/'native-story-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(dest)
if __name__=='__main__':main()
