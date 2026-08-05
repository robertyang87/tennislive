"""Rights-gated localization for user-provided video assets."""

from .pipeline import (
    ChatTranslator,
    RightsError,
    RightsManifest,
    SubtitleCue,
    VideoPipelineError,
    burn_subtitles,
    load_rights_manifest,
    localize_video,
    parse_srt,
    render_srt,
)

__all__ = [
    "ChatTranslator",
    "RightsError",
    "RightsManifest",
    "SubtitleCue",
    "VideoPipelineError",
    "burn_subtitles",
    "load_rights_manifest",
    "localize_video",
    "parse_srt",
    "render_srt",
]
