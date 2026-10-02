"""The approved Sun source exception cannot reduce other source thresholds."""
from copy import deepcopy
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
import build_match_reel as reel
URL='https://www.wtatennis.com/videos/4585115/junior-no-1-sun-xinran-advances-on-wta-debut-in-beijing-as-lys-retires'

def spec():
    return {'source_url':URL,'source_quality_exceptions':{URL:{'min_height':720,'approved_by':'user','reason':'Verified official maximum720.'}}}

def test_exact_official_source_at720_is_allowed(monkeypatch):
    monkeypatch.setattr(reel,'probe_size',lambda path:(1280,720))
    assert reel.source_quality_exceptions(spec())[URL]['min_height']==720
    reel.check_native_quality_exceptions(spec(),{'':Path('source.mp4')})

@pytest.mark.parametrize('key,value',[('min_height',719),('min_height',1080),('min_height',True),('approved_by','assistant'),('reason','')])
def test_invalid_exception_claim_rejected(key,value):
    s=spec();s['source_quality_exceptions'][URL][key]=value
    with pytest.raises(reel.ReelError):reel.source_quality_exceptions(s)

@pytest.mark.parametrize('part',['source','claim'])
def test_other_source_not_covered(part):
    s=spec()
    if part=='source':s['source_url']='https://example.org/another-match.mp4'
    else:s['source_quality_exceptions']['https://example.org/another-match.mp4']=s['source_quality_exceptions'].pop(URL)
    with pytest.raises(reel.ReelError):reel.source_quality_exceptions(s)

def test_actual_lower_resolution_rejected(monkeypatch):
    monkeypatch.setattr(reel,'probe_size',lambda path:(1280,719))
    with pytest.raises(reel.ReelError):reel.check_native_quality_exceptions(spec(),{'':Path('source.mp4')})
