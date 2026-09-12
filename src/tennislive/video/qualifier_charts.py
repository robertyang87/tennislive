"""「资格赛最远能打到哪儿」那条冷知识片的四张图。

这条选题**天生是一张表**：四大满贯 × 男女，每一格填「资格赛球员走到过哪一轮」。
任何一张球员实拍都只能讲其中一个格子，讲不了那八个格子摆在一起时的样子——
正是 CLAUDE.md 那条「示意图的触发条件是照片讲不清，不是照片找不到」。

## 口径：三件事必须钉死，混一件这张表就是假的

1. **公开赛年代（1968 起）**。资格赛这个赛制在那之前的口径和今天不是一回事，
   而所有能查到的官方表述（WTA、澳网官网、ATP）都以 Open Era 起算。
2. **「资格赛球员」＝ 打赢三场资格赛进正赛的人**，不含**幸运落败者**
   （lucky loser，资格赛输了、靠别人退赛递补进正赛的）——那是另一条通道，
   仓库里 `lucky-loser` 那条片子讲的就是它。两者混在一起这张表会多出好几格。
3. **单打**。双打的资格赛签表和轮次都不一样。

## 每一格的出处（逐条两个独立源，2026-08-30 核）

**男子——公开赛年代只有五个人从资格赛打进过大满贯半决赛，五个全部止步半决赛。**

    1977-12 澳网  吉尔蒂南     半决赛负洛依德
    1977    温网  麦肯罗       半决赛四盘负康纳斯
    1997    法网  德沃夫       半决赛负当年冠军库尔滕
    2000    温网  沃尔奇科夫   半决赛负当年冠军桑普拉斯
    2021    澳网  卡拉采夫     半决赛 3-6 4-6 2-6 负德约科维奇

来源：khelnow「Tennis players to reach men's singles Grand Slam semifinals after
coming through as qualifiers」（五人名单）、thesportingbase 同题（五人名单 ＋ 各自
的半决赛对手）、澳网官网 Karatsev 赛报（「the first male qualifier to reach a major
semifinal since Vladimir Voltchkov in the 2000 Wimbledon Championships, and the
first at the Australian Open since Bob Giltinan in **December 1977**」——⚠️ 1977 年
澳网打了两届，吉尔蒂南是 12 月那届，写「1977」不写月份是安全的，写成 1 月那届就错了）。

**男子美网那一格是空的**：从来没有过半决赛，三次 1/4 决赛封顶——
埃斯库德 1999、Gilles Müller 2008、范德赞德舒尔普 2021。来源：ABC News 与
tennis.com 的 2021 美网赛报（「just the third male qualifier to reach the
quarter-finals since the Open era began in 1968」，并点名前两个人）。
⚠️ **图上那一格只写年份、不点名**：Gilles Müller 的通行译法「米勒」在
`zh/players.py` 里已经归 Alexandre Muller 了，同一个账号不能把两个人叫一个名字。

**女子——六个人进过半决赛，两个进了决赛，其中一个夺冠。**

    1978 澳网  马蒂森           半决赛
    1999 温网  史蒂文森         半决赛
    2020 法网  波多罗斯卡       半决赛
    2021 美网  拉杜卡努         **冠军**（3 场资格赛 ＋ 7 场正赛，十场全胜，一盘未失）
    2024 澳网  亚斯特雷姆斯卡   半决赛负郑钦文
    2026 法网  赫瓦林斯卡       **亚军**（决赛 3-6 2-6 负安德列耶娃，用时 1 小时 22 分）

来源：khelnow 同题女子篇（前四人）、WTA 官网与澳网官网的 Yastremska 2024 赛报
（「the fifth qualifier overall (after Matison, Stevenson, Podoroska and
Raducanu) in the Open Era to reach a major semifinal」——这一句同时钉住了前五个人
和顺序）、吉尼斯世界纪录与 ESPN 的 Raducanu 词条（「first qualifier — male or
female — to win a Grand Slam title」）、WTA 官网
「Chwalinska breaks new ground as first qualifier to reach Roland Garros final」
与法网官网决赛页（比分 6-3 6-2、1 小时 22 分）。

⚠️ **决赛比分核过两遍**：olympics.com 写的是 6-3 6-3，而法网官网比赛页和 WTA
官网都是 **6-3 6-2**，取后者——两个独立源对得上，前者是单一来源。

**赛制**出自 **ITF 2026 大满贯规则书 L 节**原文（主源，不是转述）：

    All men's singles Main Draw matches in Grand Slam Tournaments shall be the
    best of five (5) sets. All other matches shall be the best of three (3) sets

也就是说**只有男子正赛是五盘三胜，其余全部（男子资格赛、女子资格赛、女子正赛）
都是三盘两胜**。资格赛 128 人打 3 轮出 16 个正赛名额，男女相同。

⚠️ **这条只摆事实，不下因果。** 「男子走不了那么远是因为要多打两盘」是一个
说得通的解释，但没有任何一个源这么说过，而 CLAUDE.md 明写着「战术或心理判断
都要能回到记分条、官方赛报、统计」。所以片子把两件事摆在一起，让读者自己想——
末屏那一问问的正是这个。
"""

