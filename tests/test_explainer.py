import html
import json
import re
import types
from pathlib import Path
from unittest import mock

import pytest

from tennislive.render.tournament_story import STORIES, find_story_by_slug
from tennislive.video.explainer import (
    H,
    VIDEO_H,
    VIDEO_W,
    W,
    _REPO,
    _SCRIPTS,
    _assert_photo_integrity,
    ExplainerSegment,
    ExplainerVideoError,
    _slide_html,
    explainer_script,
)

# Every hand-authored deck, so a new topic inherits the rules the last one
# was fixed into rather than only being checked the day it ships.
_SCRIPTED = tuple(_SCRIPTS)


def _beats(slug):
    """The content beats, without the opening question card."""
    return [s for s in explainer_script(find_story_by_slug(slug)) if s.kind != "cover"]


def test_right_coco澄清把原话网友推断和旧互动分开():
    """澄清不能靠抹掉不顺耳的旧事实，也不能把‘没搜到’夸成绝对不存在。"""
    from tennislive.video.explainer import _OPENINGS

    story = find_story_by_slug("gauff-right-coco")
    assert story is not None
    beats = _beats(story.slug)
    joined = "".join(s.narration for s in beats)

    # 现场原话和网友加进去的对象必须明确分层。
    assert "全段她没有提克耶高斯" in joined
    assert "网友解释，不是高芙本人的原话" in joined
    assert "影射还没证据" in beats[1].title

    # 2023 的旧语境早于 2026 事件，是排除“只能在影射本周新闻”的关键证据。
    assert "二〇二三年美网" in joined
    assert "发生前三年" in joined
    assert "八月十九日" in joined and "八月二十二日" in joined

    # 社媒结论只说公开范围内未发现；受限内容不冒充查过。
    assert "未发现可公开核实的直接表态" in joined
    assert "Stories 和点赞受登录限制" in joined

    # 不许为了澄清改写成“两人毫无交集”。旧互动照实交代，再与本次事件切开。
    assert "过去确实有职业圈互动" in joined
    assert "不能为了澄清" in joined
    assert "过去有过互动，同样不能证明她评价了这次事件" in joined

    # 封面也把联想归给评论区，不能把待核查的联系写成高芙主动发问。
    assert _OPENINGS[story.slug]["question"].startswith("评论区")
    assert "她为何影射" not in _OPENINGS[story.slug]["question"]


def test_right_coco片头复用的是已校正三比四采访段():
    """用户点名要复用采访画面；不能退成静态截图，也不能再走镜像转载源。"""
    from tennislive.video.explainer import _OPENINGS

    spec = _OPENINGS["gauff-right-coco"]
    assert spec["canvas"] == "3:4"
    assert "interview-gauff-kostyuk-cincinnati-2026-qf" in spec["intro_url"]
    assert spec["intro_start"] == 82.0
    assert spec["intro_end"] == 101.0
    assert spec["intro_end"] - spec["intro_start"] == 19.0
    # 短段只在渲染时从既有 Release 切，仓库里不再复制第二份 mp4。
    assert "intro" not in spec
    assert not (_REPO / "assets" / "explainer" / "gauff-right-coco"
                / "intro_right_coco.mp4").exists()


def test_right_coco只保留获准的双关评论正文():
    """用户明确撤回 IMG_4121：成片和资产目录都不能再带那张截图。"""
    from PIL import Image

    root = _REPO / "assets" / "explainer" / "gauff-right-coco"
    with Image.open(root / "comment_double_meaning.jpg") as im:
        assert im.size == (970, 65)
    assert not (root / "comment_kyrgios_claim.jpg").exists()

    credits = json.loads((root / "credits.json").read_text(encoding="utf-8"))
    assert "仅裁相关正文" in credits["comment_double_meaning.jpg"]["description"] or (
        "只保留" in credits["comment_double_meaning.jpg"]["description"]
    )
    assert "comment_kyrgios_claim.jpg" not in credits
    first = _beats("gauff-right-coco")[0]
    assert first.image == "assets/reel/gauff-kostyuk-cincinnati-2026-qf.jpg"


def test_科斯秋克冠军试金石只讲法网起连续四次且四张都是当站捧杯照():
    """传播钩子可以狠，但样本范围、四次赛果与视觉证据不能被标题吞掉。"""
    from tennislive.video.explainer import _OPENINGS

    story = find_story_by_slug("kostyuk-champion-test")
    assert story is not None
    beats = _beats(story.slug)
    assert len(beats) == 4
    assert [s.kind for s in beats] == ["paris", "london", "toronto", "cincinnati"]
    assert all(s.image for s in beats)
    assert all("捧杯" in s.credit for s in beats)

    joined = "".join(s.narration for s in beats)
    for score in ("六比一、六比三", "六比四、六比四", "三比六、六比一、六比二", "六比二、六比二"):
        assert score in joined
    assert "澳网首轮击败她的雅克莫并没有夺冠" in joined
    assert "从法网开始连续四次" in joined
    assert beats[-1].question == "下一次，还会应验吗？"
    assert _OPENINGS[story.slug]["question"] == "击败科斯秋克的人，都夺冠？"


def test_解说片照片不能用大块纯色画布伪装成已完整加载(tmp_path):
    """浏览器能解码不等于照片完整；大块灰底必须在渲染前被硬闸拦住。"""
    from PIL import Image

    broken = tmp_path / "half-loaded.jpg"
    image = Image.new("RGB", (600, 800), (128, 128, 128))
    for y in range(320):
        for x in range(600):
            image.putpixel((x, y), ((x + y) % 255, (x * 2) % 255, y % 255))
    image.save(broken, quality=90)

    with pytest.raises(ExplainerVideoError, match="纯色|加载|裁切"):
        _assert_photo_integrity(broken)

    fixed = (
        _REPO
        / "assets"
        / "explainer"
        / "kostyuk-champion-test"
        / "andreeva_roland_garros_2026_trophy.jpg"
    )
    _assert_photo_integrity(fixed)


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
    # 主机名从配置读，不写死：镜像是可换的（见 tennislive/cdn.py）。
    # 这条要盯的是「绝对地址、走 jsDelivr」，不是「用的哪个入口」。
    from tennislive.cdn import jsdelivr_host

    assert all(u.startswith(f"https://{jsdelivr_host()}/") for u in found)
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
    # No photo -> the beat's own schematic is the hero (never a text-only slide).
    # 这一屏原来不带 diagram，靠渲染时的兜底补上鹰眼那张图，断言写的也是
    # 「三角测量」——等于把那个 bug 当成期望行为记了下来。现在显式给一张。
    seg = ExplainerSegment("mechanism", "技术原理", "起<点>", "旁白仅配音",
                           diagram='<svg id="schematic"></svg>')
    doc = _slide_html(1, seg)  # index 1 = first beat; index 0 is the cover
    assert "① 技术原理" in doc
    assert "起&lt;点&gt;" in doc and "<点>" not in doc
    assert "<svg" in doc and 'id="schematic"' in doc  # its own, not text-only
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
        # 这里原来给 `kind == "mechanism"` 开了个口子，靠渲染时的兜底补图——
        # 而那个兜底摆的是**鹰眼**那张示意图。口子和兜底一起去掉了，见
        # `test_缺图的那一屏要报错而不是套用别的选题的图`。
        assert all(s.image or s.diagram for s in segments), (
            f"{story.slug} 有既没图也没示意图的一屏"
        )


def test_一屏不许既配图又画示意图否则示意图被静默丢掉():
    """`_slide_html` 是**照片优先**：有 image 就走照片那一支，diagram 一眼都不看。

    起草瓦林卡那条时中过：`champion` 那一屏我既挂了 2016 年的捧杯照，又挂了
    「三次大满贯决赛」那张表——渲出来只有照片，那张表**一次都没露过面**，
    而且渲染成功、全量测试全绿、`_slide_html` 一个字都不报。写它花的力气和
    它产生的效果，中间隔着一个谁也看不见的 if。

    和「缺图的那一屏」正好是一对：那条拦的是「什么都没给，它悄悄套别人的图」，
    这条拦的是「给了两样，它悄悄扔掉一样」。两种都是**兜底出事的时候不吭声**。

    修法不是让渲染器去合成两者（一屏挤不下一张照片加一张表），是在这儿拦住：
    想两样都要，就拆成两屏。
    """
    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            assert not (seg.image and seg.diagram), (
                f"{slug}/{seg.kind} 同时挂了配图和示意图，而渲染器照片优先，"
                f"这张示意图渲不出来：{seg.title}\n"
                "要么去掉一样，要么拆成两屏。"
            )

    # 判据自己的判据：渲染器**确实**照片优先，所以上面那条不是杞人忧天。
    # 这一半哪天不成立了（比如渲染器改成两样都画），上面那条就该跟着撤。
    from tennislive.video.explainer import ExplainerSegment

    both = ExplainerSegment(
        kind="cause", label="试", title="两样都给",
        narration="随便一句",
        image="assets/explainer/hawkeye/ball_mark.jpg",
        diagram='<svg id="mine"></svg>',
    )
    doc = _slide_html(0, both)
    assert 'id="mine"' not in doc, "渲染器已经会画示意图了，上面那条判据可以撤了"


def test_缺图的那一屏要报错而不是套用别的选题的图():
    """一屏既没配图也没画示意图时，渲染器原来会**悄悄**摆上鹰眼那张示意图。

    起草外卡那条时中过：封面渲出来是一张「8–12 台摄像机 · 三角测量落点」的网球场
    测线图，和外卡毫无关系，而且一声不吭。已发的十四条每屏都自带图或示意图，
    所以这个兜底从来没在产物里露过面——正因如此也没人发现它指着别的选题。

    和「补位的静音盖住真音轨」「-filter_complex 不打标签就静默失效」同一种毛病：
    **兜底出事的时候不吭声。** 缺图就停下来说缺图。
    """
    from tennislive.video.explainer import ExplainerSegment

    naked = ExplainerSegment(
        kind="cause", label="试", title="既没图也没示意图",
        narration="随便一句", image="", diagram="",
    )

    with pytest.raises(ValueError, match="既没有 image 也没有 diagram"):
        _slide_html(0, naked)

    # 有示意图就该照常渲，而且渲的是它自己那张，不是鹰眼那张。
    ok = ExplainerSegment(
        kind="cause", label="试", title="自带示意图",
        narration="随便一句", image="", diagram='<svg id="mine"></svg>',
    )
    doc = _slide_html(0, ok)
    assert 'id="mine"' in doc
    assert "三角测量落点" not in doc


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
    """The headline is 日期 + 栏目名 + 选题, and it has to fit.

    The column is per deck now — knowledge decks run under 网球有故事, a match
    preview under its own name — so the check follows the deck rather than
    asserting one string for all of them.

    Xiaohongshu truncates titles past 20 (full-width counts 1, half-width
    0.5), and a truncated headline loses the topic — the part that makes
    someone tap. Check every deck, not just the short ones.
    """
    from tennislive.render.xiaohongshu import xhs_title_len
    from tennislive.video.explainer import explainer_column, explainer_xiaohongshu

    for slug in _SCRIPTED:
        story = find_story_by_slug(slug)
        head = explainer_xiaohongshu(story, explainer_script(story), "7.26").splitlines()[0]
        column = explainer_column(slug)
        assert head.startswith(f"🎾7.26 {column}｜"), f"{slug} 标题格式不对：{head}"
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

        from tennislive.video.explainer import explainer_column

        doc = _slide_html(0, cover, column=explainer_column(slug))
        assert cover.title in doc
        assert "① " not in doc  # the cover carries no beat number
        assert explainer_column(slug) in doc
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


def test_配音把比分读成几比几而不是几杠几():
    """"5-1" is a score, and edge-tts read the hyphen out loud: 五杠一.

    Fixed at synthesis rather than in each script, so the slides keep the
    compact "6-2 5-7 6-3" and only the audio changes. Year ranges have to
    survive the same pass — "2016-2026 共十届" is not a score.
    """
    from tennislive.video.explainer import speakable

    # 「比」两边不加空格：TTS 读起来一样，屏幕上「7 比 5」松松垮垮全是机器味
    # （medvedev-damm 那条已发成片的比分板字幕就是这么印的）。
    assert speakable("辛纳 6-3、6-2、5-1 领先") == "辛纳 6比3、6比2、5比1 领先"
    assert speakable("70-68 拿下第五盘") == "70比68 拿下第五盘"
    assert speakable("2016-2026 共十届，2020 年停办") == "2016-2026 共十届，2020 年停办"

    # No deck may reach the voice with a bare score hyphen still in it.
    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            spoken = speakable(seg.narration)
            assert not re.search(r"(?<!\d)\d{1,3}\s*[-–—−]\s*\d{1,3}(?!\d)", spoken), (
                f"{slug}/{seg.kind} 旁白里还有会被读成「杠」的比分：{spoken[:60]}"
            )


def test_配音把挑球的挑读成一声():
    """挑球 is tiāo — to pick one out. The voice read it tiǎo, as in 挑战.

    edge-tts takes no pronunciation hints, so the spoken copy swaps in 选,
    which means the same thing and has one reading. On-screen text keeps 挑.
    挑战 is genuinely tiǎo and must survive untouched — including the
    Gentlemen's 挑战杯, which would otherwise become 选战杯.
    """
    from tennislive.video.explainer import speakable

    assert speakable("球员发球前挑球，挑那颗最不毛的") == "球员发球前选球，选那颗最不毛的"
    assert speakable("鹰眼挑战制") == "鹰眼挑战制"
    assert speakable("辛纳手里那只是男单挑战杯") == "辛纳手里那只是男单挑战杯"

    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            spoken = speakable(seg.narration)
            for hit in re.finditer(r"挑(.?)", spoken):
                assert hit.group(1) in "战衅拨逗剔眉", (
                    f"{slug}/{seg.kind} 旁白里还有会被读成三声的「挑」：{spoken[:60]}"
                )


# 每个元组是同一个人的几种叫法。分组是必需的：「德约」和「德约科维奇」不是两个人，
# 按字符串去重会把单人片子误判成多人片子。名单不全没关系——漏掉一个人只会少管一条
# 片子，不会误伤；发现新面孔就往里加。
_ROSTER = (
    ("郑钦文", "钦文"), ("伊埃拉",), ("德约科维奇", "德约"), ("辛纳",),
    # 「威廉姆斯」不能当任何一个人的别名：小威和维纳斯都姓这个，用它去认人
    # 恰好是这条测试要挡的那种含混。小威在稿子里一律写「小威廉姆斯」，含「小威」。
    ("阿尔卡拉斯",), ("小威",), ("维纳斯",), ("波塔波娃",), ("斯瓦泰克",),
    ("纳达尔",), ("费德勒",), ("朱琳",), ("李娜",), ("塞伦多洛",), ("兹维列夫",),
    ("梅德韦杰夫",), ("穆雷",), ("大坂",), ("高芙",), ("萨巴伦卡",),
    ("克雷吉茨科娃",), ("纳芙拉蒂洛娃",), ("斯特恩斯",), ("弗雷赫",),
    ("莱巴金娜",), ("普利斯科娃",), ("商竣程",), ("锦织圭",),
    ("穆塞蒂",), ("吴易昺",), ("梅德韦杰夫",),
    ("黄泽林",), ("莱赫奇卡",), ("谢尔顿",), ("卢布列夫",),
)


def test_标题不靠代词指人():
    """两个人同框时，「她」没有安全的指代。

    封面写过「三年前她赢了这个人」——画面上站着郑钦文，文字里的「她」却要读者
    自己判断是谁赢了谁；两边都是女球员，两种读法都通。标题是最容易被单独截图
    转发的一屏，脱离上下文之后歧义只会更大，所以片子里但凡出现两个人，标题里的
    单数第三人称就必须和名字同时出现。旁白不受这条约束——那里有前后句消歧。

    两处豁免，都是真的不会指错：
    - 只讲一个人（或一个人都不点名）的片子，「他」只能落在那一个人身上；
    - 「他们」是泛指——「发球前，他们在挑什么？」问的是所有球员。
    """
    for slug in _SCRIPTED:
        segments = explainer_script(find_story_by_slug(slug))
        blob = " ".join(f"{s.title} {s.narration}" for s in segments)
        cast = [p for p in _ROSTER if any(alias in blob for alias in p)]
        if len(cast) < 2:
            continue
        aliases = [a for p in cast for a in p]
        for seg in segments:
            for hit in re.finditer(r"[她他](?!们)", seg.title):
                assert any(a in seg.title for a in aliases), (
                    f"{slug}/{seg.kind} 片中有 {len(cast)} 个人，"
                    f"标题却用「{hit.group()}」指代：{seg.title}"
                )


def test_栏目是登记过的并且赛前片子写清了日期():
    """栏目名不是装饰，是对读者的承诺，所以它必须是登记过的那几个之一。

    「开球之前」和「网球有故事」并行，两者的保质期完全不同：知识片明年再翻出来
    也还成立，赛前片在开球那一刻就过期了。所以易逝栏目多一条硬要求——**片子里
    必须写出比赛日期**，读者一眼能判断这条还算不算数。没有日期的赛前片，过期之后
    看起来和没过期一模一样。
    """
    from tennislive.video.explainer import COLUMNS, column_of, explainer_column

    for slug in _SCRIPTED:
        name = explainer_column(slug)
        assert name in COLUMNS, f"{slug} 用了没登记的栏目「{name}」"
        col = column_of(slug)
        if not col.perishable:
            continue
        blob = " ".join(
            f"{s.title} {s.narration} {' '.join(s.points)}"
            for s in explainer_script(find_story_by_slug(slug))
        )
        assert re.search(r"\d{1,2}\s*月\s*\d{1,2}\s*日", blob), (
            f"{slug} 在易逝栏目「{name}」里，却没写出比赛日期"
        )


def test_一张照片都没有的选题也要有封面():
    """有的选题**没有一张诚实的封面照片**，封面只能是自己画的图。

    `equal-pay` 讲的是一张奖金表：任何一张球员实拍都会把「第一轮出局的那些人」
    缩回到某一张脸上，而那正是这条选题要反对的看法。

    在此之前 `_opening_segment` 把 `diagram` 写死成空串，也就是默认
    **每条片子至少有一张照片**——于是全示意图的片子会被那道「缺图就停下来」
    的闸整个挡在门外。那道闸拦得对（缺图确实该停），只是这里不缺图，缺的是照片。

    ⚠️ 另一头同样要钉：**有照片的时候不许再叠一张示意图**，
    否则封面上会同时压着两个主体。
    """
    from tennislive.video.explainer import _opening_segment

    story = find_story_by_slug("equal-pay")
    beats = explainer_script(story)
    cover = beats[0]
    assert cover.kind == "cover"
    assert not cover.image, "这条选题没有照片，封面不该凭空冒出一张"
    assert cover.diagram, "全示意图的片子拿不到封面——那道缺图闸会把它挡住"
    assert "23760" in cover.diagram and "11270" in cover.diagram, (
        "封面画的应该是这条片子最硬的那两个数"
    )

    # 反面：有照片的选题，封面走照片，`diagram` 必须是空的。
    photo_story = find_story_by_slug("nadal-academy")
    photo_cover = explainer_script(photo_story)[0]
    assert photo_cover.image, "这条选题是有照片的"
    assert not photo_cover.diagram, (
        "有照片还叠示意图，封面上会同时压着两个主体"
    )

    # 第三头：**opening 自己没给图时，从第一屏借**。
    # 用一个不在 `_OPENINGS` 里的 slug，才走得到这条路——
    # `equal-pay` 自己有封面图，spec 那一份优先，借不借得到它测不出来。
    borrowed = _opening_segment(
        types.SimpleNamespace(slug="__not-registered__", title="x"),
        [ExplainerSegment(kind="cause", label="前因后果", title="x",
                          narration="y", diagram="<svg/>")],
    )
    assert borrowed.diagram == "<svg/>", "封面没能从第一屏借到那张图"


def test_赛前片的封面要写清是哪一场():
    """封面被单独截图转发时，大问题本身说不清「哪一场、几点」。

    账号所有者定的版式：问题下面两行小字，第一行是比赛坐标，第二行是对阵。

        7.30  09:00  ATP250 洛斯卡沃斯  16 强
        黄泽林  VS  莱赫奇卡

    这一条只管「开球之前」——知识片没有一场比赛可以钉，印上去反而是噪点，
    所以常青栏目必须**没有**这两行。

    时刻允许缺（三条已发的前瞻当时没记下官方开赛时刻，宁可不印也不猜），
    日期、赛事、轮次、两个人的名字一个都不能缺：少了任何一样，这两行就
    回答不了它唯一要回答的问题。名字一律查译名表。
    """
    from tennislive.video.explainer import (
        COLUMNS,
        _OPENINGS,
        _slide_html,
        explainer_column,
    )
    from tennislive.zh import _ranked_player_names
    from tennislive.zh.players import PLAYER_ZH

    # 判据和 test_人名要以译名表为准 用的是同一份表，外加那份「同一个人的
    # 另一种叫法」白名单——封面上的名字没有上下文消歧，更不该是手打的。
    #
    # ⚠️ 只并 `PLAYER_ZH` 是漏的一半：`player_zh()` 自己查名字时
    # **top500.json 优先，players.py 兜底**（CLAUDE.md 那条「两张表，
    # `player_names_top500.json` 优先」），只查旧表会把只登记在新表里的名字
    # （比如「麦克纳莉」）判成「没查过」。两处判据都要跟 `player_zh()`
    # 真正查的范围对齐，不能各查各的一半。
    known = set(PLAYER_ZH.values()) | set(_ranked_player_names().values()) | _ON_PURPOSE

    for slug in _SCRIPTED:
        cover = explainer_script(find_story_by_slug(slug))[0]
        column = explainer_column(slug)
        if not COLUMNS[column].perishable:
            assert not cover.fixture, f"{slug} 是常青栏目「{column}」，封面不该印比赛坐标"
            continue
        assert len(cover.fixture) == 2, f"{slug} 的封面缺了那两行小字"
        spec = _OPENINGS[slug]["fixture"]
        when, who = cover.fixture
        assert re.fullmatch(r"\d{1,2}\.\d{1,2}", spec["date"]), (
            f"{slug} 的比赛日期写法不对：{spec['date']}")
        for key in ("date", "level", "site", "round"):
            assert spec.get(key) and str(spec[key]) in when, f"{slug} 的封面小字缺 {key}"
        home, away = spec["players"]
        assert who == f"{home}  VS  {away}", f"{slug} 的对阵行版式不对：{who}"
        for name in (home, away):
            assert name in known, (
                f"{slug} 封面上的「{name}」不在译名表里——人名不要手打，"
                "先查 src/tennislive/zh/")
        # 渲出来也要真的在卡上，不能只活在数据里。
        doc = _slide_html(0, cover, column=column)
        assert when in doc and who in doc, f"{slug} 的封面小字没渲进卡片"


def test_赛前片只做巡回赛级别的比赛():
    """账号所有者定的选题门槛：「**需要巡回赛级别，250 以上**」。

    这条不是排版规矩，是**选题规矩**——它决定哪一场值得做一条片子。低于这个
    门槛的（WTA 125、挑战赛、ITF）不做：读者认不出赛事，两边的来路也摆不出
    什么份量。同一条线在今日赛程那边早就有了（`TOUR_LEVELS`，2026-07-28 那天
    一个罗马尼亚的 WTA 125 混进来，13 场比三个巡回赛级别的赛事加起来还多），
    这里复用**同一份**名单，免得两处各定一套门槛然后慢慢漂开。

    判据落在封面小字的 `level` 上：那是唯一一处把级别写成机器可读的地方，
    而且它会印在卡上——门槛和产物是同一个数，改不动其中一个而不动另一个。
    """
    from tennislive.render.webcards import TOUR_LEVELS
    from tennislive.video.explainer import COLUMNS, _OPENINGS, explainer_column

    for slug in _SCRIPTED:
        column = explainer_column(slug)
        if not COLUMNS[column].perishable:
            continue
        level = (_OPENINGS[slug].get("fixture") or {}).get("level")
        assert level in TOUR_LEVELS, (
            f"{slug} 的赛事级别是「{level}」，不在巡回赛级别里。"
            f"「开球之前」只做 250 及以上，见 TOUR_LEVELS。")


