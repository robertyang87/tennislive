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

from .diagram_palette import AMBER, FILL, INK, LIME, SOFT

# (名次, 中文名, 连续周数, 累计周数)。**这是「连续」榜，不是累计榜**——账号所有者
# 看完第一版（累计）说「要看连续的」。
#
# 前八行是每人**最长的那一段**。⚠️ 官方 p6 `MOST CONSECUTIVE WEEKS AT No.1` 只列
# 到 80 周（辛吉斯），斯瓦泰克那 75 周是从 p2 沿革表逐段算出来的——而**同一段代码
# 算出来的前七名和 p6 一字不差**（186/186/156/114/113/91/80），这就是它的判据。
# 排名去重之后：格拉芙和小威并列第 1。
#
# 末行古拉贡：她**一辈子只坐过一段**，所以连续和累计都是 2——放在连续榜上成立。
# ⚠️ 但**不许写成「连续最短」**：海宁、莎拉波娃、扬科维奇、萨芬娜都有过只坐 1 周
# 的一段。她是**累计最少**（官方 p5 榜尾，29 人里的第 29），那才是片子要讲的那个数。
CONSEC_AT_NO1: tuple[tuple[str, str, int, int], ...] = (
    ("第1", "格拉芙", 186, 377),
    ("第1", "小威廉姆斯", 186, 319),
    ("第3", "纳芙拉蒂洛娃", 156, 332),
    ("第4", "巴蒂", 114, 121),
    ("第5", "埃弗特", 113, 260),
    ("第6", "塞莱斯", 91, 178),
    ("第7", "辛吉斯", 80, 209),
    ("第8", "斯瓦泰克", 75, 125),
    ("—", "古拉贡", 2, 2),
)

NO1_TOTAL = 29  # 1975-11-03 设榜至今当过世界第一的人数（官方 p5）
GRAF_TOTAL = 377  # 格拉芙的累计周数，榜首；连续最长只有 186


