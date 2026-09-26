"""拉沃尔杯转播比分板：逐帧蒙版回贴，三块胶囊各切各的，板不在不贴。

账号所有者 2026-09-25 做 `ruud-cerundolo-laver-cup-2026` 时：「比分板补一套适配，
彻底解决」。拉沃尔杯的转播图形不是 ATP / WTA / 比利·简·金杯那三家的任何一种，
而 `scoreboard_profile` 认不出的转播**直接报错**（不退回老的整段矩形回贴——那正是
「消失后背景还在……像狗皮膏药」「右边突然多一块补丁」的来路）。

判据量出来的（本场官方集锦 `10c-Msjex6s`，frame-grab 每 4 秒一帧、1920 宽，
`output/2026-09-25/frames/lavercup-board-match1/`，逐像素读的）。紧凑版板在左下：

    金色标签胶囊  y 884–916   (131,120,74)——「MATCH 1」「7 POINT TIEBREAK」「SET POINT #3」；
                              开局那几秒没有这块（frame 0/4/8s）
    欧洲队那一行  y 920–968   近黑底 (7,7,7)，**蓝色描边** (15,47,85)/(0,51,95)
    世界队那一行  y 970–1016  近黑底，**红色描边** (55,0,13)/(37,0,8)
    字            白 (185,183,186)＋金 (140,132,68)，发球方是行内一个金色小点
    球场          深灰 (80,73,81)——比近黑亮、比描边灰

「板在」不看颜色占比（红衣近景、欧洲队的蓝色背板都会冒出大片红／蓝像素，
frame 96/132/164s 量过），看**结构**：同一列上欧洲行的上下两条蓝边、世界行的上下
两条红边**四条都在**，而两行中间是近黑底或字。这样的列连成一段、够宽，才算板。
50 帧里板在的 44 帧全认出，172s 起没有板的 5 帧（握手近景、片尾板）一帧不误报。

⭐ **宽版全名板整块贴**（开场和赛后的「LAVER CUP | CASPER RUUD / FRANCISCO
CERUNDOLO」，frame 112/116/120/140/144/168s）。第一版是「不贴」，理由是它横跨源片
x 85–960、放大后比画布宽——**渲出来才看见那条理由站不住**：宽版板的右半截本来就落在
居中 3:4 窗口（源片 555–1365）里，不贴，画面左缘就露着一截被切掉名字的
「ERUNDOLO 6⁴ 6 10」（`ruud-cerundolo-laver-cup-2026` 第一版成片 8~11s），正是
账号所有者点过的「比分板没展示全」。所以整块面板从左下角贴回去，**把窗口里那截原样盖住**：
名字和比分列（源片 ≤ 870）放大后落在 1053 以内；只有金条最右那几个分盘用时
（源片 ~960）伸出画布右缘，认领这个代价。
认法：两行从带左缘往右 1 倍带高以外才开始（紧凑版紧贴左缘）；面板横向取金条那一段。
标定带因此是 y 862–1036（包住宽版面板上下那两道金边 866 / 1032——带再窄，窗口里
那截原样的金边会从贴片上下各漏出一线）。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np

PROFILE = "lavercup-v2"
EDGE_PAD = 2
MIN_ROWS_W = 0.83   # 两行最窄也有这么宽（×带高）
WIDE_START = 1.0    # 两行从这么远（×带高）之外才开始 → 宽版全名板
WIDE_SCAN_PX = 920  # 宽版面板横跨源片 85–960，扫描带至少要这么宽（相对带左缘）
LABEL_GAP = 40      # 金色标签里黑字把金色切断，隔这么宽以内算同一块
LEFT_REACH = 70     # 描边接到扫描带右头（失控）时，右端退回结构段外这么远
PANEL_REACH = 40    # 宽版面板：两行／金条之外，面板深色底最多再往右这么宽
PANEL_DARK = 70     # 面板深色底：一列的 max(r,g,b) 中位数低于它（球场 ~95，面板 ~45）

# 纵向分区，按带高的比例（标定带 y 862–1036，高 174；括号里是源片绝对 y）
LABEL = (0.120, 0.316)                       # 金色标签 884–916
ROW1 = (0.328, 0.615)                        # 欧洲队一行 920–968
ROW2 = (0.615, 0.891)                        # 世界队一行 970–1016
_R1_TOP, _R1_BOT = (0.328, 0.362), (0.580, 0.620)   # 蓝边 922–925 / 964–967
_R2_TOP, _R2_BOT = (0.612, 0.652), (0.856, 0.896)   # 红边 970–973 / 1012–1015
_R1_MID, _R2_MID = (0.40, 0.55), (0.67, 0.83)


def _rgb(band: np.ndarray):
    return (band[:, :, i].astype(np.int16) for i in range(3))


def _rows(h: int, span: tuple[float, float]) -> slice:
    return slice(int(round(span[0] * h)), max(int(round(span[0] * h)) + 1,
                                               int(round(span[1] * h))))


def blue_edge(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (b >= 55) & (b - r >= 40) & (g <= 90)


def red_edge(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (r >= 33) & (r - g >= 28) & (r - b >= 15)


def gold(band: np.ndarray) -> np.ndarray:
    r, g, b = _rgb(band)
    return (r > 100) & (r < 200) & (g > 90) & (r - b > 35) & (g - b > 25)


def fill(band: np.ndarray) -> np.ndarray:
    """行里面的东西：近黑底、白字、金字。"""
    r, g, b = _rgb(band)
    hi = np.maximum(np.maximum(r, g), b)
    lo = np.minimum(np.minimum(r, g), b)
    return (hi < 30) | (lo > 150) | gold(band)


def _runs(ok: np.ndarray, min_w: int, gap: int) -> list[tuple[int, int]]:
    out, x, n = [], 0, len(ok)
    while x < n:
        if ok[x]:
            s = x
            while x < n and ok[x:x + gap + 1].any():
                x += 1
            end = x
            while end > s and not ok[end - 1]:
                end -= 1
            if end - s >= min_w:
                out.append((s, end))
        x += 1
    return out


def structure(band: np.ndarray) -> np.ndarray:
    """每一列是不是「两行板」：四条描边都在，行中间是底或字。"""
    h = band.shape[0]
    bl, rd, fl = blue_edge(band), red_edge(band), fill(band)
    return (bl[_rows(h, _R1_TOP)].any(0) & bl[_rows(h, _R1_BOT)].any(0)
            & rd[_rows(h, _R2_TOP)].any(0) & rd[_rows(h, _R2_BOT)].any(0)
            & (fl[_rows(h, _R1_MID)].mean(0) > 0.6)
            & (fl[_rows(h, _R2_MID)].mean(0) > 0.6))


def _reach_right(zone: np.ndarray, e: int) -> int:
    """从结构段的右端 `e` 顺着「两行同时有描边」往右接，接到描边断开为止。

    ⭐ 账号所有者 2026-09-25：「比分板剪切有问题，双打的比较长」「同时要自适应
    不同的长度啊」。原来这里往右最多接 `LEFT_REACH`（70px）——单打板的结构段
    离右端圆头不远，70 够；双打板名字是「ALCARAZ / MENSIK」，结构段在名字后面
    就断了（比分数字那一截 `fill` 过不了 0.6），到右端圆头有 70~100px，于是
    `alcaraz-mensik` 抽帧 123s 那一帧（6 5 40 三列）量到 502、真右缘 ~508，
    右端圆头和最后半格比分被切掉。板每打完一盘长一列，同一个问题只会更重。

    所以不设固定的顶，**板多长接多长**；只有一种情况收回来：一路接到扫描带的
    右头（描边和背景连成了一片——带宽本来已经 ≥ 源片一半，真板到不了那儿），
    那不是板的右缘，退回老的 `e + LEFT_REACH`。
    """
    n = len(zone)
    right = e
    while right < n and zone[right:right + 4].any():
        right += 1
    if right >= n:
        return min(n, e + LEFT_REACH)
    return right


def _reach_left(zone: np.ndarray, s: int) -> int:
    """从结构段左端 `s` 顺着「两行同时有描边」往左接，接到描边断开为止（左圆头＋队徽）。

    原来最多接 `LEFT_REACH`；双打板结构段在名字那一截就碎了（见 pills），左端离
    结构段可以远过 70px，所以同 `_reach_right` 一样不设固定的顶——带左缘就是 spec
    的板左缘，接到 0 是正常的，不是失控。
    """
    left = s
    while left > 0 and zone[max(0, left - 4):left].any():
        left -= 1
    return left


def pills(band: np.ndarray):
    """这一帧的板：[(x0, x1, y0, y1), …]（相对带），板不在或是宽版就 None。"""
    h = band.shape[0]
    runs = _runs(structure(band), int(MIN_ROWS_W * h), 6)
    if not runs:
        return None
    s, e = runs[0]
    # 左端圆头和队徽那一截没有「四条描边都在」，往左接着找描边。⚠️ 两行**同时**
    # 有描边才算（与，不是或）：红色替补席（frame 76s）、欧洲队的蓝色背板
    # （frame 132s）会让单独一种颜色一路延到带边上，把背景抠进贴片。
    zone = (blue_edge(band)[_rows(h, ROW1)].any(0) & red_edge(band)[_rows(h, ROW2)].any(0))
    left = _reach_left(zone, s)
    # ⚠️ 判「宽版」看**两行描边从哪儿开始**（left），不看结构段从哪儿开始（s）：
    # 双打板名字长（「ALCARAZ / MENSIK」），名字那一截的行中间被白字占掉，结构段
    # 碎成几截、第一截够宽的要到 x≈187 才出现——按 s 判就把紧凑版双打板认成了宽版，
    # 整条带高抠一块矩形（`alcaraz-mensik` 抽帧 93s / 99s）。描边是连着的，不受字影响。
    if left > WIDE_START * h:
        return wide_panel(band, e)
    # 右端圆头同理——但**不设 LEFT_REACH 那道 70px 的顶**：两行的「四条描边都在」
    # 在比分数字那一截常常断开（字把行中间的底色占掉，`fill` 过不了 0.6），于是
    # 结构段在名字后面就停了，真正的右端要靠描边一路接过去。
    right = _reach_right(zone, e)
    y1a, y1b = _rows(h, ROW1).start, _rows(h, ROW1).stop
    y2a, y2b = _rows(h, ROW2).start, _rows(h, ROW2).stop
    out = [(left, right, y1a, y1b), (left, right, y2a, y2b)]
    g = gold(band)[_rows(h, LABEL)].mean(0) > 0.5
    lab = [r for r in _runs(g, 30, LABEL_GAP) if abs(r[0] - left) <= LABEL_GAP]
    if lab:
        ly = _rows(h, LABEL)
        out.append((max(0, lab[0][0] - 3), min(band.shape[1], lab[0][1] + 3), ly.start, ly.stop))
    return out


def wide_panel(band: np.ndarray, rows_end: int):
    """宽版全名板：一整块面板 (x0, x1, 0, 带高)——横向取金条那一段，纵向整条带。"""
    h, w = band.shape[:2]
    g = gold(band)[_rows(h, LABEL)].mean(0) > 0.5
    runs = _runs(g, 60, LABEL_GAP)
    if not runs:
        return None
    x0 = max(0, runs[0][0] - 20)                 # 面板外框在金条左端再往左一点
    # 两行的右端也按描边接到底（结构段在比分数字前就断，见 pills）——赛后的宽版板
    # 两行比金条还长，只按金条和结构段取会把最右那格比分和面板外框切掉。
    zone = (blue_edge(band)[_rows(h, ROW1)].any(0) & red_edge(band)[_rows(h, ROW2)].any(0))
    x1 = max(runs[-1][1], _reach_right(zone, rows_end))
    # 面板本身是一块半透明深色底，右边框在金条／两行之外还有十几像素（`alcaraz-mensik`
    # 抽帧 135s：两行止于 675、面板止于 ~686，球场亮度 ~95、面板底 ~45）。顺着深色底
    # 再往右接，最多 PANEL_REACH；原来固定 +12，会把面板右框切掉一截。
    dark = np.median(band.max(axis=2), axis=0) < PANEL_DARK
    edge = x1
    while edge < min(w, x1 + PANEL_REACH) and dark[edge:edge + 3].any():
        edge += 1
    x1 = min(w, max(x1 + 12, edge + 2))
    return [(x0, x1, 0, h)]


def stabilize(frames: list) -> list:
    """板要前后三帧里至少两帧在才认；每块胶囊的宽取前后一帧的并集（长出来那一帧不切掉）。"""
    out = []
    for i, cur in enumerate(frames):
        near = frames[max(0, i - 1):i + 2]
        if cur is None or sum(f is not None for f in near) < 2:
            out.append(None)
            continue
        merged = []
        for k, (x0, x1, y0, y1) in enumerate(cur):
            xs0, xs1 = [x0], [x1]
            for f in near:
                if f is not None and k < len(f) and f[k][2] == y0:
                    xs0.append(f[k][0])
                    xs1.append(f[k][1])
            merged.append((min(xs0), max(xs1), y0, y1))
        out.append(merged)
    return out


def paint(mask: np.ndarray, pill: tuple[int, int, int, int]) -> None:
    """一块胶囊：两端半圆，中间矩形——四角外的球场不抠进来。"""
    x0, x1, y0, y1 = pill
    if y0 == 0 and y1 == mask.shape[0]:          # 宽版面板：直角矩形
        mask[:, x0:x1] = 255
        return
    r = (y1 - y0) / 2.0
    cy = y0 + r - 0.5
    ys, xs = np.ogrid[y0:y1, x0:x1]
    cx = np.clip(xs, x0 + r - 0.5, x1 - r - 0.5)
    inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= r * r
    mask[y0:y1, x0:x1][inside] = 255


def write_mask(frames: list, width: int, height: int, fps: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "gray",
         "-video_size", f"{width}x{height}", "-framerate", fps, "-i", "-", "-an",
         "-c:v", "ffv1", "-threads", "1", str(dest)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    m = np.zeros((height, width), np.uint8)
    try:
        for f in frames:
            m.fill(0)
            for x0, x1, y0, y1 in f or ():
                paint(m, (x0, min(width, x1 + EDGE_PAD), y0, y1))
            enc.stdin.write(m.tobytes())
        enc.stdin.close()
        err = enc.stderr.read()
        if enc.wait():
            raise RuntimeError(err.decode(errors="replace"))
    finally:
        if enc.poll() is None:
            enc.kill()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def scan(source: Path, box: tuple[int, int, int, int], start: float,
         seconds: float, fps: str) -> tuple[list, int]:
    """逐帧量 → [胶囊列表 or None]，以及扫的带宽。"""
    x0, y0, x1, y1 = box
    sw = int(subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width", "-of", "csv=p=0", str(source)], text=True).strip().split(",")[0])
    # spec 的 x1 只是提示，不是上限：带至少扫到源片一半宽（双打板、赛后宽版板都比
    # 单打 spec 的 x1 长），板多长由 pills 自己量
    width = min(sw - x0, max(int((x1 - x0) * 1.3), WIDE_SCAN_PX, sw // 2 - x0))
    height = y1 - y0
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{seconds:.3f}",
         "-i", str(source), "-an", "-sn",
         "-vf", f"format=rgb24,crop={width}:{height}:{x0}:{y0},fps={fps}",
         "-f", "rawvideo", "-"], capture_output=True, check=False)
    raw = proc.stdout or b""
    per = width * height * 3
    frames = [pills(np.frombuffer(raw[k * per:(k + 1) * per], np.uint8).reshape(height, width, 3))
              for k in range(len(raw) // per)]
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
    if scanned and not any(f is not None for _i, _s, fr, _w in scanned for f in fr):
        raise RuntimeError(
            f"{len(scanned)} 段一帧都没认出拉沃尔杯的比分板（{PROFILE}：蓝边一行＋红边一行）"
            "——这场转播的图形和标定的那一版不一样，或者 scorebox 框错了位置。先抽一帧量颜色、"
            "补标定，别退回整段一个矩形的老回贴。")
    records = []
    for i, seg, frames, width in scanned:
        x0, y0, spec_x1, y1 = seg.score_inset
        live = [f for f in frames if f is not None]
        if not live:
            raise RuntimeError(
                f"第 {i + 1} 段（源片 {seg.start:.2f}→{seg.end:.2f}s）一帧都没认出比分板。"
                "整段都是近景/看台的话写 \"score_inset\": false ＋ \"_score_inset_why\"。")
        right = max(p[1] for f in live for p in f) + EDGE_PAD
        right = min(width, right + right % 2)
        dest = Path(outdir) / "score_masks" / f"segment-{i + 1:02d}.mkv"
        write_mask(frames, right, y1 - y0, fps, dest)
        seg.score_inset = (x0, y0, x0 + right, y1)
        seg.score_inset_mask = str(dest.resolve())
        seg.score_inset_spans = None
        if x0 + right > spec_x1:
            print(f"[score-mask] 第 {i + 1} 段：板量到 {x0 + right}，比 spec scorebox 右缘 "
                  f"{spec_x1} 宽 {x0 + right - spec_x1}px（双打／多一盘的板更长）——按量到的贴，"
                  "spec 的 x1 只是提示，不是上限")
        ws = sorted({max(p[1] for p in f) for f in live})
        n_label = sum(1 for f in live if len(f) > 2)
        records.append({"segment": i, "frames": len(frames), "present_frames": len(live),
                        "label_frames": n_label, "board_edges": [ws[0], ws[-1]], "right": right,
                        "mask": str(dest), "mask_sha256": _sha256(dest)})
        print(f"[score-mask] 第 {i + 1} 段：板在 {len(live)}/{len(frames)} 帧，"
              f"板宽逐帧 {ws[0]}~{ws[-1]}px，带标签 {n_label} 帧，贴片最宽 {right}px"
              f"（{rate:g} fps 逐帧蒙版，{PROFILE}）")
    proof = {"status": "pass", "profile": PROFILE, "segments": records}
    p = Path(outdir) / "scoreboard_qc.json"
    p.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
