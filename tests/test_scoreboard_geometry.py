import numpy as np
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import scoreboard_geometry as s

def graphic(width=476):
    a=np.full((90,732,3),[122,148,203],dtype=np.uint8) # blue court
    a[:,:width]=[20,30,95]
    a[10:25,20:120]=230;a[55:70,20:120]=230
    a[6:-6,width-42:width-4]=230
    return a

def test_blue_court_and_white_point_cell():
    edge=s.right_edge(graphic())
    assert edge is not None and 474<=edge<=478

def test_no_score_graphic_no_overlay():
    assert s.right_edge(np.full((90,732,3),[20,50,130],np.uint8)) is None

def test_two_large_outliers_do_not_set_whole_clip_width():
    result=s.stabilize([476]*100+[650,650]+[476]*100,30)
    assert set(result)=={476}

def test_real_width_changes_and_absent_frames_remain_distinct():
    edges=[476]*60+[None]*15+[550]*60
    result=s.stabilize(edges,30)
    assert result==edges

def test_unknown_graphic_is_blocked():
    with pytest.raises(RuntimeError):s.stabilize([-1]*90,30)


def test_量不出板的几何时报错要说清是哪一段和两条出路(tmp_path, monkeypatch):
    """`scan_mask` 只知道秒数，不知道段号——原来那句错没有主语。

    2026-09-11 为它白烧过一趟 render：日志里只有 `Scoreboard has no stable,
    majority-supported geometry`，而那条片子 21 段里开了回贴的有 13 段，
    只能挨个猜。报错要说出**是哪一段**，以及那两条出路
    （整段 `score_inset: false`／用 `score_inset_windows` 收到量得出来的那几秒），
    并且明说不许去调宽兜底右缘——右缘在色彩上不可分辨，调多宽都是猜。
    """
    class Seg:
        score_inset=(104,887,660,980);source='';start=150.05;end=153.75
        speed=1.0;score_inset_windows=();score_inset_mask=''
    src=tmp_path/'source.mp4';src.write_bytes(b'not really a video')
    monkeypatch.setattr(s,'scan_mask',lambda *a,**k:(_ for _ in ()).throw(
        RuntimeError('Scoreboard has no stable, majority-supported geometry')))
    with pytest.raises(RuntimeError) as exc:
        s.resolve_masks({'':src},[Seg()],tmp_path,tmp_path/'spec.json','30000/1001',0.18)
    text=str(exc.value)
    assert '第 1 段' in text and '150.05' in text and '153.75' in text, text
    assert 'score_inset": false' in text and 'score_inset_windows' in text, text
    assert '别去调宽兜底右缘' in text, text
    # 原始那句照旧带着，别把根因吞掉
    assert 'no stable' in text, text
