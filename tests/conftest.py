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
def _no_slam_feed_network(monkeypatch):
    """`orchestrate.enrich_slam_fields` 会去 usopen.org 补 round/court——沙箱里恒
    403、CI 上会真联网。单元测试一律关掉；要测它的测试自己 `setenv("TENNISLIVE_SLAM_FEED", "1")`
    并把 `lookup` 打桩（和上面两条 autouse 同一个形状）。"""
    monkeypatch.setenv("TENNISLIVE_SLAM_FEED", "0")


@pytest.fixture(autouse=True)
def _no_face_model_network(monkeypatch):
    """`face_checks.fetch_models` 缺权重会去 GitHub Release 现下 127 MB 的包。
    单元测试一律不许摸网——CI 在「备好人脸模型」那一步先下好、缓存住；本地
    自己跑一次 `python tools/face_checks.py fetch`（和上下两条同一个形状）。"""
    monkeypatch.setenv("TENNISLIVE_FACE_MODEL_FETCH", "0")


@pytest.fixture(autouse=True)
def _no_headshot_fetch_network(monkeypatch):
    """`headshot_index.resolve_headshots` 索引没命中会去 WTA 官方现抓头像（并把
    文件写进 assets/players/headshots/）。单元测试一律关掉——要测那条路的测试
    自己传 `fetch_wta=` 打桩。"""
    monkeypatch.setenv("TENNISLIVE_HEADSHOT_FETCH", "0")


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


@pytest.fixture(autouse=True)
def _isolate_production_research(monkeypatch, tmp_path):
    monkeypatch.setenv("TENNISLIVE_TACTICAL_RESEARCH", "0")
    monkeypatch.setenv("TENNISLIVE_PRODUCTION_CACHE", str(tmp_path / "production-cache"))


@pytest.fixture()
def _empty_reel_ledger(monkeypatch, tmp_path):
    """竖版短片的发布账本钉成空目录——给「拿真的已发 spec 测别的闸」的测试用
    （`@pytest.mark.usefixtures("_empty_reel_ledger")`）。

    `validate_spec(spec)` 的默认口径是渲染入口，有**两处**读发布记录：

    - `reel_facts.waiting_fact_stale_problem`：`_facts` 里写着「抽签后／正式名单」
      这类要等的事、`_rechecked_at` 又早于最近一次推送，就红；
    - `reel_asset_gates.cover_reuse_finding`（④ 封面复用）：封面照片和一条**比它先
      发出去**的片子是同一张，就红——读账本，也读 `output/*/reel/*/pushed.json`。

    哪天账本多一笔（推送落账）、或者有人给那几条已发 spec 补上时效那两个字段，它们会先
    红在这两道闸上：写了 `match=` 的对不上，没写的（`pytest.raises(ReelError)`）是
    假绿。测的不是账本，就别读账本（`reel_facts.REEL_LEDGER_DIR` 那行注释：判据测试
    一律不许读真账本）。

    进程内改 `reel_facts.REEL_LEDGER_DIR`；`TENNISLIVE_REEL_LEDGER_DIR` 管子进程，
    也管 `reel_asset_gates`——它在**调用那一刻**读这个变量（`publication_record`），
    设了就把整份发布记录（账本＋`pushed.json`）钉成这个空目录。判据
    `tests/test_reel_asset_gates.py::test_真账本多一笔_全库扫描和钉空账本的渲染入口都不许跟着红`。
    ⚠️ 不做成 autouse：`tests/test_time_sensitive_facts.py` 那几条测的就是账本，
    它们自己把账本建在 tmp_path 上。原来这个 fixture 在 `test_match_reel.py` 和
    `test_unvoiced_quote.py` 各抄了一份，挪到这儿只留一份。
    """
    import sys  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    tools = str(Path(__file__).resolve().parents[1] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import reel_facts  # noqa: PLC0415

    empty = tmp_path / "empty-reel-ledger"
    empty.mkdir()
    monkeypatch.setattr(reel_facts, "REEL_LEDGER_DIR", empty)
    # 子进程（`build_match_reel.py render --dry-run`）重新 import，monkeypatch 够不着——
    # `test_冷开场里的结局必须在正文重新兑现` 后半段就是这么走的，靠环境变量带过去。
    monkeypatch.setenv("TENNISLIVE_REEL_LEDGER_DIR", str(empty))
    return empty
