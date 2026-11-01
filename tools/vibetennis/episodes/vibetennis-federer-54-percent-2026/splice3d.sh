set -e
# 2026-11-01 二改：新段 A 从 32.32 s 加长到 42.02 s（＋291 帧）。旧渲染 r3d/seg（按 LA=32.32 渲）里 A 段之后的帧
# 整帧平移 291 复用；只重渲新 A（新第 465–1726 帧，seg2/a0–a2）和 s0 原本欠的尾巴（新第 1726–2065 帧，seg2/t5）。
#   p0 = 旧 s0 前 465 帧（锚点用 anchors_only.js 不出图重算）  p1–p3 = 新 A  p4 = t5  p5–p7 = 旧 s1–s3（帧号 +291）
#   英文版：c3 = 旧 seg_en/c2 帧号 +291
# 用法：bash splice3d.sh（新 A 与 t5 渲完之后）
cd "$(dirname "$0")/r3d"; mkdir -p seg2
ffmpeg -y -loglevel error -i seg/s0.mp4 -vf "trim=start_frame=0:end_frame=465,setpts=PTS-STARTPTS" -c:v libx264 -preset ultrafast -crf 12 -pix_fmt yuv420p seg2/p0.mp4
for i in 0 1 2; do ln -sf a$i.mp4 seg2/p$((i+1)).mp4; cp seg2/a$i.mp4.anchors.json seg2/p$((i+1)).mp4.anchors.json; done
ln -sf t5.mp4 seg2/p4.mp4; cp seg2/t5.mp4.anchors.json seg2/p4.mp4.anchors.json
for i in 1 2 3; do ln -sf ../seg/s$i.mp4 seg2/p$((i+4)).mp4; done
python3 - <<'P'
import json
J=lambda p: json.load(open(p))
for i in (1,2,3): json.dump([[f+291,a] for f,a in J(f'seg/s{i}.mp4.anchors.json')],open(f'seg2/p{i+4}.mp4.anchors.json','w'))
json.dump([[f+291,a] for f,a in J('seg_en/c2.mp4.anchors.json')],open('seg_en/c3.mp4.anchors.json','w'))
fr=[f for i in range(8) for f,_ in J(f'seg2/p{i}.mp4.anchors.json')]
print('anchors',len(fr),'first',min(fr),'last',max(fr),'连续' if sorted(fr)==list(range(min(fr),max(fr)+1)) else '有缺口')
P
ln -sf c2.mp4 seg_en/c3.mp4
for f in seg2/p*.mp4; do echo "$f $(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 $f)"; done
