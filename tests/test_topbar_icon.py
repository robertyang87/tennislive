"""顶栏第一行最前面的小图标：赛后开麦是麦克风，赛场之上是透视球场。

账号所有者 2026-09-25 看完两张示意图定的（「就用 a 吧」）。图标是 ASS 矢量，
位置由 libass 连同后面的文字一起居中——**「居中」「上下对齐」「真的画出来了」
这三件事只有烧出来量才看得见**，ASS 文本里写得再对，字体基线一偏、`\\p0`
漏写一个，成片上就是图标飘着或者整行文字变成绿色，而这些都不报错。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from tennislive.video.topbar_icon import (  # noqa: E402
    ASPECT, COURT, MIC, drawing, icon_advance)

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None,
                                reason="要 ffmpeg/libass 真烧一帧")


def _burn(ass_text: str, tmp_path: Path, w: int, h: int) -> np.ndarray:
    ass = tmp_path / "t.ass"
    ass.write_text(ass_text, encoding="utf-8")
    png = tmp_path / "t.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
         f"color=c=0x06140f:s={w}x{h}:d=1",
         "-vf", f"subtitles={ass}:fontsdir={ROOT / 'assets/fonts'}",
         "-frames:v", "1", "-y", str(png)], check=True)
    return np.asarray(Image.open(png).convert("RGB")).astype(int)


def _ink(band: np.ndarray) -> dict:
    """绿墨（图标）和白墨（文字）各自的包围盒。"""
    green = (band[:, :, 1] > 120) & (band[:, :, 1] - band[:, :, 0] > 60)
    white = band.min(axis=2) > 150
    out = {}
    for key, mask in (("icon", green), ("text", white)):
        ys, xs = np.where(mask.any(axis=1))[0], np.where(mask.any(axis=0))[0]
        assert ys.size and xs.size, f"{key} 一个像素都没画出来"
        out[key] = (xs.min(), xs.max(), ys.min(), ys.max())
    return out


def _check_line(ink: dict, canvas_w: int, want_tall: bool) -> None:
    ix0, ix1, iy0, iy1 = ink["icon"]
    tx0, tx1, ty0, ty1 = ink["text"]
    assert ix1 < tx0, "图标要在文字前面，而且不许压上去"
    gap = tx0 - ix1
    assert 6 <= gap <= 30, f"图标和文字之间空了 {gap}px"
    icon_mid, text_mid = (iy0 + iy1) / 2, (ty0 + ty1) / 2
    assert abs(icon_mid - text_mid) <= 2, (
        f"图标中线 {icon_mid} 和文字中线 {text_mid} 没对齐——`\\pbo` 那一截算错了，"
        "或者字体换了、`HEAD_CENTRE_ABOVE_BASELINE` 要重量")
    block_mid = (ix0 + tx1) / 2
    assert abs(block_mid - canvas_w / 2) <= 4, (
        f"图标＋文字整块的中线在 {block_mid}，画布中线 {canvas_w / 2}——"
        "图标该是这一行里的一段，跟着一起居中")
    iw, ih = ix1 - ix0, iy1 - iy0
    assert (ih > iw) == want_tall, f"图标 {iw}×{ih} 的方向不对（麦克风竖、球场横）"


def test_赛后开麦顶栏是麦克风而且和文字一起居中(tmp_path):
    import build_interview_clip as clip

    spec = json.loads((ROOT / "specs/interviews/"
                       "chwalinska-mertens-singapore-2026-qf-interview.json")
                      .read_text(encoding="utf-8"))
    a, b = clip.header_ass(spec)
    arr = _burn(clip._ASS_HEAD
                + f"Dialogue: 0,0:00:00.00,0:00:05.00,HEADA,,0,0,0,,{a}\n"
                + f"Dialogue: 0,0:00:00.00,0:00:05.00,HEADB,,0,0,0,,{b}\n",
                tmp_path, clip.CANVAS_W, clip.CANVAS_H)
    _check_line(_ink(arr[:clip._HEAD_B_TOP - 8]), clip.CANVAS_W, want_tall=True)


def test_赛场之上顶栏是透视球场而且和文字一起居中(tmp_path):
    import build_match_reel as reel

    spec = json.loads((ROOT / "specs/reels/chwalinska-mertens-singapore-2026-qf.json")
                      .read_text(encoding="utf-8"))
    path = reel.write_topbar_ass(reel._topbar_lines(spec), 0, 5, tmp_path / "top.ass")
    text = path.read_text(encoding="utf-8")
    assert r"{\r\p0}" in text, "图标后面要复位，不然赛事行跟着变绿"
    arr = _burn(text, tmp_path, reel.VIDEO_W, reel.VIDEO_H)
    band = arr[:reel.TOPBAR_BODY_TOP - 4]
    _check_line(_ink(band), reel.VIDEO_W, want_tall=False)
    # 赛事行本身不许被染绿（复位漏了的样子）：白墨那一块里不许混进绿墨
    tx0 = _ink(band)["text"][0]
    green = (band[:, tx0:, 1] > 120) & (band[:, tx0:, 1] - band[:, tx0:, 0] > 60)
    assert not green.any(), "赛事行被染成绿色了——图标后面那个 {\\r} 没生效"


def test_图标的步进就是矢量里最远的那个点():
    """量顶栏宽度用 `icon_advance`，libass 排版用矢量本身——两处要是同一个数。"""
    for name, h in ((MIC, 42), (COURT, 38)):
        nums = [float(tok) for tok in drawing(name, h).split() if tok not in ("m", "l")]
        xs = nums[0::2]                     # 只有 m / l，数字严格是 x y 交替
        assert max(xs) == pytest.approx(icon_advance(name, h), abs=0.2)
        assert max(xs) > h * ASPECT[name], "步进里要带着和文字之间的空隙"
