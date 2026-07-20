"""Discover and render a short official-tour video for the daily package."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import requests

from ..digest import Digest
from ..zh import PLAYER_ZH, player_zh
from .pipeline import (
    GitHubModelsTranslator,
    SubtitleCue,
    VideoPipelineError,
    render_srt,
    translate_cues,
)

WTA_VIDEO_HUB = "https://www.wtatennis.com/videos/"
WTA_ACCOUNT = "6041795521001"
WTA_PLAYER = "te01Hqw71"
_ANCHOR = re.compile(
    r'<a[^>]+href="(?P<path>/videos/\d+/[^"?#]+)"[^>]*>'
    r"(?P<body>[\s\S]{0,1800}?)</a>",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_BC_GUID = re.compile(r'"(?:bcGuid|mediaId)":"(?P<guid>\d{8,})"')
_DESCRIPTION = re.compile(r'"description":"(?P<value>(?:\\.|[^"])*)"')
_THUMBNAIL = re.compile(r'"thumbnailUrl":"(?P<value>(?:\\.|[^"])*)"')
_POLICY_KEY = re.compile(r"BCpk[A-Za-z0-9_-]{20,}")
_ORDINALS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
}
_CITY_ZH = {"athens": "雅典"}


@dataclass(frozen=True)
class OfficialVideoCandidate:
    title: str
    url: str
    tour: str = "WTA"


@dataclass(frozen=True)
class OfficialVideoMetadata:
    candidate: OfficialVideoCandidate
    description: str
    thumbnail_url: str
    playback_url: str
    duration_ms: int


def _response_text(response: object) -> str:
    response.raise_for_status()
    return str(response.text)


def parse_wta_video_candidates(page: str) -> list[OfficialVideoCandidate]:
    """Extract the ordered, public video links from the WTA video hub."""
    found: list[OfficialVideoCandidate] = []
    seen: set[str] = set()
    for match in _ANCHOR.finditer(page):
        path = match.group("path")
        if path in seen:
            continue
        title = html.unescape(_TAG.sub(" ", match.group("body")))
        title = re.sub(r"\s+", " ", title).strip()
        title = re.sub(r"\s*Watch Now\s*$", "", title, flags=re.IGNORECASE)
        if not title:
            continue
        seen.add(path)
        found.append(
            OfficialVideoCandidate(
                title=title,
                url="https://www.wtatennis.com" + path,
            )
        )
    return found


def _digest_name_tokens(digest: Digest) -> set[str]:
    tokens: set[str] = set()
    for match in [*digest.results, *digest.schedule]:
        for player in [*match.home, *match.away]:
            name = re.sub(r"[^a-z0-9 ]", "", player.name.casefold())
            if not name:
                continue
            tokens.add(name)
            family = name.split()[-1]
            if len(family) >= 4:
                tokens.add(family)
    return tokens


def select_wta_video_candidate(
    digest: Digest,
    candidates: list[OfficialVideoCandidate],
) -> OfficialVideoCandidate | None:
    """Prefer a fresh video whose title names a player in today's package."""
    tokens = _digest_name_tokens(digest)
    scored: list[tuple[int, int, OfficialVideoCandidate]] = []
    for index, candidate in enumerate(candidates):
        haystack = re.sub(r"[^a-z0-9 ]", "", candidate.title.casefold())
        score = sum(100 if " " in token else 35 for token in tokens if token in haystack)
        if score:
            scored.append((score, -index, candidate))
    return max(scored, default=(0, 0, None))[2]


def discover_wta_video(
    digest: Digest,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
) -> OfficialVideoCandidate | None:
    response = get(
        WTA_VIDEO_HUB,
        headers={"User-Agent": "tennislive/0.1 (+https://github.com/robertyang87/tennislive)"},
        timeout=timeout,
    )
    return select_wta_video_candidate(
        digest,
        parse_wta_video_candidates(_response_text(response))[:40],
    )


