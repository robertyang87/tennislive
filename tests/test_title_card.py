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

    def fake(text, out, *, kicker="", size=None):
        calls.append((text, kicker, size, out.name))
        out.write_bytes(b"jpg")

    got = reel._materialize_title_cards({}, segs, tmp_path, renderer=fake)
    assert calls == [("排名是怎么掉的", "01", (1080, 1440), "title_card_02.jpg")]
    assert got[1].image == str(tmp_path / "title_card_02.jpg")
    assert got[0] is segs[0] and got[2] is segs[2], "别的段一个字不动"
    # 带式：按画面带的尺寸渲，不然 3:4 的卡缩进 9:8 的带里两边留出大片底色
    calls.clear()
    monkeypatch.setattr(reel, "LAYOUT", "band")
    reel._materialize_title_cards({}, segs, tmp_path, renderer=fake)
    assert calls[0][2] == (1080, reel.BAND_PIC_H)
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
    with pytest.raises(SystemExit, match="最多"):
        tc.build("一" * (tc.MAX_CHARS + 1))
    with pytest.raises(SystemExit, match="空"):
        tc.build("  ")
    # 带式画布字号小一档，字数不缩字号（缩到 50px 就不是论点卡了）
    assert "font-size:84px" in tc.build("x", size=(1080, 960))
    assert "font-size:96px" in tc.build("一" * 17)


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
