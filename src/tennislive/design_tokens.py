"""设计 token——颜色、圆角、字阶、动效的**唯一出处**。

来路（2026-09-27 那轮 UI / VI 整体评审，量出来的，不是感觉）：

- 38 个出画面的文件里有 **185 个不同的 hex**，按感知距离聚类只剩 **73 簇**。
  「近白」一簇 13 个变体散在 22 个文件里；深松针墨分成 4 簇、约 37 个变体
  （#04120d / #06140f / #06100c / #061c14 / #0c1d16 / #10201a / #102d23 ……）。
  全仓库只有示意图在用一份色板（`video/diagram_palette.py`），其余每个文件各配各的。
- **两族绿在抢「品牌色」**：黄绿（oklch 色相 118–130°，#c6f65a 这一支）和翡翠／
  薄荷（151–160°，#4adc8c / #37e29a / #8fd6a8 ……）。一部赛后开麦片子里同时出现
  4 支绿，一部赛场之上里「赢一盘」有 3 种画法。这里定死：**黄绿 = 唯一品牌强调色
  （`primary`），薄荷 = 「赢」（`success` / `SCORE["win_video"]`）**。
- **同一个名字 `INK` 指两件事**：`versus_poster.py` / `outro_page.py` 里是深底
  #04120d，`diagram_palette.py` 里是近白正文 #f4fbf7。所以这儿**不用 INK 这个词**，
  一律用 shadcn 的语义角色名：深底叫 `background`，近白正文叫 `foreground`。
  `diagram_palette.INK` 这个名字为了不动调用方留着，值从这儿的 `foreground` 来。

参照（抄的是**结构**，不是它们的颜色）：

- shadcn/ui theming：**语义角色**（background / foreground / card / muted /
  muted-foreground / primary(+foreground) / destructive / border / input / ring /
  chart-1..5），浅色深色成对定义；中性底只配**一支**强调色；**一个 `--radius`**
  派生整套圆角刻度。
- transitions.dev：默认缓动 ease-out `cubic-bezier(0.22,1,0.36,1)`，按用途定时长
  （按压 120 / 颜色与关闭 150 / 打开 250 ……），关闭比打开快，
  `prefers-reduced-motion` 下把时长压到 .01ms。

⚠️ **第一步所有值取现存值，保证零视觉变化。** 评审里标着「合并」的近重复值
（比如 #06140f → #04120d），这儿只登记了合并**之后**的那个角色值，**没有去改
任何在用的面**——哪个面接 token 是 WP1–WP8 各自的事：值不变的接法要重渲到
**最大差 = 0**；真要合并近重复值，重渲均差 ≤2/255 才合并（连最大差一起报——
均差会把局部改色稀释掉，见 `tools/design_compare_sheet.py`），超过的一律走
账号所有者选择。

⚠️ **账号所有者锁定的组件级 token，照原值收进来，不许「修」**（评审 2.8 共 25 条
决定，和 token 有关的是这几条；台头位置 (70,44)、钩子 94px 与比分板几何、
封面不用遮罩、国旗矩形、屏幕不写标点这些冻结在各自模块的坐标和规则里）：

- 封面比分板完整复刻：赢家长条 #172786、面板 rgb(9,17,38)、字一律纯白、
  赢盘只靠白色粗体 → `SCORE`
- 视频顶栏的赢家和赢盘用薄荷 #4adc8c，跟赛后开麦走（2026-08-18）→
  `SCORE["win_video"]`，判据 `test_design_tokens` 拿它和
  `build_match_reel.TOPBAR_SETWIN_ASS` 逐字节比
- 顶部四色彩条 #c6f65a → #37e29a → #ff5a6a → #4bb8ff → `BRAND_BAR`
- 次级灰别再往暗调（SOFT #cfe6d8 = `muted-foreground`）；一屏只留一个强调色
- 钩子的三层阴影（封面禁用遮罩，这层阴影是唯一的可读性保护）→ `TEXT_SHADOW_HOOK`
- 英文字幕 Inter 24pt SemiBold 44px / 描边 2.5 / 字距 0.6、比分 TL Score、
  转场 0.18 秒溶解且中间不许有黑帧 → 字体参数留在各自模块，溶解时长 →
  `MOTION["video_dissolve_s"]`
- **微信推送那颗红按钮 #ff2442 不进 token**：两个调用处保持字面不动。
  打了 `design-tokens: enforced` 标记的文件里，那一行靠同一行的
  `token-exempt: <理由>` 豁免（判据 `tests/test_design_tokens.py`）。

浅色主题里 `primary` 暂时还是翡翠绿 #087747（评审 Q8 等账号所有者选：
保持翡翠绿 / 黄绿实底配墨色字 / 压暗成 #5a7800 当字色）。**黄绿 #c6f65a 在白底上
只有 1.26:1，浅底上永远不拿它当文字。**

网页端用 `tools/gen_tokens_css.py` 把这里生成成 `dashboard/tokens.css`，
判据要求两边逐字节相等——改这儿就要重跑那个脚本。
"""

