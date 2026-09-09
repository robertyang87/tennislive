"""An audited transform checkpoint cannot replace mismatched native media."""
import hashlib
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as reel


def setup_checkpoint(tmp_path, monkeypatch):
    source = tmp_path / 'source_extended.mp4'
    dst = tmp_path / 'source_extended_conform.mp4'
    source.write_bytes(b'native')
    dst.write_bytes(b'derivative')
    url = reel._APPROVED_720_SOURCE
    spec = {'sources': {'extended': url}, 'segments': [{'source': 'extended'}],
            'source_quality_exceptions': {url: {'min_height': 720, 'approved_by': 'user', 'reason': 'explicit approval'}}}
    claim = {'run_id': 34401744962, 'artifact_id': 10124538360, 'source_url': url,
             'target': [1920, 1080], 'transform': 'lanczos-increase-crop/libx264-fast-crf16/audio-copy',
             'native_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
             'conformed_sha256': hashlib.sha256(dst.read_bytes()).hexdigest()}
    manifest = tmp_path / 'conform-reuse.json'
    manifest.write_text(json.dumps(claim))
    monkeypatch.setattr(reel, 'probe_size', lambda p: (1280, 720) if p == source else (1920, 1080))
    monkeypatch.setattr(reel, 'probe_duration', lambda p: 798.58)
    return source, dst, spec, claim, manifest


def test_valid_checkpoint_and_absent_default(tmp_path, monkeypatch):
    source, dst, spec, _, manifest = setup_checkpoint(tmp_path, monkeypatch)
    assert reel._verified_conform_reuse(source, dst, spec, 'extended', (1920, 1080), tmp_path)
    manifest.unlink()
    assert not reel._verified_conform_reuse(source, dst, spec, 'extended', (1920, 1080), tmp_path)


@pytest.mark.parametrize('changed', ['native', 'derived', 'recipe', 'run', 'duration', 'dimensions'])
def test_checkpoint_mismatch_is_blocked(tmp_path, monkeypatch, changed):
    source, dst, spec, claim, manifest = setup_checkpoint(tmp_path, monkeypatch)
    if changed == 'native': source.write_bytes(b'other')
    if changed == 'derived': dst.write_bytes(b'other')
    if changed == 'recipe': claim['transform'] = 'unknown'
    if changed == 'run': claim['run_id'] = 1
    if changed == 'duration': monkeypatch.setattr(reel, 'probe_duration', lambda p: 100 if p == source else 99)
    if changed == 'dimensions': monkeypatch.setattr(reel, 'probe_size', lambda p: (1280, 720))
    manifest.write_text(json.dumps(claim))
    with pytest.raises(reel.ReelError):
        reel._verified_conform_reuse(source, dst, spec, 'extended', (1920, 1080), tmp_path)


def test_other_source_never_reuses(tmp_path, monkeypatch):
    source, dst, spec, _, _ = setup_checkpoint(tmp_path, monkeypatch)
    spec['sources']['extended'] = 'https://example.com/other.mp4'
    assert not reel._verified_conform_reuse(source, dst, spec, 'extended', (1920, 1080), tmp_path)
