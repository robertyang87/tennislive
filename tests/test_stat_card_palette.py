"""数据统计对照图的配色、台头和数字字体（UI/VI 评审 WP8，账号所有者 2026-09-27）。

三条决定，各钉一条判据：

- **Q3 深色底**：藏青底 ＋ 四色径向光 → 品牌墨绿底，**只留黄绿和薄荷**。和片里
  其余几张卡（标题卡、片尾、字卡）同一支墨；原来一部片子里两套深底。
- **Q1 绿色分工**：黄绿 #c6f65a 是唯一品牌色，薄荷 #4adc8c **只表示「这一方赢了」**。
  数据图的赢盘原来是黄绿（同一部片子里「赢一盘」有三种画法），改成薄荷，和视频
  顶栏的赢盘同一支（`SCORE["win_video"]`）；赢家头像那一圈描边说的也是「赢了」，
  一起换。黄绿留给品牌和「这一项谁占优」。
- **Q15 台头与数字**：台头「网球时差 · 数据复盘」→「网球时差 · 赛场之上」
  （「数据复盘」是三个栏目之外的第四个名字）；技术统计数字也走 `TL Score`，
  一张卡上只有一副数字。

判据都只读 `build()` 出的 HTML，不用 Chromium，CI 上跑得起来。配色那条按**色相**
判，不按色值表判：「只留黄绿和薄荷」是一句关于色族的话，哪天有人往底上加一团
蓝光，不管写成哪个色值都会红。
"""
from __future__ import annotations

import colorsys
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import render_stat_card as sc  # noqa: E402
from tennislive.design_tokens import DARK, SCORE  # noqa: E402

# 单打一条、双打一条（双打的描边是两个小圆，走另一段 markup）
_SPECS = ("wong-vallejo-hangzhou-2026-r2", "ruud-zverev-doubles-laver-cup-2026")

#: 色族：oklch 那套分法落到 HSV 色相上（#c6f65a ≈ 78.5°，#4adc8c ≈ 147°，
#: 墨绿底 #04120d / #0c1d16 ≈ 154°）。
_LIME = (68.0, 92.0)
_MINT = (138.0, 166.0)

_COLOR = re.compile(
    r"#(?P<h8>[0-9a-fA-F]{8})\b|#(?P<h6>[0-9a-fA-F]{6})\b"
    r"|rgba?\((?P<r>\d+),\s*(?P<g>\d+),\s*(?P<b>\d+)")


def _html(slug: str, variant: str) -> str:
    spec = json.loads((ROOT / f"specs/reels/{slug}.json").read_text(encoding="utf-8"))
    return sc.build(spec, variant=variant)


def _rules(html: str) -> list[tuple[str, str]]:
    """<style> 里的 (选择器, 声明) 对。@font-face 那几条（内联字体）跳过。"""
    css = html.split("<style>", 1)[1].split("</style>", 1)[0]
    css = re.sub(r"@font-face\{[^}]*\}", "", css)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _decl(html: str, selector: str, prop: str) -> str:
    hits = [body for sel, body in _rules(html) if sel == selector]
    assert hits, f"CSS 里找不到 `{selector}`——选择器改名了？"
    got = re.search(rf"(?:^|;)\s*{re.escape(prop)}\s*:\s*([^;]+)", hits[-1])
    assert got, f"`{selector}` 里没有 `{prop}`：{hits[-1]!r}"
    return got.group(1).strip()


def _chromatic(css_body: str) -> list[tuple[str, float]]:
    """声明里出现的「有颜色」的颜色 → (原文, 色相°)。灰、黑、白不算。

    阈值：饱和度 ≥0.3 且亮度 ≥0.04——墨绿底（亮度 0.07）和藏青底（#141a30，
    亮度 0.19）都要被看见，才分得出「底是哪一族」；台头那档浅绿灰 #dcefe4、
    比分连字符 #93a79c 饱和度都在 0.13 以下，是中性色。
    """
    out = []
    for m in _COLOR.finditer(css_body):
        if m.group("h8") or m.group("h6"):
            hx = (m.group("h8") or m.group("h6"))[:6]
            r, g, b = (int(hx[i:i + 2], 16) for i in (0, 2, 4))
        else:
            r, g, b = (int(m.group(k)) for k in "rgb")
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s >= 0.3 and v >= 0.04:
            out.append((m.group(0), h * 360))
    return out


