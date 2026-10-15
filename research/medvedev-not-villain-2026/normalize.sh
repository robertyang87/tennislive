# 竖版官方源片规整到 1920×1080：中央 3:4 窗口（x 555–1365）装下原画，其余黑边（成片固定居中取景，黑边不入画）。
# 音轨 -c:a copy，逐字节保留——两档 ASR 转写的证据仍对得上。
set -euxo pipefail
R=https://github.com/robertyang87/tennislive/releases/download
mkdir -p norm && cd norm
curl -sSLf -o ws.mp4 $R/source-9aqUxco0bqo/9aqUxco0bqo.mp4
# 720×1280 → 取中央 720×960（3:4，y 160 起），放大到 810×1080
ffmpeg -v error -y -i ws.mp4 -map 0:v:0 -map 0:a:0 -vf "crop=720:960:0:160,scale=810:1080:flags=lanczos,pad=1920:1080:555:0:black,setsar=1" -c:v libx264 -crf 14 -preset medium -r 50 -c:a copy ws_c.mp4
sha256sum ws_c.mp4
gh release view reel-src-medvedev-not-villain-2026 >/dev/null 2>&1 || gh release create reel-src-medvedev-not-villain-2026 --title reel-src-medvedev-not-villain-2026 --notes "网球有故事 medvedev-not-villain-2026：Tennis TV 官方竖版短片 9aqUxco0bqo（温斯顿-塞勒姆 2026 匹克球那句）规整到 1920×1080，中央 3:4 窗口装下原画，音轨逐字节保留。脚本 research/medvedev-not-villain-2026/normalize.sh"
gh release upload reel-src-medvedev-not-villain-2026 ws_c.mp4 --clobber
