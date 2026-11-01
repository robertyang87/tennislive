"""Real video framing edits must remove only the requested visual material."""
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel
import render_inputs


def ff(*args):
    return subprocess.check_output(['ffmpeg','-v','error',*map(str,args)])


def source(tmp_path):
    p=tmp_path/'source.mp4'
    ff('-y','-f','lavfi','-i',
       'color=c=0x187a44:s=320x180:r=25,drawbox=x=272:y=0:w=48:h=16:color=red:t=fill,drawbox=x=0:y=172:w=320:h=8:color=blue:t=fill,drawbox=x=0:y=16:w=320:h=156:color=red:t=fill:enable=gte(t\\,0.48)',
       '-f','lavfi','-i','sine=frequency=880:sample_rate=48000','-t','0.8',
       '-c:v','libx264','-c:a','aac',p)
    return p


def frame(path, at):
    raw=ff('-ss',at,'-i',path,'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-')
    return np.frombuffer(raw,dtype=np.uint8).reshape(160,120,3)


def test_header_trim_removes_logo_preserves_full_width_and_bottom(tmp_path,monkeypatch):
    monkeypatch.setattr(reel,'VIDEO_W',120);monkeypatch.setattr(reel,'VIDEO_H',160)
    monkeypatch.setattr(reel,'PART_PRESET','ultrafast')
    src=source(tmp_path)
    seg=reel.parse_segments({'segments':[{'start':0,'end':.4,'cx':.5,'narration':'',
        'fit':'contain','contain_keep':1.,'trim_top':16,'_trim_top_why':'Explicit owner header-crop request.'}]},{'':src},'')[0]
    out=reel.cut_segment(src,seg,tmp_path/'trim.mp4',320,threads=1)
    im=frame(out,.2)
    assert not ((im[:,:,0]>150)&(im[:,:,1]<65)&(im[:,:,2]<65)).any()
    blue=(im[:,:,2]>140)&(im[:,:,0]<70)
    assert blue[:,:4].any() and blue[:,-4:].any()
    assert render_inputs.project({'segments':[{'trim_top':16}]})['segments'][0]['trim_top']==16


def test_hold_stops_end_card_but_preserves_same_original_audio(tmp_path,monkeypatch):
    monkeypatch.setattr(reel,'VIDEO_W',120);monkeypatch.setattr(reel,'VIDEO_H',160)
    monkeypatch.setattr(reel,'PART_PRESET','ultrafast')
    src=source(tmp_path)
    seg=reel.parse_segments({'segments':[{'start':0,'end':.8,'cx':.5,'narration':'','fit':'full_source',
        'visual_end':.4,'_visual_end_why':'Hold last real trophy frame while the original sentence ends.'}]},{'':src},'')[0]
    hold=reel.cut_segment(src,seg,tmp_path/'hold.mp4',320,threads=1)
    plain=reel.cut_segment(src,replace(seg,visual_end=None),tmp_path/'plain.mp4',320,threads=1)
    assert frame(hold,.65)[80,60,1]>90
    assert frame(plain,.65)[80,60,0]>150
    def pcm(p):return ff('-i',p,'-vn','-f','s16le','-ac','1','-ar','16000','-')
    assert pcm(hold)==pcm(plain)
    assert render_inputs.project({'segments':[{'visual_end':.4}]})['segments'][0]['visual_end']==.4


@pytest.mark.parametrize('edit',[{'trim_top':True},{'trim_top':15},{'trim_top':300},
    {'trim_top':16,'fit':'crop','_trim_top_why':'wrong mode'},
    {'visual_end':.5},{'visual_end':1,'_visual_end_why':'outside'},
    {'visual_end':.5,'_visual_end_why':'no retiming','speed':.5}])
def test_framing_requests_require_valid_geometry_and_reasons(edit):
    with pytest.raises(reel.ReelError):
        reel._seg_picture_edits({'start':0,'end':1,**edit},0)
