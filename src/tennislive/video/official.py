"""Discover and render a short official-tour video for the daily package."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
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
TENNISTV_HOT_SHOTS_HUB = "https://www.tennistv.com/library/hot-shots"
WTA_ACCOUNT = "6041795521001"
WTA_PLAYER = "te01Hqw71"
ATP_YOUTUBE_CHANNEL_ID = "UCY_5h5zaSwN7Or4kIJDYNXA"
OFFICIAL_YOUTUBE_CHANNEL_IDS = {
    "ATP": ATP_YOUTUBE_CHANNEL_ID,
    "AO": "UCeTKJSW1NTAkf27nNmjWt5A",
    "RG": "UCF3K1Jf8hjFW8qliei8fQ3A",
    "WIMBLEDON": "UCNa8NxMgSm7m4Ii9d4QGk1Q",
    "USOPEN": "UCXbboag48Qlr78zzz6SkzkQ",
}


def official_youtube_uploads_feed(channel_id: str) -> str:
    """Use the uploads playlist feed, whose root retains the full channel id."""
    playlist_id = "UU" + channel_id[2:] if channel_id.startswith("UC") else channel_id
    return f"https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"


OFFICIAL_YOUTUBE_FEEDS = {
    tour: official_youtube_uploads_feed(channel_id)
    for tour, channel_id in OFFICIAL_YOUTUBE_CHANNEL_IDS.items()
}
ATP_YOUTUBE_FEED = OFFICIAL_YOUTUBE_FEEDS["ATP"]
_ANCHOR = re.compile(
    r'<a[^>]+href="(?P<path>/videos/\d+/[^"?#]+)"[^>]*>'
    r"(?P<body>[\s\S]{0,1800}?)</a>",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_BC_GUID = re.compile(r'"(?:bcGuid|mediaId)":"(?P<guid>\d{8,})"')
_DESCRIPTION = re.compile(r'"description":"(?P<value>(?:\\.|[^"])*)"')
_THUMBNAIL = re.compile(r'"thumbnailUrl":"(?P<value>(?:\\.|[^"])*)"')
_DATE_PUBLISHED = re.compile(
    r'"(?:datePublished|publishedAt|publishDate)":"(?P<value>[^"\\]+)"',
    re.IGNORECASE,
)
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
class OfficialYouTubeFeedEntry:
    """Structured metadata exposed by a verified official YouTube feed."""

    candidate: OfficialVideoCandidate
    video_id: str
    published_at: str
    description: str
    thumbnail_url: str


@dataclass(frozen=True)
class TennisTVHotShotEntry:
    """A Hot Shot card published by Tennis TV's public library.

    Tennis TV exposes editorial metadata publicly, while the playback token is
    issued by its entitlement service. Keeping this record separate from a
    downloadable ``OfficialVideoMetadata`` lets Actions use the public card as
    a discovery/heat signal without pretending that a locked stream is a file.
    """

    candidate: OfficialVideoCandidate
    video_id: str
    entry_id: str
    description: str
    thumbnail_url: str
    published_at: str
    duration_ms: int
    city: str
    year: str
    round_name: str
    series: str
    match_type: str
    entitlement: str
    references: tuple[str, ...]


@dataclass(frozen=True)
class OfficialVideoMetadata:
    candidate: OfficialVideoCandidate
    description: str
    thumbnail_url: str
    playback_url: str
    duration_ms: int
    fallback_url: str = ""
    published_at: str = ""
    source_width: int = 0
    source_height: int = 0
    source_bitrate: int = 0


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


_TENNISTV_CARD = re.compile(
    r"data-slider-props=(?:'(?P<single>[\s\S]*?)'|\"(?P<double>[\s\S]*?)\")",
    re.IGNORECASE,
)


def parse_tennistv_hot_shot_entries(page: str) -> list[TennisTVHotShotEntry]:
    """Parse Tennis TV's public Hot Shots library without executing its UI.

    The page carries one JSON object per card. We only keep single-match
    ``videoType=hotshots`` cards and discard countdowns/features, because the
    latter are montages and cannot be published as yesterday's one-point clip.
    """
    entries: list[TennisTVHotShotEntry] = []
    seen: set[str] = set()
    for match in _TENNISTV_CARD.finditer(page):
        raw = match.group("single") or match.group("double") or ""
        try:
            props = json.loads(html.unescape(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        video_url = str(props.get("videoUrl") or "").strip()
        video_id = str(props.get("videoId") or "").strip()
        entry_id = str(props.get("mediaId") or "").strip()
        if not video_url or not video_id or not entry_id:
            continue
        video_type = str(props.get("videoType") or "").casefold()
        tags = str(props.get("tags") or "").casefold()
        if video_type != "hotshots" and "video-type:hotshots" not in tags:
            continue
        title = html.unescape(str(props.get("title") or "")).strip()
        description = html.unescape(str(props.get("description") or "")).strip()
        if not title or not description or video_id in seen:
            continue
        haystack = _TAG.sub(" ", f"{title} {description}").casefold()
        if any(term in haystack for term in ("countdown", "top 10", "top 20", "season so far", "best shots in")):
            continue
        seen.add(video_id)
        references = tuple(
            item.strip()
            for item in str(props.get("references") or "").split(",")
            if item.strip()
        )
        entries.append(
            TennisTVHotShotEntry(
                candidate=OfficialVideoCandidate(
                    title=title,
                    url="https://www.tennistv.com" + video_url
                    if video_url.startswith("/")
                    else video_url,
                    tour="ATP",
                ),
                video_id=video_id,
                entry_id=entry_id,
                description=description,
                thumbnail_url=str(props.get("onDemandUrl") or "").strip(),
                published_at="",
                duration_ms=round(float(props.get("durationSecs") or 0) * 1000),
                city=html.unescape(str(props.get("metadataCity") or "")).strip(),
                year=str(props.get("metadataYear") or "").strip(),
                round_name=str(props.get("metadataRound") or "").strip(),
                series=str(props.get("metadataSeries") or "").strip(),
                match_type=str(props.get("matchType") or "").strip(),
                entitlement=str(props.get("entitlement") or "").strip(),
                references=references,
            )
        )
    return entries


def parse_tennistv_hot_shot_candidates(page: str) -> list[OfficialVideoCandidate]:
    """Compatibility helper returning the candidates in page order."""
    return [entry.candidate for entry in parse_tennistv_hot_shot_entries(page)]


def parse_official_youtube_feed_entries(
    page: str,
    *,
    channel_id: str,
    tour: str,
) -> list[OfficialYouTubeFeedEntry]:
    """Parse a verified channel feed, retaining metadata needed by visual QA."""
    try:
        root = ET.fromstring(page)
    except ET.ParseError as exc:
        raise VideoPipelineError("Official YouTube feed is not valid XML") from exc
    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    actual_channel = (root.findtext("yt:channelId", namespaces=namespaces) or "").strip()
    channel_identities = {actual_channel}
    if actual_channel and not actual_channel.startswith("UC"):
        # YouTube currently omits the leading ``UC`` in this feed-level field,
        # while the canonical channel URL and video metadata retain it.
        channel_identities.add("UC" + actual_channel)
    channel_identities.update(
        str(link.get("href") or "").rstrip("/").rsplit("/", 1)[-1]
        for link in root.findall("atom:link", namespaces)
        if str(link.get("rel") or "") == "alternate"
    )
    if channel_id not in channel_identities:
        raise VideoPipelineError("Official YouTube feed channel identity mismatch")
    entries: list[OfficialYouTubeFeedEntry] = []
    for entry in root.findall("atom:entry", namespaces):
        video_id = (entry.findtext("yt:videoId", namespaces=namespaces) or "").strip()
        title = (entry.findtext("atom:title", namespaces=namespaces) or "").strip()
        if not video_id or not title:
            continue
        candidate = OfficialVideoCandidate(
            title=title,
            url=f"https://www.youtube.com/watch?v={video_id}",
            tour=tour,
        )
        entries.append(
            OfficialYouTubeFeedEntry(
                candidate=candidate,
                video_id=video_id,
                published_at=(
                    entry.findtext("atom:published", namespaces=namespaces) or ""
                ).strip(),
                description=(
                    entry.findtext(
                        "media:group/media:description", namespaces=namespaces
                    )
                    or ""
                ).strip(),
                # Official HD uploads expose this deterministic highest-resolution
                # thumbnail endpoint. A missing maxres image is allowed to fail the
                # normal download/quality gate rather than falling back to a blurrier
                # social thumbnail.
                thumbnail_url=(
                    f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                ),
            )
        )
    return entries


def parse_official_youtube_feed(
    page: str,
    *,
    channel_id: str,
    tour: str,
) -> list[OfficialVideoCandidate]:
    """Parse an official channel feed and reject a mismatched channel identity."""
    return [
        entry.candidate
        for entry in parse_official_youtube_feed_entries(
            page,
            channel_id=channel_id,
            tour=tour,
        )
    ]


def fetch_youtube_video_metadata(
    candidate: OfficialVideoCandidate,
    *,
    info_fetcher: Callable[[str], dict] | None = None,
) -> OfficialVideoMetadata:
    """Resolve one official-channel video to a progressive HD playback URL."""
    if info_fetcher is None:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise VideoPipelineError("yt-dlp is required for official YouTube video") from exc

        def info_fetcher(url: str) -> dict:
            with YoutubeDL(
                {
                    "quiet": True,
                    "no_warnings": True,
                    "noplaylist": True,
                    "skip_download": True,
                }
            ) as downloader:
                return downloader.extract_info(url, download=False)

    try:
        info = info_fetcher(candidate.url)
    except Exception as exc:
        raise VideoPipelineError(f"Official YouTube metadata failed: {exc}") from exc
    expected_channel = OFFICIAL_YOUTUBE_CHANNEL_IDS.get(candidate.tour.upper(), "")
    if expected_channel and str(info.get("channel_id") or "") != expected_channel:
        raise VideoPipelineError("Official YouTube video channel identity mismatch")
    formats = [
        item
        for item in info.get("formats", [])
        if str(item.get("url", "")).startswith("https://")
        and item.get("vcodec") not in (None, "none")
        and item.get("acodec") not in (None, "none")
    ]
    progressive = max(
        formats,
        key=lambda item: (
            int(item.get("width") or 0) * int(item.get("height") or 0),
            float(item.get("tbr") or 0),
        ),
        default={},
    )
    playback_url = str(progressive.get("url") or "")
    if not playback_url:
        raise VideoPipelineError("Official YouTube video has no progressive playback URL")
    timestamp = info.get("timestamp")
    if timestamp:
        published_at = datetime.fromtimestamp(
            float(timestamp), tz=timezone.utc
        ).isoformat()
    else:
        upload_date = str(info.get("upload_date") or "")
        published_at = (
            f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00+00:00"
            if re.fullmatch(r"\d{8}", upload_date)
            else ""
        )
    return OfficialVideoMetadata(
        candidate=candidate,
        description=str(info.get("description") or ""),
        thumbnail_url=str(info.get("thumbnail") or ""),
        playback_url=playback_url,
        duration_ms=round(float(info.get("duration") or 0) * 1000),
        published_at=published_at,
        source_width=int(progressive.get("width") or 0),
        source_height=int(progressive.get("height") or 0),
        source_bitrate=round(float(progressive.get("tbr") or 0) * 1000),
    )


def fetch_tennistv_video_metadata(
    candidate: OfficialVideoCandidate,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 30,
    jwt_token: str | None = None,
) -> OfficialVideoMetadata:
    """Resolve a Tennis TV card through its documented entitlement endpoint.

    GitHub Actions must not reuse a browser cookie. If the public entitlement
    service does not return a playback token, this function fails explicitly;
    the caller can then try an ATP/WTA public mirror or write a skipped
    manifest. A token may be supplied as the opt-in ``TENNISTV_JWT`` secret.
    """
    headers = {"User-Agent": "tennislive/0.1", "account": "atpmedia"}
    token = jwt_token or os.getenv("TENNISTV_JWT", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    page_response = get(candidate.url, headers=headers, timeout=timeout)
    page = html.unescape(_response_text(page_response))
    entry_match = re.search(r'data-entry-id="(?P<entry>[^" ]+)"', page)
    if not entry_match:
        raise VideoPipelineError("Tennis TV page does not expose a media entry id")
    entry_id = entry_match.group("entry")

    def _itemprop(name: str) -> str:
        match = re.search(
            rf'<span[^>]+itemprop="{re.escape(name)}"[^>]+content="([^"]*)"',
            page,
            re.IGNORECASE,
        )
        return html.unescape(match.group(1)).strip() if match else ""

    entitlement_response = get(
        f"https://api.tennistv.com/entitlementcheck/v1/videoentitlements/{entry_id}",
        headers=headers,
        timeout=timeout,
    )
    entitlement_response.raise_for_status()
    entitlement = entitlement_response.json()
    access_token = str(entitlement.get("access_token") or "").strip()
    if not access_token:
        raise VideoPipelineError(
            "Tennis TV entitlement did not return a playback token; no browser login is used"
        )
    # StreamAMG's public player accepts this HLS manifest URL with the token.
    playback_url = (
        "https://open.http.mp.streamamg.com/p/atpmedia/sp/atpmedia00/"
        f"playManifest/entryId/{entry_id}/format/applehttp/protocol/https/a.m3u8"
        f"?access_token={access_token}"
    )
    duration = _itemprop("duration")
    duration_ms = 0
    match = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", duration)
    if match:
        duration_ms = round(
            (int(match.group(1) or 0) * 60 + float(match.group(2) or 0)) * 1000
        )
    published_at = _itemprop("uploadDate")
    if published_at and published_at.endswith("Z"):
        published_at = published_at[:-1] + "+00:00"
    thumbnail_url = _itemprop("thumbnailUrl")
    width_match = re.search(r"[?&]width=(\d+)", thumbnail_url)
    height_match = re.search(r"[?&]height=(\d+)", thumbnail_url)
    return OfficialVideoMetadata(
        candidate=candidate,
        description=_itemprop("description"),
        thumbnail_url=thumbnail_url,
        playback_url=playback_url,
        duration_ms=duration_ms,
        published_at=published_at,
        source_width=int(width_match.group(1)) if width_match else 1920,
        source_height=int(height_match.group(1)) if height_match else 1080,
    )


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
        is_title_match = bool(
            re.search(r"\b(claim|win|wins|won|capture|lift).{0,35}\b(title|trophy)\b", haystack)
            or re.search(r"\btitle\s+over\b", haystack)
        )
        if "final" in haystack or "championship" in haystack or is_title_match:
            score += 220
        elif "champions reel" in haystack or "road to the title" in haystack:
            score += 80
        elif "interview" in haystack:
            score += 65
        elif "highlights" in haystack:
            score += 45
        if "hot shot" in haystack:
            score -= 30
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
    published_match = _DATE_PUBLISHED.search(page)

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
    progressive_sources = [
        source
        for source in sources
        if (
            source.get("container") == "MP4" or source.get("type") == "video/mp4"
        )
        and str(source.get("src", "")).startswith("https://")
    ]
    progressive_source = max(
        progressive_sources,
        key=lambda source: (
            int(source.get("width") or 0) * int(source.get("height") or 0),
            int(source.get("avg_bitrate") or 0),
        ),
        default={},
    )
    progressive = progressive_source.get("src", "")
    hls = next(
        (
            source.get("src", "")
            for source in sources
            if source.get("type") == "application/x-mpegURL"
            and str(source.get("src", "")).startswith("https://")
        ),
        "",
    )
    playback_url = str(hls or progressive)
    if not playback_url:
        raise VideoPipelineError("WTA playback response has no HTTPS video stream")
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
        playback_url=playback_url,
        duration_ms=int(playback.get("duration") or 0),
        fallback_url=str(progressive if hls else ""),
        published_at=str(
            playback.get("published_at")
            or playback.get("created_at")
            or (published_match.group("value") if published_match else "")
        ),
        source_width=int(progressive_source.get("width") or 0),
        source_height=int(progressive_source.get("height") or 0),
        source_bitrate=int(progressive_source.get("avg_bitrate") or 0),
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


def _montage_starts(metadata: OfficialVideoMetadata, clip_seconds: int) -> list[float]:
    """Sample an official title reel across the full tournament story."""
    title = metadata.candidate.title.casefold()
    is_reel = "champions reel" in title or "road to the title" in title
    source_seconds = metadata.duration_ms / 1000
    if not is_reel or source_seconds <= clip_seconds + 4:
        return [0.0]
    segment_seconds = clip_seconds / 4
    last_start = max(0.0, source_seconds - segment_seconds)
    return [
        min(2.0, last_start),
        last_start * 0.34,
        last_start * 0.68,
        last_start,
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
        "FontName=Noto Sans CJK SC,FontSize=18,Bold=-1,"
        "PrimaryColour=&H00F7F7F7,OutlineColour=&H005F5AFF,"
        "BorderStyle=1,BackColour=&H00000000,Outline=1.6,Shadow=0.7,"
        "MarginV=28,Alignment=2'"
    )
    starts = _montage_starts(metadata, clip_seconds)
    segment_seconds = clip_seconds / len(starts)
    input_args: list[str] = []
    for start in starts:
        input_args.extend(
            [
                "-reconnect",
                "1",
                "-reconnect_streamed",
                "1",
                "-reconnect_delay_max",
                "5",
                "-ss",
                f"{start:.3f}",
                "-t",
                f"{segment_seconds:.3f}",
                "-i",
                metadata.playback_url,
            ]
        )
    if len(starts) > 1:
        concat_inputs = "".join(f"[{index}:v][{index}:a]" for index in range(len(starts)))
        montage = f"{concat_inputs}concat=n={len(starts)}:v=1:a=1[montagev][outa];"
        video_input = "[montagev]"
        audio_map = ["-map", "[outa]"]
    else:
        montage = ""
        video_input = "[0:v]"
        audio_map = ["-map", "0:a?"]
    filters = montage + (
        f"{video_input}split=2[bg][fg];"
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
        *input_args,
        "-filter_complex",
        filters,
        "-map",
        "[outv]",
        *audio_map,
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
    render_timeout = 600 if len(starts) > 1 else 240
    try:
        runner(command, check=True, timeout=render_timeout)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        if not metadata.fallback_url:
            raise VideoPipelineError(f"Official video render failed: {exc}") from exc
        fallback_command = [
            metadata.fallback_url if part == metadata.playback_url else part for part in command
        ]
        try:
            runner(fallback_command, check=True, timeout=render_timeout)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as fallback_exc:
            raise VideoPipelineError(
                f"Official video render failed on primary and fallback sources: {fallback_exc}"
            ) from fallback_exc
    if not output_path.is_file():
        raise VideoPipelineError("Official video render created no output")
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": asdict(metadata.candidate),
        "description": metadata.description,
        "thumbnail_url": metadata.thumbnail_url,
        "source_duration_ms": metadata.duration_ms,
        "clip_seconds": clip_seconds,
        "montage_starts_seconds": starts,
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
