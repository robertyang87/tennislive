"""Build an auditable vertical ``yesterday's point`` package.

The source must already be an official single-point clip.  The renderer keeps
that source clip intact and places its full 16:9 frame inside a 9:16 canvas;
it never guesses rally boundaries or follows a player with an unverified crop.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

from ..digest import Digest
from ..models import Match
from ..render.hashtags import hashtag_count, limit_hashtags
from ..zh import player_zh, round_zh, tournament_zh
from .official import (
    ATP_YOUTUBE_CHANNEL_ID,
    ATP_YOUTUBE_FEED,
    OFFICIAL_YOUTUBE_CHANNEL_IDS,
    OFFICIAL_YOUTUBE_FEEDS,
    TENNISTV_HOT_SHOTS_API,
    TENNISTV_HOT_SHOTS_HUB,
    TENNISTV_YOUTUBE_CHANNEL_ID,
    TENNISTV_YOUTUBE_FEED,
    WTA_VIDEO_HUB,
    OfficialVideoCandidate,
    OfficialVideoMetadata,
    fetch_youtube_video_metadata,
    fetch_tennistv_video_metadata,
    fetch_wta_video_metadata,
    parse_official_youtube_feed,
    parse_tennistv_hot_shot_api_entries,
    parse_tennistv_hot_shot_entries,
    parse_wta_video_candidates,
    search_official_youtube_candidates,
)
from .pipeline import AssOverlay, SubtitleCue, VideoPipelineError, render_ass, render_srt

BEIJING = ZoneInfo("Asia/Shanghai")
MIN_POINT_SECONDS = 6.0
MAX_POINT_SECONDS = 120.0
# Resolution is recorded for observability, not used as a hard publish gate.
MIN_OUTPUT_FPS = 23.0
# 3:4 portrait, matching the project's card-image canvas so a Hot Shots video
# sits in the same aspect ratio as the rest of a mixed-media Xiaohongshu post.
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1440
CAPTION_FONT_SIZE = 56
CAPTION_MARGIN_V = 300
# Same corner-mark placement as the card images (render/cards.py): brand icon
# + name top-left, "@handle · TENNIS JETLAG" bottom-right.
BRAND_TEXT = "网球时差"
BRAND_ICON_PATH = Path(__file__).resolve().parents[3] / "assets" / "logo" / "tennis-clock-icon.png"
BRAND_ICON_SIZE = 64
BRAND_ICON_MARGIN = 40
BRAND_TOP_FONT_SIZE = 34
BRAND_TOP_MARGIN_L = BRAND_ICON_MARGIN + BRAND_ICON_SIZE + 12
BRAND_TOP_MARGIN_V = 44
BRAND_BOTTOM_FONT_SIZE = 26
BRAND_BOTTOM_MARGIN_R = BRAND_ICON_MARGIN
BRAND_BOTTOM_MARGIN_V = BRAND_ICON_MARGIN

_OFFICIAL_BEST_RE = re.compile(
    r"\b(?P<kind>point|play|shot|rally)\s+of\s+(?:the\s+)?"
    r"(?P<scope>day|match)\b"
)
_NON_POINT_TERMS = (
    "highlights",
    "champions reel",
    "road to the title",
    "interview",
    "press conference",
    "practice",
    "top 10",
    "top 20",
    "best of",
    "countdown",
    "season so far",
    "montage",
)
_OFFICIAL_HOSTS = {
    "www.wtatennis.com": "WTA 官方视频",
    "wtatennis.com": "WTA 官方视频",
    "www.atptour.com": "ATP Tour 官方视频",
    "atptour.com": "ATP Tour 官方视频",
    "www.ausopen.com": "澳网官方视频",
    "ausopen.com": "澳网官方视频",
    "www.rolandgarros.com": "法网官方视频",
    "rolandgarros.com": "法网官方视频",
    "www.wimbledon.com": "温网官方视频",
    "wimbledon.com": "温网官方视频",
    "www.usopen.org": "美网官方视频",
    "usopen.org": "美网官方视频",
    "www.tennistv.com": "Tennis TV / ATP Media",
    "tennistv.com": "Tennis TV / ATP Media",
}
_OFFICIAL_YOUTUBE_TOURS = {
    "ATP": "ATP Tour 官方视频",
    "WTA": "WTA 官方视频",
    "AO": "澳网官方视频",
    "RG": "法网官方视频",
    "WIMBLEDON": "温网官方视频",
    "USOPEN": "美网官方视频",
}
_SLAM_EVENT_ALIASES = {
    "AO": ("australian open",),
    "RG": ("roland garros", "french open"),
    "WIMBLEDON": ("wimbledon",),
    "USOPEN": ("us open", "u s open"),
}


@dataclass(frozen=True)
class PointSelection:
    metadata: OfficialVideoMetadata
    match: Match
    published_at: str
    source_label: str
    editorial_score: int
    consensus_rank: int
    consensus_basis: str
    consensus_score: int
    consensus_signals: tuple[dict, ...]
    complete_point_evidence: str


@dataclass(frozen=True)
class VideoProbe:
    width: int
    height: int
    duration_seconds: float
    fps: float
    codec: str
    size_bytes: int


def _clean(value: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", html.unescape(value).casefold())


def _player_tokens(match: Match) -> set[str]:
    tokens: set[str] = set()
    for player in [*match.home, *match.away]:
        name = _clean(player.name)
        if not name:
            continue
        tokens.add(name)
        parts = name.split()
        tokens.update(
            part
            for part in dict.fromkeys(parts[:1] + parts[-1:])
            if len(part) >= 3
        )
    return tokens


def _match_player_matches(player, text: str, participants: list) -> bool:
    """Allow a unique family-name display without reusing a shared token."""
    cleaned_name = _clean(player.name).strip()
    if not cleaned_name:
        return False
    if re.search(
        rf"(?<![a-z0-9]){re.escape(cleaned_name)}(?![a-z0-9])",
        text,
    ):
        return True
    parts = cleaned_name.split()
    aliases = [parts[-1]]
    if str(player.country or "").upper() in {"CHN", "HKG", "TPE", "JPN", "KOR"}:
        aliases.append(parts[0])
    other_tokens = {
        token
        for other in participants
        if other is not player
        for token in _clean(other.name).split()
    }
    return any(
        len(alias) >= 3
        and alias not in other_tokens
        and re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text)
        for alias in dict.fromkeys(aliases)
    )


_GENERIC_EVENT_TERMS = {
    "open",
    "tennis",
    "championship",
    "championships",
    "masters",
    "international",
    "classic",
    "ladies",
}


def _event_matches(match: Match, text: str) -> bool:
    """Require a distinctive tournament or host-city anchor."""
    values = [match.tournament.name, match.tournament.city or ""]
    terms: set[str] = set()
    for value in values:
        terms.update(
            token
            for token in _clean(value).split()
            if len(token) >= 4 and token not in _GENERIC_EVENT_TERMS
        )
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text)
        for term in terms
    )


def _slam_event_matches(tour: str, match: Match, text: str) -> bool:
    aliases = _SLAM_EVENT_ALIASES.get(tour, ())
    if not aliases:
        return False
    match_text = _clean(
        f"{match.tournament.name} {match.tournament.city or ''}"
    )
    return any(alias in match_text for alias in aliases) and any(
        alias in text for alias in aliases
    )


def _candidate_matches_tour_and_event(
    match: Match,
    metadata: OfficialVideoMetadata,
    text: str,
) -> bool:
    tour = metadata.candidate.tour.upper()
    if tour in {"ATP", "WTA"}:
        return match.tour.value == tour
    if tour not in _SLAM_EVENT_ALIASES or not _slam_event_matches(tour, match, text):
        return False
    # Slam channels publish archive videos throughout the year.  Requiring the
    # edition in the page text prevents a fresh upload of an old match from
    # being attached to yesterday's current-edition score.
    match_year = str(match.start_utc.year) if match.start_utc is not None else ""
    return bool(match_year and re.search(rf"(?<!\d){match_year}(?!\d)", text))


def _linked_match(matches: Iterable[Match], metadata: OfficialVideoMetadata) -> Match | None:
    """Resolve a clip to one match without guessing an opponent or score.

    Naming both sides is conclusive.  A one-player official title is accepted
    only when it also names the event and maps to exactly one yesterday match.
    """
    text = _clean(f"{metadata.candidate.title} {metadata.description}")
    exact: list[Match] = []
    one_side_with_event: list[Match] = []
    for match in matches:
        if not _candidate_matches_tour_and_event(match, metadata, text):
            continue
        participants = [*match.home, *match.away]
        side_hits = [
            any(_match_player_matches(player, text, participants) for player in side)
            for side in (match.home, match.away)
        ]
        if all(side_hits):
            exact.append(match)
        elif any(side_hits) and (
            _event_matches(match, text)
            or metadata.candidate.tour.upper() in _SLAM_EVENT_ALIASES
        ):
            one_side_with_event.append(match)
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    if len(one_side_with_event) == 1:
        return one_side_with_event[0]
    return None


def _beijing_match_date(match: Match) -> date | None:
    if match.start_utc is None:
        return None
    value = match.start_utc
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(BEIJING).date()


def yesterday_matches(digest: Digest) -> list[Match]:
    """Return completed singles that can be proven to belong to yesterday."""
    return [
        match
        for match in digest.results
        if match.is_singles
        and match.status.is_final
        and _beijing_match_date(match) == digest.yesterday
    ]


def is_explicit_single_point(title: str, description: str = "") -> bool:
    """Accept one official day/match point or a single official hot shot.

    ``Hot Shot`` is a strong editorial/heat signal from ATP Media/Tennis TV,
    but it is deliberately ranked below an explicit ``Point/Play/Shot/Rally
    of the Day`` label. This keeps the automated package useful on days when
    no outlet names a formal daily winner without pretending that a hot shot
    is a consensus award.
    """
    text = _clean(f"{title} {description}")
    if any(term in text for term in _NON_POINT_TERMS):
        return False
    # A numeric shot-count usually describes a rally package or montage, not
    # one auditable point clip.
    if re.search(r"\b\d+\s+shot\s+rally\b", text):
        return False
    return bool(_OFFICIAL_BEST_RE.search(text) or re.search(r"\bhot\s+shot\b", text))


def official_best_signal(title: str, description: str = "") -> tuple[int, str] | None:
    """Return the editorial tier for a point clip.

    Tier 3 is an explicit daily-best label, tier 2 is a match-best label, and
    tier 1 is an official single ``Hot Shot``. The latter is publishable when
    it clears the same date, match-linkage, duration, and full-source
    gates, but its manifest is marked as a hot-shot signal rather than a best
    of day claim.
    """
    text = _clean(f"{title} {description}")
    scopes = {match.group("scope") for match in _OFFICIAL_BEST_RE.finditer(text)}
    if "day" in scopes:
        return 3, "official-daily-best"
    if "match" in scopes:
        return 2, "official-match-best"
    if re.search(r"\bhot\s+shot\b", text) and not any(
        term in text for term in _NON_POINT_TERMS
    ):
        return 1, "official-hot-shot"
    return None


def _is_hd_source(width: int, height: int) -> bool:
    """Legacy helper retained for callers; resolution is no longer a gate."""
    return width >= 0 and height >= 0


def _parse_source_time(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _published_near_yesterday(value: str, digest: Digest) -> bool:
    """Allow official uploads through the following Beijing day."""
    parsed = _parse_source_time(value)
    if parsed is None:
        return False
    local_date = parsed.astimezone(BEIJING).date()
    return local_date in {digest.yesterday, digest.today}


def _official_source_label(url: str, tour: str = "") -> str:
    host = (urlparse(url).hostname or "").casefold()
    direct = _OFFICIAL_HOSTS.get(host, "")
    if direct:
        return direct
    if host in {"youtube.com", "www.youtube.com", "youtu.be"}:
        return _OFFICIAL_YOUTUBE_TOURS.get(tour.upper(), "")
    return ""


def _round_weight(round_name: str | None) -> int:
    text = (round_name or "").casefold()
    if "final" in text and "semi" not in text:
        return 36
    if "semi" in text:
        return 24
    if "quarter" in text:
        return 16
    return 4


def _consensus_evidence(
    metadata: OfficialVideoMetadata,
    *,
    source_label: str,
    consensus_rank: int,
) -> tuple[int, tuple[dict, ...]] | None:
    official_signal = {
        "kind": (
            "official-best-designation"
            if consensus_rank > 1
            else "official-hot-shot"
        ),
        "scope": (
            "day"
            if consensus_rank == 3
            else "match"
            if consensus_rank == 2
            else "hot-shot"
        ),
        "source": source_label,
        "title": metadata.candidate.title,
        "url": metadata.candidate.url,
        "independent": False,
    }
    # Match/news/search heat describes the event or players, not this exact
    # rally. A formal daily-best label is the strongest signal; Tennis TV / an
    # official tour's single Hot Shot is a lower, but still publishable, heat
    # signal. The manifest keeps the distinction so copy never calls it
    # "全日最佳" by accident.
    if consensus_rank == 3:
        return 100, (official_signal,)
    if consensus_rank == 2:
        # A match-best label is useful context, but it is not a daily heat
        # signal on its own. Keep the existing corroboration gate here.
        return None
    if consensus_rank == 1:
        return 72, (official_signal,)
    return None


def select_daily_point(
    digest: Digest,
    metadata_items: Iterable[OfficialVideoMetadata],
) -> PointSelection | None:
    """Rank only verified, recent, full-source single-point clips."""
    matches = yesterday_matches(digest)
    ranked: list[tuple[int, int, PointSelection]] = []
    for order, metadata in enumerate(metadata_items):
        source_label = _official_source_label(
            metadata.candidate.url, metadata.candidate.tour
        )
        if not source_label:
            continue
        if not is_explicit_single_point(
            metadata.candidate.title, metadata.description
        ):
            continue
        consensus = official_best_signal(
            metadata.candidate.title, metadata.description
        )
        if consensus is None:
            continue
        consensus_rank, consensus_basis = consensus
        duration = metadata.duration_ms / 1000
        if not MIN_POINT_SECONDS <= duration <= MAX_POINT_SECONDS:
            continue
        if not _published_near_yesterday(metadata.published_at, digest):
            continue
        haystack = _clean(
            f"{metadata.candidate.title} {metadata.description}"
        )
        match = _linked_match(matches, metadata)
        if match is None:
            continue
        consensus_evidence = _consensus_evidence(
            metadata,
            source_label=source_label,
            consensus_rank=consensus_rank,
        )
        if consensus_evidence is None:
            continue
        consensus_score, consensus_signals = consensus_evidence
        named_players = sum(token in haystack for token in _player_tokens(match))
        china = any(p.country == "CHN" for p in [*match.home, *match.away])
        # Prefer a clearer rendition when several official mirrors describe
        # the same point, without rejecting a lower-resolution source.
        resolution_bonus = min(
            60,
            (metadata.source_width * metadata.source_height) // 50_000,
        )
        score = (
            consensus_rank * 1000
            + named_players * 35
            + _round_weight(match.round_name)
            + match.media_heat
            + match.search_heat
            + (30 if china else 0)
            + (18 if "rally" in haystack else 10)
            + resolution_bonus
        )
        ranked.append(
            (
                score,
                -order,
                PointSelection(
                    metadata=metadata,
                    match=match,
                    published_at=metadata.published_at,
                    source_label=source_label,
                    editorial_score=score,
                    consensus_rank=consensus_rank,
                    consensus_basis=consensus_basis,
                    consensus_score=consensus_score,
                    consensus_signals=consensus_signals,
                    complete_point_evidence=(
                        "官方标题或说明明确标注当日/全场最佳回合，"
                        "成片保留源视频从 0 秒到结尾"
                    ),
                ),
            )
        )
    selections = [item[2] for item in ranked]
    return _unique_consensus_pick(selections)


def _unique_consensus_pick(
    selections: Iterable[PointSelection],
) -> PointSelection | None:
    """Return one auditable consensus leader; an exact tie is a clean skip."""
    ordered = sorted(
        selections,
        key=lambda item: (
            item.consensus_rank,
            item.consensus_score,
            item.editorial_score,
        ),
        reverse=True,
    )
    if not ordered:
        return None
    if len(ordered) > 1 and (
        ordered[0].consensus_rank,
        ordered[0].consensus_score,
        ordered[0].editorial_score,
    ) == (
        ordered[1].consensus_rank,
        ordered[1].consensus_score,
        ordered[1].editorial_score,
    ):
        return None
    return ordered[0]


def discover_wta_point(
    digest: Digest,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_wta_video_metadata,
) -> PointSelection | None:
    """Resolve a small shortlist from the official WTA video hub."""
    response = get(
        WTA_VIDEO_HUB,
        headers={"User-Agent": "tennislive/0.1 (+https://github.com/robertyang87/tennislive)"},
        timeout=timeout,
    )
    response.raise_for_status()
    candidates = parse_wta_video_candidates(str(response.text))
    matches = yesterday_matches(digest)
    shortlist: list[OfficialVideoCandidate] = []
    for candidate in candidates[:60]:
        if official_best_signal(candidate.title) is None:
            continue
        text = _clean(candidate.title)
        if not any(any(token in text for token in _player_tokens(match)) for match in matches):
            continue
        shortlist.append(candidate)
        if len(shortlist) == 8:
            break
    metadata_items: list[OfficialVideoMetadata] = []
    for candidate in shortlist:
        try:
            metadata_items.append(metadata_fetcher(candidate, get=get, timeout=timeout))
        except (VideoPipelineError, requests.RequestException, ValueError, TypeError):
            continue
    return select_daily_point(digest, metadata_items)


def discover_tennistv_point(
    digest: Digest,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 30,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_tennistv_video_metadata,
) -> PointSelection | None:
    """Use Tennis TV's public Hot Shots library as the ATP discovery layer.

    The library is intentionally queried before YouTube: its cards carry the
    exact match references, round and editorial description. Playback is then
    resolved through Tennis TV's entitlement endpoint, never through a local
    browser cookie. If the card is freemium and no token is available, the
    resolver records a clean miss and the normal ATP official feed remains the
    next fallback.
    """
    headers = {
        "User-Agent": "tennislive/0.1 (+https://github.com/robertyang87/tennislive)"
    }
    entries = []
    try:
        response = get(
            TENNISTV_HOT_SHOTS_API,
            params={
                "offset": 0,
                "limit": 80,
                "tagNames": "video-type:hotshots",
            },
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        entries = parse_tennistv_hot_shot_api_entries(response.json())
    except (
        VideoPipelineError,
        requests.RequestException,
        ValueError,
        TypeError,
        AttributeError,
    ) as exc:
        logger.warning(
            "Tennis TV Hot Shots content API failed; using library page fallback: %s",
            exc,
        )
        entries = []
    if not entries:
        response = get(
            TENNISTV_HOT_SHOTS_HUB,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        entries = parse_tennistv_hot_shot_entries(str(response.text))
    matches = yesterday_matches(digest)
    shortlist: list = []
    for entry in entries[:80]:
        text = _clean(f"{entry.candidate.title} {entry.description} {entry.city}")
        if entry.year and str(digest.today.year) != entry.year:
            continue
        if not any(
            any(_match_player_matches(player, text, [*match.home, *match.away]) for player in [*match.home, *match.away])
            and (_event_matches(match, text) or _clean(entry.city) in _clean(match.tournament.city or ""))
            for match in matches
        ):
            continue
        shortlist.append(entry)
        if len(shortlist) >= 8:
            break
    logger.info(
        "Tennis TV Hot Shots discovery: entries=%d matching_cards=%d refresh_secret=%s jwt_secret=%s",
        len(entries),
        len(shortlist),
        "configured" if os.getenv("TENNISTV_REFRESH_TOKEN", "").strip() else "missing",
        "configured" if os.getenv("TENNISTV_JWT", "").strip() else "missing",
    )
    metadata_items: list[OfficialVideoMetadata] = []
    for entry in shortlist:
        try:
            metadata = metadata_fetcher(entry.candidate, get=get, timeout=timeout)
            metadata_items.append(
                replace(
                    metadata,
                    description=metadata.description or entry.description,
                    thumbnail_url=metadata.thumbnail_url or entry.thumbnail_url,
                    published_at=metadata.published_at or entry.published_at,
                    duration_ms=metadata.duration_ms or entry.duration_ms,
                )
            )
        except (
            VideoPipelineError,
            requests.RequestException,
            ValueError,
            TypeError,
        ) as exc:
            logger.warning(
                "Tennis TV playback resolution failed for %s: %s",
                entry.candidate.url,
                exc,
            )
            continue
    direct = select_daily_point(digest, metadata_items)
    if direct is not None:
        return direct

    # Tennis TV cards are the best ATP discovery source, but many cards are
    # freemium. Search the exact card title on the verified ATP YouTube
    # channel as a public mirror, never on arbitrary channels.
    mirror_items: list[OfficialVideoMetadata] = []
    for entry in shortlist:
        query = f'"{entry.candidate.title}" {entry.description}'.strip()
        try:
            mirrors = search_official_youtube_candidates(query, tour="ATP", limit=6)
        except (VideoPipelineError, ValueError, TypeError):
            continue
        for candidate in mirrors:
            if official_best_signal(candidate.title) is None:
                continue
            try:
                mirror_items.append(fetch_youtube_video_metadata(candidate))
            except (VideoPipelineError, requests.RequestException, ValueError, TypeError):
                continue
    return select_daily_point(digest, mirror_items)


def _discover_official_youtube_point(
    digest: Digest,
    *,
    tour: str,
    feed_url: str,
    channel_id: str,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_youtube_video_metadata,
) -> PointSelection | None:
    """Resolve one verified official YouTube uploads feed."""
    response = get(
        feed_url,
        headers={"User-Agent": "tennislive/0.1 (+https://github.com/robertyang87/tennislive)"},
        timeout=timeout,
    )
    response.raise_for_status()
    candidates = parse_official_youtube_feed(
        str(response.text),
        channel_id=channel_id,
        tour=tour,
    )
    matches = yesterday_matches(digest)
    shortlist: list[OfficialVideoCandidate] = []
    for candidate in candidates[:30]:
        if official_best_signal(candidate.title) is None:
            continue
        text = _clean(candidate.title)
        # Slam day-award titles sometimes omit the player; fetch that small
        # official shortlist so the full description can prove the match.
        if tour == "ATP" and not any(
            any(token in text for token in _player_tokens(match))
            for match in matches
        ):
            continue
        shortlist.append(candidate)
        if len(shortlist) == 8:
            break
    metadata_items: list[OfficialVideoMetadata] = []
    for candidate in shortlist:
        try:
            metadata_items.append(metadata_fetcher(candidate))
        except (VideoPipelineError, ValueError, TypeError):
            continue
    return select_daily_point(digest, metadata_items)


def discover_atp_point(
    digest: Digest,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_youtube_video_metadata,
) -> PointSelection | None:
    """Resolve ATP's verified official YouTube feed without scraping its CF page."""
    return _discover_official_youtube_point(
        digest,
        tour="ATP",
        feed_url=ATP_YOUTUBE_FEED,
        channel_id=ATP_YOUTUBE_CHANNEL_ID,
        get=get,
        timeout=timeout,
        metadata_fetcher=metadata_fetcher,
    )


