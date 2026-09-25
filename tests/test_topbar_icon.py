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


def test_全局_每一条顶栏都带着自己栏目的图标():
    """账号所有者 2026-09-25：「推广到全局使用」。

    扫仓库里**每一条**正式 spec，不是挑一条看：
    - 赛场之上：凡是有 `topbar` 的，第一行都是透视球场 ＋ 赛事行，而且装得下
    - 赛后开麦：凡是走两行版式的（场上采访、发布会、颁奖、告别……），第一段
      都是麦克风，而且整行装得下（麦克风占了宽度，顶栏宽度闸要把它算进去）

    ⚠️ **唯一不带图标的是 `subject_primary`（人物主标题那一种，名人堂致辞 /
    赛前出场秀）**：那一行是**故意只留一段**的——两次正式 runner artifact
    证明「装饰段 ＋ 中途 `\\r` ＋ 正文段」在生产上是 0 像素（见 `header_runs`
    那段注释），这个变量还没隔离出来之前，不往那一行里加第二段。表自己钉着，
    多出第三种没图标的版式就当场红。
    """
    import build_interview_clip as clip
    import build_match_reel as reel
    from PIL import ImageFont

    icon_less = []
    n_interview = 0
    for f in sorted((ROOT / "specs/interviews").glob("*.json")):
        if f.name.endswith(".draft.json"):
            continue
        spec = json.loads(f.read_text(encoding="utf-8"))
        try:
            clip.header_lines(spec)          # 宽度闸：含麦克风那一截
            runs = clip.header_runs(spec)[0]
        except SystemExit as exc:
            if "缺 `interview_kind`" in str(exc):
                continue                      # 老片子缺字段，和图标无关
            raise
        n_interview += 1
        if runs[0][1] != "icon":
            icon_less.append(clip.topbar_layout(spec))
        else:
            assert runs[0][0] == MIC, f"{f.name} 顶栏图标不是麦克风"
    assert n_interview >= 90, f"只扫到 {n_interview} 条采访 spec，扫描写空了？"
    assert set(icon_less) <= {"subject_primary"}, (
        f"这几种版式的顶栏没有麦克风：{sorted(set(icon_less))}")

    head = ImageFont.truetype(str(ROOT / "assets/fonts/SmileySans-Oblique.ttf"),
                              reel.TOPBAR_HEAD_SIZE)
    avail = reel.VIDEO_W - 2 * reel.TOPBAR_MARGIN_H
    n_reel = 0
    for f in sorted((ROOT / "specs/reels").glob("*.json")):
        spec = json.loads(f.read_text(encoding="utf-8"))
        if not spec.get("topbar"):
            continue
        n_reel += 1
        line1 = spec["topbar"]["line1"]
        head_text = reel.topbar_head_with_icon(line1)
        assert head_text.endswith(line1) and r"\p1" in head_text, f"{f.name} 顶栏没有球场"
        # 得意黑 HEAD 带 1px 字距；加上球场那一截的步进，整行要装得下
        w = (head.getlength(line1) + len(line1) * 1
             + icon_advance(COURT, reel.TOPBAR_ICON_H))
        assert w <= avail, f"{f.name} 顶栏第一行 {w:.0f}px 超过 {avail}px"
    assert n_reel >= 200, f"只扫到 {n_reel} 条带顶栏的赛场之上 spec，扫描写空了？"