from __future__ import annotations

import re

# ── 颜色角色 · 深色（视频、封面、看板、复制页深色）──────────────────────────
#
# 对比度是在 card #0c1d16 上按 WCAG 2 量的（括号里）。带 alpha 的三个角色
# （border / input / ring）写成 8 位 hex，叠在 card 上的近似实色写在注释里。
#
# 同一个值只写一处：按定义就是另一个角色的（ring = primary 加 alpha、
# primary-foreground = background ……）从下面这几个私有常量派生。
_INK_DEEP = "#04120d"
_BRAND = "#c6f65a"
_MINT = "#4adc8c"
_FILL = "#8fd6a8"
_LIGHT_BRAND = "#087747"

DARK: dict[str, str] = {
    "background": _INK_DEEP,           # 合并 #06140f / #06100c / #07140f
    "card": "#0c1d16",                 # 合并 #0d1d16 / #10201a / #061c14
    "muted": "#102d23",                # 凸起、分段轨道；合并 #10271d / #0d2b21
    "hero-glow": "#155a41",            # 只给字卡示意图渐变
    "foreground": "#f4fbf7",           # (16.6) 合并 #ffffff（采访）/ #f4f8f5
    "subtitle-foreground": "#e7f3ec",  # (15.3) 账号所有者登记的「主色近白」
    "muted-foreground": "#cfe6d8",     # (13.3) 次级说明；别再往暗里调
    "subtle-foreground": "#a9bcb2",    # (8.7) 只给元信息
    "border": "#ffffff1a",             # rgba(255,255,255,.10)，叠在 card 上约 #23342e
    "input": "#ffffff26",              # rgba(255,255,255,.15)，约 #30403a
    "ring": _BRAND + "8c",             # rgba(198,246,90,.55)
    "primary": _BRAND,                 # (13.9) 唯一品牌强调色
    "primary-foreground": _INK_DEEP,   # 黄绿底上 15.2
    "success": _MINT,                  # (9.9) 「赢」；合并 #3bd274 / #8cf0ad
    "warning": "#ffd166",              # (12.1) 合并 #ffce6a / #f1c84b
    "destructive": "#ff5a6a",          # (5.7) 合并 #ff7a7a / #ff4d5e
    "info": "#4bb8ff",                 # (8.0) 合并 #75b7ff
    "fill": _FILL,                     # 只当底，不当字
}

#: 状态芯片的底：状态色 14% 混进 card。⚠️ **只给芯片用，不给整块面用**——
#: 整张卡垫 14% 红在墨绿上会发棕（「低饱和暖色压在深绿上会发脏」）。
#: 大面积表达失败：中性卡 + 55% 红细环 + 4px 左侧色轨 + ✕ 芯片。
DARK_CHIP: dict[str, str] = {
    "success": "#143927",      # 文字对比 7.2
    "warning": "#2d3722",      # 8.7
    "destructive": "#2d2623",  # 4.9
    "info": "#143437",         # 6.1
}

