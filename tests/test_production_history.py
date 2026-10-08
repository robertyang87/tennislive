"""Keep historical diagnostics separate from forward production quality gates."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest

import production_history as H

ROOT = Path(__file__).resolve().parents[1]
FROZEN_SLUGS = frozenset({
    'medvedev-24-titles-23-cities',
    'khachanov-auger-aliassime-beijing-2026-r1',
    'tabilo-paul-tokyo-2026-r1',
    'bu-cerundolo-beijing-2026-r1',
})


def _manifest():
    return json.loads((ROOT / 'data/production_history_snapshot.json').read_text(encoding='utf-8'))


def test_snapshot_is_narrow_and_each_rule_has_an_explicit_inventory_call():
    data = _manifest()
    assert data['frozen_revision'].startswith('c850697')
    rows = data['rows']
    assert {r['slug'] for r in rows} == FROZEN_SLUGS
    assert len(rows) == len(FROZEN_SLUGS)
    for row in rows:
        assert row['known_findings'] and row['output_evidence']
        assert any(p.endswith('/render.json') for p in row['files'])
        assert any(p.endswith('/qc_attestation.json') for p in row['files'])
        for rule, finding in row['known_findings'].items():
            assert finding.strip()
            file, function = rule.split('::')
            source = (ROOT / file).read_text(encoding='utf-8')
            node = next(n for n in ast.parse(source).body
                        if isinstance(n, ast.FunctionDef) and n.name == function)
            body = ast.get_source_segment(source, node)
            assert 'should_check' in body and rule in body, rule


def test_historical_diagnostics_are_reported_as_known_findings_not_qa_pass(record_property):
    report = H.diagnostics()
    assert report
    record_property('historical_diagnostics', json.dumps(report, ensure_ascii=False))
    H.print_diagnostics()


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    # Synthetic bytes keep the test meaningful when a historical recipe is
    # intentionally repaired later: the live inventory must then check it.
    slug = 'medvedev-24-titles-23-cities'
    rule = 'tests/test_match_reel.py::test_冷开场不许随手取源片开头'
    folder = f'output/2026-09-30/reel/{slug}'
    spec = {'slug': slug, 'cover': {'eyebrow': '网球有故事'},
            'segments': [{'start': 0, 'end': 2}]}
    receipt = {'pushplus_receipt': 'synthetic-receipt', 'at': '2026-09-30T09:43:31Z'}
    ledger = {'slug': slug, 'attempts': [{'status': 'sent', **receipt}]}
    contents = {
        f'specs/reels/{slug}.json': json.dumps(spec),
        f'specs/reels/{slug}.xhs.txt': 'Historical copy',
        f'data/reel_publish_ledger/{slug}.json': json.dumps(ledger),
        f'{folder}/pushed.json': json.dumps(receipt),
        f'{folder}/render.json': '{}',
        f'{folder}/qc_attestation.json': '{}',
    }
    files = {}
    for rel, text in contents.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        files[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
    row = {'slug': slug, 'spec_path': f'specs/reels/{slug}.json',
           'copy_path': f'specs/reels/{slug}.xhs.txt',
           'ledger_path': f'data/reel_publish_ledger/{slug}.json',
           'pushed_path': f'{folder}/pushed.json', 'receipt': receipt['pushplus_receipt'],
           'published_at': receipt['at'], 'files': files,
           'output_evidence': sorted(p for p in files if p.startswith('output/')),
           'known_findings': {rule: 'Synthetic frozen known finding'}}
    asset = tmp_path / 'assets/frozen.jpg'
    asset.parent.mkdir(); asset.write_bytes(b'synthetic image bytes')
    oid = hashlib.sha1(b'blob ' + str(asset.stat().st_size).encode() + b'\0' + asset.read_bytes()).hexdigest()
    identity = {'mode': '100644', 'oid': oid}
    row['repository_inputs'] = {'assets/frozen.jpg': identity, 'assets/missing.jpg': None,
                                f'{folder}/probe.json': None}
    row['output_repository_paths'] = []
    index = {'assets/frozen.jpg': {**identity, 'skip_worktree': False}}
    monkeypatch.setattr(H, '_git_entries', lambda pathspecs: dict(index))
    manifest = tmp_path / 'data/production_history_snapshot.json'
    manifest.write_text(json.dumps({'version': 1, 'rows': [row]}), encoding='utf-8')
    monkeypatch.setattr(H, 'ROOT', tmp_path)
    monkeypatch.setattr(H, 'MANIFEST', manifest)
    assert not H.should_check(rule, tmp_path / row['spec_path'])
    row['_test_index'] = index  # test-only access to the simulated local index
    return tmp_path, row, rule


@pytest.mark.parametrize('field', ['spec_path', 'copy_path', 'pushed_path', 'ledger_path'])
def test_changed_bound_input_is_checked_again(frozen, field):
    root, row, rule = frozen
    path = root / row[field]
    path.write_bytes(path.read_bytes() + b'\n')
    assert H.should_check(rule, root / row['spec_path'])


def test_changed_or_removed_qc_evidence_is_checked_again(frozen):
    root, row, rule = frozen
    path = root / next(p for p in row['files'] if p.endswith('/qc_attestation.json'))
    path.unlink()
    assert H.should_check(rule, root / row['spec_path'])


def test_new_run_evidence_is_checked_again(frozen):
    root, row, rule = frozen
    path = root / f"output/2026-10-01/reel/{row['slug']}/render.json"
    path.parent.mkdir(parents=True); path.write_text('{}')
    assert H.should_check(rule, root / row['spec_path'])


def test_new_slug_unknown_rule_or_copied_snapshot_is_never_exempt(frozen):
    root, row, rule = frozen
    path = root / 'specs/reels/new-production.json'
    shutil.copyfile(root / row['spec_path'], path)
    assert H.should_check(rule, path)
    assert H.should_check('new-rule', root / row['spec_path'])
    assert H.should_check(rule, root.parent / row['spec_path'])


def test_even_rehashed_unsent_receipt_cannot_become_a_historical_publication(frozen):
    root, row, rule = frozen
    ledger_path = root / row['ledger_path']
    ledger = json.loads(ledger_path.read_text())
    for attempt in ledger['attempts']:
        attempt['status'] = 'failed'
    ledger_path.write_text(json.dumps(ledger))
    data = json.loads(H.MANIFEST.read_text())
    data['rows'][0]['files'][row['ledger_path']] = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    H.MANIFEST.write_text(json.dumps(data))
    assert H.should_check(rule, root / row['spec_path'])


def test_broken_or_missing_snapshot_fails_closed(frozen):
    root, row, rule = frozen
    H.MANIFEST.write_text('{bad')
    assert H.should_check(rule, root / row['spec_path'])
    H.MANIFEST.unlink()
    assert H.should_check(rule, root / row['spec_path'])


def test_no_runtime_or_workflow_imports_history_exemption():
    for folder in ('tools', 'src', '.github/workflows'):
        for path in (ROOT / folder).rglob('*'):
            if path.suffix in {'.py', '.sh', '.yml', '.yaml'}:
                source = path.read_text(encoding='utf-8')
                if path == ROOT / '.github/workflows/ci.yml':
                    # Only the explicitly visible diagnostic test is allowed;
                    # no runtime workflow may use the exemption helper.
                    source = source.replace(
                        'python tests/production_history.py', '')
                assert 'production_history' not in source, path


def test_frozen_old_recipe_is_still_rejected_by_real_runtime_gate(frozen):
    import build_match_reel as R
    root, row, rule = frozen
    assert not H.should_check(rule, root / row['spec_path'])
    old = json.loads((root / row['spec_path']).read_text())
    assert R.unvoiced_quote_problem(old), 'CI history must never bypass production validation'


def test_ci_prints_historical_diagnostics_before_aggregate_tests():
    import yaml
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text(encoding='utf-8'))
    calls = []
    for job in workflow['jobs'].values():
        for step in job.get('steps', []):
            calls.append(str(step.get('run') or ''))
    command = 'python tests/production_history.py'
    diagnostics = [i for i, run in enumerate(calls) if run.strip() == command]
    aggregate = [i for i, run in enumerate(calls) if '--dist loadfile' in run]
    assert len(diagnostics) == 1 and aggregate and diagnostics[0] < min(aggregate)


def test_diagnostic_command_reports_known_findings_without_running_media(monkeypatch, capsys):
    monkeypatch.setattr(H, 'diagnostics', lambda: [{'slug': 'old-example', 'rule': 'known-rule',
        'state': 'frozen_known_finding', 'finding': 'Known unresolved historical finding'}])
    H.print_diagnostics()
    output = capsys.readouterr().out
    assert 'not a QA pass or old-media revalidation' in output
    assert 'Known unresolved historical finding' in output


def test_previously_absent_cover_addition_reactivates_checks(frozen):
    root, row, rule = frozen
    (root / 'assets/missing.jpg').write_bytes(b'new synthetic cover')
    assert H.should_check(rule, root / row['spec_path'])


def test_materialized_asset_changed_without_staging_reactivates_checks(frozen):
    root, row, rule = frozen
    (root / 'assets/frozen.jpg').write_bytes(b'different synthetic cover')
    assert H.should_check(rule, root / row['spec_path'])


def test_indexed_asset_identity_change_reactivates_checks(frozen):
    root, row, rule = frozen
    row['_test_index']['assets/frozen.jpg']['oid'] = 'e' * 40
    assert H.should_check(rule, root / row['spec_path'])


def test_previously_absent_probe_addition_reactivates_checks(frozen):
    root, row, rule = frozen
    path = root / next(p for p, v in row['repository_inputs'].items() if p.endswith('/probe.json'))
    path.write_text('{}')
    assert H.should_check(rule, root / row['spec_path'])


def test_new_indexed_output_binary_is_detected_without_materializing_it(frozen, monkeypatch):
    root, row, rule = frozen
    rel = f"output/2026-10-01/reel/{row['slug']}/new-film.mp4"
    row['_test_index'][rel] = {'mode': '100644', 'oid': 'f' * 40, 'skip_worktree': True}
    assert not (root / rel).exists()
    monkeypatch.setattr(H, '_worktree_blob', lambda *a: pytest.fail('must reject new path before reading any binary'))
    assert H.should_check(rule, root / row['spec_path'])


def test_sparse_binary_uses_matching_git_identity_but_local_deletion_does_not(frozen):
    root, row, rule = frozen
    path = root / 'assets/frozen.jpg'; path.unlink()
    assert H.should_check(rule, root / row['spec_path'])
    row['_test_index']['assets/frozen.jpg']['skip_worktree'] = True
    assert not H.should_check(rule, root / row['spec_path'])


def test_git_index_reader_is_local_read_only_and_preserves_sparse_status(monkeypatch):
    from types import SimpleNamespace
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=(
            'H 100644 ' + 'a' * 40 + ' 0\tassets/a.jpg\0' +
            'S 100644 ' + 'b' * 40 + ' 0\toutput/date/reel/slug/movie.mp4\0').encode())
    monkeypatch.setattr(H.subprocess, 'run', run)
    entries = H._git_entries(['assets/a.jpg', 'output/*/reel/slug/*'])
    assert entries['assets/a.jpg']['skip_worktree'] is False
    assert entries['output/date/reel/slug/movie.mp4']['skip_worktree'] is True
    args, kwargs = calls[0]
    assert 'ls-files' in args and '--stage' in args and '-z' in args
    assert kwargs['env']['GIT_NO_LAZY_FETCH'] == '1'
