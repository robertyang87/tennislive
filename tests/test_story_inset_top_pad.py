"""Per-label placement must preserve the default and the native hold clock."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel
from render_inputs import diff_paths, project
from render_story_info_band import render_label


def _inset(image, **extra):
    return {"image": str(image), "kind": "story_text", "corner": "tr",
            "width": .6, "pad": .043, "motion": "editorial", "animate": False,
            "show_after": 0, "show_for": 15,
            "label": {"topic": "决赛回顾", "date": "2026.06.06", "place": "法网决赛",
                      "people": "安德烈耶娃 vs 赫瓦林斯卡", "score": "6-3 6-2"}, **extra}


def _spec(inset):
    return {"cover": {"eyebrow": "网球有故事"}, "segments": [
        {"source": "main", "start": 0, "end": 15.12, "inset": inset}]}


@pytest.mark.parametrize("extra", [
    {"top_pad": v} for v in (True, None, "0.043", -.01, .042, .151,
                             float("nan"), float("inf"))
] + [{"top_pad": .043, "kind": "metric"},
     {"top_pad": .043, "corner": "tl"}])
def test_top_pad_rejects_invalid_values_and_other_label_kinds(tmp_path, extra):
    image = tmp_path / "label.png"
    Image.new("RGBA", (20, 20), "green").save(image)
    inset = _inset(image, **extra)
    if inset["kind"] != "story_text":
        inset.pop("show_after")  # Exercise this field, not the independent delay gate.
    with pytest.raises(reel.ReelError, match="top_pad"):
        reel.parse_segments(_spec(inset), {"main": Path("source.mp4")}, "main")
    with pytest.raises(reel.ReelError, match="top_pad"):
        reel._overlay_chain("[0:v]null[base]", inset)


def _pixel(film, time, xy):
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-ss", str(time), "-threads", "1", "-i", str(film),
        "-frames:v", "1", "-threads", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    return Image.frombytes("RGB", (1080, 1440), raw).getpixel(xy)


def test_native_explicit_top_is_visible_immediately_holds_and_clears_at_15(tmp_path, monkeypatch):
    source, image = tmp_path / "source.mp4", tmp_path / "label.png"
    Image.new("RGBA", (20, 20), (0, 255, 0, 255)).save(image)
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "color=black:size=1920x1080:rate=25:duration=15.3", "-c:v", "libx264",
        "-threads", "2", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(source)],
        check=True)
    for key, value in {"CROP_W": 810, "CROP_H": 1080, "CROP_Y": 0,
                       "LAYOUT": "full", "_INSET_TOP_CLEAR_Y": 151,
                       "FPS": 25, "FPS_EXPR": "25/1", "PART_PRESET": "ultrafast"}.items():
        monkeypatch.setattr(reel, key, value)
    default = tmp_path / "default.mp4"
    reel.cut_segment(source, reel.Segment(0, .2, .5, "", inset=_inset(image)),
                     default, 1920, threads=2)
    assert _pixel(default, 0, (450, 60))[1] < 30
    assert _pixel(default, 0, (450, 170))[1] > 180
    explicit = tmp_path / "explicit.mp4"
    ins = _inset(image, top_pad=.043)
    # Validate a genuine typography asset; the solid marker below isolates
    # the placement and hold clock in actual decoded native pixels.
    real_image = tmp_path / "real-label.png"
    real_inset = _inset(real_image, top_pad=.043)
    render_label(real_inset["label"], real_image)
    assert reel.parse_segments(_spec(real_inset), {"main": source}, "main")
    reel.cut_segment(source, reel.Segment(0, 15.12, .5, "", inset=ins),
                     explicit, 1920, threads=2)
    for at, visible in ((0, True), (.04, True), (14.92, True), (15.04, False)):
        red, green, blue = _pixel(explicit, at, (450, 60))
        assert (green > 180 and red < 60 and blue < 60) == visible
    assert 15.08 <= reel.probe_duration(explicit) <= 15.2


def test_top_pad_is_part_of_native_render_projection():
    before = _spec(_inset("label.png"))
    after = deepcopy(before)
    after["segments"][0]["inset"]["top_pad"] = .043
    assert diff_paths(project(before), project(after)) == [["segments", 0, "inset", "top_pad"]]
