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
    d = Digest(today=None,
               results=[_match(MatchStatus.FINISHED)],
               live=[_match(MatchStatus.LIVE)],
               schedule=[_match(MatchStatus.SCHEDULED)],
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
