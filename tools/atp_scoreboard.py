"""ATP 巡回赛转播比分板：逐帧透明蒙版回贴，板多宽切多宽，黄条单独切。

账号所有者 2026-09-24（成都 `shang-mannarino-chengdu-2026-r1`）：

> 「那些黄条，比如说 break point、set point、match point 这些东西好像没有保全呀……
>  一个横条接到比分板的右边」
> 「不要切的过多，就是它画面里面的比分板的宽度是多少，就切多少。然后那个黄条
>  要单独切，不然的话会带着一些其他额外的画面进来，感觉屏幕像花掉一样」

原来的回贴（`resolve_board_insets`）是**一段一个矩形**：按这一段里板最宽的那一刻
裁。于是板窄的那几帧（这一分打完、小分那一列收起来）会多抠一截球场贴到画面上；
而黄条（`BREAK POINT` / `SET POINT` / `MATCH POINT`）只占板下面那一行，把矩形
放宽到黄条的右缘，就连上面那一行旁边的球场也一起抠进来——那就是「花掉」。

所以这里和美网那条（`scoreboard_geometry.py`）同一个形状：**逐帧量、逐帧出蒙版**，
蒙版里只有两块是实的——

- 板：从板左缘到**这一帧**板的右缘，板的整个高度
- 黄条：只取它自己的外框（它那一行的高度 × 它自己的宽度）

其余全透明；板不在画面里的帧整张透明（转播把板淡出时，贴片也跟着消失）。

判据量出来的（成都 Tennis TV 转播，1080p，本地源片逐像素读的）：

    板底    深藏青 (6,16,36)            → max(r,g,b) < 80
    盘分格  饱和蓝 (22,16,248)          → b > 140 且 r,g < 80
    小分格  半透明深灰 (38,60,50)        → max < 80
            杭州蓝场上是 (36,62,86)      → max < 110 且和 < 220（见 board_mask）
    板里的字 白 (240,255,250)            → 夹在上面三种中间，按列计时不单独认
    球场    绿 (123,167,128) / 蓝绿 (95,147,135) → 都不算板
    黄条    黄绿 (215,245,100)，字是深色  → r>150 且 g>185 且 g-b>60
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

PROFILE = "atp-tour-v1"
EDGE_PAD = 2          # 板右缘外多留的源片像素（抗锯齿的那一列）
SCAN_W = 760          # 从板左缘往右扫多宽：板 ≤ ~420、黄条 ≤ ~260
MIN_BOARD_W = 150     # 板最窄也有名字那一栏宽；比这窄就不是板
MEDIAN = 5            # 右缘按前后 5 帧取中位数，压掉球员走过板边那一两帧


def board_mask(band: np.ndarray) -> np.ndarray:
    r, g, b = (band[:, :, i].astype(np.int16) for i in range(3))
    top = np.maximum(np.maximum(r, g), b)
    # ⚠️ 小分格是**半透明**的，底下透出来的是球场：成都绿场上它是 (38,60,50)，
    # 杭州蓝场上是 (36,62,86)——蓝通道被球场抬过了 80。只认 `max < 80` 时，
    # `zhang-wong-hangzhou-2026-r1` 两趟 render 的回贴全停在盘分格右边，
    # 15/30/40 那一列整列没贴上，渲染和 QC 一声不吭。所以再收一档「暗而不黑」：
    # max < 110 且三通道和 < 220——球场（蓝 ~470、绿 ~420）和白字都远在外面。
    dark = (top < 80) | ((top < 110) & (r + g + b < 220))
    blue = (b > 140) & (r < 80) & (g < 80)
    return dark | blue


def yellow_mask(band: np.ndarray) -> np.ndarray:
    r, g, b = (band[:, :, i].astype(np.int16) for i in range(3))
    return (r > 150) & (g > 185) & (g - b > 60)


def board_edge(band: np.ndarray, cap: int | None = None) -> int | None:
    """这一帧板的右缘（相对带左缘的列号，不含），板不在就 None。

    按列算「板色像素占这一列多少」。板里有白字，所以一列的板色占比到不了 1，
    但从来不会低于一半；球场那一侧是 0。从左往右走到**连着 4 列**都低于一半
    为止——4 列是为了跨过盘分格之间那道细缝。
    """
    frac = board_mask(band).mean(axis=0)
    if frac[4:MIN_BOARD_W].mean() < 0.7:
        return None
    # 板一定带着饱和蓝的盘分格；盘间那张大图形（「ROUND 1 | CENTER COURT」）
    # 和近景里的深色挡板都没有。没有这一格就不是板。
    r, g, b = (band[:, :, i].astype(np.int16) for i in range(3))
    blue_cols = ((b > 180) & (r < 70) & (g < 70)).mean(axis=0) > 0.4
    if blue_cols.sum() < 6:
        return None
    low = frac < 0.5
    edge = None
    for x in range(MIN_BOARD_W, len(frac) - 4):
        if low[x:x + 4].all():
            edge = x
            break
    if edge is None:                  # 一路连到带的右头：板和深色背景连成了一片
        edge = len(frac)
    # 近景里板右边是深蓝挡板时，两者颜色分不开，量出来会一路宽出去。上限是 spec
    # `scorebox` 的右缘——那是这场板**最宽状态**的实测值，板不会比它更宽。
    return min(edge, cap) if cap is not None else edge


def tag_rect(band: np.ndarray, edge: int) -> tuple[int, int, int, int] | None:
    """紧贴板右缘的黄条外框 (x0, y0, x1, y1)（相对带），没有就 None。"""
    yel = yellow_mask(band)
    cols = yel.mean(axis=0) > 0.12
    start = None
    for x in range(max(0, edge - 6), min(len(cols), edge + 14)):
        if cols[x]:
            start = x
            break
    if start is None:
        return None
    x1 = start
    miss = 0
    while x1 < len(cols) and miss < 10:     # 字母之间的空隙不算断
        miss = 0 if cols[x1] else miss + 1
        x1 += 1
    x1 -= miss
    if x1 - start < 40:
        return None
    rows = np.flatnonzero(yel[:, start:x1].mean(axis=1) > 0.25)
    if rows.size < 12:
        return None
    return (edge, int(rows.min()), x1, int(rows.max()) + 1)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def scan(source: Path, box: tuple[int, int, int, int], start: float,
         seconds: float, fps: str) -> tuple[list, int]:
    """逐帧量 → [(板右缘 or None, 黄条框 or None)]，以及扫的带宽。"""
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
        e = board_edge(band, cap=x1 - x0)
        frames.append((e, None if e is None else tag_rect(band, e)))
    if not frames:
        raise RuntimeError(f"{start:.2f}s 起一帧都没解出来（解码失败，不是板不在）")
    return frames, width


def stabilize(frames: list) -> list:
    """板右缘取前后 MEDIAN 帧的中位数（只在板在的帧之间取）；黄条要连着 3 帧在才认。"""
    edges = [e for e, _ in frames]
    out = []
    half = MEDIAN // 2
    for i, (e, tag) in enumerate(frames):
        if e is None:
            out.append((None, None))
            continue
        near = [v for v in edges[max(0, i - half):i + half + 1] if v is not None]
        m = int(np.median(near))
        tags = [t for _, t in frames[max(0, i - 1):i + 2]]
        keep = tag if (tag is not None and sum(t is not None for t in tags) >= 2) else None
        if keep is not None:
            keep = (m, keep[1], keep[2], keep[3])
        out.append((m, keep))
    return out


def write_mask(frames: list, width: int, height: int, fps: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "gray",
         "-video_size", f"{width}x{height}", "-framerate", fps, "-i", "-", "-an",
         "-c:v", "ffv1", "-threads", "1", str(dest)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    m = np.zeros((height, width), np.uint8)
    try:
        for e, tag in frames:
            m.fill(0)
            if e is not None:
                m[:, :min(width, e + EDGE_PAD)] = 255
                if tag is not None:
                    tx0, ty0, tx1, ty1 = tag
                    m[ty0:ty1, tx0:min(width, tx1 + EDGE_PAD)] = 255
            enc.stdin.write(m.tobytes())
        enc.stdin.close()
        err = enc.stderr.read()
        if enc.wait():
            raise RuntimeError(err.decode(errors="replace"))
    finally:
        if enc.poll() is None:
            enc.kill()


def resolve_masks(sources: dict, segments: list, outdir: Path, fps: str,
                  tail: float) -> Path:
    """给开了 `score_inset` 的段逐帧出蒙版，就地写回 `seg.score_inset` / `score_inset_mask`。

    `seg.score_inset` 的右缘改成**这一段真正用到的最右一列**（板或黄条），
    所以贴片不会比画面里出现过的图形更宽；更窄的那些帧由蒙版挡掉。
    """
    records = []
    rate = float(Fraction(fps))
    for i, seg in enumerate(segments):
        if not seg.score_inset:
            continue
        x0, y0, _x1, y1 = seg.score_inset
        seconds = seg.end - seg.start + tail * seg.speed
        raw, width = scan(Path(sources[seg.source]), seg.score_inset, seg.start, seconds, fps)
        frames = stabilize(raw)
        present = [f for f in frames if f[0] is not None]
        if not present:
            raise RuntimeError(
                f"第 {i + 1} 段（源片 {seg.start:.2f}→{seg.end:.2f}s）一帧都没认出 ATP 比分板。"
                "整段都是近景/回放的话写 \"score_inset\": false ＋ \"_score_inset_why\"；"
                "板在但认不出，是这场转播的图形换了样子——先抽一帧量颜色，别调宽兜底。")
        right = max(max(e + EDGE_PAD, (t[2] + EDGE_PAD) if t else 0) for e, t in present)
        right = min(width, right + (right % 2))
        dest = Path(outdir) / "score_masks" / f"segment-{i + 1:02d}.mkv"
        write_mask(frames, right, y1 - y0, fps, dest)
        seg.score_inset = (x0, y0, x0 + right, y1)
        seg.score_inset_mask = str(dest.resolve())
        seg.score_inset_spans = None
        n_tag = sum(1 for f in present if f[1] is not None)
        widths = sorted({e for e, _ in present})
        records.append({"segment": i, "frames": len(frames), "present_frames": len(present),
                        "tag_frames": n_tag, "board_edges": widths, "right": right,
                        "mask": str(dest), "mask_sha256": _sha256(dest)})
        print(f"[score-mask] 第 {i + 1} 段：板在 {len(present)}/{len(frames)} 帧，"
              f"板宽逐帧 {widths[0]}~{widths[-1]}px，黄条 {n_tag} 帧，贴片最宽 {right}px"
              f"（{rate:g} fps 逐帧蒙版，板多宽切多宽、黄条单独切）")
    proof = {"status": "pass", "profile": PROFILE, "segments": records}
    p = Path(outdir) / "scoreboard_qc.json"
    p.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
