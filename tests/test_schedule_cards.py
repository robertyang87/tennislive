"""今日赛程卡：预计时间的推算、取材优先级、分页、以及"不带看点"。

这些规则都是踩过之后定下来的，落成测试而不是只写在注释里：
- 2026-07-28 那天 32 场里有 16 场 ESPN 只给轮次不给时间，卡上一律「待官方排期」
- 同一天混进来一个 WTA 125，13 场比三个巡回赛级别赛事加起来还多
- 7 场按 6 切会把第二页留成一张孤卡，整页九成是空的
"""

from datetime import datetime, timezone

from tennislive.models import MatchStatus, Player, Tour
from tennislive.render.schedule_time import (
    ESTIMABLE_PLACEHOLDERS,
    has_estimated_times,
    match_key,
    round_rank,
    schedule_time_display,
)
from tennislive.render.webcards import (
    SCHEDULE_PER_PAGE,
    TOUR_LEVELS,
    _balanced_chunks,
    _schedule_selection,
    schedule_body,
    schedule_pages,
)

from conftest import make_match

UTC = timezone.utc


def sched(
    *,
    match_id,
    round_name="Round 1",
    start=None,
    status_text=None,
    tournament="Mubadala DC Open",
    tour=Tour.ATP,
    discipline="Men's Singles",
    home="Alpha Player",
    away="Beta Player",
    home_country="USA",
    away_country="FRA",
    doubles=False,
):
    m = make_match(
        match_id=match_id,
        tournament=tournament,
        tour=tour,
        round_name=round_name,
        discipline=discipline,
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=start,
        home_name=home,
        away_name=away,
        home_country=home_country,
        away_country=away_country,
    )
    if doubles:
        # Match.is_doubles 看的是每边的人数，不是 discipline 字段——只改
        # discipline 造出来的仍是单打，测试会静默地什么也没验到。
        m.home.append(Player(name="Alpha Partner", country=home_country))
        m.away.append(Player(name="Beta Partner", country=away_country))
    m.schedule_time_status = status_text
    return m


# ---------- 预计时间 ----------


def test_later_round_without_a_time_is_anchored_after_the_earlier_round():
    """后一轮必然排在同赛事同项目前一轮的最后一场之后——这是赛制决定的下界。"""
    r1_early = sched(match_id="a", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
                     status_text="single-source")
    r1_late = sched(match_id="b", start=datetime(2026, 7, 28, 17, 0, tzinfo=UTC),
                    status_text="single-source")
    r2 = sched(match_id="c", round_name="Round 2", status_text="unpublished")

    display = schedule_time_display([r1_early, r1_late, r2])
    # 17:00 UTC = 北京 01:00（次日）；取的是前一轮最晚的一场，不是最早的
    assert display[match_key(r2)] == "01:00 后*"


def test_same_round_borrows_its_own_disciplines_start_time():
    """同轮次通常同一时段开赛；先按同项目找，找不到才放开。"""
    singles = sched(match_id="s", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
                    status_text="single-source")
    doubles_known = sched(
        match_id="d1", discipline="Men's Doubles", doubles=True, status_text="single-source",
        start=datetime(2026, 7, 28, 16, 30, tzinfo=UTC),
    )
    doubles_blank = sched(
        match_id="d2", discipline="Men's Doubles", doubles=True, status_text="unpublished"
    )

    display = schedule_time_display([singles, doubles_known, doubles_blank])
    # 借的是同为双打的 16:30（北京 00:30），不是单打那场的 15:00
    assert display[match_key(doubles_blank)] == "预计 00:30*"


def test_an_event_with_no_known_time_at_all_stays_unscheduled():
    """一个已知时间都没有时，宁可承认不知道，也不拿平均值糊上去。"""
    lonely = sched(match_id="x", round_name="Round 2", status_text="unpublished")
    display = schedule_time_display([lonely])
    assert display[match_key(lonely)] in ESTIMABLE_PLACEHOLDERS


def test_estimates_never_cross_events():
    """别的赛事的开赛时间不是这场的证据。"""
    dc = sched(match_id="dc", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
               status_text="single-source")
    memphis = sched(match_id="mem", round_name="Round 2", status_text="unpublished",
                    tournament="The Memphis Classic", tour=Tour.WTA,
                    discipline="Women's Singles")
    display = schedule_time_display([dc, memphis])
    assert display[match_key(memphis)] in ESTIMABLE_PLACEHOLDERS


def test_conflicting_sources_are_not_papered_over_with_an_estimate():
    """「时间待核」是多源冲突，用推算覆盖它等于把冲突藏起来。"""
    known = sched(match_id="k", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
                  status_text="single-source")
    conflicted = sched(match_id="c", round_name="Round 2", status_text="conflict")
    display = schedule_time_display([known, conflicted])
    assert display[match_key(conflicted)] == "时间待核"


def test_an_official_exact_time_is_never_overwritten():
    exact = sched(match_id="e", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
                  status_text="official-exact")
    display = schedule_time_display([exact])
    assert display[match_key(exact)] == "23:00"
    assert "*" not in display[match_key(exact)]


