"""Owner policy: newly rendered footage uses a fixed geometric center.

This deliberately inspects only video framing, never cover-photo focus/zoom.
Legacy noncentral specs must be corrected explicitly before a new render.
"""
from __future__ import annotations

import math


class VideoCropPolicyError(ValueError):
    pass


def require_fixed_center(settings: dict, *, where: str = "video") -> None:
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
