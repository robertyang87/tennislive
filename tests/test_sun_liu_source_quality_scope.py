"""The owner's 720p approval covers only this match and its exact sources."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import build_match_reel as reel

@pytest.mark.parametrize('url', list(reel.SUN_LIU_GUANGZHOU_2026_LOW_RES_SOURCES))
def test_approval_is_match_and_source_bound(url):
    claim={'min_height':720,'approved_by':'user','reason':'Owner: 可以用 720'}
    spec={'slug':'sun-liu-guangzhou-2026-qf','source_url':url,'source_quality_exceptions':{url:claim}}
    assert reel.source_quality_exceptions(spec)[url]==claim
    spec['slug']='another-match'
    with pytest.raises(reel.ReelError):
        reel.source_quality_exceptions(spec)
