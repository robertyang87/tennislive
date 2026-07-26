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
_SOFT_MARKER = "daily 的柔和内容色"


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


_SCRIM_TINT_CEILING = 40


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
        if re.search(r"(^|[;{\s])color:|background-color:|border-color:"
                     r"|box-shadow:\s*inset", line)
    ]
    assert not offenders, "布局段里出现了颜色规则：\n" + "\n".join(offenders)


def test_layout_section_backgrounds_are_neutral_photo_scrims_only():
    """布局段里唯一准许出现的 background 是照片遮罩，而且必须是"压暗"。

    遮罩浓度本来就归布局管（文档里写着），可它只能用 background 的多层
    渐变来写。所以这条不禁 background，改成验它到底是什么：
    只准出现近黑的 rgba 和 var(--page-bg)/var(--inner-bg)，一旦掺进主题色
    token 或任何色值字面量，那就不是压暗而是给整页上色了——那属于换主题。
    """
    layout = _daily_tail().split(_HIGHLIGHT_MARKER, 1)[0]
    # 从 background: 一路取到分号，渐变是跨行写的
    declarations = re.findall(r"background:(.*?);", layout, re.S)
    assert declarations, "布局段里没有 background —— 照片遮罩是不是被挪走了？"

    for decl in declarations:
        flat = " ".join(decl.split())
        for token in ("--neon", "--coral", "--sky", "--gold", "--ivory",
                      "--score-win", "--section-accent", "--flash",
                      "--ground0", "--ground1", "--panel"):
            assert token not in flat, f"遮罩里引用了主题色 {token}：{flat}"
        assert "#" not in flat, f"遮罩里出现了色值字面量：{flat}"
        used_vars = set(re.findall(r"var\((--[a-z0-9-]+)", flat))
        assert used_vars <= {"--page-bg", "--page-bg-pos", "--inner-bg"}, (
            f"遮罩引用了照片以外的变量：{sorted(used_vars)}"
        )
        for r, g, b in re.findall(r"rgba\((\d+),\s*(\d+),\s*(\d+)", flat):
            assert max(int(r), int(g), int(b)) <= _SCRIM_TINT_CEILING, (
                f"遮罩的 rgba({r},{g},{b}) 不是近黑，等于给整页上色：{flat}"
            )


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
    tail = _CSS.split(_BADGE_MARKER, 1)[1].split(_SOFT_MARKER, 1)[0]
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
    """Chromium 挂了才走 Pillow，两边必须长得一样。

    daily 相对 dark 只准差这三类，每一类都对应 HTML 那边一处明确的改动：
      底色四个面   —— 提淡；
      SOFT_ACCENT  —— 赛果/焦点两页收敛成金；
      CARD_* 那一组 —— 比赛卡从白卡改成深色面板（见下一条测试）。
    """
    daily, dark = cards._THEMES["daily"], cards._THEMES["dark"]
    changed = {k for k in daily if daily[k] != dark.get(k)}
    assert changed == {
        "BG_TOP", "BG_BOTTOM", "PANEL", "PANEL_HI", "SOFT_ACCENT",
        "CARD_BG", "CARD_TEXT", "CARD_GREY", "CARD_LINE",
        "WIN_BAND", "WIN_GREEN", "CHIP_GREEN",
    }, f"Pillow 兜底改了额外的色值：{sorted(changed)}"
    # 收敛成的那支金必须就是主题里的 --gold，不能另起一支
    assert daily["SOFT_ACCENT"] == (0xD5, 0xB4, 0x4D)
    assert "--gold:#D5B44D" in re.search(r":root \{(.*?)\}", _CSS, re.S).group(1)

    assert daily["BG_TOP"] == GROUND0 and daily["BG_BOTTOM"] == GROUND1
    # 底色确实比 dark 亮
    assert _luma(daily["BG_TOP"]) > _luma(dark["BG_TOP"])
    assert _luma(daily["BG_BOTTOM"]) > _luma(dark["BG_BOTTOM"])


def test_pillow_match_cards_are_dark_panels_like_the_html_ones():
    """比赛卡必须是压在深绿底上的深色面板，不能是白卡。

    HTML 画的是半透明深色面板，Pillow 这边原来照抄 dark 的一套白卡值——
    同一份日报走哪条渲染路径长得完全不一样。Chromium 一挂，发出去的卡是
    白底黑字，和当期封面、视频、推送正文全对不上。
    """
    daily = cards._THEMES["daily"]
    page = _luma(daily["BG_TOP"])

    # 面板比页面底色亮一点点即可，绝不能是白的
    assert _luma(daily["CARD_BG"]) < page + 30, "比赛卡还是白卡"
    assert _luma(daily["WIN_BAND"]) < page + 40, "胜方行底纹太亮"
    # 面板变深了，卡里的字就必须变亮，否则读不出来
    assert _luma(daily["CARD_TEXT"]) > 200, "深面板上的主文字还是深色"
    assert _luma(daily["WIN_GREEN"]) > 200, "深面板上的胜方比分还是深色"
    assert _luma(daily["CARD_TEXT"]) > _luma(daily["CARD_GREY"]) > _luma(daily["CARD_BG"])


