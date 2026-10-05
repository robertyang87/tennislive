import pytest
from PIL import Image

from tennislive.render.tournament_story import find_story_by_slug
from tennislive.video import explainer as E


SLUG = "medvedev-beijing-default-2026"


def test_portrait_cover_really_fills_the_declared_canvas(tmp_path):
    pytest.importorskip("playwright.sync_api")
    cover = E.explainer_script(find_story_by_slug(SLUG))[0]
    paths = E.render_explainer_slides([cover], tmp_path, height=E.VIDEO_H)
    with Image.open(paths[0]) as image:
        assert image.size == (2160, 3840)
        # The original ball logo must be present in the rendered upper left.
        badge = image.crop((140, 88, 244, 192)).convert("RGB")
        assert sum(g > 150 and g > r and b < 160
                   for r, g, b in badge.getdata()) > 200
    assert "失格 Default · 滥用球 Ball Abuse" in E._slide_html(
        0, cover, height=E.VIDEO_H)


def test_incident_excerpt_keeps_its_reviewed_bilingual_subtitles():
    opening = E._OPENINGS[SLUG]
    assert opening["intro_end"] - opening["intro_start"] == 20
    filters = E._intro_filter(opening, E.canvas_height(SLUG))
    assert "crop=1080:1920:(iw-ow)/2:(ih-oh)/2" in filters
    subtitles = (E._REPO / opening["intro_subtitles"]).read_text()
    assert "PlayResY: 1920" in subtitles
    assert "Medvedev default" in subtitles and "梅德韦杰夫失格" in subtitles
    assert "Medfordev" not in subtitles
    assert E._intro_filter({}, E.H) == ""  # Existing episodes retain their framing.


def test_missing_reviewed_subtitles_fail_before_rendering():
    with pytest.raises(E.ExplainerVideoError, match="字幕找不到"):
        E._intro_filter({"intro_subtitles": "missing-source-captions.ass"}, E.VIDEO_H)
