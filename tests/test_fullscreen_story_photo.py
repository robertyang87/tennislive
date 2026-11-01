"""A requested full-frame photo is distinct from a readable evidence card."""
import sys
from pathlib import Path
import shutil
import subprocess

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
    canvas, box = reel.still_canvas_for_layout(Image.open(path).convert('RGBA'), Image,
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


def test_photo_movie_preserves_canvas_and_requires_the_same_safety(tmp_path, monkeypatch):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg unavailable')
    path = tmp_path / 'photos.mp4'
    def movie(size):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        f'color=c=blue:s={size}:r=25', '-frames:v', '2',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True)
    movie('1080x1440')
    raw = {'image': str(path), 'image_kind': 'photo', 'seconds': 4,
           'narration': '真实照片依次出现。', '_photo_source': 'https://example.org/gallery',
           '_photo_caption_safety': 'Faces and trophies above caption; header reserved.'}
    parsed = reel.parse_segments({'segments': [raw]}, {'main': 'url'}, 'main')[0]
    assert parsed.full_bleed
    command = []
    reel.cut_still_segment(parsed, tmp_path / 'part.mp4',
                           command_sink=lambda *args: command.extend(args))
    assert 'scale=1080:1440' in command[command.index('-vf') + 1]
    # Native dry-run / reattest precedes installation of ffprobe. Read real
    # sample-entry dimensions, rather than trusting a dimension claim in spec.
    monkeypatch.setattr(reel.shutil, 'which', lambda name: None)
    monkeypatch.setattr(reel, 'probe_size', lambda path: pytest.fail('early validation called ffprobe'))
    assert reel.parse_segments({'segments': [raw]}, {'main': 'url'}, 'main')[0].full_bleed
    del raw['_photo_source']
    with pytest.raises(reel.ReelError, match='来源'):
        reel.parse_segments({'segments': [raw]}, {'main': 'url'}, 'main')
    raw['_photo_source'] = 'https://example.org/gallery'
    movie('1080x1080')
    with pytest.raises(reel.ReelError, match='不许拉伸'):
        reel.parse_segments({'segments': [raw]}, {'main': 'url'}, 'main')
    path.write_bytes(path.read_bytes()[:40])
    with pytest.raises(reel.ReelError, match='尺寸无法核验'):
        reel.parse_segments({'segments': [raw]}, {'main': 'url'}, 'main')
