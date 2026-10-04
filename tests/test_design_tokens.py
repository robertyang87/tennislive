"""设计 token 模块（`tennislive.design_tokens`）的判据——UI / VI 评审 WP0。

来路：38 个出画面的文件里 185 个不同的 hex、聚类只有 73 簇；同一个名字 `INK`
在两处指两件事；两族绿在抢品牌色。WP0 先把**唯一出处**立起来（零视觉变化），
各个面接 token 是 WP1–WP8 的事。这份文件钉这几件事：

1. 换算函数和已经锁定的决定逐字节对得上（顶栏赢盘薄荷 = 08-18 那条）；表都是只读的
2. 对比度下限——token 自己不许把字调到读不清；浅色主题完整（Q8：黄绿在浅底上只当实底）
3. 打了 enforced 标记的文件不许再写裸色值（绕过检测，带自证），名单只许加不许减
4. tokens.css 是生成物，和模块逐字节相等；变量带 `--tl-` 前缀；跟随系统（Q10）
5. 示意图色板只换了出处，值一个没动；对比图工具认得出一个像素、一格透明度的差
"""

from __future__ import annotations

import ast
import gc
import io
import re
import sys
import tokenize
import warnings
from pathlib import Path
from types import MappingProxyType

import pytest

from tennislive import design_tokens as T

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


# ── 1. 换算 ────────────────────────────────────────────────────────────────
def test_ass换算和08_18那条顶栏决定逐字节对得上():
    """ASS 颜色字节序和 CSS 相反（BGR），alpha 也是反的（0 = 不透明）。

    赛后开麦中文字幕那支淡黄绿 #c3dc74，就是当初把 #74dcc3 的字节序写反了
    得来的（commit c68938aa）——所以换算只许有一个出处，而且要钉在一个**已经
    在用的真值**上：`build_match_reel.TOPBAR_SETWIN_ASS` 是账号所有者 08-18
    定的「顶栏赢家和赢盘跟赛后开麦走」那支薄荷。
    """
    import build_match_reel  # noqa: PLC0415

    assert T.ass("#74dcc3") == "&H00C3DC74"
    assert T.ass("#74DCC3", 0x80) == "&H80C3DC74"
    assert T.ass_inline("#4adc8c") == build_match_reel.TOPBAR_SETWIN_ASS
    assert T.ass_inline(T.SCORE["win_video"]) == build_match_reel.TOPBAR_SETWIN_ASS
    assert "{\\c" + T.ass(T.SCORE["dash"]) + "&}" == build_match_reel.TOPBAR_SETDASH_ASS
    assert T.rgb("#4adc8c") == (74, 220, 140)
    # 判据自己认得出写反的那一种
    assert T.ass("#c3dc74") != T.ass("#74dcc3")

    for bad in ("#ffffff1a", "#4adc8", "red", ""):
        with pytest.raises(ValueError):
            T.rgb(bad)  # 带 alpha 的角色不许当实色用
    with pytest.raises(ValueError):
        T.ass("#000000", 256)


def test_比分组件和彩条照原值收进来():
    """账号所有者锁定的组件级 token：只许「照原值收进来」，不许顺手「修」。

    比分板三个值和 `versus_poster` 里那三个常量逐字节比——那边接 token 之后
    常量还在（值改成从这儿取），这条判据照样成立。
    """
    import versus_poster as vp  # noqa: PLC0415

    assert T.SCORE["win_bar"] == vp.SCORE_BLUE
    assert T.SCORE["panel_rgb"] == vp.SCORE_PANEL_RGB
    assert T.SCORE["ink"] == vp.SCORE_INK
    assert T.BRAND_BAR_CSS == (
        "linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%)")
    assert T.TEXT_SHADOW_HOOK == ("0 2px 6px rgba(0,0,0,.9),0 6px 30px rgba(0,0,0,.85),"
                                  "0 0 60px rgba(6,28,20,.7)")
    assert T.TEXT_SHADOW_CHROME == "0 2px 10px rgba(0,0,0,.9),0 0 24px rgba(6,28,20,.8)"
    assert T.MOTION["video_dissolve_s"] == 0.18  # 溶解，中间一帧黑都不许有
    # 推送红按钮不进 token（两个调用处保持字面不动）
    every = [*T.DARK.values(), *T.LIGHT.values(), *T.CHART, *T.SCORE.values()]
    assert not any("ff2442" in v.lower() for v in every)


def test_角色值的形状():
    """实色一律 #rrggbb；只有深色的 border / input / ring 三个带 alpha（8 位）。"""
    hex6 = re.compile(r"#[0-9a-f]{6}")
    hex8 = re.compile(r"#[0-9a-f]{8}")
    alpha = {k for k, v in T.DARK.items() if hex8.fullmatch(v)}
    assert alpha == {"border", "input", "ring"}
    for table in (T.DARK, T.LIGHT):
        for role, v in table.items():
            assert hex6.fullmatch(v) or (table is T.DARK and role in alpha), (role, v)
    for v in (*T.CHART, *T.DARK_CHIP.values(), *T.LIGHT_CHIP.values(),
              *(c for c, _ in T.BRAND_BAR)):
        assert hex6.fullmatch(v), v


