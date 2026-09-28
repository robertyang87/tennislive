"""网球有故事字卡解说的视觉判据（2026-09-27 UI/VI 评审 WP4）。

每一条钉一件事，都反向验证过（改回去当场红，见提交说明）：

- 编号药丸过了 ⑨ 接着带圈到 ⑳，不再掉成裸的「10」
- 字卡的字重只写 400 / 700（子集字体只带这两档，800 渲出来就是 700）
- 死 CSS `.foot` / `.tag` 不许回来
- 封面不再挂栏目药丸（Q5）；编号药丸描边、中性色，一屏只剩黄绿一支强调色（Q5 ＋ Q1）
- 示意图压到文案块就等比缩，缩过头就停（渲染时断言）
- 封面念的就是大问题时不另排字幕（`same_line_as_printed` 两条线共用一份）
- 每个接缝 0.18 秒溶解，含冷开场→封面、末屏→片尾，中间一帧黑都没有（Q4）
"""

from __future__ import annotations

import colorsys
import html
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tennislive.render.tournament_story import find_story_by_slug
from tennislive.video import explainer as E
from tennislive.video import explainer_card_palette as P

_SCRIPTED = tuple(E._SCRIPTS)


def _deck(slug: str):
    return E.explainer_script(find_story_by_slug(slug))


def _style(markup: str) -> str:
    """幻灯片页面里**卡片自己**那段 CSS（去掉内联的字体）。"""
    from tennislive.render.webcards import _font_css

    return markup.split("<style>", 1)[1].split("</style>", 1)[0].replace(_font_css(), "")


def _rule(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    assert m, f"CSS 里找不到 {selector}"
    return m.group(1)


# ── 编号药丸：⑩–⑳ ─────────────────────────────────────────────────────────

def _cjk_font_with(chars: str):
    """系统里的 Noto Sans CJK SC Bold（CI 装 fonts-noto-cjk）。找不到就出声。"""
    from PIL import ImageFont

    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                 "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
                 "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc"):
        if not Path(path).is_file():
            continue
        for index in range(10):
            try:
                font = ImageFont.truetype(path, 40, index=index)
            except OSError:
                break
            if font.getname()[0] == "Noto Sans CJK SC":
                return font
    raise AssertionError("没有 Noto Sans CJK SC，这条判据跑不了：apt install fonts-noto-cjk")


def _has_glyph(font, ch: str) -> bool:
    from PIL import Image, ImageDraw

    def ink(c: str) -> bytes:
        im = Image.new("L", (80, 80))
        ImageDraw.Draw(im).text((10, 10), c, font=font, fill=255)
        return im.tobytes()

    return ink(ch) != ink("")   # 私用区：一定是 .notdef


def test_编号药丸过了九接着带圈到二十():
    """`ranking-math` 十一屏，第 10 屏的药丸原来是裸的「10 落点」，前九屏带圈。"""
    assert E.CHIP_NUMERALS == tuple("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳")

    beat = _deck("bu-lucky-loser")[1]
    for index, expect in ((1, "①"), (9, "⑨"), (10, "⑩"), (20, "⑳"), (21, "21")):
        chip = re.search(r'<span class="chip">([^<]*)</span>',
                         E._slide_html(index, beat)).group(1)
        assert chip.startswith(expect + " "), f"第 {index} 屏的药丸是「{chip}」，该以 {expect} 开头"

    # 真存量：ranking-math 的第 10 屏
    deck = _deck("ranking-math")
    assert len(deck) >= 11, "ranking-math 不够 11 屏了，换一条超过 10 屏的片子来钉"
    assert '<span class="chip">⑩ ' in E._slide_html(10, deck[10])

    # 字形：子集字体 TL Sans SC 里一个带圈数字都没有，①–⑨ 本来就回退到
    # Noto Sans CJK SC 画——⑩–⑳ 要在同一个字体里，才是同一副字形。
    cjk = _cjk_font_with(E.CHIP_NUMERALS)
    missing = [c for c in E.CHIP_NUMERALS if not _has_glyph(cjk, c)]
    assert not missing, f"Noto Sans CJK SC 里没有 {''.join(missing)}——会回退到别的字体，药丸字形不一"


# ── 字重 / 死 CSS ────────────────────────────────────────────────────────

