"""Explicit full-canvas captions must survive the actual final FFmpeg graph."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build_match_reel as reel


def _ass(path):
    path.write_text('''[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 240
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,24,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,30,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,CAPTION
''', encoding='utf-8')
    return path


def _graph(ass):
    # Both match decorations and captions exist before full-canvas restoration.
    return (f'[0:v]drawbox=x=0:y=0:w=iw:h=30:color=red:t=fill,'
            f'drawbox=x=0:y=120:w=iw:h=25:color=yellow:t=fill,'
            f'subtitles={reel._escape(ass)}[out]')


def _render(graph, tmp_path):
    output = tmp_path / 'composed.mkv'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-filter_complex_threads', '1',
                    '-f', 'lavfi', '-i', 'color=c=blue:size=320x240:rate=10:duration=1.6',
                    '-filter_complex', graph, '-map', '[out]', '-c:v', 'ffv1',
                    str(output)], check=True)
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output),
                                   '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, 240, 320, 3)


def _white(frame):
    return np.all(frame[170:225] > 200, axis=2).sum()


def _assert_clean_decorations(frame):
    for area in [frame[:30], frame[120:145]]:
        assert area[..., 2].min() > 200
        assert area[..., :2].max() < 10, 'topbar/footer decoration must stay absent'


def test_actual_mixed_windows_preserve_only_opted_in_captions(tmp_path):
    ass = _ass(tmp_path / 'captions.ass')
    segs = [reel.Segment(0, .4, .5, ''),
            reel.Segment(0, .4, .5, '', full_canvas=True),
            reel.Segment(0, .4, .5, '', full_canvas=True, subtitle_bottom=96),
            reel.Segment(0, .4, .5, '')]
    graph = _graph(ass)
    # The default restoration demonstrates the pre-fix loss using the same ASS.
    old = _render(reel.full_canvas_filtergraph(graph, segs, 0), tmp_path)
    assert _white(old[9]) == 0
    frames = _render(reel.full_canvas_filtergraph(graph, segs, 0, subtitles_ass=ass), tmp_path)
    assert _white(frames[1]) > 50, 'ordinary video retains captions'
    assert _white(frames[5]) == 0, 'default full canvas still clears captions'
    assert _white(frames[9]) > 50, 'explicit full canvas must retain readable subtitle ink'
    assert _white(frames[13]) > 50, 'subtitles resume after the card'
    _assert_clean_decorations(frames[5])
    _assert_clean_decorations(frames[9])
    # Exact half-open interval: at .8 the opt-in starts, at 1.2 decoration returns.
    assert _white(frames[8]) > 50
    assert frames[12, 10, 10, 0] > 200


@pytest.mark.parametrize('opted_in', [False, True])
def test_actual_single_full_canvas_branch(tmp_path, opted_in):
    ass = _ass(tmp_path / 'captions.ass')
    seg = reel.Segment(0, 1.6, .5, '', full_canvas=True,
                       subtitle_bottom=96 if opted_in else None)
    frames = _render(reel.full_canvas_filtergraph(_graph(ass), [seg], 0,
                                                  subtitles_ass=ass), tmp_path)
    assert (_white(frames[5]) > 50) == opted_in
    _assert_clean_decorations(frames[5])
