"""Build auditable source, fact, and selection artifacts for each edition."""

from __future__ import annotations

from ..digest import Digest
from ..models import Match
from ..research.media import brief_for_match, synthesis_for_digest
from .common import group_by_tournament, match_round_display, side_display
from .rating import editorial_tonight_focus, select_lead_story


def _scoreboard_url(digest: Digest) -> str:
    day = digest.yesterday.strftime("%Y%m%d")
    return f"https://www.espn.com/tennis/scoreboard/_/date/{day}"


def _match_label(match: Match) -> str:
    return f"{side_display(match.home, with_seed=False)} vs {side_display(match.away, with_seed=False)}"


def source_manifest(digest: Digest, plan) -> dict:
    sources: list[dict] = []
    seen: set[str] = set()

    def add(name: str, url: str, *, kind: str, usage: str) -> str:
        key = url or f"{kind}:{name}"
        if key in seen:
            return key
        seen.add(key)
        sources.append(
            {
                "id": key,
                "name": name,
                "url": url,
                "kind": kind,
                "usage": usage,
            }
        )
        return key

    if digest.source:
        add(
            digest.source,
            _scoreboard_url(digest) if "espn" in digest.source.casefold() else "",
            kind="score-data",
            usage="赛程、赛果、轮次与排名快照",
        )
    if "espn" in (digest.source or "").casefold():
        add(
            "ESPN",
            _scoreboard_url(digest),
            kind="discovery-feed",
            usage="比赛覆盖、比分与时间交叉验证",
        )
    if "sofascore" in (digest.source or "").casefold():
        add(
            "SofaScore",
            "https://www.sofascore.com/tennis",
            kind="discovery-feed",
            usage="比赛补漏、比分与时间交叉验证",
        )
    for row in plan.evidence:
        add(
            row.get("source", "赛程数据"),
            row.get("url", ""),
            kind="editorial-evidence" if row.get("url") else "data-context",
            usage="人物背景或赛前看点",
        )
    for match in digest.results + digest.live + digest.schedule:
        for signal in match.trend_signals:
            add(
                signal.get("source", "趋势雷达"),
                signal.get("url", ""),
                kind=signal.get("kind", "trend-signal"),
                usage="选题热度判断；不直接作为比赛事实",
            )
        for url in match.schedule_source_urls:
            name = next(
                (
                    source
                    for source in match.data_sources
                    if "官方 OOP" in source
                ),
                "巡回赛官方 OOP",
            )
            add(
                name,
                url,
                kind="official-order-of-play",
                usage="核验比赛日期、场序与开赛时间性质",
            )
        brief = brief_for_match(match, digest.today)
        if brief is None:
            continue
        for source in brief.sources:
            add(
                source.name,
                source.url,
                kind="media-analysis",
                usage=source.lens or "外媒观点摘要",
            )
    return {
        "edition": digest.today.isoformat(),
        "policy": "只发布原创摘要；媒体正文、摄影与视频不进入仓库。",
        "sources": sources,
    }


def fact_ledger(digest: Digest) -> dict:
    claims: list[dict] = []
    score_source = _scoreboard_url(digest) if "espn" in (digest.source or "").casefold() else ""
    for match in digest.results:
        if not match.status.is_final:
            continue
        group = group_by_tournament([match])[0]
        claims.append(
            {
                "match_id": match.match_id,
                "kind": "verified-result",
                "claim": (
                    f"{group.name_zh} {match_round_display(match)}："
                    f"{_match_label(match)}，{match.score_display(from_winner=True)}"
                ).strip("，"),
                "source": digest.source or "赛果数据",
                "url": score_source,
            }
        )
        brief = brief_for_match(match, digest.today)
        if brief is not None:
            claims.extend(
                {
                    "match_id": match.match_id,
                    "kind": kind,
                    "claim": text,
                    "source": brief.source_label,
                    "urls": [source.url for source in brief.sources],
                }
                for kind, text in (
                    ("media-consensus", brief.consensus),
                    ("media-divergence", brief.divergence),
                    ("media-data-point", brief.data_point),
                    ("editorial-takeaway", brief.takeaway),
                )
                if text
            )
    for match in digest.schedule:
        if not match.schedule_time_status:
            continue
        claims.append(
            {
                "match_id": match.match_id,
                "kind": "schedule-verification",
                "claim": match.schedule_note or match.schedule_time_status,
                "status": match.schedule_time_status,
                "observations": match.time_observations,
                "sources": match.data_sources,
                "urls": match.schedule_source_urls,
            }
        )
    return {
        "edition": digest.today.isoformat(),
        "generated_from_snapshot": True,
        "claims": claims,
    }


def editorial_decision(digest: Digest) -> dict:
    selection = select_lead_story(digest)
    focus = editorial_tonight_focus(digest.schedule)
    if selection is None:
        lead = None
    else:
        lead = {
            "match_id": selection.match.match_id,
            "score": selection.score,
            "reasons": list(selection.reasons),
            "breakdown": selection.breakdown.__dict__,
            "has_media_brief": brief_for_match(selection.match, digest.today) is not None,
        }
    return {
        "edition": digest.today.isoformat(),
        "editorial_promise": "一夜只选一条主线，并说明它为什么值得记住。",
        "lead": lead,
        "tonight_focus": [match.match_id for match in focus],
        "constraints": [
            "中国球员和知名球员单打优先",
            "排名不能单独构成看点",
            "无授权技术统计时不生成伪专业页",
            "外媒观点必须保留原文链接",
        ],
    }


def evidence_artifacts(digest: Digest, plan) -> dict[str, dict]:
    return {
        "source_manifest.json": source_manifest(digest, plan),
        "fact_ledger.json": fact_ledger(digest),
        "editorial_decision.json": editorial_decision(digest),
        "media_synthesis.json": synthesis_for_digest(digest),
    }
