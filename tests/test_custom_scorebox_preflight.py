"""真实同源自定义框校准必须在生产前检查，不能等整轮 CI 才发现。"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_match_reel as b  # noqa: E402
import probe_board as pb  # noqa: E402
import probe_sources as ps  # noqa: E402
import production_preflight as preflight  # noqa: E402

URL = 'https://example.test/official'
BOX = [89, 827, 552, 982]
SEGMENT_BOX = [89, 850, 552, 982]


def _spec():
    return {'slug': 'new-wuhan-reel', 'source_url': URL, 'scorebox': BOX,
            'topbar': {'line1': '2026 WTA1000 武汉 首轮'},
            'segments': [{'score_inset': True},
                         {'score_inset': True, 'scorebox': SEGMENT_BOX}]}


def _probe():
    return {'url': URL, 'board': {'version': 1, 'fps': 5, 't0': 2.1, 'frames': 24,
            'full_source_scan_claimed': False, 'source_window': [2.1, 6.84],
            'scans': [{'box': box, 'frames': 24, 'profiles': {
                'wta': {'present': 24, 'unresolved': 0, 'runs': [[24, 480, 480]]}}}
                for box in (BOX, SEGMENT_BOX)]}}


@pytest.mark.parametrize('corruption', ['wrong_url', 'wrong_profile', 'wrong_box',
                                      'missing_segment_scan', 'zero_frames', 'empty_runs'])
def test_corrupt_custom_calibration_fails_ci_and_production_before_copy(
        tmp_path, monkeypatch, corruption):
    spec, probe = _spec(), copy.deepcopy(_probe())
    if corruption == 'wrong_url':
        probe['url'] = 'https://example.test/different-video'
    elif corruption == 'wrong_profile':
        probe['board']['scans'][1]['profiles'] = {'atp': {'runs': [[24, 480, 480]]}}
    elif corruption == 'wrong_box':
        probe['board']['scans'][1]['box'][3] = 978
    elif corruption == 'missing_segment_scan':
        probe['board']['scans'].pop()
    elif corruption == 'zero_frames':
        probe['board']['scans'][1]['frames'] = 0
    else:
        probe['board']['scans'][1]['profiles']['wta']['runs'] = []
    assert not pb.scorebox_has_probe(probe, URL, SEGMENT_BOX, 'wta')
    path = tmp_path / 'new.json'
    path.write_text(json.dumps(spec))
    monkeypatch.setattr(b, 'probes_for_spec', lambda _spec: ({URL: probe}, []))
    monkeypatch.setattr(sys, 'argv', ['production_preflight.py', '--spec', str(path),
                                     '--column', '赛场之上'])
    monkeypatch.setattr(preflight, 'check_copy', lambda *a, **k: pytest.fail(
        'Copy/media work must not start with a missing custom scan'))
    with pytest.raises(SystemExit, match='自定义 scorebox.*缺少同源 wta 扫描'):
        preflight.main()


def test_bounded_same_source_scan_passes_without_claiming_full_film(monkeypatch, capsys):
    monkeypatch.setattr(b, 'probes_for_spec', lambda spec: ({URL: _probe()}, []))
    preflight.check_custom_scoreboxes(_spec())
    output = capsys.readouterr().out
    assert '2.100→6.840s' in output
    assert '不据此宣称全片通过' in output
    assert '范围外选段仍须原生逐段蒙版检查' in output


def test_calibrated_box_does_not_add_probe_requirement(monkeypatch):
    spec = _spec()
    spec['scorebox'] = list(pb.CALIBRATED['wta'][0])
    spec['segments'] = [{'score_inset': True}]
    monkeypatch.setattr(b, 'probes_for_spec', lambda _spec: pytest.fail(
        'Known calibrated boxes keep the existing probe policy'))
    preflight.check_custom_scoreboxes(spec)


@pytest.mark.parametrize('mode', ['cover', 'narration'])
def test_nonencoding_modes_keep_existing_no_probe_policy(monkeypatch, mode):
    monkeypatch.setenv(ps.MODE_ENV, mode)
    monkeypatch.setattr(b, 'probes_for_spec', lambda _spec: pytest.fail(
        'Cover/narration must not be blocked on a scoreboard probe'))
    preflight.check_custom_scoreboxes(_spec())


def test_multisource_scan_cannot_be_borrowed_from_primary(monkeypatch):
    supplement = 'https://example.test/supplement'
    spec = _spec()
    spec['sources'] = {'official': URL, 'supplement': supplement}
    spec['segments'][1]['source'] = 'supplement'
    monkeypatch.setattr(b, 'probes_for_spec', lambda _spec: ({URL: _probe()}, ['supplement']))
    with pytest.raises(SystemExit, match='supplement'):
        preflight.check_custom_scoreboxes(spec)


def test_actual_eala_bounded_scan_is_accepted_by_shared_production_rule(monkeypatch, capsys):
    spec = json.loads((ROOT / 'specs/reels/eala-shi.json').read_text())
    probe = json.loads((ROOT / 'output/2026-10-12/reel/eala-shi/probe.json').read_text())
    monkeypatch.setattr(b, 'probes_for_spec', lambda _spec: ({probe['url']: probe}, []))
    for box in pb.scoreboxes_by_url(spec, spec['sources'])[probe['url']]:
        assert pb.scorebox_has_probe(probe, probe['url'], box, 'wta')
    preflight.check_custom_scoreboxes(spec)
    assert '仅认领这一范围' in capsys.readouterr().out


def test_runner_sparse_probe_materialization_precedes_custom_gate(tmp_path, monkeypatch):
    """真实稀疏检出：同源证据在 HEAD 而不在磁盘，恢复 JSON 即可，不拉媒体。"""
    repo = tmp_path / 'runner'
    repo.mkdir()

    def git(*args):
        subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)

    git('init', '-q', '-b', 'main')
    rel = 'output/2026-10-12/reel/different-slug/probe.json'
    probe_path = repo / rel
    probe_path.parent.mkdir(parents=True)
    probe_path.write_text(json.dumps(_probe()))
    image_path = probe_path.with_name('contact_00.jpg')
    image_path.write_bytes(b'JPEG must stay outside the sparse checkout')
    (repo / 'specs').mkdir()
    (repo / 'specs/new.json').write_text(json.dumps(_spec()))
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
        'commit', '-q', '-m', 'Source-bound probe and contact')
    git('sparse-checkout', 'init', '--cone')
    git('sparse-checkout', 'set', 'specs')
    assert not probe_path.exists()
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit, match='缺少同源'):
        preflight.check_custom_scoreboxes(_spec())
    assert ps.materialize(_spec(), cwd=repo) == [rel]
    assert probe_path.exists() and not image_path.exists()
    preflight.check_custom_scoreboxes(_spec())
