import html
import re

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
    ("莱巴金娜",), ("普利斯科娃",),
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

    「开赛之前」和「网球有故事」并行，两者的保质期完全不同：知识片明年再翻出来
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
    assert meta["rate"] == E.DEFAULT_RATE == "+22%"
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
    """一天不止一条「开赛之前」——两条前瞻不能互相覆盖。

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

    # 并且「开赛之前」这个栏目此刻确实挂着不止一条片子——不是理论上支持而已。
    from tennislive.video.explainer import explainer_column

    previews = [s for s in _SCRIPTED if explainer_column(s) == "开赛之前"]
    assert len(previews) >= 2, f"开赛之前只有 {previews}，多场并存没有真的被用起来"
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
