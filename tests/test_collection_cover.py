"""`tools/render_collection_cover.py` 的判据。

这张封面的每条规矩都是渲出来比出来的，所以测的也是那几条：缩到主页图块还
认不认得出、球是不是完整的圆、几个栏目摆在一起像不像一套。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
_FONT = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")

pytestmark = pytest.mark.skipif(
    not _FONT.exists(), reason="没装 fonts-noto-cjk，量出来的宽度和 CI 对不上")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cover = _load("render_collection_cover")


def test_栏目从注册表读而不是另抄一份():
    """新登记一个栏目就该自动有封面，撤掉一个也不该留下孤儿文件。"""
    from tennislive.video.explainer import COLUMNS
    assert cover.COLUMNS is COLUMNS
    assert "网球有故事" in cover.COLUMNS


def test_缩到主页图块还认得出球():
    """判据是 220px 的图块，不是全尺寸好不好看。

    试过让球左右出血放到最大，全尺寸很有气势，缩小后就是「一块绿方块加两根
    指针」——圆形轮廓才是这个品牌被认出来的地方。
    """
    from PIL import Image
    for name in cover.COLUMNS:
        thumb = cover.render(name, 1080).resize((cover.THUMB, cover.THUMB),
                                                 Image.LANCZOS)
        assert cover.contrast_ok(thumb), f"{name} 在 {cover.THUMB}px 上球和底分不开"


def test_底色调亮到分不出球时自检要不通过():
    """反向验证：这条检查真的看过图，不是永远返回 True。"""
    from PIL import Image
    flat = Image.new("RGB", (cover.THUMB, cover.THUMB), cover.FIELD)
    assert not cover.contrast_ok(flat)


def test_三四比例里球仍是正圆():
    """3:4 是按高度重排的，不是把 1:1 拉伸——拉伸会把球压成椭圆。"""
    square = cover.render("网球有故事", 1080, 1080)
    tall = cover.render("网球有故事", 1080, 1440)
    assert square.size == (1080, 1080) and tall.size == (1080, 1440)
    # 球径只跟宽度走，和画面高度无关
    assert _ball_span(square) == pytest.approx(_ball_span(tall), abs=4)


def _ball_span(img) -> int:
    """量出球在水平中线上的像素跨度。"""
    row = img.convert("RGB").crop((0, _ball_cy(img), img.width, _ball_cy(img) + 1))
    xs = [x for x in range(img.width)
          if _close(row.getpixel((x, 0)), cover.BALL, 40)]
    return (max(xs) - min(xs)) if xs else 0


def _ball_cy(img) -> int:
    """球心的 y —— 按构图算：整块居中、略微偏上。"""
    from PIL import ImageFont
    font = ImageFont.truetype(cover.CJK_BOLD, int(img.width * 0.185))
    ball_d = img.width * cover.BALL_WIDTH
    box = font.getbbox("网球有故事")
    block = ball_d + img.width * 0.105 + (box[3] - box[1])
    return int((img.height - block) / 2 * 0.88 + ball_d / 2)


def _close(px, want, tol) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px, want))


def test_全套共用一个字号而不是各自撑满():
    """走过的弯路：让每个名字各自撑满同样宽度，「开球之前」被放到 199、
    「网球有故事」收到 184，短名字显得虚胖，摆在一起反而不像一套。

    一套封面该是字号一致，短名字就是短一点。
    """
    font = cover.title_font(1080)
    # 同一个字号服务所有栏目，而且最长的那个不许超边
    longest = max(cover.COLUMNS, key=len)
    box = font.getbbox(longest)
    assert box[2] - box[0] <= 1080 * cover.TITLE_MAX_WIDTH
    # 短名字画出来就是窄的，不该被撑开
    short = min(cover.COLUMNS, key=len)
    if len(short) < len(longest):
        sb = font.getbbox(short)
        assert sb[2] - sb[0] < box[2] - box[0]


def test_来一个更长的栏目名时全套一起变小(monkeypatch):
    """字号由最长的那个决定，不是某个名字自己被压扁。"""
    base = cover.title_font(1080).size
    monkeypatch.setattr(cover, "COLUMNS", {**cover.COLUMNS, "很长很长的栏目名字": None})
    assert cover.title_font(1080).size < base


def test_没登记的栏目要报错并列出有哪些(capsys):
    import subprocess
    r = subprocess.run(
        [sys.executable, str(_TOOLS / "render_collection_cover.py"),
         "--only", "查无此栏目", "--check"],
        capture_output=True, text=True)
    assert r.returncode != 0
    assert "没登记的栏目" in r.stderr
    assert "网球有故事" in r.stderr        # 要说清已登记的是哪些