def test_成片旁边记下用的是哪个声音(tmp_path, monkeypatch):
    """成片自己要说得出它是谁配的音。

    每段旁白的 mp3 生成完就被工作流删掉（体积），mp4 里也读不出语音名——于是
    「这条是不是云健配的」只能靠推理：工作流传没传 --voice、代码默认是什么。
    那条推理链断过一次：工作流写死了一个旧的 --voice 每次都传，代码里换默认值
    等于没换，三条片子用被替换掉的声音发了出去，几天后翻运行日志才发现。

    所以把它写在成片旁边。查的时候打开 narration.json 就行，不用再推。
    """
    import json

    from tennislive.video import explainer as E

    monkeypatch.setattr(E, "render_explainer_slides", lambda *a, **k: [])
    monkeypatch.setattr(E, "synthesize_narration", lambda *a, **k: ["a.mp3", "b.mp3"])
    monkeypatch.setattr(E, "assemble_explainer_video", lambda *a, **k: tmp_path / "x.mp4")

    E.generate_explainer_video(find_story_by_slug("zheng-eala"), tmp_path)
    meta = json.loads((tmp_path / "narration.json").read_text(encoding="utf-8"))
    assert meta["voice"] == E.DEFAULT_VOICE == "zh-CN-YunjianNeural"
    # 只钉「记下来的就是实际用的那一档」。**具体是哪一档不在这儿钉死**——
    # 那个数由 test_explainer_budget 的 `_MEASURED` 管着，而且它连带要求
    # 换档必须重量。两处都写死的话，改语速要动三个地方，必分叉。
    assert meta["rate"] == E.DEFAULT_RATE
    assert meta["segments"] == 2

    E.generate_explainer_video(
        find_story_by_slug("zheng-eala"), tmp_path, voice="zh-CN-YunxiNeural")
    meta = json.loads((tmp_path / "narration.json").read_text(encoding="utf-8"))
    assert meta["voice"] == "zh-CN-YunxiNeural"  # 覆盖了也照实记


def test_片头片尾各留一段静音(tmp_path, monkeypatch):
    """开头第一个字就响、最后一个字一落就黑，两头都像出了故障。

    封面来不及被看清就有人开口说话；结尾那句「你第一次记住郑钦文，是哪一场？」
    是留给评论区的，字还没读完片子就没了。所以两端各按一拍——**片尾比片头长**，
    因为读一个问题比看清一张照片花的时间多。

    静音加在**声音**上（adelay 把语音往后推、apad 在末尾挂一段安静），画面靠
    每张图自己的 -t 撑满整段；如果只延长画面不延长声音，concat 会按较短的那条
    对齐，静音等于没加。
    """
    from pathlib import Path as _Path

    from tennislive.video import explainer as E

    calls: list[list[str]] = []

    def runner(cmd, **kw):
        calls.append(list(cmd))
        if "ffprobe" in cmd[0]:
            return type("R", (), {"stdout": "10.000\n"})()
        _Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"stdout": ""})()

    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    slides = [tmp_path / f"s{i}.png" for i in range(3)]
    audios = [tmp_path / f"a{i}.mp3" for i in range(3)]
    for p in slides + audios:
        p.write_bytes(b"x")

    E.assemble_explainer_video(slides, audios, tmp_path / "out.mp4", runner=runner)
    cmd = calls[-1]
    durations = [cmd[i + 1] for i, tok in enumerate(cmd) if tok == "-t"]
    assert durations == ["10.600", "10.000", "11.500"], durations

    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=600:all=1" in graph  # 只有第一段被往后推
    assert graph.count("adelay") == 1
    assert "apad=pad_dur=1.500" in graph  # 只有最后一段挂了静音
    assert graph.count("apad") == 1
    # 中间那段没有静音，但仍然要有自己的标签，否则 concat 接不上。
    assert "[3:a]anull[a1]" in graph
    assert "[v0][a0][v1][a1][v2][a2]concat=n=3" in graph


def test_只有一屏时片头片尾都加在同一段上(tmp_path, monkeypatch):
    """一屏的片子既是开头也是结尾，两段静音落在同一条声音上。"""
    from pathlib import Path as _Path

    from tennislive.video import explainer as E

    calls: list[list[str]] = []

    def runner(cmd, **kw):
        calls.append(list(cmd))
        if "ffprobe" in cmd[0]:
            return type("R", (), {"stdout": "4.000\n"})()
        _Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"stdout": ""})()

    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    slide, audio = tmp_path / "s.png", tmp_path / "a.mp3"
    slide.write_bytes(b"x")
    audio.write_bytes(b"x")

    E.assemble_explainer_video([slide], [audio], tmp_path / "one.mp4", runner=runner)
    cmd = calls[-1]
    assert cmd[cmd.index("-t") + 1] == "6.100"  # 4 + 0.6 + 1.5
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "adelay=600:all=1,apad=pad_dur=1.500" in graph


def test_解说片的片尾要接进concat(tmp_path, monkeypatch):
    """账号所有者 2026-08-05：「每个视频最后都加一页并配上关注的口播」，
    随后补的「**开球之前也要加**」——这条线一次覆盖三个栏目（每日网球知识 /
    网球有故事 / 开球之前）。

    这条只验**滤镜图接对了**（快、不碰 ffmpeg）：片尾要占 concat 的最后一格，
    索引不能和幻灯片的输入撞，而且**不给它排字幕**（那一页上印着口播的每个字）。
    真拼出来对不对，交给下面那条真跑 ffmpeg 的。
    """
    from pathlib import Path as _Path

    from tennislive.video import explainer as E

    calls: list[list[str]] = []

    def runner(cmd, **kw):
        calls.append(list(cmd))
        if "ffprobe" in cmd[0]:
            return type("R", (), {"stdout": "4.000\n"})()
        _Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"stdout": ""})()

    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    slides = [tmp_path / f"s{i}.png" for i in range(2)]
    audios = [tmp_path / f"a{i}.mp3" for i in range(2)]
    outro = tmp_path / "_outro.mp4"
    for p in [*slides, *audios, outro]:
        p.write_bytes(b"x")

    E.assemble_explainer_video(slides, audios, tmp_path / "out.mp4",
                               captions=["第一屏", "第二屏"],
                               outro=outro, runner=runner)
    graph = calls[-1][calls[-1].index("-filter_complex") + 1]

    # 幻灯片占 0..3（两屏各一图一音），片尾是第 4 个输入
    assert "[4:v]scale=" in graph, f"片尾没接进滤镜图：{graph}"
    assert "[4:a]aresample" in graph, "片尾的音轨没接上——成片最后会没声音"
    # 片尾占 concat 的最后一格
    assert "[v0][a0][v1][a1][v2][a2]concat=n=3" in graph, (
        f"片尾没排在 concat 的最后一格：{graph}")
    # **不给片尾排字幕**：那一页上印着口播说的每个字
    outro_chain = [c for c in graph.split(";") if c.startswith("[4:v]")][0]
    assert "subtitles" not in outro_chain, (
        "片尾不该排字幕——那一页上印着「网球时差」和那句解释，"
        "再排一行只会压在小字上")

    # 反向：不给 outro 就只有两格，一个字都不该多
    calls.clear()
    E.assemble_explainer_video(slides, audios, tmp_path / "out2.mp4",
                               captions=["第一屏", "第二屏"], runner=runner)
    graph2 = calls[-1][calls[-1].index("-filter_complex") + 1]
    assert "concat=n=2" in graph2 and "[4:v]" not in graph2


def test_解说片接上片尾之后成片真的变长(tmp_path):
    """**真跑一次 ffmpeg。** 上面那条查的是滤镜图字符串，而查字符串只能防
    「有人把它删了」，防不住「它从来没工作过」——这个仓库里「签名对了、实现是
    空的」是常客（`_cut_person(source, …)` 那次整整一天没人发现）。

    ⚠️ 片尾用**纯色 mp4** 造，不渲真页面：这条判据要在 CI 上跑得起来，而 CI
    上没有 Chromium 也连不上 TTS。它验的是「接上去之后成片真的长了那么多、
    而且音轨没断」，不是那一页好不好看。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    # 两屏：3:4 的卡 + 各 2 秒旁白
    slides, audios = [], []
    for i, colour in enumerate(("red", "green")):
        s = tmp_path / f"s{i}.png"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
              f"color=c={colour}:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
        a = tmp_path / f"a{i}.mp3"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
              "sine=frequency=440:sample_rate=24000", "-t", "2.0",
              "-ac", "1", str(a)])
        slides.append(s)
        audios.append(a)

    # 片尾：3 秒纯色 + 正弦音，参数照 render_clip 出来的那份
    outro = tmp_path / "_outro.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", f"color=c=blue:s={E.VIDEO_W}x{E.CARD_H}:r=30",
          "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000",
          "-t", "3.0", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          str(outro)])

    def _dur(path, stream):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True).stdout.strip().rstrip(","))

    plain = E.assemble_explainer_video(slides, audios, tmp_path / "plain.mp4")
    withx = E.assemble_explainer_video(slides, audios, tmp_path / "withx.mp4",
                                       outro=outro)

    grew = _dur(withx, "v:0") - _dur(plain, "v:0")
    assert abs(grew - 3.0) < 0.25, (
        f"接上 3 秒的片尾之后成片只长了 {grew:.2f}s——片尾没真的拼进去，"
        "或者被 concat 截掉了")

    # **音轨也要跟着长。** 只验画面会被一段无声的片尾骗过去——
    # 「音轨比画面短」这个毛病在剪辑片那条线上骗过七条已发的成片。
    assert abs(_dur(withx, "a:0") - _dur(withx, "v:0")) < 0.35, (
        f"音轨 {_dur(withx, 'a:0'):.2f}s 和画面 {_dur(withx, 'v:0'):.2f}s 对不上"
        "——片尾那一段没有声音")


def test_解说片接上片头之后成片真的变长(tmp_path):
    """`intro` 对称于上一条测试的 `outro`——冷开场实拍片段接在最前面，不是
    接在末尾。它多加了一层复杂度上一条测试没有：`intro` 抢占输入 0，后面
    每个 slide/audio 在 ffmpeg 命令行里的下标都要跟着整体后移一位。这条测试
    专挑这一层：`intro` 和 `outro` **同时给**，前后各接一段，缺一处下标算错
    就会把中间的幻灯片对到错的输入上，或者直接被 concat 报错到底。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    slides, audios = [], []
    for i, colour in enumerate(("red", "green")):
        s = tmp_path / f"s{i}.png"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
              f"color=c={colour}:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
        a = tmp_path / f"a{i}.mp3"
        _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
              "sine=frequency=440:sample_rate=24000", "-t", "2.0",
              "-ac", "1", str(a)])
        slides.append(s)
        audios.append(a)

    def _clip(path, colour, seconds):
        _run(["ffmpeg", "-v", "error", "-y",
              "-f", "lavfi", "-i", f"color=c={colour}:s={E.VIDEO_W}x{E.CARD_H}:r=25",
              "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000",
              "-t", f"{seconds}", "-c:v", "libx264", "-preset", "ultrafast",
              "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1",
              str(path)])

    intro = tmp_path / "_intro.mp4"
    outro = tmp_path / "_outro.mp4"
    _clip(intro, "yellow", 4.0)
    _clip(outro, "blue", 3.0)

    def _dur(path, stream):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True).stdout.strip().rstrip(","))

    plain = E.assemble_explainer_video(slides, audios, tmp_path / "plain2.mp4")
    both = E.assemble_explainer_video(slides, audios, tmp_path / "both.mp4",
                                       intro=intro, outro=outro)

    grew = _dur(both, "v:0") - _dur(plain, "v:0")
    assert abs(grew - 7.0) < 0.3, (
        f"接上 4 秒片头 + 3 秒片尾之后成片只长了 {grew:.2f}s（该长 7s）——"
        "片头或片尾没有真的拼进去，或者下标算错把中间的幻灯片吃掉了")
    assert abs(_dur(both, "a:0") - _dur(both, "v:0")) < 0.35, (
        f"音轨 {_dur(both, 'a:0'):.2f}s 和画面 {_dur(both, 'v:0'):.2f}s 对不上")

    # 只接片头（不接片尾）单独验一遍下标偏移，防止「两个一起给才对，
    # 单独给片头时 offset 算错」这类只在一种组合下现形的 bug。
    only_intro = E.assemble_explainer_video(slides, audios, tmp_path / "only_intro.mp4",
                                             intro=intro)
    grew_i = _dur(only_intro, "v:0") - _dur(plain, "v:0")
    assert abs(grew_i - 4.0) < 0.3, (
        f"只接 4 秒片头，成片只长了 {grew_i:.2f}s——offset 没有正确应用到"
        "后面的 slide/audio 输入下标上")


def test_冷开场实拍片段要铺满不留黑边(tmp_path):
    """账号所有者 2026-08-07：「前面的视频有点突兀」。一部分根子是横版源片
    原来按 `pad` 信箱式塞进 9:16 画布，上下各留出约三分之一屏幕高的纯色带
    ——看着像放错了比例，不是这条片子自己的画面。

    改成 `force_original_aspect_ratio=increase` + `crop`：铺满整个画布，
    代价是裁掉源片左右一部分。这条测试造一段纯色的 16:9 clip 当 intro，
    抽一帧看四个角——旧的 `pad` 写法会让四角落在 `_BAND_COLOR` 那道深绿
    纯色带里，新的 `crop` 写法应该四个角都是源片自己的颜色。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    s = tmp_path / "s0.png"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          f"color=c=green:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
    a = tmp_path / "a0.mp3"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          "sine=frequency=440:sample_rate=24000", "-t", "1.0", "-ac", "1", str(a)])

    # 16:9，跟真实源片同一形状的横版纯色 clip——纯洋红，好认。
    intro = tmp_path / "_intro.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=magenta:s=1280x720:r=25",
          "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000",
          "-t", "2.0", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          str(intro)])

    out = E.assemble_explainer_video([s], [a], tmp_path / "out.mp4", intro=intro)

    frame = tmp_path / "frame.png"
    _run(["ffmpeg", "-v", "error", "-y", "-ss", "1.0", "-i", str(out),
          "-frames:v", "1", str(frame)])
    im = Image.open(frame).convert("RGB")
    w, h = im.size
    corners = [im.getpixel((2, 2)), im.getpixel((w - 3, 2)),
               im.getpixel((2, h - 3)), im.getpixel((w - 3, h - 3))]
    # 洋红大约是 (255, 0, 255)；band color 是 (6, 28, 20)。只要四个角都
    # 明显偏红/偏亮，就证明没有信箱黑边——旧写法这四个角会是深绿。
    for px in corners:
        assert px[0] > 120, f"这个角 {px} 看着像信箱黑边，不是源片自己的颜色"


def test_冷开场台头要和幻灯片台头同一份样式(tmp_path):
    """`_render_intro_badge` 渲的是和 `_slide_html` 里 `.head` 像素级一致的
    台头——图标、品牌字、topic 行，透明背景叠上去。这条测试钉住两头：
    给了 `intro_badge` 就真的叠上去了（画面里能看到台头，不是原样的纯色）；
    没给就还是老样子（不强求，锦上添花，见 `generate_explainer_video` 里
    渲不出来就退回 None 那段）。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    s = tmp_path / "s0.png"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          f"color=c=green:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
    a = tmp_path / "a0.mp3"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          "sine=frequency=440:sample_rate=24000", "-t", "1.0", "-ac", "1", str(a)])
    intro = tmp_path / "_intro.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=magenta:s=1280x720:r=25",
          "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000",
          "-t", "2.0", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          str(intro)])

    badge = E._render_intro_badge("测试标题", "开球之前", tmp_path)
    assert badge is not None and badge.is_file(), "Chromium 装着的话台头必须渲得出来"
    im = Image.open(badge)
    assert im.mode == "RGBA", "台头必须是带透明通道的 PNG，不然叠上去会是一块实心矩形"
    assert im.split()[-1].getextrema()[1] > 0, "整张图全透明——文字和图标都没画上去"

    with_badge = E.assemble_explainer_video(
        [s], [a], tmp_path / "with_badge.mp4", intro=intro, intro_badge=badge,
    )
    without_badge = E.assemble_explainer_video(
        [s], [a], tmp_path / "without_badge.mp4", intro=intro,
    )

    def _sample(path):
        frame = tmp_path / f"{path.stem}_frame.png"
        _run(["ffmpeg", "-v", "error", "-y", "-ss", "0.3", "-i", str(path),
              "-frames:v", "1", str(frame)])
        # 台头压在左上角 top:44/left:70 那一带（1080 宽的画布上）。
        return Image.open(frame).convert("RGB").crop((70, 44, 500, 140))

    def _has_badge_pixels(im):
        # 背景故意选纯洋红 (255,0,255)：G 通道恒为 0。台头的文字（近白）和
        # 图标（浅绿的网球）两者 G 通道都很高，用它分辨"这个像素来自台头"
        # 还是"背景本身"——不能直接比亮度，纯洋红本身就够亮（255+0+255=510），
        # 第一版就是拿"总亮度 > 400"判的，被这个背景色自己骗过了假阳性。
        return any(px[1] > 150 for px in im.getdata())

    assert _has_badge_pixels(_sample(with_badge)), "给了 intro_badge，画面里却看不出台头"
    assert not _has_badge_pixels(_sample(without_badge)), (
        "没给 intro_badge，画面里却出现了台头——两次调用互相污染了？")


def test_冷开场台头不许把片头拖到台头图那么长(tmp_path):
    """2026-08-07 真实渲染栽的坑：eala-mcnally 那条片子接上台头之后，
    片头从 16.0s 变成了 60.0s——多出的 43.97s 正好是台头图 `-t 60` 减去
    intro 本身的 16s。`overlay` 默认不会在**主输入**（intro）结束时收口，
    而是把它的最后一帧冻住，跟着叠加层（台头图）一路播到 60 秒；本地那条
    抽一帧看台头有没有叠上去的测试完全没抓到——它只在 t=0.3s 采样，
    那一刻两个版本都还没跑到问题发生的地方。

    这条测试直接比总时长：intro 4 秒、台头 `-t 60`，接了台头之后的成片
    不许比没接台头长超过一点点（片头本身的长度不该被台头的 `-t` 参数
    牵着走）。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    s = tmp_path / "s0.png"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          f"color=c=green:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
    a = tmp_path / "a0.mp3"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          "sine=frequency=440:sample_rate=24000", "-t", "1.0", "-ac", "1", str(a)])
    intro = tmp_path / "_intro.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=magenta:s=1280x720:r=25",
          "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000",
          "-t", "4.0", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          str(intro)])

    badge = E._render_intro_badge("测试标题", "开球之前", tmp_path)
    assert badge is not None and badge.is_file()

    def _dur(path):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True).stdout.strip().rstrip(","))

    without_badge = E.assemble_explainer_video(
        [s], [a], tmp_path / "without_badge.mp4", intro=intro,
    )
    with_badge = E.assemble_explainer_video(
        [s], [a], tmp_path / "with_badge.mp4", intro=intro, intro_badge=badge,
    )

    grew = _dur(with_badge) - _dur(without_badge)
    assert abs(grew) < 0.3, (
        f"接上台头之后成片长了 {grew:.2f}s——台头图的 `-t 60` 把片头本身的"
        "长度拖长了，overlay 那句里是不是漏了 shortest=1？"
    )


def test_canvas_h传CARD_H画布真的变成三比四不留黑边(tmp_path):
    """账号所有者看完铺满版：「画面还不是 3:4 的啊」。铺满只是把内容裁进
    9:16 画布，画布本身没变——`canvas_h` 才是真正换画布的开关。

    卡片本来就是 1080×1440（`CARD_H`）渲的，`canvas_h=CARD_H` 时 pad 那步
    对卡片是个空操作。这条测试拿一张纯色卡片直接验证：给了 `canvas_h=CARD_H`，
    输出画面必须真的是 1080×1440，而且四个角必须是卡片自己的颜色（不是
    `_BAND_COLOR`——那道颜色就是"还留着黑边"的证据）。默认不传的那条路
    （9:16）留给别的既有测试守着，这条只钉新加的这一半。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    s = tmp_path / "s0.png"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          f"color=c=orange:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
    a = tmp_path / "a0.mp3"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          "sine=frequency=440:sample_rate=24000", "-t", "1.0", "-ac", "1", str(a)])

    out = E.assemble_explainer_video(
        [s], [a], tmp_path / "out.mp4", canvas_h=E.CARD_H,
    )

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    w, h = (int(x) for x in probe.split(","))
    assert (w, h) == (E.VIDEO_W, E.CARD_H), (
        f"传了 canvas_h=CARD_H，成片却是 {w}x{h}，不是 3:4 的 {E.VIDEO_W}x{E.CARD_H}")

    frame = tmp_path / "frame.png"
    _run(["ffmpeg", "-v", "error", "-y", "-ss", "0.5", "-i", str(out),
          "-frames:v", "1", str(frame)])
    im = Image.open(frame).convert("RGB")
    fw, fh = im.size
    corners = [im.getpixel((2, 2)), im.getpixel((fw - 3, 2)),
               im.getpixel((2, fh - 3)), im.getpixel((fw - 3, fh - 3))]
    # 橙色大约是 (255, 165, 0)；band color 是 (6, 28, 20)。四个角的 R 通道
    # 明显偏亮就说明没有黑边——旧写法（画布还是 9:16）这四个角会是深绿。
    for px in corners:
        assert px[0] > 120, f"这个角 {px} 看着像还留着黑边，画布没有真的变成 3:4"


