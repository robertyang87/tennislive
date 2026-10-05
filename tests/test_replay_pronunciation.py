"""Replay pronunciation affects synthesis, never the displayed story or timing indices."""
import json
from pathlib import Path

import pytest

from tennislive.video.explainer import readable, speakable
from tennislive.video.pronounce import apply


ROOT = Path(__file__).resolve().parents[1]


def test_current_story_corrects_all_six_replay_occurrences_without_changing_display():
    spec = json.loads((ROOT / "specs/reels/sun-gauff-led-replay-story-2026.json").read_text())
    texts = [spec["cover"]["narration"]] + [s.get("narration", "") for s in spec["segments"]]
    assert sum(t.count("重打") for t in texts) == 6
    for original in texts:
        display = readable(original)
        spoken = speakable(original)
        assert len(spoken) == len(display)
        assert spoken.count("崇打") == display.count("重打")
        assert "重打" not in spoken
        assert readable(original) == display


@pytest.mark.parametrize("text", [
    "重要的比赛，重伤不是小事。", "肩负重担，仍然重视对手。",
    "负重打球。", "严重打击。", "双重打击。", "承重打孔。", "多重打击。",
    "加重打击。", "体重打破纪录。", "看重打球的态度。", "尊重打法。",
    "侧重打正手。", "器重打球天才。", "郑重打出承诺。", "隆重打响开幕赛。",
])
def test_replay_rule_does_not_change_other_meanings_or_cross_word_boundaries(text):
    assert apply(text, only=["chong-replay"]) == text


def test_replay_correction_changes_the_existing_audio_cache_key():
    from tennislive.video.tts import tts_content_key

    original = "重打一分，不能把赛事方的保障责任一笔勾销。"
    corrected = speakable(original)
    assert corrected != original
    setup = ("zh-CN-YunjianNeural", "+6%", "+0Hz", "", "", 0.0)
    assert tts_content_key(original, *setup) != tts_content_key(corrected, *setup)
