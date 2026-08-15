"""世界第一那条片子的图表——在位周数榜，和「差距能小到什么程度」的阶梯。

数据全部出自 **WTA 官方 2026 年版 Record Book**（`WTAMG26_WTARecordBook.pdf`，
2026-08-15 下载核对）：p4 `WEEKS AT WTA WORLD NO.1 SINGLES`、
p1 `NO.1 SINGLES RANKING HISTORY (since November 3, 1975)`。

⚠️ **周数榜只取译名表里有的人**。官方榜上还有穆古鲁扎（4 周）、普利斯科娃
（8 周）、特蕾西·奥斯汀、达文波特——`src/tennislive/zh/players.py` 里没有
这四个，而这个仓库为「人名手打」栽过两次（莱巴金娜写成里巴金娜、
奥斯塔彭科写成奥斯塔片科，两次都发出去了）。**为一张图去手打四个译名不值**，
真要用先把它们补进表里。

⚠️ 「0.8 分」和「4 分」**不是同一把尺子**：1976 年是平均分制，今天是 52 周
滚动累计；而「并列」是当年 WTA 的一次安排，不是算出来的 0 分。所以阶梯那张
图讲的是**「差距能小到什么程度」**，不是「历史最小差距排行榜」——后者会把
三种不同的计分口径并排成一张假榜，正是账号所有者说的「本来是科普却成了浆糊」。
"""

from __future__ import annotations

# (中文名, 周数)。官方 p4 原样，只筛掉译名表里没有的人。
WEEKS_AT_NO1: tuple[tuple[str, int], ...] = (
    ("格拉芙", 377),
    ("纳芙拉蒂洛娃", 332),
    ("小威廉姆斯", 319),
    ("埃弗特", 260),
    ("辛吉斯", 209),
    ("塞莱斯", 178),
    ("斯瓦泰克", 125),
    ("萨巴伦卡", 71),
    ("大威廉姆斯", 11),
    ("古拉贡", 2),
)


def weeks_at_no1_chart() -> str:
    """在位周数榜。顶端 377 周和榜尾 2 周同框——差 188 倍。

    ⚠️ 条长按**平方根**画，不按线性。线性的话 2 周那根只有 0.5 个像素，
    「最短的那个人」在图上直接消失——而她正是这一屏要讲的人。开方之后
    2 周仍然明显最短（约为 377 那根的 7%），但看得见。
    ⚠️ 而这件事**要在图上说出来**（副标题里写着「条长按平方根」），
    不然就是一张骗人的图。
    """
    top, bar_h, gap = 96, 34, 12
    x0, maxw = 250, 560
    hi = max(w for _, w in WEEKS_AT_NO1) ** 0.5
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">在世界第一待了多少周</text>',
        '<text x="450" y="72" text-anchor="middle" font-size="21" '
        'fill="#a9bcb2">WTA 官方纪录 · 条长按平方根，否则最短那根看不见</text>',
    ]
    for i, (zh, wk) in enumerate(WEEKS_AT_NO1):
        y = top + i * (bar_h + gap)
        w = maxw * (wk**0.5) / hi
        last = zh == "古拉贡"
        colour = "#e0b13a" if last else "#8fd6a8"
        parts.append(
            f'<text x="{x0 - 16}" y="{y + 24}" text-anchor="end" font-size="23" '
            f'fill="#e7f3ec">{zh}</text>'
        )
        parts.append(
            f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="5" '
            f'fill="{colour}" fill-opacity="{0.9 if last else 0.55}"/>'
        )
        parts.append(
            f'<text x="{x0 + w + 12:.1f}" y="{y + 24}" font-size="23" '
            f'font-weight="{700 if last else 400}" fill="{colour}">{wk} 周</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# 差距能小到什么程度。三行**各是各的口径**，见模块 docstring 那条警告。
MARGINS: tuple[tuple[str, str, str], ...] = (
    ("4 分", "2026 · 莱巴金娜", "赢下多伦多冠军也还差 4 分"),
    ("0.8 分", "1976 · 古拉贡", "这 0.8 分真的把她送上了世界第一"),
    ("0 分", "1995 · 格拉芙和塞莱斯", "并列世界第一，整整 64 周"),
)


def margin_ladder() -> str:
    """4 分 → 0.8 分 → 0 分。最后一行是并列，所以画成两条并排的条。"""
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">差距能小到什么程度</text>',
        '<text x="450" y="72" text-anchor="middle" font-size="21" '
        'fill="#a9bcb2">三种计分口径，各讲各的</text>',
    ]
    for i, (num, who, note) in enumerate(MARGINS):
        y = 118 + i * 146
        zero = num.startswith("0 ")
        colour = "#e0b13a" if zero else "#8fd6a8"
        parts.append(
            f'<rect x="60" y="{y}" width="780" height="116" rx="10" '
            f'fill="{colour}" fill-opacity="{0.20 if zero else 0.08}" '
            f'stroke="{colour}" stroke-width="{3 if zero else 1}"/>'
        )
        parts.append(
            f'<text x="104" y="{y + 62}" font-size="46" font-weight="700" '
            f'fill="{colour}">{num}</text>'
        )
        parts.append(
            f'<text x="290" y="{y + 46}" font-size="26" fill="#e7f3ec">{who}</text>'
        )
        parts.append(
            f'<text x="290" y="{y + 84}" font-size="21" fill="#a9bcb2">{note}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
