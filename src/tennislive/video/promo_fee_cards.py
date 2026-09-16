"""「请得动球星的那条规则」那条解说片的示意图。

这条片子讲的是 ATP 规则书里一条**分级**规矩：谁可以花钱请球员来，谁不许。
分级、罚款阶梯、执法权限——**照片没有语法去表达这几样**，所以画
（CLAUDE.md「示意图的触发条件是照片讲不清，不是照片找不到」）。

⚠️ 条文和罚则的**一手出处**在 `research/promotional-fees-2026.md`：
2026 版第一章 **1.16 Promotional Fees**（2024 版是 1.15，节号变了是因为
2026 在前面插了一节 Special Events）。两版正文逐字比过，**828 字符对 828
字符，一个字没改**——这儿画的每个数都从那份 PDF 抠的，不是从摘要抄的。

⚠️ 配色一律从 `diagram_palette` 来，不在这儿另调。
"""

from __future__ import annotations

from .diagram_palette import AMBER, FILL, INK, LIME, SOFT

#: 正文那几张图里最低的那点墨不许超过这个 y——再往下会被卡片上那颗序号药丸
#: 压住。抄 `serve_clock_cards.INK_BOTTOM` 那个量出来的数，别另定一个。
INK_BOTTOM = 480

#: 封面没有序号药丸，可以铺到更低。同样抄 `serve_clock_cards`。
COVER_INK_BOTTOM = 560


def tier_cover() -> str:
    """封面：一条规矩把赛事切成两半，整条片子的全部内容就是这一刀。

    ⚠️ **封面故意不用球员照片。** 封面那一问是「花钱请球星来，犯规吗？」，
    把辛纳或阿尔卡拉斯的脸压在这句话下面，等于替读者认定了他就是那个
    收了钱的人——而**没有任何一手证据支持那句话**（查证过程在
    `research/promotional-fees-2026.md`）。CLAUDE.md「封面标题带着指控时，
    放谁的脸就是在指认谁」说的正是这一类，`gamesmanship` 是同一个先例。
    他俩的 ATP 官方实拍留在第 ①②	屏，那两屏只有赛程、比分和他们自己的原话。

    （顺带：那两张都是 1920×1080，铺满封面要放大 133%，本来也过不了
    `test_封面图不许被放大` 的 1.00x 地板。**但换掉它的理由是上一条，
    分辨率只是碰巧站在同一边**——别混，混了下次找到一张大图就会把脸放回去。）
    """
    rows = (
        (150, "大满贯", "不许", False),
        (236, "大师赛 1000", "不许", False),
        (322, "ATP 500", "可以", True),
        (408, "ATP 250", "可以", True),
    )
    body = []
    for y, name, verdict, allowed in rows:
        colour = LIME if allowed else SOFT
        body.append(
            f'  <rect x="52" y="{y}" width="796" height="68" rx="13" '
            f'fill="{FILL}" fill-opacity="{0.22 if allowed else 0.06}" '
            f'stroke="{colour}" stroke-width="{4 if allowed else 2}" '
            f'stroke-opacity="{1 if allowed else 0.40}"/>'
        )
        body.append(
            f'  <text x="88" y="{y + 45}" font-size="33" '
            f'font-weight="{800 if allowed else 600}" fill="{INK}" '
            f'fill-opacity="{1 if allowed else 0.66}">{name}</text>'
        )
        body.append(
            f'  <text x="812" y="{y + 45}" text-anchor="end" font-size="34" '
            f'font-weight="800" fill="{colour}" '
            f'fill-opacity="{1 if allowed else 0.66}">{verdict}</text>'
        )
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="52" text-anchor="middle" font-size="36" font-weight="700"
        fill="{INK}">花钱请球员来参赛</text>
  <text x="450" y="102" text-anchor="middle" font-size="26" fill="{SOFT}">ATP
        2026 规则书 · 第一章 1.16 推广费</text>
{chr(10).join(body)}
  <text x="450" y="{COVER_INK_BOTTOM}" text-anchor="middle" font-size="30"
        font-weight="800" fill="{LIME}">四档赛事，只有两档可以</text>
</svg>
"""


def who_may_pay() -> str:
    """屏 ③：谁可以给钱。一条规矩把四档赛事切成两半，这一屏就是那一刀。

    ⚠️ 四档的**顺序按级别从高到低**排，让「越高越不许」这个反直觉自己跳出来
    ——读者的默认预期是「级别越高越随便」，而规则正好相反。
    """
    # ⚠️ 整体上移一档：原来末行底缘 446、落款在 480，渲出来贴在一起。
    rows = (
        (140, "大满贯", "不许", False),
        (214, "大师赛 1000", "不许", False),
        (288, "ATP 500", "可以", True),
        (362, "ATP 250", "可以", True),
    )
    body = []
    for y, name, verdict, allowed in rows:
        colour = LIME if allowed else SOFT
        body.append(
            f'  <rect x="52" y="{y}" width="796" height="62" rx="12" '
            f'fill="{FILL}" fill-opacity="{0.20 if allowed else 0.07}" '
            f'stroke="{colour}" stroke-width="{3 if allowed else 2}" '
            f'stroke-opacity="{1 if allowed else 0.45}"/>'
        )
        body.append(
            f'  <text x="86" y="{y + 40}" font-size="30" '
            f'font-weight="{800 if allowed else 600}" fill="{INK}" '
            f'fill-opacity="{1 if allowed else 0.72}">{name}</text>'
        )
        body.append(
            f'  <text x="814" y="{y + 40}" text-anchor="end" font-size="31" '
            f'font-weight="800" fill="{colour}">{verdict}</text>'
        )
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" font-size="34" font-weight="700"
        fill="{INK}">谁可以花钱请球员来</text>
  <text x="450" y="94" text-anchor="middle" font-size="25" fill="{SOFT}">ATP
        2026 规则书 · 第一章 1.16 Promotional Fees</text>
{chr(10).join(body)}
  <text x="450" y="{INK_BOTTOM}" text-anchor="middle" font-size="27"
        font-weight="700" fill="{LIME}">这是整本规则书唯一的例外</text>
</svg>
"""


