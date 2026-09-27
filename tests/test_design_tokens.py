"""设计 token 模块（`tennislive.design_tokens`）的判据——UI / VI 评审 WP0。

来路：38 个出画面的文件里 185 个不同的 hex、聚类只有 73 簇；同一个名字 `INK`
在两处指两件事；两族绿在抢品牌色。WP0 先把**唯一出处**立起来、值一律取现存值
（零视觉变化），各个面接 token 是 WP1–WP8 的事。这份文件钉五件事：

1. 换算函数和已经锁定的决定逐字节对得上（顶栏赢盘薄荷 = 08-18 那条）
2. 对比度下限——token 自己不许把字调到读不清
3. 打了 enforced 标记的文件不许再写裸色值（绕过检测，带自证）
4. `dashboard/tokens.css` 是生成物，和模块逐字节相等
5. 示意图色板只换了出处，值一个没动
"""

from __future__ import annotations

import ast
import io
import re
import sys
import tokenize
from pathlib import Path

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
    """实色一律 #rrggbb；只有 border / input / ring 三个带 alpha（8 位）。"""
    hex6 = re.compile(r"#[0-9a-f]{6}")
    hex8 = re.compile(r"#[0-9a-f]{8}")
    alpha = {k for k, v in T.DARK.items() if hex8.fullmatch(v)}
    assert alpha == {"border", "input", "ring"}
    for table in (T.DARK, T.LIGHT):
        for role, v in table.items():
            assert hex6.fullmatch(v) or (table is T.DARK and role in alpha), (role, v)
    for v in (*T.CHART, *T.DARK_CHIP.values(), *(c for c, _ in T.BRAND_BAR)):
        assert hex6.fullmatch(v), v
    assert set(T.DARK_CHIP) <= set(T.DARK)


# ── 2. 对比度 ──────────────────────────────────────────────────────────────
def test_对比度下限():
    """深色在 card 和 background 上都量；浅色的次级灰在两种浅底上都 ≥4.5。

    浅色次级灰原来是 #7a8580（白底 3.82，不过 AA），token 里换成 #5f6f68。
    """
    assert T.contrast("#000000", "#ffffff") == pytest.approx(21.0)
    for surface in (T.DARK["card"], T.DARK["background"]):
        assert T.contrast(T.DARK["foreground"], surface) >= 12
        assert T.contrast(T.DARK["muted-foreground"], surface) >= 7
        assert T.contrast(T.DARK["subtle-foreground"], surface) >= 4.5
    assert T.contrast(T.DARK["primary-foreground"], T.DARK["primary"]) >= 7

    for surface in (T.LIGHT["background"], T.LIGHT["card"]):
        assert T.contrast(T.LIGHT["foreground"], surface) >= 12
        assert T.contrast(T.LIGHT["muted-foreground"], surface) >= 4.5
    # 浅色主色（翡翠绿，等 Q8）配白字只到 AA 这一档
    assert T.contrast(T.LIGHT["primary-foreground"], T.LIGHT["primary"]) >= 4.5

    # 判据认得出不合格的：旧的浅色次级灰、白底上的黄绿
    assert T.contrast("#7a8580", "#ffffff") < 4.5
    assert T.contrast(T.DARK["primary"], "#ffffff") < 1.5


# ── 3. 绕过检测 ────────────────────────────────────────────────────────────
#: 标记必须是**一行注释本身**，不是文中提到它——这份测试和 token 模块的
#: docstring 里都提到了这几个字，不能把自己判成被标记的文件。
_MARKER = re.compile(r"^\s*(?:#|//|/\*|\*|<!--)\s*design-tokens:\s*enforced\b")
_HEX = re.compile(r"(?<![0-9A-Za-z_&])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6})(?![0-9A-Za-z_])")
_ASS = re.compile(r"&H[0-9A-Fa-f]{6,8}(?![0-9A-Za-z_])")
_EXEMPT = re.compile(r"token-exempt:\s*\S")
_SUFFIXES = {".py", ".css", ".js", ".mjs", ".html"}
_SCAN_ROOTS = ("src", "tools", "dashboard")


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
        if _HEX.search(line) or _ASS.search(line):
            bad.append(f"{name}:{n}: {whole.strip()}")
    return bad


def _enforced_files() -> dict[str, str]:
    found = {}
    for root in _SCAN_ROOTS:
        for p in sorted((ROOT / root).rglob("*")):
            if p.suffix not in _SUFFIXES or not p.is_file():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            if "design-tokens" in text and any(_MARKER.match(ln) for ln in text.splitlines()):
                found[p.relative_to(ROOT).as_posix()] = text
    return found