def discover_tennistv_youtube_point(
    digest: Digest,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_youtube_video_metadata,
) -> PointSelection | None:
    """Resolve Tennis TV's own public YouTube uploads.

    This is a second, independent free ATP path: youtube.com/tennistv
    publicly mirrors a selection of Hot Shots and highlights from the same
    ATP Media library that requires a paid entitlement on tennistv.com
    itself. No login, no JWT.
    """
    return _discover_official_youtube_point(
        digest,
        tour="ATP",
        feed_url=TENNISTV_YOUTUBE_FEED,
        channel_id=TENNISTV_YOUTUBE_CHANNEL_ID,
        get=get,
        timeout=timeout,
        metadata_fetcher=metadata_fetcher,
    )


def discover_wta_youtube_point(
    digest: Digest,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_youtube_video_metadata,
) -> PointSelection | None:
    """Resolve WTA's verified YouTube uploads as a second WTA path."""
    return _discover_official_youtube_point(
        digest,
        tour="WTA",
        feed_url=OFFICIAL_YOUTUBE_FEEDS["WTA"],
        channel_id=OFFICIAL_YOUTUBE_CHANNEL_IDS["WTA"],
        get=get,
        timeout=timeout,
        metadata_fetcher=metadata_fetcher,
    )


def discover_youtube_search_point(
    digest: Digest,
    *,
    searcher: Callable[..., list[OfficialVideoCandidate]] = search_official_youtube_candidates,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_youtube_video_metadata,
) -> PointSelection | None:
    """Search verified tour channels using yesterday's match context.

    RSS feeds are intentionally short-lived and Tennis TV cards can lag a
    result by a few hours. This bounded search is the catch-up path: it never
    searches arbitrary creators, and the normal date/match/full-source gates
    still decide whether a result is publishable.

    This is ATP's main free path (Tennis TV's full catalog needs a paid
    entitlement this project doesn't hold; WTA has its own always-public
    video hub and leans on this less), so it covers a full day's singles
    across both tours and tries the label phrasings separately -- biasing
    the query text toward one exact phrase like "hot shot" can bury a
    "Point of the Day" upload in YouTube's ranking even though the
    acceptance gate (``official_best_signal``) already takes both.
    """
    metadata_items: list[OfficialVideoMetadata] = []
    seen: set[str] = set()
    for match in yesterday_matches(digest)[:25]:
        tour = match.tour.value
        event_text = _clean(f"{match.tournament.name} {match.tournament.city or ''}")
        for slam_code, aliases in _SLAM_EVENT_ALIASES.items():
            if any(alias in event_text for alias in aliases):
                tour = slam_code
                break
        names = [player.name for player in [*match.home, *match.away]]
        base = f'"{names[0]}" "{names[1]}" {match.tournament.name}'
        for label in ("hot shot", "point of the day"):
            query = f"{base} {label}"
            try:
                candidates = searcher(query, tour=tour, limit=8)
            except (VideoPipelineError, requests.RequestException, ValueError, TypeError):
                continue
            for candidate in candidates:
                if candidate.url in seen or official_best_signal(candidate.title) is None:
                    continue
                seen.add(candidate.url)
                try:
                    metadata_items.append(metadata_fetcher(candidate))
                except (VideoPipelineError, requests.RequestException, ValueError, TypeError):
                    continue
    return select_daily_point(digest, metadata_items)


