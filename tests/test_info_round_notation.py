"""The shared label entry points must draw the account-wide round notation."""
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import render, render_label  # noqa: E402


@pytest.mark.parametrize("written,numeric", [
    ("四分之一决赛", "1/4决赛"),
    ("八分之一决赛", "1/8决赛"),
    ("1 ／ 8 决赛", "1/8决赛"),
])
@pytest.mark.parametrize("structured", [False, True])
def test_all_label_entry_points_draw_numeric_rounds(tmp_path, written, numeric, structured):
    def draw(round_text, destination):
        if structured:
            return render_label({"topic": "逆转过关", "date": "2026.09.08",
                                 "place": f"美网{round_text}", "people": "佩古拉 vs 纳瓦罗",
                                 "score": "3-6 6-4 6-3"}, destination)
        return render("2026.09.08", "逆转过关", "佩古拉 vs 纳瓦罗", destination,
                      highlight=f"美网{round_text}", metric="3-6 6-4 6-3")

    actual = draw(written, tmp_path / "written.png")
    expected = draw(numeric, tmp_path / "numeric.png")
    with Image.open(actual) as left, Image.open(expected) as right:
        assert left.size == right.size
        assert ImageChops.difference(left.convert("RGB"), right.convert("RGB")).getbbox() is None
        assert left.getchannel("A").tobytes() == right.getchannel("A").tobytes()


def test_information_round_policy_preserves_personal_results_and_semifinals(tmp_path, monkeypatch):
    drawn = []
    original = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kwargs):
        drawn.append(text)
        return original(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    render("2026.09.08", "止步8强", "佩古拉", tmp_path / "result.png",
           highlight="美网半决赛", metric="5-7 2-6")
    assert "止步8强" in drawn
    assert any("美网半决赛" in run for run in drawn)
