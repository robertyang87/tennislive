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
