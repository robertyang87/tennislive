"""tools/pick_oncourt_clips.py —— 从采访库里挑「该剪成片」的候选（纯函数，不联网）。

三道成片闸在 oncourt_feed 的选题闸之上：
① kind == oncourt  ② 未做过成片  ③ 赛事还在打/刚打完（日历窗口 + 年份校验）。
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import pick_oncourt_clips as p  # noqa: PLC0415

    return p


def _cal():
    return [
        {"en": "Cincinnati Open", "zh": "辛辛那提大师赛", "start": "08-16", "end": "08-23",
         "pat": "cincinnati"},
        {"en": "Internazionali BNL d'Italia", "zh": "罗马大师赛", "start": "05-06", "end": "05-17",
         "pat": "rome"},
    ]


TODAY = datetime.date(2026, 8, 18)


def test_video_id归一化跨来源(tool):
    assert tool._video_id("https://www.youtube.com/watch?v=ABC123") == "ABC123"
    assert tool._video_id("https://youtu.be/XYZ789") == "XYZ789"
    assert tool._video_id("https://www.tennistv.com/videos/4561546/cincinnati-2026") == "4561546"
    assert tool._video_id("") == ""


def test_tennistv只有free资源进入无人值守生产(tool):
    base = {"id": "tennistv:4563954"}
    assert tool.production_resource_problem({**base, "entitlement": "free"}) == ""
    problem = tool.production_resource_problem({**base, "entitlement": "freemium"})
    assert "freemium" in problem and "注册会话" in problem
    assert tool.production_resource_problem({"id": "youtube:abc"}) == ""


def test_event_window窗口内入选窗口外排除(tool):
    # 辛辛那提 2026 窗口 08-16/08-23，今天 08-18 → 在窗口内
    assert tool.event_window({"title": "De Minaur Interview | Cincinnati 2026",
                              "url": "https://t.co/x"}, TODAY, _cal()) == ("辛辛那提大师赛", True)
    # 罗马 2026 窗口 05-06/05-17 → 今天早过了
    assert tool.event_window({"title": "On-Court Interview | Final | Rome 2026",
                              "url": ""}, TODAY, _cal()) == ("罗马大师赛", False)


def test_event_window陈年年份排除(tool):
    """title 里写了 2024/2025 → 排除，别让 2026 的窗口把它误判成「还在打」。"""
    assert tool.event_window(
        {"title": "Amanda Anisimova vs. Emma Navarro | 2024 Cincinnati Semifinal",
         "url": ""}, TODAY, _cal()) == (None, False)


def test_event_window年份藏url也要排除(tool):
    """tennistv 的标题常不写年份，但 url 里有（toronto-2025-…）——年份要从
    title 和 url 一起抽。"""
    assert tool.event_window(
        {"title": "Shelton storms into Toronto final",
         "url": "https://www.tennistv.com/videos/4335570/toronto-2025-sf-shelton-interview"},
        TODAY, _cal()) == (None, False)


def test_轮次未知不能建立逐场ID(tool, monkeypatch):
    monkeypatch.setattr(tool, "interviewee_en", lambda title: "Jessica Pegula")
    row = {"title": "Jessica Pegula On-Court Interview | Cincinnati 2026"}
    assert tool.match_id_for(row, "辛辛那提大师赛", TODAY) == "", (
        "同一球员一站会赢多场；缺轮次时不能把整站折成一场再猜对手")

    row["round_zh"] = "四分之一决赛"
    got = tool.match_id_for(row, "辛辛那提大师赛", TODAY)
    assert got == "2026:辛辛那提大师赛:qf:jessica-pegula"
    assert ":unknown:" not in got, "中文赛事名不能被 ASCII 清洗器压成 unknown"


def test_candidates三道闸(tool, monkeypatch, tmp_path):
    """kind 不对 / 已做过 / 窗口外 / & 双打，各挡一条。"""
    done = tmp_path / "done.json"
    done.mkdir()
    (done / "old.json").write_text(json.dumps({
        "url": "https://www.youtube.com/watch?v=ALREADYDONE"}), encoding="utf-8")

    cal = tmp_path / "cal.json"
    cal.write_text(json.dumps({"events": _cal()}), encoding="utf-8")

    lib = tmp_path / "lib.json"
    lib.write_text(json.dumps({"items": {
        "good": {"id": "GOOD2026", "kind": "oncourt", "url": "https://youtu.be/GOOD2026",
                 "title": "Alexander Zverev On-Court Interview | Quarterfinal | Cincinnati 2026",
                 "round_zh": "四分之一决赛", "source": "Cincinnati Open"},
        "ceremony": {"kind": "ceremony", "url": "https://youtu.be/CER",
                     "title": "Finalist Speech | Cincinnati 2026", "source": "X"},
        "done_already": {"kind": "oncourt", "url": "https://youtu.be/ALREADYDONE",
                         "title": "On-Court Interview | Final | Cincinnati 2026", "source": "X"},
        "old": {"kind": "oncourt", "url": "https://youtu.be/OLD",
                "title": "On-Court Interview | Final | Cincinnati 2024", "source": "X"},
        "doubles": {"kind": "oncourt", "url": "https://youtu.be/DBL",
                    "title": "Cash & Glasspool are triumphant | Cincinnati 2026", "source": "X"},
    }}), encoding="utf-8")

    monkeypatch.setattr(tool, "LIB", lib)
    monkeypatch.setattr(tool, "CAL", cal)
    monkeypatch.setattr(tool, "SPECS", done)
    monkeypatch.setattr(tool, "load_cn", lambda: ([], [], [], []))

    cands = tool.candidates(today=TODAY)
    assert [c["id"] for c in cands] == ["GOOD2026"], (
        f"只有 GOOD2026 该入选，实际 {[c['id'] for c in cands]}")
    assert cands[0]["event_zh"] == "辛辛那提大师赛"
