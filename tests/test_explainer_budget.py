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

## 语速是量出来的，而且它变过

拿成片时长反推 `字数 ÷ (片长 − 首尾静音)`，16 条片子分成清清楚楚的两簇：

    4.93 – 5.10 字/秒   longest-match、yellow-ball、ten-champions、queue、
                        wimbledon-whites、hawkeye(07-25)、rufus
    5.82 – 6.25 字/秒   hawkeye(07-26)、masters-format、roof、ball-pick、
                        shot-clock、shang-nishikori、venus-potapova、zheng-eala

**同一份 hawkeye 脚本渲了两次，字数一模一样 681，片长 135.5s 对 119.1s。**
快的那批就是落了 `narration.json`（`rate: +22%`）的那批。所以预算按**当前
这一档**算，不按两簇的中位——用中位会把预算放宽两成，而新片子全按快的渲。

字数换秒数只在 ±5% 内可信，所以下面的闸门写的是**字数**（可执行），秒数只
作为它的注解。

## 为什么是「棘轮」而不是一刀切

按 90 秒算出来的预算是 536 字，而现存 14 条**全部超标**（546 到 1347）。
一条全红的测试是墙不是闸门，给不出任何信号。所以：

- 名单外的（新片子）必须直接达标；
- 名单内的**只许降不许升**，降到达标就得从名单里删掉。

名单只会变短。这和 `test_人名要以译名表为准` 里的 `_ON_PURPOSE` 是同一个
路子：例外要显式声明，不能默默通过。
"""

from __future__ import annotations

import re

import pytest

from tennislive.render.tournament_story import find_story_by_slug
from tennislive.video.explainer import (
    LEAD_SILENCE,
    TAIL_SILENCE,
    _SCRIPTS,
    explainer_column,
    explainer_script,
    speakable,
)

# 当前这一档的语速（`rate: +22%`），从落库成片反推。见模块开头。
SPEECH_RATE = 6.1

BUDGET_SECONDS = 90
# 首尾静音不走旁白，要从预算里扣掉。
NARRATION_BUDGET = round((BUDGET_SECONDS - LEAD_SILENCE - TAIL_SILENCE) * SPEECH_RATE)

# 决定窗口：抖音 5 秒内走掉 62%。片头静音占掉 0.6 秒，剩下的才归第一句。
HOOK_SECONDS = 5.0
HOOK_BUDGET = round((HOOK_SECONDS - LEAD_SILENCE) * SPEECH_RATE)

# 现存片子的字数，只许降不许升。降到 NARRATION_BUDGET 以下就从这里删掉。
_OVER_BUDGET = {
    "venus-potapova": 1347,
    "zheng-eala": 1083,
    "ten-champions": 992,
    "shang-nishikori": 982,
    "roof": 973,
    "shot-clock": 857,
    "ball-pick": 847,
    "rufus": 737,
    "masters-format": 705,
    "longest-match": 691,
    "hawkeye": 681,
    "wimbledon-whites": 671,
    "queue": 660,
    "yellow-ball": 546,
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


@pytest.mark.parametrize("slug", sorted(_SCRIPTS))
def test_旁白字数不超过片长预算(slug):
    """片长由旁白字数决定，所以预算卡在字数上。

    新片子直接达标；名单里的老片子只许降不许升。
    """
    got = _total(slug)
    if slug in _OVER_BUDGET:
        was = _OVER_BUDGET[slug]
        assert got <= was, (
            f"{slug} 的旁白从 {was} 字涨到了 {got} 字。名单里的片子只许降不许升——"
            f"要么把它写短，要么说清为什么这一条值得更长。"
            f"（预算是 {NARRATION_BUDGET} 字 ≈ {BUDGET_SECONDS} 秒）")
        return
    assert got <= NARRATION_BUDGET, (
        f"{slug} 的旁白 {got} 字 ≈ {got / SPEECH_RATE + LEAD_SILENCE + TAIL_SILENCE:.0f} 秒，"
        f"超出预算 {NARRATION_BUDGET} 字（{BUDGET_SECONDS} 秒）。\n"
        f"三家平台的人均播放时长是 13–21 秒，真完播 2–3%——"
        f"写到两分半，后面那一多半没人看得到。")


def test_超预算名单只能变短():
    """降到预算以内的必须从名单里删掉，否则名单会永远留着一个假的上限。

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
    assert 5.8 <= SPEECH_RATE <= 6.3, "语速常数要落在当前这一档的实测区间里"
    # 90 秒预算换算回来要和实测对得上
    assert 520 <= NARRATION_BUDGET <= 545
    assert 25 <= HOOK_BUDGET <= 30
