"""The user's720p approval remains bound to this episode and exact source."""
import copy

import pytest
import build_match_reel as reel


URL = "https://github.com/robertyang87/tennislive/releases/download/source-6408255435112/6408255435112.mp4"


def approved():
    return {
        "slug": "svitolina-muchova-finals-2026-group2",
        "source_url": URL,
        "source_quality_exceptions": {
            URL: {"min_height": 720, "approved_by": "user", "reason": "那你先用 720 的做吧"}
        },
    }


def test_exact_episode_approval():
    assert reel.source_quality_exceptions(approved())[URL]["min_height"] == 720


@pytest.mark.parametrize("change", ["episode", "source", "height", "approver"])
def test_approval_cannot_be_transferred_or_weakened(change):
    spec = copy.deepcopy(approved())
    if change == "episode":
        spec["slug"] = "another-match"
    elif change == "source":
        other = "https://example.org/another-match.mp4"
        spec["source_url"] = other
        spec["source_quality_exceptions"][other] = spec["source_quality_exceptions"].pop(URL)
    elif change == "height":
        spec["source_quality_exceptions"][URL]["min_height"] = 480
    else:
        spec["source_quality_exceptions"][URL]["approved_by"] = "assistant"
    with pytest.raises(reel.ReelError):
        reel.source_quality_exceptions(spec)
