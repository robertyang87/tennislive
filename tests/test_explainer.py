from tennislive.render.tournament_story import STORIES, find_story_by_slug
from tennislive.video.explainer import (
    H,
    VIDEO_H,
    VIDEO_W,
    W,
    _REPO,
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
    # No image -> the schematic diagram is the hero (never a text-only slide).
    seg = ExplainerSegment("mechanism", "技术原理", "起<点>", "旁白仅配音")
    doc = _slide_html(0, seg, "7.25")
    assert "① 技术原理" in doc
    assert "起&lt;点&gt;" in doc and "<点>" not in doc
    assert "<svg" in doc and "三角测量" in doc  # original schematic, not text-only
    assert "width:1080px;height:1440px" in doc  # the card is 3:4


def test_hawkeye_beats_are_image_first_not_text():
    story = find_story_by_slug("hawkeye")
    segments = explainer_script(story)
    # cause & today carry a real verified photo; mechanism uses the schematic.
    assert segments[0].image and (_REPO / segments[0].image).is_file()
    assert segments[2].image and (_REPO / segments[2].image).is_file()
    assert segments[1].image == ""  # mechanism -> diagram
    # The photo beats embed the real image (image-first), not just text.
    cause_doc = _slide_html(0, segments[0], "7.25")
    assert "data:image" in cause_doc and "background-size:cover" in cause_doc
    mech_doc = _slide_html(1, segments[1], "7.25")
    assert "<svg" in mech_doc


def test_every_story_has_a_renderable_three_beat_script():
    # No story should crash the script builder (durable guard for auto use).
    for story in STORIES:
        segments = explainer_script(story)
        assert len(segments) == 3
        assert all(s.narration.strip() for s in segments)
