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
    META_SEP,
    MUTED,
    SCORE,
    WHITE,
    label_fields_problem,
    label_font_problem,
    legacy_corner_label_slugs,
    legacy_label_fields_slugs,
    metric_from_label,
    png_corner_label_problem,
    render,
    render_label,
    story_corner_label_problems,
    story_label_field_problems,
)

_OK_LABEL = {
    "topic": "第1次",
    "date": "2026.09.08",
    "place": "美网",
    "people": "小威廉姆斯",
    "event": "第1次",
}

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
            green = white = muted = False
            seen = False
            green_xs = []
            muted_xs = []
            for x in range(80, 1100):
                pixel = pix[x, y]
                if pixel[3] < 200 or pixel[:3] not in exact:
                    continue
                seen = True
                if pixel[:3] == BRAND_GREEN[:3]:
                    green = True
                    green_xs.append(x)
                elif pixel[:3] == WHITE[:3]:
                    white = True
                elif pixel[:3] == MUTED[:3]:
                    muted = True
                    muted_xs.append(x)
            rows.append((seen, green, white, muted, green_xs, muted_xs))
    bands = []
    start = None
    green = white = muted = False
    green_xs = []
    muted_xs = []
    for y, (seen, row_green, row_white, row_muted, row_gxs, row_mxs) in enumerate(rows):
        if seen and start is None:
            start = y
            green, white, muted = row_green, row_white, row_muted
            green_xs, muted_xs = list(row_gxs), list(row_mxs)
        elif seen:
            green = green or row_green
            white = white or row_white
            muted = muted or row_muted
            green_xs.extend(row_gxs)
            muted_xs.extend(row_mxs)
        elif start is not None:
            bands.append({
                "y0": start, "y1": y, "green": green, "white": white, "muted": muted,
                "green_x0": min(green_xs) if green_xs else None,
                "green_x1": max(green_xs) if green_xs else None,
                "muted_x0": min(muted_xs) if muted_xs else None,
                "muted_x1": max(muted_xs) if muted_xs else None,
            })
            start = None
    if start is not None:
        bands.append({
            "y0": start, "y1": len(rows), "green": green, "white": white, "muted": muted,
            "green_x0": min(green_xs) if green_xs else None,
            "green_x1": max(green_xs) if green_xs else None,
            "muted_x0": min(muted_xs) if muted_xs else None,
            "muted_x1": max(muted_xs) if muted_xs else None,
        })
    return bands


def test_主题独占一行_日期和地点同一行且日期在前(tmp_path):
    """主题自己一行。日期和地点同一行，日期在前，中间是「 · 」。"""
    assert META_SEP == " · "
    with_topic = render(
        "2026.10.11", "摔拍警告", "布勃利克 vs 中岛布兰登",
        tmp_path / "topic.png", highlight="ATP1000 上海", metric="6-4")
    bands = _ink_bands(with_topic)
    assert len(bands) >= 2
    topic, meta = bands[0], bands[1]
    assert topic["white"] and not topic["green"]
    assert meta["y0"] >= topic["y1"]
    assert meta["muted"] and meta["green"]
    assert meta["muted_x1"] < meta["green_x0"]

    no_topic = render(
        "2022.02.22", "", "兹维列夫 · 罚款4万美元",
        tmp_path / "place.png", highlight="阿卡普尔科")
    first = _ink_bands(no_topic)[0]
    assert first["muted"] and first["green"]
    assert first["muted_x1"] < first["green_x0"]


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


def test_每条片子的贴图都写齐字段():
    bad = []
    for path, spec in _specs():
        problems = story_label_field_problems(spec)
        if problems:
            bad.append(f"{spec['slug']}: {problems[0]}")
    assert not bad, "这些贴图缺 topic、date、place、people 或 score/event：\n  " + "\n  ".join(bad)


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
                      "motion": "editorial", "label": dict(_OK_LABEL)}}]}

    assert reel.parse_segments(spec(good), {"r1": Path("a.mp4")}, "r1")
    naked = spec(good)
    naked["segments"][0]["inset"].pop("label")
    with pytest.raises(reel.ReelError, match="label"):
        reel.parse_segments(naked, {"r1": Path("a.mp4")}, "r1")
    with pytest.raises(reel.ReelError, match="右上角"):
        reel.parse_segments(spec(good, "tl"), {"r1": Path("a.mp4")}, "r1")
    with pytest.raises(reel.ReelError, match="右缘"):
        reel.parse_segments(spec(bad), {"r1": Path("a.mp4")}, "r1")
    # 豁免只认表里的 slug，换个名字同一张左轨图照样红。
    frozen = next(iter(legacy_corner_label_slugs()))
    assert reel.parse_segments(spec(bad, slug=frozen), {"r1": Path("a.mp4")}, "r1")