def discover_slam_point(
    digest: Digest,
    tour: str,
    *,
    get: Callable[..., object] = requests.get,
    timeout: int = 25,
    metadata_fetcher: Callable[..., OfficialVideoMetadata] = fetch_youtube_video_metadata,
) -> PointSelection | None:
    """Resolve an official Grand Slam uploads feed through the same hard gate."""
    code = tour.upper()
    if code not in _SLAM_EVENT_ALIASES:
        raise ValueError(f"Unsupported Grand Slam source: {tour}")
    return _discover_official_youtube_point(
        digest,
        tour=code,
        feed_url=OFFICIAL_YOUTUBE_FEEDS[code],
        channel_id=OFFICIAL_YOUTUBE_CHANNEL_IDS[code],
        get=get,
        timeout=timeout,
        metadata_fetcher=metadata_fetcher,
    )


def discover_official_points_by_tour(digest: Digest) -> dict[str, PointSelection]:
    """Query independent official feeds and keep one consensus pick per tour.

    ATP and WTA are published independently: a strong WTA Hot Shot does not
    crowd out an equally valid ATP one (or vice versa). A major's channel can
    surface either tour, so selections are bucketed by the matched player's
    actual tour, not by source. A tour with no verified clip that day is
    simply absent from the returned mapping.
    """
    selections: list[PointSelection] = []
    for resolver in (
        discover_tennistv_point,
        discover_wta_point,
        discover_wta_youtube_point,
        discover_atp_point,
        discover_tennistv_youtube_point,
        discover_youtube_search_point,
    ):
        try:
            selection = resolver(digest)
        except (VideoPipelineError, requests.RequestException, ValueError, TypeError):
            continue
        if selection is not None:
            selections.append(selection)
    for tour in _SLAM_EVENT_ALIASES:
        try:
            selection = discover_slam_point(digest, tour)
        except (VideoPipelineError, requests.RequestException, ValueError, TypeError):
            continue
        if selection is not None:
            selections.append(selection)
    by_tour: dict[str, list[PointSelection]] = {"ATP": [], "WTA": []}
    for selection in selections:
        by_tour[selection.match.tour.value].append(selection)
    picks: dict[str, PointSelection] = {}
    for tour, candidates in by_tour.items():
        pick = _unique_consensus_pick(candidates)
        if pick is not None:
            picks[tour] = pick
    return picks


