"""The Alcaraz Shanghai transport adapter must preserve the exact native film and findings."""
from __future__ import annotations

import ast
import importlib.util
import json
import zipfile
from pathlib import Path
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'tools/import_approved_bergs_alcaraz_shanghai.py'
WORKFLOW = ROOT / '.github/workflows/import-approved-bergs-alcaraz-shanghai.yml'
sys.path.insert(0, str(ROOT / 'tools'))


@pytest.fixture
def native_chain(tmp_path, monkeypatch):
    """Build synthetic evidence using the real render-input recorder, not copied logic."""
    module_spec = importlib.util.spec_from_file_location('alcaraz_transport_test', HELPER)
    helper = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(helper)
    monkeypatch.chdir(tmp_path)
    helper.OUTDIR.mkdir(parents=True)
    helper.SPEC.parent.mkdir(parents=True)
    helper.AUDIO.parent.mkdir(parents=True)
    Path('cover.jpg').write_bytes(b'original official cover fixture')
    helper.write(helper.SPEC, {'slug': helper.SLUG, 'cover': {'image': 'cover.jpg'},
        'sources': {'main': 'https://www.youtube.com/watch?v=2tMbUc2Kknk'},
        'track': False, 'outro': False, 'subtitle_bottom': 237,
        'segments': [{'source': 'main', 'start': 212.72, 'end': 230.10,
                      'fit': 'crop', 'cx': 0.5, 'track': False, 'subtitle_bottom': 237,
                      'narration': '本场复盘的合成测试字幕'}]})
    (helper.OUTDIR / 'subtitles.ass').write_bytes(b'original subtitle fixture')
    review = f'{helper.SLUG}-review.mp4'
    for name in (helper.MASTER, review):
        (helper.OUTDIR / name).write_bytes(f'synthetic film bytes: {name}'.encode())
    with zipfile.ZipFile(helper.OUTDIR / helper.VOICE_ARCHIVE, 'w') as archive:
        archive.writestr('synthetic-evidence.json', '{"synthetic_test_fixture":true}')
    helper.EXPECTED_ASSETS = {
        name: ((helper.OUTDIR / name).stat().st_size, helper.sha(helper.OUTDIR / name))
        for name in (helper.MASTER, review, helper.VOICE_ARCHIVE)
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
    assert job['env']['REQUEST'] == 'data/approved_reel_imports/bergs-alcaraz-shanghai-2026-r3/request.json'
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


@pytest.mark.parametrize('asset', ['master', 'review', 'voice_archive'])
def test_same_size_film_substitution_is_rejected(native_chain, asset):
    helper = native_chain
    name = {'master': helper.MASTER, 'review': f'{helper.SLUG}-review.mp4',
            'voice_archive': helper.VOICE_ARCHIVE}[asset]
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
    render['video_bytes'] = helper.EXPECTED_ASSETS[helper.MASTER][0]
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


@pytest.fixture
def exact_request(native_chain, monkeypatch):
    helper = native_chain
    size, digest = helper.EXPECTED_ASSETS[helper.MASTER]
    helper.write(helper.AUTHORIZATION, {
        'film_sha256': digest, 'film_bytes': size,
        'user_instruction': '做这个阿卡出局的赛场之上视频并推送微信',
        'pronunciation_status': helper.EXPECTED_PRONUNCIATION_STATUS,
        'unresolved_occurrences': helper.EXPECTED_UNRESOLVED,
        'human_listening_claimed': False,
    })
    assets = [{'name': name, 'bytes': size, 'sha256': digest,
               'chunks': [{'sha': str(i + 1) * 40, 'bytes': size}]}
              for i, (name, (size, digest)) in enumerate(helper.EXPECTED_ASSETS.items())]
    request = {
        'slug': helper.SLUG, 'date': helper.DATE, 'bytes': size, 'sha256': digest,
        'spec_sha256': helper.EXPECTED_SPEC,
        'qc_attestation_sha256': helper.EXPECTED_QC,
        'render_inputs_sha256': helper.EXPECTED_MANIFEST,
        'assets': assets, 'chunks': assets[0]['chunks'],
        'authorization_path': helper.AUTHORIZATION,
        'authorization_sha256': helper.sha(helper.AUTHORIZATION),
    }
    helper.write('request.json', request)
    monkeypatch.setattr(helper.subprocess, 'check_output', lambda *a, **kw: '')
    assert helper.manifest('request.json') == request
    helper.no_prior_delivery()
    return helper, request


@pytest.mark.parametrize('field', ['sha256', 'spec_sha256', 'qc_attestation_sha256',
                                  'render_inputs_sha256', 'authorization_sha256'])
def test_different_evidence_cannot_arm_request(exact_request, field):
    helper, request = exact_request
    request[field] = 'f' * 64
    helper.write('request.json', request)
    with pytest.raises((RuntimeError, ValueError)):
        helper.manifest('request.json')


@pytest.mark.parametrize('mutation', ['extra_asset', 'boolean_size', 'path_asset',
                                      'wrong_chunk_sum', 'top_level_chunks'])
def test_corrupt_transfer_descriptors_rejected(exact_request, mutation):
    helper, request = exact_request
    if mutation == 'extra_asset':
        request['assets'].append(dict(request['assets'][0]))
    elif mutation == 'boolean_size':
        request['assets'][0]['chunks'][0]['bytes'] = True
    elif mutation == 'path_asset':
        request['assets'][0]['name'] = '../unapproved.mp4'
    elif mutation == 'wrong_chunk_sum':
        request['assets'][0]['chunks'][0]['bytes'] -= 1
    else:
        request['chunks'] = []
    helper.write('request.json', request)
    with pytest.raises(ValueError):
        helper.manifest('request.json')


@pytest.mark.parametrize('status', ['sent', 'sending', 'uncertain', 'failed', None])
def test_no_first_delivery_history_exception(exact_request, status):
    helper, _ = exact_request
    ledger = Path(f'data/reel_publish_ledger/{helper.SLUG}.json')
    ledger.parent.mkdir(parents=True)
    helper.write(ledger, {'attempts': [{'status': status}]})
    with pytest.raises(RuntimeError, match='Delivery already recorded'):
        helper.no_prior_delivery()


@pytest.mark.parametrize('tracked', [True, False])
def test_any_existing_pushed_receipt_rejects_import(exact_request, monkeypatch, tracked):
    helper, _ = exact_request
    if tracked:
        monkeypatch.setattr(helper.subprocess, 'check_output',
            lambda *a, **kw: f'output/2026-10-01/reel/{helper.SLUG}/pushed.json\n')
    else:
        helper.write(helper.OUTDIR / 'pushed.json', {'pushplus_receipt': 'already-accepted'})
    with pytest.raises(RuntimeError, match='Delivery already recorded'):
        helper.no_prior_delivery()


def test_release_transport_rejects_another_master_url(native_chain):
    helper = native_chain
    before = helper.OUTDIR / 'render.before-release.json'
    before.write_bytes((helper.OUTDIR / 'render.json').read_bytes())
    render = helper.read(helper.OUTDIR / 'render.json')
    render['video_url'] = 'https://example.org/unreviewed.mp4'
    helper.write(helper.OUTDIR / 'render.json', render)
    with pytest.raises(RuntimeError, match='Unexpected master transport URL'):
        helper.native_evidence()


def test_workflow_requires_native_found_true_and_never_sends():
    job = yaml.safe_load(WORKFLOW.read_text())['jobs']['import']
    steps = job['steps']
    gate = next(s for s in steps if s.get('id') == 'publish_gate')
    assert gate['run'] == 'python tools/auto_push_gate.py --forced --changed "$OUTDIR/render.json"'
    assert any(s.get('if') == "steps.publish_gate.outputs.found != 'true'"
               and 'exit 1' in s.get('run', '') for s in steps)


def test_unarmed_actual_importer_refuses_network_transport():
    module_spec = importlib.util.spec_from_file_location('alcaraz_unarmed', HELPER)
    helper = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(helper)
    # Production becomes armed only after final evidence has been produced. This
    # assertion remains meaningful after that seal: no partial identity can arm it.
    helper.EXPECTED_AUDIO = ''
    with pytest.raises(RuntimeError, match='Importer not armed'):
        helper.require_armed()


@pytest.mark.parametrize('field,value', [('track', True), ('fit', 'contain'),
                                        ('cx', 0.4), ('subtitle_bottom', 600)])
def test_even_repinned_live_layout_cannot_degrade(native_chain, field, value):
    helper = native_chain
    spec = helper.read(helper.SPEC)
    spec['segments'][0][field] = value
    helper.write(helper.SPEC, spec)
    # A transport request cannot weaken this task's full portrait/caption rule,
    # even if someone updates the manifest/spec pins around the degraded recipe.
    helper.EXPECTED_SPEC = helper.sha(helper.SPEC)
    helper.write(helper.OUTDIR / 'render_inputs.json', helper.ri.build(
        helper.SPEC, helper.OUTDIR, helper.OUTDIR / helper.MASTER, Path.cwd()))
    helper.EXPECTED_MANIFEST = helper.sha(helper.OUTDIR / 'render_inputs.json')
    qc = helper.read(helper.OUTDIR / 'qc_attestation.json')
    qc.update(spec_sha256=helper.EXPECTED_SPEC,
              render_inputs_sha256=helper.EXPECTED_MANIFEST)
    helper.write(helper.OUTDIR / 'qc_attestation.json', qc)
    helper.EXPECTED_QC = helper.sha(helper.OUTDIR / 'qc_attestation.json')
    render = helper.read(helper.OUTDIR / 'render.json')
    render.update(qc_attestation_sha256=helper.EXPECTED_QC,
                  render_inputs_sha256=helper.EXPECTED_MANIFEST)
    helper.write(helper.OUTDIR / 'render.json', render)
    helper.EXPECTED_RENDER = helper.sha(helper.OUTDIR / 'render.json')
    with pytest.raises(RuntimeError, match='Live footage|caption placement'):
        helper.native_evidence()


@pytest.mark.parametrize('different_size', [False, True])
def test_remote_get_must_match_full_approved_bytes(native_chain, monkeypatch, different_size):
    helper = native_chain
    size, _ = helper.EXPECTED_ASSETS[helper.MASTER]
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def raise_for_status(self):
            return None
        def iter_content(self, block_size):
            yield b'x' * (size + int(different_size))
    monkeypatch.setattr(helper.requests, 'get', lambda *a, **kw: Response())
    asset = {'name': helper.MASTER, 'size': size,
             'url': f'https://github.com/{helper.REPOSITORY}/releases/download/reel-{helper.SLUG}/{helper.MASTER}'}
    with pytest.raises(RuntimeError, match='Remote asset differs; refusing overwrite'):
        helper.remote_verify(asset, helper.MASTER)


def test_remote_verification_rejects_unrelated_url_before_request(native_chain, monkeypatch):
    helper = native_chain
    def forbidden_network(*args, **kwargs):
        pytest.fail('An unexpected Release URL must never be requested')
    monkeypatch.setattr(helper.requests, 'get', forbidden_network)
    size, _ = helper.EXPECTED_ASSETS[helper.MASTER]
    with pytest.raises(RuntimeError, match='Unexpected Release download URL'):
        helper.remote_verify({'size': size, 'url': 'https://example.org/same-size.mp4'}, helper.MASTER)



def repin_synthetic_chain(helper, spec):
    """Issue a fresh complete synthetic chain so layout failures are not stale pins."""
    helper.write(helper.SPEC, spec)
    helper.EXPECTED_SPEC = helper.sha(helper.SPEC)
    helper.write(helper.OUTDIR / 'render_inputs.json', helper.ri.build(
        helper.SPEC, helper.OUTDIR, helper.OUTDIR / helper.MASTER, Path.cwd()))
    helper.EXPECTED_MANIFEST = helper.sha(helper.OUTDIR / 'render_inputs.json')
    qc = helper.read(helper.OUTDIR / 'qc_attestation.json')
    qc.update(spec_sha256=helper.EXPECTED_SPEC,
              render_inputs_sha256=helper.EXPECTED_MANIFEST)
    helper.write(helper.OUTDIR / 'qc_attestation.json', qc)
    helper.EXPECTED_QC = helper.sha(helper.OUTDIR / 'qc_attestation.json')
    render = helper.read(helper.OUTDIR / 'render.json')
    render.update(qc_attestation_sha256=helper.EXPECTED_QC,
                  render_inputs_sha256=helper.EXPECTED_MANIFEST)
    helper.write(helper.OUTDIR / 'render.json', render)
    helper.EXPECTED_RENDER = helper.sha(helper.OUTDIR / 'render.json')
    audio = helper.read(helper.AUDIO)
    audio['render_json_sha256'] = helper.EXPECTED_RENDER
    helper.write(helper.AUDIO, audio)
    helper.EXPECTED_AUDIO = helper.sha(helper.AUDIO)


def test_quiet_live_uses_recorded_source_review_without_fake_caption(native_chain):
    helper = native_chain
    spec = helper.read(helper.SPEC)
    segment = spec['segments'][0]
    segment.pop('narration')
    segment.pop('subtitle_bottom')
    segment['_quote_skip_why'] = 'Synthetic source-review fixture: ball/crowd sounds only; no foreground English.'
    repin_synthetic_chain(helper, spec)
    helper.native_evidence()
    assert 'subtitle_bottom' not in helper.read(helper.SPEC)['segments'][0]


@pytest.mark.parametrize('problem', ['placement_without_caption', 'missing_reason'])
def test_quiet_live_cannot_fake_placement_or_omit_source_reason(native_chain, problem):
    helper = native_chain
    spec = helper.read(helper.SPEC)
    segment = spec['segments'][0]
    segment.pop('narration')
    if problem == 'placement_without_caption':
        segment['_quote_skip_why'] = 'Synthetic source review: no foreground commentary.'
    else:
        segment.pop('subtitle_bottom')
    repin_synthetic_chain(helper, spec)
    with pytest.raises(RuntimeError, match='Quiet live segment'):
        helper.native_evidence()



@pytest.mark.parametrize('fps', ['50/1', '30/1'])
def test_import_rejects_a_non_native_master_frame_rate(native_chain, monkeypatch, fps):
    helper = native_chain
    monkeypatch.setattr(helper.subprocess, 'check_output', lambda *a, **kw:
        json.dumps({'streams': [{'width': 1080, 'height': 1440, 'r_frame_rate': fps}]}))
    with pytest.raises(RuntimeError, match='native 25 fps rendering'):
        helper.verify_master_geometry(helper.OUTDIR / helper.MASTER)


def test_import_accepts_native_25_fps_full_portrait(native_chain, monkeypatch):
    helper = native_chain
    seen = []
    def probe(args, **kwargs):
        seen.append(args)
        return json.dumps({'streams': [{'width': 1080, 'height': 1440,
                                        'r_frame_rate': '25/1'}]})
    monkeypatch.setattr(helper.subprocess, 'check_output', probe)
    helper.verify_master_geometry(helper.OUTDIR / helper.MASTER)
    assert seen[0][0] == 'ffprobe'
    assert seen[0][-1] == str(helper.OUTDIR / helper.MASTER)
    assert 'stream=width,height,r_frame_rate' in seen[0]


def test_import_rejects_a_landscape_master_even_with_native_fps(native_chain, monkeypatch):
    helper = native_chain
    monkeypatch.setattr(helper.subprocess, 'check_output', lambda *a, **kw:
        json.dumps({'streams': [{'width': 1920, 'height': 1080, 'r_frame_rate': '25/1'}]}))
    with pytest.raises(RuntimeError, match='master canvas changed'):
        helper.verify_master_geometry(helper.OUTDIR / helper.MASTER)



def test_request_requires_exact_pinned_voice_archive_hash(exact_request):
    helper, request = exact_request
    archive = next(a for a in request['assets'] if a['name'] == helper.VOICE_ARCHIVE)
    archive['sha256'] = 'a' * 64
    helper.write('request.json', request)
    with pytest.raises(ValueError, match='Asset identity mismatch'):
        helper.manifest('request.json')


def test_request_cannot_omit_voice_evidence_archive(exact_request):
    helper, request = exact_request
    request['assets'] = [a for a in request['assets'] if a['name'] != helper.VOICE_ARCHIVE]
    helper.write('request.json', request)
    with pytest.raises(ValueError, match='exactly the pinned assets'):
        helper.manifest('request.json')


def test_request_cannot_replace_voice_archive_with_another_zip(exact_request):
    helper, request = exact_request
    archive = next(a for a in request['assets'] if a['name'] == helper.VOICE_ARCHIVE)
    archive['name'] = 'unreviewed-evidence.zip'
    helper.write('request.json', request)
    with pytest.raises(ValueError, match='exactly the pinned assets'):
        helper.manifest('request.json')


def test_opaque_zip_reconstructs_exactly_and_only_master_is_probed(exact_request, monkeypatch):
    helper, request = exact_request
    payloads = {a['chunks'][0]['sha']: (helper.OUTDIR / a['name']).read_bytes()
                for a in request['assets']}
    archive_sha = helper.sha(helper.OUTDIR / helper.VOICE_ARCHIVE)
    for asset in request['assets']:
        (helper.OUTDIR / asset['name']).unlink()
    restored = []
    def restore(chunk, cache):
        path = cache / chunk['sha']
        path.write_bytes(payloads[chunk['sha']])
        restored.append(chunk['sha'])
        return path
    monkeypatch.setattr(helper, 'download_chunk', restore)
    monkeypatch.setattr(helper, 'run', lambda *args: None)
    probes = []
    monkeypatch.setattr(helper, 'verify_master_geometry', lambda path: probes.append(path))
    helper.assemble(Path('request.json'))
    assert set(restored) == set(payloads)
    assert probes == [helper.OUTDIR / helper.MASTER]
    assert helper.sha(helper.OUTDIR / helper.VOICE_ARCHIVE) == archive_sha
    provenance = helper.read(helper.OUTDIR / 'import-provenance.json')
    assert {a['name'] for a in provenance['assets']} == set(helper.EXPECTED_ASSETS)
    assert provenance['new_audio_review'] is False
    assert provenance['message_sent_by_importer'] is False



def test_original_native_render_without_transport_fields_is_valid(native_chain):
    helper = native_chain
    render, _ = helper.native_evidence()
    assert 'video_url' not in render
    assert 'video_bytes' not in render
    assert render['film_bytes'] == helper.EXPECTED_ASSETS[helper.MASTER][0]


@pytest.mark.parametrize('bytes_value', [None, 0, True, 'missing'])
def test_release_url_requires_exact_integer_transport_bytes(native_chain, bytes_value):
    helper = native_chain
    original = helper.OUTDIR / 'render.json'
    (helper.OUTDIR / 'render.before-release.json').write_bytes(original.read_bytes())
    render = helper.read(original)
    render['video_url'] = f'https://github.com/{helper.REPOSITORY}/releases/download/reel-{helper.SLUG}/{helper.MASTER}'
    if bytes_value != 'missing':
        render['video_bytes'] = bytes_value
    helper.write(original, render)
    with pytest.raises(RuntimeError, match='Master transport byte count changed'):
        helper.native_evidence()


@pytest.mark.parametrize('field,value', [('video_bytes', 0), ('video_url', None),
                                        ('video_url', '')])
def test_before_release_transport_field_absence_is_immutable(native_chain, field, value):
    helper = native_chain
    original = helper.OUTDIR / 'render.json'
    (helper.OUTDIR / 'render.before-release.json').write_bytes(original.read_bytes())
    render = helper.read(original)
    render[field] = value
    helper.write(original, render)
    with pytest.raises(RuntimeError, match='transport fields changed before Release|Unexpected master transport URL'):
        helper.native_evidence()
