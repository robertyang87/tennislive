"""设计 token——颜色、圆角、字阶、动效的**唯一出处**。

2026-10-04 用户明确授权全栏目深蓝设计；下列墨绿迁移说明为历史档案，当前背景以 DARK 与 CARD_BACKGROUND_CSS 为准。

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

⚠️ **角色值是评审 2.1 / 2.2 合并表定的目标值，不全是现存值。** 比如 `card`
#0c1d16 仓库里还没有哪个面用过；`background` #04120d 和看板 #06100c、赛后开麦
#06140f、`index.html` #07140f 都不一样；看板的状态色 #3bd274 / #ffce6a / #ff7a7a /
#75b7ff、次级灰 #91a99b 也都和这儿不同。WP0 没有去改任何在用的面——哪个面接 token
是 WP1–WP8 各自的事，分两种：

- **值不变、只换出处**（示意图色板就是这种）：重渲到**最大差 = 0**。
- **值变了**（把 #06100c 接到 `background` 上也算）：这是**改值**，不是换出处——
  出 `tools/design_compare_sheet.py` 的「现状｜方案」对比图，报**最大差和有差像素
  占比**，别拿均差放行（WP0 的反向验证：一处条形改色，均差才 0.173/255，最大差 25、
  6.27% 的像素变了）。看得出差别的一律走账号所有者选择。

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

**浅色主题是完整的**（2026-09-27 账号所有者 Q8 / Q10 定了之后补齐）：`DARK` 里的
每个角色在 `LIGHT` 里都有值，只有 `DARK_ONLY` 那三个画布专用的角色（示意图渐变、
视频字幕、示意图填充）和 `CHART` 声明成「只有深色」。

- **Q8：浅底上黄绿是「实底」，不是字色。** 药丸、按钮用黄绿 #c6f65a 实底配墨色字
  #04120d（15.2:1）；链接用中性灰（= `muted-foreground` #5f6f68）。**黄绿 #c6f65a
  在白底上只有 1.26:1，浅底上永远不拿它当文字**——判据把浅色所有字色角色都量一遍。
  原来浅色 `primary` 的翡翠绿 #087747 腾出来当浅色的 `success`（白底 5.61）。
- **Q10：看板跟随系统。** `tokens_css()` 按消费方声明的默认主题生成：跟随系统的
  浅色写在 `@media` **外面**当兜底、深色在 `prefers-color-scheme: dark` 里覆盖它
  （`data-theme` 钉死时都让位）；**裸 `:root` 上不写 `color-scheme`**——哪个消费方
  默认深色，要在 `tools/gen_tokens_css.py` 的消费方表里写明。

网页端用 `tools/gen_tokens_css.py` 把这里生成成 CSS（现在只有 `dashboard/tokens.css`），
变量一律带 `--tl-` 前缀（`css_var()`）：看板 `styles.css` 自己有 `--muted`（**字色**
#91a99b）和 `--radius`（20px），和这里的 `muted`（**面**）/ `radius`（10）同名不同义，
不带前缀，谁在层叠里赢谁就把对方改掉。判据要求生成物和模块逐字节相等——改这儿就要
重跑那个脚本。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType

# 所有表都是只读的（`MappingProxyType`）：模块级的 dict 谁都能顺手改一个值，
# 改了之后整个进程里的面一起变，而且不报错。要派生新值就 `dict(DARK)` 拷一份。

# ── 颜色角色 · 深色（视频、封面、看板、复制页深色）──────────────────────────
#
# 对比度是在 card #0c1d16 上按 WCAG 2 量的（括号里）。带 alpha 的三个角色
# （border / input / ring）写成 8 位 hex，叠在 card 上的近似实色写在注释里。
#
# 同一个值只写一处：按定义就是另一个角色的（ring = primary 加 alpha、
# primary-foreground = background ……）从下面这几个私有常量派生。
_INK_DEEP = "#080e1d"     # 2026-10-04：全栏目蓝黑底，参考图只作方向，重新设计。
_BRAND = "#c6f65a"
_MINT = "#4adc8c"
_FILL = "#8fd6a8"
_EMERALD = "#087747"      # 浅底上的「赢／成功」字色（白底 5.61）；合并 #0a7d43
_RAISED = "#20324e"       # 柔和的蓝色信息面；也是浅色主题里那颗深色视频按钮
_FG = "#f4fbf7"
_FG_MUTED = "#cfe6d8"
_FG_LIGHT = "#17251f"
_FG_MUTED_LIGHT = "#5f6f68"

DARK: Mapping[str, str] = MappingProxyType({
    "background": _INK_DEEP,           # 合并 #06140f / #06100c / #07140f
    "card": "#15243a",                 # 蓝黑底上的柔和藏青层次
    "muted": _RAISED,                  # 凸起、分段轨道；合并 #10271d / #0d2b21
    "hero-glow": "#304d76",            # 低饱和蓝光，不用品牌绿铺大面积背景
    "foreground": _FG,                 # (16.6) 合并 #ffffff（采访）/ #f4f8f5
    "subtitle-foreground": "#e7f3ec",  # (15.3) 账号所有者登记的「主色近白」（DARK_ONLY）
    "muted-foreground": _FG_MUTED,     # (13.3) 次级说明；别再往暗里调
    "subtle-foreground": "#a9bcb2",    # (8.7) 只给元信息
    "border": "#ffffff1a",             # 白 26/255 ≈ .10，叠在 card 上约 #23342e
    "input": "#ffffff26",              # 白 38/255 ≈ .15，约 #30403a
    "ring": _BRAND + "8c",             # 黄绿 140/255 ≈ .55
    "primary": _BRAND,                 # (13.9) 唯一品牌强调色
    "primary-foreground": _INK_DEEP,   # 黄绿底上 15.2
    "secondary": _RAISED,              # 次级按钮 = 凸起面配正文色（shadcn 的 secondary）
    "secondary-foreground": _FG,       # 凸起面上 14.1
    "link": _FG_MUTED,                 # 链接用中性灰，品牌色只给按钮和药丸（Q8 的道理）
    "success": _MINT,                  # (9.9) 「赢」；合并 #3bd274 / #8cf0ad
    "warning": "#ffd166",              # (12.1) 合并 #ffce6a / #f1c84b
    "destructive": "#ff5a6a",          # (5.7) 合并 #ff7a7a / #ff4d5e
    "info": "#4bb8ff",                 # (8.0) 合并 #75b7ff
    "fill": _FILL,                     # 只当底，不当字（DARK_ONLY）
})

# 全栏目原生图卡的统一底图：右上柔光、正文区收暗。背景蓝是中性承托，
# 黄绿仍只点亮品牌/重点，薄荷仍表示赢盘；不能再用它们洗绿整张卡。
CARD_BACKGROUND_CSS = (
    f"radial-gradient(120% 85% at 100% 0%,{DARK['hero-glow']}70 0%,"
    f"{DARK['hero-glow']}00 65%),"
    f"linear-gradient(160deg,{DARK['card']} 0%,{DARK['background']} 65%)"
)

#: 只有深色、浅色主题里**故意没有**的角色——全是画布（视频、字卡）专用的，
#: 而画布永远是深底。网页浅色面上用到它们，就是用错了地方（CSS 里浅色块不声明
#: 它们，`var()` 落空，一眼看得出，而不是悄悄继承一个深色值）。`CHART` 同理，
#: 见下。判据要求：`LIGHT` 的角色 = `DARK` 的角色 − `DARK_ONLY`，一个不多一个不少。
DARK_ONLY: frozenset[str] = frozenset({"hero-glow", "subtitle-foreground", "fill"})

#: 状态芯片的底：状态色 14% 混进 card。⚠️ **只给芯片用，不给整块面用**——
#: 整张卡垫 14% 红在墨绿上会发棕（「低饱和暖色压在深绿上会发脏」）。
#: 大面积表达失败：中性卡 + 55% 红细环 + 4px 左侧色轨 + ✕ 芯片。
DARK_CHIP: Mapping[str, str] = MappingProxyType({
    "success": "#143927",      # 文字对比 7.2
    "warning": "#2d3722",      # 8.7
    "destructive": "#2d2623",  # 4.9
    "info": "#143437",         # 6.1
})

# ── 颜色角色 · 浅色（推送正文、复制页、看板跟随系统时）──────────────────────
#
# 对比度按 WCAG 2 量，括号里是「白底 / 底色 #f6f7f4 上」。状态色没有现存的浅色值
# 可取的（warning / info），是把深色那支**同色相（oklch）压暗**到两种浅底和自己的
# 芯片上都 ≥4.5 的第一档——不是另挑一支颜色。
LIGHT: Mapping[str, str] = MappingProxyType({
    "background": "#f6f7f4",           # 合并 #f4f7f5
    "card": "#ffffff",
    "muted": "#eef2ef",                # 凸起、分段轨道；次级字在它上面 4.69
    "foreground": _FG_LIGHT,           # (15.9 / 14.8) 合并 #1c2b26 / #25342e / 标题 #102d23
    "muted-foreground": _FG_MUTED_LIGHT,  # (5.30 / 4.93) 替换 #7a8580（只有 3.82）
    # 浅底上没有第三级灰的位置：≥4.5 的灰和 #5f6f68 肉眼分不开，再浅就不过 AA。
    # 所以元信息和次级说明同值——「文字最多两级」本来就是规矩。
    "subtle-foreground": _FG_MUTED_LIGHT,
    "border": "#e6ebe8",
    "input": "#d8e2dc",
    # 焦点环：黄绿在白底上 1.26，过不了非文字的 3:1，所以浅色用墨色（14.8）。
    "ring": _FG_LIGHT,
    "primary": _BRAND,                 # Q8：黄绿**实底**（药丸、按钮），永远不当字
    "primary-foreground": _INK_DEEP,   # Q8：黄绿底上的墨色字 15.2
    "secondary": _RAISED,              # 视频按钮，配白字 14.8
    "secondary-foreground": "#ffffff",
    "link": _FG_MUTED_LIGHT,           # Q8：链接用中性灰
    "success": _EMERALD,               # (5.61 / 5.22) 原来浅色 primary 的翡翠绿
    "warning": "#846405",              # (5.52 / 5.13) #ffd166 同色相压暗
    "destructive": "#c0392b",          # (5.44 / 5.06)
    "info": "#0a6ea4",                 # (5.56 / 5.17) #4bb8ff 同色相压暗
})

#: 浅色状态芯片的底：状态色 **12%** 混进白卡（sRGB）。深色是 14%，浅色少两个点：
#: 14% 会让 destructive 的字在自己芯片上掉到 4.40（不过 AA），12% 四个都 ≥4.5。
LIGHT_CHIP: Mapping[str, str] = MappingProxyType({
    "success": "#e1efe9",      # 文字对比 4.74
    "warning": "#f0ece1",      # 4.67
    "destructive": "#f7e7e6",  # 4.54
    "info": "#e2eef4",         # 4.70
})

#: 图表单色阶：只有 chart-1 带强调色，和「一屏只留一个强调色」一致。
#: **只有深色**：浅底上 chart-1 的黄绿条只有 1.26:1，过不了图形的 3:1；
#: 现在也没有浅色的图表。要做先定一套浅色色阶，再加进 `LIGHT` 那一侧。
CHART: tuple[str, str, str, str, str] = (
    _BRAND, _FILL, "#8b9892", "#5d6b65", "#3a4a44",
)

#: 顶部四色彩条（账号所有者锁定）。(颜色, 位置%)。和主题无关。
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
SCORE: Mapping[str, str] = MappingProxyType({
    "win_bar": "#172786",
    "panel_rgb": "9,17,38",
    "ink": "#ffffff",
    "dash": "#93a79c",
    "win_video": _MINT,   # = DARK["success"]：视频里凡是薄荷都在说「这一方赢了」
})

# ── 圆角 ────────────────────────────────────────────────────────────────
#: 网页：一个 `--tl-radius`（10）派生整套。按钮／输入框／toast 用 md；卡片、指标
#: 用 lg；首屏、面板用 xl；芯片、分段控件用 full。嵌套一层就降一档。
#: 画布上的圆角（海报／比分板／国旗 0、国旗描边 3、信息盒 12、药丸 999）
#: 跟着各自模块的冻结几何走，不在这儿。
RADIUS_WEB: Mapping[str, int] = MappingProxyType({
    "base": 10, "sm": 6, "md": 8, "lg": 10, "xl": 14, "full": 999, "hairline": 2,
})

# ── 网页字阶 ──────────────────────────────────────────────────────────────
#: 最小 12（看板上 9–10px 的 73 个文字节点就是这条要拦的）。字重只用 400/500/600
#: （苹方最粗到 Semibold），数字一律 `tabular-nums`。中文标题不做负字距。
TEXT_WEB: Mapping[str, int] = MappingProxyType({
    "xs": 12, "sm": 13, "base": 15, "lg": 18, "xl": 22, "2xl": 28,
})
#: 网页 UI 字体栈。⚠️ 不用 Google Fonts，也不用 GitHub 托管的字体（账号所有者在国内）。
FONT_WEB = '-apple-system,"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif'

# ── 阴影 ──────────────────────────────────────────────────────────────────
#: 网页层级。深色靠 1px 白描边分层，浅色靠极淡的黑。两个主题的层级一一对应。
#: 浅色的 `raised` 没有现存值可取（评审 2.6 只给了浅色的卡片和浮层），按「卡片
#: 和浮层之间一档」补的：描边比卡片深一点，加两层短投影。
SHADOW_WEB: Mapping[str, Mapping[str, str]] = MappingProxyType({
    "dark": MappingProxyType({
        "card": "0 0 0 1px rgba(255,255,255,.10)",
        "raised": ("0 0 0 1px rgba(255,255,255,.13),0 1px 2px rgba(0,0,0,.2),"
                   "0 2px 6px rgba(0,0,0,.2)"),
        "overlay": "0 0 0 1px rgba(255,255,255,.15),0 8px 28px rgba(0,0,0,.34)",
    }),
    "light": MappingProxyType({
        "card": "0 0 0 1px rgba(0,0,0,.06),0 1px 3px rgba(0,0,0,.04)",
        "raised": ("0 0 0 1px rgba(0,0,0,.08),0 1px 2px rgba(0,0,0,.06),"
                   "0 2px 6px rgba(0,0,0,.06)"),
        "overlay": ("0 4px 42px rgba(0,0,0,.06),0 2px 6px rgba(0,0,0,.05),"
                    "0 0 0 1px rgba(0,0,0,.06)"),
    }),
})
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
MOTION: Mapping[str, int | float | str] = MappingProxyType({
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
})

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
#: 生成的 CSS 变量一律带这个前缀。看板 `styles.css` 里已经有 `--muted`（**字色**
#: #91a99b，`color:var(--muted)` 用了 10 次）和 `--radius`（20px）——和这儿的
#: `muted`（**面** #102d23）/ `radius`（10）同名不同义。不带前缀的话，tokens.css
#: 在层叠里赢了，那 10 处字就变成面色（约 1.3:1）；输了，token 就没接上。
#: 和 `INK` 同名两义是同一类毛病，所以网页这一侧也不共用名字。
CSS_PREFIX = "--tl-"

#: `data-theme` 钉死主题时的选择器；没钉（不写或写别的值）就是「没钉死」。
_PINNED = ':root[data-theme="{theme}"]'
_UNPINNED = ':root:not([data-theme="light"]):not([data-theme="dark"])'
#: 消费方的默认主题：`system` 跟随 `prefers-color-scheme`（看板，Q10）；
#: `dark` / `light` 是这个消费方默认就是那一种。
DEFAULTS = ("system", "dark", "light")


def css_var(name: str) -> str:
    """角色名 → CSS 变量名：'primary' → '--tl-primary'。网页里写 `var(<这个>)`。"""
    return f"{CSS_PREFIX}{name}"


def _decl(name: str, value: object) -> str:
    return f"  {css_var(name)}: {value};"


def _theme_decls(theme: str) -> list[str]:
    """一个主题的颜色和阴影声明（不带选择器）。浅色少的正好是 `DARK_ONLY` 和图表。"""
    if theme == "dark":
        lines = [_decl(k, v) for k, v in DARK.items()]
        lines += [_decl(f"{k}-chip", v) for k, v in DARK_CHIP.items()]
        lines += [_decl(f"chart-{i}", v) for i, v in enumerate(CHART, 1)]
    elif theme == "light":
        lines = [_decl(k, v) for k, v in LIGHT.items()]
        lines += [_decl(f"{k}-chip", v) for k, v in LIGHT_CHIP.items()]
    else:
        raise ValueError(f"theme 只认 dark / light，拿到 {theme!r}")
    lines += [_decl(f"shadow-{k}", v) for k, v in SHADOW_WEB[theme].items()]
    return lines


def dark_only_vars() -> frozenset[str]:
    """只在深色块里声明的 CSS 变量名（`DARK_ONLY` 的角色 + 图表）。"""
    return frozenset({css_var(r) for r in DARK_ONLY}
                     | {css_var(f"chart-{i}") for i in range(1, len(CHART) + 1)})


def css_base() -> str:
    """与主题无关的一块：圆角、字阶、字体、动效、彩条。**不写 `color-scheme`**——
    深浅是主题块的事，裸 `:root` 上写 `color-scheme: dark` 会把每个链接了这份 CSS
    的页面的浏览器默认画布都翻成深色。"""
    lines = [":root {", _decl("brand-bar", BRAND_BAR_CSS)]
    lines.append(_decl("radius", f"{RADIUS_WEB['base']}px"))
    lines += [_decl(f"radius-{k}", f"{v}px") for k, v in RADIUS_WEB.items() if k != "base"]
    lines += [_decl(f"text-{k}", f"{v}px") for k, v in TEXT_WEB.items()]
    lines.append(_decl("font-sans", FONT_WEB))
    for k, v in MOTION.items():
        if k.endswith("_ms"):
            lines.append(_decl(f"duration-{k[:-3]}", f"{v}ms"))
        elif k.startswith("ease_"):
            lines.append(_decl(k.replace("_", "-"), v))
        # video_dissolve_s 是视频的，不进网页
    lines.append("}")
    return "\n".join(lines) + "\n"


def css_vars(theme: str, selector: str | None = None) -> str:
    """一个主题的 CSS 块：`color-scheme` + 颜色角色 + 芯片（+ 深色的图表）+ 阴影。

    默认选择器是钉死这个主题的 `:root[data-theme="<theme>"]`；`tokens_css()`
    会再用「没钉死」的选择器生成一份，放进 `prefers-color-scheme` 或当默认。
    """
    decls = _theme_decls(theme)
    sel = selector or _PINNED.format(theme=theme)
    return "\n".join([f"{sel} {{", f"  color-scheme: {theme};", *decls, "}"]) + "\n"


def _indent(block: str) -> str:
    return "".join(f"  {ln}" if ln.strip() else ln for ln in block.splitlines(keepends=True))


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
    f"    {css_var('duration-' + k[:-3])}: .01ms;" for k in MOTION if k.endswith("_ms")))

_DEFAULT_NOTE = {
    "system": "不写就跟随系统（prefers-color-scheme）；认不出系统偏好的浏览器按浅色",
    "dark": "不写就是深色（这个消费方默认深色）",
    "light": "不写就是浅色（这个消费方默认浅色）",
}


def _header(default: str) -> str:
    return (
        "/* 由 tools/gen_tokens_css.py 从 src/tennislive/design_tokens.py 生成——别手改。\n"
        "   改颜色、圆角、字阶、动效去改那个模块，再重跑脚本；\n"
        "   判据 tests/test_design_tokens.py 要求两边逐字节相等。\n"
        "   变量一律带 --tl- 前缀（看板自己的 --muted / --radius 和这里同名不同义）。\n"
        f"   主题：<html data-theme=\"dark|light\"> 钉死；{_DEFAULT_NOTE[default]}。 */\n"
    )


def tokens_css(*, default: str) -> str:
    """一份 tokens.css 的全文。`default` 是**这个消费方**没钉 `data-theme` 时的主题：

    - `system`：浅色那块写在 `@media` **外面**、深色那块包在
      `@media (prefers-color-scheme: dark)` 里，选择器都是「没钉死」的 `:root`
      （同特异度，后写的深色在系统要深色时赢）——`data-theme` 写了 dark / light
      就让位给钉死的那块。⚠️ 原来浅色也包在 `@media (prefers-color-scheme: light)`
      里：认不出这条媒体查询的 WebView（老 Android／X5、iOS < 12.1）两块都不生效，
      页面**一个颜色都没有**，按钮和芯片全透明（UI 评审 WP1 复核的 nit）。
    - `dark` / `light`：那个主题的块同时认「没钉死」，不跟随系统。

    两种情况下深浅都只写在主题块里，裸 `:root` 那块（`css_base()`）永远不带
    `color-scheme`。没有缺省值是故意的：每个消费方自己在
    `tools/gen_tokens_css.py` 的表里认领。
    """
    if default not in DEFAULTS:
        raise ValueError(f"default 只认 {'/'.join(DEFAULTS)}，拿到 {default!r}")
    parts = [_header(default), css_base(), css_vars("dark"), css_vars("light")]
    if default == "system":
        parts += [css_vars("light", _UNPINNED),
                  "@media (prefers-color-scheme: dark) {\n"
                  + _indent(css_vars("dark", _UNPINNED)) + "}\n"]
    else:
        parts.append(css_vars(default, _UNPINNED))
    parts.append(REDUCED_MOTION_CSS)
    return "\n".join(parts)
