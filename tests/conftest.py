from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from tennislive.digest import Digest
from tennislive.models import Match, MatchStatus, Player, SetScore, Tour, Tournament


@pytest.fixture(autouse=True)
def _no_ambient_github_token(monkeypatch):
    """单元测试一律看不见环境里的 `GITHUB_TOKEN` / `GH_TOKEN`。

    ⚠️ 2026-08-04 抖出来的：`_probe_page` 会先调 `trigger_pages_build()`，
    而那个函数**只在环境里有 token 的时候**才真的发请求。沙箱里两个变量都
    有、CI 里没有——于是同一条测试在两个地方跑的是**两条不同的路**，而且
    本地那条会悄悄打一次 `api.github.com`（在这个沙箱里恒 403）。

    单元测试碰外网本身就不对；更坏的是**它不吭声**：两边都绿，直到有人往
    那条路上加一行代码，才发现有一半的测试从来没被这些断言覆盖过。

    这和「本地装着不等于 CI 装着」是一家的，只是这次差的不是依赖，是**环境
    变量**。要用 token 的测试自己 `monkeypatch.setenv`——autouse 先跑、测试
    体后跑，显式给的那份必然盖过这里。
    """
    for name in (
        "GITHUB_TOKEN",
        "GH_TOKEN",
        # 简报那条线同一个形状：`Chat()` 不给 api_key 时会去读这两个，
        # 环境里恰好有一个，`ready` 就从假变真，走的是另一条分支。
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
        "TENNISLIVE_BRIEF_PROVIDER",
        "TENNISLIVE_BRIEF_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)


def make_match(
    home_name="Jannik Sinner",
    away_name="Novak Djokovic",
    home_country="ITA",
    away_country="SRB",
    status=MatchStatus.FINISHED,
    winner=0,
    sets=((6, 4), (7, 6)),
    tiebreaks=(None, (7, 3)),
    tournament="Wimbledon",
    tour=Tour.ATP,
    round_name="Semifinals",
    discipline="Men's Singles",
    start_utc=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
    match_id="m1",
) -> Match:
    set_scores = []
    for i, (h, a) in enumerate(sets):
        tb = tiebreaks[i] if i < len(tiebreaks) and tiebreaks[i] else (None, None)
        set_scores.append(
            SetScore(home=h, away=a, home_tiebreak=tb[0], away_tiebreak=tb[1])
        )
    return Match(
        match_id=match_id,
        tour=tour,
        tournament=Tournament(name=tournament, tour=tour),
        home=[Player(name=home_name, country=home_country, seed=1)],
        away=[Player(name=away_name, country=away_country, seed=5)],
        status=status,
        round_name=round_name,
        discipline=discipline,
        start_utc=start_utc,
        sets=set_scores,
        winner=winner,
    )


@pytest.fixture
def sample_digest() -> Digest:
    finished = make_match()
    finished_zheng = make_match(
        home_name="Qinwen Zheng",
        away_name="Aryna Sabalenka",
        home_country="CHN",
        away_country="BLR",  # 中立身份场景不影响测试
        tournament="Wimbledon",
        tour=Tour.WTA,
        round_name="Semifinals",
        discipline="Women's Singles",
        winner=0,
        sets=((6, 3), (6, 4)),
        tiebreaks=(None, None),
        match_id="m2",
    )
    upcoming = make_match(
        home_name="Carlos Alcaraz",
        away_name="Alexander Zverev",
        home_country="ESP",
        away_country="GER",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        round_name="Final",
        start_utc=datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc),
        match_id="m3",
    )
    return Digest(
        today=date(2026, 7, 16),
        results=[finished, finished_zheng],
        live=[],
        schedule=[upcoming],
        source="espn",
    )
