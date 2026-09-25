"""顶栏第一行最前面那个小图标：赛后开麦是**麦克风**，赛场之上是**透视的球场**。

账号所有者 2026-09-25 看完示意图定的（「就用 a 吧」）：赛后开麦顶栏原来那道
品牌绿竖条 `▍` 换成麦克风；赛场之上顶栏原来**什么都没有**，加一个转播机位
看过去的透视球场——和顶栏正下方的比赛画面是同一个角度。

⚠️ **为什么画成 ASS 矢量（`\\p1`），不用字形也不用贴 PNG**：

- 字形：`▍` 在得意黑里就没有，靠 fontconfig 回退才画得出来，而回退在 runner
  上不保证（`test_顶栏那个绿方块不许赌字体回退` 记的就是这件事）。麦克风、
  球场更没有哪支仓库字体带
- 贴 PNG：得先量出整行文字多宽才知道贴在哪儿，而那一行是居中的——两处
  分开算必分叉，分叉的样子是「图标和文字之间忽宽忽窄」
- 矢量是这一行里的一段，libass 把**图标＋文字当一个整体居中**，不用另算位置

⚠️ **俯视的长方形球场试过，不用**：缩到顶栏那个尺寸，挨着中文读起来像
「目」「田」字。透视（上窄下宽的梯形）才一眼是球场。

⚠️ **网球（方案 B）没选**：比分板上标发球方的就是一个绿色网球，左上角品牌
logo 本身也是一个网球——一屏三个相似的绿球，意思会混。

几何全是按图标高 `h` 的比例写的，渲出来的尺寸由调用方给（两条线各自按
自己那一行的字号定）。**颜色不在这儿**：调用方传自己那条线的强调色标签，
两条线都用 `_MARK_COLOUR` 那一支绿（`test_顶栏赢家色跟着赛后开麦走` 钉着）。
"""

from __future__ import annotations

import math

MIC = "mic"
COURT = "court"

#: 图标宽 ÷ 高。麦克风是竖的，球场是横着看过去的梯形。
ASPECT = {MIC: 0.62, COURT: 1.25}

#: 图标和后面文字之间的空隙，按图标高的比例。**做进了这段矢量的步进里**
#: （末尾那个 `m <宽+空隙> 0`）：libass 按矢量里最远的那个点算这一段占多宽，
#: 实测一个孤立的 move 点就算数（40 宽的方块后面接 `m 70 0`，文字从 +70 起）。
GAP_RATIO = 0.36

Point = tuple[float, float]


def _area(poly: list[Point]) -> float:
    return sum(x0 * y1 - x1 * y0
               for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1])) / 2


