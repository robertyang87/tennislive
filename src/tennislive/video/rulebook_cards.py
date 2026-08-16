"""「规则书里真有『盘外招』这个词」那条片子的四张示意图。

条文全部出自 **ATP 2026 年版规则书**（`2026-rulebook_19dec25.pdf`，2026-08-16 下载
核对），第 VII 章 THE COMPETITION：

- `N. Continuous Play/Delay of Game` —— 25 秒 / 90 秒换边 / 120 秒盘间
- `P. Time and Equipment Cases` 的 `Changing Shoes Case` —— 换鞋
- `Q. Toilet/Change of Attire Break` —— 厕所与换衣
- `N.4) Not Playing to the Reasonable Pace of the Server` —— **gamesmanship**

⚠️ **规则书拿不到的话别以为是「ATP 的东西够不着」。** `atptour.com` 对本环境一律
403，**而且带浏览器 UA 的 curl 现在也是 403**（CLAUDE.md 里「curl 能过」那条已经
过期）。能过的是 **ATP 系的其它域名**，`/-/media/` 路径同构：规则书从
`mubadaladcopen.com/-/media/files/rulebook/2026/…` 下到的，新闻头图从
`nextgenatpfinals.com/-/media/images/news/…` 下到的。

⚠️ **这条片子全程只引条文，不给任何人定性。** 账号所有者的原话是
「按最稳妥的方式去表达」——而最稳妥的表达不需要斟酌措辞：规则书自己把话说完了
（换鞋那一条明写着装备失灵由主裁逐次裁量；判不判 gamesmanship 也明写着交给主裁）。
**片子只负责把条文念出来，不负责判断谁在使坏。**
"""

from __future__ import annotations

# 一张图里最低的那点墨不许超过这个 y——再往下会被卡片上那颗序号药丸压住。
# 这个数是渲成真卡片看出来的，不是从 viewBox 推的（600 是画布高，不是可用高）。
INK_BOTTOM = 500

_FG = "#e7f3ec"
_DIM = "#a9bcb2"
_GREEN = "#8fd6a8"
_GOLD = "#e0b13a"


