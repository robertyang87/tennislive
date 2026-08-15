"""世界第一那条片子的图表——在位周数榜，和「差距能小到什么程度」的阶梯。

数据全部出自 **WTA 官方 2026 年版 Record Book**（`WTAMG26_WTARecordBook.pdf`，
2026-08-15 下载核对）：**p5** `SINGLES: WEEKS AT No.1`（累计周数榜）、
**p2** `NO.1 SINGLES RANKING HISTORY (since November 3, 1975)`（逐段沿革）、
**p6** `MOST CONSECUTIVE WEEKS AT No.1`（连续榜，和 p5 是两张榜）。
⚠️ 页码是 `pypdf` 数出来的（`reader.pages[4]` 即第 5 页），不是照着 PDF 上
印的页眉抄的——那份 PDF 的页眉从 `- 3 -` 开始，两套编号差两页。

⚠️ **周数榜只画 8 个人，而官方榜是 29 个人**——省掉的那一段要在图上写出来，
见 `weeks_at_no1_chart()` 的第二条警告。

⚠️ **不要按「译名表里有没有」去筛这张榜**。第一版就是这么筛的，还在注释里
写着「只有穆古鲁扎、普利斯科娃、特蕾西·奥斯汀、达文波特四个不在表里」——
**那句话是编的**。真拿 `player_zh()` 跑一遍：不在表里的是九个（巴蒂、达文
波特、毛瑞斯莫、萨芬娜、奥斯汀、扬科维奇、卡普里亚蒂、桑切斯·维卡里奥、
穆古鲁扎），而普利斯科娃**在**表里。按那个假名单筛出来的图静静丢掉了 19 行，
其中海宁、沃兹尼亚奇、哈勒普、阿扎伦卡、大坂直美、莎拉波娃……全都在表里，
**一个理由都没有就没了**——而降序条形图看起来就是一张完整排行榜，
读者会以为斯瓦泰克后面紧接着就是萨巴伦卡（真实是中间还隔着四个人）。
判据：注释里的名单**要跑一遍再写**，别凭印象。

⚠️ 「0.8 分」和「4 分」**不是同一把尺子**：1976 年是平均分制，今天是 52 周
滚动累计；而「并列」是当年 WTA 的一次安排，不是算出来的 0 分。所以阶梯那张
图讲的是**「差距能小到什么程度」**，不是「历史最小差距排行榜」——后者会把
三种不同的计分口径并排成一张假榜，正是账号所有者说的「本来是科普却成了浆糊」。
"""

from __future__ import annotations

# (名次, 中文名, 周数)。官方 p5 `SINGLES: WEEKS AT No.1` 原样，**连着的前七名
# ＋ 榜尾那一个**。中间第 8~28 名不画，但要在图上说清楚略掉了谁（见下）。
WEEKS_AT_NO1: tuple[tuple[int, str, int], ...] = (
    (1, "格拉芙", 377),
    (2, "纳芙拉蒂洛娃", 332),
    (3, "小威廉姆斯", 319),
    (4, "埃弗特", 260),
    (5, "辛吉斯", 209),
    (6, "塞莱斯", 178),
    (7, "斯瓦泰克", 125),
    (29, "古拉贡", 2),
)

# 官方榜的总人数和被略掉的那一段，印在图上。写死是因为它就是那份 PDF 的事实；
# 改数据要连这三个数一起改，判据在 tests 里（总数 = 画出来的 + 略掉的）。
NO1_TOTAL = 29  # 1975-11-03 设榜至今当过世界第一的人数
SKIPPED_RANGE = (121, 4)  # 第 8 名巴蒂 121 周 ~ 第 28 名穆古鲁扎 4 周


