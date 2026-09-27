#!/usr/bin/env python3
"""把 `face_checks`（认人＋睁眼）接进竖版短片那条线：**封面抽帧**和**分段 3:4 画面**。

## 来路（账号所有者 2026-09-27：O2+O3「两个都加」）

「赛场之上」的封面允许抽帧（2026-09-26「没有高清大图可备选的话，抽帧也可以，
但是要尽量清晰偏正面」），而这条线上**一道看脸的闸都没有**——采访线好歹有
Haar，这边连 Haar 都没有（forensics：`match-reel.yml` 里没有任何封面像素审核）。
抽帧抽到别人、抽到眨眼的那一瞬，都要等账号所有者在微信里看见才换
（`bu-majchrzak` 侧脸 5beecfa6、`alcaraz-fritz`「抽帧的太丑了」6b49049b）。

## 两道，一硬一软

| | 查什么 | 红了怎样 |
|---|---|---|
| **封面抽帧**（`cover.portrait.frame_at`） | 是不是这场球的两个人之一、眼睛睁没睁 | **硬**：`ReelError`，并把 `frame_at` 前后 ±1 秒扫一圈能过的秒数印出来 |
| **分段 3:4 画面** | 旁白只点了一个人的名，画面里最大的那张脸是不是另一个人 | **只报不拦**：写进 `render.json` 的 `face_checks.segments` |

分段那道为什么只报：转播主机位的宽景里球员的脸只有二三十像素，认人在这种画面上
**没有拿真样本量过精度**（封面那两个门槛是拿 85 张真封面量的）。先攒数，证明了再收紧
——`crosses_cut` 那次「做成硬闸然后被数据否掉」的老账不再来一遍。

## 认领口

- `cover.portrait._face_check_why`：这一帧确实要用（比如讲的就是教练席那一幕、
  闭眼流泪就是这张封面要的情绪）。写一句为什么，硬问题降成提示——和
  `_frame_why` / `_layout_why` 同一个形状：认领让「想清楚了」和「凑合」分开。

## 模型加载不了

`status: unavailable` 写进 `render.json`，日志里打 ⚠️——**大声降级，不拖垮出片，
也不装作查过**。
"""
from __future__ import annotations

import subprocess
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import face_checks

FACE_CHECK_WHY = "_face_check_why"
#: 封面被拦下时在 `frame_at` 前后扫多远、多密（秒）。±1 秒、0.2 秒一格＝11 帧，
#: 只在**失败那一支**花，约 3~5 秒。
SCAN_RADIUS = 1.0
SCAN_STEP = 0.2
#: 分段那道每段看几帧（段内相对位置）。两帧够判「是不是另一个人」，
#: 多了只是去抢 x264 的核（它和编码同时跑）。
SEGMENT_SAMPLES = (1 / 3, 2 / 3)


def _names(entry: object) -> list[str]:
    name = entry.get("name") if isinstance(entry, dict) else entry
    if isinstance(name, list):
        return [str(n).strip() for n in name if str(n).strip()]
    return [p.strip() for p in str(name or "").replace("／", "/").split("/") if p.strip()]


def expected_players(spec: dict) -> dict[str, str | None]:
    """这场球里的人 → 官方头像。优先用**这条 spec 自己认过**的 `stats.*.headshot`，
    没有再交给 `face_checks.headshot_path` 从已发 spec 反查。双打按「A / B」拆开对齐。"""
    cover = spec.get("cover") or {}
    stats = spec.get("stats") or {}
    out: dict[str, str | None] = {}
    for key, entry in zip(("a", "b"), cover.get("matchup") or []):
        names = _names(entry)
        heads = (stats.get(key) or {}).get("headshot")
        heads = heads if isinstance(heads, list) else [heads] if heads else []
        for i, name in enumerate(names):
            out[name] = heads[i] if i < len(heads) and len(heads) == len(names) else None
    if not out:
        # 「网球有故事」讲一个人，没有 matchup，主角写在 `cover.subject`
        out = {name: None for name in _names(cover.get("subject"))}
    return out


