#!/usr/bin/env python3
"""vibetennis 成片质检（L2）：查**产物**，不查信号；全绿才写发布凭证。

赛场之上的 `tools/check_reel_landed.py` 钉死了 1080×1440、旁白、比分板、源片音轨，
这一栏一样都没有（16:9 横屏、无旁白、预渲 3D），硬套只会得到一条常年红的检查。
所以这里按同一个思路另起一份，查这一栏真正承诺的东西：

1. spec 自洽（`common.spec_problems`）
2. 画布 1920×1080、H.264 yuv420p、帧率与 spec 一致；AAC 48 kHz 双声道
3. 片长在 90–300 秒之间，并且 ＝ 封面秒数 ＋ 母片秒数（±0.5s）
4. 音视频首尾对齐（各 <1s），封面之后正文里没有 >3s 的数字静音
5. 响度：正文 -14 LUFS ±2、真峰值 ≤ -1.0 dBTP（混音合同是 -14 / -1.5）
6. 第一屏就是封面帧（和 `cover_16x9.jpg` 逐像素比，平均差 < 8/255）
7. 3:4 海报在、比例对、至少 1080×1440
8. 出一张 qc_contact.jpg 抽帧总览给人看一眼（不代替看片）

全绿写 `qc_attestation.json`（绑定 spec / 文案 / 海报 / 成片的 sha256 与字节数），
并把成片指纹写回 `render.json`。发布门禁（`publish_gate.py`）只认这份凭证。

    python3 tools/vibetennis/qc.py --slug vibetennis-live-faster-2026 --date 2026-10-30
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CANVAS, COVER_FRAME_NAME, MAX_SECONDS, MIN_SECONDS,  # noqa: E402
                    POSTER_NAME, outdir_for, sha256, spec_paths, spec_problems)

LUFS_TARGET, LUFS_TOL, TP_MAX = -14.0, 2.0, -1.0


def ffprobe(film: Path) -> dict:
    return json.loads(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt,sample_rate,channels,"
         "duration,start_time:format=duration", "-of", "json", str(film)], text=True))


def loudness(film: Path, start: float) -> tuple[float, float]:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{start}", "-i", str(film), "-vn",
                          "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    i = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])
    tp = float(re.findall(r"Peak:\s+(-?[\d.]+|-inf) dBFS", err)[-1])
    return i, tp


def silences(film: Path, start: float) -> list[tuple[float, float]]:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{start}", "-i", str(film), "-vn",
                          "-af", "silencedetect=n=-60dB:d=3", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) + start for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) + start for x in re.findall(r"silence_end: (-?[\d.]+)", err)]
    return list(zip(starts, ends + [math.inf] * (len(starts) - len(ends))))


def first_frame_diff(film: Path, frame: Path, at: float) -> float:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    W, H = CANVAS
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", f"{at}", "-i", str(film),
                                   "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    got = np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(float)
    want = np.asarray(Image.open(frame).convert("RGB").resize((W, H))).astype(float)
    return float(np.abs(got - want).mean())


def contact_sheet(film: Path, out: Path, duration: float) -> None:
    step = max(1.0, duration / 36)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(film), "-vf",
                    f"fps=1/{step:.3f},scale=384:216,tile=6x6", "-frames:v", "1",
                    "-q:v", "4", str(out)], check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", required=True)
    args = ap.parse_args()

    outdir = outdir_for(args.date, args.slug)
    film = outdir / f"{args.slug}.mp4"
    spec_path, copy_path = spec_paths(args.slug)
    stale = outdir / "qc_attestation.json"
    if stale.exists():
        stale.unlink()
        print(f"[QC] 本轮重验开始，先撤销旧凭证 {stale}")
    bad: list[str] = []

    def check(ok: bool, msg: str) -> None:
        print(f"[{'ok' if ok else '不合格'}] {msg}")
        if not ok:
            bad.append(msg)

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    probs = spec_problems(spec, args.slug)
    check(not probs, "spec 自洽" + ("：" + "；".join(probs) if probs else ""))
    check(copy_path.is_file(), f"文案 {copy_path.name} 在")
    check(film.is_file(), f"成片 {film.name} 在")
    if not film.is_file():
        print(f"\n共 {len(bad)} 项不合格"); return 1
    render = json.loads((outdir / "render.json").read_text(encoding="utf-8"))
    film_cfg = spec["film"]
    cover_s = float(render["cover_seconds"])
    check(abs(cover_s - float(film_cfg.get("cover_seconds", 1.2))) < 1e-6,
          f"封面停 {cover_s}s，和 spec 一致")

    info = ffprobe(film)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    W, H = CANVAS
    check((v["width"], v["height"]) == (W, H), f"分辨率 {v['width']}×{v['height']}（要 {W}×{H}）")
    check(v["codec_name"] == "h264" and v.get("pix_fmt") == "yuv420p",
          f"视频编码 {v['codec_name']} / {v.get('pix_fmt')}（要 h264 / yuv420p）")
    num, den = map(int, v["r_frame_rate"].split("/"))
    check(abs(num / den - int(film_cfg.get("fps", 30))) < 0.01, f"帧率 {num / den:.2f}")
    check(a is not None and a["codec_name"] == "aac" and int(a["sample_rate"]) == 48000
          and int(a["channels"]) == 2, "音轨 AAC 48kHz 双声道")
    dur = float(v["duration"])
    check(MIN_SECONDS <= dur <= MAX_SECONDS, f"片长 {dur:.2f}s（栏目要 {MIN_SECONDS:.0f}–{MAX_SECONDS:.0f}s）")
    want = cover_s + float(render["master_seconds"]) + float(render.get("outro_seconds") or 0)
    check(abs(dur - want) < 0.5, f"片长 ＝ 封面 {cover_s}s ＋ 母片 {render['master_seconds']}s（差 {dur - want:+.2f}s）")
    if a is not None:
        start_gap = float(a["start_time"]) - float(v["start_time"])
        tail_gap = float(v["start_time"]) + dur - float(a["start_time"]) - float(a["duration"])
        check(abs(start_gap) < 1.0, f"音视频首端差 {start_gap:.2f}s")
        check(abs(tail_gap) < 1.0, f"音视频尾端差 {tail_gap:.2f}s")
        lufs, tp = loudness(film, cover_s)
        check(abs(lufs - LUFS_TARGET) <= LUFS_TOL, f"正文响度 {lufs:.1f} LUFS（要 {LUFS_TARGET}±{LUFS_TOL}）")
        check(tp <= TP_MAX, f"真峰值 {tp:.1f} dBTP（要 ≤ {TP_MAX}）")
        quiet = [(s, e) for s, e in silences(film, cover_s) if s < dur - 6]
        check(not quiet, "正文没有 >3s 的数字静音" + (f"：{quiet}" if quiet else ""))
    else:
        lufs = tp = None
    frame = outdir / COVER_FRAME_NAME
    diff = first_frame_diff(film, frame, min(0.5, cover_s / 2)) if frame.is_file() else 255.0
    check(diff < 8.0, f"第一屏是封面帧（平均像素差 {diff:.2f}/255）")
    poster = outdir / POSTER_NAME
    if poster.is_file():
        from PIL import Image  # noqa: PLC0415
        pw, ph = Image.open(poster).size
        check(pw * 4 == ph * 3 and pw >= 1080, f"海报 {pw}×{ph}（3:4，至少 1080×1440）")
    else:
        check(False, f"海报 {poster.name} 在")
    contact_sheet(film, outdir / "qc_contact.jpg", dur)
    print(f"[QC] 抽帧总览 → {outdir / 'qc_contact.jpg'}（给人看一眼，不代替看片）")

    if bad:
        print("[QC] 本轮不生成发布凭证")
        print(f"\n共 {len(bad)} 项不合格")
        return 1
    payload = {
        "status": "pass",
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "slug": args.slug,
        "column": "vibetennis",
        "spec_sha256": sha256(spec_path),
        "copy_sha256": sha256(copy_path),
        "poster_sha256": sha256(poster),
        "film_sha256": sha256(film),
        "film_bytes": film.stat().st_size,
        "checks": {
            "canvas": [W, H],
            "film_seconds": round(dur, 3),
            "cover_seconds": cover_s,
            "loudness_lufs": round(lufs, 2) if lufs is not None else None,
            "true_peak_dbtp": round(tp, 2) if tp is not None else None,
            "cover_frame_diff": round(diff, 2),
            "audio_start_max_s": 1.0,
            "audio_tail_max_s": 1.0,
            "narration": "none",
            "human_full_watch_claimed": False,
        },
    }
    att = outdir / "qc_attestation.json"
    att.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render.update(film_sha256=payload["film_sha256"], film_bytes=payload["film_bytes"],
                  qc_attestation_sha256=sha256(att))
    (outdir / "render.json").write_text(json.dumps(render, ensure_ascii=False, indent=2) + "\n",
                                        encoding="utf-8")
    print(f"[QC] 发布凭证 -> {att}（film {payload['film_sha256'][:12]}…）")
    print("\n共 0 项不合格")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
