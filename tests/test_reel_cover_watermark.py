"""「赛场之上」片内顶栏 ＋ 封面海报 ＋ 常驻角标（2026-09-27 UI/VI 评审 WP5 + WP6）。

每一条判据钉一件改动，都反向验证过（改回去 → 红在自己那一行）：

| 改了什么 | 来路 | 判据 |
|---|---|---|
| 颜色一律从 `design_tokens` 换算，顶栏 HEAD 的 BGR 写反修掉 | 评审根因 1 | `test_顶栏颜色都从token换算…` |
| 顶栏标题行也描边 1.5 | 评审 3.4 | `test_顶栏两行都描边1_5` |
| 顶栏底 45% 实条 → 渐变压暗（0.62 → 200px 处 0） | 账号所有者 Q6 | `test_顶栏底是渐变压暗…` |
| 国旗一圈白 .42 描边 ＋ 3px 圆角 | 评审 R1（澳旗压在藏青长条上消失） | `test_国旗一圈白描边…` |
| 名字和（排名）之间的缝 −0.28em | 评审 R10（空出 31px） | `test_名字和排名之间的缝…` |
| 重点词点亮整行：新 spec 红 | 评审 R6 | `test_钩子重点词不许点亮整行…` |
| 场地名统一英文：新 spec 红 | 账号所有者 Q13 | `test_场地名统一英文…` |
| 常驻角标文字 2px 墨绿描边、阴影收紧 | 账号所有者 Q11 | `test_常驻角标文字带墨绿描边…` |
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_match_reel as reel  # noqa: E402
import versus_poster as vp  # noqa: E402

from tennislive import design_tokens as T  # noqa: E402
from tennislive.video import watermark as wm  # noqa: E402


# ── 顶栏（WP5）───────────────────────────────────────────────────────────────
def _style_fields(ass_text: str, name: str) -> dict[str, str]:
    """把 ASS 里 `Style: <name>,…` 那一行按 Format 拆成字段表。"""
    fmt = next(ln for ln in ass_text.splitlines() if ln.startswith("Format: Name,"))
    keys = [k.strip() for k in fmt.split(":", 1)[1].split(",")]
    row = next(ln for ln in ass_text.splitlines() if ln.startswith(f"Style: {name},"))
    vals = [v.strip() for v in row.split(":", 1)[1].split(",")]
    return dict(zip(keys, vals))


def test_顶栏颜色都从token换算_HEAD的BGR写反修掉(tmp_path):
    """顶栏四支色都经 `design_tokens.ass()` / `ass_inline()` 换算，字节序只有
    一处出处。

    ⚠️ HEAD 那一支原来写死 `&H00F4FBF7`——把 CSS 的 #f4fbf7 原样抄进 ASS，
    渲出来是 #f7fbf4（R、B 各差 3）。和赛后开麦中文字幕 #c3dc74（本意 #74dcc3）
    同一类错。反向验证：把 `TOPBAR_HEAD_HEX` 改回 "#f7fbf4" → 第一条断言红。
    """
    assert reel.TOPBAR_HEAD_COLOUR == T.ass(T.DARK["foreground"]) == "&H00F7FBF4"
    assert reel.TOPBAR_HEAD_COLOUR != "&H00F4FBF7", "BGR 写反又回来了"
    # 下面三支是「值不变、只换出处」：逐字节等于接 token 之前的字面值
    assert reel.TOPBAR_BODY_COLOUR == "&H00DBE2D5" == T.ass(reel.TOPBAR_BODY_HEX)
    assert reel.TOPBAR_SETWIN_ASS == r"{\c&H8CDC4A&}" == T.ass_inline(T.SCORE["win_video"])
    assert reel.TOPBAR_SETDASH_ASS == r"{\c&H009CA793&}"
    assert reel.TOPBAR_SETDASH_ASS == "{\\c" + T.ass(T.SCORE["dash"]) + "&}"

    text = reel.write_topbar_ass(("2026 ATP250 杭州 第二轮", "黄泽林 7-6(2) 4-6 6-3 巴列霍"),
                                 1.0, 5.0, tmp_path / "t.ass").read_text("utf-8")
    assert _style_fields(text, "HEAD")["PrimaryColour"] == reel.TOPBAR_HEAD_COLOUR
    assert _style_fields(text, "BODY")["PrimaryColour"] == reel.TOPBAR_BODY_COLOUR
    # 顶栏这一段源码里不许再有手写的 `&H` 颜色（黑色描边／背景那两个除外）
    src = Path(reel.__file__).read_text("utf-8")
    style_lines = [ln for ln in src.splitlines() if ln.startswith("Style: HEAD,")
                   or ln.startswith("Style: BODY,")]
    assert len(style_lines) == 2
    for ln in style_lines:
        assert not re.search(r"&H(?!00000000)[0-9A-Fa-f]{8}", ln), (
            f"顶栏样式行里又写死了颜色：{ln}")


def test_顶栏两行都描边1_5(tmp_path):
    """标题行原来 Outline=0、比分行 1.5——54px 的得意黑压在亮画面上笔画边缘
    化进底色（评审 `sim_topbar_flat.jpg`）。两行同一个常量。
    反向验证：HEAD 那一格改回 0 → 红在第一条断言。"""
    text = reel.write_topbar_ass(("2026 ATP250 杭州 第二轮", "黄泽林 7-6(2) 4-6 6-3 巴列霍"),
                                 1.0, 5.0, tmp_path / "t.ass").read_text("utf-8")
    assert float(_style_fields(text, "HEAD")["Outline"]) == reel.TOPBAR_OUTLINE_PX == 1.5
    assert float(_style_fields(text, "BODY")["Outline"]) == reel.TOPBAR_OUTLINE_PX
    # 透视球场图标自带 \bord0，不跟着描边
    assert "\\bord0" in text.split("HEAD,,0,0,0,,", 1)[1].split("\n", 1)[0]


def _empty_ass(path: Path) -> Path:
    path.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1440\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: X,Arial,20,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,"
        "10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, "
        "MarginR, MarginV, Effect, Text\n", encoding="utf-8")
    return path


def test_顶栏底是渐变压暗没有硬边_白底上比分行读得出(tmp_path, monkeypatch):
    """账号所有者 2026-09-27 选的 Q6 方案 A：45% 黑实条（硬下边、白天比分行 1.9:1）
    换成渐变：顶上 0.62 → 200px 处 0，没有硬边。**真跑一遍 `topbar_filtergraph`**，
    在纯白底上量三头：

    ① 形状：满档那一段 ≈ 255×(1−0.62)，200px 以下回到纯白；相邻两行最多差几级
       ——老的实条下沿一行跳 114（反向验证：换回 drawbox，这一条红）
    ② 比分行（薄荷 #4adc8c，这一行最淡的那支字色）在它自己那几行的底上 ≥ 3.6:1
       （账号所有者定的「1.9:1 → 3.6:1」，实测 3.62）——满档只铺到 100px（评审图
       那一版）时是 3.31:1（反向验证过，红在这一条）
    ③ 带式不垫（顶带本来就是实色）

    ①② 在比赛画面的第 0.5 / 2 / 4 秒各量一遍：压暗那张图是 `color` 源的**一帧**
    （`d=1`），第 1 秒之后还在，全靠 overlay 默认 `eof_action=repeat` 把它重复下去。
    只在第 0.5 秒量的时候，那一帧本来就还活着——压暗层第 1 秒之后没了，这条照样绿。
    反向验证：overlay 加 `enable='lt(t,1)'`（只压第 1 秒），只量 0.5 秒的老版本
    **1 passed**，这一版红在第 2 秒那一格的 ①。
    """
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了"
    monkeypatch.setattr(reel, "LAYOUT", "full")
    fonts = ROOT / "assets" / "fonts"
    assert fonts.is_dir()
    cover_secs, match_secs = 0.4, 4.6
    ass = reel.write_topbar_ass(("2026 ATP250 杭州 第二轮", "黄泽林 7-6(2) 4-6 6-3 巴列霍"),
                                cover_secs, cover_secs + match_secs, tmp_path / "t.ass")
    graph = reel.topbar_filtergraph(cover_secs, match_secs, ass, _empty_ass(tmp_path / "e.ass"))
    white = tmp_path / "white.png"
    Image.new("RGB", (1080, 1440), (255, 255, 255)).save(white)
    vid = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "25",
                    "-i", str(white), "-t", f"{cover_secs + match_secs + 0.4:.1f}",
                    "-filter_complex", graph,
                    "-map", "[out]", "-pix_fmt", "yuv444p", "-c:v", "libx264",
                    "-preset", "ultrafast", "-qp", "0", str(vid)], check=True, cwd=ROOT)
    solid = round(255 * (1 - reel.TOPBAR_SCRIM_ALPHA))

    for at in (0.5, 2.0, 4.0):                        # 比赛画面里的第几秒
        frame = tmp_path / f"f{at}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{cover_secs + at:.2f}",
                        "-i", str(vid), "-frames:v", "1", str(frame)], check=True)
        a = np.asarray(Image.open(frame).convert("RGB"), dtype=int)

        # ① 形状：x=1060 这一列没有字
        prof = a[:260, 1060, 0]
        top = int(prof[: reel.TOPBAR_SCRIM_SOLID_PX].max())
        assert abs(top - solid) <= 3, (
            f"第 {at} 秒：满档那一段应该是 {solid} 上下，量到 {top}"
            + ("——前面几格还在、这一格没了：压暗那一帧没被一直重复下去"
               "（overlay 的 eof_action / enable）" if at > 1 else ""))
        assert prof[reel.TOPBAR_SCRIM_FADE_PX + 2:].min() >= 250, (
            f"第 {at} 秒：200px 以下还没回到画面本色")
        jump = int(np.abs(np.diff(prof)).max())
        assert jump <= 8, f"第 {at} 秒：压暗层有硬边，相邻两行差 {jump}/255（老实条下沿一行跳 114）"

        # ② 比分行：找薄荷的墨（第二行，避开第一行最前面那块同色的球场图标）
        mint = (a[..., 1] - a[..., 0] > 60) & (a[..., 1] - a[..., 2] > 30)
        rows = np.where(mint[reel.TOPBAR_BODY_TOP - 5:reel.TOPBAR_H, 330:900].any(axis=1))[0]
        assert rows.size, f"第 {at} 秒：比分行一个薄荷字都没量到——顶栏没渲出来"
        y0, y1 = reel.TOPBAR_BODY_TOP - 5 + rows.min(), reel.TOPBAR_BODY_TOP - 5 + rows.max()
        bg = a[y0:y1 + 1, 1060].max(axis=0)
        ratio = T.contrast(T.SCORE["win_video"], "#%02x%02x%02x" % tuple(int(c) for c in bg))
        assert ratio >= 3.6, (
            f"第 {at} 秒：白底上比分行（y{y0}~{y1}）的薄荷只有 {ratio:.2f}:1——账号所有者"
            "要的是 ≥3.6:1（实测 3.62）；多半是满档那一段没铺到比分行的底")

    # ③ 带式不垫
    monkeypatch.setattr(reel, "LAYOUT", "band")
    band = reel.topbar_filtergraph(0.4, 1.0, ass, ass)
    assert "topbar_scrim" not in band and "drawbox" not in band


# ── 封面（WP6）───────────────────────────────────────────────────────────────
def _scoreboard_cover(hero: Path, **extra) -> dict:
    cover = {
        "eyebrow": "赛场之上", "topic": "拉沃尔杯 第二天 · 德米纳尔 VS 兹维列夫",
        "subject": "德米纳尔", "hook": "决胜盘挽救赛点\n德米纳尔逆转兹维列夫",
        "winner": "德米纳尔", "result": "6-3 6-4",
        "matchup": [
            {"name": "德米纳尔", "name_en": "Alex de Minaur", "country": "AUS", "rank": 9},
            {"name": "兹维列夫", "name_en": "Alexander Zverev", "country": "GER", "rank": 2},
        ],
        "scoreboard": {"court": "The O2", "duration_source": {"url": "fixture"}},
        "portrait": {"image": str(hero)},
    }
    cover.update(extra)
    return cover


def _render(cover: dict, out: Path, monkeypatch) -> np.ndarray:
    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "2:03")
    try:
        reel.render_poster(cover, out, "solo")
    except Exception as exc:                          # noqa: BLE001
        pytest.skip(f"渲不出封面（多半是没装 Chromium）：{exc}")
    return np.asarray(Image.open(out).convert("RGB"), dtype=int)


def _win_bar_rows(a: np.ndarray) -> tuple[int, int]:
    """赢家那条藏青长条（#172786）占哪几行——在 x=700 那一列上量。"""
    blue = (a[..., 2] > 110) & (a[..., 0] < 45) & (a[..., 1] < 65)
    rows = np.where(blue[:, 700])[0]
    assert rows.size, "没量到赢家长条"
    return int(rows.min()), int(rows.max())