def _match_names(match: Match) -> tuple[str, str]:
    home = " / ".join(player_zh(player.name) for player in match.home)
    away = " / ".join(player_zh(player.name) for player in match.away)
    return home, away


def _winner_loser(match: Match) -> tuple[str, str]:
    home, away = _match_names(match)
    if match.winner == 1:
        return away, home
    return home, away


def _featured_and_opponent(selection: PointSelection) -> tuple[str, str]:
    match = selection.match
    haystack = _clean(
        f"{selection.metadata.candidate.title} {selection.metadata.description}"
    )
    players = [*match.home, *match.away]
    featured = next(
        (
            player
            for player in players
            if any(token in haystack for token in _player_tokens_for_name(player.name))
        ),
        (match.winner_players() or players)[0],
    )
    opponent = next(player for player in players if player is not featured)
    return player_zh(featured.name), player_zh(opponent.name)


def _player_tokens_for_name(name: str) -> set[str]:
    cleaned = _clean(name)
    if not cleaned:
        return set()
    tokens = {cleaned}
    parts = cleaned.split()
    tokens.update(
        part
        for part in dict.fromkeys(parts[:1] + parts[-1:])
        if len(part) >= 3
    )
    return tokens


_CAPTION_LINE1_TEMPLATES = (
    "这一分，值回放｜{winner} vs {loser}",
    "这一拍，值得再看一次｜{winner} vs {loser}",
    "别划走，这一分很值｜{winner} vs {loser}",
    "这一分，值得暂停｜{winner} vs {loser}",
    "回放按钮留给这一分｜{winner} vs {loser}",
)
_CAPTION_LINE2_TEMPLATES = (
    "{tournament} · {round_name}｜赛果 {winner} {score}",
    "{tournament} {round_name}｜全场比分 {winner} {score}",
    "{round_name} · {tournament}｜赛果 {winner} {score}",
)


