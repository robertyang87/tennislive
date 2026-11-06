set -e
# 用法：PY=python3 bash assemble.sh zh|en
# 前置：render3d.sh 已把 3D 渲到 r3d/seg/c*.mp4（+ .anchors.json）；cover/ 下已出 16:9 横版封面 thumb_16x9_<lang>.jpg。
# 3D 里没有文字，中英两版共用同一份 3D；英文版只换叠加层文案、不配音（docs/vibetennis.md §8）。
# 成片 = 片头 3 帧横版封面（0.1 s，docs/vibetennis.md §9）＋ 3D＋叠加层 ＋ BGM 与合成音效；中文版另加 TTS 配音（-14 LUFS / 真峰值 ≤ -1 dBTP）。
HERE="$(cd "$(dirname "$0")" && pwd)"; PY="${PY:-python3}"; L="${1:-zh}"; cd "$HERE"; mkdir -p sfx
SLUG=vibetennis-strings-2026; [ "$L" = en ] && SLUG=$SLUG-en
SEG="${SEG:-r3d/seg}"   # 中文先渲完挪到 r3d/seg_zh、英文渲进 r3d/seg 时，用 SEG=r3d/seg_zh 合中文
ls $SEG/c*.mp4 | sort | sed "s|^r3d/|file '|; s|$|'|" > r3d/list.txt
[ -f r3d/full_ov_$L.mp4 ] || VT_LANG=$L "$PY" overlay.py r3d/list.txt r3d/full_ov_$L.mp4 $(ls $SEG/c*.mp4.anchors.json | sort) 2>&1 | grep -v -i fontconfig
[ -f sfx/final_$L.m4a ] || {
  [ -f sfx/sfx_bed.wav ] && [ -f sfx/bgm_bed.wav ] || "$PY" sfx.py 2>&1 | grep -v -i fontconfig
  BED=sfx/sfx_bed.wav; [ "$L" = zh ] && { "$PY" voice.py; BED=sfx/sfx_bed_zh.wav; }
  D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 r3d/full_ov_$L.mp4)
  ffmpeg -y -loglevel error -i $BED -af "atrim=0:$D" -ac 2 -c:a pcm_f32le sfx/trim_$L.wav
  "$PY" ln.py sfx/trim_$L.wav sfx/n14_$L.wav -14 -2.5
  ffmpeg -y -loglevel error -i sfx/n14_$L.wav -af "volume=1.0dB,alimiter=limit=0.56:attack=0.5:release=40:level=false" -c:a pcm_f32le sfx/lim_$L.wav
  ffmpeg -y -loglevel error -i sfx/lim_$L.wav -af "adelay=100|100" -c:a aac -b:a 256k -ar 48000 sfx/final_$L.m4a
  # 真峰值守门：AAC 编码会在瞬态上冲过限幅（2026-11-05 英文版没有配音、全是音效瞬态，限幅后 -3.2 dBTP，编完 +0.3）。
  # 编完量一次，超过 -1.2 dBTP 就按超出量把整轨压低再编，直到合格。qc.py 的门槛是 ≤ -1.0。
  for _ in 1 2 3; do
    TP=$(ffmpeg -hide_banner -i sfx/final_$L.m4a -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+Peak:" | tail -1 | awk '{print $2}')
    awk -v t="$TP" 'BEGIN{exit !(t>-1.2)}' || break
    G=$(awk -v t="$TP" 'BEGIN{printf "%.2f", -1.6-t}'); echo "[真峰值] AAC 后 $TP dBTP，压 $G dB 重编"
    ffmpeg -y -loglevel error -i sfx/lim_$L.wav -af "volume=${G}dB,adelay=100|100" -c:a aac -b:a 256k -ar 48000 sfx/final_$L.m4a
  done; }
THUMB=cover/thumb_16x9_$L.jpg
[ -f "$THUMB" ] || { echo "横版封面 $THUMB 还没出（python3 cover/make_cover.py A wide cover/thumb_16x9_$L.jpg $L）——叠加层和音频已备好，先停在这"; exit 0; }
M=${SLUG}_master.mp4; P=${SLUG}_push.mp4
[ -f "$M" ] || ffmpeg -y -loglevel error -loop 1 -framerate 30 -t 0.1 -i "$THUMB" -i r3d/full_ov_$L.mp4 -i sfx/final_$L.m4a \
  -filter_complex "[0:v]scale=1920:1080,format=yuv420p,setsar=1[a];[1:v]format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]" \
  -map "[v]" -map 2:a -c:v libx264 -preset medium -crf 16 -pix_fmt yuv420p -r 30 -c:a copy -shortest -movflags +faststart "$M"
ffmpeg -y -loglevel error -i "$M" -map 0:v:0 -c:v libx264 -profile:v high -preset medium -b:v 7500k -fps_mode cfr -r 30 -pass 1 -passlogfile sfx/x264_$L -an -f null /dev/null
ffmpeg -y -loglevel error -i "$M" -map 0:v:0 -map 0:a -c:v libx264 -profile:v high -preset medium -b:v 7500k -maxrate 11000k -bufsize 15000k -fps_mode cfr -r 30 -pass 2 -passlogfile sfx/x264_$L -pix_fmt yuv420p -c:a copy -movflags +faststart sfx/tmp_$L.mp4
for f in "$M" "$P"; do
  src=$([ "$f" = "$P" ] && echo sfx/tmp_$L.mp4 || echo "$M")
  ffmpeg -y -loglevel error -i "$src" -i "$THUMB" -map 0 -map 1 -c copy -disposition:v:1 attached_pic -movflags +faststart sfx/att_$L.mp4 && mv sfx/att_$L.mp4 "$f"
done
rm -f sfx/tmp_$L.mp4
for f in "$M" "$P"; do echo "$f $(stat -c %s "$f") bytes"; ffmpeg -hide_banner -i "$f" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2; done
ffmpeg -y -loglevel error -i "$P" -map 0:v:0 -vf "fps=1/5,scale=384:216,tile=6x6" -frames:v 1 contact_sheet_$L.jpg
echo done
