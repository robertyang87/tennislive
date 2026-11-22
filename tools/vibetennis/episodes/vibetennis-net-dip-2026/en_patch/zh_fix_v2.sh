#!/bin/bash
# 中文 v2：等标签修正段（r3d/patch_zh/p0，870–1000 帧）渲完 → 无损接回叠加层 → 重出光效层与成片。旧版全部改名 *_v1 备份，不删。
cd "$(dirname "$0")/.."; S=vibetennis-net-dip-2026
while [ ! -f r3d/patch_zh/p0.mp4.anchors.json ]; do sleep 20; done
cp r3d/full_ov_zh.mp4 r3d/full_ov_zh_v1.mp4
bash ../../engine/patch.sh . splice patch_zh zh "870:1000" || { echo "- $(date '+%m-%d %H:%M') 中文 v2 接回失败" >> PROGRESS.md; exit 1; }
for f in r3d/full_vfx_zh.mp4 ${S}_master.mp4 ${S}_push.mp4 contact_sheet_zh.jpg; do [ -f $f ] && mv $f ${f%.*}_v1.${f##*.}; done
SEG=r3d/seg_zh bash assemble.sh zh > /workspace/ep13_assemble_zh_v2.log 2>&1 || { echo "- $(date '+%m-%d %H:%M') 中文 v2 合成失败" >> PROGRESS.md; exit 1; }
ffmpeg -y -loglevel error -i ${S}_push.mp4 -map 0:v:0 -map 0:a -c:v libx264 -preset medium -b:v 6000k -maxrate 9000k -bufsize 12000k -pix_fmt yuv420p -c:a copy -movflags +faststart /workspace/ep13_preview/EP13_网中间矮_zh_preview_v2.mp4
python3 ../../motion_check.py ${S}_push.mp4 > /workspace/scratch/motion_zh_v2.log 2>&1
echo "- $(date '+%m-%d %H:%M') 中文 v2 完成（标签修正）：${S}_push.mp4、预览 /workspace/ep13_preview/EP13_网中间矮_zh_preview_v2.mp4；旧版 *_v1；motion 见 /workspace/scratch/motion_zh_v2.log" >> PROGRESS.md
