"""tools/find_turning_points.py 和 tools/match_stat_hooks.py —— 都是纯函数，
不联网。真实数据核对过一遍（QsT5YnEa，麦克纳莉 vs 伊埃拉，2026 多伦多）：
`match_stat_hooks.py` 算出的总分差「净差 4 分，伊埃拉领先」和头部账号那篇
「伊埃拉总分仅仅领先对手 4 分」的原话对得上，这份测试里的合成数据只管
覆盖分支，不重复验证过的真实场景。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _turning_points():
    sys.path.insert(0, str(Path("tools").resolve()))
    import find_turning_points  # noqa: PLC0415

    return find_turning_points


def _stat_hooks():
    sys.path.insert(0, str(Path("tools").resolve()))
    import match_stat_hooks  # noqa: PLC0415

    return match_stat_hooks


def _game(set_="Set 1", home_games="1", away_games="0", server="home", winner="home",
          broken=False, break_points=0, set_points=0, match_points=0, pts=""):
    return {
        "set": set_, "home_games": home_games, "away_games": away_games,
        "server": server, "winner": winner, "broken": broken, "points": pts,
        "break_points": break_points, "set_points": set_points, "match_points": match_points,
    }


# ---------- find_turning_points ----------

def test_密度权重是破发点1盘点2赛点3():
    tp = _turning_points()
    assert tp.density(_game(break_points=1)) == 1
    assert tp.density(_game(set_points=1)) == 2
    assert tp.density(_game(match_points=1)) == 3
    assert tp.density(_game(break_points=2, set_points=1, match_points=1)) == 2 + 2 + 3


def test_密度为0的局不进候选清单():
    tp = _turning_points()
    games = [_game(break_points=0), _game(break_points=1)]
    ranked = tp.rank_games(games)
    assert len(ranked) == 1
    assert ranked[0]["density"] == 1


def test_候选清单按密度降序():
    tp = _turning_points()
    games = [
        _game(home_games="1", break_points=1),        # 密度1
        _game(home_games="2", match_points=1),         # 密度3
        _game(home_games="3", set_points=1),            # 密度2
    ]
    ranked = tp.rank_games(games)
    assert [g["density"] for g in ranked] == [3, 2, 1]
    assert ranked[0]["home_games"] == "2"


def test_标签把破发点盘点赛点都列出来():
    tp = _turning_points()
    g = _game(break_points=2, set_points=1, match_points=1)
    ranked = tp.rank_games([g])
    tags = ranked[0]["tags"]
    assert "2个破发点" in tags
    assert "1个盘点" in tags
    assert "1个赛点" in tags


def test_保发和破发成功的标签不一样():
    tp = _turning_points()
    hold = _game(server="home", winner="home", broken=True, break_points=1)
    brk = _game(server="home", winner="away", broken=True, break_points=1)
    ranked_hold = tp.rank_games([hold])
    ranked_brk = tp.rank_games([brk])
    assert "保发" in ranked_hold[0]["tags"]
    assert "破发成功" in ranked_brk[0]["tags"]


# ---------- match_stat_hooks: parse_stat_value ----------

@pytest.mark.parametrize("raw,pct,num,den", [
    ("53% (36/68)", 53, 36, 68),
    ("6/13", None, 6, 13),
    ("74%", 74, None, None),
    ("5", None, 5, None),
])
def test_四种已知格式都能解出来(raw, pct, num, den):
    sh = _stat_hooks()
    v = sh.parse_stat_value(raw)
    assert v["pct"] == pct
    assert v["num"] == num
    assert v["den"] == den
    assert v["raw"] == raw


def test_解不出来的格式不猜只存raw():
    sh = _stat_hooks()
    v = sh.parse_stat_value("N/A")
    assert v["pct"] is None
    assert v["num"] is None
    assert v["den"] is None
    assert v["raw"] == "N/A"


# ---------- match_stat_hooks: 聚合函数 ----------

def test_总分差算出净差和领先方():
    sh = _stat_hooks()
    idx = sh.index_stats([("Match", "Points", "Total Points Won", "49% (90/184)", "51% (94/184)")])
    gap = sh.total_points_gap(idx, "麦克纳莉", "伊埃拉")
    assert gap["diff"] == 4
    assert "伊埃拉 领先" in gap["detail"]


def test_没有总分数据时返回None不是抛错():
    sh = _stat_hooks()
    gap = sh.total_points_gap({}, "A", "B")
    assert gap is None


def test_总分打平不写领先方():
    sh = _stat_hooks()
    idx = sh.index_stats([("Match", "Points", "Total Points Won", "50% (90/180)", "50% (90/180)")])
    gap = sh.total_points_gap(idx, "A", "B")
    assert gap["diff"] == 0
    assert "领先" not in gap["detail"]
    assert "打平" in gap["detail"]


def test_一发得分率摆动够大才算候选():
    sh = _stat_hooks()
    idx = sh.index_stats([
        ("Set 1", "Service", "1st serve points won", "27%", "50%"),
        ("Set 2", "Service", "1st serve points won", "55%", "48%"),
        ("Set 3", "Service", "1st serve points won", "63%", "52%"),
    ])
    out = sh.first_serve_swing(idx, "麦克纳莉", "伊埃拉")
    labels = [c["label"] for c in out]
    assert "麦克纳莉 一发得分率摆动" in labels          # 27→63，摆动36，够格
    assert "伊埃拉 一发得分率摆动" not in labels          # 48→52，摆动4，不够格
    mc = next(c for c in out if "麦克纳莉" in c["label"])
    assert mc["detail"] == "第1盘27% → 第2盘55% → 第3盘63%"


def test_只有一盘数据不算摆动():
    sh = _stat_hooks()
    idx = sh.index_stats([("Set 1", "Service", "1st serve points won", "27%", "50%")])
    assert sh.first_serve_swing(idx, "A", "B") == []


def test_破发点兑现率():
    sh = _stat_hooks()
    idx = sh.index_stats([("Match", "Return", "Break Points Converted", "6/8", "7/13")])
    out = sh.break_point_conversion(idx, "麦克纳莉", "伊埃拉")
    assert {"label": "麦克纳莉 破发点兑现", "detail": "6/8（75%）"} in out
    assert {"label": "伊埃拉 破发点兑现", "detail": "7/13（54%）"} in out


def test_保发和破发交替不会被误判成长连续段():
    sh = _stat_hooks()
    games = [
        _game(server="home", winner="home"),   # hold, home
        _game(server="away", winner="away"),   # hold, away
        _game(server="home", winner="home"),   # hold, home
        _game(server="away", winner="home"),   # break, home
        _game(server="home", winner="home"),   # hold, home
        _game(server="away", winner="home"),   # break, home
        _game(server="home", winner="home"),   # hold, home
    ]
    # 每一段（连续同一人+同一种kind）最长只有 1 局——hold/break 交替，
    # 不该因为"整体上 home 大部分时间在赢"就被数成一条长连续段
    out = sh.longest_streaks(games, "home队", "away队", threshold=3)
    assert out == []


def test_短于阈值的连续段不进候选():
    sh = _stat_hooks()
    games = [_game(server="home", winner="home"), _game(server="away", winner="away")]
    assert sh.longest_streaks(games, "A", "B", threshold=3) == []


def test_真的连续三局保发能被数出来():
    sh = _stat_hooks()
    games = [
        _game(server="home", winner="home"),
        _game(server="home", winner="home"),
        _game(server="home", winner="home"),
    ]
    out = sh.longest_streaks(games, "甲", "乙", threshold=3)
    assert out == [{"label": "甲 连续保发", "detail": "3 局"}]
