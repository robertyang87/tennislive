"""Delay only the story label; its animation and lifetime stay clip-relative."""
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel
from render_story_info_band import render as render_band


def _inset(image="test.png", **changes):
    result = {"image": str(image), "kind": "story_text", "corner": "tr",
              "width": .6, "pad": .043, "motion": "editorial", "show_for": 15.,
              "label": {"topic": "决赛回顾", "date": "2026.04.19", "place": "斯图加特决赛",
                        "people": "穆霍娃 vs 莱巴金娜", "score": "5-7 1-6"}}
    result.update(changes)
    return result


def _parse(image, **changes):
    spec = {"cover": {"eyebrow": "网球有故事"}, "segments": [
        {"source": "main", "start": 0, "end": 10.4, "inset": _inset(image, **changes)}]}
    return reel.parse_segments(spec, {"main": Path("main.mp4")}, "main")


def test_delayed_story_label_shifts_every_animation_clock_and_keeps_default_identical(tmp_path):
    image = tmp_path / "label.png"
    render_band("2026.04.19", "决赛回顾", "穆霍娃 vs 莱巴金娜", image,
                metric="5-7 1-6", highlight="斯图加特决赛")
    base = "[0:v]null[base]"
    plain = reel._overlay_chain(base, _inset(image))
    assert reel._overlay_chain(base, _inset(image, show_after=0)) == plain
    delayed = reel._overlay_chain(base, _inset(image, show_after=18.2))
    assert "enable='gte(t,18.200)*lt(t,26.200)'" in delayed
    assert "fade=t=in:st=18.200:d=0.28" in delayed
    assert "fade=t=out:st=25.850:d=0.350" in delayed
    assert "if(lt(t,18.480)" in delayed and "(t-18.200)/0.28" in delayed
    assert reel._overlay_chain(base, _inset(image, show_after=18.2, carry="start")) == delayed
    assert "26.200" in reel._overlay_chain(base, _inset(image, show_after=18.2, show_for=20))
    assert _parse(image, show_after=18.2, show_for=15.)
    with pytest.raises(reel.ReelError, match="story_text"):
        _parse(image, show_after=4.5, show_for=15.01)


@pytest.mark.parametrize("delay", [-.01, float("nan"), float("inf"), True, "4.5", None])
def test_story_label_delay_requires_finite_nonnegative_seconds(tmp_path, delay):
    image = tmp_path / "label.png"
    Image.new("RGBA", (20, 20), "green").save(image)
    with pytest.raises(reel.ReelError, match="show_after"):
        _parse(image, show_after=delay)
    with pytest.raises(reel.ReelError, match="show_after"):
        reel._overlay_chain("[0:v]null[base]", _inset(image, show_after=delay))


@pytest.mark.parametrize("animate", [True, False])
def test_delayed_label_is_absent_before_start_and_ends_with_short_clip(tmp_path, monkeypatch, animate):
    source, image, dest = (tmp_path / name for name in ("source.mp4", "label.png", "part.mp4"))
    Image.new("RGBA", (20, 20), (0, 255, 0, 255)).save(image)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=black:size=1920x1080:rate=25:duration=3.8", "-c:v", "libx264",
                    "-threads", "2", "-preset", "ultrafast", str(source)], check=True)
    monkeypatch.setattr(reel, "CROP_W", 810)
    monkeypatch.setattr(reel, "CROP_H", 1080)
    monkeypatch.setattr(reel, "CROP_Y", 0)
    monkeypatch.setattr(reel, "LAYOUT", "full")
    monkeypatch.setattr(reel, "_INSET_TOP_CLEAR_Y", 0)
    monkeypatch.setattr(reel, "PART_PRESET", "ultrafast")
    # Delay is longer than the hold: all entrance/fade clocks must still start at 2.9.
    inset = _inset(image, show_after=2.9, show_for=2.8, animate=animate, carry="start")
    seg = reel.Segment(0, 3.7, .5, "", inset=inset)
    reel.cut_segment(source, seg, dest, 1920, threads=2)
    assert 3.6 <= reel.probe_duration(dest) < 3.85, "show_after/show_for不得把视频延长或跨段续挂"
    for seconds, visible in ((2.7, False), (3.55, True)):
        frame = tmp_path / f"{seconds}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(seconds), "-i", str(dest),
                        "-frames:v", "1", str(frame)], check=True)
        with Image.open(frame) as canvas:
            r, g, b = canvas.convert("RGB").getpixel((450, 120))
            assert (g > 180 and r < 70 and b < 70) == visible
