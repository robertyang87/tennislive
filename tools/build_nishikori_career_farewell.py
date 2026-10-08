#!/usr/bin/env python3
"""Build an explicitly partial, footage-led Nishikori review sample.

Native story_info_band fonts/palette; full-bleed 3:4; continuous match point
through reaction; configurable fixed crop per authored shot (default centered).
No publication, download, synthetic voice, or claim of final completeness.
"""
from __future__ import annotations
import argparse
import json
import subprocess
from fractions import Fraction
from pathlib import Path
from render_story_info_band import render

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / 'work/nishikori-career-farewell/sample'


def probe(path: Path) -> dict:
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))


def default_manifest(windows: Path) -> dict:
    data = json.loads(windows.read_text())
    source = str(data['source'])
    titles = {r['id']:r for r in data['titles']}
    first, tokyo = titles['2008-delray'], titles['2012-tokyo']
    return {'status':'partial_review_sample','width':1080,'height':1440,'fps':'25/1',
            'limitations':['Only 2008 first title, 2012 Tokyo title and 2026 Tokyo departure. Not final full-career film.',
                          'Source title reel begins after service preparation; existing toss, strike and point retained.',
                          'Centered full-bleed crop can omit lateral player movement. This sample does not certify full-action coverage.',
                          'Original on-court audio only; no narration, music or subtitles yet.',
                          'Career master contains burned-in English titles partially cut by portrait framing; not clean final footage.'],
            'shots':[
                {'name':'2008-point-reaction','source':source,'start':first['point_window'][0],'end':13.0,'cx':0.5,
                 'card':['2008 德尔雷海滩','锦织圭首冠','逆转布雷克，拿下生涯第1冠'],'metric':'3-6 6-1 6-4','show_for':5.5},
                {'name':'2008-trophy','source':source,'start':34.0,'end':38.5,'cx':0.5,
                 'card':['第1座ATP冠军','梦，从这里开始','德尔雷海滩 · 2008'],'show_for':0.0},
                {'name':'2012-point-reaction','source':source,'start':tokyo['point_window'][0],'end':62.0,'cx':0.5,
                 'card':['2012 东京决赛','主场登顶','击败拉奥尼奇，拿下生涯第2冠'],'metric':'7-6(5) 3-6 6-0','show_for':5.0},
                {'name':'2012-trophy','source':source,'start':74.0,'end':78.5,'cx':0.5,
                 'card':['第2座ATP冠军','让主场沸腾','东京 · 2012'],'show_for':0.0},
                {'name':'2026-departure','source':'/workspace/scratch/tokyo-official-x-thanks.mp4',
                 'start':7.0,'end':15.0,'cx':0.5,'cy':0.35,
                 'card':['2026 东京','谢谢你，锦织圭','从第一座奖杯，到最后一次告别'],'show_for':0.0},
            ]}


