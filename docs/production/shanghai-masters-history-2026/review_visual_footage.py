"""Episode-only visual inspection sheets. Does not alter video spec or templates."""
from pathlib import Path
import json
import subprocess
import math
from PIL import Image, ImageDraw, ImageFont

REPO=Path(__file__).resolve().parents[3]
OUT=REPO/'work/shanghai-masters-history-2026/visual-review'
SOURCES=REPO/'work/shanghai-masters-history-2026/sources'
REVIEW=json.loads((Path(__file__).parent/'visual-footage-review.json').read_text())
FONT=ImageFont.truetype(str(REPO/'assets/fonts/NotoSansSC-Regular-sub.ttf'),23)

def ffprobe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def sheets(key, start, end, step, name):
    source=SOURCES/f'source_{key}.mp4'
    if not source.exists(): return []
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(source),'-t',str(end-start),'-vf',f'fps={1/step},scale=1920:1080','-q:v','2',str(folder/'frame_%04d.jpg')],check=True)
    frames=sorted(folder.glob('frame_*.jpg')); result=[]
    for offset in range(0,len(frames),12):
        board=Image.new('RGB',(1520,2520),(8,14,29)); d=ImageDraw.Draw(board)
        for j,f in enumerate(frames[offset:offset+12]):
            original=Image.open(f).convert('RGB'); crop=original.crop((555,0,1365,1080))
            x=j%2*760; y=j//2*420
            board.paste(original.resize((480,270)),(x,y+47))
            board.paste(crop.resize((270,360)),(x+486,y+47))
            tm=start+(offset+j+.5)*step
            d.text((x+10,y+10),f'{key}  {tm:.2f}s  原片 / 中心3:4',font=FONT,fill='white')
        dest=folder/f'sheet_{offset//12:02d}.jpg';board.save(dest,quality=95);result.append(str(dest.relative_to(REPO)))
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    index=[]
    for key in REVIEW.get('source_expected_not_verified', [x['source'] for x in REVIEW.get('sources_verified', [])]):
        source=SOURCES/f'source_{key}.mp4'
        if not source.exists():
            print(key,'not yet present',flush=True);continue
        meta=ffprobe(source);duration=float(meta['format']['duration'])
        vs=next(s for s in meta['streams'] if s['codec_type']=='video')
        if (vs['width'],vs['height'])!=(1920,1080):raise RuntimeError((key,vs['width'],vs['height']))
        overview=sheets(key,0,duration,8,f'{key}-overview')
        index.append({'key':key,'duration':duration,'original_size':[vs['width'],vs['height']],'overview':overview})
        for w in REVIEW['existing_original_audio_windows']:
            if w['source']==key:
                one=sheets(key,max(0,w['start']-1),min(duration,w['end']+1),1,f'{key}-index{w["index"]}-1s')
                dense=sheets(key,max(0,w['start']-1),min(duration,w['end']+1),.25,f'{key}-index{w["index"]}-dense')
                index[-1].setdefault('windows',[]).append({'index':w['index'],'start':w['start'],'end':w['end'],'one_second':one,'quarter_second':dense})
        print(key,'inspection sheets generated',flush=True)
    (OUT/'frame-sheet-index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
