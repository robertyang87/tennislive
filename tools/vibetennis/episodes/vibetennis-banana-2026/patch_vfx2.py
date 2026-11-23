#!/usr/bin/env python3
"""Reliable seam+flash patch via trim+concat (overlay+enable was a no-op).
- 8-frame fade-to-R on frames 232-239 toward frame 240
- replace frame 4240 with average of 4239 and 4241
"""
from __future__ import annotations
import subprocess, sys, shutil
from pathlib import Path
import numpy as np
from PIL import Image

W, H, FPS = 1920, 1080, 30
SEAM_N, CUT, FLASH = 8, 240, 4240

def run(cmd):
    print('+', ' '.join(str(c) for c in cmd[:8]), '...')
    subprocess.run(cmd, check=True)

def grab_range(src: Path, start: int, n: int, dest: Path, limit_t: float | None = None):
    dest.mkdir(parents=True, exist_ok=True)
    for p in dest.glob('*.png'):
        p.unlink()
    vf = f"select='between(n,{start},{start+n-1})',setpts=N/TB"
    cmd = ['ffmpeg','-y','-v','error']
    if limit_t is not None:
        cmd += ['-t', f'{limit_t:.3f}']
    cmd += ['-i', str(src), '-vf', vf, '-vsync','vfr','-pix_fmt','rgb24', str(dest/'f%02d.png')]
    run(cmd)
    files = sorted(dest.glob('f*.png'))
    if len(files) != n:
        raise SystemExit(f'expected {n} frames from {start}, got {len(files)}')
    return [np.asarray(Image.open(f).convert('RGB')) for f in files]

def grab_from(src: Path, start: int, n: int, dest: Path):
    """Output-seek (frame-accurate) from start, n frames."""
    dest.mkdir(parents=True, exist_ok=True)
    for p in dest.glob('*.png'):
        p.unlink()
    run(['ffmpeg','-y','-v','error','-i',str(src),'-ss',f'{start/FPS:.6f}',
         '-frames:v',str(n),'-pix_fmt','rgb24',str(dest/'f%02d.png')])
    files=sorted(dest.glob('f*.png'))
    if len(files)!=n:
        raise SystemExit(f'expected {n} frames from {start} (output seek), got {len(files)}')
    return [np.asarray(Image.open(f).convert('RGB')) for f in files]

def small(x):
    im=Image.fromarray(x).convert('L').resize((320,180), Image.BILINEAR)
    return np.asarray(im).astype(np.float32)

def gray_diff(a,b):
    return float(np.mean(np.abs(small(a)-small(b))))