def test_intro_cx显式给定的比例决定哪一段源片落在画面中心(tmp_path):
    """账号所有者 2026-08-07：「居中啊，和后面视频一样啊」——`crop` 不给
    `x` 就是缺省居中源片的几何中心，不是画面里那个人。`intro_cx` 是显式
    给的水平中心（源片宽度的比例，0.5＝几何居中，行为跟改之前一样）。

    造一段源片：蓝色背景配一条窄的洋红竖条，竖条中心精确落在源片 1280 宽
    的 30%（x=384）处。给 `intro_cx=0.3`，这条竖条应该被钉到输出画面正
    中心；不给（缺省 0.5，纯几何居中）时，它应该落在输出左侧、明显偏离
    中心——两者一起验证：给了会真的移动裁切窗口，不给还是老样子。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    from tennislive.video import explainer as E

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def _run(args):
        subprocess.run(args, check=True, capture_output=True)

    s = tmp_path / "s0.png"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          f"color=c=green:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s)])
    a = tmp_path / "a0.mp3"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          "sine=frequency=440:sample_rate=24000", "-t", "1.0", "-ac", "1", str(a)])

    # 蓝底 + 一条窄的洋红竖条，竖条中心精确落在源片 30% 宽度处（x=384）。
    intro = tmp_path / "_intro.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=25",
          "-f", "lavfi", "-i", "color=c=magenta:s=20x720:r=25",
          "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=24000",
          "-filter_complex", "[0:v][1:v]overlay=374:0[v]",
          "-map", "[v]", "-map", "2:a",
          "-t", "1.0", "-c:v", "libx264", "-preset", "ultrafast",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1",
          str(intro)])

    def _bar_x(out):
        frame = tmp_path / f"{out.stem}_frame.png"
        _run(["ffmpeg", "-v", "error", "-y", "-ss", "0.3", "-i", str(out),
              "-frames:v", "1", str(frame)])
        im = Image.open(frame).convert("RGB")
        row = im.size[1] // 2
        # 沿中间那一行找洋红那道竖条（R、B 都高，G 低）。
        xs = [x for x in range(im.size[0])
              if (im.getpixel((x, row))[0] > 150
                  and im.getpixel((x, row))[2] > 150
                  and im.getpixel((x, row))[1] < 100)]
        assert xs, "洋红竖条在这一帧里一个像素都没找到"
        return sum(xs) / len(xs)

    default_out = E.assemble_explainer_video(
        [s], [a], tmp_path / "default.mp4", intro=intro, canvas_h=E.CARD_H,
    )
    centered_out = E.assemble_explainer_video(
        [s], [a], tmp_path / "centered.mp4", intro=intro, canvas_h=E.CARD_H,
        intro_cx=0.3,
    )

    default_x = _bar_x(default_out)
    centered_x = _bar_x(centered_out)
    ow = E.VIDEO_W

    assert abs(centered_x - ow / 2) < 20, (
        f"intro_cx=0.3 应该把 30% 处的竖条钉到输出中心 {ow / 2}，实测在 {centered_x:.1f}"
    )
    assert abs(default_x - ow / 2) > 200, (
        "默认 cx=0.5 应该是纯几何居中，30% 处的竖条不该落在输出中心附近，"
        f"实测在 {default_x:.1f}——是不是默认值被意外改动了？"
    )


def test_同一天可以并存多条片子():
    """一天不止一条「开球之前」——两条前瞻不能互相覆盖。

    这条测试盯的是工作流，不是 Python：成片路径、并发分组、提交范围三处只要有一处
    丢掉 slug，同一天的第二条片子就会把第一条盖掉。三处都是事故换来的：

    - 分组名写死一个常量 → GitHub 每组只留一个 pending，一口气发七条只活下来两条
    - 提交时重放整棵 `output/` → 八条片子整晚互相退回到各自开跑时的样子
    - 同一个 slug 连发两版 → 两个 run 一起跑，先落库的旧版赢，commit message 还一模一样
    """
    from pathlib import Path

    yml = (_REPO / ".github" / "workflows" / "explainer.yml").read_text(encoding="utf-8")

    # 成片路径按 slug 分目录：两条片子各写各的，天然不打架。
    assert 'OUT_DIR="output/$OUT_DATE/explainer/$SLUG"' in yml

    # 并发分组必须带 slug，否则不同选题会互相取消。
    assert "group: explainer-video-${{ github.event.inputs.slug" in yml
    # 同一个 slug 反过来要取消旧的：一条片子只有一个"最新"。
    assert "cancel-in-progress: true" in yml

    # 提交与重放只碰本次的 outdir，绝不整棵 output/ 重放。
    assert 'git add "$OUTDIR"' in yml
    assert 'git checkout rendered -- "$OUTDIR"' in yml
    assert "git checkout rendered -- output/" not in yml

    # 并且「开球之前」这个栏目此刻确实挂着不止一条片子——不是理论上支持而已。
    from tennislive.video.explainer import explainer_column

    previews = [s for s in _SCRIPTED if explainer_column(s) == "开球之前"]
    assert len(previews) >= 2, f"开球之前只有 {previews}，多场并存没有真的被用起来"
    assert len(set(previews)) == len(previews)
    assert Path("assets/explainer").is_dir()


def test_大标题里不能有冒号():
    """小红书文案把每一屏排成「小标：大标」，标题里再带冒号就成了一行两个。

    「答案：维纳斯说：我回来是为了上保险」——念不通，看着也像排版出错。改成逗号即可，
    引号里的原话一个字不动。
    """
    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            assert "：" not in seg.title and ":" not in seg.title, (
                f"{slug}/{seg.kind} 大标题里有冒号：{seg.title}"
            )


def test_收尾那个问题一定要念出来():
    """问题只印在末屏、旁白不问，等于没留。

    十三条片子里有十条是这样：画面上写着「你更爱看群雄逐鹿，还是王朝统治？」，
    旁白讲完最后一句就停了——**只看视频的人根本不知道被问了什么**，而这一问是
    这类短片换评论区的唯一抓手。现在由 `_ask_it_out_loud` 统一补，靠"结尾有没有
    问号"判断，不靠逐字比对：好几条旁白早就问过意思一样、措辞不同的话，逐字比
    对匹配不上，补一遍就成了连问两遍。
    """
    from tennislive.video.explainer import speakable

    for slug in _SCRIPTED:
        closer = explainer_script(find_story_by_slug(slug))[-1]
        assert closer.question, f"{slug} 末屏没有互动提问"
        spoken = speakable(closer.narration)
        assert "？" in spoken[-40:], f"{slug} 旁白结尾没有问出来：…{spoken[-30:]}"
        # 也不能把同一个问题问两遍。不查问号个数——鹰眼那条的旁白本来就连着
        # 抛了两问（「法网还能坚持多久？什么时候也会换成电子司线？」），那是写稿
        # 时的选择，不是重复。查的是末屏那一问有没有被补进去两次。
        core = closer.question.rstrip("？?")
        assert spoken.count(core) <= 1, f"{slug} 同一个问题问了两遍：{core}"


def test_旁白里不能留下markdown记号():
    """写稿时顺手打的 `**加粗**`，配音会一个字一个字念出来。

    这些标记只对写稿的人有意义，对 edge-tts 没有——它不会跳过星号。画面文字
    同理，卡片是纯文本渲染，星号会原样印上去。
    """
    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            for field, text in (("旁白", seg.narration), ("标题", seg.title)):
                assert not re.search(r"[*`_#]", text), (
                    f"{slug}/{seg.kind} 的{field}里有 markdown 记号：{text[:40]}"
                )
            for p in seg.points:
                assert not re.search(r"[*`_#]", p), f"{slug}/{seg.kind} 要点里有记号：{p}"


def test_字幕补上耳朵那一份():
    """卡上放得下的只有两三条短句，旁白里装着的是全部。

    静音刷是默认状态。没有字幕，静音的人拿到的就只有那几条短句——引语、数字、
    来龙去脉全丢了，而那才是这条片子的内容。所以字幕不是装饰，是补上耳朵那一份。

    这里盯三件事：切出来的行不会长到顶边、字幕文本和**听到的**一致（比分照着
    念的样子写）、行与行在原文里首尾相接不丢字。
    """
    from tennislive.video import explainer as E

    text = "二〇二四年九月，成都公开赛首轮，当时十九岁的商竣程6-4、6-4击败锦织圭。"
    lines = E.subtitle_lines(E.readable(text))
    assert lines, "一句话都没切出来"
    for _, _, shown in lines:
        assert len(shown) <= E._SUB_MAX, f"这行顶到边了：{shown}"
    # 比分要和耳朵对上：屏幕上是 6-4，念出来和字幕里都是「6比4」——
    # 「比」两边不加空格，没有人把比分写成「6 比 4」。
    assert any("6比4" in shown for _, _, shown in lines), lines
    # 相邻两行在原文里首尾相接——中间掉字的话，时间轴也会跟着错位。
    for (_, end, _), (start, _, _) in zip(lines, lines[1:]):
        assert start == end


def test_顿号连的并列项和半截短句都并进一行():
    """zheng-burel 那条切出「郑钦文6比1｜7比5击败布雷尔｜闯进决胜轮」三连闪屏，
    「2018年，」独占 0.9 秒一屏——机器味全在这类碎行上。

    两条合并规矩：顿号连的是**并列项**，装得下就整组一行（步骤 3a）；
    句内 ≤6 字的半截话并进邻行（3b，`_SUB_MERGE_SHORT`——原来的门槛是
    「短到读不到」的 <5，「2018年」这种 5 字半句够不着）。跨句合并照旧
    只认 ≤2 的地板（「字幕也要保持断句的完整性，不要多也不要少」）。
    """
    from tennislive.video import explainer as E

    def shown(text):
        return [s for _, _, s in E.subtitle_lines(E.readable(text))]

    # 顿号并列成组；逗号后那句和整组装不下一行，各自成行
    assert shown("郑钦文6-1、7-5击败布雷尔，闯进决胜轮。") == [
        "郑钦文6比1 7比5击败布雷尔", "闯进决胜轮"]
    # 两边都不短（各 7 字）**只有**顿号并列这条规矩会合——短句合并够不着它
    assert shown("上半区斯瓦泰克、下半区萨巴伦卡。") == [
        "上半区斯瓦泰克 下半区萨巴伦卡"]
    # 5 个字的「2018年」不再独占一屏
    assert shown("2018年，她登顶青少年世界第一。") == [
        "2018年 她登顶青少年世界第1"]
    # 比分并列成组 + 比分不空格（medvedev-damm 那条的两个毛病一起钉住）
    assert shown("达姆7-5、6-3爆冷，总分67比56。") == [
        "达姆7比5 6比3爆冷", "总分67比56"]
    # 跨句（句号那一档）照旧不合并——两句不同的话不许挤在同一屏
    assert shown("先看一眼签表。这是澳网女单签表的一角。") == [
        "先看一眼签表", "这是澳网女单签表的一角"]


def test_超宽子句报出来让人在标点处断开():
    """两个标点之间宽过一行字幕（16 格）的子句只能从词语边界硬切——切得再好
    也比在标点处断开差一截。`overwide_clauses` 把它们报出来（dry-run 的软提醒，
    只报不拦：硬切是兜底不是错误，做成硬闸会把一批已发的好 spec 挡住）。"""
    from pathlib import Path

    from tennislive.video import explainer as E

    long_clause = "格里克斯普尔一口气要到三个破发点之后又亲手全部还了回去"
    assert E.overwide_clauses(f"开局那一局，{long_clause}。") == [f"{long_clause}。"]
    assert E.overwide_clauses("郑钦文6-1、7-5击败布雷尔，闯进决胜轮。") == []
    # 接线：dry-run 真的调它（写出来没人用是这个仓库的常客）
    body = Path("tools/build_match_reel.py").read_text("utf-8")
    assert "overwide_clauses(readable(" in body


def test_断行不许把人名孤成一行():
    """「正赛首轮两盘击败当届温网冠军｜莱巴金娜」——四个字的人名孤成一行只停
    一秒（zheng-burel 已发成片）。「军」在 `_SUB_AFTER` 里，边界分压过了一切。

    修法两半：量词边界（数目字＋盘/局/轮才算，「三个盘点」的「盘」前面是
    「个」，不算——无条件加分会把「盘点」劈开）＋ 孤行罚分（罚不满一个边界档：
    别的边界赢过它，只剩它时孤行仍好过把词劈开）。
    """
    from tennislive.video import explainer as E

    def shown(text):
        return [s for _, _, s in E.subtitle_lines(E.readable(text))]

    assert shown("正赛首轮两盘击败当届温网冠军莱巴金娜") == [
        "正赛首轮两盘", "击败当届温网冠军莱巴金娜"]
    # 「三个盘点」不许从「盘」后断开
    for line in shown("决胜盘他浪费了三个盘点之后被连破两局"):
        assert not line.endswith("个盘"), line


def test_分行整句一起挑最优不许贪心把尾巴挤成孤屏():
    """账号所有者 2026-08-31：「再去帮我看看配音文案断句和字幕换行断句问题」。

    量出来 123 处「前一行贴满（≥13.5 格）＋ 同句尾巴只剩两三个字」，根子是
    `subtitle_lines` 步骤 3b **从左往右的贪心**：它把短片段用在前面，后面的
    尾巴就没了伴。换成「整句一起挑最优」之后 **123 → 69**。

    ⚠️ **搜索空间没变，合并规矩一条没松**：一组里要么只有一个子句，要么
    组里有个短到该被并走的（同句 ≤6 / 跨句 ≤2）。所以上面那条
    `test_顿号连的并列项和半截短句都并进一行` 的每一条断言原样成立。

    ⚠️⚠️ **`_best_break` 也试过同一个改法，撤了**——它会把词劈开，账记在那个
    函数的 docstring 和 `test_断点不许让非词边界赢过词边界` 里。这条判据只管
    3b 这一半。

    三个方向分别反向验证过，各红在自己的断言行：3b 退回从左往右的贪心 → ①；
    代价里的空余退回线性 → ②；孤屏代价调成 0 → ③。

    ⚠️ 代价函数里「**末行不算孤屏**」那一条**没有断言**，因为它验不出来：
    构造和真实例子都试过，DP 总是先把短片段并掉、并完末行就不短了，所以
    末行算不算孤屏得到的分法一模一样。它是防御性的（万一某天末片段真的
    无处可并，不至于为了消灭它去做更碎的分法），**不是量出来的**——
    别在这儿写一条看起来验过、其实分不出两种设计的断言。
    """
    from tennislive.video import explainer as E

    def shown(text):
        return [s for _, _, s in E.subtitle_lines(E.readable(text))]

    # ① 3b：同一句里的短片段要并给「并完不留孤屏」的那一边，不是先到先得
    #    贪心把「捷克人」花在前面 → 「对面的巴尔通科娃20岁 捷克人｜世界第39」
    assert shown("对面的巴尔通科娃二十岁，捷克人，世界第三十九。") == [
        "对面的巴尔通科娃20岁", "捷克人 世界第39"]

    # ② 空出来的那截要**平方**：线性的话「把一个片段从这行挪到那行」两边
    #    一增一减正好抵消，任何分法总和都一样，选中谁全看遍历顺序先撞上谁。
    #    这一条线性下切成「掀翻世界第1之后 这一次｜她能走多远？」——把「这一次」
    #    拽到上一屏的尾巴，末屏那一问断了头。
    assert shown("掀翻世界第一之后，这一次，她能走多远？") == [
        "掀翻世界第1之后", "这一次 她能走多远？"]

    # ③ 短片段要并给**前面**（留在前面就成了孤屏，留到末尾是落点）。
    #    片段宽 5.0 / 8.7 / 4.4，两种分法完全对称、均衡项一模一样，
    #    **只有孤屏那一项在区分**——这条是专门为它写的：孤屏代价一旦归零
    #    或压到均衡之下，DP 就会翻过去选「5.0 ｜ 8.7+4.4」，把 5 格那行
    #    孤在中间。
    assert shown("第二盘开局，他一口气连丢了三局，二比五落后。") == [
        "第二盘开局 他一口气连丢了3局", "2比5落后"]

    # ④ 换成 DP 之后**跨句仍然不许合并**——这是新写的 `_group_ok` 最容易
    #    破坏的一条（「字幕也要保持断句的完整性，不要多也不要少」）
    assert shown("先看一眼签表。这是澳网女单签表的一角。") == [
        "先看一眼签表", "这是澳网女单签表的一角"]
    # 而句内的短片段照旧并得动（同一条规矩的另一头，别一起收紧）
    assert shown("对手排在115位到455位之间，正赛，她一场没赢过。") == [
        "对手排在115位到455位之间", "正赛 她一场没赢过"]


def test_断点不许让非词边界赢过词边界():
    """`_best_break` 里那几个分数是一个**调好的平衡**，动它之前先读这条。

    2026-08-31 我把同档内的取舍从 `+ i` 换成一个 [0,90] 的「越均分越好」，
    全库孤屏从 69 再降到 59（多消掉 10 处）——代价是**四条把词劈开**，而 `_best_break` docstring
    开头那条「哪怕上一行短一点」正是反过来做过一版才定下来的：

        贝莱克一路稳扎稳打建 ｜ 立起5比1的领先    「建立」
        本西奇熬了3小时20 ｜ 四分钟才拿下汤森德   「二十四分钟」劈成 20 和四
        首盘她一度让汤森德打 ｜ 出5比2的领先      「打出」
        一记救球让整个蒙特利 ｜ 尔一起站了起来    「蒙特利尔」

    根子是量级：孤行罚分 −95 把 `bonus=1` 的候选从 100 拉到 5，此时它和
    `bonus=0` 只差 5 分——`+ i` 最多 20 但**跨不过一个边界档**（100），
    90 分的均分项跨得过去。

    所以这条判据钉的是**不变量**，不是某个具体的分数：**只要还有 bonus>0 的
    合法候选，就不许选 bonus==0 的**。谁再想动那几个数，先让这条绿。

    ⚠️ **它只钉四个手挑的句子，覆盖不了全库**——上面那四条劈词里只有两条在
    这四个里。全库那一半归 `test_断行的硬切不许悄悄挪位置`，两条一起看才够。

    两个方向反向验证过：把 `+ i` 换成 `90*(1-|w-target|/16)` 的均分项 → 红在
    ①（「本西奇」那句切在非边界）；把孤行罚分从 95 提到 200 → 红在同一头
    （罚分大到把边界档整个吃掉，也会让非边界赢）。
    """
    from tennislive.video import explainer as E

    def first_cut(text: str) -> int:
        return E._best_break(E.readable(text))

    # 逐个候选算一遍：有 bonus>0 的合法位置时，选中的那个必须也 bonus>0
    for text in ("本西奇熬了三小时二十四分钟才拿下汤森德",
                 "正赛首轮两盘击败当届温网冠军莱巴金娜",
                 "代表亚洲国家的男子球员唯一一次打进大满贯单打决赛",
                 "首盘她一度让汤森德打出五比二的领先"):
        t = E.readable(text)
        cut = first_cut(text)
        legal = [i for i in range(1, len(t))
                 if E._sub_width(t[:i]) <= E._SUB_MAX
                 and E._sub_width(t[:i]) >= E._SUB_MIN_AT_BOUNDARY
                 and not (E._break_bonus(t, i) <= 0
                          and E._sub_width(t[:i]) < E._SUB_SOFT)]
        if not any(E._break_bonus(t, i) > 0 for i in legal):
            continue                      # 这一句真的没有词边界可用，跳过
        assert E._break_bonus(t, cut) > 0, (
            f"① 切在了非词边界：{t[:cut]!r}｜{t[cut:]!r}——"
            f"有 bonus>0 的候选却没选（分数的量级被谁改动了？"
            "孤行罚分 −95 之后一个边界档只剩 5 分，别让别的项跨过去）")

    # ② 而「宁可孤行也不劈词」那一头照旧：这一句唯一的边界必然留下 3 字的尾巴
    assert [s for _, _, s in E.subtitle_lines(
        E.readable("本西奇熬了三小时二十四分钟才拿下汤森德"))] == [
        "本西奇熬了三小时24分钟才拿下", "汤森德"]


def test_断行的硬切不许悄悄挪位置():
    """全库每一条超宽子句今天断在哪儿，冻结在
    `tests/fixtures/subtitle_hard_cuts.json` 里——**动了断行算法，这条会逐条
    告诉你哪些句子的断点挪了**。

    来路（2026-08-31）：我改了 `_best_break` 的分数，**只拿四个例子对比过就
    合并了**。事后手工跑一遍全库 before/after 才看见，那次改动把三条**词劈开**
    了（「本西奇熬了3小时20 ｜ 四分钟」「首盘她一度让汤森德打 ｜ 出5比2的领先」）。
    上一条判据（`test_断点不许让非词边界赢过词边界`）是那次的产物，可它只钉四个
    手挑的句子——**而我改坏的那三条，两条不在那四个里**。这一条是把那次手工
    diff 变成机器做的。

    ⚠️ **它不是一条内容闸，是一条算法闸**：表按**子句原文**认领，所以

        新写一条 spec              → 新子句不在表里，跳过，**不红**
        改一句旁白                 → 老子句消失、新子句未知，**不红**
        动 `_best_break` 的分数    → 表里的句子断点挪位置，**当场红**

    这一点是故意的：CLAUDE.md 早定过「超宽子句只报不拦」（做成硬闸会把一批
    已发的好 spec 挡住），所以这条判据一个字都不许去管新内容。

    改对了要重新冻结（**先 `--diff` 逐条看过**，尤其「从词边界挪到了非词边界」
    那几条）：

        python3 tools/freeze_subtitle_cuts.py --diff
        python3 tools/freeze_subtitle_cuts.py

    ⚠️ 报告里那个 `❌` **只是提示不是判决**：`_SUB_AFTER` 那张词尾表很粗，
    bonus==0 不等于真把词劈开（那次 7 条挂 ❌，真劈词的只有 4 条）。逐条读，
    别照着标记数数。

    ⚠️ 末尾那句 `assert checked >= 100` 是**判据自己的判据**：spec 目录挪走、
    `_clause_spans` 改了口径、`readable()` 换了写法——这些都会让这条测试
    校到 0 条然后安安静静地绿，而那和「全都没挪」长得一模一样。
    """
    import json as _json
    from tennislive.video import explainer as E

    frozen = _json.loads(
        (E._REPO / "tests" / "fixtures" / "subtitle_hard_cuts.json").read_text(
            encoding="utf-8"))
    assert frozen, "冻结表是空的——判据没有主语了"

    checked = 0
    moved: list[str] = []
    for spec_path in sorted((E._REPO / "specs" / "reels").glob("*.json")):
        spec = _json.loads(spec_path.read_text(encoding="utf-8"))
        for seg in spec.get("segments", []):
            text = seg.get("narration") or ""
            if not text.strip():
                continue
            shown = E.readable(text)
            for lo, hi in E._clause_spans(shown):
                clause = shown[lo:hi]
                if E._sub_width(E._sub_display(clause)) <= E._SUB_MAX:
                    continue
                if clause not in frozen:
                    continue          # 新写的子句没有冻结值，不管
                checked += 1
                cut = E._best_break(clause)
                if cut == frozen[clause]:
                    continue
                was, now = frozen[clause], cut

                def _show(k: int) -> str:
                    edge = "" if E._break_bonus(clause, k) > 0 else "  ⚠️ 非词边界"
                    return (f"{E._sub_display(clause[:k])} ｜ "
                            f"{E._sub_display(clause[k:])}{edge}")

                worse = (E._break_bonus(clause, was) > 0
                         and E._break_bonus(clause, now) <= 0)
                moved.append(
                    f"\n  {spec_path.stem}"
                    f"{'  ❌ 从词边界挪到了非词边界' if worse else ''}"
                    f"\n    旧：{_show(was)}\n    新：{_show(now)}")

    assert not moved, (
        f"断行算法改了，{len(moved)} 条子句的断点挪了位置："
        + "".join(moved)
        + "\n\n看过并且确实改好了，就重新冻结："
          "\n  python3 tools/freeze_subtitle_cuts.py --diff"
          "\n  python3 tools/freeze_subtitle_cuts.py")
    assert checked >= 100, f"只校到 {checked} 条超宽子句，判据失效了"


def test_断句的两条软报告接在dry_run上():
    """机器改不掉、只能改文案的两条，dry-run 要报出来（写 spec 那一刻看见，
    不是渲完一趟才看见）：

    - **孤屏**：同一句被切成「一行贴满 + 一行三两个字」，后半是半截话
    - **连逗号**：一句串四个以上逗号——逗号只给短停，连着四个等于没停
      （CLAUDE.md「停顿全部来自标点」量过的四类错之一）

    两条都**只报不拦**：一句话的落点本来就常常是短的，做成硬闸会把一批已发的
    好 spec 挡住（和 `overwide_clauses` 同一个口径）。

    ⚠️ 判「隔没隔着句号」两处共用 `crosses_hard_break`——`subtitle_lines` 拿它
    决定能不能跨句合并，报告拿它分「半截话」和「一句短话」。写两处必分叉，
    而分叉的样子是「报出来的和实际切出来的不是同一批」。
    """
    from pathlib import Path

    from tennislive.video import explainer as E

    # crosses_hard_break 自己：句号那一档隔开算跨句，逗号不算
    assert E.crosses_hard_break("先看签表。这是澳网", 5, 6)
    assert not E.crosses_hard_break("第四盘，纳沃内连赢五局", 3, 4)

    # 接线：dry-run 真的调这三样（写出来没人用是这个仓库的常客）
    body = Path("tools/build_match_reel.py").read_text("utf-8")
    for name in ("crosses_hard_break(readable(", "subtitle_lines(readable(",
                 "_SUB_LONELY"):
        assert name in body, f"dry-run 没接上 {name}"
    assert "串了四个以上逗号" in body


def test_没有词边界也要有字幕(tmp_path):
    """拿不到 WordBoundary 就按字数分——不完美，但绝不能整条片子没字幕。"""
    import pytest

    from tennislive.video import explainer as E

    text = "他说过一句话：我其实还想继续打。三十六岁，能伤的地方几乎伤了个遍。"
    cues = E.subtitle_cues(text, 10.0, boundaries=(), offset=0.6)
    assert len(cues) >= 2
    assert cues[0][0] == pytest.approx(0.6)          # 片头静音推过
    assert cues[-1][1] == pytest.approx(10.6)        # 收在音频末尾
    for (s1, e1, _), (s2, _, _) in zip(cues, cues[1:]):
        assert s1 < e1 and e1 <= s2 + 1e-6, (s1, e1, s2)

    # 有词边界时按它对齐，不再按字数猜——**正好压在标记上的那一行拿到标记的
    # 时刻，中间的按字数插值**。字幕改成一句一行之后行变密了，同一对标记之间
    # 经常落进两三行；沿用前一个标记的话它们会拿到同一个起始时刻，两条字幕在
    # 时间轴上重叠，libass 会同时画出来。
    marks = [{"offset": 0, "duration": 5_000_000, "text": "他说过一句话"},
             {"offset": 60_000_000, "duration": 5_000_000, "text": "三十六岁"}]
    aligned = E.subtitle_cues(text, 10.0, boundaries=marks)
    at_mark = text.index("三十六岁")
    lines = E.subtitle_lines(text)
    for (start, _, _), (a, _, _) in zip(aligned, lines):
        if a == at_mark:
            assert start == pytest.approx(6.0), aligned
        # 插值出来的时刻要落在两个锚点之间，不能倒退也不能越过。
        assert 0.0 <= start <= 10.0, aligned
    # 谁也不许和上一条重叠。
    for (_, e1, _), (s2, _, _) in zip(aligned, aligned[1:]):
        assert e1 <= s2 + 1e-6, aligned


def test_字幕烧在下边条里不压画面(tmp_path, monkeypatch):
    """3:4 的卡居中在 9:16 上，上下各空 240px——字幕丢进下边条，画面一个像素不动。

    盯住样式里的两个数：Alignment=2（贴底居中）和 MarginV，两者加上字号必须
    留在 240px 的黑边内。字压到照片上，等于把「图不好看就加字」那条错误
    重犯一遍。
    """
    from pathlib import Path as _Path

    from tennislive.video import explainer as E

    calls: list[list[str]] = []

    def runner(cmd, **kw):
        calls.append(list(cmd))
        if "ffprobe" in cmd[0]:
            return type("R", (), {"stdout": "8.000\n"})()
        _Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"stdout": ""})()

    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    slides = [tmp_path / f"s{i}.png" for i in range(2)]
    audios = [tmp_path / f"a{i}.mp3" for i in range(2)]
    for p in slides + audios:
        p.write_bytes(b"x")

    E.assemble_explainer_video(
        slides, audios, tmp_path / "out.mp4", runner=runner,
        captions=["这一站他要靠一张外卡才能进正赛。", "一场首轮，装着一代人的交接。"],
    )
    graph = calls[-1][calls[-1].index("-filter_complex") + 1]
    assert graph.count("subtitles=") == 2, graph

    first = (tmp_path / "sub_00.ass").read_text(encoding="utf-8")
    # 字号得有个参照系。写成 SRT 时 ffmpeg 按 libass 默认的 384×288 画布转换，
    # 再拉到 1080×1920——字号 52 落到画面上成了三百多像素，四个字盖住整张卡。
    # 所以 PlayRes 必须就是真实画布，字号才等于真实像素。这一条是烧出第一帧
    # 亲眼看见才发现的，滤镜链本身一点问题都没有。
    assert f"PlayResX: {E.VIDEO_W}" in first and f"PlayResY: {E.VIDEO_H}" in first
    assert "Alignment" not in first.split("[Events]")[1]  # 样式只在 Style 行里定义
    assert f",{E._ASS_ALIGN},{E._ASS_MARGIN_H},{E._ASS_MARGIN_H},{E._ASS_MARGIN_V},1" in first

    # 第一段被片头静音推过。
    assert "Dialogue: 0,0:00:00.60," in first, first[-300:]
    assert "外卡" in first


def test_没有旁白的那一段不挂字幕(tmp_path, monkeypatch):
    """空旁白挂个空字幕文件，ffmpeg 会当成错误——干脆不挂。"""
    from pathlib import Path as _Path

    from tennislive.video import explainer as E

    calls: list[list[str]] = []

    def runner(cmd, **kw):
        calls.append(list(cmd))
        if "ffprobe" in cmd[0]:
            return type("R", (), {"stdout": "3.000\n"})()
        _Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"stdout": ""})()

    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    slide, audio = tmp_path / "s.png", tmp_path / "a.mp3"
    slide.write_bytes(b"x")
    audio.write_bytes(b"x")

    E.assemble_explainer_video([slide], [audio], tmp_path / "one.mp4",
                               runner=runner, captions=["   "])
    graph = calls[-1][calls[-1].index("-filter_complex") + 1]
    assert "subtitles=" not in graph


def test_末屏那一问不能是封面那一问的回声():
    """一头一尾问同一个问题，等于白留一屏。

    踩过两次：商竣程那条封面问「锦织圭的最后一年，谁来接？」，末屏又问
    「锦织圭之后，亚洲男网谁来接？」；屋顶那条封面问「温网的屋顶，谁说了算？」，
    末屏还问「关屋顶是谁说了算？」。末屏那一问是换评论区的唯一抓手，
    它要开一扇新门，不是把封面的话再说一遍。

    判据用字集重合度，不逐字比对——两句话措辞不同、问的是同一件事，
    正是这条要拦的情形。
    """
    from tennislive.video import explainer as E

    drop = set("的了是在有和与也都就还你我他她它们这那什么吗呢啊，。？！、：；—…「」《》")

    def chars(text: str) -> set[str]:
        return {c for c in text if c not in drop and not c.isspace()}

    for slug in E._SCRIPTS:
        segs = E.explainer_script(find_story_by_slug(slug))
        closer = (segs[-1].question or "").strip()
        if not closer:
            continue
        cover = chars(f"{segs[0].title}{segs[0].question or ''}")
        tail = chars(closer)
        shared = cover & tail
        ratio = len(shared) / len(cover | tail)
        assert ratio < 0.5, (
            f"{slug} 末屏那一问和封面重了（{ratio:.0%}）："
            f"封面「{segs[0].title}」／末屏「{closer}」"
        )


def test_字幕里的数字用阿拉伯数字():
    """屏幕上「19 岁」比「十九岁」好读，但只在它真的是个数字的时候。

    旁白里写「二〇二六」「六比四」是给合成器定读法用的，那份不能动——所以
    换算只作用在**显示的那一份**上，而且要挑得住这些坑：

    - 「唯一一次」里连着两个「一」，按数字读就成了「唯 11 次」
    - 「一场首轮」「两盘」不是在数数
    - 「第二盘」「第三轮」「第一次」是序数，中文更顺；「世界第四」是排名，要写成数字
    - 「七十万英镑」得在「万」处收住，不然变成 700000
    """
    from tennislive.video.explainer import arabic_numerals as A

    assert A("二〇一四年美网") == "2014年美网"
    assert A("一九八九年十二月生") == "1989年12月生"
    assert A("六比四击败锦织圭") == "6比4击败锦织圭"
    assert A("三十六岁") == "36岁"
    assert A("七十万英镑") == "70万英镑"
    assert A("世界第四百六十九") == "世界第469"
    assert A("生涯最高的世界第四") == "生涯最高的世界第4"
    assert A("二十八局里赢到十二局") == "28局里赢到12局"
    # 「天」也算单位：字幕里「8月2日」和「三天前」同句出现过，一半阿拉伯
    # 一半汉字，账号所有者一眼看出来。「一天」「第二天」不受影响。
    assert A("三天前华盛顿首轮") == "3天前华盛顿首轮"
    assert A("四天前她升到生涯最高") == "4天前她升到生涯最高"

    # 不能碰的
    assert A("唯一一次打进大满贯单打决赛") == "唯一一次打进大满贯单打决赛"
    assert A("一场首轮，装着一代人的交接") == "一场首轮，装着一代人的交接"
    assert A("两盘，都是六比四") == "两盘，都是6比4"
    assert A("第二盘他化解了两个破发点") == "第二盘他化解了两个破发点"
    assert A("那是他第一次遇上") == "那是他第一次遇上"
    assert A("有一天她会回来") == "有一天她会回来"
    assert A("第二天她拿了冠军") == "第二天她拿了冠军"

    # **「抢七」是术语不是数字，而它后面常常紧跟比分。** 贪婪的比分匹配会把
    # 「抢七七比九」里的两个「七」一起吃掉，输出「抢7比9」——「抢七」塌成
    # 「抢」，屏幕上是个错字。黄泽林那条片子渲出来才看见（第 78 秒那行字幕），
    # 而语音一直是对的，所以只查旁白原文永远发现不了。
    assert A("六比七，抢七七比九") == "6比7，抢七7比9"
    assert A("抢七比分是七比九") == "抢七比分是7比9"
    # 单独的「抢七」本来就没事，一起钉住，免得修法把它带坏
    assert A("这一盘他硬生生拖进了抢七") == "这一盘他硬生生拖进了抢七"
    assert A("抢七打到七平") == "抢七打到七平"

    # **日期不许半中半洋。** 「号」和「点」原来不在量词表里，于是「八月二号」
    # 只换掉前半截，屏幕上是「8月二号」；「凌晨三点五十分」出来是「3点」没换、
    # 「50分」换了。两处都出现在伊埃拉对大坂那条片子最要紧的两句上——开球时刻
    # 和决赛时刻——而它**不报错**：换算成功了，只是换了一半。
    assert A("北京时间八月二号凌晨三点五十分") == "北京时间8月2号凌晨3点50分"
    assert A("北京时间八月三号零点") == "北京时间8月3号0点"
    assert A("三号种子大坂直美") == "3号种子大坂直美"
    # 「点」不能误伤：这几个词里的「点」前面不是数字，或者压在裸「一/两」的豁免上
    assert A("三个破发点她全救了") == "3个破发点她全救了"
    assert A("四十比零，三个赛点") == "40比0，3个赛点"
    assert A("差一点就破了") == "差一点就破了"
    assert A("两点之间") == "两点之间"


def test_字幕待在3比4画面里(): 
    """两头都有 UI，所以字幕必须待在**卡片内部**，而不是画布的边条里。

    走过两版弯路，都是量真成片量出来的：

    1. 贴画布最底（`MarginV=30`）——字幕像素落在 y 1849–1882，离底边只有 38px，
       被小红书/抖音的底部文案区和 home 指示条盖住
    2. 把整张卡抬到 `CARD_TOP=88`、字幕塞进变宽的下边条——底下躲开了，卡片顶上
       那行「网球时差 · 开球之前」又钻进了 app 顶部的返回键/状态栏

    答案不是挪卡片，是把卡上的文字块往上收，在卡片里腾一条出来。所以这条测试盯的是
    **字幕的上下沿都在卡片内**，以及它和卡上文字块不打架。
    """
    from tennislive.video import explainer as E

    card_top, card_bottom = E.CARD_TOP, E.CARD_TOP + E.CARD_H
    copy_bottom = card_bottom - E.CARD_COPY_BOTTOM      # 卡上文字块的下沿
    top = E._ASS_MARGIN_V
    one, two = top + E._ASS_NUM_SIZE, top + E._ASS_NUM_SIZE * 2

    assert E.CARD_TOP == (E.VIDEO_H - E.CARD_H) // 2, "卡片要居中，两头才都躲得开 UI"
    assert E._ASS_ALIGN == 8, "上锚，一行两行才从同一条线往下长"

    assert top > copy_bottom, "字幕压到卡上的要点了"
    assert two <= card_bottom, "字幕掉出 3:4 画面，会被 app 底部盖住"
    assert card_top + E.CARD_H * 0.75 < top, "字幕爬得太高，挡住画面主体"


def test_一行字幕待在左右两条边栏之间():
    """字幕横过去会被 app 右边那一列按钮盖住，所以左右要留够，而且**只排一行**。

    小红书/抖音在右侧压着点赞、收藏、评论、分享一列，约占屏宽 15%；我们的字幕
    正落在它的高度上。所以一行的最大宽度不是拍出来的，是从边距倒推的——
    改字号或改边距，`_SUB_MAX` 必须跟着算，否则字就伸到按钮底下去了。
    """
    from tennislive.video import explainer as E

    usable = E.VIDEO_W - 2 * E._ASS_MARGIN_H
    # 一个汉字占 FontSize/1.46，不是 FontSize——量出来的，别按字号直接算。
    widest = E._SUB_MAX * E._ASS_SIZE / E._ASS_CJK_RATIO + 2 * 3
    # 一格＝一个汉字；数字/西文按 0.68 格算，已经含了单独放大那一档。
    assert widest <= usable, f"一行最宽 {widest}px，可用只有 {usable}px"
    assert E._ASS_MARGIN_H >= 0.13 * E.VIDEO_W, "右边那一列按钮会盖住字幕"

    # 每条字幕都排得下一行——真排到两行就说明切行那步漏了。
    for slug in E._SCRIPTS:
        for seg in E.explainer_script(find_story_by_slug(slug)):
            for _, _, shown in E.subtitle_lines(E.readable(seg.narration)):
                assert E._sub_width(shown) <= E._SUB_MAX, f"{slug}：{shown}"


def test_数字和汉字看起来是一家的():
    """同一个字体文件，但思源黑体的西文比汉字矮 17%（墨高 52 : 63），并排放着
    像换了一种字体。拿成片里的「6」和 NotoSansCJK-Bold 逐像素比对过——**字体本来
    就是同一个**，差的是西文画得小。所以数字和西文单独放大一档。

    全角数字试过，不行：思源的全角只是把同一个字形塞进全角框，字没变粗，
    「2026」反而散成「２ ０ ２ ６」。
    """
    from tennislive.video import explainer as E

    out = E._ass_text("曾经的世界第4，现在世界第464")
    assert out.count(f"{{\\fs{E._ASS_NUM_SIZE}}}") == 2, out   # 两段数字各套一次
    assert out.count(f"{{\\fs{E._ASS_SIZE}}}") == 2, out       # 每段后面都收回来
    assert "第4，" not in out and "第464" not in out, "数字没被套上"
    assert "曾经的世界第" in out and "，现在世界第" in out, "汉字被动过"

    # 西文缩写同理，不然「ATP」也比旁边的汉字矮一截。
    assert f"{{\\fs{E._ASS_NUM_SIZE}}}ATP{{\\fs{E._ASS_SIZE}}}" in E._ass_text("一个 ATP 冠军")

    # 放大之后更宽了，行宽模型要跟着——按 0.5 估会宽出小半个字。
    assert E._sub_width("2026") > 2.5


def test_成片链接和图片走同一条_CDN(tmp_path):
    """⚠️ 2026-08-13 起这条钉的是**老路那一支**：没有 render.json 时退回 jsDelivr。

    账号所有者当天定了「所有视频统一走 Release 路线」，新片子的成片链接从
    render.json 的 video_url 读（判据在
    test_推送里的成片链接优先读render_json的video_url）。老路**不许删**：
    存量已发的包（成片还在 git 里、jsDelivr 链接已经发进微信）重推时靠它
    拿到当年那条链接。下面这段当年的账没过期，留着：

    视频链接原来指向 `github.com/<repo>/raw/main/…`，它 302 跳到
    raw.githubusercontent.com——那台机器国内既没有节点也没有 CDN，点开要等很久。
    同一封信里的图片一直是好的，因为图片走 jsDelivr（Cloudflare 边缘）。

    写成 `@main` 还有第二层用处：`pin_asset_revision` 只认 jsDelivr 的 `@main`，
    换过去之后视频会和图片**一起**被钉到本次 commit 上。钉住的链接 jsDelivr 给的是
    immutable + 一年 TTL；而且成片被下一次生成覆盖之后，老推送里的链接仍然指向
    当初那一版。

    outdir 用 tmp_path（**不放 render.json**＝存量包的样子），不用仓库里真的
    `output/…`——CI 的稀疏检出没有 output/，而本地那格哪天多出一份带
    video_url 的 render.json，这条测试就会在两台机器上走两条路。
    """
    import datetime

    from tennislive.render.pushmsg import pin_asset_revision
    from tennislive.video import explainer as E

    outdir = tmp_path / "output/2026-07-27/explainer/shang-nishikori"
    outdir.mkdir(parents=True)
    segs = E.explainer_script(find_story_by_slug("shang-nishikori"))
    html = E.explainer_push_html(
        segs, outdir, date=datetime.date(2026, 7, 27), xhs_text="测试文案")

    assert "/raw/main/" not in html, "视频还在走 raw.githubusercontent"
    urls = [u for u in html.replace("'", '"').split('"') if u.endswith("explainer.mp4")]
    assert urls, "推送里没有成片链接"
    from tennislive.cdn import jsdelivr_host

    assert urls[0].startswith(
        f"https://{jsdelivr_host()}/gh/{E._REPOSITORY}@main/"), urls[0]

    rel = "output/2026-07-27/explainer/shang-nishikori"
    rev = "37853825db235e7290df16fe890d00d556327d94"
    pinned = pin_asset_revision(html, rev)
    assert f"@{rev}/{rel}/explainer.mp4" in pinned, "视频没跟着图片一起钉版本"
    assert f"@{rev}/{rel}/slide_00.jpg" in pinned, "图片没被钉住"
    assert "@main/" not in pinned


def test_推送里的成片链接优先读render_json的video_url(tmp_path):
    """成片 2026-08-13 起一律走 Release、不进 git——链接的出处是 render.json。

    来路：账号所有者 2026-08-13「当前代码库太大了」「后面新的视频全部走新的
    架构不要放在代码里面」「包括后续所有的视频，制作的视频。都走统一的
    Release 路线」。量出来 .git 已 6.0 GB，其中 mp4 blob 4.93 GB。工作流传完
    Release 附件、Range 探活过之后把链接写进 render.json 再重渲 push.html——
    **优先级反过来的话**（有 video_url 仍拼 jsDelivr），新片子的 ▶ 按钮指向
    一条不在 git 里的 mp4，点开 404，而消息发出去收不回来。

    三支都要验：

    1. 有 video_url → 用它，jsDelivr 的成片链接一条都不许剩
       （图片照旧走 jsDelivr——统一 Release 管的是视频，不是图）
    2. `pin_asset_revision` 不许误改 Release 链接（`_JSDELIVR_MAIN_RE` 只认
       `*.jsdelivr.net/gh/…@main/`，github.com 匹配不上——这条是「确认过」，
       不是「应该不会」）
    3. 没有 render.json / 坏 JSON → 退回 jsDelivr 老路（存量包重推的兜底），
       坏 JSON 那支要出声——静默退回的样子和正常一模一样，而新片子的老路
       链接就是 404
    """
    import datetime

    from tennislive.cdn import jsdelivr_host
    from tennislive.render.pushmsg import pin_asset_revision
    from tennislive.video import explainer as E

    segs = E.explainer_script(find_story_by_slug("hawkeye"))
    release_url = (
        "https://github.com/robertyang87/tennislive/releases/download/"
        "explainer-hawkeye/explainer.mp4"
    )

    # ① 有 video_url：用 Release 链接，成片不再走 jsDelivr
    outdir = tmp_path / "with/output/2026-08-13/explainer/hawkeye"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text(
        json.dumps({"video_url": release_url, "video_bytes": 7_000_000}),
        encoding="utf-8")
    body = E.explainer_push_html(
        segs, outdir, date=datetime.date(2026, 8, 13), xhs_text="测试文案")
    assert release_url in body, "render.json 里的 video_url 没被用上"
    assert "explainer.mp4" not in body.replace(release_url, ""), (
        "有 video_url 时还在拼 jsDelivr 的成片链接——那条 mp4 不在 git 里，是 404")
    # 图片没跟着搬家：统一 Release 管的是视频
    assert f"https://{jsdelivr_host()}/gh/{E._REPOSITORY}@main/" in body, (
        "幻灯图片也离开 jsDelivr 了？统一 Release 只管视频")

    # ② pin_asset_revision 钉图片、不碰 Release 链接
    rev = "37853825db235e7290df16fe890d00d556327d94"
    pinned = pin_asset_revision(body, rev)
    assert release_url in pinned, "pin_asset_revision 把 Release 链接改坏了"
    assert f"@{rev}/" in pinned and "@main/" not in pinned, "图片没被钉住"

    # ③ 没有 render.json → 老路兜底；坏 JSON → 老路兜底而且要出声
    bare = tmp_path / "bare/output/2026-08-13/explainer/hawkeye"
    bare.mkdir(parents=True)
    body2 = E.explainer_push_html(
        segs, bare, date=datetime.date(2026, 8, 13), xhs_text="测试文案")
    assert f"https://{jsdelivr_host()}/gh/{E._REPOSITORY}@main/" in body2
    assert "explainer.mp4" in body2, "没有 video_url 时把成片链接整个丢了"

    import contextlib
    import io

    broken = tmp_path / "broken/output/2026-08-13/explainer/hawkeye"
    broken.mkdir(parents=True)
    (broken / "render.json").write_text("{oops", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        body3 = E.explainer_push_html(
            segs, broken, date=datetime.date(2026, 8, 13), xhs_text="测试文案")
    assert "explainer.mp4" in body3, "坏 JSON 时连兜底链接都没了"
    assert "读不出来" in buf.getvalue(), (
        "坏 JSON 静默退回了老路——它和「没写过」是两回事，要出声")


def test_每条片子的标签都放满五个():
    """小红书标签最多五个，**要放满**——账号所有者定的：「最多五个，以后要放满」。

    thiem-football 发出去时只带了三个。原因不是谁写少了，是它在 `_CAPTIONS`
    里**根本没有条目**，于是 hook 和 tags 一起退回默认，而当时的
    `_DEFAULT_TAGS` 只有三个。其余 15 条都各自写满了五个——所以光看别的条
    完全看不出这个洞，直到成品发出去才被一眼看见。

    所以这条测试查的是**渲染出来的那份文案**，不是 `_CAPTIONS` 的字面值：
    只查表就漏掉了「没有条目 → 走默认」这条路径，正是出问题的那条。
    兜底那组也一起查，它必须自己就是五个。
    """
    from tennislive.video.explainer import _DEFAULT_TAGS, explainer_xiaohongshu

    assert len(_DEFAULT_TAGS) == 5, (
        f"_DEFAULT_TAGS 只有 {len(_DEFAULT_TAGS)} 个。它是漏写条目时的兜底，"
        "自己不满五个，那条片子就会无声地少几个标签。")

    for slug in sorted(_SCRIPTED):
        story = find_story_by_slug(slug)
        text = explainer_xiaohongshu(story, explainer_script(story), "7.29")
        tags = [w for w in text.split() if w.startswith("#")]
        assert len(tags) == 5, (
            f"{slug} 的文案里有 {len(tags)} 个标签：{' '.join(tags)}\n"
            "小红书最多五个，要放满——在 _CAPTIONS 里给它写自己的五个。")
        assert len(set(tags)) == 5, f"{slug} 的标签有重复：{' '.join(tags)}"
        assert tags[:2] == ["#网球", "#网球时差"], (
            f"{slug} 前两个标签不是 #网球 #网球时差：{' '.join(tags)}")


def test_复制页探不到就不放那个按钮():
    """GitHub Pages 只服务 main，分支上生成的包点开是 404。

    微信那条消息**发出去就收不回来**，宁可不放按钮。判据是探一次：200 且
    Content-Type 是 text/html 才算数（soft-404 会返回 200）。
    """
    import datetime
    from pathlib import Path as _Path

    from tennislive.render.pushmsg import drop_dead_copy_button
    from tennislive.video import explainer as E

    outdir = _Path("output/2026-07-29/explainer/thiem-football")
    segs = E.explainer_script(find_story_by_slug("thiem-football"))
    body = E.explainer_push_html(
        segs, outdir, date=datetime.date(2026, 7, 29), xhs_text="测试文案")
    assert f"{outdir.as_posix()}/copy.html" in body, "渲染时就该带上复制页链接"

    kept, url = drop_dead_copy_button(body, probe=lambda _u: True)
    assert url and url.endswith("/copy.html"), "探到了却没报出是哪个 URL"
    assert "分别复制标题" in kept, "探到了反而把按钮摘了"

    dropped, url = drop_dead_copy_button(body, probe=lambda _u: False)
    assert url is None
    assert "copy.html" not in dropped, "探不到时仍然放了复制页按钮——那是个死链"
    assert "分别复制标题" not in dropped
    # 摘按钮不能连带把文案弄丢：正文得还在消息里，可以长按复制
    assert "测试文案" in dropped, "摘按钮的同时把正文也弄丢了，文案就没有出口了"
    # 别误伤别的按钮：成片链接和图片得原样留着
    assert "explainer.mp4" in dropped, "把成片链接一起摘掉了"
    assert dropped.count("slide_0") == body.count("slide_0"), "图片被误伤"


def test_探复制页的重试预算不许再退回四十秒():
    """闸门判得对，却因为等得太短把能用的按钮摘了——这是同一个坑的另一半。

    2026-08-02「保护排名」那条推送：成片 16:11:08 提交到 main，16:11:48 探到
    404，直到 16:2x 才 200——**Pages 花了 12 分钟以上**。而当时的预算是
    3 次 × 20 秒 = 40 秒，于是按钮被摘（run 30707429355）。闸门没判错，
    页面确实还没发布；错的是那句写在注释里、从没量过的「一两分钟」。

    40 秒对「合并很久之后再推」够用，对「合并完立刻重渲再推」永远不够：
    渲染→提交→探链接全在 50 秒内跑完，Pages 怎么都赶不上。

    这条不查具体数字（改 12×30 还是 20×20 都行），查的是**总预算**，
    因为会退化的正是它。
    """
    from tennislive.render import pushmsg

    budget = pushmsg._COPY_PAGE_ATTEMPTS * pushmsg._COPY_PAGE_RETRY_SECONDS
    # ⚠️ **这条断言原来写死 300 秒，而它自己的 docstring 就说「实测可以慢到
    # 12 分钟以上」——于是 12×30=360 轻松过关，按钮照样永远等不到。**
    # 判据比它引用的那个数还松，等于没装。现在从实测常量推，改不动一头
    # 不改另一头：`MEASURED_PAGES_BUILD_SECONDS` 是量出来最慢的那次成功构建。
    floor = pushmsg.MEASURED_PAGES_BUILD_SECONDS
    assert budget >= floor, (
        f"探复制页的总预算只有 {budget:.0f} 秒，而实测 Pages 建一次站要 "
        f"{floor:.0f} 秒（这个仓库 output/ 一 GB 多，每次重建整站）。"
        "窗口短于发布时间＝那颗按钮永远出不来，而且**不会报错**——"
        "日志里「取不到」和「还没发布」长得一模一样。"
    )
    # 但也不能无限等：出片那步已经花掉五分钟，工作流的 timeout 是 25 分钟。
    assert budget <= 900, f"预算 {budget:.0f} 秒太长，会把整个 run 拖进超时。"


def test_复制页可达但内容是旧版时也要摘掉按钮():
    """「能打开」不等于「是这一版」。

    2026-07-29 那条赛程推送踩了这个：新的 copy.html 只在特性分支上，而
    **Pages 只服务 main**，于是线上那份还是同一天早些时候生成的旧包。
    探到 200 就把按钮留下了，读者点开看到的是另一批场次——
    **这比死链更糟**：死链一眼能看出坏了，旧内容看着完全正常。

    所以判据从「HTTP 200 + text/html」加成「正文里有本地这一版的标题」。
    """
    import requests

    from tennislive.render.pushmsg import _probe_page, copy_page_fingerprint

    class _Resp:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __init__(self, text):
            self.text = text

    # ⚠️ **两边都用真的 `to_copy_page()` 渲，不许手搓假页面。**
    #
    # 这条测试原来喂的是自己写的 `<html><h1>标题</h1></html>`，于是它证明的是
    # 「函数能从 h1 里抠字」，而不是「真页面的 h1 是当期标题」——**而真模板里
    # `<h1>` 写死是「贴图发布文案」**（`pushmsg.py` 的 `<h1>贴图发布文案</h1>`）。
    # 结果：指纹对任何一天都返回同一句话，`expect in response.text` **恒真**，
    # 这道闸从上线那天起就没拦过任何东西，而测试一直是绿的。
    #
    # 又一次「断言全绿不等于页面对」，而这次的根子是**判据喂了假产物**。
    from tennislive.render.pushmsg import to_copy_page

    old_page = to_copy_page("7.29 今日赛程 | 郑钦文凌晨1点战伊埃拉\n\n正文甲")
    new_page = to_copy_page("7.29 今日赛程 | 王欣瑜战萨姆索诺娃\n\n正文乙")
    live_old, live_new = _Resp(old_page), _Resp(new_page)
    fresh = "7.29 今日赛程 | 王欣瑜战萨姆索诺娃"

    with mock.patch.object(requests, "get", return_value=live_old):
        assert not _probe_page("http://x/copy.html", attempts=1, expect=fresh), (
            "线上还是旧版，却判成可用——按钮会指向另一批场次")
        # 不给指纹时退回旧行为：只探可达。老调用方不该被这次改动带崩
        assert _probe_page("http://x/copy.html", attempts=1)

    with mock.patch.object(requests, "get", return_value=live_new):
        assert _probe_page("http://x/copy.html", attempts=1, expect=fresh)

    # 指纹必须**能区分两版**，而且必须真的出现在渲出来的页面里——
    # 取不到会让闸从「放行恒真」翻到「拦截恒真」，那是另一头的坏。
    import tempfile
    from pathlib import Path as _Path

    fingerprints = []
    for text, page in (("甲", old_page), ("乙", new_page)):
        path = _Path(tempfile.mkdtemp()) / "copy.html"
        path.write_text(page, encoding="utf-8")
        fp = copy_page_fingerprint(path)
        assert fp, f"{text} 版取不到指纹"
        assert fp in page, f"{text} 版的指纹「{fp}」不在页面里，探活永远匹配不上"
        fingerprints.append(fp)
    assert fingerprints[0] != fingerprints[1], (
        f"两版内容完全不同，指纹却一样（{fingerprints[0]}）——这道闸是恒真的")
    assert fingerprints[1] == fresh
    assert copy_page_fingerprint("/nowhere/copy.html") == "", "取不到时要退回空串"


def tmp_copy_page(body: str):
    import tempfile
    from pathlib import Path as _P

    path = _P(tempfile.mkdtemp()) / "copy.html"
    path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
    return path


def test_探活命中也要出声而且要报第几次(caplog):
    """命中那一路原来一个字都不打——于是「第 1 次就中」在日志里是**零行**。

    这是「只在失败时出声的检查没法证明它真的看过」的镜像版，而且更阴：

        第 1 次就中     零行
        探七次才中     六行 404，**没有任何一行说「后来中了」**
        这一步没跑     零行  ← 和第一种一模一样

    2026-08-04 我把「下条片子推送时看一眼是不是第 1 次就中」写进了 CLAUDE.md，
    引用的那句日志 `第 1 次探活：已是这一版的内容` **当时根本不存在**——
    判据引用了一个不存在的产物，正是这一轮要终结的那个毛病。

    报第几次不是装饰，它有判据：实测 dispatch 到部署完 19 秒
    （`MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS`）、探活间隔 30 秒，
    所以**正常就该是第 1 次**。第 2 次以上要当信号查，不是「Pages 今天慢」。
    """
    import logging

    import requests

    from tennislive.render.pushmsg import (
        MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS,
        _probe_page,
    )

    class _Resp:
        status_code = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "<html>正文</html>"

    class _Miss:
        status_code = 404
        headers = {"Content-Type": "text/html"}
        text = ""

    # ① 第 1 次就中：必须出声，而且说得出「第 1 次」
    with caplog.at_level(logging.INFO, logger="tennislive.render.pushmsg"), \
            mock.patch.object(requests, "get", return_value=_Resp()):
        assert _probe_page("http://x/copy.html", attempts=3, delay=0)
    hit = [r for r in caplog.records if "探活命中" in r.getMessage()]
    assert hit, (
        "命中之后一个字都没打——「第 1 次就中」和「这一步压根没跑」"
        "在日志里长得一模一样")
    assert "第 1 次" in hit[0].getMessage(), hit[0].getMessage()

    # ② 前两次不可达、第 3 次才中：要报出 3，而且要说明「本该是 1」，
    #    否则读日志的人得回头翻 CLAUDE.md 才知道这是异常
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="tennislive.render.pushmsg"), \
            mock.patch.object(requests, "get",
                              side_effect=[_Miss(), _Miss(), _Resp()]):
        assert _probe_page("http://x/copy.html", attempts=3, delay=0)
    late = [r for r in caplog.records if "探活" in r.getMessage()
            and "命中" in r.getMessage()]
    assert late, "探了三次才中，却没有任何一行说它后来中了"
    msg = late[0].getMessage()
    assert "第 3 次" in msg, msg
    assert late[0].levelno >= logging.WARNING, (
        f"第 3 次才中是异常，不该用 info 混在正常输出里：{msg}")
    assert f"{MEASURED_PAGES_DISPATCH_TO_LIVE_SECONDS:.0f}" in msg, (
        f"没把「本该多快」写进日志，读的人还得回头查常量：{msg}")


def test_每条探活路径都要报第几次():
    """自己推导，不维护白名单——第三条探活路径出现时它会替人记得。

    判据是结构性的：**凡是接 `attempts` 又真的 `requests.get` 的函数**，
    都是一条探活路径，都必须调 `_say_probe_hit`。手写名单会在有人新加一条
    探活时静默失效，而那正是这次出问题的形状（`live_copy_page_url` 和
    `_probe_page` 各写各的，其中一条忘了出声也没人知道）。
    """
    import ast
    import inspect

    from tennislive.render import pushmsg

    tree = ast.parse(inspect.getsource(pushmsg))

    def _calls(node, dotted: str) -> bool:
        want = dotted.split(".")[-1]
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            fn = sub.func
            if isinstance(fn, ast.Attribute) and fn.attr == want:
                return True
            if isinstance(fn, ast.Name) and fn.id == want:
                return True
        return False

    probes = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(a.arg == "attempts"
                for a in list(node.args.args) + list(node.args.kwonlyargs))
        and _calls(node, "requests.get")
    ]
    names = sorted(n.name for n in probes)
    # 判据自己的判据：主语没了要出声，而不是变成一条恒真的绿灯
    assert len(names) >= 2, f"探活路径少于两条，判据多半失效了：{names}"

    missing = [n.name for n in probes if not _calls(n, "_say_probe_hit")]
    assert not missing, (
        f"这些探活路径命中之后不出声：{missing}——"
        "「第 1 次就中」和「这一步没跑」会长得一模一样")


def test_复制页那道闸装在发的那一步不是渲的那一步():
    """第一版装错了位置，结果每次都把按钮拿掉。

    渲染（`tennislive explainer`）排在提交**之前**，那一刻 copy.html 还没进
    仓库，Pages 必然取不到——在渲染时探等于给所有推送判死刑，连 main 上本来
    能用的也一起摘掉。2026-07-29 蒂姆那条推送就是这么少了按钮的
    （run 30432435525：第 9 步渲染 07:41，第 11 步提交 07:43，第 12 步推送 07:44）。

    `publish pushplus` 跑在提交之后，那才是链接真正该可达的时刻。这条测试
    盯的是**位置**：生成流程里不许再出现探测调用，否则又会回到那个行为。
    """
    import inspect

    from tennislive import cli

    gen = inspect.getsource(cli.cmd_explainer)
    assert "live_copy_page_url" not in gen, (
        "生成流程里又探复制页了——那时文件还没提交，必然探不到，"
        "按钮会被无声摘掉。闸要装在 cmd_publish_pushplus 里。")

    send = inspect.getsource(cli.cmd_publish_pushplus)
    assert "drop_dead_copy_button" in send, "发送那一步没装这道闸"


# 稿子里**故意**用的写法，不在译名表里但也不是笔误。加进来之前先想清楚：
# 表里没有的名字，正确做法是补进 `zh/players.py`，这里只留「同一个人的另一种叫法」。
_ON_PURPOSE = {
    "维纳斯·威廉姆斯",   # 表里是「大威廉姆斯」；这条片子通篇叫她维纳斯，是写稿的选择
    # 伊埃拉的名（Alexandra Eala）。下面那条「少一个字」的判据会把它读成
    # 「亚历山德罗娃」——**两个都是真人，判据分不出来**，只能显式声明。
    # 它是全部 1106 段存量里唯一一条误报，所以那条判据是收得住的。
    "亚历山德拉",
    # `pegula-eala-dc2026-final.json`：赛事工作人员的名字（Christina/Kristina，
    # 两份 ASR 拼法不同，`_zh_why` 里已经写明「不是球员，译名表里没有」）。
    # 表里的「克里斯蒂安」是另一个真人（WTA 球员 Jaqueline Cristian），只差
    # 一个字——同一个「两个都是真人，判据分不出来」的形状，把 `specs/interviews/`
    # 接进这条测试时才第一次扫到（那批 spec 之前没被这条测试碰过）。
    "克里斯蒂娜",
    # `shelton-mensik.json`：Daniel Merida Aguilar 姓氏 Aguilar，表里唯一现成的
    # 参照是「Joaquin Aguilar Cardozo」→「阿吉拉尔·卡多佐」，同姓氏一致译成
    # 「梅里达-阿吉拉尔」。判据把它读成「阿吉亚尔」（表里另一位球员 Enzo
    # Aguiard 的译名，姓氏拼法不同、只是形近）——**两个都是真人，判据分不出来**，
    # 同一个形状。
    "阿吉拉尔",
    # ⚠️ **这一条不是人名，是地名**——法国的斯特拉斯堡（Strasbourg，WTA250 那一站）。
    # 判据按 4 个字的窗口扫，「斯特拉斯」和表里的「斯特恩斯」（Peyton Stearns）
    # 只差一个字，于是任何一条提到这一站的文案都会被误报。写这条豁免不是为了
    # 放宽判据：赛事所在的城市名迟早还会出现（这批片子里已经出现过多伦多、
    # 汉堡、蒙特利尔），而它们和球员译名共用一个字库，撞上是必然的。
    # `boisson-krueger.xhs.txt` 是第一条撞上的。
    "斯特拉斯堡",
    # ⚠️ **同一个形状第二次，同样是地名**——捷克的俄斯特拉发（Ostrava，
    # 博尔特 2026 年 2 月夺冠那一站）。四个字的窗口切出「斯特拉发」，
    # 和上面刚豁免的「斯特拉斯堡」只差一个字，于是它被读成「是不是想写
    # 斯特拉斯堡」。**两个都是真地名，判据分不出来。**
    # `boulter-volynets.xhs.txt` 是第一条撞上的。
    "俄斯特拉发",
}

#: **已经推过微信、名字却写错了的**。改不回来的那一半挂在这儿：视频里的旁白、
#: 封面和顶栏都把字烧进去了，改文本救不回来，而重渲＝同一场球发第二条片子。
#:
#: ⚠️ **还救得回来的那一半必须真的改掉**——`.xhs.txt` 是小红书正文，账号所有者
#: 复制的就是它，那是唯一还能编辑的出口（CLAUDE.md「已发的片子改文本不重渲…
#: 但正文是可以编辑的」）。所以这张表里**只许出现 `.json`**，出现 `.xhs.txt`
#: 就说明有人偷懒了。
#:
#: 只许减不许加，底下有自检。
_SHIPPED_TYPOS = {
    # 商竣程—达尔德里蒙特利尔 R3（e22a6e1）：两张译名表都是**达尔代里**。
    # 2026-08-07 01:36:54Z 已经推过微信（run 31138555626 第 30 步 success）。
    ("shang-darderi-montreal-2026.json", "达尔德里"),
}

#: **近似串那条查不到两三个字的名字**——三个字的窗口会撞上普通词，所以下面那条
#: 测试只查四个字以上。可表里有 210 个两三字的名字，「凯斯」就在里面：我把
#: Madison Keys 写成「基斯」，写进了王欣瑜那条的旁白和文案，**全绿照过、推到了
#: 微信**，屏幕上和配音里都是错的。
#:
#: 补不了射程，就补记性：**每次真写错一个，就把这一对钉在这儿。** 覆盖面窄，
#: 但零误报，而且每踩一次就长一条——和这个仓库里其它规矩一样。
_KNOWN_TYPOS = {
    "基斯": "凯斯",            # Madison Keys
    "雷巴金娜": "莱巴金娜",     # Elena Rybakina
    "里巴金娜": "莱巴金娜",     # 同上，更早的一次
    "奥斯塔片科": "奥斯塔彭科",  # Jelena Ostapenko
    # 2026-08-02 一天里写错四个人名。四个错各卡在不同的地方，值得分开记：
    #   蒙菲尔斯 → 孟菲尔斯      等长差一字，判据 ① 抓到了
    #   科梅萨纳 → 科梅萨尼亚    长度 4/5，判据 ① 抓不到 → 这次补了判据 ②
    #   波佩林   → 波皮林        三个字，在射程之外 → 只能钉在这儿
    #   费恩利   → 弗恩利        同上
    "波佩林": "波皮林",         # Alexei Popyrin
    "费恩利": "弗恩利",         # Jacob Fearnley
}

#: 正当地含着某个错字串的词，查之前先遮掉。「巴基斯坦」里就有「基斯」——
#: 短名做子串匹配必然会撞上这种，遮掉比放宽判据好。
#: 「斯图加特」（德国城市，Stuttgart）四个字里三个和「斯图尔特」（球员
#: Hamish Stewart，登记在 player_names_top500.json）重叠——`known` 并进
#: 排名快照之后才现形的假阳性，判据变准了、`_TYPO_SAFE` 跟着补一条。
_TYPO_SAFE = ("巴基斯坦", "斯图加特")


#: 「全汉字」和「全汉字或间隔号」的极大区间。
#:
#: 2026-08-14 profile 出来的：`test_人名要以译名表为准` 单跑 **255 秒**，占了
#: CI 关键路径（全量 `-n auto --dist loadfile` 396 秒）的大半。热点不是模糊匹配
#: 本身，是**那句逐窗口的字符范围检查**——
#:
#:     ncalls        tottime  cumtime  函数
#:     373,891,284   110.0s   256.4s   builtins.all          ← 字符范围检查
#:     704,601,834   138.2s   138.2s   <genexpr> 判据①的 all
#:     241,744,812    42.8s    42.8s   <genexpr> 判据②的 all
#:      34,402,718    33.5s    85.3s   builtins.sum          ← 过了闸才走到这儿
#:     （语料 3899 段 / 521,856 字，规范名 547 个，命中 5 条；总计 702s，
#:       上面这份是带 cProfile 的口径，裸跑 255s）
#:
#: `all` 被调了 **3.739 亿次**，而它只跟「这一段是不是全汉字」有关，**跟拿哪个
#: 名字去比一点关系都没有**——547 个名字每个都把同一个窗口重新验了一遍。
#: 所以提到外面：整段文本一次正则切出极大区间，窗口只在区间内滑。语义完全
#: 一样——原来那句 `all` 要求窗口整段都是汉字，等价于「窗口落在某个极大汉字
#: 区间里」，而遮罩用的全角空格（U+3000）本来就在这个范围外，照旧断开区间。
#:
#: ⚠️ 范围要和原来那两个条件**逐字对得上**：`"一" <= c <= "鿿"` 就是
#: U+4E00–U+9FFF，判据①另外放行间隔号，判据②不放行。写宽一个字符就是
#: 一条悄悄放行的假绿。
_CJK_RUN = re.compile("[一-鿿]+")
_CJK_DOT_RUN = re.compile("[一-鿿·]+")


def _typo_index(probes):
    """把 (比对串, 报出去的名字) 建成两把钥匙的索引：前两字、第 3-4 字。

    上面那条注释拆掉了「每个窗口验 547 遍字符范围」；这条拆掉剩下的那一半
    冗余——**每个窗口和 547 个名字逐个比一遍**。

    窗口和比对串恰好差一个字，那个字要么落在前两位、要么落在第 3 位往后：

    * 落在第 3 位往后 → **前两个字必然一模一样** → 「前两字」那张表查得到
    * 落在前两位     → **第 3、4 个字必然一模一样** → 「第 3-4 字」那张表查得到

    两支是穷尽的（差的那个字不落在前两位，就落在第 3 位往后），所以并起来
    **必然盖住所有真候选，一个都不漏**；查出来的假候选再逐字数一遍差多少
    剔掉，所以**也一个都不多**。比对串最短 4 个字（`canon` 就是这么筛的），
    两把钥匙各 2 个字，正好取得到。

    ⚠️ 一个名字可能同时被两把钥匙查到（差的那个字在第 5 位往后时，前两字和
    第 3-4 字都对得上）。`_near_misses` 里那句 `probe[:2] == head_key` 就是
    为这个——**不去重会把同一处报两遍**。
    """
    by_head, by_mid = {}, {}
    for probe, name in probes:
        by_head.setdefault(probe[:2], []).append((probe, name))
        by_mid.setdefault(probe[2:4], []).append((probe, name))
    return by_head, by_mid


def _near_misses(masked, run_re, index):
    """找出 `masked` 里和某个比对串**恰好差一个字**的窗口，产出 (窗口, 名字)。

    `run_re` 决定窗口允许哪些字符（见 `_CJK_RUN` / `_CJK_DOT_RUN`），
    `index` 是 `_typo_index` 建的那两张表。
    """
    by_head, by_mid = index
    hits = []
    for run in run_re.finditer(masked):
        seg = run.group()
        n = len(seg)
        # 比对串最短 4 个字，所以起点最远到 n-4；n < 4 时 range 直接是空的。
        for i in range(n - 3):
            head_key = seg[i:i + 2]
            for probe, name in by_head.get(head_key, ()):
                width = len(probe)
                if i + width > n:
                    continue        # 窗口伸出了这段区间，原来那句 all 也拦得住
                window = seg[i:i + width]
                if sum(a != b for a, b in zip(window, probe)) == 1:
                    hits.append((window, name))
            for probe, name in by_mid.get(seg[i + 2:i + 4], ()):
                if probe[:2] == head_key:
                    continue        # 已经在「前两字」那一支里数过，别数第二遍
                width = len(probe)
                if i + width > n:
                    continue
                window = seg[i:i + width]
                if sum(a != b for a, b in zip(window, probe)) == 1:
                    hits.append((window, name))
    return hits


def test_人名要以译名表为准():
    """人名不手打，以 `zh/players.py` 为准——这条写在 CLAUDE.md 里，仍然被违反了两次。

    把 Rybakina 写成「里巴金娜」发了出去（表里一直是**莱巴金娜**），把 Ostapenko
    写成「奥斯塔片科」（表里是**奥斯塔彭科**）。两次都不是不知道，是没查。所以
    落成测试。

    判据是**近似串**：先把文中所有规范名遮掉，再找剩下的、与某个规范名只差一个字的
    片段。这样「德约科维奇」不会因为内含「科维奇」而被误判成「约维奇」——不遮的话
    同样一批稿子会报出 61 条误报，遮完只剩 3 条，其中一条是真错。

    只查四个字以上：三个字的窗口会撞上大量普通词（「东西里挑」撞「西里奇」）。
    这意味着两三个字的名字写错了它挡不住——**表里没有的名字，仍然要自己补进表里**。
    """
    from tennislive.video import explainer as E
    from tennislive.zh import _ranked_player_names
    from tennislive.zh.players import PLAYER_ZH

    # 同一处漏洞的另一半（见 test_赛前片的封面要写清是哪一场 的注释）：
    # 只并旧表会漏掉只登记在 player_names_top500.json 里的名字，遮罩阶段
    # 遮不掉它们，也就防不住"表里明明有、却被判成手打错"的假阳性。
    known = sorted(
        set(PLAYER_ZH.values()) | set(_ranked_player_names().values()) | _ON_PURPOSE,
        key=len, reverse=True,
    )
    canon = [n for n in known if len(n) >= 4]

    def strip_known(text: str) -> str:
        for name in known:          # 长的先遮，短名才不会把长名切碎
            text = text.replace(name, "　" * len(name))
        return text

    # ① 等长、恰好差一个字：「里巴金娜」之于「莱巴金娜」
    index_same = _typo_index([(name, name) for name in canon])

    # ② 少一个字、其余至多差一个字：「科梅萨纳」之于「科梅萨尼亚」。
    #
    # 2026-08-02 补的。那天四个人名错，判据 ① 只拦住一个——**而我第一反应
    # 是「补编辑距离 ≤1 的增删」，量完才发现那也拦不住**：科梅萨纳到
    # 科梅萨尼亚的编辑距离是 **2**（改 纳→尼、再插 亚），不是 1。
    #
    # 先试过「共同前缀 ≥3」那种宽判据，全部 1106 段存量上报出 **33 条**，
    # 全是合法短称或另一个真人（维纳斯 / 克鲁兹 / 亚历山德拉）——判据宁可
    # 窄不可宽，扩大化的判据不吭声。收窄成这一条之后只剩 1 条误报，
    # 已声明在 `_ON_PURPOSE` 里。
    #
    # 极大 CJK 串试过，不行：中文没有词边界，整句话就是一个串。
    index_short = _typo_index([(name[:-1], name) for name in canon
                               if len(name) - 1 >= 4 and "·" not in name])

    bad = []

    def keep(msg: str) -> bool:
        return not any(f"{where}：「{wrong}」" in msg
                       for where, wrong in _SHIPPED_TYPOS)

    def scan(where: str, text: str) -> None:
        safe = text
        for word in _TYPO_SAFE:
            safe = safe.replace(word, "　" * len(word))
        for wrong, right in _KNOWN_TYPOS.items():
            if wrong in safe:
                bad.append(f"{where}：「{wrong}」写错了，表里是「{right}」")
        # ⚠️ 这里原来写的是 `strip_known(text)`——`_TYPO_SAFE` 遮的是 `safe`，
        # 而下面①②两条模糊匹配吃的却是没遮过 `_TYPO_SAFE` 的 `text`，等于
        # `_TYPO_SAFE` 只护住了 `_KNOWN_TYPOS` 那一半，模糊匹配这一半从没被
        # 遮过。「巴基斯坦」当年凑巧没撞上任何一个 canon 近似串，所以这个
        # 缺口一直没现形；`known` 并进 top500 表之后「斯图加特」撞上新收进来的
        # 「斯图尔特」才炸出来（见 `_TYPO_SAFE` 那条注释）。改成遮过的 `safe`。
        masked = strip_known(safe)
        # ① 允许间隔号（名字里有「维纳斯·威廉姆斯」这种），② 只认汉字——
        # 两条的字符范围原来各写在一句 `all(...)` 里，现在收进那两个正则，
        # 见 `_CJK_RUN` / `_CJK_DOT_RUN` 上面那段。
        for window, name in _near_misses(masked, _CJK_DOT_RUN, index_same):
            bad.append(f"{where}：「{window}」是不是想写「{name}」")
        for window, name in _near_misses(masked, _CJK_RUN, index_short):
            bad.append(f"{where}：「{window}」是不是想写「{name}」")

    # **「赛场之上」的 spec 和文案也要扫。** 这条测试原来只看解说片的脚本，
    # 于是 2026-07-29 我在 `eala-fernandez.xhs.txt` 里把 Rybakina 写成
    # 「雷巴金娜」（表里是**莱巴金娜**），全绿照过——**同一个名字，第三次写错**，
    # 前两次是「里巴金娜」和这次。判据早就写好了，只是没指到这批文件上。
    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        scan(path.name, path.read_text(encoding="utf-8"))
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") or {}
        texts = [cover.get("hook", ""), cover.get("winner", ""), cover.get("meta", "")]
        texts += list((cover.get("versus") or {}).get("names") or [])
        texts += [s.get("narration", "") for s in spec.get("segments") or []]
        # **推送那几栏也要扫。** `push.summary` / `push.lead` 是微信标题和正文
        # 第一行，发出去收不回来，而它们原来一个字都没被查过——名字写错在这儿
        # 和写在旁白里一样会发出去。`_` 开头的是注解，不扫。
        texts += [v for k, v in (spec.get("push") or {}).items()
                  if not k.startswith("_") and isinstance(v, str)]
        for text in filter(None, texts):
            scan(path.name, text)

    # **「赛后开麦」（`specs/interviews/`）也是一条会发出去的线，之前一直没被
    # 这条测试碰过。** 结构和 reels 不一样——台词在 `zh` 数组里，不在
    # `segments[].narration` 里——所以另开一段，不能直接并进上面那个循环。
    #
    # ⚠️ **起因是 `swiatek-shnaider-tor2026-qf.json` 把 Shnaider 写成「申拜德」
    # （表里是施奈德），但这条测试其实拦不住那一次。** 「施奈德」只有三个字，
    # 而上面那句 docstring 早写着「只查四个字以上：三个字的窗口会撞上大量普通词」——
    # 反向验证过（把「申拜德」注回一个**会被扫到**的字段，不是 `_note`），
    # 这条测试对它就是哑的，跟字段是不是 `_`开头没关系。三个字的名字写错了，
    # 还是只能靠写的时候自己 `player_zh()` 查一遍，测试防不住。
    # 这一段真正值回票价的是**四个字以上**的名字（下面反向验证抓到的
    # 「克里斯蒂娜」就是一个）。
    for path in sorted(Path("specs/interviews").glob("*.xhs.txt")):
        scan(path.name, path.read_text(encoding="utf-8"))
    # 草稿不会进入发布链；它只有机器转写/译文，尚未具备正式 spec 的内容字段。
    for path in sorted(p for p in Path("specs/interviews").glob("*.json")
                       if not p.name.endswith(".draft.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") or {}
        texts = [spec.get("event", ""), spec.get("winner", "")]
        texts += list(spec.get("zh") or [])
        texts += [v for k, v in cover.items()
                  if not k.startswith("_") and isinstance(v, str)]
        texts += [v for k, v in (spec.get("push") or {}).items()
                  if not k.startswith("_") and isinstance(v, str)]
        # `takeaway` 是 `{"close": {"point": ..., "ask": ..., "facts": [...]}}`
        # 这一层嵌套——不逐个键名硬编，免得以后加一张新卡（比如 `open`）又漏了。
        for card in (spec.get("takeaway") or {}).values():
            if not isinstance(card, dict):
                continue
            for k, v in card.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, str):
                    texts.append(v)
                elif isinstance(v, list):
                    texts += [s for s in v if isinstance(s, str)]
        for text in filter(None, texts):
            scan(path.name, text)

    for slug in E._SCRIPTS:
        opening = E._OPENINGS.get(slug) or {}
        texts = [opening.get("topic", ""), opening.get("narration", "")]
        for seg in E.explainer_script(find_story_by_slug(slug)):
            # 示意图里的名字是**画在屏幕上**的，一样要查——反向验证时才发现漏了：
            # 「莱巴金娜」第一处就在十冠那张图的 <text> 里。SVG 里的标记不会误报，
            # 因为窗口要求整段都是汉字。
            texts += [seg.title, seg.narration, seg.question or "", seg.label,
                      seg.diagram or "", *seg.points]
        for text in filter(None, texts):
            scan(slug, text)
    fresh = sorted({m for m in set(bad) if keep(m)})
    assert not fresh, "人名和译名表对不上：\n  " + "\n  ".join(fresh)

    # ⚠️ **豁免表要自证它豁免的是真的还在违规。** 一个写错的名字就是一盏永远
    # 亮着的绿灯——这个仓库为它栽过。
    seen = set(bad)
    stale = [(w, n) for w, n in _SHIPPED_TYPOS
             if not any(f"{w}：「{n}」" in m for m in seen)]
    assert not stale, (
        f"{stale} 已经不违规了（或者名字写错了），从 _SHIPPED_TYPOS 里删掉——"
        "这张表只许减不许加")


def test_人名近似匹配的索引和笨办法结果一样():
    """`_typo_index` / `_near_misses` 是上一条测试的加速索引，这条钉住它和
    「逐个名字滑窗口」那个笨办法**结果完全一样**。

    2026-08-14 加的。上一条原来单跑 **255 秒**，把 CI 关键路径（全量 396 秒）
    吃掉大半；换成两把钥匙查表之后 **1.6 秒**。而换掉的是**判据本身的实现**——
    判据悄悄变窄是这个仓库反复栽过的那种坏：它不报错，只是从此拦不住东西，
    而测试照样绿（「是不是这一版那道闸恒真了一个月」「碰巧对和真的接上了
    长得一模一样」）。所以拿笨办法当基准做差分，比的是**多重集**。

    ⚠️ **真语料上那条判据只命中 5 条，证不动「一般情况下也一样」。** 所以这里
    自己造语料，把两条判据的每一支都打满：改一个字的（判据①该报）、少一个字
    再改一个的（判据②该报）、差两个字的和原样的真名字（两条都不该报）、
    间隔号（判据①放行、判据②不放行）、遮罩用的全角空格，以及汉字区间两头
    的边界字符（U+4DFF / U+4E00 / U+9FFF / U+A000）——范围写宽一个字符，
    就是一条悄悄放行的假绿。
    """
    import random

    from tennislive.zh import _ranked_player_names
    from tennislive.zh.players import PLAYER_ZH

    known = sorted(
        set(PLAYER_ZH.values()) | set(_ranked_player_names().values()) | _ON_PURPOSE,
        key=len, reverse=True,
    )
    # 每种长度各取几个，外加全部带间隔号的——跑得快，又盖得住 4 字到最长的
    # 那个名字的每一档长度（长度只取一档的话，「窗口伸出区间」那一支就没样本）。
    canon, taken = [], {}
    for name in sorted(n for n in known if len(n) >= 4):
        if taken.get(len(name), 0) < 8 or "·" in name:
            canon.append(name)
        taken[len(name)] = taken.get(len(name), 0) + 1
    assert len({len(n) for n in canon}) >= 5, "长度盖得太少，差分没意义"
    assert any("·" in n for n in canon), "没有带间隔号的名字，判据①那一支没样本"

    def naive_scan(masked):
        """HEAD~ 的写法，逐字抄下来当基准。"""
        out = []
        for name in canon:
            width = len(name)
            for i in range(len(masked) - width + 1):
                window = masked[i:i + width]
                if not all("一" <= c <= "鿿" or c == "·" for c in window):
                    continue
                if sum(a != b for a, b in zip(window, name)) == 1:
                    out.append((window, name))
            short = width - 1
            if short < 4 or "·" in name:
                continue
            head = name[:short]
            for i in range(len(masked) - short + 1):
                window = masked[i:i + short]
                if not all("一" <= c <= "鿿" for c in window):
                    continue
                if sum(a != b for a, b in zip(window, head)) == 1:
                    out.append((window, name))
        return out

    index_same = _typo_index([(n, n) for n in canon])
    index_short = _typo_index([(n[:-1], n) for n in canon
                               if len(n) - 1 >= 4 and "·" not in n])

    def indexed_scan(masked):
        return (_near_misses(masked, _CJK_DOT_RUN, index_same)
                + _near_misses(masked, _CJK_RUN, index_short))

    cjk = [chr(c) for c in range(0x4E00, 0x4E00 + 300)]
    #: 汉字区间的两头、外面各一个，加上间隔号、遮罩用的全角空格、标点和拉丁字母
    edge = ["䷿", "一", "鿿", "ꀀ", "·", "　", "，", "A", " "]
    rnd = random.Random(20260814)      # 钉死种子：这条测试不许今天绿明天红

    def retype(name, k):
        """把 k 个字改到别的汉字上。"""
        chars = list(name)
        for pos in rnd.sample(range(len(chars)), min(k, len(chars))):
            chars[pos] = rnd.choice(cjk)
        return "".join(chars)

    # ⚠️ **两条判据的字符范围只差一个间隔号，而随机语料撞不出那个差别。**
    # 反向验证时逮到的：把判据②也换成放行间隔号的 `_CJK_DOT_RUN`（范围写宽
    # 一个字符，正是「悄悄放行的假绿」那一类），200 条随机语料**全绿**——
    # 因为要露馅得凑出「窗口里带一个间隔号、其余和 head 一字不差」这种形状，
    # 随机撞不到。所以这几条钉死，不靠运气：
    #
    #   `name[:-1] + "·"`  长度等于名字，只差最后一个字 → **判据①该报**（①放行间隔号）
    #   `head[:-1] + "·"`  长度等于 head，只差最后一个字 → **判据②不该报**（②只认汉字）
    corpus = []
    for name in canon[:40]:
        if "·" in name:
            continue
        corpus.append("的" + name[:-1] + "·" + "在")
        head = name[:-1]
        if len(head) >= 4:
            corpus.append("的" + head[:-1] + "·" + "在")
            corpus.append("的" + head[:2] + "·" + head[3:] + "在")

    fired_same = fired_short = 0
    for _ in range(200):
        parts = []
        for _ in range(rnd.randint(1, 6)):
            roll = rnd.random()
            if roll < 0.30:                      # 改一个字 → 判据①该报
                parts.append(retype(rnd.choice(canon), 1))
            elif roll < 0.50:                    # 少一个字再改一个 → 判据②该报
                name = rnd.choice(canon)
                parts.append(retype(name[:-1], 1) if len(name) > 4
                             else retype(name, 1))
            elif roll < 0.62:                    # 差两个字 → 两条都不该报
                parts.append(retype(rnd.choice(canon), 2))
            elif roll < 0.74:                    # 原样的真名字 → 不该报
                parts.append(rnd.choice(canon))
            elif roll < 0.88:
                parts.append("".join(rnd.choice(cjk)
                                     for _ in range(rnd.randint(1, 8))))
            else:
                parts.append("".join(rnd.choice(edge)
                                     for _ in range(rnd.randint(1, 4))))
        corpus.append("".join(parts))

    for text in corpus:
        baseline = sorted(naive_scan(text))
        assert baseline == sorted(indexed_scan(text)), (
            f"索引和笨办法对不上，语料是 {text!r}\n"
            f"  笨办法：{baseline}\n"
            f"  走索引：{sorted(indexed_scan(text))}")
        # 判据①的窗口和名字等长，判据②的窗口少一个字——分开数，见下。
        fired_same += sum(1 for w, n in baseline if len(w) == len(n))
        fired_short += sum(1 for w, n in baseline if len(w) == len(n) - 1)

    # ⚠️ **判据自己也要有判据。** 上面每一句断言的都是「两边一样」，而
    # 「两边都没报」同样满足它——语料要是造得不对题，这条测试会变成一盏
    # 恒真的绿灯（这个仓库为「断言恒真」栽过好几次）。
    #
    # ⚠️ 而**只数总条数是不够的**：判据①的样本比②多得多，光看总数，②那一支
    # 整个哑掉也照样过关。所以两支分开钉。实测（2026-08-14，钉死的种子，
    # 114 个名字盖住 4~16 字十档长度）**①188 条 / ②55 条**；门槛按数量级留，
    # 别贴着实测写——译名表长了短了这两个数会跟着动，而那不是回归。
    assert fired_same > 50, f"判据①只命中 {fired_same} 条，差分等于没比"
    assert fired_short > 15, f"判据②只命中 {fired_short} 条，差分等于没比"


def test_旁白不解说画面():
    """旁白不说「画面里是什么」。

    片子里图和话是两条腿：**画负责一眼看懂，话负责讲清楚**。旁白一开口描述画面，
    就等于把观众已经看见的东西再念一遍——占掉的是本该讲事实的时间，而看得见的人
    不需要，听不见画面的人（比如通勤时只听声音）也拿不到有用信息。

    改法不是删句子，是**把指画面的那半句去掉、把事实留住**：
    「画面里是 2026 年温网的莱巴金娜，你可以照着条文一条条对」→
    「2026 年温网的莱巴金娜，可以照着条文一条条对」。二十九句都是这么改的。

    卡上的要点不在这条管辖内：那儿的「图为 2022 年温网冠军莱巴金娜」是在**把年份
    写到画面上**，是另一条规矩要求的（旧照片必须标年份）。
    """
    import re

    from tennislive.video import explainer as E

    pointing = re.compile(r"画面(里|上|中|就是)|镜头(里|中)|图为|这张图|图片里|上图|下图")
    bad = []
    for slug in E._SCRIPTS:
        for seg in E.explainer_script(find_story_by_slug(slug)):
            for field, text in (("旁白", seg.narration), ("标题", seg.title),
                                ("末屏问", seg.question or "")):
                m = pointing.search(text or "")
                if m:
                    bad.append(f"{slug}/{seg.kind} 的{field}在解说画面："
                               f"「{m.group(0)}」→ {text[:36]}…")
    assert not bad, "旁白在解说画面：\n  " + "\n  ".join(bad)


def test_栏目名不能只活在代码里():
    """代码里印出去的栏目名，必须能在 docs/columns.md 找到。

    「昨日好球」那条线一度有四个名字同时在跑（值回放 / 值得回放 / 值得暂停 /
    昨日好球）。四个名字等于没有名字——这条盯的就是别再长出第五个。
    """
    doc = Path("docs/columns.md").read_text(encoding="utf-8")

    from tennislive.video.explainer import COLUMNS

    for name in COLUMNS:
        assert name in doc, f"COLUMNS 里的「{name}」没有写进 docs/columns.md"

    # 各生产线自带的栏目名（解说视频之外的那些线不共用 COLUMNS）。
    #
    # 原来这里扫的是 `_COLUMN_LABEL` 常量，而它只存在于「昨日一分」那条线；
    # 2026-07-31 那条线整个拿掉之后，扫描结果为空，这个判据自己的自检
    # （`assert labels`）当场报「判据失效了」——**它设计对了**，主语没了就出声，
    # 而不是变成一条恒真的断言。
    #
    # 换成还活着的主语：竖版短片的栏目名写在每条 spec 的 `cover.eyebrow` 里，
    # 海报台头和微信标题都从它来（见 `push_reel.column_of`）。
    import json  # noqa: PLC0415

    labels = {
        path.name: str((json.loads(path.read_text(encoding="utf-8")).get("cover")
                        or {}).get("eyebrow", "")).strip()
        for path in sorted(Path("specs/reels").glob("*.json"))
    }
    assert labels, "没扫到任何 spec 的栏目名，判据失效了"
    for source, name in labels.items():
        assert name, f"{source} 的 cover.eyebrow 是空的"
        assert name in doc, f"{source} 的栏目名「{name}」没有写进 docs/columns.md"


def test_新定的两个栏目写清了位置和承诺():
    doc = Path("docs/columns.md").read_text(encoding="utf-8")
    for name in ("赛场之上", "赛后开麦"):
        assert name in doc
    # 界线按时间划，不按深浅——这是选它的全部理由，丢了这句表就白排
    assert "打到握手为止" in doc
    assert "话筒递过来" in doc


def test_字幕里不写标点():
    """账号所有者：「以后字幕里的尽量不要用标点符号，可以切换下一页表达。」

    停顿本来就该由换页表达，一个逗号在屏幕上只是噪点。只留 `？！`——换页
    表达得了停顿，表达不了「这是一问」，末屏那一问少了问号就成了陈述句。

    ⚠️ 去标点只作用在**显示的那一份**。切子句、找断点仍然靠原文里的标点，
    先去掉就没有断点可依，又会退回「数满 16 个字一刀切」，把词劈成两半
    （「代表亚洲国家打／进大满贯」那次）。所以这条测试查的是 subtitle_lines
    的第三个返回值，不是它的输入。
    """
    from tennislive.video.explainer import _SUB_MAX, _sub_width, subtitle_lines

    banned = "。，、：；,…「」『』（）《》·—"
    for slug in _SCRIPTED:
        for seg in explainer_script(find_story_by_slug(slug)):
            for _, _, shown in subtitle_lines(seg.narration):
                hit = [c for c in shown if c in banned]
                assert not hit, f"{slug} 字幕里还有标点 {hit}：{shown}"
                # 合并两句时中间要留个空格，不能糊成一坨（「WC它是谁给的」）。
                assert "  " not in shown, f"{slug} 字幕里有连续空格：{shown}"
                assert shown == shown.strip(), f"{slug} 字幕两头有空白：{shown}"
                # 去标点之后仍然不能顶出左右两条边栏。
                assert _sub_width(shown) <= _SUB_MAX, f"{slug} 字幕超宽：{shown}"
                # 一闪而过的行读不到（时间轴最短只给 0.4 秒）。
                # 三个字是下限：左右两邻都已经排满时并不进去，只能
                # 自己站一行（roof 那条的「他赢了」）。再短就该改稿。
                assert len(shown) >= 3, f"{slug} 字幕太短会一闪而过：{shown}"


def test_去标点这条规矩是全站的不是解说片专属():
    """账号所有者补的那句：「字幕要应用到全局里。」

    先只改了解说片，于是「视频本地化」「大满贯竖版 v2」等线
    还在往画面上烧逗号句号。同一个账号出去的片子，字幕两种样子。

    规矩和实现收在 `video/subtitle_text.py`，写 ASS 的几条路径共用；这条测试盯的是
    「每条写 ASS 的路径都真的过了这一道」，而不是某一条的输出长什么样。
    """
    import inspect

    from tennislive.video import pipeline
    from tennislive.video.subtitle_text import drop_punctuation

    # 1) 定时字幕过这一道；常驻角标／台标不过——去掉水印的标点等于改水印本身。
    src = inspect.getsource(pipeline.render_ass)
    assert "drop_punctuation(cue.text)" in src, "render_ass 没给定时字幕去标点"
    assert "drop_punctuation(mark" not in src, "角标不该被去标点"

    # 2) 大满贯竖版 v2 是独立脚本，自己写 Dialogue 行。
    grand_slam = (_REPO / "tools" / "build_grand_slam_v2.py").read_text("utf-8")
    assert "drop_punctuation(text)" in grand_slam, "大满贯竖版没给字幕去标点"

    # 3) 共用函数本身：标点换空格（不是删掉，删掉会把两句糊成一坨），
    #    换行留着（ASS 靠它排两行），`？！` 留着。
    assert drop_punctuation("他说过一句话：我其实还想继续打。") == "他说过一句话 我其实还想继续打"
    assert drop_punctuation("郑钦文 6-4、7-5 取胜，晋级八强。") == "郑钦文 6-4 7-5 取胜 晋级八强"
    assert drop_punctuation("上一行，好\n下一行。真的吗？") == "上一行 好\n下一行 真的吗？"

def test_字幕一行不许横跨两句话():
    """账号所有者 2026-08-03：「字幕也要保持断句的完整性，不要多也不要少。」

    切行本来就有「一个子句就是一行」的规矩，但合并短句那一支**根本不看隔开
    它们的是句号还是逗号**——于是「流程是这样的。本周三、周四」并成一行，
    「官方宣布顺延到周一。而那时候」并成一行：**两句不同的话挤在同一屏，
    而且后半句还是半截的**，读者会把两件事读成一件。

    句内（逗号、顿号）合并是好的：空格把停顿显出来，读起来仍是一句话。
    跨句合并是坏的。唯一的例外是那一片短到独自成行也读不到（≤2 字）——
    那时候一闪而过比共一行更糟，让可读性的地板赢。

    ⚠️ 这里**不逐条扫已发的片子**：它们的旁白按老规矩写，句号两边本来就有
    大量短片段，扫它们只会得到一份要人维护的豁免名单（「一个会过期的名单和
    一条常年红的检查是同一个毛病」）。测的是**机制**。
    """
    from tennislive.video.explainer import subtitle_lines

    # 两句都够长：绝不能并成一行
    text = "官方宣布顺延到周一。而那时候，加拿大站的资格赛两天前就打完了。"
    lines = [l for _, _, l in subtitle_lines(text)]
    for line in lines:
        assert "顺延到周一" not in line or "而那时候" not in line, (
            f"跨句并成了一行：{line}")

    # ≤2 字的那一支：短到独自成行会一闪而过，允许并
    text2 = "他站得上场，但打了就凑不满六个月。他没打。多伦多复出首轮输球。"
    merged = [l for _, _, l in subtitle_lines(text2) if "没打" in l]
    assert merged, "「他没打」这三个字整个不见了？"
    assert all(len(l) >= 3 for _, _, l in subtitle_lines(text2)), (
        "还是留下了会一闪而过的短行")


def test_特殊豁免那条的字幕行行都是完整子句():
    """新写的片子要真的达标——上一条测机制，这一条测**这条片子**。

    只钉 special-exempt：它是按这条规矩重排过标点的那一条，也是判据的样本。
    盯死三个数，任何一个回涨都说明标点或切行退化了。
    """
    import re

    from tennislive.video.explainer import _OPENINGS, _SCRIPTS, speakable, subtitle_lines
    from tennislive.video.explainer import _sub_display

    segs = [_OPENINGS["special-exempt"]["narration"]] + [
        s[3] for s in _SCRIPTS["special-exempt"]]
    total = cross = split = short = 0
    norm = lambda x: re.sub(r"[，。；：？！——、\s]", "", _sub_display(x))  # noqa: E731
    for raw in segs:
        text = speakable(raw)
        sents = [x for x in re.split(r"(?<=[。！？；…])", text) if x.strip()]
        for a, b, line in subtitle_lines(text):
            total += 1
            cross += not any(norm(line) in norm(s) for s in sents)
            split += not re.search(r"[，。；：？！、—]", text[a:b])
            short += len(line) < 3
    assert total > 100, f"只切出 {total} 行？判据的主语没了"
    assert (cross, split, short) == (0, 0, 0), (
        f"{total} 行里：横跨两句 {cross} 行、子句被劈开 {split} 行、太短 {short} 行")



# ---------------------------------------------------------------- Pages 触发
#
# 2026-08-04：`pages.yml` 从上线到出事一共跑过四趟，**只有真人合并 PR 那趟是
# push 自动触发的**；两次由推送流程自己 commit + push 的复制页一次都没触发。
# 根因是 `GITHUB_TOKEN` 推的 push 不创建 workflow run（GitHub 防递归）。
# 症状是「慢」不是「错」：探活探满 40 分钟，然后静静把按钮摘掉。

def _fake_post(calls, status=204):
    def post(url, **kw):
        calls.append((url, kw))
        return type("R", (), {"status_code": status, "text": ""})()
    return post


def _fake_runs(*snapshots):
    """按顺序返回每次「查运行列表」看到的东西。

    每份是 `[(id, actor, event), …]`，`None` 表示这次读不到（HTTP 500）。
    用完之后停在最后一份——确认循环会查很多次。
    """
    seen = []

    def get(url, **kw):
        seen.append(url)
        runs = snapshots[min(len(seen) - 1, len(snapshots) - 1)]
        if runs is None:
            return type("R", (), {"status_code": 500, "text": "",
                                  "json": lambda self: {}})()
        payload = {"workflow_runs": [
            {"id": rid, "actor": {"login": actor}, "event": event}
            for rid, actor, event in runs]}
        return type("R", (), {"status_code": 200, "text": "",
                              "json": lambda self, p=payload: p})()

    return get


def test_触发Pages要真发出那个dispatch(monkeypatch):
    """204 才算点动了，而且要打到 `pages.yml` 的 dispatches 上。"""
    from tennislive.render import pushmsg

    calls = []
    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    monkeypatch.setenv("GITHUB_REPOSITORY", "someone/repo")
    monkeypatch.setattr(pushmsg.requests, "post", _fake_post(calls))
    monkeypatch.setattr(pushmsg.requests, "get", _fake_runs(
        [(1, "someone", "push")],                       # 点之前
        [(2, "github-actions[bot]", "workflow_dispatch"),
         (1, "someone", "push")],                       # 点之后，多了一条
    ))
    assert pushmsg.trigger_pages_build(confirm_seconds=0) is True
    (url, kw), = calls
    assert url == ("https://api.github.com/repos/someone/repo/actions/"
                   "workflows/pages.yml/dispatches"), url
    assert kw["json"] == {"ref": "main"}, "Pages 只服务 main，别按当前分支点"
    assert kw["headers"]["Authorization"] == "Bearer t0ken"


def test_点不动Pages不许静默(monkeypatch, caplog):
    """点不动**不算失败**（探活那道闸还在），但必须出声。

    「没点成」和「点成了」在日志上长得一样，正是这个 bug 藏了一整天的原因。
    """
    import logging

    from tennislive.render import pushmsg

    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    monkeypatch.setattr(pushmsg.requests, "post", _fake_post([], status=403))
    monkeypatch.setattr(pushmsg.requests, "get", _fake_runs([]))
    with caplog.at_level(logging.WARNING):
        assert pushmsg.trigger_pages_build(confirm_seconds=0) is False
    assert "403" in caplog.text and "actions: write" in caplog.text

    caplog.clear()
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with caplog.at_level(logging.INFO):
        assert pushmsg.trigger_pages_build(confirm_seconds=0) is False
    assert "GITHUB_TOKEN" in caplog.text


def test_点完要确认真的出现了一条新的运行记录(monkeypatch, caplog):
    """**204 是信号，运行记录才是产物。**

    `dispatches` 返回 204 只保证 GitHub 收下了请求：工作流被停用、
    `pages.yml` 不在默认分支上、ref 指到没有这个文件的地方，都会收下之后
    什么也不发生。2026-08-04 那两条「看起来自动触发了」的记录其实是我手动
    补的，而日志里两者一模一样——所以现在要把 **run id 和 actor** 打出来。

    ⚠️ 顺带钉住「**比变化量，别比内容特征**」：下面第二档的基线里**本来就
    有**一条 `workflow_dispatch`，如果按「最近有没有 workflow_dispatch」判，
    它一上来就为真，这道确认等于没装。
    """
    import logging

    from tennislive.render import pushmsg

    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    monkeypatch.setattr(pushmsg.requests, "post", _fake_post([]))

    # ① 真的多出来一条 → True，而且 id 和 actor 都要落进日志
    monkeypatch.setattr(pushmsg.requests, "get", _fake_runs(
        [(7, "robertyang87", "workflow_dispatch")],
        [(8, "github-actions[bot]", "workflow_dispatch"),
         (7, "robertyang87", "workflow_dispatch")],
    ))
    with caplog.at_level(logging.INFO):
        assert pushmsg.trigger_pages_build(confirm_seconds=0) is True
    assert "8" in caplog.text and "github-actions[bot]" in caplog.text, (
        "确认到了却没把 run id 和 actor 打出来——"
        "而 actor 正是「这段代码点的」和「有人手动补的」之间唯一的区别")

    # ② 收下了但什么也没发生 → False，而且要出声
    caplog.clear()
    monkeypatch.setattr(pushmsg.requests, "get", _fake_runs(
        [(7, "robertyang87", "workflow_dispatch")]))   # 前后一模一样
    with caplog.at_level(logging.WARNING):
        assert pushmsg.trigger_pages_build(confirm_seconds=0) is False, (
            "没有新的运行记录却报成功了——那正是这条修复要防的「写了没跑过」")
    assert "204" in caplog.text


def test_读不到运行列表不算确认过(monkeypatch, caplog):
    """「查不了」和「没跑起来」处置相反，日志里不许混成一句。

    读不到基线就没法比集合差，这时**不能**把「看见一条旧 run」当成确认——
    那是「非空结果 ≠ 对题」。所以直接说「这一趟确认不了」，返回 True
    （POST 确实成功了，别把它误报成失败去吓下一个人）。
    """
    import logging

    from tennislive.render import pushmsg

    monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
    monkeypatch.setattr(pushmsg.requests, "post", _fake_post([]))
    monkeypatch.setattr(pushmsg.requests, "get", _fake_runs(None))
    with caplog.at_level(logging.INFO):
        assert pushmsg.trigger_pages_build(confirm_seconds=0) is True
    assert "确认不了" in caplog.text, "读不到列表却装作确认过了"
    assert "github-actions" not in caplog.text, (
        "没确认过就不该报出 actor——那会让人以为验过了")


def test_触发要排在探活之前不是之后():
    """**只测行为拦不住位置错。**

    排在探活之后等于没装：那时循环已经探满全程、按钮已经摘掉了。仓库里
    「闸装在发的那一步不是渲的那一步」是同一个形状——那次三档行为全对、
    全绿，按钮照样每次消失。
    """
    import inspect

    from tennislive.render import pushmsg

    reel = Path("tools/push_reel.py").read_text(encoding="utf-8")
    for src, where in (
        (inspect.getsource(pushmsg._probe_page), "pushmsg._probe_page"),
        (reel.split("def wait_for_copy_page")[1].split("\ndef ")[0],
         "push_reel.wait_for_copy_page"),
    ):
        assert "trigger_pages_build()" in src, f"{where} 没触发 Pages 部署"
        assert src.index("trigger_pages_build()") < src.index("for attempt"), (
            f"{where} 把触发排在了探活循环**之后**——那时按钮早就摘掉了")


#: 探复制页的那两个函数。谁（间接）调用它们，谁就要能点动 Pages。
_COPY_PAGE_PROBES = {"drop_dead_copy_button", "wait_for_copy_page"}


def _funcs_calling(tree, names: set[str]) -> set[str]:
    """模块里哪些顶层函数调用了 `names` 里的任何一个。

    **用 AST 不用正则**：`push_reel.py` 的 docstring 里提了三次
    `wait_for_copy_page`，真正的调用只有一处；正则分不出这个差别，而这个
    仓库的注释正是记教训的地方，必然会提到被测的那个名字。
    """
    import ast

    hit = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                name = getattr(sub.func, "id", None) or getattr(
                    sub.func, "attr", None)
                if name in names:
                    hit.add(node.name)
    return hit


def _probing_entry_points() -> list[str]:
    """从代码推出「哪些命令行入口会走到探复制页」，不手写清单。"""
    import ast

    tools = sorted(
        p.name for p in Path("tools").glob("*.py")
        if _funcs_calling(ast.parse(p.read_text(encoding="utf-8")),
                          _COPY_PAGE_PROBES))

    cli_src = Path("src/tennislive/cli.py").read_text(encoding="utf-8")
    probing = _funcs_calling(ast.parse(cli_src), _COPY_PAGE_PROBES)
    # `if args.channel == "pushplus": return cmd_publish_pushplus(args)`
    channels = sorted({
        chan for chan, fn in re.findall(
            r'args\.channel\s*==\s*"([^"]+)"[^\n]*\n\s*return\s+(\w+)\(', cli_src)
        if fn in probing})

    # **判据自己也要有判据**：主语没了它要出声，而不是变成一条恒真的绿灯。
    assert tools, "一个 tools 脚本都没查到会探复制页——判据失效了"
    assert channels, "一个 publish channel 都没查到会探复制页——判据失效了"
    return ([re.escape(t) for t in tools]
            + [rf"publish\s+{re.escape(c)}" for c in channels])


def test_会发微信的工作流都要能触发Pages():
    """判据自己推导，不维护白名单。

    凡是跑 `push_reel.py` 或 `tennislive publish pushplus` 的工作流都会走到
    探复制页那条路，所以都要：`permissions: actions: write`（才点得动
    workflow_dispatch）+ 那一步拿得到 token。少一样就退回「探满 40 分钟再摘
    按钮」，**而它不报错**。

    ⚠️ 扫之前先去掉整行注释——工作流的注释正是这个仓库记教训的地方，
    连它一起扫会把「把坑记下来」判成「又踩了这个坑」。

    ⚠️ **第一版写的是 `push_reel\\.py|publish\\s+pushplus`——那是一张伪装成
    推导的白名单。** 它把「哪些入口会探复制页」的答案硬编码成了两种拼法，
    于是 `publish content`（内容雷达）到底算不算，全靠写测试的人当时记得。
    这次核下来它**碰巧**是对的（`cmd_publish_flash` 直接推图文，根本没有
    复制页），可「碰巧对」和「真的接上了」长得一模一样，而且前者会一直绿。
    现在从代码推：拿 AST 找出真正调用探活那两个函数的入口，再顺着
    `args.channel` 的分发表倒推出 channel 名。以后哪个入口新接上探活，
    这条会替人记得。
    """
    import yaml

    need = re.compile("|".join(_probing_entry_points()))
    checked = []
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        perms = spec.get("permissions") or {}
        for job in (spec.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                run = "\n".join(
                    line for line in str(step.get("run") or "").splitlines()
                    if not line.lstrip().startswith("#"))
                if not need.search(run):
                    continue
                env = step.get("env") or {}
                checked.append(f"{path.name}「{step.get('name')}」")
                assert perms.get("actions") == "write", (
                    f"{path.name} 会发微信却没有 `actions: write`——"
                    "点不动 pages.yml，复制页只能等别的 push 才发布")
                assert "GITHUB_TOKEN" in env or "GH_TOKEN" in env, (
                    f"{path.name}「{step.get('name')}」拿不到 token，"
                    "`trigger_pages_build` 会直接跳过")
    assert len(checked) >= 9, f"只校到 {len(checked)} 处，判据可能失效了"


def test_验证Pages那条路要够得着而且不发微信():
    """**「写了」和「跑通了」之间，不该隔着一条要发微信才能走的路。**

    #173 那个修复的判据是「`pages.yml` 里出现一条 `actor=github-actions[bot]`
    的运行记录」，可它只在**真推送**的时候才走到——而真推送会发微信，那条
    消息发出去收不回来。于是这个修复在仓库里躺了一整天，状态是「写了，
    没跑过」，而它看起来和「修好了」一模一样。

    `pages-selftest.yml` 把验证从发布里拆出来。三头都要钉：

    - **入口够得着**（工作流在，手动能跑）
    - **那条路真的短**——不出片、不发微信。只钉入口的话，有人把它写成一趟
      完整推送也照样绿（`--cover-only` 那次就是这么栽的）
    - **工具自己查一遍产物**，不只信 `trigger_pages_build()` 的返回值。
      判据和被判的东西是同一个来源，就什么也证明不了
    """
    import yaml

    path = Path(".github/workflows/pages-selftest.yml")
    assert path.exists(), (
        "验证 Pages 触发的入口没了——那条修复又只能等真推送才验得了")
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    # YAML 1.1 把裸的 `on:` 读成布尔 True
    triggers = spec.get("on") or spec.get(True) or {}
    assert "workflow_dispatch" in triggers, "手动入口没了，这条就跑不起来"
    assert (spec.get("permissions") or {}).get("actions") == "write", (
        "没有 `actions: write` 就点不动 pages.yml——这条自检自己会失败")

    runs, envs = [], {}
    for job in (spec.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            runs.append("\n".join(
                line for line in str(step.get("run") or "").splitlines()
                if not line.lstrip().startswith("#")))
            envs.update(step.get("env") or {})
    body = "\n".join(runs)
    assert "GITHUB_TOKEN" in envs, (
        "拿不到 token，`trigger_pages_build` 会直接跳过——这条自检等于空转")
    assert "check_pages_trigger.py" in body, "没跑那个自检工具"
    for banned in ("push_reel.py", "tennislive publish", "ffmpeg",
                   "playwright", "yt-dlp"):
        assert banned not in body, (
            f"pages-selftest 里出现了 {banned}——这条路只该点一下 Pages，"
            "不出片也不发微信。它一旦变长，就又没人愿意跑它了")

    tool = Path("tools/check_pages_trigger.py").read_text(encoding="utf-8")
    assert tool.count("pages_runs(") >= 2, (
        "自检工具没有自己前后各查一遍运行列表——只信函数的返回值，"
        "等于拿判据去证明判据")
    assert "expect_actor" in tool and "github-actions[bot]" in tool, (
        "没有校 actor。而 actor 正是「这段代码点的」和「有人手动补的」之间"
        "唯一的区别——2026-08-04 那两条看起来自动触发的记录就是手动补的")


# ---------------------------------------------------------------------------
# 成片一律走 Release（2026-08-13 账号所有者：「所有视频统一走 Release 路线」）


def _wf_yaml_only(text: str) -> str:
    """去掉整行注释再扫。

    工作流的注释正是这个仓库记教训的地方，正文里必然写着当年那些错值
    （Release 那一步的注释里就有「jsDelivr」「进 git」这些词）——连注释一起扫，
    「把坑记下来」会被判成「又踩了这个坑」。同 `test_match_reel._yaml_only`。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _explainer_step_block(name: str) -> str:
    """取 explainer.yml 某一步自己那一段——先去注释，再锚在步骤头上。

    两个坑照抄 `test_match_reel._step_block` 的教训：按裸的步骤名切会先命中
    注释；从 `- name:` 开始切再按 `- name:` 分割会在第 0 位截断出空串，
    要按整行头 `\\n      - name:` 切。
    """
    body = _wf_yaml_only(
        (_REPO / ".github" / "workflows" / "explainer.yml")
        .read_text(encoding="utf-8"))
    head = f"      - name: {name}"
    start = body.index(head)
    return body[start:].split("\n      - name:", 1)[0]


