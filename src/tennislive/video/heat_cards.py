"""「28 度也能叫极端高温」那条片子的四张示意图。

条文出自 **ATP 2026 年版规则书**（`2026-rulebook_19dec25.pdf`，210 页，
2026-08-17 下载后逐条核对）第 VII 章 `O. Heat Policy`——**这一节 2026 年才有**，
是上一季之后新写进去的。

⚠️ **`WBGT` / `Heat Policy` / `Cooling Break` / `Extreme Heat` 四个词在全书只出现
在同一页上**（PDF 第 106 页 ＝ 印刷第 210/211 页；数过，别的页一次都没有），
另有第 192 页一句交叉引用「关顶因高温的，见 ATP Heat Policy」。也就是说这条
规则在书里是**孤零零一节**，没有散落在别处的补充——片子把那一节讲完就是讲完了。

⚠️ **规则书自己不给 WBGT 的算法**，只写「the composite metric used to assess heat
stress. WBGT readings are taken or confirmed on-court by ATP Sport Science &
Medical」。所以七二一那张图的权重**不是从规则书来的**，出处是 ISO 7243:2017 的
户外公式 `WBGT = 0.7·Tnwb + 0.2·Tg + 0.1·Ta`。两个出处不能混着说成一个。

⚠️ **这条片子不给德约下诊断。** 他赛后说的是「一个跟了我好多年的健康问题，
湿度和高温大的时候特别麻烦」，**没有说是什么病**，也没有人宣布他中暑。所以
片子只写他说过的话和场上发生的事（18 分钟九次平分的保发、医疗暂停、理疗师和
队医、冰毛巾），**一个诊断词都不写**——和 `rulebook_cards` 那条「只引条文，
不给人定性」是同一条规矩，只不过那次要克制的是「他在使坏」，这次是「他中暑了」。

⚠️ **那天的四个气象读数不是 WBGT。** WBGT 由 ATP 在场地上量、不公开，我们手上
没有那个数。这四个是 Open-Meteo 历史存档在梅森（Mason, OH，39.36N/-84.27E）
当地 15:00 的记录，也就是**WBGT 的原料，不是 WBGT 本身**。图上因此只说
「那天下午」，一个字都不声称越过那条线没有。
"""

from __future__ import annotations

from .diagram_palette import AMBER, FILL, INK, LIME, SOFT

# 和 `rulebook_cards` 同一个地板：再往下会被卡片上那颗序号药丸压住。
#
# ⚠️ **它是上限，而且最后一屏的上限更低。** 卡片的文案块是从底往上排的，
# 所以**块越高，那颗药丸越往上顶**——而最后一屏比别的屏多一行「末屏那一问」，
# 于是药丸整个抬高一截。量出来（`where_it_came_from` 第一版，675×900 的本地渲染）：
#
#     非末屏  药丸上沿 ≈ SVG y 512   → 底部那行写 `INK_BOTTOM - 4`（496）没问题
#     末屏    药丸上沿 ≈ SVG y 490   → 496 那行的**左边三个字被药丸盖掉**
#
# 药丸横向占到 SVG x≈330，所以居中的长句（14 个字 ≈ 420px，从 x=240 起）正好
# 探进它的地盘。`rulebook_cards.two_violations`（那条片子的末屏）早就写着
# `INK_BOTTOM - 28`，注释里也记了同一件事——**这里是第二次撞上，所以把数写下来**。
INK_BOTTOM = 500

#: 末屏专用的地板。末屏多一行「末屏那一问」，文案块更高，药丸更靠上。
INK_BOTTOM_LAST = INK_BOTTOM - 28

_FG = INK        # 正文，和卡片 `.point` 同色
_DIM = SOFT      # 次级说明
_ACC = LIME      # **文字**上的强调色，和卡片 `.point i` 同色
_FILL = FILL     # 大面积的条和框
_GOLD = AMBER    # 第二类（停赛 / 例外）


def _head(title: str, subtitle: str) -> list[str]:
    return [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        f'<text x="450" y="44" text-anchor="middle" font-size="36" '
        f'font-weight="700" fill="{_FG}">{title}</text>',
        f'<text x="450" y="80" text-anchor="middle" font-size="26" '
        f'fill="{_DIM}">{subtitle}</text>',
    ]


# 2026-08-15 当地 15:00，梅森（辛辛那提赛场所在地）。德约那场 14:15 开打，
# 第二盘那个 18 分钟的发球局大致落在这一小时里。
# 出处：Open-Meteo 历史存档 API（`archive-api.open-meteo.com/v1/archive`）。
# ⚠️ 顺序是**故意**的：气温排第一，因为它是这一屏要拆穿的那个数。
THAT_AFTERNOON: tuple[tuple[str, str, str], ...] = (
    ("气温", "28.6", "°C"),
    ("湿度", "76", "%"),
    ("风速", "1.3", "km/h"),
    ("日照", "491", "W/m²"),
)


