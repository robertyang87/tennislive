from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from render_story_info_band import BRAND_GREEN, display_units, metric_runs, render  # noqa: E402


def test_story_info_band_is_typography_not_a_large_panel(tmp_path):
    out = render("第一关", "尤晓迪", "六安W100冠军 · 擅长苦战",
                 tmp_path / "band.png", metric="世界第198", variant="player")
    with Image.open(out) as image:
        assert image.size == (1200, 340)
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
        alpha = image.getchannel("A")
        opaque = sum(alpha.histogram()[25:])
        assert opaque > 10_000, "文字锁定渲空了"
        assert opaque / (image.width * image.height) < 0.40, (
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


def test_story_info_band_uses_the_brand_green_as_its_only_accent(tmp_path):
    """2026-09-05 账号所有者「文字贴图也要重新设计好看些」。上一版是球场蓝＋网球黄两个
    强调色，和封面/章节卡/片尾那套墨绿＋品牌绿不是一家；现在只留品牌绿一个强调色
    （短轨、标签、硬数据都是它），名字暖白，证据冷灰白。判据钉在渲出来的像素上。"""
    out = render("2026 美网第三轮", "郑钦文 vs 凯斯", "凯斯发球胜赛局 40-30",
                 tmp_path / "band.png", metric="决胜盘 1-5 赛点", variant="player")
    with Image.open(out) as image:
        rgb = image.convert("RGBA")
        assert rgb.getpixel((27, 170))[:3] == BRAND_GREEN[:3], "短轨要是品牌绿"
        # 全图里饱和的彩色像素只许是品牌绿那一族：不许再出现球场蓝 / 网球黄
        chroma = [p for p in rgb.getdata()
                  if p[3] > 200 and max(p[:3]) - min(p[:3]) > 90]
        assert chroma, "强调色得真的画出来了"
        off_brand = [p for p in chroma if not (p[1] > p[0] > p[2])]   # 绿 > 红 > 蓝 才是那一族
        assert len(off_brand) / len(chroma) < 0.02, f"混进了别的强调色：{off_brand[:5]}"
    assert metric_runs("决胜盘 1-5 赛点") == [("决胜盘 ", False), ("1-5", True), (" 赛点", False)]
    assert metric_runs("盘分 2-2") == [("盘分 ", False), ("2-2", True)]
