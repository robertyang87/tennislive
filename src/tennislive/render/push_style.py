"""微信推送正文和复制页的视觉——**同一套系统浅／深色 token**，三条线共用。

来路（2026-09-27 UI / VI 评审 3.2，WP2）：

- **推送正文和复制页之间用了 22 个 hex，一个都没共享**：推送的药丸是 #e7f5ea 底
  #087747 字、提示灰 #7a8580（白底只有 3.82:1）、视频按钮 #102d23；复制页的按钮是
  #0a7d43，深色模式换成不是品牌色的 #b8e986，toast 的底和深色页面底是同一个色
  （1.00:1，完全看不见）。现在两边的颜色都从 `design_tokens.LIGHT` / `DARK` 来。
  2026-09-30 起推送正文也跟随系统：浅色内联兜底，深色用作用域媒体查询覆盖；
  复制页继续用 `tokens_css(default="system")`。这是所有栏目后续网页的全局要求。
  不按时钟判断夜间，不用脚本记住固定主题，也不对图片／视频做反色。
  PushPlus 若过滤 `<style>` 或 WebView 不传系统偏好，仍可读但只能浅色；
  本地浏览器测试不能冒充已验证 PushPlus 托管页或微信实机。
- **账号所有者 2026-09-27 Q8**：浅底上药丸和按钮用**黄绿实底 + 墨色字**
  （#c6f65a / #04120d，15.2:1），链接用**中性灰**。黄绿在白底上只有 1.26:1，
  **永远不当字色**。
- **「网球有故事」两条产线的推送长得不一样**：剪辑片走 `push_reel.build_html`（药丸
  写栏目名、标题底下有「长按这一行即可复制」、按钮「▶ 打开竖版成片」），字卡走
  `knowledge_push_html_from_parts`（药丸写「知识解说视频 · 9.26」、没有标题提示行、
  按钮「▶ 打开 9:16 成片」）。现在两边的药丸、标题、提示行、视频按钮、「原图 ↗」
  都从这儿的同一组函数出——**文案和样式都只有一处出处**，调用方传不进另一套。

⚠️⚠️ **红按钮 #ff2442 不在这儿。** 账号所有者 2026-08-31：「微信推送的红色按钮
不要改了」。它在 `tools/push_reel.py` 和 `render/knowledge.py` 里**各写一遍、字面
不动**（两份还差一个分号——那也不动），判据 `tests/test_push_visual.py` 拿两处的
真产出和金样逐字节比。这里只有卡片顶上那条 5px 红边用的 `PUSH_RED`（同一支红，
不是按钮）。

⚠️ **推送是 2 万字预算里的东西**（`pushplus.check_content_length`）：字卡推送每张图
都有一组「图 + 原图链接」，样式每多一个字就乘以图数。改这里的每图样式要重量一遍
（`test_字卡推送图多也装得下_每张图不比改之前更贵`）。
"""

from __future__ import annotations

# design-tokens: enforced
import html
import re

from ..design_tokens import DARK, FONT_WEB, LIGHT, RADIUS_WEB, TEXT_WEB, css_vars, tokens_css

#: 推送卡顶上那条红边——和卡底那颗红按钮同一支红（账号所有者 2026-08-31 定了不动）。
PUSH_RED = "#ff2442"  # token-exempt: 推送红边／红按钮的红，账号所有者「不要改了」

_L = LIGHT
#: 进 `style="…"` 属性的字体栈：token 里是双引号，放进双引号属性会把属性截断。
FONT_INLINE = FONT_WEB.replace('"', "'")

# ── 推送正文（浅色内联兜底 + 系统深色覆盖）──────────────────────────────────────────────────
PAGE = (f"background-color:{_L['background']};color:{_L['foreground']};"
        f"padding:12px 10px;font-family:{FONT_INLINE};color-scheme:light dark")