def _claim(spec: dict) -> str:
    art = (spec.get("cover") or {}).get("portrait") or {}
    return str(art.get(FACE_CHECK_WHY) or "").strip()


def cover_frame_report(spec: dict, frame: Path) -> dict:
    """封面抽下来的那一帧：认人＋睁眼。`problems` 非空＝要拦（除非认领过）。"""
    expected = expected_players(spec)
    rep = face_checks.check_frame(Path(frame), expected)
    rep["frame"] = str(frame)
    rep["frame_at"] = ((spec.get("cover") or {}).get("portrait") or {}).get("frame_at")
    if not expected:
        rep["warnings"].append("cover.matchup / cover.subject 里没有人名，认人无从比起")
    if rep["problems"] and (why := _claim(spec)):
        rep["warnings"] += [f"{p}（已认领：{why}）" for p in rep["problems"]]
        rep["claimed"] = why
        rep["problems"] = []
    return rep


def grab_frame(source: Path, at: float, dest: Path, vf_args: tuple[str, ...] = ()) -> Path:
    """从源片抓一帧（和封面抓帧同一条 ffmpeg 命令形状，`vf_args` 给 conform 用）。"""
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{max(0.0, at):.2f}", "-i", str(source), *vf_args,
                    "-frames:v", "1", "-q:v", "2", str(dest)],
                   check=True, capture_output=True, timeout=120)
    return dest


def nearby_passing(spec: dict, source: Path, at: float, workdir: Path,
                   vf_args: tuple[str, ...] = ()) -> list[dict]:
    """被拦下之后「换哪一帧」：`frame_at` 前后扫一圈，返回能过的（好的在前）。"""
    scan = workdir / "_face_scan"
    scan.mkdir(parents=True, exist_ok=True)
    frames = []
    steps = int(round(SCAN_RADIUS / SCAN_STEP))
    for k in range(-steps, steps + 1):
        t = round(at + k * SCAN_STEP, 2)
        if k == 0 or t < 0:
            continue
        try:
            frames.append((t, grab_frame(source, t, scan / f"{t:.2f}.jpg", vf_args)))
        except (subprocess.SubprocessError, OSError):
            continue
    try:
        rows = face_checks.rank_frames(frames, expected_players(spec))
    finally:
        for _, path in frames:
            path.unlink(missing_ok=True)
        try:
            scan.rmdir()
        except OSError:
            pass
    return [r for r in rows if r["ok"]]


def cover_error(rep: dict, candidates: list[dict] | None) -> str:
    """拦下封面帧时的报错正文：量到的数、为什么、换哪一帧。"""
    ident, eyes = rep.get("identity") or {}, rep.get("eyes") or {}
    lines = [f"封面抽帧 {rep.get('frame_at')}s 过不了认人／睁眼闸"
             "（账号所有者 2026-09-27 批的 O2+O3：选错人、闭眼／垂眼的帧不许上封面）："]
    lines += [f"  - {p}" for p in rep["problems"]]
    lines.append(f"  量到的：相似度 {ident.get('similarity')}（门槛 match ≥ "
                 f"{face_checks.MATCH_SIM}、mismatch < {face_checks.MISMATCH_SIM}）｜"
                 f"眼睛纵横比 {eyes.get('ear')}（< {face_checks.EYE_OPEN_EAR} 算垂眼）｜"
                 f"脸高 {ident.get('face_px')}px")
    if candidates:
        best = "、".join(f"{c['frame']}s（像 {c['name']} {c['similarity']:.2f}，眼 {c['ear']:.2f}）"
                        for c in candidates[:4])
        lines.append(f"  前后 ±{SCAN_RADIUS:g} 秒里能过的：{best}——把 `frame_at` 改成其中一个")
    elif candidates is not None:
        lines.append(f"  前后 ±{SCAN_RADIUS:g} 秒里没有一帧能过——换一个镜头，"
                     "或者先去找官方高清实拍（tools/find_cover_photo.py）")
    lines.append(f"  这一帧确实要用，就在 cover.portrait 写 `{FACE_CHECK_WHY}` 说清楚为什么。")
    return "\n".join(lines)