def _sample_markups() -> list[str]:
    fixture_deck = _deck("eala-anisimova")      # 赛前片封面带 .fixture
    fils = _deck("fils-tokyo-qualifying")
    return [
        E._slide_html(0, fils[0], topic="t", column="网球有故事"),   # 照片封面
        E._slide_html(1, fils[1], topic="t", column="网球有故事"),   # 示意图
        E._slide_html(2, fils[2], topic="t", column="网球有故事"),   # 照片正文
        E._slide_html(0, fixture_deck[0], column="开球之前"),
    ]


def test_字卡字重只写400和700():
    """`TL Sans SC` 只带 400 / 700 两个字面，写 800 渲出来和 700 一模一样
    （评审 `font_weight_test.png` 量过）——写一个不存在的字重，下一个人会以为
    它比 700 粗。改成 700 那一步重渲 33 屏逐字节相同。"""
    for markup in _sample_markups():
        weights = set(re.findall(r"font-weight:(\d+)", _style(markup)))
        assert weights <= {"400", "700"}, f"字卡 CSS 里出现了字重 {sorted(weights)}"
    import inspect

    badge = inspect.getsource(E._render_intro_badge)
    assert set(re.findall(r"font-weight:(\d+)", badge)) <= {"400", "700"}


def test_死CSS不许回来():
    """`.foot` / `.tag` 没有任何元素用（评审量过），删掉那一步重渲逐字节相同。"""
    for markup in _sample_markups():
        css = _style(markup)
        assert ".foot{" not in css and ".tag{" not in css


# ── Q5：封面药丸、编号药丸 ────────────────────────────────────────────────

def test_封面不再挂栏目药丸():
    """台头第一行已经写着「网球时差 · 网球有故事」，底下再垫一颗同名药丸是同一屏
    印两遍（账号所有者 2026-09-27 Q5；赛场之上 08-14 删过同一颗）。"""
    spans = re.compile(r'<span class="([^"]*)">([^<]*)</span>')
    covers = 0
    for slug in _SCRIPTED:
        column = E.explainer_column(slug)
        markup = E._slide_html(0, _deck(slug)[0], column=column)
        found = spans.findall(markup)
        assert not [c for c, _ in found if c in ("kicker", "chip")], f"{slug} 封面还挂着药丸"
        assert [t for c, t in found if c == "brand"] == [f"网球时差 · {html.escape(column)}"], (
            f"{slug} 封面的台头品牌行不对——栏目名只该在台头出现这一次")
        assert not [t for c, t in found if t == column], f"{slug} 封面上栏目名单独又印了一遍"
        covers += 1
    assert covers >= 40, f"只扫到 {covers} 张封面，判据失效了"
    # 正文各屏的编号药丸照留
    assert '<span class="chip">① ' in E._slide_html(1, _deck("bu-lucky-loser")[1])


def _accents(css: str) -> set[str]:
    """CSS 里所有**鲜艳**的颜色（HSV 饱和度 > .35 且明度 > .45）。彩条那一条除外
    （账号所有者锁定的四色条，本来就是四支）。"""
    css = re.sub(r"\.bar\{[^}]*\}", "", css)
    out = set()
    for hx in re.findall(r"#[0-9a-fA-F]{6}\b", css):
        r, g, b = (int(hx[i:i + 2], 16) / 255 for i in (1, 3, 5))
        _, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s > .35 and v > .45:
            out.add(hx.lower())
    for r, g, b in re.findall(r"rgba?\((\d+),(\d+),(\d+)", css):
        _, s, v = colorsys.rgb_to_hsv(int(r) / 255, int(g) / 255, int(b) / 255)
        if s > .35 and v > .45:
            out.add(f"rgb({r},{g},{b})")
    return out


def test_编号药丸描边中性色_一屏只剩一支强调色():
    """账号所有者 2026-09-27：Q5「每屏编号药丸改描边、中性色」；Q1「黄绿 #c6f65a 是
    唯一品牌色，薄荷只表示『这一方赢了』」。原来药丸是薄荷实底 #37e29a，和下面要点
    那条黄绿边线同屏两支绿（`fils_s04.jpg`）。"""
    for markup in _sample_markups():
        css = _style(markup)
        assert _accents(css) == {P.PRIMARY.lower()}, (
            f"字卡上除了黄绿还有别的强调色：{sorted(_accents(css))}")

    chip = _rule(_style(_sample_markups()[1]), ".chip")
    assert f"border:2px solid {P.CHIP_OUTLINE}" in chip, f"药丸不是描边的：{chip}"
    assert f"color:{P.CHIP_TEXT}" in chip and P.CHIP_TEXT == P.FOREGROUND
    assert "#37e29a" not in chip.lower()
    # 描边从内边距里扣：外框和原来（padding 12px 28px、无描边）一样大，标题不挪
    pad = re.search(r"padding:(\d+)px (\d+)px", chip).groups()
    assert (int(pad[0]) + 2, int(pad[1]) + 2) == (12, 28), f"药丸外框变了：{chip}"


