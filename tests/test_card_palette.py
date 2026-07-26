"""日报卡改版：A2 暖沙纸底（paper）的配色约束。

改版要求：专业+高级感、弱化绿（绿只做点缀不做主色）、中性底、大留白、
一屏只点亮比分与决胜数据、细线代替色块高亮、去掉顶部彩虹条。

两条必须钉死的边界：
1. 「网球有故事」知识贴走 :root 深绿底，是这次要**对齐**的参照物，不是要
   改的对象。所有新规则都必须锁在 html.paper 作用域里。
2. Chromium 挂掉时会退到 cards.py 的 Pillow 兜底，两边配色必须一致，否则
   一次渲染失败就发出深绿+荧光黄绿的卡，和当期其余内容对不上。
"""

from __future__ import annotations

import re

import pytest

from tennislive.render import cards
from tennislive.render.webcards import _CSS, _shell, daily_card_theme

# webcards.py 的 html.paper 与 cards.py 的 _THEMES["paper"] 共用这支强调色
ACCENT = (194, 72, 43)


# CSS 里那段收敛规则的起点，测试靠它把"新增规则"和原有规则分开
_PAPER_MARKER = "paper 的结构性收敛"


def _paper_tail() -> str:
    assert _PAPER_MARKER in _CSS, "paper 收敛段落的标记注释被改掉了"
    return _CSS.split(_PAPER_MARKER, 1)[1]


def _paper_block() -> str:
    match = re.search(r"html\.paper \{(.*?)\}", _CSS, re.S)
    assert match, "html.paper 的 token 块不见了"
    return match.group(1)


def test_paper_is_the_daily_card_palette_and_is_not_the_shared_theme_switch(
    monkeypatch,
):
    """日报卡的配色和 TENNISLIVE_THEME 解耦。

    TENNISLIVE_THEME 是 daily / knowledge-adhoc / explainer / flash /
    news-radar 五个 workflow 共用的一个变量，且都显式写成 'dark'。跟着它走
    的话，日报卡改版会顺手把知识贴也改了。
    """
    monkeypatch.delenv("TENNISLIVE_CARD_PALETTE", raising=False)
    monkeypatch.setenv("TENNISLIVE_THEME", "dark")
    assert daily_card_theme() == "paper"

    # 留一个回滚开关
    monkeypatch.setenv("TENNISLIVE_CARD_PALETTE", "dark")
    assert daily_card_theme() == "dark"


def test_shell_toggles_paper_independently_of_light():
    """paper 不是 light 的别名：它自带一整套 token。"""
    assert "classList.toggle('paper', true)" in _shell("<div></div>", "paper")
    assert "classList.toggle('light', false)" in _shell("<div></div>", "paper")
    assert "classList.toggle('paper', false)" in _shell("<div></div>", "dark")
    assert "classList.toggle('paper', false)" in _shell("<div></div>", "light")


def test_top_rainbow_bar_is_dropped_only_for_the_daily_cards():
    """去掉顶部彩虹条——但只在 paper 下去掉，知识贴保留自己的那条。"""
    # 彩虹条本身还在（知识贴在用）
    assert "body::before" in _CSS
    assert re.search(
        r"linear-gradient\(90deg,var\(--neon\) 0 42%,var\(--coral\)", _CSS
    ), "彩虹条定义被整个删掉了，会连知识贴一起改"
    # paper 下关掉：封面和内页两处都要
    assert "html.paper body::before, html.paper .cover::after { display:none; }" in _CSS


def test_every_new_rule_is_scoped_to_paper():
    """新增规则一律锁在 html.paper 里，一条都不能泄漏到 :root。

    这是知识贴不被改动的结构性保证——比逐像素比对便宜，而且能一直守着。
    """
    assert _PAPER_MARKER in _CSS
    tail = _paper_tail()
    selectors = [
        line.split("{", 1)[0].strip()
        for line in tail.splitlines()
        if "{" in line and not line.strip().startswith(("/*", "*"))
    ]
    assert selectors, "paper 收敛段落是空的"
    for selector in selectors:
        for part in selector.split(","):
            part = part.strip()
            if not part:
                continue
            assert part.startswith("html.paper"), f"规则泄漏到全局：{part}"