# ---------------------------------------------------------------- 分段 3:4 画面

def _window_x(seg, index: int, tracks: dict, source_w: int, crop_w: int, rel: float) -> int:
    path = tracks.get(index) or []
    if path:
        return min(path, key=lambda p: abs(p[0] - rel))[1]
    x = int(round((seg.cx if seg.cx is not None else 0.5) * source_w - crop_w / 2))
    return max(0, min(x, source_w - crop_w))


def segment_checks(spec: dict, segments: list, sources: dict[str, Path], tracks: dict,
                   *, source_w: int, crop_w: int, window, vf_for, workdir: Path) -> dict:
    """每一段旁白**只点了一个人的名**的，抽两帧、按成片的 3:4 窗口裁出来，看最大的
    那张脸是不是另一个人。`window(x, seg) -> (w, h, x, y)` 由调用方给（就是
    `build_match_reel.zoomed_window` 那套几何，写两份必分叉）。**只报不拦。**
    """
    import cv2  # noqa: PLC0415

    try:
        model = face_checks.load()
    except face_checks.ModelUnavailable as exc:
        return {"status": "unavailable", "error": str(exc), "report_only": True,
                "warnings": [f"人脸模型不可用，分段画面没查：{exc}"]}
    players = [n for n in expected_players(spec)]
    rows, findings = [], []
    scan = workdir / "_face_segments"
    scan.mkdir(parents=True, exist_ok=True)
    for i, seg in enumerate(segments):
        if getattr(seg, "image", None) or getattr(seg, "fit", "crop") != "crop":
            continue
        text = str(getattr(seg, "narration", "") or "")
        named = [n for n in players if n in text]
        if len(named) != 1 or len(players) < 2:
            continue
        others = [n for n in players if n != named[0]]
        frames = []
        for frac in SEGMENT_SAMPLES:
            rel = (seg.end - seg.start) * frac
            at = seg.start + rel
            dest = scan / f"{i:02d}_{frac:.2f}.jpg"
            try:
                grab_frame(sources[seg.source], at, dest, vf_for(seg.source))
            except (subprocess.SubprocessError, OSError, KeyError):
                continue
            img = cv2.imread(str(dest))
            dest.unlink(missing_ok=True)
            if img is None:
                continue
            w, h, x, y = window(_window_x(seg, i, tracks, source_w, crop_w, rel), seg)
            frames.append((f"第 {i + 1} 段 {at:.1f}s", img[y:y + h, x:x + w]))
        found, tally = face_checks.crop_findings(frames, named[0], others, model=model)
        rows.append({"segment": i + 1, "named": named[0], **tally})
        findings += found
    try:
        scan.rmdir()
    except OSError:
        pass
    return {"status": "ok", "model": face_checks.MODEL_VERSION, "report_only": True,
            "segments": rows, "findings": findings,
            "frames": sum(r["frames"] for r in rows),
            "faces": sum(r["faces"] for r in rows)}


_POOL: ThreadPoolExecutor | None = None


def start_segment_checks(*args, **kwargs) -> Future:
    """和分段编码**同时跑**（一个后台线程）。它只报不拦，没有理由排在编码前面
    占着关键路径——账号所有者 2026-09-27 那句「加速」管的正是这种。"""
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="face-segments")
    return _POOL.submit(segment_checks, *args, **kwargs)


def finish_segment_checks(future: Future | None, timeout: float = 120.0) -> dict | None:
    """等它交卷；超时或出错都**记下来**，不许当成「查过了、没问题」。"""
    if future is None:
        return None
    try:
        return future.result(timeout=timeout)
    except Exception as exc:                                      # noqa: BLE001
        return {"status": "error", "report_only": True,
                "error": f"{type(exc).__name__}: {exc}",
                "warnings": [f"分段画面认人没跑完：{type(exc).__name__}: {exc}"]}
