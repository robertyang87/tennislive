"""「二发那一段，规则里没有钟」那条解说片的示意图。

这条片子讲的全是规则结构和统计——**照片讲不清的那一类**，所以画。
`shot-clock` 那条已经把「一发 25 秒的钟怎么来的」铺开讲过了（人工计时 →
2018 美网 → 2026 全自动），同栏目不许重讲；这儿只画它没碰过的那一半：
一发打出去之后、二发打出来之前的那一段，为什么至今没有钟。

⚠️ 配色一律从 `diagram_palette` 来，不在这儿另调——账号所有者 2026-08-16
说的「卡片上的文字…很土」，根子就是几个模块各调各的。
"""

from __future__ import annotations

from .diagram_palette import FILL, INK, LIME, SOFT

# 正文那几张图里最低的那点墨不许超过这个 y——再往下会被卡片上那颗序号药丸
# 压住。⚠️ **这个数是渲成真卡片、把序号药丸叠上去看出来的，不是从 viewBox
# 推的**：第一版抄 `rulebook_cards` 写了 500，`next_gen_lab` 的末行
# 「不是没人想过，是已经在跑了」当场被「⑧ 所以」那颗药丸挤到右边——
# 居中的那行文字和药丸落在同一条水平线上。落点 486 的 `rule_quotes`
# 渲出来是干净的，所以收到 480 留一档余量。加行要往上压，不许加高度。
INK_BOTTOM = 480

# 封面没有序号药丸，所以它那张可以铺到更低。
COVER_INK_BOTTOM = 560


def gap_timeline() -> str:
    """封面：一分之间，钟只走前半段。整条片子的全部内容就是这一张。"""
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" font-size="34" font-weight="700"
        fill="{INK}">一分之间，钟只走前半段</text>

  <circle cx="72" cy="196" r="11" fill="{SOFT}"/>
  <text x="72" y="160" text-anchor="middle" font-size="25" fill="{SOFT}">上一分结束</text>

  <rect x="72" y="178" width="470" height="38" rx="9"
        fill="{FILL}" fill-opacity="0.22" stroke="{FILL}" stroke-width="3"/>
  <text x="307" y="205" text-anchor="middle" font-size="28" font-weight="800"
        fill="{FILL}">25 秒 · 有钟</text>

  <circle cx="542" cy="196" r="11" fill="{FILL}"/>
  <text x="542" y="160" text-anchor="middle" font-size="25" fill="{SOFT}">一发击出</text>

  <rect x="542" y="178" width="286" height="38" rx="9"
        fill="none" stroke="{LIME}" stroke-width="3" stroke-dasharray="9 8"/>
  <text x="685" y="205" text-anchor="middle" font-size="28" font-weight="800"
        fill="{LIME}">没有钟</text>

  <circle cx="828" cy="196" r="11" fill="{LIME}"/>
  <text x="828" y="160" text-anchor="middle" font-size="25" fill="{SOFT}">二发</text>

  <text x="685" y="266" text-anchor="middle" font-size="26" font-weight="700"
        fill="{LIME}">擦汗 · 走动 · 拍二十下球</text>
  <text x="685" y="302" text-anchor="middle" font-size="25" fill="{SOFT}">都在这一段里</text>

  <line x1="72" y1="352" x2="828" y2="352" stroke="{SOFT}" stroke-opacity=".35" stroke-width="2"/>

  <text x="72" y="410" font-size="26" fill="{SOFT}">一发</text>
  <text x="220" y="410" font-size="29" font-weight="800" fill="{INK}">25 秒</text>
  <text x="410" y="410" font-size="25" fill="{SOFT}">写在规则里</text>

  <text x="72" y="472" font-size="26" fill="{SOFT}">二发</text>
  <text x="220" y="472" font-size="29" font-weight="800" fill="{LIME}">没有这个数</text>
  <text x="470" y="472" font-size="25" fill="{SOFT}">只有一句「不得延误」</text>

  <text x="450" y="548" text-anchor="middle" font-size="27" font-weight="700"
        fill="{INK}">拍几下球，规则也没写</text>