def test_解说成片一律走Release不进git():
    """解说成片 7 MB 上下一条条进 git，攒成了 .git 6.0 GB 里的一份子。

    来路（2026-08-13）：账号所有者「当前代码库太大了」「后面新的视频全部走
    新的架构不要放在代码里面」「包括后续所有的视频，制作的视频。都走统一的
    Release 路线」。存量动不了（jsDelivr 链接钉在仓库文件路径上、已发的微信
    消息收不回来），只改增量：**从这天起成片发 Release，不再进 git**。

    钉的几件事，少一件就会退回老样子：

    1. Release 那一步存在，tag 是 `explainer-$SLUG`，`SZ=$(stat …)` 要留着
       （render.json 的 video_bytes 从它来）
    2. `gh release upload` 外面**真的套着重试循环**，退避是涨的
       （`WAIT=$((5*i*i))` 二次方），用尽要 `exit 1`；循环里不许出现
       `[ A ] && …`——`bash -e` 下 AND 列表整条为假会把这一步杀掉
       （match-reel.yml 同一步骤的注释记着这个坑，抄结构也要抄注释）
    3. 传完 Range 探活（`-r 0-99`，206/200 才算），探不到 `exit 1`——
       写一个探不到的链接进 render.json 等于把 404 发到微信
    4. 链接和字节数写进 render.json（`video_url` / `video_bytes`），然后
       `rm -f "$CLIP"`——不删的话 `git add` 照样把 mp4 吃进去，白传一趟
    5. **重渲 push.html**：它是生成那一步写的，那一刻 render.json 还没有
       video_url，▶ 按钮拼的是 jsDelivr 老路，而这条 mp4 不进 git，
       那个链接必然 404
    6. 顺序：生成 → 上传 artifact（mp4 的兜底，提交步骤的报错一直承诺
       「成片仍在 artifact 里」）→ Release/rm → 提交

    ⚠️ 判据宁可窄：只扫去注释后的步骤块（`_explainer_step_block`），
    不扫整份 yml——步骤注释里如实记着 jsDelivr 那段来路。
    """
    text = (_REPO / ".github" / "workflows" / "explainer.yml").read_text(
        encoding="utf-8")
    stripped = _wf_yaml_only(text)
    names = [
        line.split("- name:", 1)[1].strip()
        for line in text.splitlines() if line.startswith("      - name:")
    ]
    assert stripped.count("gh release upload") == 1, (
        "该正好有一步传 Release 附件")
    body = _explainer_step_block("成片发到 Release（不进 git）")

    # ① tag 形状 + SZ
    assert 'TAG="explainer-$SLUG"' in body, "tag 不是 explainer-<slug>"
    assert 'SZ=$(stat -c%s "$CLIP")' in body, (
        "SZ 没了——render.json 的 video_bytes 从它来")

    # ② 上传的重试循环：退避是涨的，用尽要报错，不许用会被 errexit 杀掉的写法
    upload = body.index("gh release upload")
    loop = body.rfind("for ", 0, upload)
    assert loop != -1, "`gh release upload` 外面没有重试循环——一次 5xx 报销整趟生成"
    tail = body[loop:]
    assert "sleep" in tail[:tail.index("URL=")], (
        "重试循环里没有退避——贴着重发四次，撞上的同一个 5xx 多半还在")
    assert "WAIT=$((5 * i * i))" in body, (
        "退避不是涨的：等长的重试对一次持续几十秒的服务端故障没有用")
    assert 'UPLOADED" = 1 ]' in body and "exit 1" in body, (
        "四次都没传上去却没有拦住：下游会把一个取不到的链接写进 render.json")
    for line in tail.splitlines():
        one = line.strip()
        if one.startswith("[") and "&&" in one:
            raise AssertionError(
                f"`bash -e` 下这一行整条为假会直接杀掉这一步，用 if：{one!r}")

    # ③ Range 探活，探不到不许往下走
    assert "-r 0-99" in body, "没有 Range 探活——写进 render.json 的链接没人验证过"
    assert '"206"' in body and '"200"' in body, "探活没认 206/200"
    assert body.index("-r 0-99") < body.index("render.json"), (
        "探活要排在写 render.json 之前——先写后探等于把没验证的链接落了盘")

    # ④ render.json + rm
    assert '"video_url"' in body and '"video_bytes"' in body, (
        "Release 链接没写进 render.json——explainer_push_html 优先读的就是它")
    assert re.search(r'rm -f "\$CLIP"', body), (
        "传完 Release 没删本地那份——git add 照样把 mp4 吃进去，白传一趟")

    # ⑤ 重渲 push.html，而且排在 render.json 写完之后
    assert "explainer_push_html" in body, (
        "没重渲 push.html——生成那一步写的 ▶ 按钮还指着 jsDelivr 老路，必然 404")
    assert body.index('"video_url"') < body.index("explainer_push_html"), (
        "重渲要排在 render.json 写完之后，不然读到的还是没有 video_url 的那份")

    # ⑥ 顺序：生成 → artifact → Release → 提交
    i_gen = names.index("生成解说视频")
    i_art = names.index("上传成片 artifact")
    i_rel = names.index("成片发到 Release（不进 git）")
    i_commit = names.index("提交成片到仓库")
    assert i_gen < i_art < i_rel < i_commit, (
        f"顺序不对（生成={i_gen}，artifact={i_art}，Release={i_rel}，"
        f"提交={i_commit}）——artifact 要先拿到 mp4 当兜底，Release/rm 要在"
        "提交之前，否则 mp4 又进 git")