def test_token表都是只读的():
    """模块级的 dict 谁都能顺手改一个值，改了之后整个进程里的面一起变、不报错。
    所以表一律 `MappingProxyType`，要派生就 `dict(T.DARK)` 拷一份。"""
    tables = {
        "DARK": T.DARK, "LIGHT": T.LIGHT, "SCORE": T.SCORE,
        "DARK_CHIP": T.DARK_CHIP, "LIGHT_CHIP": T.LIGHT_CHIP,
        "RADIUS_WEB": T.RADIUS_WEB, "TEXT_WEB": T.TEXT_WEB, "MOTION": T.MOTION,
        "SHADOW_WEB": T.SHADOW_WEB, "SHADOW_WEB[dark]": T.SHADOW_WEB["dark"],
        "SHADOW_WEB[light]": T.SHADOW_WEB["light"],
    }
    for name, table in tables.items():
        assert isinstance(table, MappingProxyType), f"{name} 是可改的 {type(table).__name__}"
        with pytest.raises(TypeError):
            table["primary"] = "#123456"  # type: ignore[index]
    copy = dict(T.DARK)
    copy["primary"] = "#000000"
    assert T.DARK["primary"] == "#c6f65a"  # 拷出去的改不回来


# ── 2. 对比度 · 浅色主题 ──────────────────────────────────────────────────
#: 浅色面上「当字用」的角色——每一个都要在三种浅底上读得清。
_LIGHT_TEXT_ROLES = ("foreground", "muted-foreground", "subtle-foreground", "link",
                     "success", "warning", "destructive", "info")


def test_对比度下限():
    """深色在 card 和 background 上都量；浅色的字在三种浅底（底色 / 白卡 / 凸起面）
    上都 ≥4.5；状态字在自己的芯片上也 ≥4.5。

    浅色次级灰原来是 #7a8580（白底 3.82，不过 AA），token 里换成 #5f6f68。
    """
    assert T.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    for surface in (T.DARK["card"], T.DARK["background"]):
        assert T.contrast(T.DARK["foreground"], surface) >= 12
        assert T.contrast(T.DARK["muted-foreground"], surface) >= 7
        assert T.contrast(T.DARK["link"], surface) >= 7
        assert T.contrast(T.DARK["subtle-foreground"], surface) >= 4.5
    assert T.contrast(T.DARK["primary-foreground"], T.DARK["primary"]) >= 7
    assert T.contrast(T.DARK["secondary-foreground"], T.DARK["secondary"]) >= 7

    for surface in (T.LIGHT["background"], T.LIGHT["card"], T.LIGHT["muted"]):
        assert T.contrast(T.LIGHT["foreground"], surface) >= 12
        for role in _LIGHT_TEXT_ROLES:
            assert T.contrast(T.LIGHT[role], surface) >= 4.5, (role, surface)
        # 焦点环是非文字元素：WCAG 1.4.11 要 ≥3
        assert T.contrast(T.LIGHT["ring"], surface) >= 3
    assert T.contrast(T.LIGHT["primary-foreground"], T.LIGHT["primary"]) >= 7
    assert T.contrast(T.LIGHT["secondary-foreground"], T.LIGHT["secondary"]) >= 7

    for theme, chips in (("dark", T.DARK_CHIP), ("light", T.LIGHT_CHIP)):
        roles = T.DARK if theme == "dark" else T.LIGHT
        for status, chip in chips.items():
            assert T.contrast(roles[status], chip) >= 4.5, (theme, status)

    # 判据认得出不合格的：旧的浅色次级灰、白底上的黄绿
    assert T.contrast("#7a8580", "#ffffff") < 4.5
    assert T.contrast(T.DARK["primary"], "#ffffff") < 1.5


def test_浅色主题是完整的_只有画布角色声明成只有深色():
    """评审复核在 Chromium 里量到：`data-theme="light"` 下 `--muted` 还是 #102d23、
    `--subtitle-foreground` 是近白、`--success` / 芯片 / 图表 / 浮起阴影全是深色值
    ——浅色只定义了一半，另一半悄悄继承深色。

    现在：`LIGHT` 的角色 = `DARK` 的角色 − `DARK_ONLY`，一个不多一个不少；
    `DARK_ONLY` 里只许是画布专用的（示意图渐变、视频字幕、示意图填充）。
    芯片和阴影两个主题的档位一一对应。
    """
    assert T.DARK_ONLY <= set(T.DARK), T.DARK_ONLY - set(T.DARK)
    assert T.DARK_ONLY == {"hero-glow", "subtitle-foreground", "fill"}
    missing = set(T.DARK) - T.DARK_ONLY - set(T.LIGHT)
    assert not missing, f"这几个深色角色在浅色里没有值，也没声明成只有深色：{sorted(missing)}"
    extra = set(T.LIGHT) - set(T.DARK)
    assert not extra, f"这几个角色只有浅色有，深色面上 var() 会落空：{sorted(extra)}"
    assert set(T.LIGHT_CHIP) == set(T.DARK_CHIP) <= set(T.LIGHT)
    assert set(T.SHADOW_WEB["light"]) == set(T.SHADOW_WEB["dark"])

    # 浅色芯片是公式算出来的（状态色 12% 混进白卡，sRGB），不是另挑的
    def mix(fg: str, bg: str, p: float) -> str:
        return "#" + "".join(f"{round(p * a + (1 - p) * b):02x}"
                             for a, b in zip(T.rgb(fg), T.rgb(bg)))
    for status, chip in T.LIGHT_CHIP.items():
        assert chip == mix(T.LIGHT[status], T.LIGHT["card"], 0.12), status


