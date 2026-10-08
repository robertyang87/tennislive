"""Segment subtitle positioning must preserve every unaffected subtitle byte."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
import build_match_reel as reel
import render_inputs as ri
from tennislive.video.explainer import write_subtitles

CUES=[(1.,2.,'第一条中文'),(2.,3.,'What a shot!\n这一拍真精彩'),(11.,13.,'孙心然连赢9局后 利斯退赛'),(15.,16.,'最后一条')]

def render(path,cues=CUES,**extra):
    return write_subtitles(cues,path,height=1440,margin_v=1002,outline=4,shadow=1,**extra).read_bytes()

@pytest.mark.parametrize('bad',[None,True,False,140.,'140',0,95,1345,-1,float('nan')])
def test_invalid_segment_values_rejected(bad):
    with pytest.raises(reel.ReelError):reel._seg_subtitle_bottom({'subtitle_bottom':bad,'narration':'中文'},0)

@pytest.mark.parametrize('margin',[96,140,1344])
def test_safe_integer_values(margin):
    assert reel._seg_subtitle_bottom({'subtitle_bottom':margin,'narration':'中文'},0)==margin

def test_position_needs_a_caption():
    with pytest.raises(reel.ReelError):reel._seg_subtitle_bottom({'subtitle_bottom':140},0)
    assert reel._seg_subtitle_bottom({},0) is None

def test_only_contained_segment_changes(tmp_path):
    old=render(tmp_path/'old.ass',bottom_margin=302).splitlines()
    new=render(tmp_path/'new.ass',bottom_margin=302,bottom_margin_windows=[(10.,15.,140)]).splitlines()
    changes=[(a,b) for a,b in zip(old,new) if a!=b]
    assert len(changes)==1
    assert changes[0][0].replace(b',302,,',b',140,,')==changes[0][1]

@pytest.mark.parametrize('window',[[(10.,15.,True)],[(10.,15.,80)],[(10.,15.,140.0)],[(15.,10.,140)],[(float('nan'),15.,140)],[(10.,15.,140),(14.,18.,140)]])
def test_invalid_windows_rejected(tmp_path,window):
    with pytest.raises(ValueError):render(tmp_path/'bad.ass',bottom_margin_windows=window)

@pytest.mark.parametrize('cue',[(9.,11.,'cross start'),(14.,16.,'cross end'),(9.,16.,'cross both')])
def test_cross_segment_cues_rejected(tmp_path,cue):
    with pytest.raises(ValueError):render(tmp_path/'bad.ass',[cue],bottom_margin_windows=[(10.,15.,140)])

def test_boundary_cues_unchanged(tmp_path):
    cues=[(8.,10.,'before'),(15.,17.,'after')]
    assert render(tmp_path/'a.ass',cues)==render(tmp_path/'b.ass',cues,bottom_margin_windows=[(10.,15.,140)])

def test_position_is_render_input_and_whitelisted():
    old={'segments':[{'narration':'字幕'}]};new=deepcopy(old);new['segments'][0]['subtitle_bottom']=140
    assert ri.project(old)!=ri.project(new)
    assert 'subtitle_bottom' in reel._REAL_FIELDS['segment']

def test_windows_include_cover_and_real_segment_duration():
    segments=[reel.Segment(0,10,.5,'中文'),reel.Segment(0,9,.5,'中文',subtitle_bottom=140),reel.Segment(0,7,.5,'')]
    assert reel.segment_subtitle_bottom_windows(segments,1.2)==[(11.2,20.2,140)]

@pytest.mark.parametrize('bottom,digest',[(None,'936b829a27ea5c001b417e0b9c6660390474a586b8fe80ebcfc26bdaf246fa57'),(302,'3a8a257a94c7ad9cf15266558a023754afadc061de5207c6981d312ac29a12b9')])
def test_default_bytes_match_unmodified_native_renderer(tmp_path,bottom,digest):
    assert hashlib.sha256(render(tmp_path/'default.ass',bottom_margin=bottom)).hexdigest()==digest

def test_parser_carries_position_to_real_nine_second_card():
    spec={'segments':[{'stat_card':True,'seconds':9,'narration':'中文','subtitle_bottom':140}], 'stats':{}}
    # Image placeholder parsing exercises the same segment path without a browser render.
    spec['stats']={'a':{},'b':{}}
    segs=reel.parse_segments(spec,{'main':{}},'main')
    assert segs[0].subtitle_bottom==140 and segs[0].length==9
