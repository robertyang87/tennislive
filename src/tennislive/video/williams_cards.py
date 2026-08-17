"""「开球之前」威廉姆斯姐妹那条片子的示意图。

这条片子四屏里只有这一屏是画的，其余三屏全是实拍——账号所有者 2026-08-17：
「我需要更多是图片或视频，而不是文字卡片」「最好再减少示意图」。

⚠️ **那为什么这一屏还画？** 因为它是 CLAUDE.md 那条触发条件本来说的那种：
「这件事**照片本身讲不清**」。这一屏要说的是「她们作为一对组合，十七年里在
四个大满贯拿了 14 个双打冠军，外加三届奥运金牌」——**没有任何一张照片能表达
一串横跨十七年的冠军年份**，不是拍不到，是拍不出。而把它摊在一条时间轴上，
一眼就看得见那个真正的形状：**冠军是分两簇来的，中间隔着好几年**。

数字两个源独立对上（赛事官网外卡公告 + 维基百科逐年列表），逐年份写在下面
`SLAMS` 里，谁要核对照着数就行。
"""

from __future__ import annotations

from .diagram_palette import FILL, INK, LIME, SOFT

#: 四个大满贯各自的夺冠年份。维基百科 Williams sisters 条目逐个列出，
#: 与赛事官网「14 Major titles」的总数对得上（4+2+6+2 = 14）。
SLAMS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("澳网", (2001, 2003, 2009, 2010)),
    ("法网", (1999, 2010)),
    ("温网", (2000, 2002, 2008, 2009, 2012, 2016)),
    ("美网", (1999, 2009)),
)

#: 奥运女双金牌。三届，全部是两人搭档拿的。
OLYMPICS: tuple[tuple[int, str], ...] = (
    (2000, "悉尼"),
    (2008, "北京"),
    (2012, "伦敦"),
)

_FIRST, _LAST = 1999, 2016


def _x(year: int, x0: float = 150.0, x1: float = 838.0) -> float:
    """年份 → 横坐标。时间轴是线性的，所以「中间空着好几年」看得出来。"""
    return x0 + (x1 - x0) * (year - _FIRST) / (_LAST - _FIRST)


def doubles_record() -> str:
    """一条 1999→2016 的时间轴，每个大满贯一行，夺冠那年点一个点。"""
    rows: list[str] = []
    y = 150.0
    for name, years in SLAMS:
        rows.append(
            f'<text x="52" y="{y + 9:.0f}" fill="{SOFT}" font-size="28" '
            f'font-weight="700">{name}</text>'
        )
        rows.append(
            f'<line x1="140" y1="{y:.0f}" x2="848" y2="{y:.0f}" '
            f'stroke="{FILL}" stroke-width="2" stroke-opacity=".35"/>'
        )
        for yr in years:
            rows.append(
                f'<circle cx="{_x(yr):.1f}" cy="{y:.0f}" r="11" fill="{LIME}"/>'
            )
        rows.append(
            f'<text x="866" y="{y + 9:.0f}" fill="{LIME}" font-size="28" '
            f'font-weight="800">{len(years)}</text>'
        )
        y += 62

    # 奥运单独一档：它不是大满贯，混进上面那四行会把「14」这个数说错。
    y += 16
    rows.append(
        f'<text x="52" y="{y + 9:.0f}" fill="{SOFT}" font-size="28" '
        f'font-weight="700">奥运</text>'
    )
    rows.append(
        f'<line x1="140" y1="{y:.0f}" x2="848" y2="{y:.0f}" '
        f'stroke="{FILL}" stroke-width="2" stroke-opacity=".35"/>'
    )
    for yr, city in OLYMPICS:
        rows.append(
            f'<circle cx="{_x(yr):.1f}" cy="{y:.0f}" r="11" fill="{INK}"/>'
        )
        rows.append(
            f'<text x="{_x(yr):.1f}" y="{y - 22:.0f}" fill="{SOFT}" '
            f'font-size="21" text-anchor="middle">{city}</text>'
        )
    rows.append(
        f'<text x="866" y="{y + 9:.0f}" fill="{INK}" font-size="28" '
        f'font-weight="800">3</text>'
    )

    axis_y = y + 54
    ticks: list[str] = []
    for yr in (1999, 2004, 2010, 2016):
        ticks.append(
            f'<text x="{_x(yr):.1f}" y="{axis_y + 26:.0f}" fill="{SOFT}" '
            f'font-size="24" text-anchor="middle">{yr}</text>'
        )
    body = "\n  ".join(rows + ticks)
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="52" y="52" fill="{INK}" font-size="38" font-weight="800">两个人一起，拿过这些</text>
  <text x="52" y="92" fill="{SOFT}" font-size="26">大满贯女双 14 冠 · 奥运女双 3 金 · 全部是这一对组合</text>
  {body}
  <line x1="140" y1="{axis_y:.0f}" x2="848" y2="{axis_y:.0f}"
   stroke="{SOFT}" stroke-width="2" stroke-opacity=".5"/>
</svg>
""".strip()