def test_Q8浅底上黄绿只当实底_链接用中性灰():
    """账号所有者 2026-09-27 Q8：推送／复制页这些浅底上，药丸和按钮用黄绿**实底**
    配墨色字 #04120d；链接用中性灰。黄绿 #c6f65a 在白底上只有 1.26:1，所以浅色
    里**任何一个当字用的角色**都不许是它（也不许是任何过不了 4.5 的色）。
    """
    assert T.LIGHT["primary"] == T.DARK["primary"] == "#c6f65a"
    assert T.LIGHT["primary-foreground"] == T.DARK["background"]
    assert T.LIGHT["link"] == T.LIGHT["muted-foreground"] == "#5f6f68"
    for role in _LIGHT_TEXT_ROLES:
        assert T.LIGHT[role] != T.LIGHT["primary"], f"浅色的 {role} 拿黄绿当字了"
    # 链接是中性灰：三个通道差不出一个色相来（黄绿三通道差 156）
    r, g, b = T.rgb(T.LIGHT["link"])
    assert max(r, g, b) - min(r, g, b) <= 24
    # 原来浅色 primary 的翡翠绿腾出来当浅色的「赢」
    assert T.LIGHT["success"] == "#087747"


# ── 3. 绕过检测 ────────────────────────────────────────────────────────────
#: 标记必须是**一行注释本身**，不是文中提到它——这份测试和 token 模块的
#: docstring 里都提到了这几个字，不能把自己判成被标记的文件。
_MARKER = re.compile(r"^\s*(?:#|//|/\*|\*|<!--)\s*design-tokens:\s*enforced\b")
#: `#rgb` / `#rgba` / `#rrggbb` / `#rrggbbaa`。前面不许是字母数字或 `&`（URL 片段
#: `page.html#abc`、HTML 实体 `&#123;`），后面不许再跟字母数字、`_`、`-`
#: （`#add-btn` 这种 id 选择器）。⚠️ 字符串里写 PR 号 `#168` 会被当成三位色——
#: enforced 的文件里 PR 号写进注释。
_HEX = re.compile(
    r"(?<![0-9A-Za-z_&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9A-Za-z_-])")
#: ASS 的 `&HBBGGRR` / `&HAABBGGRR`，大小写都认（libass 两种都吃）。
_ASS = re.compile(r"&[Hh][0-9A-Fa-f]{6,8}(?![0-9A-Za-z_])")
#: ffmpeg 的 `0xRRGGBB[AA]`（`color=0x061c14`、`drawbox=…:color=0xc6f65a@0.5`）。
_INT_HEX = re.compile(r"(?<![0-9A-Za-z_])0[xX](?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6})(?![0-9A-Za-z_])")
#: CSS 颜色函数，**第一个参数是字面值**才算（`rgba(0,0,0,.5)`、`oklch(0.9 0.18 124)`）。
#: `rgb(var(--tl-x) / .5)`、`oklch(from var(--tl-primary) l c h)` 是从 token 派生的，
#: 不算；Python 里调 token 模块自己的 `rgb(DARK[...])`、拼 `rgba({panel_rgb},.9)`
#: 也不算。
_COLOR_FN = re.compile(
    r"(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch)\(\s*(?:[-+]?\.?\d|none\b)", re.I)
_COLOR_MIX = re.compile(r"(?<![\w-])color-mix\(", re.I)
#: color-mix 的一个操作数「从 token 来」：var(--…)、transparent、currentColor，
#: 或者又是一个 color-mix（它自己单独查）。
_FROM_TOKEN = re.compile(r"(?:var\(\s*--|transparent\b|currentcolor\b|color-mix\()", re.I)
_EXEMPT = re.compile(r"token-exempt:\s*\S")
_SUFFIXES = {".py", ".css", ".js", ".mjs", ".html"}
_SCAN_ROOTS = ("src", "tools", "dashboard")


def _color_mix_has_literal(line: str) -> bool:
    """`color-mix(in <空间>, A p%, B)` 里只要有一个操作数不是从 token 来的就算。

    ⚠️ 已知扫不到的：命名色写在 color-mix 外面（`color: white`）、PIL 的
    `(244, 251, 247)` 元组、`"#" + "c6f65a"` 这种拼出来的串——前两种和坐标、
    CSS 关键字长得一样，扫了就是天天误报的闸；这几种靠 review。
    """
    for m in _COLOR_MIX.finditer(line):
        depth, args, cur = 1, [], ""
        for ch in line[m.end():]:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    break
            if ch == "," and depth == 1:
                args.append(cur)
                cur = ""
            else:
                cur += ch
        args.append(cur)
        for op in args[1:]:  # args[0] 是插值空间 `in srgb`
            op = re.sub(r"^\s*[\d.]+%\s*|\s*[\d.]+%\s*$", "", op).strip()
            if op and not _FROM_TOKEN.match(op):
                return True
    return False


