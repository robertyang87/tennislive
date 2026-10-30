set -e
# 用法：VT_WORK=/tmp/vt BGM=/path/to/bgm.m4a PY=python3 bash assemble.sh
# 先在 r3d/ 起静态服务（python3 -m http.server 8765）并用 cap.js 分段渲出 $VT_WORK/r3d/seg/s?.mp4。
HERE="$(cd "$(dirname "$0")" && pwd)"
VT_WORK="${VT_WORK:-$HERE}"; PY="${PY:-python3}"; BGM="${BGM:?需要 BGM=音乐文件路径}"
export VT_WORK
cd "$VT_WORK"; mkdir -p sfx r3d
ls r3d/seg/s?.mp4 | sort | sed "s|^r3d/|file '|; s|$|'|" > r3d/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i r3d/list.txt -c copy r3d/full3d.mp4
"$PY" "$HERE/overlay.py" r3d/full3d.mp4 r3d/full_ov.mp4 r3d/seg/s?.mp4.anchors.json 2>&1 | grep -v -i fontconfig
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 r3d/full_ov.mp4); ST=$(python3 -c "print($D-5)")
# SFX-only stem (no music): -18 LUFS leaves headroom for Robert's own BGM
ffmpeg -y -loglevel error -i sfx/sfx_bed.wav -af "atrim=0:$D" -c:a pcm_f32le sfx/sfx_trim.wav
"$PY" "$HERE/ln.py" sfx/sfx_trim.wav sfx/sfx_n18.wav -18 -1.5
# music stem
ffmpeg -y -loglevel error -i "$BGM" -af "atrim=0:$D,afade=t=in:d=0.3,afade=t=out:st=$ST:d=5,aresample=48000" -ac 2 -c:a pcm_f32le sfx/music_trim.wav
"$PY" "$HERE/ln.py" sfx/music_trim.wav sfx/music_n16.wav -16 -1.5
# mix: SFX sit ~4 dB under the music, then master to -14 LUFS / -1.5 dBTP
ffmpeg -y -loglevel error -i sfx/music_n16.wav -i sfx/sfx_n18.wav -filter_complex "[1:a]volume=-2dB[s];[0:a][s]amix=inputs=2:normalize=0:duration=first[m]" -map "[m]" -c:a pcm_f32le sfx/mix_raw.wav
"$PY" "$HERE/ln.py" sfx/mix_raw.wav sfx/mix_n14.wav -14 -1.5
ffmpeg -y -loglevel error -i r3d/full_ov.mp4 -i sfx/mix_n14.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart tennis_live_faster_v2.mp4
ffmpeg -y -loglevel error -i r3d/full_ov.mp4 -i sfx/sfx_n18.wav -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart tennis_live_faster_v2_silent.mp4
for f in tennis_live_faster_v2.mp4 tennis_live_faster_v2_silent.mp4; do echo $f; ffmpeg -hide_banner -i $f -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2; done
ffmpeg -y -loglevel error -i tennis_live_faster_v2.mp4 -vf "fps=1/5,scale=384:216,tile=6x6" -frames:v 1 contact_sheet_v2.jpg
ffprobe -v error -show_entries format=duration -of csv=p=0 tennis_live_faster_v2.mp4