# ── 颜色角色 · 浅色（推送正文、复制页、看板浅色若要做）─────────────────────
LIGHT: dict[str, str] = {
    "background": "#f6f7f4",           # 合并 #f4f7f5
    "card": "#ffffff",
    "foreground": "#17251f",           # 白底 15.9；合并 #1c2b26 / #25342e / 标题 #102d23
    "muted-foreground": "#5f6f68",     # 白底 5.30 / 底色上 4.93；替换 #7a8580（只有 3.82）
    "border": "#e6ebe8",
    "input": "#d8e2dc",
    "primary": _LIGHT_BRAND,           # 白底 5.61；合并 #0a7d43。等 Q8
    "primary-foreground": "#ffffff",   # 翡翠绿底上 5.61
    "secondary": "#102d23",            # 视频按钮，配白字 14.8
    "secondary-foreground": "#ffffff",
    "destructive": "#c0392b",          # 白底 5.44
    "ring": _LIGHT_BRAND,              # 等于 primary，2px 描边、2px 偏移
}

#: 图表单色阶：只有 chart-1 带强调色，和「一屏只留一个强调色」一致。
CHART: tuple[str, str, str, str, str] = (
    _BRAND, _FILL, "#8b9892", "#5d6b65", "#3a4a44",
)

#: 顶部四色彩条（账号所有者锁定）。(颜色, 位置%)。
BRAND_BAR: tuple[tuple[str, int], ...] = (
    (_BRAND, 0), ("#37e29a", 34), ("#ff5a6a", 67), ("#4bb8ff", 100),
)
#: 和 `versus_poster` / `outro_page` / `explainer` 等处 `.bar` 的那串逐字节相同。
BRAND_BAR_CSS = "linear-gradient(90deg," + ",".join(
    f"{c} {p}%" for c, p in BRAND_BAR) + ")"

#: 比分组件（账号所有者锁定，照原值收进来）。
#:
#: - `win_bar` / `panel_rgb` / `ink`：封面比分板完整复刻美网官方赛果图，
#:   逐个从参考图上量的（`versus_poster.SCORE_BLUE` / `SCORE_PANEL_RGB` /
#:   `SCORE_INK`）。`panel_rgb` 是 `"r,g,b"` 串，调用处拼成
#:   `rgba({panel_rgb},α)`——面板是一条半透明长坡，不是一块实色。
#: - `dash`：比分里的连字符和抢七小分（`.setdash` / `.tb`，顶栏 `TOPBAR_SETDASH_ASS`）。
#: - `win_video`：**视频**顶栏的赢家和赢盘，2026-08-18 改成跟赛后开麦走的薄荷，
#:   和封面比分板（白色粗体）不是同一支——这条分叉是认领过的。
SCORE: dict[str, str] = {
    "win_bar": "#172786",
    "panel_rgb": "9,17,38",
    "ink": "#ffffff",
    "dash": "#93a79c",
    "win_video": _MINT,   # = DARK["success"]：视频里凡是薄荷都在说「这一方赢了」
}

# ── 圆角 ────────────────────────────────────────────────────────────────
#: 网页：一个 `--radius`（10）派生整套。按钮／输入框／toast 用 md；卡片、指标
#: 用 lg；首屏、面板用 xl；芯片、分段控件用 full。嵌套一层就降一档。
#: 画布上的圆角（海报／比分板／国旗 0、国旗描边 3、信息盒 12、药丸 999）
#: 跟着各自模块的冻结几何走，不在这儿。
RADIUS_WEB: dict[str, int] = {
    "base": 10, "sm": 6, "md": 8, "lg": 10, "xl": 14, "full": 999, "hairline": 2,
}

# ── 网页字阶 ──────────────────────────────────────────────────────────────
#: 最小 12（看板上 9–10px 的 73 个文字节点就是这条要拦的）。字重只用 400/500/600
#: （苹方最粗到 Semibold），数字一律 `tabular-nums`。中文标题不做负字距。
TEXT_WEB: dict[str, int] = {
    "xs": 12, "sm": 13, "base": 15, "lg": 18, "xl": 22, "2xl": 28,
}
#: 网页 UI 字体栈。⚠️ 不用 Google Fonts，也不用 GitHub 托管的字体（账号所有者在国内）。
FONT_WEB = '-apple-system,"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif'

