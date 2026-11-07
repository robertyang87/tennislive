"""Episode-only photo/native-card composition, no voice/source/audio changes."""
from pathlib import Path
import argparse,hashlib,json,subprocess,tempfile
from PIL import Image,ImageOps
W,H,FPS,FADE=1080,1440,25,.28

def crop_photo(shot,out):
    with Image.open(shot['path']) as source:
        im=ImageOps.exif_transpose(source).convert('RGB');w,h=im.size
        cw=min(w,h*W/H);ch=cw*H/W
        left=max(0,min(w-cw,w*shot['cx']-cw/2));top=max(0,min(h-ch,h*shot['cy']-ch/2))
        target=(W,H) if shot.get('static') else (W*2,H*2)
        im.resize(target,Image.Resampling.LANCZOS,box=(left,top,left+cw,top+ch)).save(out)
    return {'original_size':[w,h],'crop_box':[left,top,left+cw,top+ch],
        'native_scale':W/cw,'extra_zoom':False if shot.get('static') else 'gentlefixedcentrepush',
        'source_sha256':hashlib.sha256(Path(shot['path']).read_bytes()).hexdigest()}

def render(row):
    shots=row['shots'];cuts=row['cuts'];seconds=row['seconds'];dest=Path(row['output']);dest.parent.mkdir(parents=True,exist_ok=True)
    assert len(cuts)==len(shots)+1 and cuts[0]==0 and abs(cuts[-1]-seconds)<.001
    evidence=[]
    with tempfile.TemporaryDirectory(prefix='jodar-visuals-') as folder:
        tmp=Path(folder);args=[];filters=[]
        for j,shot in enumerate(shots):
            duration=cuts[j+1]-cuts[j]+(FADE if j<len(shots)-1 else .56)
            if shot['kind']=='native_card':
                args+=['-i',shot['path']];vf=f'fps={FPS},trim=duration={duration},setpts=PTS-STARTPTS'
                proof={'source_sha256':hashlib.sha256(Path(shot['path']).read_bytes()).hexdigest(),'native_component':shot['native_component'],'extra_zoom':False}
            else:
                frame=tmp/f'{j}.png';proof=crop_photo(shot,frame)
                args+=['-loop','1','-framerate',str(FPS),'-t',str(duration),'-i',str(frame)]
                vf=(f'fps={FPS}' if shot.get('static') else f'zoompan=z=1+0.00011*on:x=iw/2-iw/zoom/2:y=ih/2-ih/zoom/2:d=1:s={W}x{H}:fps={FPS}')
                vf+=f',trim=duration={duration},setpts=PTS-STARTPTS'
            filters.append(f'[{j}:v]{vf},fps={FPS},settb=1/{FPS},format=yuv420p[p{j}]')
            evidence.append({**shot,**proof,'start':cuts[j],'end':cuts[j+1]})
        previous='p0'
        for j in range(1,len(shots)):
            nxt=f'x{j}';filters.append(f'[{previous}][p{j}]xfade=transition=fade:duration={FADE}:offset={cuts[j]},fps={FPS}[{nxt}]');previous=nxt
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-filter_complex_threads','1',*args,'-filter_complex',';'.join(filters),'-map',f'[{previous}]','-t',str(seconds+.56),'-r',str(FPS),'-an','-c:v','libx264','-preset','fast','-crf','19','-threads','2','-pix_fmt','yuv420p','-movflags','+faststart',str(dest)],check=True)
    result={**row,'shots':evidence,'actual_input_seconds':seconds+.56,'canvas':[W,H],'fps':FPS,'transition_seconds':FADE,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size}
    print(json.dumps({'id':row['id'],'bytes':result['bytes'],'sha256':result['sha256']},ensure_ascii=False),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('manifest',type=Path);ap.add_argument('--evidence',required=True,type=Path);args=ap.parse_args()
    results=[render(row) for row in json.loads(args.manifest.read_text())]
    args.evidence.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
