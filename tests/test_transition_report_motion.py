"""Actual shared production pages, not scratch-only demo templates."""
import json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from tennislive.video import transition_cards as cards


def comparison():
    return {'comparisons':[
      {'metric':'制胜分','scope':'全场','unit':'个','nodes':[{'label':'球员甲','value':'12','source':'facts#match-winners'},{'label':'球员乙','value':'11','source':'facts#match-winners'}]},
      {'metric':'非受迫失误','scope':'全场','unit':'个','nodes':[{'label':'球员甲','value':'9','source':'facts#match-ue'},{'label':'球员乙','value':'25','source':'facts#match-ue'}]}]}


@pytest.mark.parametrize('mutate',[
 lambda c:c['comparisons'][0].pop('scope'),
 lambda c:c['comparisons'][1]['nodes'].reverse(),
 lambda c:c['comparisons'][0]['nodes'][0].update(value='-1'),
 lambda c:c['comparisons'][0]['nodes'][0].pop('source'),
])
def test_unscoped_swapped_negative_and_unbound_groups_fail(mutate):
    c=comparison();mutate(c)
    with pytest.raises(ValueError):cards.validate_content(c)


@pytest.mark.parametrize('size',[(1080,1440),(1080,960)])
def test_offline_shared_scene_and_hyperframes_export(tmp_path,size):
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    content=comparison()
    entry=cards.export_hyperframes('赢球的另一面\n把失误留给对手',tmp_path/'hf',content=content,seconds=9,size=size)
    assert 'data-composition-id="main"' in entry.read_text()
    assert 'https://cdn' not in entry.read_text()
    # No dependency on the HyperFrames CLI or npm in native production.
    with sync_playwright() as pw:
        browser=launch_chromium(pw,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':size[0],'height':size[1]});errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(entry.as_uri());page.evaluate('document.fonts.ready');page.wait_for_function('window.transitionMotion || window.transitionMotionError')
        page.evaluate('window.setTransitionTime(6)')
        widths=page.eval_on_selector_all('.chart-bar',"es=>es.map(e=>Number(e.getAttribute('width')))")
        assert len(widths)==4 and widths[0]/widths[1]==pytest.approx(12/11)
        assert widths[2]/widths[3]==pytest.approx(9/25)
        assert widths[0]/widths[3]==pytest.approx(12/25)
        assert page.locator('.metric-title').all_text_contents()==['全场 制胜分 个','全场 非受迫失误 个']
        assert not errors
        cards.check_page(page,cards.plan('赢球的另一面\n把失误留给对手',content,size=size))
        page.evaluate('window.setTransitionTime(0)')
        assert all(v==0 for v in page.eval_on_selector_all('.chart-bar',"es=>es.map(e=>Number(e.getAttribute('width')))||0"))
        browser.close()


def test_photo_result_has_no_visible_source_caption(tmp_path,monkeypatch):
    from PIL import Image
    # A generated fixture verifies geometry; it is never published as a match photo.
    photo=tmp_path/'assets/photo.jpg';photo.parent.mkdir();Image.new('RGB',(1600,1100),(30,50,90)).save(photo)
    monkeypatch.setattr(cards,'ROOT',tmp_path)
    content={'photo':{'path':'assets/photo.jpg','source':'official-same-match-gallery','result':{'value':'6–3 6–1','label':'晋级第二轮','source':'official-match-result'}}}
    page=cards.build('美网后巡回赛首胜\n重新出发',content=content,seconds=10)
    assert 'motion-result' in page and '6–3 6–1' in page
    assert 'official-same-match-gallery' not in page and 'hf-credit' not in page
    assert cards.plan('美网后巡回赛首胜\n重新出发',content)['photo']


def test_native_column_still_keeps_cold_open_and_no_cover_heading():
    import build_match_reel as reel
    spec={'slug':'new-approved-motion-fixture','cover':{'eyebrow':'赛场之上'},'segments':[{'source':'main','start':90,'end':99,'narration':''},{'source':'main','start':10,'end':25,'narration':''},{'source':'main','start':85,'end':110,'narration':''}]}
    assert reel.cold_open_problem(spec,primary='main') is None
    spec['segments'][0].update(start=1,end=9)
    assert reel.cold_open_problem(spec,primary='main') is not None
    assert not reel.wants_watermark('赛场之上')


def test_four_score_nodes_use_the_planned_vertical_space(tmp_path):
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    content={'scores':[{'label':f'阶段{i+1}','value':v,'source':'verified-result'} for i,v in enumerate(['1–1','3–3','5–3','6–3'])],
             'summary':{'value':'6–3','label':'拿下首盘','source':'verified-result'}}
    p=cards.plan('重新拿回主动\n把比赛带向终点',content)
    assert p['direction']=='vertical'
    entry=tmp_path/'card.html';entry.write_text(cards.build('重新拿回主动\n把比赛带向终点',content=content))
    with sync_playwright() as pw:
        browser=launch_chromium(pw,args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':1080,'height':1440});page.goto(entry.as_uri())
        page.wait_for_function('window.transitionMotion');page.evaluate('window.setTransitionTime(6)')
        cards.check_page(page,p)
        boxes=page.eval_on_selector_all('.transition-node,.motion-summary','es=>es.map(e=>e.getBoundingClientRect().toJSON())')
        assert all(a['bottom']<=b['top']+.1 for a,b in zip(boxes,boxes[1:]))
        browser.close()