def test_国旗一圈白描边_澳旗压在藏青长条上也看得出边(tmp_path, monkeypatch):
    """评审 R1：澳大利亚旗是藏青底，压在同样藏青的赢家长条（#172786）上整面旗
    和长条融成一块（`crop_flag_aus_on_navy.jpg`）；单打原来没有描边、双打那面
    压上去的旗是 2px 黑——两种做法。现在一律 1.5px 白 .42 ＋ 3px 圆角，旗子仍是矩形。

    ① **像素**：澳旗左缘外 1px 那一列（描边），在旗面下半（藏青那一截）比
       左边的长条和右边的旗面**都亮**（反向验证：删掉 box-shadow → 红在这一条）
    ② CSS：单打和双打同一道描边，没有第二种（反向验证：把双打那条黑边加回来 → 红）
    """
    hero = tmp_path / "hero.jpg"
    Image.new("RGB", (1080, 1440), (40, 30, 30)).save(hero)
    a = _render(_scoreboard_cover(hero), tmp_path / "p.jpg", monkeypatch)
    top, bottom = _win_bar_rows(a)
    mid = (top + bottom) // 2
    x0 = 70 + vp.SCORE_FILL_PAD_L          # 旗面左缘：`.storycopy` 左 70 ＋ 长条左内边距
    rows = range(mid + 6, mid + vp.SCORE_FLAG_H // 2 - 4)   # 旗面下半：藏青底 ＋ 南十字
    lum = a[..., :].mean(axis=2)
    ring = np.array([lum[y, x0 - 1] for y in rows])
    bar = np.array([lum[y, x0 - 7] for y in rows])
    flag = np.array([lum[y, x0 + 3] for y in rows])
    assert np.median(ring) > np.median(bar) + 12 and np.median(ring) > np.median(flag) + 12, (
        f"澳旗左缘那一圈描边（中位亮度 {np.median(ring):.0f}）不比长条"
        f"（{np.median(bar):.0f}）和旗面（{np.median(flag):.0f}）亮——"
        "藏青旗压在藏青长条上又融成一块了")

    body, css = vp._solo_body(_scoreboard_cover(hero))
    rule = re.search(r"\.score-flag\{([^}]*)\}", css).group(1)
    assert "border-radius:3px" in rule
    assert "box-shadow:0 0 0 1.5px rgba(255,255,255,0.42)" in rule
    pair_rules = re.findall(r"\.score-flag-pair[^{]*\{([^}]*)\}", css)
    assert pair_rules and not any("box-shadow" in r or "border-radius" in r
                                  for r in pair_rules), (
        "双打那面旗又单独写了一道描边——单打双打要同一种做法")


def test_名字和排名之间的缝跟着SCORE_RANK_GAP_EM走(tmp_path, monkeypatch):
    """评审 R10：全角「（」的左半个字面是空的，原来 `margin-left:4px` 叠上它，
    梅德韦杰夫和（6）之间实量空出 31px。现在 `.score-rank` 的缝是
    `SCORE_RANK_GAP_EM`（−0.28em），**CSS 和量宽度的 `_name_width_px` 读同一个常量**。

    ① CSS 里真的是这个常量（反向验证：CSS 写回 4px → 红）
    ② `_name_width_px` 跟着它变（反向验证：量宽度那头写回 +4 → 红）
    ③ 真渲：名字墨和括号墨之间 ≤ 20px（改前 31）
    浏览器那一头的宽度对账归 `test_scoreboard_template::test_量名字宽度要和浏览器对得上`。
    """
    hero = tmp_path / "hero.jpg"
    Image.new("RGB", (1080, 1440), (40, 30, 30)).save(hero)
    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "2:03")
    _, css = vp._solo_body(_scoreboard_cover(hero))
    rank_rule = re.search(r"\.score-rank\{([^}]*)\}", css).group(1)
    assert f"margin-left:{vp.SCORE_RANK_GAP_EM}em" in rank_rule, rank_rule
    assert vp.SCORE_RANK_GAP_EM < 0

    w = vp._name_width_px("梅德韦杰夫", 6, 52)
    gap = vp.SCORE_RANK_GAP_EM
    monkeypatch.setattr(vp, "SCORE_RANK_GAP_EM", 0.0)
    assert vp._name_width_px("梅德韦杰夫", 6, 52) - w == pytest.approx(
        -52 * vp.SCORE_RANK_EM * gap, abs=0.01), "量宽度那头没跟着 SCORE_RANK_GAP_EM 走"
    monkeypatch.setattr(vp, "SCORE_RANK_GAP_EM", gap)

    cover = _scoreboard_cover(hero, winner="梅德韦杰夫", result="7-6(6) 6-3", matchup=[
        {"name": "梅德韦杰夫", "name_en": "Daniil Medvedev", "country": "RUS", "rank": 6},
        {"name": "鲁瓦耶", "name_en": "Valentin Royer", "country": "FRA", "rank": 104}])
    a = _render(cover, tmp_path / "m.jpg", monkeypatch)
    top, bottom = _win_bar_rows(a)
    band = a[top + 40:bottom - 5, 180:700]
    cols = np.where((band.min(axis=2) > 200).any(axis=0))[0] + 180
    gaps = [int(cols[i + 1] - cols[i]) for i in range(len(cols) - 1) if cols[i + 1] - cols[i] > 8]
    assert gaps, "没量到名字和括号之间的缝"
    assert max(gaps) <= 20, f"名字和（排名）之间空出 {max(gaps)}px（改前 31）"


