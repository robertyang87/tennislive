"""同场获胜画面冷开场：窗口选择、字幕解析和待配清单，不联网。

⚠️ 自动配冷开场（找集锦 → 逐 cue 翻译 → 写回 spec）已于 2026-10-12 随
模型通道整体移除：`attach()` 和它那套 CLI 不在了，这里只钉留下来的
机械半截——`select_window` / `parse_json3` / `needs_lead_in` 和只报清单
的 `main`，以及渲染那头 `check_lead_in` 对正式 spec 的合同。
"""

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


def test_parse_json3解析字幕事件成cue():
    import tempfile

    payload = {"events": [
        {"tStartMs": 70000, "dDurationMs": 3000,
         "segs": [{"utf8": "Championship point is over"}]},
        {"tStartMs": 74000, "dDurationMs": 4000,
         "segs": [{"utf8": "What a victory for Zverev"}]},
        {"tStartMs": 79000, "dDurationMs": 2000,
         "segs": [{"utf8": "[cheering]"}]},
    ]}
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "lead.json3"
        path.write_text(json.dumps(payload), encoding="utf-8")
        rows = lead.parse_json3(path)
    assert [(r["a"], r["b"], r["en"]) for r in rows] == [
        (70.0, 73.0, "Championship point is over"),
        (74.0, 78.0, "What a victory for Zverev"),
    ], "方括号音效行不算解说，不许进 cue"


def test_needs_lead_in只认没片头且没配过的正式spec():
    spec = _spec()
    assert lead.needs_lead_in({**spec, "opening": {"kind": "none"}})
    assert not lead.needs_lead_in({**spec, "opening": {"kind": "none"},
                                   "lead_in": {"url": "https://youtu.be/x"}})
    assert not lead.needs_lead_in({**spec, "opening": {"kind": "native"}})


def test_main只报待配清单不写spec(tmp_path, monkeypatch, capsys):
    """自动配字幕那一步没了之后，CLI 只许出声报清单——一个字节都不许写。"""
    specs = tmp_path / "interviews"
    specs.mkdir()
    base = {"opening": {"kind": "none"}, "requested_content_type": "on_court"}
    (specs / "pending-one.json").write_text(json.dumps({**base, "slug": "pending-one"}), "utf-8")
    (specs / "done-one.json").write_text(json.dumps(
        {**base, "slug": "done-one", "lead_in": {"url": "https://youtu.be/x"}}), "utf-8")
    (specs / "skip.draft.json").write_text(json.dumps({**base, "slug": "skip"}), "utf-8")
    monkeypatch.setattr(lead, "SPECS", specs)
    monkeypatch.setattr(sys, "argv", ["attach_interview_lead_in.py"])

    assert lead.main() == 0
    out = capsys.readouterr().out
    assert "待配冷开场：pending-one" in out
    assert "缺 lead_in 的正式 spec 1 条" in out
    assert "done-one" not in out and "skip" not in out


def test_正式片头verification必须与当前比赛逐字段一致():
    from build_interview_clip import check_lead_in

    spec = _spec()
    spec["lead_in"] = {
        "url": "https://youtu.be/highlight", "start": 70.0, "end": 78.0,
        "why": "同场赛点和获胜后解说",
        "subs": [{"a": 70.0, "b": 72.0, "en": "Match point", "zh": "赛点"}],
        # 2026-09-26 起新 spec 要带源片字幕事件，冷开场的每一句解说都得有字幕
        "source_captions": [[70.0, "Match point"]],
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
