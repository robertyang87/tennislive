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


@pytest.mark.parametrize('movie', [False, True])
def test_composed_canvas_keeps_photo_edges_without_evidence_padding(tmp_path, monkeypatch, movie):
    from PIL import Image
    monkeypatch.setattr(reel, 'VIDEO_W', 120)
    monkeypatch.setattr(reel, 'VIDEO_H', 160)
    monkeypatch.setattr(reel, 'PART_PRESET', 'ultrafast')
    image = tmp_path / 'canvas.png'
    im = Image.new('RGB', (120, 160), '#17394d')
    for x in range(12):
        for y in range(25, 120):
            im.putpixel((x, y), (240, 20, 30))
            im.putpixel((119-x, y), (20, 230, 30))
    im.save(image)
    if movie:
        clip = tmp_path / 'canvas.mp4'
        ff('-y', '-loop', '1', '-i', image, '-t', '0.4', '-r', '25',
           '-c:v', 'libx264', '-pix_fmt', 'yuv420p', clip)
        image = clip
    raw = {'image': str(image), 'image_kind': 'canvas', 'seconds': .4,
           'narration': '真实比赛图与事实卡', '_canvas_caption_safety': 'Captions below y128, photo y25–120.'}
    seg = reel.parse_segments({'segments': [raw]}, {'': image}, '')[0]
    landed = reel.cut_still_segment(seg, tmp_path / 'landed.mp4', threads=1)
    pixels = frame(landed, .2)
    assert pixels[70, 1, 0] > 170
    assert pixels[70, -2, 1] > 170
    assert seg.full_bleed
    with pytest.raises(reel.ReelError):
        reel.parse_segments({'segments': [{**raw, '_canvas_caption_safety': ' '}]}, {'': image}, '')
    Image.new('RGB', (120, 100)).save(tmp_path / 'wrong.png')
    with pytest.raises(reel.ReelError):
        reel.parse_segments({'segments': [{**raw, 'image': str(tmp_path / 'wrong.png')}]}, {'': image}, '')


@pytest.mark.parametrize('edit', [
    {'score_inset_y': True}, {'score_inset_y': -2}, {'score_inset_y': 1440},
    {'score_inset_y': 1000, 'score_inset': False},
    {'score_inset_y': 1000, 'fit': 'crop'},
    {'score_inset_y': 1000, '_score_inset_y_why': ' '},
])
def test_score_position_rejects_unclaimed_or_invalid_geometry(edit):
    raw = {'score_inset_y': 1000, 'score_inset': True, 'fit': 'contain',
           '_score_inset_y_why': 'Keep the same-frame board inside the picture.', **edit}
    with pytest.raises(reel.ReelError):
        reel._seg_score_inset_y(raw, 0)


def test_explicit_score_position_moves_real_board_and_preserves_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(reel, 'VIDEO_W', 120)
    monkeypatch.setattr(reel, 'VIDEO_H', 160)
    monkeypatch.setattr(reel, 'CROP_W', 90)
    monkeypatch.setattr(reel, 'PART_PRESET', 'ultrafast')
    src = tmp_path / 'board-source.mp4'
    ff('-y', '-f', 'lavfi', '-i',
       'color=c=0x317a44:s=320x180:r=25,drawbox=x=10:y=130:w=60:h=20:color=blue:t=fill',
       '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000', '-t', '0.4',
       '-c:v', 'libx264', '-c:a', 'aac', src)
    raw = {'start': 0, 'end': .4, 'fit': 'contain', 'contain_keep': .62, 'cx': .5,
           'score_inset': {'x2': 70}, 'scorebox': [10, 130, 70, 150],
           'score_inset_y': 90, '_score_inset_y_why': 'Align board inside the picture.'}
    seg = reel.parse_segments({'segments': [raw]}, {'': src}, '')[0]
    moved = reel.cut_segment(src, seg, tmp_path / 'moved.mp4', 320, threads=1)
    plain = reel.cut_segment(src, replace(seg, score_inset_y=None), tmp_path / 'default.mp4', 320, threads=1)
    assert frame(moved, .2)[98, 10, 2] > 160
    assert frame(plain, .2)[98, 10, 2] < 100
    def pcm(p):
        return ff('-i', p, '-vn', '-f', 's16le', '-ac', '1', '-ar', '16000', '-')
    assert pcm(moved) == pcm(plain)
    assert render_inputs.project({'segments': [raw]})['segments'][0]['score_inset_y'] == 90
    with pytest.raises(reel.ReelError):
        reel._scoreboard_overlay_y(replace(seg, score_inset_y=150), 0, 28)
