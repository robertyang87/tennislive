"""章节卡 / 论点卡（review 路线 ⑤，tools/render_title_card.py ＋ build_match_reel 的
`title_card` 段）。账号所有者 2026-08-29 点名要学「小丝瓜🎾」那两条的 01/02/03 章节卡。"""
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import build_match_reel as reel  # noqa: E402
import render_title_card as tc  # noqa: E402


def _spec(seg_extra=None, **top):
    seg = {"title_card": "排名是怎么掉的", "kicker": "01", "seconds": 2.4}
    seg.update(seg_extra or {})
    d = {"source_url": "https://youtu.be/x", "cover": {"hook": "x"},
         "segments": [{"start": 0, "end": 5, "narration": "开场"}, seg,
                      {"start": 10, "end": 16, "narration": "收尾"}]}
    d.update(top)
    return d


def test_章节卡段解析成整屏段_旁白缺省就是卡上那句():
    """章节卡不能是一段死寂：QC 的数字静音闸 1 秒就红，账号所有者定过「卡要有配音」。"""
    segs = reel.parse_segments(_spec(), {"": 1}, "")
    assert segs[1].image.startswith(reel.TITLE_CARD_PREFIX)
    assert json.loads(segs[1].image[len(reel.TITLE_CARD_PREFIX):]) == \
        {"text": "排名是怎么掉的", "kicker": "01"}
    assert segs[1].narration == "排名是怎么掉的"
    assert (segs[1].start, segs[1].end) == (0.0, 2.4) and segs[1].fit == "contain"
    # 显式写了旁白就用它
    segs = reel.parse_segments(_spec({"narration": "先看排名。"}), {"": 1}, "")
    assert segs[1].narration == "先看排名。"


def test_章节卡缺seconds或多给一张image都当场红():
    with pytest.raises(reel.ReelError, match="seconds"):
        reel.parse_segments(_spec({"seconds": None}), {"": 1}, "")
    with pytest.raises(reel.ReelError, match="二选一"):
        reel.parse_segments(_spec({"image": "x.jpg"}), {"": 1}, "")
    with pytest.raises(reel.ReelError, match="空"):
        reel.parse_segments(_spec({"title_card": "  "}), {"": 1}, "")


def test_章节卡在load_spec那一刻归一_QC那份公式也认它(tmp_path):
    p = tmp_path / "x.json"
    p.write_text(json.dumps(_spec(), ensure_ascii=False), encoding="utf-8")
    loaded = reel.load_spec(p)
    assert loaded["segments"][1]["image"].startswith(reel.TITLE_CARD_PREFIX)
    assert loaded["segments"][1]["title_card"] == "排名是怎么掉的"
    src = inspect.getsource(reel.load_spec)
    assert src.index("_normalize_title_card_segments(spec)") < src.index("reel_length_verdict(spec)")
    import check_reel_landed  # noqa: PLC0415
    assert check_reel_landed.seg_film_seconds({"title_card": "x", "seconds": 2.4}) == 2.4


def test_render在切段之前按版式尺寸渲章节卡(tmp_path, monkeypatch):
    segs = reel.parse_segments(_spec(), {"": 1}, "")
    calls = []

    def fake(text, out, *, kicker="", size=None, clear_bottom=0):
        calls.append((text, kicker, size, out.name, clear_bottom))
        out.write_bytes(b"jpg")

    got = reel._materialize_title_cards({}, segs, tmp_path, renderer=fake)
    # 全出血：品牌用卡片自己的底边（HANDLE_BOTTOM_PX），不跟字幕上锚抬高。
    assert calls == [("排名是怎么掉的", "01", (1080, 1440), "title_card_02.jpg",
                      0)]
    assert got[1].image == str(tmp_path / "title_card_02.jpg")
    assert got[0] is segs[0] and got[2] is segs[2], "别的段一个字不动"
    # 带式：按画面带的尺寸渲，不然 3:4 的卡缩进 9:8 的带里两边留出大片底色
    calls.clear()
    monkeypatch.setattr(reel, "LAYOUT", "band")
    reel._materialize_title_cards({}, segs, tmp_path, renderer=fake)
    assert calls[0][2] == (1080, reel.BAND_PIC_H)
    assert calls[0][4] == 0, "带式的字幕在底带里、卡外，handle 不用让"
    # 没有章节卡的 spec 一次都不渲
    plain = reel.parse_segments({"segments": [{"start": 0, "end": 3, "narration": "x"}]}, {"": 1}, "")
    calls.clear()
    assert reel._materialize_title_cards({}, plain, tmp_path, renderer=fake) == plain and calls == []
    # 渲不出图要红（换个空目录——上面那次 fake 已经把 title_card_02.jpg 写在 tmp_path 里了）
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(reel.ReelError, match="没渲出来"):
        reel._materialize_title_cards({}, segs, empty, renderer=lambda *a, **k: None)
    body = inspect.getsource(reel.render)
    assert body.index("_materialize_title_cards(") < body.index("_check_segments_fit(")
    assert body.index("_materialize_stat_card(") < body.index("_materialize_title_cards(")