def weeks_at_no1_chart() -> str:
    """**累计**在位周数榜。顶端 377 周和榜尾 2 周同框——差 188 倍。

    ⚠️ 是**累计**不是连续，标题里必须写出来。账号所有者一眼问「你这是连续
    多少周的排序啊」——而原标题「在世界第一待了多少周」两种读法都通。
    拿官方 p1 沿革表自证过：格拉芙先后九段（186+1+3+87+1+5+9+2+18＝312）
    加上与塞莱斯并列的两段（64+1＝65），312+65 正好是 377。
    她**最长的一段只有 186 周**——连续榜是另一张榜（小威和格拉芙并列 186、
    纳芙拉蒂洛娃 156、巴蒂 114），两张别混。

    ⚠️ **画了 8 个人，榜上是 29 个**，所以每一行都印着名次、末尾还写着
    「第 8 ~ 第 28 名没画」。降序条形图**天生看起来像一张完整排行榜**——
    第一版就是这么静静丢掉 19 行的，读者会以为斯瓦泰克后面紧接着萨巴伦卡。
    「摆了 7 格」和「总共就 7 格」长得一样，一次不出声的截断读起来就是
    「全看过了」。

    ⚠️ 条长按**平方根**画，不按线性。线性的话 2 周那根只有 3 个像素，
    「最短的那个人」在图上直接消失——而她正是这一屏要讲的人。开方之后
    2 周仍然明显最短（约为 377 那根的 7%），但看得见。
    ⚠️ 而这件事**要在图上说出来**（副标题里写着「条长按平方根」），
    不然就是一张骗人的图。
    """
    top, bar_h, gap = 100, 34, 11
    x0, maxw = 280, 520
    hi = max(w for _, _, w in WEEKS_AT_NO1) ** 0.5
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="42" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">累计在世界第一多少周</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="21" '
        f'fill="#a9bcb2">WTA 官方 · 累计非连续 · 设榜以来共 {NO1_TOTAL} 人 · '
        "条长按平方根，否则最短那根看不见</text>",
    ]
    for i, (rank, zh, wk) in enumerate(WEEKS_AT_NO1):
        y = top + i * (bar_h + gap)
        w = maxw * (wk**0.5) / hi
        last = rank == NO1_TOTAL
        colour = "#e0b13a" if last else "#8fd6a8"
        parts.append(
            f'<text x="{x0 - 74}" y="{y + 25}" text-anchor="end" font-size="26" '
            f'fill="#e7f3ec">{zh}</text>'
        )
        parts.append(
            f'<text x="{x0 - 16}" y="{y + 25}" text-anchor="end" font-size="21" '
            f'fill="#a9bcb2">第{rank}</text>'
        )
        parts.append(
            f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="5" '
            f'fill="{colour}" fill-opacity="{0.9 if last else 0.55}"/>'
        )
        parts.append(
            f'<text x="{x0 + w + 12:.1f}" y="{y + 25}" font-size="26" '
            f'font-weight="{700 if last else 400}" fill="{colour}">{wk} 周</text>'
        )
    gap_y = top + (len(WEEKS_AT_NO1) - 1) * (bar_h + gap) + bar_h + 46
    hi_wk, lo_wk = SKIPPED_RANGE
    parts.append(
        f'<text x="450" y="{gap_y}" text-anchor="middle" font-size="26" '
        f'fill="#a9bcb2">第 8 ~ 第 28 名这 {NO1_TOTAL - len(WEEKS_AT_NO1)} 人没画，'
        f"她们在 {lo_wk} ~ {hi_wk} 周之间</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


# 差距能小到什么程度。三行**各是各的口径**，见模块 docstring 那条警告。
#
# ⚠️ 第一行原来写的是「4 分 / 赢下多伦多冠军也还差 4 分」，**撤掉了，两个理由**：
#
# 1. **它是假设句。** 账号所有者 2026-08-03：「不要用写这些假设，普通人看不懂，
#    就用实际举例。」她没赢那场决赛，"要是赢了会怎样"就是要读者先在脑子里造一个
#    没发生过的世界。
# 2. **它和真实数字对不上，而且是硬矛盾。** 那个 4 出自 cincinnatiopen.com
#    的签表前瞻（8-12，决赛之前的推演）；WTA 官方 8-14 的 Rankings Watch 写的是
#    「Rybakina's run to her fourth final of the season narrowed the gap to just
#    **54 points**」。而 WTA1000 冠军 1000 分、亚军 650 分——**赢和输差 350 分**，
#    所以「输了差 54、赢了差 4」不可能同时成立（赢了应该是反超 296）。
#    两个源报两个数就去查哪个新、哪个是实测：官方的、决赛之后的、非推演的那个说了算。
#
# 三行现在全是**真发生过的事**：54 分是已经出的排名差，0.8 分和 0 分是历史记录。
MARGINS: tuple[tuple[str, str, str], ...] = (
    ("54 分", "2026 · 莱巴金娜", "输掉多伦多决赛，离世界第一 54 分"),
    ("0.8 分", "1976 · 古拉贡", "这 0.8 分真的把她送上了世界第一"),
    ("0 分", "1995 · 格拉芙和塞莱斯", "并列世界第一，整整 64 周"),
)


def goolagong_gap() -> str:
    """一九七六到二零零七：那两周，三十一年之后才追认。

    ⚠️ **两个端点是圆点，不是一根按比例画的条。** 三十一年是一千六百多周，
    那两周按比例只有零点九个像素——画出来等于没有，而**看起来又像画过了**。
    「差距能小到什么程度」那张图敢开方是因为副标题写着开了方；这一张没有
    诚实的比例可用，所以干脆不声称比例。

    ⚠️ 这一屏是**示意图而不是照片**，理由是仓库里那条硬判据：
    「他/她**没打**（缺席、放弃、等待）——这是示意图的触发条件」。
    她那三十一年不在球场上，一张她打球的照片会把这一屏说反。
    """
    x0, x1, y = 148, 752, 222
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="42" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">那两周，三十一年后才追认</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="21" '
        'fill="#a9bcb2">WTA 官方 · 1976 年 4 到 7 月的几张成绩单没录进电脑</text>',
        # ⚠️ 线分两段，中间留给那句「31 年」。别画整条再把字压上去——示意图
        # 落在卡片上时背景不是纯色，拿一块底色去盖会露出一个方块。
        f'<line x1="{x0}" y1="{y}" x2="300" y2="{y}" stroke="#8fd6a8" '
        'stroke-width="4" stroke-opacity="0.45"/>',
        f'<line x1="600" y1="{y}" x2="{x1}" y2="{y}" stroke="#8fd6a8" '
        'stroke-width="4" stroke-opacity="0.45"/>',
        f'<circle cx="{x0}" cy="{y}" r="14" fill="#8fd6a8"/>',
        f'<circle cx="{x1}" cy="{y}" r="14" fill="#e0b13a"/>',
        f'<text x="{x0}" y="{y - 40}" text-anchor="middle" font-size="26" '
        'fill="#e7f3ec">1976.4.26</text>',
        f'<text x="{x0}" y="{y + 52}" text-anchor="middle" font-size="26" '
        'fill="#8fd6a8">登顶，两周</text>',
        f'<text x="{x1}" y="{y - 40}" text-anchor="middle" font-size="26" '
        'fill="#e7f3ec">2007.12.27</text>',
        f'<text x="{x1}" y="{y + 52}" text-anchor="middle" font-size="26" '
        'fill="#e0b13a">她才收到通知</text>',
        f'<text x="450" y="{y + 13}" text-anchor="middle" '
        'font-size="38" font-weight="700" fill="#e0b13a">中间隔了 31 年</text>',
    ]
    steps = (
        ("1976", "成绩单漏录进电脑"),
        ("2007", "档案室翻出那几张纸"),
        ("12.27", "一通电话，她才知道"),
    )
    for i, (when, what) in enumerate(steps):
        ry = 306 + i * 60
        parts.append(
            f'<rect x="{x0}" y="{ry}" width="{x1 - x0}" height="48" rx="9" '
            'fill="#8fd6a8" fill-opacity="0.08"/>'
        )
        parts.append(
            f'<text x="{x0 + 34}" y="{ry + 35}" font-size="26" '
            f'fill="#a9bcb2">{when}</text>'
        )
        parts.append(
            f'<text x="{x0 + 190}" y="{ry + 35}" font-size="26" '
            f'fill="#e7f3ec">{what}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def margin_ladder() -> str:
    """54 分 → 0.8 分 → 0 分。最后一行是并列，所以描边和垫底都换成强调色。

    ⚠️ 三行**不是一张排行榜**，是同一件事的三个样子——两条巡回赛都没有
    「历史最小分差」这项官方纪录，副标题「三种计分口径，各讲各的」就是
    为了不让人把它读成榜。第一行为什么不是那个「4 分」，见常量上面那段。
    """
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">差距能小到什么程度</text>',
        '<text x="450" y="72" text-anchor="middle" font-size="21" '
        'fill="#a9bcb2">三种计分口径，各讲各的</text>',
    ]
    for i, (num, who, note) in enumerate(MARGINS):
        y = 110 + i * 130
        zero = num.startswith("0 ")
        colour = "#e0b13a" if zero else "#8fd6a8"
        parts.append(
            f'<rect x="60" y="{y}" width="780" height="104" rx="10" '
            f'fill="{colour}" fill-opacity="{0.20 if zero else 0.08}" '
            f'stroke="{colour}" stroke-width="{3 if zero else 1}"/>'
        )
        parts.append(
            f'<text x="104" y="{y + 58}" font-size="46" font-weight="700" '
            f'fill="{colour}">{num}</text>'
        )
        parts.append(
            f'<text x="290" y="{y + 42}" font-size="26" fill="#e7f3ec">{who}</text>'
        )
        parts.append(
            f'<text x="290" y="{y + 78}" font-size="21" fill="#a9bcb2">{note}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
