#!/bin/bash
# 英文收尾链：等首轮 render_en.sh 结束 → 再跑一轮补缺（含标签修正后要重渲的 720/960 段）→ 合成英文版。
cd "$(dirname "$0")/.."
while pgrep -f "en_patch/render_en.sh" >/dev/null; do sleep 30; done
while pgrep -f "patch_zh/p0.mp4" >/dev/null; do sleep 30; done
K=6 bash en_patch/render_en.sh >> /workspace/ep13_en_render.log 2>&1
n=$(wc -l < en_patch/jobs.txt); ok=0; while read a b; do [ -f $(printf "r3d/seg_en/c%05d.mp4.anchors.json" $a) ] && ok=$((ok+1)); done < en_patch/jobs.txt
[ $ok = $n ] || { echo "- $(date '+%m-%d %H:%M') 英文段只完成 $ok/$n，重跑 en_chain.sh" >> PROGRESS.md; exit 1; }
SEG=r3d/seg_en bash assemble.sh en > /workspace/ep13_assemble_en.log 2>&1 && echo "- $(date '+%m-%d %H:%M') 英文成片合成完：vibetennis-net-dip-2026-en_push.mp4（日志 /workspace/ep13_assemble_en.log）" >> PROGRESS.md || echo "- $(date '+%m-%d %H:%M') 英文合成失败：/workspace/ep13_assemble_en.log" >> PROGRESS.md
