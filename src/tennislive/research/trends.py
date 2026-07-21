"""Automatic, source-backed trend signals for editorial selection.

The radar uses public RSS surfaces that are stable in GitHub Actions:
official-publisher headlines indexed by Google News and Google Trends'
official Trending Now feeds. Signals affect selection only; they never become
match facts or invented analysis.
"""

from __future__ import annotations

import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

from ..models import Match


_NEWS_QUERIES = (
    ("ATP Tour", "site:atptour.com/en/news"),
    ("WTA", "site:wtatennis.com/news"),
    ("Australian Open", "site:ausopen.com/articles/news"),
    ("Roland-Garros", "site:rolandgarros.com/en-us/article"),
    ("Wimbledon", "site:wimbledon.com/en_GB/news"),
    ("US Open", "site:usopen.org/en_US/news"),
    ("Top media", "tennis when:1d"),
)
_TREND_GEOS = ("HK", "US", "GB", "AU")
_HT = "https://trends.google.com/trends/trendingsearches/daily"
_STOP_TERMS = {
    "open",
    "tennis",
    "tour",
    "atp",
    "wta",
    "mens",
    "womens",
    "singles",
    "international",
    "championships",
    "presented",
    "powered",
    "the",
}
_TENNIS_CONTEXT = {
    "tennis",
    "atp",
    "wta",
    "wimbledon",
    "usopen",
    "rolandgarros",
    "australianopen",
    "grand slam",
    "masters",
}
_MEDIA_ALLOWLIST = {
    "reuters",
    "associated press",
    "ap news",
    "bbc",
    "bbc sport",
    "espn",
    "the guardian",
    "sky sports",
    "eurosport",
    "tennis.com",
    "l'equipe",
}


@dataclass(frozen=True)
class TrendSignal:
    kind: str  # official-news / search-trend
    source: str
    title: str
    url: str
    published_at: str
    traffic: str = ""


@dataclass(frozen=True)
class TrendRadarResult:
    signals: int
    matched_matches: int
    source_status: dict[str, str]


def _norm(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in plain if ch.isalnum())


def _published(value: str) -> datetime | None:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clean_news_title(title: str, source: str) -> str:
    if " - " not in title:
        return title.strip()
    body, suffix = title.rsplit(" - ", 1)
    if source.casefold() in suffix.casefold() or "tennis" in suffix.casefold():
        return body.strip()
    return title.strip()


def _parse_news_feed(content: bytes, source: str, now: datetime) -> list[TrendSignal]:
    root = ET.fromstring(content)
    cutoff = now - timedelta(hours=72)
    output: list[TrendSignal] = []
    for item in root.findall(".//item"):
        published = _published(item.findtext("pubDate", ""))
        publisher = item.findtext("source", "").strip() or source
        if source == "Top media" and publisher.casefold() not in _MEDIA_ALLOWLIST:
            continue
        title = _clean_news_title(item.findtext("title", ""), publisher)
        url = item.findtext("link", "").strip()
        if (
            not title
            or not url
            or published is None
            or published < cutoff
            or published > now + timedelta(hours=1)
        ):
            continue
        output.append(
            TrendSignal(
                kind="official-news",
                source=publisher,
                title=title,
                url=url,
                published_at=published.isoformat(),
            )
        )
    return output[:20]


def _parse_trend_feed(content: bytes, geo: str, now: datetime) -> list[TrendSignal]:
    root = ET.fromstring(content)
    cutoff = now - timedelta(hours=36)
    output: list[TrendSignal] = []
    for item in root.findall(".//item"):
        published = _published(item.findtext("pubDate", ""))
        if (
            published is None
            or published < cutoff
            or published > now + timedelta(hours=1)
        ):
            continue
        title = item.findtext("title", "").strip()
        related = " ".join(
            (value.text or "").strip()
            for value in item.findall(f".//{{{_HT}}}news_item_title")
            if (value.text or "").strip()
        )
        combined = " | ".join(part for part in (title, related) if part)
        if not combined:
            continue
        output.append(
            TrendSignal(
                kind="search-trend",
                source=f"Google Trends {geo}",
                title=combined,
                url=item.findtext("link", "").strip(),
                published_at=published.isoformat(),
                traffic=item.findtext(f"{{{_HT}}}approx_traffic", "").strip(),
            )
        )
    return output


def _fetch_one(
    kind: str,
    label: str,
    url: str,
    now: datetime,
    get,
    timeout: int,
) -> tuple[str, list[TrendSignal], str]:
    try:
        response = get(
            url,
            headers={
                "User-Agent": (
                    "TennisLive/1.0 "
                    "(+https://github.com/robertyang87/tennislive)"
                )
            },
            timeout=timeout,
        )
        response.raise_for_status()
        signals = (
            _parse_news_feed(response.content, label, now)
            if kind == "news"
            else _parse_trend_feed(response.content, label, now)
        )
        return label, signals, f"正常 · {len(signals)} 条"
    except Exception as exc:  # noqa: BLE001 - every feed is an optional signal
        return label, [], f"降级 · {type(exc).__name__}"


