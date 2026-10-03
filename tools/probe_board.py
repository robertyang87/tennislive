"""probe 那一趟把转播比分板逐帧量一遍，存进 `probe.json` 的 `board`；`--dry-run` 拿它预判回贴。

来路（2026-09-27 全库返工盘点，「加速加速」那一轮）：比分板回贴是「赛场之上」
**头号返工来源**——22 次返工、11 趟 render 红在蒙版那一步（51.5 runner-分钟），
而**每一次都是渲完把成片拉回来、或者抽帧才发现的**：

| 形状 | 例子 |
|---|---|
| 开着 `score_inset` 的段里一帧板都没有 → render 在 `resolve_masks` 红 | `prozorova-eala` 第 13 段（run 36020126044）、`alcaraz-mensik-doubles` 第 9 段（run 36197683115）、`wong-paul` 盘间那段（843526ae，老路贴出一块球场） |
| 写着 `false`，而板还在画面里 → 居中窗口露出半截板 | `osaka-mertens` 第 ② 段（64f8dbaf：179.5→180.38 那 0.88 秒名字被裁掉只剩盘分） |
| 美网带式量不出几何 / 板比 spec 的框宽 → render 红 | `rybakina-sabalenka`（8a523097）等 8 趟美网 run |

判「这一段有没有板」要**解源片**，而 `--dry-run` 只读 spec 和 probe.json——所以这件事
一直只能在 render 里（源片下完 3 分钟之后）才知道。可 probe 那一趟**源片本来就在手上**：
这里趁它在，拿 render 用的**同一套逐帧判据**（`atp_scoreboard` / `wta_scoreboard` /
`itf_scoreboard` / `lavercup_scoreboard` / `scoreboard_geometry`，**一个颜色阈值都不抄**）
按 `PROBE_FPS` 扫一遍，把每一帧「板在不在、右缘在哪」落进 probe.json。dry-run 拿 spec
自己的窗口去对，0.2 秒就知道 render 会不会红。

⚠️ **框要对得上才算数**：判据是按带（scorebox 的 y0~y1）标定的，拿别的框量出来的数
不能拿来判这条 spec。所以 probe 同时扫两类框——
**① 每一家标定过的转播在 spec 里实际用的那条带**（`CALIBRATED`，全库 spec 量出来的，
同一家转播的带几乎一律相同）、**② 这一趟给的 `--scorebox` 或猜到的框**；dry-run 只认
和 spec 的 `scorebox` 对得上（±`BOX_TOL_X`/`BOX_TOL_Y`）的那一份，对不上就说一声、这一层不判。
`--scorebox` 常常没人给（2026-09-19 量过：478 份 probe 里只有 53 份有 `point_ends`），
所以 ① 那一档不能省。
"""
from __future__ import annotations

from pathlib import Path

#: 扫板的帧率。render 按源片帧率逐帧量；这里 5 fps（每 0.2 秒一格）够判「这一段有没有板、
#: 连着在了多久」，而且**成本在解码不在判据**：五家判据合计每帧约 6.5 ms（本地量的），
#: 500 秒的源片 2500 帧 ≈ 16 秒，解码那一遍本来就要把每一帧解出来。
PROBE_FPS = 5

#: 每一家标定过的转播，spec 里实际用的 scorebox（源片 1920×1080 像素）。**不是拍的**：
#: 全库 spec 按 `reel_facts.broadcast_profile` 分组量出来（2026-09-27）——ATP 9/9、
#: WTA 6/6、比利·简·金杯 6/6 条的 x0/y0/y1 一律相同；拉沃尔杯单打 6 条一种、双打 2 条
#: 另一种（板更高，y1 1040）；美网带式 56 条里 55 条落在容差内（887/888、978/980 两种
#: 写法），只有 `swiatek-bouzkova` 把黄色表头也框进来（y0 863）——那种就靠这一趟给的
#: `--scorebox` 另扫一份。x1 是「这场最宽那一档」，各条不同，这里只当扫描宽度的提示。
#: 判据 `test_标定框和全库spec用的框对得上`：哪天某家转播换了框，那条测试先红。
CALIBRATED = {
    "atp": ((98, 920, 519, 1029),),
    "wta": ((90, 870, 550, 980),),
    "itf-bjk": ((145, 915, 600, 1012),),
    "lavercup": ((80, 862, 520, 1036), (80, 862, 920, 1040)),
    "us-open": ((104, 888, 660, 978),),
}
CALIBRATED_SOURCE = (1920, 1080)
BOX_TOL_X = 4
BOX_TOL_Y = 2

