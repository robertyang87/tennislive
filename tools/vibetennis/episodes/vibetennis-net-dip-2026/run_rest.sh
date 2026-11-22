#!/bin/bash
# EP13 断点续跑：3D 中文 → 挪 seg_zh → 并行（英文 3D ｜ 中文合成）→ 英文合成。每步幂等，重跑只补没做完的。
# nohup setsid bash run_rest.sh > /workspace/ep13_run.log 2>&1 &
cd "$(dirname "$0")"; E=$(pwd); R=/workspace/tennislive; export NODE_PATH=/workspace/nodetools/node_modules
log(){ echo "- $(date '+%m-%d %H:%M') $*" >> PROGRESS.md; echo "$*"; }
render(){ while pgrep -f "engine/render3d.sh" >/dev/null; do sleep 30; done   # 已有一份在跑（比如上次手动起的）就等它
  for i in 1 2 3 4 5; do VT_LANG=$1 bash $R/tools/vibetennis/engine/render3d.sh "$E" 8771 6 && return 0; sleep 5; done; return 1; }
if [ ! -d r3d/seg_zh ]; then
  render zh || { log "中文 3D 渲染失败，看 r3d/seg/w*.log"; exit 1; }
  mv r3d/seg r3d/seg_zh; log "中文 3D 渲完（r3d/seg_zh，$(ls r3d/seg_zh/*.anchors.json | wc -l) 块）"
fi
( if [ ! -f vibetennis-net-dip-2026_push.mp4 ]; then SEG=r3d/seg_zh bash assemble.sh zh > /workspace/ep13_assemble_zh.log 2>&1 && log "中文成片合成完：vibetennis-net-dip-2026_push.mp4（日志 /workspace/ep13_assemble_zh.log）" || log "中文合成失败：/workspace/ep13_assemble_zh.log"; fi ) &
if [ ! -f r3d/seg/.en_done ]; then
  render en || { log "英文 3D 渲染失败"; wait; exit 1; }
  touch r3d/seg/.en_done; log "英文 3D 渲完（r3d/seg）"
fi
wait
if [ ! -f vibetennis-net-dip-2026-en_push.mp4 ]; then SEG=r3d/seg bash assemble.sh en > /workspace/ep13_assemble_en.log 2>&1 && log "英文成片合成完：vibetennis-net-dip-2026-en_push.mp4" || log "英文合成失败：/workspace/ep13_assemble_en.log"; fi
log "run_rest.sh 结束"
