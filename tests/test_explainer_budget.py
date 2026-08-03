"""片长预算：旁白写多长，片子就多长。

三家平台的后台数据摆在一起，最硬的一条是**片长和实际消费差一个数量级**：

    片长中位 140s ──── 平均播放时长 小红书 21s / 抖音 20s / 视频号 13s
                  └─── 真完播率     抖音 2.0% / 视频号 2.9%

也就是 97–98% 的人没看到结尾。而末屏那一问、收尾屏必须在球场上、字幕不越漂
越多——花最大力气打磨的东西全在 100 秒之后。

片长不是渲染参数决定的，是**旁白字数**决定的：`assemble_explainer_video` 里
每屏时长 = 该屏旁白的音频长度，首尾各加一点静音。所以能机械卡住的闸门只有
一个，就是字数。

## 两条闸门

1. **总字数** —— 决定片子多长。
2. **封面第一句** —— 决定 62% 的人拿到的是不是一个完整的意思。抖音的留存
   数据：5 秒内走掉 62%，前 2 秒走掉 37%。一句话在第 5 秒还没说完，那 62%
   的人听到的就是半截。

## 老片子不改，新片子按预算做

已经发出去的片子**不回头重排**（编辑决定）。所以下面那张名单是**祖父名单**，
不是待还的债：它的作用只有一个——挡住老片子继续变长。新片子不在名单里，必须
直接达标。

唯一重排过的是 masters-format（705 字 → 349 字），当时是拿它验证「答案提到
第 ① 屏」这个做法可行；它没有发布，所以也没有对照数据回来。

## 语速是量出来的，而且它变过

拿成片时长反推 `字数 ÷ (片长 − 首尾静音)`，16 条片子分成清清楚楚的两簇：

    4.93 – 5.10 字/秒   longest-match、yellow-ball、ten-champions、queue、
                        wimbledon-whites、hawkeye(07-25)、rufus
    5.82 – 6.25 字/秒   hawkeye(07-26)、masters-format、roof、ball-pick、
                        shot-clock、shang-nishikori、venus-potapova、zheng-eala

**同一份 hawkeye 脚本渲了两次，字数一模一样 681，片长 135.5s 对 119.1s。**
快的那批就是落了 `narration.json`（`rate: +22%`）的那批。所以预算按**当前
这一档**算，不按两簇的中位——用中位会把预算放宽两成，而新片子全按快的渲。

`+28%` 那一档已经量过了，`SPEECH_RATE` 是实测值不是估的。按落库成片
（`narration.json` 里记着当时用的 rate）反推：

    +22%   n=6   5.69 – 6.13   中位 5.98
    +28%   n=3   6.11 – 6.80   中位 6.38   ← 现在这一档

**换语速之后必须重量，别按比例推。** 从 +22% 到 +28%，SSML 参数只涨了 4.9%，
实测字/秒涨了 6.7%；而更早那次换档，两簇之间差了两成。比例推每次都推歪。

`+28%` 这一档只有三条（6.11 / 6.38 / 6.80），极差 11%，所以这个数还会动。
再多几条成片就重量一次——量法：找 `output/**/narration.json` 里 rate 对得上的，
`字数 ÷ (mp4 时长 − 首尾静音)`，取中位。

字数换秒数只在 ±5% 内可信，所以下面的闸门写的是**字数**（可执行），秒数只
作为它的注解。

## 为什么是「棘轮」而不是一刀切

按 90 秒算出来的预算是 536 字，而立这条闸门时现存 14 条**全部超标**（546 到
1347）。一条全红的测试是墙不是闸门，给不出任何信号。所以：

- 名单外的（新片子）必须直接达标；
- 名单内的**只许降不许升**——不要求它们去达标，只挡住继续变长。

这和 `test_人名要以译名表为准` 里的 `_ON_PURPOSE` 是同一个路子：例外要显式
声明，不能默默通过。
"""

from __future__ import annotations

import re

import pytest

from tennislive.render.tournament_story import find_story_by_slug
from tennislive.video.explainer import (
    LEAD_SILENCE,
    TAIL_SILENCE,
    _OPENINGS,
    _SCRIPTS,
    explainer_column,
    explainer_script,
    speakable,
)

# 字/秒，在 `rate: +28%`（当前档）的三条成片上量出来的中位。见模块开头。
# 换语速就要重量，别按比例推。
SPEECH_RATE = 6.4

BUDGET_SECONDS = 90
# 首尾静音不走旁白，要从预算里扣掉。
NARRATION_BUDGET = round((BUDGET_SECONDS - LEAD_SILENCE - TAIL_SILENCE) * SPEECH_RATE)

