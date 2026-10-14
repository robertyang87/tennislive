"""自动草稿反查比赛：按整词、分两边认人（2026-10-12 王曦雨对王欣瑜配到了 Sawangkaew/Joint）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import fetch_match_pbp as pbp  # noqa: E402
import fetch_match_stats_fs as fs  # noqa: E402
from tennislive.names import name_fits, pair_fits  # noqa: E402


def test_子串不算同一个人():
    assert not name_fits("wang", "Sawangkaew M.")
    assert not name_fits("Xiyu Wang", "Sawangkaew M.")


def test_缩写名和全名认得上_同姓靠名字分开():
    assert name_fits("Xiyu Wang", "Wang Xiy.")
    assert not name_fits("Xinyu Wang", "Wang Xiy.")
    assert name_fits("Felix Auger-Aliassime", "Auger-Aliassime F.")
    assert name_fits("Elena-Gabriela Ruse", "Ruse E. G.")
    assert name_fits("Iga Swiatek", "Świątek I.")
    assert name_fits("medvedev", "Medvedev D.")


def test_两个名字要落在两边():
    assert pair_fits(["Xiyu Wang", "Xinyu Wang"], "Wang Xin.", "Wang Xiy.")
    assert not pair_fits(["wang", "wang"], "Wang Xiy.", "Joint M.")


def _body(home: str, away: str, mid: str) -> str:
    return f"SA÷2¬~AA÷{mid}¬AE÷{home}¬AF÷{away}¬"


def test_flashscore反查不再配到Sawangkaew(monkeypatch):
    rows = _body("Sawangkaew M.", "Joint M.", "wrong") + _body("Wang Xiy.", "Wang Xin.", "right")
    monkeypatch.setattr(fs, "feed", lambda name: rows)
    assert fs.find_match(["Xiyu Wang", "Xinyu Wang"], offsets=(0,))[0] == "right"


def test_WTA接口反查同一条规则(monkeypatch):
    def fake_get(session, path, params=None, **kw):
        if path == "tournaments":
            return {"content": [{"tournamentGroup": {"id": 1075}, "year": 2026}]}
        return {"matches": [
            {"MatchID": "LS999", "PlayerNameFirstA": "Mananchaya", "PlayerNameLastA": "Sawangkaew",
             "PlayerNameFirstB": "Maya", "PlayerNameLastB": "Joint"},
            {"MatchID": "LS045", "PlayerNameFirstA": "Xiyu", "PlayerNameLastA": "Wang",
             "PlayerNameFirstB": "Xinyu", "PlayerNameLastB": "Wang"}]}
    monkeypatch.setattr(pbp, "get", fake_get)
    from datetime import date
    got = pbp.find_match(None, ["Xinyu Wang", "Xiyu Wang"], date(2026, 10, 11), date(2026, 10, 12))
    assert got[2] == "LS045"
