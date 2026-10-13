"""Pipeline selection must preserve cross-line faults and fail closed on uncertainty."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import production_test_scopes as S


@pytest.fixture(scope='module')
def catalog():
    return S.load_catalog(ROOT)


def chosen(rows, catalog):
    return S.select(ROOT, rows, *catalog)


def includes(report, target):
    return report['targets'] == ['tests'] or target in report['targets'] or target.split('::')[0] in report['targets']


def test_manifest_covers_real_inventory(catalog):
    assert set(catalog[1]) == {p.relative_to(ROOT).as_posix() for p in (ROOT / 'tests').glob('test_*.py')}


@pytest.mark.parametrize('line,own,excluded', [
    ('reel', 'test_match_reel.py', 'test_interview_segment_ruler.py'),
    ('interview', 'test_interview_clip.py', 'test_reel_narration.py'),
    ('explainer', 'test_explainer_budget.py', 'test_interview_segment_ruler.py'),
])
def test_actual_spec_families_select_own_requirements_without_unrelated_history(catalog, line, own, excluded):
    folder = {'reel': 'reels', 'interview': 'interviews', 'explainer': 'explainers'}[line]
    report = chosen([('M', f'specs/{folder}/episode.json')], catalog)
    assert report['mode'] == 'scoped' and report['scopes'] == [line]
    assert includes(report, 'tests/' + own)
    assert not includes(report, 'tests/' + excluded)
    for target in catalog[0]['always'] + catalog[0]['video_shared']:
        assert includes(report, target)
    assert not any('::' in t and t.split('::')[0] in report['targets'] for t in report['targets'])


def test_cross_line_spec_inventory_checks_are_not_lost(catalog):
    report = chosen([('M', 'specs/reels/episode.xhs.txt')], catalog)
    assert includes(report, 'tests/test_release_tag_collision.py')
    assert includes(report, 'tests/test_explainer.py::test_会发微信的工作流都要能触发Pages')
    assert includes(report, 'tests/test_interview_clip.py::test_会合语音的工作流都要装edge_tts')
    assert includes(report, 'tests/test_oncourt_collect.py::test_测试用到的第三方包都在dev依赖里')


def test_mixed_and_cross_line_move_select_both_sides(catalog):
    report = chosen([('D', 'specs/reels/old.json'), ('A', 'specs/interviews/new.json')], catalog)
    assert report['mode'] == 'scoped' and report['scopes'] == ['interview', 'reel']
    assert includes(report, 'tests/test_match_reel.py') and includes(report, 'tests/test_interview_clip.py')


@pytest.mark.parametrize('path,status', [
    ('assets/fonts/Inter-SemiBold.ttf', 'M'), ('assets/new-unclaimed.jpg', 'A'),
    ('assets/old-cover.jpg', 'D'), ('tools/unknown-new-module.py', 'A'),
    ('tools/build_match_reel.py', 'D'), ('src/tennislive/design_tokens.py', 'M'),
    ('src/tennislive/render/webcards.py', 'M'), ('src/tennislive/video/__init__.py', 'M'),
    ('data/unclaimed-evidence.txt', 'M'), ('pyproject.toml', 'M'),
    ('tests/test_match_reel.py', 'M'), (S.CATALOG, 'M'),
    ('tools/production_test_scopes.py', 'M'), ('.github/workflows/ci.yml', 'M'),
])
def test_uncertain_or_foundation_changes_are_full_even_when_mixed_with_one_film(catalog, path, status):
    report = chosen([('M', 'specs/reels/episode.json'), (status, path)], catalog)
    assert report['mode'] == 'full' and report['targets'] == ['tests']


def test_actual_shared_renderer_and_qc_consumers_are_covered(catalog, monkeypatch):
    consumers = S.dependency_consumers(ROOT, catalog[1])
    monkeypatch.setattr(S, 'dependency_consumers', lambda *_a: consumers)
    cases = json.loads((ROOT / 'data/evidence/production-test-scopes/cross-line-cases.json').read_text())['cases']
    for case in cases:
        report = chosen([('M', path) for path in case['changed_paths']], catalog)
        for target in case['required_tests']:
            assert includes(report, target), (case['id'], target, report)
        if case.get('required_mode') == 'full':
            assert report['mode'] == 'full'


def test_new_referenced_photo_and_real_evidence_follow_owning_spec(catalog, tmp_path, monkeypatch):
    monkeypatch.setattr(S, 'references', lambda root: ({'assets/new-cover.jpg': {'interview'}}, {'episode': {'interview'}}))
    report = chosen([('A', 'assets/new-cover.jpg'), ('A', 'data/evidence/episode/source-review.json')], catalog)
    assert report['mode'] == 'scoped' and report['scopes'] == ['interview']
    assert includes(report, 'tests/test_face_checks.py')
    assert includes(report, 'tests/test_publication_ledger.py')
    # Existing media must cover possible non-video users, even if a spec refers to it.
    assert chosen([('M', 'assets/new-cover.jpg')], catalog)['mode'] == 'full'


def test_plain_docs_are_small_but_production_copy_and_unknown_evidence_are_not_docs(catalog):
    report = chosen([('M', 'docs/usage.md')], catalog)
    assert report['mode'] == 'scoped' and report['scopes'] == []
    assert not includes(report, 'tests/test_match_reel.py')
    assert chosen([('M', 'specs/interviews/episode.xhs.txt')], catalog)['scopes'] == ['interview']
    assert chosen([('M', 'data/evidence/unknown/review.md')], catalog)['mode'] == 'full'


def test_real_git_diff_records_both_rename_sides_and_current_tree(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q'); git('config', 'user.name', 'Test'); git('config', 'user.email', 'test@example.invalid')
    source = tmp_path / 'specs/reels/old.json'; source.parent.mkdir(parents=True); source.write_text('{}')
    git('add', '.'); git('commit', '-qm', 'base'); base = git('rev-parse', 'HEAD')
    target = tmp_path / 'specs/interviews/new.json'; target.parent.mkdir(parents=True); source.rename(target)
    git('add', '-A'); git('commit', '-qm', 'move')
    before, after, rows = S.read_changes(tmp_path, base, 'HEAD')
    assert before == base and after == git('rev-parse', 'HEAD')
    assert set(rows) == {('D', 'specs/reels/old.json'), ('A', 'specs/interviews/new.json')}


def test_missing_base_empty_diff_and_stale_catalog_cannot_be_empty_green(catalog, monkeypatch):
    assert S.plan(ROOT, '0' * 40, 'HEAD')['targets'] == ['tests']
    assert S.plan(ROOT, 'HEAD', 'HEAD')['mode'] == 'full'
    monkeypatch.setattr(S, 'load_catalog', lambda root: (_ for _ in ()).throw(ValueError('new unclassified test')))
    assert S.plan(ROOT, 'HEAD', 'HEAD')['targets'] == ['tests']


def test_catalog_rejects_missing_duplicate_and_unsafe_targets(catalog, monkeypatch):
    read = Path.read_text
    replacement = [None]
    def edited(path, *args, **kwargs):
        return json.dumps(replacement[0]) if path == ROOT / S.CATALOG else read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', edited)
    for target in ('--ignore=tests', 'tests/test_match_reel.py', 'tests/test_match_reel.py::test_missing'):
        fake = deepcopy(catalog[0]); fake['always'].append(target); replacement[0] = fake
        with pytest.raises(ValueError):
            S.load_catalog(ROOT)
    fake = deepcopy(catalog[0]); fake['scopes']['reel'].remove('tests/test_match_reel.py'); replacement[0] = fake
    with pytest.raises(ValueError, match='inventory'):
        S.load_catalog(ROOT)


def test_ci_keeps_single_required_status_real_diff_full_schedule_and_nonempty_pytest():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    triggers = workflow.get('on', workflow.get(True))
    assert triggers['schedule'] and 'workflow_dispatch' in triggers
    steps = workflow['jobs']['test']['steps']
    selector = next(s for s in steps if s.get('id') == 'test_scope')
    history = next(s for s in steps if s.get('run') == 'python tests/production_history.py')
    run = next(s for s in steps if s.get('name') == '运行测试')
    assert run['env']['PYTHONPATH'] == 'src'
    assert steps.index(selector) < steps.index(history) < steps.index(run)
    assert '--full' in selector['run'] and '--base "$CI_BASE" --head HEAD' in selector['run']
    assert 'pull_request.base.sha' in selector['env']['CI_BASE'] and 'github.event.before' in selector['env']['CI_BASE']
    assert 'mapfile -t targets' in run['run'] and '"${targets[@]}"' in run['run']
    assert '--dist loadfile' in run['run'] and '--durations=25' in run['run']
    # Execute the actual shell block with a fake pytest: empty targets fail,
    # spaced/node arguments stay intact, and pytest failures remain failures.
    code = run['run'].replace('/tmp/production-test-scope/pytest-args.txt', '"$SCOPE_TARGETS"')
    import os, tempfile
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory); args = directory / 'targets.txt'; binary = directory / 'pytest'
        capture = directory / 'argv.json'
        binary.write_text('#!' + sys.executable + '\nimport os,json,sys\nfrom pathlib import Path\n'
                          'Path(os.environ["SCOPE_CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\nraise SystemExit(7)\n')
        binary.chmod(0o755)
        env = {**os.environ, 'PATH': str(directory) + os.pathsep + os.environ['PATH'],
               'SCOPE_TARGETS': str(args), 'SCOPE_CAPTURE': str(capture)}
        args.write_text('')
        assert subprocess.run(['bash', '-e', '-c', code], env=env, capture_output=True).returncode == 1
        args.write_text('tests/test_match_reel.py::test_赛场之上\n')
        assert subprocess.run(['bash', '-e', '-c', code], env=env, capture_output=True).returncode == 7
        assert json.loads(capture.read_text())[0] == 'tests/test_match_reel.py::test_赛场之上'


def test_function_local_and_dynamic_consumers_expand_lines_without_docstring_false_edges(tmp_path):
    paths = {
        'tools/ladder.py': 'def download():\n    return 1\n',
        'tests/test_reel.py': 'def test_download():\n    import importlib\n    importlib.import_module("ladder")\n',
        'tests/test_interview.py': 'def test_download():\n    from ladder import download\n',
        'tests/test_other.py': '"""A past example mentioned ladder.py; this is not a consumer."""\ndef test_model(): pass\n',
        'tests/test_global.py': 'def test_global(): pass\n',
        'tests/test_shared.py': 'def test_shared(): pass\n',
        'tests/test_production_test_scopes.py': 'def test_catalog(): pass\n',
    }
    for path, content in paths.items():
        file = tmp_path / path; file.parent.mkdir(parents=True, exist_ok=True); file.write_text(content)
    owners = {path: {'test_reel.py': 'reel', 'test_interview.py': 'interview',
                    'test_global.py': 'always', 'test_shared.py': 'video_shared'}.get(Path(path).name, 'other')
              for path in paths if path.startswith('tests/')}
    graph = S.dependency_consumers(tmp_path, owners)
    assert graph['tools/ladder.py'] == {'tests/test_reel.py', 'tests/test_interview.py'}
    catalog = {'always': ['tests/test_global.py'], 'video_shared': ['tests/test_shared.py'],
               'scopes': {line: [path for path, owner in owners.items() if owner == line] for line in (*S.LINES, 'other')}}
    report = S.select(tmp_path, [('M', 'tools/ladder.py')], catalog, owners)
    assert report['mode'] == 'scoped' and report['scopes'] == ['interview', 'reel']
    assert includes(report, 'tests/test_reel.py') and includes(report, 'tests/test_interview.py')


@pytest.mark.parametrize('line,node,fault', [
    ('interview', 'tests/test_en_subtitle_font.py::test_三条线的英文字体是同一支', 'font'),
    ('interview', 'tests/test_fixed_center_video_policy.py::test_interview_all_video_blocks_refuse_shift', 'crop'),
    ('reel', 'tests/test_segment_subtitle_bottom_windows.py::test_invalid_or_crossing_intervals_are_rejected', 'window'),
])
def test_real_selected_contracts_fail_when_their_quality_guard_is_broken(catalog, tmp_path, line, node, fault):
    folder = 'interviews' if line == 'interview' else 'reels'
    report = chosen([('M', f'specs/{folder}/episode.json')], catalog)
    assert includes(report, node)
    plugin = tmp_path / 'scope_fault.py'
    plugin.write_text('''import os
def pytest_configure(config):
    fault = os.environ.get('SCOPE_FAULT')
    if fault == 'font':
        import build_interview_clip as clip
        clip._ASS_NAME['en'] = 'wrong-font'
    elif fault == 'crop':
        from tennislive.video import crop_policy
        crop_policy.require_interview_center = lambda *_a, **_k: None
    elif fault == 'window':
        from tennislive.video import explainer
        native = explainer.write_subtitles
        def without_window(*a, **kw):
            kw.pop('bottom_margin_windows', None)
            return native(*a, **kw)
        explainer.write_subtitles = without_window
''')
    import os
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(map(str, (tmp_path, ROOT / 'src', ROOT / 'tools')))}
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'scope_fault', node]
    good = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    assert good.returncode == 0, good.stdout + good.stderr
    bad = subprocess.run(command, cwd=ROOT, env={**env, 'SCOPE_FAULT': fault}, capture_output=True, text=True)
    assert bad.returncode == 1 and 'FAILED ' + node in bad.stdout, bad.stdout + bad.stderr


def test_ci_event_schedule_exception_cannot_hide_real_schedule_publication(tmp_path):
    import os
    node = 'tests/test_match_reel.py::test_今日赛程没有发布出口了'
    plugin = tmp_path / 'scope_publication_fault.py'
    plugin.write_text('''import os
from pathlib import Path
def pytest_configure(config):
    if not os.environ.get('SCOPE_PUBLISH_FAULT'):
        return
    native = Path.read_text
    def changed(path, *a, **kw):
        text = native(path, *a, **kw)
        if path.name == 'ci.yml' and path.parent.name == 'workflows':
            text += '\\n  restored_schedule:\\n    runs-on: ubuntu-latest\\n    steps:\\n      - run: tennislive schedule --date 2026-10-13\\n'
        return text
    Path.read_text = changed
''')
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(map(str, (tmp_path, ROOT / 'src', ROOT / 'tools')))}
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'scope_publication_fault', node]
    good = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    assert good.returncode == 0, good.stdout + good.stderr
    bad = subprocess.run(command, cwd=ROOT, env={**env, 'SCOPE_PUBLISH_FAULT': '1'}, capture_output=True, text=True)
    assert (bad.returncode == 1 and 'FAILED ' + node in bad.stdout
            and '又在自动产今日赛程了' in bad.stdout), bad.stdout + bad.stderr
