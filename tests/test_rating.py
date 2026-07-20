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
    lead_story_breakdown,
    match_score,
    select_lead_story,
    stay_up_stars,
    tonight_focus,
    tonight_event_focus,
    top_results,
)
from tennislive.render.titles import daily_lead_match, flash_headline, title_candidates
from tennislive.sources.rankings import RankEntry, Rankings, _parse, rank_map

from conftest import make_match


def test_chinese_weight_is_significant_but_not_a_bypass():
    """V1 §2.2：中国相关性固定 +35（与爆冷同级），大满贯决赛不会被常规中国场次压过."""
    cn = make_match(home_name="Qinwen Zheng", home_country="CHN", tournament="Iasi Open")
    gs_final = make_match(round_name="Final", tournament="Wimbledon", match_id="x")
    non_cn = make_match(home_name="Player One", home_country="ITA", tournament="Iasi Open", match_id="y")
    assert match_score(cn) - match_score(non_cn) == 35
    assert top_results([gs_final, cn])[0] is gs_final


def test_chinese_weight_is_exactly_35_for_doubles_too():
    from tennislive.models import Player

    cn = make_match(home_name="Qinwen Zheng", home_country="CHN")
    cn.home.append(Player(name="Xinyu Wang", country="CHN"))
    cn.away.append(Player(name="Player Four", country="USA"))
    non_cn = make_match(
        home_name="Player One", home_country="ITA", match_id="non-cn-doubles"
    )
    non_cn.home.append(Player(name="Player Three", country="FRA"))
    non_cn.away.append(Player(name="Player Four", country="USA"))

    assert cn.is_doubles and non_cn.is_doubles
    assert match_score(cn) - match_score(non_cn) == 35
    assert match_score(cn, cn_boost=False) == match_score(
        non_cn, cn_boost=False
    )


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
    assert "6-4 7-6(3)" not in post
    assert "刚刚结束，但这场不该只看比分" in post
    assert "📝 我的一票" in post
    assert "💬 留个答案" in post


def test_flash_headline_cn_win():
    m = make_match(home_name="Qinwen Zheng", home_country="CHN", tournament="Wimbledon")
    h = flash_headline(m)
    assert "郑钦文" in h and "晋级男单决赛" in h


def test_flash_headline_advances_from_current_round():
    semifinal = make_match(
        home_name="Jannik Sinner",
        away_name="Novak Djokovic",
        round_name="Semifinals",
    )
    quarterfinal = make_match(
        home_name="Jannik Sinner",
        away_name="Novak Djokovic",
        round_name="Quarterfinals",
        match_id="qf",
    )

    assert "晋级温布尔登网球锦标赛男单决赛" in flash_headline(semifinal)
    assert "晋级温布尔登网球锦标赛男单半决赛" in flash_headline(quarterfinal)


def test_title_candidates_follow_shared_lead(sample_digest):
    cands = title_candidates(sample_digest)
    lead = daily_lead_match(sample_digest)
    assert lead is not None and lead.match_id == "m2"
    assert cands and "郑钦文" in cands[0]


def test_upcoming_cn_focus_is_retained_without_bypassing_result_lead():
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
    candidates = title_candidates(digest)
    assert not candidates[0].startswith("郑钦文22:30")
    assert any(candidate.startswith("郑钦文22:30") for candidate in candidates)


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


def test_tonight_focus_spreads_five_matches_across_four_events():
    matches = []
    for index, tournament in enumerate(
        ["Prague Open", "Prague Open", "Prague Open", "Kitzbuhel Open", "Estoril Open", "Hamburg Open"]
    ):
        match = make_match(
            home_name=f"Player {index}A",
            away_name=f"Player {index}B",
            tournament=tournament,
            status=MatchStatus.SCHEDULED,
            winner=None,
            sets=(),
            tiebreaks=(),
            match_id=f"event-{index}",
        )
        match.home[0].rank = index + 1
        matches.append(match)

    picks = tonight_focus(matches, min_n=3, max_n=5)
    events = [match.tournament.name for match in picks]

    assert len(picks) == 5
    assert len(set(events)) == 4
    assert events.count("Prague Open") == 2


