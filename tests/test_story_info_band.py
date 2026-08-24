from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import render  # noqa: E402


def test_story_info_band_has_fixed_grid_and_transparent_exterior(tmp_path):
    out = render("第一关", "尤晓迪｜世界第198", "六安W100冠军 · 擅长苦战",
                 tmp_path / "band.png")
    with Image.open(out) as image:
        assert image.size == (864, 232)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        assert image.getpixel((40, 40))[3] > 180


def test_story_info_band_requires_all_three_levels(tmp_path):
    with pytest.raises(SystemExit, match="都必须填写"):
        render("第一关", "尤晓迪", "", tmp_path / "bad.png")
