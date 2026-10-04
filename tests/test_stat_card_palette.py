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
_NAVY = (210.0, 235.0)

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
def test_数据图底色是统一深蓝_品牌和胜负强调色保留(slug, variant):
    """Q3：藏青底 ＋ 蓝红两团光拿掉。除了顶部四色彩条（账号所有者锁定），
    整张卡上每一个「有颜色」的颜色都得落在黄绿或薄荷那一族。"""
    html = _html(slug, variant)
    stray = []
    for sel, body in _rules(html):
        if sel == ".bar":          # 顶部四色彩条：锁定的品牌元素，不在这条规矩里
            continue
        for literal, hue in _chromatic(body):
            if not (_LIME[0] <= hue <= _LIME[1] or _MINT[0] <= hue <= _MINT[1]
                    or _NAVY[0] <= hue <= _NAVY[1]):
                stray.append(f"{sel} → {literal}（色相 {hue:.0f}°）")
    assert not stray, (
        f"{slug} / {variant}：这几处颜色不在深蓝（{_NAVY}）、黄绿（{_LIME}）或薄荷（{_MINT}）色族——"
        "账号所有者 2026-10-04 更新为全栏目统一深蓝底，保留品牌与胜负强调色：\n  "
        + "\n  ".join(stray))
    body_bg = _decl(html, "body", "background")
    assert DARK["background"] in body_bg, (
        f"{slug} / {variant}：底色不是共享深蓝 {DARK['background']}：{body_bg!r}")


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
    # 三个变体都查：带式那一版没有台头，但它的大标题原来也写着「全场数据复盘」——
    # 评审 2026-09-27 抓到 Q15 那句「第四个栏目名」在带式卡上活了下来
    assert "数据复盘" not in html, "还写着「数据复盘」——三个栏目之外的第四个名字"
    if variant == "film_band":     # 带式那一版没有台头（上面压着视频顶栏）
        assert "<h1>全场数据对比</h1>" in html, (
            "带式那版的大标题不是「全场数据对比」——和 poster 的段标题分叉了")
    else:
        assert '<span class="brand">网球时差 · 赛场之上</span>' in html, (
            "台头不是「网球时差 · 赛场之上」")
        # 一张图上只印一次：poster 的 footer 左边原来也是这一句，台头换成它之后印了两遍
        assert html.count("网球时差 · ") == 1, (
            f"「网球时差 · 栏目」在一张图上印了 {html.count('网球时差 · ')} 遍——"
            "footer 左边又把台头那句写了一遍？")
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


@pytest.mark.parametrize("variant", ["poster", "film"])
def test_数据图台头的栏目名跟着封面走(variant):
    """台头读 `cover.eyebrow`（缺省「赛场之上」），和封面台头、正片常驻角标**同一处**
    ——`build_match_reel` 常驻角标那段注释：各读各的，一部片子里就写着两个栏目。
    写死「赛场之上」的话，一条「网球有故事」剪辑片挂了 `stat_card: true`，
    数据图就在「网球有故事」的角标底下印出「赛场之上」。"""
    spec = json.loads((ROOT / f"specs/reels/{_SPECS[0]}.json").read_text(encoding="utf-8"))
    spec["cover"]["eyebrow"] = "网球有故事"
    html = sc.build(spec, variant=variant)
    assert '<span class="brand">网球时差 · 网球有故事</span>' in html, (
        "封面写的是「网球有故事」，数据图台头没跟着走")
    assert "赛场之上" not in html, "栏目名还有一处是写死的「赛场之上」"
    del spec["cover"]["eyebrow"]
    assert '<span class="brand">网球时差 · 赛场之上</span>' in sc.build(spec, variant=variant), (
        "封面没写 eyebrow 时缺省应该是「赛场之上」（和封面、常驻角标的缺省一样）")


def test_数据图台头的缺省栏目和格式只有一处出处(monkeypatch):
    """评审 2026-09-27（第二轮）：`DEFAULT_COLUMN = "赛场之上"` 原来在 `render_stat_card` 和
    `build_match_reel` 各写一遍，「网球时差 · 栏目」那句格式也和常驻角标的 `watermark.brand_label`
    各写一遍——值今天一样，改一处另一处不报错。

    判据按行为钉，不按源码文本：把出处那一头换掉，台头必须跟着变。"""
    import build_match_reel as reel  # noqa: PLC0415
    from tennislive.video import watermark  # noqa: PLC0415

    assert not hasattr(sc, "DEFAULT_COLUMN"), (
        "render_stat_card 又自己定义了一份 DEFAULT_COLUMN——缺省栏目跟 build_match_reel 走")
    monkeypatch.setattr(reel, "DEFAULT_COLUMN", "某个栏目")
    assert sc.brand_line({}) == "网球时差 · 某个栏目", (
        "eyebrow 空着时台头没跟 build_match_reel.DEFAULT_COLUMN 走——又写死了一份缺省")
    monkeypatch.setattr(watermark, "brand_label", lambda column: f"<{column}>")
    assert sc.brand_line({"eyebrow": "网球有故事"}) == "<网球有故事>", (
        "台头那句的格式没走 watermark.brand_label——和常驻角标那一行各写一份")


def test_数据图打着token标记():
    """`design-tokens: enforced` 是 `test_design_tokens` 扫描的入口：标记一删，
    这个文件里再写裸色值就没人管了。所以标记本身也要钉住。"""
    lines = (ROOT / "tools/render_stat_card.py").read_text(encoding="utf-8").splitlines()
    assert "# design-tokens: enforced" in (ln.strip() for ln in lines), (
        "render_stat_card.py 的 design-tokens 标记被删了")