def test_卡片缩一半要用lanczos不许退回缺省的bicubic(tmp_path):
    """账号所有者 2026-08-16：「文字卡做成视频之后，上面的文字虚化了不少，
    看起来不是太清晰和做渲染之前」。

    卡片是 2160×2880 截的，成片画布只有 1080 宽——每一屏都要**整整缩小一半**
    才进得了视频。缩小用哪个滤镜，决定了字的笔画还剩多少；`swscale` 的缺省是
    bicubic，而这条线一直没给它指定过。量出来 bicubic 比 lanczos 少 13.6% 的
    高频能量，是 q86 JPEG（2.2%）的六倍，也远大于 `crf 26`（量不出来）。
    出处和那张表写在 `_SCALE_FLAGS` 上面。

    判据钉两头，缺一头都拦不住这个错：

    · **行为**——真跑一次 ffmpeg，真的把一张「深绿底浅色小字」缩一半，
      lanczos 出来的笔画必须比 bicubic 实。只钉字符串的话，哪天有人换成
      `flags=neighbor` 照样绿
    · **位置**——每一条把卡片缩进画布的 `scale=` 都要带上 `flags=`。只验行为
      的话，漏掉片尾那一条也不会红
    """
    import shutil
    import subprocess

    import numpy as np

    from tennislive.video import explainer as E

    body = Path(E.__file__).read_text(encoding="utf-8")

    # ① 位置：凡是 force_original_aspect_ratio=decrease（把卡片缩进画布的那种）
    #    都必须显式指定滤镜。自己从源码里推，不维护白名单——以后多一条
    #    scale+pad 的链子，它会替人记得。
    shrink = re.findall(r"scale=\{[^}]+\}:\{[^}]+\}:"
                        r"(?:\"\s*\n\s*f\")?force_original_aspect_ratio=decrease"
                        r"(:flags=\{?[A-Za-z_]+\}?)?", body)
    assert shrink, "一条把卡片缩进画布的 scale= 都没找到——判据的主语没了"
    missing = [s for s in shrink if not s]
    assert not missing, (
        f"{len(missing)} 条缩放链没写 flags=，会落回 swscale 缺省的 bicubic："
        "文字卡的笔画会少掉一成多的高频。见 _SCALE_FLAGS 上面那张表")

    # ② 行为：真缩一次，量高频能量。没有 ffmpeg 就是环境缺依赖，不许 skip——
    #    一条常年跳过的检查和常年红是同一个毛病。
    assert shutil.which("ffmpeg"), "缺 ffmpeg：装上再跑，别把这条跳过去"
    src = tmp_path / "card.png"
    # 造一张「深绿底 + 浅色一像素细线」的卡：细线正是笔画在 2× 下的样子，
    # 缩一半之后滤镜好不好，全看它还剩多少对比度。
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", "color=c=0x0b3a2a:s=2160x2880",
         "-vf", "drawgrid=w=6:h=6:t=1:c=0xe7f3ec",
         "-frames:v", "1", "-y", str(src)],
        check=True,
    )

    def high_freq(flags: str) -> float:
        out = tmp_path / f"{flags}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(src),
             "-vf", f"scale=1080:1440:flags={flags}", "-y", str(out)],
            check=True,
        )
        from PIL import Image

        a = np.asarray(Image.open(out).convert("L"), dtype=float)
        return float((a[1:-1, 1:-1] * -4 + a[:-2, 1:-1] + a[2:, 1:-1]
                      + a[1:-1, :-2] + a[1:-1, 2:]).var())

    lanczos, bicubic = high_freq("lanczos"), high_freq("bicubic")
    assert lanczos > bicubic * 1.05, (
        f"lanczos({lanczos:.0f}) 没比 bicubic({bicubic:.0f}) 实——"
        "这条判据引用的那个差别不存在了，先重量一遍再改常量")
    assert E._SCALE_FLAGS == "lanczos", (
        f"_SCALE_FLAGS 现在是 {E._SCALE_FLAGS!r}；换之前照 _SCALE_FLAGS "
        "上面那张表的口径重量一遍，别按感觉换")


