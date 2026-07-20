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


def test_official_exact_time_overrides_feed_time():
    match = _scheduled(datetime(2026, 7, 20, 14, tzinfo=timezone.utc))
    doc = _document(
        Fragment("Not before 1:30 PM", 100, 700),
        Fragment("BARTUNKOVA", 90, 650),
        Fragment("YUAN", 115, 620),
    )

    counts = _apply_document([match], doc)

    assert counts == {"exact": 1, "ordered": 0, "unlisted": 0}
    assert match.start_utc == datetime(2026, 7, 20, 11, 30, tzinfo=timezone.utc)
    assert match.schedule_time_status == "official-exact"
    assert "已以官方为准" in match.schedule_note


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
