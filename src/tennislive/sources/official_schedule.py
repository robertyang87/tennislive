"""Enrich schedule times from tour-owned Order of Play PDFs.

The provider is intentionally HTTP-only so it can run unattended in GitHub
Actions.  Discovery feeds remain useful for breadth; official OOP documents
decide whether a time is exact, merely an estimated "followed by" slot, or has
not been published yet.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from pypdf import PdfReader

from ..digest import Digest
from ..models import Match
from .base import make_session

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY = Path("data/official_schedule_sources.json")


@dataclass(frozen=True)
class OfficialEvent:
    tour: str
    aliases: tuple[str, ...]
    source: str
    url: str
    timezone: str


@dataclass(frozen=True)
class Fragment:
    text: str
    x: float
    y: float


@dataclass(frozen=True)
class OfficialDocument:
    event: OfficialEvent
    url: str
    play_date: date | None
    text: str
    fragments: tuple[Fragment, ...]


def _matrix_multiply(m: list[float], n: list[float]) -> tuple[float, ...]:
    return (
        m[0] * n[0] + m[1] * n[2],
        m[0] * n[1] + m[1] * n[3],
        m[2] * n[0] + m[3] * n[2],
        m[2] * n[1] + m[3] * n[3],
        m[4] * n[0] + m[5] * n[2] + n[4],
        m[4] * n[1] + m[5] * n[3] + n[5],
    )


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in value if ch.isalnum())


def _load_registry(path: Path = DEFAULT_REGISTRY) -> list[OfficialEvent]:
    if not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        OfficialEvent(
            tour=str(row["tour"]),
            aliases=tuple(str(alias) for alias in row["aliases"]),
            source=str(row["source"]),
            url=str(row["url"]),
            timezone=str(row["timezone"]),
        )
        for row in rows
    ]


def _event_for_match(match: Match, events: list[OfficialEvent]) -> OfficialEvent | None:
    name = _norm(match.tournament.name)
    candidates = [
        event
        for event in events
        if event.tour == match.tour.value
        and any(_norm(alias) in name or name in _norm(alias) for alias in event.aliases)
    ]
    return max(candidates, key=lambda event: max(map(len, event.aliases)), default=None)


def _parse_play_date(text: str) -> date | None:
    line = next(
        (line for line in text.splitlines() if "ORDER OF PLAY" in line.upper()), ""
    )
    for pattern, fmt in (
        (r"\b(\d{1,2} [A-Z]+ \d{4})\b", "%d %B %Y"),
        (r"\b([A-Z]+ \d{1,2}, \d{4})\b", "%B %d, %Y"),
    ):
        match = re.search(pattern, line.upper())
        if match:
            try:
                return datetime.strptime(match.group(1).title(), fmt).date()
            except ValueError:
                pass
    return None


def _read_pdf(event: OfficialEvent, year: int) -> OfficialDocument:
    url = event.url.format(year=year)
    response = make_session({"Accept": "application/pdf"}).get(url, timeout=30)
    response.raise_for_status()
    page = PdfReader(BytesIO(response.content)).pages[0]
    fragments: list[Fragment] = []

    def visit(text, cm, tm, _font, _size):
        clean = " ".join(str(text).split())
        if not clean:
            return
        matrix = _matrix_multiply(tm, cm)
        fragments.append(Fragment(clean, float(matrix[4]), float(matrix[5])))

    plain = page.extract_text(visitor_text=visit) or ""
    return OfficialDocument(
        event=event,
        url=url,
        play_date=_parse_play_date(plain),
        text=plain,
        fragments=tuple(fragments),
    )


def _player_markers(name: str) -> tuple[str, ...]:
    tokens = [_norm(token) for token in re.split(r"[\s-]+", name)]
    useful = [token for token in tokens if len(token) >= 3]
    return tuple(sorted(useful, key=len, reverse=True)[:3])


def _player_positions(document: OfficialDocument, name: str) -> list[Fragment]:
    markers = _player_markers(name)
    return [
        fragment
        for fragment in document.fragments
        if any(marker in _norm(fragment.text) for marker in markers)
    ]


def _match_position(document: OfficialDocument, match: Match) -> tuple[float, float] | None:
    if not match.home or not match.away:
        return None
    home = _player_positions(document, match.home[0].name)
    away = _player_positions(document, match.away[0].name)
    pairs = [
        (left, right)
        for left in home
        for right in away
        if abs(left.x - right.x) <= 220 and abs(left.y - right.y) <= 90
    ]
    if not pairs:
        return None
    left, right = min(
        pairs, key=lambda pair: abs(pair[0].x - pair[1].x) + abs(pair[0].y - pair[1].y)
    )
    return (left.x + right.x) / 2, (left.y + right.y) / 2


def _directive_for(document: OfficialDocument, position: tuple[float, float]) -> str | None:
    x, y = position
    directives = [
        fragment
        for fragment in document.fragments
        if re.search(r"starting at|starts at|not before|followed by", fragment.text, re.I)
        and fragment.y > y
        and abs(fragment.x - x) <= 190
    ]
    if not directives:
        return None
    return min(
        directives,
        key=lambda fragment: (fragment.y - y) + abs(fragment.x - x) * 0.2,
    ).text


def _official_datetime(
    play_date: date, directive: str, timezone_name: str
) -> datetime | None:
    found = re.search(r"(\d{1,2}):(\d{2})(?:\s*([AP]M))?", directive, re.I)
    if not found:
        return None
    hour, minute = int(found.group(1)), int(found.group(2))
    meridiem = (found.group(3) or "").upper()
    if meridiem == "PM" and hour != 12:
        hour += 12
    elif meridiem == "AM" and hour == 12:
        hour = 0
    local = datetime.combine(
        play_date, time(hour, minute), tzinfo=ZoneInfo(timezone_name)
    )
    return local.astimezone(timezone.utc)


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _apply_document(matches: list[Match], document: OfficialDocument) -> dict[str, int]:
    counts = {"exact": 0, "ordered": 0, "unlisted": 0}
    for match in matches:
        _append_unique(match.data_sources, document.event.source)
        _append_unique(match.schedule_source_urls, document.url)
        position = _match_position(document, match)
        if position is None:
            if document.play_date is not None:
                match.schedule_time_status = "official-unlisted"
                match.schedule_note = (
                    f"{document.event.source} {document.play_date.isoformat()} 未列出该场，"
                    "等待下一版官方排期"
                )
                counts["unlisted"] += 1
            continue
        directive = _directive_for(document, position)
        if directive and re.search(r"starting at|starts at|not before", directive, re.I):
            official = (
                _official_datetime(
                    document.play_date, directive, document.event.timezone
                )
                if document.play_date
                else None
            )
            if official is not None:
                original = match.start_utc
                match.start_utc = official
                match.time_observations[document.event.source] = official.isoformat()
                match.schedule_time_status = "official-exact"
                match.schedule_note = (
                    f"{document.event.source}：{directive}"
                    + (
                        "；聚合源时间与官方时间不一致，已以官方为准"
                        if original and abs((original - official).total_seconds()) > 15 * 60
                        else ""
                    )
                )
                counts["exact"] += 1
                continue
        match.schedule_time_status = "official-order-estimate"
        match.schedule_note = f"{document.event.source}：{directive or '已列入场序，未给定开赛时间'}"
        counts["ordered"] += 1
    return counts


def enrich_official_schedules(
    digest: Digest, registry_path: Path = DEFAULT_REGISTRY
) -> dict[str, str]:
    """Apply every matching official OOP and return human-readable source status."""
    events = _load_registry(registry_path)
    grouped: dict[OfficialEvent, list[Match]] = {}
    for match in digest.schedule:
        # Daily social cards prioritize singles. Doubles names frequently repeat
        # elsewhere in a multi-column OOP, so do not claim a pairing match until
        # the parser supports four-player spatial clustering.
        if match.is_doubles:
            continue
        event = _event_for_match(match, events)
        if event is not None:
            grouped.setdefault(event, []).append(match)

    statuses: dict[str, str] = {}
    for event, matches in grouped.items():
        label = f"{event.source} · {matches[0].tournament.name}"
        try:
            document = _read_pdf(event, digest.today.year)
            counts = _apply_document(matches, document)
            statuses[label] = (
                f"正常 · 精确 {counts['exact']} 场 / 场序 {counts['ordered']} 场 / "
                f"待下一版 {counts['unlisted']} 场"
            )
        except Exception as exc:  # noqa: BLE001 - each official event degrades alone
            logger.warning("官方 OOP 读取失败（%s）: %s", label, exc)
            statuses[label] = f"失败 · {exc}"
    return statuses
