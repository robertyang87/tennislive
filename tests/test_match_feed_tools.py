"""tools/find_turning_points.py 和 tools/match_stat_hooks.py —— 都是纯函数，
不联网。真实数据核对过一遍（QsT5YnEa，麦克纳莉 vs 伊埃拉，2026 多伦多）：
`match_stat_hooks.py` 算出的总分差「净差 4 分，伊埃拉领先」和头部账号那篇
「伊埃拉总分仅仅领先对手 4 分」的原话对得上，这份测试里的合成数据只管
覆盖分支，不重复验证过的真实场景。
"""

from __future__ import annotations

import json
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
    assert {"label": "麦克纳莉 破发点兑现", "detail": "6/8（75%）",
            "source": "flashscore df_st_1（破发点）"} in out
    assert {"label": "伊埃拉 破发点兑现", "detail": "7/13（54%）",
            "source": "flashscore df_st_1（破发点）"} in out


def _alternating(pattern_home: str, pattern_away: str) -> list[dict]:
    """按真实网球的**轮流发球**造逐局数据。

    ⚠️ 这个 helper 存在的理由本身就是一条判据：第一版测试手搓了「同一个人
    连发三局」，那在网球里不可能发生——于是它绿着证明了一个不可能的世界，
    而真实数据（31 局）上函数返回 0 条候选。**手搓 fixture 要先问一句：
    真实数据长这样吗。**

    `pattern_*` 用 H（保发）/ X（被破）描述各自发球局的结果，交替编织。
    """
    games = []
    for i in range(max(len(pattern_home), len(pattern_away))):
        if i < len(pattern_home):
            games.append(_game(server="home",
                               winner="home" if pattern_home[i] == "H" else "away"))
        if i < len(pattern_away):
            games.append(_game(server="away",
                               winner="away" if pattern_away[i] == "H" else "home"))
    return games


def test_保发和破发交替不会被误判成长连续段():
    sh = _stat_hooks()
    # 两边发球局都在 H/X 交替，谁都没有 3 连
    games = _alternating("HXHXHX", "XHXHXH")
    assert sh.longest_streaks(games, "home队", "away队", threshold=3) == []


def test_短于阈值的连续段不进候选():
    sh = _stat_hooks()
    games = _alternating("HH", "HH")
    assert sh.longest_streaks(games, "A", "B", threshold=3) == []


def test_连续保发按这个人自己的发球局数不按逐局列表相邻项():
    """网球轮流发球，同一个人的发球局在列表里隔一局出现一次——按相邻项数
    永远数不出连续保发。这条锁死"先筛发球方再数连续"这个口径。"""
    sh = _stat_hooks()
    games = _alternating("HHH", "XXX")     # 甲连保三个发球局，乙连丢三个
    out = sh.longest_streaks(games, "甲", "乙", threshold=3)
    labels = {c["label"]: c["detail"] for c in out}
    assert labels.get("甲 连续保发") == "3 个发球局"
    assert labels.get("乙 连续被破") == "3 个发球局"


def test_和真实比赛手工核对过的那两个数对得上():
    """QsT5YnEa（麦克纳莉 vs 伊埃拉，2026 多伦多）真实逐局，人工数过：

        伊埃拉的发球局    XXHHHHXXHXXHHHHH   最长连保 5
        麦克纳莉的发球局  XHXXHXXHXHXHHHH    最长连保 4

    冻结这两个数，免得口径又漂回"数逐局列表相邻项"那一版（那一版在这份
    真实数据上返回 0 条）。
    """
    sh = _stat_hooks()
    games = _alternating("XHXXHXXHXHXHHHH", "XXHHHHXXHXXHHHHH")
    labels = {c["label"]: c["detail"] for c in sh.longest_streaks(games, "麦克纳莉", "伊埃拉")}
    assert labels.get("伊埃拉 连续保发") == "5 个发球局"
    assert labels.get("麦克纳莉 连续保发") == "4 个发球局"


