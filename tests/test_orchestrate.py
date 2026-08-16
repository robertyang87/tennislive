"""tools/orchestrate.py —— 无人值守编排器的纯函数（不联网、不 dispatch）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import orchestrate  # noqa: PLC0415

    return orchestrate


def _match(status):
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    return Match(
        match_id="x", tour=Tour.WTA,
        tournament=Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000"),
        home=[Player(name="Alexandra Eala", country="PHI", seed=5)],
        away=[Player(name="Jessica Pegula", country="USA", seed=2)],
        status=status, round_name="Final", sets=[SetScore(6, 4)])


def test_路由完赛进reel未开赛进preview进行中不路由():
    from tennislive.models import MatchStatus
    o = _tool()
    assert o.route(_match(MatchStatus.FINISHED)) == "reel"
    assert o.route(_match(MatchStatus.SCHEDULED)) == "preview"
    assert o.route(_match(MatchStatus.LIVE)) == "", "进行中的比赛不该被路由"


def test_candidates跳过进行中的比赛():
    from tennislive.digest import Digest
    from tennislive.models import MatchStatus
    o = _tool()
    # ⚠️ 完赛和未开赛必须用**不同的球员对**——同 slug 会被去重并成一条，
    # 而这条测试要验的是「live 被跳过」不是「同场去重」。
    finished = _match(MatchStatus.FINISHED)
    scheduled = _match(MatchStatus.SCHEDULED)
    scheduled.home[0].name = "Qinwen Zheng"
    scheduled.away[0].name = "Aryna Sabalenka"
    d = Digest(today=None,
               results=[finished],
               live=[_match(MatchStatus.LIVE)],
               schedule=[scheduled],
               source="x")
    cands = o.candidates(d)
    assert len(cands) == 2, "只该有完赛 + 未开赛两条，live 要跳过"
    assert {c["column"] for c in cands} == {"reel", "preview"}


def test_工作流映射按栏目对上生产线():
    o = _tool()
    assert o._workflow_for("reel") == "match-reel.yml"
    assert o._workflow_for("preview") == "preview-reel.yml", (
        "开球之前要独立管线（08-08 定了单独走），别混进 match-reel，"
        "也别走 explainer 的卡片视频")


def test_slug取姓拼横杠():
    o = _tool()
    m = _match(0)
    assert o.slug_for(m) == "eala-pegula"


def test_slug缩写名取第一个词当姓():
    """ESPN 缩写名「Kenin S.」姓在第一个词，取最后一个词会得到 s. 垃圾 slug。"""
    from tennislive.models import Match, Player, Tour, Tournament
    o = _tool()
    m = Match(
        match_id="x", tour=Tour.WTA,
        tournament=Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000"),
        home=[Player(name="Kenin S.", country="USA")],
        away=[Player(name="Lys E.", country="GER")],
        status=0)
    assert o.slug_for(m) == "kenin-lys", "缩写名要取第一个词当姓，不是最后一个"


def test_candidates同场去重且留全名():
    from tennislive.digest import Digest
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    o = _tool()
    tour = Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000")

    def _m(home, away):
        return Match(
            match_id="x", tour=Tour.WTA, tournament=tour,
            home=[Player(name=home, country="X")],
            away=[Player(name=away, country="Y")],
            status=MatchStatus.FINISHED, round_name="Final",
            sets=[SetScore(6, 4)])

    full = _m("Sofia Kenin", "Eva Lys")
    abbr = _m("Kenin S.", "Lys E.")
    d = Digest(today=None, results=[full, abbr], live=[], schedule=[], source="x")
    cands = o.candidates(d)
    slugs = [c["slug"] for c in cands]
    assert slugs == ["kenin-lys"], f"同场去重后只该有一条，实际 {slugs}"
    assert cands[0]["home"] == "sofia kenin", "去重要留全名版，不是缩写版"


def test_candidates缩写名还原成全名():
    """ESPN 缩写名（Kovacevic A.）要还原成全名——detect_highlights 的搜索词和
    assemble 的译名都要全名，缩写直接拿去搜会搜错。"""
    from tennislive.digest import Digest
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    o = _tool()
    m = Match(
        match_id="x", tour=Tour.WTA,
        tournament=Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000"),
        home=[Player(name="Kovacevic A.", country="USA")],
        away=[Player(name="Khachanov K.", country="RUS")],
        status=MatchStatus.FINISHED, round_name="Final",
        sets=[SetScore(6, 4)])
    d = Digest(today=None, results=[m], live=[], schedule=[], source="x")
    cands = o.candidates(d)
    assert cands[0]["home"] == "aleksandar kovacevic", "缩写名要还原成全名"
    assert cands[0]["away"] == "karen khachanov"


def test_beijing_today是date():
    o = _tool()
    import datetime as dt
    assert isinstance(o._beijing_today(), dt.date)


def test_main把今天传给build_digest(monkeypatch, capsys):
    """编排器从没真跑过：build_digest() 必填 today，裸调会 TypeError。钉住
    main 必须传北京时间的今天，否则这条工具在 CI 上一触发就崩。"""
    o = _tool()
    captured = {}

    def fake_build(today):
        captured["today"] = today
        return type("D", (), {"results": [], "schedule": []})()

    monkeypatch.setattr(o, "build_digest", fake_build)
    monkeypatch.setattr(o, "candidates", lambda dig: [])
    monkeypatch.setattr(sys, "argv", ["orchestrate.py"])
    rc = o.main()
    assert rc == 0
    assert "today" in captured, "build_digest 必须收到 today 参数"


def test_assemble_draft跳过出声(monkeypatch):
    o = _tool()
    notes = o.assemble_draft({"slug": "x"}, skip=True)
    assert notes == ["[assemble] 已跳过（--no-assemble）"]


def test_assemble_draft成功返回备料notes(monkeypatch):
    o = _tool()

    def _fake_assemble(**kw):
        return {"_notes": ["flashscore id：A"]}

    fake = type("M", (), {"assemble": staticmethod(_fake_assemble)})()
    monkeypatch.setitem(sys.modules, "assemble_spec", fake)
    notes = o.assemble_draft({"slug": "eala-pegula", "home": "A E", "away": "B R",
                              "event": "C", "year": 2026})
    assert notes[0] == "[assemble] eala-pegula 草稿备好（未落盘）"
    assert "flashscore id：A" in notes


def test_assemble_draft失败不抛出声(monkeypatch):
    o = _tool()

    class Boom:
        def assemble(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setitem(sys.modules, "assemble_spec", Boom())
    notes = o.assemble_draft({"slug": "x", "home": "A", "away": "B",
                              "event": "C", "year": 2026})
    assert any("备料没成" in n and "network down" in n for n in notes), (
        "备料失败必须出声且不抛——dispatch 已经点下去了，别让便宜的备料把整趟带崩")