# 决定窗口：抖音 5 秒内走掉 62%。片头静音占掉 0.6 秒，剩下的才归第一句。
HOOK_SECONDS = 5.0
HOOK_BUDGET = round((HOOK_SECONDS - LEAD_SILENCE) * SPEECH_RATE)

# yellow-ball 出过名单，但不是因为有人改短了它：语速常数从 6.1 校准到实测的
# 6.4 之后，90 秒对应的字数从 536 涨到 563，它那 538 字（≈85 秒）就落到线下了。
# 判定本身是对的——按当前语速它确实不到 90 秒。
#
# 祖父名单：立预算之前就存在的片子，**不要求它们达标**（老片子不回头重排）。
# 唯一的约束是不许继续变长。哪条真的被改短到达标了，就从这里删掉。
#
# masters-format 不在名单里：它被重排过（705 字 → 349 字），当时是拿它验证
# 「把答案提到第 ① 屏」这个做法可行——依据是三个平台的中位观众都停在第 ① 屏，
# 原来 ⑤⑥ 两屏一个人都走不到，收尾那一问等于没问。
_OVER_BUDGET = {
    "venus-potapova": 1347,
    "zheng-eala": 1083,
    "ten-champions": 992,
    "shang-nishikori": 982,
    "roof": 973,
    "shot-clock": 857,
    "ball-pick": 847,
    "rufus": 737,
    "longest-match": 691,
    "hawkeye": 681,
    "wimbledon-whites": 671,
    "queue": 660,
}

# 封面第一句超出决定窗口的。两条都是「开球之前」——这个格式开场要交代对阵、
# 时间、来路，一句话就铺了三十多个字。知识解说那一栏的首句都在 10–17 字。
_HOOK_TOO_LONG = {
    "venus-potapova": 38,
    "zheng-eala": 31,
}


def _chars(text: str) -> int:
    """按合成器实际要念的字数算：走 speakable()，去掉空白。

    `speakable` 里有给合成器纠音的替换（挑→选之类），念的是那一版，所以
    字数也该按那一版数。标点不发音但会停顿，忽略它带来的误差在 ±5% 以内。
    """
    return len(re.sub(r"\s", "", speakable(text)))


def _total(slug: str) -> int:
    return sum(_chars(seg.narration) for seg in explainer_script(find_story_by_slug(slug)))


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。？！?!])", text.strip())
    return next((p for p in parts if p.strip()), text)


def _hook(slug: str) -> int:
    cover = explainer_script(find_story_by_slug(slug))[0].narration
    return _chars(_first_sentence(cover))


# 2026-07-28，账号所有者改了口径：**「字数不用刻意限制，讲清楚话题最重要」**。
#
# 这条闸门原来硬卡 536 字（≈90 秒），依据是三家平台的人均播放 13–21 秒、
# 真完播 2–3%。那个依据没变，但它回答的是「怎样让更多人看完」，而所有者要的是
# 「先把这件事讲清楚」——这是编辑取舍，不是测量结论，所以由他定。
#
# 现实也支持这次放宽：已发的十一条里，ball-pick 800 字、hawkeye 659 字、
# ten-champions 962 字，全都远超 536，而它们就是所有者拿来当参照的成品。
# 硬卡 536 等于要求新片子比参照件短一半。
#
# 所以上限从「90 秒」放到 **150 秒**（≈900 字），并保留一条硬上限——不是为了
# 省时长，是为了挡住「一屏写成一篇」：超过这个数就该拆片，不该继续加长。
# 名单里的老片子仍然只许降不许升，那条没变。
# 2026-07-28 再次收紧口径：账号所有者说的是「**字数和图片都不用做限制，
# 只是为了把问题讲清楚就行**」。所以这里**不再有编辑意义上的上限**。
#
# 只留一条**防 bug 的兜底**，它和「片长该多长」无关：旁白是拼接出来的，
# 一次模板错误或循环写错就可能拼出几千字，那种东西 TTS 会跑十几分钟、
# 成片没法用。5000 字 ≈ 13 分钟，任何正常的知识片都够不到，
# 够到就说明是拼错了，不是写长了。
SANITY_MAX_CHARS = 5000

# **目标**（不是闸门）：账号所有者「最好控制在 3 分钟左右的配音」。
# 按实测语速 6.1 字/秒，3 分钟 ≈ 1100 字。写稿时朝这个数走，超一点不拦——
# 上面那条硬断言只管拼接失控。已发成品的实际落点：hawkeye 659、ball-pick 800、
# ten-champions 962，都在这个量级里偏短的一侧，说明 1100 是够用的。
TARGET_SECONDS = 180
TARGET_CHARS = round((TARGET_SECONDS - LEAD_SILENCE - TAIL_SILENCE) * SPEECH_RATE)


