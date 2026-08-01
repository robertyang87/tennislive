#!/usr/bin/env python3
"""Validate the repository-wide audio QA record before a video is delivered.

Renderers own the edit plan; this gate owns the delivery contract.  Keeping
the checks here means a workflow cannot accidentally treat "ffmpeg exited 0"
as proof that the final MP4 still has a complete, aligned audio stream.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

from tennislive.video.audio import (
    MIN_EFFECTIVE_FADE_SECONDS,
    NA_AUDIO_EXPECTATIONS,
)


POLICY_VERSION = 1
MAX_AV_DELTA_SECONDS = 0.05
MAX_TIMELINE_DELTA_SECONDS = 0.001
ROLES = {"speech", "music", "ambience", "mixed", "silence"}
STATUSES = {"pass", "not_applicable"}
JOIN_MODES = {
    "fade_through_silence",
    "lcut_crossfade",
    "keep",
    "declick",
}


class AudioQAGateError(RuntimeError):
    """The structured report or final media violates the audio contract."""


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AudioQAGateError(f"{field} 必须是数字")
    result = float(value)
    if not math.isfinite(result):
        raise AudioQAGateError(f"{field} 必须是有限数字")
    return result


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise AudioQAGateError(f"{field} 必须是非负整数")
    return value


def validate_report(payload: dict[str, Any]) -> None:
    """Validate schema, transition accounting and speech safety."""
    if payload.get("policy_version") != POLICY_VERSION:
        raise AudioQAGateError(
            f"policy_version 必须是 {POLICY_VERSION}，实为 "
            f"{payload.get('policy_version')!r}"
        )
    status = payload.get("status")
    if status not in STATUSES:
        raise AudioQAGateError(f"status 必须是 {sorted(STATUSES)}，实为 {status!r}")
    role = payload.get("role")
    if role not in ROLES:
        raise AudioQAGateError(f"role 必须是 {sorted(ROLES)}，实为 {role!r}")
    reason = payload.get("reason")
    if not isinstance(reason, str):
        raise AudioQAGateError("reason 必须是字符串")

    joins = payload.get("joins")
    if not isinstance(joins, list):
        raise AudioQAGateError("joins 必须是数组")
    transition_count = _integer(payload.get("transition_count"), "transition_count")
    if transition_count != len(joins):
        raise AudioQAGateError(
            f"transition_count={transition_count}，但 joins 有 {len(joins)} 条"
        )
    declared_hard_cuts = _integer(
        payload.get("hard_cut_count"), "hard_cut_count"
    )
    duration_delta = _number(
        payload.get("duration_delta_seconds"), "duration_delta_seconds"
    )
    if abs(duration_delta) > MAX_TIMELINE_DELTA_SECONDS:
        raise AudioQAGateError(
            f"音频转场改变时间线 {duration_delta:.6f}s，超过 "
            f"{MAX_TIMELINE_DELTA_SECONDS:.3f}s"
        )

    observed = {mode: 0 for mode in JOIN_MODES}
    derived_hard_cuts = 0
    boundaries: set[tuple[str, int]] = set()
    for index, row in enumerate(joins):
        if not isinstance(row, dict):
            raise AudioQAGateError(f"joins[{index}] 必须是对象")
        boundary = _integer(row.get("boundary"), f"joins[{index}].boundary")
        layer_id = str(row.get("layer_id") or "programme")
        boundary_key = (layer_id, boundary)
        if boundary_key in boundaries:
            raise AudioQAGateError(f"{layer_id} 的边界 {boundary} 重复")
        boundaries.add(boundary_key)
        mode = row.get("mode")
        if mode not in JOIN_MODES:
            raise AudioQAGateError(f"joins[{index}].mode 非法：{mode!r}")
        observed[mode] += 1
        fade_out = _number(row.get("fade_out"), f"joins[{index}].fade_out")
        fade_in = _number(row.get("fade_in"), f"joins[{index}].fade_in")
        if fade_out < 0 or fade_in < 0:
            raise AudioQAGateError(f"joins[{index}] 淡化时长不能为负")
        row_role = row.get("layer_role", role)
        if row_role not in ROLES:
            raise AudioQAGateError(f"joins[{index}].layer_role 非法：{row_role!r}")
        if row_role in {"speech", "silence"}:
            if mode == "keep":
                continue
            if mode != "declick" or max(fade_out, fade_in) > 0.03:
                raise AudioQAGateError(
                    f"{role} 边界 {boundary} 只能 keep 或至多 30ms de-click"
                )
        if mode in {"fade_through_silence", "declick"} and min(
            fade_out, fade_in
        ) < MIN_EFFECTIVE_FADE_SECONDS:
            raise AudioQAGateError(
                f"joins[{index}] 的 {mode} 两侧淡化都必须至少 "
                f"{MIN_EFFECTIVE_FADE_SECONDS:.3f}s，不能用零时长或近零时长伪装处理"
            )
        if mode == "keep" and row_role not in {"speech", "silence"}:
            same_continuous_source = (
                row.get("previous_source") is not None
                and row.get("previous_source") == row.get("next_source")
            )
            if not same_continuous_source:
                derived_hard_cuts += 1

    if declared_hard_cuts != derived_hard_cuts:
        raise AudioQAGateError(
            f"hard_cut_count={declared_hard_cuts}，但 resolved joins 推导为 "
            f"{derived_hard_cuts}"
        )
    if derived_hard_cuts:
        raise AudioQAGateError("交付视频不允许未平滑的硬切")

    count_fields = {
        "lcut_crossfade": "lcut_crossfade_count",
        "fade_through_silence": "fade_through_silence_count",
        "declick": "declick_count",
        "keep": "keep_count",
    }
    for mode, field in count_fields.items():
        declared = _integer(payload.get(field), field)
        if declared != observed[mode]:
            raise AudioQAGateError(
                f"{field}={declared}，但 joins 中 {mode} 有 {observed[mode]} 条"
            )
    fallback_count = _integer(payload.get("fallback_count", 0), "fallback_count")
    if fallback_count != observed["fade_through_silence"]:
        raise AudioQAGateError(
            f"fallback_count={fallback_count}，但 fade_through_silence 有 "
            f"{observed['fade_through_silence']} 条"
        )
    if fallback_count and not reason.strip():
        raise AudioQAGateError(
            "fade_through_silence 是降级路径，必须提供非空 reason"
        )

    layers = payload.get("layers")
    if layers is not None:
        if not isinstance(layers, list) or not layers:
            raise AudioQAGateError("layers 必须是非空数组")
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict) or not isinstance(layer.get("audio_qa"), dict):
                raise AudioQAGateError(f"layers[{index}] 缺 audio_qa")
            validate_report(layer["audio_qa"])

    if status == "not_applicable":
        if reason not in NA_AUDIO_EXPECTATIONS:
            rendered = ", ".join(sorted(NA_AUDIO_EXPECTATIONS))
            raise AudioQAGateError(
                f"not_applicable reason 必须是受控枚举：{rendered}"
            )
        expected_audio = payload.get("expected_audio_stream")
        required_audio = NA_AUDIO_EXPECTATIONS[reason]
        if expected_audio != required_audio:
            raise AudioQAGateError(
                f"reason={reason} 的 expected_audio_stream 必须是 "
                f"{required_audio!r}，实为 {expected_audio!r}"
            )
        if joins or transition_count:
            raise AudioQAGateError("not_applicable 不能同时声明转场")
    elif role in {"music", "ambience", "mixed"} and transition_count:
        for row in joins:
            if row["mode"] != "keep":
                continue
            row_role = row.get("layer_role", role)
            same_continuous_source = (
                row.get("previous_source") is not None
                and row.get("previous_source") == row.get("next_source")
            )
            if row_role not in {"speech", "silence"} and not same_continuous_source:
                raise AudioQAGateError("多段节目音频仍存在未平滑的跨源 keep 边界")


def _stream_duration(stream: dict[str, Any]) -> float | None:
    value = stream.get("duration")
    if value not in {None, "N/A"}:
        try:
            result = float(value)
        except (TypeError, ValueError):
            pass
        else:
            if math.isfinite(result) and result >= 0:
                return result
    duration_ts = stream.get("duration_ts")
    time_base = stream.get("time_base")
    if duration_ts in {None, "N/A"} or not isinstance(time_base, str):
        return None
    try:
        numerator, denominator = time_base.split("/", 1)
        result = float(duration_ts) * float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) and result >= 0 else None


def _stream_start(stream: dict[str, Any]) -> float | None:
    """Read one stream's real timeline origin, not the container origin."""
    value = stream.get("start_time")
    if value not in {None, "N/A"}:
        try:
            result = float(value)
        except (TypeError, ValueError):
            pass
        else:
            if math.isfinite(result):
                return result
    start_pts = stream.get("start_pts")
    time_base = stream.get("time_base")
    if start_pts in {None, "N/A"} or not isinstance(time_base, str):
        return None
    try:
        numerator, denominator = time_base.split("/", 1)
        result = float(start_pts) * float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) else None