def test_卡上那句话不写标点_换行表达停顿_太长当场红():
    html = tc.build("两次差点丢掉一盘，三个盘点一个没给")
    assert "两次差点丢掉一盘<br>三个盘点一个没给" in html and "，" not in html
    assert "能再来吗？" in tc.build("那一盘六比一，能再来吗？"), "？留着——那是语气不是停顿"
    assert 'class="kicker">02<' in tc.build("x", kicker="02")
    assert 'class="kicker"' not in tc.build("x")
    assert 'class="kicker">错失机会<' in tc.build("x", kicker="错失机会")
    for column in tc.COLUMN_LABELS:
        assert 'class="kicker"' not in tc.build("x", kicker=column)
    with pytest.raises(SystemExit, match="最多"):
        tc.build("一" * (tc.MAX_CHARS + 1))
    with pytest.raises(SystemExit, match="空"):
        tc.build("  ")
    # 带式画布字号小一档；两行共用字号，放不下要明确按语义分行。
    assert "font-size:84px" in tc.build("x", size=(1080, 960))
    with pytest.raises(SystemExit, match="显式换行"):
        tc.build("一" * 17)


def test_单行太长在制作预检就拦住_明确分行后通过():
    with pytest.raises(reel.ReelError, match="显式换行"):
        reel._normalize_title_card_segments(_spec({"title_card": "一" * 17}))
    reel._normalize_title_card_segments(_spec({"title_card": "一" * 9 + "\n" + "一" * 8}))


def test_较长语义行适度缩字号后真实浏览器仍只有两行():
    from playwright.sync_api import sync_playwright  # noqa: PLC0415
    from render_stat_card import _launch_browser  # noqa: PLC0415

    text = "萨巴伦卡始终没能拿到破发\n两盘出局"
    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page(viewport={"width": 1080, "height": 1440})
        page.set_content(tc.build(text))
        page.evaluate("document.fonts.ready")
        measured = page.eval_on_selector(".thesis", """el => ({
            font: parseFloat(getComputedStyle(el).fontSize),
            height: el.getBoundingClientRect().height,
            width: el.clientWidth, scroll: el.scrollWidth,
            text: el.innerText
        })""")
        browser.close()
    assert 72 <= measured["font"] < 96
    assert measured["height"] == pytest.approx(measured["font"] * 1.28 * 2, abs=1)
    assert measured["width"] <= 940 and measured["scroll"] <= measured["width"] + 1
    assert measured["text"] == text