from __future__ import annotations

from .diagram_palette import FILL, INK, LIME, SOFT

#: 四大满贯 × 男女的最好成绩。**格子里只写成绩，不写人名**——
#: 一格 190px 装不下「1978 马蒂森 · 2024 亚斯特雷姆斯卡」，硬塞就成了
#: CLAUDE.md 说的「用文字排成表格冒充图表」。人名留给 ③④ 两屏各自展开。
#:
#: 第四项是**亮度档**，决定这一格画多亮：3 冠军 / 2 决赛 / 1 半决赛 / 0 更浅。
#: 一眼看出来的那个梯度就是这条片子的全部内容。
BOARD: tuple[tuple[str, str, int, str, int], ...] = (
    # (赛事, 女子成绩, 女子亮度, 男子成绩, 男子亮度)
    ("澳网", "半决赛", 1, "半决赛", 1),
    ("法网", "决赛", 2, "半决赛", 1),
    ("温网", "半决赛", 1, "半决赛", 1),
    ("美网", "冠军", 3, "1/4 决赛", 0),
)

#: 男子那五个人，按时间排。**这张表就是「五十八年只有五个」这句话的全部依据**，
#: 所以每一行都带年份和赛事，读者可以逐条去查。
#:
#: ⚠️ **它现在没有渲染函数读它，是故意的。** 第一版把这五行画成了一张图——
#: 五行文字排成表格，正是账号所有者 2026-08-30 点名的「不要全是文字的卡片」
#: （CLAUDE.md 里 heat-rule 那条记过同一句话：「我需要更多是图片或视频，
#: 而不是文字卡片」）。那一屏现在换成了卡拉采夫在美网外场打资格赛的实拍，
#: 五个人的名单退回旁白和要点里。**表留着是因为它是事实的出处**，
#: 删了下一个人就得重查一遍。
MEN_SEMIS: tuple[tuple[str, str, str], ...] = (
    ("1977", "澳网", "吉尔蒂南"),
    ("1977", "温网", "麦肯罗"),
    ("1997", "法网", "德沃夫"),
    ("2000", "温网", "沃尔奇科夫"),
    ("2021", "澳网", "卡拉采夫"),
)

#: 男子在美网的三次 1/4 决赛。⚠️ 只写年份，不点名，理由见模块 docstring。
#: ⚠️ 和 `MEN_SEMIS` 一样，**现在没有渲染函数读它**——那张赛制对照图删掉了。
#: 留着是因为它是「美网那一格到今天还是空的」这句话的出处，不是忘了删的死代码。
MEN_USO_QF_YEARS = ("1999", "2008", "2021")

_TIER_FILL = {3: LIME, 2: "none", 1: FILL, 0: "none"}
_TIER_OPACITY = {3: 1.0, 2: 0.0, 1: 0.22, 0: 0.0}
_TIER_STROKE = {3: LIME, 2: LIME, 1: FILL, 0: SOFT}
_TIER_STROKE_W = {3: 0, 2: 3, 1: 0, 0: 1.5}
#: 冠军那一格是实心亮绿，字压在上面只能用卡片的底色，不能用 INK（浅压浅会没）。
_CHAMP_INK = "#0d2b1e"
_TIER_TEXT = {3: _CHAMP_INK, 2: LIME, 1: INK, 0: SOFT}