# ── 阴影 ──────────────────────────────────────────────────────────────────
#: 网页层级。深色靠 1px 白描边分层，浅色靠极淡的黑。
SHADOW_WEB: dict[str, dict[str, str]] = {
    "dark": {
        "card": "0 0 0 1px rgba(255,255,255,.10)",
        "raised": ("0 0 0 1px rgba(255,255,255,.13),0 1px 2px rgba(0,0,0,.2),"
                   "0 2px 6px rgba(0,0,0,.2)"),
        "overlay": "0 0 0 1px rgba(255,255,255,.15),0 8px 28px rgba(0,0,0,.34)",
    },
    "light": {
        "card": "0 0 0 1px rgba(0,0,0,.06),0 1px 3px rgba(0,0,0,.04)",
        "overlay": ("0 4px 42px rgba(0,0,0,.06),0 2px 6px rgba(0,0,0,.05),"
                    "0 0 0 1px rgba(0,0,0,.06)"),
    },
}
#: 画布 · 封面钩子（`.storytitle`）的三层阴影，维持现状。
TEXT_SHADOW_HOOK = ("0 2px 6px rgba(0,0,0,.9),0 6px 30px rgba(0,0,0,.85),"
                    "0 0 60px rgba(6,28,20,.7)")
#: 画布 · 台头副标题等「框架」文字（`.topic`）。
TEXT_SHADOW_CHROME = "0 2px 10px rgba(0,0,0,.9),0 0 24px rgba(6,28,20,.8)"

# ── 动效 ──────────────────────────────────────────────────────────────────
#: 网页时长（毫秒）和缓动；视频溶解（秒）。
#:
#: - 按压 `scale(.97)` 用 `press_ms`；hover / 颜色 / 关闭用 `quick_ms`；打开、
#:   tab 指示条用 `fast_ms`——**关闭比打开快**。
#: - `ease_out` 是默认；`ease_spring` 只用在入场（弹一下），视频里默认不用回弹。
#: - 永远列出具体属性，不写 `transition: all`；hover 只写在
#:   `@media (hover:hover) and (pointer:fine)` 里（微信是触屏，:hover 会粘住）。
#: - `video_dissolve_s`：所有接缝 `xfade=fade` + `acrossfade` 0.18 秒，
#:   **中间一帧黑都不许有**（账号所有者规则）。
MOTION: dict[str, int | float | str] = {
    "press_ms": 120,
    "quick_ms": 150,
    "fast_ms": 250,
    "medium_ms": 350,
    "slow_ms": 400,
    "emphasis_ms": 500,
    "stagger_ms": 40,
    "ease_out": "cubic-bezier(0.22,1,0.36,1)",
    "ease_spring": "cubic-bezier(0.34,1.35,0.64,1)",
    "video_dissolve_s": 0.18,
}

# ── 换算 ──────────────────────────────────────────────────────────────────
_HEX6 = re.compile(r"#?([0-9a-fA-F]{6})")


def _hex6(hex_colour: str) -> str:
    """'#rrggbb' → 'rrggbb'（小写）。带 alpha 的 8 位 hex 不收：它不是实色。"""
    m = _HEX6.fullmatch(hex_colour.strip())
    if not m:
        raise ValueError(
            f"要 #rrggbb 实色，拿到 {hex_colour!r}——带 alpha 的角色"
            "（border / input / ring）不能当实色用")
    return m.group(1).lower()


