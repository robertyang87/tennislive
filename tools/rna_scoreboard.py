"""纳达尔学院十周年 SLAM 转播，实源 mXIoUmxozgw / HLTTYfIi5J8 标定。

1080p 左板外缘 x183:645, y890:1000。青色队标约 (87,247,202)，
藏青名字／分数底 (4,27,74)，白边与行分隔线。发球点在名字栏内。
右下团体总比分板不回贴。板出现才贴；必须两种签名色同时成立，
并找到真实右边界，不能以暗背景替代比分板。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

from atp_scoreboard import report_beyond_hint, stabilize, write_mask

PROFILE = "rna-slam-v1"
EDGE_PAD = 2
HINT_SLACK = 1.0


def _rgb(band: np.ndarray):
    return (band[:, :, i].astype(np.int16) for i in range(3))


def cyan(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (r < 140) & (g > 205) & (b > 155) & (g - r > 80)


def navy(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (r < 30) & (g < 55) & (b > 45) & (b < 105) & (b - g > 25)


def board_edge(band: np.ndarray, cap: int | None = None) -> int | None:
    """学院 SLAM 板必须同时含左青色队标及右藏青名字栏；缺席帧全透明。"""
    h, w = band.shape[:2]
    logo_w = int(h * .8)
    if w < 3*h or cyan(band[:, 4:logo_w-4]).mean() < .55:
        return None
    if navy(band[:, logo_w+5:int(3*h)]).mean() < .58:
        return None
    r, g, b = _rgb(band)
    white = np.minimum(np.minimum(r, g), b) > 175
    # The right border is two white columns (x642:644 in 1080p samples).
    # Unlike the court-colour transition, it remains measurable against navy
    # advertising/close-up backgrounds. Skip the internal name/score separator.
    white_cols = white.mean(axis=0)
    for x in range(int(3.8*h), w - 2):
        if (white_cols[x:x+2] > .65).all() and navy(band[:, x-12:x]).mean() > .6:
            end = x + 2
            while end < w and white_cols[end] > .65:
                end += 1
            return end
    return None


def dot_rect(band: np.ndarray, edge: int):
    # The service dot is inside the name column, already preserved by the board mask.
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def scan(source: Path, box: tuple[int, int, int, int], start: float,
         seconds: float, fps: str) -> tuple[list, int]:
    """逐帧量 → [(板右缘 or None, 发球小球框 or None)]，以及扫的带宽。"""
    x0, y0, x1, y1 = box
    sw = int(subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width", "-of", "csv=p=0", str(source)], text=True).strip().split(",")[0])
    # spec 的 x1 只是提示：带至少扫到源片一半宽，双打／多一盘的板更长也量得到
    hint = int((x1 - x0) * HINT_SLACK)
    width = min(sw - x0, max(hint, sw // 2 - x0))
    height = y1 - y0
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{seconds:.3f}",
         "-i", str(source), "-an", "-sn",
         "-vf", f"format=rgb24,crop={width}:{height}:{x0}:{y0},fps={fps}",
         "-f", "rawvideo", "-"], capture_output=True, check=False)
    raw = proc.stdout or b""
    per = width * height * 3
    frames = []
    for k in range(len(raw) // per):
        band = np.frombuffer(raw[k * per:(k + 1) * per], np.uint8).reshape(height, width, 3)
        e = board_edge(band, cap=min(width, hint))
        frames.append((e, None if e is None else dot_rect(band, e)))
    if not frames:
        raise RuntimeError(f"{start:.2f}s 起一帧都没解出来（解码失败，不是板不在）")
    return frames, width


def resolve_masks(sources: dict, segments: list, outdir: Path, fps: str,
                  tail: float) -> Path:
    """给开了 `score_inset` 的段逐帧出蒙版，就地写回 `seg.score_inset` / `score_inset_mask`。"""
    rate = float(Fraction(fps))
    scanned = []
    for i, seg in enumerate(segments):
        if not seg.score_inset:
            continue
        seconds = seg.end - seg.start + tail * seg.speed
        raw, width = scan(Path(sources[seg.source]), seg.score_inset, seg.start, seconds, fps)
        scanned.append((i, seg, stabilize(raw), width))
    if scanned and not any(e is not None for _i, _s, fr, _w in scanned for e, _t in fr):
        raise RuntimeError(
            f"{len(scanned)} 段一帧都没认出纳达尔学院 SLAM 的比分板（{PROFILE}：左青色队标＋藏青名字栏）"
            "——这场转播的图形和标定的那一版不一样。先抽一帧量颜色、补标定，"
            "别退回整段一个矩形的老回贴（那正是「消失后背景还在」「右边多一块补丁」的来路）。")
    records = []
    for i, seg, frames, width in scanned:
        x0, y0, spec_x1, y1 = seg.score_inset
        live = [f for f in frames if f[0] is not None]
        if not live:
            raise RuntimeError(
                f"第 {i + 1} 段（源片 {seg.start:.2f}→{seg.end:.2f}s）一帧都没认出比分板。"
                "整段都是近景/看台/回放的话写 \"score_inset\": false ＋ \"_score_inset_why\"。")
        right = max(max(e + EDGE_PAD, (t[2] + EDGE_PAD) if t else 0) for e, t in live)
        right = min(width, right + right % 2)
        dest = Path(outdir) / "score_masks" / f"segment-{i + 1:02d}.mkv"
        write_mask(frames, right, y1 - y0, fps, dest)
        seg.score_inset = (x0, y0, x0 + right, y1)
        seg.score_inset_mask = str(dest.resolve())
        seg.score_inset_spans = None
        report_beyond_hint(i, x0 + right, spec_x1)
        ws = sorted({e for e, _ in live})
        n_dot = sum(1 for _e, t in live if t is not None)
        records.append({"segment": i, "frames": len(frames), "present_frames": len(live),
                        "dot_frames": n_dot, "board_edges": [ws[0], ws[-1]], "right": right,
                        "mask": str(dest), "mask_sha256": _sha256(dest)})
        print(f"[score-mask] 第 {i + 1} 段：板在 {len(live)}/{len(frames)} 帧，"
              f"板宽逐帧 {ws[0]}~{ws[-1]}px，发球小球 {n_dot} 帧，贴片最宽 {right}px"
              f"（{rate:g} fps 逐帧蒙版，{PROFILE}）")
    proof = {"status": "pass", "profile": PROFILE, "segments": records}
    p = Path(outdir) / "scoreboard_qc.json"
    p.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
