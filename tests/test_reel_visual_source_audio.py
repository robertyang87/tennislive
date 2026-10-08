"""Full-canvas brand graphics retain a real, bounded source audio window."""
from pathlib import Path
import copy
import json
import subprocess
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel
import render_inputs
import taste_gates_extra as taste


def test_visual_image_keeps_original_audio_and_image_pixels(tmp_path, monkeypatch):
    graphic = tmp_path / 'brand.png'
    Image.new('RGB', (1080, 1440), (200, 40, 60)).save(graphic)
    source = tmp_path / 'original.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=320x240:r=25', '-f', 'lavfi', '-i',
                    'sine=frequency=880:sample_rate=48000', '-t', '1.2',
                    '-c:v', 'libx264', '-c:a', 'aac', '-y', str(source)], check=True)
    spec = {'segments': [{'source': 'official', 'start': .2, 'end': 1,
                          'visual_image': str(graphic), 'cx': .5}]}
    seg = reel.parse_segments(spec, {'official': source}, 'official')[0]
    assert not seg.image and seg.length == .8
    monkeypatch.setattr(reel, 'PART_PRESET', 'ultrafast')
    out = reel.cut_segment(source, seg, tmp_path / 'film.mp4', 320)
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error',
                       '-show_streams', '-of', 'json', str(out)]))
    assert {s['codec_type'] for s in probe['streams']} == {'audio', 'video'}
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    assert (video['width'], video['height']) == (1080, 1440)
    pixel = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(out),
                '-frames:v', '1', '-vf', 'scale=1:1', '-f', 'rawvideo',
                '-pix_fmt', 'rgb24', '-'])
    assert abs(pixel[0]-200) < 8 and abs(pixel[1]-40) < 8
    assert 'visual_image' in render_inputs.project(spec)['segments'][0]
    bad = copy.deepcopy(spec); bad['segments'][0]['image'] = str(graphic)
    with pytest.raises(reel.ReelError, match='sole'):
        reel.parse_segments(bad, {'official': source}, 'official')


def farewell_spec():
    return {'slug': 'nishikori-career-farewell', 'cover': {'eyebrow': '网球有故事'},
            'sources': {'official': 'https://x.com/japanopentennis/status/2105641498721284153'},
            'segments': [{'narration': '把最后的话留给他自己。'},
                {'source': 'official', 'start': 313, 'end': 323,
                 'quote': [{'text': '本当にありがとうございました\n真的非常感谢大家'}]},
                {'source': 'official', 'start': 315, 'end': 320, 'visual_image': 'real-brand.png'}]}


def test_only_explicit_real_farewell_ending_may_use_thanks_instead_of_question():
    spec = farewell_spec()
    assert taste.ending_problem(spec) is None
    for key, value in [('slug', 'another-film'), ('sources', {'official': 'https://example.org/fake'})]:
        changed = copy.deepcopy(spec); changed[key] = value
        assert taste.ending_problem(changed)
    for edit in ['rewritten_quote', 'long_tail', 'narration', 'missing_graphic']:
        changed = copy.deepcopy(spec)
        if edit == 'rewritten_quote': changed['segments'][-2]['quote'][0]['text'] = 'Thank you\n谢谢'
        if edit == 'long_tail': changed['segments'][-1]['end'] = 325
        if edit == 'narration': changed['segments'][-1]['narration'] = '后面的数据。'
        if edit == 'missing_graphic': changed['segments'][-1].pop('visual_image')
        assert taste.ending_problem(changed)
