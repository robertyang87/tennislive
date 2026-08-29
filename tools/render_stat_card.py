#!/usr/bin/env python3
"""赛场之上：数据统计对照图。官方头像在上（小、圆）→ 比分夹在中间
（竖排、按盘）→ 技术统计在下（每一项谁占优谁的数字点亮）。9:16，铺满。

    PYTHONPATH=src python3 tools/render_stat_card.py \\
        --spec specs/reels/rybakina-osaka.json \\
        --out output/2026-08-11/reel/rybakina-osaka/stat_card.jpg

读的是 spec 里的 `cover`（matchup/winner/result/scoreboard——跟视频封面
同一份数据，不会两处对不上）和 `stats`（这张图独有，见下）。**不要求
spec 有 `segments`/`sources`**——只做统计图、不出视频的比赛（比如没打算
剪成片的 ATP 场次）可以只写一份 `{"cover": …, "stats": …}` 的精简 JSON，
一样能渲。

## `stats` 该怎么写

    "stats": {
      "tour": "wta",                              // "wta" 或 "atp"，决定头像去哪条路径找（仅供人核对，渲染本身只认 headshot 路径）
      "a": {                                       // 对应 cover.matchup[0]（版式顺序，不是赢家顺序）
        "headshot": "assets/players/headshots/wta-319998.jpg",
        "aces": 3, "df": 6, "winners": 18, "ue": 51,
        "first_in": 68, "first_total": 109, "first_won": 44,
        "second_won": 22, "second_total": 41,
        "bp_conv": 3, "bp_chances": 7,
        "pts_won": 107, "pts_total": 218
      },
      "b": { … 同上，对应 cover.matchup[1] … },
      "_source": "写清楚这些数字从哪查来的、怎么核实的——和 spec 别处的 _why 一个规矩"
    }

## 双打：两个人一队

`headshot` 可以是**一个路径**（单打，原样）或**一个正好两个路径的列表**
（双打，一队两个人）。数字仍然只有一组——flashscore `df_st_1` 给的是
**队伍合计**（发球/破发点/总分都不拆到某一个人身上），没有第二组数字
可填，所以 `stats.a`/`stats.b` 的字段结构和单打一模一样，只是 `headshot`
从一张脸变成两张脸并排（略微重叠，见 `.h2h-pair` 那段 CSS）。

`williams-sisters-cincinnati` 这条是第一次这么用：`stats.a.headshot`
是 `[威廉姆斯姐妹两人的头像]`，`stats.b.headshot` 是
`[科斯秋克, 斯特恩斯]` 两张。**别去猜"该放谁的脸代表整支队伍"**——
这正是当初没做数据图的理由，两个人一起放才不用做这个选择。

**`_source` 不是可选项。** 这张图存在的全部意义就是"数字要经得起查"——
ACE/双误/一发这几项在 flashscore `df_st_1` 就有；Winners/非受迫失误多数
公开源都没有，要么找官方转播统计大屏（截图核对），要么找赛事方赛后稿
（WTA 官网 Match Reaction 那类）交叉验证。别拿单一二手站（如 rallyher.com）
的数字不加验证就用——这个仓库已经在 rybakina-osaka 这条上吃过一次亏：
二手站给的 Winners/UE 和官方转播图对不上。

**Winners/UE 找不到时，按这个顺序多查几个源**（2026-08-13 实测，别重新试一遍）：

    rallyher.com                独立赛后稿，覆盖当周大部分 Toronto 比赛，
                                 但**不能单独采信**（上面那条教训）；
                                 WebFetch 对这个域名会 EGRESS_BLOCKED，
                                 改用 `curl -A "Mozilla/5.0 ..."` 走 Bash
                                 的代理能通——WebFetch 和 Bash 走的不是
                                 同一条出网路径，一个被挡不代表另一个也被挡
    tennisabstract.com/charting 人工逐分记谱，质量最高（Jeff Sackmann
                                 Match Charting Project），但**覆盖是志愿者
                                 手工挑的，当天/当周的非大满贯比赛基本不会
                                 有**——查 `charting/meta.html` 里的索引，
                                 同一对球员的历史交手会先跳出来，别把旧的
                                 那场当成这次的。大满贯和马德里/罗马/印第安
                                 维尔斯这类大站更可能被charting，Toronto
                                 这种规模的常规站基本查不到
    sofascore.com / matchstat.com / ultimatetennisstatistics.com
                                 三个在这台沙箱**恒不通**：sofascore 和
                                 matchstat 的 API 403，UTS 直接连接被重置
                                 （TLS 层面的阻断，不是权限问题）。别再花
                                 时间试，浪费一次请求就够确认了
    WTA 官方赛后稿（Match Reaction / By the Numbers）
                                 仍然是最可信的一档，但**发布有延迟**——
                                 半决赛打完当天常常还没有，决赛的稿子
                                 通常更快。查不到不代表以后也查不到，
                                 隔几小时可以再查一次

**2026-08-15 又加探了三条，都是真空，但三条都值得记**（wang-vandewinkel，
辛辛那提 WTA1000 首轮）：

    赛事官网自己的实时 feed      辛辛那提的 `score-center` 用的是
                                 `https://tennis-feeds.rain-digital.ca/get/
                                 <wta|atp>/<赛事 slug>/<matchId>`，纯 HTTP、
                                 不用浏览器，`feed_ip`/`tournament` 两个值就
                                 明写在赛事官网页面的 `<script>` 里。给的是
                                 分盘 12 项，**没有 Winners/UE**（`-stats`
                                 `-pbp` `-full` 这些端点变体全返回空数组）。
                                 ⚠️ 记它不是因为它有 UE，是因为它是**第三条
                                 独立数据线**——flashscore 和 WTA 官方掐架
                                 时它能当裁判，见下
    tennis.com 比赛页            `/tournaments/<赛事>/matches/<slug>-<日期>`，
                                 统计表是**服务端直出的 HTML**（不用跑 JS），
                                 11 项技术统计。同样没有 Winners/UE，但同样
                                 是一条独立数据线
    Yahoo Sports 比赛页          Sportradar 那条线，页面很大但 `unforced`
                                 零命中

⚠️ **多查这几个源的第二个用处：flashscore 会多算分，而它自己前后矛盾。**
wang-vandewinkel 那场 flashscore 报范德温克尔发球总分 95、总得分 67，可
54 一发 ＋ 40 二发 = 94、35 ＋ 10 = 45 ≠ 它写的 46；WTA 官方 `/stats`、
赛事官网 feed、tennis.com **三个源都说 94/66**。所以 `_source` 里遇到
「这个源自己对不上」时不要只记一句「如实记下不抹平」——**再拉一个源就能
把它判掉**，而判掉之前那张图上印的是个错数字。

**这条不是「查够了就能用」的许可**，是「查完这一轮该查的都查了，仍然
一个都没有」时如实说清楚查过什么——参照上面『查得够深、查得够广』那条
判据，报告里要点名每一个查过的源和它给出的结论（含"被墙""无覆盖"这类
否定结果），不能只说「查过了，没有」。

## 头像

**不在渲染时抓，抓好之后缓存成文件、spec 里写路径。** 用
`tools/fetch_official_headshot.py` 抓一次、存进
`assets/players/headshots/`，多次渲染不用重复打网络请求。

## 每一行谁占优

`ROW_SPECS` 是这张图的固定模板，换球员不用改。每条是
`(中文标签, 英文标签, 方向, *字段名)`。方向语义：

    "hi"    数字越大越好（ACE / 制胜分 / 总得分）
    "lo"    数字越小越好（双误 / 非受迫失误）
    "pct"   分子/分母算百分比，主数字显示百分比，小字标原始分数，越大越好
    "frac"  分子/分母，**主数字就是分数本身**（不折算成 %），比率越大越好

两边相等（比如双误打平）不点亮任何一侧——不替谁背书。

### 中文标签底下那行英文（账号所有者 2026-08-15：「后续都这么做」）

英文跟中文写在**同一条 `ROW_SPECS`**里，不另开一张对照表——两处必分叉，而
分叉的样子是「某一行的英文是上一行的」，图上完全看不出来。

⚠️ **这一行不许把行高撑高**（账号所有者同一句话里的第二个要求：「每行的高度
不变」）。所以它是 `position:absolute` 挂在 `.slabel` 底下的，**不参与行盒的
高度计算**；中文那行再用 `position:relative` 往上提一点，让「中文 + 英文」这
一对在原来那个行高里视觉居中。两样都改不得：

    英文改成在流内（去掉 absolute）  → 每行长高，整张图跟着变长
    中文那个 relative 位移去掉        → 一对偏下，压到分隔线上

实测（wang-vandewinkel，2160×3840）：加英文前后**相邻两条分隔线的间距一模
一样**，整张表的首尾像素位置也一模一样。判据在
`test_每行英文不许把行高撑高`。

⚠️ **`top` 那个 −24px 是量出来的，别按感觉调。** 账号所有者 2026-08-15 第二次
反馈：「把中文往上移，英文在下面，然后它们并行居中。垂直居中」——最早那版写的
−11px 只够把英文塞进去，「中文 + 英文」这一对的光学中心仍然比两侧那个大号数字
**低 18~25px**（2160 空间，也就是 9~12 个 CSS 像素），看起来是整块往下坠。

量法：按分隔线切出每一行，左列（数字）和中列（中英）各取墨迹的上下沿，比两个
中心。英文 19px 那一版扫出来 −21px 最正（+0.6）；同一天账号所有者又说「英文
太小」，字号提到 24px 之后**这一对整体变高，−21px 就不够了**，重扫：

    top:-23px   每行偏移 [—, 4, 0, 0, 0, 6, 4]    平均 +2.3
    top:-24px   每行偏移 [—, 2, -2, -2, -2, 4, 2]  平均 +0.3   ← 选它
    top:-25px   每行偏移 [—, 0, -4, -4, -4, 2, 0]  平均 -1.7

（ACE 那一行没有英文，走 `.slabel--solo`，不参与这张表。）

剩下那 ±4px（2160 空间 ≈ 2 个 CSS 像素）是字形本身的差别（`%` 比纯数字高、
`6/17` 那道斜杠更长），不是版式没对齐——**再调只会把一部分行调正、另一部分
调歪**。判据在 `test_中英那一对的垂直位置是量出来的一组数`。

⚠️ **改英文字号就要重扫 `top`。** 上面这两轮正是同一件事发生了两次：19 → 24px
之后 −21px 立刻不对了，而**歪掉在产物上不报错**。判据把「中文字号 / 英文字号 /
行距 / 位移」四个数一起锁住，动任何一个都当场红，逼着重量一次。

### ⚠️ 中文标签本身就是英文的那一行，不出英文

账号所有者 2026-08-15：「**ACE 就不要英文了**」——底下再写一行 `Aces` 是把同一个
词说两遍。`ROW_SPECS` 里英文写**空串**就是认领这件事：不出那个 span，并且换一档
位移（`.slabel--solo`）——`−24px` 是按两行的高度量的，只剩一行还提 24px 会顶太高。

solo 那一档单独量过：纯中文在 `top:0` 时比数字中心**低 10.6px**，所以取 −5px，
实测 ACE 那一行偏移 +2。

⚠️ 英文的**水平**居中不是靠 `left:0;right:0`——`.slabel` 那一格的宽度是按
中文文字撑出来的（`white-space:nowrap` + `grid` 的 `auto` 列），而英文往往更宽
（`Break Points Converted` 比「破发点转化」宽一截）。撑在格子里会换行，所以用
`left:50%` + `translateX(-50%)`：以中文的中心为轴，而那个中心正好是画布中心
（三列 `1fr auto 1fr`）。

## ⚠️ 制胜分 / 非受迫失误这两行可以缺，其余不许缺

账号所有者 2026-08-14（斯瓦泰克-莱巴金娜那张）：「**没有的话这两条就不显示**」。

来路是数据源的硬限制，不是懒得填：**WTA 巡回赛（1000/500/250）拿不到
`Winners` / `Unforced errors`**——flashscore 那个 feed 对 WTA 巡回赛只给 17 项，
WTA 官方 `/stats` 的 32 个字段一个都不含，八条路都自证过是真空
（CLAUDE.md「上面那句范围写宽了」那节）。而**大满贯的女子比赛和 ATP 一直有**，
所以这两行绝大多数时候照常出现。

判据不是「谁重要」，是**这个数存不存在**：

    OPTIONAL_FIELDS 里的字段    两边都没有 → 整行不画
                                只有一边有 → **报错**（数据对不齐是 bug，不是缺数据）
    其余字段                    缺任何一个 → 报错，照旧

⚠️ **还留了一道下限**：至少要画得出 `MIN_ROWS` 行，否则报错。不设的话，
一份几乎全空的 stats 也能渲出一张「看起来正常」的图——而这正是本仓库
反复记的那种不吭声的坏。
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import versus_poster as vp  # noqa: E402
from tennislive.render.webcards import _font_css  # noqa: E402
from tennislive.video.explainer import _data_uri  # noqa: E402

W, H = 1080, 1920

# (标签, 类型, ...字段名)——固定模板，见模块 docstring「每一行谁占优」。
ROW_SPECS = [
    # ⚠️ 英文写空串＝**这一行故意不要英文**（账号所有者 2026-08-15：「ACE 就
    # 不要英文了」）。判据只放行「中文标签本身就是英文」的那种（ACE），
    # 中文标签留空串是另一回事，照旧报错。
    ("ACE", "", "hi", "aces"),
    ("双误", "Double Faults", "lo", "df"),
    ("制胜分", "Winners", "hi", "winners"),
    ("非受迫失误", "Unforced Errors", "lo", "ue"),
    ("一发成功率", "1st Serve %", "pct", "first_in", "first_total"),
    ("一发得分率", "1st Serve Points Won", "pct", "first_won", "first_in"),
    ("二发得分率", "2nd Serve Points Won", "pct", "second_won", "second_total"),
    ("破发点转化", "Break Points Converted", "frac", "bp_conv", "bp_chances"),
    ("总得分", "Total Points Won", "hi", "pts_won"),
]

# 这两项 WTA 巡回赛拿不到（见模块 docstring）。**只有这两个可以缺**，
# 别往里加——加一个就等于允许那一行悄悄消失，而缺一行的图和完整的图
# 在产物上长得一模一样。
OPTIONAL_FIELDS = frozenset({"winners", "ue"})

# 画不出这么多行就报错。9 行里最多允许缺制胜分和非受迫失误，所以下限是 7。
MIN_ROWS = 7


def usable_rows(a: dict, b: dict) -> list[tuple]:
    """按「这个数存不存在」筛出要画的行。

    ⚠️ **只有两边都没有才跳过。** 只有一边有的时候报错——那不是「拿不到」，
    那是数据对不齐，而对不齐的图会把两个人的数放在同一行里比。
    """
    rows = []
    for spec_row in ROW_SPECS:
        fields = spec_row[3:]
        in_a = all(f in a for f in fields)
        in_b = all(f in b for f in fields)
        if in_a and in_b:
            rows.append(spec_row)
            continue
        if in_a != in_b:
            raise SystemExit(
                f"「{spec_row[0]}」这一行只有一边有数（a={in_a} b={in_b}）。"
                "两边都没有才跳过；只有一边有是数据对不齐，不是拿不到。")
        if not set(fields) <= OPTIONAL_FIELDS:
            raise SystemExit(
                f"「{spec_row[0]}」这一行缺字段 {sorted(fields)}，而它不在可缺清单里。"
                f"可缺的只有制胜分和非受迫失误（{sorted(OPTIONAL_FIELDS)}）——"
                "那两项 WTA 巡回赛拿不到，其余的都拿得到。")
    if len(rows) < MIN_ROWS:
        raise SystemExit(
            f"只画得出 {len(rows)} 行，少于下限 {MIN_ROWS}。"
            "一份几乎全空的 stats 也能渲出一张看起来正常的图，所以这里拦住。")
    return rows

_SET_TOKEN_RE = re.compile(r"^(\d{1,2})-(\d{1,2})(\(\d{1,2}\))?$")


def _stat_row(kind: str, a: dict, b: dict, *fields: str) -> tuple:
    """算出 (主值a, 分数注脚a, 主值b, 分数注脚b, 谁占优)。谁占优 ∈ {"a","b",None}。"""
    if kind in ("hi", "lo"):
        (key,) = fields
        av, bv = a[key], b[key]
        lead = None
        if av != bv:
            lead = ("a" if av > bv else "b") if kind == "hi" else ("a" if av < bv else "b")
        return str(av), "", str(bv), "", lead
    if kind == "pct":
        num_key, den_key = fields
        an, ad = a[num_key], a[den_key]
        bn, bd = b[num_key], b[den_key]
        apct = round(an / ad * 100) if ad else 0
        bpct = round(bn / bd * 100) if bd else 0
        lead = None if apct == bpct else ("a" if apct > bpct else "b")
        return f"{apct}%", f"{an}/{ad}", f"{bpct}%", f"{bn}/{bd}", lead
    if kind == "frac":
        num_key, den_key = fields
        an, ad = a[num_key], a[den_key]
        bn, bd = b[num_key], b[den_key]
        arate = an / ad if ad else 0
        brate = bn / bd if bd else 0
        lead = None if arate == brate else ("a" if arate > brate else "b")
        return f"{an}/{ad}", "", f"{bn}/{bd}", "", lead
    raise ValueError(f"未知的行类型：{kind}")


def _stat_row_html(label: str, label_en: str, lv: str, lf: str, rv: str, rf: str,
                   lead: str | None) -> str:
    """⚠️ 英文那个 `<span>` **必须嵌在 `.slabel` 里面**，不能当成第四个网格项。

    `.srow` 是 `1fr auto 1fr` 三列，多一个子元素就多一列，整行版式塌掉；
    而嵌在里面 + `position:absolute`，它既不占列也不占高度（见模块 docstring
    「这一行不许把行高撑高」）。
    """
    lcls = " lead" if lead == "a" else ""
    rcls = " lead" if lead == "b" else ""
    lfrac = f'<span class="sfrac">({html.escape(lf)})</span>' if lf else ""
    rfrac = f'<span class="sfrac">({html.escape(rf)})</span>' if rf else ""
    # 英文是空串的那一行（ACE）不出这个 span，并且换一档位移：`.slabel` 那个
    # −21px 是按「中文 + 英文」两行的高度量的，只剩一行还提 21px 就顶太高了。
    en = f'<span class="slabel-en">{html.escape(label_en)}</span>' if label_en else ""
    solo = "" if label_en else " slabel--solo"
    return f"""
