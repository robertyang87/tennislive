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


def test_both_ends_of_cited_time_range_must_be_inside_window():
    event={'start':251.48,'end':276.,'kind':'aftermath','winner_visible':True,
           'confidence':.9,'reason':'246.5–262.5s 球员出现在画面里。'}
    raw={'cold_open':event,'ending':dict(event),'cover':{
        'same_match':True,'subject':'王欣瑜','moment':'winner_celebration',
        'wrong_or_old':False,'confidence':.9,'reason':'本场人物和背景一致'}}
    draft={'_match':{'winner':'王欣瑜'},'cover':{'portrait':{'image':'candidate.jpg'}}}
    assert any('246.5' in problem for problem in clean_report(raw,draft,305.16)[1])
