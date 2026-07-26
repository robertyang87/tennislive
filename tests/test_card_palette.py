"""日报卡改版：主题色不动，只把底色提淡两档 + 重做布局。

改版要求：保持「网球时差」原有的深绿主题（--neon 荧光黄绿 / --coral 珊瑚 /
--sky 青 / --gold 金 / --ivory），把近黑的底色提淡，解决"视觉过重"；
再重做四类卡的布局——大留白、细线代替色块高亮、一屏只点亮比分与决胜数据、
去掉顶部彩虹条。

两条必须钉死的边界：
1. 「网球有故事」知识贴与科普视频仍走 :root 的近黑深绿，改版不能碰它们。
   所有新规则都必须锁在 html.daily 作用域里。
2. Chromium 挂掉时会退到 cards.py 的 Pillow 兜底，两边配色必须一致，否则
   一次渲染失败就发出和当期其余内容对不上的卡。
"""

from __future__ import annotations

import re

import pytest

from tennislive.render import cards
from tennislive.render.webcards import _CSS, _shell, daily_card_theme

# 提淡两档后的底色（:root 是 #061D17 → #0B3B2C）
GROUND0, GROUND1 = (0x15, 0x33, 0x28), (0x1E, 0x52, 0x41)

# CSS 里那段布局重做的起点，测试靠它把"新增规则"和原有规则分开
_DAILY_MARKER = "daily 的布局重做"


def _daily_tail() -> str:
    assert _DAILY_MARKER in _CSS, "daily 布局段落的标记注释被改掉了"
    return _CSS.split(_DAILY_MARKER, 1)[1]


def _daily_block() -> str:
    match = re.search(r"html\.daily \{(.*?)\}", _CSS, re.S)
    assert match, "html.daily 的 token 块不见了"
    return match.group(1)