def test_pillow_fallback_keeps_every_theme_colour_identical_to_dark():
    """主题色在 Pillow 侧也必须逐个等于 dark 的原值。"""
    daily, dark = cards._THEMES["daily"], cards._THEMES["dark"]
    # CARD_* 那一组是**版面**不是主题色（白卡 → 深色面板），单独有测试管；
    # 这里管的是强调色，一个都不许动。
    for key in ("ACCENT", "BALL", "OUTLINE", "WHITE", "GREY", "SCORE_GREY",
                "RED", "FOOT", "STAR_PILL", "STAR_PILL_HOT", "BTN_TEXT",
                "PANEL_LINE", "DECO"):
        assert daily[key] == dark[key], f"{key} 被改了：{dark[key]} -> {daily[key]}"


def test_key_stat_row_is_the_decisive_one():
    """一屏只点亮"决胜数据"：破发兑现在就用它，不在才退到优先级最高的一行。"""
    from tennislive.render.webcards import _key_stat_label

    assert _key_stat_label(["总得分", "一发得分率", "破发兑现"]) == "破发兑现"
    # 没有破发兑现时退到 _CARD_STAT_PRIORITY 里最靠前的
    assert _key_stat_label(["一发成功率", "总得分", "二发得分率"]) == "总得分"
    assert _key_stat_label([]) is None


def test_soft_section_only_calms_the_two_result_cards():
    """柔和内容色只准作用在赛果速递和焦点复盘上。

    这两页原来最跳的是荧光黄绿 #D6FF00（栏目大标题 + 每一位胜者的比分数字
    + 决胜行高亮），改成温网那一路：象牙白数字 + 单支金色强调。
    但它不能顺手把封面、今晚焦点、知识贴一起改了。
    """
    assert _SOFT_MARKER in _CSS, "柔和内容色段落的标记注释被改掉了"
    tail = _CSS.split(_SOFT_MARKER, 1)[1]

    selectors = [
        line.split("{", 1)[0].strip()
        for line in tail.splitlines()
        if "{" in line and not line.strip().startswith(("/*", "*"))
    ]
    assert selectors, "柔和段是空的"
    for selector in selectors:
        for part in selector.split(","):
            part = part.strip()
            if not part:
                continue
            assert part.startswith("html.daily"), f"规则泄漏到全局：{part}"
            assert ".results-page" in part or ".focus-page" in part, (
                f"柔和内容色越界改了这两页以外的卡：{part}"
            )

    # 数字回到象牙白，强调色收敛成金
    assert "--score-win:var(--ivory);" in tail
    assert "--section-accent:var(--gold);" in tail
    # 决胜那一行仍然要点亮（完全中性的话它就和其余行分不出来了）
    assert "html.daily .focus-page .compare-row.key .winner { color:var(--gold); }" in tail


def test_soft_section_introduces_exactly_one_new_colour_and_it_is_calmer():
    """这一段唯一准许的新色值是爆冷用的暗酒红，而且必须比 --flash 更收敛。

    其余都得引用既有主题色。新增一支是因为 --flash #F15A3A 在收敛下来的
    这两页上是全屏最扎眼的东西；但它必须是"同色相往下压"，不能是又一支高
    饱和色，否则等于换了个颜色继续喊。
    """
    import colorsys

    # 标记本身就写在段落头部的注释里，split 之后还落在注释中间；那段注释会
    # 引用 #D6FF00 / #F15A3A 说明"从哪儿改过来的"，先跳到注释结束再看规则。
    tail = _CSS.split(_SOFT_MARKER, 1)[1].split("*/", 1)[1]
    tail = re.sub(r"/\*.*?\*/", "", tail, flags=re.S)
    hexes = set(re.findall(r"#[0-9A-Fa-f]{6}\b", tail))
    assert hexes == {"#C0705C"}, f"柔和段引入了预期之外的色值：{sorted(hexes)}"

    def hsv(value: str) -> tuple[float, float, float]:
        red, green, blue = (int(value[i:i + 2], 16) / 255 for i in (1, 3, 5))
        return colorsys.rgb_to_hsv(red, green, blue)

    soft_h, soft_s, _ = hsv("#C0705C")
    flash_h, flash_s, _ = hsv("#F15A3A")   # :root 的 --flash
    assert soft_s < flash_s, "新色比 --flash 还艳，等于换个颜色继续喊"
    assert abs(soft_h - flash_h) < 0.06, "新色偏离了原来的色相，不是'压下来'而是换色"