def _spec(slug: str, **cover) -> dict:
    return {"slug": slug, "cover": cover}


def test_钩子重点词不许点亮整行_新spec红老spec豁免(capsys):
    """评审 R6（`svitolina-paolini` 那张）：`hook_accent` 等于钩子一整行，整行变绿
    就没有「重点词」了。**新手写 spec 在 `validate_spec` 第一道（`_topbar_lines`）
    就红**，自动产的只报，已发的挂 `LEGACY_WHOLE_LINE_ACCENT`。

    反向验证：把 `hook_accent_problem` 的整行判断拆掉 → 第一条断言红。
    """
    hook = "去年被保利尼逆转\n今年2比0赢回来"
    assert vp.hook_accent_problem({"hook": hook, "hook_accent": "今年2比0赢回来"})
    assert vp.hook_accent_problem({"hook": hook, "hook_accent": "2比0"}) is None
    assert vp.hook_accent_problem({"hook": hook}) is None

    new = _spec("new-slug", hook=hook, hook_accent="今年2比0赢回来")
    with pytest.raises(reel.ReelError, match="一整行"):
        reel._topbar_lines(new)
    auto = {**new, "_production": {"status": "ready_for_render"}}
    reel._topbar_lines(auto)                       # 自动产的只报不拦
    assert "一整行" in capsys.readouterr().out
    assert vp.cover_style_problems(
        _spec("svitolina-paolini-bjk-cup-2026-sf", hook=hook, hook_accent="今年2比0赢回来")) == []


