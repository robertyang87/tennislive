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


def test_hawkeye_beats_are_grounded_in_verified_facts():
    story = find_story_by_slug("hawkeye")
    segments = explainer_script(story)

    assert [s.kind for s in segments] == [
        "cause",
        "human",
        "mechanism",
        "today",
        "exception",
        "why",
    ]
    joined = " ".join(s.narration for s in segments)
    # Each beat must trace to the story's verified facts, not invented claims.
    assert "2004" in joined and "误判" in joined  # cause
    assert "司线" in joined  # human
    assert "三角测量" in joined and "毫米" in joined  # mechanism
    assert "电子司线" in joined  # today
    assert "法网" in joined  # exception
    assert "红土" in joined and "球印" in joined  # why


def test_每屏都有提炼要点配合旁白():
    # 画面不能只有大标题：要点是给眼睛看的骨架，旁白是给耳朵的全文。
    for story_slug in ("hawkeye",):
        for seg in explainer_script(find_story_by_slug(story_slug)):
            assert 2 <= len(seg.points) <= 3, f"{seg.kind} 要点数量不对"
            assert all(p.strip() for p in seg.points)
            # 要点是提炼，不是把旁白整句搬上去。
            assert all(len(p) <= 24 for p in seg.points), f"{seg.kind} 要点太长"
            doc = _slide_html(0, seg, "7.25")
            for point in seg.points:
                assert point in doc


def test_法网那屏不能配温网的草地():
    """The exception beat is about Roland-Garros; a grass frame would lie.

    This is the concrete mistake that shipped once: the beat said "only the
    French Open still keeps human line judges" over a Wimbledon Centre Court
    photo. Each beat's hero must match what the beat claims.
    """
    segments = explainer_script(find_story_by_slug("hawkeye"))
    beats = {s.kind: s for s in segments}

    exception = beats["exception"]
    assert "chatrier" in exception.image  # Court Philippe Chatrier
    assert "today.jpg" not in exception.image  # never the Wimbledon frame
    # ...and the Wimbledon frame stays on the beat it actually illustrates:
    # the three Slams that already converted.
    assert "today.jpg" in beats["today"].image


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


def test_photo_beats_embed_a_real_file_and_carry_no_burned_in_credit():
    segments = explainer_script(find_story_by_slug("hawkeye"))
    photo_beats = [s for s in segments if s.image]
    assert len(photo_beats) >= 3  # image-first: most beats carry a real photo
    for seg in photo_beats:
        assert (_REPO / seg.image).is_file(), f"{seg.image} 不存在"
        doc = _slide_html(0, seg, "7.25")
        assert "data:image" in doc and "background-size:cover" in doc
        # Provenance is kept in the data for records, never painted on the frame.
        assert seg.credit
        assert seg.credit not in doc


def test_every_story_has_a_renderable_script():
    # No story should crash the script builder (durable guard for auto use).
    for story in STORIES:
        segments = explainer_script(story)
        assert len(segments) >= 3
        assert all(s.narration.strip() for s in segments)
        # Never a text-only beat: a real photo, or the schematic.
        assert all(s.image or s.kind == "mechanism" for s in segments)
