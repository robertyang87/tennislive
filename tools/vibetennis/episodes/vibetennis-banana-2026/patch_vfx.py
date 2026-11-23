#!/usr/bin/env python3
"""Patch full_vfx_zh.mp4 in place (caller must have backed up):
- 8-frame fade-to-R across the c00000/c00240 seam (frames 232-239)
- replace the single-frame flash at frame 4240 with the average of its neighbours
"""
from __future__ import annotations
import subprocess, sys, shutil
from pathlib import Path
import numpy as np
from PIL import Image

W, H, FPS = 1920, 1080, 30
SEAM_N, CUT, FLASH = 8, 240, 4240

def run(cmd):
    subprocess.run(cmd, check=True)

def grab(src: Path, start: int, n: int, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    for p in dest.glob('*.png'):
        p.unlink()
    run(['ffmpeg','-y','-v','error','-ss',f'{start/FPS:.6f}','-i',str(src),
         '-frames:v',str(n),'-pix_fmt','rgb24',str(dest/'f%02d.png')])
    files=sorted(dest.glob('f*.png'))
    if len(files)!=n:
        raise SystemExit(f'expected {n} frames from {start}, got {len(files)}')
    return [np.asarray(Image.open(f).convert('RGB')) for f in files]

def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    work = Path(sys.argv[3] if len(sys.argv)>3 else '/tmp/ep14_qc/patch')
    work.mkdir(parents=True, exist_ok=True)
    # seam: frames 232..240 (9), write 8 blended into 232..239
    lefts_and_r = grab(src, CUT-SEAM_N, SEAM_N+1, work/'seam_src')
    R = lefts_and_r[-1]
    seam_dir = work/'seam_out'; seam_dir.mkdir(exist_ok=True)
    for k in range(SEAM_N):
        a = k/(SEAM_N-1)
        fr = np.clip((1-a)*lefts_and_r[k] + a*R, 0, 255).astype(np.uint8)
        Image.fromarray(fr).save(seam_dir/f'f{k+1:02d}.png')
    seam_mp4 = work/'seam.mp4'
    run(['ffmpeg','-y','-v','error','-framerate',str(FPS),'-i',str(seam_dir/'f%02d.png'),
         '-c:v','libx264','-preset','fast','-crf','12','-pix_fmt','yuv420p',str(seam_mp4)])
    # flash: frames 4239,4240,4241 — keep avg of first and third
    trip = grab(src, FLASH-1, 3, work/'flash_src')
    avg = np.clip((trip[0].astype(np.float32)+trip[2].astype(np.float32))/2,0,255).astype(np.uint8)
    flash_png = work/'flash.png'
    Image.fromarray(avg).save(flash_png)
    # overlay onto the source
    # seam starts at frame 232 → t=232/30
    t_seam = CUT-SEAM_N
    t_flash = FLASH
    tmp = work/'patched.mp4'
    fc = (
        f"[1:v]setpts=PTS-STARTPTS+{t_seam}/{FPS}[seam];"
        f"[2:v]setpts=PTS-STARTPTS+{t_flash}/{FPS},format=yuv420p[fl];"
        f"[0:v][seam]overlay=eof_action=pass:repeatlast=0:enable='between(n,{t_seam},{t_seam+SEAM_N-1})'[a];"
        f"[a][fl]overlay=eof_action=pass:repeatlast=0:enable='eq(n,{t_flash})'[v]"
    )
    run(['ffmpeg','-y','-v','error','-i',str(src),'-i',str(seam_mp4),'-loop','1','-i',str(flash_png),
         '-filter_complex',fc,'-map','[v]','-c:v','libx264','-preset','medium','-crf','17',
         '-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)])
    shutil.move(str(tmp), str(out))
    print(f'patched seam frames {t_seam}-{t_seam+SEAM_N-1} and flash frame {t_flash} → {out}')

if __name__=='__main__':
    main()
