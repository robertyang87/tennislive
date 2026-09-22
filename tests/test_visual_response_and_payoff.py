import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import analyze_reel_visuals as visual


def test_reasoning_only_response_is_not_visual_evidence(monkeypatch):
    monkeypatch.setattr(visual, "model_instructions", lambda _: "")
    response = {"choices": [{"finish_reason": "length", "message": {
        "reasoning_content": '{"cold_open": {"confidence": 1}}'}}]}
    monkeypatch.setattr(visual.urllib.request, "urlopen",
                        lambda *a, **kw: io.BytesIO(json.dumps(response).encode()))
    with pytest.raises(ValueError, match="no final content.*length"):
        visual.ask_minimax({}, [], None, {"duration": 305}, "test-key")


def test_reviewed_silent_winning_point_survives_aftermath_cold_open():
    draft = {"segments": [
        {"start": 197.08, "end": 251.48, "narration": "末盘走势"},
        {"start": 251.48, "end": 282.88, "narration": "",
         "_preserve_source_window": True}]}
    report = {
        "cold_open": {"start": 262.32, "end": 276, "reason": "赛后原声"},
        "ending": {"start": 260, "end": 282, "reason": "赛后反应"}}
    result = visual.apply_story(draft, report, [(264, "She wins.")],
                                [("She wins.", "她赢了。")])
    assert result["segments"][-1]["start"] == 251.48
    assert result["segments"][-1]["end"] == 282.88
    assert result["_visual_evidence"]["ending"]["start"] == 260