# ─── H2H 交手记录（df_hh_1）───
# 罐头数据按真实 feed 的格式造（AFGhOCE8，萨巴伦卡 vs 亚历山德罗娃）：
# `*` 标在赢家名下、KA 是场地分区、每个分区各有一节 Head-to-head。
# 字段含义的交叉验证记录在 parse_h2h 的 docstring 里。

def _h2h_feed() -> str:
    row = ("~KC÷{ts}¬KP÷{mid}¬KD÷hard¬KF÷{city}¬AC÷3¬"
           "KJ÷{p1}¬UE÷x¬KK÷{p2}¬UG÷y¬KL÷{sets}¬")
    all_rows = (row.format(ts=3, mid="CUR00001", city="Toronto",
                           p1="Saba A.", p2="*Alex E.", sets="1:2")
                + row.format(ts=2, mid="OLD00001", city="Berlin",
                             p1="*Saba A.", p2="Alex E.", sets="2:0")
                + row.format(ts=1, mid="OLD00002", city="Doha",
                             p1="Alex E.", p2="*Saba A.", sets="0:2"))
    hard_rows = (row.format(ts=3, mid="CUR00001", city="Toronto",
                            p1="Saba A.", p2="*Alex E.", sets="1:2")
                 + row.format(ts=1, mid="OLD00002", city="Doha",
                              p1="Alex E.", p2="*Saba A.", sets="0:2"))
    return ("SA÷2¬~KA÷All surfaces¬IS÷¬"
            "~KB÷Last matches: Saba A.¬" + row.format(
                ts=9, mid="ZZZ00001", city="Rome", p1="*Saba A.",
                p2="Other P.", sets="2:0")
            + "~KB÷Head-to-head matches¬" + all_rows
            + "~KA÷Clay¬~KB÷Head-to-head matches¬"
            + "~KA÷Hard¬~KB÷Head-to-head matches¬" + hard_rows)


def test_h2h星号在谁名下谁就是赢家():
    sh = _stat_hooks()
    sections = sh.parse_h2h(_h2h_feed())
    total = sections[0]
    assert total["surface"] == "All surfaces"
    winners = [r["winner"] for r in total["rows"]]
    assert winners == ["Alex E.", "Saba A.", "Saba A."]
    # `*` 只是标记，名字本身要剥干净
    assert all("*" not in r["p1"] + r["p2"] + r["winner"]
               for r in total["rows"])
    # 「Last matches」分区不是交手记录，不许混进来（Rome 那行）
    assert all(r["city"] != "Rome" for r in total["rows"])


def test_h2h总战绩只认AllSurfaces分场地只作拆分(monkeypatch):
    """四个场地分区各有一节 H2H，同一场会在总表和分场地表各出现一次——
    加在一起就是把每场数两遍。总战绩只认 All surfaces，分场地只进拆分。"""
    sh = _stat_hooks()
    monkeypatch.setattr(sh, "fs_feed", lambda name, mid: _h2h_feed())
    got = sh.h2h_candidate("CUR00001")
    assert got["label"] == "交手记录"
    assert "Saba A. 2 : 1 Alex E." in got["detail"]
    assert "（含本场）" in got["detail"]
    assert "硬地 1:1" in got["detail"]
    assert "红土" not in got["detail"], "空场地不该出现在拆分里"


def test_h2h没有星号的行不猜赢家而且要出声(monkeypatch):
    """没有文档的标记缺失时宁可少算，但少算了要说——「没算进去」和
    「本来就没有」长得一样。"""
    sh = _stat_hooks()
    broken = _h2h_feed().replace("KJ÷*Saba A.", "KJ÷Saba A.")
    monkeypatch.setattr(sh, "fs_feed", lambda name, mid: broken)
    got = sh.h2h_candidate("CUR00001")
    assert "Saba A. 1 : 1 Alex E." in got["detail"]
    assert "1 场赢家标记缺失" in got["detail"]