def weeks_at_no1_chart() -> str:
    """**连续**在位周数榜。顶端 186 周和榜尾 2 周同框。

    ⚠️ 标题必须写「连续」，就像上一版必须写「累计」一样——「在世界第一待了多少周」
    两种读法都通，而这两张是**两张不同的榜**：累计榜格拉芙 377 独一档，
    连续榜她和小威并列 186。所以每一行的右边把累计那个数也印出来，
    让人一眼看见两者不是一回事（巴蒂 121 里有 114 周是连着的，
    而辛吉斯 209 周最长只连了 80 周）。

    ⚠️ **画了 9 个人，榜上是 29 个**，所以每行印名次、末尾写着略掉了谁。
    降序条形图天生看起来像一张完整排行榜——上一版就是这么静静丢掉 19 行的。

    ⚠️ 条长按**平方根**画，不按线性。线性的话 2 周那根只有 6 个像素，
    「最短的那个人」在图上几乎消失——而她正是这一屏要引出的人。
    ⚠️ 而这件事**要在图上说出来**（副标题里写着「条长按平方根」），
    不然就是一张骗人的图。
    """
    top, bar_h, pitch = 104, 32, 42
    x0, maxw = 300, 318
    hi = max(c for _, _, c, _ in CONSEC_AT_NO1) ** 0.5
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="42" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{INK}">连续在世界第一多少周</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="26" '
        f'fill="{SOFT}">WTA 官方 · 每人最长的那一段 · 设榜以来共 {NO1_TOTAL} 人 · '
        "条长按平方根</text>",
    ]
    for i, (rank, zh, consec, total) in enumerate(CONSEC_AT_NO1):
        y = top + i * pitch
        w = maxw * (consec**0.5) / hi
        last = zh == "古拉贡"
        colour = AMBER if last else FILL
        parts.append(
            f'<text x="{x0 - 124}" y="{y + 24}" text-anchor="end" font-size="26" '
            f'fill="{INK}">{zh}</text>'
        )
        parts.append(
            f'<text x="{x0 - 16}" y="{y + 24}" text-anchor="end" font-size="26" '
            f'fill="{SOFT}">{rank}</text>'
        )
        parts.append(
            f'<rect x="{x0}" y="{y}" width="{w:.1f}" height="{bar_h}" rx="5" '
            f'fill="{colour}" fill-opacity="{0.9 if last else 0.55}"/>'
        )
        parts.append(
            f'<text x="{x0 + w + 12:.1f}" y="{y + 24}" font-size="26" '
            f'font-weight="{700 if last else 400}" fill="{colour}">{consec} 周</text>'
        )
        parts.append(
            f'<text x="840" y="{y + 24}" text-anchor="end" font-size="26" '
            f'fill="{SOFT}">累计 {total}</text>'
        )
    note_y = top + (len(CONSEC_AT_NO1) - 1) * pitch + bar_h + 44
    parts.append(
        f'<text x="450" y="{note_y}" text-anchor="middle" font-size="26" '
        f'fill="{SOFT}">榜上另外 {NO1_TOTAL - len(CONSEC_AT_NO1)} 人没画；'
        "古拉贡一辈子只坐过这一段，累计也是 2 周</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


# 差距能小到什么程度。三行**各是各的口径**，见模块 docstring 那条警告。
#
# ⚠️ 第一行改过三次，第三次是把第二次的判断**推翻**——记全，因为错的是我的推理。
#
# ① 「4 分」→ 撤（理由：假设句，且和 WTA 官方 08-14 说的「54 分」硬矛盾）
# ② 「54 分」→ 撤（账号所有者：「不止差 54 分吧，如果夺冠才多得 50 分这不符合逻辑啊」。
#    对的：WTA1000 冠亚军差 350 分，54 和 4 不可能同时成立）
# ③ **改回「4 分」**——账号所有者：「可以说如果他夺冠就差 4 分」。**他两次都是对的，
#    而我把错归到了「4」头上。** 真正站不住的是 WTA 那句 54。判据是这两个数自己：
#
#      输掉决赛（实际）  官方排名 莱巴金娜 8316 / 萨巴伦卡 8670   差 354
#      赢下冠军（当时的赌注） 莱巴金娜 8666 / 萨巴伦卡 8670        差   4
#      8666 − 8316 = 350 = WTA1000 冠亚军分差   ← **两个数正好差一个冠亚军，自洽**
#
#    8666 / 4 分这一对有两个独立出处：cincinnatiopen.com 的签表前瞻
#    （「Should she win the trophy in Canada, Rybakina would trail Sabalenka by a
#    razor-thin four PIF WTA Ranking points」）和 Yardbarker 的赛前稿；而
#    8670 是官方排名接口现在就查得到的数。
#
# ⚠️ **它是「当时的赌注」，不是凭空推演。** 账号所有者 2026-08-03 禁的假设句，禁的是
#    「造一个不存在的人再把四条规则套上去」；「赢下这场就能追到几分」是体育报道的
#    常规写法，两边的数都是公开发布过的。这条是账号所有者点名要的写法。
MARGINS: tuple[tuple[str, str, str], ...] = (
    ("4 分", "2026 · 莱巴金娜", "就算赢下多伦多冠军，也还差 4 分"),
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
        f'font-weight="700" fill="{INK}">那两周，三十一年后才追认</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="26" '
        f'fill="{SOFT}">WTA 官方 · 1976 年 4 到 7 月的几张成绩单没录进电脑</text>',
        # ⚠️ 线分两段，中间留给那句「31 年」。别画整条再把字压上去——示意图
        # 落在卡片上时背景不是纯色，拿一块底色去盖会露出一个方块。
        f'<line x1="{x0}" y1="{y}" x2="300" y2="{y}" stroke="{FILL}" '
        'stroke-width="4" stroke-opacity="0.45"/>',
        f'<line x1="600" y1="{y}" x2="{x1}" y2="{y}" stroke="{FILL}" '
        'stroke-width="4" stroke-opacity="0.45"/>',
        f'<circle cx="{x0}" cy="{y}" r="14" fill="{FILL}"/>',
        f'<circle cx="{x1}" cy="{y}" r="14" fill="{AMBER}"/>',
        f'<text x="{x0}" y="{y - 40}" text-anchor="middle" font-size="26" '
        f'fill="{INK}">1976.4.26</text>',
        f'<text x="{x0}" y="{y + 52}" text-anchor="middle" font-size="26" '
        f'fill="{FILL}">登顶，两周</text>',
        f'<text x="{x1}" y="{y - 40}" text-anchor="middle" font-size="26" '
        f'fill="{INK}">2007.12.27</text>',
        f'<text x="{x1}" y="{y + 52}" text-anchor="middle" font-size="26" '
        f'fill="{AMBER}">她才收到通知</text>',
        f'<text x="450" y="{y + 13}" text-anchor="middle" '
        f'font-size="38" font-weight="700" fill="{AMBER}">中间隔了 31 年</text>',
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
            f'fill="{FILL}" fill-opacity="0.08"/>'
        )
        parts.append(
            f'<text x="{x0 + 34}" y="{ry + 35}" font-size="26" '
            f'fill="{SOFT}">{when}</text>'
        )
        parts.append(
            f'<text x="{x0 + 190}" y="{ry + 35}" font-size="26" '
            f'fill="{INK}">{what}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def margin_ladder() -> str:
    """4 分 → 0.8 分 → 0 分。最后一行是并列，所以描边和垫底都换成强调色。

    ⚠️ 三行**不是一张排行榜**，是同一件事的三个样子——两条巡回赛都没有
    「历史最小分差」这项官方纪录，副标题「三种计分口径，各讲各的」就是
    为了不让人把它读成榜。第一行为什么不是那个「4 分」，见常量上面那段。
    """
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{INK}">差距能小到什么程度</text>',
        '<text x="450" y="72" text-anchor="middle" font-size="26" '
        f'fill="{SOFT}">三种计分口径，各讲各的</text>',
    ]
    for i, (num, who, note) in enumerate(MARGINS):
        y = 110 + i * 130
        zero = num.startswith("0 ")
        colour = AMBER if zero else FILL
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
            f'<text x="290" y="{y + 42}" font-size="26" fill="{INK}">{who}</text>'
        )
        parts.append(
            f'<text x="290" y="{y + 78}" font-size="26" fill="{SOFT}">{note}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