def _decode_json_string(value: str) -> str:
    return json.loads('"' + value + '"')


def fetch_wta_video_metadata(
    candidate: OfficialVideoCandidate,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 30,
) -> OfficialVideoMetadata:
    headers = {"User-Agent": "Mozilla/5.0 tennislive/0.1"}
    page = html.unescape(_response_text(get(candidate.url, headers=headers, timeout=timeout)))
    guid_match = _BC_GUID.search(page)
    if not guid_match:
        raise VideoPipelineError("WTA page does not expose a Brightcove video id")
    description_match = _DESCRIPTION.search(page)
    thumbnail_match = _THUMBNAIL.search(page)

    player_url = (
        f"https://players.brightcove.net/{WTA_ACCOUNT}/"
        f"{WTA_PLAYER}_default/index.min.js"
    )
    player_js = _response_text(get(player_url, headers=headers, timeout=timeout))
    policy_match = _POLICY_KEY.search(player_js)
    if not policy_match:
        raise VideoPipelineError("WTA player policy key was not found")
    api_url = (
        f"https://edge.api.brightcove.com/playback/v1/accounts/{WTA_ACCOUNT}/"
        f"videos/{guid_match.group('guid')}"
    )
    playback_response = get(
        api_url,
        headers={"Accept": f"application/json;pk={policy_match.group(0)}"},
        timeout=timeout,
    )
    playback_response.raise_for_status()
    playback = playback_response.json()
    sources = playback.get("sources", [])
    hls = next(
        (
            source.get("src", "")
            for source in sources
            if source.get("type") == "application/x-mpegURL"
            and str(source.get("src", "")).startswith("https://")
        ),
        "",
    )
    if not hls:
        raise VideoPipelineError("WTA playback response has no HTTPS HLS stream")
    return OfficialVideoMetadata(
        candidate=candidate,
        description=(
            _decode_json_string(description_match.group("value"))
            if description_match
            else ""
        ),
        thumbnail_url=(
            _decode_json_string(thumbnail_match.group("value"))
            if thumbnail_match
            else str(playback.get("poster", ""))
        ),
        playback_url=hls,
        duration_ms=int(playback.get("duration") or 0),
    )


def _source_cues(metadata: OfficialVideoMetadata, clip_seconds: int) -> list[SubtitleCue]:
    sentences = [metadata.candidate.title]
    description = re.sub(r"\bNo\.\s+(?=\d)", "No.\u2060", metadata.description)
    sentences.extend(
        sentence.replace("\u2060", " ").strip()
        for sentence in re.split(r"(?<=[.!?])\s+|[,;]\s+", description)
        if sentence.strip()
    )
    sentences = sentences[:4]
    if not sentences:
        raise VideoPipelineError("Official video has no title or description to translate")
    slot = clip_seconds * 1000 // len(sentences)
    return [
        SubtitleCue(
            index=index,
            start_ms=(index - 1) * slot,
            end_ms=clip_seconds * 1000 if index == len(sentences) else index * slot,
            text=text,
        )
        for index, text in enumerate(sentences, start=1)
    ]


