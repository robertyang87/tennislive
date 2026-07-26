"""日报卡改版：主题色不动，只把底色提淡 + 重做布局。

改版要求：保持「网球时差」原有的深绿主题（--neon 荧光黄绿 / --coral 珊瑚 /
--sky 青 / --gold 金 / --ivory）一个色都不动，只把近黑的底色提淡来解决
"视觉过重"；布局那一层重做——大留白、间距、行高、照片遮罩，外加去掉顶部
彩虹条。

"一屏只点亮比分与决胜数据"后来单独做了：技术统计表里只有决胜那一行
（_key_stat_label 选出）保持荧光黄绿，其余胜方数字回到 --ivory。它是**唯一**
准许改颜色的段落，用的也全是既有主题色，比分/徽章/栏目色一概不动。
"细线代替色块高亮"也做了：实心徽章（今日头条 / 中国军团 / 爆冷 / 重点 /
硬地 / 看点）改成彩色字 + 1px 同色描边，只换填充与描边，颜色仍是同一支
主题色。Pillow 兜底同步改成描边。

改颜色的段落一共两节——"只点亮决胜数据"和"描边徽章"，各自有测试圈定
边界；布局段仍然一条颜色规则都不许有。

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

# 提淡后的底色（:root 是 #061D17 → #0B3B2C）
GROUND0, GROUND1 = (0x1E, 0x42, 0x34), (0x2A, 0x64, 0x50)

# CSS 里那段布局重做的起点，测试靠它把"新增规则"和原有规则分开
_DAILY_MARKER = "daily 的布局重做"
_HIGHLIGHT_MARKER = 'daily 的"一屏只点亮比分与决胜数据"'
_BADGE_MARKER = "daily 的描边徽章"


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


def test_daily_overrides_only_the_four_background_surfaces():
    """html.daily 只准覆盖背景面，别的 token 一个都不许碰。

    "把背景搞淡"要的就是 ground/panel 这四个。上一版顺手改了 --divider
    （荧光黄绿细线变成象牙色）、--fade、--panel-muted，等于换了主题。
    """
    block = _daily_block()
    overridden = set(re.findall(r"(--[a-z0-9-]+):", block))
    assert overridden == {"--ground0", "--ground1", "--panel", "--panel-strong"}, (
        f"html.daily 覆盖了额外的 token：{sorted(overridden)}"
    )
    assert "--ground0:#1E4234" in block and "--ground1:#2A6450" in block

    root_ground0, root_ground1 = (0x06, 0x1D, 0x17), (0x0B, 0x3B, 0x2C)
    assert _luma(GROUND0) > _luma(root_ground0)
    assert _luma(GROUND1) > _luma(root_ground1)


def test_layout_section_contains_no_colour_rules_at_all():
    """布局段只准改几何：留白、间距、行高、照片遮罩浓度。

    这是"不要换主题色"最直接的护栏。上一版在这一段里把实心徽章改成描边、
    把胜方整列的荧光黄绿数字改成白字、把 .china-marker 从金色改成黄绿——
    每一条单独看都像"布局"，加起来就是换了主题。
    """
    # "只点亮决胜数据"是唯一准许改颜色的段落，单独校验、不混进布局段
    layout = _daily_tail().split(_HIGHLIGHT_MARKER, 1)[0]
    offenders = [
        line.strip()
        for line in layout.splitlines()
        if re.search(r"(^|[;{\s])color:|background(-color)?:|border-color:"
                     r"|box-shadow:\s*inset", line)
    ]
    assert not offenders, "布局段里出现了颜色规则：\n" + "\n".join(offenders)


def test_only_the_decisive_stat_row_stays_lit():
    """一屏只点亮比分与决胜数据。

    原来胜方整列七个数字全是荧光黄绿，一屏下来到处在亮，比分反而不突出。
    现在只有 _key_stat_label 选中的那一行保持荧光黄绿，其余回到 --ivory。
    用的是既有主题色，没有引入新色值。
    """
    assert _HIGHLIGHT_MARKER in _CSS and _BADGE_MARKER in _CSS
    tail = _CSS.split(_HIGHLIGHT_MARKER, 1)[1].split(_BADGE_MARKER, 1)[0]
    assert "html.daily .compare-row:not(.key) .winner { color:var(--ivory); }" in tail
    assert "html.daily .compare-row.key { background:var(--panel-soft); }" in tail

    # 这一段只准碰技术统计表，不许动比分/徽章/栏目色
    selectors = [
        line.split("{", 1)[0].strip()
        for line in tail.splitlines()
        if "{" in line and not line.strip().startswith(("/*", "*"))
    ]
    assert selectors
    for selector in selectors:
        assert "compare-row" in selector, f"越界改了技术统计表以外的东西：{selector}"


def test_badges_are_outlined_not_filled_blocks():
    """细线代替色块高亮：实心徽章改描边，颜色仍是同一支主题色。

    一屏上原本有 6 处实心色块（今日头条 / 中国军团 / 爆冷 / 重点 / 硬地 /
    看点），和比分抢注意力。只换填充与描边，不引入新色值。
    """
    tail = _CSS.split(_BADGE_MARKER, 1)[1]
    for rule in (
        "html.daily .chip { background:transparent;",
        "html.daily .rating { background:transparent;",
        "html.daily .event-meta b { background:transparent;",
        "html.daily .pick .reason b { background:transparent;",
    ):
        assert rule in tail, f"没改成描边：{rule}"

    # 颜色只准引用既有主题色变量，不许出现写死的色值
    literals = re.findall(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", tail)
    assert not literals, f"描边段里出现了写死的色值：{literals}"


def test_pillow_fallback_draws_outlined_badges_too():
    """Chromium 挂了走 Pillow，徽章也得是描边，不能两边不一样。"""
    import inspect

    source = inspect.getsource(cards._match_card)
    assert "outline=fill, width=2" in source
    assert "outline=RED, width=2" in source
    assert "fill=(255, 255, 255)" not in source, "还在往实心块上写白字"


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


def test_layout_reworks_all_four_card_types():
    """四类卡都要动到：封面 / 赛果 / 焦点 / 今晚。"""
    tail = _daily_tail()
    assert "html.daily .cover-copy" in tail, "封面没重做"
    assert "html.daily .card {" in tail, "赛果/焦点的卡间距没重做"
    assert "html.daily .compare-row { height:66px; }" in tail, "技术统计行高没放宽"
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
    daily, dark = cards._THEMES["daily"], cards._THEMES["dark"]
    changed = {k for k in daily if daily[k] != dark.get(k)}
    assert changed == {"BG_TOP", "BG_BOTTOM", "PANEL", "PANEL_HI"}, (
        f"Pillow 兜底改了额外的色值：{sorted(changed)}"
    )
    assert daily["BG_TOP"] == GROUND0 and daily["BG_BOTTOM"] == GROUND1
    # 底色确实比 dark 亮
    assert _luma(daily["BG_TOP"]) > _luma(dark["BG_TOP"])
    assert _luma(daily["BG_BOTTOM"]) > _luma(dark["BG_BOTTOM"])


def test_pillow_fallback_keeps_every_theme_colour_identical_to_dark():
    """主题色在 Pillow 侧也必须逐个等于 dark 的原值。"""
    daily, dark = cards._THEMES["daily"], cards._THEMES["dark"]
    for key in ("ACCENT", "BALL", "OUTLINE", "WHITE", "GREY", "SCORE_GREY",
                "RED", "FOOT", "STAR_PILL", "STAR_PILL_HOT", "BTN_TEXT",
                "CARD_BG", "CARD_TEXT", "CARD_GREY", "CARD_LINE",
                "WIN_BAND", "WIN_GREEN", "CHIP_GREEN", "PANEL_LINE", "DECO"):
        assert daily[key] == dark[key], f"{key} 被改了：{dark[key]} -> {daily[key]}"


def test_key_stat_row_is_the_decisive_one():
    """一屏只点亮"决胜数据"：破发兑现在就用它，不在才退到优先级最高的一行。"""
    from tennislive.render.webcards import _key_stat_label

    assert _key_stat_label(["总得分", "一发得分率", "破发兑现"]) == "破发兑现"
    # 没有破发兑现时退到 _CARD_STAT_PRIORITY 里最靠前的
    assert _key_stat_label(["一发成功率", "总得分", "二发得分率"]) == "总得分"
    assert _key_stat_label([]) is None