def test_示意图那一屏的scrim不许压在示意图上():
    """账号所有者 2026-08-16：「卡片上面的文字做成图片之后看起来很不清晰」
    「把文字的亮度调高」。

    根子不在颜色，在图层：`.scrim` 排在 `.diagram-wrap` 后面、两个都是
    `position:absolute` 又都没有 z-index，所以**它盖在示意图上面**，而它顶部
    那一档是 55% 的压暗。示意图占卡片高度的 14.6%~57.2%，按四个色标插值是
    被压暗 36%（顶）到 19%（底）——渲出来量过：框内正文对比度只有 **3.8:1**，
    而同一张卡下半的要点是 **17:1**。

    scrim 存在的理由是让贴底的 `.copy` 压在**照片**上还读得出来；示意图这一屏
    底下没有照片，背景是我们自己画的渐变，所以这层压暗纯粹在削自己的字。

    判据钉两头：**示意图那一屏用的是另一条 scrim**，而且**那条 scrim 的上半
    是全透明的**。只钉前一头的话，有人把 `scrim--diagram` 定义成和 `.scrim`
    一样也照样绿。
    """
    from tennislive.video import explainer as E

    story = find_story_by_slug("weeks-at-no1")
    segs = E.explainer_script(story)
    diagram_seg = next(s for s in segs[1:] if s.diagram and not s.image)
    html = E._slide_html(2, diagram_seg, theme="dark", topic="", column="网球有故事")

    assert 'class="scrim scrim--diagram"' in html, (
        "示意图那一屏还在用通用的 .scrim——它会盖在示意图上面，"
        "顶部压暗 36%，正文对比度从 8:1 掉到 3.8:1")

    # 那条 scrim 的**第一段必须是全透明**。取 `.scrim--diagram` 的 background，
    # 把色标读出来：0% 那一档的 alpha 要是 0。
    block = html.split(".scrim--diagram{")[1].split("}")[0]
    stops = re.findall(r"rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([\d.]+)\s*\)\s+(\d+)%", block)
    assert stops, f"读不出 .scrim--diagram 的色标：{block}"
    top = [float(a) for a, pos in stops if int(pos) == 0]
    assert top and top[0] == 0, (
        f".scrim--diagram 顶部 alpha 是 {top}，不是 0——示意图又被压暗了")
    # 示意图画布下沿约在 57.2%，那之前一档都不许开始压。
    early = [(float(a), int(pos)) for a, pos in stops if int(pos) < 57 and float(a) > 0]
    assert not early, (
        f"57% 之前就开始压暗了：{early}。示意图的下沿在 57.2%（top 210px + "
        "920px 宽的 3:2 画布高 613px ÷ 1440px），那之前一点都不该压")
    # 反过来：**底下那一段必须还压着**，不然 .copy 压在示意图上会读不出来。
    bottom = [float(a) for a, pos in stops if int(pos) == 100]
    assert bottom and bottom[0] >= 0.9, (
        f"底部 alpha 只有 {bottom}——.copy 就是靠它压住背景才读得出来的")


