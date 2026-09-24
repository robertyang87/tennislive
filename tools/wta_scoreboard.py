"""WTA 巡回赛转播比分板：逐帧透明蒙版回贴，板在才贴、板多宽切多宽。

账号所有者 2026-09-24（新加坡 `prozorova-eala-singapore-2026-r2` 第一版成片）：

> 「裁剪的比分板，有时候消失后背景还在，显得很突兀，像狗皮膏药贴上去的」
> 「而且有时候还会裁剪过多，导致右边突然多一块补丁似的」

两句话是老回贴（`resolve_board_insets`）的两个结构性毛病，和 ATP 那条
（`atp_scoreboard.py`）同一个形状：

- **板没了补丁还在**：「板在不在」原来按「离球场色够远＋够暗」判。WTA 夜场的
  近景背后是深色人群、深色花墙，**它们也满足这两条**——实测新加坡这条源片
  看台镜头（88、92s）、花墙（216s）、盘间大图形（224s）的名字区「暗像素」占比
  0.79~1.00，比真板（0.69~0.81）还高。于是整块人群被当成板贴了出去。
- **右边多一块补丁**：一段一个矩形，按这一段最宽的那一刻（或 spec 的兜底
  右缘）裁，板窄的那几帧就多抠一截球场贴到另一个位置。

所以这里**逐帧**量、逐帧出蒙版（板不在的帧整张透明，板窄的帧蒙版跟着窄），
而「板在」要一个**只有板才有的正面特征**，不能靠「暗」：

    板底     半透明深灰绿 (55,95,66)，压在深色背景上更暗 (6,46,32)
    局分格   **亮薄荷绿** (21,255,171) / (40,228,154)  → g>195 且 r<100 且 b>80
    字       白 (254,255,253)
    球场     绿 (125,179,110)、近景的浅紫蓝 (180,189,255)、灰白 (207,218,210)

薄荷绿局分格是板的签名：有板的帧 9~10 列（640 宽抽帧），看台/花墙/盘间图形/
球场一律 0~1。**唯一的例外**是开局还没有局分那几秒（板只有名字＋小分），
那时退到第二条：名字区的底色本身就是板底色（深灰绿、g 比 r 高 20 以上、
一半以上像素贴着它）。深色人群的底色是灰黑 (20,17,22)，花墙偏紫 (98,61,104)，
都过不了。

右缘：从名字那一栏往右数「板色列」（暗、薄荷绿、白字），连着 4 列都不是就停；
**有薄荷绿格时，右缘最多到最后一列薄荷绿再往右一格小分宽**（`POINTS_MAX`）——
板最右边永远是「当前盘局分＋小分」，背景是深色人群时暗像素会一路连出去，
这一刀把它钉回板上。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

from atp_scoreboard import stabilize, write_mask

PROFILE = "wta-tour-v1"
EDGE_PAD = 2          # 板右缘外多留的源片像素（抗锯齿的那一列）
SCAN_W = 760          # 从板左缘往右扫多宽：板 ≤ ~480
MIN_BOARD_W = 150     # 名字那一栏最窄也这么宽
NAME_W = 140          # 判「板在」看名字那一栏的这么宽
POINTS_MAX = 56       # 最后一列薄荷绿之后，小分格最多这么宽（源片像素；三档实测 51~54）
MINT_COLS = 12        # 薄荷绿列至少这么多（源片像素；640 宽抽帧量到 9~10 列 ×3）


def _rgb(band: np.ndarray):
    return (band[:, :, i].astype(np.int16) for i in range(3))


def mint_mask(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (g > 195) & (r < 100) & (b > 80)


def board_colour(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    return (mx < 130) | mint_mask(band) | (mn > 225)


def present(band: np.ndarray) -> bool:
    """这一帧板在不在。要正面特征（薄荷绿局分格，或板底色的名字栏），不认「暗」。"""
    if band.ndim != 3 or band.shape[1] < MIN_BOARD_W:
        return False
    name = band[:, 8:8 + NAME_W].astype(np.int16)
    dark = (name.max(axis=2) < 130).mean()
    mint_cols = (mint_mask(band).mean(axis=0) > 0.4).sum()
    if mint_cols >= MINT_COLS:
        # 盘间那张大图形（「ROUND 2」＋名字＋绿条）也有大片薄荷绿，但名字栏是
        # 白底——真板的名字栏暗像素 0.73~0.82，那张图形是 0.00
        return dark >= 0.5
    med = np.median(name.reshape(-1, 3), axis=0)
    r, g, b = (int(v) for v in med)
    near = (np.linalg.norm(name - med, axis=2) < 30).mean()
    return (35 <= r <= 95 and 80 <= g <= 120 and 50 <= b <= 105
            and g - r >= 20 and near >= 0.5 and dark >= 0.5)


def board_edge(band: np.ndarray, cap: int | None = None) -> int | None:
    """这一帧板的右缘（相对带左缘的列号，不含），板不在就 None。"""
    if not present(band):
        return None
    frac = board_colour(band).mean(axis=0)
    low = frac < 0.5
    edge = None
    for x in range(MIN_BOARD_W, len(frac) - 4):
        if low[x:x + 4].all():
            edge = x
            break
    if edge is None:
        edge = len(frac)
    mint_cols = np.flatnonzero(mint_mask(band).mean(axis=0) > 0.4)
    if mint_cols.size >= MINT_COLS:
        edge = min(edge, int(mint_cols.max()) + 1 + POINTS_MAX)
    return min(edge, cap) if cap is not None else edge


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def scan(source: Path, box: tuple[int, int, int, int], start: float,
         seconds: float, fps: str) -> tuple[list, int]:
    """逐帧量 → [(板右缘 or None, None)]（WTA 板没有黄条），以及扫的带宽。"""
    x0, y0, x1, y1 = box
    sw = int(subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width", "-of", "csv=p=0", str(source)], text=True).strip().split(",")[0])
    width = min(sw - x0, SCAN_W)
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
        frames.append((board_edge(band, cap=x1 - x0), None))
    if not frames:
        raise RuntimeError(f"{start:.2f}s 起一帧都没解出来（解码失败，不是板不在）")
    return frames, width


def debounce(frames: list, hold: int = 3) -> list:
    """「在 / 不在」连着 `hold` 帧才翻：板淡入淡出那几帧和球员走过不闪。"""
    out = list(frames)
    n = len(frames)
    for i in range(n):
        here = frames[i][0] is not None
        run = [frames[j][0] is not None for j in range(max(0, i - hold // 2),
                                                       min(n, i + hold // 2 + 1))]
        if here and sum(run) < (len(run) + 1) // 2:
            out[i] = (None, None)
    return out


def resolve_masks(sources: dict, segments: list, outdir: Path, fps: str,
                  tail: float) -> Path:
    """给开了 `score_inset` 的段逐帧出蒙版，就地写回 `seg.score_inset` / `score_inset_mask`。

    **整条片子一帧都没认出这块板**（换了一家转播、图形长得不一样）→ 报错，
    **不退回老的整段矩形回贴**（账号所有者 2026-09-24「那去彻底解决啊」）。
    有段认出了、某一段一帧都没有，照 ATP 那条报错（那一段写 `score_inset: false`）。
    """
    rate = float(Fraction(fps))
    scanned = []
    for i, seg in enumerate(segments):
        if not seg.score_inset:
            continue
        seconds = seg.end - seg.start + tail * seg.speed
        raw, width = scan(Path(sources[seg.source]), seg.score_inset, seg.start, seconds, fps)
        scanned.append((i, seg, debounce(stabilize(raw)), width))
    if scanned and not any(e is not None for _i, _s, fr, _w in scanned for e, _t in fr):
        raise RuntimeError(
            f"{len(scanned)} 段一帧都没认出 WTA 比分板（{PROFILE} 的薄荷绿局分格）——"
            "多半是这场转播的图形和标定的那一版不一样。**不退回老的整段矩形回贴**"
            "（那正是「消失后背景还在」「右边多一块补丁」的来路）：先用 frame-grab "
            "抽几帧量颜色、给这家转播补一套判据；整段真没有板的写 "
            "\"score_inset\": false ＋ \"_score_inset_why\"。")
    records = []
    for i, seg, frames, width in scanned:
        x0, y0, _x1, y1 = seg.score_inset
        live = [e for e, _ in frames if e is not None]
        if not live:
            raise RuntimeError(
                f"第 {i + 1} 段（源片 {seg.start:.2f}→{seg.end:.2f}s）一帧都没认出 WTA 比分板。"
                "整段都是近景/看台/回放的话写 \"score_inset\": false ＋ \"_score_inset_why\"。")
        right = min(width, max(live) + EDGE_PAD)
        right += right % 2
        right = min(width, right)
        dest = Path(outdir) / "score_masks" / f"segment-{i + 1:02d}.mkv"
        write_mask(frames, right, y1 - y0, fps, dest)
        seg.score_inset = (x0, y0, x0 + right, y1)
        seg.score_inset_mask = str(dest.resolve())
        seg.score_inset_spans = None
        widths = sorted(set(live))
        records.append({"segment": i, "frames": len(frames), "present_frames": len(live),
                        "board_edges": [widths[0], widths[-1]], "right": right,
                        "mask": str(dest), "mask_sha256": _sha256(dest)})
        print(f"[score-mask] 第 {i + 1} 段：板在 {len(live)}/{len(frames)} 帧，"
              f"板宽逐帧 {widths[0]}~{widths[-1]}px，贴片最宽 {right}px"
              f"（{rate:g} fps 逐帧蒙版：板不在就不贴，板多宽切多宽）")
    proof = {"status": "pass", "profile": PROFILE, "segments": records}
    p = Path(outdir) / "scoreboard_qc.json"
    p.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