def test_estimate_marker_drives_the_footnote():
    assert has_estimated_times(["23:00", "预计 22:00*"])
    assert not has_estimated_times(["23:00", "待官方排期"])


def test_round_rank_puts_earlier_rounds_higher():
    """推算依赖这个方向：第一轮的权重必须大于第二轮、决赛最小。"""
    r1 = sched(match_id="1", round_name="Round 1")
    r2 = sched(match_id="2", round_name="Round 2")
    final = sched(match_id="f", round_name="Final")
    assert round_rank(r1) > round_rank(r2) > round_rank(final)


# ---------- 取材优先级 ----------


def test_chinese_singles_come_first():
    """优先中国单打。"""
    plain = sched(match_id="p")
    cn = sched(match_id="cn", home="Zhizhen Zhang", home_country="CHN")
    selected = _schedule_selection([plain, cn])
    assert selected[0].match_id == "cn"


def test_a_chinese_doubles_never_outranks_a_singles_match():
    """「优先中国球员」限定在单打上。

    一场中国组合的双打排在大坂直美那种单打前面，不是读者要的——所以中国
    这一维只在单打内部生效，不越过"单打先于双打"这条线。
    """
    singles = sched(match_id="s")
    cn_doubles = sched(
        match_id="cn", discipline="Men's Doubles", doubles=True,
        home="Zhizhen Zhang", home_country="CHN",
    )
    selected = _schedule_selection([cn_doubles, singles])
    assert [m.match_id for m in selected] == ["s", "cn"]


def test_singles_outrank_doubles_after_chinese_players():
    doubles = sched(match_id="d", discipline="Men's Doubles", doubles=True)
    singles = sched(match_id="s")
    selected = _schedule_selection([doubles, singles])
    assert [m.match_id for m in selected] == ["s", "d"]


def test_doubles_only_fill_the_space_singles_leave_behind():
    """双打是填空位的，不许把单打挤到多出来的一页上。"""
    singles = [sched(match_id=f"s{i}") for i in range(SCHEDULE_PER_PAGE)]
    doubles = [
        sched(match_id=f"d{i}", discipline="Men's Doubles", doubles=True) for i in range(4)
    ]
    selected = _schedule_selection(singles + doubles)
    assert len(selected) == SCHEDULE_PER_PAGE
    assert all(m.is_singles for m in selected)


def test_doubles_do_get_added_when_the_page_has_room():
    singles = [sched(match_id=f"s{i}") for i in range(3)]
    doubles = [
        sched(match_id=f"d{i}", discipline="Men's Doubles", doubles=True) for i in range(5)
    ]
    selected = _schedule_selection(singles + doubles)
    assert len(selected) == SCHEDULE_PER_PAGE
    assert sum(1 for m in selected if m.is_doubles) == SCHEDULE_PER_PAGE - 3


# ---------- 分页 ----------


def test_balanced_chunks_do_not_leave_an_orphan_page():
    """7 场按 6 硬切会留下一张孤卡；均分成 4+3。"""
    assert [len(c) for c in _balanced_chunks(list(range(7)), 6)] == [4, 3]
    assert [len(c) for c in _balanced_chunks(list(range(13)), 6)] == [5, 4, 4]
    assert [len(c) for c in _balanced_chunks(list(range(4)), 6)] == [4]


def test_no_page_exceeds_the_per_page_limit():
    for total in range(1, 40):
        for chunk in _balanced_chunks(list(range(total)), SCHEDULE_PER_PAGE):
            assert 0 < len(chunk) <= SCHEDULE_PER_PAGE


# ---------- 分组与级别 ----------


def test_atp_and_wta_of_the_same_event_are_separate_pages():
    """同名赛事的两个巡回赛必须各自成页——今晚焦点页那边是合并的，这里不要。"""
    atp = sched(match_id="a", tour=Tour.ATP, discipline="Men's Singles")
    wta = sched(match_id="w", tour=Tour.WTA, discipline="Women's Singles")
    pages = schedule_pages([atp, wta], "7.28")
    assert len(pages) == 2
    bodies = "".join(body for _kind, body in pages)
    assert bodies.count("Today's Schedule · 今日赛程") == 2


def test_below_tour_level_events_are_dropped():
    """WTA 125 / 挑战赛不进今日赛程。"""
    tour_level = sched(match_id="t")
    minor = sched(
        match_id="m", tournament="Axeria Open 2026 powered by Intaro Sport",
        tour=Tour.WTA, discipline="Women's Singles",
    )
    pages = schedule_pages([tour_level, minor], "7.28")
    assert len(pages) == 1
    assert "Axeria" not in pages[0][1]
    # 关掉开关就应该两个都在
    assert len(schedule_pages([tour_level, minor], "7.28", tour_level_only=False)) == 2