def _curated_chinese_cues(
    metadata: OfficialVideoMetadata,
    clip_seconds: int,
) -> list[SubtitleCue] | None:
    """Build concise fact captions when the official description is structured."""
    combined = f"{metadata.candidate.title} {metadata.description}"
    player_en = next((name for name in PLAYER_ZH if name in combined), "")
    career = re.search(
        r"her (?P<ordinal>\w+) career WTA(?: Tour.*?)? title",
        metadata.description,
        re.IGNORECASE,
    )
    since_slam = re.search(
        r"first since (?P<slam>Wimbledon|Roland Garros|the US Open|the Australian Open) "
        r"(?P<year>\d{4})",
        metadata.description,
        re.IGNORECASE,
    )
    city_history = re.search(
        r"first time a WTA tournament had been held in (?P<city>[A-Za-z ]+) since "
        r"(?P<year>\d{4})",
        metadata.description,
        re.IGNORECASE,
    )
    ordinal = _ORDINALS.get(career.group("ordinal").casefold()) if career else None
    if not (player_en and ordinal and since_slam and city_history):
        return None
    city_en = city_history.group("city").strip()
    city = _CITY_ZH.get(city_en.casefold(), city_en)
    slam = {
        "wimbledon": "温网",
        "roland garros": "法网",
        "the us open": "美网",
        "the australian open": "澳网",
    }[since_slam.group("slam").casefold()]
    lines = [
        f"{player_zh(player_en)}｜{city}夺冠之路",
        f"生涯第 {ordinal} 座 WTA 单打冠军",
        f"这是她自 {since_slam.group('year')} 年{slam}后的第一冠",
        f"{city}自 {city_history.group('year')} 年以来首次迎回 WTA 赛事",
    ]
    slot = clip_seconds * 1000 // len(lines)
    return [
        SubtitleCue(
            index=index,
            start_ms=(index - 1) * slot,
            end_ms=clip_seconds * 1000 if index == len(lines) else index * slot,
            text=text,
        )
        for index, text in enumerate(lines, start=1)
    ]


def render_wta_video(
    metadata: OfficialVideoMetadata,
    output_dir: Path,
    *,
    clip_seconds: int = 38,
    ffmpeg_bin: str = "ffmpeg",
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    """Render a short vertical clip with translated contextual subtitles."""
    if shutil.which(ffmpeg_bin) is None:
        raise VideoPipelineError(f"ffmpeg executable not found: {ffmpeg_bin}")
    localized = _curated_chinese_cues(metadata, clip_seconds)
    if localized is None:
        translator = GitHubModelsTranslator()
        localized = translate_cues(_source_cues(metadata, clip_seconds), translator)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    subtitle_path = output_dir / "official-highlight.zh-CN.srt"
    output_path = output_dir / "official-highlight.mp4"
    subtitle_path.write_text(render_srt(localized), encoding="utf-8")

    escaped = subtitle_path.as_posix().replace(":", r"\:").replace("'", r"\'")
    subtitle_filter = (
        f"subtitles=filename='{escaped}':force_style='"
        "FontName=Noto Sans CJK SC,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00101814,BorderStyle=3,BackColour=&H9005100D,"
        "Outline=2,Shadow=0,MarginV=70,Alignment=2'"
    )
    filters = (
        "[0:v]split=2[bg][fg];"
        "[bg]scale=1080:1440:force_original_aspect_ratio=increase,"
        "crop=1080:1440,gblur=sigma=28,eq=brightness=-0.3[bg2];"
        "[fg]scale=1080:-2[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,{subtitle_filter}[outv]"
    )
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        metadata.playback_url,
        "-t",
        str(clip_seconds),
        "-filter_complex",
        filters,
        "-map",
        "[outv]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "23",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        runner(command, check=True, timeout=240)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise VideoPipelineError(f"Official video render failed: {exc}") from exc
    if not output_path.is_file():
        raise VideoPipelineError("Official video render created no output")
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": asdict(metadata.candidate),
        "description": metadata.description,
        "thumbnail_url": metadata.thumbnail_url,
        "source_duration_ms": metadata.duration_ms,
        "clip_seconds": clip_seconds,
        "output": output_path.name,
    }
    (output_dir / "official-video.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output_path


def generate_official_video(digest: Digest, output_dir: Path) -> Path | None:
    """Best-effort discovery and rendering entry point used by GitHub Actions."""
    if os.environ.get("TENNISLIVE_OFFICIAL_VIDEO", "off").casefold() != "on":
        return None
    candidate = discover_wta_video(digest)
    if candidate is None:
        return None
    return render_wta_video(fetch_wta_video_metadata(candidate), output_dir)
