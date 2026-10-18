"""Real native720p score pixels must survive1080p conform and cache reuse."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import scoreboard_mask_cache as cache
import wta_scoreboard as wta

FRAME = ROOT / 'tests/fixtures/wta_scoreboard/wuhan-final-720p-399440.png'
VF = ('scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,'
      'crop=1920:1080')
TRANSFORM = {'vf': VF, 'size': [1920, 1080]}


def point(source='extended'):
    return SimpleNamespace(source=source, start=0., end=.16, speed=1.,
        score_inset=(90, 826, 550, 980), score_inset_windows=(),
        score_inset_spans=None, score_inset_auto=True, score_inset_mask=None)


@pytest.fixture
def real_sources(tmp_path):
    sources = {}
    for name in ('main', 'extended'):
        source = tmp_path / f'{name}.mkv'
        args = ['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-framerate', '25',
                '-i', str(FRAME), '-t', '0.16']
        if name == 'main':
            args += ['-vf', VF]
        subprocess.run([*args, '-c:v', 'ffv1', '-pix_fmt', 'bgr0', '-threads', '1',
                        str(source)], check=True)
        sources[name] = source
    return sources


def first_alpha(segment):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', segment.score_inset_mask,
                                   '-frames:v', '1', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
    x0, y0, x1, y1 = segment.score_inset
    return np.frombuffer(raw, np.uint8).reshape(y1-y0, x1-x0)


def assert_complete_score(segment):
    # Independently read actual frame locations: both player rows,2/6 and6/4,
    # games5/2, bottom-rowAd and the separateBREAKPOINT#3 header.
    x0, y0, x1, y1 = segment.score_inset
    assert x0 <= 92 and y0 <= 830 and x1 >= 548 and y1 >= 977
    alpha = first_alpha(segment)
    for x, y in [(180, 898), (180, 951), (411, 897), (447, 897),
                 (411, 951), (447, 951), (482, 897), (482, 951), (523, 951),
                 (160, 848)]:
        assert alpha[y-y0, x-x0] == 255, (x, y)
    assert alpha[848-y0, 350-x0] == 0  # court next to the narrow header


def test_real_720_frame_conform_retains_both_rows_and_scores(real_sources, tmp_path):
    segments = [point('main'), point()]
    report = cache.resolve_masks_cached('wta', real_sources, segments, tmp_path / 'cold',
        '25', 0, decode_transforms={'extended': TRANSFORM}, cache_root=tmp_path / 'cache')
    for segment in segments:
        assert_complete_score(segment)
    assert segments[0].score_inset == segments[1].score_inset
    assert np.array_equal(first_alpha(segments[0]), first_alpha(segments[1]))
    records = json.loads(report.read_text())['segments']
    assert records[1]['decode_transform'] == TRANSFORM
    assert 'decode_transform' not in records[0]
    # Warm whole-bundle restoration must preserve the complete actual mask.
    warm = [point('main'), point()]
    cache.resolve_masks_cached('wta', real_sources, warm, tmp_path / 'warm', '25', 0,
        decode_transforms={'extended': TRANSFORM}, cache_root=tmp_path / 'cache')
    for a, b in zip(segments, warm):
        assert_complete_score(b)
        assert Path(a.score_inset_mask).read_bytes() == Path(b.score_inset_mask).read_bytes()


def test_transform_identity_invalidates_only_its_incremental_source(real_sources, tmp_path, monkeypatch):
    count = SimpleNamespace(main=0, extended=0)
    actual = wta.scan_geometry
    def scanned(source, *args, **kwargs):
        setattr(count, source.stem, getattr(count, source.stem) + 1)
        return actual(source, *args, **kwargs)
    monkeypatch.setattr(wta, 'scan_geometry', scanned)
    def run(name, transforms):
        segments = [point('main'), point()]
        cache.resolve_masks_cached('wta', real_sources, segments, tmp_path / name, '25', 0,
            decode_transforms=transforms, cache_root=tmp_path / 'cache')
        return segments
    run('cold', {'extended': TRANSFORM})
    assert vars(count) == {'main': 1, 'extended': 1}
    run('warm', {'extended': TRANSFORM})
    assert vars(count) == {'main': 1, 'extended': 1}
    changed = deepcopy(TRANSFORM)
    changed['vf'] = VF.replace('flags=lanczos', 'flags=bicubic')
    for segment in run('changed-filter', {'extended': changed}):
        assert_complete_score(segment)
    assert vars(count) == {'main': 1, 'extended': 2}
    # Effective dimensions are also independently bound, even with identicalvf.
    changed['size'] = [1922, 1080]
    run('changed-size', {'extended': changed})
    assert vars(count) == {'main': 1, 'extended': 3}


def test_cache_refuses_unsupported_profile_transform_before_scanning(tmp_path):
    with pytest.raises(ValueError, match='do not support decode transforms'):
        cache.resolve_masks_cached('atp', {'extended': Path('not-read.mp4')}, [point()],
            tmp_path, '25', 0, decode_transforms={'extended': TRANSFORM})


def test_transformed_box_outside_effective_frame_is_not_silently_clamped(real_sources):
    with pytest.raises(RuntimeError, match='exceeds transformed source'):
        wta.scan_geometry(real_sources['extended'], (90, 1100, 550, 1254), 0, .04, '25',
                          decode_transform=TRANSFORM)


def test_native_720_source_rejects_1080_box_instead_of_ffmpeg_clamp(real_sources):
    with pytest.raises(RuntimeError, match='exceeds native source'):
        wta.scan_geometry(real_sources['extended'], (90, 826, 550, 980), 0, .04, '25')


def test_filter_change_during_scan_cannot_be_stored_under_original_key(
        real_sources, tmp_path, monkeypatch, capsys):
    actual = wta.scan_geometry
    count = SimpleNamespace(n=0)
    def changed(source, *args, **kwargs):
        count.n += 1
        result = actual(source, *args, **kwargs)
        # A detector must not rewrite the decode context after the cache key is
        # computed. Even an equivalentnull filter must invalidate that binding.
        kwargs['decode_transform']['vf'] += ',null'
        return result
    monkeypatch.setattr(wta, 'scan_geometry', changed)
    source = {'extended': real_sources['extended']}
    for name in ('first', 'second'):
        segment = point()
        cache.resolve_masks_cached('wta', source, [segment], tmp_path / name, '25', 0,
            decode_transforms={'extended': TRANSFORM}, cache_root=tmp_path / 'cache')
        assert_complete_score(segment)
    assert count.n == 2
    assert 'Inputs changed during native mask scan' in capsys.readouterr().out
    assert not list((tmp_path / 'cache/entries').glob('*/manifest.json'))
