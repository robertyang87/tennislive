"""A requested full-frame photo is distinct from a readable evidence card."""
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path('tools').resolve()))
import build_match_reel as reel


def test_photo_fills_canvas_but_evidence_keeps_subtitle_guard(tmp_path):
    path = tmp_path / 'photo.jpg'
    Image.new('RGB', (1080, 1440), (43, 82, 121)).save(path)
    segment = {'image': str(path), 'seconds': 4, 'narration': '真实合影'}
    spec = {'segments': [segment]}
    assert reel.evidence_card_overlaps_subtitle(spec)
    segment.update(image_kind='photo', _photo_source='https://example.org/photo',
                   _photo_caption_safety='Faces above the caption; no evidence text below.')
    parsed = reel.parse_segments(spec, {'main': 'https://youtu.be/example'}, 'main')[0]
    assert not reel.evidence_card_overlaps_subtitle(spec)
    canvas, box = reel.still_canvas_for_layout(Image.open(path), Image,
                                             full_bleed=parsed.full_bleed)
    assert box == (0, 0, 1080, 1440)
    assert canvas.getpixel((0, 0))[:3] == canvas.getpixel((500, 500))[:3]
    del segment['_photo_caption_safety']
    with pytest.raises(reel.ReelError, match='目视依据'):
        reel.parse_segments(spec, {'main': 'url'}, 'main')
    segment['_photo_caption_safety'] = 'Checked'
    Image.new('RGB', (1080, 1080)).save(path)
    with pytest.raises(reel.ReelError, match='不许拉伸'):
        reel.parse_segments(spec, {'main': 'url'}, 'main')