@pytest.mark.parametrize("size", [(1080, 1440), (1080, 960)])
def test_萨巴伦卡语义两行在真实浏览器保持完整_没有二次折行(size):
    """10-04 手机实帧：换行被当成空格，名字挤在首行、次行只剩两盘出局。"""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415
    from render_stat_card import _launch_browser  # noqa: PLC0415

    lines = ["5次反扑机会落空", "萨巴伦卡两盘出局"]
    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        page.set_content(tc.build("\n".join(lines), kicker="错失机会", size=size))
        page.evaluate("document.fonts.ready")
        assert page.locator(".kicker").inner_text() == "错失机会"
        geometry = page.eval_on_selector(".thesis", """el => {
            const ranges = [...el.childNodes].filter(n => n.nodeType === Node.TEXT_NODE)
                .map(n => { const r = document.createRange(); r.selectNodeContents(n);
                    return {text: n.textContent, rects: [...r.getClientRects()].map(b =>
                        ({x: b.x, y: b.y, width: b.width, height: b.height}))}; });
            return {ranges, client: el.clientWidth, scroll: el.scrollWidth,
                fontSize: parseFloat(getComputedStyle(el).fontSize)};
        }""")
        browser.close()
    assert [row["text"] for row in geometry["ranges"]] == lines
    assert all(len(row["rects"]) == 1 for row in geometry["ranges"]), geometry
    first, second = [row["rects"][0] for row in geometry["ranges"]]
    assert second["y"] - first["y"] == pytest.approx(geometry["fontSize"] * 1.28, abs=1)
    assert all(70 <= row["x"] and row["x"] + row["width"] <= size[0] - 70
               for row in (first, second)), geometry
    assert geometry["scroll"] <= geometry["client"] + 1
    assert min(first["width"], second["width"]) / max(first["width"], second["width"]) > .85


def test_真渲一张_深底上有亮字_尺寸是画布的两倍(tmp_path):
    from PIL import Image  # noqa: PLC0415
    out = tc.render("排名是怎么掉的", tmp_path / "c.jpg", kicker="01")
    im = Image.open(out).convert("L")
    assert im.size == (2160, 2880)
    px = list(im.getdata())
    dark = sum(1 for v in px if v < 40) / len(px)
    bright = sum(1 for v in px if v > 200) / len(px)
    assert dark > 0.85, f"深底要占大头，现在 {dark:.2f}"
    assert 0.005 < bright < 0.10, f"大字要真的画出来了（亮像素 {bright:.3f}）"
    out2 = tc.render("排名是怎么掉的", tmp_path / "b.jpg", size=(1080, 960))
    assert Image.open(out2).size == (2160, 1920)


