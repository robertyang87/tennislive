"""全出血「赛场之上」的比分板回贴只认标定过的转播（账号所有者 2026-09-24）。

「消失后背景还在……像狗皮膏药」「右边突然多一块补丁」「那去彻底解决啊」——
两个毛病都出在老的整段矩形回贴，而没标定过的转播原来会静悄悄地走它。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_match_reel as b  # noqa: E402

ON = [{"score_inset": True}]


@pytest.mark.parametrize("line1, want", [
    ("2026 WTA500 新加坡站 1/8决赛", "wta"),
    ("2026 ATP250 成都站 首轮", "atp"),
    ("2026 比利·简·金杯 1/4决赛", "itf-bjk"),
])
def test_认得出的转播走各自的逐帧判据(line1, want):
    assert b.scoreboard_profile({"topbar": {"line1": line1}, "segments": ON}) == want


def test_认不出的转播直接报错_不退回老的矩形回贴():
    with pytest.raises(b.ReelError, match="认不出是哪一家转播"):
        b.scoreboard_profile({"topbar": {"line1": "2026 戴维斯杯资格赛 第二轮"},
                              "segments": ON})


def test_没开回贴的片子不管():
    assert b.scoreboard_profile({"topbar": {"line1": "2026 戴维斯杯"},
                                 "segments": [{"score_inset": False}]}) is None


def test_全库开了回贴的全出血片子都落在标定过的转播上():
    """新写的 spec 撞上没标定的转播，这条和 `--dry-run` 一起红。"""
    seen = 0
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if not isinstance(spec, dict) or spec.get("layout") == "band":
            continue
        if not any(isinstance(s, dict) and s.get("score_inset")
                   for s in spec.get("segments") or []):
            continue
        seen += 1
        assert b.scoreboard_profile(spec) in {"atp", "wta", "itf-bjk"}, path.name
    assert seen >= 5, "一条开了回贴的全出血 spec 都没扫到，判据的主语像是没了"


def test_自动草稿的顶栏拼不出级别时_按赛事名和男女认转播():
    """`tour_topline` 认不出城市站时自动草稿的顶栏是「2026 SINGAPORE 1/8决赛」，
    没有 WTA 字样；北京这种男女同站的赛事，级别表只记一个，要按头像前缀分男女。"""
    auto = {"topbar": {"line1": "2026 SINGAPORE 1/8决赛"}, "segments": ON,
            "_production": {"event": "SINGAPORE"}}
    assert b.scoreboard_profile(auto) == "wta"
    beijing = {"topbar": {"line1": "2026 BEIJING 第二轮"}, "segments": ON,
               "_production": {"event": "BEIJING"},
               "stats": {"a": {"headshot": "assets/players/headshots/wta-330332.jpg"}}}
    assert b.scoreboard_profile(beijing) == "wta"
    beijing["stats"]["a"]["headshot"] = "assets/players/headshots/atp-Y09V.png"
    assert b.scoreboard_profile(beijing) == "atp"