def test_h2h一场都没有返回None不是抛错(monkeypatch):
    """新秀首次交手是常态。查空 ≠ 报错。"""
    sh = _stat_hooks()
    monkeypatch.setattr(sh, "fs_feed",
                        lambda name, mid: "SA÷2¬~KA÷All surfaces¬"
                        "~KB÷Head-to-head matches¬")
    assert sh.h2h_candidate("CUR00001") is None


# ---------- match_stat_hooks --from-spec ----------


def test_from_spec读spec取id和中文名(tmp_path):
    """`--from-spec` 的机械半截：从 spec 里抽出 flashscore_id 和两个中文名。"""
    sh = _stat_hooks()
    spec = {"_match": {"flashscore_id": "ABC123"},
            "cover": {"matchup": [{"name": "商竣程"}, {"name": "卢布列夫"}]}}
    (tmp_path / "demo.json").write_text(json.dumps(spec, ensure_ascii=False),
                                        encoding="utf-8")
    got = sh.load_spec_slug("demo", tmp_path)
    assert got == {"slug": "demo", "flashscore_id": "ABC123",
                   "home": "商竣程", "away": "卢布列夫"}


def test_from_spec缺flashscore_id报错并指路(tmp_path):
    """缺 id 要报错指路，不静默空跑——「找不到 id」和「这场没数据」不一样。"""
    sh = _stat_hooks()
    (tmp_path / "demo.json").write_text(
        json.dumps({"cover": {"matchup": [{"name": "甲"}, {"name": "乙"}]}},
                   ensure_ascii=False), encoding="utf-8")
    with pytest.raises(KeyError, match="flashscore_id"):
        sh.load_spec_slug("demo", tmp_path)


def test_from_spec找不到spec报错(tmp_path):
    """slug 拼错要出声，别让调用方以为「这场没有狠数据」。"""
    sh = _stat_hooks()
    with pytest.raises(FileNotFoundError):
        sh.load_spec_slug("no-such-slug", tmp_path)


def test_狠数据候选都带来源标注():
    """每条候选必须带 source——「写进 _facts 可机械回查」的前提是来源在场。
    判据是字段在场，不是具体文案。"""
    sh = _stat_hooks()
    e = lambda num=None, den=None, pct=None, raw="": {  # noqa: E731
        "raw": raw, "pct": pct, "num": num, "den": den}
    idx = {
        ("Match", "Total Points Won"): (e(60), e(56)),
        ("Set 1", "1st serve points won"): (e(32, 40, 80, "80% (32/40)"),
                                            e(28, 40, 70, "70% (28/40)")),
        ("Set 2", "1st serve points won"): (e(16, 40, 40, "40% (16/40)"),
                                            e(28, 40, 70, "70% (28/40)")),
        ("Match", "Break Points Converted"): (e(4, 10), e(2, 8)),
    }
    games = [{"server": "home", "winner": "home"},
             {"server": "away", "winner": "away"},
             {"server": "home", "winner": "home"},
             {"server": "away", "winner": "away"},
             {"server": "home", "winner": "home"},
             {"server": "away", "winner": "away"},
             {"server": "home", "winner": "home"}]
    got = []
    tp = sh.total_points_gap(idx, "甲", "乙")
    assert tp is not None
    got.append(tp)
    got += sh.first_serve_swing(idx, "甲", "乙")
    got += sh.break_point_conversion(idx, "甲", "乙")
    got += sh.longest_streaks(games, "甲", "乙")
    assert got, "这套合成数据至少该出几条候选，先修数据别改判据"
    for c in got:
        assert c.get("source"), f"{c['label']} 缺来源标注"