# ── 示意图不许压到文案块 ──────────────────────────────────────────────────

@pytest.fixture
def chromium_page():
    """⚠️ 函数级，不是模块级：sync_playwright 开着的时候事件循环在跑，同一个进程里
    后面再调 `render_explainer_slides`（它自己开 sync_playwright）就报「Sync API inside
    the asyncio loop」——`test_渲染入口每屏都过示意图那道闸` 排在它后面时栽过。"""
    from playwright.sync_api import sync_playwright

    from tennislive.chromium import launch_chromium
    from tennislive.render.webcards import _font_css

    with sync_playwright() as p:
        browser = launch_chromium(p)
        page = browser.new_page(viewport={"width": E.W, "height": E.H})
        # 字体只装一次，之后每屏只换卡片自己的 CSS 和 body——一屏一次
        # set_content 要重新解析十几 MB 的 base64 字体，112 屏跑不动。
        page.set_content(
            '<!DOCTYPE html><html><head><meta charset="utf-8">'
            f'<style>{_font_css()}</style><style id="card"></style></head>'
            "<body></body></html>")
        yield page
        browser.close()


def _load(page, markup: str) -> None:
    body = markup.split("<body>", 1)[1].split("</body>", 1)[0]
    page.evaluate("([s, b]) => { document.getElementById('card').textContent = s;"
                  " document.body.innerHTML = b; }", [_style(markup), body])
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=15000)


def test_示意图压到文案块就等比缩_缩过头就停():
    """判据本身：压到了报、缩过头报、正常的不报。"""
    ok = {"top": 210, "bottom": 700, "height": 490, "natural": 613, "copyTop": 716}
    assert E.diagram_fit_problem(ok) == ""
    assert E.diagram_fit_problem(None) == ""
    assert "编号药丸" in E.diagram_fit_problem({**ok, "copyTop": 705})
    assert "缩到原高度" in E.diagram_fit_problem({**ok, "height": 400})
    assert E.DIAGRAM_COPY_GAP == 16
    assert E.diagram_fit_problem({**ok, "height": 613 * 0.79}) == ""


def test_bu_lucky_loser第2屏的药丸不再压着示意图(chromium_page):
    """评审截图 `chip_collision_crops.jpg`：「② 大满贯怎么补」盖住了「2026 美网第一天：
    14 个人签到」那一行。先证明它**原样真的压着**（否则这条是恒真的），再证明
    渲染时那一步把它让开了。"""
    seg = _deck("bu-lucky-loser")[2]
    markup = E._slide_html(2, seg, column="网球有故事")
    _load(chromium_page, markup)
    raw = chromium_page.evaluate(E.FIT_DIAGRAM_JS, -1e6)   # 只量不缩
    assert not raw["fitted"]
    assert raw["copyTop"] - raw["bottom"] < 0, (
        f"这一屏原样就没压着（{raw}）——换一屏真压着的来钉")
    fit = chromium_page.evaluate(E.FIT_DIAGRAM_JS, E.DIAGRAM_COPY_GAP)
    assert fit["fitted"], "压着却没缩"
    assert fit["copyTop"] - fit["bottom"] >= E.DIAGRAM_COPY_GAP - 0.5
    assert E.diagram_fit_problem(fit) == ""