def test_绕过检测器自己认得出绕过():
    """判据自己的判据：注释、docstring 里提到色值不算；代码行、三引号里的 CSS、
    ASS 标签都算；同一行写了 `token-exempt: <理由>` 就放行。"""
    py = (
        '"""doc 里提到 #123456 不算"""\n'           # 1
        "# design-tokens: enforced\n"                # 2
        'A = "#123456"\n'                            # 3 ← 红
        'B = "#abcdef"  # token-exempt: 测试豁免\n'  # 4
        '# C = "#654321" 注释里不算\n'               # 5
        'D = r"{\\c&H8CDC4A&}"\n'                    # 6 ← 红
        'CSS = """\n'                                # 7
        ".x{color:#0a0b0c}\n"                        # 8 ← 红
        '"""\n'                                      # 9
        'E = "page.html#abcdef"\n'                   # 10 URL 片段不算
    )
    assert [int(b.split(":")[1]) for b in token_bypasses("x.py", py)] == [3, 6, 8]

    css = (
        "/* design-tokens: enforced */\n"                     # 1
        ".a{color:#123456}\n"                                  # 2 ← 红
        "/* #654321 注释里不算 */\n"                           # 3
        ".b{background:#ff2442} /* token-exempt: 红按钮 */\n"  # 4
        ".c{color:var(--foreground)}\n"                        # 5
        ".d{color:#12345678}\n"                                # 6 ← 红（8 位也算）
    )
    assert [int(b.split(":")[1]) for b in token_bypasses("x.css", css)] == [2, 6]
    assert all(_MARKER.match(s.splitlines()[i]) for s, i in ((py, 1), (css, 0)))


def test_打了enforced标记的文件不许绕过token():
    """凡是带 `design-tokens: enforced` 标记的文件，非注释行里不许出现
    `#rrggbb` / `#rrggbbaa` 或 ASS 的 `&H…`，除非同一行写了
    `token-exempt: <理由>`（推送红按钮 #ff2442 那一行就靠它）。

    ⚠️ 扫描面是 `src/`、`tools/`、`dashboard/` 下所有 .py/.css/.js/.html，
    标记由文件自己认领——WP1–WP8 各自接完 token 就给自己的文件打上。
    反向验证（2026-09-27）：往 `diagram_palette.py` 里塞一行 `X = "#123456"`，
    这条当场红在那一行。
    """
    marked = _enforced_files()
    assert "src/tennislive/video/diagram_palette.py" in marked, (
        f"判据失效：标记过的文件里没有示意图色板，扫到的是 {sorted(marked)}")
    # 在真文件上再自证一次：塞一个裸色值进去必须被抓到
    probe = marked["src/tennislive/video/diagram_palette.py"] + 'EVIL = "#123456"\n'
    assert token_bypasses("probe.py", probe), "塞进去的裸色值没被抓到——检测器是恒真的"

    bad = [b for name, text in marked.items() for b in token_bypasses(name, text)]
    assert not bad, (
        "这几行绕过了 design token（写了裸色值）：\n" + "\n".join(bad)
        + "\n修法：从 tennislive.design_tokens 取角色；真要保留字面值的，"
          "同一行写 `token-exempt: <理由>`。")


# ── 4. tokens.css ──────────────────────────────────────────────────────────
def test_tokens_css是生成物():
    """`dashboard/tokens.css` 必须和 `design_tokens.tokens_css()` 逐字节相等——
    改了模块忘了重跑 `python3 tools/gen_tokens_css.py`，当场红。"""
    css = (ROOT / "dashboard" / "tokens.css").read_text(encoding="utf-8")
    assert css == T.tokens_css(), "tokens.css 过期了：重跑 python3 tools/gen_tokens_css.py"

    dark, light = T.css_vars("dark"), T.css_vars("light")
    assert dark in css and light in css
    for role, value in T.DARK.items():
        assert f"--{role}: {value};" in dark
    for role, value in T.LIGHT.items():
        assert f"--{role}: {value};" in light
    assert f"--radius: {T.RADIUS_WEB['base']}px;" in dark
    assert f"--ease-out: {T.MOTION['ease_out']};" in dark
    for k, v in T.MOTION.items():
        if k.endswith("_ms"):
            assert f"--duration-{k[:-3]}: {v}ms;" in dark
    reduced = css.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert "transition-duration: .01ms" in reduced and "animation-duration: .01ms" in reduced
    # 浅色不自动跟随系统（Q10 没定）
    assert "prefers-color-scheme" not in css
    with pytest.raises(ValueError):
        T.css_vars("sepia")


# ── 5. 示意图色板 ───────────────────────────────────────────────────────────
def test_示意图色板只换了出处_值一个没动():
    """`diagram_palette` 的五个名字改成从 token 取；值钉在迁移前的字面值上。

    重渲 weeks-at-no1 / golden-masters / heat-rule 共 19 屏，前后 JPEG 逐字节
    相同。卡片那一头的判据（`test_card_palette.py`、`test_示意图的颜色要和卡片
    本身是同一套`）照旧管着 CSS 和色板对不对得上。
    """
    from tennislive.video import diagram_palette as P  # noqa: PLC0415

    assert (P.INK, P.SOFT, P.LIME, P.FILL, P.AMBER) == (
        "#f4fbf7", "#cfe6d8", "#c6f65a", "#8fd6a8", "#ffd166")
    assert P.INK == T.DARK["foreground"] and P.SOFT == T.DARK["muted-foreground"]
    assert P.LIME == T.DARK["primary"] and P.FILL == T.DARK["fill"]
    assert P.AMBER == T.DARK["warning"]


def test_对比图工具认得出零差和一个像素的差(tmp_path):
    """`design_compare_sheet` 是后面各包「零视觉变化」的自证工具，它自己得先
    分得清 0 和 1：一个像素的蓝通道差 1，最大差要报 1、变了的像素要 > 0。"""
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

    out = tmp_path / "sheet.jpg"
    stats = D.compare_sheet([[("现状", a), ("方案", b)]], out, title="自检", diff=True)
    assert stats[0]["max"] == 1
    with Image.open(out) as im:
        assert im.format == "JPEG" and im.size[0] <= D.MAX_WIDTH
