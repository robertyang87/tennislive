#!/bin/bash
# 把整片 3D 分 3 段并行渲出来：r3d/seg/s0..s2.mp4（+ .anchors.json）。需要 r3d/ 下起着静态服务（端口 8765）。
cd "$(dirname "$0")/r3d"
N=7320; K=3; STEP=$(( (N+K-1)/K ))
for i in $(seq 0 $((K-1))); do a=$((i*STEP)); b=$(( (i+1)*STEP<N ? (i+1)*STEP : N )); node cap.js $a $b seg/s$i.mp4 > seg/s$i.log 2>&1 & done
wait; echo done
