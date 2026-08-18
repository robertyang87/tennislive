"""tools/align_points.py —— 逐分 ↔ 比分板对齐（纯函数，不联网、不读图）。

判据都在合成数据上跑，映射关系拿 `wangxiyu-timofeeva`（王曦雨 vs Timofeeva，
WTA 辛辛那提 LS077，66 分 8 局）真实数据核对过一遍：局分从 set/game 变化重建、
破发点按发球方视角判，和 `fetch_match_pbp.summarise` 的口径一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def ap(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import align_points  # noqa: PLC0415

    return align_points


def _pt(setn, gamen, server, winner, pa, pb):
    """造一个 WTA 逐分形状的点。gameScore 是「这一分打完」的小分。"""
    return {"setNumber": setn, "gameNumber": gamen, "server": server,
            "pointWinner": winner,
            "scoreAfterPoint": {"gameScore": {"teamAScore": pa, "teamBScore": pb}}}


def _two_game_set():
    """第 1 局 A 发球保发，第 2 局 B 发球保发（每局 4 分，最后一分 G）。"""
    return [
        _pt(1, 1, "A", "A", "15", "0"),
        _pt(1, 1, "A", "A", "30", "0"),
        _pt(1, 1, "A", "A", "40", "0"),
        _pt(1, 1, "A", "A", "G", "0"),
        _pt(1, 2, "B", "B", "0", "15"),
        _pt(1, 2, "B", "B", "0", "30"),
        _pt(1, 2, "B", "B", "0", "40"),
        _pt(1, 2, "B", "B", "0", "G"),
    ]


def _break_sequence():
    """第 1 局 B 发球被 A 破发（40-0 后 A 拿下）。"""
    return [
        _pt(1, 1, "B", "A", "15", "0"),
        _pt(1, 1, "B", "A", "30", "0"),
        _pt(1, 1, "B", "A", "40", "0"),  # ← 破发点（server B 面对 0-40）
        _pt(1, 1, "B", "A", "G", "0"),
    ]


def test_point_states重建局分不读终局sets(ap):
    """局分从 set/game 变化 + pointWinner 重建，不能读 scoreAfterPoint.sets
    （那是终局比分，第 1 分就写着整盘结果）。"""
    states = ap.point_states(_two_game_set())
    assert [(s["games_A"], s["games_B"]) for s in states[:4]] == [(0, 0)] * 4, (
        "第 1 局打满 4 分，局分应该一直是 0-0")
    assert [(s["games_A"], s["games_B"]) for s in states[4:]] == [(1, 0)] * 4, (
        "A 拿下第 1 局，第 2 局里局分应该是 1-0")
    assert states[0]["point_A"] == "15" and states[0]["point_B"] == "0"
    assert states[7]["point_A"] == "0" and states[7]["point_B"] == "G", (
        "小分照抄，G 标记「这一分拿下这一局」要保留")


def test_point_states破发点按发球方视角(ap):
    """破发点要按发球方视角判：server B 面对 0-40（即 A 小分 40-0）是破发点，
    反过来 server A 的 40-0 不是破发点。"""
    states = ap.point_states(_break_sequence())
    assert states[2]["break_point"] is True, "server B 在 0-40 是破发点"
    assert states[0]["break_point"] is False, "15-0 还不是破发点"
    assert states[3]["break_point"] is False, "G 已经拿下，不算破发点"
    # 对照 _two_game_set：A 发球 40-0 保发，不是破发点
    hold = ap.point_states(_two_game_set())
    assert hold[2]["break_point"] is False, "发球方 40-0 领先不是破发点"


def test_point_states盘点在局分5领先且到局点(ap):
    """B 连下 5 局后在第 6 局到 40 → B 的盘点。每局只造一分，point_states 只数
    gameNumber 跳变，不数每局分数，所以能压成 6 分。"""
    pts = [_pt(1, g, "A", "B", "0", "G") for g in range(1, 6)]
    pts.append(_pt(1, 6, "B", "B", "0", "40"))
    states = ap.point_states(pts)
    last = states[-1]
    assert (last["games_A"], last["games_B"]) == (0, 5)
    assert last["set_point"] is True, "B 5-0 领先到 40 是盘点"


def test_parse_scoreboard各种格式(ap):
    """从原文抽数字分类，不依赖分隔符：`4 / 2`、带名字、`4-2`、局分+小分连着。"""
    assert ap.parse_scoreboard("4 / 2") == (4, 2, "", "")
    assert ap.parse_scoreboard("TIMOFEEVA 4 / WANG 2") == (4, 2, "", "")
    assert ap.parse_scoreboard("4-2") == (4, 2, "", "")
    assert ap.parse_scoreboard("0 / 40") == (-1, -1, "0", "40"), "40 只可能是小分"
    assert ap.parse_scoreboard("4 2 0 40") == (4, 2, "0", "40"), "局分 4-2 + 小分 0-40"
    # 顺序反了（小分在前）也要能换回来
    assert ap.parse_scoreboard("0 40 4 2") == (4, 2, "0", "40")


def test_parse_scoreboard读不出返回None不猜(ap):
    """名字、三盘比、空串都读不出单局比分，返回 None 不猜。"""
    assert ap.parse_scoreboard("MARIA TIMOFEEVA VS XIYU WANG") is None
    assert ap.parse_scoreboard("6 4 0 / 4 6 2") is None, "三盘比不是单局比分"
    assert ap.parse_scoreboard("") is None
    assert ap.parse_scoreboard("5") is None


def test_align关键分定位到视频秒(ap):
    """破发点那一分 → 命中的比分板读秒。局分精确、小分读到了也对上；读不到
    小分的读（只有局分）也算命中。"""
    states = ap.point_states(_break_sequence())  # 第 2 分是破发点（40-0）
    reads = [
        {"t": 10.0, "score": "0 0 40 0"},   # 局分 0-0 + 小分 40-0，精确命中
        {"t": 12.5, "score": "0 / 0"},      # 只有局分 0-0，也命中
        {"t": 20.0, "score": "1 / 0"},      # 局分对不上，跳过
        {"t": 30.0, "score": "MARIA TIMOFEEVA VS XIYU WANG"},  # 读不出，跳过
    ]
    aligned = ap.align(reads, states)
    assert len(aligned) == 1, f"只有第 2 分是破发点，aligned={aligned}"
    assert aligned[0]["index"] == 2
    assert aligned[0]["break_point"] is True
    assert aligned[0]["t"] == [10.0, 12.5], "两个命中的读都要保留（慢放/回放会重复出现）"


def test_align读结构化games_points(ap):
    """read_scoreboard 新版输出 games/points 分开的字段，align 要优先用它——
    局分和小分分开读，不会把「局分 2 + 小分 40」混成一个「2-40」。"""
    states = ap.point_states(_break_sequence())  # 第 2 分破发点：局分 0-0、小分 40-0
    reads = [
        {"t": 10.0, "games": "0-0", "points": "40-0"},  # 结构化，精确命中破发点
        {"t": 20.0, "games": "0-0", "points": "0-40"},  # 小分对不上（方向反了），跳过
        {"t": 30.0, "score": "0 0 40 0"},               # 旧自由文本，仍兼容
    ]
    aligned = ap.align(reads, states)
    assert aligned[0]["index"] == 2
    assert aligned[0]["t"] == [10.0, 30.0], "结构化 games/points 命中 + 旧 score 文本兼容"


def test_align时间码类型不一致也归一化(ap):
    """MiniMax 输出的 t 有的 float 有的 str，align 要统一归一化，别把 str 传给
    下游做减法（TypeError: str - float）。读不出数字的格子跳过。"""
    states = ap.point_states(_break_sequence())  # 第 2 分破发点 40-0
    reads = [
        {"t": "10.5", "score": "0 0 40 0"},    # str 时间码
        {"t": 12.0, "score": "0 0 40 0"},      # float 时间码
        {"t": "读不清", "score": "0 0 40 0"},   # 读不出数字，跳过
    ]
    aligned = ap.align(reads, states)
    assert aligned[0]["t"] == [10.5, 12.0], "str 和 float 都归一化成 float，读不清的跳过"
    assert all(isinstance(t, float) for t in aligned[0]["t"])


def test_align无关键分时返回空(ap):
    """一场没有破发/盘点/赛点的比赛（两边一路保发到 1-0），align 返回空。"""
    states = ap.point_states(_two_game_set())
    reads = [{"t": 10.0, "score": "1 / 0"}]
    assert ap.align(reads, states) == []


def _aligned():
    """合成对齐结果：4 个关键分，覆盖破发/盘点/赛点三种。"""
    return [
        {"index": 2, "set": 1, "game": 1, "games": "0-0", "point": "40-0",
         "break_point": True, "set_point": False, "match_point": False, "t": [10.0]},
        {"index": 28, "set": 1, "game": 4, "games": "0-3", "point": "0-40",
         "break_point": True, "set_point": False, "match_point": False, "t": [40.0]},
        {"index": 42, "set": 1, "game": 6, "games": "0-5", "point": "0-40",
         "break_point": True, "set_point": True, "match_point": False, "t": [60.0]},
        {"index": 65, "set": 2, "game": 3, "games": "0-2", "point": "40-0",
         "break_point": False, "set_point": True, "match_point": True, "t": [90.0]},
    ]


def test_screen_anchors映射赛点首盘转折结局(ap):
    """①冷开场=赛点、⑤首盘=第一个关键分、⑥转折=最后一个破发点、⑦结局=最后一个
    盘点/赛点。"""
    anchors = ap.screen_anchors([], _aligned(), clip_end=100.0)
    assert anchors["cold_open"] == 90.0, "赛点那一分是全片最抓人的开场"
    assert anchors["first_set"] == 10.0, "首盘=第一个关键分（开场最早）"
    assert anchors["turning"] == 60.0, "转折=最后一个破发点（换手最硬的信号）"
    assert anchors["finale"] == 90.0, "结局=最后一个盘点/赛点"
    assert anchors["outro"] == 100.0, "收尾=视频结尾"


def test_screen_anchors无对齐时全None(ap):
    """没有对齐结果（比分板一个都没读出来），锚点全 None，收尾照传 clip_end。"""
    anchors = ap.screen_anchors([], [], clip_end=88.0)
    assert anchors == {"cold_open": None, "first_set": None, "turning": None,
                       "finale": None, "outro": 88.0}


def test_segment_skeleton生成草稿窗口(ap):
    """锚点 + 旁白 → 草稿 segments：冷开场无旁白，三个 beat 各挂一句旁白。"""
    anchors = ap.screen_anchors([], _aligned(), clip_end=100.0)
    segs = ap.segment_skeleton(
        anchors, ["她一分一分追回来", "五个破发点一个都没给", "六比零三比零"],
        margin=5.0)
    assert [s["start"] for s in segs] == [85.0, 5.0, 55.0, 85.0]
    assert segs[0]["narration"] == "", "冷开场不配旁白，留现场声"
    assert segs[1]["narration"] == "她一分一分追回来"   # beat 0 → 首盘
    assert segs[2]["narration"] == "五个破发点一个都没给"  # beat 1 → 转折
    assert segs[3]["narration"] == "六比零三比零"       # beat 2 → 结局


def test_segment_skeleton旁白不够就留空(ap):
    """旁白条数少于 3 句时，缺的挂空串，不崩、不越界。"""
    anchors = ap.screen_anchors([], _aligned())
    segs = ap.segment_skeleton(anchors, ["只有一句"], margin=5.0)
    assert segs[0]["narration"] == ""
    assert segs[1]["narration"] == "只有一句"
    assert segs[2]["narration"] == ""


def test_finalize_windows装得下旁白不跨切点(ap):
    """窗口收口：带旁白的段至少 speech_seconds+余量 宽；窗口内的切点要收住，
    切点前不够装就把 start 挪到切点后重扩。冷开场（无旁白）只做切点对齐。"""
    segs = [
        {"start": 10.0, "end": 14.0, "narration": "她一分一分追回来五个破发点一个都没给这场球打了两小时"},
        {"start": 20.0, "end": 25.0, "narration": ""},   # 冷开场
    ]
    out = ap.finalize_windows(segs, [13.0, 30.0])
    # 第一段：切点 13 在窗口内且切点前不够装旁白 → start 挪到 13.2，end 扩到够装
    s0 = out[0]
    assert s0["start"] >= 13.2, "切点前不够装，start 该挪到切点后"
    assert s0["end"] - s0["start"] >= 5.0, "窗口至少装得下旁白（26 字 ≈ 4.6s + 余量）"
    # 冷开场：窗口保持，不硬扩
    assert out[1] == {"start": 20.0, "end": 25.0, "narration": ""}


def test_finalize_windows切点前够装就收end(ap):
    """切点前够装旁白时，end 收到切点前（留溶解），start 不动。"""
    segs = [{"start": 10.0, "end": 20.0, "narration": "短句"}]
    out = ap.finalize_windows(segs, [15.0])
    assert out[0]["end"] == 14.8, "切点 15 前够装（10→14.8 有 4.8s），end 收到切点前"
    assert out[0]["start"] == 10.0
