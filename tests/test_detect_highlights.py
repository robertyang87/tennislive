"""tools/detect_highlights.py —— T0 集锦探测（只测纯函数，yt-dlp 搜索不测）。"""

from __future__ import annotations

import sys
from pathlib import Path


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import detect_highlights as dh  # noqa: PLC0415

    return dh


def test_query_for用姓和简称拼词():
    dh = _tool()
    q = dh.query_for("Alexandra Eala", "Jessica Pegula", "Mubadala Citi DC Open", 2026)
    assert "Eala" in q and "Pegula" in q, "用姓，不用全名"
    assert "highlights" in q
    assert "Mubadala" not in q, "赞助商前缀要被 short_event 剥掉"
    assert "2026" in q


def test_pick_highlight宁可窄不要错():
    dh = _tool()
    good = [("Eala vs Pegula Highlights | Washington 2026", "https://y/1")]
    bad_title = [("Eala vs Pegula | Washington 2026", "https://y/2")]  # 没 highlights
    wrong_player = [("Eala vs Svitolina Highlights | Washington", "https://y/3")]
    assert dh.pick_highlight(good, "Eala", "Pegula") == "https://y/1"
    assert dh.pick_highlight(bad_title, "Eala", "Pegula") is None
    assert dh.pick_highlight(wrong_player, "Eala", "Pegula") is None


def test_pick_highlight没搜到返回None():
    dh = _tool()
    assert dh.pick_highlight([], "Eala", "Pegula") is None