def build(manifest:dict,out:Path) -> Path:
    out.mkdir(parents=True,exist_ok=True)
    width,height=manifest.get('width',1080),manifest.get('height',1440)
    parts=[]
    audit=[]
    for idx,s in enumerate(manifest['shots']):
        source=Path(s['source']); meta=probe(source)
        stream=next(st for st in meta['streams'] if st['codec_type']=='video')
        length=float(s['end'])-float(s['start'])
        if length<=0 or float(s['end'])>float(meta['format']['duration']):
            raise ValueError(f"Invalid source interval: {s['name']}")
        fps=str(manifest.get('fps','25/1'))
        # A common 25 fps timeline decimates 50 fps footage; it duplicates none
        # of the archival 25 fps frames. Landscape and portrait sources cover.
        crop_w=min(stream['width'],int(stream['height']*width/height))//2*2
        crop_h=min(stream['height'],int(stream['width']*height/width))//2*2
        cx=float(s.get('cx',0.5)); cy=float(s.get('cy',0.5))
        crop_x=int(max(0,min(stream['width']-crop_w,cx*stream['width']-crop_w/2)))//2*2
        crop_y=int(max(0,min(stream['height']-crop_h,cy*stream['height']-crop_h/2)))//2*2
        card=out/f'{idx:02d}-card.png'
        render(*s['card'],card,metric=s.get('metric',''),variant='timeline')
        # Native annotation typography, upper-right placement. The clear center
        # remains available for player faces; placement still needs visual review.
        card_width=int(s.get('card_width',560)); card_x=width-card_width-60; card_y=int(s.get('card_y',105))
        show=min(length,float(s.get('show_for',4)))
        part=out/f'{idx:02d}-{s["name"]}.mp4'
        vf=(f'[0:v]crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={width}:{height}:flags=lanczos,setsar=1,setpts=PTS-STARTPTS[v];'
            f'[1:v]scale={card_width}:-1:flags=lanczos[c];'
            f'[v][c]overlay={card_x}:{card_y}:enable=\'lt(t,{show:.3f})\':eof_action=repeat,format=yuv420p[out]')
        cmd=['ffmpeg','-v','error','-threads','2','-ss',str(s['start']),'-t',str(length),'-i',str(source),
             '-loop','1','-i',str(card),'-filter_complex_threads','1','-filter_complex',vf,'-map','[out]','-map','0:a:0?',
             '-c:v','libx264','-preset','veryfast','-crf','19','-r',fps,'-c:a','aac','-b:a','192k','-af','asetpts=PTS-STARTPTS',
             '-t',str(length),'-movflags','+faststart','-y',str(part)]
        if idx not in manifest.get('reuse_existing_parts',[]) or not part.is_file():
            subprocess.run(cmd,check=True)
        actual=probe(part)
        encoded=next(st for st in actual['streams'] if st['codec_type']=='video')
        if (encoded['width'],encoded['height'])!=(width,height) or Fraction(encoded['r_frame_rate'])!=Fraction(fps):
            raise ValueError(f'Encoded dimensions/fps differ from manifest: {part}')
        if abs(float(actual['format']['duration'])-length)>0.15:
            raise ValueError(f'Encoded duration differs from authored interval: {part}')
        parts.append(part)
        audit.append({'shot':s,'source_fps':stream['r_frame_rate'],'output_fps':fps,'crop':[crop_x,crop_y,crop_w,crop_h],
                      'actual_duration':float(actual['format']['duration']), 'card_bbox':[card_x,card_y,card_width,round(card_width*340/1200)],
                      'scope':'Partial review sample; source interval is authoritative'})
    # Straight cuts in this inspection copy keep the first existing serve frame
    # of each point intact. Final film may add headroom and 0.18s dissolves.
    listing=out/'concat.txt'
    listing.write_text('\n'.join("file '"+str(p).replace("'","'\\''")+"'" for p in parts)+'\n')
    target=out/'preview.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy','-movflags','+faststart','-y',str(target)],check=True)
    if manifest.get('subtitles_ass'):
        # Supply reviewed bilingual ASS: English above Chinese, both anchored
        # inside the lower safe area. This builder never invents transcript text.
        ass=Path(manifest['subtitles_ass']).resolve()
        if not ass.is_file():
            raise FileNotFoundError(ass)
        silent_target=out/'preview-unsubtitled.mp4'
        target.replace(silent_target)
        subtitle_filter="ass=filename='"+str(ass).replace("'","\\'")+"':fontsdir='"+str(ROOT/'assets/fonts')+"'"
        subprocess.run(['ffmpeg','-v','error','-i',str(silent_target),'-vf',subtitle_filter,
                        '-c:v','libx264','-preset','veryfast','-crf','19','-c:a','copy','-movflags','+faststart','-y',str(target)],check=True)
    timeline=0.0
    frames=[]
    for idx,(s,a) in enumerate(zip(manifest['shots'],audit)):
        for label,offset in [('start',min(1,a['actual_duration']/3)),('end',max(0,a['actual_duration']-1))]:
            path=out/f'frame-{idx:02d}-{label}.jpg'
            subprocess.run(['ffmpeg','-v','error','-ss',str(timeline+offset),'-i',str(target),'-frames:v','1','-vf','scale=540:720','-y',str(path)],check=True)
            frames.append(str(path))
        a['output_start']=timeline
        timeline+=a['actual_duration']
    result=probe(target)
    (out/'review.json').write_text(json.dumps({'manifest':manifest,'shots':audit,'frames':frames,'actual_duration':result['format']['duration'],
                                              'verification':'ffprobe dimensions/audio checked; key-frame review pending; no publication'},ensure_ascii=False,indent=2))
    return target


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path)
    ap.add_argument('--windows',type=Path,default=Path('/workspace/scratch/career-windows.json'))
    ap.add_argument('--subtitles-ass',type=Path,help='Reviewed timeline ASS; English above Chinese in lower safe area')
    ap.add_argument('--outdir',type=Path,default=DEFAULT_OUT)
    args=ap.parse_args()
    manifest=json.loads(args.manifest.read_text()) if args.manifest else default_manifest(args.windows)
    if args.subtitles_ass:
        manifest['subtitles_ass']=str(args.subtitles_ass.resolve())
    args.outdir.mkdir(parents=True,exist_ok=True)
    (args.outdir/'sample-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(build(manifest,args.outdir))

if __name__=='__main__':main()