def narration_seconds(slug: str) -> float:
    """这条片子的旁白大概多长（秒）。写稿时拿来对目标，不参与断言。"""
    return _total(slug) / SPEECH_RATE + LEAD_SILENCE + TAIL_SILENCE


@pytest.mark.parametrize("slug", sorted(_SCRIPTS))
def test_旁白字数不超过片长预算(slug):
    """片长由旁白字数决定，所以预算卡在字数上。

    上限是 150 秒那一档（见上面那段口径说明）；名单里的老片子只许降不许升。
    """
    got = _total(slug)
    if slug in _OVER_BUDGET:
        was = _OVER_BUDGET[slug]
        assert got <= was, (
            f"{slug} 的旁白从 {was} 字涨到了 {got} 字。名单里的片子只许降不许升——"
            f"要么把它写短，要么说清为什么这一条值得更长。"
            f"（预算是 {NARRATION_BUDGET} 字 ≈ {BUDGET_SECONDS} 秒）")
        return
    assert got <= SANITY_MAX_CHARS, (
        f"{slug} 的旁白 {got} 字 ≈ {got / SPEECH_RATE / 60:.0f} 分钟。\n"
        f"字数**不设编辑上限**（讲清楚最重要），这条只是防拼接出错的兜底——"
        f"到这个量级基本可以确定是模板或循环写错了。")


def test_超预算名单只能变短():
    """真被改短到达标的，要从名单里删掉，否则名单会留着一个假的上限。

    注意这**不要求**老片子去达标——它们按编辑决定保持原样。这条只保证：
    一旦某条真的短到了预算以内，它就该受预算约束，而不是继续挂在祖父名单里
    享受一个宽松的上限。

    名单里的幽灵条目交给下面那条测试报——这里跳过它们，免得一处笔误让两条
    测试同时抛异常，看不出到底哪里错了。
    """
    fixed = {s: v for s, v in _OVER_BUDGET.items()
             if s in _SCRIPTS and _total(s) <= NARRATION_BUDGET}
    assert not fixed, (
        f"{'、'.join(fixed)} 已经降到 {NARRATION_BUDGET} 字以内，"
        f"把它们从 _OVER_BUDGET 里删掉——名单只该变短。")


def test_超预算名单里不许有不存在的片子():
    """删掉一条片子却忘了删名单，会让下一个人以为它还欠着债。"""
    ghosts = set(_OVER_BUDGET) - set(_SCRIPTS)
    assert not ghosts, f"_OVER_BUDGET 里这些片子已经不存在了：{'、'.join(sorted(ghosts))}"


@pytest.mark.parametrize("slug", sorted(_SCRIPTS))
def test_封面第一句要在决定窗口里说完(slug):
    """抖音：5 秒内走掉 62%。第一句在第 5 秒还没说完，那 62% 的人听到的是半截。

    卡的是**第一句**，不是整屏封面。整屏封面「开球之前」要 16–20 秒，那不是
    问题——问题是走掉的人有没有拿到一个完整的意思。
    """
    got = _hook(slug)
    if slug in _HOOK_TOO_LONG:
        was = _HOOK_TOO_LONG[slug]
        assert got <= was, (
            f"{slug} 封面第一句从 {was} 字涨到 {got} 字，只许降不许升。")
        return
    assert got <= HOOK_BUDGET, (
        f"{slug} 封面第一句 {got} 字 ≈ {got / SPEECH_RATE + LEAD_SILENCE:.1f} 秒，"
        f"超出 {HOOK_SECONDS} 秒的决定窗口（上限 {HOOK_BUDGET} 字）。\n"
        f"把第一句砍短，把交代挪到第二句——前 5 秒决定 62% 的人走不走。")


#: 封面那一问排不进一行、退回两行的片子。**只许减不许加。**
#:
#: 退回两行本身不是坏事——`text-wrap:balance` 至少保证两行长度接近。坏的是
#: 中文没有词边界，浏览器可以在任意两个汉字之间断，于是两行版**必然**在某处
#: 把一个词劈开：「排名到了，为什么还打资格赛？」断成了「…为什 / 么…」。
#: 所以新片子要么排得进一行，要么显式把自己加进这份名单——让「又断成两行」
#: 变成一次看得见的决定，而不是渲出来才发现。
_COVER_TWO_LINES = {
    "comeback-middle",   # 伤好了打不出来，是低谷还是终点？
    "thiem-football",    # 美网冠军退役两年后，在哪儿比赛？
    "zheng-eala",        # 三年前钦文赢了那个人，这次呢？
    "venus-potapova",    # 46 岁了，维纳斯为什么还在打？
    "wildcard",          # 签表里名字旁的 WC，是谁给的？
}