def qualifier_board() -> str:
    """核心图卡：四大满贯 × 男女，资格赛球员走到过哪一轮。

    ⚠️ **女子那一行排在上面，男子在下面**——这条片子的落点是「女子那边更高」，
    而读者是从上往下读的，把结论那一行放在第一眼扫到的位置。

    ⚠️ 亮度只有四档，而且**只由轮次决定**，不掺别的意思：亮＝走得远。
    一屏一个强调色那条照旧管用，LIME 就是那一个，FILL 只当底不当字。
    """
    x0, colw = 118, 188
    rows = (("女子", 1), ("男子", 3))
    top, cell_h, pitch = 168, 104, 132
    parts = [
        '<svg viewBox="0 0 900 640" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="46" text-anchor="middle" font-size="34" '
        f'font-weight="700" fill="{INK}">资格赛球员走到过哪一轮</text>',
        '<text x="450" y="84" text-anchor="middle" font-size="26" '
        f'fill="{SOFT}">公开赛年代 1968 年至今 · 四大满贯单打</text>',
    ]
    # 列头
    for i, (event, *_rest) in enumerate(BOARD):
        cx = x0 + i * colw + colw / 2
        parts.append(
            f'<text x="{cx:.0f}" y="{top - 22}" text-anchor="middle" '
            f'font-size="28" font-weight="700" fill="{SOFT}">{event}</text>'
        )
    for label, idx in rows:
        y = top + (0 if label == "女子" else pitch)
        parts.append(
            f'<text x="{x0 - 26}" y="{y + cell_h / 2 + 10:.0f}" text-anchor="end" '
            f'font-size="30" font-weight="700" fill="{INK}">{label}</text>'
        )
        for i, row in enumerate(BOARD):
            text, tier = row[idx], row[idx + 1]
            gx = x0 + i * colw + 6
            gw = colw - 12
            parts.append(
                f'<rect x="{gx}" y="{y}" width="{gw}" height="{cell_h}" rx="14" '
                f'fill="{_TIER_FILL[tier]}" fill-opacity="{_TIER_OPACITY[tier]}" '
                f'stroke="{_TIER_STROKE[tier]}" stroke-width="{_TIER_STROKE_W[tier]}"/>'
            )
            parts.append(
                f'<text x="{gx + gw / 2:.0f}" y="{y + cell_h / 2 + 12:.0f}" '
                f'text-anchor="middle" font-size="{34 if tier >= 2 else 30}" '
                f'font-weight="700" fill="{_TIER_TEXT[tier]}">{text}</text>'
            )
    parts.append(
        f'<text x="450" y="{top + pitch + cell_h + 62}" text-anchor="middle" '
        f'font-size="27" fill="{SOFT}">资格赛球员＝打赢三场资格赛进正赛的人，'
        "不含幸运落败者</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)




def ceiling_cover() -> str:
    """封面：把这条片子最硬的那一个对比摆出来，不放脸。

    ⚠️ **封面故意不用球员实拍。** 这条片子的答案是两个数摆在一起，而任何一张
    球员照片都会把它缩回到某一个人身上——读者读到的会是「这个人最远走到哪儿」，
    而那是另一个问题。和 `equal-pay` 的封面同一个理由。

    ⚠️ 两根条**按轮次画长度**（冠军 7 轮 / 半决赛 5 轮），不是随手定的比例。
    """
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="54" text-anchor="middle" font-size="30" '
        f'font-weight="700" fill="{SOFT}">从资格赛打进正赛，然后呢</text>',
    ]
    # ⚠️ 两组之间留 80px，不是 40。第一版渲出来女子那行的注脚和「男子」标签
    # 几乎贴在一起，读成了一坨；而图的下半是空的——挤的地方挤、空的地方空。
    rows = (
        (168, "女子", "冠军", 7, LIME, 0.95, _CHAMP_INK, "2021 美网 · 拉杜卡努"),
        (414, "男子", "半决赛", 5, FILL, 0.30, INK, "五十八年五个人，到此为止"),
    )
    for y, label, best, rounds, colour, opacity, ink, note in rows:
        w = 660 * rounds / 7
        parts.append(
            f'<text x="120" y="{y - 20}" font-size="30" font-weight="700" '
            f'fill="{INK}">{label}</text>'
        )
        parts.append(
            f'<rect x="120" y="{y}" width="{w:.0f}" height="106" rx="16" '
            f'fill="{colour}" fill-opacity="{opacity}"/>'
        )
        parts.append(
            f'<text x="{120 + w / 2:.0f}" y="{y + 70}" text-anchor="middle" '
            f'font-size="44" font-weight="700" fill="{ink}">{best}</text>'
        )
        parts.append(
            f'<text x="120" y="{y + 148}" font-size="26" fill="{SOFT}">{note}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
