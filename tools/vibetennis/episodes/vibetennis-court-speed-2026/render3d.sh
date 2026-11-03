#!/bin/bash
# 整片 3D 渲染，切成 240 帧一块（r3d/seg/c00000.mp4 …，各带 .anchors.json），4 个进程各领一摞块并行渲。
# 可续渲：块的 .anchors.json 在（cap.js 最后才写它）就算完成、跳过；容器重启后重跑本脚本只补没渲完的块
# （2026-11-03 容器重启丢了 55 分钟的整段渲染——整段一个 mp4 没写完就没有 moov，一帧都救不回来）。
# 需要 r3d/ 下起着静态服务（端口 8766）：cd r3d && python3 -m http.server 8766 --bind 127.0.0.1 &
cd "$(dirname "$0")/r3d"; mkdir -p seg
# 同一时刻只许一份整片渲染：两份并跑会往同一批块里写，文件写坏且日志交错看不出来（2026-11-02 踩过）
exec 9>seg/.render.lock; flock -n 9 || { echo "已有一份渲染在跑（seg/.render.lock），不重复开" >&2; exit 3; }
if pgrep -f "^node cap.js" >/dev/null; then echo "还有 cap.js 进程在跑：$(pgrep -fa '^node cap.js' | head -4)" >&2; exit 3; fi
# 帧数 N 跟着 plan.py 写的 timeline.json 总长走
N=$(python3 -c "import json;print(round(json.load(open('timeline.json'))['total']*30))"); K=4; C=240
work(){ local w=$1 a b f; for ((a=w*C; a<N; a+=K*C)); do b=$((a+C<N?a+C:N)); f=$(printf "seg/c%05d.mp4" $a)
    [ -f "$f.anchors.json" ] && continue; rm -f "$f"; node cap.js $a $b $f 1920 1080 8766 >> seg/w$w.log 2>&1 || { echo "块 $f 失败" >> seg/w$w.log; return 1; }; done; }
for w in $(seq 0 $((K-1))); do work $w & sleep 8; done; wait
miss=0; for ((a=0; a<N; a+=C)); do [ -f "$(printf "seg/c%05d.mp4.anchors.json" $a)" ] || { echo "缺块 $a"; miss=1; }; done
[ $miss = 0 ] && echo done || { echo "有块没渲完，重跑本脚本续渲" >&2; exit 1; }
