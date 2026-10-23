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
