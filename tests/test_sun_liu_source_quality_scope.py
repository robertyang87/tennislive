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


@pytest.mark.parametrize('url', list(reel.LIU_HONG_KONG_STORY_2026_LOW_RES_SOURCES))
def test_liu_biography_approval_does_not_escape_its_episode(url):
    claim = {'min_height': 720, 'approved_by': 'user',
             'reason': '2026-11-08: 允许本期使用官方720p（推荐）'}
    spec = {'slug': 'liu-hong-kong-first-title-story-2026', 'source_url': url,
            'source_quality_exceptions': {url: claim}}
    assert reel.source_quality_exceptions(spec)[url] == claim
    for slug in ('another-match', 'dart-guangzhou-first-title-story-2026'):
        spec['slug'] = slug
        with pytest.raises(reel.ReelError):
            reel.source_quality_exceptions(spec)


def test_liu_biography_approval_rejects_unapproved_source_and_floor():
    url = next(iter(reel.LIU_HONG_KONG_STORY_2026_LOW_RES_SOURCES))
    spec = {'slug': 'liu-hong-kong-first-title-story-2026', 'source_url': url,
            'source_quality_exceptions': {url: {'min_height': 480, 'approved_by': 'user',
                                               'reason': '720p approval is not 480p approval'}}}
    with pytest.raises(reel.ReelError):
        reel.source_quality_exceptions(spec)
    unknown = url.replace('6408098837112', 'unapproved-new-source')
    spec['source_url'] = unknown
    spec['source_quality_exceptions'] = {unknown: {'min_height': 720, 'approved_by': 'user',
                                                  'reason': 'Cannot extend an exact-source approval'}}
    with pytest.raises(reel.ReelError):
        reel.source_quality_exceptions(spec)
