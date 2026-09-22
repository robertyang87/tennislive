import copy
import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from story_visual_policy import review_story_visuals


def story(*segments):
    return {"cover": {"eyebrow": "网球有故事"},
            "source_url": "https://example.com/fixture.mp4",
            "segments": list(segments)}


def codes(spec):
    return {item["code"] for item in review_story_visuals(spec)["errors"]}


def test_real_footage_with_context_card_preserves_input():
    spec = story({"start": 0, "end": 5, "narration": "走进球场"},
                 {"title_card": "杭州", "narration": "时间回到那一年", "visual_role": "context"},
                 {"start": 8, "end": 13, "visual_role": "ending"})
    original = copy.deepcopy(spec)
    assert not codes(spec)
    assert spec == original
    assert review_story_visuals(spec)["visual_review"] == "pending"


@pytest.mark.parametrize("segments,expected", [
    ([{"title_card": "第一张"}, {"title_card": "第二张"}, {"start": 0, "end": 3}], "consecutive_title_cards"),
    ([{"start": 0, "end": 3}, {"title_card": "总结"}], "title_only_ending"),
    ([{"title_card": "他赢了！", "narration": "他赢了。"}, {"start": 0, "end": 3}], "duplicate_text"),
    ([{"title_card": "练习", "visual_role": "narrative"}, {"start": 0, "end": 3}], "ordinary_text_card"),
])
def test_bad_patterns_and_local_documented_exceptions(segments, expected):
    spec = story(*segments)
    assert expected in codes(spec)
    affected = [x["segment"] for x in review_story_visuals(spec)["errors"]]
    for index in affected:
        spec["segments"][index - 1]["visual_exception"] = "原话须与前页证据对照，来源见 _why；合并会影响可读性"
    result = review_story_visuals(spec)
    assert not result["errors"]
    assert result["exceptions"]
    assert result["visual_review"] == "pending"
    assert result["outcome_validation"] == "not_measured"


@pytest.mark.parametrize("role", [[], {}, True, "bogus"])
def test_bad_role_is_reported_not_crashed(role):
    assert "invalid_role" in codes(story({"visual_role": role}))


def test_exception_does_not_suppress_other_segments():
    spec = story({"title_card": "A", "visual_exception": "有据的引语"},
                 {"title_card": "B"})
    assert "consecutive_title_cards" in codes(spec)
    spec["segments"][1]["visual_exception"] = True
    assert "invalid_exception" in codes(spec)
    assert "title_only_ending" in codes(spec)


def test_images_are_not_mistaken_for_verified_photos():
    result = review_story_visuals(story({"image": "unknown.png"}))
    assert result["segments"][0]["kind"] == "image_unreviewed"
    assert result["visual_review"] == "pending"


@pytest.mark.parametrize("column", ["赛场之上", "赛后开麦", "开球之前"])
def test_other_columns_unchanged(column):
    spec = story({"title_card": "A"}, {"title_card": "B"})
    spec["cover"]["eyebrow"] = column
    assert not codes(spec)
    assert not review_story_visuals(spec)["applicable"]


def test_real_validation_entry_blocks_before_media_download():
    module_spec = importlib.util.spec_from_file_location("story_reel_entry", TOOLS / "build_match_reel.py")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    with pytest.raises(module.ReelError, match="故事视觉检查"):
        module.validate_spec(story({"title_card": "结尾"}))
