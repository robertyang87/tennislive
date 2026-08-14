"""`tools/mcp_stats.py`：从 Match Charting Project 取制胜分和非受迫失误。

**它补的是 WTA 巡回赛那一段**——大满贯和 ATP 巡回赛 flashscore 直接就有
（CLAUDE.md「上面那句范围写宽了」那节列着八条路各自怎么自证的）。

⚠️ **fixture 是真页面的节选，不是手搓的。** 本仓库栽过一次：
`copy_page_fingerprint` 那道闸恒真了一个月，根因就是测试喂的是自己拼的假页面
——它证明的是「函数能从 h1 里抠字」，而不是「真页面的 h1 是当期标题」。
所以这里两个 fixture 都是从 tennisabstract 真产物上剪下来的。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import mcp_stats as M  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
OVERVIEW = (FIX / "mcp_overview_sample.html").read_text(encoding="utf-8")
INDEX = (FIX / "mcp_index_sample.html").read_text(encoding="utf-8")


def test_同一站两条巡回赛的赛事名对不上():
    """**这条才是「别按赛事名过滤，按球员姓找」的真来路。**

    同一站男子叫 `Canada_Masters`、女子叫 `Toronto`。我第一次按 `-Toronto-`
    扫，男子那 14 场一场都没进来——**而漏掉的样子和「这一站没人标」一模一样**。

    ⚠️ 这条测试的第一版写的是「赛事名带下划线所以不能按 `-` 无脑切」，
    **那句话是编的**：全部 18099 条量过，赛事名 762 种一个连字符都没有，
    轮次永远是 14 个大写标记之一，无脑切也切得对。反向验证时把正则退回
    `[^-]+`，那一版**照样绿**——它拦的是一个不存在的坑。留着解析字段的断言，
    把假理由删掉。
    """
    got = {e["slug"]: e for e in M.entries(INDEX)}
    assert got, "一条都没解析出来，判据的主语像是没了"

    men = got["20260811-M-Canada_Masters-QF-Learner_Tien-Daniel_Merida_Aguilar"]
    assert men["event"] == "Canada_Masters", "带下划线的赛事名被切断了"
    assert men["round"] == "QF"
    assert men["sex"] == "M"
    assert men["players"] == "Learner_Tien-Daniel_Merida_Aguilar"

    women = got["20260809-W-Toronto-R16-Coco_Gauff-Alina_Korneeva"]
    assert women["event"] == "Toronto" and women["sex"] == "W"

    # 同一站两条巡回赛登记成两个赛事名——这就是不许按赛事名过滤的理由
    assert men["event"] != women["event"]


def test_这份索引fixture是真产物不是手搓的():
    """**判据自己也要有判据。**

    第一版 fixture 我拼成 `<a href="X">X</a>`，于是同一个 slug 出现两次、
    条数翻倍，测试红了——而**红的是测试，不是代码**。真索引长这样：

        <a href="20260802-W-…-Jessica_Pegula.html">2026-08-02 Washington F: …(WTA)</a>

    链接文字是人读的那一串，和 href 里的 slug 完全不同。所以这里钉死这一点：
    fixture 里每条的**链接文字不许等于 slug**，谁再手搓一份就当场红。
    """
    import re
    pairs = re.findall(r'<a href="([^"]+)\.html">([^<]+)</a>', INDEX)
    assert len(pairs) >= 4, "fixture 空了，判据的主语没了"
    for slug, text in pairs:
        assert text != slug, "链接文字等于 slug——这份 fixture 是手搓的，不是真产物"
        assert "vs" in text, f"真索引的链接文字长这样「2026-08-02 … A vs B (WTA)」，而这条是 {text!r}"
    assert len({s for s, _ in pairs}) == len(pairs), "同一条出现了两次"


def test_按球员姓找而不是按flashscore那种写法():
    """MCP 用的是**全名带下划线**（`Alexandra_Eala`），不是 flashscore 的
    `Eala A.`——拿后者去搜必然零命中，而零命中和「没人标过」长得一模一样。
    """
    assert M.find(INDEX, who="Eala"), "按姓找不到，那这个工具就没法用了"
    assert not M.find(INDEX, who="Eala A."), \
        "flashscore 的写法居然搜得到？那说明匹配太松，会撞上别人"
    assert len(M.find(INDEX, who="Gauff")) == 1
    assert M.find(INDEX, who="Eala", year="2026")
    assert not M.find(INDEX, who="Eala", year="2025")
    assert all(e["sex"] == "W" for e in M.find(INDEX, sex="W"))


def test_从真页面里读出制胜分和非受迫失误():
    """列名对不对得上，只能拿真页面验。"""
    ov = M.parse_overview(OVERVIEW)
    assert ov["columns"][0] == "STATS OVERVIEW"
    assert "Winners (FH/BH)" in ov["columns"]
    assert "UFE (FH/BH)" in ov["columns"]

    full = {r["player"]: r for r in ov["rows"] if r["scope"] == "全场"}
    assert set(full) == {"Alexandra Eala", "Jessica Pegula"}
    assert full["Alexandra Eala"]["Winners (FH/BH)"] == "11 (8/3)"
    assert full["Alexandra Eala"]["UFE (FH/BH)"] == "21 (13/5)"
    assert full["Jessica Pegula"]["Winners (FH/BH)"] == "23 (13/5)"
    assert full["Jessica Pegula"]["UFE (FH/BH)"] == "35 (19/15)"

    # 分盘也要读出来，而且「SET 1」那种小标题行不许被当成一个球员
    scopes = {r["scope"] for r in ov["rows"]}
    assert scopes == {"全场", "SET 1", "SET 2", "SET 3"}
    assert not any(r["player"].upper().startswith("SET") for r in ov["rows"])

    assert ov["charter"], "谁标的要读出来——志愿者标注必须能追溯到人"


def test_正手加反手不等于总数():
    """⚠️ Gauff 那场 `16 (6/7)`——6+7=13，还差 3 个（截击、高压这些不在这两栏）。

    **别把「6/7」当成完整拆分印出去。** `split_count` 把差额算成 `other`
    就是为了让下一个人一眼看见它不是零。
    """
    assert M.split_count("16 (6/7)") == {"total": 16, "fh": 6, "bh": 7, "other": 3}
    # 真数据里就有 other=0 和 other=5 两种，两头都要认得
    assert M.split_count("11 (8/3)")["other"] == 0
    assert M.split_count("23 (13/5)")["other"] == 5
    assert M.split_count("") == {}
    assert M.split_count("n/a") == {}


def test_交叉核对过的那七项要留在文档里():
    """**这个工具的可信度是拿两个源对出来的，不是声明出来的。**

    伊埃拉-佩古拉华盛顿决赛，MCP 和 flashscore 官方对得上七项，其中三项精确到
    小数（佩古拉 Ace 4/71=5.6%、伊埃拉双误 3/70=4.3%、佩古拉双误 1/71=1.4%）。
    列映射读错的话这七项不可能同时对上——所以 Winners/UFE 那两栏可以信。

    判据钉在文档里：把这段来路删掉，下一个人就没法知道这个工具验过没有。
    """
    doc = M.__doc__ or ""
    assert "志愿者" in doc, "必须写明是志愿者标注，不是官方统计"
    assert "flashscore" in doc, "必须写明大满贯和 ATP 不走这条路"
    for gotcha in ("Canada_Masters", "Gauff C.", "FH/BH", "早轮"):
        assert gotcha in doc, f"模块文档里少了「{gotcha}」这个坑"


def test_索引缓存要展开波浪号():
    """⚠️ 本仓库栽过：`TENNISLIVE_SOURCE_CACHE: ~/.cache/…` 写进 YAML 之后
    **Python 不展开波浪号**，落成一个名叫 `~` 的相对目录，两趟绿的 run 一个
    字节都没缓存。凡是「路径从配置来」的判据，必须喂一次 `~/…`。
    """
    assert "expanduser" in Path(M.__file__).read_text(encoding="utf-8"), \
        "缓存路径没展开波浪号，会在工作区里落一个名叫 ~ 的目录"


@pytest.mark.parametrize("bad", ["", "<html>没有 overview 这个变量</html>"])
def test_页面不对要报错不许返回空表(bad):
    """**空表和「这场没有统计」长得一模一样。** 解析不出来要出声。"""
    with pytest.raises(ValueError, match="overview"):
        M.parse_overview(bad)