</svg>
"""


def rule_quotes() -> str:
    """屏 1：把两处原文摘出来。照 `gamesmanship` 的做法——证据本身就是画面。"""
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="44" text-anchor="middle" font-size="34" font-weight="700"
        fill="{INK}">规则原文，只有两处</text>

  <text x="52" y="96" font-size="24" fill="{SOFT}">ATP · 大满贯 · 国际网联 · WTA 通用《发球计时程序》A-2</text>

  <rect x="52" y="118" width="796" height="72" rx="12"
        fill="{FILL}" fill-opacity="0.16" stroke="{FILL}" stroke-width="2" stroke-opacity="0.7"/>
  <text x="76" y="164" font-size="24" fill="{SOFT}">The Serve/Shot Clock is only in operation for <tspan
        font-weight="700" fill="{LIME}">1st serves</tspan><tspan fill="{SOFT}">.</tspan></text>

  <rect x="52" y="206" width="796" height="72" rx="12"
        fill="{FILL}" fill-opacity="0.16" stroke="{FILL}" stroke-width="2" stroke-opacity="0.7"/>
  <text x="76" y="252" font-size="24" fill="{SOFT}"><tspan font-weight="700"
        fill="{LIME}">2nd serves</tspan><tspan fill="{SOFT}"> will not have a Serve/Shot Clock.</tspan></text>

  <text x="52" y="330" font-size="24" fill="{SOFT}">2026 大满贯规则书 · 对二发的全部要求</text>

  <rect x="52" y="352" width="796" height="86" rx="12"
        fill="{FILL}" fill-opacity="0.16" stroke="{FILL}" stroke-width="2" stroke-opacity="0.7"/>
  <text x="450" y="408" text-anchor="middle" font-size="38" font-weight="800"
        fill="{LIME}">&#8220;without delay&#8221;</text>

  <text x="450" y="478" text-anchor="middle" font-size="27" font-weight="700"
        fill="{INK}">两个词，没有秒数，也没有次数</text>
</svg>
"""


def clock_ends_at_first() -> str:
    """屏 3：25 秒的终点写的是「一发被击出」，所以二发天然在计时之外。"""
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="44" text-anchor="middle" font-size="34" font-weight="700"
        fill="{INK}">不是漏写，是终点画在了一发上</text>

  <text x="52" y="96" font-size="24" fill="{SOFT}">国际网联《网球规则》第 29 条 a 款</text>

  <rect x="52" y="118" width="796" height="104" rx="12"
        fill="{FILL}" fill-opacity="0.16" stroke="{FILL}" stroke-width="2" stroke-opacity="0.7"/>
  <text x="76" y="160" font-size="24" fill="{SOFT}">…until the <tspan font-weight="700"
        fill="{LIME}">first service is struck</tspan></text>
  <text x="76" y="198" font-size="24" fill="{SOFT}">直到一发被击出——这 25 秒就到头了</text>

  <circle cx="90" cy="290" r="10" fill="{SOFT}"/>
  <text x="90" y="262" text-anchor="middle" font-size="23" fill="{SOFT}">一分结束</text>
  <line x1="90" y1="290" x2="470" y2="290" stroke="{FILL}" stroke-width="5"/>
  <text x="280" y="326" text-anchor="middle" font-size="26" font-weight="800" fill="{FILL}">这 25 秒</text>

  <circle cx="470" cy="290" r="14" fill="{LIME}"/>
  <text x="470" y="262" text-anchor="middle" font-size="23" font-weight="700" fill="{LIME}">一发击出</text>
  <text x="470" y="356" text-anchor="middle" font-size="25" font-weight="800" fill="{LIME}">计时到此为止</text>

  <line x1="470" y1="290" x2="830" y2="290" stroke="{SOFT}" stroke-width="3" stroke-dasharray="9 8"/>
  <text x="660" y="326" text-anchor="middle" font-size="25" fill="{SOFT}">一发失误之后</text>

  <line x1="52" y1="396" x2="848" y2="396" stroke="{SOFT}" stroke-opacity=".35" stroke-width="2"/>

  <text x="450" y="440" text-anchor="middle" font-size="27" font-weight="700" fill="{INK}">
    这一分还没打完，计时却已经走完了</text>
  <text x="450" y="478" text-anchor="middle" font-size="25" fill="{SOFT}">
    所以二发那一段，不属于任何一个钟</text>
