"""Duration prose must not invent an out-of-window source timestamp."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from analyze_reel_visuals import clean_report


def test_duration_range_is_not_a_source_time_but_real_citations_still_are():
    event={'start':112.5,'end':127.53,'kind':'match_point','winner_visible':True,
           'confidence':.97,'reason':'112.5–118.5s 比分牌 MATCH POINT；122.5–126.5s 赢家庆祝，保持3–30秒收官长度。'}
    raw={'cold_open':event,'ending':dict(event),'cover':{'same_match':True,'subject':'蒂亚福','moment':'winner_celebration','wrong_or_old':False,'confidence':.96,'reason':'本场衣服和场馆与原片一致'}}
    draft={'_match':{'winner':'蒂亚福'},'cover':{'portrait':{'image':'official.jpg'}}}
    assert clean_report(raw,draft,207.8)[1] == []
    raw['ending']['reason'] += '150.5s 两人拥抱。'
    assert any('150.5' in p for p in clean_report(raw,draft,207.8)[1])