def test_所有带示意图的字卡_渲染后示意图底边离文案块至少16px(chromium_page):
    """评审验收：「所有带示意图的 _SCRIPTS：svg 底边 < 文案顶边 − 16」。
    没压着的一个像素都不动（`fitted` 为假），压着的等比缩，缩不到下限的当场红。"""
    checked, fitted, problems = 0, [], []
    for slug in _SCRIPTED:
        column = E.explainer_column(slug)
        topic = (E._OPENINGS.get(slug) or {}).get("topic", "")
        for index, seg in enumerate(_deck(slug)):
            if not seg.diagram or (seg.image and (E._REPO / seg.image).is_file()):
                continue
            _load(chromium_page, E._slide_html(index, seg, topic=topic, column=column))
            fit = chromium_page.evaluate(E.FIT_DIAGRAM_JS, E.DIAGRAM_COPY_GAP)
            checked += 1
            if fit["fitted"]:
                fitted.append(f"{slug}#{index} {fit['height'] / fit['natural']:.0%}")
            problem = E.diagram_fit_problem(fit)
            if problem:
                problems.append(f"{slug} 第 {index} 屏：{problem}")
    assert checked >= 100, f"只量到 {checked} 屏示意图，判据失效了"
    assert not problems, "\n".join(problems)
    assert fitted, "一屏都没缩——bu-lucky-loser 第 2 屏明明压着，量法失效了"
    # 量的是**画出来的东西**，不是 SVG 盒子：盒子底下那截空白压在药丸后面看不见，
    # 拿盒子算会把一半的示意图冤枉缩掉（2026-09-27 量：盒子口径 76 屏，画面口径 38 屏）
    assert len(fitted) < checked // 2, f"{len(fitted)}/{checked} 屏都缩了——量的多半是盒子"


def test_渲染入口每屏都过示意图那道闸(tmp_path, monkeypatch):
    """闸要装在**渲染入口**上，不是只在测试里量——判据是它红了渲染就停。"""
    seg = _deck("bu-lucky-loser")[2]
    monkeypatch.setattr(E, "diagram_fit_problem", lambda fit, **k: "压到了（测试注入）")
    with pytest.raises(E.ExplainerVideoError, match="压到了"):
        E.render_explainer_slides([seg], tmp_path)


# ── 封面同句字幕 ──────────────────────────────────────────────────────────

def test_字卡封面念的就是大问题就不另排字幕():
    """评审截图 `exp_cover_dup_crop.jpg`：96px 的「世界第 11 / 为什么要打资格赛？」
    底下，字幕又写了一遍「世界第11 为什么要打资格赛？」。52 条存量封面 41 条如此。"""
    from tennislive.video.subtitle_text import same_line_as_printed

    def cues(seg):
        return E.subtitle_cues(E.readable(seg.narration), 12.0)

    fils = _deck("fils-tokyo-qualifying")[0]
    before = cues(fils)
    after = E.drop_printed_cues(before, fils.title)
    assert [c[2] for c in before if same_line_as_printed(c[2], fils.title)], "fils 封面原样就没有重复——判据空转"
    assert len(after) == len(before) - 1 and after == before[1:], "只该丢那一条，其余原样"

    # 大问题被切成两条字幕的，两条一起丢
    fv = _deck("finals-venues")[0]
    fv_before, fv_after = cues(fv), E.drop_printed_cues(cues(fv), fv.title)
    assert len(fv_after) == len(fv_before) - 2 and fv_after == fv_before[2:]

    # 口播多说了字（「赢了 12 号种子」对「赢种子」）不算同一句：字幕留着
    bu = _deck("bu-lucky-loser")[0]
    assert E.drop_printed_cues(cues(bu), bu.title) == cues(bu)

    # 全部存量封面：丢完之后，没有任何一条（或相邻两三条拼起来）还等于大问题
    for slug in _SCRIPTED:
        cover = _deck(slug)[0]
        kept = [c[2] for c in E.drop_printed_cues(cues(cover), cover.title)]
        for i in range(len(kept)):
            for run in (1, 2, 3):
                assert not same_line_as_printed("".join(kept[i:i + run]), cover.title), (
                    f"{slug} 封面丢完还剩一句和大字一样的字幕：{kept[i:i + run]}")


def test_same_line_as_printed只有一份():
    """函数搬进了两条线共用的 `subtitle_text`，赛场之上从那儿 import——一个判据
    写两处必分叉，所以钉的是**同一个对象**，不是「两份判得一样」。"""
    import importlib

    from tennislive.video.subtitle_text import same_line_as_printed as shared

    reel = importlib.import_module("build_match_reel")
    assert reel.same_line_as_printed is shared, "build_match_reel 又长出了自己的一份"
    assert "def same_line_as_printed" not in Path(reel.__file__).read_text(encoding="utf-8")
    # 行为本身（赛场之上那几条老判据在 test_match_reel.py 里照跑）
    assert shared("五天前出局，五天后赢了种子？", "五天前出局\n五天后赢了种子")
    assert shared("八张门票发完了，只有一张是送的。", "8张门票发完了\n只有1张是送的")
    assert not shared("八张门票发完了，只有三张是送的。", "8张门票发完了\n只有1张是送的")
    assert not shared("全美第三大的网球赛事，办在一个三万多人的小镇。", "全美第三大赛事\n办在小镇")