</svg>
"""


def slow_play_history() -> str:
    """屏 5：拿时间做文章不是新鲜事。

    ⚠️ 第一版把六件事排成了「年份｜赛事｜一句话」的三列表格，渲出来就是一面
    文字墙，而下面那三条要点又把同样的事再说一遍——账号所有者 2026-09-15：
    「内容里面要图文并茂一些，不要堆砌太多文字」。CLAUDE.md 早写过同一条：
    「列清单可以，但别用文字排成表格冒充图表」。现在是一条真的时间轴，
    四个节点，每个节点两行短字；要点那一栏改说图上没有的东西。
    """
    marks = (
        (110, "1989", "张德培", "喝水被判违例"),
        (350, "2012", "5 小时 53 分", "最长的大满贯决赛"),
        (590, "2018", "钟上场", "第一次进大满贯正赛"),
        (818, "2026", "谢尔顿", "要求管二发"),
    )
    out = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="450" y="46" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{INK}">拿时间做文章，一直都有</text>',
        f'<line x1="70" y1="212" x2="846" y2="212" stroke="{SOFT}" '
        f'stroke-opacity=".55" stroke-width="3"/>',
    ]
    for x, year, line1, line2 in marks:
        hot = year == "2026"
        colour = LIME if hot else FILL
        out += [
            f'<text x="{x}" y="176" text-anchor="middle" font-size="30" '
            f'font-weight="800" fill="{colour}">{year}</text>',
            f'<circle cx="{x}" cy="212" r="{13 if hot else 10}" fill="{colour}"/>',
            f'<text x="{x}" y="272" text-anchor="middle" font-size="26" '
            f'font-weight="700" fill="{INK if hot else SOFT}">{line1}</text>',
            f'<text x="{x}" y="308" text-anchor="middle" font-size="23" '
            f'fill="{SOFT}">{line2}</text>',
        ]
    out += [
        f'<line x1="70" y1="376" x2="846" y2="376" stroke="{SOFT}" '
        f'stroke-opacity=".3" stroke-width="2"/>',
        f'<text x="450" y="432" text-anchor="middle" font-size="27" '
        f'font-weight="700" fill="{INK}">1989 年那场，伦德尔最后输在一个二发上</text>',
        f'<text x="450" y="472" text-anchor="middle" font-size="24" '
        f'fill="{SOFT}">而这一次问的，是没有钟的那一段</text>',
        "</svg>",
    ]
    return "\n".join(out)


def next_gen_lab() -> str:
    """屏 7：同一块试验田，上面那条路走完了，下面这条正在走。

    ⚠️ 同样从「年份＋一句话」的竖排列表改成两条平行的轴——这一屏的全部意思
    是**两段时间线长得一样**，而列表表达不了「一样」，并排的轴可以。
    """
    top = ((150, "2017", "试验田"), (420, "2018", "大满贯"), (690, "2019", "巡回赛"))
    bottom = ((150, "2023", "8 秒"), (420, "2024", "沿用"), (690, "2025", "沿用"))
    out = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="450" y="46" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{INK}">同一块试验田，这条路走过一次</text>',
        f'<text x="70" y="118" font-size="25" font-weight="700" fill="{SOFT}">一发的 25 秒</text>',
        f'<line x1="150" y1="176" x2="690" y2="176" stroke="{FILL}" stroke-width="4"/>',
    ]
    for x, year, what in top:
        out += [
            f'<circle cx="{x}" cy="176" r="11" fill="{FILL}"/>',
            f'<text x="{x}" y="152" text-anchor="middle" font-size="27" '
            f'font-weight="800" fill="{FILL}">{year}</text>',
            f'<text x="{x}" y="216" text-anchor="middle" font-size="24" fill="{SOFT}">{what}</text>',
        ]
    out += [
        f'<path d="M782 176 L846 176" stroke="{FILL}" stroke-width="4" stroke-dasharray="8 7"/>',
        f'<path d="M868 250 L868 330" stroke="{SOFT}" stroke-width="0"/>',
        f'<text x="450" y="290" text-anchor="middle" font-size="25" '
        f'font-weight="700" fill="{SOFT}">同一条路，再走一次</text>',
        f'<path d="M450 306 L450 344" stroke="{LIME}" stroke-width="4"/>',
        f'<path d="M438 332 L450 348 L462 332 Z" fill="{LIME}"/>',
        f'<text x="70" y="392" font-size="25" font-weight="700" fill="{LIME}">二发</text>',
        f'<line x1="150" y1="438" x2="690" y2="438" stroke="{LIME}" stroke-width="4"/>',
    ]
    for x, year, what in bottom:
        out += [
            f'<circle cx="{x}" cy="438" r="11" fill="{LIME}"/>',
            f'<text x="{x}" y="414" text-anchor="middle" font-size="27" '
            f'font-weight="800" fill="{LIME}">{year}</text>',
            f'<text x="{x}" y="478" text-anchor="middle" font-size="24" fill="{SOFT}">{what}</text>',
        ]
    out += [
        f'<path d="M782 438 L846 438" stroke="{LIME}" stroke-width="4" stroke-dasharray="8 7"/>',
        "</svg>",
    ]
    return "\n".join(out)