def test_soft_section_leaves_the_root_score_colour_alone():
    """:root 的 --score-win 仍然是荧光黄绿——柔和只发生在这两页的作用域里。"""
    root = re.search(r":root \{(.*?)\}", _CSS, re.S).group(1)
    assert "--score-win:#D6FF00" in root


@pytest.mark.parametrize("theme", ["dark", "light", "daily"])
def test_every_theme_defines_soft_accent(theme):
    """三个主题都得给 SOFT_ACCENT 赋值。

    set_theme 走 globals().update：少给一个 key，切过一次主题之后它就停在
    上一个主题的值上，之后每张卡都带着别人的颜色。
    """
    assert "SOFT_ACCENT" in cards._THEMES[theme]


def test_only_the_two_result_cards_use_the_soft_accent_in_pillow():
    """Pillow 侧也只有赛果速递和焦点复盘收敛，封面/今晚焦点不动。"""
    import inspect

    for builder, should in (
        (cards._card_scoreboard, True),
        (cards._card_focus, True),
        (cards._card_tonight, False),
    ):
        source = inspect.getsource(builder)
        assert ("SOFT_ACCENT" in source) is should, (
            f"{builder.__name__} 用不用 SOFT_ACCENT 和预期不符"
        )


def test_gold_is_spent_on_the_section_title_not_on_every_row():
    """收敛成一支强调色之后，它反而被用得太多。

    大标题、四个巡回赛 logo、徽章描边、种子号全是满强度的金，整页数下来比
    原来的荧光黄绿还密。行内这些配件是次要信息，必须退成中性。
    """
    tail = _CSS.split(_SOFT_MARKER, 1)[1]
    for rule in (
        "html.daily .results-page .seed, html.daily .focus-page .seed { color:var(--fade); }",
    ):
        assert rule in tail, f"缺少收敛规则：{rule}"
    # 巡回赛 logo / 赛事名退成 --panel-muted
    assert "html.daily .results-page .tour-level" in tail
    assert "color:var(--panel-muted); }" in tail


def test_score_numerals_use_a_geometric_sans_with_a_winner_loser_contrast():
    """比分数字用几何无衬线，且胜负两行必须有轻重对比。

    温网的品牌字是 Gotham——商用授权不能内嵌，而且是几何无衬线。所以既不能
    直接用，风格上也不是衬线那一路（中间试过一版 Newsreader 衬线，方向错了）。
    Montserrat 是公认最接近 Gotham 的开源替代。
    单字重不行：胜方和败方一样粗，一眼看不出谁赢。
    """
    from pathlib import Path

    tail = _CSS.split(_SOFT_MARKER, 1)[1]
    assert "font-family:'TL Numeral',sans-serif;" in tail
    assert "html.daily .results-page .set.sw" in tail and "font-weight:600;" in tail
    assert "html.daily .results-page .set.sl" in tail and "font-weight:500;" in tail

    fonts = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    for weight in (500, 600):
        path = fonts / f"Montserrat-latin-{weight}.woff2"
        assert path.is_file(), f"字体文件没入库：{path.name}"
        # 拉丁子集，别把整套 CJK 塞进每张卡的 base64 里
        assert path.stat().st_size < 60_000, f"{path.name} 太大了，应该是拉丁子集"
    assert not list(fonts.glob("Newsreader*")), "换掉的衬线字体没删干净"

    attribution = (fonts / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert "Montserrat" in attribution and "Open Font License" in attribution
    # 出处里要写清楚"为什么不是温网那支字本身"，别让下一个人再试一遍
    assert "Gotham" in attribution


def test_numeral_font_is_embedded_and_only_used_by_the_two_result_cards():
    """字体要真的内联进 HTML（CI 里没有系统字体可依赖），且只有这两页在用。"""
    from tennislive.render.webcards import _font_css

    css = _font_css()
    for weight in (500, 600):
        assert f"font-family:'TL Numeral';font-weight:{weight}" in css
    assert "data:font/woff2;base64," in css

    users = [
        line for line in _CSS.splitlines()
        if "TL Numeral" in line and not line.strip().startswith(("/*", "*"))
    ]
    assert users, "没有任何规则在用 TL Numeral"
    # 引用它的那条规则，选择器必须在上一行或本行限定在这两页里
    block = _CSS.split(_SOFT_MARKER, 1)[1]
    assert "TL Numeral" in block, "TL Numeral 用在了柔和段之外"
    assert _CSS.count("TL Numeral',sans-serif") == 1