def that_afternoon() -> str:
    """那天下午场上的四个读数——气温单独摆左边，因为它是被拆穿的那个。

    ⚠️ 这一屏**不画 WBGT 的值**。那个数由 ATP 在场地上量、不公开，我们没有；
    画一个算出来的数上去，就是把推断印成事实。这一屏只说「原料是这四样」。
    """
    parts = _head("德约倒下那天，场上四个数", "2026-08-15 当地 15:00 · Open-Meteo 历史存档")

    # 左边：气温，大字、但用**次级色**——它是这一屏要说「别只看它」的那个数。
    parts.append(
        f'<rect x="52" y="120" width="330" height="230" rx="14" '
        f'fill="{_DIM}" fill-opacity="0.10" stroke="{_DIM}" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="217" y="168" text-anchor="middle" font-size="28" '
        f'fill="{_DIM}">气温</text>'
    )
    parts.append(
        f'<text x="217" y="256" text-anchor="middle" font-size="76" '
        f'font-weight="700" fill="{_DIM}">28.6</text>'
    )
    parts.append(
        f'<text x="217" y="300" text-anchor="middle" font-size="30" '
        f'fill="{_DIM}">摄氏度</text>'
    )
    parts.append(
        f'<text x="217" y="336" text-anchor="middle" font-size="26" '
        f'fill="{_DIM}">听起来不吓人</text>'
    )

    # 右边：另外三个，竖排，用强调色——它们才是这一屏的主语。
    for i, (label, value, unit) in enumerate(THAT_AFTERNOON[1:]):
        y = 120 + i * 78
        parts.append(
            f'<rect x="410" y="{y}" width="438" height="66" rx="10" '
            f'fill="{_FILL}" fill-opacity="0.12" stroke="{_FILL}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="436" y="{y + 44}" font-size="28" fill="{_FG}">{label}</text>'
        )
        parts.append(
            f'<text x="822" y="{y + 44}" text-anchor="end" font-size="34" '
            f'font-weight="700" fill="{_ACC}">{value} {unit}</text>'
        )

    # ⚠️ 这一行和底下那句**故意隔开 60px 以上**：它们是两件事（一句描述、
    # 一句结论）。第一版排在 404，和 496 之间空出 92px 的洞，读起来像漏了一行。
    parts.append(
        f'<text x="450" y="432" text-anchor="middle" font-size="30" '
        f'fill="{_FG}">湿度七成半，风几乎没有，太阳还在头顶</text>'
    )
    parts.append(
        f'<text x="450" y="{INK_BOTTOM - 4}" text-anchor="middle" font-size="30" '
        f'fill="{_FG}">要不要停赛，看的不是第一个数</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# ISO 7243:2017 的户外公式：WBGT = 0.7·自然湿球 + 0.2·黑球 + 0.1·干球。
# ⚠️ 这三份权重**不出自 ATP 规则书**——规则书只说 WBGT 是「composite metric」，
# 一个系数都没给。混着说会让人以为 ATP 自己定了这个配方。
RECIPE: tuple[tuple[str, int, str], ...] = (
    ("湿球", 70, "湿度：汗蒸不蒸得出去"),
    ("黑球", 20, "日照：太阳晒在身上"),
    ("干球", 10, "气温：温度计上那个数"),
)


def wbgt_recipe() -> str:
    """七二一——这张图就是整条片子的落点，也是封面。

    ⚠️ **条上不写字**（CLAUDE.md「条形图上不要写字」）：百分比写在条的上一行，
    说明写在下一行。第一版把 `70%` 压在条子里，和条的边界互相削。
    """
    parts = _head("WBGT 是怎么合出来的", "ISO 7243:2017 户外公式 · 三份权重")

    x0, total_w, top, bar_h = 60, 780, 168, 76
    x = x0
    for label, pct, why in RECIPE:
        w = total_w * pct / 100
        # 湿球那一份用强调色，另外两份用底色——一屏只留一个强调色。
        colour = _ACC if pct == 70 else _FILL
        parts.append(
            f'<rect x="{x:.0f}" y="{top}" width="{w - 6:.0f}" height="{bar_h}" '
            f'rx="8" fill="{colour}" fill-opacity="{0.55 if pct == 70 else 0.28}" '
            f'stroke="{colour}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + (w - 6) / 2:.0f}" y="{top - 16}" text-anchor="middle" '
            f'font-size="34" font-weight="700" fill="{colour}">{pct}%</text>'
        )
        parts.append(
            f'<text x="{x + (w - 6) / 2:.0f}" y="{top + bar_h + 36}" '
            f'text-anchor="middle" font-size="28" fill="{_FG}">{label}</text>'
        )
        x += w

    # 三行说明摆在条子底下，一行一个——挤在条上会撞（干球那一份只有 78px 宽）。
    for i, (label, pct, why) in enumerate(RECIPE):
        y = 318 + i * 46
        parts.append(
            f'<text x="112" y="{y}" text-anchor="end" font-size="27" '
            f'fill="{_DIM}">{label}</text>'
        )
        parts.append(
            f'<text x="132" y="{y}" font-size="27" fill="{_FG}">{why}</text>'
        )

    parts.append(
        f'<text x="450" y="{INK_BOTTOM - 4}" text-anchor="middle" font-size="32" '
        f'fill="{_ACC}">气温只占一成</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# `O. Heat Policy` 的四档与两条动作线，原文见规则书印刷第 210/211 页。
# （档位, 门槛文字, 会发生什么, 是不是"停"那一档）
LADDER: tuple[tuple[str, str, str, bool], ...] = (
    ("Extreme Heat 2", "32.2 以上", "持续 15 分钟 → 监督暂停所有室外场", True),
    ("Extreme Heat 1", "30.1 以上", "任一方可申请 10 分钟降温休息", False),
    ("Heat Advisory", "29.0 ~ 30.0", "高温提示", False),
    ("Normal", "29.0 以下", "照常打", False),
)


def heat_ladder() -> str:
    """四档门槛，从高到低——高的排上面，和「热」的方向一致。

    ⚠️ 复赛那条线（降到 30.5 以下**持续 20 分钟**）单独写在底下：它不是第五档，
    是「停了之后怎么回来」，混进阶梯里会被读成又一个门槛。
    """
    parts = _head("三条线，画在 WBGT 上", "ATP 2026 规则书 · Heat Policy（今年新增）")
    for i, (name, threshold, what, is_stop) in enumerate(LADDER):
        y = 112 + i * 82
        colour = _GOLD if is_stop else _FILL
        parts.append(
            f'<rect x="52" y="{y}" width="796" height="72" rx="10" '
            f'fill="{colour}" fill-opacity="{0.20 if is_stop else 0.12}" '
            f'stroke="{colour}" stroke-width="{3 if is_stop else 1}"/>'
        )
        parts.append(
            f'<text x="76" y="{y + 30}" font-size="26" fill="{_DIM}">{name}</text>'
        )
        parts.append(
            f'<text x="76" y="{y + 62}" font-size="32" font-weight="700" '
            f'fill="{colour}">{threshold}</text>'
        )
        parts.append(
            f'<text x="824" y="{y + 48}" text-anchor="end" font-size="27" '
            f'fill="{_FG}">{what}</text>'
        )
    # ⚠️ 排 452 不排 464：底下那句是 30px，两行只隔 32px 时几乎贴在一起，
    # 渲出来像同一段的两行，而它们是「怎么回来」和「谁没有」两件事。
    parts.append(
        f'<text x="450" y="452" text-anchor="middle" font-size="27" '
        f'fill="{_DIM}">停了之后要降到 30.5 以下、持续 20 分钟才复赛</text>'
    )
    parts.append(
        f'<text x="450" y="{INK_BOTTOM - 4}" text-anchor="middle" font-size="30" '
        f'fill="{_FG}">双打没有那十分钟</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


# 2025 年 10 月上海：气温三十出头、湿度超过八成。鲁内在第三轮对安贝尔的
# 医疗暂停里问主裁那一句，主裁的回答同样有据可查（多家赛报一致）。
SHANGHAI_LINES: tuple[tuple[str, str], ...] = (
    ("鲁内", "你们是想让球员死在场上吗？"),
    ("主裁", "我不知道，但这是个很好的问题。"),
)


def where_it_came_from() -> str:
    """这条规则的来路：2025 年 10 月上海的那一问。

    ⚠️ 这一屏是全片唯一带情绪的一屏，所以**只放两句原话，不加任何转述**。
    引号里的每个字都能在赛报里找到出处；引号外面只有时间地点和两个环境读数。
    """
    parts = _head("这条规则是怎么来的", "2025 年 10 月 · 上海大师赛")

    # 上：当时的条件，两个数并排
    for i, (label, value) in enumerate((("气温", "30 度出头"), ("湿度", "超过 80%"))):
        x = 60 + i * 400
        parts.append(
            f'<rect x="{x}" y="108" width="380" height="72" rx="10" '
            f'fill="{_FILL}" fill-opacity="0.12" stroke="{_FILL}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x + 24}" y="152" font-size="28" fill="{_DIM}">{label}</text>'
        )
        parts.append(
            f'<text x="{x + 356}" y="152" text-anchor="end" font-size="32" '
            f'font-weight="700" fill="{_ACC}">{value}</text>'
        )

    # 中：两句原话，各占一整行
    for i, (who, line) in enumerate(SHANGHAI_LINES):
        y = 216 + i * 96
        parts.append(
            f'<text x="60" y="{y + 34}" font-size="27" fill="{_DIM}">{who}</text>'
        )
        parts.append(
            f'<text x="60" y="{y + 76}" font-size="30" fill="{_FG}">「{line}」</text>'
        )
    # ⚠️ **这一屏是末屏，用 `INK_BOTTOM_LAST` 不是 `INK_BOTTOM`。** 见文件顶上
    # 那段：末屏的药丸比别的屏高一截，写在 496 上左边三个字会被它盖掉。
    parts.append(
        f'<text x="450" y="{INK_BOTTOM_LAST}" text-anchor="middle" font-size="30" '
        f'fill="{_FG}">一年之后，这一节写进了规则书</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)
