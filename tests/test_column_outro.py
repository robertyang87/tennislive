"""Active production routes must select the right column and preserve frozen audio."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET

import pytest

from tennislive.video import column_outro, outro_page


@pytest.mark.parametrize('column',list(column_outro.COLUMNS))
def test_active_master_is_real_and_uses_identical_frozen_voice(column):
    from tools.build_column_outros import audio_hash, probe

    master = outro_page.master_for(column)
    manifest = json.loads((outro_page.ROOT/'assets/brand/column_outros.json').read_text())
    record = next(x for x in manifest['masters'] if x['column']==column)
    assert master.is_file() and master != outro_page.MASTER
    assert hashlib.sha256(master.read_bytes()).hexdigest()==record['sha256']
    assert audio_hash(master)==audio_hash(outro_page.MASTER)==record['audio_packet_sha256']
    streams = probe(master)['streams']
    v = next(s for s in streams if s['codec_type']=='video')
    a = next(s for s in streams if s['codec_type']=='audio')
    assert (v['width'],v['height'],v['r_frame_rate'])==(1080,1440,'60/1')
    assert (a['sample_rate'],a['channels'])==('48000',2)
    assert float(v['duration'])>=outro_page.min_length(column)
    assert record['browser']['text']=='网球时差 · '+column


def test_column_selection_handles_story_reels_and_rejects_ambiguity():
    assert outro_page.column_from_spec({})=='赛场之上'
    assert outro_page.column_from_spec({'cover':{'eyebrow':'网球有故事'}})=='网球有故事'
    assert outro_page.column_from_spec({'column':'网球时差 · 赛后开麦'})=='赛后开麦'
    assert outro_page.master_for(' 网球时差 · 网球有故事 ')==outro_page.master_for('网球有故事')
    with pytest.raises(ValueError,match='栏目'):
        outro_page.master_for('赛场之上 / 网球有故事')


def test_real_court_lines_stop_at_correct_boundaries():
    root = ET.fromstring(column_outro.court_svg())
    paths = {p.attrib['data-court']:p for p in root}
    service = paths['service-lines'].attrib['d']
    assert service.count('M')==2
    numbers = [float(x) for x in re.findall(r'[-+]?\d*\.?\d+',service)]
    far,near = numbers[1],numbers[5]
    # Invert the perspective using only the boundary width ratio, then check feet.
    def court_y(y):
        ratio=(y-20)/600
        return 78*ratio/(13/18+5/18*ratio)
    assert court_y(far)==pytest.approx(18,abs=.001)
    assert court_y(near)==pytest.approx(60,abs=.001)
    center=[float(x) for x in re.findall(r'[-+]?\d*\.?\d+',paths['centre-service-line'].attrib['d'])]
    assert center==[380,far,380,near]
    assert paths['net'].attrib['stroke-dasharray']


@pytest.mark.parametrize('column',list(column_outro.COLUMNS))
def test_shared_builder_uses_selected_master_without_tts(tmp_path,monkeypatch,column):
    from tennislive.video import explainer
    calls=[]
    monkeypatch.setattr(subprocess,'run',lambda args,**kw:calls.append(args))
    monkeypatch.setattr(explainer,'synthesize_narration',lambda *a,**k:pytest.fail('复用母版不应重新合成'))
    outro_page.build_with_voice(tmp_path,chromium='',dest=tmp_path/'out.mp4',fps=25,
        audio_rate='48000',preset='ultrafast',crf='26',audio_bitrate='128k',
        audio_channels=2,column=column)
    assert calls[0][calls[0].index('-i')+1]==str(outro_page.master_for(column))


def test_reel_native_builder_uses_passed_column(tmp_path,monkeypatch):
    from tools import build_match_reel as reel
    calls=[]
    monkeypatch.setattr(reel,'run',lambda *args,**kw:calls.append(args))
    reel.build_outro(tmp_path,4.5,column='网球有故事')
    assert str(outro_page.master_for('网球有故事')) in calls[0]
    assert str(outro_page.master_for('赛场之上')) not in calls[0]


def test_interview_and_explainer_native_builders_pass_their_column(tmp_path,monkeypatch):
    from tennislive.render import webcards
    from tennislive.video import explainer
    from tools import build_interview_clip as interview
    calls=[]
    monkeypatch.setattr(webcards,'_chromium_executable',lambda:'')
    monkeypatch.setattr(outro_page,'build_with_voice',lambda *a,**kw:calls.append(kw) or kw['dest'])
    monkeypatch.setattr(explainer,'_audio_seconds',lambda *a:4.12)
    assert interview._build_outro(tmp_path) is not None
    assert explainer._build_outro_clip(tmp_path,voice='v',rate='r',pitch='p') is not None
    assert [c['column'] for c in calls]==['赛后开麦','网球有故事']


@pytest.mark.parametrize(('fps','rate','channels'),[('25','48000',2),('30','24000',1),('30000/1001','48000',2)])
def test_actual_column_master_conforms_to_consumer_streams(tmp_path,fps,rate,channels):
    from tools.build_column_outros import probe
    dest=tmp_path/'converted.mp4'
    outro_page.build_with_voice(tmp_path,chromium='',dest=dest,fps=30,
        fps_expr=fps,audio_rate=rate,preset='ultrafast',crf='26',
        audio_bitrate='128k',audio_channels=channels,column='赛后开麦')
    streams=probe(dest)['streams']
    video=next(s for s in streams if s['codec_type']=='video')
    audio=next(s for s in streams if s['codec_type']=='audio')
    assert video['r_frame_rate']==('25/1' if fps=='25' else '30/1' if fps=='30' else fps)
    assert (audio['sample_rate'],audio['channels'])==(rate,channels)
    assert abs(float(video['duration'])-float(audio['duration']))<.1