def test_按画面区尺寸渲的章节卡铺满整幅_彩条落在顶边不缩不居中(monkeypatch):
    """2026-09-05 账号所有者「顶部的彩条位置不对」。章节卡按 1080×1440 渲、顶上 12px
    是品牌彩条；`still_canvas_for_layout` 原来一律缩进 0.94×0.88 的盒子再居中，
    底色相同看不出边框，**只把彩条挪到 y≈87**——正好横穿左上角常驻角标的两行字。
    整幅设计页不许缩；照片/数据图那一支照旧缩（那是给它们留呼吸的）。

    ⚠️ 第一版只喂了 1× 手搓卡，而 `render_title_card` 出的是 **2×**（2160×2880）
    ——「尺寸等于画面区」那个等式在生产里一次都没成立，渲出来的成片彩条照旧在
    y≈87。所以章节卡走显式的 `full_bleed`；2× 那一档要缩回画面区再铺，而**没认领
    的 2× 图照旧缩进盒子**（不许按长宽比猜：一张恰好 3:4 的照片不是设计页）。"""
    from PIL import Image  # noqa: PLC0415
    stripe = (198, 246, 90)
    card = Image.new("RGBA", (reel.VIDEO_W, reel.VIDEO_H), (4, 18, 13, 255))
    card.paste((*stripe, 255), (0, 0, reel.VIDEO_W, 12))
    monkeypatch.setattr(reel, "LAYOUT", "full")
    canvas, box = reel.still_canvas_for_layout(card, Image)
    assert box == (0, 0, reel.VIDEO_W, reel.VIDEO_H), box
    px = canvas.convert("RGB").load()
    assert px[540, 3] == stripe and px[20, 3] == stripe, "彩条要在 y=0 起、贯通全宽"
    assert px[540, 90] != stripe, "缩过的那版彩条落在 y≈87，这儿不许再有"
    # 2× 的设计页（真渲染器出的那一档）：认领 full_bleed 就缩回 1× 铺满
    card2 = Image.new("RGBA", (reel.VIDEO_W * 2, reel.VIDEO_H * 2), (4, 18, 13, 255))
    card2.paste((*stripe, 255), (0, 0, reel.VIDEO_W * 2, 24))
    canvas, box = reel.still_canvas_for_layout(card2, Image, full_bleed=True)
    assert box == (0, 0, reel.VIDEO_W, reel.VIDEO_H), box
    px = canvas.convert("RGB").load()
    assert px[540, 3] == stripe and px[20, 3] == stripe and px[1060, 3] == stripe, \
        "2× 章节卡认领 full_bleed 之后彩条也要在 y=0 起、贯通全宽"
    assert px[540, 90] != stripe
    # 同一张 2× 图**没认领**就照旧缩进盒子——不按尺寸倍数、不按长宽比猜
    _canvas, (x0, y0, x1, _y1) = reel.still_canvas_for_layout(card2, Image)
    assert y0 > 0 and x0 > 0 and x1 - x0 <= int(reel.VIDEO_W * 0.94), (x0, y0, x1)
    # 认领了 full_bleed 但长宽比对不上画面区：拉变形比缩过还糟，当场红
    with pytest.raises(reel.ReelError, match="长宽比"):
        reel.still_canvas_for_layout(
            Image.new("RGBA", (1080, 1920), (0, 0, 0, 255)), Image, full_bleed=True)
    # 带式：按画面带尺寸渲的卡铺满画面带，顶上让给顶栏那条带
    monkeypatch.setattr(reel, "LAYOUT", "band")
    band_card = Image.new("RGBA", (reel.VIDEO_W, reel.BAND_PIC_H), (4, 18, 13, 255))
    band_card.paste((*stripe, 255), (0, 0, reel.VIDEO_W, 12))
    canvas, box = reel.still_canvas_for_layout(band_card, Image)
    assert box == (0, reel.BAND_TOP, reel.VIDEO_W, reel.BAND_TOP + reel.BAND_PIC_H)
    assert canvas.convert("RGB").getpixel((540, reel.BAND_TOP + 3)) == stripe
    # 照片（不是画面区尺寸）照旧缩进盒子居中——这一支一个字没变
    monkeypatch.setattr(reel, "LAYOUT", "full")
    photo = Image.new("RGBA", (1080, 1920), (255, 255, 255, 255))
    _canvas, (x0, y0, x1, y1) = reel.still_canvas_for_layout(photo, Image)
    assert y0 > 0 and x0 > 0 and x1 - x0 <= int(reel.VIDEO_W * 0.94)


def _bright_rows(im, y0, y1, *, thresh=100, min_hits=8):
    """一行里中段够亮的像素达到 `min_hits` 才算墨迹，柔光底不算。"""
    xs = range(im.width // 5, 4 * im.width // 5, 2)
    return [y for y in range(max(0, y0), min(im.height, y1))
            if sum(im.getpixel((x, y)) > thresh for x in xs) >= min_hits]


def _row_spans(rows, join=3):
    if not rows:
        return []
    spans = [[rows[0], rows[0]]]
    for y in rows[1:]:
        if y - spans[-1][1] <= join:
            spans[-1][1] = y
        else:
            spans.append([y, y])
    return [(a, b) for a, b in spans]


def _burn_caption(card, ass, frame):
    import subprocess  # noqa: PLC0415

    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(card),
         "-vf", f"scale=1080:1440,ass={ass}:fontsdir={ROOT / 'assets' / 'fonts'}",
         "-frames:v", "1", str(frame)],
        check=True)


