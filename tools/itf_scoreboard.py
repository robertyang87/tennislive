"""比利·简·金杯（ITF 转播）比分板：逐帧透明蒙版回贴，板在才贴、板多宽切多宽。

账号所有者 2026-09-24：「消失后背景还在……像狗皮膏药」「右边突然多一块补丁」
「那去彻底解决啊」。这套板在 `zhang-cocciaretto` / `zheng-paolini`（深圳，
ITF 官方 YouTube 转播）两条片子上一直走老回贴——一段一个矩形、按「暗」认板。

判据量出来的（`zheng-paolini-bjk-cup-2026-qf` 源片 `MP8ZbrE0lKw`，frame-grab
每 3 秒一帧逐像素读的）：

    板底     饱和宝蓝 (24,79,240) / (21,72,223)   → b>190 且 r<60 且 g<110
    小分格   浅青 (142,255,251) / (130,246,225)   → g>228 且 b>200 且 90<r<180
    发球方   黄绿小球 (192,255,67)，挂在小分格右边 → r>160 且 g>230 且 b<170
    字       白 (228,254,255)、国旗红 (218,8,37)
    球场     亮蓝 (117,195,252)——g≈195，和小分格的 g≥238 分得开
    看台暗场 深蓝 (0,46,93)——b<190

「板在」要名字栏（板左缘往右 1.5 倍板高）过半是宝蓝底——球场、看台、场地上刷的
白字都过不了。发球小球单独切（只取它自己那一小块，像 ATP 的黄条），不把它
周围的球场一起抠进来。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

from atp_scoreboard import beyond_hint, report_beyond_hint, stabilize, write_mask

PROFILE = "itf-bjk-v1"
EDGE_PAD = 2
NAME_W = 1.5        # 判「板在」看名字栏这么宽（×板高）
MIN_BOARD_W = 1.5   # 板最窄也有名字栏这么宽（×板高）
DOT_REACH = 0.4     # 小分格右缘之后这么远（×板高）以内找发球小球
CELL_TAIL = 8       # 越过提示右缘时：最后一列浅青小分格之后最多再这么宽（源片像素，格子的外框）
HINT_SLACK = 1.3    # 老的扫描宽度＝spec 板宽 ×1.3；现在它是「提示」，越过要有浅青格撑着


def _rgb(band: np.ndarray):
    return (band[:, :, i].astype(np.int16) for i in range(3))


def royal(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (b > 190) & (r < 60) & (g < 110)


def cell(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (g > 228) & (b > 200) & (r > 90) & (r < 180)


def dot(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (r > 160) & (g > 230) & (b < 170)


def board_colour(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    white = np.minimum(np.minimum(r, g), b) > 200
    red = (r > 180) & (g < 80) & (b < 80)
    return royal(band) | cell(band) | white | red


def present(band: np.ndarray) -> bool:
    h = band.shape[0]
    name = band[:, :int(NAME_W * h)]
    return bool(royal(name).mean() >= 0.5)


def board_edge(band: np.ndarray, cap: int | None = None) -> int | None:
    """这一帧板的右缘（相对带左缘，不含），板不在就 None。"""
    if not present(band):
        return None
    h = band.shape[0]
    frac = board_colour(band).mean(axis=0)
    low = frac < 0.5
    edge = None
    for x in range(int(MIN_BOARD_W * h), len(frac) - 4):
        if low[x:x + 4].all():
            edge = x
            break
    if edge is None:                  # 一路连到带右头：板和背景连成了一片，读数不可信
        edge = len(frac)
        return min(edge, cap) if cap is not None else edge
    cells = np.flatnonzero(cell(band).mean(axis=0) > 0.2)
    anchor = int(cells.max()) + 1 + CELL_TAIL if cells.size else 0
    return beyond_hint(edge, cap, anchor)


def dot_rect(band: np.ndarray, edge: int) -> tuple[int, int, int, int] | None:
    """紧挨着板右缘的发球小球外框 (x0, y0, x1, y1)，没有就 None。"""
    h = band.shape[0]
    hi = min(band.shape[1], edge + int(DOT_REACH * h))
    m = dot(band[:, max(0, edge - 4):hi])
    if m.sum() < max(12, (h // 10) ** 2):
        return None
    ys, xs = np.nonzero(m)
    x0 = max(0, edge - 4) + int(xs.min())
    return (min(edge, x0), int(ys.min()), max(0, edge - 4) + int(xs.max()) + 1,
            int(ys.max()) + 1)


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
    # （账号所有者 2026-09-25「同时要自适应不同的长度啊」）；原来的 ×1.3 退成提示
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
            f"{len(scanned)} 段一帧都没认出比利·简·金杯的比分板（{PROFILE}：名字栏的宝蓝底）"
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
