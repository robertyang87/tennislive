"""转场动画库（`tennislive.video.transitions`）：名字认得出、接缝不闪、长度账不动。

账号所有者 2026-10-27：「多准备一些转场动画作为过渡效果，后续做视频需要的时候
直接套用」。用法和每个预设的用途见 `docs/transition-presets.md`。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel  # noqa: E402
import reel_join_fusion as fusion  # noqa: E402
from tennislive.video import transitions  # noqa: E402

W, H, FPS = 96, 128, 60


def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


@pytest.fixture(scope="module")
def two_shots(tmp_path_factory):
    """两路有纹理、亮度不同的画面，各 1.5 秒。"""
    d = tmp_path_factory.mktemp("shots")
    out = []
    for name, src in (("a", "testsrc2"), ("b", "smptehdbars")):
        p = d / f"{name}.mp4"
        ff("-f", "lavfi", "-i", f"{src}=size={W}x{H}:rate={FPS}:duration=1.5",
           "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12", "-pix_fmt", "yuv420p", p)
        out.append(p)
    return out


def _seam_frames(shots, xfade: str) -> np.ndarray:
    a, b = shots
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(a), "-i", str(b), "-filter_complex",
         f"[0:v][1:v]xfade=transition={xfade}:duration={reel.SEG_FADE}:offset=1.0,"
         "trim=start=0.95:end=1.25,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(float)


def _flashes(frames: np.ndarray) -> bool:
    """接缝中段比两头暗一截，或者整幅糊成一块纯色——都算闪。"""
    mean, std = frames.mean((1, 2)), frames.std((1, 2))
    ends_mean = min(mean[0], mean[-1])
    ends_std = min(std[0], std[-1])
    return bool(mean.min() < 0.6 * ends_mean or std.min() < 0.4 * ends_std)


@pytest.mark.parametrize("name", sorted(transitions.PRESETS))
def test_每个转场中间都不闪黑不闪成一块纯色(two_shots, name):
    frames = _seam_frames(two_shots, transitions.xfade_transition(name))
    assert not _flashes(frames), f"{name} 在接缝中段闪了一下——不许进动画库"


@pytest.mark.parametrize("xfade", ["fadeblack", "fadewhite", "zoomin"])
def test_判据自己拦得住淡到黑和放成纯色的那几种(two_shots, xfade):
    """反向：不收的那几个，同一把尺子必须量得出来。"""
    assert _flashes(_seam_frames(two_shots, xfade)), xfade


def test_默认是溶解_写错名字当场报并列出能用的():
    assert transitions.validate(None) == "dissolve"
    assert reel._seg_transition({}, 0) == "dissolve"
    assert reel._seg_transition({"transition": "iris"}, 3) == "iris"
    with pytest.raises(reel.ReelError, match="第 2 段.*zoom.*slide_left"):
        reel._seg_transition({"transition": "zoom"}, 1)


def test_拼接图按段换动画_时长和offset一个数不变():
    lengths = [1.2, 2.0, 1.5, 3.0]
    plain = reel.dissolve_filtergraph(lengths, reel.SEG_FADE)
    mixed = reel.dissolve_filtergraph(lengths, reel.SEG_FADE,
                                      transitions=["dissolve", "whip", "memory"])
    assert "transition=hblur" in mixed and "transition=fadegrays" in mixed
    assert mixed.replace("hblur", "fade").replace("fadegrays", "fade") == plain
    with pytest.raises(ValueError):
        reel.dissolve_filtergraph(lengths, reel.SEG_FADE, transitions=["whip"])


def test_换了动画的拼接图照样走2x2时钟那条快路(tmp_path):
    lengths = [1.0, .8, .9]
    names = ["slide_left", "iris"]
    graph = reel.dissolve_filtergraph(lengths, reel.SEG_FADE, transitions=names)
    plan, reason = fusion.plan(graph, len(lengths))
    assert plan and not reason, reason
    parts = []
    for i, length in enumerate(lengths):
        dur = length + (reel.SEG_FADE if i < len(lengths) - 1 else 0)
        p = tmp_path / f"p{i}.mp4"
        ff("-f", "lavfi", "-i", f"testsrc2=size={W}x{H}:rate=25:duration={dur}",
           "-f", "lavfi", "-i", f"sine=frequency={300 + 100 * i}:sample_rate=48000:duration={dur}",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", p)
        parts.append(p)
    inputs = [a for p in parts for a in ("-i", str(p))]
    joined, clock = tmp_path / "joined.mp4", tmp_path / "clock.mp4"
    for path, g in ((joined, graph), (clock, plan.clock_graph())):
        ff(*inputs, "-filter_complex", g, "-map", "[vout]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-ar", "48000", path)
    assert reel.probe_duration(joined) == pytest.approx(sum(lengths), abs=0.05)
    assert fusion.video_clock(joined) == fusion.video_clock(clock)