def test_场地名统一英文_新spec红老spec豁免(capsys):
    """账号所有者 2026-09-27（评审 Q13）：比分板场地名统一英文。238 条里 227 条
    英文、11 条中文（10 条是金杯深圳那一周）。新手写 spec 写中文 `--dry-run` 就红。

    反向验证：把 `_CJK` 换成永不匹配 → 第一条断言红。
    """
    zh = {"scoreboard": {"court": "深圳湾体育中心"}}
    assert vp.court_language_problem(zh)
    assert vp.court_language_problem({"scoreboard": {"court": "Shenzhen Bay Sports Center"}}) is None
    assert vp.court_language_problem({"scoreboard": {"court": "Court 7"}}) is None
    with pytest.raises(reel.ReelError, match="场地名统一英文"):
        reel._topbar_lines(_spec("brand-new-bjk", **zh))
    reel._topbar_lines({**_spec("brand-new-bjk", **zh),
                        "_production": {"status": "ready_for_render"}})
    assert "场地名统一英文" in capsys.readouterr().out
    assert vp.cover_style_problems(_spec("zheng-paolini-bjk-cup-2026-qf", **zh)) == []


#: 两张豁免表 2026-09-27 盘点时的样子——**只许减不许加**。
_LEGACY_ZH_COURT_0927 = frozenset({
    "bouzkova-kartal-bjk-cup-2026-qf", "bucsa-noskova-bjk-cup-2026-sf",
    "grant-kalinina-bjk-cup-2026-sf", "muchova-bouzas-bjk-cup-2026-sf",
    "noskova-boulter-bjk-cup-2026-qf", "putintseva-bucsa-bjk-cup-2026",
    "svitolina-paolini-bjk-cup-2026-sf", "wang-vandewinkel",
    "zhang-cocciaretto-bjk-cup-2026-qf", "zheng-paolini-bjk-cup-2026-qf",
    "zhiyenbayeva-bouzas-bjk-cup-2026",
})
_LEGACY_WHOLE_LINE_ACCENT_0927 = frozenset({
    "grant-kalinina-bjk-cup-2026-sf", "svitolina-paolini-bjk-cup-2026-sf",
})