def fetch_trend_signals(
    *,
    now: datetime | None = None,
    get=requests.get,
    timeout: int = 15,
) -> tuple[list[TrendSignal], dict[str, str]]:
    """Fetch all trend feeds concurrently; one source failure never blocks output."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    jobs = [
        (
            "news",
            source,
            "https://news.google.com/rss/search?q="
            f"{quote_plus(query)}&hl=en-US&gl=US&ceid=US:en",
        )
        for source, query in _NEWS_QUERIES
    ] + [
        ("trend", geo, f"https://trends.google.com/trending/rss?geo={geo}")
        for geo in _TREND_GEOS
    ]
    signals: list[TrendSignal] = []
    status: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [
            pool.submit(_fetch_one, kind, label, url, now, get, timeout)
            for kind, label, url in jobs
        ]
        for future in as_completed(futures):
            label, items, detail = future.result()
            signals.extend(items)
            status[label] = detail
    signals.sort(key=lambda item: item.published_at, reverse=True)
    return signals, status


def _match_terms(match: Match) -> tuple[list[tuple[str, set[str]]], set[str]]:
    player_groups: list[tuple[str, set[str]]] = []
    for player in match.home + match.away:
        tokens = re.findall(r"[^\W\d_]{2,}", player.name)
        full_name = _norm(player.name)
        edge_terms: set[str] = set()
        # Headlines normally shorten players to a family name. Keeping only
        # the two edge tokens supports both Western and reversed Chinese names
        # while avoiding middle-name collisions.
        for token in dict.fromkeys((tokens[:1] + tokens[-1:])):
            term = _norm(token)
            if len(term) >= 4 and term not in _STOP_TERMS:
                edge_terms.add(term)
        player_groups.append((full_name if len(full_name) >= 6 else "", edge_terms))
    tournament_raw = " ".join(
        value or ""
        for value in (
            match.tournament.name,
            match.tournament.city,
            match.tournament.country,
        )
    )
    tournament_terms = {
        _norm(token)
        for token in re.findall(r"[^\W\d_]{4,}", tournament_raw)
        if _norm(token) not in _STOP_TERMS
    }
    return player_groups, tournament_terms


def _traffic_points(value: str) -> int:
    match = re.search(r"([\d,.]+)\s*([KMB]?)", value.upper())
    if not match:
        return 0
    amount = float(match.group(1).replace(",", ""))
    amount *= {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(
        match.group(2), 1
    )
    return min(8, max(1, int(math.log10(max(10, amount))) - 1))


def _signal_match(match: Match, signal: TrendSignal) -> tuple[int, bool]:
    title = _norm(signal.title)
    player_groups, tournament_terms = _match_terms(match)
    has_tennis_context = any(_norm(term) in title for term in _TENNIS_CONTEXT)
    player_hits = 0
    for full_name, edge_terms in player_groups:
        full_hit = bool(full_name and full_name in title)
        edge_hit = any(term in title for term in edge_terms)
        if signal.kind == "search-trend":
            edge_hit = edge_hit and has_tennis_context
        if full_hit or edge_hit:
            player_hits += 1
    tournament_hit = any(term in title for term in tournament_terms)
    if signal.kind == "search-trend":
        tournament_hit = tournament_hit and has_tennis_context
    return player_hits, tournament_hit


def apply_trend_signals(
    matches: list[Match],
    *,
    signals: list[TrendSignal] | None = None,
    now: datetime | None = None,
) -> TrendRadarResult:
    """Attach bounded news/search heat to matches for downstream ranking."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if signals is None:
        signals, status = fetch_trend_signals(now=now)
    else:
        status = {"injected": f"正常 · {len(signals)} 条"}

    matched = 0
    for match in matches:
        news: list[tuple[TrendSignal, int, bool]] = []
        trends: list[tuple[TrendSignal, int, bool]] = []
        for signal in signals:
            player_hits, tournament_hit = _signal_match(match, signal)
            if not (player_hits or tournament_hit):
                continue
            (trends if signal.kind == "search-trend" else news).append(
                (signal, player_hits, tournament_hit)
            )

        news_sources = {item.source for item, _, _ in news}
        news_heat = 0
        for signal, player_hits, tournament_hit in news[:8]:
            age = now - datetime.fromisoformat(signal.published_at)
            freshness = (
                10
                if age <= timedelta(hours=4)
                else 8
                if age <= timedelta(hours=12)
                else 5
            )
            if player_hits >= 2 or (player_hits and tournament_hit):
                relevance = freshness + (12 if player_hits >= 2 else 6)
            elif player_hits:
                relevance = max(3, freshness // 2)
            else:
                relevance = 2
            news_heat += relevance
        if len(news_sources) > 1:
            news_heat += min(10, (len(news_sources) - 1) * 5)

        trend_sources = {item.source for item, _, _ in trends}
        trend_heat = sum(
            14 + _traffic_points(item.traffic) for item, _, _ in trends[:4]
        )
        if len(trend_sources) > 1:
            trend_heat += min(8, (len(trend_sources) - 1) * 3)

        match.media_heat = min(35, news_heat)
        match.search_heat = min(35, trend_heat)
        match.trend_signals = [
            asdict(item) for item, _, _ in (trends[:4] + news[:8])
        ]
        if match.media_heat or match.search_heat:
            matched += 1

    return TrendRadarResult(
        signals=len(signals),
        matched_matches=matched,
        source_status=status,
    )
