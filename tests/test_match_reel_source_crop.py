"""Explicit native source geometry must fill the canvas without disguising 720p."""
import copy
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel
import probe_sources


BAD_URL = "https://players.brightcove.net/6041795521001/te01Hqw71_default/index.html?videoId=6399578560112"


def _spec(key="portrait", floor=1080):
    return {"slug": "muchova-finals-2026",
            "sources": {"main": "https://example.com/main", key: BAD_URL if floor == 720 else "https://example.com/portrait"},
            "source_crop": {key: {"reason": "本集明确要求真实源裁切铺满", "fill_y": .5,
                                  "min_height": floor, "approved_by": "user"}},
            "segments": [{"source": key, "start": 0, "end": .2, "cx": .5, "fit": "crop"}]}


def test_portrait_source_has_its_own_crop_geometry_and_native_floor():
    spec = _spec()
    paths = {key: Path(key + ".mp4") for key in spec["sources"]}
    dims = {"main": (1920, 1080, "25/1", 25.), "portrait": (1080, 1920, "25/1", 25.)}
    reel.check_sources_match(paths, spec, dims)
    probes = {key: {"url": spec["sources"][key], "width": w, "height": h,
                    "fps": fps, "fps_value": value}
              for key, (w, h, fps, value) in dims.items()}
    assert probe_sources.geometry_findings(spec, probes, reel.check_sources_match,
                                           reel.ReelError) == ([], [])
    seg = reel.parse_segments(spec, paths, "main")[0]
    assert seg.native_crop == spec["source_crop"]["portrait"]
    assert reel.native_source_crop_window(1080, 1920) == (1080, 1440, 0, 240)
    assert reel.native_source_crop_window(1280, 720) == (540, 720, 370, 0)
    assert reel.native_source_crop_window(1080, 1920, fill_y=0) == (1080, 1440, 0, 0)
    dims["portrait"] = (720, 1280, "25/1", 25.)
    with pytest.raises(reel.ReelError, match="原生短边"):
        reel.check_sources_match(paths, spec, dims)
    conflict = copy.deepcopy(spec)
    conflict["conform"] = {"portrait": "不能预先改成横幅"}
    with pytest.raises(reel.ReelError, match="同时声明"):
        reel.source_crop_claims(conflict)


def test_archival_default_stays_contain_and_720_crop_is_episode_url_bound():
    spec = _spec("archive", 720)
    spec["archival"] = {"archive": "官方最高已核720p，用户本集要求裁切，放大不增加细节"}
    paths = {key: Path(key + ".mp4") for key in spec["sources"]}
    reel.check_archival_fit(spec, reel.parse_segments(spec, paths, "main"))
    dims = {"main": (1920, 1080, "25/1", 25.), "archive": (1280, 720, "25/1", 25.)}
    reel.check_sources_match(paths, spec, dims)
    for field, value in (("slug", "another-episode"), ("sources", {**spec["sources"], "archive": "https://example.com/unapproved"})):
        wrong = copy.deepcopy(spec)
        wrong[field] = value
        with pytest.raises(reel.ReelError, match="精确URL"):
            reel.source_crop_claims(wrong)
    del spec["source_crop"]
    with pytest.raises(reel.ReelError, match="contain"):
        reel.check_archival_fit(spec, reel.parse_segments(spec, paths, "main"))
    spec["segments"][0]["fit"] = "contain"
    reel.check_archival_fit(spec, reel.parse_segments(spec, paths, "main"))


@pytest.mark.parametrize("width,height,box,floor", [
    (1080, 1920, "0:240:1080:1440", 1080),
    (1280, 720, "370:0:540:720", 720),
])
def test_native_crop_really_fills_canvas_without_using_main_globals(tmp_path, monkeypatch,
                                                                  width, height, box, floor):
    source = tmp_path / "source.mp4"
    x, y, w, h = box.split(":")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    f"color=red:size={width}x{height}:rate=25:duration=0.4",
                    "-vf", f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x00ff00:t=fill",
                    "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast",
                    "-crf", "10", "-pix_fmt", "yuv420p", str(source)], check=True)
    # Deliberately wrong for both sources: the main broadcast's 810x1080 crop.
    monkeypatch.setattr(reel, "CROP_W", 810)
    monkeypatch.setattr(reel, "CROP_H", 1080)
    monkeypatch.setattr(reel, "CROP_Y", 0)
    monkeypatch.setattr(reel, "LAYOUT", "full")
    monkeypatch.setattr(reel, "PART_PRESET", "ultrafast")
    seg = reel.Segment(0, .2, .5, "", native_crop={"min_height": floor, "fill_y": .5})
    dest = tmp_path / "part.mp4"
    reel.cut_segment(source, seg, dest, 1920, threads=2)
    assert (reel.CROP_W, reel.CROP_H, reel.CROP_Y) == (810, 1080, 0)
    assert reel.probe_size(source) == (width, height)
    assert reel.probe_size(dest) == (reel.VIDEO_W, reel.VIDEO_H)
    png = tmp_path / "frame.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(dest),
                    "-frames:v", "1", str(png)], check=True)
    with Image.open(png) as image:
        for point in ((8, 8), (image.width // 2, image.height // 2), (image.width - 9, image.height - 9)):
            r, g, b = image.convert("RGB").getpixel(point)
            assert g > 180 and r < 70 and b < 70, "裁切必须铺满，没有红色外框或留边"