#: 写着不贴、而板**连着**在画面里这么久，就是「板在、观众看不到」。和
#: `build_match_reel.BOARD_SPAN_MIN` 同一个数（「短于这个的在场片段不值得贴（一闪而过）」），
#: 判据钉着两者相等。⚠️ 为什么不用 0.3 秒：赛点落地那一刀起的冷开场，板在头半秒淡出
#: 是常态（`chwalinska-mertens` 第 1 段「270.5 只剩板的残影在淡出」），那几帧 render
#: 自己也不认为值得贴；`osaka-mertens` 那次是 0.88 秒，落在线上。
ON_SCREEN_MIN_S = 0.8

#: 板在、右缘却量不出来（深色背景把板连成一片）的帧占多少就提醒：这些帧 render 只能按
#: spec 的 x1 兜底（ATP/WTA/金杯），美网带式则会直接报「量不出几何」。
UNRESOLVED_WARN = 0.3

#: 美网带式的判据（`scoreboard_geometry`）按 spec 的框 +100 列扫、右缘 +4 像素余量，
#: 量到的板比框宽就当场报「Verified graphic exceeds source box」。
US_OPEN_EDGE_PAD = 4
#: 标定过「x1 只是提示」的三家：有签名色撑着的帧越过 x1 照量到的贴，没有签名色的帧按 x1 截。
HINT_PROFILES = ("atp", "wta", "itf-bjk")
#: 右缘比 x1 宽多少才提（源片像素）：现量对真值本来抖 ±5（`build_match_reel._BOARD_MONO_TOL`）。
EDGE_TOL = 8


# --------------------------------------------------------------------------
# 逐帧量（probe 那一趟，要源片）
# --------------------------------------------------------------------------

def _modules():
    """render 用的那五套判据。**懒加载**：dry-run 那条路不需要 numpy。"""
    import atp_scoreboard  # noqa: PLC0415
    import itf_scoreboard  # noqa: PLC0415
    import lavercup_scoreboard  # noqa: PLC0415
    import scoreboard_geometry  # noqa: PLC0415
    import wta_scoreboard  # noqa: PLC0415
    return {"atp": atp_scoreboard, "wta": wta_scoreboard, "itf-bjk": itf_scoreboard,
            "lavercup": lavercup_scoreboard, "us-open": scoreboard_geometry}


