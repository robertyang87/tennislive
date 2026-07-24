import json
from datetime import date, datetime, timezone

from tennislive.digest import Digest
from tennislive.models import MatchStats, MatchStatus, StatPair, Tour
from tennislive.render.authority import (
    apply_curated_editorial,
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


def test_schedule_note_prefers_current_rank_and_stakes_over_previous_stats():
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
        round_name="Quarterfinals",
    )
    scheduled.home[0].rank = 6
    scheduled.away[0].rank = 18
    digest = _digest(result, scheduled)

    enrich_schedule_editorial(digest)

    assert scheduled.editorial_note == "郑钦文离四强席位只差一场；排名只是入场券，真正要兑现的是热门身份。"
    assert "上一轮" not in scheduled.editorial_note
    assert "Ace" not in scheduled.editorial_note
    assert scheduled.editorial_source == "实时排名与赛程"
    assert schedule_insight(scheduled) == scheduled.editorial_note


def test_previous_score_is_not_used_as_schedule_background():
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
    digest = _digest(result, scheduled)
    enrich_schedule_editorial(digest)

    assert "上一轮" not in scheduled.editorial_note
    assert "直落两盘" not in scheduled.editorial_note
    assert "6" not in scheduled.editorial_note


def test_schedule_insight_rotates_when_unplayed_fixture_persists_across_days():
    """生产事故复现（2026-07-24 日报未推送）：布拉格站女单八强布兹科娃 vs
    瓦伦托娃因官方赛程一直未定，连续两天都被选进"今晚焦点"，排名差（42）
    和轮次（四强席位）完全没变。enrich_schedule_editorial 之前不区分日期，
    两天生成的 editorial_note 逐字相同，撞上小红书近7期查重 FATAL 闸门，
    导致当天日报整包生成失败、没有推送到微信。"""
    scheduled = make_match(
        home_name="Marie Bouzkova",
        away_name="Nikola Bartunkova",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        round_name="Quarterfinals",
    )
    scheduled.home[0].seed = scheduled.away[0].seed = None
    scheduled.home[0].rank, scheduled.away[0].rank = 41, 83  # 差 42 位，命中 gap>=35 分支

    day1 = Digest(today=date(2026, 7, 23), schedule=[scheduled])
    enrich_schedule_editorial(day1)
    note_23 = scheduled.editorial_note

    scheduled.editorial_note = None  # 模拟次日重新生成，未命中已发布缓存
    day2 = Digest(today=date(2026, 7, 24), schedule=[scheduled])
    enrich_schedule_editorial(day2)
    note_24 = scheduled.editorial_note

    assert note_23 != note_24
    assert "四强席位" in note_23 and "四强席位" in note_24


def test_schedule_fallback_explains_current_stakes_without_technique_cliches():
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
    assert "四强席位" in insight
    assert "接发" not in insight and "关键分" not in insight


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
    assert "首次参加年终总决赛便闯入决赛" in scheduled.editorial_note
    assert "6比3" not in scheduled.editorial_note


def test_curated_previous_match_analysis_is_rejected(tmp_path):
    scheduled = make_match(
        home_name="Nuno Borges",
        away_name="Luciano Darderi",
        tournament="Nordea Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )
    digest = _digest(make_match(), scheduled)
    notes = {
        "2026-07-17": [
            {
                "tour": "ATP",
                "tournament_aliases": ["nordea"],
                "players": ["Nuno Borges", "Luciano Darderi"],
                "text": "博尔热斯上一轮以6比3取胜，发球表现更稳定。",
                "source_name": "ATP Tour",
                "source_url": "https://www.atptour.com/example",
            }
        ]
    }
    path = tmp_path / "editorial_notes.json"
    path.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")

    assert apply_curated_editorial(digest, path) == 0
    assert scheduled.editorial_note is None
