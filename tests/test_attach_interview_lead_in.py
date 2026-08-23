"""同场获胜画面冷开场：窗口选择和身份透传，不联网。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import attach_interview_lead_in as lead  # noqa: E402
from interview_source_gate import finalize_source_contract  # noqa: E402


def _spec() -> dict:
    spec = {
        "slug": "zverev-atmane-cincinnati-2026-qf",
        "url": "https://example.test/interview",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": {
            "status": "verified", "detected_type": "on_court",
            "method": "human_visual_verdict", "source_url": "https://example.test/interview",
            "evidence": [{"kind": "visual_verdict", "by": "test"}],
        },
        "match": {
            "id": "2026:cincinnati:qf:zverev", "event": "辛辛那提大师赛",
            "round": "四分之一决赛", "winner": "兹维列夫", "loser": "阿特马内",
            "participants": ["兹维列夫", "阿特马内"],
            "winner_en": "Alexander Zverev", "loser_en": "Terence Atmane",
            "event_search": "Cincinnati Open", "year": 2026,
        },
    }
    return finalize_source_contract(spec)


def test_select_window只取片尾连续解说且不超40秒():
    cues = [
        {"a": 2.0, "b": 4.0, "en": "early rally"},
        {"a": 70.0, "b": 73.0, "en": "championship point is over"},
        {"a": 74.0, "b": 78.0, "en": "what a victory for Zverev"},
        {"a": 79.0, "b": 82.0, "en": "he moves into the semifinal"},
    ]
    start, end, selected = lead.select_window(cues, 90.0, seconds=20.0)
    assert start == 70.0 and end == 82.0
    assert len(selected) == 3 and end - start <= 40.0


def test_attach把同场官方集锦和逐cue双语字幕写回(monkeypatch, tmp_path):
    sub = tmp_path / "lead.json3"
    sub.write_text(json.dumps({"events": [
        {"tStartMs": 70000, "dDurationMs": 3000,
         "segs": [{"utf8": "Championship point is over"}]},
        {"tStartMs": 74000, "dDurationMs": 4000,
         "segs": [{"utf8": "What a victory for Zverev"}]},
    ]}), encoding="utf-8")
    monkeypatch.setattr(lead, "find_highlight",
                        lambda *_a, **_k: ("https://youtu.be/highlight", "official search"))
    monkeypatch.setattr(lead, "probe_meta", lambda _url: ("ATP Tour", 82.0, 1080.0))
    monkeypatch.setattr(lead, "_download_subtitles", lambda *_a, **_k: sub)
    monkeypatch.setattr(lead, "translate",
                        lambda rows, _chat: [f"中译{i}" for i, _ in enumerate(rows, 1)])

    got = lead.attach(_spec(), object())
    assert got["lead_in"]["url"] == "https://youtu.be/highlight"
    assert got["lead_in"]["verification"]["match_id"] == got["match"]["id"]
    assert [row["zh"] for row in got["lead_in"]["subs"]] == ["中译1", "中译2"]


def test_attach找不到精确同场官方集锦就明确停止(monkeypatch):
    monkeypatch.setattr(lead, "find_highlight", lambda *_a, **_k: (None, ""))
    with pytest.raises(RuntimeError, match="尚未找到"):
        lead.attach(_spec(), object())


def test_正式片头verification必须与当前比赛逐字段一致():
    from build_interview_clip import check_lead_in

    spec = _spec()
    spec["lead_in"] = {
        "url": "https://youtu.be/highlight", "start": 70.0, "end": 78.0,
        "why": "同场赛点和获胜后解说",
        "subs": [{"a": 70.0, "b": 72.0, "en": "Match point", "zh": "赛点"}],
        "verification": {
            "match_id": spec["match"]["id"], "channel": "ATP Tour", "height": 1080,
            "method": "official_exact_match_highlight",
            "winner_en": spec["match"]["winner_en"],
            "loser_en": spec["match"]["loser_en"],
            "event_search": spec["match"]["event_search"], "year": 2026,
        },
    }
    check_lead_in(spec)
    no_subs = _spec()
    no_subs["lead_in"] = {k: v for k, v in spec["lead_in"].items() if k != "subs"}
    with pytest.raises(SystemExit, match="必须配中英文字幕"):
        check_lead_in(no_subs)
    spec["lead_in"]["verification"]["loser_en"] = "Wrong Opponent"
    with pytest.raises(SystemExit, match="与当前比赛不一致"):
        check_lead_in(spec)
