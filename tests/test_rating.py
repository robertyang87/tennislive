from datetime import date, datetime, timedelta, timezone

from tennislive.digest import Digest
from tennislive.models import MatchStatus, Tour
from tennislive.render.hotspot import (
    HOTSPOT_THRESHOLD,
    hotspot_candidates,
    hotspot_post,
    hotspot_score,
    hotspot_title_candidates,
)
from tennislive.render.rating import (
    flash_candidates,
    is_upset,
    match_score,
    stay_up_stars,
    tonight_focus,
    top_results,
)
from tennislive.render.titles import flash_headline, title_candidates
from tennislive.sources.rankings import RankEntry, Rankings, _parse, rank_map

from conftest import make_match


def test_chinese_weight_is_significant_but_not_a_bypass():
    """V1 §2.2：中国相关性固定 +35（与爆冷同级），大满贯决赛不会被常规中国场次压过."""
    cn = make_match(home_name="Qinwen Zheng", home_country="CHN", tournament="Iasi Open")
    gs_final = make_match(round_name="Final", tournament="Wimbledon", match_id="x")
    non_cn = make_match(home_name="Player One", home_country="ITA", tournament="Iasi Open", match_id="y")
    assert match_score(cn) - match_score(non_cn) == 35
    assert top_results([gs_final, cn])[0] is gs_final


def test_upset_by_seed_and_rank():
    m = make_match(winner=1)  # away(种子5)赢 home(种子1)
    m.home[0].seed, m.away[0].seed = 1, 12
    assert is_upset(m)
    m2 = make_match()
    m2.home[0].seed = None
    m2.home[0].rank = 80
    m2.away[0].seed = None
    m2.away[0].rank = 5
    assert is_upset(m2)  # 排名80赢排名5


def test_stars_range():
    m = make_match(status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=())
    assert 1 <= stay_up_stars(m) <= 5


def test_flash_candidates():
    cn = make_match(home_name="Qinwen Zheng", home_country="CHN", match_id="cn")
    gs_final = make_match(round_name="Final", tournament="Wimbledon", match_id="gs")
    small_final = make_match(round_name="Final", tournament="Nordea Open Bastad", match_id="small")
    scheduled = make_match(status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(), match_id="pre")
    ids = [m.match_id for m in flash_candidates([cn, gs_final, small_final, scheduled])]
    assert "cn" in ids and "gs" in ids
    assert "small" not in ids and "pre" not in ids


def test_hotspot_engine_prefers_fresh_story_worthy_matches():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    cn = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Prague Open",
        tour=Tour.WTA,
        start_utc=now - timedelta(hours=3),
        match_id="cn-hot",
    )
    cn.tournament.tour = cn.tour
    cn.tournament.level = "WTA250"
    old = make_match(start_utc=now - timedelta(hours=14), match_id="old")
    qualifying = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Prague Open",
        tour=Tour.WTA,
        round_name="Qualification",
        start_utc=now - timedelta(hours=2),
        match_id="qualifying",
    )
    qualifying.tournament.tour = qualifying.tour
    qualifying.tournament.level = "WTA250"

    picks = hotspot_candidates([old, qualifying, cn, cn], now=now)

    assert [match.match_id for match in picks] == ["cn-hot"]
    assert hotspot_score(cn) >= HOTSPOT_THRESHOLD
    assert hotspot_score(qualifying) < HOTSPOT_THRESHOLD


def test_hotspot_package_has_three_compact_titles_and_evidence():
    match = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Wimbledon",
        match_id="story",
    )
    match.tournament.level = "GS"

    titles = hotspot_title_candidates(match)
    post = hotspot_post(match)

    assert len(titles) == 3
    assert all(len(title) <= 20 and " " not in title for title in titles)
    assert titles[0] in post
    assert "大满贯·温布尔登网球锦标赛" in post
    assert "6-4 7-6(3)" in post
    assert "一句看懂" in post


def test_flash_headline_cn_win():
    m = make_match(home_name="Qinwen Zheng", home_country="CHN", tournament="Wimbledon")
    h = flash_headline(m)
    assert "郑钦文" in h and ("晋级" in h or "夺冠" in h)


def test_title_candidates_cn_first(sample_digest):
    cands = title_candidates(sample_digest)
    assert cands and "郑钦文" in cands[0]


def test_upcoming_cn_focus_outranks_cn_loss():
    from datetime import datetime, timezone

    from tennislive.digest import Digest
    from tennislive.render.titles import title_candidates

    loss = make_match(
        home_name="Xinyu Gao", home_country="CHN", winner=1, match_id="loss"
    )
    upcoming = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 17, 14, 30, tzinfo=timezone.utc),
        match_id="upcoming",
    )
    digest = Digest(
        today=date(2026, 7, 17), results=[loss], schedule=[upcoming]
    )
    assert title_candidates(digest)[0].startswith("郑钦文22:30")


def test_tonight_focus_prefers_cn_and_known_players():
    cn = make_match(
        home_name="Qinwen Zheng", home_country="CHN",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(), match_id="cn"
    )
    star = make_match(
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(), match_id="star"
    )
    star.home[0].rank = 1
    low = make_match(
        home_name="Player A", away_name="Player B",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(), match_id="low"
    )
    low.home[0].seed = low.away[0].seed = None
    picks = tonight_focus([low, star, cn], min_n=2, max_n=3)
    assert picks[0].match_id == "cn"
    assert {m.match_id for m in picks[:2]} == {"cn", "star"}


def test_rankings_parse_and_map():
    data = {
        "rankings": [
            {
                "type": "atp",
                "ranks": [
                    {
                        "current": 1, "previous": 2, "points": 10000.0, "trend": "+1",
                        "athlete": {"id": "3623", "displayName": "Jannik Sinner"},
                    },
                    {
                        "current": 2, "previous": 1, "points": 9000.0, "trend": "-1",
                        "athlete": {"id": "1", "displayName": "Zhizhen Zhang"},
                    },
                ],
            }
        ]
    }
    entries = _parse(data)
    assert entries[0].name == "Jannik Sinner" and entries[0].move == 1
    lookup = rank_map(Rankings(atp=entries))
    assert lookup["jannik sinner"] == 1
    assert lookup["zhang zhizhen"] == 2  # 反转词序也能命中
