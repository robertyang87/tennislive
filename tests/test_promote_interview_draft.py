"""tools/promote_interview_draft.py —— 草稿提升（不联网，mock digest）。

核心判据：render 顶栏硬要求 `winner` 且在 `push.matchup` 里（build_interview_clip
1159 行的闸），所以提升必须从赛果反查对手——查不到就不提升，宁可留草稿。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import promote_interview_draft as p  # noqa: PLC0415

    return p


def _match(home_name, away_name, winner_idx=0):
    """造一个最小 Match 形状（home/away 各一个 Player，winner_players 返回赢家）。"""
    class _P:
        def __init__(self, name):
            self.name = name

    class _M:
        def __init__(self):
            self.home = [_P(home_name)]
            self.away = [_P(away_name)]
            self.winner = home_name if winner_idx == 0 else away_name

        def winner_players(self):
            return self.home if self.winner == self.home[0].name else self.away

    return _M()


def test_find_opponent按姓找对手(tool, monkeypatch):
    """受访者姓 zverev，赛果里他的对手是 Atmane——返回 (兹维列夫, 阿特马内, 对阵)。"""
    class _Digest:
        results = [_match("Zverev A.", "Atmane T.")]

    monkeypatch.setattr("tennislive.zh.player_zh", lambda en: {
        "Zverev A.": "兹维列夫", "Atmane T.": "阿特马内",
        "Alexander Zverev": "兹维列夫"}.get(en, en))
    got = tool.find_opponent(_Digest(), "zverev")
    assert got == ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内")


def test_find_opponent受访者不是赢家返回None(tool):
    """赛后采访都是赢球后，受访者不是赢家就返回 None（别猜）。"""
    class _Digest:
        results = [_match("Atmane T.", "Zverev A.", winner_idx=0)]

    assert tool.find_opponent(_Digest(), "zverev") is None


def test_find_opponent赛果里没有这位球员返回None(tool):
    class _Digest:
        results = [_match("Sinner J.", "Alcaraz C.")]

    assert tool.find_opponent(_Digest(), "zverev") is None


def test_promote补winner和push(tool):
    draft = {"_draft": True, "slug": "zverev-cincinnati-2026-r3",
             "url": "x", "zh": ["a"]}
    spec = tool.promote(draft, ("兹维列夫", "阿特马内", "兹维列夫 vs 阿特马内"))
    assert "_draft" not in spec, "正式 spec 不带草稿标记"
    assert spec["winner"] == "兹维列夫"
    assert spec["push"]["matchup"] == "兹维列夫 vs 阿特马内"
    assert spec["zh"] == ["a"], "草稿已有的 zh 要保留"
