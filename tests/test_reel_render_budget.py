"""Render concurrency has a finite budget and cover-only work ignores audio."""
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


@pytest.mark.parametrize('cpus,affinity,segments,expected', [
    (64, 64, 30, (4, 4)), (64, 2, 30, (2, 1)),
    (4, 4, 1, (1, 4)), (1, 1, 12, (1, 1)), (None, 1, 12, (1, 1)),
])
def test_segment_budget(monkeypatch, cpus, affinity, segments, expected):
    monkeypatch.setattr(reel.os, 'cpu_count', lambda: cpus)
    monkeypatch.setattr(reel.os, 'sched_getaffinity', lambda _: set(range(affinity)), raising=False)
    assert reel.segment_encode_budget(segments) == expected


def test_cover_preview_never_reads_or_merges_legacy_audio(monkeypatch, tmp_path):
    source = tmp_path / 'source.mp4'
    source.write_bytes(b'video placeholder')
    for name in ('validate_spec', '_preflight_cutout', 'check_native_quality_exceptions',
                 'conform_sources', 'check_sources_match', 'precheck_cover_face'):
        monkeypatch.setattr(reel, name, lambda *a, **kw: None)
    monkeypatch.setattr(reel, 'effective_size', lambda p: (1920, 1080))
    monkeypatch.setattr(reel, '_has_audio', lambda p: pytest.fail('cover inspected audio'))
    monkeypatch.setattr(reel, 'run', lambda *a, **kw: pytest.fail('cover merged audio'))

    def cover(sources, primary, spec, dest, width):
        (tmp_path / reel.POSTER_NAME).write_bytes(b'poster')
        dest.write_bytes(b'cover')
        return dest

    monkeypatch.setattr(reel, 'build_cover', cover)
    result = reel.render({'source_url': 'https://example.com/video.mp4',
                          'source_audio': '/missing/legacy.m4a'}, tmp_path,
                         voice='unused', rate='+0%', cover_only=True)
    assert result.read_bytes() == b'poster'
    assert not (tmp_path / 'source_av.mp4').exists()


@pytest.mark.parametrize('kind', ['footage', 'still', 'visual_image'])
def test_bounded_real_ffmpeg_preserves_frames_audio_and_duration(monkeypatch, tmp_path, kind):
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    'testsrc2=size=320x240:rate=25:duration=1.5',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1.5',
                    '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast',
                    '-c:a', 'aac', '-shortest', str(source)], check=True)
    image = tmp_path / 'still.png'
    Image.new('RGB', (180, 240), '#102040').save(image)
    for key, value in {'VIDEO_W': 180, 'VIDEO_H': 240, 'CROP_W': 180,
                       'CROP_H': 240, 'CROP_Y': 0, 'FPS': 25, 'FPS_EXPR': '25',
                       'LAYOUT': 'full'}.items():
        monkeypatch.setattr(reel, key, value)
    commands = []
    real_run = reel.run

    def record(*args, **kwargs):
        if args[0] == 'ffmpeg':
            commands.append(args)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(reel, 'run', record)
    seg = reel.Segment(.2, 1.2, .5, '', track=False)
    output = tmp_path / 'part.mp4'
    if kind == 'still':
        seg.image = str(image)
        reel.cut_still_segment(seg, output, threads=1)
    else:
        if kind == 'visual_image':
            seg.visual_image = str(image)
        reel.cut_segment(source, seg, output, 320, threads=1)
    assert abs(reel.probe_duration(output) - 1) < .09
    assert reel.probe_size(output) == (180, 240)
    assert reel._has_audio(output)
    command = commands[0]
    assert command.count('-threads') >= 2  # decoder and encoder scopes
    key = '-filter_threads' if kind == 'still' else '-filter_complex_threads'
    assert command[command.index(key) + 1] == '1'
    if kind != 'still':
        assert reel.audio_peak_db(output) > -40
