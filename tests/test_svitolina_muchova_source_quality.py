"""The user's720p approval remains bound to this episode and exact source."""
import copy

import pytest
import build_match_reel as reel


APPROVALS = [
    ("svitolina-muchova-finals-2026-group2", "https://github.com/robertyang87/tennislive/releases/download/source-6408255435112/6408255435112.mp4"),
    ("gauff-kostyuk-finals-2026-group1", "https://github.com/robertyang87/tennislive/releases/download/source-6408304798112/6408304798112.mp4"),
    ("gauff-kostyuk-finals-2026-group1", "https://players.brightcove.net/6041795521001/te01Hqw71_default/index.html?videoId=6408304798112"),
]


@pytest.fixture(params=APPROVALS)
def approval(request):
    return request.param


def approved(episode, url):
    return {
        "slug": episode,
        "source_url": url,
        "source_quality_exceptions": {
            url: {"min_height": 720, "approved_by": "user", "reason": "用户明确授权本集官网720p"}
        },
    }


def test_exact_episode_approval(approval):
    episode, url = approval
    assert reel.source_quality_exceptions(approved(episode, url))[url]["min_height"] == 720


@pytest.mark.parametrize("change", ["episode", "source", "height", "approver"])
def test_approval_cannot_be_transferred_or_weakened(change, approval):
    episode, url = approval
    spec = copy.deepcopy(approved(episode, url))
    if change == "episode":
        spec["slug"] = "another-match"
    elif change == "source":
        other = "https://example.org/another-match.mp4"
        spec["source_url"] = other
        spec["source_quality_exceptions"][other] = spec["source_quality_exceptions"].pop(url)
    elif change == "height":
        spec["source_quality_exceptions"][url]["min_height"] = 480
    else:
        spec["source_quality_exceptions"][url]["approved_by"] = "assistant"
    with pytest.raises(reel.ReelError):
        reel.source_quality_exceptions(spec)
