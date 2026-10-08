import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import winners_ue_gate,reel_asset_gates
SPEC=Path(__file__).resolve().parents[1]/'specs/reels/pending/nadal-academy-10th-2026.json'
def test_seven_match_exhibition_video_has_no_fake_tour_totals():
    s=json.loads(SPEC.read_text())
    assert winners_ue_gate.problem(s) is None
    assert reel_asset_gates.stats_card_problem(s) is None
    for key,value in [('slug','ordinary-tour-reel'),('push',{'auto':True})]:
        other=copy.deepcopy(s);other[key]=value
        assert winners_ue_gate.problem(other)
        assert reel_asset_gates.stats_card_problem(other)


def test_verified_local_date_does_not_invent_beijing_time_or_tour_round():
    from team_exhibition_scope import local_exhibition_context
    from narrated_audio_mode import no_quote_reason
    s = json.loads((SPEC.parent.parent / SPEC.name).read_text())
    opening = s['segments'][1]['narration']
    assert local_exhibition_context(s, opening)
    assert not local_exhibition_context(s, opening.replace('当地十月三日', '十周年'))
    assert no_quote_reason(s)
    other = copy.deepcopy(s); other['slug'] = 'ordinary-tour-reel'
    assert not local_exhibition_context(other, opening)
    import pytest
    with pytest.raises(ValueError):
        no_quote_reason(other)