def test_paper_neutralises_green_and_keeps_one_accent():
    """弱化绿：绿不再是高亮色，强调色只有一支赤陶红。"""
    block = _paper_block()
    # --neon 从荧光黄绿降为墨色，--score-win / --section-accent 都是赤陶红
    assert "--neon:#1E3328" in block
    assert "--score-win:#C2482B" in block
    assert "--section-accent:#C2482B" in block
    assert "--coral:#C2482B" in block
    # 中性沙底，不是绿底
    assert "--ground0:#F2EDE2" in block and "--ground1:#E9E2D2" in block


def test_paper_replaces_block_highlights_with_hairlines():
    """细线代替色块高亮；一屏只点亮比分与决胜数据。"""
    tail = _paper_tail()
    # 胜方整列的色块高亮拿掉
    assert "html.paper .compare-row .winner { background:transparent; }" in tail
    assert "html.paper .side.won { background:transparent;" in tail
    # 只有决胜那一行是亮的，其余列回到墨色
    assert "html.paper .compare-row:not(.key) .winner { color:var(--pagetext); }" in tail
    assert "html.paper .compare-row.key .winner { color:var(--section-accent); }" in tail
    # 大标题回到墨色，否则一屏不止"点亮比分"
    assert "html.paper h1 { color:var(--pagetext);" in tail


def test_cover_keeps_the_bright_coral_because_it_is_always_a_dark_photo():
    """封面是整张深色实拍照：沙底那支加深版压上去只有 2 出头的对比度，看不见。

    改回知识贴原色 #FF7657（深底 6.8:1），顺带这也是跨栏目共用的那个色值。
    """
    tail = _paper_tail()
    assert "html.paper .cover { --section-accent:#FF7657; --coral:#FF7657;" in tail


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_legacy_themes_still_carry_every_key_paper_added(theme):
    """set_theme 走 globals().update：新增的 key 三个主题都要有值。

    少给一个的话，切到 paper 再切回来，那个常量就留在上一个主题的值上。
    """
    added = {"BTN_TEXT", "CARD_BG", "CARD_TEXT", "CARD_GREY", "CARD_LINE",
             "WIN_BAND", "WIN_GREEN", "CHIP_GREEN"}
    assert added <= set(cards._THEMES[theme])
    assert added <= set(cards._THEMES["paper"])


def test_pillow_fallback_matches_the_html_palette():
    """Chromium 挂了才走 Pillow，两边配色必须是同一套。"""
    paper = cards._THEMES["paper"]
    assert paper["ACCENT"] == ACCENT
    assert paper["OUTLINE"] == ACCENT
    # html 侧同一支色
    assert f"#{ACCENT[0]:02X}{ACCENT[1]:02X}{ACCENT[2]:02X}" == "#C2482B"
    assert "--section-accent:#C2482B" in _paper_block()
    # 沙底两端与 CSS 的 --ground0/--ground1 对齐
    assert paper["BG_TOP"] == (242, 237, 226)
    assert paper["BG_BOTTOM"] == (233, 226, 210)


def test_pillow_fallback_has_no_green_highlight_left():
    """赛果卡的胜方底色/比分/头条药丸曾经写死在 _THEMES 外面，全是绿的。

    底色都换成暖沙了，那三块绿还在——所以它们必须跟着主题走。
    绿只准留在 BALL（logo 球身）这一处。
    """
    paper = cards._THEMES["paper"]

    def is_green(rgb: tuple[int, int, int]) -> bool:
        red, green, blue = rgb
        return green > red + 12 and green > blue + 12

    for key in ("ACCENT", "OUTLINE", "WIN_GREEN", "CHIP_GREEN", "WIN_BAND",
                "STAR_PILL", "STAR_PILL_HOT", "RED"):
        assert not is_green(paper[key]), f"{key} 还是绿的：{paper[key]}"

    assert is_green(paper["BALL"]), "logo 球身应当是唯一保留的绿"


def test_key_stat_row_is_the_decisive_one():
    """一屏只点亮"决胜数据"：破发兑现在就用它，不在才退到优先级最高的一行。"""
    from tennislive.render.webcards import _key_stat_label

    assert _key_stat_label(["总得分", "一发得分率", "破发兑现"]) == "破发兑现"
    # 没有破发兑现时退到 _CARD_STAT_PRIORITY 里最靠前的
    assert _key_stat_label(["一发成功率", "总得分", "二发得分率"]) == "总得分"
    assert _key_stat_label([]) is None
