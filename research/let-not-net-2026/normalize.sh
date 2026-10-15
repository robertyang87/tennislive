# 竖版 / 方版官方源片规整到 1920×1080：中央 3:4 窗口（x 555–1365）装下原画，其余黑边（成片固定居中取景，黑边不入画）。
# 音轨 -c:a copy，逐字节保留——两档 ASR 转写的证据仍对得上。
set -euxo pipefail
R=https://github.com/robertyang87/tennislive/releases/download
mkdir -p norm && cd norm
curl -sSLf -o er.mp4 $R/source-ErRIKW61Rsc/ErRIKW61Rsc.mp4
curl -sSLf -o ng.mp4 $R/source-PZVUqAkrS1E/PZVUqAkrS1E.mp4
ffmpeg -v error -y -i er.mp4 -map 0:v:0 -map 0:a:0 -vf "crop=1080:1440:0:240,scale=810:1080:flags=lanczos,pad=1920:1080:555:0:black,setsar=1" -c:v libx264 -crf 14 -preset medium -r 60 -c:a copy er_c.mp4
ffmpeg -v error -y -i ng.mp4 -map 0:v:0 -map 0:a:0 -vf "pad=1920:1080:420:0:black,setsar=1" -c:v libx264 -crf 14 -preset medium -c:a copy ng_c.mp4
sha256sum er_c.mp4 ng_c.mp4
gh release view reel-src-let-not-net-2026 >/dev/null 2>&1 || gh release create reel-src-let-not-net-2026 --title reel-src-let-not-net-2026 --notes "网球有故事 let-not-net-2026：竖版 ErRIKW61Rsc、方版 PZVUqAkrS1E（均 Tennis TV 官方）规整到 1920×1080，中央 3:4 窗口装下原画，音轨逐字节保留。脚本 research/let-not-net-2026/normalize.sh"
gh release upload reel-src-let-not-net-2026 er_c.mp4 ng_c.mp4 --clobber