def _oriented(poly: list[Point], hole: bool = False) -> list[Point]:
    """统一绕向。libass 按**非零环绕**填充：同向的形状叠在一起照样是实的，
    反向的那一块挖成洞（实测：方块里套一个反向的小方块就是个框）。"""
    positive = _area(poly) > 0
    return poly if positive != hole else poly[::-1]


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[Point]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _bar(p: Point, q: Point, t: float) -> list[Point]:
    """一条粗 t 的线段，画成四边形（ASS 只有填充，没有描边）。"""
    (x0, y0), (x1, y1) = p, q
    length = math.hypot(x1 - x0, y1 - y0) or 1.0
    nx, ny = -(y1 - y0) / length * t / 2, (x1 - x0) / length * t / 2
    return [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
            (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]


def _capsule(cx: float, top: float, bottom: float, r: float,
             steps: int = 10) -> list[Point]:
    """竖着的胶囊（话筒头）：上下两个半圆夹一段直边。"""
    pts: list[Point] = []
    for i in range(steps + 1):              # 上半圆，从左到右
        a = math.pi + math.pi * i / steps
        pts.append((cx + r * math.cos(a), top + r + r * math.sin(a)))
    for i in range(steps + 1):              # 下半圆，从右到左
        a = math.pi * i / steps
        pts.append((cx + r * math.cos(a), bottom - r + r * math.sin(a)))
    return pts


def _half_ring(cx: float, cy: float, rx: float, ry: float, t: float,
               steps: int = 14) -> list[Point]:
    """下半个椭圆环（话筒的 U 形支架）。"""
    outer = [(cx + (rx + t / 2) * math.cos(math.pi * i / steps),
              cy + (ry + t / 2) * math.sin(math.pi * i / steps))
             for i in range(steps + 1)]
    inner = [(cx + (rx - t / 2) * math.cos(math.pi * i / steps),
              cy + (ry - t / 2) * math.sin(math.pi * i / steps))
             for i in range(steps, -1, -1)]
    return outer + inner


def _mic(h: float) -> tuple[list[list[Point]], list[list[Point]]]:
    w = h * ASPECT[MIC]
    cx, lw = w / 2, h * 0.085
    head_r = w * 0.24
    solids = [
        _capsule(cx, 0.0, h * 0.60, head_r),
        _half_ring(cx, h * 0.40, w * 0.44 - lw / 2, h * 0.36 - lw / 2, lw),
        _rect(cx - lw / 2, h * 0.76, cx + lw / 2, h * 0.93),
        _rect(cx - w * 0.26, h * 0.91, cx + w * 0.26, h),
    ]
    # 话筒头上的三道格栅：挖掉的洞，不是另画一层深色（深色得跟着背景变）
    holes = [_rect(cx - head_r * 0.55, h * y - lw * 0.28,
                   cx + head_r * 0.55, h * y + lw * 0.28)
             for y in (0.19, 0.30, 0.41)]
    return solids, holes


def _court(h: float) -> tuple[list[list[Point]], list[list[Point]]]:
    w = h * ASPECT[COURT]
    lw = h * 0.085
    top_l, top_r = w * 0.27, w * 0.73
    bot_l, bot_r = lw / 2, w - lw / 2
    y0, y1 = lw / 2, h - lw / 2

    def x_at(t: float, left: bool) -> float:
        a, b = (top_l, bot_l) if left else (top_r, bot_r)
        return a + (b - a) * t

    def y_at(t: float) -> float:
        return y0 + (y1 - y0) * t

    thin = lw * 0.62
    net_t = 0.42           # 透视：远端那半场画得短一些
    solids = [
        _bar((top_l, y0), (top_r, y0), lw),          # 远端底线
        _bar((bot_l, y1), (bot_r, y1), lw),          # 近端底线
        _bar((top_l, y0), (bot_l, y1), lw),          # 双打边线
        _bar((top_r, y0), (bot_r, y1), lw),
        # 球网：出头（网柱在界外），而且比别的线粗——缺了它就只是个梯形
        _bar((x_at(net_t, True) - lw * 0.9, y_at(net_t)),
             (x_at(net_t, False) + lw * 0.9, y_at(net_t)), lw * 1.5),
        _bar((w / 2, y_at(0.20)), (w / 2, y_at(0.70)), thin),   # 中线
    ]
    for t in (0.20, 0.70):                                       # 发球线
        xl, xr = x_at(t, True), x_at(t, False)
        k = (xr - xl) * 0.12
        solids.append(_bar((xl + k, y_at(t)), (xr - k, y_at(t)), thin))
    for left in (True, False):                                   # 单打边线
        xt, xb = x_at(0, left), x_at(1, left)
        solids.append(_bar((xt + (w / 2 - xt) * 0.12, y0),
                           (xb + (w / 2 - xb) * 0.12, y1), thin))
    return solids, []


_SHAPES = {MIC: _mic, COURT: _court}


def icon_width(name: str, h: float) -> float:
    return h * ASPECT[name]


def icon_advance(name: str, h: float) -> float:
    """这一段在行里占多宽（图标本身＋和文字之间的空隙）。量顶栏宽度用它。"""
    return icon_width(name, h) + h * GAP_RATIO


def drawing(name: str, h: float) -> str:
    """ASS 矢量指令（`\\p1` 下的那一串），末尾带着空隙那个 move 点。"""
    solids, holes = _SHAPES[name](h)
    parts = []
    for poly, hole in [(p, False) for p in solids] + [(p, True) for p in holes]:
        pts = _oriented(poly, hole)
        head, rest = pts[0], pts[1:]
        parts.append(f"m {head[0]:.1f} {head[1]:.1f} l "
                     + " ".join(f"{x:.1f} {y:.1f}" for x, y in rest))
    parts.append(f"m {icon_advance(name, h):.1f} 0")
    return " ".join(parts)


#: 得意黑的字面中线在基线上方多高（按字号的比例）。**量出来的**：54px 下
#: 「2026 WTA500 新加坡站 1/4决赛」整行的墨从 y44 到 y87、基线在 y83，
#: 中线在基线上方 17.5px ＝ 0.324 × 54。矢量的底边由 libass 对到基线上，
#: 要让图标和文字上下居中，就往下挪 `h/2 − 0.324 × 字号`。
HEAD_CENTRE_ABOVE_BASELINE = 0.324


def centred_pbo(h: float, font_px: float) -> float:
    """让高 h 的图标和这一行得意黑上下居中要往下挪多少（`\\pbo`）。"""
    return round(h / 2 - HEAD_CENTRE_ABOVE_BASELINE * font_px, 1)


def icon_ass(name: str, h: float, tags: str, *, font_px: float) -> str:
    r"""整段 ASS：`{标签\p1\pbo…}矢量{\r\p0}`。

    `tags` 是调用方那一段本来就要写的覆盖标签（颜色，第一段还带定位）。
    竖直落点：libass 把矢量的底边对到文字基线上，所以按字号算一个
    `\pbo` 让图标和文字上下居中（`centred_pbo`）——判据真渲一帧量两块墨
    的中线是不是对得上。
    ⚠️ 收尾写 `{\\r\\p0}`：退出矢量模式的同时把颜色、描边这些复位回这一行的
    样式——不然后面的文字跟着变绿（ASS 的覆盖是粘连的）。赛后开麦那条线还有
    一条判据要求**每一段都以 `\\r` 开头**，所以 `\\r` 写在前面。
    ⚠️ 描边和阴影显式清零：这一行的 Style 若带 `Outline`，矢量会被描一圈
    深色边，图标看起来比文字粗一圈。
    """
    pbo = centred_pbo(h, font_px)
    return (rf"{{{tags}\bord0\shad0\p1\pbo{pbo:g}}}"
            f"{drawing(name, h)}{{\\r\\p0}}")
