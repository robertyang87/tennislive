"""The Zheng transport adapter must preserve the exact native film and findings."""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/import_approved_zheng_andreeva_beijing.py'
WORKFLOW = ROOT / '.github/workflows/import-approved-zheng-andreeva-beijing.yml'
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
    segments = [None] * 21
    for i, source, start, end in helper.EXPECTED_SOURCE_PLAN:
        segments[i] = {'source': source, 'start': start, 'end': end,
                       'fit': 'crop', 'cx': 0.5, 'track': False}
    for i, seconds in helper.EXPECTED_CARDS:
        segments[i] = {'title_card': 'approved card', 'seconds': seconds}
    helper.write(helper.SPEC, {
        'slug': helper.SLUG, 'cover': {'image': 'cover.jpg'},
        'sources': {'main': 'https://www.youtube.com/watch?v=Vq_UC0n5DKQ'},
        'track': False, 'outro': False, 'segments': segments,
    })
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
    helper.write(helper.AUDIO, {
        'render_json_sha256': helper.EXPECTED_RENDER,
        'pronunciation_status': helper.EXPECTED_PRONUNCIATION_STATUS,
        'unresolved_occurrences': 43, 'human_listening_claimed': False,
        'findings': [{'status': 'uncertain', 'method': 'asr_cross_checked'}],
    })
    helper.EXPECTED_AUDIO = helper.sha(helper.AUDIO)
    helper.native_evidence()
    return helper


@pytest.fixture
def revision_request(native_chain, monkeypatch):
    helper = native_chain
    pushed = {
        'at': '2026-10-11T15:51:05Z', 'run': 'https://github.com/robertyang87/tennislive/actions/runs/38152935043',
        'pushplus_receipt': helper.PREVIOUS_RECEIPT,
        'message_url': f'https://www.pushplus.plus/shortMessage/{helper.PREVIOUS_RECEIPT}',
    }
    ledger = {'slug': helper.SLUG, 'channel': 'pushplus', 'attempts': [{
        'key': f'pushplus:reel:{helper.SLUG}:{helper.PREVIOUS_FILM}',
        'fingerprint': helper.PREVIOUS_FILM, 'status': 'sent', **pushed,
    }]}
    baseline = {
        'schema': 'tennislive.reel-revision-baseline.v1', 'revision': helper.REVISION,
        'user_request': '要都用铺满画布的竖屏画面，重新做',
        'historical_evidence_only': True, 'previous_pushed': pushed,
        'previous_ledger': ledger,
        'previous_render': {
            'film_sha256': helper.PREVIOUS_FILM, 'film_bytes': 67425605,
            'video_url': f'https://github.com/{helper.REPOSITORY}/releases/download/reel-{helper.SLUG}/{helper.MASTER}',
        },
    }
    helper.write(helper.PREVIOUS_PUBLICATION, baseline)
    helper.EXPECTED_PREVIOUS_PUBLICATION = helper.sha(helper.PREVIOUS_PUBLICATION)
    helper.LEDGER.parent.mkdir(parents=True)
    helper.write(helper.LEDGER, ledger)
    size, digest = helper.EXPECTED_ASSETS[helper.MASTER]
    binding = {'revision': helper.REVISION,
               'previous_publication_path': str(helper.PREVIOUS_PUBLICATION),
               'previous_publication_sha256': helper.EXPECTED_PREVIOUS_PUBLICATION}
    helper.write(helper.AUTHORIZATION, {
        **binding, 'film_sha256': digest, 'film_bytes': size,
        'user_instruction': baseline['user_request'], 'unresolved_occurrences': 43,
        'human_listening_claimed': False,
        'pronunciation_status': helper.EXPECTED_PRONUNCIATION_STATUS,
    })
    assets = [{'name': name, 'bytes': n, 'sha256': sha,
               'chunks': [{'sha': str(i + 1) * 40, 'bytes': n}]}
              for i, (name, (n, sha)) in enumerate(helper.EXPECTED_ASSETS.items())]
    request = {
        **binding, 'slug': helper.SLUG, 'date': helper.DATE, 'bytes': size, 'sha256': digest,
        'spec_sha256': helper.EXPECTED_SPEC, 'qc_attestation_sha256': helper.EXPECTED_QC,
        'render_inputs_sha256': helper.EXPECTED_MANIFEST,
        'assets': assets, 'chunks': assets[0]['chunks'],
        'authorization_path': helper.AUTHORIZATION,
        'authorization_sha256': helper.sha(helper.AUTHORIZATION),
    }
    helper.write('request.json', request)
    monkeypatch.setattr(helper.subprocess, 'check_output', lambda *a, **kw: '')
    return helper, request


