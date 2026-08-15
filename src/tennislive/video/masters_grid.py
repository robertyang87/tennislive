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
    ("巴黎", "paris-centre-court.jpg", "hard"),
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
    x0, y0 = 26, 68
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