def test_tour_levels_cover_every_badge_the_grouping_can_produce():
    """级别白名单和 compact_level 的取值必须对得上，否则会静默丢掉整个赛事。"""
    from tennislive.render.common import LEVEL_COMPACT_BADGE

    for level in LEVEL_COMPACT_BADGE:
        assert level in TOUR_LEVELS, f"{level} 不在 TOUR_LEVELS 里，会被整站挡掉"


# ---------- 页面本身 ----------


def test_schedule_page_has_no_viewing_angle_line():
    """赛程卡不带看点——那是今晚焦点页的东西。"""
    body = schedule_body([sched(match_id="a")], "7.28")
    assert 'class="reason"' not in body
    assert "看点" not in body


def test_schedule_page_keeps_the_glass_panel_of_the_tonight_card():
    """去掉看点不等于退回素卡：压在地标照片上仍要那层玻璃面板。"""
    body = schedule_body([sched(match_id="a")], "7.28")
    assert "card pick" in body


def test_schedule_page_centres_its_fixtures():
    """赛程居中：卡片前后各一个弹性 spacer。今晚焦点只有前面一个（卡片沉底）。"""
    body = schedule_body([sched(match_id="a")], "7.28")
    assert body.count('<div class="event-spacer') == 2
    assert "event-spacer-tail" in body


def test_schedule_page_shows_the_estimated_time_not_the_placeholder():
    known = sched(match_id="k", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
                  status_text="single-source")
    blank = sched(match_id="b", round_name="Round 2", status_text="unpublished")
    body = schedule_body([known, blank], "7.28")
    assert "23:00 后*" in body
    assert "待官方排期" not in body


def test_schedule_page_marks_the_estimate_footnote():
    blank = sched(match_id="b", status_text="unpublished")
    known = sched(match_id="k", start=datetime(2026, 7, 28, 15, 0, tzinfo=UTC),
                  status_text="single-source")
    assert "*为预计时间" in schedule_body([known, blank], "7.28")


def test_every_match_shows_its_court_when_the_feed_gives_one():
    """有场地就标，没有就空着——赛程最实用的就是「几点、在哪块场」。"""
    a = sched(match_id="a")
    b = sched(match_id="b")
    a.court = b.court = "Stadium"
    assert schedule_body([a, b], "7.28").count("Stadium") == 2
    b.court = "Court 4"
    body = schedule_body([a, b], "7.28")
    assert "Stadium" in body and "Court 4" in body


def test_a_match_without_a_court_just_omits_it():
    body = schedule_body([sched(match_id="a")], "7.28")
    assert "·  ·" not in body and "· </span>" not in body


def test_page_number_appears_only_when_there_is_more_than_one_page():
    single = schedule_body([sched(match_id="a")], "7.28", page=1, total=1)
    assert "· 1/1" not in single
    paged = schedule_body([sched(match_id="a")], "7.28", page=1, total=2)
    assert "· 1/2" in paged


# ---------- 推送文案 ----------


def _cn_lead():
    m = sched(
        match_id="z", tour=Tour.WTA, discipline="Women's Singles",
        start=datetime(2026, 7, 28, 17, 0, tzinfo=UTC), status_text="single-source",
        home="Alexandra Eala", home_country="PHI",
        away="Zheng Qinwen", away_country="CHN",
    )
    m.home[0].rank, m.home[0].seed = 28, None
    m.away[0].rank, m.away[0].seed = 123, None
    m.court = "Stadium"
    return m


def test_title_fits_the_xiaohongshu_budget():
    """标题超过 20 字左右会被小红书截断，读者看到的是半句话。"""
    from datetime import date

    from tennislive.render.schedule_post import TITLE_MAX, _width, post_title

    title = post_title(date(2026, 7, 28), _cn_lead())
    assert _width(title) <= TITLE_MAX, title
    assert title.startswith("7.28 今日赛程 | ")


def test_title_never_drops_the_two_names():
    """砍长度时球场、排名、轮次都能丢，两个人名不能——那是读者点进来的理由。"""
    from datetime import date

    from tennislive.render.schedule_post import post_title

    title = post_title(date(2026, 7, 28), _cn_lead())
    assert "郑钦文" in title and "伊埃拉" in title


def test_lead_prefers_the_chinese_match_with_the_stronger_opponent():
    """同为中国单打时看对手排名——对手越强，这一问越有分量。"""
    from tennislive.render.schedule_post import pick_lead

    strong = _cn_lead()
    weak = sched(
        match_id="w", tour=Tour.WTA, discipline="Women's Singles",
        home="Wang Xinyu", home_country="CHN", away="Julieta Pareja",
    )
    weak.home[0].rank, weak.home[0].seed = 42, None
    weak.away[0].rank, weak.away[0].seed = None, None
    assert pick_lead([weak, strong]) is strong


def test_body_only_lists_matches_that_are_on_the_cards():
    """正文和图对不上，读者第一眼就发现。"""
    from tennislive.render.schedule_post import post_body

    a, b = sched(match_id="a"), sched(match_id="b")
    display = schedule_time_display([a, b])
    body = post_body([a], display)
    assert "Alpha Player" in body or "阿尔法" in body
    assert body.count("·") >= 1
