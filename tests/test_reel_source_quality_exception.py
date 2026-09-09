"""720p is a URL-bound user exception, never a global quality downgrade."""
from pathlib import Path

import pytest

from test_match_reel import _reel

URL = "https://www.youtube.com/watch?v=-6Gv0033I2I"
OTHER = "https://www.youtube.com/watch?v=another1080"


def approved_spec():
    return {
        "sources": {"extended": URL, "other": OTHER},
        "source_quality_exceptions": {
            URL: {"min_height": 720, "approved_by": "user",
                  "reason": "用户明确同意本条郑钦文重剪使用原生720p补齐关键过程"}},
        "segments": [
            {"source": key, "start": 1, "end": 3, "narration": "比赛画面"}
            for key in ("extended", "other")],
    }


@pytest.mark.parametrize("authorized,extended_h,other_h,blocked", [
    (True, 720, 1080, False), (False, 720, 1080, True),
    (True, 719, 1080, True), (True, 720, 720, True),
])
def test_probe_exception_is_scoped(monkeypatch, authorized, extended_h, other_h, blocked):
    reel = _reel()
    spec = approved_spec()
    if not authorized:
        del spec["source_quality_exceptions"]
    probes = {url: {"url": url, "width": 1280, "height": h, "duration": 30,
                    "scene_cuts": [], "point_ends": []}
              for url, h in ((URL, extended_h), (OTHER, other_h))}
    monkeypatch.setattr(reel, "probes_for_spec", lambda _: (probes, []))
    segs = reel.parse_segments(spec, {key: Path(key) for key in spec["sources"]}, "")
    assert reel.probe_dry_run(spec, segs) is blocked
    assert probes[URL]["height"] == extended_h  # Never relabel native resolution.


@pytest.mark.parametrize("change", ["url", "unreferenced", "floor", "approval", "reason", "shape"])
def test_invalid_authorization_is_rejected(change):
    reel = _reel()
    spec = approved_spec()
    claims = spec["source_quality_exceptions"]
    if change == "url":
        claims[OTHER] = claims.pop(URL)
    elif change == "unreferenced":
        del spec["sources"]["extended"]
    elif change == "floor":
        claims[URL]["min_height"] = 480
    elif change == "approval":
        claims[URL]["approved_by"] = "assistant"
    elif change == "reason":
        claims[URL]["reason"] = " "
    else:
        spec["source_quality_exceptions"] = []
    with pytest.raises(reel.ReelError, match="source_quality_exceptions"):
        reel.source_quality_exceptions(spec)


def test_downloaded_native_height_is_checked_before_conform(monkeypatch, capsys):
    reel = _reel()
    spec = approved_spec()
    paths = {"extended": Path("native.mp4")}
    monkeypatch.setattr(reel, "probe_size", lambda _: (1280, 720))
    reel.check_native_quality_exceptions(spec, paths)
    assert "原生 1280x720" in capsys.readouterr().out
    monkeypatch.setattr(reel, "probe_size", lambda _: (854, 480))
    with pytest.raises(reel.ReelError, match="低于明确授权的 720p"):
        reel.check_native_quality_exceptions(spec, paths)
    import inspect
    body = inspect.getsource(reel.render)
    assert body.index("check_native_quality_exceptions(") < body.index("conform_sources(")