def penalty_ladder() -> str:
    """屏 ⑤：罚款按级别递增，而**罚得最狠的那一档本来就一分都不许给**。

    ⚠️ 条形的长度按罚款金额等比，别按视觉顺手拉——这一屏的全部意思就是
    「最高的那根，属于一个连给都不许给的级别」。
    """
    # ⚠️ y 起点和行距是**渲出来看着调的**：原来 150/78 那一版末条底缘落在
    # 452，和 INK_BOTTOM 那行落款只差 28，渲出来贴在一起。现在末条底缘 424。
    bars = (
        (136, "挑战赛", 2, "2 万", False),
        (208, "ATP 250", 3, "3 万", True),
        (280, "ATP 500", 4, "4 万", True),
        (352, "大师赛 1000", 6, "6 万", False),
    )
    unit = 96  # 每万美元多长
    body = []
    for y, name, wan, label, may_pay in bars:
        w = wan * unit
        colour = AMBER if not may_pay else FILL
        body.append(
            f'  <text x="52" y="{y + 26}" font-size="27" fill="{SOFT}">{name}</text>'
        )
        body.append(
            f'  <rect x="52" y="{y + 38}" width="{w}" height="30" rx="7" '
            f'fill="{colour}" fill-opacity="0.85"/>'
        )
        body.append(
            f'  <text x="{52 + w + 16}" y="{y + 62}" font-size="28" '
            f'font-weight="800" fill="{INK}">{label}</text>'
        )
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" font-size="34" font-weight="700"
        fill="{INK}">违规给钱，罚多少</text>
  <text x="450" y="94" text-anchor="middle" font-size="25" fill="{SOFT}">球员
        这一头的罚款上限 · 另追缴那笔钱本身</text>
{chr(10).join(body)}
  <text x="450" y="{INK_BOTTOM}" text-anchor="middle" font-size="27"
        font-weight="700" fill="{AMBER}">罚最重的那一档，本来就一分都不许给</text>
</svg>
"""


def audit_power() -> str:
    """屏 ⑥：这条规矩有牙（查账权、十万、终止会籍），**而金额从不披露**。

    ⚠️ 这一屏是整条片子的落点，所以左右分成「查得动」和「看不到」两栏——
    对比本身就是论点，不用旁白再说一遍。
    """
    # ⚠️ 第一条从 172 挪到 196：原来和框内标题（y=150）只隔 22，渲出来是贴着的。
    teeth = (
        (196, "要交出全部相关记录"),
        (248, "没有记录就出具宣誓书"),
        (300, "罚款最高 10 万美元"),
        (352, "可以终止会籍"),
    )
    body = []
    for y, line in teeth:
        body.append(f'  <circle cx="86" cy="{y - 8}" r="6" fill="{FILL}"/>')
        body.append(
            f'  <text x="112" y="{y}" font-size="26" fill="{INK}">{line}</text>'
        )
    return f"""
<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">
  <text x="450" y="46" text-anchor="middle" font-size="34" font-weight="700"
        fill="{INK}">它查得动，可你看不到</text>

  <rect x="52" y="112" width="418" height="268" rx="14"
        fill="{FILL}" fill-opacity="0.14" stroke="{FILL}"
        stroke-width="2" stroke-opacity="0.6"/>
  <text x="86" y="150" font-size="26" font-weight="700" fill="{FILL}">规则书写得很细</text>
{chr(10).join(body)}

  <rect x="500" y="112" width="348" height="268" rx="14"
        fill="none" stroke="{LIME}" stroke-width="3" stroke-dasharray="10 9"/>
  <text x="674" y="150" text-anchor="middle" font-size="26" font-weight="700"
        fill="{LIME}">而这一格是空的</text>
  <text x="674" y="236" text-anchor="middle" font-size="44" font-weight="800"
        fill="{LIME}">给了多少</text>
  <text x="674" y="296" text-anchor="middle" font-size="30" font-weight="700"
        fill="{SOFT}">从来不公布</text>

  <text x="450" y="{INK_BOTTOM}" text-anchor="middle" font-size="27"
        font-weight="700" fill="{INK}">合法、写在明处，金额在暗处</text>
</svg>
"""