def _cover_one_line_px(question: str) -> int:
    """这一问排成一行时字号会是多少——**调生产用的那个算式**，不另写一套。"""
    from tennislive.video.explainer import (
        W, _COVER_WIDTH_MARGIN, _cover_title_em,
    )

    return int((W - 140) * _COVER_WIDTH_MARGIN / _cover_title_em(question))


@pytest.mark.parametrize("slug", sorted(_OPENINGS))
def test_封面那一问要能排进一行(slug):
    """`HOOK_BUDGET` 管的是**几秒说得完**，不管**一行排得下**——两个不同的量。

    2026-08-02 我把这两件事当成了一件：「排名到了，为什么还打资格赛？」14 个字，
    远在 27 字的首句预算之内，于是我以为没问题；渲出来断成了「为什 / 么」。
    量了才知道**卡的根本不是字数**——存量里 16 字的封面问题有四条都排得进一行，
    因为它们含半角字符；而那条 14 个字全是全角，反而更宽。

    机制早就有（`_COVER_MIN_ONE_LINE_PX`：装得下就一行，装不下才退两行），
    缺的只是一条在渲之前出声的判据。那条断掉的算出来是 82px，就差 84 这道线
    两个像素——而这两个像素只有把片子渲出来才看得见。
    """
    question = (_OPENINGS.get(slug) or {}).get("question")
    if not question:
        return
    from tennislive.video.explainer import _COVER_MIN_ONE_LINE_PX

    got = _cover_one_line_px(question)
    if slug in _COVER_TWO_LINES:
        return
    assert got >= _COVER_MIN_ONE_LINE_PX, (
        f"{slug} 的封面问题「{question}」排一行只能到 {got}px，"
        f"低于 {_COVER_MIN_ONE_LINE_PX}px，会退回两行并在词中间断开。\n"
        f"要么把它改短（每少一个全角字约多 {got // max(len(question) - 1, 1)}px），"
        f"要么显式加进 _COVER_TWO_LINES 并说明为什么可以。")


def test_两行名单只能变短而且每条都要真的排不进一行():
    """判据自己的判据。

    没有下半段的话，这份名单会**慢慢变成一条恒真的绿灯**：谁改短了标题却忘了
    把 slug 摘掉，那条就永远豁免着，下次真超了也不出声。
    """
    from tennislive.video.explainer import _COVER_MIN_ONE_LINE_PX

    assert _COVER_TWO_LINES, "名单空了？那这条判据的主语没了"
    stale = {
        slug for slug in _COVER_TWO_LINES
        if _cover_one_line_px((_OPENINGS.get(slug) or {}).get("question") or "")
        >= _COVER_MIN_ONE_LINE_PX
    }
    assert not stale, (
        f"{'、'.join(sorted(stale))} 的封面问题已经排得进一行了，"
        f"从 _COVER_TWO_LINES 里删掉。")
    assert len(_COVER_TWO_LINES) <= 5, "两行的片子只许减不许加"


def test_首句超窗名单只能变短():
    fixed = {s: v for s, v in _HOOK_TOO_LONG.items()
             if s in _SCRIPTS and _hook(s) <= HOOK_BUDGET}
    assert not fixed, (
        f"{'、'.join(fixed)} 的封面首句已经落进窗口了，从 _HOOK_TOO_LONG 里删掉。")


def test_知识解说那一栏的首句本来就都在窗口内():
    """反过来验一次：这个闸门不是把所有片子都判红的空规则。

    「网球有故事」十一条的封面首句是 10–17 字，全部落在窗口里——说明窗口
    定得住，超标的两条是真超标，不是标准定得不合理。
    """
    inside = [s for s in _SCRIPTS
              if explainer_column(s) == "网球有故事" and _hook(s) <= HOOK_BUDGET]
    total = [s for s in _SCRIPTS if explainer_column(s) == "网球有故事"]
    assert len(inside) == len(total), (
        f"「网球有故事」有 {len(total) - len(inside)} 条首句超窗，"
        f"那 {HOOK_BUDGET} 字这个上限就该重新量，而不是让大家去改稿。")


def test_预算是按当前语速算的不是两簇的中位():
    """语速变过：老片子 4.93–5.10 字/秒，当前这一档 5.82–6.25。

    取两簇的中位（约 5.5）会把预算放宽两成，而新片子全按快的那档渲——
    等于给了一个永远兑现不了的预算。
    """
    assert 6.1 <= SPEECH_RATE <= 6.8, "语速常数要落在 +28% 那一档的实测区间里"
    # 90 秒预算换算回来要和实测对得上
    assert 545 <= NARRATION_BUDGET <= 600
    assert 25 <= HOOK_BUDGET <= 30