def test_章节卡品牌在真实字幕下方的底部安全区(tmp_path, monkeypatch):
    """默认全出血字幕锚下，品牌在字幕墨迹下方，并留在底边安全区内。

    2026-10-08 年终第一的章节卡把「网球时差 · TENNIS JETLAG」叠进了单行旁白：
    品牌距底 64px（墨迹约 y=1339–1372），旁白上锚 MarginV=1284（墨迹约
    y=1303–1349）。下移之后要同时满足三件事——单行旁白底下留空、双语两行
    （下锚，中文在下）底下留空、品牌离画布底边不贴死。高字幕锚（郑钦文那档
    bottom_margin=361）也不许把品牌抬回正文中段。

    上锚的两行中文第二行会落到画布最底，位置上腾不出安全带，闸不拿它当放行
    样本。真正烧进章节卡旁白的是单行；两行是双语原声。
    """
    from PIL import Image  # noqa: PLC0415

    monkeypatch.setattr(reel, "LAYOUT", "full")
    # 高字幕锚也不许改变卡片：materialize 不传 clear_bottom。
    monkeypatch.setattr(reel, "default_margin_v", lambda: 943)
    segs = reel.parse_segments(_spec(), {"": 1}, "")
    card = reel._materialize_title_cards({}, segs, tmp_path)[1]
    html = tc.build("排名是怎么掉的", kicker="01")
    assert f"bottom:{tc.HANDLE_BOTTOM_PX}px" in html
    assert "bottom:64px" not in html

    bare = Image.open(card.image).convert("L").resize((1080, 1440), Image.Resampling.BOX)
    brand_spans = _row_spans(_bright_rows(bare, 1100, 1440))
    assert len(brand_spans) == 1, f"底部只该有一条品牌，量到 {brand_spans}"
    brand_top, brand_bot = brand_spans[-1]
    inset = bare.height - 1 - brand_bot
    assert inset >= 24, f"品牌离画布底只有 {inset}px，贴边了 ({brand_top}–{brand_bot})"
    assert brand_top >= 1360, f"品牌被抬离底部安全区：y={brand_top}–{brand_bot}"
    assert not _bright_rows(bare, 900, 1200), "未叠字幕时，页面中段不该有品牌"

    def gap_under(shown, name):
        ass = reel.write_subtitles(
            [(0, 2.4, shown)], tmp_path / f"{name}.ass",
            height=1440, margin_v=reel._REEL_MARGIN_V, outline=4, shadow=1)
        frame = tmp_path / f"{name}.png"
        _burn_caption(card.image, ass, frame)
        landed = Image.open(frame).convert("L")
        assert landed.size == (1080, 1440)
        above = _row_spans(_bright_rows(landed, 1100, brand_top))
        assert above, f"{name} 的字幕没有烧出来"
        sub_bot = above[-1][1]
        gap = brand_top - sub_bot - 1
        assert gap >= 16, (
            f"{name} 字幕底 y={sub_bot} 与品牌顶 y={brand_top} 只隔 {gap}px")
        # 品牌自己还在，没有被字幕盖住或渲丢。
        assert _bright_rows(landed, brand_top, brand_bot + 1), f"{name} 叠完后品牌不见了"
        return gap

    one_gap = gap_under("10月6日，辛纳宣布结束赛季", "one-line")
    bi_gap = gap_under("Year-end number one\n年终第一几乎到手", "bilingual")
    assert one_gap >= 16 and bi_gap >= 16

    # 郑钦文那种高锚：字幕停在页面中上段，品牌仍钉在刚才量到的底边。
    high = reel.write_subtitles(
        [(0, 2.4, "北京时间十月三号下午")], tmp_path / "high.ass",
        height=1440, margin_v=1002, outline=4, shadow=1, bottom_margin=361)
    high_frame = tmp_path / "high.png"
    _burn_caption(card.image, high, high_frame)
    high_im = Image.open(high_frame).convert("L")
    assert _bright_rows(high_im, 990, 1150), "高锚字幕必须仍在原定锚位可见"
    high_brand = _row_spans(_bright_rows(high_im, 1200, 1440))
    assert high_brand and abs(high_brand[-1][0] - brand_top) <= 2, (
        f"高字幕锚把品牌从 y={brand_top} 挪到了 {high_brand}")