def system_theme_style() -> str:
    """PushPlus 正文的系统主题，限定在我们自己的 `.tl-push` 内。

    用 token 生成行内颜色选择器：不用给每张图的链接重复加 class，25 页字卡仍能
    放进 PushPlus 的 2 万字预算。选择器和值同源，换 token 时不会漏改另一处。
    `!important` 只覆盖颜色；浅色原样、红按钮逐字节不动、宿主与图片不受影响。
    不依赖 JS、远程 CSS 或新 WebView 才支持的 `light-dark()`。
    """
    rules = [
        f".tl-push{{color-scheme:dark;background-color:{DARK['background']}!important;"
        f"color:{DARK['foreground']}!important}}",
    ]
    for prop, role in (("background-color", "card"), ("color", "foreground"),
                       ("color", "muted-foreground"), ("color", "link")):
        rule = (f'.tl-push [style*="{prop}:{LIGHT[role]};"]'
                f"{{{prop}:{DARK[role]}!important}}")
        if rule not in rules:
            rules.append(rule)
    rules.append(f'.tl-push [style*="border-top:1px solid {LIGHT["border"]};"]'
                 f'{{border-top-color:{DARK["border"]}!important}}')
    return '<style>@media (prefers-color-scheme: dark){' + ''.join(rules) + '}</style>'


def card(padding: str) -> str:
    """白卡：顶上一条 5px 红边（参照那条知识解说推送，账号所有者指定）。"""
    return (f"max-width:680px;margin:0 auto;background-color:{_L['card']};"
            f"border-top:5px solid {PUSH_RED};padding:{padding}")


#: 台头药丸：Q8 黄绿实底 + 墨色字。写**栏目名**，不写日期（标题第一格就是日期）。
#:
#: 改之前 → 改之后（颜色是 Q8 定的；**形状是按「视觉精美且优雅」这条口味顺手改的，
#: 不是 Q8 的内容**，单列在这儿好让人一眼否掉）：
#: `#e7f5ea` 底 `#087747` 字、12px bold、`padding:4px 8px`、**圆角 4px 的小方块** →
#: `primary` 底 `primary-foreground` 字、12px/600、`3px 10px`、**整颗胶囊**（`full`）。
PILL = (f"display:inline-block;background-color:{_L['primary']};"
        f"color:{_L['primary-foreground']};font-size:{TEXT_WEB['xs']}px;font-weight:600;"
        f"line-height:18px;padding:3px 10px;border-radius:{RADIUS_WEB['full']}px")
#: 标题和正文整块可选（`user-select:all`）：长按一下选中整段，不用手指拖着选
#: 一千字。评审 3.2「在推送里复制整段正文要手指拖选约 1000 字」。
_SELECT_ALL = "-webkit-user-select:all;user-select:all"
#: 大标题。改之前 → 改之后（同上：**字号字重不是 Q8 的内容**，是按口味规则收的一档）：
#: `23px / 1.38 / 800 / #102d23`（深绿，不是正文色）→ `xl`=22px / 1.4 / **600** /
#: `foreground` #17251f（和正文同一个墨色）。字重和复制页 `h1`、药丸同一档 600；
#: 字阶里没有 23，就近落到 22。
TITLE = (f"font-size:{TEXT_WEB['xl']}px;line-height:1.4;font-weight:600;"
         f"color:{_L['foreground']};margin:10px 0 4px;{_SELECT_ALL}")
HINT = f"color:{_L['muted-foreground']};font-size:{TEXT_WEB['xs']}px"
BODY = (f"font-size:{TEXT_WEB['base']}px;line-height:1.85;white-space:pre-wrap;"
        f"word-break:break-word;margin:0 0 4px;{_SELECT_ALL}")
LEAD = (f"font-size:{TEXT_WEB['base']}px;line-height:1.8;color:{_L['foreground']};"
        "margin:0 0 14px")