def test_same_line_as_printed_零映成0():
    """`_CJK_DIGITS` 原来是 `"01123456789"`（从 `build_match_reel` 原样搬来）：十一个字对
    十一个字，「零」错位映成 `1`。印着的那一份本来就是阿拉伯数字、不过这张表，所以
    念「零封对手」、印「0封对手」被判成两句（多叠一行字幕），而印「1封对手」反倒被判成
    同一句（该出的字幕被丢掉）。两个方向都钉住。"""
    from tennislive.video.subtitle_text import same_line_as_printed

    assert same_line_as_printed("零封对手。", "0封对手"), "念「零」印「0」是同一句"
    assert same_line_as_printed("〇封对手。", "0封对手")
    assert not same_line_as_printed("零封对手。", "1封对手"), "念「零」印「1」不是同一句"
    for spoken, printed in zip("〇零一二三四五六七八九", "00123456789"):
        assert same_line_as_printed(f"第{spoken}号", f"第{printed}号"), (spoken, printed)


def _fake_runner(seconds: str):
    def runner(cmd, **kw):
        if "ffprobe" in cmd[0]:
            return type("R", (), {"stdout": f"{seconds}\n"})()
        Path(cmd[-1]).write_bytes(b"mp4")
        return type("R", (), {"stdout": ""})()
    return runner


def test_装配时按printed丢掉封面那条字幕(tmp_path, monkeypatch):
    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    cover = _deck("fils-tokyo-qualifying")[0]
    slide, audio = tmp_path / "s.jpg", tmp_path / "a.mp3"
    slide.write_bytes(b"x")
    audio.write_bytes(b"x")
    shown_title = "世界第11 为什么要打资格赛？"

    def dialogues() -> list[str]:
        """字幕正文，去掉 ASS 的覆盖标签（数字放大那层 `{\\fs78}`）和换行符。"""
        ass = (tmp_path / "sub_00.ass").read_text(encoding="utf-8")
        return [re.sub(r"\{[^}]*\}", "", ln.split(",,", 1)[1]).replace("\\N", " ")
                for ln in ass.splitlines() if ln.startswith("Dialogue:")]

    E.assemble_explainer_video([slide], [audio], tmp_path / "o.mp4",
                               captions=[cover.narration], runner=_fake_runner("12.000"))
    assert any(shown_title in d for d in dialogues()), "对照组：不给 printed 时应该还在"
    E.assemble_explainer_video([slide], [audio], tmp_path / "o.mp4",
                               captions=[cover.narration], printed=[cover.title],
                               runner=_fake_runner("12.000"))
    assert not any(shown_title in d for d in dialogues())
    assert len(dialogues()) >= 3, "封面其余的话照旧要有字幕"