def test_本片字卡品牌下移到两行字幕下方(tmp_path, monkeypatch):
    """年终第一的品牌压住烧录字幕。本片把品牌下移，并让字卡字幕下锚。

    抽查的是两行同时出现的中文，不是单行。上锚两行会落到品牌里；
    下锚之后文字底边停在品牌上方，中间要有一条暗带。"""
    import subprocess  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    monkeypatch.setattr(reel, "LAYOUT", "full")
    assert f"bottom:{tc.HANDLE_BOTTOM_PX}px" in tc.build("排名是怎么掉的")
    assert "bottom:64px" not in tc.build("排名是怎么掉的")
    assert "bottom:28px" in tc.build("16岁最多12站", handle_bottom=28)
    segs = reel.parse_segments(_spec(), {"": 1}, "")
    card = reel._materialize_title_cards(
        {"title_card_handle_bottom": 28}, segs, tmp_path)[1]
    assert card.subtitle_bottom == reel.TITLE_CARD_SUBTITLE_BOTTOM == 96
    two = "16岁这一年最多12站\n外卡也算进这12站里"
    ass = reel.write_subtitles([(0.0, 2.4, two)], tmp_path / "two.ass",
                               height=1440, margin_v=1284, outline=4, shadow=1,
                               bottom_margin_windows=[(0.0, 2.4, 96)])
    frame = tmp_path / "with-two-lines.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", card.image,
                    "-vf", f"scale=1080:1440,ass={ass}:fontsdir={ROOT / 'assets' / 'fonts'}",
                    "-frames:v", "1", str(frame)], check=True)
    bare = tmp_path / "bare.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", card.image,
                    "-vf", "scale=1080:1440", "-frames:v", "1", str(bare)], check=True)
    brand_rows = _bright_rows(Image.open(bare).convert("L"), 1280, 1440)
    both = _bright_rows(Image.open(frame).convert("L"), 1100, 1440)
    assert brand_rows, "下移后的品牌要画在画面底部"
    brand_top = min(brand_rows)
    subtitle_rows = [y for y in both if y < brand_top - 1]
    assert subtitle_rows, "两行字幕要画在品牌上方"
    gap = brand_top - max(subtitle_rows) - 1
    assert gap >= 16, f"两行字幕和品牌间距只有 {gap}px（字幕底 {max(subtitle_rows)}，品牌顶 {brand_top}）"
    assert max(subtitle_rows) < brand_top, "两行字幕不能压进品牌"


def test_真渲的章节卡走完切段那条路_成片第一行就是彩条(tmp_path):
    """判据要过**真渲染器 + 真切段**，不许再拿手搓卡验：上一条的第一版就是这么
    绿着放过了一版彩条在 y≈87 的成片（2026-09-05 comeback-five-love-down）。
    真链：parse_segments → _materialize_title_cards（Chromium，2×）→ cut_still_segment
    （PIL 铺满 + ffmpeg）→ 抽第一帧量：顶上那几行是彩条（亮、高饱和），y≈87 是
    深底；`Segment.full_bleed` 由 materialize 认领，不是 spec 写的。"""
    import subprocess  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    segs = reel.parse_segments(_spec(), {"": 1}, "")
    got = reel._materialize_title_cards({}, segs, tmp_path)
    card_seg = got[1]
    assert card_seg.full_bleed is True and not segs[0].full_bleed and not got[2].full_bleed
    with Image.open(card_seg.image) as im:
        assert im.size == (reel.VIDEO_W * 2, reel.VIDEO_H * 2), "渲染器出的是 2×，判据要拿这一档验"
    dest = tmp_path / "part.mp4"
    reel.cut_still_segment(card_seg, dest)
    frame = tmp_path / "f0.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(dest), "-frames:v", "1", str(frame)],
                   check=True)
    px = Image.open(frame).convert("RGB")
    assert px.size == (reel.VIDEO_W, reel.VIDEO_H)

    def row(y):
        return [px.getpixel((x, y)) for x in range(0, reel.VIDEO_W, 20)]

    # 彩条中段混色处饱和度会掉下来，所以按亮度判；柔光深蓝背景仍明显暗于彩条。
    for y in (1, 5, 9):
        hits = sum(max(c) > 120 for c in row(y))
        assert hits >= len(row(y)) * 0.9, f"y={y} 这一行该是彩条（亮），只有 {hits} 格是"
    assert px.getpixel((10, 1))[1] > 200 and px.getpixel((1070, 1))[2] > 200, \
        "彩条左端是品牌绿、右端是蓝——渐变要贯通全宽"
    for y in (60, 87, 95):
        assert all(max(c) < 110 and c[2] > c[1] >= c[0] for c in row(y)), \
            f"y={y} 该是柔光深蓝底——彩条要是还落在这儿就是又缩了"