def _pick_caption_template(templates: tuple[str, ...], seed: str) -> str:
    """Deterministic per-clip choice: same clip always renders the same way,

    different matches/days land on different phrasing without an
    unreproducible random draw.
    """
    index = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(templates)
    return templates[index]


def _context_text(selection: PointSelection) -> tuple[str, str]:
    match = selection.match
    winner, loser = _winner_loser(match)
    tournament = tournament_zh(match.tournament.name) or match.tournament.name
    round_name = round_zh(match.round_name) or match.round_name or "正赛"
    score = match.score_display(from_winner=True)
    seed = f"{match.match_id}:{selection.published_at}"
    line1 = _pick_caption_template(_CAPTION_LINE1_TEMPLATES, seed + ":line1").format(
        winner=winner, loser=loser
    )
    line2 = _pick_caption_template(_CAPTION_LINE2_TEMPLATES, seed + ":line2").format(
        tournament=tournament, round_name=round_name, winner=winner, score=score
    )
    return line1, line2


def _caption_cues(selection: PointSelection) -> list[SubtitleCue]:
    duration_ms = selection.metadata.duration_ms
    first, second = _context_text(selection)
    split = max(1, duration_ms // 2)
    return [
        SubtitleCue(1, 0, split, first),
        SubtitleCue(2, split, duration_ms, second),
    ]


def _escape_filter_path(path: Path) -> str:
    return path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")


def build_point_ffmpeg_command(
    selection: PointSelection,
    output_path: Path,
    subtitle_path: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    """Build a full-frame vertical render; there is intentionally no crop tracker.

    ``subtitle_path`` is an ``.ass`` file with an explicit PlayRes (see
    ``render_ass``) so the burned-in caption and brand watermark text render
    at the size and position they were authored for, instead of ffmpeg
    guessing an authoring resolution for a bare SRT and silently rescaling
    FontSize by several times. The brand icon is composited separately since
    it is a raster image, not text.
    """
    subtitle = _escape_filter_path(subtitle_path)
    filters = (
        "[0:v]split=2[bg][fg];"
        f"[bg]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},gblur=sigma=32,"
        "eq=brightness=-0.22:saturation=0.82[bg2];"
        f"[fg]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease[fg2];"
        "[bg2][fg2]overlay=(W-w)/2:(H-h)/2[full];"
        f"[1:v]scale={BRAND_ICON_SIZE}:{BRAND_ICON_SIZE}[icon];"
        f"[full][icon]overlay={BRAND_ICON_MARGIN}:{BRAND_ICON_MARGIN}[marked];"
        f"[marked]subtitles=filename='{subtitle}'[outv]"
    )
    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-reconnect",
        "1",
        "-reconnect_streamed",
        "1",
        "-reconnect_delay_max",
        "5",
        "-i",
        selection.metadata.playback_url,
        "-i",
        str(BRAND_ICON_PATH),
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
        "21",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]


def probe_video(
    path: Path,
    *,
    ffprobe_bin: str = "ffprobe",
    runner: Callable[..., object] = subprocess.run,
) -> VideoProbe:
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = runner(command, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise VideoPipelineError(f"昨日好球 ffprobe 失败：{exc}") from exc
    stream = next(
        (item for item in payload.get("streams", []) if item.get("codec_type") == "video"),
        {},
    )
    try:
        fps = float(Fraction(str(stream.get("r_frame_rate") or "0/1")))
        return VideoProbe(
            width=int(stream.get("width") or 0),
            height=int(stream.get("height") or 0),
            duration_seconds=float(payload.get("format", {}).get("duration") or 0),
            fps=fps,
            codec=str(stream.get("codec_name") or ""),
            size_bytes=int(payload.get("format", {}).get("size") or path.stat().st_size),
        )
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise VideoPipelineError("昨日好球 ffprobe 返回字段无效") from exc


def validate_rendered_point(
    selection: PointSelection,
    probe: VideoProbe,
) -> None:
    errors: list[str] = []
    source_seconds = selection.metadata.duration_ms / 1000
    if (probe.width, probe.height) != (OUTPUT_WIDTH, OUTPUT_HEIGHT):
        errors.append(f"画布应为 1080x1920，实际 {probe.width}x{probe.height}")
    if abs(probe.duration_seconds - source_seconds) > 0.9:
        errors.append(
            f"成片时长 {probe.duration_seconds:.2f}s 未完整保留源片 {source_seconds:.2f}s"
        )
    if probe.fps < MIN_OUTPUT_FPS:
        errors.append(f"帧率过低：{probe.fps:.2f}fps")
    if probe.codec not in {"h264", "hevc"}:
        errors.append(f"视频编码不适合发布：{probe.codec or '未知'}")
    if probe.size_bytes < 200_000:
        errors.append("成片体积异常，可能为空白或渲染不完整")
    if errors:
        raise VideoPipelineError("昨日好球质量门禁未通过：" + "；".join(errors))


# Shot descriptors map to a short Chinese noun. Order matters: the most specific
# descriptor wins. The noun leads the (short, no-date, no-name) title and, when
# the point is a winner, becomes 制胜分 in the body hook.
_SHOT_NOUN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"one[- ]hand(?:ed)? backhand|single[- ]hand(?:ed)? backhand", "单手反拍"),
    (r"\bbackhand\b", "反拍"),
    (r"\bforehand\b", "正手"),
    (r"passing (?:shot|winner)|\bpasses\b", "穿越球"),
    (r"\blob\b|lobbed", "高吊过顶"),
    (r"drop[- ]?shot", "放小球"),
    (r"tweener|between[- ]the[- ]legs|through the legs", "胯下击球"),
    (r"around the (?:net|post)|behind the back", "神仙操作"),
    (r"half[- ]?volley", "半截击"),
    (r"\bvolley(?:s|ed)?\b", "网前截击"),
    (r"\bsmash(?:es)?\b|overhead", "高压扣杀"),
    (r"\bace(?:s)?\b", "ACE"),
)
_WINNER_RE = re.compile(r"\bwinner\b|\bunreturnable\b|\bclean\b", re.IGNORECASE)
# Short title punches, shot-led ("单手反拍，直接封神"). Kept confident but not
# clickbait. Only rank 3 may assert the day's best; rank 1 never borrows it.
_TITLE_PUNCH = {
    3: ("今日最佳", "当日最佳一拍", "今日封神"),
    2: ("封神一分", "全场最佳", "封神了"),
    1: ("直接封神", "一拍封神", "太顶了"),
}
# When the official text names no shot, the title falls back to a short tiered
# line (still varied per clip).
_TITLE_FALLBACK = {
    3: ("今日最佳名场面", "当日最佳这一拍"),
    2: ("全场最佳一分", "封神一分"),
    1: ("神仙球名场面", "神仙球预警"),
}
# Lead-ins vary the body hook's punch per clip without touching the grounded fact.
_COPY_LEADINS = ("全场高能：", "名场面：", "划重点：", "这一下必看：", "高光时刻：")
# Body-hook fallback when the official text says nothing concrete (still varied
# per clip). Only rank 3 may claim the day's best; rank 1 uses 「神仙球」.
_COPY_FALLBACK_HOOKS = {
    3: ("官方选出的当日最佳就是这一分", "一整天的好球里，最佳落在这一分", "当日最佳，说的就是它"),
    2: ("全场最值得回放的就是这一分", "这一分是整场比赛的高光", "一场打下来最想重看这一分"),
    1: ("这一拍被官方剪成了神仙球", "标准神仙球，官方单独收录", "官方给这一拍单开了特写"),
}
_COPY_TAGS = "#网球 #网球名场面 #精彩回合 #网球时差"
# Column label shown in the title, parallel to 今日球局 / 网球有故事 on the other
# columns. Kept in Chinese to match the project's no-English-in-public-copy rule.
_COLUMN_LABEL = "昨日好球"


