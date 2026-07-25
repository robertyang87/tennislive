import html

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
        "human",
        "mechanism",
        "today",
        "exception",
        "why",
    ]
    joined = " ".join(s.narration for s in segments)
    # Each beat must trace to the story's verified facts, not invented claims.
    assert "2004" in joined and "误判" in joined  # the incident
    assert "司线" in joined  # human
    assert "三角测量" in joined and "毫米" in joined  # mechanism
    assert "电子司线" in joined  # today
    assert "法网" in joined  # exception
    assert "红土" in joined and "球印" in joined  # why


def test_结尾要留一个问题给评论区():
    """A short explainer earns its reach in the comments, so it ends by asking."""
    segments = explainer_script(find_story_by_slug("hawkeye"))
    closer = segments[-1]
    assert closer.question, "末屏缺少互动提问"
    assert closer.question in _slide_html(0, closer, "7.25")
    assert "电子司线" in closer.narration  # 旁白也要问出口，不能只在画面上


def test_推送里的图必须是绝对地址否则微信收到空图():
    """The publisher only counts images whose src is already absolute.

    A repo-relative src is skipped silently: the message still sends, the log
    says the image channel was "none", and the push lands with nothing WeChat
    can resolve. That shipped once.
    """
    from pathlib import Path as _Path

    from tennislive.publish.pushplus import image_sources
    from tennislive.video.explainer import explainer_push_html

    import datetime as _dt

    story = find_story_by_slug("hawkeye")
    segments = explainer_script(story)
    from tennislive.video.explainer import explainer_xiaohongshu

    body = explainer_push_html(
        segments,
        _Path("output/2026-07-25/explainer/hawkeye"),
        date=_dt.date(2026, 7, 25),
        xhs_text=explainer_xiaohongshu(story, segments, "7.25"),
    )
    found = image_sources(body)
    assert len(found) == len(segments), "推送里的图没有被识别为可投递图片"
    assert all(u.startswith("https://cdn.jsdelivr.net/") for u in found)
    assert all("@main/" in u for u in found)  # so pin_asset_revision can pin it
    # ...and it uses the knowledge post's layout, not a second one.
    assert "第1张未显示？点此打开原图" in body
    assert "分别复制标题 / 正文 / 置顶评论" in body


def test_文案本身要在推送里能长按复制():
    """The copy button points at a Pages URL, which can 404 mid-deploy.

    When it does, the push carries a caption nobody can lift off the phone —
    which is the whole point of sending it. So the text itself has to travel
    inside the message, not only behind a link.
    """
    import datetime as _dt
    from pathlib import Path as _Path

    from tennislive.video.explainer import explainer_push_html, explainer_xiaohongshu

    story = find_story_by_slug("hawkeye")
    segments = explainer_script(story)
    xhs = explainer_xiaohongshu(story, segments, "7.25")
    body = explainer_push_html(
        segments,
        _Path("output/2026-07-25/explainer/hawkeye"),
        date=_dt.date(2026, 7, 25),
        xhs_text=xhs,
    )
    assert "长按" in body, "推送里没有告诉用户怎么复制"
    # every non-empty line of the caption must actually be in the message
    for line in (ln.strip() for ln in xhs.splitlines()):
        if line:
            assert html.escape(line) in body, f"文案这行没进推送：{line}"
    assert "图片长按保存" in body
    assert "▶ 打开 9:16 成片" in body


def test_每屏都有提炼要点配合旁白():
    # 画面不能只有大标题：要点是给眼睛看的骨架，旁白是给耳朵的全文。
    for story_slug in ("hawkeye",):
        for seg in explainer_script(find_story_by_slug(story_slug)):
            assert 2 <= len(seg.points) <= 3, f"{seg.kind} 要点数量不对"
            assert all(p.strip() for p in seg.points)
            # 要点是提炼，不是把旁白整句搬上去。
            # 要点是提炼；唯一放宽的是点名时间/地点/人物的那一行。
            assert all(len(p) <= 30 for p in seg.points), f"{seg.kind} 要点太长"
            doc = _slide_html(0, seg, "7.25")
            for point in seg.points:
                assert point in doc


def test_没有实拍的时刻不拿近似照片顶替():
    """2004's quarter-final has no licensable frame, so no beat claims to show it.

    Every photograph in the deck depicts what its own beat is about; the 2004
    incident is carried by narration and on-screen text, never by a picture
    standing in for a match it isn't.
    """
    segments = explainer_script(find_story_by_slug("hawkeye"))
    opener = segments[0]
    # The opener's photo is the line judges it describes — a real frame whose
    # own date and place match what we say about it.
    assert "us_open_court" in opener.image
    assert "2004" in opener.narration  # the incident is told, not depicted
    assert any("2004" in p for p in opener.points)


def test_法网那屏不能配温网的草地():
    """The exception beat is about Roland-Garros; a grass frame would lie.

    This is the concrete mistake that shipped once: the beat said "only the
    French Open still keeps human line judges" over a Wimbledon Centre Court
    photo. Each beat's hero must match what the beat claims.
    """
    segments = explainer_script(find_story_by_slug("hawkeye"))
    beats = {s.kind: s for s in segments}

    exception = beats["exception"]
    assert "rg2026" in exception.image  # this year's Roland-Garros
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
        # cover for portrait frames; contain for wide ones, whose edges
        # carry the subject and must not be cropped away.
        assert "data:image" in doc
        assert "background-size:cover" in doc or "background-size:contain" in doc
        # Provenance is kept in the data for records, never painted on the frame.
        assert seg.credit
        assert seg.credit not in doc


def test_every_story_has_a_renderable_script():
    # No story should crash the script builder (durable guard for auto use).
    for story in STORIES:
        segments = explainer_script(story)
        assert len(segments) >= 3
        assert all(s.narration.strip() for s in segments)
        # Never a text-only beat: a real photo, or an original diagram.
        assert all(s.image or s.diagram or s.kind == "mechanism" for s in segments)
