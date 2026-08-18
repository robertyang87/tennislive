"""tools/draft_interview_spec.py —— 自动建「赛后开麦」spec 草稿（纯函数，不联网）。

转写/翻译要 faster-whisper + DeepSeek（Actions 里跑），这里只测不联网的
拼接逻辑：slug 生成（受访者-赛事-年份-轮次）和草稿结构。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import draft_interview_spec as d  # noqa: PLC0415

    return d


def _cal():
    return [{"en": "Cincinnati Open", "zh": "辛辛那提大师赛", "start": "08-16",
             "end": "08-23", "pat": "cincinnati"}]


def test_event_year_round从标题解析(tool):
    ev, year, rnd = tool._event_year_round(
        "Cincinnati 2026 R3 Alexander Zverev Interview", _cal())
    assert (ev, year, rnd) == ("cincinnati", "2026", "r3")
    ev, year, rnd = tool._event_year_round(
        "On-Court Interview | Quarterfinal | Rome 2026", [])
    assert rnd == "qf", "四分之一决赛 → qf"


def test_surname_zh_player取受访者(tool):
    assert tool._surname_zh_player("Cincinnati 2026 R3 Alexander Zverev Interview") == "zverev"
    assert tool._surname_zh_player("On-Court Interview: Iga Swiatek says …") == "swiatek"


def test_build_spec草稿结构(tool):
    c = {"title": "Cincinnati 2026 R3 Alexander Zverev Interview",
         "url": "https://t.co/x", "event_zh": "辛辛那提大师赛", "id": "VID1"}
    spec = tool.build_spec(c, ["萨沙 恭喜你", "这场打得很过瘾"], 53.7, _cal())
    assert spec["_draft"] is True
    assert spec["slug"] == "zverev-cincinnati-2026-r3"
    assert spec["start"] == 0.0 and spec["end"] == 53.7
    assert spec["asr_model"] == "small.en"
    assert spec["column"] == "赛后开麦"
    assert spec["zh"] == ["萨沙 恭喜你", "这场打得很过瘾"]
    assert spec["transcript_verified"] is False, "双模型核对由 render 的 verify_transcript 完成"
    assert spec["_candidate_id"] == "VID1"