def rgb(hex_colour: str) -> tuple[int, int, int]:
    """'#4adc8c' → (74, 220, 140)。"""
    h = _hex6(hex_colour)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ass(hex_colour: str, alpha: int = 0) -> str:
    """CSS 的 '#RRGGBB' → ASS 样式行用的 '&HAABBGGRR'。

    ⚠️ **字节序和 CSS 相反**（BGR），而且 ASS 的 alpha 是**反的**：0 = 不透明、
    255 = 全透明。赛后开麦中文字幕那支淡黄绿 #c3dc74，就是当初把 #74dcc3 的
    字节序写反了得来的——这正是这个函数存在的理由。
    """
    if not 0 <= alpha <= 255:
        raise ValueError(f"ASS alpha 是 0–255 的整数（0 = 不透明），拿到 {alpha!r}")
    r, g, b = rgb(hex_colour)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ass_inline(hex_colour: str) -> str:
    """CSS 的 '#RRGGBB' → ASS 行内颜色标签 '{\\c&HBBGGRR&}'（不带 alpha 字节）。"""
    r, g, b = rgb(hex_colour)
    return f"{{\\c&H{b:02X}{g:02X}{r:02X}&}}"


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    """WCAG 2 相对亮度。"""
    r, g, b = (_linear(c) for c in rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    """WCAG 2 对比度（1–21），与前后景顺序无关。"""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# ── CSS ───────────────────────────────────────────────────────────────────
def _decl(name: str, value: object) -> str:
    return f"  --{name}: {value};"


def css_vars(theme: str = "dark") -> str:
    """一个主题的 CSS 自定义属性块。

    - `dark` → `:root { … }`：颜色角色 + 状态芯片 + 图表 + 彩条 + 阴影，外加
      与主题无关的圆角、字阶、字体、动效（只在这一块写一次）。
    - `light` → `:root[data-theme="light"] { … }`：只覆盖颜色和阴影。选择器
      特异性高一档，和源码顺序无关。**不挂 `prefers-color-scheme`**：
      看板要不要跟随系统是账号所有者的 Q10，这里只提供、不替他打开。

    ⚠️ 浅色只定义了 `LIGHT` 里那几个角色；`muted` / `success` / 芯片这些
    在浅色块里没有覆盖，会继承深色值——浅色面只许用 `LIGHT` 里有的角色。
    """
    if theme == "dark":
        lines = [":root {", "  color-scheme: dark;"]
        lines += [_decl(k, v) for k, v in DARK.items()]
        lines += [_decl(f"{k}-chip", v) for k, v in DARK_CHIP.items()]
        lines += [_decl(f"chart-{i}", v) for i, v in enumerate(CHART, 1)]
        lines.append(_decl("brand-bar", BRAND_BAR_CSS))
        lines += [_decl(f"shadow-{k}", v) for k, v in SHADOW_WEB["dark"].items()]
        lines.append(_decl("radius", f"{RADIUS_WEB['base']}px"))
        lines += [_decl(f"radius-{k}", f"{v}px")
                  for k, v in RADIUS_WEB.items() if k != "base"]
        lines += [_decl(f"text-{k}", f"{v}px") for k, v in TEXT_WEB.items()]
        lines.append(_decl("font-sans", FONT_WEB))
        for k, v in MOTION.items():
            if k.endswith("_ms"):
                lines.append(_decl(f"duration-{k[:-3]}", f"{v}ms"))
            elif k.startswith("ease_"):
                lines.append(_decl(k.replace("_", "-"), v))
            # video_dissolve_s 是视频的，不进网页
    elif theme == "light":
        lines = [':root[data-theme="light"] {', "  color-scheme: light;"]
        lines += [_decl(k, v) for k, v in LIGHT.items()]
        lines += [_decl(f"shadow-{k}", v) for k, v in SHADOW_WEB["light"].items()]
    else:
        raise ValueError(f"theme 只认 dark / light，拿到 {theme!r}")
    lines.append("}")
    return "\n".join(lines) + "\n"


#: `prefers-reduced-motion: reduce` 下把时长压到 .01ms（不是 0：有的页面靠
#: `transitionend` 收尾，0 会让它不触发）。
REDUCED_MOTION_CSS = """@media (prefers-reduced-motion: reduce) {
  :root {
{durations}
  }
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}
""".replace("{durations}", "\n".join(
    f"    --duration-{k[:-3]}: .01ms;" for k in MOTION if k.endswith("_ms")))

TOKENS_CSS_HEADER = (
    "/* 由 tools/gen_tokens_css.py 从 src/tennislive/design_tokens.py 生成——别手改。\n"
    "   改颜色、圆角、字阶、动效去改那个模块，再重跑脚本；\n"
    "   判据 tests/test_design_tokens.py 要求两边逐字节相等。 */\n"
)


def tokens_css() -> str:
    """`dashboard/tokens.css` 的全文：深色 + 浅色 + reduced-motion。"""
    return "\n".join((TOKENS_CSS_HEADER, css_vars("dark"), css_vars("light"),
                      REDUCED_MOTION_CSS))