def test_生成时只把封面的大问题当成印着的那句(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(E, "render_explainer_slides", lambda *a, **k: [])
    monkeypatch.setattr(E, "synthesize_narration", lambda *a, **k: [])
    monkeypatch.setattr(E, "_build_outro_clip", lambda *a, **k: None)
    monkeypatch.setattr(E, "assemble_explainer_video",
                        lambda *a, **k: seen.update(k) or tmp_path / "x.mp4")
    E.generate_explainer_video(find_story_by_slug("fils-tokyo-qualifying"), tmp_path)
    deck = _deck("fils-tokyo-qualifying")
    assert seen["printed"] == [deck[0].title] + [""] * (len(deck) - 1)


# ── Q4：每个接缝溶解 ──────────────────────────────────────────────────────

def test_接缝一律溶解_含冷开场和片尾(tmp_path, monkeypatch):
    """账号所有者 2026-09-27 Q4：「字卡解说所有接缝 0.18s 溶解（含进片尾）」。"""
    from tennislive.design_tokens import MOTION

    monkeypatch.setattr(E.shutil, "which", lambda *_: "/usr/bin/ffmpeg")
    files = [tmp_path / n for n in ("s0.jpg", "a0.mp3", "s1.jpg", "a1.mp3", "i.mp4", "o.mp4")]
    for f in files:
        f.write_bytes(b"x")
    calls = []

    def runner(cmd, **kw):
        calls.append(list(cmd))
        return _fake_runner("4.000")(cmd, **kw)

    E.assemble_explainer_video(files[0:3:2], files[1:4:2], tmp_path / "out.mp4",
                               intro=files[4], outro=files[5], runner=runner)
    graph = calls[-1][calls[-1].index("-filter_complex") + 1]
    fades = re.findall(r"xfade=transition=(\w+):duration=([\d.]+):offset=([\d.]+)", graph)
    # 冷开场 4.0 → 封面 4.0+0.6 → 末屏 4.0+1.5 → 片尾：三个接缝，起点和硬切时一样
    assert fades == [("fade", "0.18", "4.000"), ("fade", "0.18", "8.600"),
                     ("fade", "0.18", "14.100")], fades
    assert float(fades[0][1]) == MOTION["video_dissolve_s"] == E.SLIDE_DISSOLVE
    assert "v=1:a=1" not in graph, "画面还在走 concat 硬切"
    assert "[aintro][a0][a1][a2]concat=n=4:v=0:a=1[outa]" in graph
    # 除最后一路（片尾）外，每一路都垫了溶解底料
    for label in ("[vintro]", "[v0]", "[v1]"):
        chain = next(c for c in graph.split(";") if c.endswith(label))
        assert "tpad=stop_mode=clone" in chain, f"{label} 没垫底料，溶解会吃掉它自己的画面"
    assert "tpad" not in next(c for c in graph.split(";") if c.endswith("[v2]"))


def _luma_per_frame(path: Path) -> list[float]:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
         "signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-", "-f", "null", "-"],
        check=True, capture_output=True, text=True).stdout
    return [float(x) for x in re.findall(r"YAVG=([\d.]+)", out)]


