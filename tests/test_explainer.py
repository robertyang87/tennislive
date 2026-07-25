import html

from tennislive.render.tournament_story import STORIES, find_story_by_slug
from tennislive.video.explainer import (
    H,
    VIDEO_H,
    VIDEO_W,
    W,
    _REPO,
    _SCRIPTS,
    ExplainerSegment,
    _slide_html,
    explainer_script,
)

# Every hand-authored deck, so a new topic inherits the rules the last one
# was fixed into rather than only being checked the day it ships.
_SCRIPTED = tuple(_SCRIPTS)


def _beats(slug):
    """The content beats, without the opening question card."""
    return [s for s in explainer_script(find_story_by_slug(slug)) if s.kind != "cover"]


def test_hawkeye_beats_are_grounded_in_verified_facts():
    story = find_story_by_slug("hawkeye")
    segments = _beats("hawkeye")

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
    assert closer.question in _slide_html(0, closer)
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
    # ...and the body exactly once. Rendering a pretty copy plus a copyable
    # copy sent the whole caption twice, which reads as a bug on the phone.
    # (The title is exempt — it is also the headline and every image's alt.)
    for line in (ln.strip() for ln in xhs.splitlines()[1:]):
        if len(line) > 8 and not line.startswith("#"):
            assert body.count(html.escape(line)) == 1, f"文案这行重复出现：{line}"
    assert "图片长按保存" in body
    assert "▶ 打开 9:16 成片" in body


def test_知识卡右上角不写日期():
    """Knowledge explainers are evergreen — a date stamps a shelf life on them.

    The daily digest cards want a date; these don't. Posting one in October
    should not show a July date in the corner.
    """
    seg = explainer_script(find_story_by_slug("hawkeye"))[0]
    doc = _slide_html(0, seg)
    assert "网球时差 · 网球有故事" in doc  # the brand line stays
    assert 'class="date"' not in doc
    assert "7.25" not in doc and "2026-" not in doc


def test_每屏都有提炼要点配合旁白():
    # 画面不能只有大标题：要点是给眼睛看的骨架，旁白是给耳朵的全文。
    for story_slug in _SCRIPTED:
        for seg in _beats(story_slug):
            assert 2 <= len(seg.points) <= 3, f"{seg.kind} 要点数量不对"
            assert all(p.strip() for p in seg.points)
            # 要点是提炼，不是把旁白整句搬上去。
            # 要点是提炼；唯一放宽的是点名时间/地点/人物的那一行。
            assert all(len(p) <= 30 for p in seg.points), f"{seg.kind} 要点太长"
            doc = _slide_html(0, seg)
            for point in seg.points:
                assert point in doc


def test_没有实拍的时刻不拿近似照片顶替():
    """2004's quarter-final has no licensable frame, so no beat claims to show it.

    Every photograph in the deck depicts what its own beat is about; the 2004
    incident is carried by narration and on-screen text, never by a picture
    standing in for a match it isn't.
    """
    opener = _beats("hawkeye")[0]
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
    beats = {s.kind: s for s in _beats("hawkeye")}

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
    doc = _slide_html(1, seg)  # index 1 = first beat; index 0 is the cover
    assert "① 技术原理" in doc
    assert "起&lt;点&gt;" in doc and "<点>" not in doc
    assert "<svg" in doc and "三角测量" in doc  # original schematic, not text-only
    assert "width:1080px;height:1440px" in doc  # the card is 3:4


def test_photo_beats_embed_a_real_file_and_carry_no_burned_in_credit():
    segments = [s for slug in _SCRIPTED for s in _beats(slug)]
    photo_beats = [s for s in segments if s.image]
    assert len(photo_beats) >= 3  # image-first: most beats carry a real photo
    for seg in photo_beats:
        assert (_REPO / seg.image).is_file(), f"{seg.image} 不存在"
        doc = _slide_html(0, seg)
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


def test_每个成稿选题都要有可查证的图片出处():
    """A photo without a recorded source cannot be checked later.

    The frame is chosen from what the source says about it, so that sentence
    has to survive next to the file — credits.json is where it lives, and the
    beat's own credit string is what shows up in review.
    """
    import json
    from pathlib import Path

    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            if not seg.image:
                continue
            assert seg.credit, f"{slug}/{seg.kind} 没有记出处"
            book = _REPO / Path(seg.image).parent / "credits.json"
            assert book.is_file(), f"{book} 缺失"
            recorded = json.loads(book.read_text(encoding="utf-8"))
            name = Path(seg.image).name
            # user-supplied assets are recorded too, just without a Commons page
            assert name in recorded, f"{name} 未登记在 credits.json"