def test_字段缺一项就红_比分和事件至少要有一个():
    assert label_fields_problem(None)
    assert "topic" in (label_fields_problem({**_OK_LABEL, "topic": ""}) or "")
    assert "date" in (label_fields_problem({**_OK_LABEL, "date": "2026-09-08"}) or "")
    assert "score" in (label_fields_problem({**_OK_LABEL, "event": ""}) or "")
    bad_score = label_fields_problem({**_OK_LABEL, "score": "决胜盘 1-5"})
    assert bad_score and "整场比分" in bad_score
    assert label_fields_problem({**_OK_LABEL, "event": ""}) 
    scored = {**_OK_LABEL, "event": "", "score": "6-4 2-6"}
    assert label_fields_problem(scored) is None
    assert label_fields_problem(_OK_LABEL) is None
    assert metric_from_label(_OK_LABEL) == ""
    assert metric_from_label(scored) == "6-4 2-6"
    distinct = {**_OK_LABEL, "event": "罚一分"}
    assert label_fields_problem(distinct) is None
    assert metric_from_label(distinct) == "罚一分"


def test_字段豁免表只许减不许加():
    legacy = legacy_label_fields_slugs()
    assert legacy, "豁免表读不到，整条判据会静静失效"
    assert len(legacy) <= 21, "只许减不许加（闸合并那天是 21 条）"
    seen = {spec["slug"]: spec for _path, spec in _specs()}
    missing = sorted(slug for slug in legacy if slug not in seen)
    fixed = []
    for slug in sorted(legacy):
        if slug not in seen:
            continue
        still = False
        for raw in seen[slug].get("segments") or []:
            inset = (raw or {}).get("inset") or {}
            if str(inset.get("kind") or "") != "story_text":
                continue
            if label_fields_problem(inset.get("label")):
                still = True
                break
        if not still:
            fixed.append(slug)
    assert not missing, f"豁免表里有不存在的 slug：{missing}"
    assert not fixed, f"这些字段已经齐了，从 data/legacy_label_fields.json 里删掉：{fixed}"


def test_按字段渲贴图_事件和主题同一句时不另起比分行(tmp_path):
    out = tmp_path / "label.png"
    render_label(_OK_LABEL, out)
    with Image.open(out) as image:
        assert image.size[0] == 1200
        assert image.size[1] >= 340 and image.size[1] % 2 == 0
    with pytest.raises(SystemExit, match="label"):
        render_label({}, tmp_path / "nope.png")


