"""「规则书里真有『盘外招』这个词」那条片子的四张示意图。

条文全部出自 **ATP 2026 年版规则书**（`2026-rulebook_19dec25.pdf`，2026-08-16
下载后逐条核对，210 页、99.8 万字符），第 VII 章 THE COMPETITION：

- `N. Continuous Play/Delay of Game` —— 25 秒 / 90 秒换边 / 120 秒盘间
- `P. Time and Equipment Cases` 的三个判例 —— `Shoe Breaks` / `Changing Shoes`
  / `Replacing Shoes`
- `Q. Toilet/Change of Attire Break` —— 离场那道门
- **`gamesmanship` 这个词在全书出现三次**，三处的动词还不一样

⚠️ **「三次」是数出来的，不是印象**：`t.count("gamesmanship") == 3`，分别落在
第 105、108、110 页；首字母大写的 `Gamesmanship` 出现 **0** 次。这条片子的标题
（「规则书里真有这个词」）就靠它撑着，所以它必须是数出来的——本文件所在的仓库
为「没量过的推断写进注释，之后每个人都拿它当判据」栽过不止一次。

⚠️ **规则书拿不到的话别以为是「ATP 的东西够不着」。** `atptour.com` 对本环境
一律 403，**而且带浏览器 UA 的 curl 现在也是 403**（CLAUDE.md 里「curl 能过」
那条已经过期）。能过的是 **ATP 系的其它域名**，`/-/media/` 路径同构：规则书从
`mubadaladcopen.com/-/media/files/rulebook/2026/…` 下到的，新闻头图从
`nextgenatpfinals.com/-/media/images/news/…` 下到的。

⚠️ **这条片子全程只引条文，不给任何人定性。** 账号所有者的原话是
「按最稳妥的方式去表达」——而最稳妥的表达不需要斟酌措辞：**规则书自己把话
说完了**。鞋那一条明写着坏了就该停表、由主裁逐次裁量；判不判 gamesmanship
也明写着交给主裁认定。**片子只负责把条文念出来，不负责判断谁在使坏。**

⚠️ **故意没有画「2021 年美网八分钟 → 现在三分钟」那种跨年份对比。** 那是大满贯
赛事，归大满贯规则书管，不归 ATP 这本；而 CLAUDE.md 那条「判历史事件要用当年
那本规则书」说的正是这种混用。手上只有 2026 这一本，就只讲 2026 这一本写了什么。
"""

from __future__ import annotations

from .diagram_palette import AMBER, FILL, INK, LIME, SOFT

# 一张图里最低的那点墨不许超过这个 y——再往下会被卡片上那颗序号药丸压住。
# 这个数是渲成真卡片看出来的，不是从 viewBox 推的（600 是画布高，不是可用高）。
INK_BOTTOM = 500

# 本地别名，只为让下面那些 f-string 短一点。**值一律从 `diagram_palette`
# 来，不在这儿另调**——账号所有者 2026-08-16 说的「卡片上的文字…很土，
# 前景的颜色很鲜艳」，根子就是这几个模块各调各的，和卡片自己那套对不上。
_FG = INK        # 正文，和卡片 `.point` 同色
_DIM = SOFT      # 次级说明
_ACC = LIME      # **文字**上的强调色，和卡片 `.point i` / `.ask` 同色
_FILL = FILL     # 大面积的条和框，铺一片亮绿会盖过字，所以底色另用一档
_GOLD = AMBER    # 第二类（不准 / 例外）


def _head(title: str, subtitle: str) -> list[str]:
    return [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="450" y="44" text-anchor="middle" font-size="36" '
        f'font-weight="700" fill="{_FG}">{title}</text>',
        f'<text x="450" y="80" text-anchor="middle" font-size="26" '
        f'fill="{_DIM}">{subtitle}</text>',
    ]


# (标签, 秒数, 什么时候)。条文原文：a maximum of twenty-five (25) seconds may
# elapse from the moment the ball goes out of play … except at a ninety (90)
# second changeover or a one hundred and twenty (120) second set break.
CLOCKS: tuple[tuple[str, int, str], ...] = (
    ("两分之间", 25, "球出界到下一分开球"),
    ("换边", 90, "单数局结束"),
    ("盘间", 120, "一盘打完"),
)


