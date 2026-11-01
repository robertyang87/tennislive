set -e
# 英文版（Tennis Jetlag）：画面、时间轴、音效与中文版完全相同，只把叠加层换成 overlay_en.py。
# 前置：render3d.sh 已把 3D 渲到 r3d/seg/s*.mp4（+ .anchors.json）。
# 直接拿分段清单喂 overlay（concat demuxer），不先拼一份 6.4 GB 的 full3d.mp4，省会话磁盘。
HERE="$(cd "$(dirname "$0")" && pwd)"; PY="${PY:-python3}"; cd "$HERE"; mkdir -p sfx
ls r3d/seg/s*.mp4 | sort | sed "s|^r3d/|file '|; s|$|'|" > r3d/list.txt
"$PY" overlay_en.py r3d/list.txt r3d/full_ov_en.mp4 r3d/seg/s*.mp4.anchors.json 2>&1 | grep -v -i fontconfig
"$PY" sfx.py 2>&1 | grep -v -i fontconfig
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 r3d/full_ov_en.mp4)
ffmpeg -y -loglevel error -i sfx/sfx_bed.wav -af "atrim=0:$D" -ac 2 -c:a pcm_f32le sfx/sfx_trim.wav
# 混音与推送版编码参数照 deliver.sh
"$PY" ln.py sfx/sfx_trim.wav sfx/mix_n14.wav -14 -2.5
ffmpeg -y -loglevel error -i sfx/mix_n14.wav -af "volume=1.0dB,alimiter=limit=0.56:attack=0.5:release=40:level=false" -c:a pcm_f32le sfx/mix_lim.wav
ffmpeg -y -loglevel error -i sfx/mix_lim.wav -c:a aac -b:a 256k -ar 48000 sfx/final.m4a
M=vibetennis-electronic-line-calling-2026-en_master.mp4; P=vibetennis-electronic-line-calling-2026-en.mp4
ffmpeg -y -loglevel error -i r3d/full_ov_en.mp4 -i sfx/final.m4a -map 0:v -map 1:a -c copy -shortest -movflags +faststart "$M"
ffmpeg -y -loglevel error -i "$M" -map 0:v -c:v libx264 -profile:v high -preset medium -b:v 6200k -pass 1 -passlogfile sfx/x264 -an -f null /dev/null
ffmpeg -y -loglevel error -i "$M" -map 0:v -map 0:a -c:v libx264 -profile:v high -preset medium -b:v 6200k -maxrate 9000k -bufsize 12000k -pass 2 -passlogfile sfx/x264 -pix_fmt yuv420p -c:a copy -movflags +faststart "$P"
for f in "$M" "$P"; do echo "$f $(stat -c %s "$f") bytes"; ffmpeg -hide_banner -i "$f" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2; done
ffmpeg -y -loglevel error -i "$P" -vf "fps=1/6,scale=384:216,tile=6x7" -frames:v 1 contact_sheet_en.jpg
echo done
