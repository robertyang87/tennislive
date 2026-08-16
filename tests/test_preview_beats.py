"""开球之前纯视频管线（`tools/preview_beats.py`）的判据。

这条线目前只有两个真正新写的部件：`cut_footage_beat`（裁切+居中+角标合成）
和 `_render_stat_overlay`（角标本身）。其余（`dissolve_filtergraph` /
`duck_filtergraph` / `_still_to_clip`）是从 `build_match_reel.py` 原样导入
的，那边已经有自己的判据，这里不重复测。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("tools").resolve()))
sys.path.insert(0, str(Path("src").resolve()))


def _has_ffmpeg() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _run(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True)


def test_footage_beat按cx把源片的指定位置钉到画面中心(tmp_path):
    """和 explainer.py 的 `intro_cx` 同一条公式，这里换成 `cut_footage_beat`
    的入口验一遍。造一段源片：蓝底 + 一条洋红竖条，竖条中心精确落在源片
    1280 宽的 30%（x=384）处。给 `cx=0.3`，裁完这条竖条应该正好落在输出
    画面中心。
    """
    if not _has_ffmpeg():
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    import preview_beats as R  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    source = tmp_path / "source.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=25",
          "-f", "lavfi", "-i", "color=c=magenta:s=20x720:r=25",
          "-filter_complex", "[0:v][1:v]overlay=374:0[v]",
          "-map", "[v]", "-t", "2.0", "-c:v", "libx264",
          "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(source)])

    out = R.cut_footage_beat(
        source, 0.0, 1.0, 0.3, tmp_path / "beat.mp4",
        canvas_w=R.VIDEO_W, canvas_h=R.VIDEO_H,
    )

    frame = tmp_path / "frame.png"
    _run(["ffmpeg", "-v", "error", "-y", "-ss", "0.3", "-i", str(out),
          "-frames:v", "1", str(frame)])
    im = Image.open(frame).convert("RGB")
    row = im.size[1] // 2
    xs = [x for x in range(im.size[0])
          if (im.getpixel((x, row))[0] > 150
              and im.getpixel((x, row))[2] > 150
              and im.getpixel((x, row))[1] < 100)]
    assert xs, "洋红竖条在这一帧里一个像素都没找到"
    bar_x = sum(xs) / len(xs)
    assert abs(bar_x - R.VIDEO_W / 2) < 20, (
        f"cx=0.3 应该把 30% 处的竖条钉到输出中心 {R.VIDEO_W / 2}，实测在 {bar_x:.1f}"
    )


def test_角标要撑满整段不提前消失(tmp_path):
    """真实素材验证过（8 秒主片段，0.2/4.0/7.8 秒角标都在，见
    `preview_beats.cut_footage_beat` 的 docstring），这里把它锁进
    自动判据：静态图当输入不给 `-loop 1`，配合 `overlay` 默认的
    `eof_action=repeat`，角标应该一直撑到主片段结束，不会像
    `_render_intro_badge` 当年那样被 60 秒的 `-t` 拖长或提前消失。
    """
    if not _has_ffmpeg():
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    import preview_beats as R  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    source = tmp_path / "source.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=25:d=6",
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          str(source)])

    overlay = tmp_path / "overlay.png"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
          "-i", f"color=c=red@0.9:s={R.VIDEO_W}x{R._OVERLAY_BAR_H}",
          "-frames:v", "1", str(overlay)])

    out = R.cut_footage_beat(
        source, 0.0, 6.0, 0.5, tmp_path / "beat.mp4", overlay=overlay,
    )

    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True).stdout.strip())
    assert abs(dur - 6.0) < 0.2, f"beat 应该是 6.0s，实测 {dur:.2f}s"

    for t in (0.3, 3.0, 5.7):
        frame = tmp_path / f"chk_{t}.png"
        _run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(out),
              "-frames:v", "1", str(frame)])
        im = Image.open(frame).convert("RGB")
        px = im.getpixel((im.size[0] // 2, im.size[1] - 40))
        assert px[0] > 150 and px[1] < 100, (
            f"t={t}s 角标不见了（{px}）——是不是又踩了「静态图当输入提前 EOF」"
        )


def test_角标要撑满整段_反向验证(tmp_path):
    """上面那条测试如果对合成数据本身有偏，这条把 `overlay` 拆掉，确认
    没给角标的 beat 里**没有**红色像素——排除"随便什么像素都偏红"的假阳性。
    """
    if not _has_ffmpeg():
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    import preview_beats as R  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    source = tmp_path / "source.mp4"
    _run(["ffmpeg", "-v", "error", "-y",
          "-f", "lavfi", "-i", "color=c=blue:s=1280x720:r=25:d=3",
          "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
          str(source)])

    out = R.cut_footage_beat(source, 0.0, 3.0, 0.5, tmp_path / "beat.mp4")
    frame = tmp_path / "chk.png"
    _run(["ffmpeg", "-v", "error", "-y", "-ss", "1.5", "-i", str(out),
          "-frames:v", "1", str(frame)])
    im = Image.open(frame).convert("RGB")
    px = im.getpixel((im.size[0] // 2, im.size[1] - 40))
    assert not (px[0] > 150 and px[1] < 100), (
        f"没给 overlay，这一段却出现了红色角标像素 {px}——两次调用互相污染了？"
    )


def test_player_card角标要渲出真实的国旗名字排名(tmp_path):
    if not shutil.which("ffmpeg"):
        raise AssertionError("没有 ffmpeg，这条判据跑不了")

    import preview_beats as R  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    png = R._render_stat_overlay(
        "player_card",
        {"name": "伊埃拉", "country": "PHI", "rank": 28},
        tmp_path,
    )
    assert png is not None and png.is_file(), "Chromium 装着的话角标必须渲得出来"
    im = Image.open(png)
    assert im.mode == "RGBA", "角标必须是带透明通道的 PNG"
    assert im.size == (R.VIDEO_W, R._OVERLAY_BAR_H)
    alpha = im.split()[-1]
    assert alpha.getextrema()[1] > 0, "整张图全透明——名条没画上去"


def test_player_card缺国旗或排名要报错不许悄悄渲空(tmp_path):
    import preview_beats as R  # noqa: PLC0415

    with pytest.raises(SystemExit):
        R._render_stat_overlay(
            "player_card", {"name": "麦克纳莉", "rank": 60}, tmp_path,
        )
    with pytest.raises(SystemExit):
        R._render_stat_overlay(
            "player_card", {"name": "麦克纳莉", "country": "USA"}, tmp_path,
        )


def test_不支持的角标类型要报错不能悄悄渲空(tmp_path):
    import preview_beats as R  # noqa: PLC0415

    with pytest.raises(ValueError):
        R._render_stat_overlay(
            "h2h_bar", {"a": 2, "b": 1}, tmp_path,
        )


def test_poster_beat产出的时长要包含tail(tmp_path):
    if not _has_ffmpeg():
        raise AssertionError("没有 ffmpeg/ffprobe，这条判据跑不了：apt install ffmpeg")

    import preview_beats as R  # noqa: PLC0415

    poster = tmp_path / "poster.jpg"
    _run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
          f"color=c=green:s={R.VIDEO_W}x{R.VIDEO_H}", "-frames:v", "1",
          str(poster)])

    out = R.poster_beat(poster, tmp_path / "cover_beat.mp4", 2.0, tail=0.3)
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(out)],
        check=True, capture_output=True, text=True).stdout.strip())
    assert abs(dur - 2.3) < 0.1, f"应该是 2.0+0.3=2.3s，实测 {dur:.2f}s"