@pytest.mark.parametrize("variant", sorted(sc.VARIANTS))
@pytest.mark.parametrize("slug", _SPECS)
def test_数据图底色是品牌墨绿_颜色只留黄绿和薄荷(slug, variant):
    """Q3：藏青底 ＋ 蓝红两团光拿掉。除了顶部四色彩条（账号所有者锁定），
    整张卡上每一个「有颜色」的颜色都得落在黄绿或薄荷那一族。"""
    html = _html(slug, variant)
    stray = []
    for sel, body in _rules(html):
        if sel == ".bar":          # 顶部四色彩条：锁定的品牌元素，不在这条规矩里
            continue
        for literal, hue in _chromatic(body):
            if not (_LIME[0] <= hue <= _LIME[1] or _MINT[0] <= hue <= _MINT[1]):
                stray.append(f"{sel} → {literal}（色相 {hue:.0f}°）")
    assert not stray, (
        f"{slug} / {variant}：这几处颜色不在黄绿（{_LIME}）或薄荷（{_MINT}）那一族——"
        "账号所有者 2026-09-27 Q3 定的是「品牌墨绿底，只留黄绿和薄荷」：\n  "
        + "\n  ".join(stray))
    body_bg = _decl(html, "body", "background")
    assert DARK["background"] in body_bg, (
        f"{slug} / {variant}：底色不是品牌墨绿 {DARK['background']}：{body_bg!r}")


@pytest.mark.parametrize("variant", sorted(sc.VARIANTS))
def test_数据图赢盘用薄荷_占优用黄绿(variant):
    """Q1：薄荷只表示「这一方赢了」——赢下的那一盘、赢家头像的描边；
    「这一项谁占优」和品牌处一律黄绿。"""
    html = _html(_SPECS[0], variant)
    assert _decl(html, ".setwin", "color") == SCORE["win_video"], (
        "赢下那一盘的数字不是薄荷——和视频顶栏的赢盘（SCORE['win_video']）分叉了")
    assert _decl(html, ".sval.lead .smain", "color") == DARK["primary"], (
        "「这一项谁占优」的数字不是黄绿")
    assert _decl(html, "h1" if variant == "film_band" else ".setplain",
                 "color") == DARK["primary"]
    if variant != "film_band":     # 带式那一版不画头像
        assert _decl(html, ".h2h-ring.win", "border-color") == SCORE["win_video"], (
            "赢家头像的描边不是薄荷——它唯一的意思就是「这一方赢了」")
    # 薄荷只许出现在这几处：说「赢了」的两处，和底上那团薄荷光（Q3「只留黄绿和薄荷」）
    mint = {SCORE["win_video"].lower(), "rgba(74,220,140"}
    used = sorted({sel for sel, body in _rules(html)
                   if any(m in body.lower().replace(" ", "") for m in mint)})
    assert set(used) <= {".setwin", ".h2h-ring.win", "body"}, (
        f"薄荷用在了不说「赢」的地方：{used}")


@pytest.mark.parametrize("variant", sorted(sc.VARIANTS))
def test_数据图台头是赛场之上_统计数字也用TL_Score(variant):
    """Q15：台头「网球时差 · 赛场之上」；技术统计数字和比分同一副 TL Score。"""
    html = _html(_SPECS[0], variant)
    if variant != "film_band":     # 带式那一版没有台头（上面压着视频顶栏）
        assert '<span class="brand">网球时差 · 赛场之上</span>' in html, (
            "台头不是「网球时差 · 赛场之上」")
        assert "数据复盘" not in html, "台头还写着「数据复盘」——三个栏目之外的第四个名字"
    families = [re.search(r"font-family:([^;]+)", body).group(1).split(",")[0].strip()
                for sel, body in _rules(html)
                if sel == ".sval" and "font-family" in body]
    assert families == ["'TL Score'"], (
        f"技术统计数字的第一支字体是 {families}，不是 'TL Score'——一张卡上两副数字")
    numeral = [sel for sel, body in _rules(html) if "TL Numeral" in body]
    assert not numeral, f"还有规则在用 Montserrat（TL Numeral）：{numeral}"
    if variant != "film_band":     # 带式那一版每行定高 76px，不靠行高
        # 换字体那天量的：`TL Score` 的 normal 行高让每一行高 12px，film 版九行
        # 到 1519px、溢出 1440 画布（静默裁掉最后一行）。62px 把行距钉回原来那一格。
        assert _decl(html, ".smain", "line-height") == "62px", (
            "统计数字的行高没钉住——TL Score 的 normal 行高每行多 12px，film 版会溢出画布")


def test_数据图打着token标记():
    """`design-tokens: enforced` 是 `test_design_tokens` 扫描的入口：标记一删，
    这个文件里再写裸色值就没人管了。所以标记本身也要钉住。"""
    lines = (ROOT / "tools/render_stat_card.py").read_text(encoding="utf-8").splitlines()
    assert "# design-tokens: enforced" in (ln.strip() for ln in lines), (
        "render_stat_card.py 的 design-tokens 标记被删了")
