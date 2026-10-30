"""Keep this session's 720p preference bound to the requested match and bytes."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


@pytest.mark.parametrize('url', list(reel.SHI_TAGGER_GUANGZHOU_2026_LOW_RES_SOURCES))
def test_720p_preference_is_match_and_source_bound(url):
    claim = {'min_height': 720, 'approved_by': 'user', 'reason': 'User: 可以用 720'}
    spec = {'slug': 'shi-tagger-guangzhou-2026-qf', 'source_url': url,
            'source_quality_exceptions': {url: claim}}
    assert reel.source_quality_exceptions(spec)[url] == claim
    spec['slug'] = 'another-match'
    with pytest.raises(reel.ReelError):
        reel.source_quality_exceptions(spec)
