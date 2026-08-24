from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import display_units, render  # noqa: E402


def test_story_info_band_is_typography_not_a_large_panel(tmp_path):
    out = render("第一关", "尤晓迪", "六安W100冠军 · 擅长苦战",
                 tmp_path / "band.png", metric="世界第198", variant="player")
    with Image.open(out) as image:
        assert image.size == (1200, 292)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        alpha = image.getchannel("A")
        opaque = sum(alpha.histogram()[25:])
        assert opaque > 10_000, "文字锁定渲空了"
        assert opaque / (image.width * image.height) < 0.34, (
            "不许退回覆盖大半画面的实色圆角板")


def test_story_info_band_requires_all_three_levels(tmp_path):
    with pytest.raises(SystemExit, match="都必须填写"):
        render("第一关", "尤晓迪", "", tmp_path / "bad.png")


def test_story_info_band_separates_fields_and_caps_copy(tmp_path):
    with pytest.raises(SystemExit, match="不要用竖线"):
        render("第一关", "尤晓迪｜世界第198", "擅长苦战",
               tmp_path / "pipe.png")
    with pytest.raises(SystemExit, match="一屏只留一个记忆点"):
        render("第一关", "尤晓迪", "这是一行明显长到不能扫读完的屏幕解释文字还在继续",
               tmp_path / "long.png")
    assert display_units("世界No.127") < display_units("世界第一百二十七")
