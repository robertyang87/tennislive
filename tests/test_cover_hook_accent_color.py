"""封面标题重点词的可选字色：只改字色，其他 HTML/CSS 逐字节不变。"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import versus_poster as vp  # noqa: E402

LAYOUTS = ("solo", "diagonal", "split", "stack", "cutout")


@pytest.fixture(params=("WTA", "ATP"))
def cover(request, tmp_path):
    """两条巡回赛使用同一入口，照片为本地合成测试输入，不是视觉验收图。"""
    image = tmp_path / "input.png"
    Image.new("RGBA", (20, 30), (0, 0, 0, 0)).save(image)
    pair = [
        {"name": "甲", "name_en": "A. ONE", "country": None, "rank": 1},
        {"name": "乙", "name_en": "B. TWO", "country": None, "rank": 2},
    ]
    return {
        "eyebrow": "赛场之上", "topic": f"{request.param} · 甲 VS 乙",
        "subject": "甲", "hook": "他第一次赢下来\n这次没有让机会溜走",
        "hook_accent": "第一次", "winner": "甲", "result": "6-3 6-4",
        "matchup": pair,
        "scoreboard": {"court": "Centre Court", "duration_source": {"url": "fixture"}},
        "portrait": {"image": str(image)},
        "versus": {
            "names": [p["name"] for p in pair],
            "top": {**pair[0], "image": str(image), "cutout": str(image)},
            "bottom": {**pair[1], "image": str(image), "cutout": str(image)},
            "background": {"image": str(image)},
        },
    }


@pytest.fixture
def html_output(monkeypatch, tmp_path):
    """运行实际 HTML/CSS 构建；只隔离字体打包、时长联网和 Chromium 输出。"""
    monkeypatch.setattr(vp, "_font_css", lambda: "")
    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "1:23")
    captured = []

    def capture(document, out):
        captured.append(document)
        return out

    monkeypatch.setattr(vp, "_render_html", capture)

    def build(cover, layout):
        before = copy.deepcopy(cover)
        assert vp.build_poster(cover, tmp_path / "unused.jpg", layout) == tmp_path / "unused.jpg"
        assert cover == before, "颜色配置不许改写调用方的 cover"
        return captured[-1]

    return build


@pytest.mark.parametrize("layout", LAYOUTS)
def test_default_is_brand_and_explicit_brand_is_identical(cover, html_output, layout):
    default = html_output(cover, layout)
    explicit = html_output({**cover, "hook_accent_color": vp.BRAND}, layout)
    assert default == explicit
    assert vp.BRAND == vp.DARK["primary"] == "#c6f65a"
    assert f".hook .accent{{color:{vp.BRAND}}}" in default
    if layout == "solo":
        assert f".storytitle .accent{{color:{vp.BRAND}}}" in default


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("color", ("#FFD600", "#12abEF"))
def test_color_only_changes_title_accent_rules(cover, html_output, layout, color):
    default = html_output(cover, layout)
    changed = html_output({**cover, "hook_accent_color": color}, layout)
    selectors = [".hook .accent"]
    if layout == "solo":
        selectors.append(".storytitle .accent")
    expected = default
    for selector in selectors:
        old, new = f"{selector}{{color:{vp.BRAND}}}", f"{selector}{{color:{color}}}"
        assert expected.count(old) == 1
        expected = expected.replace(old, new)
    assert changed == expected, "除了指定重点词的 color 声明，不许改背景、描边、阴影或其他 token"
    assert changed.count(color) == len(selectors)
    assert changed.count('<span class="accent">第一次</span>') == 1
    assert f"background:{vp.BRAND}" in changed
    assert vp.BRAND == vp.DARK["primary"] == "#c6f65a"


def test_color_does_not_create_an_accent(cover, html_output):
    cover.pop("hook_accent")
    document = html_output({**cover, "hook_accent_color": "#FFD600"}, "solo")
    assert '<span class="accent">' not in document


@pytest.mark.parametrize("color", (
    None, False, 123, {}, [], "", "FFD600", "#ff0", "#FFD600FF", "#GGD600",
    " #FFD600", "#FFD600\n", "yellow", "var(--brand)", "rgb(255,214,0)",
    "#FFD600;background:red", "#FFD600}</style><script>alert(1)</script>",
))
def test_invalid_color_is_rejected_before_render(monkeypatch, color):
    def unexpected_render(*args):
        pytest.fail("无效颜色必须在渲染前拒绝")

    monkeypatch.setattr(vp, "_render_html", unexpected_render)
    with pytest.raises(SystemExit, match=r"cover\.hook_accent_color.*#RRGGBB"):
        vp.build_poster({"subject": "甲", "hook": "第一次赢", "hook_accent_color": color},
                        Path("unused.jpg"), "solo")


def test_new_field_is_registered():
    import build_match_reel as reel  # noqa: PLC0415

    assert "hook_accent_color" in reel._REAL_FIELDS["cover"]
