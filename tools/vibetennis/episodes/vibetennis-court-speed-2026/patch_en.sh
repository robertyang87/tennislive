#!/bin/bash
# 英文版：3D 里的粒子大字（four / q / idx / end）跟语言走，只重渲这几段（VT_LANG=en），叠英文叠加层后替换进 full_ov_en.mp4。
set -e; cd "$(dirname "$0")"
pgrep -f "^node cap.js" >/dev/null && { echo "还有 cap.js 在跑" >&2; exit 3; }
R="0:378 966:1092 2607:2853 5487:5918"
cd r3d; i=0; for r in $R; do a=${r%:*}; b=${r#*:}; VT_LANG=en node cap.js $a $b patch_en/p$i.mp4 1920 1080 8766 > patch_en/p$i.log 2>&1 & i=$((i+1)); sleep 8; done; wait; cd ..
i=0; for r in $R; do a=${r%:*}; OV_F0=$a VT_LANG=en python3 overlay.py r3d/patch_en/p$i.mp4 r3d/patch_en/ov$i.mp4 r3d/patch_en/p$i.mp4.anchors.json 2>&1 | grep -v -i fontconfig; i=$((i+1)); done
# 拼：原片段与补丁交替
IN="-i r3d/full_ov_en.mp4"; FC=""; LBL=""; n=0; prev=0; i=0
for r in $R; do a=${r%:*}; b=${r#*:}
  if [ $a -gt $prev ]; then FC+="[0:v]trim=start_frame=$prev:end_frame=$a,setpts=PTS-STARTPTS[s$n];"; LBL+="[s$n]"; n=$((n+1)); fi
  IN+=" -i r3d/patch_en/ov$i.mp4"; FC+="[$((i+1)):v]setpts=PTS-STARTPTS[s$n];"; LBL+="[s$n]"; n=$((n+1)); prev=$b; i=$((i+1)); done
[ $prev -lt 5918 ] && { FC+="[0:v]trim=start_frame=$prev,setpts=PTS-STARTPTS[s$n];"; LBL+="[s$n]"; n=$((n+1)); }
ffmpeg -v error -y $IN -filter_complex "${FC}${LBL}concat=n=$n:v=1[v]" -map "[v]" -r 30 -c:v libx264 -preset medium -crf 19 -maxrate 30M -bufsize 60M -pix_fmt yuv420p -movflags +faststart r3d/new_ov_en.mp4
[ "$(ffprobe -v error -count_packets -show_entries stream=nb_read_packets -of csv=p=0 r3d/new_ov_en.mp4)" = 5918 ] && mv r3d/new_ov_en.mp4 r3d/full_ov_en.mp4 && echo spliced
