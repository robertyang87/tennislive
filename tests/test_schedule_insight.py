"""`render/story.py::schedule_insight` 的守卫——**这个文件是从 `test_authority.py` 剩下来的**。

2026-09-15 清掉日报（`daily.yml`，2026-07-31 停产）时代的无调用方模块，
`render/authority.py`（`apply_curated_editorial` / `enrich_schedule_editorial`）
跟着删了：AST 扫过 `src/` `tools/` `tests/`，生产代码里零 import，喂它的只有
这个文件自己。

**但它不是主语型的文件，是名单型的**：下面两条测的是 `schedule_insight`，
而那个函数今天还活着——`wechat.py` / `xiaohongshu.py` / `hotspot.py` /
`narrative.py` / `content_package.py` 五处在用。原来它们借
`enrich_schedule_editorial` 当驱动，所以看起来像 authority 的测试；主语没了
就直接调 `schedule_insight`。**删主语的时候不许把搭车的判据一起带走。**
"""

from datetime import date

from tennislive.models import MatchStatus
from tennislive.render.story import schedule_insight

from conftest import make_match


def test_schedule_insight_rotates_when_unplayed_fixture_persists_across_days():
    """生产事故复现（2026-07-24 日报未推送）：布拉格站女单八强布兹科娃 vs
    瓦伦托娃因官方赛程一直未定，连续两天都被选进"今晚焦点"，排名差（42）
    和轮次（四强席位）完全没变。`schedule_insight` 之前不区分日期，
    两天生成的文案逐字相同，撞上小红书近7期查重 FATAL 闸门，
    导致当天日报整包生成失败、没有推送到微信。

    ⚠️ 日报和那道查重闸（`render/history_dedupe.py`）都已经停产删掉了，
    **但这条判据管的是 `schedule_insight` 自己按日期轮换这件事**，
    而它还在给「今晚焦点」「赛前提醒」供文案——所以留着。
    """
    scheduled = make_match(
        home_name="Marie Bouzkova",
        away_name="Nikola Bartunkova",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        round_name="Quarterfinals",
    )
    scheduled.home[0].seed = scheduled.away[0].seed = None
    scheduled.home[0].rank, scheduled.away[0].rank = 41, 83  # 差 42 位，命中 gap>=35 分支

    note_23 = schedule_insight(scheduled, date(2026, 7, 23))
    note_24 = schedule_insight(scheduled, date(2026, 7, 24))

    assert note_23 != note_24
    assert "四强席位" in note_23 and "四强席位" in note_24


def test_schedule_fallback_explains_current_stakes_without_technique_cliches():
    scheduled = make_match(
        home_name="Qinwen Zheng",
        away_name="Barbora Krejcikova",
        home_country="CHN",
        away_country="CZE",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        round_name="Quarterfinals",
    )

    insight = schedule_insight(scheduled)
    assert "四强席位" in insight
    assert "接发" not in insight and "关键分" not in insight
