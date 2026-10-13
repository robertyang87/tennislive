"""Native dynamic alpha cache preserves widths, absent frames and point headers."""
from __future__ import annotations

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
import scoreboard_mask_cache as C
import wta_scoreboard as W


def _geometry(width, header=False):
    body = (0, 36, width, 154)
    tag = (0, 0, 230, 28) if header else None
    rows = [(y, 0, width) for y in range(36, 154)]
    if tag:
        rows += [(y, 0, 230) for y in range(28)]
    return {'edge': width, 'body': body, 'header': tag,
            'bounds': (0, 0 if tag else 36, width, 154), 'rows': rows}


@pytest.fixture
def dynamic(tmp_path, monkeypatch):
    source = tmp_path / 'source.bin'; source.write_bytes(b'original-score-pixels')
    frames = [None] * 4 + [_geometry(390)] * 8 + [_geometry(460, True)] * 6 + [_geometry(390)] * 8 + [None] * 6
    counter = SimpleNamespace(n=0, boxes=[])
    def scan(*args, **kwargs):
        counter.n += 1
        counter.boxes.append(args[1])
        return deepcopy(frames), 760
    monkeypatch.setattr(W, 'scan_geometry', scan)
    segment = SimpleNamespace(source='main', start=0.0, end=1.28, speed=1.0,
        score_inset=(90, 827, 580, 982), score_inset_windows=(),
        score_inset_spans=None, score_inset_auto=True, score_inset_mask=None,
        narration='old narration')
    def run(name, seg=None, fps='25', tail=0):
        out = tmp_path / name
        selected = deepcopy(segment) if seg is None else seg
        result = C.resolve_masks_cached('wta', {'main': source}, [selected], out, fps, tail,
                                        cache_root=tmp_path / 'cache')
        return selected, result, out / 'score_masks/segment-01.mkv'
    return SimpleNamespace(source=source, counter=counter, segment=segment, run=run,
                           root=tmp_path / 'cache', frames=frames)


def _pixels(path, box):
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
        '-f', 'rawvideo', '-pix_fmt', 'gray', '-'])
    return np.frombuffer(raw, np.uint8).reshape(-1, box[3]-box[1], box[2]-box[0])


def test_complete_dynamic_ffv1_sequence_is_identical_on_hit_and_copy_edit(dynamic):
    a, _, cold = dynamic.run('cold')
    (dynamic.root / '.dirty').unlink()
    changed = deepcopy(dynamic.segment); changed.narration = 'different words'
    b, _, warm = dynamic.run('warm', changed)
    assert dynamic.counter.n == 1
    assert cold.read_bytes() == warm.read_bytes()
    assert a.score_inset == b.score_inset == (90, 827, 550, 981)
    decoded = _pixels(warm, b.score_inset)
    assert len(decoded) == 32
    assert not decoded[:4].any() and not decoded[26:].any()
    assert not decoded[4:12, :, 390:].any()  # no widest-frame patch on narrow frames
    assert np.all(decoded[12:18, 36:, 450] == 255)
    assert np.all(decoded[12:18, :28, :230] == 255)
    assert not decoded[:12, :28].any() and not decoded[18:, :28].any()
    assert not decoded[:, 28:36].any()       # court gap never becomes opaque
    assert not (dynamic.root / '.dirty').exists()
    manifest = json.loads(next((dynamic.root / 'entries').glob('*/manifest.json')).read_text())
    assert 'status' not in manifest and 'spec_sha256' not in manifest
    assert not list(dynamic.root.rglob('qc_attestation.json'))


@pytest.mark.parametrize('field,value', [
    ('start', 0.04), ('end', 1.32), ('speed', 0.5),
    ('score_inset', (88, 827, 580, 982)),
    ('score_inset_windows', ((0, 0.4), (0.8, 1.28))),
])
def test_changed_geometry_or_timing_calls_native_scanner(dynamic, field, value):
    dynamic.run('first')
    changed = deepcopy(dynamic.segment); setattr(changed, field, value)
    dynamic.run('changed', changed)
    assert dynamic.counter.n == 2


