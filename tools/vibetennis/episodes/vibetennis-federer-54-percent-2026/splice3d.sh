set -e
# 2026-11-01 二改：新段 A 从 32.32 s 加长到 42.02 s（＋291 帧）。旧渲染（r3d/seg，按 LA=32.32 渲的 7094 帧）里
# A 段之外的帧整帧平移复用，只重渲新 A（第 465–1726 帧）。产物：r3d/seg2/p*.mp4 ＋ 同名 .anchors.json（帧号已是新时间轴）
#   用法：bash splice3d.sh render   # 先渲新 A（4 路并行，要 r3d 下 8766 端口的静态服务）
#         bash splice3d.sh splice   # 再拼：旧 s0 前 465 帧 ＋ 新 A ＋ 旧 s0 第 1435 帧起 ＋ 旧 s1–s3（帧号 +291）
cd "$(dirname "$0")/r3d"; mkdir -p seg2
SH=291; A0=465; A1=1726
if [ "$1" = render ]; then
  for i in 0 1 2 3; do a=$((A0+(A1-A0)*i/4)); b=$((A0+(A1-A0)*(i+1)/4)); node cap.js $a $b seg2/a$i.mp4 1920 1080 8766 > seg2/a$i.log 2>&1 & done; wait; echo rendered; exit 0
fi
trimv(){ ffmpeg -y -loglevel error -i "$1" -vf "trim=start_frame=$2:end_frame=$3,setpts=PTS-STARTPTS" -c:v libx264 -preset ultrafast -crf 12 -pix_fmt yuv420p "$4"; }
trimv seg/s0.mp4 0 465 seg2/p0.mp4
trimv seg/s0.mp4 1435 1774 seg2/p5.mp4
for i in 0 1 2 3; do ln -sf ../seg2/a$i.mp4 seg2/p$((i+1)).mp4; done
for i in 1 2 3; do ln -sf ../seg/s$i.mp4 seg2/p$((i+5)).mp4; done
python3 - <<'P'
import json
J=lambda p: json.load(open(p))
s0=J('seg/s0.mp4.anchors.json')
json.dump([x for x in s0 if x[0]<465],open('seg2/p0.mp4.anchors.json','w'))
for i in range(4): json.dump(J(f'seg2/a{i}.mp4.anchors.json'),open(f'seg2/p{i+1}.mp4.anchors.json','w'))
json.dump([[f+291,a] for f,a in s0 if f>=1435],open('seg2/p5.mp4.anchors.json','w'))
for i in (1,2,3): json.dump([[f+291,a] for f,a in J(f'seg/s{i}.mp4.anchors.json')],open(f'seg2/p{i+5}.mp4.anchors.json','w'))
c=J('seg_en/c2.mp4.anchors.json'); json.dump([[f+291,a] for f,a in c],open('seg_en/c3.mp4.anchors.json','w'))
n=sum(len(J(f'seg2/p{i}.mp4.anchors.json')) for i in range(9)); print('anchors frames',n)
P
ln -sf c2.mp4 seg_en/c3.mp4
for f in seg2/p*.mp4; do echo "$f $(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 $f)"; done