def time_structure() -> str:
    """25 / 90 / 120——网球的时间是被切成几段的。

    ⚠️ 这张**按线性画**，不开方：最短那根占最长那根的 21%，看得见。
    开方是给「2 周 vs 377 周」那种一百多倍的差距用的，这里用了反而是
    把差距画小，等于骗人往另一个方向。
    """
    parts = _head("一分之间，最多 25 秒", "ATP 2026 规则书 · Play shall be continuous")
    # x0 是从**最长那条标签**倒推的：「球出界到下一分开球」9 个字 × 26px
    # ≈ 234px，右端顶在 x0-20，所以 x0 至少要 254。250 差一点点，渲出来
    # 那行左边被画布切掉一个字——**而 SVG 溢出不报错**，只是没了。
    x0, maxw, top, bar_h, pitch = 300, 470, 136, 58, 112
    hi = max(s for _, s, _ in CLOCKS)
    for i, (label, secs, when) in enumerate(CLOCKS):
        y = top + i * pitch
        w = maxw * secs / hi
        parts.append(
            f'<text x="{x0 - 20}" y="{y + 40}" text-anchor="end" font-size="28" '
            f'fill="{_FG}">{label}</text>'
        )
        parts.append(
            f'<rect x="{x0}" y="{y}" width="{w:.0f}" height="{bar_h}" rx="7" '
            f'fill="{_FILL}" fill-opacity="0.5"/>'
        )
        # ⚠️ 秒数**装不下就摆到条子外面**。`25 秒` 在 36px 下约 80px 宽，而最短
        # 那根条子只有 98px——压在里面正好探出头一点点，看着像渲错了。这跟
        # 「条形图上不要写字」是同一件事的两半：能摆进去才摆，摆不进去就让路。
        inside = w >= 118
        parts.append(
            f'<text x="{x0 + (22 if inside else w + 20):.0f}" y="{y + 40}" '
            f'font-size="36" font-weight="700" fill="{_ACC}">{secs} 秒</text>'
        )
        parts.append(
            f'<text x="{x0 - 20}" y="{y + 74}" text-anchor="end" font-size="26" '
            f'fill="{_DIM}">{when}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# 鞋那三个判例，全在 `P. Time and Equipment Cases` 里，一个挨着一个。
# 分界不是「换不换鞋」，是**坏没坏**。
SHOE_CASES: tuple[tuple[str, str, str, bool], ...] = (
    ("Shoe Breaks", "鞋坏了，备用的那双在更衣室",
     "主裁应当停表，让他去拿", True),
    ("Changing Shoes", "换边时要求换鞋换袜，主裁额外给时间",
     "一场限一次；但装备失灵优先，那就逐次裁量", True),
    ("Replacing Shoes", "没坏，想换一双鞋底更抓地的",
     "不准。这不算「装备失灵」", False),
)


def shoe_rule() -> str:
    """鞋那三条判例摆一起：分界是**坏没坏**，不是换不换。

    ⚠️ 这一屏是全片「不给人定性」的支点。鞋带断了落在第一条上，而第一条
    白纸黑字写着「主裁应当停表」——**规则书自己把话说完了**，不用替谁下结论。
    第三条留着是因为**没有它就看不出分界在哪儿**：一条「不准」的判例，才让
    上面两条「准」显出条件来。
    """
    parts = _head("鞋，规则书写了三条判例", "ATP 2026 规则书 · Time and Equipment Cases")
    # ⚠️ case 和 decision **各占一整行**，不许摆成同一行的左右两端：中文一长
    # 两段就会在中间撞上，而 SVG 的 <text> 不换行也不报错——第一版正是这么渲出
    # 一行叠字的（`换边时要求换鞋换袜，主裁额外给时间` 撞 `一场限一次；但装备
    # 失灵优先…`）。判据只有一条：**渲出来看**。
    for i, (name, case, decision, allowed) in enumerate(SHOE_CASES):
        y = 104 + i * 120
        colour = _FILL if allowed else _GOLD      # 框：大面积，用底色那一档
        ink = _ACC if allowed else _GOLD           # 字：用和卡片同一个亮绿
        parts.append(
            f'<rect x="52" y="{y}" width="796" height="112" rx="12" '
            f'fill="{colour}" fill-opacity="{0.12 if allowed else 0.20}" '
            f'stroke="{colour}" stroke-width="{1 if allowed else 3}"/>'
        )
        parts.append(
            f'<text x="76" y="{y + 34}" font-size="26" fill="{_DIM}">{name}</text>'
        )
        parts.append(
            f'<text x="824" y="{y + 34}" text-anchor="end" font-size="28" '
            f'font-weight="700" fill="{colour}">{"准" if allowed else "不准"}</text>'
        )
        parts.append(
            f'<text x="76" y="{y + 70}" font-size="27" fill="{_FG}">{case}</text>'
        )
        parts.append(
            f'<text x="76" y="{y + 100}" font-size="26" fill="{_DIM}">{decision}</text>'
        )
    parts.append(
        f'<text x="450" y="{INK_BOTTOM - 4}" text-anchor="middle" font-size="30" '
        f'fill="{_FG}">分界是坏没坏，不是换不换</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# `Q. Toilet/Change of Attire Break` 的原文要点。最后一条是这一屏的落点：
# **鞋袜衣服要在场上换**，能离场的只有换湿短裤/内裤。
TOILET_LIMITS: tuple[tuple[str, str], ...] = (
    ("三盘制", "一场只有一次，而且只能在盘间"),
    ("厕所", "从进门起算 3 分钟"),
    ("加换衣", "合计 5 分钟，超了按连续两次时间违例罚"),
    ("鞋、袜、上衣", "要在场上换 —— 离场只为换湿短裤"),
)


def toilet_rule() -> str:
    """离场那道门有多窄——而鞋根本不在门里面。

    ⚠️ 最后一行是这一屏存在的理由：条文原文 `Shirts, socks, and shoes should
    be changed on court`，也就是说鞋这件事从头到尾都发生在场上，跟「离场」
    那套限制是两码事。前三行不是背景板，是**用来量这道门有多窄的尺子**。
    """
    parts = _head("离场那道门，只开这么大", "ATP 2026 规则书 · Toilet/Change of Attire Break")
    for i, (what, limit) in enumerate(TOILET_LIMITS):
        y = 128 + i * 92
        last = i == len(TOILET_LIMITS) - 1
        colour = _GOLD if last else _FILL         # 框
        ink = _GOLD if last else _ACC              # 字
        parts.append(
            f'<rect x="52" y="{y}" width="796" height="74" rx="10" '
            f'fill="{colour}" fill-opacity="{0.20 if last else 0.09}" '
            f'stroke="{colour}" stroke-width="{3 if last else 0}"/>'
        )
        parts.append(
            f'<text x="80" y="{y + 48}" font-size="28" font-weight="700" '
            f'fill="{colour}">{what}</text>'
        )
        parts.append(
            f'<text x="820" y="{y + 48}" text-anchor="end" font-size="27" '
            f'fill="{_FG}">{limit}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# `gamesmanship` 在 ATP 2026 规则书里出现的**全部三处**，按页码排。
# 第三列是条文自己用的情态动词——三处不一样，而主语一样。
GAMESMANSHIP_SPOTS: tuple[tuple[str, str, str], ...] = (
    ("接发方拖慢发球方的节奏",
     "Not Playing to the Reasonable Pace of the Server", "must 必须判"),
    ("自称急性伤病，被判定其实是抽筋",
     "Medical Conditions", "could 可以判"),
    ("接发方反射性回球之后喊「等一下」",
     "Receiver Not Ready", "may 可以判"),
)


def two_violations() -> str:
    """三处 gamesmanship，三个不同的情态动词，同一个主语：主裁。

    ⚠️ 全片的落点在这儿，而它是**数出来的**：全书 `gamesmanship` 出现三次，
    一次不多一次不少（见模块 docstring）。三处的动词分别是 must / could / may
    ——重的那一档必须判，另两档交给主裁掂量；但**认定意图这件事，三处都是
    主裁的活**。片子讲到这儿就停，不替谁下结论。
    """
    parts = _head(
        "「盘外招」在规则书里出现三次",
        "ATP 2026 规则书 · must / could / may，主语都是主裁",
    )
    for i, (what, where, verb) in enumerate(GAMESMANSHIP_SPOTS):
        y = 108 + i * 110
        parts.append(
            f'<rect x="52" y="{y}" width="796" height="98" rx="12" '
            f'fill="{_FILL}" fill-opacity="0.10" stroke="{_FILL}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="76" y="{y + 44}" font-size="28" fill="{_FG}">{what}</text>'
        )
        parts.append(
            f'<text x="824" y="{y + 44}" text-anchor="end" font-size="26" '
            f'font-weight="700" fill="{_GOLD}">{verb}</text>'
        )
        parts.append(
            f'<text x="76" y="{y + 80}" font-size="26" fill="{_DIM}">{where}</text>'
        )
    # ⚠️ 落款**只留一行**。第一版写了两行（`INK_BOTTOM-38` 和 `INK_BOTTOM`），
    # 渲成真卡片一看，第二行正压在那颗序号药丸的上沿——`INK_BOTTOM` 是**上限
    # 不是位置**，贴着它放就等于没有余量。第二行那句话挪进了副标题。
    parts.append(
        f'<text x="450" y="{INK_BOTTOM - 28}" text-anchor="middle" font-size="32" '
        f'font-weight="700" fill="{_FG}">三处都要先认定意图</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# 封面那张。三条原文摘句 + 页码，**就是那个词的证据本身**。
#
# ⚠️ 摘句一字未改，从 `2026-rulebook_19dec25.pdf` 抽出来的正文里直接截的：
#   p.105  The Chair Umpire must assess a Code Violation
#          **if the receiver is employing “gamesmanship.”**
#   p.108  If it is determined by the Chair Umpire or Supervisor
#          **that gamesmanship was involved**, then a Code Violation …
#   p.110  (If the Chair Umpire **believes that gamesmanship is involved**
#          on the part of the receivers, then he may issue a code violation …)
BOOK_HITS: tuple[tuple[str, str, str, str], ...] = (
    ("p.105", "if the receiver is employing ", "gamesmanship", "."),
    ("p.108", "that ", "gamesmanship", " was involved"),
    ("p.110", "believes that ", "gamesmanship", " is involved"),
)


def word_in_the_book() -> str:
    """封面：把那个词在规则书里的三处原文摘出来，页码摆在旁边。

    ⚠️ **封面故意不用球员照片。** 这条片子的标题问的是「盘外招算犯规吗」，
    把某一个人的脸压在这句话下面，等于替读者认定了他就是那个使盘外招的人
    ——而账号所有者要的正是「按最稳妥的方式去表达」。霍达尔那张 ATP 官方
    实拍留在第 ① 屏，那一屏的文字只有比分、轮次和双方的原话，不带判断。
    （顺带：那张图 1920×1080，铺满 1080×1440 的封面要放大 133%，本来也过不了
    `test_封面图不许被放大` 那条 1.00x 的地板。**但换掉它的理由是前一条，
    不是这一条**——分辨率只是碰巧站在同一边。）

    ⚠️ 和第 ⑤ 屏不重复：那一屏讲的是**三处各自是什么情形、动词有什么差别**，
    这一屏只摆**原文和页码**，也就是「这个词真的在书里」这件事本身。
    """
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="450" y="46" text-anchor="middle" font-size="36" '
        f'font-weight="700" fill="{_FG}">「盘外招」不是球迷发明的词</text>',
        f'<text x="450" y="86" text-anchor="middle" font-size="27" '
        f'fill="{_DIM}">ATP 2026 规则书 · 全书 210 页</text>',
    ]
    for i, (page, before, word, after) in enumerate(BOOK_HITS):
        y = 128 + i * 116
        # ⚠️ 封面上盖着一层 `.scrim`（顶上就有 55% 的压暗），所以这三个框比
        # 正文屏的同类要**再实一点**才读得出来——渲成真封面看出来的，不是照
        # 正文屏那套抄的。
        parts.append(
            f'<rect x="52" y="{y}" width="796" height="94" rx="12" '
            f'fill="{_FILL}" fill-opacity="0.16" stroke="{_FILL}" '
            f'stroke-width="2" stroke-opacity="0.7"/>'
        )
        parts.append(
            f'<text x="76" y="{y + 38}" font-size="26" fill="{_DIM}">{page}</text>'
        )
        # ⚠️ **高亮只靠颜色，不画底色块。** 第一版在词底下垫了一个 <rect>，
        # 位置按 `12 * len(before)` 估——渲出来三行**没有一行对得上**（前两行
        # 偏左、第一行探出词尾）。SVG 里没有「量一段文字有多宽」这回事，
        # 要么拿 PIL 按真字体量一遍（比分板那条就是这么做的），要么干脆别画。
        # 这一屏用不着那块底：金色加粗在深绿底上已经足够跳出来，而且
        # 「一屏只留一个强调色」本来就说了别再叠第二种强调。
        parts.append(
            f'<text x="76" y="{y + 78}" font-size="26" fill="{_DIM}">{before}'
            f'<tspan font-size="26" font-weight="700" fill="{_GOLD}">{word}</tspan>'
            f'<tspan fill="{_DIM}">{after}</tspan></text>'
        )
    parts.append(
        f'<text x="450" y="524" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{_FG}">全书出现三次</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)
