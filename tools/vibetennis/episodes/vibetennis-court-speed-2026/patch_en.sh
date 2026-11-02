#!/bin/bash
# 英文版：3D 里的粒子大字（four / q / idx / end）跟语言走，只重渲这几段（VT_LANG=en），叠英文叠加层后替换进 full_ov_en.mp4。
set -e; cd "$(dirname "$0")"
pgrep -f "^node cap.js" >/dev/null && { echo "还有 cap.js 在跑" >&2; exit 3; }
R="0:378 966:1092 2607:2853 5487:5918"
[ "$1" = splice ] || { cd r3d; i=0; for r in $R; do a=${r%:*}; b=${r#*:}; VT_LANG=en node cap.js $a $b patch_en/p$i.mp4 1920 1080 8766 > patch_en/p$i.log 2>&1 & i=$((i+1)); sleep 8; done; wait; cd ..
i=0; for r in $R; do a=${r%:*}; OV_F0=$a VT_LANG=en python3 overlay.py r3d/patch_en/p$i.mp4 r3d/patch_en/ov$i.mp4 r3d/patch_en/p$i.mp4.anchors.json 2>&1 | grep -v -i fontconfig; i=$((i+1)); done; }
# 拼：原片段按同一套编码参数单独切出来，和补丁交替，用 concat 分离器无损接（单趟 filter 里多次 trim 同一路输入会把内存吃爆，2026-11-02 被杀过）
ENC="-c:v libx264 -preset medium -crf 19 -maxrate 30M -bufsize 60M -pix_fmt yuv420p"
J=r3d/patch_en/join.txt; : > $J; prev=0; i=0; k=0
cut(){ ffmpeg -v error -y -i r3d/full_ov_en.mp4 -vf "trim=start_frame=$1${2:+:end_frame=$2},setpts=PTS-STARTPTS" -r 30 $ENC r3d/patch_en/o$k.mp4; echo "file 'o$k.mp4'" >> $J; k=$((k+1)); }
for r in $R; do a=${r%:*}; b=${r#*:}; [ $a -gt $prev ] && cut $prev $a; echo "file 'ov$i.mp4'" >> $J; prev=$b; i=$((i+1)); done
[ $prev -lt 5918 ] && cut $prev ""
ffmpeg -v error -y -f concat -safe 0 -i $J -c copy -movflags +faststart r3d/new_ov_en.mp4
[ "$(ffprobe -v error -count_packets -show_entries stream=nb_read_packets -of csv=p=0 r3d/new_ov_en.mp4)" = 5918 ] && mv r3d/new_ov_en.mp4 r3d/full_ov_en.mp4 && echo spliced