<div class="srow">
  <span class="sval sval-l{lcls}"><span class="smain">{html.escape(lv)}</span>{lfrac}</span>
  <span class="slabel{solo}">{html.escape(label)}{en}</span>
  <span class="sval sval-r{rcls}"><span class="smain">{html.escape(rv)}</span>{rfrac}</span>
</div>"""


def _reorder_result(result: str, swap: bool) -> str:
    """`cover.result` 是赢家在前；头像左边不一定是赢家，所以按 matchup 的
    物理左右重新拼一遍每一盘的两个数字（带抢七小分原样跟走）。"""
    if not swap:
        return result
    out = []
    for token in result.split():
        m = _SET_TOKEN_RE.match(token)
        if not m:
            out.append(token)
            continue
        left, right, tb = m.group(1), m.group(2), m.group(3) or ""
        out.append(f"{right}-{left}{tb}")
    return " ".join(out)


def _add_tb_parens(sets_html: str) -> str:
    """`_sets_html()` 的 `.tb` 只放裸数字（那是给小字用的），这版比分是
    画面正中的焦点，裸数字紧跟在盘分后面容易看成指数——加回括号。"""
    return re.sub(r'(<span class="tb">)(\d+)(</span>)', r"\1(\2)\3", sets_html)


def _headshot_style(raw: dict, where: str) -> str:
    """按球员校准头像的视觉尺度；默认值保持所有历史产物不变。"""
    try:
        zoom = float(raw.get("headshot_zoom", 1))
        focus_x = float(raw.get("headshot_focus_x", 50))
        focus_y = float(raw.get("headshot_focus_y", 18))
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{where} 的头像缩放/焦点必须是数字。") from exc
    if not 1 <= zoom <= 3:
        raise SystemExit(f"{where}.headshot_zoom 必须在 1 到 3 之间。")
    if not 0 <= focus_x <= 100 or not 0 <= focus_y <= 100:
        raise SystemExit(f"{where}.headshot_focus_x/y 必须在 0 到 100 之间。")
    if zoom == 1 and focus_x == 50 and focus_y == 18:
        return ""
    return (
        f' style="object-position:{focus_x:g}% {focus_y:g}%;'
        f'transform:scale({zoom:g});transform-origin:{focus_x:g}% {focus_y:g}%"'
    )


def build(spec: dict) -> str:
    cover = spec["cover"]
    stats = spec.get("stats")
    if not stats:
        raise SystemExit("spec 里没有 `stats` 块，没法渲数据统计对照图。")
    if "a" not in stats or "b" not in stats:
        raise SystemExit("`stats` 必须同时给 `a`（对应 matchup[0]）和 `b`（对应 matchup[1]）。")
    a, b = stats["a"], stats["b"]
    for side, raw in (("a", a), ("b", b)):
        if "headshot" not in raw:
            raise SystemExit(f"stats.{side} 缺 `headshot`——先用 "
                              "tools/fetch_official_headshot.py 抓一张，再把路径写进来。")
        missing = [f for spec_row in ROW_SPECS for f in spec_row[3:]
                   if f not in raw and f not in OPTIONAL_FIELDS]
        if missing:
            raise SystemExit(f"stats.{side} 缺这些字段：{sorted(set(missing))}")
    rows = usable_rows(a, b)

    matchup = cover.get("matchup") or []
    if len(matchup) != 2:
        raise SystemExit("数据统计对照图要 cover.matchup 给出两位球员。")
    winner = str(cover["winner"]).strip()
    result = str(cover["result"]).strip()
    court = str(cover["scoreboard"]["court"]).strip()
    duration = vp._fetch_match_duration(  # noqa: SLF001
        cover["scoreboard"]["duration_source"], "cover.scoreboard")

    left_meta, right_meta = matchup[0], matchup[1]
    swap = str(left_meta["name"]).strip() != winner
    sets_rows = "".join(
        f'<div class="h2h-set-row">{_add_tb_parens(vp._sets_html(token))}</div>'  # noqa: SLF001
        for token in _reorder_result(result, swap).split())

    icon = REPO_ROOT / "assets/logo/brand/icon.png"
    icon_html = f'<img class="brand-icon" src="{_data_uri(icon)}" alt="">'

    rows_html = "".join(
        _stat_row_html(spec_row[0], spec_row[1],
                       *_stat_row(spec_row[2], a, b, *spec_row[3:]))
        for spec_row in rows)

    def side(meta: dict, raw: dict, where: str) -> str:
        is_win = str(meta["name"]).strip() == winner
        ring_cls = " win" if is_win else ""
        rank = meta["rank"]
        rank_html = f'<span class="h2h-rank">（{int(rank)}）</span>' if rank is not None else ""
        flag_html = vp._score_flag(meta, where)  # noqa: SLF001
        en = vp._english_display(meta["name"], meta, where)  # noqa: SLF001
        headshot = raw["headshot"]
        if isinstance(headshot, list):
            # **双打：两张头像，不是一张。** 见模块 docstring「双打：两个人
            # 一队」——同一个视觉footprint（252×252）里塞两个较小的圆、
            # 略微重叠，像头像堆叠；两个都跟着队伍的胜负描边，不单独判
            # 谁赢谁输（这是团队数据，不是个人数据）。
            if len(headshot) != 2:
                raise SystemExit(
                    f"{where}.headshot 给了列表就必须正好两张（双打两个人各一张），"
                    f"现在是 {len(headshot)} 张。")
            portrait_html = '<div class="h2h-pair">' + "".join(
                f'<div class="h2h-ring h2h-ring--pair{ring_cls}">'
                f'<img src="{_data_uri(REPO_ROOT / p)}" alt=""></div>'
                for p in headshot) + "</div>"
        else:
            headshot_uri = _data_uri(REPO_ROOT / headshot)
            image_style = _headshot_style(raw, where)
            portrait_html = (f'<div class="h2h-ring{ring_cls}">'
                              f'<img src="{headshot_uri}" alt=""{image_style}></div>')
        return f"""<div class="h2h-side">
  {portrait_html}
  <div class="h2h-cn">{html.escape(meta["name"])}{rank_html}</div>
  <div class="h2h-flagrow">{flag_html}<span class="h2h-en">{html.escape(en)}</span></div>
