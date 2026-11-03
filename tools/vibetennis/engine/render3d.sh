#!/bin/bash
# 整片 3D 渲染（共用引擎，EP05 那套搬出来的）：bash render3d.sh <集目录> [端口=8766] [进程数=4]
# 切成 240 帧一块（<集>/r3d/seg/c00000.mp4 …，各带 .anchors.json），K 个进程各领一摞块并行渲。
# 可续渲：块的 .anchors.json 在（cap.js 最后才写它）就算完成、跳过——容器重启后重跑只补没渲完的块
# （2026-11-03 容器重启丢了 55 分钟的整段渲染：一个 mp4 没写完就没有 moov，一帧都救不回来）。
# 帧数 N 跟着 <集>/r3d/timeline.json 的 total 走（plan.py 按配音落位后写的）。
set -u; E="$(cd "$1" && pwd)"; P=${2:-8766}; K=${3:-4}; C=240; CAP="$(cd "$(dirname "$0")" && pwd)/cap.js"
bash "$(dirname "$0")/serve.sh" "$E" "$P" || exit 1
cd "$E/r3d"; mkdir -p seg
# 同一时刻只许一份整片渲染：两份并跑会往同一批块里写（2026-11-02 踩过）。pgrep 锚 ^node，免得匹配到自己
exec 9>seg/.render.lock; flock -n 9 || { echo "已有一份渲染在跑（seg/.render.lock）" >&2; exit 3; }
if pgrep -f "^node (.*/)?cap\.js" >/dev/null; then echo "还有 cap.js 在跑：$(pgrep -fa '^node (.*/)?cap\.js' | head -4)" >&2; exit 3; fi
N=$(python3 -c "import json;print(round(json.load(open('timeline.json'))['total']*30))")
work(){ local w=$1 a b f; for ((a=w*C; a<N; a+=K*C)); do b=$((a+C<N?a+C:N)); f=$(printf "seg/c%05d.mp4" $a)
    [ -f "$f.anchors.json" ] && continue; rm -f "$f"; node "$CAP" $a $b $f 1920 1080 $P >> seg/w$w.log 2>&1 || { echo "块 $f 失败" >> seg/w$w.log; return 1; }; done; }
for w in $(seq 0 $((K-1))); do work $w & sleep 8; done; wait
miss=0; for ((a=0; a<N; a+=C)); do [ -f "$(printf "seg/c%05d.mp4.anchors.json" $a)" ] || { echo "缺块 $a"; miss=1; }; done
[ $miss = 0 ] && echo done || { echo "有块没渲完，重跑本脚本续渲" >&2; exit 1; }