@pytest.mark.parametrize("metric", ["6-2 6-3", "7-6(5) 6-7(8) 7-5 4-6 6-4"])
def test_确认版角标同基线居中并按盘区分粗细和抢七上标(tmp_path, monkeypatch, metric):
    """Exercise the production drawing calls, including both tiebreak orientations."""
    from PIL import ImageDraw
    import render_story_info_band as band

    calls = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        if kwargs.get("fill") in {WHITE, MUTED, BRAND_GREEN}:
            calls.append((xy, text, kwargs))
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    out = render("2026.09.07", "领先之后被逆转", "斯瓦泰克 vs 郑钦文",
                 tmp_path / "five.png", highlight="美网第四轮", metric=metric)
    date = next(c for c in calls if c[1] == "2026.09.07")
    place = next(c for c in calls if c[1] == " · 美网第四轮")
    assert date[0][1] == place[0][1], "日期和赛事必须共用基线"
    people = [next(c for c in calls if c[1] == t)
              for t in ("斯瓦泰克", " vs ", "郑钦文")]
    centers = []
    for xy, text, kw in people:
        box = kw["font"].getbbox(text, anchor=kw["anchor"])
        centers.append(xy[1] + (box[1] + box[3]) / 2)
        assert Path(kw["font"].path).name == "SmileySans-Oblique.ttf"
    assert max(centers) - min(centers) <= 1
    assert people[0][2]["fill"] == BRAND_GREEN  # left wins 3 sets to 2
    assert people[2][2]["fill"] == WHITE
    digits = [c for c in calls if c[1].isdigit()]
    main_size = max(c[2]["font"].size for c in digits)
    assert main_size == band.CORNER_SCORE_SIZE == 98, "两盘和五盘必须保持确认的同一字号"
    for xy, text, kw in digits:
        expected = "TLScore-Bold.ttf" if kw["fill"] == BRAND_GREEN else "TLScore-Light.ttf"
        assert Path(kw["font"].path).name == expected
        if kw["font"].size < main_size:
            assert xy[1] < max(c[0][1] for c in digits), "小分必须上移"
    assert not any("(" in text or ")" in text for _xy, text, _kw in calls)
    digit_boxes = []
    for xy, text, kw in digits:
        box = kw["font"].getbbox(text, anchor="ls")
        digit_boxes.append((xy[0] + box[0], xy[0] + box[2]))
    score_width = max(b[1] for b in digit_boxes) - min(b[0] for b in digit_boxes)
    assert score_width <= band.CORNER_SCORE_LANE
    if len(metric.split()) == 5:
        assert score_width > band.CORNER_LANE, "五盘应向左展开，不能仍挤在原窄列里"
    assert min(b[0] for b in digit_boxes) >= 66, "展开后也不能裁掉左侧数字"
    assert png_corner_label_problem(out) is None
    def ink_y(call):
        xy, text, kw = call
        box = kw["font"].getbbox(text, anchor="ls")
        return xy[1] + box[1], xy[1] + box[3]

    # Include outlines and the shadow, not just configured row padding.
    meta_bottom = max(ink_y(c)[1] for c in (date, place))
    score_top = min(ink_y(c)[0] for c in digits)
    score_bottom = max(ink_y(c)[1] for c in digits)
    people_top = min(ink_y(c)[0] for c in people)
    assert meta_bottom + band.CORNER_STROKE + band.CORNER_SHADOW_OFFSET < score_top - band.CORNER_STROKE
    assert score_bottom + band.CORNER_STROKE + band.CORNER_SHADOW_OFFSET < people_top - band.CORNER_STROKE


def test_固定字号比分超出画布必须报错而非缩小(tmp_path):
    # A deliberately oversized, otherwise parseable layout fixture.
    metric = " ".join(["7-6(100)"] * 5)
    with pytest.raises(SystemExit, match="比分固定字号超出画布"):
        render("2026.09.07", "排版示意", "球员甲 vs 球员乙",
               tmp_path / "overflow.png", highlight="美网男单决赛", metric=metric)


def test_新字卡默认15秒并允许向右靠_超过上限仍拒绝(tmp_path):
    import build_match_reel as reel
    import render_story_info_band as band

    path = render_label(_OK_LABEL, tmp_path / "label.png")
    inset = {"image": str(path), "kind": "story_text", "corner": "tr",
             "width": band.STORY_LABEL_WIDTH, "pad": band.STORY_LABEL_PAD,
             "motion": "editorial", "label": dict(_OK_LABEL)}
    spec = {"cover": {}, "segments": [{"source": "r", "start": 0, "end": 2,
                                         "inset": inset}]}
    segments = reel.parse_segments(spec, {"r": Path("source.mp4")}, "r")
    assert segments[0].length == 2
    assert "lt(t,15.000)" in reel._overlay_chain("[0:v]null[base]", segments[0].inset)
    inset["show_for"] = 15.01
    with pytest.raises(reel.ReelError, match="story_text"):
        reel.parse_segments(spec, {"r": Path("source.mp4")}, "r")


def test_完整五盘比分不套解释文案字数上限():
    five = {**_OK_LABEL, "score": "7-6(5) 6-7(8) 7-5 4-6 6-4"}
    assert label_fields_problem(five) is None
    assert "最多5盘" in label_fields_problem({**five, "score": five["score"] + " 6-4"})
