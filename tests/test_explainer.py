from tennislive.render.tournament_story import STORIES, find_story_by_slug
from tennislive.video.explainer import (
    H,
    VIDEO_H,
    VIDEO_W,
    W,
    ExplainerSegment,
    _slide_html,
    explainer_script,
)


def test_hawkeye_script_has_three_grounded_beats():
    story = find_story_by_slug("hawkeye")
    segments = explainer_script(story)

    assert [s.kind for s in segments] == ["cause", "mechanism", "today"]
    assert [s.label for s in segments] == ["前因后果", "技术原理", "当今现状"]
    joined = " ".join(s.narration for s in segments)
    # Each beat must trace to the story's verified facts, not invented claims.
    assert "2004" in joined and "误判" in joined  # cause
    assert "三角测量" in joined and "毫米" in joined  # mechanism
    assert "法网" in joined and "电子司线" in joined  # today


def test_generic_script_uses_story_moments_and_facts_verbatim():
    story = find_story_by_slug("longest-match")  # has no hand-authored script
    segments = explainer_script(story)

    assert len(segments) == 3
    # mechanism / today are the story's verified facts verbatim — nothing added.
    assert segments[1].narration == story.facts[0]
    assert segments[2].narration == story.facts[-1]
    # cause is assembled from the first moment (headline + detail), no invention.
    assert story.moments[0].headline in segments[0].narration
    assert story.moments[0].detail in segments[0].narration


def test_card_stays_3x4_while_video_canvas_is_9x16():
    # The image/card keeps the brand 3:4; only the video canvas is 9:16.
    assert (W, H) == (1080, 1440)  # card / image 3:4 (unchanged)
    assert (VIDEO_W, VIDEO_H) == (1080, 1920)  # video 9:16
    seg = ExplainerSegment("cause", "前因后果", "起<点>", "旁白 & 文本")
    doc = _slide_html(0, seg, "7.25")
    assert "① 前因后果" in doc
    assert "起&lt;点&gt;" in doc and "<点>" not in doc
    assert "旁白 &amp; 文本" in doc
    assert "width:1080px;height:1440px" in doc  # the card is 3:4


def test_every_story_has_a_renderable_three_beat_script():
    # No story should crash the script builder (durable guard for auto use).
    for story in STORIES:
        segments = explainer_script(story)
        assert len(segments) == 3
        assert all(s.narration.strip() for s in segments)
