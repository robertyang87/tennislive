from datetime import date, datetime, timedelta, timezone

from tennislive.content_ops import (
    PREVIEW_DAILY_LIMIT,
    RESULT_DAILY_LIMIT,
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


def test_即时赛果停掉之后同样的候选只会选出赛前焦点():
    """这条原来叫 `..._prefers_one_result_per_run`，断言的是「result 优先」。

    **2026-07-31 那个前提没了**：账号所有者「即时赛果推送也不要了」，
    `RESULT_DAILY_LIMIT` 归零。同样喂进一个刚完赛的热点和一个赛前焦点，
    现在只该出赛前焦点——`result` 那一路名额是 0，一条都取不进去。

    改成记录新行为而不是删掉：这两路的取舍是内容雷达的核心，
    留一条能看出「现在是什么样」的测试比留一片空白强。
    """
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

    kinds = [(pick.kind, pick.match.match_id) for pick in picks]
    assert not [k for k in kinds if k[0] == "result"], (
        f"即时赛果又被选出来了：{kinds}")
    assert kinds == [("preview", "preview")], (
        f"赛前焦点那一半是「其他的可以保留」，不该跟着一起没：{kinds}")


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


def test_赛前焦点不再限制每天一条():
    """账号所有者 2026-08-05：「不要限制只有一条」。

    那个 1 是**冷启动期的频控**（playbook：「避免低粉阶段高频刷屏」），
    挡的是「今天已经发过一条了」，不是「这条不值得发」。编辑闸另有其人，
    没动：`PREVIEW_THRESHOLD = 38` 和 45–210 分钟的发布窗口。

    ⚠️ 判据钉的是**一轮能取出多条**，不是那两个常量等于几——盯常量的话，
    以后有人把 `RUN_LIMIT` 调回 1 而 `PREVIEW_DAILY_LIMIT` 留着 10，
    测试照样绿，而实际又变回一天一条。**两个数任意一个卡住都会红。**
    """
    now = datetime(2026, 7, 19, 12, tzinfo=timezone.utc)
    previews = []
    for index in range(3):
        match = _preview(now)
        match.match_id = f"preview-{index}"
        previews.append(match)

    picks = select_content(previews, now=now, state={})

    assert len(picks) == 3, (
        f"一轮只取出了 {len(picks)} 条——PREVIEW_DAILY_LIMIT 或 RUN_LIMIT 又把它卡住了"
    )
    assert all(pick.kind == "preview" for pick in picks)


def test_即时赛果那一半没跟着一起放开():
    """「不要限制只有一条」说的是赛前焦点的日限，不是把赛果推送开回来。

    赛果那一半是 2026-07-31 另一个明确决定（「即时赛果推送也不要了」），
    两件事别混——放开日限的时候顺手把它一起开了，就是替对方改了他没说的事。
    """
    assert RESULT_DAILY_LIMIT == 0
