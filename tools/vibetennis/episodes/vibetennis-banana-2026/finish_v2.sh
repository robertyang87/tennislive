#!/bin/bash
# After c06960/c07200/c07440 anchors exist: overlay → vfx → patch → remux → qc/preview.
set -euo pipefail
EP=/workspace/tennislive/tools/vibetennis/episodes/vibetennis-banana-2026
ROOT=/workspace/tennislive
cd "$EP"
LOG=$EP/log/finish_v2.log
exec >>"$LOG" 2>&1
echo "==== finish_v2 start $(date '+%F %T %Z') ===="
wait_anchors(){
  local n=0
  while [ ! -f /tmp/ep14_seg/c06960.mp4.anchors.json ] || [ ! -f /tmp/ep14_seg/c07200.mp4.anchors.json ] || [ ! -f /tmp/ep14_seg/c07440.mp4.anchors.json ]; do
    n=$((n+1))
    echo "$(date '+%T') waiting for end-segment anchors ($n) ..."
    ls -lh /tmp/ep14_seg/c06960.mp4 /tmp/ep14_seg/c07200.mp4 /tmp/ep14_seg/c07440.mp4 2>/dev/null || true
    sleep 30
    if [ $n -gt 80 ]; then echo "timeout waiting for anchors"; exit 1; fi
  done
  echo "$(date '+%T') end segments ready"
  ls -lh /tmp/ep14_seg/c06960.mp4 /tmp/ep14_seg/c07200.mp4 /tmp/ep14_seg/c07440.mp4 \
         /tmp/ep14_seg/c06960.mp4.anchors.json /tmp/ep14_seg/c07200.mp4.anchors.json /tmp/ep14_seg/c07440.mp4.anchors.json
}
wait_anchors

# overlay (backup any leftover incomplete)
if [ -f r3d/full_ov_zh.mp4 ]; then
  mv r3d/full_ov_zh.mp4 r3d/full_ov_zh_prefinish_$(date +%H%M%S).mp4
fi
echo "$(date '+%T') overlay ..."
VT_LANG=zh python3 overlay.py r3d/list.txt r3d/full_ov_zh.mp4 $(ls r3d/seg/c*.mp4.anchors.json | sort) | grep -v -i fontconfig || true
ls -lh r3d/full_ov_zh.mp4
ffprobe -v error -show_entries stream=nb_frames,duration -of default=nw=1 r3d/full_ov_zh.mp4

# vfx
if [ -f r3d/full_vfx_zh.mp4 ]; then
  # keep v1 already backed up; any newer stray gets a stamp
  [ -f r3d/full_vfx_zh_v1.mp4 ] && mv r3d/full_vfx_zh.mp4 r3d/full_vfx_zh_prepatch_$(date +%H%M%S).mp4 || mv r3d/full_vfx_zh.mp4 r3d/full_vfx_zh_v1.mp4
fi
echo "$(date '+%T') vfx ..."
python3 vfx.py r3d/full_ov_zh.mp4 r3d/full_vfx_zh.mp4
ls -lh r3d/full_vfx_zh.mp4

# patch seam + flash
echo "$(date '+%T') patch seam+flash ..."
mv r3d/full_vfx_zh.mp4 r3d/full_vfx_zh_unpatched.mp4
python3 patch_vfx.py r3d/full_vfx_zh_unpatched.mp4 r3d/full_vfx_zh.mp4 /tmp/ep14_qc/patch
ls -lh r3d/full_vfx_zh.mp4

# audio: trim to vfx duration, loudness, delay, aac
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 r3d/full_ov_zh.mp4)
echo "overlay duration $D"
# backup current finals already in sfx/_bak_v1_20261123
ffmpeg -y -loglevel error -i sfx/sfx_bed_zh.wav -af "atrim=0:$D" -ac 2 -c:a pcm_f32le sfx/trim_zh.wav
python3 ln.py sfx/trim_zh.wav sfx/n14_zh.wav -14 -2.5
ffmpeg -y -loglevel error -i sfx/n14_zh.wav -af "volume=1.0dB,alimiter=limit=0.56:attack=0.5:release=40:level=false" -c:a pcm_f32le sfx/lim_zh.wav
ffmpeg -y -loglevel error -i sfx/lim_zh.wav -af "adelay=100|100" -c:a aac -b:a 256k -ar 48000 sfx/final_zh.m4a

# rename previous master/push
[ -f vibetennis-banana-2026_master.mp4 ] && mv vibetennis-banana-2026_master.mp4 vibetennis-banana-2026_master_v1.mp4
[ -f vibetennis-banana-2026_push.mp4 ] && mv vibetennis-banana-2026_push.mp4 vibetennis-banana-2026_push_v1.mp4
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
python3 $ROOT/tools/vibetennis/motion_check.py "$P" | tee /tmp/ep14_qc/motion_check_v2.log

# poster B + finalize + qc
DATE=2026-11-23
OUT=$ROOT/output/$DATE/vibetennis/$SLUG
mkdir -p "$OUT"
cp -a cover/opt_B_tall_zh.jpg "$OUT/poster.jpg"
echo "$(date '+%T') finalize ..."
python3 $ROOT/tools/vibetennis/finalize.py --slug $SLUG --date $DATE --master "$EP/$P"
echo "$(date '+%T') qc.py ..."
python3 $ROOT/tools/vibetennis/qc.py --slug $SLUG --date $DATE | tee /tmp/ep14_qc/qc_v2.log

# 720p preview
mkdir -p /workspace/ep14_preview
echo "$(date '+%T') 720p preview ..."
ffmpeg -y -loglevel error -i "$P" -map 0:v:0 -map 0:a:0 -vf "scale=-2:720" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart /workspace/ep14_preview/EP14_zh_preview_720p.mp4
ls -lh /workspace/ep14_preview/EP14_zh_preview_720p.mp4
# also copy a contact sheet
ffmpeg -y -loglevel error -i "$P" -vf "fps=1/5,scale=384:216,tile=6x6" -frames:v 1 -q:v 4 /workspace/ep14_preview/contact_sheet_zh.jpg
cp -a contact_sheet_zh.jpg "$EP/contact_sheet_zh.jpg" 2>/dev/null || true
echo "==== finish_v2 done $(date '+%F %T %Z') ===="