def test_示意图的颜色要和卡片本身是同一套():
    """账号所有者同一条消息：「卡片上的文字和前景的文字的颜色看起来很土，
    前景的颜色很鲜艳，卡片上的文字就比较暗和模糊」。

    卡片下半（`.point` / `.point i`）用的是 `#f4fbf7` 正文加 `#c6f65a` 亮绿；
    而后加的 `no1_charts` / `rulebook_cards` 里我自己调了 `#e7f3ec` 正文加
    `#8fd6a8` 薄荷、`#e0b13a` 暗金——**同一张卡上两套色，下半鲜艳上半发闷**。

    ⚠️ 这不是「调得不好看」，是**分叉**：`explainer.py` 里那 40 多张老示意图
    早就一路写着 `#c6f65a`，也就是这套色本来就定过，只有后加的模块没跟上。
    所以判据是**从卡片自己的 CSS 里把颜色抠出来比**，不是另记一张色表——
    CSS 改了而 `diagram_palette` 不改，当场红。
    """
    from tennislive.video import diagram_palette as P
    from tennislive.video import explainer as E

    story = find_story_by_slug("weeks-at-no1")
    css = E._slide_html(2, E.explainer_script(story)[2], theme="dark",
                        topic="", column="网球有故事")

    def rule(selector: str) -> str:
        return css.split(selector + "{")[1].split("}")[0]

    body = re.search(r"color:(#[0-9a-fA-F]{6})", rule(".point")).group(1)
    accent = re.search(r"color:(#[0-9a-fA-F]{6})", rule(".point i")).group(1)
    assert P.INK == body, (
        f"示意图正文 {P.INK} 和卡片 .point 的 {body} 不是同一个色——"
        "同一张卡上两套色，上半就会看着比下半闷")
    assert P.LIME == accent, (
        f"示意图强调色 {P.LIME} 和卡片 .point i 的 {accent} 不是同一个色")

    # 三个模块一个都不许再自己写死颜色（`FILL` 之外的那几档）。
    # 用 AST 找模块级的字符串常量，注释和 docstring 里提到旧色不算数。
    import ast

    retired = {"#e7f3ec", "#a9bcb2", "#e0b13a"}
    for name in ("no1_charts", "masters_grid", "rulebook_cards"):
        src = (_REPO / "src" / "tennislive" / "video" / f"{name}.py").read_text(
            encoding="utf-8")
        tree = ast.parse(src)
        lits = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        # docstring 会整段进来，所以按「出现过退役色」而不是「等于退役色」查
        hits = {c for c in retired
                for lit in lits
                if c in lit and not lit.lstrip().startswith("\n")}
        assert not hits, (
            f"{name}.py 里还写着退役的颜色 {sorted(hits)}——"
            "从 diagram_palette 取，别再各调各的")


