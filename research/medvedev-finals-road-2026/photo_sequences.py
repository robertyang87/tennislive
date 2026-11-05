#!/usr/bin/env python3
"""Episode-only full-canvas photographic inputs for the native reel renderer.

Manifest has entries: segment, seconds, output, shots[{path, cx, cy, label}],
optional cuts=[0, ... final seconds]. Labels are evidence only, not burned in.
No source footage, TTS, source sound or publication is changed here.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess, tempfile
from PIL import Image, ImageOps

W,H,FPS,FADE=1080,1440,25,.28

def crop_photo(path,cx,cy,out):
    with Image.open(path) as source:
        im=ImageOps.exif_transpose(source).convert('RGB')
        width,height=im.size
        ratio=W/H
        if width/height>ratio:
            crop_h=height;crop_w=height*ratio
        else:
            crop_w=width;crop_h=width/ratio
        left=max(0,min(width-crop_w,width*cx-crop_w/2))
        top=max(0,min(height-crop_h,height*cy-crop_h/2))
        box=(round(left),round(top),round(left+crop_w),round(top+crop_h))
        # Render at double size to keep the gentle push-in smooth.
        im.crop(box).resize((W*2,H*2),Image.Resampling.LANCZOS).save(out)
    return {'original_size':[width,height], 'crop_box':list(box),
            'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}

def render(row):
    shots=row['shots'];seconds=float(row['seconds']);n=len(shots)
    assert seconds>0 and n>0
    cuts=row.get('cuts',[seconds*j/n for j in range(n+1)])
    assert len(cuts)==n+1 and cuts[0]==0 and abs(cuts[-1]-seconds)<.001
    assert all(b>a+FADE for a,b in zip(cuts,cuts[1:]))
    dest=Path(row['output']);dest.parent.mkdir(parents=True,exist_ok=True)
    evidence=[]
    with tempfile.TemporaryDirectory(prefix='medvedev-photos-') as temporary:
        tmp=Path(temporary);args=[];filters=[]
        for j,shot in enumerate(shots):
            frame=tmp/f'{j}.png'
            proof=crop_photo(shot['path'],float(shot.get('cx',.5)),float(shot.get('cy',.5)),frame)
            evidence.append({**shot,**proof,'start':cuts[j],'end':cuts[j+1]})
            duration=cuts[j+1]-cuts[j]+(FADE if j<n-1 else .56)
            args+=['-loop','1','-framerate',str(FPS),'-t',str(duration),'-i',str(frame)]
            # Roughly 1.4 percent push over a typical 5-second photographic shot.
            filters.append(f'[{j}:v]zoompan=z=1+0.00011*on:x=iw/2-iw/zoom/2:y=ih/2-ih/zoom/2:d=1:s={W}x{H}:fps={FPS},trim=duration={duration},setpts=PTS-STARTPTS,fps={FPS},settb=1/{FPS},format=yuv420p[p{j}]')
        prev='p0'
        for j in range(1,n):
            nxt=f'x{j}';filters.append(f'[{prev}][p{j}]xfade=transition=fade:duration={FADE}:offset={cuts[j]},fps={FPS}[{nxt}]');prev=nxt
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_complex_threads','1',*args,'-filter_complex',';'.join(filters),'-map',f'[{prev}]','-t',str(seconds+.56),'-r',str(FPS),'-an','-c:v','libx264','-preset','fast','-crf','19','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)]
        subprocess.run(command,check=True)
    result={**row,'actual_input_seconds':seconds+.56,'fps':FPS,'canvas':[W,H],
            'transition_seconds':FADE,'shots':evidence,
            'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size}
    print(json.dumps({'segment':row['segment'],'bytes':result['bytes'],'sha256':result['sha256']},ensure_ascii=False),flush=True)
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('--only',nargs='*',type=int)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    rows=json.loads(args.manifest.read_text())
    results=[render(row) for row in rows if args.only is None or row['segment'] in args.only]
    args.evidence.parent.mkdir(parents=True,exist_ok=True)
    args.evidence.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
