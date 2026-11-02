"""Focused contract and real browser seek tests for composable photography."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tennislive.video.story_photo_motion import photo_blocks_html, validate_block


def example():
    return {"start": 2, "duration": 6, "pages": [
        {"path": "a.jpg", "source": "https://example.org/photo-a", "date": "2026.01.02",
         "event": "测试赛事 第二轮", "headline": "球员甲的节点", "kicker": "CITY A"},
        {"path": "b.jpg", "source": "https://example.org/photo-b", "date": "2026.06.03",
         "event": "另一赛事 八强", "headline": "Smith 的新一页", "kicker": "CITY B"},
    ]}


@pytest.mark.parametrize("change", [
    lambda b: b.pop("start"), lambda b: b.update(duration=float("nan")),
    lambda b: b.update(start=True), lambda b: b.update(frame=[0, 0, 1081, 1440]),
    lambda b: b.update(frame=[0, 1000, 1080, 1000]),
    lambda b: b.update(copy_y=1400), lambda b: b.update(unknown="field"),
    lambda b: b["pages"][0].pop("source"),
    lambda b: b["pages"][0].update(source=" "),
    lambda b: b["pages"][0].update(source="url\nsecond line"),
    lambda b: b["pages"][0].update(path=""),
    lambda b: b["pages"][0].update(focus=[1.1, .5]),
    lambda b: b["pages"][0].update(duration=4),
    lambda b: b["pages"][0].update(start=1),
    lambda b: [p.update(start=3) for p in b["pages"]],
])
def test_rejects_invalid_layout_sources_and_timing(change):
    block = example()
    change(block)
    with pytest.raises(ValueError):
        validate_block(block)


def test_arbitrary_page_schedule_and_metadata_are_detached():
    block = example()
    block["pages"][0].update(start=.5, duration=1)
    block["pages"][1].update(start=3.5, duration=2)
    original = deepcopy(block)
    p = validate_block(block)
    assert block == original
    assert [n["start"] for n in p["pages"]] == [.5, 3.5]
    p["pages"][0]["focus"][0] = .2
    assert "focus" not in block["pages"][0]
    assert p["frame"] == [0, 180, 1080, 1000]


def test_resolver_and_escaping_preserve_content_without_executing_it():
    block = example()
    block["pages"][0]["headline"] = '<script>alert("x")</script>'
    block["pages"][0]["source"] = 'https://example.org/</script>'
    seen = []
    body, css, js = photo_blocks_html(block, 8, lambda path: seen.append(path) or "/photos/" + path)
    assert seen == ["a.jpg", "b.jpg"]
    assert 'id="story-photo-8"' in body
    assert "&lt;script&gt;" in body and "</script>" not in js
    assert "data-story-text" in body
    assert "window.storyRenderers.push(render)" in js
    assert "gsap.set" not in js
    with pytest.raises(ValueError):
        photo_blocks_html(block, 1, lambda _: "javascript:alert(1)")


def test_browser_seek_backwards_multiple_subjects_and_transparent_gaps():
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    # Synthetic image fixture only; the production resolver supplies verified
    # native photography. No production card, source file or encoder is touched.
    image = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="1080" height="1000"%3E%3Cpath fill="%23215471" d="M0 0h1080v1000H0z"/%3E%3C/svg%3E'
    block = example()
    body, css, js = photo_blocks_html(block, 0, lambda _: image)
    with sync_playwright() as pw:
        browser = launch_chromium(pw, args=["--no-sandbox"])
        try:
            page = browser.new_page(viewport={"width": 1080, "height": 1440})
            page.set_content('<style>body{margin:0}' + css + '</style>' + body)
            page.wait_for_function('Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)')
            page.evaluate(js)
            def shot(t):
                page.evaluate('(t)=>window.storyRenderers.forEach(f=>f(t))', t)
                return page.screenshot()
            first = shot(3.4)
            second = shot(6.4)
            assert first != second
            shot(30)
            assert shot(3.4) == first
            shot(0)
            assert shot(6.4) == second
            assert page.evaluate('window.storyPhotoChecks.flatMap(f=>f())') == []
            shot(8)
            assert page.eval_on_selector('#story-photo-0', 'n=>getComputedStyle(n).visibility') == 'hidden'
            # A declared gap stays empty, then restores on backward seek.
            gap = example()
            gap["pages"][0]["duration"] = 1
            gb, gc, gj = photo_blocks_html(gap, 1, lambda _: image)
            page.add_style_tag(content=gc)
            page.evaluate('(s)=>document.body.insertAdjacentHTML("beforeend",s)', gb)
            page.evaluate(gj)
            shot(4)
            assert page.eval_on_selector_all('#story-photo-1 .spm-page', 'ns=>ns.every(n=>getComputedStyle(n).visibility==="hidden")')
        finally:
            browser.close()