def test_接缝真跑ffmpeg_没有黑帧没有单帧跳变_声画对得上(tmp_path):
    """真拼一条：冷开场（画面 2.0s、声音只有 1.5s）→ 三屏 → 片尾，相邻两段亮度各差
    40 以上（硬切的话接缝上就是一帧跳 40+）。

    - 相邻两帧亮度差不超过 20（评审验收：「接缝处逐帧差分，不允许单帧跳变超过 20」）。
      ⚠️ 这个 20 只对**这组素材**成立：0.18 秒溶解在 30fps 上约 5.4 帧，单帧步长
      ≈ 两屏亮度差 ÷ 5.4——这里两屏差 40 上下，一步 7~8；换成 200→60 的纯灰，老老实实的
      溶解一步也有 22.6。别把 20 当成任意内容的硬指标，判「是不是溶解」看的是步长
      和对比度的比例（真稿三个接缝 5.4 / 1.5 / 2.9）
    - 没有一帧比最暗的那段还暗（「中间一帧黑都不许有」）
    - **每一屏的旁白都在它那一屏画面起点之后正好那么久响起**，总长、声画一样长。
      两个会漂的来源都在这儿：冷开场声音比画面短 0.5s；每屏的 mp3 是 libmp3lame
      编的，ffprobe 报 1.056s 而解码出来只有 1.000s——溶解之后声音单独 concat，
      不按画面原长锁死的话，一屏一屏往前漂（2026-09-27 样片三屏漂了 183ms）
    """
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    def run(*args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True)

    slides, audios = [], []
    for i, grey in enumerate(("0x9a9a9a", "0x5a5a5a", "0x9a9a9a")):
        s, a = tmp_path / f"s{i}.png", tmp_path / f"a{i}.mp3"
        run("-f", "lavfi", "-i", f"color=c={grey}:s={E.VIDEO_W}x{E.CARD_H}", "-frames:v", "1", str(s))
        # 每屏的「旁白」：先 0.5 秒安静，再 0.5 秒 440Hz——起音点就是这一屏的旁白起点
        run("-f", "lavfi", "-i",
            "aevalsrc='if(gt(t\\,0.5)\\,sin(2*PI*440*t)\\,0)':s=24000:d=1.0", "-ac", "1", str(a))
        slides.append(s)
        audios.append(a)
    intro, outro = tmp_path / "_intro.mp4", tmp_path / "_outro.mp4"
    run("-f", "lavfi", "-i", "color=c=0xdadada:s=1280x720:r=25", "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono", "-t", "2.0", "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ar", "24000", "-ac", "1", "-af", "atrim=end=1.5", str(intro))
    run("-f", "lavfi", "-i", f"color=c=0x1a1a1a:s={E.VIDEO_W}x{E.CARD_H}:r=30", "-f", "lavfi",
        "-i", "anullsrc=r=24000:cl=mono", "-t", "2.0", "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "24000", "-ac", "1", str(outro))

    out = E.assemble_explainer_video(slides, audios, tmp_path / "out.mp4", intro=intro,
                                     outro=outro)

    # 每一路的原长——和装配时同一个量法（ffprobe），接缝就落在这些数的累加上
    def probe(p):
        return float(f"{E._audio_seconds(Path(p), 'ffprobe', subprocess.run):.3f}")

    a_len = [probe(a) for a in audios]
    # 对照组要的是「ffprobe 报长了」的 mp3（源是 d=1.0 生成的）。报长多少看 ffmpeg 版本：
    # Ubuntu 6.1 报 1.056、CI 的 BtbN nightly 报 1.022——所以不写死 1.03。要的是**不锁
    # 画面长度的装配会被下面的间隔断言逮到**：第 3 屏漂两倍的报长量，得超过那 0.02 的容差。
    over = a_len[0] - 1.0
    assert 2 * over > 0.02, f"这条 mp3 ffprobe 报 {a_len[0]}——报长量太小，对照组逮不住漂移"
    c0 = probe(intro)
    c1 = c0 + a_len[0] + E.LEAD_SILENCE
    c2 = c1 + a_len[1]
    c3 = c2 + a_len[2] + E.TAIL_SILENCE

    y = _luma_per_frame(out)
    jumps = [abs(b - a) for a, b in zip(y, y[1:])]
    assert max(jumps) <= 20, f"接缝上有一帧跳了 {max(jumps):.1f}（>20），不是溶解"
    assert min(y) >= min(y[5], y[-5]) - 3, f"有一帧比最暗的那段还暗（{min(y):.1f}）——碰黑了"
    # 相邻两段的平台亮度差 ≥ 40：硬切一定会被上面那条逮到（对照组不是空转）
    plateaus = [y[int(t * 30)] for t in (c0 / 2, (c0 + c1) / 2, (c1 + c2) / 2,
                                         (c2 + c3) / 2)] + [y[-10]]
    assert all(abs(a - b) >= 40 for a, b in zip(plateaus, plateaus[1:])), plateaus

    def dur(stream):
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream, "-show_entries",
             "stream=duration", "-of", "csv=p=0", str(out)],
            check=True, capture_output=True, text=True).stdout.strip().rstrip(","))

    total = c3 + probe(outro)
    assert abs(dur("v:0") - total) < 0.05, f"总长 {dur('v:0'):.3f}，该是 {total:.3f}——溶解把时长吃掉了"
    assert abs(dur("a:0") - dur("v:0")) < 0.05, (
        f"声音 {dur('a:0'):.3f}s、画面 {dur('v:0'):.3f}s——声音没锁成画面的长度")

    sil = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(out), "-af", "silencedetect=n=-40dB:d=0.3",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    onsets = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", sil)][:3]
    expect = [c0 + E.LEAD_SILENCE + 0.5, c1 + 0.5, c2 + 0.5]
    assert len(onsets) == 3, f"只找到 {len(onsets)} 个起音点：{sil[-600:]}"
    # 第一屏：冷开场**画面**结束后 0.6 + 0.5 秒（AAC 起音有几十毫秒的毛刺，给 60ms）
    assert abs(onsets[0] - expect[0]) < 0.06, f"第一屏旁白在 {onsets[0]:.3f}s 响起，该是 {expect[0]:.3f}s"
    # 后面每一屏：拿**间隔**比，AAC 那点毛刺两边一样、自己抵掉——漂一屏 56ms 就红
    for k in (1, 2):
        got, want = onsets[k] - onsets[0], expect[k] - expect[0]
        assert abs(got - want) < 0.02, (
            f"第 {k + 1} 屏旁白离第一屏 {got:.3f}s，该是 {want:.3f}s——声音一屏一屏往前漂了")
