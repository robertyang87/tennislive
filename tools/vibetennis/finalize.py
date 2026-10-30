#!/usr/bin/env python3
"""vibetennis 成片定稿：片头接封面帧 → 编码交付版 → 写 render.json。

赛场之上的成片第一屏就是封面海报（停 1.2 秒、不配音，`build_match_reel.COVER_SECONDS`），
vibetennis 照同一条约定：`cover.py` 出的 16:9 封面帧停 `film.cover_seconds` 秒，
音轨在这一段是静音，然后接预渲好的 3D 母片（音乐＋音效已混好，-14 LUFS / -1.5 dBTP）。

交付版是 H.264 High / yuv420p / 30fps / AAC 48k 双声道，`-movflags +faststart`。
母片 27 Mbps（600 MB 级）发出去手机点不开，这里压到约 8 Mbps：3D 的颗粒和辉光
在这个码率下肉眼看不出损失（见 qc 抽帧），文件约 190 MB，走 GitHub Release。

    python3 tools/vibetennis/finalize.py --slug vibetennis-live-faster-2026 \
        --date 2026-10-30 --master /path/to/tennis_live_faster_v2b.mp4
    python3 tools/vibetennis/qc.py --slug ... --date ...      # 再跑质检出凭证
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CANVAS, COVER_FRAME_NAME, load_spec, outdir_for  # noqa: E402


def probe(path: Path) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration",
         "-of", "json", str(path)], text=True)
    return json.loads(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--master", required=True, help="预渲好的 16:9 母片（含音乐与音效）")
    ap.add_argument("--video-bitrate", default="8M")
    args = ap.parse_args()

    spec = load_spec(args.slug)
    film_cfg = spec["film"]
    cover_s = float(film_cfg.get("cover_seconds", 1.2))
    fps = int(film_cfg.get("fps", 30))
    W, H = CANVAS
    outdir = outdir_for(args.date, args.slug)
    frame = outdir / COVER_FRAME_NAME
    if not frame.is_file():
        raise SystemExit(f"{frame} 不在——先跑 tools/vibetennis/cover.py")
    master = Path(args.master)
    info = probe(master)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    if (v["width"], v["height"]) != (W, H):
        raise SystemExit(f"母片是 {v['width']}×{v['height']}，这一栏要 {W}×{H}")
    film = outdir / f"{args.slug}.mp4"
    filt = (# 封面帧是 JPEG（全范围 yuvj420p），不转成 TV 范围的话 concat 会把整片标成 yuvj420p，
            # 有的播放器会整片偏灰/过曝。qc.py 那一项就是为这个设的。
            f"[0:v]scale={W}:{H}:in_range=pc:out_range=tv,fps={fps},format=yuv420p,setsar=1[cv];"
            f"[1:v]scale={W}:{H},fps={fps},format=yuv420p,setsar=1[mv];"
            f"[2:a]aformat=sample_rates=48000:channel_layouts=stereo[ca];"
            f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo[ma];"
            f"[cv][ca][mv][ma]concat=n=2:v=1:a=1[v][a]")
    vb = args.video_bitrate
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-framerate", str(fps), "-t", f"{cover_s}", "-i", str(frame),
           "-i", str(master),
           "-f", "lavfi", "-t", f"{cover_s}", "-i", "anullsrc=r=48000:cl=stereo",
           "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "slow", "-profile:v", "high",
           "-b:v", vb, "-maxrate", "12M", "-bufsize", "24M", "-pix_fmt", "yuv420p", "-color_range", "tv",
           "-g", str(fps * 2), "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
           "-movflags", "+faststart", str(film)]
    print("[编码]", " ".join(cmd[:6]), "…", film)
    subprocess.run(cmd, check=True)
    total = float(probe(film)["format"]["duration"])
    master_s = float(info["format"]["duration"])
    meta = {
        "pipeline": "vibetennis",
        "column": "vibetennis",
        "canvas": [W, H],
        "fps": fps,
        "cover_seconds": cover_s,
        "cover_narrated": False,
        "outro_seconds": float(film_cfg.get("outro_seconds", 0) or 0),
        "master_seconds": round(master_s, 3),
        "film_seconds": round(total, 3),
        "narration_backend": "none",
        "captions": film_cfg.get("captions", "anchored"),
        "master_name": master.name,
    }
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print(f"[成片] {film}（{film.stat().st_size / 1e6:.1f} MB，{total:.2f}s ＝ 封面 {cover_s}s ＋ 母片 {master_s:.2f}s）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
