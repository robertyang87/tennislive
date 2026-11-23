#!/bin/bash
# After a successful concat patch into r3d/full_vfx_zh.mp4: remix, master/push, qc, preview.
set -euo pipefail
EP=/workspace/tennislive/tools/vibetennis/episodes/vibetennis-banana-2026
ROOT=/workspace/tennislive
cd "$EP"
LOG=$EP/log/finish_v5.log
exec >>"$LOG" 2>&1
echo "==== finish_v5 start $(date '+%F %T %Z') ===="

D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 r3d/full_ov_zh.mp4)
echo "overlay duration $D"
# reuse already-rebuilt voice bed; re-trim to this duration
ffmpeg -y -loglevel error -i sfx/sfx_bed_zh.wav -af "atrim=0:$D" -ac 2 -c:a pcm_f32le sfx/trim_zh.wav
python3 ln.py sfx/trim_zh.wav sfx/n14_zh.wav -14 -2.5
ffmpeg -y -loglevel error -i sfx/n14_zh.wav -af "volume=1.0dB,alimiter=limit=0.56:attack=0.5:release=40:level=false" -c:a pcm_f32le sfx/lim_zh.wav
ffmpeg -y -loglevel error -i sfx/lim_zh.wav -af "adelay=100|100" -c:a aac -b:a 256k -ar 48000 sfx/final_zh.m4a

stamp=$(date +%H%M%S)
[ -f vibetennis-banana-2026_master.mp4 ] && mv vibetennis-banana-2026_master.mp4 vibetennis-banana-2026_master_pre_v5_$stamp.mp4
[ -f vibetennis-banana-2026_push.mp4 ] && mv vibetennis-banana-2026_push.mp4 vibetennis-banana-2026_push_pre_v5_$stamp.mp4
THUMB=cover/thumb_16x9_zh.jpg
SLUG=vibetennis-banana-2026
M=${SLUG}_master.mp4
P=${SLUG}_push.mp4
echo "$(date '+%T') encode master ..."
ffmpeg -y -loglevel error -loop 1 -framerate 30 -t 0.1 -i "$THUMB" -i r3d/full_vfx_zh.mp4 -i sfx/final_zh.m4a \
  -filter_complex "[0:v]scale=1920:1080,format=yuv420p,setsar=1[a];[1:v]format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]" \
  -map "[v]" -map 2:a -c:v libx264 -preset medium -crf 16 -pix_fmt yuv420p -r 30 -c:a copy -shortest -movflags +faststart "$M"
echo "$(date '+%T') 2-pass push ..."
ffmpeg -y -loglevel error -i "$M" -map 0:v:0 -c:v libx264 -profile:v high -preset medium -b:v 7500k -fps_mode cfr -r 30 -pass 1 -passlogfile sfx/x264_zh -an -f null /dev/null
ffmpeg -y -loglevel error -i "$M" -map 0:v:0 -map 0:a -c:v libx264 -profile:v high -preset medium -b:v 7500k -maxrate 11000k -bufsize 15000k -fps_mode cfr -r 30 -pass 2 -passlogfile sfx/x264_zh -pix_fmt yuv420p -c:a copy -movflags +faststart sfx/tmp_zh.mp4
for f in "$M" "$P"; do
  src=$([ "$f" = "$P" ] && echo sfx/tmp_zh.mp4 || echo "$M")
  ffmpeg -y -loglevel error -i "$src" -i "$THUMB" -map 0 -map 1 -c copy -disposition:v:1 attached_pic -movflags +faststart sfx/att_zh.mp4 && mv sfx/att_zh.mp4 "$f"
done
rm -f sfx/tmp_zh.mp4
for f in "$M" "$P"; do echo "$f $(stat -c %s "$f") bytes"; ffmpeg -hide_banner -i "$f" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2; done

echo "$(date '+%T') motion_check ..."
mkdir -p /tmp/ep14_qc
python3 $ROOT/tools/vibetennis/motion_check.py "$P" | tee /tmp/ep14_qc/motion_check_v5.log

DATE=2026-11-23
OUT=$ROOT/output/$DATE/vibetennis/$SLUG
mkdir -p "$OUT"
cp -a cover/opt_B_tall_zh.jpg "$OUT/poster.jpg"
echo "$(date '+%T') finalize ..."
python3 $ROOT/tools/vibetennis/finalize.py --slug $SLUG --date $DATE --master "$EP/$P"
echo "$(date '+%T') qc.py ..."
python3 $ROOT/tools/vibetennis/qc.py --slug $SLUG --date $DATE | tee /tmp/ep14_qc/qc_v5.log

mkdir -p /workspace/ep14_preview
echo "$(date '+%T') 720p preview ..."
ffmpeg -y -loglevel error -i "$P" -map 0:v:0 -map 0:a:0 -vf "scale=-2:720" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart /workspace/ep14_preview/EP14_zh_preview_720p.mp4
ls -lh /workspace/ep14_preview/EP14_zh_preview_720p.mp4
ffmpeg -y -loglevel error -i "$P" -vf "fps=1/5,scale=384:216,tile=6x9" -frames:v 1 -q:v 4 /workspace/ep14_preview/contact_sheet_zh.jpg || \
ffmpeg -y -loglevel error -i "$P" -vf "fps=1/5,scale=384:216,tile=6x6" -frames:v 1 -q:v 4 /workspace/ep14_preview/contact_sheet_zh.jpg
cp -a /workspace/ep14_preview/contact_sheet_zh.jpg "$EP/contact_sheet_zh.jpg"
mkdir -p /tmp/ep14_qc/v5beats /workspace/ep14_preview/review
python3 - << 'PY'
import subprocess
from pathlib import Path
film='/workspace/tennislive/tools/vibetennis/episodes/vibetennis-banana-2026/vibetennis-banana-2026_push.mp4'
out=Path('/workspace/ep14_preview/review')
shots=[
 ('salt_miss',73.2),('salt_race',82.0),('salt_vd',87.6),
 ('fuel_bar',132.2),('fuel_all',134.5),
 ('proof_m',173.0),('proof_n',182.0),('proof_blo',188.0),('proof_none',196.8),
 ('end_k',236.0),('end_fade',239.6),('end_cho',243.0),('end_q',250.0),
 ('gi',47.0),('seam',8.10),
]
for name,t in shots:
    subprocess.run(['ffmpeg','-y','-v','error','-ss',f'{t:.3f}','-i',film,'-frames:v','1','-q:v','2',str(out/f'{t:07.1f}_{name}.jpg')],check=True)
print('review stills',len(list(out.glob('*.jpg'))))
PY
echo "==== finish_v5 done $(date '+%F %T %Z') ===="
