"""段落级 `crop_zoom`：原来在允许字段表里、渲染一处都没读——写了不报错也不生效。

来路：prozorova-concussion-withdrawal-2026 给 Guardian 成片的三段写了 `crop_zoom: 1.3`
想把顶上的水印条裁出画外，run 36214015142 渲出来水印原样还在。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel  # noqa: E402


@pytest.fixture(autouse=True)
def _window(monkeypatch):
    # 1920×1080 源片的 3:4 窗口
    monkeypatch.setattr(reel, "CROP_W", 810)
    monkeypatch.setattr(reel, "CROP_H", 1080)
    monkeypatch.setattr(reel, "CROP_Y", 0)


def test_不放大就是原窗口():
    assert reel.zoomed_window(555, 1.0, None) == (810, 1080, 555, 0)


def test_放大后窗口缩小_横向中心不变_纵向按fill_y落():
    w, h, x, y = reel.zoomed_window(555, 1.3, 1.0)
    assert (w, h) == (622, 830)
    assert x + w / 2 == pytest.approx(555 + 810 / 2, abs=1)
    assert y == 1080 - 830            # 往下对齐：顶上裁掉 250px（水印条就在那儿）
    _, _, _, y_mid = reel.zoomed_window(555, 1.3, None)
    assert y_mid == (1080 - 830) // 2
    _, _, _, y_top = reel.zoomed_window(555, 1.3, 0.0)
    assert y_top == 0


def test_spec里的crop_zoom真的被读进Segment():
    assert reel._seg_crop_zoom({"crop_zoom": 1.3}, 0) == 1.3
    assert reel._seg_crop_zoom({}, 0) == 1.0


@pytest.mark.parametrize("bad", [0.8, 2.5, "x"])
def test_crop_zoom越界当场报(bad):
    with pytest.raises(reel.ReelError, match="crop_zoom"):
        reel._seg_crop_zoom({"crop_zoom": bad}, 0)


@pytest.mark.parametrize("extra", [{"track": True}, {"score_inset": True},
                                   {"fit": "contain"}])
def test_crop_zoom只支持普通裁切段(extra):
    with pytest.raises(reel.ReelError, match="只支持普通裁切段"):
        reel._seg_crop_zoom({"crop_zoom": 1.2, **extra}, 0)


def test_渲染的普通裁切链真的用了放大后的窗口():
    """反向验证过：把 `zoomed_window` 那一行换回 `crop={CROP_W}:{CROP_H}:{x}:{CROP_Y}`，这一条红。"""
    src = (Path(reel.__file__).read_text(encoding="utf-8"))
    assert 'zw, zh, zx, zy = zoomed_window(x, seg.crop_zoom, seg.fill_y)' in src
    assert 'chain = (f"crop={zw}:{zh}:{zx}:{zy},"' in src