def _code_lines_py(text: str) -> dict[int, str]:
    """行号 → 这一行的「代码」部分：注释和 docstring 去掉，**字符串留着**
    （颜色恰恰写在字符串里，CSS 就活在三引号字符串里）。"""
    doc_lines: set[int] = set()
    for node in ast.walk(ast.parse(text)):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            doc_lines.update(range(node.lineno, node.end_lineno + 1))
    skip = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
            tokenize.DEDENT, tokenize.ENDMARKER}
    out: dict[int, list[str]] = {}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in skip or tok.start[0] in doc_lines:
            continue
        for i, part in enumerate(tok.string.split("\n")):
            out.setdefault(tok.start[0] + i, []).append(part)
    return {n: " ".join(parts) for n, parts in out.items()}


def _code_lines_web(text: str, suffix: str) -> dict[int, str]:
    def blank(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")

    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    if suffix == ".html":
        text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    if suffix in (".js", ".mjs"):
        text = re.sub(r"(?<![:\"'\\])//[^\n]*", "", text)
    return dict(enumerate(text.splitlines(), 1))


def _is_bypass(line: str) -> bool:
    return bool(_HEX.search(line) or _ASS.search(line) or _INT_HEX.search(line)
                or _COLOR_FN.search(line) or _color_mix_has_literal(line))


def token_bypasses(name: str, text: str) -> list[str]:
    """一个文件里所有「非注释行写了裸色值、又没有同一行 token-exempt」的位置。"""
    suffix = Path(name).suffix
    raw = text.splitlines()
    code = _code_lines_py(text) if suffix == ".py" else _code_lines_web(text, suffix)
    bad = []
    for n, line in sorted(code.items()):
        whole = raw[n - 1] if n - 1 < len(raw) else ""
        if _EXEMPT.search(whole):
            continue
        if _is_bypass(line):
            bad.append(f"{name}:{n}: {whole.strip()}")
    return bad


def _enforced_files() -> dict[str, str]:
    found = {}
    for root in _SCAN_ROOTS:
        for p in sorted((ROOT / root).rglob("*")):
            if p.suffix not in _SUFFIXES or not p.is_file() or "__pycache__" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "design-tokens" in text and any(_MARKER.match(ln) for ln in text.splitlines()):
                found[p.relative_to(ROOT).as_posix()] = text
    return found


def _flagged_lines(name: str, text: str) -> list[int]:
    return [int(b.split(":")[1]) for b in token_bypasses(name, text)]


def test_绕过检测器自己认得出绕过():
    """判据自己的判据：注释、docstring 里提到色值不算；代码行、三引号里的 CSS、
    ASS 标签、ffmpeg 的 0x、字面值的颜色函数都算；从 token 派生的不算；
    同一行写了 `token-exempt: <理由>` 就放行。

    评审 WP0 复核时量到，第一版只认 `#rrggbb` 和大写 `&H`：`#fff`、`rgba(…)`、
    `oklch(…)`、`0xc6f65a`、小写 `&h8cdc4a` 全都判成干净——而看板 `styles.css`
    里有 25 个 `rgba(` 字面色，WP1 一打标记就是一条恒绿的闸。
    """
    py = (
        '"""doc 里提到 #123456 和 rgba(0,0,0,.5) 不算"""\n'  # 1
        "# design-tokens: enforced\n"                # 2
        'A = "#123456"\n'                            # 3 ← 红
        'B = "#abcdef"  # token-exempt: 测试豁免\n'  # 4
        '# C = "#654321" 注释里不算\n'               # 5
        'D = r"{\\c&H8CDC4A&}"\n'                    # 6 ← 红
        'CSS = """\n'                                # 7
        ".x{color:#0a0b0c}\n"                        # 8 ← 红
        '"""\n'                                      # 9
        'E = "page.html#abcdef"\n'                   # 10 URL 片段不算
        'F = "color=0xc6f65a@0.5"\n'                 # 11 ← 红（ffmpeg）
        'G = r"{\\c&h8cdc4a&}"\n'                    # 12 ← 红（小写 &h）
        'H = rgb(DARK["background"])\n'              # 13 调 token 模块的 rgb() 不算
        'I = f"rgba({panel},.9)"\n'                  # 14 从 token 拼的不算
        'J = "box-shadow:0 2px 6px rgba(0,0,0,.9)"\n'  # 15 ← 红
        'K = "#fff"\n'                               # 16 ← 红（3 位）
        'L = 0x10\n'                                 # 17 小整数不算
        'M = "{:#010x}".format(n)\n'                 # 18 格式串不算
        'N = "&hellip;"\n'                           # 19 HTML 实体不算
    )
    assert _flagged_lines("x.py", py) == [3, 6, 8, 11, 12, 15, 16]

    css = (
        "/* design-tokens: enforced */\n"                                 # 1
        ".a{color:#123456}\n"                                              # 2 ← 红
        "/* #654321 注释里不算 */\n"                                       # 3
        ".b{background:#ff2442} /* token-exempt: 红按钮 */\n"              # 4
        ".c{color:var(--tl-foreground)}\n"                                 # 5
        ".d{color:#12345678}\n"                                            # 6 ← 红（8 位）
        ".e{color:#fff}\n"                                                 # 7 ← 红（3 位）
        ".f{color:#ffff}\n"                                                # 8 ← 红（4 位）
        ".g{background:rgba(14, 32, 24, .82)}\n"                           # 9 ← 红
        ".h{color:rgb(0 0 0 / .5)}\n"                                      # 10 ← 红
        ".i{color:hsl(120deg 50% 50%)}\n"                                  # 11 ← 红
        ".j{color:oklch(0.91 0.188 124.7)}\n"                              # 12 ← 红
        ".k{color:oklab(0.5 0.1 0.1)}\n"                                   # 13 ← 红
        ".l{color:color-mix(in srgb, white 10%, var(--tl-card))}\n"        # 14 ← 红（命名色）
        ".m{color:color-mix(in oklab, var(--tl-success) 18%, transparent)}\n"  # 15 从 token 派生
        ".n{color:rgb(var(--tl-foreground-rgb) / .5)}\n"                   # 16 从 token 派生
        "#add-btn{color:var(--tl-link)}\n"                                 # 17 id 选择器不算
        ".o{background:RGBA(0,0,0,.5)}\n"                                  # 18 ← 红（大小写不敏感）
        ".p{color:color-mix(in srgb, var(--tl-a) 40%, #fff)}\n"           # 19 ← 红
    )
    assert _flagged_lines("x.css", css) == [2, 6, 7, 8, 9, 10, 11, 12, 13, 14, 18, 19]

    js = (
        "// design-tokens: enforced\n"                      # 1
        "el.style.color = '#c6f65a';\n"                     # 2 ← 红
        "// el.style.color = '#c6f65a'; 注释里不算\n"       # 3
        "ctx.fillStyle = 0xc6f65a;\n"                       # 4 ← 红
        "el.style.color = 'var(--tl-primary)';\n"           # 5
        "location.href = 'https://a.b/#top';\n"             # 6
    )
    assert _flagged_lines("x.js", js) == [2, 4]
    assert all(_MARKER.match(s.splitlines()[i]) for s, i in ((py, 1), (css, 0), (js, 0)))


#: 打了 enforced 标记的文件——**只许加不许减**。
#:
#: 评审复核时量的：原来只钉了示意图色板一个文件，把 `design_compare_sheet.py`
#: 那行标记删掉，那个文件的检测就不吭声地关了。现在标记和这张表必须一一对应：
#: 删标记（或挪走、删掉文件）→ 红在「被拿掉了」；新打标记 → 红在「要登记」，
#: 登记之后再想拿掉，就得同时改这张表，在 diff 里看得见。WP1–WP8 接完 token
#: 各自往这儿加一行。
_ENFORCED_FLOOR = (
    "dashboard/styles.css",                  # WP1 看板：样式只写 var(--tl-…)
    "src/tennislive/render/knowledge.py",    # WP2 推送：字卡那条推送正文
    "src/tennislive/render/push_style.py",   # WP2 推送 + 复制页的唯一样式出处
    "src/tennislive/video/diagram_palette.py",
    "src/tennislive/video/explainer_card_palette.py",  # WP4 字卡
    "src/tennislive/video/outro_page.py",    # WP7 片尾
    "src/tennislive/video/watermark.py",     # WP6 常驻角标
    "tools/build_interview_clip.py",         # WP3 赛后开麦封面、收尾卡、字幕
    "tools/design_compare_sheet.py",
    "tools/gen_tokens_css.py",
    "tools/push_reel.py",                    # WP2 推送：赛场之上／赛后开麦／剪辑片
    "tools/render_stat_card.py",             # WP8 数据统计图
    "tools/versus_poster.py",                # WP5 赛场之上封面
)


def test_enforced名单只许加不许减():
    assert list(_ENFORCED_FLOOR) == sorted(set(_ENFORCED_FLOOR)), "名单要排序、不许重复"
    marked = set(_enforced_files())
    dropped = [p for p in _ENFORCED_FLOOR if p not in marked]
    assert not dropped, (
        "这几个文件的 design-tokens enforced 标记被拿掉了（或文件被挪走 / 删了），"
        f"它们的绕过检测不吭声地关了：{dropped}")
    unlisted = sorted(marked - set(_ENFORCED_FLOOR))
    assert not unlisted, f"新打了标记的文件要登记进 _ENFORCED_FLOOR：{unlisted}"


def test_打了enforced标记的文件不许绕过token():
    """凡是带 `design-tokens: enforced` 标记的文件，非注释行里不许出现裸色值
    （`#rgb`…`#rrggbbaa`、ASS 的 `&H…`、ffmpeg 的 `0x…`、字面值的 CSS 颜色函数、
    带字面操作数的 color-mix），除非同一行写了 `token-exempt: <理由>`
    （推送红按钮 #ff2442 那一行就靠它）。

    ⚠️ 扫描面是 `src/`、`tools/`、`dashboard/` 下所有 .py/.css/.js/.html，
    标记由文件自己认领——WP1–WP8 各自接完 token 就给自己的文件打上，并登记进
    `_ENFORCED_FLOOR`。
    """
    marked = _enforced_files()
    assert "src/tennislive/video/diagram_palette.py" in marked, (
        f"判据失效：标记过的文件里没有示意图色板，扫到的是 {sorted(marked)}")
    # 在真文件上再自证一次：每一种裸色值塞进去都必须被抓到
    base = marked["src/tennislive/video/diagram_palette.py"]
    for evil in ('"#123456"', '"#fff"', '"rgba(0,0,0,.5)"', '"oklch(0.9 0.1 120)"',
                 '"color=0xc6f65a"', 'r"{\\c&h8cdc4a&}"'):
        probe = base + f"EVIL = {evil}\n"
        assert token_bypasses("probe.py", probe), f"塞进去的 {evil} 没被抓到——检测器是恒真的"

    bad = [b for name, text in marked.items() for b in token_bypasses(name, text)]
    assert not bad, (
        "这几行绕过了 design token（写了裸色值）：\n" + "\n".join(bad)
        + "\n修法：从 tennislive.design_tokens 取角色；真要保留字面值的，"
          "同一行写 `token-exempt: <理由>`。")


# ── 4. tokens.css ──────────────────────────────────────────────────────────
def _css_blocks(css: str) -> list[tuple[tuple[str, ...], str]]:
    """(外层 @media…, 选择器) → 声明体。只认这份生成物的形状（最多两层嵌套）。"""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: list[tuple[tuple[str, ...], str]] = []
    stack: list[str] = []
    buf = ""
    for ch in css:
        if ch == "{":
            stack.append(buf.strip())
            buf = ""
        elif ch == "}":
            if buf.strip():
                out.append((tuple(stack), buf))
            stack.pop()
            buf = ""
        else:
            buf += ch
    assert not stack, "花括号没配平"
    return out


def _declared(body: str) -> set[str]:
    return set(re.findall(r"(--[\w-]+)\s*:", body))


def test_tokens_css是生成物():
    """`tools/gen_tokens_css.py` 表里的每一份都必须和
    `design_tokens.tokens_css(default=…)` 逐字节相等——改了模块忘了重跑
    `python3 tools/gen_tokens_css.py`，当场红。"""
    import gen_tokens_css as G  # noqa: PLC0415

    assert G.OUTPUTS == {"dashboard/tokens.css": "system"}, "看板跟随系统（Q10）"
    for rel, default in G.OUTPUTS.items():
        css = (ROOT / rel).read_text(encoding="utf-8")
        assert css == T.tokens_css(default=default), (
            f"{rel} 过期了：重跑 python3 tools/gen_tokens_css.py")

    css = T.tokens_css(default="system")
    blocks = {sel: body for sel, body in _css_blocks(css)}
    dark = blocks[(':root[data-theme="dark"]',)]
    light = blocks[(':root[data-theme="light"]',)]
    for role, value in T.DARK.items():
        assert f"{T.css_var(role)}: {value};" in dark
    for role, value in T.LIGHT.items():
        assert f"{T.css_var(role)}: {value};" in light
    base = blocks[(":root",)]
    assert f"--tl-radius: {T.RADIUS_WEB['base']}px;" in base
    assert f"--tl-ease-out: {T.MOTION['ease_out']};" in base
    for k, v in T.MOTION.items():
        if k.endswith("_ms"):
            assert f"--tl-duration-{k[:-3]}: {v}ms;" in base
    reduced = css.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert "transition-duration: .01ms" in reduced and "animation-duration: .01ms" in reduced
    with pytest.raises(ValueError):
        T.css_vars("sepia")
    with pytest.raises(ValueError):
        T.tokens_css(default="sepia")
    with pytest.raises(TypeError):
        T.tokens_css()  # type: ignore[call-arg]  # 没有缺省值：每个消费方自己认领


def test_CSS变量带tl前缀_和看板自己的变量不撞名():
    """看板 `styles.css` 里 `--muted` 是**字色** #91a99b（`color:var(--muted)` 10 处）、
    `--radius` 是 20px；token 的 `muted` 是**面** #102d23、`radius` 是 10。同名的话，
    tokens.css 在层叠里赢了，那 10 处字就压成约 1.3:1 的面色；输了，token 就没接上。
    所以生成的变量一律 `--tl-` 前缀，而且和 dashboard 下任何别的 CSS 定义的变量
    一个都不许重名。"""
    ours: set[str] = set()
    for _, body in _css_blocks(T.tokens_css(default="system")):
        ours |= _declared(body)
    assert ours and all(v.startswith("--tl-") for v in ours), sorted(
        v for v in ours if not v.startswith("--tl-"))
    assert T.css_var("muted") == "--tl-muted"

    theirs: dict[str, set[str]] = {}
    for p in sorted((ROOT / "dashboard").glob("*.css")):
        if p.name == "tokens.css":
            continue
        theirs[p.name] = _declared(p.read_text(encoding="utf-8"))
    # WP1 之后看板 styles.css 一个自己的变量都不定义了（只用 var(--tl-…)），
    # 所以「扫到了 --muted」这条自证换成：styles.css 确实被扫了，而且撞名检测
    # 拿老看板那两个名字喂进去必须报出来——不然这条是恒真的绿灯。
    assert "styles.css" in theirs, "判据失效：看板的 styles.css 没扫到"
    old_dashboard = _declared(":root{--muted:#91a99b;--radius:20px}")
    assert old_dashboard - ours == old_dashboard, "判据失效：老看板的 --muted/--radius 本该不撞"
    assert {"--tl-muted"} & ours and _declared(":root{--tl-muted:#000}") & ours, (
        "判据失效：同名变量喂进去没被认成撞名")
    clash = {name: sorted(names & ours) for name, names in theirs.items() if names & ours}
    assert not clash, f"和看板自己的变量撞名：{clash}"


def test_主题跟随系统_钉死的data_theme优先_裸root不写color_scheme():
    """账号所有者 Q10：看板跟随系统。生成物里：

    - 裸 `:root`（与主题无关的那块）**不写 `color-scheme`**——评审复核时量到，
      原来那句 `:root{color-scheme:dark}` 会把任何链接了 tokens.css、又没写
      `data-theme="light"` 的页面的浏览器画布翻成深色；
    - `data-theme="dark|light"` 钉死的两块，永远在；
    - 跟随系统：浅色那块写在 `@media` 外面兜底、深色那块包在
      `prefers-color-scheme: dark` 里、**排在浅色后面**（同特异度，后写的赢），
      选择器都是「没钉死」的 `:root`，钉死了就让位。⚠️ 原来浅色也包在
      `prefers-color-scheme: light` 里——认不出这条媒体查询的 WebView（老 Android／X5、
      iOS < 12.1）两块都不生效，页面一个颜色都没有（WP1 复核的 nit）；
    - 浅色块声明的变量 = 深色块 − 画布专用的（`DARK_ONLY` 和图表），画布角色在
      任何一块浅色里都不出现（不会悄悄继承一个深色值）。
    """
    unpinned = ':root:not([data-theme="light"]):not([data-theme="dark"])'
    css = T.tokens_css(default="system")
    blocks = _css_blocks(css)
    by_sel = {sel: body for sel, body in blocks}
    assert "color-scheme" not in by_sel[(":root",)]
    assert set(by_sel) >= {
        (":root",), (':root[data-theme="dark"]',), (':root[data-theme="light"]',),
        (unpinned,), ("@media (prefers-color-scheme: dark)", unpinned),
    }
    schemes = {sel: re.findall(r"color-scheme:\s*(\w+)", body) for sel, body in blocks}
    assert {sel: s for sel, s in schemes.items() if s} == {
        (':root[data-theme="dark"]',): ["dark"],
        (':root[data-theme="light"]',): ["light"],
        (unpinned,): ["light"],
        ("@media (prefers-color-scheme: dark)", unpinned): ["dark"],
    }, "没钉死的颜色只许一块在 @media 外面（浅色兜底），否则认不出媒体查询的浏览器没颜色"
    order = [sel for sel, _ in blocks]
    assert order.index((unpinned,)) < order.index(("@media (prefers-color-scheme: dark)", unpinned)), \
        "深色要排在浅色兜底后面，否则系统要深色时被浅色盖回去"
    dark_vars = _declared(by_sel[(':root[data-theme="dark"]',)])
    light_vars = _declared(by_sel[(':root[data-theme="light"]',)])
    assert light_vars == dark_vars - T.dark_only_vars()
    assert T.dark_only_vars() <= dark_vars
    assert _declared(by_sel[("@media (prefers-color-scheme: dark)", unpinned)]) == dark_vars
    assert _declared(by_sel[(unpinned,)]) == light_vars

    # 默认深色的消费方：深色块兼认「没钉死」，不跟随系统，裸 :root 照样不写
    dark_default = _css_blocks(T.tokens_css(default="dark"))
    by_sel = {sel: body for sel, body in dark_default}
    assert not any(s and s[0].startswith("@media (prefers-color-scheme") for s, _ in dark_default)
    assert "color-scheme" not in by_sel[(":root",)]
    assert "color-scheme: dark;" in by_sel[(unpinned,)]
    assert _declared(by_sel[(unpinned,)]) == dark_vars


# ── 5. 示意图色板 · 对比图工具 · 指针 ───────────────────────────────────────
def test_示意图色板只换了出处_值一个没动():
    """`diagram_palette` 的五个名字改成从 token 取；值钉在迁移前的字面值上。

    重渲 weeks-at-no1 / golden-masters / heat-rule 共 19 屏，前后 JPEG 逐字节
    相同。卡片那一头的判据（`test_card_palette.py`、`test_示意图的颜色要和卡片本身是同一套`）
    照旧管着 CSS 和色板对不对得上。
    """
    from tennislive.video import diagram_palette as P  # noqa: PLC0415

    assert (P.INK, P.SOFT, P.LIME, P.FILL, P.AMBER) == (
        "#f4fbf7", "#cfe6d8", "#c6f65a", "#8fd6a8", "#ffd166")
    assert P.INK == T.DARK["foreground"] and P.SOFT == T.DARK["muted-foreground"]
    assert P.LIME == T.DARK["primary"] and P.FILL == T.DARK["fill"]
    assert P.AMBER == T.DARK["warning"]


def test_对比图工具认得出零差和一个像素的差(tmp_path):
    """`design_compare_sheet` 是后面各包「零视觉变化」的自证工具，它自己得先
    分得清 0 和 1：一个像素的蓝通道差 1，最大差要报 1、变了的像素要 > 0；
    **只改透明度**也要报出来（转成 RGB 再比，alpha 的差就没了）。"""
    from PIL import Image  # noqa: PLC0415

    import design_compare_sheet as D  # noqa: PLC0415

    a = Image.new("RGB", (400, 300), T.rgb(T.DARK["card"]))
    b = a.copy()
    r, g, bl = b.getpixel((0, 0))
    b.putpixel((0, 0), (r, g, bl + 1))
    same = D.mean_abs_diff(a, a.copy())
    assert same["mean"] == 0 and same["max"] == 0 and same["changed_ratio"] == 0
    one = D.mean_abs_diff(a, b)
    assert one["max"] == 1 and one["changed_ratio"] > 0 and not one["resized"]
    assert one["mean"] == pytest.approx(1 / (400 * 300 * 3))  # 均差仍按 RGB 三通道

    ca = Image.new("RGBA", (40, 30), T.rgb(T.DARK["primary"]) + (255,))
    cb = ca.copy()
    cb.putpixel((5, 5), T.rgb(T.DARK["primary"]) + (254,))
    alpha_only = D.mean_abs_diff(ca, cb)
    assert alpha_only["max"] == 1 and alpha_only["max_alpha"] == 1
    assert alpha_only["changed_ratio"] > 0 and alpha_only["mean"] == 0

    out = tmp_path / "sheet.jpg"
    stats = D.compare_sheet([[("现状", a), ("方案", b)]], out, title="自检", diff=True)
    assert stats[0]["max"] == 1
    with Image.open(out) as im:
        assert im.format == "JPEG" and im.size[0] <= D.MAX_WIDTH
    # 宽度上限在函数里守，不只在命令行守
    with pytest.raises(ValueError):
        D.compare_sheet([[("现状", a), ("方案", b)]], tmp_path / "wide.jpg",
                        max_width=D.MAX_WIDTH + 1)


def test_对比图工具读完就关文件(tmp_path):
    """`Image.open` 是惰性的：多帧的 GIF 在 `convert` 之后句柄还挂着，要等垃圾
    回收才关，并报 ResourceWarning。工具一次读几十张图，句柄要当场关。"""
    from PIL import Image  # noqa: PLC0415

    import design_compare_sheet as D  # noqa: PLC0415

    gif = tmp_path / "anim.gif"
    frames = [Image.new("RGB", (8, 8), (i * 60, 0, 0)) for i in range(3)]
    frames[0].save(gif, save_all=True, append_images=frames[1:])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        D.mean_abs_diff(gif, gif)
        gc.collect()
    leaked = [w for w in caught if issubclass(w.category, ResourceWarning)]
    assert not leaked, [str(w.message) for w in leaked]


#: token 工具链自己的文件：里面引用的 `test_…` 名字必须真的存在。
_POINTER_FILES = (
    "src/tennislive/design_tokens.py",
    "src/tennislive/render/push_style.py",
    "tools/gen_tokens_css.py",
    "tools/design_compare_sheet.py",
    "tests/test_design_tokens.py",
    "tests/test_push_visual.py",
    # WP1 看板：注释里点名的判据同样要指得到
    ".github/workflows/pages.yml",
    ".github/workflows/pipeline-health.yml",
    "dashboard/app.js",
    "dashboard/index.html",
    "dashboard/styles.css",
    "tools/build_dashboard_snapshot.py",
    "tools/pipeline_health.py",
)


def test_文档里指向的判据名字都真的存在():
    """`gen_tokens_css.py` 的 docstring 原来写着一个不存在的测试名（多了一个
    下划线），评审复核时才发现——指针指不到东西，下一个人照着找就扑空。
    现在这几个文件里出现的每个 `test_…`，要么是 tests/ 里某个 `def test_…`，
    要么是 tests/ 下的一个测试文件名。"""
    tests_dir = ROOT / "tests"
    defined = set()
    for p in tests_dir.rglob("test_*.py"):
        defined.add(p.stem)
        defined |= set(re.findall(r"^\s*def (test_\w+)\(", p.read_text(encoding="utf-8"), re.M))
    dangling = {}
    for rel in _POINTER_FILES:
        names = set(re.findall(r"(?<![\w/])test_\w+", (ROOT / rel).read_text(encoding="utf-8")))
        missing = sorted(names - defined)
        if missing:
            dangling[rel] = missing
    assert not dangling, f"指向不存在的判据：{dangling}"