def test_两张封面豁免表只许减不许加_而且每一条真的还犯着():
    """豁免表的自检：多一条（有人往里塞新 spec）红；写错名字、或者那条 spec 已经
    改好了还挂着，也红——否则豁免就成了一盏恒真的绿灯。"""
    assert vp.LEGACY_ZH_COURT <= _LEGACY_ZH_COURT_0927, "场地名豁免表只许减不许加"
    assert vp.LEGACY_WHOLE_LINE_ACCENT <= _LEGACY_WHOLE_LINE_ACCENT_0927, (
        "整行重点词豁免表只许减不许加")
    for slug in vp.LEGACY_ZH_COURT:
        spec = json.loads((ROOT / "specs" / "reels" / f"{slug}.json").read_text("utf-8"))
        assert vp.court_language_problem(spec["cover"]), f"{slug} 已经改成英文了，从豁免表里删掉"
    for slug in vp.LEGACY_WHOLE_LINE_ACCENT:
        spec = json.loads((ROOT / "specs" / "reels" / f"{slug}.json").read_text("utf-8"))
        assert vp.hook_accent_problem(spec["cover"]), f"{slug} 已经改好了，从豁免表里删掉"
    # 全库扫一遍：除了豁免表，一条都不许犯（新写的在 dry-run 就该被拦下）
    offenders = []
    for path in sorted((ROOT / "specs" / "reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        spec.setdefault("slug", path.stem)
        if vp.cover_style_problems(spec):
            offenders.append(path.stem)
    assert not offenders, f"这几条封面犯了新闸又不在豁免表里：{offenders}"


# ── 常驻角标（WP6 / Q11）──────────────────────────────────────────────────
def test_常驻角标文字带墨绿描边_阴影收紧(tmp_path):
    """账号所有者 2026-09-27 选的 Q11 方案 A：剪辑片常驻角标在白色／米色画面上
    文字几乎看不见——加 2px 墨绿描边，阴影收紧。

    ① **描边**：贴在纯白上，字标那一带最暗的像素就是 token 的深底 #04120d
       （老版最暗 75，是阴影；反向验证：`WATERMARK_TEXT_STROKE_PX=0` → 红）
    ② **阴影收紧**：阴影从实墨（alpha>200，字＋描边）往外能伸多远——把实墨
       膨胀 k 像素、盖住所有 alpha>20 的像素要多大的 k。老版（6/180）10px、
       加了描边但阴影不动 9px、现在（3/140）6px；门槛 7（反向验证：阴影改回
       6/180 → 红。⚠️ 第一版拿「淡雾面积 / 实墨面积」当判据，**描边一加实墨变多，
       6/180 那一版的比值也掉到 0.9，照样过**——是反向验证抓出来的）
    位置和封面台头逐像素对得上那一头归
    `test_match_reel::test_常驻角标就是封面台头那一块_落位也是封面那个位置`。
    """
    png = wm.brand_watermark(tmp_path / "wm.png", "网球有故事", "张帅 · 第十五次")
    art = Image.open(png).convert("RGBA")
    on_white = Image.alpha_composite(Image.new("RGBA", art.size, (255, 255, 255, 255)), art)
    x0 = wm.WATERMARK_SHADOW_PAD + wm.BRAND_ICON_PX + wm.BRAND_GAP_PX
    word = np.asarray(on_white.convert("RGB").crop((x0, 0, art.width, art.height)), dtype=int)
    lum = word.mean(axis=2)
    darkest = word[np.unravel_index(np.argmin(lum), lum.shape)]
    ink = np.array(T.rgb(T.DARK["background"]))
    assert np.abs(darkest - ink).max() <= 4, (
        f"字标最暗的像素是 {tuple(darkest)}，不是墨绿描边 {tuple(ink)}——描边没画上")
    assert (lum < 60).mean() > 0.05, "描边太稀，撑不住白底"

    alpha = np.asarray(art)[..., 3]
    solid = Image.fromarray(((alpha > 200) * 255).astype("uint8"))
    reach = next(k for k in range(1, 40)
                 if not ((alpha > 20)
                         & ~(np.asarray(solid.filter(ImageFilter.MaxFilter(2 * k + 1))) > 0)).any())
    assert reach <= 7, f"阴影从字（含描边）往外伸了 {reach}px——没收紧（老版 10px）"
    assert wm.STROKE_COLOUR == T.rgb(T.DARK["background"])
    assert wm.WATERMARK_TEXT_STROKE_PX == 2


def test_这几个文件接了token_标记不许摘():
    """`design-tokens: enforced` 的扫描在 `test_design_tokens` 里；这儿只钉「这两个
    文件在扫描面里」——摘掉标记，那条扫描就静静地不管它们了（WP0 评审 nit 1）。
    ⚠️ 那条扫描只认 `#rrggbb` / `&H`；`rgba(` 和 PIL 元组它看不见，所以这儿另查：
    两个文件的代码里不许再有**非黑**的 `rgba(r,g,b` 字面值和三元组颜色。"""
    sys.path.insert(0, str(ROOT / "tests"))
    from test_design_tokens import _code_lines_py  # noqa: PLC0415

    for rel in ("tools/versus_poster.py", "src/tennislive/video/watermark.py"):
        text = (ROOT / rel).read_text("utf-8")
        assert re.search(r"^\s*#\s*design-tokens:\s*enforced\b", text, re.M), rel
        code = "\n".join(_code_lines_py(text).values())
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)       # CSS 注释里提到的不算
        lit = [m.group(0) for m in re.finditer(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", code)
               if m.groups() != ("0", "0", "0")]
        lit += re.findall(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)", code)
        assert not lit, f"{rel} 里还有手写的颜色字面值：{lit}——从 design_tokens 取"
    assert wm.BRAND_COLOUR == T.rgb(T.DARK["foreground"])
