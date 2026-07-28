from datetime import date, datetime, timezone

from conftest import make_match

from tennislive.models import MatchStatus
from tennislive.sources.official_schedule import (
    Fragment,
    OfficialDocument,
    OfficialEvent,
    _apply_document,
)


EVENT = OfficialEvent(
    tour="WTA",
    aliases=("Example Open",),
    source="WTA 官方 OOP",
    url="https://example.test/{year}/op.pdf",
    timezone="Europe/Prague",
)


def _document(*fragments):
    return OfficialDocument(
        event=EVENT,
        url="https://example.test/2026/op.pdf",
        play_date=date(2026, 7, 20),
        text="ORDER OF PLAY - MONDAY, 20 JULY 2026",
        fragments=tuple(fragments),
    )


def _scheduled(start_utc=None):
    return make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        tournament="Example Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=start_utc,
        match_id="focus",
    )


def test_official_time_overrides_feed_time():
    match = _scheduled(datetime(2026, 7, 20, 14, tzinfo=timezone.utc))
    doc = _document(
        Fragment("Not before 1:30 PM", 100, 700),
        Fragment("BARTUNKOVA", 90, 650),
        Fragment("YUAN", 115, 620),
    )

    counts = _apply_document([match], doc)

    # 聚合源说 14:00，官方说 11:30——差 2.5 小时，算一次"两源不一致"。
    # 这个计数是这条线唯一能自证在做交叉校验的证据：全是 conflict 就说明
    # 某一侧（多半是时区或场序解析）系统性错了，而卡面上看不出差别。
    assert counts == {
        "exact": 0, "not_before": 1, "ordered": 0, "unlisted": 0,
        "conflict": 1, "agree": 0,
    }
    assert match.start_utc == datetime(2026, 7, 20, 11, 30, tzinfo=timezone.utc)
    assert "已以官方为准" in match.schedule_note


def test_starts_at_and_not_before_are_two_different_things():
    """`Starts At` 是这块场地这一节的首场，到点就打；`Not Before` 只是下界。

    原来两种都记 `official-exact`，卡上一律印裸时间。郑钦文那场是
    `Not Before 1:00 AM`，跟在 23:00 那场后面——前一场打成三盘就得往后拖，
    印成"01:00"等于告诉熬夜的人到点开电视。
    """
    firm = _scheduled(datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc))
    floor = _scheduled(datetime(2026, 7, 20, 17, 30, tzinfo=timezone.utc))

    firm_counts = _apply_document([firm], _document(
        Fragment("Starts At 1:30 PM", 100, 700),
        Fragment("BARTUNKOVA", 90, 650),
        Fragment("YUAN", 115, 620),
    ))
    floor_counts = _apply_document([floor], _document(
        Fragment("Not before 1:30 PM", 100, 700),
        Fragment("BARTUNKOVA", 90, 650),
        Fragment("YUAN", 115, 620),
    ))

    # 时刻是同一个，口径不是
    assert firm.start_utc == floor.start_utc
    assert firm.schedule_time_status == "official-exact"
    assert floor.schedule_time_status == "official-not-before"
    assert firm_counts["exact"] == 1 and firm_counts["not_before"] == 0
    assert floor_counts["not_before"] == 1 and floor_counts["exact"] == 0
    # 口径差别要落进 note，否则只有 status 知道，人看不见
    assert "需等前一场结束" in (floor.schedule_note or "")
    assert "需等前一场结束" not in (firm.schedule_note or "")


def test_matching_feed_time_counts_as_agreement_not_conflict():
    """两源对得上时不能记成冲突——否则 conflict 恒为正，计数就没有判别力了。"""
    match = _scheduled(datetime(2026, 7, 20, 11, 30, tzinfo=timezone.utc))
    doc = _document(
        Fragment("Not before 1:30 PM", 100, 700),
        Fragment("BARTUNKOVA", 90, 650),
        Fragment("YUAN", 115, 620),
    )

    counts = _apply_document([match], doc)

    # 「不早于」照样参与交叉校验：口径是下界，时刻仍然是两源都给出的那个
    assert counts == {
        "exact": 0, "not_before": 1, "ordered": 0, "unlisted": 0,
        "conflict": 0, "agree": 1,
    }
    assert "已以官方为准" not in (match.schedule_note or "")


def test_official_followed_by_marks_feed_time_as_estimate():
    original = datetime(2026, 7, 20, 14, tzinfo=timezone.utc)
    match = _scheduled(original)
    doc = _document(
        Fragment("Followed by", 100, 700),
        Fragment("BARTUNKOVA", 90, 650),
        Fragment("YUAN", 115, 620),
    )

    counts = _apply_document([match], doc)

    assert counts["ordered"] == 1
    assert match.start_utc == original
    assert match.schedule_time_status == "official-order-estimate"


def test_official_current_oop_unlisted_waits_for_next_release():
    match = _scheduled(None)

    counts = _apply_document([match], _document(Fragment("Someone Else", 10, 10)))

    assert counts["unlisted"] == 1
    assert match.schedule_time_status == "official-unlisted"
    assert "等待下一版官方排期" in match.schedule_note
