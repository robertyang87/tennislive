set -e
# 用法：PY=python3 bash assemble.sh
# 前置：render3d.sh 已把 3D 分段渲到 r3d/seg/s0..s3.mp4（+ .anchors.json）。
# 这一集没有 BGM（授权未定，docs/vibetennis.md TODO）：成片 = 3D + 字幕叠加 + 合成音效，总混 -14 LUFS / -1.5 dBTP。
HERE="$(cd "$(dirname "$0")" && pwd)"; PY="${PY:-python3}"; cd "$HERE"; mkdir -p sfx
ls r3d/seg/s*.mp4 | sort | sed "s|^r3d/|file '|; s|$|'|" > r3d/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i r3d/list.txt -c copy r3d/full3d.mp4
"$PY" overlay.py r3d/full3d.mp4 r3d/full_ov.mp4 r3d/seg/s*.mp4.anchors.json 2>&1 | grep -v -i fontconfig
"$PY" sfx.py 2>&1 | grep -v -i fontconfig
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 r3d/full_ov.mp4)
ffmpeg -y -loglevel error -i sfx/sfx_bed.wav -af "atrim=0:$D" -ac 2 -c:a pcm_f32le sfx/sfx_trim.wav
"$PY" ln.py sfx/sfx_trim.wav sfx/mix_n14.wav -14 -1.5
OUT=vibetennis-electronic-line-calling-2026_master.mp4
ffmpeg -y -loglevel error -i r3d/full_ov.mp4 -i sfx/mix_n14.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart "$OUT"
ffmpeg -hide_banner -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2
ffmpeg -y -loglevel error -i "$OUT" -vf "fps=1/6,scale=384:216,tile=6x7" -frames:v 1 contact_sheet.jpg
ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT"
