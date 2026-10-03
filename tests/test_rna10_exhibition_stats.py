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