def _head(title: str, subtitle: str) -> list[str]:
    return [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="450" y="42" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{_FG}">{title}</text>',
        f'<text x="450" y="76" text-anchor="middle" font-size="21" '
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
    x0, maxw, top, bar_h, pitch = 250, 520, 130, 56, 108
    hi = max(s for _, s, _ in CLOCKS)
    for i, (label, secs, when) in enumerate(CLOCKS):
        y = top + i * pitch
        w = maxw * secs / hi
        parts.append(
            f'<text x="{x0 - 20}" y="{y + 38}" text-anchor="end" font-size="26" '
            f'fill="{_FG}">{label}</text>'
        )
        parts.append(
            f'<rect x="{x0}" y="{y}" width="{w:.0f}" height="{bar_h}" rx="7" '
            f'fill="{_GREEN}" fill-opacity="0.5"/>'
        )
        parts.append(
            f'<text x="{x0 + 22}" y="{y + 38}" font-size="34" font-weight="700" '
            f'fill="{_GREEN}">{secs} 秒</text>'
        )
        parts.append(
            f'<text x="{x0 - 20}" y="{y + 70}" text-anchor="end" font-size="20" '
            f'fill="{_DIM}">{when}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def shoe_rule() -> str:
    """换鞋那一条：一场限一次，**除非**装备失灵——那就由主裁逐次裁量。

    ⚠️ 这一屏是全片「不给人定性」的支点：霍达尔鞋带断了属于后一支，
    规则上没有次数上限。片子把条文摆出来就够了，不用替谁下结论。
    """
    parts = _head(
        "换鞋，规则书专门写了一条",
        "ATP 2026 规则书 · Changing Shoes Case",
    )
    parts.append(
        f'<rect x="290" y="112" width="320" height="66" rx="10" '
        f'fill="{_GREEN}" fill-opacity="0.14" stroke="{_GREEN}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="450" y="154" text-anchor="middle" font-size="26" '
        f'fill="{_FG}">换边时要求换鞋或换袜</text>'
    )
    # 两条分支，左边是常规、右边是例外（例外那支上色，因为它才是这一屏的落点）
    branches = (
        (60, "主裁给了额外时间", "一场限一次", _GREEN, 0.10, 1),
        (470, "装备失灵", "主裁逐次裁量，没有次数上限", _GOLD, 0.20, 3),
    )
    for x, head, tail, colour, op, sw in branches:
        parts.append(
            f'<path d="M450 178 L450 206 L{x + 185} 206 L{x + 185} 246" '
            f'fill="none" stroke="{colour}" stroke-width="2" stroke-opacity="0.55"/>'
        )
        parts.append(
            f'<rect x="{x}" y="246" width="370" height="146" rx="10" '
            f'fill="{colour}" fill-opacity="{op}" stroke="{colour}" stroke-width="{sw}"/>'
        )
        parts.append(
            f'<text x="{x + 185}" y="298" text-anchor="middle" font-size="26" '
            f'font-weight="700" fill="{colour}">{head}</text>'
        )
        parts.append(
            f'<text x="{x + 185}" y="346" text-anchor="middle" font-size="23" '
            f'fill="{_FG}">{tail}</text>'
        )
    parts.append(
        f'<text x="450" y="452" text-anchor="middle" font-size="26" '
        f'fill="{_DIM}">鞋带断了，属于右边那一支</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# 条文原文：三盘制一场一次；只能在盘间；厕所从进门起 3 分钟；厕所加换衣合计 5 分钟。
TOILET_LIMITS: tuple[str, ...] = (
    "三盘制 一场只有一次",
    "只能在盘间，不得用于其他目的",
    "厕所 3 分钟，加换衣合计 5 分钟",
)


def toilet_rule() -> str:
    """八分钟 → 三分钟：一次争议如何变成一条写死的条文。

    ⚠️ 左边那个 8 分钟是**当年媒体记的时长**，不是规则书里的数；右边三条才是
    条文。所以两根条子的颜色和描边不一样，副标题也点明了左边是「那一次」、
    右边是「现在的条文」——别让人读成「规则以前允许 8 分钟」。
    """
    parts = _head(
        "那一次八分钟，现在写死三分钟",
        "左：2021 年美网那次争议 · 右：ATP 2026 规则书 Q 条",
    )
    x0, maxw, hi = 250, 470, 8
    for i, (label, mins, colour, op) in enumerate(
        (("2021 年那一次", 8, _DIM, 0.16), ("今天的条文上限", 3, _GOLD, 0.9))
    ):
        y = 122 + i * 92
        w = maxw * mins / hi
        parts.append(
            f'<text x="{x0 - 20}" y="{y + 42}" text-anchor="end" font-size="24" '
            f'fill="{_FG}">{label}</text>'
        )
        parts.append(
            f'<rect x="{x0}" y="{y}" width="{w:.0f}" height="62" rx="7" '
            f'fill="{colour}" fill-opacity="{op}"/>'
        )
        parts.append(
            f'<text x="{x0 + w + 16:.0f}" y="{y + 42}" font-size="32" '
            f'font-weight="700" fill="{colour}">{mins} 分钟</text>'
        )
    for i, line in enumerate(TOILET_LIMITS):
        y = 326 + i * 58
        parts.append(
            f'<rect x="120" y="{y}" width="660" height="46" rx="8" '
            f'fill="{_GREEN}" fill-opacity="0.08"/>'
        )
        parts.append(
            f'<text x="450" y="{y + 33}" text-anchor="middle" font-size="24" '
            f'fill="{_FG}">{line}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def two_violations() -> str:
    """两种罚，分界是意图——而意图，规则书明确交给主裁认定。

    条文原文（N.4 Not Playing to the Reasonable Pace of the Server）：
    主裁 **must** 在接发方使用 gamesmanship 时判 Code Violation；
    若只是拖慢了发球方的合理节奏，则在 25 秒前判 Time Violation。

    ⚠️ 全片的落点在这儿：`gamesmanship` 是规则书里的**正式术语**，
    而它罚得比单纯拖延重——重的那一档要先认定意图。
    """
    parts = _head(
        "拖延和盘外招，罚得不一样",
        "ATP 2026 规则书 · Not Playing to the Reasonable Pace of the Server",
    )
    cols = (
        (58, "拖慢了发球方的节奏", "Time Violation", "时间违例", _GREEN, 0.10, 1),
        (472, "在使用 gamesmanship", "Code Violation", "行为违例", _GOLD, 0.20, 3),
    )
    for x, what, en, zh, colour, op, sw in cols:
        parts.append(
            f'<rect x="{x}" y="118" width="370" height="242" rx="12" '
            f'fill="{colour}" fill-opacity="{op}" stroke="{colour}" stroke-width="{sw}"/>'
        )
        parts.append(
            f'<text x="{x + 185}" y="168" text-anchor="middle" font-size="24" '
            f'fill="{_FG}">{what}</text>'
        )
        parts.append(
            f'<text x="{x + 185}" y="248" text-anchor="middle" font-size="34" '
            f'font-weight="700" fill="{colour}">{zh}</text>'
        )
        parts.append(
            f'<text x="{x + 185}" y="296" text-anchor="middle" font-size="21" '
            f'fill="{_DIM}">{en}</text>'
        )
        parts.append(
            f'<text x="{x + 185}" y="336" text-anchor="middle" font-size="20" '
            f'fill="{_DIM}">25 秒之内判</text>'
            if colour == _GREEN
            else f'<text x="{x + 185}" y="336" text-anchor="middle" font-size="20" '
            f'fill="{_DIM}">重的那一档</text>'
        )
    parts.append(
        f'<text x="450" y="424" text-anchor="middle" font-size="26" '
        f'fill="{_FG}">分界是意图</text>'
    )
    parts.append(
        f'<text x="450" y="466" text-anchor="middle" font-size="23" '
        f'fill="{_DIM}">而认定意图这件事，规则书交给了主裁</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)
