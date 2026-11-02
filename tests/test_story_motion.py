"""Composition must preserve editorial freedom, full time and native contracts."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from tennislive.video import transition_cards as cards
from tennislive.video.story_motion import validate_scene


def headline(start=0, duration=2):
    return {'kind':'headline','start':start,'duration':duration,'lines':['重新出发'],
            'frame':[70,250,940,300],'source':'test fixture'}


def test_late_components_and_reordered_editorial_input_are_preserved():
    scene={'blocks':[headline(7,2),headline(0,2)]}
    original=copy.deepcopy(scene)
    assert validate_scene(scene,seconds=9)==original
    assert cards.plan('测试',{'scene':scene})['kind']=='scene'
    assert scene==original
    with pytest.raises(ValueError,match='窗口'):
        cards.build('测试',content={'scene':scene},seconds=8)


@pytest.mark.parametrize('change',[
    {'kind':'video'}, {'duration':float('nan')}, {'start':True},
    {'frame':[70,100,940,400]}, {'frame':[70,900,940,500]},
    {'source':''}, {'lines':['一行\n仍要换行']}, {'mystery':1},
    {'exit':{'style':'slide','duration':3}},
])
def test_invalid_compositions_fail_before_encoding(change):
    with pytest.raises(ValueError):
        validate_scene({'blocks':[{**headline(),**change}]},seconds=9)


def test_no_competing_scene_and_old_relationship_fields():
    with pytest.raises(ValueError):
        cards.plan('重新出发',{'scene':{'blocks':[headline()]},'events':[]})


def test_native_clock_keeps_late_component_and_rewinds_exactly(tmp_path,monkeypatch):
    if not Path('/usr/bin/chromium').is_file():
        pytest.skip('native Chromium unavailable')
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    monkeypatch.setenv('CHROMIUM_PATH','/usr/bin/chromium')
    scene={'blocks':[headline(0,2),{**headline(7,2),'lines':['再次来到赛场'],
                                  'exit':{'style':'slide','duration':.4}}]}
    target=tmp_path/'scene.html'
    target.write_text(cards.build('重新出发',content={'scene':scene},seconds=9))
    with sync_playwright() as pw:
        browser=launch_chromium(pw,args=['--no-sandbox'])
        try:
            page=browser.new_page(viewport={'width':1080,'height':1440})
            page.goto(target.as_uri())
            page.wait_for_function('window.transitionMotion || window.transitionMotionError')
            assert not page.evaluate('window.transitionMotionError || null')
            page.evaluate('window.setTransitionTime(7.8)')
            first=hashlib.sha256(page.screenshot()).hexdigest()
            assert '再次来到赛场' in json.dumps(cards.check_page(page,{'kind':'scene'}),ensure_ascii=False)
            page.evaluate('window.setTransitionTime(.8)')
            assert '再次来到赛场' not in json.dumps(cards.check_page(page,{'kind':'scene'}),ensure_ascii=False)
            page.evaluate('window.setTransitionTime(7.8)')
            assert hashlib.sha256(page.screenshot()).hexdigest()==first
        finally:
            browser.close()
