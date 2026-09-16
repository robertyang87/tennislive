"""Portrait archive footage must retain its own geometry without relaxing match gates."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("tools").resolve()))
import build_match_reel as reel


def test_native_archive_requires_claim_and_every_use_contained(monkeypatch):
    sizes = {"match": (1920, 1080), "archive": (360, 640)}
    monkeypatch.setattr(reel, "probe_size", lambda p: sizes[p.stem])
    monkeypatch.setattr(reel, "resolve_fps", lambda p: ("30/1", 30.0))
    paths = {k: Path(k + ".mp4") for k in sizes}
    spec = {"archival": {"archive": "Original portrait recovery vlog"},
            "segments": [{"source": "archive", "fit": "contain"}]}
    reel.check_sources_match(paths, spec)
    with pytest.raises(reel.ReelError, match="尺寸"):
        reel.check_sources_match(paths, {"segments": spec["segments"]})
    spec["segments"].append({"source": "archive", "fit": "crop"})
    with pytest.raises(reel.ReelError, match="尺寸"):
        reel.check_sources_match(paths, spec)
    spec["segments"].pop()
    # 2026-09-16 起横幅的存档源同样放行：contain 整幅缩进画布、不裁不取窗口，
    # 几何和横竖无关（戴维斯杯那条的 640×480 百代新闻片，run 35072955589）。
    # 原来这儿断言 854×480 要红——那条「必须竖屏」是给手机录屏写的，去掉了。
    # 横幅那一头的三个方向钉在 test_match_reel.py::test_横幅的存档源整幅铺时不受尺寸闸管。
    sizes["archive"] = (854, 480)
    reel.check_sources_match(paths, spec)
    spec["segments"].append({"source": "archive", "fit": "crop"})
    with pytest.raises(reel.ReelError, match="尺寸"):
        reel.check_sources_match(paths, spec)