def _stream_timing(stream: dict[str, Any]) -> dict[str, float] | None:
    """Return a coherent start/duration/end triple for the same stream."""
    start = _stream_start(stream)
    duration = _stream_duration(stream)
    if start is None or duration is None:
        return None
    return {
        "start_seconds": start,
        "duration_seconds": duration,
        "end_seconds": start + duration,
    }


def probe_media(video: Path, *, ffprobe_bin: str = "ffprobe") -> dict[str, Any]:
    if shutil.which(ffprobe_bin) is None:
        raise AudioQAGateError(f"找不到 {ffprobe_bin}")
    if not video.is_file() or video.stat().st_size == 0:
        raise AudioQAGateError(f"最终视频不存在或为空：{video}")
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,start_time,start_pts,duration,duration_ts,time_base:format=duration",
        "-of",
        "json",
        str(video),
    ]
    try:
        raw = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        ).stdout
        data = json.loads(raw)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise AudioQAGateError(f"ffprobe 失败：{video}: {exc}") from exc
    streams = data.get("streams") or []
    result: dict[str, Any] = {"has_video": False, "has_audio": False}
    for kind in ("video", "audio"):
        candidates = [item for item in streams if item.get("codec_type") == kind]
        result[f"has_{kind}"] = bool(candidates)
        # Pick one complete stream and keep its timing coherent.  Taking the
        # longest duration from one stream and the earliest start from another
        # would manufacture an end point that does not exist in the file.
        timings = [timing for item in candidates
                   if (timing := _stream_timing(item)) is not None]
        if timings:
            timing = max(timings, key=lambda item: item["duration_seconds"])
            for field, value in timing.items():
                result[f"{kind}_{field}"] = value
        else:
            # Retain any independently readable duration for a precise error;
            # delivery validation will still reject a missing start/end.
            durations = [duration for item in candidates
                         if (duration := _stream_duration(item)) is not None]
            if durations:
                result[f"{kind}_duration_seconds"] = max(durations)
    if not result["has_video"]:
        raise AudioQAGateError(f"最终文件没有视频流：{video}")
    return result