</div>"""

    h2h_a = side(left_meta, a, "stats.a")
    h2h_b = side(right_meta, b, "stats.b")

    topic = f'{html.escape(str(cover.get("topic", "")))}'
    footer_venue = html.escape(str(stats.get("footer_venue") or court))
    footer_date = html.escape(str(stats.get("footer_date") or ""))

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden}}
body{{color:{vp.TEXT};font-family:'TL Sans SC','Noto Sans CJK SC',sans-serif;
 background:
  radial-gradient(1150px 800px at 8% -8%, rgba(198,246,90,.20), transparent 52%),
  radial-gradient(1000px 900px at 106% 14%, rgba(75,184,255,.18), transparent 52%),
  radial-gradient(900px 750px at 90% 96%, rgba(255,90,106,.11), transparent 50%),
  radial-gradient(950px 700px at 20% 108%, rgba(55,226,154,.13), transparent 52%),
  linear-gradient(170deg,#141a30 0%,#0d0f20 40%,#08091a 72%,#05050f 100%)}}
.bar{{height:11px;background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,
 #ff5a6a 67%,#4bb8ff 100%)}}
.head{{display:flex;align-items:center;gap:18px;padding:32px 74px 6px}}
.brand-icon{{width:58px;height:58px;object-fit:contain}}
.brandlines{{display:flex;flex-direction:column;gap:5px}}
.brand{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:41px;
 font-weight:400;color:{vp.TEXT}}}
.topic{{font-family:'TL Sans SC',sans-serif;font-size:28px;font-weight:700;
 color:#dcefe4;letter-spacing:.5px}}

/* 头像＋比分夹在中间：官方头像给一圈描边，赢家那侧描边给品牌绿，
   输的一侧给中性灰——不用另加一个"W"角标，赢没赢在描边上已经看得出来。 */
.h2h{{display:flex;align-items:flex-start;justify-content:space-between;
 padding:36px 58px 0}}
.h2h-side{{display:flex;flex-direction:column;align-items:center;width:284px}}
.h2h-ring{{width:252px;height:252px;border-radius:50%;overflow:hidden;
 border:6px solid rgba(244,251,247,.32);box-shadow:0 14px 30px rgba(0,0,0,.5);
 flex:0 0 auto}}
.h2h-ring.win{{border-color:#c6f65a;box-shadow:0 14px 34px rgba(198,246,90,.4)}}
.h2h-ring img{{width:100%;height:100%;object-fit:cover;object-position:50% 18%;
 background:#e9efe9}}
/* 双打：两张小头像叠在同一个 252×252 footprint 里居中，不改
   `.h2h-mid` 的 padding-top（那个数是照 252px 高的头像量的）。
   两个圆各 150px、重叠 30px，视觉宽度和单人版的 252px 大致相当。 */
.h2h-pair{{width:252px;height:252px;display:flex;align-items:center;
 justify-content:center;flex:0 0 auto}}
.h2h-ring--pair{{width:150px;height:150px;margin:0 -15px;position:relative}}
.h2h-ring--pair:first-child{{z-index:2}}
.h2h-ring--pair:last-child{{z-index:1}}
.h2h-cn{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:41px;
 margin-top:18px;text-align:center;white-space:nowrap}}
.h2h-rank{{font-size:.6em;color:{vp.DIM};margin-left:2px}}
.h2h-flagrow{{display:flex;align-items:center;gap:9px;margin-top:10px}}
.h2h-flagrow .score-flag-slot{{width:43px;height:29px;flex:0 0 43px}}
.h2h-flagrow .score-flag{{width:39px;height:26px}}
.h2h-en{{font-family:'TL Sans SC',sans-serif;font-size:21px;letter-spacing:1.2px;
 color:#dcefe4;white-space:nowrap}}

.h2h-mid{{flex:0 0 auto;display:flex;flex-direction:column;align-items:center;
 padding-top:8px;min-width:170px}}
/* 竖着排：每一盘单独一行，行间距比行内的连字符更松，读起来是"三盘"
   不是"一串数字"。padding-top:8px 是量出来让比分块的视觉中心跟头像圆的
   视觉中心对齐的值——改字号/头像尺寸要重新量，别凭感觉改这个数。 */
/* ⚠️ 数字走 `TL Sans SC`（Noto Sans），不是 `TL Numeral`（Montserrat）——
   账号所有者 2026-08-29：「比分的数字字体都用这种，**包括以后所有视频里的
   其他地方的比分都用这种字体**，赢的一盘的加粗」。换哪一支是拿 IoU 量出来的，
   账记在 `versus_poster` 的 `.score-number` 那段注释里；封面比分板、视频顶栏、
   赛后开麦顶栏和这张卡从此是同一套数字。
   ⚠️ 这一条只管**比分**。底下 `.sval` 那些技术统计（Ace、双误）不是比分，
   没跟着改——账号所有者说的是比分。 */
.h2h-set-row{{font-family:'TL Sans SC',sans-serif;font-size:56px;
 font-weight:400;white-space:nowrap;text-align:center;line-height:1.42}}
.set{{display:inline-block}}
/* 赢下那一盘：上绿**＋加粗**（「赢的一盘的加粗」）。 */
.setwin{{color:#c6f65a;font-weight:700}}
.setlose{{color:{vp.TEXT};font-weight:400}}
.setdash{{color:#93a79c;margin:0 .05em;font-size:.7em}}
.tb{{font-size:.42em;color:#93a79c;vertical-align:super;margin-left:.04em}}
.setplain{{color:#c6f65a}}
/* 球场和用时分两行（账号所有者 2026-08-15）。⚠️ 第二行用 `h2h-meta2` 只压
   行距，**不再重复 `margin-top:18px`**——那 18px 是比分块和这一段之间的呼吸，
   不是行距；两行都带上会把用时那行推得像另一个板块。 */
.h2h-meta{{margin-top:18px;font-family:'TL Sans SC',sans-serif;font-size:21px;
 color:{vp.DIM};text-align:center;white-space:nowrap;letter-spacing:.3px}}
.h2h-meta2{{margin-top:6px}}

.wrap{{padding:52px 74px 0}}
.section-title{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;
 font-weight:400;color:{vp.TEXT};margin-bottom:30px;text-align:center}}

/* 无进度条：数字分两侧对齐画布边缘，标签居中，谁占优谁点亮。
   ⚠️ 没有固定配色的图例——高亮是按每一行的方向算出来的（谁数字大/小占优），
   同一个人在不同行可能一次亮一次不亮。图例如果画成「灰=A 绿=B」的固定点，
   A 在自己占优的那几行也会变绿，和图例说的正好相反，所以干脆不画图例。 */
.srow{{display:grid;grid-template-columns:1fr auto 1fr;align-items:baseline;
 gap:14px;margin-bottom:33px;padding-bottom:23px;
 border-bottom:1px solid rgba(244,251,247,.10)}}
.srow:last-child{{border-bottom:none;margin-bottom:0;padding-bottom:0}}
.sval{{display:inline-flex;align-items:baseline;gap:10px;white-space:nowrap;
 font-family:'TL Numeral','TL Sans SC',sans-serif}}
.sval-l{{justify-content:flex-start}}
.sval-r{{justify-content:flex-end}}
/* 左列 DOM 顺序是 smain→sfrac，flex-start 贴左边，主数字天然贴边。
   右列同样的 DOM 顺序配 flex-end 会把 sfrac 贴到最外沿、主数字反而缩进——
   用 order 只调右列的视觉顺序，让主数字（大号、占优时变色）也贴在外沿，
   和左列对称。 */
.sval-r .smain{{order:2}}
.sval-r .sfrac{{order:1}}
.smain{{font-size:51px;font-weight:400;color:rgba(244,251,247,.55)}}
.sval.lead .smain{{color:#c6f65a;font-weight:700}}
.sfrac{{font-size:23px;font-weight:400;color:rgba(244,251,247,.6)}}
.sval.lead .sfrac{{color:rgba(198,246,90,.75)}}
/* 中文标签 + 底下那行英文。⚠️ 两条都不许动，理由见模块 docstring
   「中文标签底下那行英文」那节：
   - `.slabel` 的 `top:-24px` 是 `position:relative` 的**视觉**位移，不改
     行盒高度；它把「中文 + 英文」这一对在原来的行高里顶回视觉居中。
     ⚠️ 这个数是量出来的（扫墨迹比两个光学中心，−23/−24/−25 三档都渲过），
     不是拍的；**改英文字号就要重扫一次**，docstring 里有那张表。
   - `.slabel-en` 是 `position:absolute`，**不参与行盒高度计算**——这是
     「每行的高度不变」唯一的实现方式。改成流内每行就会长高。
   `left:50%` + `translateX(-50%)` 而不是 `left:0;right:0`：这一格的宽度是
   中文撑出来的，英文更宽（`Break Points Converted`），撑在格子里会换行。 */
.slabel{{font-family:'TL Sans SC',sans-serif;font-size:32px;font-weight:700;
 color:rgba(244,251,247,.92);letter-spacing:.3px;text-align:center;white-space:nowrap;
 position:relative;top:-24px}}
.slabel-en{{position:absolute;top:100%;left:50%;transform:translateX(-50%);
 margin-top:4px;white-space:nowrap;font-size:24px;font-weight:400;
 letter-spacing:.7px;color:rgba(244,251,247,.46)}}
/* 没有英文的那一行（ACE）：只剩中文一行，−21px 会把它顶太高。solo 的
   位移单独量过（纯中文在 top:0 时比数字中心低 10.6px，所以取 −5px）。 */
.slabel--solo{{top:-5px}}

.footer{{margin-top:38px;padding-top:20px;border-top:1px solid rgba(244,251,247,.18);
 display:flex;justify-content:space-between;align-items:center;
 font-family:'TL Sans SC',sans-serif;font-size:23px;color:{vp.DIM};letter-spacing:.5px}}
</style></head>
<body>
<div class="bar"></div>
<div class="head">{icon_html}
  <div class="brandlines"><span class="brand">网球时差 · 数据复盘</span>
  <span class="topic">{topic}</span></div>
</div>

<div class="h2h">
  {h2h_a}
  <div class="h2h-mid">
    {sets_rows}
    <div class="h2h-meta">{html.escape(court)}</div>
    <div class="h2h-meta h2h-meta2">{html.escape(duration)}</div>
  </div>
  {h2h_b}
</div>

<div class="wrap">
  <div class="section-title">全场数据对比</div>
  {rows_html}

  <div class="footer">
    <span>网球时差 · 赛场之上</span>
    <span>{footer_venue}{" · " + footer_date if footer_date else ""}</span>
  </div>
</div>
</body></html>"""


