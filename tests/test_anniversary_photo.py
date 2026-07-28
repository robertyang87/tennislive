"""配图工具的判据（CLAUDE.md：规则要落成测试）。

全部是纯函数与守门条件，不走网络——网络那部分靠 probe 的人工复核。
"""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "anniversary_photo", Path("tools/anniversary_photo.py")
)
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)


def test_photo_resources_必须补上width否则恒回400():
    """WTA 图库两个地址空间取法不同，这条是探 8/2 混双那张时试出来的。

    不知道的话会把整个 /photo-resources/ 空间误判成「下载失败」，
    而那里面躺着真正的报道图——8/3 那张 4000px 就在里面。
    """
    resources = "https://photoresources.wtatennis.com/photo-resources/2024/08/03/x/a.jpg"
    assert tool.sized_url(resources).endswith("?width=4000")
    # 已经带了就不要再加一遍
    assert tool.sized_url(resources + "?width=1600") == resources + "?width=1600"
    # /wta/photo/ 直接给原图，不能画蛇添足
    direct = "https://photoresources.wtatennis.com/wta/photo/2024/08/03/x/a.jpg"
    assert tool.sized_url(direct) == direct


def test_满高那一档裁法让人物相对最小():
    """「宁可人小一点：整个人在画面里、左右留白比想象的更多」。"""
    boxes = tool._crop_boxes(4000, 2666, center_x=1946)
    widths = sorted((box[2] - box[0]) for box in boxes.values())
    assert len(widths) == 2 and widths[1] > widths[0]
    for box in boxes.values():
        w, h = box[2] - box[0], box[3] - box[1]
        assert abs(w / h - 0.75) < 0.01, f"不是 3:4：{w}x{h}"
        assert box[0] >= 0 and box[2] <= 4000 and box[3] <= 2666


def test_竖图裁高度而不是硬塞宽度():
    boxes = tool._crop_boxes(1920, 2880, center_x=None)
    (box,) = boxes.values()
    w, h = box[2] - box[0], box[3] - box[1]
    assert w == 1920 and abs(w / h - 0.75) < 0.01


def test_装饰件按文件名筛而不是按路径():
    """第一版按路径筛，把 Mixed-doubles-gold-medal.jpg 当装饰件滤掉了。

    那是一张真正的报道图。判据钉在这个回归上。
    """
    html = " ".join(
        [
            "https://photoresources.wtatennis.com/photo-resources/2024/08/02/x/Mixed-doubles-gold-medal.jpg",
            "https://photoresources.wtatennis.com/photo-resources/2026/05/07/y/Accenture-Footer-Logo.png",
            "https://photoresources.wtatennis.com/photo-resources/2026/07/01/z/Finals-Quick-Link-Tile.png",
        ]
    )
    found = tool._IMAGE_IN_PAGE.findall(html)
    assert len(found) == 3
    kept = [
        u
        for u in found
        if not any(
            w in u.rsplit("/", 1)[-1].lower()
            for w in ("logo", "tile", "footer", "header", "banner", "icon", "quick-link")
        )
    ]
    assert kept == [found[i] for i in range(3) if "Mixed-doubles" in found[i]]


def _commit(tmp_path, monkeypatch, size, **kw):
    from PIL import Image

    monkeypatch.setattr(tool, "TRIVIA", tmp_path)
    monkeypatch.setattr(tool, "CREDITS", tmp_path / "credits.json")
    src = tmp_path / "in.jpg"
    Image.new("RGB", size, "red").save(src)
    args = {
        "slug": "otd-0101",
        "image": str(src),
        "page": "https://example.org/a",
        "license": "CC BY-SA 4.0",
        "artist": "Someone",
        "license_free": True,
        "title": "",
        "description": "",
        "date_original": "",
        "crop_note": "",
        "tradeoff": "",
        "rights_note": "",
    }
    args.update(kw)
    import argparse

    return tool.cmd_commit(argparse.Namespace(**args))


def test_入库前挡住不是3比4的图(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="3:4"):
        _commit(tmp_path, monkeypatch, (1600, 900))


def test_入库前挡住低于封面下限的图(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="下限"):
        _commit(tmp_path, monkeypatch, (600, 800))


def test_授权和作者是必填(tmp_path, monkeypatch):
    """缺授权就记 unknown/unverified，但不能不写——权利判断靠这两个字段。"""
    with pytest.raises(SystemExit, match="必填"):
        _commit(tmp_path, monkeypatch, (1200, 1600), license="")
    with pytest.raises(SystemExit, match="必填"):
        _commit(tmp_path, monkeypatch, (1200, 1600), artist="")


def test_非自由授权要在credits里留痕(tmp_path, monkeypatch):
    _commit(
        tmp_path,
        monkeypatch,
        (1200, 1600),
        license="官方媒体供图 · 非商业资讯引用",
        license_free=False,
        rights_note="发布前需人工过权利",
    )
    entry = json.loads((tmp_path / "credits.json").read_text(encoding="utf-8"))[
        "trivia-otd-0101.jpg"
    ]
    assert entry["license_free"] is False
    assert entry["rights_note"]
