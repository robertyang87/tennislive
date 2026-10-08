"""「网球有故事」字卡（`explainer._slide_html` / `_render_intro_badge`）的颜色——一处出处。

2026-10-04 全栏目蓝色设计已获授权：SLIDE_INK / HERO_DEEP 现接共享背景和卡片蓝，下列零视觉变化说明为历史。

来路：2026-09-27 那轮 UI / VI 整体评审（WP4）。字卡的 CSS 里原来手写了十来个
色值，和 `design_tokens` 各配各的；这儿把它们收成**角色**，值从 token 来。

⚠️ **接 token 的那一步是零视觉变化**：重渲 `fils-tokyo-qualifying`、
`bu-lucky-loser`、`ranking-math`、`eala-anisimova` 四条共 32 屏，前后逐像素
**最大差 = 0**（不是均差——均差会把局部改色稀释掉，见
`tools/design_compare_sheet.py` 的 docstring）。

⚠️ **有四个值 token 里没有，照原值留在这儿**，同一行写了 `token-exempt` 的理由：

| 名字 | 值 | 为什么不直接换成 token |
|---|---|---|
| `SLIDE_INK` | #061c14 | 评审把它登记成 `card`（#0c1d16）的合并对象——那是**改值**，整张卡的底和 scrim 都会变亮一档，要重渲量过、账号所有者点头才合 |
| `HERO_DEEP` | #0b3a2a | 示意图径向渐变的中段，token 里只有两头（`hero-glow` / 底） |
| `TOPIC` | #dcefe4 | 台头副标题；评审表里 `muted-foreground` 的合并对象写着「待验证」 |
| `TAIL` | #dff3e8 | `.tail` / `.fixture .when`，同上 |

**一屏只留一个强调色**（账号所有者 2026-09-27 Q1：黄绿 #c6f65a 是唯一品牌色，
薄荷只表示「这一方赢了」）：字卡上带颜色的只有 `PRIMARY` 这一支——要点前面的
▪、要点框的左边线、末屏那一问。每屏的编号药丸原来是薄荷实底（#37e29a），和下面
的黄绿要点同屏两支绿；Q5 定成**描边、中性色**，见 `CHIP_*`。

本文件打了 design-tokens 的 enforced 标记：代码行里不许再出现 6/8 位 hex 或
ASS 的 `&H` 颜色，要写就去 token 模块加角色，或者同一行写 `token-exempt: <理由>`。
判据 `tests/test_design_tokens.py`。
"""

from __future__ import annotations

# design-tokens: enforced
from ..design_tokens import (
    BRAND_BAR_CSS, CARD_BACKGROUND_CSS, DARK, TEXT_SHADOW_CHROME, TEXT_SHADOW_HOOK, rgb,
)


def rgba(hex_colour: str, alpha: float) -> str:
    """'#061c14', .55 → 'rgba(6,28,20,.55)'（CSS 里就是这么写的，逐字节对得上）。"""
    r, g, b = rgb(hex_colour)
    a = f"{alpha:g}"
    if a.startswith("0."):
        a = a[1:]
    return f"rgba({r},{g},{b},{a})"


#: 正文、标题、要点。
FOREGROUND = DARK["foreground"]
#: 唯一的强调色：要点前的 ▪、要点框左边线、末屏那一问、赛前片小字的左边线。
PRIMARY = DARK["primary"]
#: 封面标题底下那行注（`.gloss`）——次级灰，别再往暗里调。
MUTED_FOREGROUND = DARK["muted-foreground"]
#: 示意图那一屏背景的径向渐变：中心。
HERO_GLOW = DARK["hero-glow"]

#: 字卡的底色，也是 scrim 压暗用的那支墨（`rgba(6,28,20,…)`）。
SLIDE_INK = DARK["background"]
#: 示意图径向渐变的中段。
HERO_DEEP = DARK["card"]
BACKGROUND = CARD_BACKGROUND_CSS
#: 台头副标题（`.topic`）。
TOPIC = "#dcefe4"  # token-exempt: 评审里 muted-foreground 的合并对象「待验证」
#: 封面收尾那行、赛前片小字的时间行（`.tail` / `.fixture .when`）。
TAIL = "#dff3e8"  # token-exempt: 同上，合并前要量

#: 顶部四色彩条（账号所有者锁定，照原值）。
BRAND_BAR = BRAND_BAR_CSS
#: 封面大标题的三层阴影（封面禁用遮罩，这层是唯一的可读性保护）。
SHADOW_HOOK = TEXT_SHADOW_HOOK
#: 台头副标题这类「贴在照片上的小字」的阴影。
SHADOW_CHROME = TEXT_SHADOW_CHROME

# ── 每屏的编号药丸（Q5：描边、中性色）──────────────────────────────────────
#: 字：正文近白。药丸只负责「这是第几屏、讲什么」，不再抢强调色。
CHIP_TEXT = FOREGROUND
#: 描边：次级灰压到 .55——压在照片上也看得见边，又不会亮过要点那条黄绿边线。
CHIP_OUTLINE = rgba(MUTED_FOREGROUND, .55)
#: 底：品牌深墨压 .45——照片亮的那几屏，字底下仍然垫着一层暗。
CHIP_FILL = rgba(DARK["background"], .45)