def test_workflow_executes_this_same_helper_in_both_stages():
    workflow = yaml.safe_load(WORKFLOW.read_text())
    job = workflow['jobs']['import']
    imports = [step['run'] for step in job['steps']
               if 'import_approved_' in step.get('run', '')]
    assert imports == [
        f'python tools/{HELPER.name} {stage} --request "$REQUEST"'
        for stage in ('assemble', 'release')
    ]
    assert job['env']['REQUEST'] == 'data/approved_reel_imports/zheng-andreeva-beijing-2026-final/request.json'
    assert job['if'] == "github.ref == 'refs/heads/main'"
    assert workflow['permissions'] == {'contents': 'write'}
    commands = '\n'.join(step.get('run', '') for step in job['steps'])
    assert 'full-frame-v2/final-audio-review-manifest.json' in commands
    assert ' ' + 'data/evidence/zheng-andreeva-beijing-2026-final/final-audio-review-manifest.json' not in commands


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
    render['video_url'] = f'https://github.com/{helper.REPOSITORY}/releases/download/{helper.RELEASE_TAG}/{helper.MASTER}'
    helper.write(helper.OUTDIR / 'render.json', render)
    rebound = dict(original_audio, render_json_sha256=helper.sha(helper.OUTDIR / 'render.json'))
    helper.write(helper.AUDIO, rebound)
    _, actual = helper.native_evidence()
    assert {k: v for k, v in actual.items() if k != 'render_json_sha256'} == {
        k: v for k, v in original_audio.items() if k != 'render_json_sha256'
    }
    assert actual['unresolved_occurrences'] == 43
    assert actual['human_listening_claimed'] is False
    actual['findings'][0]['status'] = 'human-pass'
    helper.write(helper.AUDIO, actual)
    with pytest.raises(RuntimeError, match='Original audio evidence changed'):
        helper.native_evidence()


def test_exact_old_sent_history_is_allowed_and_never_rewritten(revision_request):
    helper, request = revision_request
    before = helper.LEDGER.read_bytes()
    helper.no_prior_delivery(helper.manifest('request.json'))
    assert helper.LEDGER.read_bytes() == before
    assert helper.RELEASE_TAG == 'reel-zheng-andreeva-beijing-2026-final-full-frame-v2'


@pytest.mark.parametrize('status', ['sent', 'sending', 'uncertain', 'unknown', 'failed', None])
def test_any_new_attempt_rejected_even_with_exact_old_sent(revision_request, status):
    helper, request = revision_request
    ledger = helper.read(helper.LEDGER)
    ledger['attempts'].append({
        'key': f'pushplus:reel:{helper.SLUG}:{helper.EXPECTED_ASSETS[helper.MASTER][1]}',
        'fingerprint': helper.EXPECTED_ASSETS[helper.MASTER][1], 'status': status,
    })
    helper.write(helper.LEDGER, ledger)
    with pytest.raises(RuntimeError, match='Delivery ledger differs'):
        helper.no_prior_delivery(request)


@pytest.mark.parametrize('mutation', ['receipt', 'fingerprint', 'status', 'missing', 'extra'])
def test_old_history_exception_is_exact(revision_request, mutation):
    helper, request = revision_request
    if mutation == 'missing':
        helper.LEDGER.unlink()
    else:
        ledger = helper.read(helper.LEDGER)
        if mutation == 'extra':
            ledger['unknown_attempt'] = True
        else:
            key = {'receipt': 'pushplus_receipt', 'fingerprint': 'fingerprint', 'status': 'status'}[mutation]
            ledger['attempts'][0][key] = 'incorrect'
        helper.write(helper.LEDGER, ledger)
    with pytest.raises(RuntimeError, match='Delivery ledger differs'):
        helper.no_prior_delivery(request)