def validate_delivery(
    payload: dict[str, Any],
    video: Path,
    *,
    ffprobe_bin: str = "ffprobe",
) -> dict[str, Any]:
    """Validate that the report describes the actual final delivery MP4."""
    validate_report(payload)
    media = probe_media(video, ffprobe_bin=ffprobe_bin)
    status = payload["status"]
    reason = payload["reason"]
    role = payload["role"]
    has_audio = bool(media["has_audio"])
    if status == "pass" and not has_audio:
        raise AudioQAGateError("报告为 pass，但最终视频没有音频流")
    if status == "not_applicable":
        expected_audio = NA_AUDIO_EXPECTATIONS[reason]
        if expected_audio == "not_applicable":
            raise AudioQAGateError(
                f"reason={reason} 只适用于没有成片的阶段，不能用来验最终视频"
            )
        if expected_audio == "absent" and has_audio:
            raise AudioQAGateError(
                f"报告写 {reason} / audio absent，但最终视频存在音频流"
            )
        if expected_audio == "present" and not has_audio:
            raise AudioQAGateError(
                f"报告写 {reason} / audio present，但最终视频没有音频流"
            )
        if reason in {"no_audio", "synthetic_silence"} and role != "silence":
            raise AudioQAGateError(f"{reason} 的 role 必须是 silence")

    # Always retain the measured final stream evidence in the sidecar payload.
    # The CLI persists this mutation on both pass and fail, so a red gate still
    # explains exactly which edge drifted.
    metric_names = (
        "video_start_seconds",
        "audio_start_seconds",
        "video_duration_seconds",
        "audio_duration_seconds",
        "video_end_seconds",
        "audio_end_seconds",
    )
    for name in metric_names:
        value = media.get(name)
        if value is not None:
            payload[f"final_{name}"] = round(float(value), 6)

    if has_audio:
        required = {
            name: media.get(name)
            for name in metric_names
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise AudioQAGateError(
                "ffprobe 读不到最终视频/音频流的独立起点、时长和终点："
                + ", ".join(missing)
            )
        video_start = float(required["video_start_seconds"])
        audio_start = float(required["audio_start_seconds"])
        video_duration = float(required["video_duration_seconds"])
        audio_duration = float(required["audio_duration_seconds"])
        video_end = float(required["video_end_seconds"])
        audio_end = float(required["audio_end_seconds"])
        start_delta = abs(video_start - audio_start)
        av_delta = abs(float(video_duration) - float(audio_duration))
        end_delta = abs(video_end - audio_end)
        media.update({
            "av_start_delta_seconds": start_delta,
            "av_duration_delta_seconds": av_delta,
            "av_end_delta_seconds": end_delta,
        })
        payload.update({
            "av_start_delta_seconds": round(start_delta, 6),
            "av_duration_delta_seconds": round(av_delta, 6),
            "av_end_delta_seconds": round(end_delta, 6),
            "max_av_delta_seconds": MAX_AV_DELTA_SECONDS,
        })
        if start_delta > MAX_AV_DELTA_SECONDS:
            raise AudioQAGateError(
                f"最终 A/V 起点时差 {start_delta:.3f}s，超过 "
                f"{MAX_AV_DELTA_SECONDS:.3f}s"
            )
        if end_delta > MAX_AV_DELTA_SECONDS:
            raise AudioQAGateError(
                f"最终 A/V 终点时差 {end_delta:.3f}s，超过 "
                f"{MAX_AV_DELTA_SECONDS:.3f}s"
            )
        if av_delta > MAX_AV_DELTA_SECONDS:
            raise AudioQAGateError(
                f"最终 A/V 时长差 {av_delta:.3f}s，超过 "
                f"{MAX_AV_DELTA_SECONDS:.3f}s"
            )

    expected = payload.get("expected_duration_seconds")
    if expected is None:
        expected = payload.get("declared_output_duration_seconds")
    if expected is not None and media.get("video_duration_seconds") is not None:
        expected_number = _number(expected, "expected_duration_seconds")
        delivery_delta = abs(float(media["video_duration_seconds"]) - expected_number)
        if delivery_delta > MAX_AV_DELTA_SECONDS:
            raise AudioQAGateError(
                f"最终视频相对声明时长偏差 {delivery_delta:.3f}s，超过 "
                f"{MAX_AV_DELTA_SECONDS:.3f}s"
            )
        media["expected_duration_delta_seconds"] = delivery_delta
        payload["expected_duration_delta_seconds"] = round(delivery_delta, 6)
    return media


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验最终视频的全工程音频 QA")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--video", type=Path)
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args(argv)
    payload: dict[str, Any] | None = None
    try:
        payload = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AudioQAGateError("音频 QA 顶层必须是对象")
        if args.video is None:
            validate_report(payload)
            print(f"audio QA pass: {args.report}")
        else:
            media = validate_delivery(payload, args.video, ffprobe_bin=args.ffprobe)
            args.report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"audio delivery QA pass: {args.video} "
                f"(audio={media['has_audio']}, "
                f"start={media.get('av_start_delta_seconds', 0.0):.3f}s, "
                f"end={media.get('av_end_delta_seconds', 0.0):.3f}s)"
            )
    except (OSError, ValueError, AudioQAGateError) as exc:
        # Timing evidence is most useful when the gate is red.  validate_delivery
        # mutates only after it has a real ffprobe result; persist that evidence
        # without turning a report-write failure into a false pass.
        if payload is not None and args.video is not None:
            try:
                args.report.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            except OSError:
                pass
        parser.exit(1, f"audio QA failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
