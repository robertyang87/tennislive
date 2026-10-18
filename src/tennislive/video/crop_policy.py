"""Owner policy: newly rendered footage uses a fixed geometric center.

This deliberately inspects only video framing, never cover-photo focus/zoom.
Legacy noncentral specs must be corrected explicitly before a new render.

The one exception (owner 2026-10-18): interview / speech / ceremony segments
declared ``"frame": "person"`` are cropped on the speaker's face — still a
*fixed* window for the whole segment (no following) that keeps every sampled
face inside, with the measured
evidence in ``cx_face`` (``tools/measure_person_center.py``). Match footage
stays at the court center.
"""
from __future__ import annotations

import math


class VideoCropPolicyError(ValueError):
    pass


PERSON_CENTER_MIN_DETECTED = 5
# 脸中心离裁切框左右边缘至少留源片宽的 8%（一张近景脸半宽约 3~5%）。
PERSON_CENTER_EDGE_MARGIN = 0.08


def _half_window(width: int, height: int) -> float:
    return (height * 3 / 4) / (2 * width)


def person_center_max_spread(width: int, height: int) -> float:
    """一个固定框最多装得下多宽的脸位移（两个机位、镜头慢摇都在这里面）。"""
    return round(max(0.0, 2 * (_half_window(width, height) - PERSON_CENTER_EDGE_MARGIN)), 4)


def person_center_cx(lo: float, hi: float, width: int, height: int) -> float:
    """这一段所有采样脸中心的 [最左, 最右] → 固定框的 cx：取正中，夹住不出画。"""
    half = _half_window(width, height)
    if half >= 0.5:
        return 0.5
    return round(min(max((float(lo) + float(hi)) / 2, half), 1 - half), 3)


def person_center_problem(settings: dict) -> str | None:
    """`frame: person` 那一段的 cx 是不是由 `cx_face` 证据算出来的。"""
    if settings.get("frame") != "person":
        return "只有 frame=person 的段可以偏离画面中心"
    if settings.get("track") or settings.get("square_pan"):
        return "人物中心也是固定框，不许 track / square_pan"
    ev = settings.get("cx_face")
    if not isinstance(ev, dict) or not ev.get("samples"):
        return "frame=person 要有 cx_face 证据（跑 tools/measure_person_center.py）"
    xs = [float(x) for x in ev["samples"]]
    if len(xs) < PERSON_CENTER_MIN_DETECTED:
        return f"cx_face 只认出 {len(xs)} 帧脸，不足 {PERSON_CENTER_MIN_DETECTED}"
    size = ev.get("source_size") or []
    if len(size) != 2:
        return "cx_face 缺 source_size"
    spread = max(xs) - min(xs)
    limit = person_center_max_spread(*size)
    if spread > limit + 1e-9:
        return f"cx_face 横向散开 {spread:.3f} 超过一个固定框装得下的 {limit}"
    want = person_center_cx(min(xs), max(xs), *size)
    try:
        got = float(settings.get("cx"))
    except (TypeError, ValueError):
        return "frame=person 的 cx 不是数"
    if abs(got - want) > 0.0015:
        return f"cx={got} 和 cx_face 算出来的 {want} 对不上（重跑 measure_person_center）"
    return None


PERSON_QUOTE_KINDS = ("ceremony", "interview", "press_conference", "player_interview")


def person_frame_problems(spec: dict) -> list[str]:
    """采访／发言段（`_quote_kind` 是人在说话的那几类）必须声明取景。

    `frame: "person"` ＋ `cx_face` 证据（按人物中心固定框），或
    `frame: "court"` ＋ `_frame_why`（这一段确实该用画面中心，例如人太小、在走动）。
    """
    out = []
    for index, seg in enumerate(spec.get("segments") or [], 1):
        if not isinstance(seg, dict):
            continue
        frame = seg.get("frame")
        if frame == "person":
            if problem := person_center_problem(seg):
                out.append(f"第 {index} 段：{problem}")
        elif frame == "court":
            if not str(seg.get("_frame_why") or "").strip():
                out.append(f"第 {index} 段 frame=court 要写 `_frame_why`")
        elif frame is not None:
            out.append(f"第 {index} 段 frame={frame!r}，只认 person / court")
        elif seg.get("_quote_kind") in PERSON_QUOTE_KINDS:
            out.append(
                f"第 {index} 段是采访／发言（_quote_kind={seg.get('_quote_kind')}），"
                "要声明取景：写 `\"frame\": \"person\"` 后跑 "
                "`python3 tools/measure_person_center.py --spec <spec> --src-dir <源片目录>`"
                "（账号所有者 2026-10-18：人物采访按人物中心裁），"
                "或写 `\"frame\": \"court\"` ＋ `_frame_why`")
    return out


def require_fixed_center(settings: dict, *, where: str = "video") -> None:
    if settings.get("frame") == "person":
        if problem := person_center_problem(settings):
            raise VideoCropPolicyError(f"{where}: 人物中心裁切不合格：{problem}")
        settings = {k: v for k, v in settings.items() if k != "cx"}
    bad = []
    if settings.get("track"):
        bad.append("track")
    if settings.get("square_pan"):
        bad.append("square_pan")
    for key, expected in (("cx", 0.5), ("intro_cx", 0.5), ("crop_shift_x", 0.0)):
        value = settings.get(key)
        if value is None:
            continue
        try:
            valid = (not isinstance(value, bool) and math.isfinite(float(value))
                     and float(value) == expected)
        except (TypeError, ValueError):
            valid = False
        if not valid:
            bad.append(key)
    if bad:
        raise VideoCropPolicyError(
            f"{where}: 全局视频裁切策略为固定中间 cx=0.5、track=false、"
            f"crop_shift_x=0；不允许自动跟随或左右偏移（{', '.join(bad)}）。"
            "请显式修正旧视频配置；封面照片 focus/zoom 不受此限制。")


def require_interview_center(spec: dict) -> None:
    require_fixed_center(spec, where="interview")
    for key in ("lead_in", "trail_in"):
        if isinstance(spec.get(key), dict):
            require_fixed_center(spec[key], where=f"interview.{key}")


def require_reel_center(spec: dict) -> None:
    for index, video in enumerate(spec.get("segments", []), 1):
        if not any(video.get(key) for key in ("image", "stat_card", "title_card")):
            require_fixed_center(video, where=f"segments[{index}]")
