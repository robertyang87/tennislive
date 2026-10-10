"""The Zheng transport adapter must preserve the exact native film and findings."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/import_approved_zheng_mertens_beijing.py'
WORKFLOW = ROOT / '.github/workflows/import-approved-zheng-mertens-beijing.yml'
sys.path.insert(0, str(ROOT / 'tools'))


@pytest.fixture
def native_chain(tmp_path, monkeypatch):
    """Build synthetic evidence using the real render-input recorder, not copied logic."""
    module_spec = importlib.util.spec_from_file_location('zheng_transport_test', HELPER)
    helper = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(helper)
    monkeypatch.chdir(tmp_path)
    helper.OUTDIR.mkdir(parents=True)
    helper.SPEC.parent.mkdir(parents=True)
    helper.AUDIO.parent.mkdir(parents=True)
    Path('cover.jpg').write_bytes(b'original official cover fixture')
    helper.write(helper.SPEC, {'slug': helper.SLUG, 'cover': {'image': 'cover.jpg'}})
    (helper.OUTDIR / 'subtitles.ass').write_bytes(b'original subtitle fixture')
    review = f'{helper.SLUG}-review.mp4'
    for name in (helper.MASTER, review):
        (helper.OUTDIR / name).write_bytes(f'synthetic film bytes: {name}'.encode())
    helper.EXPECTED_ASSETS = {
        name: ((helper.OUTDIR / name).stat().st_size, helper.sha(helper.OUTDIR / name))
        for name in (helper.MASTER, review)
    }
    helper.EXPECTED_SPEC = helper.sha(helper.SPEC)
    helper.write(helper.OUTDIR / 'render_inputs.json', helper.ri.build(
        helper.SPEC, helper.OUTDIR, helper.OUTDIR / helper.MASTER, tmp_path))
    helper.EXPECTED_MANIFEST = helper.sha(helper.OUTDIR / 'render_inputs.json')
    size, digest = helper.EXPECTED_ASSETS[helper.MASTER]
    helper.write(helper.OUTDIR / 'qc_attestation.json', {
        'status': 'pass', 'spec_sha256': helper.EXPECTED_SPEC,
        'render_inputs_sha256': helper.EXPECTED_MANIFEST,
        'film_sha256': digest, 'film_bytes': size,
    })
    helper.EXPECTED_QC = helper.sha(helper.OUTDIR / 'qc_attestation.json')
    helper.write(helper.OUTDIR / 'render.json', {
        'qc_attestation_sha256': helper.EXPECTED_QC,
        'render_inputs_sha256': helper.EXPECTED_MANIFEST,
        'film_sha256': digest, 'film_bytes': size,
        'video_url': '', 'video_bytes': size,
    })
    helper.EXPECTED_RENDER = helper.sha(helper.OUTDIR / 'render.json')
    helper.EXPECTED_UNRESOLVED = 2
    helper.EXPECTED_PRONUNCIATION_STATUS = 'uncertain-no-human-listening'
    helper.write(helper.AUDIO, {
        'render_json_sha256': helper.EXPECTED_RENDER,
        'pronunciation_status': helper.EXPECTED_PRONUNCIATION_STATUS,
        'unresolved_occurrences': 2, 'human_listening_claimed': False,
        'findings': [{'status': 'uncertain', 'method': 'asr_cross_checked'}],
    })
    helper.EXPECTED_AUDIO = helper.sha(helper.AUDIO)
    helper.native_evidence()
    return helper


def test_workflow_executes_this_same_helper_in_both_stages():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job = workflow['jobs']['import']
    imports = [step['run'] for step in job['steps']
               if 'import_approved_' in step.get('run', '')]
    assert imports == [
        f'python tools/{HELPER.name} {stage} --request "$REQUEST"'
        for stage in ('assemble', 'release')
    ]
    assert job['env']['REQUEST'] == 'data/approved_reel_imports/zheng-mertens-beijing-2026-sf/request.json'
    assert job['if'] == "github.ref == 'refs/heads/main'"
    assert workflow['permissions'] == {'contents': 'write'}


@pytest.mark.parametrize('target', ['spec', 'qc', 'asset', 'subtitles'])
def test_native_byte_substitution_is_rejected(native_chain, target):
    helper = native_chain
    path = {
        'spec': helper.SPEC,
        'qc': helper.OUTDIR / 'qc_attestation.json',
        'asset': Path('cover.jpg'),
        'subtitles': helper.OUTDIR / 'subtitles.ass',
    }[target]
    path.write_bytes(path.read_bytes() + b' substituted bytes')
    with pytest.raises(RuntimeError):
        helper.native_evidence()


@pytest.mark.parametrize('asset', ['master', 'review'])
def test_same_size_film_substitution_is_rejected(native_chain, asset):
    helper = native_chain
    name = helper.MASTER if asset == 'master' else f'{helper.SLUG}-review.mp4'
    path = helper.OUTDIR / name
    path.write_bytes(b'x' * path.stat().st_size)
    with pytest.raises(RuntimeError, match='Asset bytes differ'):
        helper.verify_file(path, name)


def test_release_rebind_preserves_uncertain_findings(native_chain):
    helper = native_chain
    before = helper.OUTDIR / 'render.before-release.json'
    before.write_bytes((helper.OUTDIR / 'render.json').read_bytes())
    original_audio = helper.read(helper.AUDIO)
    render = helper.read(helper.OUTDIR / 'render.json')
    render['video_url'] = f'https://github.com/{helper.REPOSITORY}/releases/download/reel-{helper.SLUG}/{helper.MASTER}'
    helper.write(helper.OUTDIR / 'render.json', render)
    rebound = dict(original_audio, render_json_sha256=helper.sha(helper.OUTDIR / 'render.json'))
    helper.write(helper.AUDIO, rebound)
    _, actual = helper.native_evidence()
    assert {k: v for k, v in actual.items() if k != 'render_json_sha256'} == {
        k: v for k, v in original_audio.items() if k != 'render_json_sha256'
    }
    assert actual['unresolved_occurrences'] == 2
    assert actual['human_listening_claimed'] is False
    actual['findings'][0]['status'] = 'human-pass'
    helper.write(helper.AUDIO, actual)
    with pytest.raises(RuntimeError, match='Original audio evidence changed'):
        helper.native_evidence()


def test_transport_has_no_message_sending_or_dispatch():
    tree = ast.parse(HELPER.read_text())
    prohibited = {'send', 'send_pushplus', 'pushplus', 'dispatch', 'workflow_dispatch'}
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name in prohibited for node in ast.walk(tree))
    local_stages = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        assert not (isinstance(node.func, ast.Attribute) and node.func.attr in prohibited)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == 'native':
                assert node.func.attr in {'prepare_copy', 'push_meta', 'build_html', 'copy_page_url'}
            if node.func.value.id == 'requests':
                assert node.func.attr == 'get'
        strings = [argument.value for argument in node.args
                   if isinstance(argument, ast.Constant) and isinstance(argument.value, str)]
        if isinstance(node.func, ast.Name) and node.func.id == 'run' and 'tools/push_reel.py' in strings:
            assert '--stage' in strings
            local_stages.append(strings[strings.index('--stage') + 1])
    assert local_stages == ['check', 'check', 'page']
    workflow = yaml.safe_load(WORKFLOW.read_text())
    commands = '\n'.join(step.get('run', '') for step in workflow['jobs']['import']['steps'])
    for forbidden in ('gh workflow run', '/dispatches', '--stage push'):
        assert forbidden not in commands