def test_黄球那条的画面要对得上它讲的年份和地点():
    """The white-ball beat shows white balls; the Wimbledon beat shows 1986.

    Same failure mode as the Roland-Garros/Wimbledon mix-up: a beat about one
    place or era illustrated by a frame from another. Pin the two that carry
    the argument.
    """
    beats = {s.kind: s for s in _beats("yellow-ball")}
    assert [*beats] == ["white", "tv", "switch", "exception", "color"]
    assert "white_era" in beats["white"].image  # actual white balls, not a yellow one
    assert "wimbledon" in beats["exception"].image
    assert "1986" in beats["exception"].credit  # the year the beat is about
    assert any("1986" in p for p in beats["exception"].points)
    assert beats["color"].question  # ends by asking, like every deck


def test_文案的开场和标签属于它自己的选题():
    """The hook and hashtags used to be literals written for Hawk-Eye.

    The second deck exposed it: a post about why the ball is yellow opened
    with a line about line calls and tagged itself #鹰眼 #电子司线 #法网.
    Each topic carries its own, and no topic borrows another's.
    """
    from tennislive.video.explainer import explainer_xiaohongshu

    captions = {
        slug: explainer_xiaohongshu(
            find_story_by_slug(slug), explainer_script(find_story_by_slug(slug)), "7.25"
        )
        for slug in _SCRIPTED
    }
    for slug, text in captions.items():
        head = text.split("\n\n")[1]  # the hook, right under the headline
        tags = text.rsplit("\n\n", 1)[-1].split()
        assert 3 <= len(tags) <= 5, f"{slug} 标签数量应为 3-5 个"
        assert "#网球时差" in tags
        for other, other_text in captions.items():
            if other == slug:
                continue
            assert head != other_text.split("\n\n")[1], f"{slug} 用了 {other} 的开场"
            assert set(tags) != set(other_text.rsplit("\n\n", 1)[-1].split()), (
                f"{slug} 和 {other} 的标签完全一样"
            )


def test_文案标题带上品牌语且不超小红书上限():
    """The headline is 日期 + 网球有故事 + 选题, and it has to fit.

    Xiaohongshu truncates titles past 20 (full-width counts 1, half-width
    0.5), and a truncated headline loses the topic — the part that makes
    someone tap. Check every deck, not just the short ones.
    """
    from tennislive.render.xiaohongshu import xhs_title_len
    from tennislive.video.explainer import explainer_xiaohongshu

    for slug in _SCRIPTED:
        story = find_story_by_slug(slug)
        head = explainer_xiaohongshu(story, explainer_script(story), "7.26").splitlines()[0]
        assert head.startswith("🎾7.26 网球有故事｜"), f"{slug} 标题格式不对：{head}"
        assert story.title in head
        assert xhs_title_len(head) <= 20, f"{slug} 标题 {xhs_title_len(head)} 字，超小红书上限"


def test_每条片子都以问题开场():
    """Nobody watches past three seconds if they cannot tell what this is about.

    Opening on beat one made the viewer work the subject out for themselves.
    Every deck now leads with the question it answers - on screen, in the
    narration, and without a beat number, because it is not a beat.
    """
    for slug in _SCRIPTED:
        segments = explainer_script(find_story_by_slug(slug))
        cover = segments[0]
        assert cover.kind == "cover", f"{slug} 第一屏不是开场问题卡"
        assert cover.title.endswith("？"), f"{slug} 开场没有问出一个问题：{cover.title}"
        assert len(cover.title) <= 16, f"{slug} 开场问题太长：{cover.title}"
        assert cover.title[:6] in cover.narration or "？" in cover.narration
        assert not cover.points  # the cover states the question, nothing else

        doc = _slide_html(0, cover)
        assert cover.title in doc
        assert "① " not in doc  # the cover carries no beat number
        assert "网球有故事" in doc
        # ...and the first real beat still starts the count at one.
        assert "① " in _slide_html(1, segments[1])


def test_每屏标题不能把自己的标签再说一遍():
    """The caption prints "标签：标题", so a title starting with its own label
    reads as a stutter: "4️⃣ 赛事方：赛事方：这已经不是个案". That shipped once.
    """
    from tennislive.video.explainer import explainer_xiaohongshu

    for slug in _SCRIPTED:
        story = find_story_by_slug(slug)
        for seg in _beats(slug):
            assert seg.label not in seg.title, (
                f"{slug}/{seg.kind} 标题里重复了标签「{seg.label}」：{seg.title}"
            )
        caption = explainer_xiaohongshu(story, explainer_script(story), "7.26")
        for line in caption.splitlines():
            if "：" in line and line[:1].isdigit() is False and "️⃣" in line:
                head = line.split("：", 1)[0].split(" ", 1)[-1]
                assert line.count(f"{head}：") == 1, f"{slug} 文案里标签重复：{line}"
