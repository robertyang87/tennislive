#!/usr/bin/env python3
"""Author a reviewable Nishikori story assembly, never fake missing footage.

Scene sources/cuts, authored smooth crop keyframes, narrator offsets, original
English slots and real word boundaries are explicit JSON. Full 67-node timeline
remains an internal project. --full-rough exports all 67 nodes as a clearly
labelled internal film, retaining explicit source and publication gaps.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from pathlib import Path
from fractions import Fraction
from PIL import Image, ImageDraw, ImageFont
from build_nishikori_career_farewell import probe
from render_story_info_band import render as render_info

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs/production/nishikori-career-farewell'
OUT=ROOT/'work/nishikori-career-farewell/assembly'
FONT=ROOT/'assets/fonts/NotoSansSC-Bold-sub.ttf'
REGULAR=ROOT/'assets/fonts/NotoSansSC-Regular-sub.ttf'
WIDTH,HEIGHT=1080,1440
RENDER_PRESET="veryfast"


def run(args:list[str]) -> None:
    subprocess.run(args,check=True)


def ass_time(t:float) -> str:
    ticks=round(t*100);h,ticks=divmod(ticks,360000);m,ticks=divmod(ticks,6000);s,ticks=divmod(ticks,100)
    return f'{h}:{m:02d}:{s:02d}.{ticks:02d}'


def project_timeline() -> dict:
    final_path=DOCS/'final-timeline.json'
    final=json.loads(final_path.read_text())
    readiness=json.loads((DOCS/'assembly-readiness.json').read_text())
    ready={n['node_id']:n for n in readiness['nodes']}
    nodes={n['id']:n for n in final['nodes']}
    cursor=float(final['runtime']['opening_budget_seconds']);chapters=[];timeline=[]
    for chapter in final['chapters']:
        start=cursor;budget=float(chapter['target_duration_seconds'])
        for index,node_id in enumerate(chapter['node_ids']):
            n=nodes[node_id];r=ready[node_id]
            step=float(n['expected_duration_seconds'])
            if index==len(chapter['node_ids'])-1:step=start+budget-cursor
            card=n['fact_card'];windows=n['actual_source_windows']
            present=any(w.get('file_exists',Path(w.get('source','')).is_file()) for w in windows)
            timeline.append({'node_id':node_id,'sequence':n['sequence'],'chapter':chapter['chapter'],
                'start':round(cursor,3),'end':round(cursor+step,3),'allocation':'final_timeline_budget_not_final_EDL',
                'event':card['event'],'year':n['year'],'headline':card['headline'],'opponent':card.get('opponent_zh'),
                'score_Kei_first':card.get('score_kei_first'),'status':r['classification'],'source_state':n['source_state'],
                'missing_video':not present,'missing_required_video':not n['complete_node_ready'],
                'source_candidates':windows,'selected_source_segments':n['selected_source_segments'],
                'gaps':n['internal_missing_status'],'internal_placeholder_only':not present,
                'render_narration_unit_ids':n['render_narration_unit_ids']})
            cursor+=step
        chapters.append({**chapter,'start':round(start,3),'end':round(cursor,3)})
    duration=float(final['runtime']['planned_total_seconds'])
    if len(timeline)!=67 or len({n['node_id'] for n in timeline})!=67:
        raise ValueError('All 67 distinct milestone nodes must remain in the project')
    return {'title':'NarratedAssembly v1 · 锦织圭生涯告别片内部工程','status':'internal_incomplete_not_final',
            'source_timeline':str(final_path),'source_timeline_schema':final['schema'],
            'frame':final['frame'],'preview_frame':{'width':WIDTH,'height':HEIGHT,'fps':'25/1','full_bleed':True,'default_cx':.5},
            'opening':{'start':0,'end':final['runtime']['opening_budget_seconds'],'status':'not_assembled','script':final['opening']},
            'chapters':chapters,'timeline':timeline,'ending':{'start':round(cursor,3),'end':duration,'script':final['ending'],'status':'not_assembled'},
            'project_seconds':duration,'node_count':67,'coverage':readiness['counts'],'render_gate':final['render_gate'],
            'narration_units':final['narration_units'],'publication_blocked':True,
            'publication_block_reason':'Missing node video, incomplete source action and audio/crop/subtitle review pending.'}


def default_chapter() -> dict:
    audio_dir=ROOT/'work/nishikori-career-farewell/audio/chapters'
    audio=json.loads((audio_dir/'manifest.json').read_text())['chapters'][0]
    marks=json.loads((audio_dir/'01-marks.json').read_text())
    split=next(m['offset']/1e7 for m in marks if m['text']=='百慕大')
    source=str(ROOT/'work/nishikori-career-farewell/career.mp4')
    return {'title':'NarratedAssembly v1 · 第一章 少年远行（内部预览）','chapter':1,'duration':50.0,'internal_preview':True,
            'scenes':[
                {'id':'first-title-point-reaction','kind':'video','node_ids':['20080211-02'],'source':source,'in':0,'out':32,
                 'cx':.5,'cy':.5,'info':['2008 德尔雷海滩 第1冠','锦织圭','决赛逆转布雷克'],'metric':'3-6 6-1 6-4','info_for':5.5,'info_y':20},
                {'id':'first-title-trophy','kind':'video','node_ids':['20080211-02'],'source':source,'in':34,'out':42.4,'cx':.5,'cy':.5},
                {'id':'bermuda-usopen-factual-bridge','kind':'missing_video','node_ids':['20080421-14','20080825-40'],'duration':9.6,
                 'headline':'2008，继续向前','rows':['百慕大挑战赛：夺冠','美网：五盘击败费雷尔','首次晋级大满贯第四轮'],
                 'status':'facts_only_missing_corresponding_event_footage','missing_video':True},
            ],
            'narration':[
                {'audio':audio['mp3'],'marks':audio['word_boundaries'],'spoken_text':audio['spoken_text'],
                 'audio_in':0,'audio_out':split,'start':12.05,'gain':1.5,'node_ids':['19891229-01','20080211-02']},
                {'audio':audio['mp3'],'marks':audio['word_boundaries'],'spoken_text':audio['spoken_text'],
                 'audio_in':split,'audio_out':audio['duration'],'start':40.4,'gain':1.5,'node_ids':['20080421-14','20080825-40']},
            ],
            'original_slots':[{'start':9.24,'end':11.85,'en':"I'm not sure anyone could have scripted this one.",
                               'zh':'恐怕谁也写不出这样的剧本。','verification':'both ASR models agree; human hearing pending','human_heard':False}],
            'subtitle_layout':{'english_pos':[540,1284],'chinese_pos':[540,1326],'english_size':42,'chinese_size':49,
                               'fixed_position_no_collision_reflow':True,'visual_gap_target_px':[8,12]},
            'missing_nodes':['19891229-01','20080421-14','20080825-40'],
            'limitations':['Source opening begins during service action; service preparation is missing.',
                          'Full-bleed centered crop can omit lateral movement; original burned English title is partially cropped.',
                          'Narrator TTS and bilingual source line are not human-heard final audio.',
                          'Childhood/Bermuda/2008 US Open footage missing; explicitly marked factual internal bridge, never claimed as event footage.']}


def crop_expression(scene:dict,stream:dict) -> tuple[str,dict]:
    sw,sh=stream['width'],stream['height']
    cw=min(sw,int(sh*WIDTH/HEIGHT))//2*2;ch=min(sh,int(sw*HEIGHT/WIDTH))//2*2
    cy=float(scene.get('cy',.5));y=max(0,min(sh-ch,cy*sh-ch/2))
    keys=scene.get('cx_keyframes')
    if keys:
        if not scene.get('authored_pan_reason'):
            raise ValueError('A keyframed pan requires its authored exception/reason')
        if len(keys)<2 or any(b['t']<=a['t'] for a,b in zip(keys,keys[1:])):
            raise ValueError('Pan keyframes must have increasing relative scene times')
        last=keys[-1];expr=str(last['cx'])
        for a,b in reversed(list(zip(keys,keys[1:]))):
            u=f'clip((t-{a["t"]})/{b["t"]-a["t"]},0,1)'
            eased=f'({u})*({u})*(3-2*({u}))'
            lerp=f'{a["cx"]}+({b["cx"]}-{a["cx"]})*({eased})'
            expr=f'if(lt(t,{b["t"]}),{lerp},{expr})'
        x=f'clip(({expr})*{sw}-{cw/2},0,{sw-cw})'
    else:
        cx=float(scene.get('cx',.5));x=str(max(0,min(sw-cw,cx*sw-cw/2)))
    return f"crop={cw}:{ch}:x='{x}':y={round(y)}",{'source':[sw,sh],'input_resolution':[sw,sh],'input_encoded_hd_class':f'{sh}p','archival_720p_input':sh==720,'window':[cw,ch],'output_resolution':[WIDTH,HEIGHT],'crop_to_output_scale':round(WIDTH/cw,4),'does_not_claim_native_1080_input':sh<1080,'cx_keyframes':keys,'cy':cy,'pan_reason':scene.get('authored_pan_reason')}


def make_bridge(scene:dict,path:Path) -> Path:
    im=Image.new('RGB',(WIDTH,HEIGHT),(4,18,13));d=ImageDraw.Draw(im)
    if scene.get('archive_photo'):
        spec=scene['archive_photo'];photo=Image.open(spec['image_path']).convert('RGB')
        if scene.get('id')=='cover-author-intro' or spec.get('full_canvas'):
            from PIL import ImageOps
            im=ImageOps.fit(photo,(WIDTH,HEIGHT),method=Image.Resampling.LANCZOS,centering=(.5,.5));d=ImageDraw.Draw(im)
            d.text((40,1388),spec.get('scene_label_zh','档案照片')+' · '+('Getty Images' if 'Getty' in spec.get('credit','') else spec.get('credit','')),font=ImageFont.truetype(str(REGULAR),22),fill=(213,226,219),stroke_width=1,stroke_fill=(4,18,13))
            im.save(path);return path
        height=min(700,round(1080*photo.height/photo.width));photo=photo.resize((1080,height),Image.Resampling.LANCZOS);im.paste(photo,(0,420))
        d.text((54,110),('档案照片' if scene.get('publication_candidate') else '内部粗剪 · 档案照片 · 比赛原片待补'),font=ImageFont.truetype(str(FONT),32),fill=(198,246,90))
        headline=scene.get('headline','').replace('｜',' · ')
        size=min(52,int(970/max(1,len(headline))))
        d.text((54,230),headline,font=ImageFont.truetype(str(FONT),size),fill=(244,251,247))
        for i,row in enumerate(scene.get('rows',[])[:1]):
            text=row.replace('｜',' · ');size=min(42,int(970/max(1,len(text))))
            d.text((54,310+i*48),text,font=ImageFont.truetype(str(REGULAR),size),fill=(213,226,219))
        d.text((54,max(1140,420+height+30)),'照片：'+spec.get('credit',''),font=ImageFont.truetype(str(REGULAR),26),fill=(213,226,219))
        im.save(path);return path
    d.rounded_rectangle((74,118,1006,182),radius=20,outline=(198,246,90),width=2)
    d.text((104,128),('生涯记录 · 非比赛画面' if scene.get('publication_candidate') else ('内部预览 · 已核记录 · 非比赛画面' if scene.get('documentary_record') else '内部预览 · 对应赛事原片待补')),font=ImageFont.truetype(str(FONT),32),fill=(198,246,90))
    d.text((74,320),scene['headline'].replace('｜',' · '),font=ImageFont.truetype(str(FONT),66),fill=(244,251,247))
    for i,row in enumerate(scene['rows']):
        size=48 if len(row)>17 else 54
        d.text((74,510+i*145),row.replace('｜',' · '),font=ImageFont.truetype(str(REGULAR),size),fill=(213,226,219))
    d.text((74,1100),('生涯记录字卡；比赛回合与原声另段保留。' if scene.get('documentary_record') else '此屏为事实过渡，未取得这些赛事画面。'),font=ImageFont.truetype(str(REGULAR),32),fill=(213,226,219))
    im.save(path);return path


def render_scene(scene:dict,index:int,out:Path) -> tuple[Path,float,dict]:
    target=out/f'{index:02d}-{scene["id"]}.mp4'
    duration=float(scene.get('duration',float(scene.get('out',0))-float(scene.get('in',0))))
    if duration<=0:raise ValueError('Positive scene duration required')
    enc=['-c:v','libx264','-preset',RENDER_PRESET,'-crf','18','-r','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(duration),'-y',str(target)]
    if scene['kind']=='missing_video':
        image=(ROOT/scene['native_still']) if scene.get('native_still') else make_bridge(scene,out/f'{index:02d}-bridge.png')
        run(['ffmpeg','-v','error','-loop','1','-i',str(image),'-f','lavfi','-i','anullsrc=r=48000:cl=stereo','-shortest',*enc])
        return target,duration,{'missing_video':True,'facts_only_internal':not scene.get('publication_candidate',False),'documentary_visual':True}
    source=Path(scene['source']);meta=probe(source);stream=next(s for s in meta['streams'] if s['codec_type']=='video')
    crop,audit=crop_expression(scene,stream)
    filt=f'[0:v]setpts=PTS-STARTPTS,{crop},scale={WIDTH}:{HEIGHT}:flags=lanczos,setsar=1'
    args=['ffmpeg','-v','error','-threads','2','-ss',str(scene['in']),'-t',str(duration),'-i',str(source)]
    if scene.get('info'):
        card=out/f'{index:02d}-info.png';render_info(*scene['info'],card,metric=scene.get('metric',''),variant='timeline')
        args+=['-loop','1','-i',str(card)]
        filt+=f'[v];[1:v]scale=560:-1:flags=lanczos[c];[v][c]overlay=460:{scene.get("info_y",20)}:enable=\'lt(t,{scene.get("info_for",4)})\':eof_action=repeat'
    filt+='[out]'
    run(args+['-filter_complex_threads','1','-filter_complex',filt,'-map','[out]','-map','0:a:0','-af','asetpts=PTS-STARTPTS',*enc])
    return target,duration,audit


def subtitle_events(voice:dict) -> list[dict]:
    marks=json.loads(Path(voice['marks']).read_text());spoken=voice['spoken_text'];cursor=0;selected=[]
    for m in marks:
        loc=spoken.find(m['text'],cursor)
        if loc<0:raise ValueError(f'Cannot align TTS text boundary: {m["text"]}')
        endloc=loc+len(m['text']);punct=''
        while endloc<len(spoken) and spoken[endloc] in '，。！？；：、':
            punct+=spoken[endloc];endloc+=1
        cursor=endloc;start=m['offset']/1e7;end=(m['offset']+m['duration'])/1e7
        if start+1e-5>=voice['audio_in'] and start<voice['audio_out']:
            selected.append({'text':m['text']+punct,'start':voice['start']+start-voice['audio_in'],
                             'end':voice['start']+min(end,voice['audio_out'])-voice['audio_in']})
    cues=[];batch=[]
    for word in selected:
        if batch and len(''.join(w['text'] for w in batch))+len(word['text'])>20:
            cues.append({'start':batch[0]['start'],'end':batch[-1]['end'],'text':''.join(w['text'] for w in batch)});batch=[]
        batch.append(word)
        if word['text'].endswith(('，','。','！','？','；')):
            cues.append({'start':batch[0]['start'],'end':batch[-1]['end'],'text':''.join(w['text'] for w in batch)});batch=[]
    if batch:cues.append({'start':batch[0]['start'],'end':batch[-1]['end'],'text':''.join(w['text'] for w in batch)})
    merged=[]
    for cue in cues:
        if merged and (cue['end']-cue['start']<.70 or len(cue['text'])<=3) and len(merged[-1]['text']+cue['text'])<=28:
            merged[-1]['text']+=cue['text'];merged[-1]['end']=cue['end']
        else:merged.append(cue)
    return merged


def write_ass(chapter:dict,out:Path) -> Path:
    header='''[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1440\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: English,Inter 24pt SemiBold,42,&H00FFFFFF,&H000000FF,&H00151515,&H88000000,-1,0,0,0,100,100,0,0,1,3,1,2,65,65,156,1\nStyle: Chinese,Noto Sans SC Thin,49,&H00FFFFFF,&H000000FF,&H00151515,&H88000000,-1,0,0,0,100,100,0,0,1,3,1,2,65,65,114,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'''
    events=[] if chapter.get('publication_candidate') else [f'Dialogue: 1,0:00:00.00,{ass_time(chapter["duration"])},Chinese,,0,0,0,,{{\\an1\\pos(40,1398)\\fs24\\c&H9ADAC6&}}内部粗剪 · 待审 · 非最终发布版'];cues=[]
    for slot in chapter['original_slots']:
        for style,text,y in [('English',slot['en'],1284),('Chinese',slot['zh'],1326)]:
            if style=='English':
                from PIL import ImageFont
                size=42
                while size>30 and ImageFont.truetype(str(ROOT/'assets/fonts/Inter-SemiBold.ttf'),size).getlength(text)>930:size-=1
                if ImageFont.truetype(str(ROOT/'assets/fonts/Inter-SemiBold.ttf'),size).getlength(text)>930:raise ValueError('English cue requires semantic word-boundary split')
            else:size=min(49,int(930/max(1,len(text))))
            events.append(f'Dialogue: 0,{ass_time(slot["start"])},{ass_time(slot["end"])},{style},,0,0,0,,{{\\an2\\pos(540,{y})\\fs{size}}}{text}')
    for voice in chapter['narration']:
        for cue in subtitle_events(voice):
            cues.append(cue);events.append(f'Dialogue: 0,{ass_time(cue["start"])},{ass_time(cue["end"])},Chinese,,0,0,0,,{{\\an2\\pos(540,1326)\\fs{min(49,int(930/max(1,len(cue["text"]))))}}}{cue["text"]}')
    path=out/f'chapter-{int(chapter["chapter"]):02d}.ass';path.write_text(header+'\n'.join(events)+'\n')
    (out/'narration-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2));return path


def duck_curve(intervals:list[tuple[float,float]]) -> str:
    curves=[]
    for start,end in intervals:
        fadein=.12;fadeout=.16
        presence=f'if(lt(t,{start}),clip((t-{start-fadein})/{fadein},0,1),if(lte(t,{end}),1,clip(({end+fadeout}-t)/{fadeout},0,1)))'
        curves.append(f'(1-0.82*({presence}))')
    return '*'.join(curves) or '1'


def assemble(chapter:dict,out:Path) -> Path:
    if not chapter.get('internal_preview') and not chapter.get('publication_candidate'):raise ValueError('Missing-source assembly is only authorized as an internal preview')
    out.mkdir(parents=True,exist_ok=True)
    total=sum(float(s.get('duration',s.get('out',0)-s.get('in',0))) for s in chapter['scenes'])
    if abs(total-chapter['duration'])>.02:raise ValueError('Scene duration must match chapter budget')
    intervals=[]
    for v in chapter['narration']:
        end=v['start']+v['audio_out']-v['audio_in'];intervals.append((v['start'],end))
        if end>chapter['duration']+.02:raise ValueError('Narration extends beyond chapter')
        for slot in chapter['original_slots']:
            if max(v['start'],slot['start'])<min(end,slot['end']):
                raise ValueError('Narration overlaps preserved English slot; author a real pause at a word boundary')
    parts=[];scene_audit=[]
    prior_path=out/f'chapter-{int(chapter["chapter"]):02d}-review.json'
    prior=json.loads(prior_path.read_text()) if prior_path.is_file() else {}
    prior_scenes={row['scene']['id']:row for row in prior.get('scenes',[])}
    for i,s in enumerate(chapter['scenes']):
        cached=prior_scenes.get(s['id']);path=out/f'{i:02d}-{s["id"]}.mp4'
        if chapter.get('reuse_verified_scenes') and cached and cached['scene']==s and path.is_file() and s['kind']!='missing_video':
            dur=float(cached['duration']);audit={**cached['crop'],'reused_identical_reviewed_scene':True}
            encoded=probe(path);v=next(row for row in encoded['streams'] if row['codec_type']=='video')
            if (v['width'],v['height'])!=(WIDTH,HEIGHT) or abs(float(encoded['format']['duration'])-dur)>.15:
                raise ValueError('Cached scene fails dimensional/duration check')
        else:
            path,dur,audit=render_scene(s,i,out)
        parts.append((path,dur));scene_audit.append({'scene':s,'crop':audit,'duration':dur})
    args=['ffmpeg','-v','error','-threads','2'];filters=[];concat_inputs=[]
    for i,(path,dur) in enumerate(parts):
        args+=['-i',str(path)];filters.append(f'[{i}:v]trim=duration={dur},setpts=PTS-STARTPTS[v{i}]')
        filters.append(f'[{i}:a]atrim=duration={dur},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo[a{i}]');concat_inputs.append(f'[v{i}][a{i}]')
    filters.append(''.join(concat_inputs)+f'concat=n={len(parts)}:v=1:a=1[video][source]')
    filters.append(f"[source]volume='{duck_curve(intervals)}':eval=frame[ducked]")
    audio_inputs=['[ducked]']
    for j,v in enumerate(chapter['narration']):
        idx=len(parts)+j;args+=['-i',str(v['audio'])];delay=round(v['start']*1000)
        filters.append(f'[{idx}:a]atrim=start={v["audio_in"]}:end={v["audio_out"]},asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={v.get("gain",1)},adelay={delay}|{delay}[voice{j}]');audio_inputs.append(f'[voice{j}]')
    music=chapter.get('music_bed')
    if music:
        ranges=music['intervals']
        for a,z in ranges:
            for slot in chapter['original_slots']:
                if max(a,slot['start']) < min(z,slot['end']):
                    raise ValueError('Documentary music must not overlap preserved source speech')
        idx=len(parts)+len(chapter['narration']);args+=['-stream_loop','-1','-i',str(music['source'])]
        enabled='+'.join(f'between(t,{a},{z})' for a,z in ranges) or '0'
        filters.append(f'[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=duration={chapter["duration"]},asetpts=PTS-STARTPTS,volume={music.get("gain",.36)},volume=0:enable=\'not({enabled})\'[music]')
        audio_inputs.append('[music]')
    filters.append(''.join(audio_inputs)+f'amix=inputs={len(audio_inputs)}:normalize=0:duration=longest,alimiter=limit=.95:level=false[mixed]')
    ass=write_ass(chapter,out)
    filters.append(f"[video]ass=filename='{ass}':fontsdir='{ROOT/'assets/fonts'}'[out]")
    target=out/f'chapter-{int(chapter["chapter"]):02d}-narrated-preview.mp4'
    args+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[out]','-map','[mixed]',
           '-c:v','libx264','-preset',RENDER_PRESET,'-crf','18','-r','25','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
           '-t',str(chapter['duration']),'-movflags','+faststart','-y',str(target)]
    run(args)
    actual=probe(target);video=next(s for s in actual['streams'] if s['codec_type']=='video')
    if (video['width'],video['height'])!=(WIDTH,HEIGHT) or Fraction(video['r_frame_rate'])!=25:raise ValueError('Rendered frame/fps mismatch')
    if abs(float(actual['format']['duration'])-chapter['duration'])>.12:raise ValueError('Rendered chapter duration mismatch')
    review={'chapter':chapter,'scenes':scene_audit,'narration_intervals':intervals,'render_metadata':actual,
            'status':('publication_candidate_pending_native_qa' if chapter.get('publication_candidate') else 'internal_narrated_assembly_not_final'),'audio_heard_by_human':False,'bilingual_subtitle_heard_by_human':False,
            'subtitle_spacing':'Fixed English pos(540,1284), Chinese pos(540,1326), position delta42; collision reflow disabled.',
            'missing_nodes':chapter.get('missing_nodes',[node for scene in chapter['scenes'] if scene['kind']=='missing_video' for node in scene.get('node_ids',[])]),'keyframe_review':'pending'}
    (out/f'chapter-{int(chapter["chapter"]):02d}-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
    for t in [t for t in [1,5,10,15,24,35,42,47] if t < chapter['duration']-.1]:
        run(['ffmpeg','-v','error','-ss',str(t),'-i',str(target),'-frames:v','1','-vf','scale=540:720','-y',str(out/f'frame-{t:02d}.jpg')])
    return target


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,default=OUT)
    p.add_argument('--full-rough',action='store_true',help='Render all 67 nodes as an internal review film');p.add_argument('--chapter-manifest',type=Path);p.add_argument('--prepare-only',action='store_true');args=p.parse_args()
    out=args.outdir.resolve();out.mkdir(parents=True,exist_ok=True)
    project=project_timeline();(out/'project-timeline.json').write_text(json.dumps(project,ensure_ascii=False,indent=2))
    chapter=json.loads(args.chapter_manifest.read_text()) if args.chapter_manifest else default_chapter()
    (out/f'chapter-{int(chapter["chapter"]):02d}-manifest.json').write_text(json.dumps(chapter,ensure_ascii=False,indent=2))
    if not args.prepare_only:print(assemble(chapter,out))




def full_rough(out:Path) -> Path:
    """Render every node, real existing footage plus explicitly identified fact records.

    Shared narrator units play exactly once, on the last referenced node. Rally
    audio and Chinese narration are sequential, so neither masks the other.
    """
    global RENDER_PRESET
    RENDER_PRESET='ultrafast'  # Fast internal-review encode; final export has its own quality gate.
    out.mkdir(parents=True,exist_ok=True)
    final=json.loads((DOCS/'final-timeline.json').read_text())
    audio={a['chapter']:a for a in json.loads((ROOT/'work/nishikori-career-farewell/audio/chapters/manifest.json').read_text())['chapters']}
    base=ROOT/'work/nishikori-career-farewell'
    titles=json.loads((base/'twelve-titles/manifest.json').read_text())
    title_nodes=[n for n in final['nodes'] if n['fact_card'].get('title_number')]
    prefixes=['2008','2012','2013-memphis','2014-memphis','2014-barcelona','2014-kuala-lumpur','2014-tokyo','2015-memphis','2015-barcelona','2015-washington','2016-memphis','2019-brisbane']
    title_map={n['id']:[] for n in title_nodes}
    offset=0
    for i,s in enumerate(titles['shots']):
        duration=s['end']-s['start']; node=next(n for n,prefix in zip(title_nodes,prefixes) if s['name'].startswith(prefix+'-'))
        title_map[node['id']].append({'source':str(base/'twelve-titles/twelve-titles-review-bilingual.mp4'),'in':offset,'out':offset+(min(duration,2.5) if 'trophy' in s['name'] else duration),'already_framed':True})
        offset+=duration
    pivotal=json.loads((base/'pivotal-wins/manifest.json').read_text())
    pivotal_map={}
    for i,s in enumerate(pivotal['scenes']):
        path=base/'pivotal-wins'/f'{i:02d}-{s["id"]}.mp4'
        pivotal_map.setdefault(s['node_ids'][0],[]).append({'source':str(path),'in':0,'out':s['out']-s['in'],'already_framed':True})
    units_by_node={}
    for u in final['narration_units']:units_by_node.setdefault(u['node_ids'][-1],[]).append(u)
    all_parts=[];coverage=[];all_cues=[];global_time=0;used=[]
    # Existing opening is an honest documentary opening, no synthetic quote.
    opening=base/'opening/opening-candidate.mp4'
    if opening.is_file():
        duration=float(probe(opening)['format']['duration']);all_parts.append(opening);global_time+=duration
    for ch in final['chapters']:
        chout=out/f'chapter-{ch["chapter"]:02d}';chout.mkdir(exist_ok=True)
        scenes=[];voices=[];cursor=0;nodes=[n for n in final['nodes'] if n['id'] in ch['node_ids']]
        for n in nodes:
            node_start=cursor
            candidates=title_map.get(n['id'],pivotal_map.get(n['id'],n['selected_source_segments']))
            selected=[]
            for j,s in enumerate(candidates):
                src=Path(s['source'])
                if not src.is_file():continue
                a=float(s.get('in',s.get('start',0)));b=float(s.get('out',s.get('end',0)))
                if b<=a:continue
                scene={'id':f'{n["id"]}-{j}','kind':'video','node_ids':[n['id']],'source':str(src),'in':a,'out':b,'cx':.5,'cy':.5,'already_framed':s.get('already_framed',False)}
                if not scene['already_framed'] and j==0:
                    c=n['fact_card'];scene.update(info=[f"{n['year']} {c['event']}",'锦织圭',(('对手：'+c['opponent_zh']+' '+c['score_kei_first']) if len(c['score_kei_first'])>20 else ('对手：'+c['opponent_zh'])) if c['opponent_zh'] else c['event']],metric=c['score_kei_first'] if len(c['score_kei_first'])<=20 else '',info_for=min(4,b-a))
                scenes.append(scene);cursor+=b-a;selected.append(scene)
            units=units_by_node.get(n['id'],[])
            card_duration=sum(u['duration_seconds'] for u in units)
            if not selected and not units:card_duration=1.4
            if card_duration:
                c=n['fact_card'];rows=[c['kicker']]
                if c['opponent_zh']:rows.append('对手：'+c['opponent_zh'])
                if c['score_kei_first']:rows.append(c['score_kei_first'])
                rows.append('已核赛事记录 · 非比赛画面')
                if len(c['headline'])>15:headline=c['event']
                else:headline=c['headline']
                scenes.append({'id':n['id']+'-record','kind':'missing_video','node_ids':[n['id']],'duration':card_duration,'headline':headline,'rows':rows,'documentary_record':True})
                for u in units:
                    a,b=u['source_window'];voices.append({'audio':u['source'],'marks':u['word_boundary_source'],'spoken_text':audio[ch['chapter']]['spoken_text'],'audio_in':a,'audio_out':b,'start':cursor,'gain':1.5,'unit_id':u['id'],'node_ids':u['node_ids']});cursor+=b-a;used.append(u['id'])
                if not units:cursor+=card_duration
            coverage.append({'node_id':n['id'],'chapter':ch['chapter'],'start':round(global_time+node_start,3),'end':round(global_time+cursor,3),'actual_video':bool(selected),'selected_footage':selected,'narration_units':[u['id'] for u in units],'fact_record_only':not bool(selected),'complete_point_claim':False})
        manifest={'title':f'内部粗剪 · 第{ch["chapter"]}章 {ch["title"]}','chapter':ch['chapter'],'duration':cursor,'internal_preview':True,'scenes':scenes,'narration':voices,'original_slots':[],'reuse_verified_scenes':True,'limitations':['67节点粗剪，事实卡明确非对应比赛画面。','原声未全部逐句听审；纪录片来源可能包含采访或原有音乐。','全铺满档案裁切，不能声称所有原档native1080或完整动作通过。']}
        (chout/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
        for v in voices:
            for cue in subtitle_events(v):all_cues.append({**cue,'start':cue['start']+global_time,'end':cue['end']+global_time,'unit_id':v['unit_id']})
        candidate=chout/f'chapter-{ch["chapter"]:02d}-narrated-preview.mp4'
        oldreview=chout/f'chapter-{ch["chapter"]:02d}-review.json'
        same=oldreview.is_file() and json.loads(oldreview.read_text()).get('chapter')==manifest
        target=candidate if same and candidate.is_file() else assemble(manifest,chout)
        all_parts.append(target);global_time+=cursor
        (out/'progress.json').write_text(json.dumps({'completed_chapter':ch['chapter'],'duration_so_far':global_time,'status':'rendering_internal_rough'},indent=2))
    if len(used)!=len(set(used)) or len(used)!=len(final['narration_units']):raise ValueError('Narrator unit coverage failed')
    # 780s is an editorial target; user prioritizes full actual action and source sentences.
    listing=out/'concat.txt';listing.write_text(''.join(f"file '{p}'\n" for p in all_parts))
    target=out/'nishikori-career-farewell-67-node-internal-rough.mp4'
    run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart','-y',str(target)])
    metadata=probe(target)
    report={'status':'complete_67_node_internal_rough_not_final','video':str(target),'duration_seconds':float(metadata['format']['duration']),'node_count':len(coverage),'real_video_nodes':sum(n['actual_video'] for n in coverage),'fact_record_only_nodes':sum(n['fact_record_only'] for n in coverage),'all_twelve_titles_actual_video':all(next(c for c in coverage if c['node_id']==n['id'])['actual_video'] for n in title_nodes),'narration_units_once':used,'publication_blocked':True,'human_heard':False,'runtime_policy':{'soft_target_seconds':780,'hard_limit_seconds':None},'original_subtitles':{'twelve_titles':'existing bilingual review subtitles baked into reused footage','pivotal_and_other_sources':'pending verified transcription; no invented subtitles'},'limitations':['Missing event footage shown as explicitly labelled factual record.','No claim of complete service preparation, continuous crop pass or native1080 archival detail.','Original commentary subtitles carry existing verification limitations; unverified speech not transcribed.']}
    for filename,data in [('coverage.json',coverage),('captions.json',all_cues),('review.json',report),('ffprobe.json',metadata)]: (out/filename).write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return target

if __name__=='__main__':
    if '--full-rough' in __import__('sys').argv:
        print(full_rough(ROOT/'work/nishikori-career-farewell/full-assembly'))
    else:main()
