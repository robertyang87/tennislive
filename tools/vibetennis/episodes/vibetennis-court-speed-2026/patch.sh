#!/bin/bash
# 局部重渲：只重渲改过的镜头，叠字幕后无损接回整片叠加层。
#   bash patch.sh render <tag> <3D语言> "a:b c:d ..."    # 各段并行渲 3D（帧号半开区间），写 r3d/<tag>/
#   bash patch.sh splice <tag> <字幕语言> "a:b c:d ..."  # 叠该语言字幕，按帧号接回 r3d/full_ov_<语言>.mp4
# 3D 里只有粒子大字跟语言走；没有大字的段 3D 渲一次，两种语言各叠一次字幕即可。
set -e; cd "$(dirname "$0")"; MODE=$1; TAG=$2; L=$3; R=$4; D=r3d/$TAG; mkdir -p $D
if [ "$MODE" = render ]; then
  pgrep -f "^node cap.js" >/dev/null && { echo "还有 cap.js 在跑" >&2; exit 3; }
  cd r3d; i=0; for r in $R; do VT_LANG=$L node cap.js ${r%:*} ${r#*:} $TAG/p$i.mp4 1920 1080 8766 > $TAG/p$i.log 2>&1 & i=$((i+1)); sleep 8; done; wait; cd ..
  i=0; for r in $R; do [ "$(ffprobe -v error -count_packets -show_entries stream=nb_read_packets -of csv=p=0 $D/p$i.mp4)" = $(( ${r#*:} - ${r%:*} )) ] || { echo "p$i 帧数不对" >&2; exit 1; }; i=$((i+1)); done; echo rendered; exit 0; fi
# splice
i=0; for r in $R; do OV_F0=${r%:*} VT_LANG=$L python3 overlay.py $D/p$i.mp4 $D/ov_${L}_$i.mp4 $D/p$i.mp4.anchors.json 2>&1 | grep -v -i fontconfig || true; i=$((i+1)); done
ENC="-c:v libx264 -preset medium -crf 19 -maxrate 30M -bufsize 60M -pix_fmt yuv420p"
J=$D/join_$L.txt; : > $J; prev=0; i=0; k=0
cut(){ ffmpeg -v error -y -i r3d/full_ov_$L.mp4 -vf "trim=start_frame=$1${2:+:end_frame=$2},setpts=PTS-STARTPTS" -r 30 $ENC $D/o_${L}_$k.mp4; echo "file 'o_${L}_$k.mp4'" >> $J; k=$((k+1)); }
for r in $(echo $R | tr ' ' '\n' | sort -t: -k1,1n); do a=${r%:*}; b=${r#*:}; [ $a -gt $prev ] && cut $prev $a
  j=0; for rr in $R; do [ "$rr" = "$r" ] && break; j=$((j+1)); done; echo "file 'ov_${L}_$j.mp4'" >> $J; prev=$b; done
[ $prev -lt 5918 ] && cut $prev ""
ffmpeg -v error -y -f concat -safe 0 -i $J -c copy -movflags +faststart r3d/new_ov_$L.mp4
[ "$(ffprobe -v error -count_packets -show_entries stream=nb_read_packets -of csv=p=0 r3d/new_ov_$L.mp4)" = 5918 ] && mv r3d/new_ov_$L.mp4 r3d/full_ov_$L.mp4 && rm -f $D/o_${L}_*.mp4 && echo "spliced $L"
