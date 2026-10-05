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

2026-10-04：搜索带的高度也不能当作实心板。逐帧量两行主体的原生外缘，
BREAK/SET/MATCH POINT 短窄标签按它自己的行轮廓保留；标签旁的球场始终透明。
整段容器仅用已量到的图形并集，蒙版仍逐帧变化，宽高同比缩放由调用方统一处理。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

from atp_scoreboard import beyond_hint, report_beyond_hint

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
        # A centred result graphic can put its mint winner row at the far
        # right of this wide search band while the supposed name column is
        # just a uniform blue courtside wall. Dark pixels alone accept that
        # wall. A native name column has white lettering or the green/teal
        # board tint; reject only the blue, textless background combination.
        med = np.median(name.reshape(-1, 3), axis=0)
        white = (name.min(axis=2) > 225).mean()
        blue_background = med[2] - med[1] > 20 and white < .01
        return dark >= 0.5 and not blue_background
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
    mint_cols = mint_mask(band).mean(axis=0) > 0.4
    cells = [(lo, hi) for lo, hi in _runs(mint_cols)
             if lo >= MIN_BOARD_W and hi - lo >= MINT_COLS]
    if cells:
        # Mint TEXT in the point-score slot (e.g. 40) is not another filled games
        # cell. Use the broad solid cell, rather than the last mint-coloured letter.
        cell_lo, cell_hi = max(cells, key=lambda bounds: bounds[1] - bounds[0])
        margin = max(1, band.shape[0] // 10)
        body = band[margin:-margin].astype(np.int16)
        jump = np.abs(body[:, 1:] - body[:, :-1]).mean(axis=2)
        persistent = (jump > 8).mean(axis=0)
        # A native border/background boundary runs through both player rows.
        # Point numerals form discontinuous strokes; no fixed point-slot width
        # is made opaque, and stat panels without a point slot remain narrower.
        first = cell_hi + 6
        last = min(band.shape[1] - 1, cell_hi + POINTS_MAX + EDGE_PAD)
        boundaries = [x for x in range(first, last + 1) if persistent[x - 1] >= .55]
        if boundaries:
            return boundaries[-1]
        if edge < cell_hi + POINTS_MAX:
            return edge
        # The native graphic wipes away from right to left. During the last
        # frames the point slot is gone and the wipe crosses the mint games
        # cell itself. Measure its remaining vertical edge, including only the
        # observed antialias fringe; never substitute the old slot width.
        # A native wipe/glow may transition across two antialias pixels on
        # either side of the thresholded mint edge. Still require a measured
        # persistent edge plus exposed background, never a padded rectangle.
        wipe_edges = [x for x in range(max(cell_lo + 1, cell_hi - EDGE_PAD),
                                      min(band.shape[1], cell_hi + 2 * EDGE_PAD) + 1)
                      if persistent[x - 1] >= .55]
        # A complete games cell spans at least half one player-row height.
        # A truncated residual cell proves the wipe crossed the games cell.
        # An intact cell needs separate exposed-background evidence below.
        # Compare with the actual mint cell's vertical span, not the search
        # band's expanded body height. A full 28px games cell in Beijing has
        # a ~108px native height; the geometry scan's antialias fringe expands
        # its band to 117px and must not turn that intact cell into a wipe.
        cell_rows = np.flatnonzero(mint_mask(band[:, cell_lo:cell_hi]).any(axis=1))
        cell_height = int(cell_rows[-1] - cell_rows[0] + 1) if cell_rows.size else 0
        truncated_cell = cell_hi - cell_lo < cell_height / 4
        # Prefer the established tight edge when its background is already
        # exposed. Only inspect the wider glow transition if that evidence
        # fails; do not expand previously verified native wipe silhouettes.
        tight = [x for x in wipe_edges if x <= cell_hi + EDGE_PAD]
        candidates = tight[-1:] + [x for x in wipe_edges if x > cell_hi + EDGE_PAD]
        for wipe_edge in candidates:
            # A wipe can remove the point slot while leaving the games cell
            # intact. Require positive exposed blue-background evidence beyond
            # its antialias fringe; a dark, unmeasurable point slot must still
            # fail rather than being mistaken for this native outer edge.
            exposed = body[:, wipe_edge + 2 * EDGE_PAD:wipe_edge + 2 * EDGE_PAD + 6]
            r, g, b = _rgb(exposed)
            exposed_blue = exposed.size > 0 and (
                (b - g > 15) & (b - r > 20)).mean() >= .8
            if truncated_cell or exposed_blue:
                return wipe_edge
        # Native AV1 antialias can spread the outer border over two pixels:
        # neither one-pixel jump spans both rows, but their measured combined
        # change does. Use this only after the established sharp/wipe edge tests
        # fail, so an already measured wipe silhouette cannot grow into court.
        # Numeral strokes still do not persist through both player rows.
        across_two = (np.abs(body[:, 2:] - body[:, :-2]).mean(axis=2) > 8).mean(axis=0)
        soft_boundaries = [x for x in range(max(2, first), last + 1)
                           if across_two[x - 2] >= .55]
        if soft_boundaries:
            return soft_boundaries[-1]
        raise RuntimeError("WTA board present but native right boundary cannot be measured")
    # 没有薄荷绿（开局还没有局分那几秒）：没有签名色撑着，
    # 越过 spec 右缘的读数不可信，照旧封顶
    return min(edge, cap) if cap is not None else edge


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _runs(flags: np.ndarray) -> list[tuple[int, int]]:
    values = np.flatnonzero(flags)
    if not values.size:
        return []
    cuts = np.flatnonzero(np.diff(values) > 1) + 1
    return [(int(v[0]), int(v[-1]) + 1) for v in np.split(values, cuts)]


def frame_geometry(band: np.ndarray, cap: int | None = None) -> dict | None:
    """Measure native body and optional narrow header; coordinates stay source-relative.

    The search rectangle is never itself an opaque graphic. A positive board signature
    with unmeasurable body geometry is an error, rather than a rectangular fallback.
    """
    if band.ndim != 3 or band.shape[1] < MIN_BOARD_W:
        return None
    mint = mint_mask(band)
    colour = board_colour(band)
    anchor_cols = np.flatnonzero((mint.mean(axis=0) > .25)
                                & (np.arange(band.shape[1]) >= MIN_BOARD_W))
    anchors = _runs(mint[:, anchor_cols].sum(axis=1) >= 2)
    if anchor_cols.size < MINT_COLS:
        anchors = []
    # Text cuts holes through the mint column; join <= 3px gaps, without joining
    # an independent small header at the left of the body.
    merged = []
    for lo, hi in anchors:
        if merged and lo - merged[-1][1] <= 3:
            merged[-1] = (merged[-1][0], hi)
        else:
            merged.append((lo, hi))
    candidates = [(lo, hi) for lo, hi in merged if hi - lo >= 24]
    if candidates:
        lo, hi = max(candidates, key=lambda v: v[1] - v[0])
        # Native antialiased/rounded edge can precede/follow the solid mint column.
        broad = colour[:, :max(MIN_BOARD_W, cap or MIN_BOARD_W)].sum(axis=1) >= MIN_BOARD_W
        for _ in range(3):
            if lo > 0 and broad[lo - 1]:
                lo -= 1
            if hi < len(broad) and broad[hi]:
                hi += 1
        body_band = band[lo:hi]
        edge = board_edge(body_band, cap=cap)
        if edge is None:
            return None
    else:
        # Opening graphic without a mint games cell: require the existing positive
        # name-background signature in a broad contiguous region.
        row_fraction = colour[:, 8:8 + NAME_W].mean(axis=1)
        candidates = [(lo, hi) for lo, hi in _runs(row_fraction >= .5)
                      if hi - lo >= 24 and present(band[lo:hi])]
        if not candidates:
            if present(band):
                raise RuntimeError("WTA board present but native body height cannot be measured")
            return None
        lo, hi = max(candidates, key=lambda v: v[1] - v[0])
        edge = board_edge(band[lo:hi], cap=cap)
        if edge is None:
            raise RuntimeError("WTA board present but native body width cannot be measured")
    if lo < 0 or hi > band.shape[0] or edge < MIN_BOARD_W:
        raise RuntimeError("WTA board present but native body geometry is invalid")

    rows = []
    right_limit = min(band.shape[1], edge)
    for y in range(lo, hi):
        pixels = np.flatnonzero(colour[y, :right_limit])
        outer = np.flatnonzero(((band[y, :right_limit].max(axis=1) < 130)
                                | mint[y, :right_limit]))
        if not pixels.size:
            rows.append((y, None, None))
            continue
        # Fill the graphic's interior (white text and service-ball icon included),
        # retain rounded outer edges, and allow only a 1px antialias fringe.
        left = max(0, int(outer[0] if outer.size else pixels[0]) - 1)
        right = min(right_limit, int(pixels[-1]) + 2)
        rows.append((y, left, right))
    missing = _runs(np.array([r[1] is None for r in rows]))
    if any(hi - lo > 3 for lo, hi in missing):
        raise RuntimeError("WTA board present but native body row geometry is unmeasurable")
    for first, last in missing:
        neighbours = [rows[j] for j in (first - 1, last)
                      if 0 <= j < len(rows) and rows[j][1] is not None]
        if not neighbours:
            raise RuntimeError("WTA board present but native body edge is unmeasurable")
        # A <=3px antialiased outline/separator can miss all colour thresholds.
        # Bridge only its measured adjacent row spans, never the whole search band.
        for j in range(first, last):
            rows[j] = (rows[j][0], int(np.mean([r[1] for r in neighbours])),
                       int(np.mean([r[2] for r in neighbours])))
    # Retain one pixel of native antialias at horizontal body edges.
    if lo > 0:
        rows.insert(0, (lo - 1, rows[0][1], rows[0][2]))
    if hi < band.shape[0]:
        rows.append((hi, rows[-1][1], rows[-1][2]))
    body = (min(r[1] for r in rows), rows[0][0],
            max(r[2] for r in rows), rows[-1][0] + 1)

    if body[2] - body[0] < MIN_BOARD_W or body[3] - body[1] < 48:
        if present(band):
            raise RuntimeError("WTA board present but complete two-player body geometry is unmeasurable")
        # A sliding-out remnant is not a complete board; never paste one player row.
        return None

    header_rows = []
    # Header is native mint at the LEFT, above the two-row board. It may be
    # only a clipped 10px animation in an already cropped supplied source.
    header_columns = []
    if lo:
        for first, last in _runs(mint[:lo, :right_limit].mean(axis=0) > .2):
            if header_columns and first - header_columns[-1][1] <= 4:
                header_columns[-1] = (header_columns[-1][0], last)
            else:
                header_columns.append((first, last))
    header_limit = next((last for first, last in header_columns
                         if first < MIN_BOARD_W and last - first >= 12), 0)
    for y in range(lo):
        xs = np.flatnonzero(mint[y, :header_limit])
        if xs.size >= 12:
            header_rows.append((y, max(0, int(xs[0]) - 1),
                                min(right_limit, int(xs[-1]) + 2)))
    header = None
    if header_rows:
        groups = _runs(np.isin(np.arange(lo), [r[0] for r in header_rows]))
        h0, h1 = max(groups, key=lambda v: v[1] - v[0])
        header_rows = [r for r in header_rows if h0 <= r[0] < h1]
        if h0 > 0:
            header_rows.insert(0, (h0 - 1, header_rows[0][1], header_rows[0][2]))
        # A tag's black letters are interior to its native outer mint silhouette.
        header = (min(r[1] for r in header_rows), header_rows[0][0],
                  max(r[2] for r in header_rows), header_rows[-1][0] + 1)
    all_rows = rows + header_rows
    bounds = (min(r[1] for r in all_rows), min(r[0] for r in all_rows),
              max(r[2] for r in all_rows), max(r[0] for r in all_rows) + 1)
    return {"body": body, "header": header, "bounds": bounds,
            "rows": all_rows, "edge": edge}


def scan_geometry(source: Path, box: tuple[int, int, int, int], start: float,
                  seconds: float, fps: str) -> tuple[list, int]:
    """Read the search band once and retain each frame's measured alpha geometry."""
    x0, y0, x1, y1 = box
    sw = int(subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width", "-of", "csv=p=0", str(source)], text=True).strip().split(",")[0])
    width, height = min(sw - x0, SCAN_W), y1 - y0
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{seconds:.3f}",
         "-i", str(source), "-an", "-sn",
         "-vf", f"format=rgb24,crop={width}:{height}:{x0}:{y0},fps={fps}",
         "-f", "rawvideo", "-"], capture_output=True, check=False)
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode(errors="replace"))
    raw, per = proc.stdout or b"", width * height * 3
    frames = []
    for k in range(len(raw) // per):
        band = np.frombuffer(raw[k * per:(k + 1) * per], np.uint8).reshape(height, width, 3)
        frames.append(frame_geometry(band, cap=x1 - x0))
    if not frames:
        raise RuntimeError(f"{start:.2f}s 起一帧都没解出来（解码失败，不是板不在）")
    return frames, width


def scan(source: Path, box: tuple[int, int, int, int], start: float,
         seconds: float, fps: str) -> tuple[list, int]:
    """Compatible probe API: body right edge and optional measured native header."""
    frames, width = scan_geometry(source, box, start, seconds, fps)
    return [(f["edge"], f["header"]) if f else (None, None) for f in frames], width


def alpha_frame(geometry: dict | None, bounds: tuple[int, int, int, int]) -> np.ndarray:
    """Opaque native graphic rows only; every court gap stays transparent."""
    x0, y0, x1, y1 = bounds
    mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
    if geometry:
        for y, left, right in geometry["rows"]:
            if y0 <= y < y1:
                mask[y - y0, max(0, left - x0):min(x1 - x0, right - x0)] = 255
    return mask


def write_geometry_mask(frames: list, bounds: tuple, fps: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    x0, y0, x1, y1 = bounds
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "gray",
         "-video_size", f"{x1-x0}x{y1-y0}", "-framerate", fps, "-i", "-", "-an",
         "-c:v", "ffv1", "-threads", "1", str(dest)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for geometry in frames:
            enc.stdin.write(alpha_frame(geometry, bounds).tobytes())
        enc.stdin.close()
        err = enc.stderr.read()
        if enc.wait():
            raise RuntimeError(err.decode(errors="replace"))
    finally:
        if enc.poll() is None:
            enc.kill()


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
    """Measure each frame and crop the container to the visible native graphic union.

    Body and BREAK/SET/MATCH POINT header keep the same source coordinates and
    scale. Their rectangular background gaps never become an opaque patch.
    """
    records = []
    rate = float(Fraction(fps))
    for i, seg in enumerate(segments):
        if not seg.score_inset:
            continue
        x0, y0, spec_x1, y1 = seg.score_inset
        seconds = seg.end - seg.start + tail * seg.speed
        frames, width = scan_geometry(Path(sources[seg.source]), seg.score_inset,
                                      seg.start, seconds, fps)
        # Presence debounce suppresses isolated false positives; it never expands
        # one frame to another frame's wider/taller opaque geometry.
        states = debounce([(f["edge"], None) if f else (None, None) for f in frames])
        frames = [f if state[0] is not None else None for f, state in zip(frames, states)]
        live = [f for f in frames if f]
        if not live:
            raise RuntimeError(
                f"第 {i + 1} 段（源片 {seg.start:.2f}→{seg.end:.2f}s）一帧都没认出 WTA 比分板。"
                "先核实原生图形；不退回整段矩形回贴。整段无板才写 score_inset:false ＋说明。")
        left = min(f["bounds"][0] for f in live)
        top = min(f["bounds"][1] for f in live)
        right = min(width, max(f["bounds"][2] for f in live))
        bottom = max(f["bounds"][3] for f in live)
        # Crop coordinates must be chroma-safe; extra container pixels remain alpha0.
        left -= left % 2
        top -= top % 2
        right = min(width, right + ((right - left) % 2))
        bottom = min(y1 - y0, bottom + ((bottom - top) % 2))
        bounds = (left, top, right, bottom)
        dest = Path(outdir) / "score_masks" / f"segment-{i + 1:02d}.mkv"
        write_geometry_mask(frames, bounds, fps, dest)
        seg.score_inset = (x0 + left, y0 + top, x0 + right, y0 + bottom)
        seg.score_inset_mask = str(dest.resolve())
        seg.score_inset_spans = None
        report_beyond_hint(i, x0 + right, spec_x1)
        widths = sorted({f["edge"] for f in live})
        bodies = sorted({f["body"] for f in live})
        headers = sorted({f["header"] for f in live if f["header"]})
        records.append({"segment": i, "frames": len(frames), "present_frames": len(live),
                        "tag_frames": sum(bool(f["header"]) for f in live),
                        "board_edges": [widths[0], widths[-1]], "right": right,
                        "source_bounds": list(seg.score_inset),
                        "body_bounds": [list(b) for b in bodies],
                        "header_bounds": [list(h) for h in headers],
                        "geometry_origin": [x0, y0],
                        "alpha_geometry": "native-body-and-header-rows",
                        "mask": str(dest), "mask_sha256": _sha256(dest)})
        print(f"[score-mask] 第 {i + 1} 段：板在 {len(live)}/{len(frames)} 帧，"
              f"原生有效外缘 {seg.score_inset}，body/header独立透明蒙版（{rate:g} fps）")
    proof = {"status": "pass", "profile": PROFILE, "segments": records}
    p = Path(outdir) / "scoreboard_qc.json"
    p.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
