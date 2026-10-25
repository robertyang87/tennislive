"""Real Osaka final pixels: event text and final scores stay on the native plane."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import wta_scoreboard as w
ROOT=Path(__file__).parent/'fixtures'/'wta_scoreboard'

def _alpha(name):
    image=np.asarray(Image.open(ROOT/name).convert('RGB'))
    geometry=w.frame_geometry(image,cap=580)
    assert geometry is not None
    return geometry,w.alpha_frame(geometry,(0,0,760,160))

def test_osaka_native_event_entry_retains_actual_green_extension():
    geometry,alpha=_alpha('osaka-final-258640-event.png')
    assert geometry['native_event']=='broad-mint-banner'
    assert geometry['body'][1]>=35
    assert alpha[90,500]==255  # genuine event entering beyond the old board edge
    assert alpha[20,100]==255  # native CHAMPIONSHIP POINT stays visible
    assert alpha[20,250]==0  # transparent court beside short header
    assert not alpha[:,515:].any()

def test_osaka_full_double_fault_banner_keeps_letters_and_rounded_silhouette():
    geometry,alpha=_alpha('osaka-final-259360-event.png')
    assert alpha[90,240]==255  # black DOUBLE FAULT letters are part of banner
    assert not alpha[:35].any()
    assert not alpha[:,485:].any()

def test_osaka_event_slide_reveals_real_final_score_without_losing_it():
    for stamp in ('259840','259920'):
        geometry,alpha=_alpha(f'osaka-final-{stamp}-event.png')
        assert alpha[90,100]==255  # outgoing native event
        assert alpha[100,425]==255  # 6/0 games cell behind the event
        assert alpha[130,450]==255  # actual dark final-score body
        assert not alpha[:,485:].any()
        assert not alpha[:35].any()

def test_osaka_point_digits_do_not_truncate_slot_before_event():
    geometry,alpha=_alpha('osaka-final-258480-event.png')
    assert geometry['body'][2]>=505
    assert alpha[85,484]==255
    assert alpha[130,484]==255
    assert not alpha[:,512:].any()

def test_osaka_normal_score_slots_keep_both_point_numerals():
    for name in ('osaka-qf-702560-score.png','osaka-qf-704880-score.png',
                 'osaka-r2-242440-score.png','osaka-sf-260640-score.png'):
        geometry,alpha=_alpha(name)
        assert geometry['body'][2]>=505
        assert alpha[85,484]==255
        assert alpha[130,484]==255
        assert not alpha[:,515:].any()
    geometry,alpha=_alpha('osaka-final-156080-score.png')
    assert geometry['body'][2]>=474
    assert alpha[85,454]==255
    assert alpha[130,454]==255
    assert not alpha[:,482:].any()

def test_osaka_background_lower_third_is_not_an_event_banner():
    geometry,alpha=_alpha('osaka-qf-704880-score.png')
    assert 'native_event' not in geometry
    assert not alpha[:,515:].any()
    assert alpha[20,100]==255
    assert alpha[20,250]==0
