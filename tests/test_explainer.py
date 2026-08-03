import html
import json
import re
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

    assert speakable("辛纳 6-3、6-2、5-1 领先") == "辛纳 6 比 3、6 比 2、5 比 1 领先"
    assert speakable("70-68 拿下第五盘") == "70 比 68 拿下第五盘"
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
    from tennislive.zh.players import PLAYER_ZH

    # 判据和 test_人名要以译名表为准 用的是同一份表，外加那份「同一个人的
    # 另一种叫法」白名单——封面上的名字没有上下文消歧，更不该是手打的。
    known = set(PLAYER_ZH.values()) | _ON_PURPOSE

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
    # 比分要和耳朵对上：屏幕上是 6-4，念出来和字幕里都是「6 比 4」。
    assert any("6 比 4" in shown for _, _, shown in lines), lines
    # 相邻两行在原文里首尾相接——中间掉字的话，时间轴也会跟着错位。
    for (_, end, _), (start, _, _) in zip(lines, lines[1:]):
        assert start == end


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


def test_成片链接和图片走同一条_CDN():
    """一封推送里两条路，慢的那条是没走 CDN 的那条。

    视频链接原来指向 `github.com/<repo>/raw/main/…`，它 302 跳到
    raw.githubusercontent.com——那台机器国内既没有节点也没有 CDN，点开要等很久。
    同一封信里的图片一直是好的，因为图片走 jsDelivr（Cloudflare 边缘）。

    写成 `@main` 还有第二层用处：`pin_asset_revision` 只认 jsDelivr 的 `@main`，
    换过去之后视频会和图片**一起**被钉到本次 commit 上。钉住的链接 jsDelivr 给的是
    immutable + 一年 TTL；而且成片被下一次生成覆盖之后，老推送里的链接仍然指向
    当初那一版。
    """
    import datetime
    from pathlib import Path as _Path

    from tennislive.render.pushmsg import pin_asset_revision
    from tennislive.video import explainer as E

    outdir = _Path("output/2026-07-27/explainer/shang-nishikori")
    segs = E.explainer_script(find_story_by_slug("shang-nishikori"))
    html = E.explainer_push_html(
        segs, outdir, date=datetime.date(2026, 7, 27), xhs_text="测试文案")

    assert "/raw/main/" not in html, "视频还在走 raw.githubusercontent"
    urls = [u for u in html.replace("'", '"').split('"') if u.endswith("explainer.mp4")]
    assert urls, "推送里没有成片链接"
    from tennislive.cdn import jsdelivr_host

    assert urls[0].startswith(
        f"https://{jsdelivr_host()}/gh/{E._REPOSITORY}@main/"), urls[0]

    rev = "37853825db235e7290df16fe890d00d556327d94"
    pinned = pin_asset_revision(html, rev)
    assert f"@{rev}/{outdir.as_posix()}/explainer.mp4" in pinned, "视频没跟着图片一起钉版本"
    assert f"@{rev}/{outdir.as_posix()}/slide_00.jpg" in pinned, "图片没被钉住"
    assert "@main/" not in pinned


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
_TYPO_SAFE = ("巴基斯坦",)


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
    from tennislive.zh.players import PLAYER_ZH

    known = sorted(set(PLAYER_ZH.values()) | _ON_PURPOSE, key=len, reverse=True)
    canon = [n for n in known if len(n) >= 4]

    def strip_known(text: str) -> str:
        for name in known:          # 长的先遮，短名才不会把长名切碎
            text = text.replace(name, "　" * len(name))
        return text

    bad = []

    def scan(where: str, text: str) -> None:
        safe = text
        for word in _TYPO_SAFE:
            safe = safe.replace(word, "　" * len(word))
        for wrong, right in _KNOWN_TYPOS.items():
            if wrong in safe:
                bad.append(f"{where}：「{wrong}」写错了，表里是「{right}」")
        masked = strip_known(text)
        for name in canon:
            # ① 等长、恰好差一个字：「里巴金娜」之于「莱巴金娜」
            width = len(name)
            for i in range(len(masked) - width + 1):
                window = masked[i:i + width]
                if not all("一" <= c <= "鿿" or c == "·" for c in window):
                    continue
                if sum(a != b for a, b in zip(window, name)) == 1:
                    bad.append(f"{where}：「{window}」是不是想写「{name}」")

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
            short = width - 1
            if short < 4 or "·" in name:
                continue
            head = name[:short]
            for i in range(len(masked) - short + 1):
                window = masked[i:i + short]
                if not all("一" <= c <= "鿿" for c in window):
                    continue
                if sum(a != b for a, b in zip(window, head)) == 1:
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
    assert not bad, "人名和译名表对不上：\n  " + "\n  ".join(sorted(set(bad)))


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

