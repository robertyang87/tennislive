"""数据源注册与聚合：主源负责稳定，备用源用于补漏."""

from __future__ import annotations

import logging
import unicodedata
from datetime import date, datetime

from ..models import DailyData, Match
from ..timeutil import now_utc
from ..zh.tournaments import tournament_level
from .base import SourceError, TennisSource
from .espn import EspnSource
from .sofascore import SofaScoreSource

logger = logging.getLogger(__name__)

__all__ = [
    "EspnSource",
    "SofaScoreSource",
    "SourceError",
    "TennisSource",
    "fetch_day",
    "make_source_chain",
]


def make_source_chain(prefer: str | None = None) -> list[TennisSource]:
    """Aggregate the configured discovery feeds; licensed stats are separate."""
    chain: list[TennisSource] = [EspnSource(), SofaScoreSource()]
    if prefer:
        chain.sort(key=lambda s: 0 if s.name == prefer else 1)
    return chain


def _identity_name_key(name: str) -> str:
    """Stable cross-feed identity tolerant of reversed names and middle names."""
    plain = unicodedata.normalize("NFKD", name.casefold())
    tokens = [
        "".join(ch for ch in token if ch.isalnum())
        for token in plain.replace("-", " ").split()
    ]
    tokens = [token for token in tokens if token]
    if len(tokens) <= 2:
        return "".join(sorted(tokens))
    # Feeds frequently add or omit a middle/compound family-name token. The
    # outer tokens remain stable, including when Chinese names reverse order.
    return "".join(sorted((tokens[0], tokens[-1])))


def _side_key(players) -> tuple[str, ...]:
    return tuple(sorted(_identity_name_key(player.name) for player in players))


def _match_key(match: Match) -> tuple:
    """跨数据源比赛身份：fetch_day 已限定日期，不让缺失时间阻断合并."""
    sides = []
    for players in (match.home, match.away):
        sides.append(_side_key(players))
    discipline = "doubles" if match.is_doubles else "singles"
    return match.tour.value, discipline, tuple(sorted(sides))


def _quality(match: Match) -> int:
    players = match.home + match.away
    return (
        len(match.sets) * 8
        + sum(2 for p in players if p.country)
        + sum(2 for p in players if p.headshot_url)
        + sum(2 for p in players if p.rank)
        + (4 if match.round_name else 0)
        + (2 if match.tournament.level else 0)
    )


def _refresh_time_status(match: Match) -> None:
    """Classify schedule time evidence without discarding useful observations."""
    values = []
    for value in match.time_observations.values():
        if not value:
            continue
        try:
            values.append(datetime.fromisoformat(value))
        except ValueError:
            continue
    if not values:
        match.schedule_time_status = "unpublished"
    elif len(values) == 1:
        match.schedule_time_status = "single-source"
    else:
        spread = max(values) - min(values)
        match.schedule_time_status = (
            "cross-verified" if spread.total_seconds() <= 15 * 60 else "conflict"
        )


def _record_source(match: Match, source_name: str) -> None:
    if source_name not in match.data_sources:
        match.data_sources.append(source_name)
    match.time_observations[source_name] = (
        match.start_utc.isoformat() if match.start_utc else None
    )
    _refresh_time_status(match)


def _merge_match(primary: Match, extra: Match) -> Match:
    """保留更完整记录，并从另一来源补齐安全字段."""
    best, other = (primary, extra) if _quality(primary) >= _quality(extra) else (extra, primary)
    # 官网常给简写全大写赛事名（如 ATHENS），展示时采用更完整的品牌名。
    best.tournament.name = max(
        (best.tournament.name, other.tournament.name),
        key=lambda name: (not name.isupper(), len(name)),
    )
    if best.tournament.level is None:
        best.tournament.level = other.tournament.level or tournament_level(
            best.tournament.name, best.tour.value
        )
    best.start_utc = best.start_utc or other.start_utc
    best.round_name = best.round_name or other.round_name
    best.court = best.court or other.court
    other_sides = {_side_key(side): side for side in (other.home, other.away)}
    for best_side in (best.home, best.away):
        other_side = other_sides.get(_side_key(best_side), [])
        lookup = {_identity_name_key(p.name): p for p in other_side}
        for player in best_side:
            candidate = lookup.get(_identity_name_key(player.name))
            if candidate is None:
                continue
            player.country = player.country or candidate.country
            player.rank = player.rank or candidate.rank
            player.seed = player.seed or candidate.seed
            player.headshot_url = player.headshot_url or candidate.headshot_url
            player.player_id = player.player_id or candidate.player_id
    for source_name in other.data_sources:
        if source_name not in best.data_sources:
            best.data_sources.append(source_name)
    best.time_observations.update(other.time_observations)
    for url in other.schedule_source_urls:
        if url not in best.schedule_source_urls:
            best.schedule_source_urls.append(url)
    _refresh_time_status(best)
    return best


def fetch_day(d: date, prefer: str | None = None) -> DailyData:
    """聚合所有可用数据源，再按球员与比赛日期跨源去重."""
    errors: list[str] = []
    merged: dict[tuple, Match] = {}
    used_sources: list[str] = []
    source_status: dict[str, str] = {}
    for source in make_source_chain(prefer):
        try:
            matches: list[Match] = source.fetch_day(d)
            logger.info("数据源 %s 返回 %d 场比赛", source.name, len(matches))
            used_sources.append(source.name)
            source_status[source.name] = f"正常 · {len(matches)} 场"
            for match in matches:
                _record_source(match, source.name)
                match.tournament.level = match.tournament.level or tournament_level(
                    match.tournament.name, match.tour.value
                )
                key = _match_key(match)
                merged[key] = (
                    _merge_match(merged[key], match) if key in merged else match
                )
        except SourceError as e:
            errors.append(f"{source.name}: {e}")
            source_status[source.name] = f"失败 · {e}"
            logger.warning("数据源 %s 失败，继续使用已成功来源: %s", source.name, e)
    if not used_sources:
        raise SourceError("所有数据源均失败 — " + " | ".join(errors))
    matches = sorted(
        merged.values(),
        key=lambda m: (
            m.start_utc.isoformat() if m.start_utc else "9999",
            m.tour.value,
            m.tournament.name,
        ),
    )
    logger.info("聚合数据源 %s：去重后 %d 场", "+".join(used_sources), len(matches))
    return DailyData(
        date_beijing=d.isoformat(),
        matches=matches,
        source="+".join(used_sources),
        source_status=source_status,
        fetched_at_utc=now_utc(),
    )