def band_width(profile: str, box: tuple[int, int, int, int], source_w: int) -> int:
    """这一家判据在 render 里扫多宽（相对板左缘）——照各自 `scan()` 的算法，常量从模块里读。

    美网带式例外：render 只扫 `x1 - x0 + 100`，这里放宽到 ATP 那么宽，为的是**量出真右缘**
    ——板要是比框宽，render 会报错，dry-run 要能先看见那个数。
    """
    mods = _modules()
    x0, _y0, x1, _y1 = box
    room = source_w - x0
    if profile == "wta":
        return min(room, mods["wta"].SCAN_W)
    if profile in ("atp", "us-open"):
        return min(room, mods["atp"].SCAN_W)
    if profile == "itf-bjk":
        return min(room, max(int((x1 - x0) * mods["itf-bjk"].HINT_SLACK), source_w // 2 - x0))
    if profile == "lavercup":
        return min(room, max(int((x1 - x0) * 1.3), mods["lavercup"].WIDE_SCAN_PX,
                             source_w // 2 - x0))
    raise ValueError(profile)


def measure(profile: str, band) -> tuple[int, int | None] | None:
    """一帧、一家判据 → `None`（板不在）或 `(raw, anchored)`（相对带左缘的列号）。

    - `raw`：判据**不封顶**量到的右缘；`-1` ＝ 板在、右缘量不出（和深色背景连成一片）
    - `anchored`：有签名色（ATP 盘分蓝／WTA 薄荷绿／金杯浅青）撑着的右缘，`None` ＝ 没撑着

    render 拿 spec 的右缘 `c` 当提示时，这一帧贴多宽由这两个数决定：没撑着就按
    `min(raw, c)` 截，撑着就越过 `c` 贴到 `anchored`（`atp_scoreboard.beyond_hint`）。
    这里**不重写任何判据**：`board_edge(cap=None)` 给 raw，`board_edge(cap=1)` 给
    anchored（`beyond_hint` 在提示为 1 时退回签名色那一刀，没签名色就是 1）。
    """
    w = int(band.shape[1])
    mod = _modules()[profile]
    if profile == "lavercup":
        pills = mod.pills(band)
        if not pills:
            return None
        right = max(int(p[1]) for p in pills)
        return (-1, None) if right >= w else (right, right)
    if profile == "us-open":
        edge = mod.right_edge(band)
        if edge is None:
            return None
        return (-1, None) if edge < 0 else (int(edge), int(edge))
    raw = mod.board_edge(band, cap=None)
    if raw is None:
        return None
    hint = mod.board_edge(band, cap=1)
    anchored = None if hint is None or hint <= 1 else int(hint)
    if raw >= w and anchored is None:
        return (-1, None)
    return (int(raw), anchored)


def _rle(frames: list) -> list:
    out: list[list] = []
    for f in frames:
        raw, anc = (None, None) if f is None else f
        if out and out[-1][1] == raw and out[-1][2] == anc:
            out[-1][0] += 1
        else:
            out.append([1, raw, anc])
    return out


def frames_of(entry: dict, profile: str) -> list | None:
    """probe.json 里一份扫描 → 这一家判据的逐帧 `[None | (raw_abs, anchored_abs)]`。没扫这家 → None。"""
    prof = (entry.get("profiles") or {}).get(profile)
    if prof is None:
        return None
    if not prof.get("present"):
        return [None] * int(entry.get("frames") or 0)
    out: list = []
    for n, raw, anc in prof.get("runs") or []:
        out.extend([None if raw is None else (int(raw), None if anc is None else int(anc))] * int(n))
    return out


def plan_boxes(given: tuple[int, int, int, int] | None,
               source_size: tuple[int, int]) -> list[tuple[tuple[str, ...], tuple[int, int, int, int]]]:
    """要扫哪些框、每个框跑哪几家判据。

    源片是 1920×1080 时，每家标定过的转播各扫**自己那条带**（只跑自己那家判据）；这一趟给的
    或猜的框要是和它们都对不上，再单独扫一份、五家判据都跑（不知道是哪家转播）。
    """
    plan: list[tuple[tuple[str, ...], tuple[int, int, int, int]]] = []
    if tuple(source_size) == CALIBRATED_SOURCE:
        plan.extend(((name,), box) for name, boxes in CALIBRATED.items() for box in boxes)
    if given and not any(same_box(given, box) for _p, box in plan):
        plan.append((tuple(CALIBRATED), tuple(int(v) for v in given)))
    return plan


def same_box(a, b) -> bool:
    """两个框判的是不是同一条带：x0 ±BOX_TOL_X，y0/y1 ±BOX_TOL_Y（x1 只是提示，不比）。"""
    return (abs(int(a[0]) - int(b[0])) <= BOX_TOL_X and abs(int(a[1]) - int(b[1])) <= BOX_TOL_Y
            and abs(int(a[3]) - int(b[3])) <= BOX_TOL_Y)


def scan_frames(frames, plan, source_w: int, origin: tuple[int, int]) -> list[dict]:
    """逐帧（已经裁好的 RGB 大带，左上角在源片 `origin`）跑判据 → probe.json 的 `scans`。

    拆成纯函数是为了**不解源片也能测**：测试直接喂合成的 numpy 帧。
    """
    ox, oy = origin
    per: list[dict[str, list]] = [{p: [] for p in profiles} for profiles, _box in plan]
    widths = [{p: band_width(p, box, source_w) for p in profiles} for profiles, box in plan]
    n = 0
    for frame in frames:
        n += 1
        for k, (profiles, box) in enumerate(plan):
            x0, y0, _x1, y1 = box
            for p in profiles:
                band = frame[y0 - oy:y1 - oy, x0 - ox:x0 - ox + widths[k][p]]
                got = measure(p, band)
                per[k][p].append(None if got is None else (
                    -1 if got[0] < 0 else x0 + got[0],
                    None if got[1] is None else x0 + got[1]))
    scans = []
    for k, (profiles, box) in enumerate(plan):
        entry = {"box": list(box), "frames": n, "profiles": {}}
        for p in profiles:
            seen = per[k][p]
            present = sum(1 for f in seen if f is not None)
            record = {"present": present,
                      "unresolved": sum(1 for f in seen if f is not None and f[0] < 0)}
            if present:
                record["runs"] = _rle(seen)
            entry["profiles"][p] = record
        scans.append(entry)
    return scans


def _decode(source: Path, crop: tuple[int, int, int, int], start: float,
            stop: float | None, fps: int):
    """流式解出裁好的 RGB 帧（一帧一个 numpy 数组）——不整段读进内存：500 秒 × 5 fps 的
    大带合起来上百 MB。"""
    import subprocess  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    x, y, w, h = crop
    cmd = ["ffmpeg", "-v", "error"]
    if start:
        cmd += ["-ss", f"{start:.3f}"]
    if stop is not None:
        cmd += ["-t", f"{max(0.05, stop - start):.3f}"]
    # ⚠️ `fps` 排在最前：先降到 5 fps 再转 RGB，别让每一帧源片都先转一遍色彩空间。
    # 复查实测（60 s 1080p30）：18.7 s → 9.3 s，输出逐字节相同（md5 一致）。
    cmd += ["-i", str(source), "-an", "-sn",
            "-vf", f"fps={fps},format=rgb24,crop={w}:{h}:{x}:{y}", "-f", "rawvideo", "-"]
    # stderr 落临时文件，不走 PIPE：边读 stdout 边不排 stderr，解码报错一多就把
    # 64 KB 管道塞满、两头互等，probe 整趟卡死（复查指出的死锁）。
    import tempfile  # noqa: PLC0415
    errf = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=errf)
    per = w * h * 3
    try:
        while True:
            raw = proc.stdout.read(per)
            if len(raw) < per:
                break
            yield np.frombuffer(raw, np.uint8).reshape(h, w, 3)
    finally:
        proc.stdout.close()
        rc = proc.wait()
        errf.seek(0)
        err = errf.read().decode("utf-8", "replace")
        errf.close()
        if rc and err.strip():
            raise RuntimeError(f"ffmpeg 解板失败：{err.strip()[-300:]}")


def scan_plan(source: Path, plan: list, source_w: int, *, start: float = 0.0,
              stop: float | None = None, fps: int = PROBE_FPS) -> list[dict]:
    """按 `plan` 解源片、逐帧跑判据 → probe.json 的 `scans`（顺序和 plan 一致）。

    所有框合成**一条**大带解一遍（标定过的那几条带都挤在源片左下 y 862~1040 之间）；
    给的框离得太远（比如猜到了右上角）就单独再解一遍，别为了它把大带撑成半幅画面。
    """
    sw = source_w
    groups: list[list[int]] = []
    for k, (_p, box) in sorted(enumerate(plan), key=lambda it: it[1][1][1]):
        if groups:
            lo = min(plan[j][1][1] for j in groups[-1])
            if box[3] - lo <= 320:
                groups[-1].append(k)
                continue
        groups.append([k])
    scans: list[dict | None] = [None] * len(plan)
    for group in groups:
        sub = [plan[k] for k in group]
        ox = min(box[0] for _p, box in sub)
        oy = min(box[1] for _p, box in sub)
        right = max(box[0] + band_width(p, box, sw) for ps, box in sub for p in ps)
        bottom = max(box[3] for _p, box in sub)
        got = scan_frames(_decode(source, (ox, oy, right - ox, bottom - oy), start, stop, fps),
                          sub, sw, (ox, oy))
        for k, entry in zip(group, got):
            scans[k] = entry
    return scans


def _parse_box(given: str) -> tuple[int, int, int, int] | None:
    try:
        box = tuple(int(float(v)) for v in str(given or "").split(","))
    except ValueError:
        return None
    return box if len(box) == 4 else None


class BoardScan:
    """probe 模式的入口：源片一下完就在**后台线程**里开扫标定过的那几条带，写 probe.json
    之前 `finish()` 收——这一趟给的或猜到的框要是和标定带都对不上，那时再补扫一份。

    ⚠️ **为什么要并行**：量板要把源片整条解一遍，本地量 60 秒的 1080p 源片 10.3 秒
    （光解码 5.8 秒），500 秒的 WTA 集锦串行加上去就是一分多钟——每一趟 probe 都付。
    而 probe 本来最慢的是缩略图墙那几百次单帧 seek（单线程为主），两者叠在一起跑，
    多出来的墙钟时间接近于零。「时效第一」管的正是这种顺序和并行。

    ⚠️ **永远不让 probe 失败**：量板只是给 dry-run 的线索；可失败要出声、要落进
    probe.json（`error`），dry-run 会说「这一层没查」，别让「没量成」和「量了没板」长一样。
    """

    def __init__(self, source: Path, source_size: tuple[int, int],
                 start: float = 0.0, stop: float | None = None, fps: int = PROBE_FPS):
        import threading  # noqa: PLC0415

        self.source, self.size = Path(source), tuple(source_size)
        self.start, self.stop, self.fps = float(start or 0.0), stop, fps
        self._plan = plan_boxes(None, self.size)
        self._scans: list[dict] = []
        self._error: Exception | None = None
        self._thread = threading.Thread(target=self._run, name="probe-board", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._scans = self._scan(self._plan)
        except Exception as exc:  # noqa: BLE001 - 收的时候报
            self._error = exc

    def _scan(self, plan: list) -> list[dict]:
        if not plan:
            return []
        return scan_plan(self.source, plan, self.size[0], start=self.start,
                         stop=self.stop, fps=self.fps)

    def finish(self, given: str) -> dict:
        """`given` 是 `--scorebox` 或者猜到的框（"x0,y0,x1,y1"，可以是空串）。"""
        self._thread.join()
        extra = [p for p in plan_boxes(_parse_box(given), self.size) if p not in self._plan]
        try:
            if self._error is not None:
                raise self._error
            scans = self._scans + self._scan(extra)
        except Exception as exc:  # noqa: BLE001 - 量板只是给 dry-run 的线索，不能把 probe 带崩
            print(f"[量板] ⚠️ 这一趟没量成（{exc}）——dry-run 的回贴那一层会说「没查」")
            return {"version": 1, "error": str(exc)[:400]}
        if not scans:
            why = "源片不是 1920×1080、这一趟也没给 --scorebox、也没猜到框"
            print(f"[量板] 跳过：{why}")
            return {"version": 1, "skipped": why}
        for entry in scans:
            hits = {p: r["present"] for p, r in entry["profiles"].items() if r["present"]}
            shown = "、".join(f"{p} {n}/{entry['frames']} 帧" for p, n in hits.items()) or "一帧都没认出板"
            print(f"[量板] 框 {entry['box']}：{shown}")
        return {"version": 1, "fps": self.fps, "t0": round(self.start, 3),
                "frames": min(e["frames"] for e in scans), "scans": scans}


# --------------------------------------------------------------------------
# dry-run（只读 probe.json）
# --------------------------------------------------------------------------

def legacy_board_on_screen() -> frozenset:
    """「板在画面里却写着不贴」那道闸（2026-09-27）之前已经写好的 spec，只许减不许加。"""
    import json  # noqa: PLC0415
    path = Path(__file__).resolve().parents[1] / "data" / "legacy_board_on_screen.json"
    try:
        return frozenset(json.loads(path.read_text(encoding="utf-8")).get("reels") or ())
    except FileNotFoundError:
        return frozenset()


def legacy_board_unprobed() -> dict[str, list[str]]:
    """「开着回贴、probe 却没量板」那道闸（2026-09-28）之前已经写好的手写 spec：
    `slug → [源键]`，只许减不许加（自检 `tests/test_small_gates.py`）。"""
    import json  # noqa: PLC0415
    path = Path(__file__).resolve().parents[1] / "data" / "legacy_board_unprobed.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {str(k): [str(x) for x in v] for k, v in (data.get("reels") or {}).items()}


def scoreboxes_by_url(spec: dict, urls: dict) -> dict[str, list]:
    """回贴实际取到的源 → 该源使用的框；段级框覆盖顶层默认，不借别的源的扫描。"""
    if not urls:
        return {}
    primary = str(spec.get("primary") or next(iter(urls)))
    owned: dict[str, list] = {}
    for raw in spec.get("segments") or []:
        if not isinstance(raw, dict) or not raw.get("score_inset") or raw.get("image"):
            continue
        url = urls.get(str(raw.get("source") or primary))
        box = raw.get("scorebox", spec.get("scorebox"))
        if url and isinstance(box, (list, tuple)) and len(box) == 4:
            boxes = owned.setdefault(url, [])
            if list(box) not in boxes:
                boxes.append(list(box))
    # 原来的带式记录：没有段开回贴时，顶层框仍归主源。
    if not owned and isinstance(spec.get("scorebox"), (list, tuple)):
        url = urls.get(primary)
        if url:
            owned[url] = [list(spec["scorebox"])]
    return owned


def reprobe_command(spec: dict, source_key: str, url: str, probe: dict | None) -> str:
    """重跑一趟 probe 的那一行命令（带上老 probe 的区间和 spec 的 scorebox）。"""
    slug = str(spec.get("slug") or "<slug>")
    parts = [f"gh workflow run match-reel.yml --ref <分支> -f mode=probe -f slug={slug}",
             f"-f url={url}"]
    for key, flag in (("clip_from", "clip_from"), ("clip_to", "clip_to")):
        value = (probe or {}).get(key)
        if value not in (None, ""):
            parts.append(f"-f {flag}={value}")
    urls = spec.get("sources") or {source_key: url}
    owned = scoreboxes_by_url(spec, urls).get(url) or []
    box = owned[0] if len(owned) == 1 else None
    if isinstance(box, (list, tuple)) and len(box) == 4:
        parts.append("-f scorebox=" + ",".join(str(int(v)) for v in box))
    return " ".join(parts)


def _pick_scan(board: dict, spec_box, profile: str) -> tuple[dict | None, str]:
    """probe 里和 spec 的 scorebox 对得上、而且跑过这家判据的那一份扫描。"""
    boxes = []
    for entry in board.get("scans") or []:
        if entry and same_box(entry.get("box") or (0, 0, 0, 0), spec_box):
            if profile in (entry.get("profiles") or {}):
                return entry, ""
            boxes.append(entry.get("box"))
    scanned = [e.get("box") for e in board.get("scans") or [] if e]
    if boxes:
        return None, f"框对得上，但这份 probe 没按「{profile}」的判据量过"
    return None, (f"probe 量板用的框 {scanned} 和 spec 的 scorebox {list(spec_box)} 都对不上"
                  f"（x0 容差 ±{BOX_TOL_X}、y0/y1 ±{BOX_TOL_Y}）")


def _longest_run(flags: list[bool]) -> int:
    best = cur = 0
    for on in flags:
        cur = cur + 1 if on else 0
        best = max(best, cur)
    return best


def board_findings(spec: dict, segments, probes: dict, urls: dict, *,
                   profile: str | None, tail: float) -> tuple[list[str], list[str]]:
    """回贴那一层的 dry-run 判定，返回 `(硬, 软)`。probe_dry_run 的第 ⑧ 条。

    | 判什么 | 硬不硬 |
    |---|---|
    | 开着 `score_inset` 的段，probe 在它的窗口里**一帧板都没认出** | **硬**——render 的 `resolve_masks` 会红（五家判据都是「一帧都没认出」就 raise）；板只闪了不到一格（0.2 秒）的漏得掉，那种段贴出去也只是一闪 |
    | 美网带式：这一段板在、右缘**一帧都量不出** | **硬**——`scoreboard_geometry.stabilize` 必报「no stable geometry」 |
    | 美网带式：量到的板比这一段的框（x1 / x2）宽 | **硬**——render 报「Verified graphic exceeds source box」 |
    | 写着不贴（`false`/没写），板却**连着 ≥ `ON_SCREEN_MIN_S` 秒**在画面里 | 手写的新 spec **硬**；`_board_on_screen_why` 认领、豁免表里的老 spec、自动产的 spec 只报 |
    | 板在、右缘量不出来的帧超过 `UNRESOLVED_WARN` | 只报（ATP/WTA/金杯这些帧按 x1 兜底） |
    | x1 比这一段有签名色撑着的右缘窄，而这一段有没撑着的帧 | 只报（那几帧会按 x1 截掉最右一列） |

    ⚠️ **只在数据对得上时判**：probe 没量板（老 probe）、框对不上、窗口落在扫描范围外，
    一律只报「这一层没查」，别让「没查」和「查过没问题」长得一样。
    ⚠️ **只报不拦的那几条不做硬**：「右缘量不出」在近景深色背景上是常态，render 有兜底；
    拿它做硬闸会天天红（`crosses_cut` 那次的老账）。
    """
    hard: list[str] = []
    soft: list[str] = []
    if profile in (None, "band-legacy"):
        return hard, soft
    slug = str(spec.get("slug") or "")
    auto = (spec.get("_production") or {}).get("status") == "ready_for_render"
    strict_off = not auto and slug not in legacy_board_on_screen()
    unprobed_legacy = set(legacy_board_unprobed().get(slug, ())) if not auto else set()
    raw_segments = spec.get("segments") or []
    told: set[str] = set()
    # 开着回贴、而 probe 早于逐帧量板（没有 `board` 这一栏）的段：按源收拢，循环后一起报
    unprobed_on: dict[str, list[int]] = {}
    for index, seg in enumerate(segments):
        if seg.image:
            continue
        raw = raw_segments[index] if index < len(raw_segments) else {}
        box = raw.get("scorebox", spec.get("scorebox"))
        if not (isinstance(box, (list, tuple)) and len(box) == 4):
            continue
        on = bool(seg.score_inset)
        label = seg.source or "(主源)"
        probe = probes.get(urls.get(seg.source, ""))
        if probe is None:
            continue
        board = probe.get("board")
        if not board and on:
            unprobed_on.setdefault(seg.source, []).append(index + 1)
            continue
        if not board or board.get("error") or board.get("skipped"):
            if label not in told:
                told.add(label)
                why = ((board or {}).get("error") or (board or {}).get("skipped")
                       or "这份 probe 早于逐帧量板（probe_board，2026-09-27）")
                soft.append(f"  源 {label}：回贴这一层没查——{why}；重跑一趟 probe 就有数")
            continue
        entry, why = _pick_scan(board, box, profile)
        if entry is None:
            if label not in told:
                told.add(label)
                soft.append(f"  源 {label}：回贴这一层没查——{why}")
            continue
        frames = frames_of(entry, profile) or []
        fps = float(board.get("fps") or PROBE_FPS)
        t0 = float(board.get("t0") or 0.0)
        name = f"第 {index + 1} 段（源片 {seg.start:.2f}→{seg.end:.2f}s）"

        def window(lo: float, hi: float) -> list[int]:
            return [k for k in range(len(frames)) if lo <= t0 + k / fps < hi]

        if on:
            ks = window(seg.start, seg.end + tail * seg.speed)
            if seg.score_inset_windows:
                ks = [k for k in ks if any(seg.start + a <= t0 + k / fps < seg.start + b
                                           for a, b in seg.score_inset_windows)]
            if not ks:
                soft.append(f"  {name}：窗口落在 probe 扫过的范围外，回贴没查")
                continue
            live = [frames[k] for k in ks if frames[k] is not None]
            if not live:
                hard.append(
                    f"  {name} 开着 score_inset，probe 在这个窗口里逐帧量了 {len(ks)} 帧"
                    f"（{fps:g} fps，{profile} 判据），**一帧板都没认出**——render 的逐帧蒙版"
                    "会在这一段报「一帧都没认出比分板」（板只闪了不到 "
                    f"{1 / fps:.1f}s 的除外——那种段贴出去也只是一闪，同样该关）。"
                    '整段是近景/看台/回放/盘间图形的话写 "score_inset": false ＋ "_score_inset_why"')
                continue
            unresolved = sum(1 for f in live if f[0] < 0)
            if profile == "us-open" and unresolved == len(live):
                hard.append(
                    f"  {name}：板在 {len(live)} 帧，**右缘一帧都量不出**（近景贴着深蓝挡板）——"
                    "render 的 scoreboard_geometry 会报「no stable, majority-supported geometry」。"
                    '写 "score_inset_windows" 收到量得出的那几秒，或 false ＋ "_score_inset_why"')
                continue
            if unresolved / len(live) > UNRESOLVED_WARN:
                soft.append(f"  {name}：板在的 {len(live)} 帧里 {unresolved} 帧右缘量不出"
                            f"（> {UNRESOLVED_WARN:.0%}）——这些帧 render 只能按 spec 的 x1 兜底")
            cap = int(seg.score_inset[2])
            resolved = sorted(f[0] for f in live if f[0] >= 0)
            if profile == "us-open" and len(resolved) >= 2:
                widest = resolved[-2]          # 两票起步，一帧的尖刺不算
                if widest + US_OPEN_EDGE_PAD > cap:
                    hard.append(
                        f"  {name}：量到板右缘 {widest}（+{US_OPEN_EDGE_PAD} 余量），比这一段的框 "
                        f"x1={cap} 宽——render 会报「Verified graphic exceeds source box」。"
                        f"scorebox 的 x1（或这一段的 x2）至少写到 {widest + US_OPEN_EDGE_PAD}")
            elif profile in HINT_PROFILES:
                anchored = [f[1] for f in live if f[1] is not None]
                loose = sum(1 for f in live if f[1] is None)
                if anchored and loose and max(anchored) > cap + EDGE_TOL:
                    soft.append(
                        f"  {name}：有签名色撑着的帧量到板右缘 {max(anchored)}，比 x1={cap} 宽；"
                        f"没撑着的 {loose} 帧 render 会按 x1 截掉最右那一列——"
                        f"scorebox 的 x1 按这场最宽那一档写到 {max(anchored)}")
            continue

        # 写着不贴（false 或没写）
        if seg.fit == "full_source":
            continue                       # 整幅铺进来，原板本来就在画面里
        ks = window(seg.start, seg.end)
        if not ks:
            continue
        run = _longest_run([frames[k] is not None for k in ks])
        secs = run / fps
        if secs < ON_SCREEN_MIN_S:
            continue
        claim = str((raw or {}).get("_board_on_screen_why") or "").strip()
        line = (f"  {name} 写着不贴比分板，可 probe 量到板**连着 {secs:.1f}s** 在画面里"
                f"（{profile} 判据，{fps:g} fps）——居中窗口要么露出半截板、要么这几秒观众看不到比分"
                "（账号所有者 2026-09-24：全出血也要看得到比分）。改 `\"score_inset\": true`"
                "（板淡出的那几秒渲染时自动不贴）")
        if claim:
            soft.append(f"{line}\n    已认领 _board_on_screen_why：{claim}")
        elif strict_off:
            hard.append(f"{line}，或看过缩略图墙后写 `\"_board_on_screen_why\": \"<为什么>\"` 认领")
        else:
            soft.append(line)
    # **开着回贴、probe 却没量板**（2026-09-28 返工审计）：`prozorova-eala` 第 13 段
    # （run 36020126044）、`alcaraz-mensik-doubles` 第 9 段（run 36197683115）都是这个形状——
    # 老 probe 没有 `board`，上面那条「一帧板都没认出」判不了，只报一句「没查」，render
    # 下完源片在 `resolve_masks` 红。手写 spec 硬：重跑一趟 probe（五分钟）换来的是
    # 把一趟七分钟的 render 红提前到 0.2 秒；自动 spec 和定规矩之前已有的只报。
    for source, numbers in sorted(unprobed_on.items()):
        label = source or "(主源)"
        url = urls.get(source, "")
        cmd = reprobe_command(spec, source, url, probes.get(url))
        line = (f"  源 {label}：第 {numbers} 段开着 score_inset，可这份 probe 早于逐帧量板"
                "（没有 `board`，probe_board 2026-09-27 之前跑的）——render 会不会在 "
                "`resolve_masks` 报「一帧都没认出比分板」，dry-run 判不了。重跑一趟 probe：\n"
                f"    {cmd}")
        if auto:
            soft.append(line + "（自动产的 spec 只报）")
        elif source in unprobed_legacy:
            soft.append(line + "（定规矩之前就有的，挂在 legacy_board_unprobed）")
        else:
            hard.append(line)
    return hard, soft
