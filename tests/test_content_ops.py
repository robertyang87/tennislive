from datetime import date, datetime, timedelta, timezone

from tennislive.content_ops import (
    PREVIEW_DAILY_LIMIT,
    preview_candidates,
    prune_state,
    select_content,
)
from tennislive.models import MatchStatus, Tour

from conftest import make_match


def _preview(now: datetime, *, match_id: str = "preview"):
    match = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Prague Open",
        tour=Tour.WTA,
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=now + timedelta(hours=2),
        match_id=match_id,
        round_name="Round of 16",
    )
    match.tournament.level = "WTA250"
    return match


def test_preview_candidates_use_lead_window_score_and_dedupe():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    preview = _preview(now)
    too_late = _preview(now, match_id="too-late")
    too_late.start_utc = now + timedelta(minutes=20)
    qualifying = _preview(now, match_id="qualifying")
    qualifying.round_name = "Qualification"

    picks = preview_candidates(
        [too_late, qualifying, preview, preview], now=now
    )

    assert [match.match_id for match in picks] == ["preview"]


def test_content_selector_prefers_one_result_per_run():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    result = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tournament="Prague Open",
        tour=Tour.WTA,
        start_utc=now - timedelta(hours=2),
        match_id="result",
    )
    result.tournament.level = "WTA250"

    picks = select_content([_preview(now), result], now=now)

    assert [(pick.kind, pick.match.match_id) for pick in picks] == [
        ("result", "result"),
    ]


def test_content_selector_respects_legacy_dedupe_and_daily_cap():
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    preview = _preview(now)
    result = make_match(
        home_name="Qinwen Zheng",
        home_country="CHN",
        tour=Tour.WTA,
        start_utc=now - timedelta(hours=2),
        match_id="legacy-result",
    )
    result.tournament.level = "WTA250"
    state = {
        f"preview:WTA:old-{index}": "2026-07-19"
        for index in range(PREVIEW_DAILY_LIMIT)
    }

    picks = select_content(
        [result, preview],
        now=now,
        state=state,
        legacy_result_ids={"legacy-result"},
    )

    assert picks == []


def test_prune_state_retains_only_recent_entries():
    state = {
        "result:ATP:new": "2026-07-19",
        "preview:WTA:edge": "2026-07-05",
        "result:ATP:old": "2026-07-04",
    }

    assert prune_state(state, today=date(2026, 7, 19)) == {
        "result:ATP:new": "2026-07-19",
        "preview:WTA:edge": "2026-07-05",
    }
