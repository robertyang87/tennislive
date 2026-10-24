"""右上信息字卡垫「F 贴边渐隐底」（账号所有者 2026-10-24 从四种底里选的）。

圆角底被否掉的理由是「在外面没包住那个右边的竖线」，所以判据钉三件事：
底一直铺到画面右边缘（竖线和右缘之间也压暗）、往左渐隐到不碰画面、
字卡墨迹的落位和不垫底时一致。量的是 ffmpeg 真编出来的帧。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import build_match_reel as reel  # noqa: E402
from render_story_info_band import render_label  # noqa: E402

_LABEL = {"topic": "六个赛点未兑现", "date": "2026.04.28", "place": "马德里1/4决赛",
          "people": "萨巴伦卡 vs 巴普蒂斯特", "score": "6-2 2-6 6-7(6)"}


def _frame(path: Path, at: float, out: Path) -> Image.Image:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at}", "-i", str(path),
                    "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB")


@pytest.fixture
def native(tmp_path, monkeypatch):
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=0xf0f0f0:size=1920x1080:rate=25:duration=2",
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                    str(source)], check=True)
    for key, value in {"CROP_W": 810, "CROP_H": 1080, "CROP_Y": 0, "LAYOUT": "full",
                       "_INSET_TOP_CLEAR_Y": 151, "FPS": 25, "FPS_EXPR": "25/1",
                       "PART_PRESET": "ultrafast"}.items():
        monkeypatch.setattr(reel, key, value)
    image = render_label(_LABEL, tmp_path / "label.png")
    inset = {"image": str(image), "kind": "story_text", "corner": "tr", "width": .6,
             "pad": .043, "motion": "editorial", "animate": False, "label": dict(_LABEL)}
    return source, inset


def test_字卡垫贴边渐隐底_铺到右边缘_往左渐隐_墨迹不挪位(tmp_path, native, monkeypatch):
    source, inset = native
    scrim = tmp_path / "scrim.mp4"
    reel.cut_segment(source, reel.Segment(0, 1.5, .5, "", inset=inset), scrim, 1920, threads=2)
    framed = _frame(scrim, 1.0, tmp_path / "scrim.png")
    bare_inset = dict(inset)
    monkeypatch.setattr(reel, "_with_story_scrim", lambda ins, dest: ins)
    bare = tmp_path / "bare.mp4"
    reel.cut_segment(source, reel.Segment(0, 1.5, .5, "", inset=bare_inset), bare, 1920, threads=2)
    plain = _frame(bare, 1.0, tmp_path / "bare.png")

    width, pad, y_top = reel._inset_box(inset)
    mid_y = y_top + 90
    # 竖线和画面右边缘之间：垫了底就压暗，没垫就是原画面的浅灰。
    edge = (1080 - pad // 2, mid_y)
    assert sum(plain.getpixel(edge)) > 650
    assert sum(framed.getpixel(edge)) < sum(plain.getpixel(edge)) - 150, "底没铺到右边缘"
    # 往左渐隐：字卡左侧远处不碰画面。
    far_left = (1080 - pad - width - 200, mid_y)
    assert abs(sum(framed.getpixel(far_left)) - sum(plain.getpixel(far_left))) < 12
    # 字卡墨迹落位不动：品牌绿竖线在两版里是同一列。
    def rail_x(im):
        row = [im.getpixel((x, mid_y)) for x in range(700, 1080)]
        greens = [700 + i for i, (r, g, b) in enumerate(row) if g > 200 and r > 150 and b < 140]
        return greens[len(greens) // 2]
    assert abs(rail_x(framed) - rail_x(plain)) <= 1


def test_没有图的规划替身不造垫底文件(tmp_path):
    ins = {"image": str(tmp_path / "missing.png"), "kind": "story_text", "corner": "tr"}
    assert reel._with_story_scrim(ins, tmp_path / "seg.mp4") is ins
    assert not list(tmp_path.glob("*scrim*"))
