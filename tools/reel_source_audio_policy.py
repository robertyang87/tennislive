"""Standard-library-only source-audio policy for new native reel production.

This describes a new render, never the gain of an already published film.
Explicit owner-approved source replacement/effects modes keep their own gates.
"""
from __future__ import annotations

UNITY_POLICY = "unity_no_loudness_v1"
LEGACY_POLICY = "explicit_audio_mode"


def normal_source_audio(spec: dict) -> bool:
    return not (spec.get("original_audio_mode") or spec.get("audio_effects_review"))


def validate(spec: dict) -> None:
    """Reject gain-changing recipes before downloading or encoding a new film."""
    if not normal_source_audio(spec):
        return
    if spec.get("music") or spec.get("source_audio"):
        raise ValueError("正常制作保留原声，不接受额外音乐或替换音轨")
    for index, seg in enumerate(spec.get("segments") or []):
        if seg.get("mute") or seg.get("bed") or seg.get("speed", 1) != 1:
            raise ValueError(f"第 {index + 1} 段正常制作不调整原声：去掉 mute、bed 或变速")


def record(spec: dict) -> str:
    return UNITY_POLICY if normal_source_audio(spec) else LEGACY_POLICY
