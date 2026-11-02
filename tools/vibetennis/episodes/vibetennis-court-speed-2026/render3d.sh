#!/bin/bash
# 整片 3D 分 4 段并行渲：r3d/seg/s0..s3.mp4（+ .anchors.json）。需要 r3d/ 下起着静态服务（端口 8766）：
#   cd r3d && python3 -m http.server 8766 --bind 127.0.0.1 &
cd "$(dirname "$0")/r3d"; mkdir -p seg
# 同一时刻只许一份整片渲染：两份并跑会往同一批 seg/s*.mp4 里写，文件写坏且日志交错看不出来（2026-11-02 踩过）
exec 9>seg/.render.lock; flock -n 9 || { echo "已有一份渲染在跑（seg/.render.lock），不重复开" >&2; exit 3; }
if pgrep -f "node cap.js" >/dev/null; then echo "还有 cap.js 进程在跑：$(pgrep -fa 'node cap.js' | head -4)" >&2; exit 3; fi
N=5918; K=4; STEP=$(( (N+K-1)/K ))
for i in $(seq 0 $((K-1))); do a=$((i*STEP)); b=$(( (i+1)*STEP<N ? (i+1)*STEP : N )); node cap.js $a $b seg/s$i.mp4 1920 1080 8766 > seg/s$i.log 2>&1 & sleep 8; done
wait; echo done
