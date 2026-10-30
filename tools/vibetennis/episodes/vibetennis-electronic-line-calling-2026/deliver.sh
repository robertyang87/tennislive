set -e
# 合成之后的交付两步（assemble.sh 跑完 overlay 与音效后）：
# 1) 母片（存档）：字幕叠加版画面 + 音效混音，-14 LUFS；真峰值目标 -2.5 dBTP（AAC 编码会把峰值顶高约 1 dB，-1.5 不够过 qc 的 -1.0）
# 2) 推送版（发布链接只放它，docs/vibetennis.md §5）：H.264 High 1080p、AAC 直接拷贝、+faststart、≤200 MB。
#    244 秒按「约 7.5 Mbps」会到约 229 MB，两条冲突时以 200 MB 为准 → 视频两遍编码 6.2 Mbps。
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"; PY="${PY:-python3}"
"$PY" ln.py sfx/sfx_trim.wav sfx/mix_n14.wav -14 -2.5
M=vibetennis-electronic-line-calling-2026_master.mp4; P=vibetennis-electronic-line-calling-2026_push.mp4
ffmpeg -y -loglevel error -i r3d/full_ov.mp4 -i sfx/mix_n14.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart "$M"
ffmpeg -y -loglevel error -i "$M" -map 0:v -c:v libx264 -profile:v high -preset medium -b:v 6200k -pass 1 -passlogfile sfx/x264 -an -f null /dev/null
ffmpeg -y -loglevel error -i "$M" -map 0:v -map 0:a -c:v libx264 -profile:v high -preset medium -b:v 6200k -maxrate 9000k -bufsize 12000k -pass 2 -passlogfile sfx/x264 -pix_fmt yuv420p -c:a copy -movflags +faststart "$P"
for f in "$M" "$P"; do echo "$f $(stat -c %s "$f") bytes"; ffmpeg -hide_banner -i "$f" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2; done
ffmpeg -y -loglevel error -i "$P" -vf "fps=1/6,scale=384:216,tile=6x7" -frames:v 1 contact_sheet.jpg
echo done
