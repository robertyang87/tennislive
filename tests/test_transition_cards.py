from dataclasses import replace
from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'),str(ROOT/'src')]
from tennislive.video import transition_cards as cards
import build_match_reel as reel


def nodes(n=2):
    return [{'label':f'节点{i+1}','value':str(i+1),'source':'verified.json#same-match'} for i in range(n)]


def test_content_relationship_changes_geometry_and_motion():
    text='重新拿回主动\n把比赛带向终点'
    a=cards.plan(text)
    b=cards.plan(text,{'scores':[{'label':'首盘','value':'3–3','source':'facts#1'},{'label':'第二盘','value':'4–0','source':'facts#2'}]})
    c=cards.plan(text,{'comparison':{'metric':'全场失误','nodes':nodes()}})
    d=cards.plan(text,{'events':nodes(4)})
    assert [p['kind'] for p in (a,b,c,d)]==['turn','score_progress','comparison','chronology']
    assert d['direction']=='vertical'
    assert 'tc-fold' in cards.build(text,content=b['content'])
    assert 'comparison-bar' in cards.build(text,content=c['content'])


@pytest.mark.parametrize('content',[
    {'scores':[{'label':'首盘','value':'3–3'},{'label':'第二盘','value':'4–0'}]},
    {'events':nodes(6)}, {'events':nodes(),'scores':[]},
    {'comparison':{'nodes':nodes()}}, {'layout':'some-template'},
    {'highlight':'并不在标题中'}, {'photo':{'path':'../private.jpg','source':'url'}},
])
def test_reject_unbound_or_ambiguous_visuals(content):
    with pytest.raises(ValueError):cards.plan('重新出发',content)


def test_missing_photo_falls_back_without_importing_unrelated_data():
    p=cards.plan('重新出发',{'photo':{'path':'assets/no-such-photo.jpg','source':'official gallery'}})
    assert p['kind']=='turn' and p['notes'] and not p['nodes']


def test_native_normalization_keeps_content_in_render_projection():
    spec={'segments':[{'title_card':'重新出发','seconds':4,'transition_card':{'highlight':'重新出发'}}]}
    reel._normalize_title_card_segments(spec)
    data=json.loads(spec['segments'][0]['image'][len(reel.TITLE_CARD_PREFIX):])
    assert data['content']=={'highlight':'重新出发'}
    import render_inputs
    projected=render_inputs.project(spec)
    assert 'transition_card' in json.dumps(projected)


def test_native_default_materializer_uses_animated_clip_and_full_window(tmp_path,monkeypatch):
    calls=[]
    def fake(text,out,**kwargs):
        calls.append((text,kwargs));out.write_bytes(b'video');return out
    monkeypatch.setattr(cards,'render_clip',fake)
    segments=reel.parse_segments({'segments':[{'title_card':'重新出发','seconds':4}]},{'':1},'')
    got=reel._materialize_title_cards({},segments,tmp_path)
    assert got[0].image.endswith('.mp4')
    assert calls[0][1]['seconds']==4
    command=[]
    reel.cut_still_segment(got[0],tmp_path/'part.mp4',tail=.18,command_sink=lambda *args:command.extend(args))
    assert '-loop' not in command and '4.180' in command
    assert 'tpad=stop_mode=clone' in command[command.index('-vf')+1]


def test_explainer_transition_uses_shared_page():
    from tennislive.video.explainer import ExplainerSegment,_slide_html
    import inspect
    params=inspect.signature(ExplainerSegment).parameters
    kwargs={k:'' for k,v in params.items() if v.default is inspect.Parameter.empty}
    kwargs.update(title='重新出发',visual={'layout':'transition','content':{'highlight':'重新出发'}})
    segment=ExplainerSegment(**kwargs)
    page=_slide_html(1,segment)
    assert 'window.setTransitionTime' in page and 'tc-enter' in page


def test_actual_movie_cache_and_silent_window(tmp_path,monkeypatch):
    monkeypatch.setenv('CHROMIUM_PATH','/usr/bin/chromium')
    # This is an actual browser + encoder test, not a mocked green receipt.
    if not Path('/usr/bin/chromium').is_file():pytest.skip('system Chromium unavailable')
    target=tmp_path/'card.mp4'
    cards.render_clip('重新拿回主动\n把比赛带向终点',target,seconds=.64,fps=25)
    import subprocess
    meta=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(target)]))
    assert len(meta['streams'])==1 and meta['streams'][0]['codec_type']=='video'
    assert abs(float(meta['streams'][0]['duration'])-.64)<.041
    digest=target.read_bytes()
    before=target.stat().st_mtime_ns
    cards.render_clip('重新拿回主动\n把比赛带向终点',target,seconds=.64,fps=25)
    assert target.read_bytes()==digest and target.stat().st_mtime_ns==before