@pytest.mark.parametrize('change', ['source', 'fps', 'tail', 'detector', 'shared_helper'])
def test_source_bytes_frame_clock_tail_and_detector_changes_miss(dynamic, monkeypatch, change):
    dynamic.run('first')
    kwargs = {}
    if change == 'source':
        old = dynamic.source.stat()
        dynamic.source.write_bytes(b'changed!-score-pixels')
        import os
        os.utime(dynamic.source, ns=(old.st_atime_ns, old.st_mtime_ns))
    elif change == 'fps':
        kwargs['fps'] = '50'
    elif change == 'tail':
        kwargs['tail'] = .24
    elif change == 'detector':
        monkeypatch.setattr(W, 'EDGE_PAD', W.EDGE_PAD + 1)
    else:
        import atp_scoreboard as A
        monkeypatch.setattr(A, 'EDGE_PAD', A.EDGE_PAD + 1)
    dynamic.run('changed', **kwargs)
    assert dynamic.counter.n == 2


@pytest.mark.parametrize('damage', ['mask', 'manifest', 'missing_mask', 'wrong_frame_count'])
def test_damaged_or_incomplete_bundle_is_rescanned(dynamic, damage):
    dynamic.run('first')
    entry = next((dynamic.root / 'entries').iterdir())
    mask = entry / 'masks/segment-01.mkv'
    if damage == 'mask':
        mask.write_bytes(b'bad ffv1')
    elif damage == 'missing_mask':
        mask.unlink()
    elif damage == 'manifest':
        (entry / 'manifest.json').write_text('{broken')
    else:
        manifest = json.loads((entry / 'manifest.json').read_text())
        manifest['records'][0]['frames'] += 1
        manifest.pop('manifest_sha256')
        import hashlib
        manifest['manifest_sha256'] = hashlib.sha256(C._json(manifest)).hexdigest()
        (entry / 'manifest.json').write_bytes(C._json(manifest))
    dynamic.run('second')
    assert dynamic.counter.n == 2


def test_failed_scan_never_creates_entry_or_dirty(dynamic, monkeypatch):
    def failed(*a, **kw):
        raise RuntimeError('native unknown graphic')
    monkeypatch.setattr(W, 'scan_geometry', failed)
    with pytest.raises(RuntimeError, match='native unknown graphic'):
        dynamic.run('failed')
    assert not (dynamic.root / '.dirty').exists()
    assert not (dynamic.root / 'entries').exists()


def test_workflow_tilde_environment_uses_expanded_cache_directory(dynamic, tmp_path, monkeypatch):
    literal = '~/.cache/tennislive-scoreboard-masks'
    native_expand = Path.expanduser
    expanded = []
    def expand(path):
        if str(path) == literal:
            expanded.append(str(path))
            return dynamic.root
        return native_expand(path)
    monkeypatch.setattr(Path, 'expanduser', expand)
    monkeypatch.setenv('TENNISLIVE_SCOREBOARD_MASK_CACHE', literal)
    monkeypatch.chdir(tmp_path)
    for name in ('first', 'second'):
        C.resolve_masks_cached('wta', {'main': dynamic.source}, [deepcopy(dynamic.segment)],
                               tmp_path / name, '25', 0)
    assert expanded == [literal, literal]
    assert (dynamic.root / '.dirty').is_file()
    assert len(list((dynamic.root / 'entries').glob('*/manifest.json'))) == 1
    assert dynamic.counter.n == 1
    assert not (tmp_path / '~').exists()


def test_failed_restore_write_reuses_original_input_geometry(dynamic, monkeypatch):
    dynamic.run('first')
    replace = C.os.replace
    def fail_once(source, target):
        if Path(source).name.startswith('.scoreboard-cached-'):
            raise OSError('cannot write restored report')
        return replace(source, target)
    monkeypatch.setattr(C.os, 'replace', fail_once)
    dynamic.run('second')
    assert dynamic.counter.n == 2
    assert dynamic.counter.boxes == [dynamic.segment.score_inset] * 2