def _launch_browser(pw):
    try:
        return pw.chromium.launch(args=["--no-sandbox"])
    except Exception as default_error:  # noqa: BLE001
        import os
        candidates = [
            os.environ.get("CHROMIUM_PATH"),
            str(REPO_ROOT / ".local-browser" / "chromium"),
            "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
        ]
        for executable in candidates:
            if executable and Path(executable).is_file():
                return pw.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        raise default_error


def render(spec: dict, out: Path) -> Path:
    html_str = build(spec)
    page = out.with_suffix(".html")
    page.write_text(html_str, encoding="utf-8")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        tab = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        tab.goto(page.resolve().as_uri())
        # 头像是 data URI，文件稍大时 Chromium 会先把首批扫描线画出来，
        # `img.complete` 也可能已经为真；固定等 400ms 会截到“上半张脸 + 下半块
        # 背景色”的半解码状态。截图前逐张 await decode()，拿到完整像素再落图。
        tab.wait_for_function(
            "Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)",
            timeout=15_000,
        )
        tab.evaluate(
            "() => Promise.all(Array.from(document.images).map(img => img.decode()))"
        )
        tab.wait_for_timeout(100)
        tab.screenshot(path=str(out), type="jpeg", quality=95)
        content_h = tab.evaluate("document.body.scrollHeight")
        if content_h > H:
            print(f"[数据统计图] ⚠️ 内容溢出：画布 {H}px，实际 {content_h}px")
        browser.close()
    page.unlink(missing_ok=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(spec, args.out)
    print(f"[数据统计图] {args.out}（{args.out.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