def test_探活正常是第几次要按间隔算不许写死1(caplog):
    """账号所有者那条盘外招推送的日志里挂着一条 WARNING，说「这条链上多半还有
    别的没接上」——**而链子好好的**。

    第一次探活是紧跟在 `trigger_pages_build()` 之后发出的（中间只隔一次 HTTP
    往返），而点一下到部署完实测 19 秒。所以 30 秒间隔下，**第一枪结构性打不中**，
    健康值本来就是第 2 次。原来那句告警写死「正常应该第 1 次就中」，是把另一条
    线的时序搬了过来。

    CLAUDE.md 记着同一个形状：「判据要连它的时序前提一起搬」「一个搬错线的判据
    比没有判据坏——它会让下一个人去追一个不存在的问题，而且他找不到」。

    钉三头：算得对、正常那几次**不许**报 warning、真的慢了**必须**报。
    """
    import logging

    from tennislive.render import pushmsg as P

    # ① 算得对：第 1 次在 t=0，第 n 次在 (n-1)*delay，第一个够得着 19 秒的才算数
    assert P.expected_first_hit(30.0) == 2, "30 秒间隔下第 2 次才够得着 19 秒"
    assert P.expected_first_hit(10.0) == 3, "10 秒间隔要到第 3 次（20s）才过 19 秒"
    assert P.expected_first_hit(0) == 1, "间隔 0 是退化情况，别除零"

    # ② 正常范围内不许报 warning——这正是被误报的那一格
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=P.logger.name):
        P._say_probe_hit(2, "https://example.invalid/copy.html", delay=30.0)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert not warnings, (
        "30 秒间隔下第 2 次命中是**最快的健康值**，不该报警："
        + "；".join(r.getMessage() for r in warnings))
    assert any("最快能中的是第 2 次" in r.getMessage() for r in caplog.records), (
        "命中那一行要把「最快能中的是第几次」一起打出来，"
        "不然读日志的人得回头翻文档才知道 2 是正常的")

    # ③ 真的慢了必须报——判据自己的判据：②那一条不能是因为它从来不报警才绿
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=P.logger.name):
        P._say_probe_hit(5, "https://example.invalid/copy.html", delay=30.0)
    assert [r for r in caplog.records if r.levelno >= logging.WARNING], (
        "第 5 次才命中是真的异常（比最快值多三次），必须报 warning")


def test_示意图吐出来的每个颜色属性都得是合法的():
    """⚠️ 2026-08-16 我自己写坏过一次，而**四道闸全绿、渲出来也像模像样**。

    起因是把三个示意图模块的硬编码颜色换成 `diagram_palette` 的 token 时，
    用脚本批量替换，中间一步给字符串补 `f` 前缀的正则**连 SVG 属性值里那对
    引号也补上了**，于是生成出来是

        fill=f"#f4fbf7"

    多一个 `f`。这在 HTML 解析里是 `fill` 取到一个垃圾值——Chromium 不报错，
    照样渲出一张看着挺正常的图，只有把两版逐像素比才看得出笔画暗了一档
    （量出来那一块的最亮像素从 `#f4fbf7` 掉到 `#0d2b1e`，也就是底色）。
    19 处，跨两个模块。

    「渲出来看」这一关它是过得去的——**所以判据不能是看，得是解析**。
    这条扫每一张示意图吐出来的 SVG，要求每个颜色属性的值都是认得出来的东西。
    """
    import importlib
    import xml.etree.ElementTree as ET

    diagrams = {
        "no1_charts": ("weeks_at_no1_chart", "goolagong_gap", "margin_ladder"),
        "masters_grid": ("nine_masters_grid", "two_tours_grid",
                         "wta_table_drift", "atp_table_future"),
        "rulebook_cards": ("time_structure", "shoe_rule", "toilet_rule",
                           "two_violations", "word_in_the_book"),
    }
    # 判据自己的判据：模块改名 / 函数删掉的样子就是一张空表，那时它会安静地全绿。
    checked = 0
    ok_value = re.compile(r"^(#[0-9a-fA-F]{3,8}|none|currentColor|url\(#[\w-]+\))$")
    for mod, fns in diagrams.items():
        m = importlib.import_module(f"tennislive.video.{mod}")
        for fn in fns:
            svg = getattr(m, fn)()
            checked += 1

            # ① **真的用 XML 解析器解一遍**。`fill=f"#f4fbf7"` 在解析器眼里
            #    直接是语法错，而正则想认它总会误伤——第一版就把文本里的
            #    `2Q=` 当成了属性名。判据宁可用真解析器，不用手搓的模式。
            try:
                root = ET.fromstring(svg)
            except ET.ParseError as exc:
                raise AssertionError(
                    f"{mod}.{fn} 吐出来的不是合法 SVG：{exc}——"
                    "十有八九是批量替换时给 SVG 属性里的引号补了 f 前缀"
                    "（`fill=f\"…\"`）。Chromium 不会报错，只会把那个值整个读废"
                ) from None

            # ② 每个颜色属性的值都要认得出来
            for el in root.iter():
                for attr in ("fill", "stroke"):
                    val = el.get(attr)
                    if val is not None:
                        assert ok_value.match(val), (
                            f"{mod}.{fn} 的 <{el.tag}> {attr} 值认不出来：{val!r}")

    assert checked >= 12, f"只校到 {checked} 张示意图，判据失效了"


def test_封面不许再压一层居中的阴影(tmp_path):
    """账号所有者：「感觉封面还有蒙了一层阴影」。

    `.cover .scrim` 原来叠着两层：一条竖向渐变，**外加**一层
    `radial-gradient(... at 50% 50%)`。那层椭圆的注释写着理由是
    「给**居中的那一问**垫一层软椭圆」——而 `.copy` 早就按账号所有者的要求
    改成贴底了（和 VS 海报对齐），**居中的那一问从此不存在**。椭圆留在原地，
    压的就成了照片正中间，也就是人脸那一块。

    ⚠️ **它一个字都不报**：封面照样渲得出来，四道闸门全过，全量测试全绿。
    分辨率、授权、四要素、构图统统合格——错的只是「有一层黑纱盖在上面」，
    而那没有任何一条判据在看。

    ⚠️ **不能拿 CSS 文本当判据。** 上面那段注释里正引着 `radial-gradient(128% 40%`
    这个老写法（这个仓库的注释就是教训的存放处），按文本扫会把「把坑记下来」
    判成「又踩了这个坑」——同一个错本仓库犯过五次。所以这一条**渲出来量像素**。

    量法：拿一张**纯白照片**当封面底图，渲出来每一行的灰度直接就是 `1 - alpha`
    ——不依赖任何一张真照片，也就不会被「换了张图」搅乱。实测两版：

        高度      改前（带椭圆）   改后
         35%        0.351         0.071
         40%        0.382         0.071
         50%        0.412         0.071   ← 画面正中被压掉四成
         70%        0.323         0.318
         85%        0.249         0.532   ← 文案那一带反而更暗了
        100%        0.539         0.650

    ⚠️ **为什么不去钉每张封面的「标题对比度」**：试过三种取样口径，三个互相
    矛盾的答案。固定带子会把标题上方的空档算进「底」（标题只有一行的封面
    因此被读成最差）；按行找字又分不开「白字」和「大太阳底下的白草地」。
    真正托住可读性的是 `.cover .title` 那三层 text-shadow，而按中位数算的
    对比度看不见逐字的描边光晕——36 张封面逐张打开看过，标题全都读得出来，
    而同一批数字里有六张「低于 AA」。**一个会随换图漂移的判据，不是变成
    常年红就是变成假绿灯**，所以这里只钉压暗曲线本身。

    **两头都要钉，缺一头都不算判据：**

    ① 正中那一段必须近乎透明——只钉这一头的话，把整条 scrim 删光也是绿的。
    ② 文案那一带必须够暗——只钉这一头的话，椭圆加回来照样绿（它在底部
       反而更亮，见上表）。

    ⚠️ 门槛落在两版中间，不贴着任何一版：正中 0.071 vs 0.351~0.412，取 0.20；
    底部 0.532 vs 0.249，取 0.40。两个方向分别反向验证过（把椭圆加回来，
    第 ① 条红；把底部那几档拉平成老写法的 .22，第 ② 条红）。

    ⚠️ 正中只取 35~50%——**主体（脸、上半身）在那一段**。60% 往下已经是
    起坡区（`.copy` 长标题会占到那儿），把它算进「正中」会逼着下一个人
    为了过闸把文案那一带的压暗也拆掉，而那正是这条判据的另一头要拦的。
    """
    import numpy as np
    from PIL import Image

    from tennislive.video.explainer import ExplainerSegment, render_explainer_slides

    repo = Path(__file__).resolve().parents[1]
    white = repo / "assets" / "_scrim_probe_white.png"
    # ⚠️ **这张探针图不能是纯白的**，虽然「纯白」才是量压暗曲线最自然的底。
    # 2026-08-24 `96301d2` 加了一道闸：图片顶部/底部 40% 的 stddev < 1.5 就判
    # 「像加载/裁切未完成」（拦的是拿纯灰纯白画布补齐的半张照片，是对的）。
    # 而纯白画布的 stddev 恒等于 0，**这条判据自己造的探针图第一个撞上它**——
    # main 因此连红了 8 个提交、14 个小时。
    #
    # 改成横向 248→255 的浅渐变：band stddev 2.00 过闸，而**量的那一条
    # （最左 3% 列）几乎不受影响**——基线 alpha 0.0275，对「正中 ≤ 0.20」
    # 这一头绰绰有余；对「底部 ≥ 0.40」那一头只会更宽松，而真把底部那段
    # 压暗拆掉时读数是 0.0275，照样离 0.40 很远，判据没有被削弱。
    #
    # **别再「顺手」改回 `Image.new(..., (255,255,255))`**——那会立刻把 CI 打红。
    import numpy as _np
    _w, _h = 2000, 1500
    _ramp = _np.tile(_np.linspace(248, 255, _w).astype("uint8"), (_h, 1))
    Image.fromarray(_np.dstack([_ramp] * 3), "RGB").save(white)
    seg = ExplainerSegment(
        kind="cover", label="网球冷知识", title="这一屏只用来量压暗曲线",
        narration="", image=f"assets/{white.name}",
    )
    try:
        render_explainer_slides([seg], tmp_path, topic="量一量", column="网球有故事")
    except Exception as exc:                                    # noqa: BLE001
        if "chrom" in str(exc).lower() or "executable" in str(exc).lower():
            raise AssertionError(
                "没有 Chromium，这条判据跑不了——它必须真渲出来量像素，"
                "查 CSS 文本看不见「有一层黑纱盖在上面」这一类错") from exc
        raise
    finally:
        white.unlink(missing_ok=True)

    a = np.asarray(Image.open(tmp_path / "slide_00.jpg").convert("L"), dtype=float)
    h, w = a.shape
    # 取最左那一条：`.copy` 从 x=70 起（2x 截图后 140），左边距干净，
    # 量到的才是 scrim 本身，不掺文字和它的描边。
    strip = a[:, : int(w * 0.03)].mean(axis=1)

    def alpha(pct: float) -> float:
        return 1.0 - float(strip[min(int(h * pct), h - 1)]) / 255.0

    正中 = max(alpha(p) for p in (0.35, 0.40, 0.45, 0.50))
    assert 正中 <= 0.20, (
        f"封面正中被压掉了 {正中 * 100:.0f}%——那儿没有字，压它只是把照片蒙住。\n"
        "⚠️ 八成是又给 `.cover .scrim` 叠了一层居中的 radial-gradient。"
        "那层当年是给**居中的那一问**垫底的，而 `.copy` 早就贴底了，"
        "它现在压的是人脸。")

    文案带 = min(alpha(p) for p in (0.85, 0.90, 0.95))
    assert 文案带 >= 0.40, (
        f"文案那一带只压了 {文案带 * 100:.0f}%——封面标题是近白的 #f4fbf7，"
        "底不够暗就读不出来了。\n"
        "⚠️ 这一条是上面那条的另一头：删掉居中那层黑纱的同时，底部那几档"
        "**要一起压重**（老写法靠椭圆在文案那一带顺手帮忙，删了得补回来）。")

    # 判据自己的判据：这条带子必须真的量到了变化，否则上面两句是在量一张
    # 恒定的图。纯白底片过 scrim 之后，顶、中、底三段必然是三个不同的数。
    assert alpha(0.02) > 正中 and 文案带 > 正中, (
        "顶/中/底量出来没有差别——底片或取样列选错了，这两条断言等于恒真")


#: 「开球之前」名下已经发过的片子。**只许减不许加**——这条栏目不再做新的了，
#: 见下面那条判据。表自己有自检：名字写错、或者某条其实已经不是这个栏目了，
#: 都会当场红（一个会过期的名单和一条常年红的检查是同一个毛病）。
_LEGACY_PREVIEWS = frozenset({
    "eala-anisimova", "eala-mcnally", "fonseca-oconnell", "shang-nishikori",
    "shang-rublev", "venus-potapova", "wang-sabalenka", "wong-lehecka",
    "zheng-eala",
})


def test_不再做比赛前瞻():
    """账号所有者 2026-08-17：「**不要做比赛前瞻，这不是网球有故事的内容**」。

    来路：我扫完当天的比赛日，挑了威廉姆斯姐妹重组打双打那条，做成了一条
    「开球之前」——事实全部两个源核过、四道选图闸门逐条走过、全量绿、PR 都开了。
    **东西没做错，是这个品类不该做。** 账号所有者看到之后一句话把它停掉。

    ⚠️ **为什么要落成判据，而不是记在对话里。** 写这条的时候，`开球之前` 名下
    已经有 9 条，其中三条（`eala-anisimova` / `fonseca-oconnell` /
    `wang-sabalenka`）是**当天别的会话刚推上 main 的**——也就是说这条线正在被
    好几个会话同时生产。一条只活在某一次对话里的决定，拦不住下一个会话，
    也拦不住换了上下文之后的我自己。CLAUDE.md 那句「要长期记住的东西，写进文件，
    别留在上下文里」说的正是这个。

    ⚠️ **停的是栏目，不是底下那套工具**（和日报那次同一个形状）：`COLUMNS` 里
    那一条、封面的比赛坐标两行、`perishable` 那套过期逻辑全部留着——已经发出去的
    9 条还要能渲、能查。**变的只有「不再往里加新的」。**

    真要恢复：把这条测试连同它的理由一起改掉，别只往豁免表里塞一个名字。
    """
    from tennislive.video.explainer import _SCRIPTS, explainer_column

    now = {s for s in _SCRIPTS if explainer_column(s) == "开球之前"}

    # 判据自己的判据①：豁免表里的每一条都得真的存在、真的还是这个栏目。
    # 少了这一条，写错一个名字就等于凭空多放行一条新片子。
    stale = _LEGACY_PREVIEWS - now
    assert not stale, (
        f"豁免表里这几条已经不是「开球之前」了（或者名字写错了）：{sorted(stale)}。"
        "表要跟着现实走——一个会过期的名单和一条常年红的检查是同一个毛病")

    # 判据自己的判据②：表不能是空的，否则下面那句是在拿空集比空集。
    assert _LEGACY_PREVIEWS, "豁免表空了，这条判据失效了"

    fresh = sorted(now - _LEGACY_PREVIEWS)
    assert not fresh, (
        f"这几条是新的「开球之前」：{fresh}\n"
        "⚠️ 账号所有者定过：**不要做比赛前瞻，这不是网球有故事的内容**。\n"
        "比赛还没打的前瞻不做了——想讲这两个人，等球打完做「赛场之上」，"
        "或者把他们的来路做成常青的「网球有故事」。")