#: 正文后面另起一屏（数据图）时那行小标题的外边距。原来是 `margin:4px 0 8px`，
#: 和正文自带的 4px 底边距折叠之后，「📊 数据统计对照」离正文最后一行的 #话题
#: 只剩 4px（评审 3.2 看图量的是 8px 左右，含行距），读着像正文的一部分。现在
#: 20px（折叠后真渲量出来就是 20），和复制页 `section` 之间的间距一样。
SECTION_GAP = "margin:20px 0 8px"
DIVIDER = f"border-top:1px solid {_L['border']};margin:18px 0 12px"
#: 视频按钮：Q8 黄绿实底 + 墨色字；几何和红按钮一模一样（两颗叠在一起，只差颜色）。
VIDEO_BUTTON = (f"display:block;background-color:{_L['primary']};"
                f"color:{_L['primary-foreground']};text-align:center;text-decoration:none;"
                f"font-weight:bold;padding:13px 16px;border-radius:{RADIUS_WEB['sm']}px;"
                "margin:0 0 7px")
#: 图片没显示时的回退链接：灰色「原图 ↗」，右对齐，40px 高的点击区（次要操作 ≥40，
#: 评审 2.5）。原来是一行 13px 的绿字「封面没显示？点此打开原图」，只有 15px 高，
#: 字卡推送每张图下面挂一条，满屏绿链接。
#:
#: ⚠️ **这一串乘以图数**：字卡推送每张图一条，推送有 2 万字的上限。所以这里没有
#: 外边距、没有横向内边距——40px 的行高本身就把上下两张图隔开（字落在行中间，
#: 上下各留约 12px）。多写一个 `margin:0 0 8px` 就是每张图 15 个字符。
ORIGINAL_LINK = (f"display:inline-block;line-height:40px;color:{_L['link']};"
                 f"font-size:{TEXT_WEB['sm']}px;text-decoration:none")

TITLE_HINT_TEXT = "☝️ 标题，长按这一行即可复制"
BODY_HINT_TEXT = "👇 正文全文如下，长按整段即可复制"
VIDEO_BUTTON_TEXT = "▶ 打开竖版成片"
ORIGINAL_TEXT = "原图 ↗"
FOOT_TEXT = "图片长按保存"

#: 推送里每种图的宽高比（用来给 `<img>` 预留高度，图没下完页面不跳）。
#: 判据 `test_推送图片预留的比例和出图的画布对得上` 拿它们和出图模块的画布常量比。
#: 写约分过的（`3/4` 比 `1080/1440` 每张图省 6 个字符，理由同上）。
POSTER_RATIO = (3, 4)       # tools/versus_poster.py VIDEO_W, VIDEO_H = 1080, 1440
STAT_CARD_RATIO = (9, 16)   # tools/render_stat_card.py W, H = 1080, 1920（推送用 poster 变体）
SLIDE_RATIO = (3, 4)        # video/explainer.py W, H = 1080, 1440（字卡 3:4）


def pill(text: str) -> str:
    return f'<div style="{PILL}">{html.escape(text)}</div>'


def title_block(safe_title: str) -> str:
    """`safe_title` 已经转义过（两个调用方各自转义，这里不再转一遍）。"""
    return f'<div style="{TITLE}">{safe_title}</div>'


def hint(text: str, margin: str) -> str:
    return f'<div style="{HINT};margin:{margin}">{text}</div>'


def title_hint() -> str:
    """大标题底下那行「长按这一行即可复制」：复制页打不开时标题的出口
    （`test_复制页打不开时消息本身留得住文案`）。两条「网球有故事」都要有。"""
    return hint(TITLE_HINT_TEXT, "0 0 14px")


def section_label(text: str, pad: str) -> str:
    """正文之后另起一屏的灰色小标题（「📊 数据统计对照」）。`pad` 是那条线文字块的
    左右内边距（海报铺满的那条线卡片本身没有内边距）。"""
    return (f'<div style="{pad};{SECTION_GAP}">'
            f'<div style="{HINT}">{text}</div></div>')