def test_from_spec主入口把id和名字喂给collect(monkeypatch, capsys):
    """主入口的接缝：--from-spec 解出的三个值必须原样进 collect。"""
    import sys as _sys
    sh = _stat_hooks()
    called = {}
    monkeypatch.setattr(sh, "load_spec_slug",
                        lambda slug, specs_dir=None: {
                            "slug": slug, "flashscore_id": "FS01",
                            "home": "甲", "away": "乙"})
    monkeypatch.setattr(sh, "collect",
                        lambda mid, home, away: called.update(
                            mid=mid, home=home, away=away) or
                        {"candidates": [], "durations": []})
    old_argv = _sys.argv
    _sys.argv = ["match_stat_hooks.py", "--from-spec", "some-slug"]
    try:
        rc = sh.main()
    finally:
        _sys.argv = old_argv
    assert rc == 0
    assert called == {"mid": "FS01", "home": "甲", "away": "乙"}
    out = capsys.readouterr().out
    assert "FS01" in out and "some-slug" in out


# ---------- match_feed._get 重试（只重试"没送到"） ----------


def _match_feed():
    sys.path.insert(0, str(Path("tools").resolve()))
    import match_feed  # noqa: PLC0415

    return match_feed


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self) -> bytes:
        return self._body


def test_match_feed网络抖动会重试而不是裸崩(monkeypatch):
    """`_get` 只重试「没送到」：前两次 IncompleteRead（网络截断）、第三次
    成功，要返回数据。一次抖动就裸崩会把 `--from-spec` 整条带倒——
    2026-08-14 真实踩过，这不是纸面规矩。"""
    import http.client
    mf = _match_feed()
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise http.client.IncompleteRead(b"", 10)
        return _FakeResp(b"ok")

    monkeypatch.setattr(mf.urllib.request, "urlopen", flaky)
    assert mf._get("http://example.test/feed") == b"ok"
    assert calls["n"] == 3


def test_match_feed的4xx是明确拒绝不重试(monkeypatch):
    """HTTP 4xx 是「没有这场/被挡」，重试只会把同一个 404 再问三遍——
    当场 SystemExit，一次都不多试。"""
    mf = _match_feed()
    calls = {"n": 0}

    def denied(*_a, **_k):
        calls["n"] += 1
        raise mf.urllib.error.HTTPError("http://x", 404, "Not Found", {}, None)

    monkeypatch.setattr(mf.urllib.request, "urlopen", denied)
    with pytest.raises(SystemExit):
        mf._get("http://example.test/feed")
    assert calls["n"] == 1


# ---------- match_stat_hooks --stats-block ----------
#
# **来路是一次真实的漏填**（2026-08-15，`hijikata-monfils`）：那场 flashscore
# 有 `Winners 30/35`、`Unforced errors 39/55`，写 spec 的人（我）在旁白里用了
# UE，却没把这两个字段抄进 `stats` 块——成片里那张数据图因此少了两行。
# ⚠️ **而它一个字都不报**：`render_stat_card.OPTIONAL_FIELDS` 允许这两项缺席
# （多数场次接口里真的没有），所以「漏抄」和「本来就没有」在产物上长得一模一样。
#
# 手抄十二个数字这件事本身就是那个坑，所以现在从接口直接摊出来。

def _st_row(item, home, away, scope="Match"):
    return (scope, "grp", item, home, away)


def _feed_rows(*, with_quality=True):
    """一份 `Match` 那一栏的最小样本，字段名和格式都照真实 feed 写。"""
    rows = [
        _st_row("Aces", "3", "16"),
        _st_row("Double Faults", "4", "7"),
        _st_row("1st serve points won", "67% (37/55)", "81% (46/57)"),
        _st_row("2nd serve points won", "62% (28/45)", "41% (27/66)"),
        _st_row("Break Points Converted", "3/5", "4/6"),
        _st_row("Total Points Won", "51% (115/224)", "49% (109/224)"),
    ]
    if with_quality:
        rows += [_st_row("Winners", "30", "35"),
                 _st_row("Unforced errors", "39", "55")]
    return rows


