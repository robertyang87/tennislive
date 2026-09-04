"""抽帧工具的判据：**帧的名字必须是片子里的绝对秒数。**

这个工具的产物是给人挑 `cover.frame_at` 用的，挑完直接照抄文件名里那个数——
所以名字错多少，封面就偏多少，而封面闸只会说一句「没检出正面人脸」，
不会说「你渲的是另一个镜头」。

2026-09-04 挑孟菲尔斯告别仪式封面时就是这么丢掉一趟的：我拿缩略图墙的格号
乘了 4.9，而真步长是 storyboard 自报的 1/fps = 4.8947，39 格下来偏 0.2 秒，
正好跨过一个镜头切点。截段抽帧引进来的 `--start` 让同一个错有了新的入口
（「第几张」不再等于「第几秒」），所以这里把它钉死。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import grab_frames as G  # noqa: E402


def _clip(dest: Path, seconds: int = 30) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi",
         "-i", f"testsrc2=size=320x180:rate=25", "-t", str(seconds),
         "-pix_fmt", "yuv420p", str(dest)], check=True)
    return dest


needs_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg"), reason="没装 ffmpeg")


def test_帧的名字是绝对秒数不是第几张(tmp_path):
    """截一段之后，第 0 张也要叫它在**整条片子**里的那个秒数。"""
    assert G.frame_stamp(0) == "frame_0000s.jpg"
    assert G.frame_stamp(122) == "frame_0122s.jpg"
    # 带小数的步长不能被 int() 抹平成同一个名字，否则两张帧会互相覆盖
    assert G.frame_stamp(122.5) != G.frame_stamp(122.0)


@needs_ffmpeg
def test_截一段抽出来的帧和整条抽的同一秒逐像素相同(tmp_path):
    """`-ss` 放对了位置才成立——放错就是整体偏移，而偏移不报错。"""
    from PIL import Image
    import numpy as np

    src = _clip(tmp_path / "src.mp4")
    whole = tmp_path / "whole"
    whole.mkdir()
    G.sample(src, whole, every=5, width=160)
    part = tmp_path / "part"
    part.mkdir()
    got = G.sample(src, part, every=5, width=160, start=10, end=25)

    assert [p.name for p in got] == [
        "frame_0010s.jpg", "frame_0015s.jpg", "frame_0020s.jpg"], \
        f"截段之后名字不是绝对秒数：{[p.name for p in got]}"
    for t in (10, 15, 20):
        a = np.asarray(Image.open(whole / f"frame_{t:04d}s.jpg").convert("RGB"),
                       dtype=float)
        b = np.asarray(Image.open(part / f"frame_{t:04d}s.jpg").convert("RGB"),
                       dtype=float)
        assert float(np.abs(a - b).mean()) == 0.0, f"第 {t} 秒那一帧对不上"


@needs_ffmpeg
def test_不给范围时抽帧行为一个字节都不变(tmp_path):
    """既有调用方（工作流不填 start/end）必须拿到和以前一样的产物。"""
    src = _clip(tmp_path / "src.mp4", seconds=20)
    out = tmp_path / "o"
    out.mkdir()
    got = G.sample(src, out, every=5, width=160)
    assert [p.name for p in got] == [
        "frame_0000s.jpg", "frame_0005s.jpg",
        "frame_0010s.jpg", "frame_0015s.jpg"]


def test_范围写反了要当场报错(tmp_path):
    src = tmp_path / "nope.mp4"
    src.write_bytes(b"")
    with pytest.raises(SystemExit) as exc:
        G.sample(src, tmp_path, every=5, width=160, start=20, end=10)
    assert "要大于" in str(exc.value)


def test_工作流把范围传下去了而且空值不传空串():
    """能力写出来了，能用的那台机器上也得有开关。

    ⚠️ 空串必须整个不给这个开关，不能给 `--start ""`——argparse 会吃到一个
    空参数然后报一句看不出病因的错。
    """
    body = Path(".github/workflows/frame-grab.yml").read_text(encoding="utf-8")
    assert "start:" in body and "end:" in body, "表单里没有这两个输入"
    assert "--start" in body and "--end" in body, "没把范围传给工具"
    assert '[ -n "$GRAB_START" ]' in body, "空值没有被挡住"
    assert '[ -n "$GRAB_END" ]' in body, "空值没有被挡住"