def _luma(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def test_daily_is_the_card_palette_and_is_not_the_shared_theme_switch(monkeypatch):
    """日报卡的配色和 TENNISLIVE_THEME 解耦。

    TENNISLIVE_THEME 是 daily / knowledge-adhoc / explainer / flash /
    news-radar 五个 workflow 共用的一个变量，且都显式写成 'dark'。跟着它走
    的话，日报卡提淡底色会把知识贴和科普视频一起提淡。
    """
    monkeypatch.delenv("TENNISLIVE_CARD_PALETTE", raising=False)
    monkeypatch.setenv("TENNISLIVE_THEME", "dark")
    assert daily_card_theme() == "daily"

    # 留一个回滚开关
    monkeypatch.setenv("TENNISLIVE_CARD_PALETTE", "dark")
    assert daily_card_theme() == "dark"


def test_shell_toggles_daily_independently_of_light():
    """daily 不是 light 的别名：它继承 :root 再覆盖底色。"""
    assert "classList.toggle('daily', true)" in _shell("<div></div>", "daily")
    assert "classList.toggle('light', false)" in _shell("<div></div>", "daily")
    assert "classList.toggle('daily', false)" in _shell("<div></div>", "dark")
    assert "classList.toggle('daily', false)" in _shell("<div></div>", "light")


def test_theme_colours_are_untouched():
    """主题色一个都不许动——这是这次改版最硬的约束。

    第一版把主题整个换成了暖沙底 + 赤陶红，方向是错的：要的是同一个深绿
    主题变淡，不是换主题。所以 html.daily 里不能出现任何强调色的重定义。
    """
    block = _daily_block()
    for token in ("--neon", "--coral", "--sky", "--gold", "--ivory",
                  "--score-win", "--section-accent", "--pagetext", "--flash"):
        assert f"{token}:" not in block, (
            f"html.daily 重定义了主题色 {token}，主题必须保持不变"
        )
    # :root 里这些主题色仍然是原值
    root = re.search(r":root \{(.*?)\}", _CSS, re.S).group(1)
    assert "--neon:#D6FF00" in root
    assert "--coral:#FF7657" in root
    assert "--sky:#76D7EA" in root
    assert "--gold:#D5B44D" in root


def test_daily_only_lifts_the_ground_and_it_really_is_lighter():
    """只动底色，而且必须确实比 :root 亮——否则"提淡"就没发生。"""
    block = _daily_block()
    assert "--ground0:#153328" in block and "--ground1:#1E5241" in block
    # 面板要跟着底色一起提亮：底色变亮而面板不动，深色面板压在亮底上
    # 反而更像"一块一块"的，比原来还重。
    assert "--panel:rgba(14,44,35,.74)" in block
    assert "--panel-strong:rgba(17,53,42,.86)" in block

    root_ground0, root_ground1 = (0x06, 0x1D, 0x17), (0x0B, 0x3B, 0x2C)
    assert _luma(GROUND0) > _luma(root_ground0)
    assert _luma(GROUND1) > _luma(root_ground1)


def test_top_rainbow_bar_is_dropped_only_for_the_daily_cards():
    """去掉顶部彩虹条——但只在 daily 下去掉，知识贴保留自己的那条。"""
    assert "body::before" in _CSS
    assert re.search(
        r"linear-gradient\(90deg,var\(--neon\) 0 42%,var\(--coral\)", _CSS
    ), "彩虹条定义被整个删掉了，会连知识贴一起改"
    assert "html.daily body::before, html.daily .cover::after { display:none; }" in _CSS


def test_every_new_rule_is_scoped_to_daily():
    """新增规则一律锁在 html.daily 里，一条都不能泄漏到 :root。

    这是知识贴与科普视频不被改动的结构性保证——比逐像素比对便宜，
    而且能一直守着。
    """
    tail = _daily_tail()
    selectors = [
        line.split("{", 1)[0].strip()
        for line in tail.splitlines()
        if "{" in line and not line.strip().startswith(("/*", "*"))
    ]
    assert selectors, "daily 布局段落是空的"
    for selector in selectors:
        for part in selector.split(","):
            part = part.strip()
            if not part:
                continue
            assert part.startswith("html.daily"), f"规则泄漏到全局：{part}"


def test_layout_replaces_block_highlights_with_hairlines():
    """细线代替色块高亮；一屏只点亮比分与决胜数据。"""
    tail = _daily_tail()
    # 外层面板去底去阴影（原来是"圆角面板里再嵌一层胜方底色块"）
    assert "html.daily .card { background:transparent; border:0;" in tail
    assert "html.daily .compare-grid { background:transparent; border:0;" in tail
    # 胜方整列的色块高亮拿掉，改成名字一侧一道细线
    assert "html.daily .compare-row .winner { background:transparent; }" in tail
    assert "html.daily .side.won { background:transparent;" in tail
    # 只有决胜那一行是亮的，其余数字回到正文色
    assert "html.daily .compare-row:not(.key) .winner { color:var(--pagetext); }" in tail
    assert "html.daily .compare-row.key .winner { color:var(--neon); }" in tail


def test_layout_reworks_all_four_card_types():
    """四类卡都要动到：封面 / 赛果 / 焦点 / 今晚。"""
    tail = _daily_tail()
    assert "html.daily .cover-copy" in tail, "封面没重做"
    assert "html.daily .card {" in tail, "赛果/焦点的面板没重做"
    assert "html.daily .compare-grid" in tail, "焦点技术统计没重做"
    assert "html.daily .tonight-page .pick" in tail, "今晚焦点没重做"
    # 大留白
    assert "html.daily .poster { padding:44px 72px 26px; }" in tail


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_legacy_themes_still_carry_every_key_daily_added(theme):
    """set_theme 走 globals().update：新增的 key 三个主题都要有值。

    少给一个的话，切到 daily 再切回来，那个常量就留在上一个主题的值上。
    """
    added = {"BTN_TEXT", "CARD_BG", "CARD_TEXT", "CARD_GREY", "CARD_LINE",
             "WIN_BAND", "WIN_GREEN", "CHIP_GREEN"}
    assert added <= set(cards._THEMES[theme])
    assert added <= set(cards._THEMES["daily"])


def test_pillow_fallback_matches_the_html_palette():
    """Chromium 挂了才走 Pillow，两边必须是同一套色值。"""
    daily = cards._THEMES["daily"]
    assert daily["BG_TOP"] == GROUND0
    assert daily["BG_BOTTOM"] == GROUND1
    # 主题色沿用 dark，不是另起一套
    assert daily["ACCENT"] == (214, 255, 0)      # --neon #D6FF00
    assert daily["RED"] == (255, 118, 87)        # --coral #FF7657
    assert daily["WHITE"] == (247, 243, 232)     # --ivory #F7F3E8
    # 底色确实比 dark 亮
    assert _luma(daily["BG_TOP"]) > _luma(cards._THEMES["dark"]["BG_TOP"])
    assert _luma(daily["BG_BOTTOM"]) > _luma(cards._THEMES["dark"]["BG_BOTTOM"])


def test_pillow_fallback_white_card_constants_follow_the_theme():
    """赛果卡的胜方底色/比分/头条药丸曾经写死在 _THEMES 外面。

    那七个常量注释着"主题无关"，于是底色一换主题它们纹丝不动，整页对不上。
    daily 下它们必须是深色卡面 + 荧光黄绿比分，而不是留在浅色白卡那一套。
    """
    daily = cards._THEMES["daily"]
    assert _luma(daily["CARD_BG"]) < _luma(cards._THEMES["dark"]["CARD_BG"])
    assert daily["WIN_GREEN"] == daily["ACCENT"]
    assert daily["CHIP_GREEN"] == daily["ACCENT"]
    # 卡面文字必须够亮，深色卡面上不能沿用白卡的深色字
    assert _luma(daily["CARD_TEXT"]) > 200


def test_key_stat_row_is_the_decisive_one():
    """一屏只点亮"决胜数据"：破发兑现在就用它，不在才退到优先级最高的一行。"""
    from tennislive.render.webcards import _key_stat_label

    assert _key_stat_label(["总得分", "一发得分率", "破发兑现"]) == "破发兑现"
    # 没有破发兑现时退到 _CARD_STAT_PRIORITY 里最靠前的
    assert _key_stat_label(["一发成功率", "总得分", "二发得分率"]) == "总得分"
    assert _key_stat_label([]) is None
