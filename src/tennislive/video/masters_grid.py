"""九站大师赛的中心球场九宫格——「金大师」那条片子的 ②屏。

为什么是示意图而不是照片：这一屏讲的是「**集齐九站**」，而没有任何一张
照片能表达一个集合被凑满——一张辛纳打球的照片只能证明「他在打球」。
这落在「示意图的触发条件是照片讲不清，不是照片找不到」那一条上。

⚠️ 而九站的 logo 那条路探过，别再试（2026-08-14 实测）：
首页扫 ``img[src*=logo]`` 抓到的是**赞助商** logo（印第安维尔斯抓到
「29 SPOTLIGHT CASINO」、巴黎抓到「ROLEX」），``og:image`` 是社交卡照片，
七张里只有马德里一张是对的——**而光看尺寸和文件名完全分不出来**，
是拼成联系表打开看才现形的（「非空 ≠ 对题」）。九个 logo 的宽高比还
差得离谱（2939x2877 方 / 1488x610 横条 / 512x641 竖），拼 3x3 必然乱。

改用中心球场全景是账号所有者定的，好在三处：``data/venue_assets.json``
里九站现成且都是 ``shot=centre-court``（仓库自己那道闸验过的）；九张同一种
机位语言，天然对齐；**而且图本身多讲一层——红土和硬地一眼分得出**。

⚠️ base64 在这里**运行时算，不写进源码**。整张 SVG 约 750KB，而源码里
已有的内嵌图（``nadal-academy``）是 143KB——五倍的差距不该塞进
``explainer.py`` 那个六千行的文件里。
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

# ⚠️ 按**文件名精确认领**，不按子串匹配赛事名。踩过：拿 "monte" 去匹配会
# 命中 `monterrey-centre-court.jpg`（蒙特雷，墨西哥），而它和真的命中长得
# 一模一样——又一次「判据宁可窄，不可宽」。
NINE_MASTERS: tuple[tuple[str, str, str], ...] = (
    ("印第安维尔斯", "indianwells-centre-court.jpg", "hard"),
    ("迈阿密", "miami-centre-court.jpg", "hard"),
    ("蒙特卡洛", "montecarlo-centre-court.jpg", "clay"),
    ("马德里", "madrid-centre-court.jpg", "clay"),
    ("罗马", "rome-foro-italico-centre-court.jpg", "clay"),
    ("加拿大", "canada-iga-stadium-centre-court.jpg", "hard"),
    ("辛辛那提", "cincinnati-centre-court-full.jpg", "hard"),
    ("上海", "shanghai-qizhong-centre-court.jpg", "hard"),
    # ⚠️ 换过一次：原来的 `paris-centre-court.jpg` 是室内紫光秀场镜头，
    # 光束和人群占满，**球场几乎看不见**——账号所有者一眼指出来。现在这张
    # 满场、球场清楚，和其余八格同一种视觉语言（高位全景＋满看台）。
    # ⚠️ 它是**贝尔西**（Palais Omnisports Paris-Bercy）2024-10-30，而巴黎
    # 大师赛 2025 年已搬到拉德芳斯球馆（Nanterre）。城市没错，场馆是上一个——
    # 要用现址得另找，这条留着让下一个人知道这不是没注意到。
    ("巴黎", "paris-bercy-centre-court.jpg", "hard"),
)

VENUE_DIR = Path("assets/venues")

# 每格的渲染尺寸。SVG 在卡上是 920px 宽、viewBox 900 单位、2 倍截图，
# 3 列每格约 610 设备像素——所以 560 已经略有余量，再大只是白占体积。
#
# ⚠️ 比例是 **2:1 全景**，不是原图的 3:2。第一版按 3:2 排，三行要 780 单位高，
# 而这个仓库的示意图 viewBox 一律 900x600——**底下一整行被切掉了**，
# 而 SVG 本身、字符数、image 个数全都正常，只有渲出来打开看才发现。
# 2:1 之后三行连标题共约 586 单位，装得下。
#
# ⚠️ 第二版仍然差一点：底行的**文字标签**落在 y=608，还是出了 600 那条边。
# 格子看着都在、SVG 也正常——**只有把底边那几个字读一遍才发现**。
# 排版要按最后一个元素的落点算，不是按最后一个格子的落点算。
_TILE_W, _TILE_H = 560, 280
_TILE_QUALITY = 76


def _tile_data_uri(name: str) -> str:
    """把一张中心球场图裁成 3:2、缩到渲染尺寸、编成 data URI。"""
    path = VENUE_DIR / name
    with Image.open(path) as raw:
        im = raw.convert("RGB")
        want = _TILE_W / _TILE_H
        w, h = im.size
        if w / h > want:  # 太宽，横向收边
            nw = int(h * want)
            im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:  # 太高，纵向收边
            nh = int(w / want)
            im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
        im = im.resize((_TILE_W, _TILE_H), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=_TILE_QUALITY, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def nine_masters_grid() -> str:
    """九宫格 SVG。红土那三站描橙边，硬地描蓝边，一眼看得出分野。"""
    cols, gap = 3, 14
    # ⚠️ x0 收到 66（而不是贴边的 26）是为了把整张图**压矮**：格宽小了，
    # 格高跟着小，底行标签从 y=582 收到 540。真卡片上 600 那条边不是安全线——
    # 示意图下面紧跟着序号药丸，582 那一版「辛辛那提」被药丸压住了，
    # **而裸渲预览完全看不出来**（那儿没有药丸）。渲真卡片才发现的。
    x0, y0 = 66, 68
    tw = (900 - x0 * 2 - gap * (cols - 1)) / cols
    th = tw * _TILE_H / _TILE_W
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="30" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">九站大师赛</text>',
        '<text x="450" y="56" text-anchor="middle" font-size="22" '
        'fill="#a9bcb2">红土三站 · 硬地六站</text>',
    ]
    for i, (zh, fname, surface) in enumerate(NINE_MASTERS):
        cx = x0 + (i % cols) * (tw + gap)
        cy = y0 + (i // cols) * (th + gap + 26)
        stroke = "#e08b3a" if surface == "clay" else "#5b9bd5"
        parts.append(
            f'<image href="{_tile_data_uri(fname)}" x="{cx:.1f}" y="{cy:.1f}" '
            f'width="{tw:.1f}" height="{th:.1f}" preserveAspectRatio="xMidYMid slice"/>'
        )
        parts.append(
            f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{tw:.1f}" height="{th:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="3"/>'
        )
        parts.append(
            f'<text x="{cx + tw / 2:.1f}" y="{cy + th + 22:.1f}" text-anchor="middle" '
            f'font-size="24" fill="#e7f3ec">{zh}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# ── ③屏：男子九站 vs 女子十站 ────────────────────────────────────────
#
# ⚠️ 这一屏**故意不用照片**。②屏已经把「九站长什么样」交代完了，这一屏要讲的
# 是**两个集合的关系**——而十三张照片挤进 900x600 每张只剩 180 单位宽，球场
# 根本看不清，还要再背六百多 KB 的 base64。集合关系是结构，画成结构最清楚。
#
# ⚠️ 名单是核过的（2026-08-14，维基 ATP Masters 1000 / WTA 1000 两页）：
# 男子九站里**没有**多哈、迪拜、北京、武汉；女子十站里没有蒙特卡洛、上海、巴黎。
# 也就是说两边的差异不是细节，是小半张表。
MEN_ONLY = ("蒙特卡洛", "上海", "巴黎")
SHARED = ("印第安维尔斯", "迈阿密", "马德里", "罗马", "加拿大", "辛辛那提")
WOMEN_ONLY = ("多哈", "迪拜", "北京", "武汉")


def two_tours_grid() -> str:
    """男子九站与女子十站的重合关系。三段：男子独有 / 共有 / 女子独有。"""
    men, women = "#5b9bd5", "#d98cb3"
    both = "#8fd6a8"
    # ⚠️ 第一版在顶上并排放「男子 9 站」「女子 10 站」两个标题，**暗示了一个
    # 并不存在的左右分栏**——底下其实是上中下三段。计数并进副标题就没这个歧义。
    # 另外第一版「女子独有」那四个换行后，武汉单独掉到末行和页脚字撞在一起，
    # 同样是渲出来才看见的（排版按最后一个元素的落点算，不是按最后一格）。
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">两张表长得不一样</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="25" '
        'fill="#a9bcb2">男子 9 站 · 女子 10 站 · 只有 6 站重合</text>',
    ]
    rows = (
        (MEN_ONLY, men, "男子独有", 126),
        (SHARED, both, "两边都有", 244),
        (WOMEN_ONLY, women, "女子独有", 424),
    )
    for names, colour, label, top in rows:
        parts.append(
            f'<text x="60" y="{top}" font-size="24" fill="#a9bcb2">{label}'
            f"（{len(names)}）</text>"
        )
        for i, zh in enumerate(names):
            bx = 60 + (i % 3) * 262
            by = top + 18 + (i // 3) * 58
            parts.append(
                f'<rect x="{bx}" y="{by}" width="244" height="46" rx="8" '
                f'fill="{colour}" fill-opacity="0.16" stroke="{colour}" stroke-width="2"/>'
            )
            parts.append(
                f'<text x="{bx + 122}" y="{by + 31}" text-anchor="middle" '
                f'font-size="26" fill="#e7f3ec">{zh}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


# ── ④屏：女子那张表一直在变（全片的核心答案） ────────────────────────
#
# ⚠️ 每一行都可核（维基 WTA 1000 tournaments，2026-08-14 查）：
# 2021 创立时是 4 强制 + 5 非强制，而北京和武汉当年直接取消；2022 武汉换成
# 瓜达拉哈拉、多哈和迪拜在 1000 与 500 之间轮换（**那年全年只有 8 站**）；
# 2023 北京回来；2024 全部改成强制、武汉回归、瓜达拉哈拉降回 500、
# 多哈和迪拜同时成为常设 1000——**十站到这一年才定型**。
#
# ⚠️ 故意不讲「为什么会变」（疫情、中国赛季停摆、赛事产权买卖）：原因链太长，
# 每一环都要单独找证据，塞进来会把核心答案冲散。只讲「它变了」这个可核的事实。
WTA_TABLE_YEARS = (
    ("2021", "创立", "北京武汉当年取消", 9),
    ("2022", "武汉换成瓜达拉哈拉", "迪拜不在表上", 8),
    ("2023", "北京回来", "", 9),
    ("2024", "全部改成强制", "十站定型", 10),
)


def wta_table_drift() -> str:
    """女子那张表的逐年变动。2024 那一行高亮——十站到这年才定下来。"""
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">女子那张表一直在变</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="25" '
        'fill="#a9bcb2">十站到 2024 年才定下来</text>',
    ]
    top = 118
    for i, (year, change, note, count) in enumerate(WTA_TABLE_YEARS):
        y = top + i * 108
        final = year == "2024"
        accent = "#8fd6a8" if final else "#a9bcb2"
        parts.append(
            f'<rect x="56" y="{y}" width="788" height="88" rx="10" '
            f'fill="{accent}" fill-opacity="{0.18 if final else 0.07}" '
            f'stroke="{accent}" stroke-width="{3 if final else 1}"/>'
        )
        parts.append(
            f'<text x="96" y="{y + 56}" font-size="40" font-weight="700" '
            f'fill="{accent}">{year}</text>'
        )
        parts.append(
            f'<text x="240" y="{y + 38}" font-size="26" fill="#e7f3ec">{change}</text>'
        )
        if note:
            parts.append(
                f'<text x="240" y="{y + 72}" font-size="22" fill="#a9bcb2">{note}</text>'
            )
        parts.append(
            f'<text x="800" y="{y + 56}" text-anchor="end" font-size="36" '
            f'font-weight="700" fill="{accent}">{count} 站</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


# ── ⑧屏：男子那张表 2028 年也要变 ────────────────────────────────────
#
# ⚠️ 这一屏是全片的落点，而它把「性别对立」那条路堵住了：尺子本来就是人定的，
# 男子那把也在改。维基 ATP Masters 1000 页原文：「On October 23, 2025, the ATP
# announced that a new Masters 1000 tournament (the tenth on the calendar) will
# be held in Saudi Arabia, likely beginning in 2028.」
#
# ⚠️ 「九站没变过」要写 **2009 年至今**（上海顶掉汉堡、马德里改红土那年定的型），
# 不是「二十年」——我第一版写二十年，是没查就说的。
ATP_TABLE_YEARS = (
    ("2009", "上海顶掉汉堡，九站定型", 9),
    ("2026", "十七年没变过", 9),
    ("2028", "沙特加入", 10),
)


def atp_table_future() -> str:
    """男子那张表也不是永远不变——2028 年变成十站。"""
    parts = [
        '<svg viewBox="0 0 900 600" xmlns="http://www.w3.org/2000/svg">',
        '<text x="450" y="40" text-anchor="middle" font-size="34" '
        'font-weight="700" fill="#e7f3ec">男子那把尺子也要改</text>',
        '<text x="450" y="76" text-anchor="middle" font-size="25" '
        'fill="#a9bcb2">2028 年沙特加入，变成十站</text>',
    ]
    top = 140
    for i, (year, note, count) in enumerate(ATP_TABLE_YEARS):
        y = top + i * 126
        future = year == "2028"
        accent = "#e0b13a" if future else "#5b9bd5"
        parts.append(
            f'<rect x="56" y="{y}" width="788" height="100" rx="10" '
            f'fill="{accent}" fill-opacity="{0.20 if future else 0.08}" '
            f'stroke="{accent}" stroke-width="{3 if future else 1}"'
            + (' stroke-dasharray="10 6"' if future else "")
            + "/>"
        )
        parts.append(
            f'<text x="96" y="{y + 62}" font-size="42" font-weight="700" '
            f'fill="{accent}">{year}</text>'
        )
        parts.append(
            f'<text x="252" y="{y + 60}" font-size="28" fill="#e7f3ec">{note}</text>'
        )
        parts.append(
            f'<text x="800" y="{y + 62}" text-anchor="end" font-size="38" '
            f'font-weight="700" fill="{accent}">{count} 站</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)
