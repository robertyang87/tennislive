"""制胜分 / 非受迫失误这两行拿不到的时候，整行不画，其余照旧。

账号所有者 2026-08-14（斯瓦泰克-莱巴金娜那张统计图）：
「**没有的话这两条就不显示**」。

来路是数据源的硬限制：**WTA 巡回赛（1000/500/250）拿不到 Winners /
Unforced errors**——flashscore 对这三档只给 17 项，WTA 官方 `/stats` 的
32 个字段一个都不含，八条路都自证过是真空（CLAUDE.md「上面那句范围写宽了」）。
而大满贯的女子比赛和 ATP 一直有，所以这两行绝大多数时候照常出现。

⚠️ 判据不是「谁重要」，是**这个数存不存在**——所以三头都要钉：

1. 两边都没有 → 跳过那一行（这是账号所有者要的行为）；
2. **只有一边有 → 报错**。那不是「拿不到」，是数据对不齐，而对不齐的图
   会把两个人的数放在同一行里比，看起来完全正常；
3. **别的字段缺了照旧报错**，而且**画不出 MIN_ROWS 行也报错**——不设下限的话，
   一份几乎全空的 stats 也能渲出一张「看起来正常」的图。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import render_stat_card as R  # noqa: E402


def _side(**over) -> dict:
    raw = {"aces": 4, "df": 11, "winners": 20, "ue": 30,
           "first_in": 40, "first_total": 60, "first_won": 25,
           "second_won": 10, "second_total": 20,
           "bp_conv": 6, "bp_chances": 12, "pts_won": 94}
    raw.update(over)
    return raw


def test_两边都有就九行全画():
    rows = R.usable_rows(_side(), _side())
    assert len(rows) == len(R.ROW_SPECS)
    labels = [r[0] for r in rows]
    assert "制胜分" in labels and "非受迫失误" in labels


def test_两边都没有这两项就不画那两行():
    """账号所有者要的行为本身。"""
    a = _side(); b = _side()
    for d in (a, b):
        del d["winners"], d["ue"]
    rows = R.usable_rows(a, b)
    labels = [r[0] for r in rows]
    assert "制胜分" not in labels, "拿不到还画，那一行会是空的"
    assert "非受迫失误" not in labels
    # 其余七行一个都不许少——「不显示这两条」不是「少画几行」
    assert labels == ["ACE", "双误", "一发成功率", "一发得分率",
                      "二发得分率", "破发点转化", "总得分"]
    assert len(rows) == R.MIN_ROWS


def test_只有一边有要当场报错():
    """**这一头才是真会出事的那头。**

    只有一边有的时候如果照画，另一边会取到 KeyError 或者被当成 0——
    而「0 个制胜分」和「这场没统计」在图上长得一模一样。
    """
    a = _side()
    b = _side()
    del b["winners"], b["ue"]
    with pytest.raises(SystemExit, match="只有一边有数"):
        R.usable_rows(a, b)
    with pytest.raises(SystemExit, match="只有一边有数"):
        R.usable_rows(b, a)


def test_别的字段缺了照旧报错():
    """可缺清单**只有**制胜分和非受迫失误。放宽到别的字段，就等于允许任意
    一行悄悄消失，而缺一行的图和完整的图在产物上分不出来。
    """
    assert R.OPTIONAL_FIELDS == {"winners", "ue"}
    a = _side(); b = _side()
    for d in (a, b):
        del d["aces"]
    with pytest.raises(SystemExit, match="不在可缺清单里"):
        R.usable_rows(a, b)


def test_画不出下限那么多行也要报错():
    """没有这条，一份几乎全空的 stats 也能渲出一张看起来正常的图。"""
    a = _side(); b = _side()
    for d in (a, b):
        for f in ("winners", "ue"):
            del d[f]
    # 先证明现在正好卡在下限上（判据自己的判据：下限不是一个随便写的数）
    assert len(R.usable_rows(a, b)) == R.MIN_ROWS
    keep = R.MIN_ROWS
    try:
        R.MIN_ROWS = keep + 1          # 把下限抬高一格，同一份数据就该被拦下
        with pytest.raises(SystemExit, match="少于下限"):
            R.usable_rows(a, b)
    finally:
        R.MIN_ROWS = keep


def test_校验那一步不许再把可缺字段当成必填():
    """闸装在两处，两处口径要一致。

    `render()` 里那句 `missing = ...` 排在 `usable_rows` 之前——它要是还把
    `winners`/`ue` 当必填，上面那几条行为全都走不到。
    """
    body = Path(R.__file__).read_text(encoding="utf-8")
    assert "f not in raw and f not in OPTIONAL_FIELDS" in body, \
        "render() 里的必填校验没放过可缺字段，跳过那一行的逻辑根本走不到"
    assert "for spec_row in rows)" in body, \
        "画表格那一行还在遍历 ROW_SPECS，而不是筛过的 rows"