@pytest.mark.parametrize('tracked', [False, True])
def test_any_current_pushed_receipt_rejected(revision_request, monkeypatch, tracked):
    helper, request = revision_request
    if tracked:
        monkeypatch.setattr(helper.subprocess, 'check_output', lambda *a, **kw: f'output/another-day/reel/{helper.SLUG}/pushed.json\n')
    else:
        helper.write(helper.OUTDIR / 'pushed.json', {'pushplus_receipt': helper.PREVIOUS_RECEIPT})
    with pytest.raises(RuntimeError, match='Delivery already recorded'):
        helper.no_prior_delivery(request)


@pytest.mark.parametrize('field', ['revision', 'previous_publication_path', 'previous_publication_sha256'])
@pytest.mark.parametrize('target', ['request', 'authorization'])
def test_owner_and_request_both_bind_exact_revision(revision_request, field, target):
    helper, request = revision_request
    if target == 'request':
        request[field] = 'wrong'
    else:
        auth = helper.read(helper.AUTHORIZATION)
        auth[field] = 'wrong'
        helper.write(helper.AUTHORIZATION, auth)
        request['authorization_sha256'] = helper.sha(helper.AUTHORIZATION)
    helper.write('request.json', request)
    with pytest.raises(ValueError, match='previous-publication binding'):
        helper.manifest('request.json')


@pytest.mark.parametrize('mutation', [
    {'fit': 'contain'}, {'fit': 'full_source'}, {'cx': .55}, {'track': True},
    {'crop_track': []}, {'contain_keep': .65}, {'end': 155.5},
    {'intro_cx': .45}, {'crop_shift_x': .1}, {'square_pan': True},
    {'image': 'cover.jpg'},
])
def test_all_crop_and_complete_source_plan_required(native_chain, mutation):
    helper = native_chain
    spec = helper.read(helper.SPEC)
    helper.full_frame_spec(spec)
    spec['segments'][7].update(mutation)
    with pytest.raises(RuntimeError, match='Full-frame-v2'):
        helper.full_frame_spec(spec)


@pytest.mark.parametrize('mutation', [
    {'unresolved_occurrences': 0}, {'human_listening_claimed': True},
    {'pronunciation_status': 'all-pass'},
])
def test_actual_uncertainty_cannot_be_upgraded(native_chain, mutation):
    helper = native_chain
    audio = helper.read(helper.AUDIO)
    audio.update(mutation)
    helper.write(helper.AUDIO, audio)
    with pytest.raises(RuntimeError, match='pronunciation status changed'):
        helper.native_evidence()


def test_old_release_cannot_be_used_for_new_upload(native_chain):
    helper = native_chain
    size, _ = helper.EXPECTED_ASSETS[helper.MASTER]
    with pytest.raises(RuntimeError, match='Unexpected Release download URL'):
        helper.remote_verify({'size': size, 'url': f'https://github.com/{helper.REPOSITORY}/releases/download/reel-{helper.SLUG}/{helper.MASTER}'}, helper.MASTER)


def test_unarmed_new_film_cannot_start(native_chain):
    helper = native_chain
    helper.EXPECTED_SPEC = 'UNARMED'
    with pytest.raises(RuntimeError, match='Importer not armed'):
        helper.require_armed()


@pytest.mark.parametrize('field,value', [
    ('user_instruction', 'publish something else'), ('film_sha256', '0' * 64),
    ('film_bytes', 1), ('human_listening_claimed', True), ('unresolved_occurrences', 0),
])
def test_owner_instruction_cannot_authorize_different_film_or_review(revision_request, field, value):
    helper, request = revision_request
    auth = helper.read(helper.AUTHORIZATION)
    auth[field] = value
    helper.write(helper.AUTHORIZATION, auth)
    request['authorization_sha256'] = helper.sha(helper.AUTHORIZATION)
    helper.write('request.json', request)
    with pytest.raises(ValueError):
        helper.manifest('request.json')


def test_baseline_bytes_cannot_be_replaced(revision_request):
    helper, request = revision_request
    baseline = helper.read(helper.PREVIOUS_PUBLICATION)
    baseline['previous_ledger']['attempts'][0]['pushplus_receipt'] = 'wrong'
    helper.write(helper.PREVIOUS_PUBLICATION, baseline)
    with pytest.raises(RuntimeError, match='Pinned native evidence changed'):
        helper.no_prior_delivery(request)


def test_native_transport_cannot_overwrite_public_assets():
    tree = ast.parse(HELPER.read_text())
    assert not any(isinstance(node, ast.Constant) and node.value == '--clobber'
                   for node in ast.walk(tree))


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
