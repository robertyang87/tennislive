"""「网球有故事」字卡稿（`explainer._SCRIPTS`）的**渲前预检**：一个 slug，几秒钟。

    python tools/explainer_preflight.py --slug <slug> [--date today|YYYY-MM-DD]

不碰 TTS、ffmpeg、Chromium，也不上网——只读稿子本身，所以能排在 `explainer.yml`
的**第一步**（装字体、Chromium、ffmpeg 之前），本地写稿时也能随手跑。

## 来路

竖版短片那条线有 `--dry-run`（0.2 秒，`validate_spec` 里几十道闸），采访线至少有
`production_preflight`；**解说片这条线一道渲前闸都没有**——`explainer.yml` 直接
`tennislive explainer`，编辑口径的判据全活在 `tests/test_explainer*.py` 里，
分支上的稿子可以带着红着的判据渲出来、推出去（2026-09-27 全库取证量的）：

| 返工 | 是什么 | 这里对应的那一项 |
|---|---|---|
| f58553ef | `wawrinka-wildcard`「一共只进过三次大满贯决赛」——是四次，推了微信才被指出 | 全称断言 |
| 2c38adef | `ranking-math`「多哈和迪拜逐年轮换」——2024 年就停了，读者当众指出 | 多哈迪拜轮换 |
| d18bba31 | `second-serve-clock` 带着 1118 字的正文发出去；闸在渲完之后才跑 | 小红书正文 1000 字 |
| 4ddea136 / 20ac8457 | 切词、引号，渲完读 `words.json` 才发现 | 假词（射程只有量过的那几个） |
| 2756cec3 | `qualifier-ceiling`「北京时间今天，美网正赛开打」——常青栏目钉死了发布那一天 | 相对时间词 |

⚠️ **1000 字那道闸原来就有，只是排错了位置**：`cli.cmd_explainer` 先
`generate_explainer_video()`（TTS + ffmpeg，几分钟），**之后**才 `to_copy_page()`
→ `split_xhs()` 拦超长——红在那儿要白烧一整趟渲染。

## 单一出处

这里的每一项都是**同一个判据**，不是抄一份：`tests/test_explainer*.py` 里对应的
全库扫描现在调的就是这里的函数（名单、阈值、豁免表也挪到了这儿）。写两处必分叉，
而分叉的样子是「测试红、预检绿」或者反过来——那是这个仓库栽过最多次的形状。

⚠️ **人名近似匹配（`test_人名要以译名表为准`）不在这儿**：那一道横跨三条线、
带着四张手工表，拆出来是另一件事；它仍然只在测试里（全库 4 秒）。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "tools"))

from tennislive.render.tournament_story import find_story_by_slug  # noqa: E402
from tennislive.video import explainer as E  # noqa: E402

import absolute_claims  # noqa: E402
import reel_facts  # noqa: E402


# ── 片长／首句那一组（原来在 tests/test_explainer_budget.py，量法和来路都在那儿）──

#: 字/秒，`+22%` 那一档实测中位（n=6，5.69–6.13）。换语速必须重量，
#: 判据 `test_预算是按当前语速算的不是两簇的中位`。
SPEECH_RATE = 5.98
#: 决定窗口：抖音 5 秒内走掉 62%。片头静音占掉 0.6 秒，剩下的才归第一句。
HOOK_SECONDS = 5.0
HOOK_BUDGET = round((HOOK_SECONDS - E.LEAD_SILENCE) * SPEECH_RATE)

#: 封面第一句超出决定窗口的老片子。只许降不许升，改短到窗口里就删掉。
HOOK_TOO_LONG = {
    "venus-potapova": 38,
    "zheng-eala": 31,
}

#: 封面那一问排不进一行、退回两行的片子。**只许减不许加**（两行版必然把一个词劈开）。
COVER_TWO_LINES = frozenset({
    "comeback-middle",   # 伤好了打不出来，是低谷还是终点？
    "thiem-football",    # 美网冠军退役两年后，在哪儿比赛？
    "zheng-eala",        # 三年前钦文赢了那个人，这次呢？
    "venus-potapova",    # 46 岁了，维纳斯为什么还在打？
    "wildcard",          # 签表里名字旁的 WC，是谁给的？
})


def spoken_chars(text: str) -> int:
    """按合成器实际要念的字数算：走 speakable()，去掉空白。

    `speakable` 里有给合成器纠音的替换（挑→选之类），念的是那一版，所以
    字数也该按那一版数。标点不发音但会停顿，忽略它带来的误差在 ±5% 以内。
    """
    return len(re.sub(r"\s", "", E.speakable(text)))


def first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。？！?!])", text.strip())
    return next((p for p in parts if p.strip()), text)


def cover_one_line_px(question: str) -> int:
    """这一问排成一行时字号会是多少——调生产用的那个算式，不另写一套。"""
    return int((E.W - 140) * E._COVER_WIDTH_MARGIN / E._cover_title_em(question))


# ── 字卡要认领（原来在 tests/test_explainer.py） ──────────────────────────

#: 2026-09-17 之前用**字卡**做的 40 条「网球有故事」。⚠️ **只许减不许加**：
#: 新片的默认是视频剪辑（`specs/reels/<slug>.json`，`cover.eyebrow` 写「网球有故事」），
#: 真要走字卡，在 `_OPENINGS[slug]["cards_why"]` 里写清为什么。
CARD_DECK_LEGACY = frozenset({
    "ball-pick", "big-three", "bu-lucky-loser", "challenger-climb",
    "comeback-middle", "cramp-timeout", "entry-deadline", "equal-pay",
    "finals-venues", "gamesmanship", "gauff-right-coco", "golden-masters",
    "hawkeye", "heat-rule", "kostyuk-champion-test", "longest-match",
    "lucky-loser", "mandatory-1000", "masters-format", "nadal-academy",
    "pr-allowance", "promotional-fees", "protected-ranking", "qualifier-ceiling",
    "queue", "roof", "rufus", "second-serve-clock",
    "shot-clock", "special-exempt", "svitolina-handshake", "ten-champions",
    "thiem-football", "tour-balls", "wawrinka-wildcard", "weeks-at-no1",
    "wildcard", "wimbledon-whites", "wuhan-alternate", "yellow-ball",
})

#: 标题「🎾<日期> <栏目>｜<选题>」里**最宽**的那个日期。日期是 `f"{月}.{日}"`，
#: 10.10–12.31 比 9.27 宽一个半角（0.5 字位）——拿「今天」去量标题字位，等于只替
#: 今天这个日期量：9 月里过得了的标题，同一条稿子 10 月重渲就超 20。所以测试和
#: 默认口径一律按最宽的量（2026-09-27 对抗 review 指出来的：测试原来钉的 7.26 /
#: 9.27 都是窄的那一档，`a-plus-wildcard` 当时的标题「ATP 500 有第 4 张外卡」在两位数的
#: 月份里是 20.5——同日改成「ATP 500 第 4 张外卡」，最宽 19.5）。
WIDEST_DATE_LABEL = "12.28"

#: 按 `WIDEST_DATE_LABEL` 量、标题超 20 字位的**已发**稿子：{slug: 最宽日期下的字位}。
#: ⚠️ **只许降不许升**（和 `HOOK_TOO_LONG` 同一个形状）：豁免的是「装闸之前已经
#: 按窄日期发出去了」，不是「这条标题合格」——十月以后重渲它，小红书照样截断；
#: 真要重渲先把选题标题改短，改完从这儿删掉。
#: 2026-09-27 已清空：唯一一条 `a-plus-wildcard`（20.5）把选题标题改成
#: 「ATP 500 第 4 张外卡」（最宽日期 19.5）。⚠️ 省的是「有」字，**不是**级别中间那个空格：
#: 同一条稿子的 chips／封面台头／示意图／小红书钩子，和全部故事卡的 chips 都写「ATP 500」，
#: 只把标题改成连写的「ATP500」，一条稿子里就有两种写法（级别连写是「赛场之上」顶栏和
#: 封面副标题的规矩，不管解说片）。
#: 已发的那条不重渲——改的只是下一次重渲会用的标题。
TITLE_TOO_WIDE: dict[str, float] = {}

#: 旁白里已知会被切词器念错的串，已经发出去的那几处。只许减不许加。
FAKE_WORDS_LEGACY = frozenset({
    # 挑战赛那条第 ④ 屏：「规则书写着挑战赛必须给正赛球员提供免费房间」。
    ("challenger-climb", "floor", "规则书写"),
    # 强制大师赛那条的**封面**旁白：「规则书写着自动生效、不可申诉」。
    ("mandatory-1000", "__cover__", "规则书写"),
})

#: 同一句里排名半中半洋，定判据之前已经发出去的。只许减不许加。
MIXED_RANK_LEGACY = frozenset({
    "big-three",  # 「德约科维奇从第五掉到第12」，2026-09-15 已发
})

#: 常青栏目里钉死在发布那一天的相对时间词，装闸之前已经发出去的。只许减不许加。
#: 认领口 `_OPENINGS[slug]["dated_why"]`（和 `cards_why` 同一个位置）。
DATED_WORDS_LEGACY = frozenset({
    "golden-masters",         # 「北京时间今天凌晨，多伦多」
    "kostyuk-champion-test",  # 「就是刚刚结束的辛辛那提」
    "wuhan-alternate",        # 「今天公布的首批名单里」
})

# 同一句里中文年份和阿拉伯年份被一个连接词夹在一起，两个方向都要拦。
_MIXED_YEAR = re.compile(
    r"(?:[一二三四五六七八九〇]{4}\s*[到至和与、]\s*\d{4})"
    r"|(?:\d{4}\s*年?\s*[到至和与、]\s*[一二三四五六七八九〇]{4})"
)
_RANK_CLASSIFIERS = "轮次盘个局场章届座条区号种批期周年岁天名位张代任"
_RANK_CN = re.compile(rf"第[一二三四五六七八九十]+(?![一二三四五六七八九十\d{_RANK_CLASSIFIERS}])")
_RANK_AR = re.compile(rf"第\s*\d+(?![\d{_RANK_CLASSIFIERS}])")

# 多哈／迪拜那条轮换：2024 年就停了，提它必须把终止年一起写出来（2c38adef）。
ROTATION_STATIONS = re.compile(r"多哈|迪拜")
ROTATION_WORD = re.compile(r"轮换")
#: 旁白喂 TTS 写汉字、上屏和正文写阿拉伯数字，所以两种都认。
ROTATION_ENDED = re.compile(r"2024|二〇二四")

# 末屏那一问和封面那一问比字集重合度时，不算这些虚字和标点。
_ECHO_DROP = set("的了是在有和与也都就还你我他她它们这那什么吗呢啊，。？！、：；—…「」《》")


def rotation_problem(text: str) -> bool:
    """提了多哈／迪拜的轮换，却没写它 2024 年就停了。"""
    return bool(ROTATION_STATIONS.search(text) and ROTATION_WORD.search(text)
                and not ROTATION_ENDED.search(text))


def spoken_texts(slug: str):
    """这条稿子**会过 TTS** 的文本：(段名, 旁白)。封面旁白记成 `__cover__`。

    ⚠️ 两个面：段旁白在 `_SCRIPTS` 里，封面旁白在 `_OPENINGS[slug]["narration"]`——
    `mandatory-1000` 那处假词正是落在封面上的。`_CAPTIONS` 没人念，不在这儿。
    """
    for beat in E._SCRIPTS.get(slug, ()):
        narration = beat[3] if len(beat) > 3 else ""
        if isinstance(narration, str) and narration:
            yield beat[0], narration
    narration = (E._OPENINGS.get(slug) or {}).get("narration", "")
    if isinstance(narration, str) and narration:
        yield "__cover__", narration


# ── 一条稿子 ────────────────────────────────────────────────────────────

class PreflightError(RuntimeError):
    """这条稿子连装都装不起来（slug 没注册、脚本拼不出来）。"""


@dataclass
class Deck:
    slug: str
    story: object
    segments: list
    date_label: str
    xhs: str

    @property
    def opening(self) -> dict:
        return E._OPENINGS.get(self.slug) or {}

    @property
    def beats(self) -> list:
        return [s for s in self.segments if s.kind != "cover"]


def load_deck(slug: str, date_label: str = WIDEST_DATE_LABEL) -> Deck:
    story = find_story_by_slug(slug)
    if story is None:
        raise PreflightError(f"找不到 slug 为「{slug}」的选题（tournament_story 里没注册）")
    try:
        segments = E.explainer_script(story)
    except Exception as exc:  # noqa: BLE001 — 拼不出来本身就是这一项的结论
        raise PreflightError(f"{slug} 的脚本拼不出来：{exc}") from exc
    xhs = E.explainer_xiaohongshu(story, segments, date_label)
    return Deck(slug, story, segments, date_label, xhs)


# ── 每一项：Deck → 问题列表（空＝合格） ──────────────────────────────────

def column_problems(deck: Deck) -> list[str]:
    try:
        E.column_of(deck.slug)
    except KeyError as exc:
        return [str(exc).strip("'\"")]
    return []


def copy_body_problems(deck: Deck) -> list[str]:
    """小红书正文那一格 1000 字，超了粘不进去——用复制页那个共用的 `split_xhs`。"""
    from tennislive.render.pushmsg import split_xhs  # noqa: PLC0415

    try:
        split_xhs(deck.xhs)
    except SystemExit as exc:
        return [f"{deck.slug}：{exc}"]
    return []


def copy_title_problems(deck: Deck) -> list[str]:
    """The final copy title has no whitespace and at most 20 characters."""
    from tennislive.render.copy_title import make_copy_title, validate_copy_title  # noqa: PLC0415

    head = deck.xhs.splitlines()[0] if deck.xhs.splitlines() else ""
    problems = []
    try:
        validate_copy_title(head, require_prefix=True)
        if make_copy_title(deck.date_label, E.explainer_column(deck.slug),
                           deck.story.title, slug=deck.slug) != head:
            problems.append(f"{deck.slug} 标题与选题不符：{head}")
    except SystemExit as exc:
        problems.append(f"{deck.slug}：{exc}")
    return problems


def tag_problems(deck: Deck) -> list[str]:
    """小红书标签最多五个，要放满、不许重复、账号名要在。"""
    tags = [w for w in deck.xhs.split() if w.startswith("#")]
    problems = []
    if len(tags) != 5:
        problems.append(
            f"{deck.slug} 的文案里有 {len(tags)} 个标签：{' '.join(tags)}——"
            "要放满五个，在 _CAPTIONS 里给它写自己的五个")
    if len(set(tags)) != len(tags):
        problems.append(f"{deck.slug} 的标签有重复：{' '.join(tags)}")
    if "#网球时差" not in tags:
        problems.append(f"{deck.slug} 的标签里没有 #网球时差：{' '.join(tags)}")
    return problems


def hook_budget_problems(deck: Deck) -> list[str]:
    """封面第一句要在 5 秒的决定窗口里说完（首句预算 `HOOK_BUDGET` 字）。"""
    got = spoken_chars(first_sentence(deck.segments[0].narration))
    if deck.slug in HOOK_TOO_LONG:
        was = HOOK_TOO_LONG[deck.slug]
        return ([] if got <= was else
                [f"{deck.slug} 封面第一句从 {was} 字涨到 {got} 字，只许降不许升。"])
    if got <= HOOK_BUDGET:
        return []
    return [
        f"{deck.slug} 封面第一句 {got} 字 ≈ {got / SPEECH_RATE + E.LEAD_SILENCE:.1f} 秒，"
        f"超出 {HOOK_SECONDS:g} 秒的决定窗口（上限 {HOOK_BUDGET} 字）。"
        "把第一句砍短，把交代挪到第二句——前 5 秒决定 62% 的人走不走。"]


def cover_one_line_problems(deck: Deck) -> list[str]:
    """封面那一问要排得进一行，否则两行版会在某个词中间劈开。"""
    question = deck.opening.get("question")
    if not question or deck.slug in COVER_TWO_LINES:
        return []
    got = cover_one_line_px(question)
    if got >= E._COVER_MIN_ONE_LINE_PX:
        return []
    return [
        f"{deck.slug} 的封面问题「{question}」排一行只能到 {got}px，"
        f"低于 {E._COVER_MIN_ONE_LINE_PX}px，会退回两行并在词中间断开。"
        "改短它，或者显式加进 COVER_TWO_LINES 并说明为什么可以。"]


def cover_question_problems(deck: Deck) -> list[str]:
    """第一屏是开场问题卡：问出一个问题、每行不超 16 字、不带要点。"""
    cover = deck.segments[0]
    problems = []
    if cover.kind != "cover":
        return [f"{deck.slug} 第一屏不是开场问题卡"]
    if not cover.title.endswith("？"):
        problems.append(f"{deck.slug} 开场没有问出一个问题：{cover.title}")
    for line in E.cover_title_lines(cover.title):
        if len(line) > 16:
            problems.append(f"{deck.slug} 开场问题有一行太长：{line}")
    if not (cover.title[:6] in cover.narration or "？" in cover.narration):
        problems.append(f"{deck.slug} 封面旁白没把那一问念出来：{cover.narration[:40]}")
    if cover.points:
        problems.append(f"{deck.slug} 封面只问问题，不带要点：{cover.points}")
    return problems


def cards_why_problems(deck: Deck) -> list[str]:
    """新的「网球有故事」默认走视频剪辑；走字卡要在 `_OPENINGS[slug]["cards_why"]` 认领。"""
    if deck.slug in E._ARCHIVED_DECKS or deck.slug in CARD_DECK_LEGACY:
        return []
    if str(deck.opening.get("cards_why", "")).strip():
        return []
    return [
        f"{deck.slug} 是新的「网球有故事」，走了字卡却没说为什么。默认那条路是**视频剪辑**"
        "（`specs/reels/<slug>.json`，`cover.eyebrow` 写「网球有故事」）；真要走字卡，在 "
        '`_OPENINGS[slug]["cards_why"]` 里写清是哪一种例外：天然图表题材，'
        "或者完全找不到可用画面。"]


def title_mark_problems(deck: Deck) -> list[str]:
    """大标题里不许有冒号；旁白、标题、要点里不许留 markdown 记号。"""
    problems = []
    for seg in deck.segments:
        if "：" in seg.title or ":" in seg.title:
            problems.append(f"{deck.slug}/{seg.kind} 大标题里有冒号：{seg.title}")
        for field, text in (("旁白", seg.narration), ("标题", seg.title)):
            if re.search(r"[*`_#]", text):
                problems.append(f"{deck.slug}/{seg.kind} 的{field}里有 markdown 记号：{text[:40]}")
        for point in seg.points:
            if re.search(r"[*`_#]", point):
                problems.append(f"{deck.slug}/{seg.kind} 要点里有记号：{point}")
    return problems


def beat_points_problems(deck: Deck) -> list[str]:
    """每屏 2–3 条要点、每条不超 30 字；标题不许把自己的标签再说一遍。"""
    problems = []
    for seg in deck.beats:
        if not 2 <= len(seg.points) <= 3:
            problems.append(f"{deck.slug}/{seg.kind} 要点数量不对：{len(seg.points)} 条")
        if not all(p.strip() for p in seg.points):
            problems.append(f"{deck.slug}/{seg.kind} 有空要点")
        long = [p for p in seg.points if len(p) > 30]
        if long:
            problems.append(f"{deck.slug}/{seg.kind} 要点太长：{long}")
        if seg.label in seg.title:
            problems.append(f"{deck.slug}/{seg.kind} 标题里重复了标签「{seg.label}」：{seg.title}")
    return problems


def closer_problems(deck: Deck) -> list[str]:
    """末屏那一问：旁白要问出来、不许问两遍、不许是封面那一问的回声。"""
    closer = deck.segments[-1]
    if not closer.question:
        return [f"{deck.slug} 末屏没有互动提问"]
    problems = []
    spoken = E.speakable(closer.narration)
    if "？" not in spoken[-40:]:
        problems.append(f"{deck.slug} 旁白结尾没有问出来：…{spoken[-30:]}")
    core = closer.question.rstrip("？?")
    if spoken.count(core) > 1:
        problems.append(f"{deck.slug} 同一个问题问了两遍：{core}")

    def chars(text: str) -> set[str]:
        return {c for c in text if c not in _ECHO_DROP and not c.isspace()}

    cover = chars(f"{deck.segments[0].title}{deck.segments[0].question or ''}")
    tail = chars(closer.question.strip())
    ratio = len(cover & tail) / len(cover | tail) if cover | tail else 0.0
    if ratio >= 0.5:
        problems.append(
            f"{deck.slug} 末屏那一问和封面重了（{ratio:.0%}）："
            f"封面「{deck.segments[0].title}」／末屏「{closer.question}」")
    return problems


def reading_problems(deck: Deck) -> list[str]:
    """配音读法：比分的「-」会被念成「杠」。

    ⚠️ 原来还有一半：「挑」只许留在挑战／挑衅这类词里（别的都该被 挑→选 换掉）。
    2026-09-27 挑→选 整条拿掉了——量出来原文「挑球」已经读 tiāo，而挑高球那个「挑」
    换成「选」是另一个词（`video/pronounce.py` 表头注释）——所以这一半的前提不在了。
    挑高／挑起／挑回 的 tiǎo 读偏归 `check_polyphones.REWRITE_ONLY` 提醒。"""
    problems = []
    for seg in deck.segments:
        spoken = E.speakable(seg.narration)
        if re.search(r"(?<!\d)\d{1,3}\s*[-–—−]\s*\d{1,3}(?!\d)", spoken):
            problems.append(f"{deck.slug}/{seg.kind} 旁白里还有会被读成「杠」的比分：{spoken[:60]}")
    return problems


def fake_word_problems(deck: Deck) -> list[str]:
    """切词器会念错、而渲出来一个像素都看不出来的那几个串（`FAKE_WORDS`）。"""
    from tennislive.zh.tts_fake_words import FAKE_WORDS  # noqa: PLC0415

    return [
        f"{deck.slug} / {seg}：「{pat}」——{why}"
        for seg, text in spoken_texts(deck.slug)
        for pat, why in FAKE_WORDS.items()
        if pat in text and (deck.slug, seg, pat) not in FAKE_WORDS_LEGACY
    ]


def mixed_year_hits(deck: Deck) -> list[str]:
    return [f"{deck.slug} 第 {i} 段：…{m.group(0)}…"
            for i, seg in enumerate(deck.segments)
            for m in _MIXED_YEAR.finditer(E.arabic_numerals(seg.narration))]


def mixed_rank_hits(deck: Deck) -> list[str]:
    hits = []
    for i, seg in enumerate(deck.segments):
        for sentence in re.split(r"[。！？；]", E.arabic_numerals(seg.narration)):
            if _RANK_CN.search(sentence) and _RANK_AR.search(sentence):
                hits.append(f"{deck.slug} 第 {i} 段：{sentence}")
    return hits


def numeral_problems(deck: Deck) -> list[str]:
    """字幕里同一句的年份／排名不许一个中文一个阿拉伯数字（渲完抽帧才看得见的那种）。"""
    problems = [f"年份半中半洋（写成「二〇二五年到二〇二七年」）：{h}"
                for h in mixed_year_hits(deck)]
    if deck.slug not in MIXED_RANK_LEGACY:
        problems += [f"排名半中半洋（旁白写「世界第三」，转换器会一律换成数字）：{h}"
                     for h in mixed_rank_hits(deck)]
    return problems


def outward_texts(deck: Deck) -> list[str]:
    """这条稿子会发到读者眼前的字：每屏标题、旁白、问句、小标、示意图、注释、要点，
    封面台头与注释，小红书钩子（正文不扫）。"""
    texts: list[str] = []
    for seg in deck.segments:
        texts += [seg.title, seg.narration, seg.question or "", seg.label,
                  seg.diagram or "", seg.gloss or "", *seg.points]
    texts += [str(deck.opening.get("topic", "")), str(deck.opening.get("gloss", ""))]
    texts.append(str((E._CAPTIONS.get(deck.slug) or {}).get("hook", "")))
    return [t for t in texts if t]


def rotation_problems(deck: Deck) -> list[str]:
    """提多哈／迪拜的轮换，必须写出它 2024 年就停了（2c38adef）。"""
    texts = outward_texts(deck) + [str(deck.story.hero_fact), *map(str, deck.story.facts)]
    return [f"{deck.slug}：提了多哈／迪拜的轮换，却没写它 2024 年就停了——{t[:80]}"
            for t in texts if rotation_problem(t)]


def claim_problems(deck: Deck) -> list[str]:
    """全称断言（含「一共只进过三次决赛，三次全部拿下」这种计数式）要两个独立源。"""
    if deck.slug in absolute_claims.EXPLAINER_LEGACY:
        return []
    missing = absolute_claims.unsourced(outward_texts(deck), E._CLAIMS.get(deck.slug))
    if not missing:
        return []
    return [absolute_claims.problem_text(
        missing, f"`explainer._CLAIMS[{deck.slug!r}]`")]


def dated_word_problems(deck: Deck) -> list[str]:
    """常青栏目不许把一件事钉在发布那一天（「北京时间今天」「今晚」「刚刚结束」）。

    ⚠️ 栏目认不出（没登记、或者撤掉了）时 `column_of` 会抛——这一项就**判不了**是
    常青还是易逝，报成一行 ✗，而不是让整份预检炸成一段 traceback（「判不了」不是
    「没问题」，也不该把其余十几项的报告一起吞掉）。真因在「栏目」那一项里。
    """
    try:
        perishable = E.column_of(deck.slug).perishable
    except KeyError as exc:
        why = str(exc).strip("'\"")
        return [f"{deck.slug}：栏目认不出（{why}），判不了是不是常青栏目——先修「栏目」那一项"]
    if perishable or deck.slug in DATED_WORDS_LEGACY:
        return []
    if str(deck.opening.get("dated_why", "")).strip():
        return []
    texts = [seg.narration for seg in deck.segments] + [seg.title for seg in deck.segments]
    texts.append(str((E._CAPTIONS.get(deck.slug) or {}).get("hook", "")))
    hits = reel_facts.dated_word_hits(texts)
    if not hits:
        return []
    return [
        f"{deck.slug}：「{E.explainer_column(deck.slug)}」是常青栏目，旁白/标题/钩子里却"
        f"钉着发布那一天：{hits}。讲已经发生的事写绝对日期（「8 月 30 日」），讲现状写"
        "「现在」；真要钉在那一天，在 `_OPENINGS[slug][\"dated_why\"]` 里写清为什么。"
        "（qualifier-ceiling 2756cec3：「北京时间今天，美网正赛开打」）"]


#: (名字, 判据)。顺序就是报告的顺序；**加一项就要在测试里给它一个会红的例子**。
CHECKS: tuple[tuple[str, Callable[[Deck], list[str]]], ...] = (
    ("栏目", column_problems),
    ("小红书正文 1000 字", copy_body_problems),
    ("标题字位", copy_title_problems),
    ("标签", tag_problems),
    ("封面首句窗口", hook_budget_problems),
    ("封面一行", cover_one_line_problems),
    ("开场问题卡", cover_question_problems),
    ("字卡认领", cards_why_problems),
    ("冒号与记号", title_mark_problems),
    ("每屏要点", beat_points_problems),
    ("末屏一问", closer_problems),
    ("配音读法", reading_problems),
    ("假词", fake_word_problems),
    ("数字半中半洋", numeral_problems),
    ("多哈迪拜轮换", rotation_problems),
    ("全称断言", claim_problems),
    ("相对时间词", dated_word_problems),
)


def preflight(slug: str, date_label: str = WIDEST_DATE_LABEL) -> list[tuple[str, list[str]]]:
    """每一项的 (名字, 问题列表)——**合格的也列出来**，只在出错时出声的检查证明不了它看过。"""
    deck = load_deck(slug, date_label)
    return [(name, check(deck)) for name, check in CHECKS]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--slug", required=True, help="字卡稿 slug（explainer._SCRIPTS 的键）")
    ap.add_argument("--date", default="today",
                    help="北京日期，和 `tennislive explainer --date` 同一个口径（默认 today）")
    args = ap.parse_args(argv)

    from tennislive.timeutil import parse_date_arg  # noqa: PLC0415

    d = parse_date_arg(args.date)
    label = f"{d.month}.{d.day}"
    try:
        results = preflight(args.slug, label)
    except PreflightError as exc:
        print(f"[预检] {exc}")
        return 2
    bad = [(name, problems) for name, problems in results if problems]
    print(f"[预检] {args.slug}（{E.explainer_column(args.slug)}，按 {label} 出文案）"
          f" 共 {len(results)} 项，不合格 {len(bad)} 项")
    for name, problems in results:
        print(f"  {'✗' if problems else '✓'} {name}")
        for problem in problems:
            for line in problem.splitlines():
                print(f"      {line}")
    if bad:
        print("修完再渲——这些都只读稿子本身，不用等 TTS 和 ffmpeg。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