def test_tonight_event_focus_builds_one_page_per_250_plus_event():
    events = []
    for tournament, level in (
        ("Prague Open", "WTA250"),
        ("Hamburg Open", "WTA250"),
        ("Kitzbuhel Open", "ATP250"),
        ("Millennium Estoril Open", "ATP250"),
        ("Palermo 125", "WTA125"),
    ):
        for index in range(3):
            match = make_match(
                home_name=f"{tournament} Player {index}A",
                away_name=f"{tournament} Player {index}B",
                tournament=tournament,
                status=MatchStatus.SCHEDULED,
                winner=None,
                sets=(),
                tiebreaks=(),
                match_id=f"{tournament}-{index}",
            )
            match.tournament.level = level
            events.append(match)

    pages = tonight_event_focus(events)

    assert len(pages) == 4
    assert all(2 <= len(page) <= 5 for page in pages)
    assert {page[0].tournament.name for page in pages} == {
        "Prague Open",
        "Hamburg Open",
        "Kitzbuhel Open",
        "Millennium Estoril Open",
    }


def test_tonight_event_focus_prioritizes_singles_and_uses_doubles_only_as_fill():
    singles = make_match(
        home_name="Singles A",
        away_name="Singles B",
        tournament="Millennium Estoril Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        match_id="estoril-singles",
    )
    doubles = make_match(
        home_name="Doubles A",
        away_name="Doubles C",
        tournament="Millennium Estoril Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        discipline="Men's Doubles",
        match_id="estoril-doubles",
    )
    doubles.home.append(doubles.home[0])
    doubles.away.append(doubles.away[0])
    spare_doubles = make_match(
        home_name="Doubles E",
        away_name="Doubles G",
        tournament="Millennium Estoril Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        discipline="Men's Doubles",
        match_id="estoril-spare-doubles",
    )
    spare_doubles.home.append(spare_doubles.home[0])
    spare_doubles.away.append(spare_doubles.away[0])

    pages = tonight_event_focus([spare_doubles, doubles, singles])

    assert len(pages) == 1
    assert len(pages[0]) == 2
    assert pages[0][0] is singles
    assert pages[0][1] in (doubles, spare_doubles)


def test_lead_story_explains_china_headliner_stage_and_official_evidence():
    chinese = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="China Open",
        tour=Tour.WTA,
        round_name="Semifinals",
        match_id="cn-evidence",
    )
    chinese.tournament.level = "WTA500"
    chinese.editorial_note = "官方赛后报道摘要"
    chinese.editorial_source = "WTA"
    chinese.editorial_url = "https://www.wtatennis.com/news/example"
    comparable = make_match(
        tournament="Halle Open",
        round_name="Semifinals",
        match_id="star-no-evidence",
    )
    comparable.tournament.level = "ATP500"
    digest = Digest(today=date(2026, 7, 20), results=[comparable, chinese])

    selected = select_lead_story(digest)

    assert selected is not None and selected.match is chinese
    assert selected.breakdown.china == 45
    assert selected.breakdown.evidence == 20
    assert "中国球员相关" in selected.reasons
    assert "处于半决赛" in selected.reasons
    assert "有WTA原文支撑" in selected.reasons


def test_lead_story_keeps_major_final_above_routine_chinese_result():
    chinese = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Iasi Open",
        round_name="Round of 32",
        match_id="cn-routine",
    )
    chinese.tournament.level = "WTA250"
    major = make_match(
        tournament="Wimbledon",
        round_name="Final",
        match_id="major-final",
    )
    major.tournament.level = "GS"
    digest = Digest(today=date(2026, 7, 20), results=[chinese, major])

    selected = select_lead_story(digest)

    assert selected is not None and selected.match is major
    assert selected.breakdown.event == 50
    assert selected.breakdown.stage == 35


def test_lead_story_recaps_a_result_before_previewing_schedule():
    result = make_match(
        tournament="Iasi Open",
        round_name="Round of 32",
        match_id="finished",
    )
    result.tournament.level = "ATP250"
    scheduled = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Wimbledon",
        round_name="Final",
        match_id="scheduled",
    )
    scheduled.tournament.level = "GS"
    digest = Digest(today=date(2026, 7, 20), results=[result], schedule=[scheduled])

    selected = select_lead_story(digest)

    assert selected is not None and selected.match is result
    assert "已有完整赛果可复盘" in selected.reasons


def test_lead_story_score_does_not_reward_an_upset():
    upset = make_match(match_id="upset", winner=0)
    upset.home[0].seed = upset.away[0].seed = None
    upset.home[0].rank, upset.away[0].rank = 80, 5
    expected = make_match(match_id="expected", winner=1)
    expected.home[0].seed = expected.away[0].seed = None
    expected.home[0].rank, expected.away[0].rank = 80, 5

    upset_breakdown, upset_reasons = lead_story_breakdown(upset)
    expected_breakdown, _ = lead_story_breakdown(expected)

    assert is_upset(upset) and not is_upset(expected)
    assert upset_breakdown.total == expected_breakdown.total
    assert all("爆冷" not in reason and "冷门" not in reason for reason in upset_reasons)


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
