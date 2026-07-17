from datetime import date, datetime, timezone

from tennislive.digest import Digest
from tennislive.models import MatchStats, MatchStatus, StatPair, Tour
from tennislive.render.authority import (
    apply_curated_editorial,
    build_schedule_evidence,
    enrich_schedule_editorial,
)
from tennislive.render.story import schedule_insight

from conftest import make_match


def _digest(result, scheduled, source="espn+sofascore"):
    return Digest(
        today=date(2026, 7, 17),
        results=[result],
        schedule=[scheduled],
        source=source,
    )


def test_official_stats_become_attributed_schedule_note():
    result = make_match(
        home_name="Qinwen Zheng",
        away_name="Maria Sakkari",
        home_country="CHN",
        away_country="GRE",
        tournament="Athens",
        tour=Tour.WTA,
        sets=((6, 3), (6, 2)),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    result.stats = MatchStats(
        source="Sportradar 授权网球数据",
        aces=StatPair(8, 2),
        first_serve_won_pct=StatPair(78, 61),
        break_points_won=StatPair(4, 1),
        break_points_chances=StatPair(9, 3),
    )
    scheduled = make_match(
        home_name="Qinwen Zheng",
        away_name="Barbora Krejcikova",
        home_country="CHN",
        away_country="CZE",
        tournament="Athens",
        tour=Tour.WTA,
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 17, 14, tzinfo=timezone.utc),
    )
    digest = _digest(result, scheduled)

    enrich_schedule_editorial(digest)

    assert "Sportradar授权技术统计" in scheduled.editorial_note
    assert "郑钦文上一轮8记Ace" in scheduled.editorial_note
    assert "一发得分率78%" in scheduled.editorial_note
    assert scheduled.editorial_source == "Sportradar 授权网球数据"
    assert schedule_insight(scheduled) == scheduled.editorial_note


def test_official_score_fallback_describes_straight_sets_without_rank_hype():
    result = make_match(
        home_name="Qinwen Zheng",
        away_name="Maria Sakkari",
        home_country="CHN",
        away_country="GRE",
        tournament="Athens",
        tour=Tour.WTA,
        sets=((6, 2), (6, 3)),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    scheduled = make_match(
        home_name="Qinwen Zheng",
        away_name="Barbora Krejcikova",
        home_country="CHN",
        away_country="CZE",
        tournament="Athens",
        tour=Tour.WTA,
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 17, 14, tzinfo=timezone.utc),
    )
    evidence = build_schedule_evidence(_digest(result, scheduled), scheduled)

    assert evidence is not None
    assert evidence.text == "聚合赛果：郑钦文上一轮直落两盘过关，仅丢5局"
    assert "种子" not in evidence.text


def test_unrelated_tournament_is_not_used_as_previous_round():
    result = make_match(tournament="Iasi")
    scheduled = make_match(
        tournament="Umag",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )

    assert build_schedule_evidence(_digest(result, scheduled), scheduled) is None


def test_schedule_fallback_uses_round_and_observation_not_seed():
    scheduled = make_match(
        home_name="Qinwen Zheng",
        away_name="Barbora Krejcikova",
        home_country="CHN",
        away_country="CZE",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        round_name="Quarterfinals",
    )

    insight = schedule_insight(scheduled)
    assert "四分之一决赛" in insight
    assert "接发" in insight and "关键分" in insight
    assert "种子" not in insight


def test_curated_media_note_wins_and_keeps_source_url():
    result = make_match(tournament="Vanda Pharmaceuticals Athens Open")
    scheduled = make_match(
        home_name="Barbora Krejcikova",
        away_name="Zheng Qinwen",
        home_country="CZE",
        away_country="CHN",
        tournament="Vanda Pharmaceuticals Athens Open",
        tour=Tour.WTA,
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )
    digest = _digest(result, scheduled)

    assert apply_curated_editorial(digest) == 1
    enrich_schedule_editorial(digest)

    assert scheduled.editorial_source == "WTA"
    assert scheduled.editorial_url.startswith("https://www.wtatennis.com/")
    assert "6比3、7比5" in scheduled.editorial_note
