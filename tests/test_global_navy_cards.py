"""用户 2026-10-04：全栏目图卡要统一愉悦的蓝色设计，含网球有故事。

查真实浏览器像素，避免只改 token、遗漏独立背景或还在播放旧片尾母版。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def card_markup(kind: str) -> tuple[str, tuple[int, int]]:
    from tennislive.render.webcards import _shell, tournament_story_body
    from tennislive.render.tournament_story import find_story_by_slug
    from tennislive.video import explainer as ex, outro_page
    from tennislive.video.no1_charts import weeks_at_no1_chart
    import build_interview_clip as interview
    import render_stat_card as stats
    import render_title_card as title

    if kind == "chapter":
        return title.build("5次反扑机会落空\n萨巴伦卡两盘出局", kicker="错失机会"), (1080, 1440)
    if kind == "story-video":
        beat = ex.ExplainerSegment("ends", "排名历史", "连续最久一百八十六周", "",
                                   points=("连续最久186周", "累计最多377周"),
                                   diagram=weeks_at_no1_chart())
        return ex._slide_html(1, beat, column="网球有故事"), (1080, 1440)
    if kind == "story-image":
        story = find_story_by_slug("weeks-at-no1")
        return _shell(tournament_story_body(story, "2026.10.04"), "dark"), (1080, 1440)
    if kind == "outro":
        return outro_page._page(None), (1080, 1440)
    if kind == "interview":
        spec = {"column": "赛后开麦", "takeaway": {"close": {"point": "先看他说了什么"}}}
        return interview.takeaway_html(spec, "close"), (1080, 1440)
    spec = json.loads((ROOT / "specs/reels/sabalenka-bartunkova-beijing-2026-r3.json").read_text())
    return stats.build(spec, variant="film"), (1080, 1440)


KINDS = ("chapter", "stats", "story-video", "story-image", "interview", "outro")


@pytest.mark.parametrize("kind", KINDS)
def test_各栏目实际背景像素都是柔和深蓝(kind):
    from playwright.sync_api import sync_playwright
    from render_stat_card import _launch_browser

    markup, size = card_markup(kind)
    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        page.set_content(markup)
        page.evaluate("document.fonts.ready")
        frame = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
        browser.close()
    # 左侧空白处避开彩条、文字、头像和图表，分别量上、中、下三层底图。
    for y in (200, 800, 1250):
        r, g, b = frame.getpixel((20, y))
        assert b > g >= r and b - r >= 10, (kind, y, (r, g, b))
        assert max(r, g, b) < 110, (kind, y, "背景不能抢正文", (r, g, b))


def test_生产片尾母版实际像素也已经换成深蓝(tmp_path):
    import subprocess
    from tennislive.video import outro_page

    frame = tmp_path / "master.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2.5", "-i", str(outro_page.MASTER),
                    "-frames:v", "1", str(frame)], check=True)
    r, g, b = Image.open(frame).convert("RGB").getpixel((20, 800))
    assert b > g >= r and b - r >= 10, (r, g, b)
