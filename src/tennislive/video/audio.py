"""Duration-safe audio joins shared by the video renderers.

The normal join in this module deliberately is *not* an ``acrossfade``.
FFmpeg's ``acrossfade`` overlaps its inputs and therefore shortens the output
timeline.  Most tennislive renderers already place narration and subtitles on
the sum-of-segments timeline, so changing that duration inside a helper would
silently desynchronise the finished video.

Instead, unrelated sources fade out and back in inside their existing segment
windows.  This removes abrupt changes between already-mastered source clips
without moving a single chapter boundary.  A duration-preserving L-cut is
available when the caller supplies a legitimate post-cut tail handle.  A plain
``acrossfade`` remains explicitly unsupported until the repository has one
auditable helper that builds both the matching video and audio timelines.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from typing import Literal, Mapping, Sequence


JoinMode = Literal[
    "fade_through_silence",
    "lcut_crossfade",
    "keep",
    "declick",
    "acrossfade",
]
AudioRole = Literal["speech", "music", "ambience", "mixed", "silence"]
SameSourceStrategy = Literal["keep", "declick"]
NotApplicableReason = Literal[
    "no_audio",
    "single_continuous_source",
    "audio_passthrough",
    "single_supplied_voiceover",
    "synthetic_silence",
    "subtitle_only",
    "single_continuous_layer",
    "no_usable_audio_source",
]

DEFAULT_FADE_OUT = 0.40
DEFAULT_FADE_IN = 0.30
DEFAULT_FADE_CURVE = "qsin"
DEFAULT_DECLICK_SECONDS = 0.02
MIN_EFFECTIVE_FADE_SECONDS = 0.005
DEFAULT_SAMPLE_RATE = 48_000
DEFAULT_CHANNEL_LAYOUT = "stereo"
LCUT_PEAK_LIMIT = 0.95
AUDIO_POLICY_VERSION = 1

_JOIN_MODES = {
    "fade_through_silence",
    "lcut_crossfade",
    "keep",
    "declick",
    "acrossfade",
}
_SAME_SOURCE_STRATEGIES = {"keep", "declick"}
_AUDIO_ROLES = {"speech", "music", "ambience", "mixed", "silence"}
NA_AUDIO_EXPECTATIONS = {
    "no_audio": "absent",
    "single_continuous_source": "present",
    "audio_passthrough": "present",
    "single_supplied_voiceover": "present",
    "synthetic_silence": "present",
    "subtitle_only": "not_applicable",
    "single_continuous_layer": "present",
    "no_usable_audio_source": "absent",
}
_FADE_CURVES = {
    "tri",
    "qsin",
    "esin",
    "hsin",
    "log",
    "ipar",
    "qua",
    "cub",
    "squ",
    "cbr",
    "par",
    "exp",
    "iqsin",
    "ihsin",
    "dese",
    "desi",
    "losi",
    "sinc",
    "isinc",
    "nofade",
}
_LABEL = re.compile(r"^[A-Za-z0-9_.:-]+$")


class AudioJoinError(ValueError):
    """Raised when an audio join would be invalid or change time implicitly."""


@dataclass(frozen=True)
class AVSegment:
    """Metadata needed to build a filtergraph for one prepared A/V input.

    Labels are bare FFmpeg labels (``0:v``, not ``[0:v]``).  When omitted,
    ``concat_av_filter`` uses the input index: ``0:v``/``0:a``, then
    ``1:v``/``1:a``, and so on.
    """

    duration: float
    source_id: str | None = None
    video_label: str | None = None
    audio_label: str | None = None

    def __post_init__(self) -> None:
        _positive_finite(self.duration, "segment duration")
        if self.video_label is not None:
            _bare_label(self.video_label)
        if self.audio_label is not None:
            _bare_label(self.audio_label)


@dataclass(frozen=True)
class AudioTailHandle:
    """An already-extracted tail used for a duration-preserving L-cut.

    Extraction is deliberately outside this module.  The label must point to
    audio that starts exactly where the preceding main segment ends; the graph
    overlays it on the beginning of the next segment and never adds it to the
    programme duration.
    """

    label: str
    duration: float

    def __post_init__(self) -> None:
        _bare_label(self.label)
        _positive_finite(self.duration, "tail handle duration")


@dataclass(frozen=True)
class AudioJoinPolicy:
    """Editorial policy for the boundary between two segments."""

    mode: JoinMode = "fade_through_silence"
    fade_out: float = DEFAULT_FADE_OUT
    fade_in: float = DEFAULT_FADE_IN
    curve: str = DEFAULT_FADE_CURVE
    overlap: float | None = None

    def __post_init__(self) -> None:
        if self.mode == "acrossfade":
            raise AudioJoinError(
                "acrossfade is not supported by the repository-wide QA "
                "contract; use a duration-preserving L-cut with a tail handle"
            )
        if self.mode not in _JOIN_MODES:
            raise AudioJoinError(f"unknown audio join mode: {self.mode}")
        _nonnegative_finite(self.fade_out, "fade_out")
        _nonnegative_finite(self.fade_in, "fade_in")
        if self.curve not in _FADE_CURVES:
            raise AudioJoinError(f"unsupported FFmpeg fade curve: {self.curve}")
        if self.mode in {"acrossfade", "lcut_crossfade"}:
            if self.overlap is None:
                raise AudioJoinError(
                    f"{self.mode} requires an explicit overlap; use its "
                    "AudioJoinPolicy constructor"
                )
            _positive_finite(self.overlap, "acrossfade overlap")
        elif self.overlap is not None:
            raise AudioJoinError("overlap is only valid for acrossfade")
        if self.mode in {"fade_through_silence", "declick"}:
            if min(self.fade_out, self.fade_in) < MIN_EFFECTIVE_FADE_SECONDS:
                raise AudioJoinError(
                    f"{self.mode} requires both fades to be at least "
                    f"{MIN_EFFECTIVE_FADE_SECONDS:.3f}s"
                )

    @classmethod
    def fade_through_silence(
        cls,
        *,
        fade_out: float = DEFAULT_FADE_OUT,
        fade_in: float = DEFAULT_FADE_IN,
        curve: str = DEFAULT_FADE_CURVE,
    ) -> "AudioJoinPolicy":
        return cls(
            mode="fade_through_silence",
            fade_out=fade_out,
            fade_in=fade_in,
            curve=curve,
        )

    @classmethod
    def keep(cls) -> "AudioJoinPolicy":
        return cls(mode="keep", fade_out=0.0, fade_in=0.0)

    @classmethod
    def lcut_crossfade(
        cls,
        overlap: float,
        *,
        curve: str = DEFAULT_FADE_CURVE,
    ) -> "AudioJoinPolicy":
        """Crossfade an external outgoing tail over the next main segment."""
        return cls(
            mode="lcut_crossfade",
            fade_out=0.0,
            fade_in=0.0,
            curve=curve,
            overlap=overlap,
        )

    @classmethod
    def declick(
        cls,
        seconds: float = DEFAULT_DECLICK_SECONDS,
        *,
        curve: str = DEFAULT_FADE_CURVE,
    ) -> "AudioJoinPolicy":
        return cls(
            mode="declick",
            fade_out=seconds,
            fade_in=seconds,
            curve=curve,
        )

    @classmethod
    def acrossfade(
        cls,
        overlap: float,
        *,
        curve: str = DEFAULT_FADE_CURVE,
    ) -> "AudioJoinPolicy":
        return cls(
            mode="acrossfade",
            fade_out=0.0,
            fade_in=0.0,
            curve=curve,
            overlap=overlap,
        )


@dataclass(frozen=True)
class ResolvedAudioJoin:
    """A boundary policy after segment-length clamping has been applied."""

    boundary: int
    mode: JoinMode
    fade_out: float
    fade_in: float
    curve: str
    previous_source: str | None
    next_source: str | None
    overlap: float = 0.0
    tail_handle_label: str | None = None


@dataclass(frozen=True)
class ConcatFiltergraph:
    """A duration-preserving FFmpeg A/V concat filtergraph."""

    filtergraph: str
    video_label: str
    audio_label: str
    output_duration: float
    duration_delta: float
    joins: tuple[ResolvedAudioJoin, ...]
    audio_role: AudioRole


@dataclass(frozen=True)
class AudioConcatFiltergraph:
    """A duration-preserving FFmpeg audio-only concat filtergraph."""

    filtergraph: str
    audio_label: str
    output_duration: float
    duration_delta: float
    joins: tuple[ResolvedAudioJoin, ...]
    audio_role: AudioRole


@dataclass(frozen=True)
class TimelineDeclaration:
    """Reserved shape for a future audited A/V overlap implementation.

    The current repository contract rejects acrossfade even when this object is
    supplied; retaining the shape makes that rejection explicit for old callers
    without silently accepting an audio-only timeline change.
    """

    video_overlaps: tuple[float, ...]
    expected_output_duration: float

    def __post_init__(self) -> None:
        for overlap in self.video_overlaps:
            _positive_finite(overlap, "video overlap")
        _positive_finite(self.expected_output_duration, "expected output duration")

    @classmethod
    def for_overlaps(
        cls,
        durations: Sequence[float],
        overlaps: Sequence[float],
    ) -> "TimelineDeclaration":
        """Declare an already-chosen overlapping video timeline."""
        output = math.fsum(durations) - math.fsum(overlaps)
        return cls(tuple(float(value) for value in overlaps), output)


@dataclass(frozen=True)
class AcrossfadeFiltergraph:
    """Reserved return shape; no repository-wide acrossfade is currently built."""

    filtergraph: str
    audio_label: str
    output_duration: float
    duration_delta: float
    overlaps: tuple[float, ...]


def audio_qa_for_graph(
    graph: ConcatFiltergraph | AudioConcatFiltergraph,
    *,
    audio_role: AudioRole,
    reason: str = "",
) -> dict[str, object]:
    """Return the repository-wide, JSON-serialisable audio QA record."""
    role = _audio_role(audio_role)
    if role != graph.audio_role:
        raise AudioJoinError(
            f"audio QA role {role} does not match graph role {graph.audio_role}"
        )
    joins = [asdict(join) for join in graph.joins]
    fallback_count = sum(
        join["mode"] == "fade_through_silence" for join in joins
    )
    if fallback_count and not reason.strip():
        raise AudioJoinError(
            "fade_through_silence fallback requires a non-empty reason"
        )
    hard_cut_count = sum(
        _resolved_join_is_hard_cut(join, role) for join in graph.joins
    )
    return {
        "policy_version": AUDIO_POLICY_VERSION,
        "status": "pass",
        "role": role,
        "reason": reason,
        "duration_delta_seconds": graph.duration_delta,
        "transition_count": len(joins),
        "hard_cut_count": hard_cut_count,
        "lcut_crossfade_count": sum(
            join["mode"] == "lcut_crossfade" for join in joins
        ),
        "fade_through_silence_count": sum(
            join["mode"] == "fade_through_silence" for join in joins
        ),
        "fallback_count": fallback_count,
        "declick_count": sum(join["mode"] == "declick" for join in joins),
        "keep_count": sum(join["mode"] == "keep" for join in joins),
        "joins": joins,
    }


def not_applicable_audio_qa(
    *,
    audio_role: AudioRole,
    reason: NotApplicableReason,
    detail: str = "",
) -> dict[str, object]:
    """Record why a single-source or no-audio renderer has no edit boundary."""
    role = _audio_role(audio_role)
    if reason not in NA_AUDIO_EXPECTATIONS:
        rendered = ", ".join(sorted(NA_AUDIO_EXPECTATIONS))
        raise AudioJoinError(
            f"not_applicable reason must be one of: {rendered}"
        )
    return {
        "policy_version": AUDIO_POLICY_VERSION,
        "status": "not_applicable",
        "role": role,
        "reason": reason,
        "reason_detail": detail.strip(),
        "expected_audio_stream": NA_AUDIO_EXPECTATIONS[reason],
        "duration_delta_seconds": 0.0,
        "transition_count": 0,
        "hard_cut_count": 0,
        "lcut_crossfade_count": 0,
        "fade_through_silence_count": 0,
        "fallback_count": 0,
        "declick_count": 0,
        "keep_count": 0,
        "joins": [],
    }


def resolve_join_policy(
    previous_source: str | None,
    next_source: str | None,
    *,
    override: AudioJoinPolicy | JoinMode | None = None,
    same_source_strategy: SameSourceStrategy = "declick",
) -> AudioJoinPolicy:
    """Resolve one join without using filenames or source titles as guesses.

    Unknown source IDs are treated as cross-source, which is the safe default.
    Callers that know two same-source cuts are sample-contiguous can select
    ``same_source_strategy="keep"`` or pass a per-boundary ``keep`` override.
    """

    if same_source_strategy not in _SAME_SOURCE_STRATEGIES:
        raise AudioJoinError(
            f"unknown same-source strategy: {same_source_strategy}"
        )
    if override is not None:
        return _coerce_policy(override)
    same_source = (
        previous_source is not None
        and next_source is not None
        and previous_source == next_source
    )
    if not same_source:
        return DEFAULT_CROSS_SOURCE_POLICY
    if same_source_strategy == "keep":
        return AudioJoinPolicy.keep()
    return DEFAULT_SAME_SOURCE_POLICY


def concat_av_filter(
    segments: Sequence[AVSegment | float],
    *,
    audio_role: AudioRole,
    join_overrides: Mapping[int, AudioJoinPolicy | JoinMode] | None = None,
    tail_handles: Mapping[int, AudioTailHandle] | None = None,
    same_source_strategy: SameSourceStrategy = "declick",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channel_layout: str = DEFAULT_CHANNEL_LAYOUT,
    output_video_label: str = "vout",
    output_audio_label: str = "aout",
) -> ConcatFiltergraph:
    """Build a duration-preserving FFmpeg filtergraph for prepared A/V parts.

    Boundary ``i`` is the join between segment ``i`` and ``i + 1``.  Every
    requested fade is clamped to one quarter of its own segment, so a short
    insert cannot be consumed by its two edge ramps.  The graph never uses
    ``acrossfade`` and its output duration remains the sum of the inputs.

    ``lcut_crossfade`` is the exception that still preserves duration: the
    caller supplies an extra outgoing ``AudioTailHandle`` for that boundary.
    It is mixed over the next segment's opening while the next source fades in.
    This module does not extract handles because only the editor knows which
    post-cut source samples are legitimate and rights-cleared.
    """

    items = _coerce_segments(segments)
    role = _audio_role(audio_role)
    if not items:
        raise AudioJoinError("at least one A/V segment is required")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise AudioJoinError("sample_rate must be a positive integer")
    _bare_label(channel_layout)
    video_out = _bare_label(output_video_label)
    audio_out = _bare_label(output_audio_label)
    if video_out == audio_out:
        raise AudioJoinError("video and audio output labels must be different")

    overrides = dict(join_overrides or {})
    handles = dict(tail_handles or {})
    valid_boundaries = set(range(len(items) - 1))
    unknown_boundaries = (set(overrides) | set(handles)) - valid_boundaries
    if unknown_boundaries:
        rendered = ", ".join(str(value) for value in sorted(unknown_boundaries))
        raise AudioJoinError(f"join override has invalid boundary: {rendered}")

    joins: list[ResolvedAudioJoin] = []
    for boundary, (previous, following) in enumerate(zip(items, items[1:])):
        policy = resolve_join_policy(
            previous.source_id,
            following.source_id,
            override=overrides.get(boundary),
            same_source_strategy=same_source_strategy,
        )
        if policy.mode == "acrossfade":
            raise AudioJoinError(
                "acrossfade is not supported by the repository-wide QA contract; "
                "use a duration-preserving L-cut with a tail handle"
            )
        _validate_policy_for_role(role, policy, boundary)
        handle = handles.get(boundary)
        if policy.mode == "lcut_crossfade":
            if handle is None:
                raise AudioJoinError(
                    f"boundary {boundary} L-cut requires an AudioTailHandle"
                )
            assert policy.overlap is not None  # checked by AudioJoinPolicy
            overlap = min(
                policy.overlap,
                handle.duration,
                previous.duration / 4.0,
                following.duration / 4.0,
            )
            fade_out = 0.0
            fade_in = overlap
        elif policy.mode == "keep":
            fade_out = fade_in = 0.0
            overlap = 0.0
        else:
            fade_out = min(policy.fade_out, previous.duration / 4.0)
            fade_in = min(policy.fade_in, following.duration / 4.0)
            overlap = 0.0
        _validate_effective_resolved_join(
            policy.mode,
            fade_out=fade_out,
            fade_in=fade_in,
            boundary=boundary,
        )
        if handle is not None and policy.mode != "lcut_crossfade":
            raise AudioJoinError(
                f"boundary {boundary} has a tail handle but is not an L-cut"
            )
        joins.append(
            ResolvedAudioJoin(
                boundary=boundary,
                mode=policy.mode,
                fade_out=fade_out,
                fade_in=fade_in,
                curve=policy.curve,
                previous_source=previous.source_id,
                next_source=following.source_id,
                overlap=overlap,
                tail_handle_label=_bare_label(handle.label) if handle else None,
            )
        )

    filters: list[str] = []
    for index, segment in enumerate(items):
        video_input = _ref(segment.video_label or f"{index}:v")
        audio_input = _ref(segment.audio_label or f"{index}:a")
        video_label = f"vj{index}"
        incoming = joins[index - 1] if index else None
        audio_label = f"ab{index}" if incoming and incoming.overlap else f"aj{index}"
        filters.append(
            f"{video_input}trim=duration={_seconds(segment.duration)},"
            f"settb=AVTB,setpts=PTS-STARTPTS[{video_label}]"
        )
        audio_steps = [
            f"aresample={sample_rate}",
            "aformat="
            f"sample_fmts=fltp:sample_rates={sample_rate}:"
            f"channel_layouts={channel_layout}",
            # ``atrim`` never extends a short input.  Pad first, then trim, so
            # the emitted stream really occupies the declared A/V window and
            # cannot silently shorten the programme timeline.
            f"apad=whole_dur={_seconds(segment.duration)}",
            f"atrim=duration={_seconds(segment.duration)}",
            "asetpts=PTS-STARTPTS",
        ]
        if incoming:
            if incoming.fade_in:
                audio_steps.append(
                    "afade=t=in:st=0:"
                    f"d={_seconds(incoming.fade_in)}:curve={incoming.curve}"
                )
        if index < len(joins):
            outgoing = joins[index]
            if outgoing.fade_out:
                start = max(0.0, segment.duration - outgoing.fade_out)
                audio_steps.append(
                    f"afade=t=out:st={_seconds(start)}:"
                    f"d={_seconds(outgoing.fade_out)}:curve={outgoing.curve}"
                )
        filters.append(f"{audio_input}{','.join(audio_steps)}[{audio_label}]")
        if incoming and incoming.overlap:
            handle_label = f"ah{index - 1}"
            assert incoming.tail_handle_label is not None
            filters.append(
                f"{_ref(incoming.tail_handle_label)}"
                f"aresample={sample_rate},"
                "aformat="
                f"sample_fmts=fltp:sample_rates={sample_rate}:"
                f"channel_layouts={channel_layout},"
                f"atrim=duration={_seconds(incoming.overlap)},"
                "asetpts=PTS-STARTPTS,"
                f"afade=t=out:st=0:d={_seconds(incoming.overlap)}:"
                f"curve={incoming.curve}[{handle_label}]"
            )
            # The next segment is input 0 to amix so duration=first pins this
            # local composite to its main A/V window.  The extra tail can never
            # extend the programme or move a narration/subtitle boundary.
            filters.append(
                f"[{audio_label}][{handle_label}]"
                "amix=inputs=2:normalize=0:duration=first:"
                "dropout_transition=0,"
                f"alimiter=limit={LCUT_PEAK_LIMIT:.3f}:level=0:latency=1,"
                f"atrim=duration={_seconds(segment.duration)},"
                f"asetpts=PTS-STARTPTS[aj{index}]"
            )

    if len(items) == 1:
        filters.extend(
            [
                f"[vj0]null[{video_out}]",
                f"[aj0]anull[{audio_out}]",
            ]
        )
    else:
        inputs = "".join(f"[vj{i}][aj{i}]" for i in range(len(items)))
        filters.append(
            f"{inputs}concat=n={len(items)}:v=1:a=1"
            f"[{video_out}][{audio_out}]"
        )

    return ConcatFiltergraph(
        filtergraph=";".join(filters),
        video_label=_ref(video_out),
        audio_label=_ref(audio_out),
        output_duration=math.fsum(segment.duration for segment in items),
        duration_delta=0.0,
        joins=tuple(joins),
        audio_role=role,
    )


def concat_audio_filter(
    segments: Sequence[AVSegment | float],
    *,
    audio_role: AudioRole,
    join_overrides: Mapping[int, AudioJoinPolicy | JoinMode] | None = None,
    tail_handles: Mapping[int, AudioTailHandle] | None = None,
    same_source_strategy: SameSourceStrategy = "declick",
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channel_layout: str = DEFAULT_CHANNEL_LAYOUT,
    output_audio_label: str = "aout",
) -> AudioConcatFiltergraph:
    """Build a duration-preserving audio-only concat filtergraph.

    This is the audio-only counterpart of :func:`concat_av_filter`.  It is for
    editors that prepare ambience/music stems before they are mixed under TTS.
    Keeping that work separate means source-bed transitions can be softened
    without fading, shortening, or overlapping adjacent narration.

    ``AVSegment.audio_label`` selects each input.  ``video_label`` is ignored.
    Every input is trimmed to its declared duration, and the returned duration
    is exactly the sum of those declarations.  As with the A/V helper, a real
    L-cut requires an explicit post-cut tail handle.
    """

    items = _coerce_segments(segments)
    role = _audio_role(audio_role)
    if not items:
        raise AudioJoinError("at least one audio segment is required")
    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise AudioJoinError("sample_rate must be a positive integer")
    _bare_label(channel_layout)
    audio_out = _bare_label(output_audio_label)

    overrides = dict(join_overrides or {})
    handles = dict(tail_handles or {})
    valid_boundaries = set(range(len(items) - 1))
    unknown_boundaries = (set(overrides) | set(handles)) - valid_boundaries
    if unknown_boundaries:
        rendered = ", ".join(str(value) for value in sorted(unknown_boundaries))
        raise AudioJoinError(f"join override has invalid boundary: {rendered}")

    joins: list[ResolvedAudioJoin] = []
    for boundary, (previous, following) in enumerate(zip(items, items[1:])):
        policy = resolve_join_policy(
            previous.source_id,
            following.source_id,
            override=overrides.get(boundary),
            same_source_strategy=same_source_strategy,
        )
        if policy.mode == "acrossfade":
            raise AudioJoinError(
                "acrossfade is not supported by the repository-wide QA contract; "
                "use a duration-preserving L-cut with a tail handle"
            )
        _validate_policy_for_role(role, policy, boundary)
        handle = handles.get(boundary)
        if policy.mode == "lcut_crossfade":
            if handle is None:
                raise AudioJoinError(
                    f"boundary {boundary} L-cut requires an AudioTailHandle"
                )
            assert policy.overlap is not None
            overlap = min(
                policy.overlap,
                handle.duration,
                previous.duration / 4.0,
                following.duration / 4.0,
            )
            fade_out = 0.0
            fade_in = overlap
        elif policy.mode == "keep":
            fade_out = fade_in = 0.0
            overlap = 0.0
        else:
            fade_out = min(policy.fade_out, previous.duration / 4.0)
            fade_in = min(policy.fade_in, following.duration / 4.0)
            overlap = 0.0
        _validate_effective_resolved_join(
            policy.mode,
            fade_out=fade_out,
            fade_in=fade_in,
            boundary=boundary,
        )
        if handle is not None and policy.mode != "lcut_crossfade":
            raise AudioJoinError(
                f"boundary {boundary} has a tail handle but is not an L-cut"
            )
        joins.append(
            ResolvedAudioJoin(
                boundary=boundary,
                mode=policy.mode,
                fade_out=fade_out,
                fade_in=fade_in,
                curve=policy.curve,
                previous_source=previous.source_id,
                next_source=following.source_id,
                overlap=overlap,
                tail_handle_label=_bare_label(handle.label) if handle else None,
            )
        )

    filters: list[str] = []
    for index, segment in enumerate(items):
        audio_input = _ref(segment.audio_label or f"{index}:a")
        incoming = joins[index - 1] if index else None
        audio_label = f"ab{index}" if incoming and incoming.overlap else f"aj{index}"
        audio_steps = [
            f"aresample={sample_rate}",
            "aformat="
            f"sample_fmts=fltp:sample_rates={sample_rate}:"
            f"channel_layouts={channel_layout}",
            # Audio-only concat has the same duration contract as A/V concat:
            # a short stem gets tail silence rather than stealing time from
            # every downstream narration/subtitle boundary.
            f"apad=whole_dur={_seconds(segment.duration)}",
            f"atrim=duration={_seconds(segment.duration)}",
            "asetpts=PTS-STARTPTS",
        ]
        if incoming and incoming.fade_in:
            audio_steps.append(
                "afade=t=in:st=0:"
                f"d={_seconds(incoming.fade_in)}:curve={incoming.curve}"
            )
        if index < len(joins):
            outgoing = joins[index]
            if outgoing.fade_out:
                start = max(0.0, segment.duration - outgoing.fade_out)
                audio_steps.append(
                    f"afade=t=out:st={_seconds(start)}:"
                    f"d={_seconds(outgoing.fade_out)}:curve={outgoing.curve}"
                )
        filters.append(f"{audio_input}{','.join(audio_steps)}[{audio_label}]")
        if incoming and incoming.overlap:
            handle_label = f"ah{index - 1}"
            assert incoming.tail_handle_label is not None
            filters.append(
                f"{_ref(incoming.tail_handle_label)}"
                f"aresample={sample_rate},"
                "aformat="
                f"sample_fmts=fltp:sample_rates={sample_rate}:"
                f"channel_layouts={channel_layout},"
                f"atrim=duration={_seconds(incoming.overlap)},"
                "asetpts=PTS-STARTPTS,"
                f"afade=t=out:st=0:d={_seconds(incoming.overlap)}:"
                f"curve={incoming.curve}[{handle_label}]"
            )
            filters.append(
                f"[{audio_label}][{handle_label}]"
                "amix=inputs=2:normalize=0:duration=first:"
                "dropout_transition=0,"
                f"alimiter=limit={LCUT_PEAK_LIMIT:.3f}:level=0:latency=1,"
                f"atrim=duration={_seconds(segment.duration)},"
                f"asetpts=PTS-STARTPTS[aj{index}]"
            )

    if len(items) == 1:
        filters.append(f"[aj0]anull[{audio_out}]")
    else:
        inputs = "".join(f"[aj{i}]" for i in range(len(items)))
        filters.append(f"{inputs}concat=n={len(items)}:v=0:a=1[{audio_out}]")

    return AudioConcatFiltergraph(
        filtergraph=";".join(filters),
        audio_label=_ref(audio_out),
        output_duration=math.fsum(segment.duration for segment in items),
        duration_delta=0.0,
        joins=tuple(joins),
        audio_role=role,
    )


def build_acrossfade_audio_filter(
    segments: Sequence[AVSegment | float],
    policies: Sequence[AudioJoinPolicy],
    *,
    audio_role: AudioRole,
    timeline: TimelineDeclaration | None,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channel_layout: str = DEFAULT_CHANNEL_LAYOUT,
    output_audio_label: str = "aout",
) -> AcrossfadeFiltergraph:
    """Reject audio-only acrossfades until an auditable A/V contract exists.

    Keeping the public function as a hard failure gives older callers a useful
    migration error instead of silently shortening audio beneath an unchanged
    video/subtitle timeline.
    """

    raise AudioJoinError(
        "acrossfade is not supported by the repository-wide QA contract; "
        "use a duration-preserving L-cut with a tail handle"
    )


def _coerce_segments(segments: Sequence[AVSegment | float]) -> tuple[AVSegment, ...]:
    return tuple(
        segment if isinstance(segment, AVSegment) else AVSegment(float(segment))
        for segment in segments
    )


def _audio_role(role: AudioRole | str) -> AudioRole:
    if role not in _AUDIO_ROLES:
        rendered = ", ".join(sorted(_AUDIO_ROLES))
        raise AudioJoinError(f"audio_role must be one of: {rendered}")
    return role  # type: ignore[return-value]


def _validate_policy_for_role(
    role: AudioRole,
    policy: AudioJoinPolicy,
    boundary: int,
) -> None:
    """Prevent music-oriented transitions from ever being applied to speech.

    A renderer must identify the stem it is joining.  Speech can be kept or
    receive at most a 30 ms de-click; longer fades swallow syllables and any
    overlap makes two adjacent speakers talk at once.  Silence likewise has
    no programme bed to crossfade.
    """
    if role not in {"speech", "silence"}:
        return
    if policy.mode == "keep":
        return
    if (
        policy.mode == "declick"
        and policy.fade_out <= 0.03
        and policy.fade_in <= 0.03
    ):
        return
    raise AudioJoinError(
        f"boundary {boundary}: audio_role={role} forbids {policy.mode}; "
        "speech/silence may only keep or de-click for at most 30 ms"
    )


def _validate_effective_resolved_join(
    mode: JoinMode,
    *,
    fade_out: float,
    fade_in: float,
    boundary: int,
) -> None:
    """Reject fades which become no-ops after short-segment clamping."""
    if mode not in {"fade_through_silence", "declick"}:
        return
    if min(fade_out, fade_in) < MIN_EFFECTIVE_FADE_SECONDS:
        raise AudioJoinError(
            f"boundary {boundary}: resolved {mode} fades must both be at least "
            f"{MIN_EFFECTIVE_FADE_SECONDS:.3f}s; choose a longer segment or an "
            "explicit safe boundary policy"
        )


def _resolved_join_is_hard_cut(
    join: ResolvedAudioJoin,
    role: AudioRole,
) -> bool:
    """Derive hard-cut accounting from the actual resolved join plan."""
    if join.mode != "keep" or role in {"speech", "silence"}:
        return False
    return not (
        join.previous_source is not None
        and join.previous_source == join.next_source
    )


def _coerce_policy(policy: AudioJoinPolicy | JoinMode) -> AudioJoinPolicy:
    if isinstance(policy, AudioJoinPolicy):
        return policy
    if policy == "fade_through_silence":
        return AudioJoinPolicy.fade_through_silence()
    if policy == "keep":
        return AudioJoinPolicy.keep()
    if policy == "declick":
        return AudioJoinPolicy.declick()
    if policy == "lcut_crossfade":
        raise AudioJoinError(
            "lcut_crossfade string is incomplete; use "
            "AudioJoinPolicy.lcut_crossfade(...)"
        )
    if policy == "acrossfade":
        raise AudioJoinError(
            "acrossfade is not supported by the repository-wide QA contract; "
            "use a duration-preserving L-cut with a tail handle"
        )
    raise AudioJoinError(f"unknown audio join mode: {policy}")


def _ref(label: str) -> str:
    return f"[{_bare_label(label)}]"


def _bare_label(label: str) -> str:
    if not isinstance(label, str) or not label:
        raise AudioJoinError("FFmpeg label must be a non-empty string")
    if label.startswith("[") and label.endswith("]"):
        label = label[1:-1]
    if not _LABEL.fullmatch(label):
        raise AudioJoinError(f"invalid FFmpeg label: {label}")
    return label


def _positive_finite(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise AudioJoinError(f"{name} must be positive and finite")


def _nonnegative_finite(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise AudioJoinError(f"{name} must be non-negative and finite")


def _seconds(value: float) -> str:
    return f"{value:.3f}"


# Instantiate reusable policies only after the validation helpers exist.  The
# dataclass constructors call them during module import.
DEFAULT_CROSS_SOURCE_POLICY = AudioJoinPolicy.fade_through_silence()
DEFAULT_SAME_SOURCE_POLICY = AudioJoinPolicy.declick()


__all__ = [
    "AUDIO_POLICY_VERSION",
    "AVSegment",
    "AudioConcatFiltergraph",
    "AudioTailHandle",
    "AudioRole",
    "AcrossfadeFiltergraph",
    "AudioJoinError",
    "AudioJoinPolicy",
    "ConcatFiltergraph",
    "DEFAULT_CHANNEL_LAYOUT",
    "DEFAULT_CROSS_SOURCE_POLICY",
    "DEFAULT_DECLICK_SECONDS",
    "DEFAULT_FADE_CURVE",
    "DEFAULT_FADE_IN",
    "DEFAULT_FADE_OUT",
    "DEFAULT_SAMPLE_RATE",
    "DEFAULT_SAME_SOURCE_POLICY",
    "LCUT_PEAK_LIMIT",
    "MIN_EFFECTIVE_FADE_SECONDS",
    "NA_AUDIO_EXPECTATIONS",
    "NotApplicableReason",
    "ResolvedAudioJoin",
    "TimelineDeclaration",
    "audio_qa_for_graph",
    "build_acrossfade_audio_filter",
    "concat_audio_filter",
    "concat_av_filter",
    "not_applicable_audio_qa",
    "resolve_join_policy",
]
