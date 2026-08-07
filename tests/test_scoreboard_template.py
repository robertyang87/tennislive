from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel  # noqa: E402
import versus_poster  # noqa: E402


def _cover() -> dict:
    return {
        "winner": "伊埃拉",
        "result": "6-1 4-6 6-2",
        "matchup": [
            {"name": "伊埃拉", "name_en": "A. EALA", "country": "PHI", "rank": 25},
            {"name": "帕克斯", "name_en": "A. PARKS", "country": "USA", "rank": 71},
        ],
        "scoreboard": {"court": "Centre Court", "duration_source": {"url": "fixture"}},
    }


def test_scoreboard_uses_real_duration_and_per_set_winners(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    html = versus_poster._scoreboard_html(_cover())

    assert "1:51" in html
    assert 'class="score-flag"' in html
    assert "🇵🇭" not in html and "🇺🇸" not in html
    assert "伊埃拉" in html and "（25）" in html and "A. EALA" in html
    assert "帕克斯" in html and "（71）" in html and "A. PARKS" in html
    assert html.count('class="score-number setwin"') == 3
    assert html.count('class="score-number setlose"') == 3


def test_duration_parser_hides_seconds():
    assert versus_poster._duration_seconds("01:51:42") == 6702
    hours, minutes = divmod(6702 // 60, 60)
    assert f"{hours}:{minutes:02d}" == "1:51"


def test_scoreboard_requires_rank(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(versus_poster, "_fetch_match_duration", lambda source, where: "1:51")
    cover = _cover()
    del cover["matchup"][1]["rank"]
    with pytest.raises(SystemExit, match="缺 `rank`"):
        versus_poster._scoreboard_html(cover)


def test_match_video_remains_full_bleed():
    graph = build_match_reel.topbar_filtergraph(
        1.8, 10.0, Path("topbar.ass"), Path("subtitles.ass")
    )
    assert "crop=1080:1440" in graph
    assert "drawbox=x=0:y=0:w=iw:h=150" in graph
    assert "scale=-2:1290" not in graph
    assert "match_bg_src" not in graph
    assert "overlay=(W-w)/2" not in graph