def test_source_change_during_restore_forces_native_current_bytes(dynamic, monkeypatch):
    dynamic.run('first')
    probe = C._probe
    changed = SimpleNamespace(done=False)
    def swap_source(path):
        if not changed.done:
            changed.done = True
            dynamic.source.write_bytes(b'replacement source pixels')
        return probe(path)
    monkeypatch.setattr(C, '_probe', swap_source)
    dynamic.run('second')
    assert dynamic.counter.n == 2
    assert dynamic.counter.boxes == [dynamic.segment.score_inset] * 2


def test_retention_removes_oldest_complete_entry_without_touching_partial(tmp_path, monkeypatch):
    root = tmp_path / 'cache'; (root / 'entries').mkdir(parents=True)
    for n in range(3):
        entry = root / 'entries' / f'{n:064x}'; entry.mkdir()
        (entry / 'data').write_bytes(b'abc')
        import os
        os.utime(entry, ns=(n + 1, n + 1))
    partial = root / '.building-partial'; partial.mkdir()
    monkeypatch.setattr(C, 'MAX_ENTRIES', 2)
    C._prune(root)
    assert not (root / 'entries' / f'{0:064x}').exists()
    assert len(list((root / 'entries').iterdir())) == 2 and partial.is_dir()


def test_native_us_open_rebinds_current_spec_and_expands_geometry_only_once(tmp_path, monkeypatch):
    import scoreboard_geometry as U
    source = tmp_path / 'source'; source.write_bytes(b'same original pixels')
    spec = tmp_path / 'spec.json'; spec.write_text('{"narration":"old"}')
    counter = SimpleNamespace(n=0, boxes=[])
    def scan(source, box, start, seconds, dest, fps, windows, body_top):
        counter.n += 1
        counter.boxes.append(box)
        assert body_top == 36
        W.write_geometry_mask([_geometry(390)] * 2, box, fps, dest)
        return {'profile': U.PROFILE, 'frames': 2, 'present_frames': 2,
                'mask': str(dest), 'mask_sha256': C._sha(dest), 'box': list(box),
                'max_extra_source_px': 4, 'gap_bridge_frames': 0}
    monkeypatch.setattr(U, 'scan_mask', scan)
    def segment():
        return SimpleNamespace(source='main', start=0., end=.08, speed=1.,
            score_inset=(0, 36, 460, 154), score_inset_windows=(),
            score_inset_spans=None, score_inset_auto=True, score_inset_mask=None)
    cold_segment = segment()
    C.resolve_masks_cached('us-open', {'main': source}, [cold_segment], tmp_path / 'cold', '25', 0,
                           spec_path=spec, cache_root=tmp_path / 'cache')
    spec.write_text('{"narration":"new copy requires current spec binding"}')
    warm_segment = segment()
    report = C.resolve_masks_cached('us-open', {'main': source}, [warm_segment], tmp_path / 'warm', '25', 0,
                           spec_path=spec, cache_root=tmp_path / 'cache')
    assert counter.n == 1
    assert cold_segment.score_inset == warm_segment.score_inset == (0, 0, 460, 154)
    assert counter.boxes == [(0, 0, 460, 154)]
    assert json.loads(report.read_text())['spec_sha256'] == C._sha(spec)


def test_storage_failure_reports_cause_and_keeps_complete_native_mask(dynamic, monkeypatch, capsys):
    def deny(*args, **kwargs):
        raise PermissionError('cache directory is read-only')
    monkeypatch.setattr(C, '_store', deny)
    segment, result, mask = dynamic.run('uncached')
    assert mask.is_file() and result.is_file()
    assert len(_pixels(mask, segment.score_inset)) == 32
    assert not (dynamic.root / '.dirty').exists()
    assert 'PermissionError: cache directory is read-only' in capsys.readouterr().out
