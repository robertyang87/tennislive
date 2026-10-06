"""Opt-in story photographs reuse the native centred outro push, never cards."""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw, ImageStat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel


def test_motion_selects_only_marked_photos_even_when_card_shares_path():
    spec = {
        "cover": {"eyebrow": "网球有故事"},
        "segments": [
            {"image": "shared.png", "image_kind": "photo"},
            {"image": "shared.png", "image_kind": "evidence"},
            {"image": "generated.jpg", "title_card": "章节", "image_kind": "photo"},
        ],
    }
    assert reel.story_photo_push_indices(spec) == frozenset()
    spec["story_photo_motion"] = "push"
    assert reel.story_photo_push_indices(spec) == frozenset({0})
    spec["story_photo_motion"] = "pan"
    with pytest.raises(reel.ReelError, match="只认 push"):
        reel.story_photo_push_indices(spec)
    spec["story_photo_motion"] = "push"
    spec["cover"]["eyebrow"] = "赛场之上"
    with pytest.raises(reel.ReelError, match="只用于网球有故事"):
        reel.story_photo_push_indices(spec)
    spec["cover"]["eyebrow"] = "网球有故事"
    spec["layout"] = "band"
    with pytest.raises(reel.ReelError, match="不支持band"):
        reel.story_photo_push_indices(spec)


def _frame(path: Path, number: int) -> Image.Image:
    decoded = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf",
         f"select=eq(n\\,{number})", "-frames:v", "1", "-f", "image2pipe",
         "-vcodec", "png", "-threads", "1", "pipe:1"],
        check=True, capture_output=True,
    ).stdout
    return Image.open(io.BytesIO(decoded)).convert("RGB")


def _marker_box(frame: Image.Image) -> tuple[int, int, int, int]:
    r, g, b = frame.split()
    mask = ImageChops.darker(ImageChops.darker(r, g), b).point(
        lambda value: 255 if value > 180 else 0)
    box = mask.getbbox()
    assert box is not None
    return box


def test_real_native_photo_push_changes_scale_with_fixed_center_and_no_borders(
        monkeypatch, tmp_path):
    # A true1080×1440 encode through the production still cutter and unmodified
    # 4× supersampled native push filter. Short duration keeps the test bounded.
    monkeypatch.setattr(reel, "LAYOUT", "full")
    monkeypatch.setattr(reel, "FPS", 25)
    monkeypatch.setattr(reel, "FPS_EXPR", "25")
    image = tmp_path / "photo.png"
    fixture = Image.new("RGB", (1080, 1440), (24, 42, 70))
    ImageDraw.Draw(fixture).rectangle((300, 420, 780, 1020), fill=(235, 225, 210))
    fixture.save(image)
    raw = {"image": str(image), "image_kind": "photo", "seconds": .64,
           "narration": "照片小样", "_photo_source": "https://example.org/fixture",
           "_photo_caption_safety": "Synthetic marker above bottom caption zone."}
    segment = reel.parse_segments({"segments": [raw]}, {"main": "url"}, "main")[0]
    push = tmp_path / "push.mp4"
    static = tmp_path / "static.mp4"
    reel.cut_still_segment(segment, push, threads=1, photo_push=True)
    reel.cut_still_segment(segment, static, threads=1)
    assert reel.probe_size(push) == reel.probe_size(static) == (1080, 1440)
    assert abs(reel.probe_duration(push) - .64) < .05
    assert reel._has_audio(push)  # Native silent placeholder remains available.
    first, last = _frame(push, 0), _frame(push, 15)
    a, b = _marker_box(first), _marker_box(last)
    initial_size = (a[2] - a[0], a[3] - a[1])
    final_size = (b[2] - b[0], b[3] - b[1])
    scale = [end / start for start, end in zip(initial_size, final_size)]
    assert all(1.02 < factor < 1.04 for factor in scale), scale
    assert abs(scale[0] - scale[1]) < .004  # The image shape stays proportional.
    assert max(abs((a[i] + a[i + 2] - b[i] - b[i + 2]) / 2)
               for i in (0, 1)) <= 1
    for frame in (first, last):
        w, h = frame.size
        for box in ((0, 0, w, 1), (0, h - 1, w, h), (0, 0, 1, h), (w - 1, 0, w, h)):
            assert min(lo for lo, _hi in frame.crop(box).getextrema()) > 10
    static_first, static_last = _frame(static, 0), _frame(static, 15)
    assert _marker_box(static_first) == _marker_box(static_last)
    assert sum(ImageStat.Stat(ImageChops.difference(static_first, static_last)).mean) / 3 < .1