def body_block(body: str) -> str:
    """正文一整块（pre-wrap），一次长按整段可选。`body` 是原文，这里转义。"""
    return (hint(BODY_HINT_TEXT, "0 0 8px")
            + f'<div style="{BODY}">{html.escape(body)}</div>')


def image(url: str, alt: str, ratio: tuple[int, int], *, rounded: bool,
          data_src: bool = False) -> str:
    """一张推送图。`aspect-ratio:auto w/h`：没下完时按 w/h 预留高度，下完按图自己的
    比例（写成 `auto` 那种，万一比例对不上也不会把图压扁）。"""
    w, h = ratio
    style = f"width:100%;display:block;aspect-ratio:auto {w}/{h}"
    if rounded:
        style += f";border-radius:{RADIUS_WEB['sm']}px"
    lazy = f' data-src="{url}"' if data_src else ""
    return (f'<img src="{url}"{lazy} width="100%" alt="{alt}"'
            f' referrerpolicy="no-referrer" style="{style}">')


def original_link(url: str, pad: str = "") -> str:
    """图下面那条灰色「原图 ↗」。`pad` 给没有卡片内边距的那条线（海报铺满）用。"""
    return (f'<div style="text-align:right{pad}">'
            f'<a href="{url}" style="{ORIGINAL_LINK}">{ORIGINAL_TEXT}</a></div>')


def video_button(url: str) -> str:
    return f'<a href="{url}" style="{VIDEO_BUTTON}">{VIDEO_BUTTON_TEXT}</a>'


def foot() -> str:
    return (f'<div style="text-align:center;{HINT}">{FOOT_TEXT}</div>')


# ── 复制页（真网页，跟随系统浅／深）──────────────────────────────────────
def copy_page_tokens() -> str:
    """复制页自带的那份 token CSS（和看板 `dashboard/tokens.css` 同一个生成函数，
    默认跟随系统）。**内嵌，不链接**：复制页是单文件，挂在
    `output/<日期>/…/copy.html`，不依赖另一次部署、也不多一趟国内要绕境外的请求。
    头注释去掉——那段写的是「由 gen_tokens_css.py 生成」，对这儿不成立。

    ⚠️ **不认 `prefers-color-scheme` 的 WebView 也要是浅色**（2026-09-27 WP2 复核）：
    `tokens_css("system")` 要是把浅色也包在 `@media (prefers-color-scheme: light)` 里，
    那种 WebView 里每个 `--tl-*` 颜色都落空：按钮透明、只剩一行黑字，toast 透明（复核把
    媒体特性改名模拟出来的，判据 `test_复制页不认prefers_color_scheme也是浅色` 就是那个
    模拟）。老复制页在同一个模拟下还是浅色。

    所以这里**先看** `@media` 外面、没钉 `data-theme` 的块里有没有整套浅色：有（看板那头
    WP1 把浅色挪到 `@media` 外面之后就是这样）就原样用，不多垫一份死 CSS；没有才在最前面
    垫一份 `css_vars("light", ":root")`。垫的这份选择器是 `:root`（0,1,0），**比两种主题
    块都弱**——`[data-theme]` 是 (0,2,0)、跟随系统那块是 (0,3,0)——而且和 `css_base()`
    那块一个变量都不重名，所以**排在哪儿都一样**：认这条查询的浏览器照旧按系统走，一个
    像素都不变。`tokens_css()` 哪天换了排版也只是走「垫」那条路，不会在无人值守的出片
    链上抛异常。只在复制页垫：看板那份 `tokens.css` 是另一个消费方。"""
    css = re.sub(r"\A/\*.*?\*/\n", "", tokens_css(default="system"), flags=re.S)
    light = css_vars("light", ":root")
    have = _unconditional_decls(css)
    if all(have.get(k) == v for k, v in _DECL.findall(light)):
        return css
    return light + "\n" + css