def test_explainer_actual_transition_movie_keeps_its_audio_window(tmp_path,monkeypatch):
    import subprocess
    from tennislive.video.explainer import ExplainerSegment, render_explainer_slides, assemble_explainer_video
    if not Path('/usr/bin/chromium').is_file():pytest.skip('system Chromium unavailable')
    monkeypatch.setenv('CHROMIUM_PATH','/usr/bin/chromium')
    segment=ExplainerSegment(kind='beat',label='转折',title='重新出发',narration='重新出发',
                            visual={'layout':'transition','content':{'highlight':'重新出发'}})
    slides=render_explainer_slides([segment],tmp_path,height=1440)
    assert slides[0].with_suffix(cards.SIDECAR_SUFFIX).is_file()
    audio=tmp_path/'fixture.wav'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:duration=0.8',str(audio)],check=True)
    output=tmp_path/'joined.mp4'
    assemble_explainer_video(slides,[audio],output,canvas_h=1440,full_bleed=True,lead_silence=.1,tail_silence=.2)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(output)]))
    assert {s['codec_type'] for s in probe['streams']}=={'video','audio'}
    assert abs(float(probe['format']['duration'])-1.1)<.1


def test_explainer_motion_keeps_the_column_header_and_topic():
    from tennislive.video.explainer import ExplainerSegment, _slide_html
    segment = ExplainerSegment(kind="cause", label="报名", title="排名够资格", narration="排名够资格。", visual={"layout":"transition", "content":{"highlight":"排名"}})
    page = _slide_html(1, segment, topic="报名与外卡", column="网球有故事")
    assert 'class="explainer-head"' in page
    assert "网球时差 · 网球有故事" in page
    assert 'class="topic"' in page and "报名与外卡" in page


def _entry_content(scene='reserved'):
    from tennislive.video.explainer import explainer_script
    from tennislive.render.tournament_story import find_story_by_slug
    segments = explainer_script(find_story_by_slug('djokovic-basel-wildcard-animation-2026'))
    return next(s.visual['content'] for s in segments[1:]
                if s.visual['content']['entry_process']['scene'] == scene)


@pytest.mark.parametrize('change', ['slots', 'source', 'timing', 'case'])
def test_rule_process_rejects_unbound_or_false_slot_geometry(change):
    content = json.loads(json.dumps(_entry_content()))
    item = content['entry_process']
    if change == 'slots':
        item['case']['draw_size'] = 33
    elif change == 'source':
        item.pop('source')
    elif change == 'timing':
        item['cues'] = [.8, .2, .4, .6]
    else:
        item['case']['locals'] = ['one', 'two']
    with pytest.raises(ValueError):
        cards.validate_content(content)


def test_rule_process_moves_after_six_seconds_and_keeps_fixed_draw(tmp_path):
    from playwright.sync_api import sync_playwright
    from tennislive.chromium import launch_chromium
    content = _entry_content()
    with sync_playwright() as pw:
        browser = launch_chromium(pw)
        page = browser.new_page(viewport={'width':1080,'height':1440})
        page.set_content(cards.build('外卡进入预留名额', content=content, seconds=20,
            header={'brand':'网球时差 · 网球有故事','topic':'报名与外卡'}))
        page.evaluate('document.fonts.ready')
        page.wait_for_function('window.transitionMotion || window.transitionMotionError')
        page.evaluate('document.fonts.ready')
        assert page.evaluate('window.transitionMotionError || null') is None
        assert page.evaluate('window.transitionMotion.library') == 'Renoise vibe-knowledge'
        evidence, pictures = [], []
        for t in (7, 13.5, 18, 7):
            page.evaluate('(t)=>window.setTransitionTime(t)',t)
            evidence.append(page.eval_on_selector('[data-player="德约"]', 'e=>({transform:e.getAttribute("transform"),r:e.getBoundingClientRect().toJSON()})'))
            pictures.append(page.screenshot())
            assert page.locator('.draw-slot').count() == 32
            assert page.locator('.brand-icon').evaluate('e=>e.naturalWidth') > 0
            cards.check_page(page, cards.plan('外卡进入预留名额',content))
        assert evidence[0] != evidence[1] != evidence[2]
        assert evidence[0]['transform'] == evidence[3]['transform']
        assert pictures[0] == pictures[3], 'Seeking back must reproduce identical rendered pixels'
        assert page.locator('.brand').evaluate('e=>getComputedStyle(e).fontFamily') == '"TL Display SC"'
        browser.close()