def test_接口给了制胜分和非受迫失误就必须摊进stats块(monkeypatch):
    """有这两项时不许丢——丢了那张数据图会少两行，而且不出声。"""
    mod = _stat_hooks()
    monkeypatch.setattr(mod, "stats", lambda _mid: _feed_rows(with_quality=True))
    blk = mod.stats_block("X")

    assert blk["_has_winners_ue"] is True
    assert (blk["a"]["winners"], blk["b"]["winners"]) == (30, 35)
    assert (blk["a"]["ue"], blk["b"]["ue"]) == (39, 55)
    assert blk["_missing_required"] == []

    # 其余字段照 `render_stat_card` 要的名字和口径摊开
    assert blk["a"]["aces"] == 3 and blk["b"]["aces"] == 16
    assert (blk["a"]["first_in"], blk["a"]["first_won"]) == (55, 37)
    assert (blk["a"]["second_total"], blk["a"]["second_won"]) == (45, 28)
    assert (blk["a"]["bp_conv"], blk["a"]["bp_chances"]) == (3, 5)
    assert (blk["a"]["pts_won"], blk["a"]["pts_total"]) == (115, 224)
    # ⚠️ `first_total` 按 `first_in + second_total` 算，不取接口的 Service Points
    # Won 分母——那个数偶尔差 1（let 的记法差异），而一发成功率是 first_in/first_total
    assert blk["a"]["first_total"] == 55 + 45
    assert blk["b"]["first_total"] == 57 + 66


def test_接口没有这两项时不许硬凑(monkeypatch):
    """反过来那一头：多数场次真的没有，这时留空是对的，不许编。"""
    mod = _stat_hooks()
    monkeypatch.setattr(mod, "stats", lambda _mid: _feed_rows(with_quality=False))
    blk = mod.stats_block("X")

    assert blk["_has_winners_ue"] is False
    for side in ("a", "b"):
        assert "winners" not in blk[side]
        assert "ue" not in blk[side]
    # 少了这两项**不算缺必填**——`render_stat_card` 把它们列进了 OPTIONAL_FIELDS
    assert blk["_missing_required"] == []
    # 而真正的必填项一个都不能少，否则那张图会用一份半空的数渲出来
    assert blk["a"]["aces"] == 3 and blk["a"]["pts_won"] == 115


def test_必填项解不出来要报出来不能静默跳过(monkeypatch):
    mod = _stat_hooks()
    rows = [r for r in _feed_rows() if r[2] != "Total Points Won"]
    monkeypatch.setattr(mod, "stats", lambda _mid: rows)
    blk = mod.stats_block("X")
    assert any("pts_won" in m for m in blk["_missing_required"])


def test_可缺的字段两处必须是同一份(monkeypatch):
    """`match_stat_hooks` 里哪些能缺，和 `render_stat_card` 允许缺的那份，
    **必须自己推导出来对得上**——两处各写一份名单，早晚会分叉，而分叉的样子是
    「这一行悄悄消失」。"""
    sys.path.insert(0, str(Path("tools").resolve()))
    import render_stat_card  # noqa: PLC0415

    mod = _stat_hooks()
    optional_here = {field for field, _item, _which, required in mod._STATS_FIELDS
                     if not required}
    assert optional_here == set(render_stat_card.OPTIONAL_FIELDS), (
        "两处的「可缺字段」对不上：match_stat_hooks 认为可缺的是 "
        f"{sorted(optional_here)}，render_stat_card 认的是 "
        f"{sorted(render_stat_card.OPTIONAL_FIELDS)}")

    # 反过来也钉住：这个表必须盖住那张图要画的每一个字段，
    # 少一个就等于「摊出来的 stats 块渲不出完整的图」
    needed = {f for spec_row in render_stat_card.ROW_SPECS for f in spec_row[3:]}
    covered = {field for field, *_ in mod._STATS_FIELDS} | {"first_total"}
    assert needed <= covered, f"这张图要的字段没盖全：{sorted(needed - covered)}"
