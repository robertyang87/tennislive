#!/usr/bin/env python3
"""vibetennis 成片定稿：**母片原样交付**，只写 render.json。

账号所有者 2026-10-30 更正：「不要把封面放在视频开头，也不要合进视频里」——成片就是
预渲好的 16:9 母片本身（音乐＋音效已混好，-14 LUFS / -1.5 dBTP），**一个字节都不改、
不重新编码**；3:4 高清封面是单独的一张图（`cover.py` → `poster.jpg`），只用作推送第一屏
和各平台的封面。所以这里只做两件事：把母片按 `<slug>.mp4` 拷进产物目录（字节逐一核对），
写 `render.json`。

    python3 tools/vibetennis/finalize.py --slug vibetennis-live-faster-2026 \
        --date 2026-10-30 --master /path/to/tennis_live_faster_v2b.mp4
    python3 tools/vibetennis/qc.py --slug ... --date ...      # 再跑质检出凭证
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CANVAS, load_spec, outdir_for, sha256  # noqa: E402


def probe(path: Path) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,width,height:format=duration", "-of", "json", str(path)], text=True)
    return json.loads(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--master", required=True, help="预渲好的 16:9 母片（含音乐与音效），原样交付")
    args = ap.parse_args()

    spec = load_spec(args.slug)
    film_cfg = spec["film"]
    W, H = CANVAS
    master = Path(args.master)
    info = probe(master)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    if (v["width"], v["height"]) != (W, H):
        raise SystemExit(f"母片是 {v['width']}×{v['height']}，这一栏要 {W}×{H}")
    outdir = outdir_for(args.date, args.slug)
    outdir.mkdir(parents=True, exist_ok=True)
    film = outdir / f"{args.slug}.mp4"
    shutil.copyfile(master, film)
    if sha256(film) != sha256(master):
        raise SystemExit("拷贝后的成片和母片字节不一致")
    secs = float(info["format"]["duration"])
    meta = {
        "pipeline": "vibetennis",
        "column": "vibetennis",
        "canvas": [W, H],
        "fps": int(film_cfg.get("fps", 30)),
        "cover_seconds": 0.0,
        "cover_in_film": False,
        "outro_seconds": float(film_cfg.get("outro_seconds", 0) or 0),
        "master_seconds": round(secs, 3),
        "film_seconds": round(secs, 3),
        "master_name": master.name,
        "master_sha256": sha256(master),
        "reencoded": False,
        "narration_backend": "none",
        "captions": film_cfg.get("captions", "anchored"),
    }
    (outdir / "render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print(f"[成片] {film}（{film.stat().st_size / 1e6:.1f} MB，{secs:.2f}s，母片原样，未重编码）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
