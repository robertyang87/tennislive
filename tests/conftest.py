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


@pytest.fixture(autouse=True)
def _isolate_tts_cache(monkeypatch, tmp_path):
    """TTS 内容缓存默认落在 `~/.cache/tennislive-tts`，测试里会**跨测试污染**：
    上一个测试合成的「同一句」会命中缓存，让下一个测 edge-tts 重试逻辑的测试
    一步都不走——`test_reel_narration.py` 三条就是这么红在 CI 上的（缓存命中后
    `built` 记 0 次、`ReelError` 也不抛了）。

    每个测试都指到一个干净的临时目录；要测缓存本身的测试自己
    `monkeypatch.setenv("TENNISLIVE_TTS_CACHE", ...)` 覆盖——autouse 先跑、
    测试体后跑，显式给的那份必然盖过这里（和上面 `_no_ambient_github_token`
    同一个形状）。
    """
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path / "tts-cache"))


@pytest.fixture(autouse=True)
def _isolate_story_state(monkeypatch, tmp_path):
    """选题账本 `data/story_state.json` 是**跟踪进仓库的数据**，测试不许写它。

    ⚠️ 2026-08-29 量出来的：`pytest tests/test_cli.py -k knowledge` 跑完
    （**5 passed**），`git status` 里那个文件就脏了——少掉一条
    `__visual_backoff__` 的记录。走的是 `cmd_knowledge` → `mark_story_used()`
    这条真路，而 `test_cli.py` 一处都没有把 `STATE_PATH` 打桩
    （`test_render.py` 每条都打了，所以它一直没事）。

    **它不吭声**：测试全绿，只有 `git status` 才看得见。而这个仓库的提交习惯
    是 `git add -A`，stop hook 还会主动催「有未提交的改动，请提交并推送」——
    于是一次全量跑下来的副作用会被当成一次改动推上去，把另一条线的账本
    悄悄改掉。`__visual_backoff__` 那几条正是「这个选题的素材预检刚失败过，
    三天内别再排它」（见 CLAUDE.md 无人值守那节的第 ④ 条），抹掉它就等于
    让那条线明天再去撞同一堵墙。

    ⚠️ **要拷一份真的过去，不能指到一个空文件**：`published_topics()` 读的
    就是它，指空了「这个选题发过没有」会全部答成「没发过」——那比脏一个
    文件糟得多。每个测试各拿一份 `tmp_path` 里的副本，写坏了也只坏自己那份。

    要测账本本身的测试自己 `monkeypatch.setattr(..., STATE_PATH, ...)` 覆盖
    ——autouse 先跑、测试体后跑，显式给的那份必然盖过这里（和上面两条同一个
    形状）。
    """
    from tennislive.render import tournament_story
    from tennislive.research import topic_radar

    real = tournament_story.STATE_PATH
    # ⚠️ **放进单独一层目录，别放在 `tmp_path` 根上。** `test_visual_backoff.py`
    # 的 `_state()` 和 `test_render.py` 里好几条自己也往 `tmp_path/story_state.json`
    # 打桩，而它们**指望那份是空的**——第一版就放在根上，同名撞车，八条当场红
    # （「左边多出 7 项」正是这里拷过去的真账本）。
    fake = tmp_path / "_ledger_isolation" / "story_state.json"
    fake.parent.mkdir(parents=True, exist_ok=True)
    try:
        fake.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        fake.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(tournament_story, "STATE_PATH", fake)
    monkeypatch.setattr(topic_radar, "_STORY_STATE", fake)


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
