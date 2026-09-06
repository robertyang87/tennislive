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
    sizes["archive"] = (854, 480)
    with pytest.raises(reel.ReelError, match="尺寸"):
        reel.check_sources_match(paths, spec)