def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work = Path(sys.argv[3] if len(sys.argv)>3 else '/tmp/ep14_qc/patch_v5')
    work.mkdir(parents=True, exist_ok=True)

    # frames 232..240 (9): last is R
    frames = grab_range(src, CUT-SEAM_N, SEAM_N+1, work/'seam_src', limit_t=(CUT+2)/FPS)
    R = frames[-1]
    seam_dir = work/'seam_out'; seam_dir.mkdir(exist_ok=True)
    blended=[]
    for k in range(SEAM_N):
        a = k/(SEAM_N-1)
        fr = np.clip((1-a)*frames[k].astype(np.float32) + a*R.astype(np.float32), 0, 255).astype(np.uint8)
        Image.fromarray(fr).save(seam_dir/f'f{k+1:02d}.png')
        blended.append(fr)
    # verify fade: last blended should match R, pairwise 320gray should stay under 12
    diffs=[]
    seq = blended + [R]
    for i in range(len(seq)-1):
        d=gray_diff(seq[i], seq[i+1])
        diffs.append(d)
        print(f'  fade {CUT-SEAM_N+i}->{CUT-SEAM_N+i+1}  320gray={d:.2f}')
    if max(diffs) > 11.0:
        raise SystemExit(f'fade still too sharp: max {max(diffs):.2f}')
    print(f'fade ok, max {max(diffs):.2f}')

    seam_mp4 = work/'seam.mp4'
    run(['ffmpeg','-y','-v','error','-framerate',str(FPS),'-i',str(seam_dir/'f%02d.png'),
         '-c:v','libx264','-preset','fast','-crf','12','-pix_fmt','yuv420p',
         '-video_track_timescale','30',str(seam_mp4)])

    trip = grab_from(src, FLASH-1, 3, work/'flash_src')
    # sanity: middle should be the flash (much brighter or different vs neighbours)
    d01=gray_diff(trip[0],trip[1]); d12=gray_diff(trip[1],trip[2]); d02=gray_diff(trip[0],trip[2])
    print(f'flash neighbours 4239-4240={d01:.1f} 4240-4241={d12:.1f} 4239-4241={d02:.1f}')
    avg = np.clip((trip[0].astype(np.float32)+trip[2].astype(np.float32))/2,0,255).astype(np.uint8)
    flash_dir = work/'flash_out'; flash_dir.mkdir(exist_ok=True)
    Image.fromarray(avg).save(flash_dir/'f01.png')
    flash_mp4 = work/'flash.mp4'
    run(['ffmpeg','-y','-v','error','-framerate',str(FPS),'-i',str(flash_dir/'f01.png'),
         '-c:v','libx264','-preset','fast','-crf','12','-pix_fmt','yuv420p',
         '-video_track_timescale','30',str(flash_mp4)])

    tmp = work/'patched.mp4'
    # 232 + 8 + (4240-240) + 1 + rest = 7604
    fc = (
        f"[0:v]trim=end_frame={CUT-SEAM_N},setpts=PTS-STARTPTS[a];"
        f"[1:v]setpts=PTS-STARTPTS[s];"
        f"[0:v]trim=start_frame={CUT}:end_frame={FLASH},setpts=PTS-STARTPTS[b];"
        f"[2:v]setpts=PTS-STARTPTS[f];"
        f"[0:v]trim=start_frame={FLASH+1},setpts=PTS-STARTPTS[c];"
        f"[a][s][b][f][c]concat=n=5:v=1:a=0,format=yuv420p[v]"
    )
    run(['ffmpeg','-y','-v','error','-i',str(src),'-i',str(seam_mp4),'-i',str(flash_mp4),
         '-filter_complex',fc,'-map','[v]','-c:v','libx264','-preset','medium','-crf','17',
         '-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(tmp)])

    # count frames
    out_probe = subprocess.check_output(
        ['ffprobe','-v','error','-count_frames','-select_streams','v:0',
         '-show_entries','stream=nb_read_frames,duration','-of','csv=p=0',str(tmp)], text=True).strip()
    print('patched probe', out_probe)

    # quick local motion check around seam and flash on the patched file
    def local_mc(t0,t1,label):
        raw=subprocess.run(
            ['ffmpeg','-v','error','-i',str(tmp),'-ss',str(t0),'-t',str(t1-t0),
             '-vf','fps=30,scale=320:180,format=gray','-f','rawvideo','-'],
            capture_output=True, check=True).stdout
        # use output seek? -ss after -i is in the cmd after -i... I put -ss after -i. Good.
        # wait I put -i then -ss. Good.
        fr=np.frombuffer(raw,np.uint8).reshape(-1,180,320).astype(np.float32)
        d=np.abs(np.diff(fr,axis=0)).mean(axis=(1,2))
        mx=float(d.max()) if len(d) else 0
        im=int(d.argmax()) if len(d) else 0
        print(f'  local {label} max 320gray={mx:.2f} at t≈{t0+(im+1)/30:.3f}')
        return mx

    # decode-from-start for the first 9s only (accurate)
    raw=subprocess.run(
        ['ffmpeg','-v','error','-t','9.2','-i',str(tmp),
         '-vf','fps=30,scale=320:180,format=gray','-f','rawvideo','-'],
        capture_output=True, check=True).stdout
    fr=np.frombuffer(raw,np.uint8).reshape(-1,180,320).astype(np.float32)
    d=np.abs(np.diff(fr,axis=0)).mean(axis=(1,2))
    # print around 7.5-8.3s
    for i,v in enumerate(d):
        t=(i+1)/30
        if 7.4 <= t <= 8.4:
            mark=' <<<' if v>12 else ''
            print(f'  patched t={t:.3f}  {v:.2f}{mark}')
    mx=float(d[int(7.4*30)-1:int(8.4*30)].max())
    if mx>12:
        raise SystemExit(f'seam still fails after concat patch: max {mx:.2f}')
    print(f'concat patch seam ok, max in 7.4-8.4s = {mx:.2f}')

    shutil.move(str(tmp), str(out))
    print(f'wrote {out}')

if __name__=='__main__':
    main()
