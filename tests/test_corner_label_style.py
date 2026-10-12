"""角标是全局默认：右上角、右缘短轨、文字右对齐。

2026-10-12 账号所有者把梅德韦杰夫 24 冠那张贴图定为以后所有片子的角标。
共享渲染器 ``render_story_info_band.render`` 的默认就是这一版。左轨只剩
显式 ``layout="classic", align="left"``，而且 spec 里一旦拿去当 story_text，
``parse_segments`` 就红。已经发出去的左轨片挂在 ``data/legacy_corner_label.json``，
只许减不许加。没有贴图的片子不查。
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import (
    BRAND_GREEN,
    LABEL_FONT,
    MUTED,
    SCORE,
    WHITE,
    label_font_problem,
    legacy_corner_label_slugs,
    png_corner_label_problem,
    render,
    story_corner_label_problems,
)

ROOT = Path(__file__).resolve().parents[1]


def _specs():
    for path in sorted((ROOT / "specs").rglob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(spec, dict) or not isinstance(spec.get("segments"), list):
            continue
        if not any(isinstance(seg, dict)
                   and str((seg.get("inset") or {}).get("kind") or "") == "story_text"
                   for seg in spec["segments"]):
            continue
        spec = dict(spec)
        spec["slug"] = str(spec.get("slug") or path.stem)
        yield path, spec


def test_默认贴图是右轨右对齐(tmp_path):
    signature = inspect.signature(render)
    assert signature.parameters["align"].default == "right"
    assert signature.parameters["layout"].default == "corner"
    source = (ROOT / "tools" / "render_story_info_band.py").read_text(encoding="utf-8")
    assert 'choices=["left", "right"], default="right"' in source
    assert 'choices=["corner", "classic"], default="corner"' in source
    out = render("2018.01.13", "第1冠", "vs 德米纳尔", tmp_path / "corner.png",
                 highlight="ATP250 悉尼", metric="1-6 6-4 7-5")
    assert png_corner_label_problem(out) is None
    with Image.open(out) as image:
        assert image.size[0] == 1200
        assert image.size[1] >= 340 and image.size[1] % 2 == 0
        assert image.getpixel((1173, 170))[:3] == BRAND_GREEN[:3]
        assert image.getpixel((27, 170))[:3] != BRAND_GREEN[:3]
    left = render("2018.01.13", "第1冠", "vs 德米纳尔", tmp_path / "left.png",
                  metric="6-4 6-3", layout="classic", align="left")
    assert png_corner_label_problem(left)


def _ink_bands(path):
    """按精确填色把文字行切开。软阴影和描边不进这堆，行与行才分得开。"""
    exact = {BRAND_GREEN[:3], WHITE[:3], MUTED[:3]}
    with Image.open(path) as image:
        pix = image.convert("RGBA").load()
        _width, height = image.size
        rows = []
        for y in range(height):
            green = white = False
            seen = False
            for x in range(80, 1100):
                pixel = pix[x, y]
                if pixel[3] < 200 or pixel[:3] not in exact:
                    continue
                seen = True
                if pixel[:3] == BRAND_GREEN[:3]:
                    green = True
                if pixel[:3] == WHITE[:3]:
                    white = True
            rows.append((seen, green, white))
    bands = []
    start = None
    green = white = False
    for y, (seen, row_green, row_white) in enumerate(rows):
        if seen and start is None:
            start, green, white = y, row_green, row_white
        elif seen:
            green = green or row_green
            white = white or row_white
        elif start is not None:
            bands.append((start, y, green, white))
            start = None
    if start is not None:
        bands.append((start, len(rows), green, white))
    return bands


def test_主题独占一行_日期在地点前面(tmp_path):
    """行序是主题、日期、地点、比分、人物。没有主题时从日期起排。"""
    with_topic = render(
        "2026.10.11", "摔拍警告", "布勃利克 vs 中岛布兰登",
        tmp_path / "topic.png", highlight="ATP1000 上海", metric="6-4")
    bands = _ink_bands(with_topic)
    assert len(bands) >= 3
    _top, top_end, top_green, top_white = bands[0]
    date_top, date_end, date_green, date_white = bands[1]
    place_top, _place_end, place_green, _place_white = bands[2]
    assert top_white and not top_green
    assert date_top >= top_end and not date_green and not date_white
    assert place_green and place_top >= date_end

    no_topic = render(
        "2022.02.22", "", "兹维列夫 · 罚款4万美元",
        tmp_path / "place.png", highlight="阿卡普尔科")
    opened = _ink_bands(no_topic)
    _first_top, first_end, first_green, first_white = opened[0]
    second_top, _second_end, second_green, _second_white = opened[1]
    assert not first_green and not first_white
    assert second_green and second_top >= first_end


def test_角标文字和左上角品牌标题同一支_比分除外():
    """主题、地点、日期、人物、罚款都走品牌标题那一支；比分数字仍是 TL Score。"""
    import render_story_info_band as band
    from tennislive.video.watermark import BRAND_FONT

    assert label_font_problem() is None
    assert LABEL_FONT.name == BRAND_FONT
    assert SCORE.name == "TLScore-Bold.ttf"
    for fn in (band._render_corner, band._metric_fonts):
        source = inspect.getsource(fn)
        assert "BOLD" not in source
        assert "REGULAR" not in source
        assert "NotoSans" not in source
    # 字体漂了，豁免表也拦不住。
    real = band.LABEL_FONT
    band.LABEL_FONT = real.parent / "NotoSansSC-Bold-sub.ttf"
    try:
        problem = story_corner_label_problems(
            {"slug": "medvedev-24-titles", "segments": []})
    finally:
        band.LABEL_FONT = real
    assert problem and "品牌标题" in problem[0]


def test_别的脚本没有把左对齐写死成默认():
    hits = []
    for path in sorted((ROOT / "tools").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if ('align="left"' in text or "align='left'" in text
                or 'default="left"' in text):
            hits.append(path.name)
    assert hits == []


def test_每条片子的贴图都是右上角右轨右对齐():
    bad = []
    for path, spec in _specs():
        problems = story_corner_label_problems(spec)
        if problems:
            bad.append(f"{spec['slug']}: {problems[0]}")
    assert not bad, "这些贴图不是右上角、右轨、右对齐：\n  " + "\n  ".join(bad)


def test_角标豁免表只许减不许加():
    legacy = legacy_corner_label_slugs()
    assert legacy, "豁免表读不到，整条判据会静静失效"
    assert "code-violation-point-penalty-2026" not in legacy
    seen = {spec["slug"]: spec for _path, spec in _specs()}
    missing = sorted(slug for slug in legacy if slug not in seen)
    fixed = sorted(slug for slug in legacy
                   if slug in seen
                   and not story_corner_label_problems(seen[slug], honor_legacy=False))
    assert not missing, f"豁免表里有不存在的 slug：{missing}"
    assert not fixed, f"这些已经合格式了，从 data/legacy_corner_label.json 里删掉：{fixed}"


def test_渲染入口拒绝左上角或左轨(tmp_path):
    import build_match_reel as reel

    good = tmp_path / "good.png"
    bad = tmp_path / "bad.png"
    render("2026美网", "第1次", "场外指导", good, highlight="警告")
    render("2026美网", "第1次", "场外指导", bad, highlight="警告",
           layout="classic", align="left")

    def spec(image: Path, corner: str = "tr", slug: str = "zz-new-corner") -> dict:
        return {"slug": slug, "cover": {}, "segments": [{
            "start": 1, "end": 6, "source": "r1",
            "inset": {"image": str(image), "kind": "story_text", "corner": corner,
                      "width": 0.56, "pad": 0.085, "show_for": 3.8,
                      "motion": "editorial"}}]}

    assert reel.parse_segments(spec(good), {"r1": Path("a.mp4")}, "r1")
    with pytest.raises(reel.ReelError, match="右上角"):
        reel.parse_segments(spec(good, "tl"), {"r1": Path("a.mp4")}, "r1")
    with pytest.raises(reel.ReelError, match="右缘"):
        reel.parse_segments(spec(bad), {"r1": Path("a.mp4")}, "r1")
    # 豁免只认表里的 slug，换个名字同一张左轨图照样红。
    frozen = next(iter(legacy_corner_label_slugs()))
    assert reel.parse_segments(spec(bad, slug=frozen), {"r1": Path("a.mp4")}, "r1")