_DECL = re.compile(r"(--[\w-]+):\s*([^;]+);")
_MEDIA_BLOCK = re.compile(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")
_PINNED_THEME = re.compile(r':root\[data-theme="(?:light|dark)"\]')


def _unconditional_decls(css: str) -> dict[str, str]:
    """`@media` 外面、选择器没钉 `data-theme` 的块里声明的变量——不认媒体查询的
    WebView 只看得见这些。"""
    decls: dict[str, str] = {}
    for sel, body in re.findall(r"(?m)^([^\s{}@][^{}]*?)\s*\{([^{}]*)\}", _MEDIA_BLOCK.sub("", css)):
        if not _PINNED_THEME.fullmatch(sel.strip()):
            decls.update(_DECL.findall(body))
    return decls


#: 复制页自己的样式：**只写 `var(--tl-…)`**，不写一个色值
#: （判据 `test_复制页自己的样式只用token变量`）。
#:
#: - 按钮 44px 高（主操作 ≥44，评审 2.5；原来 42）、黄绿实底 + 墨色字（Q8，两个主题
#:   都是）；按压 `scale(.97)` 走 `press`，焦点环 2px `ring`，「已复制」换成
#:   `muted` 底 + 正文色（不借薄荷——薄荷只表示「赢」，Q1）。
#: - toast **反色**：浅色是墨底白字，深色是近白底墨字（#f4fbf7 / #04120d）。原来深色
#:   toast 的底和页面底一样（1.00:1）。位置让开 iPhone 底部的 home 条
#:   （`env(safe-area-inset-bottom)`，要配 `viewport-fit=cover`）。打开 250ms、
#:   关闭 150ms——**关闭比打开快**（评审 2.7）。
#: - hover 只写在 `(hover:hover) and (pointer:fine)` 里（微信是触屏，:hover 会粘住）；
#:   `touch-action: manipulation` 免得连点两下被 iOS 当成双击缩放。
#: - `prefers-reduced-motion` 由 token 那块统一压到 .01ms；这里再把位移去掉，只留透明度。
COPY_PAGE_CSS = """\
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--tl-background); color: var(--tl-foreground);
  font-family: var(--tl-font-sans); -webkit-tap-highlight-color: transparent; }
main { width: min(100%, 680px); margin: 0 auto;
  padding: 20px max(16px, env(safe-area-inset-right))
    calc(40px + env(safe-area-inset-bottom)) max(16px, env(safe-area-inset-left)); }
h1 { margin: 0 0 6px; font-size: var(--tl-text-xl); font-weight: 600; line-height: 1.3; }
.sub { margin: 0 0 20px; color: var(--tl-muted-foreground); font-size: var(--tl-text-sm); }
section { margin-top: 20px; }
.label { display: flex; align-items: center; justify-content: space-between; gap: 12px;
  margin-bottom: 8px; font-size: var(--tl-text-base); font-weight: 600; }
button { min-height: 44px; min-width: 104px; padding: 0 16px; border: 0;
  border-radius: var(--tl-radius-md); background: var(--tl-primary);
  color: var(--tl-primary-foreground); font: 600 var(--tl-text-base)/1 var(--tl-font-sans);
  cursor: pointer; touch-action: manipulation;
  transition: transform var(--tl-duration-press) var(--tl-ease-out),
    background-color var(--tl-duration-quick) var(--tl-ease-out),
    color var(--tl-duration-quick) var(--tl-ease-out),
    box-shadow var(--tl-duration-quick) var(--tl-ease-out); }
button:active { transform: scale(.97); }
button.copied { background: var(--tl-muted); color: var(--tl-foreground); }
button:focus-visible, textarea:focus-visible { outline: 2px solid var(--tl-ring);
  outline-offset: 2px; }
@media (hover: hover) and (pointer: fine) {
  button:hover { box-shadow: var(--tl-shadow-raised); }
}
textarea { display: block; width: 100%; resize: vertical; border: 1px solid var(--tl-input);
  border-radius: var(--tl-radius-md); background: var(--tl-card); color: var(--tl-foreground);
  padding: 12px; font: var(--tl-text-base)/1.7 var(--tl-font-sans); }
#title { min-height: 76px; }
.alt { min-height: 52px; }
#body { min-height: 55vh; }
#comment { min-height: 118px; }
#toast { position: fixed; left: 50%; bottom: calc(24px + env(safe-area-inset-bottom));
  width: max-content; max-width: calc(100% - 32px); text-align: center;
  background: var(--tl-foreground); color: var(--tl-background);
  box-shadow: var(--tl-shadow-overlay); padding: 10px 16px;
  border-radius: var(--tl-radius-md); font-size: var(--tl-text-base); line-height: 1.5;
  opacity: 0; pointer-events: none; transform: translate(-50%, 8px);
  transition: opacity var(--tl-duration-quick) var(--tl-ease-out),
    transform var(--tl-duration-quick) var(--tl-ease-out); }
#toast.show { opacity: 1; transform: translate(-50%, 0);
  transition-duration: var(--tl-duration-fast); }
@media (prefers-reduced-motion: reduce) {
  #toast, #toast.show { transform: translate(-50%, 0); }
  button:active { transform: none; }
}
"""

#: 复制失败时 toast 说的话（账号所有者没定措辞，评审 3.2 给的这句）。
COPY_FAILED_TEXT = "复制失败，已帮你选中，长按拷贝"

#: 复制页的脚本。三件事是评审 3.2 量出来的毛病：
#:
#: 1. **复制失败也说「已复制」**——原来 `catch` 里 `execCommand('copy')` 的返回值
#:    没人看，不管成没成都弹「标题已复制」。现在跟踪 `ok`：两条路都没成，就把那一格
#:    整段选中，告诉人「复制失败，已帮你选中，长按拷贝」。**说成功必须真的成功**。
#: 2. **连点两次，第二条 toast 只停约 400ms**——第一次的 `setTimeout` 没清，到点把
#:    第二条提前收走。现在每次 `clearTimeout` 后重新计时。
#: 3. 按钮没有「已复制」状态：成功后按钮字换成「已复制 ✓」，1.4 秒后还原（同样
#:    连点重新计时）。**失败时当场还原**（2026-09-27 WP2 复核）：同一颗按钮还在
#:    「已复制 ✓」那 1.4 秒里、下一次又失败了，原来 toast 说失败、按钮却还挂着
#:    「已复制 ✓」——两句话打架。现在失败分支先清掉这颗按钮的计时、把字和样式还原。
COPY_PAGE_JS = """\
const toast = document.getElementById('toast');
const labels = {body: '正文已复制', comment: '评论已复制'};
const buttonTimers = new Map();
let toastTimer = 0;
function say(text, ms) {
  toast.textContent = text;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), ms);
}
function restore(button) {
  clearTimeout(buttonTimers.get(button));
  if (button.dataset.label) button.textContent = button.dataset.label;
  button.classList.remove('copied');
}
function selectAll(field) {
  field.focus();
  field.select();
  try { field.setSelectionRange(0, field.value.length); } catch (_) {}
}
async function copyText(id, button) {
  const field = document.getElementById(id);
  let ok = false;
  try {
    await navigator.clipboard.writeText(field.value);
    ok = true;
  } catch (_) {
    selectAll(field);
    try { ok = document.execCommand('copy') === true; } catch (_) { ok = false; }
  }
  if (!ok) {
    restore(button);
    selectAll(field);
    say('%(failed)s', 2600);
    return;
  }
  if (document.activeElement === field) field.blur();
  say(labels[id] || '标题已复制', 1400);
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.textContent = '已复制 ✓';
  button.classList.add('copied');
  clearTimeout(buttonTimers.get(button));
  buttonTimers.set(button, setTimeout(() => restore(button), 1400));
}
document.querySelectorAll('[data-copy]').forEach((button) => {
  button.addEventListener('click', () => copyText(button.dataset.copy, button));
});
""" % {"failed": COPY_FAILED_TEXT}