def _official_shot_noun(metadata: OfficialVideoMetadata) -> str | None:
    """Return the shot's short Chinese noun if the official text names it."""
    low = _clean(f"{metadata.candidate.title} {metadata.description}").casefold()
    for pattern, noun in _SHOT_NOUN_PATTERNS:
        if re.search(pattern, low):
            return noun
    return None


def _official_is_winner(metadata: OfficialVideoMetadata) -> bool:
    low = _clean(f"{metadata.candidate.title} {metadata.description}").casefold()
    return bool(_WINNER_RE.search(low))


def _official_match_hook(metadata: OfficialVideoMetadata) -> str | None:
    """Pull the strongest match-level angle the official description states."""
    low = _clean(metadata.description).casefold()
    minutes = re.search(r"\b(?:just |in )(\d{1,3}) minutes?\b", low)
    if minutes:
        return f"{minutes.group(1)} 分钟速战速决"
    if re.search(r"saved? .{0,25}match point|match point[s]? down", low):
        return "挽救赛点惊险过关"
    if re.search(r"from a set down|came from .{0,20}down|fought back|rallied from", low):
        return "先丢一盘完成逆转"
    if re.search(r"straight[- ]sets|raced? past|cruis|dominat|breez", low):
        return "直落两盘轻松过关"
    if re.search(r"maiden .{0,20}title|first .{0,20}title|career-first", low):
        return "拿下生涯里程碑一冠"
    return None


