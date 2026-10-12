"""自动建「赛后开麦」spec 草稿的机械半截（原 `tools/draft_interview_spec.py`）。

草稿生成器本体已于 2026-10-12 随模型通道整体移除；它原来的两个纯机械
helper 搬了家、活还在，这里只钉它们：

| helper | 现在的家 |
|---|---|
| `interviewee_en`（从名册认受访者） | `tools/pick_oncourt_clips.py` |
| `cap_json3`（ASR 行 → json3 形状） | `tools/build_interview_request.py` |
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def pick_tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import pick_oncourt_clips as p  # noqa: PLC0415

    return p


@pytest.fixture()
def request_tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import build_interview_request as b  # noqa: PLC0415

    return b


def test_interviewee_en从名册认人不按位置猜(pick_tool):
    """**旧版取「最后一个大写词」在真实标题上几乎全错**——受访者常在标题开头，
    尾巴是赛事名。判据拿 `data/oncourt_interviews.json` 里的真实标题形状：
    受访者在头、在尾、在冒号后都要认得出，认的是**名册里的全名**。"""
    # 受访者在开头，尾巴是赛事名（旧版取出来是 Hopman/Mastercard 一类）
    assert pick_tool.interviewee_en(
        "Karen Khachanov on-court interview (RR) | Mastercard Hopman Cup 2018"
    ) == "Karen Khachanov"
    # 受访者在中间（冒号后）
    assert pick_tool.interviewee_en(
        "On-Court Interview: Jasmine Paolini feels 'elated' with her win"
    ) == "Jasmine Paolini"
    # 受访者在结尾
    assert pick_tool.interviewee_en(
        "Cincinnati 2026 R3 Alexander Zverev Interview") == "Alexander Zverev"
    # 双人标题取位置靠前的那个
    assert pick_tool.interviewee_en(
        "Djokovic and Kyrgios' BROMANCE BLOSSOMS in on-court interview"
    ).endswith("Djokovic")
    # 名册里没有的名字：返回空串，不许瞎猜
    assert pick_tool.interviewee_en("Some Nobody Qualifier Interview 2026") == ""


def test_cap_json3是fetch_words认的形状(request_tool):
    """`fetch_words` 报错正文写的约定：`events[].tStartMs` + `segs[].utf8`。
    `dDurationMs` 也要给——`_caption_spans` 按它算空档，全 0 的话 whisper
    分段之间的每个间隙都会被误报成空档，render 那道闸淹在假红里。"""
    rows = [{"t": 1.42, "end": 3.9, "text": "Well, thank you."},
            {"t": 4.0, "end": 4.5, "text": "It was tough."}]
    data = request_tool.cap_json3(rows)
    evs = data["events"]
    assert evs[0]["tStartMs"] == 1420
    assert evs[0]["dDurationMs"] == 2480
    assert evs[0]["segs"] == [{"utf8": "Well, thank you."}]
    assert evs[1]["tStartMs"] == 4000 and evs[1]["dDurationMs"] == 500
    # whisper 不分说话人，不许编 `>> ` 标记（假边界比没有更糟）
    assert not any(">>" in s["utf8"] for e in evs for s in e["segs"])
