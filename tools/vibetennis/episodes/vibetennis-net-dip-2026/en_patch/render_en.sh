#!/bin/bash
# 英文段并行渲（K 进程，默认 4；可续渲：.anchors.json 在就跳过）。nohup setsid bash en_patch/render_en.sh > /workspace/ep13_en_render.log 2>&1 &
cd "$(dirname "$0")/.."; E=$(pwd); K=${K:-4}; export NODE_PATH=/workspace/nodetools/node_modules
bash ../../engine/serve.sh "$E" 8771 || exit 1; cd r3d
one(){ a=$1; b=$2; f=$(printf "seg_en/c%05d.mp4" $a); [ -f "$f.anchors.json" ] && exit 0; rm -f "$f"
  VT_LANG=en node ../../../engine/cap.js $a $b $f 1920 1080 8771 >> seg_en/r_$a.log 2>&1 || echo "段 $a 失败"; }
export -f one; xargs -P $K -L 1 bash -c 'one $0 $1' < ../en_patch/jobs.txt
n=$(wc -l < ../en_patch/jobs.txt); ok=0; while read a b; do [ -f $(printf "seg_en/c%05d.mp4.anchors.json" $a) ] && ok=$((ok+1)); done < ../en_patch/jobs.txt
echo "英文段 $ok / $n 完成"; [ $ok = $n ] && echo "- $(date '+%m-%d %H:%M') 英文 3D 局部重渲完成（r3d/seg_en）" >> ../PROGRESS.md