def point_xiaohongshu_copy(selection: PointSelection, published_for: date) -> str:
    """A short Xiaohongshu post: a titled column line, one grounded hook, context.

    The title follows the house style shared with the daily digest and the
    knowledge post -- emoji, date, column name, then a short highlight after the
    ｜ divider (``🎾7.24 昨日好球｜单手反拍，一拍封神``). The highlight leads with the
    actual shot when the official text names one and falls back to a short
    tiered line otherwise -- no player name (it's in the body context line). The
    body's first line is the 引爆点, likewise grounded in the official description
    (the shot as 制胜分, a fast win, a comeback) or a tiered fallback. A per-clip
    seed varies the punch, lead-in and any fallback so clips never read alike.
    """
    featured, opponent = _featured_and_opponent(selection)
    winner, _loser = _winner_loser(selection.match)
    score = selection.match.score_display(from_winner=True)
    tournament = (
        tournament_zh(selection.match.tournament.name)
        or selection.match.tournament.name
    )
    rank = selection.consensus_rank
    seed = f"{selection.match.match_id}:{selection.published_at}"
    shot = _official_shot_noun(selection.metadata)
    if shot:
        punch = _pick_caption_template(_TITLE_PUNCH[rank], seed + ":punch")
        highlight = f"{shot}，{punch}"
    else:
        highlight = _pick_caption_template(_TITLE_FALLBACK[rank], seed + ":titlefb")
    title = f"🎾{published_for.month}.{published_for.day} {_COLUMN_LABEL}｜{highlight}"
    if shot:
        core = (
            f"一记{shot}制胜分"
            if shot != "ACE" and _official_is_winner(selection.metadata)
            else f"一记{shot}"
        )
    else:
        core = _official_match_hook(selection.metadata) or _pick_caption_template(
            _COPY_FALLBACK_HOOKS[rank], seed + ":hook"
        )
    lead = _pick_caption_template(_COPY_LEADINS, seed + ":lead")
    hook = f"{lead}{core}。"
    context = f"{featured} vs {opponent}｜{tournament}，赛果 {winner} {score}。"
    body = limit_hashtags("\n".join([hook, context, _COPY_TAGS]))
    copy = title + "\n\n" + body
    validate_point_copy(copy)
    return copy


def point_push_html(digest: Digest, copy: str, *, tour_dir: str = "") -> str:
    """Build a phone-friendly PushPlus package without public source credits.

    ``tour_dir`` is the ``atp``/``wta`` subfolder a per-tour package renders
    into; empty keeps the legacy single-package layout.
    """
    lines = copy.strip().splitlines()
    title = lines[0].strip() if lines else "昨日好球"
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
    subpath = f"yesterday-point/{tour_dir}" if tour_dir else "yesterday-point"
    video_url = (
        f"https://cdn.jsdelivr.net/gh/{repository}@main/output/"
        f"{digest.today.isoformat()}/{subpath}/yesterday-point.mp4"
    )
    owner, _, repo_name = repository.partition("/")
    pages_root = os.environ.get(
        "TENNISLIVE_PAGES_URL", f"https://{owner}.github.io/{repo_name}"
    ).rstrip("/")
    copy_url = f"{pages_root}/output/{digest.today.isoformat()}/{subpath}/copy.html"
    return (
        '<div style="background:#f6f7f4;color:#17251f;padding:12px 10px;">'
        '<div style="max-width:680px;margin:0 auto;background:#fff;border-top:5px solid #ff2442;'
        'padding:18px 16px 22px;">'
        '<div style="font-size:12px;font-weight:700;color:#087747;">这一分，值得回放</div>'
        f'<div style="font-size:22px;line-height:1.4;font-weight:800;margin:8px 0 14px;">'
        f'{html.escape(title)}</div>'
        f'<a href="{html.escape(video_url, quote=True)}" style="display:block;background:#102d23;'
        'color:#fff;text-align:center;text-decoration:none;font-weight:700;padding:14px 16px;'
        'border-radius:6px;margin:0 0 16px;">打开 / 下载竖屏成片</a>'
        f'<div style="font-size:15px;line-height:1.85;color:#25342e;margin-bottom:16px;'
        f'white-space:pre-line;">{html.escape(body)}</div>'
        f'<a href="{html.escape(copy_url, quote=True)}" style="display:block;background:#ff2442;'
        'color:#fff;text-align:center;text-decoration:none;font-weight:700;padding:13px 16px;'
        'border-radius:6px;">分别复制标题 / 正文</a>'
        '</div></div>'
    )


def validate_point_copy(copy: str) -> None:
    parts = [part.strip() for part in copy.split("\n\n") if part.strip()]
    if len(parts) != 2:
        raise VideoPipelineError("昨日好球必须是标题加一个正文块")
    body = parts[1]
    public_citation_markers = ("来源：", "图源：", "摄影/图源", "非商业资料引用")
    if any(marker in body for marker in public_citation_markers):
        raise VideoPipelineError("昨日好球正文不得显示资料或图片来源")
    if not any(word in body for word in ("比分", "赛果")):
        raise VideoPipelineError("昨日好球正文必须含比分上下文")
    if body.count("？") > 1:
        raise VideoPipelineError("昨日好球正文最多一个评论问题")
    if not 3 <= hashtag_count(body) <= 5:
        raise VideoPipelineError("昨日好球正文话题标签应保持 3 至 5 个")
    # Keep it short: a punchy hook, one context line, the tags -- a few short
    # lines inside one phone screen, not a dense block. The blank line between
    # title and body already split it off above.
    lines = [line for line in body.splitlines() if line.strip()]
    if not 2 <= len(lines) <= 4:
        raise VideoPipelineError("昨日好球正文应为 2 至 4 行短句，便于手机阅读")
    if len(body) > 240:
        raise VideoPipelineError("昨日好球正文超过手机一屏长度")


def render_daily_point(
    selection: PointSelection,
    output_dir: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    runner: Callable[..., object] = subprocess.run,
    prober: Callable[[Path], VideoProbe] | None = None,
) -> Path:
    if shutil.which(ffmpeg_bin) is None:
        raise VideoPipelineError(f"ffmpeg executable not found: {ffmpeg_bin}")
    if prober is None and shutil.which(ffprobe_bin) is None:
        raise VideoPipelineError(f"ffprobe executable not found: {ffprobe_bin}")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cues = _caption_cues(selection)
    subtitle_path = output_dir / "yesterday-point.zh-CN.srt"
    caption_path = output_dir / "yesterday-point.ass"
    output_path = output_dir / "yesterday-point.mp4"
    subtitle_path.write_text(render_srt(cues), encoding="utf-8")
    caption_path.write_text(
        render_ass(
            cues,
            play_res_x=OUTPUT_WIDTH,
            play_res_y=OUTPUT_HEIGHT,
            font_size=CAPTION_FONT_SIZE,
            margin_v=CAPTION_MARGIN_V,
            overlays=(
                AssOverlay(
                    BRAND_TEXT,
                    alignment=7,
                    font_size=BRAND_TOP_FONT_SIZE,
                    margin_l=BRAND_TOP_MARGIN_L,
                    margin_v=BRAND_TOP_MARGIN_V,
                ),
                AssOverlay(
                    f"@{BRAND_TEXT} · TENNIS JETLAG",
                    alignment=3,
                    font_size=BRAND_BOTTOM_FONT_SIZE,
                    margin_r=BRAND_BOTTOM_MARGIN_R,
                    margin_v=BRAND_BOTTOM_MARGIN_V,
                ),
            ),
        ),
        encoding="utf-8",
    )
    command = build_point_ffmpeg_command(
        selection,
        output_path,
        caption_path,
        ffmpeg_bin=ffmpeg_bin,
    )
    try:
        runner(command, check=True, timeout=300)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        fallback = selection.metadata.fallback_url
        if not fallback:
            raise VideoPipelineError(f"昨日好球渲染失败：{exc}") from exc
        fallback_command = [
            fallback if part == selection.metadata.playback_url else part
            for part in command
        ]
        try:
            runner(fallback_command, check=True, timeout=300)
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as fallback_exc:
            raise VideoPipelineError(
                f"昨日好球主播放源与备用源均渲染失败：{fallback_exc}"
            ) from fallback_exc
    if not output_path.is_file():
        raise VideoPipelineError("昨日好球渲染未产生成片")
    measured = (
        prober(output_path)
        if prober is not None
        else probe_video(output_path, ffprobe_bin=ffprobe_bin)
    )
    validate_rendered_point(selection, measured)
    return output_path


def _generate_tour_point(
    tour: str, selection: PointSelection, digest: Digest, tour_dir: Path
) -> Path:
    """Render one tour's package (video, copy, manifest) into its own subdir."""
    output = render_daily_point(selection, tour_dir)
    copy = point_xiaohongshu_copy(selection, digest.today)
    (tour_dir / "xiaohongshu.txt").write_text(copy, encoding="utf-8")
    from ..render.pushmsg import to_copy_page

    (tour_dir / "copy.html").write_text(to_copy_page(copy), encoding="utf-8")
    (tour_dir / "push.html").write_text(
        point_push_html(digest, copy, tour_dir=tour.lower()), encoding="utf-8"
    )
    # Record exactly what the copy grounded on, so a shot claim ("单手反拍") is
    # auditable against the raw official text rather than taken on trust.
    copy_shot = _official_shot_noun(selection.metadata)
    copy_match = None if copy_shot else _official_match_hook(selection.metadata)
    manifest = {
        "status": "pass",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": "yesterday-point",
        "tour": tour,
        "published_for": digest.today.isoformat(),
        "match_date": digest.yesterday.isoformat(),
        "source": asdict(selection.metadata.candidate),
        "source_description": selection.metadata.description,
        "copy_grounding": {
            "basis": (
                "official-shot"
                if copy_shot
                else "official-match"
                if copy_match
                else "fallback"
            ),
            "shot": copy_shot or "",
            "shot_as_winner": bool(copy_shot)
            and copy_shot != "ACE"
            and _official_is_winner(selection.metadata),
            "match_angle": copy_match or "",
        },
        "source_label": selection.source_label,
        "source_published_at": selection.published_at,
        "source_duration_ms": selection.metadata.duration_ms,
        "source_resolution": [
            selection.metadata.source_width,
            selection.metadata.source_height,
        ],
        "match": {
            "id": selection.match.match_id,
            "players": list(_match_names(selection.match)),
            "tournament": selection.match.tournament.name,
            "round": selection.match.round_name,
            "score": selection.match.score_display(from_winner=True),
        },
        "selection_score": selection.editorial_score,
        "consensus": {
            "verified": True,
            "rank": selection.consensus_rank,
            "basis": selection.consensus_basis,
            "score": selection.consensus_score,
            "signals": list(selection.consensus_signals),
            "evidence": (
                "官方当日最佳标签"
                if selection.consensus_rank == 3
                else "官方全场最佳标签"
                if selection.consensus_rank == 2
                else "官方 Hot Shots 单分视频；热度信号优先于‘最佳’断言"
            ),
        },
        "complete_rally": {
            "verified": True,
            "evidence": selection.complete_point_evidence,
            "source_window_ms": [0, selection.metadata.duration_ms],
            "montage": False,
        },
        "framing": {
            "canvas": "3:4",
            "foreground": "full-source-frame",
            "mode": "contain",
            "dynamic_tracking_crop": False,
            "reason": "没有逐帧高置信度追踪证据，完整 16:9 主体优先",
        },
        "outputs": {
            "video": output.name,
            "subtitles": "yesterday-point.zh-CN.srt",
            "copy": "xiaohongshu.txt",
            "copy_page": "copy.html",
            "pushplus": "push.html",
        },
    }
    (tour_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return output


def generate_yesterday_point(
    digest: Digest,
    output_dir: Path,
    *,
    skip_tours: frozenset[str] = frozenset(),
) -> dict[str, Path]:
    """GitHub Actions entry point.

    Publishes one ATP and one WTA package independently under
    ``output_dir/atp`` and ``output_dir/wta``; a tour with no verified clip
    that day is a clean skip for that tour only, not the other.

    ``skip_tours`` lets a caller re-run this later the same day without
    redoing (or re-pushing) a tour that already succeeded -- the point of
    the retry cadence is to keep trying only the tour that is still
    missing, since official channels don't all upload at the same time.
    """
    if os.environ.get("TENNISLIVE_YESTERDAY_POINT", "off").casefold() != "on":
        return {}
    output_dir = Path(output_dir).resolve()
    if skip_tours >= {"ATP", "WTA"}:
        return {}
    picks = discover_official_points_by_tour(digest)
    outputs: dict[str, Path] = {}
    for tour, selection in picks.items():
        if tour in skip_tours:
            continue
        tour_dir = output_dir / tour.lower()
        outputs[tour] = _generate_tour_point(tour, selection, digest, tour_dir)
    return outputs
