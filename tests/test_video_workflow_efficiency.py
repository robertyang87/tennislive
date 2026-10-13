"""三条视频线缓存/传输合同：检查执行配置，不把注释当成优化。"""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def _steps(name):
    workflow = yaml.safe_load((ROOT / '.github/workflows' / name).read_text())
    return [step for job in workflow['jobs'].values() for step in job['steps']]


@pytest.mark.parametrize('name', ['match-reel.yml', 'interview-clip.yml', 'explainer.yml'])
def test_media_artifacts_skip_recompression(name):
    uploads = [s for s in _steps(name)
               if s.get('uses', '').startswith('actions/upload-artifact@')]
    assert uploads
    for step in uploads:
        assert step['with']['compression-level'] == 0
        assert step['with']['path']  # 禁止以不传产物的方式节省时间。


@pytest.mark.parametrize('name,consumer', [
    ('interview-clip.yml', '剪 + 烧字幕'),
    ('explainer.yml', '生成解说视频'),
])
def test_shared_tts_cache_survives_runner_restarts(name, consumer):
    steps = _steps(name)
    caches = [s for s in steps if s.get('uses') == 'actions/cache@v4'
              and s.get('with', {}).get('path') == '~/.cache/tennislive-tts']
    assert len(caches) == 1
    cache = caches[0]
    assert steps.index(cache) < next(i for i, s in enumerate(steps) if s.get('name') == consumer)
    key = cache['with']['key']
    assert 'inputs.slug' in key
    assert 'hashFiles(' in key
    assert 'github.run_id' not in key  # 完全相同输入不重复保存缓存。
    fallback = cache['with']['restore-keys']
    assert 'inputs.slug' in fallback
    assert 'src/tennislive/video/tts.py' in fallback
    assert 'src/tennislive/video/azure_tts.py' in fallback
    if name == 'interview-clip.yml':
        assert cache['if'] == "github.event.inputs.mode == 'render'"
        assert "specs/interviews/{0}.json" in key
    else:
        assert 'inputs.voice' in key and 'inputs.rate' in key
        assert "'hawkeye'" in key


def test_cleanup_keeps_source_evidence_and_removes_media(tmp_path):
    """执行 workflow 的实际 shell，防止前缀清理误删永久溯源证据。"""
    import os
    import subprocess

    steps = _steps('match-reel.yml')
    cleanup = next(s['run'] for s in steps if s.get('name') == '丢掉不进仓库的中间物')
    keep = ['source_evidence.txt', 'source_identity.json', 'source_photo.json',
            'source_map.json', 'poster.jpg', 'render.json', 'cover_src/source.jpg']
    drop = ['source.mp4', 'source_r1.mp4', 'source_iv.mkv', 'source.f251.webm',
            'source.f140.m4a', 'source_r2_conform.mp4', 'source.f137.mp4.part',
            'source.mp4.ytdl', 'voice_00.mp3', 'frames/frame.jpg']
    for name in keep + drop:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'evidence-or-media')
    script = cleanup.replace('${{ steps.paths.outputs.outdir }}', '${TEST_OUTDIR}')
    result = subprocess.run(['bash', '-e', '-c', script], capture_output=True, text=True,
                            env={**os.environ, 'TEST_OUTDIR': str(tmp_path)})
    assert result.returncode == 0, result.stderr
    assert all((tmp_path / name).is_file() for name in keep)
    assert all(not (tmp_path / name).exists() for name in drop)


def test_reel_failure_artifact_keeps_source_evidence():
    from fnmatch import fnmatch

    upload = next(s for s in _steps('match-reel.yml')
                  if s.get('name') == '上传 artifact'
                  and s.get('uses', '').startswith('actions/upload-artifact@'))
    root = '${{ steps.paths.outputs.outdir }}/'
    patterns = [line[len('!' + root):] for line in upload['with']['path'].splitlines()
                if line.startswith('!' + root)]
    assert patterns
    for name in ('source_evidence.txt', 'source_identity.json', 'source_photo.json'):
        assert not any(fnmatch(name, pattern) for pattern in patterns)
    for name in ('source_av.mp4', 'source.f137.mp4.part', 'source.f251.webm',
                 'source_iv.mkv', 'source.mp4.ytdl', 'frames/frame.jpg'):
        assert any(fnmatch(name, pattern) for pattern in patterns)


def test_official_photo_checkout_has_inputs_and_output_without_media(tmp_path):
    """用实际 git sparse-checkout 验匹配语义，防根文件或产物格静默漏检出。"""
    import subprocess

    step = next(s for s in _steps('official-social-images.yml')
                if s.get('uses', '').startswith('actions/checkout@'))
    assert step['with']['sparse-checkout-cone-mode'] is False
    keep = ['pyproject.toml', 'README.md', 'src/tennislive/__init__.py',
            'tools/collect_official_social_images.py', 'tools/check_staged_file_sizes.py',
            'tools/nudge_stale_ticks.sh', 'data/official_social_image_watch.json',
            'data/official_social_image_results/demo.json', 'specs/reels/demo.json',
            'assets/reel/official-social/demo.jpg', 'output/day/reel/demo/render.json']
    drop = ['assets/reel/other.jpg', 'assets/fonts/heavy.ttf',
            'assets/other/clip.mp4', 'output/day/reel/demo/demo.mp4',
            'output/day/reel/demo/source.mp4', 'tests/test_unneeded.py', 'docs/history.md']
    def git(*args, **kwargs):
        return subprocess.run(['git', *args], cwd=tmp_path, check=True,
                              capture_output=True, text=True, **kwargs)
    git('init', '-q')
    for name in keep + drop:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    (tmp_path / 'specs/reels/demo.json').write_text(
        '{"cover":{"portrait":{"frame_at":12.3}}}')
    (tmp_path / 'output/day/reel/demo/render.json').write_text('{}')
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture')
    git('sparse-checkout', 'init', '--no-cone')
    git('sparse-checkout', 'set', '--no-cone', '--stdin',
        input=step['with']['sparse-checkout'])
    assert all((tmp_path / name).is_file() for name in keep)
    assert all(not (tmp_path / name).exists() for name in drop)
    from tennislive.research.official_social_images import monitor_trigger_ready
    watch = {'trigger': {'type': 'video-ready-cover-pending',
                         'spec': 'specs/reels/demo.json',
                         'render_manifest': 'output/day/reel/demo/render.json'}}
    assert monitor_trigger_ready(watch, tmp_path) == (True, 'video-ready-cover-pending')
    # 新的官方图片/结果仍在可提交范围，而非 git add 返回0却只报稀疏警告。
    new = ['assets/reel/official-social/new.jpg', 'data/official_social_image_results/new.json']
    for name in new:
        (tmp_path / name).write_text('new evidence')
    git('add', *new)
    assert set(git('diff', '--cached', '--name-only').stdout.splitlines()) == set(new)


def _transport_bundle(path, slug='test-reel'):
    import hashlib, json, zipfile
    from tennislive.video.tts import tts_request
    from tennislive.video.tts_bundle import SCHEMA, implementation_identity, request_id
    request = tts_request('测试。', 'zh-CN-YunjianNeural', '+6%', '+0Hz')
    rid = request_id(request)
    audio = b'transport-only bytes; actual decode covered by bundle tests'
    marks = json.dumps([{'text': '测试', 'offset': 0, 'duration': 1000000}]).encode()
    manifest = {'schema': SCHEMA, 'artifact_kind': 'native_tts_inputs', 'quality_approval': False,
        'implementation': implementation_identity(), 'metadata': {'slug': slug, 'kind': 'reel_native_tts'},
        'entries': [{'request': request, 'request_id': rid,
            'audio_sha256': hashlib.sha256(audio).hexdigest(),
            'marks_sha256': hashlib.sha256(marks).hexdigest(), 'duration_seconds': 1}]}
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('manifest.json', json.dumps(manifest))
        z.writestr(f'requests/{rid}/audio.mp3', audio)
        z.writestr(f'requests/{rid}/marks.json', marks)


def test_frozen_tts_transport_is_content_addressed_and_never_clobbers(tmp_path, monkeypatch):
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('reel_tts_release', ROOT / 'tools/reel_tts_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = tmp_path / 'producer-slug.zip'
    _transport_bundle(bundle)
    sha = module.digest(bundle)
    metadata = tmp_path / 'record.json'
    record = {'schema': module.SCHEMA, 'artifact_kind': 'native_tts_inputs',
              'quality_approval': False, 'bundle_sha256': sha, 'request_count': 1}
    metadata.write_text(json.dumps({'tts_bundle': record, 'duration': 10}))
    calls = []
    uploaded = {}

    def fake_gh(*args):
        calls.append(args)
        if args[:2] == ('release', 'view'):
            return json.dumps({'assets': [{'name': module.ASSET}] if uploaded else []})
        if args[:2] == ('release', 'upload'):
            path = Path(args[3])
            assert path.name == module.ASSET
            assert '--clobber' not in args
            uploaded['bytes'] = path.read_bytes()
        elif args[:2] == ('release', 'download'):
            folder = Path(args[args.index('--dir') + 1])
            (folder / module.ASSET).write_bytes(uploaded['bytes'])
        return ''

    monkeypatch.setattr(module, 'gh', fake_gh)
    result = module.publish('test-reel', bundle, metadata)
    assert result['release_tag'] == f'reel-tts-test-reel-{sha[:16]}'
    assert json.loads(metadata.read_text())['duration'] == 10
    output = tmp_path / 'restored.zip'
    assert module.restore('test-reel', metadata, output)
    assert output.read_bytes() == bundle.read_bytes()
    module.publish('test-reel', bundle, metadata)
    assert sum(args[:2] == ('release', 'upload') for args in calls) == 1
    with pytest.raises(ValueError, match='producer manifest'):
        module.publish('other-slug', bundle, metadata)
    uploaded['bytes'] = b'tampered release'
    with pytest.raises(ValueError, match='hash mismatch'):
        module.publish('test-reel', bundle, metadata)
    output.unlink()
    with pytest.raises(ValueError, match='hash mismatch'):
        module.restore('test-reel', metadata, output)
    assert not output.exists()
    record = json.loads(metadata.read_text())
    record['tts_bundle']['url'] = 'https://foreign.example/voice.zip'
    metadata.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='locator'):
        module.restore('test-reel', metadata, output)
    assert not module.restore('test-reel', tmp_path / 'absent.json', output)
    record['tts_bundle']['url'] = result['url']
    metadata.write_text(json.dumps(record))
    uploaded['bytes'] = bundle.read_bytes()
    assert module.restore('test-reel', tmp_path / 'absent.json', output, metadata)
    assert output.read_bytes() == bundle.read_bytes()


def test_frozen_tts_release_permission_failures_do_not_create(tmp_path, monkeypatch):
    import importlib.util
    import json
    spec = importlib.util.spec_from_file_location('tts_release_failure', ROOT / 'tools/reel_tts_release.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bundle = tmp_path / 'bundle.zip'
    _transport_bundle(bundle)
    metadata = tmp_path / 'record.json'
    metadata.write_text(json.dumps({'tts_bundle': {'schema': module.SCHEMA,
        'artifact_kind': 'native_tts_inputs', 'quality_approval': False,
        'bundle_sha256': module.digest(bundle), 'request_count': 1}}))
    calls = []
    def fail(*args):
        calls.append(args)
        raise RuntimeError('HTTP 403 permission denied')
    monkeypatch.setattr(module, 'gh', fail)
    with pytest.raises(RuntimeError, match='403'):
        module.publish('test-reel', bundle, metadata)
    assert len(calls) == 1
    assert 'url' not in json.loads(metadata.read_text())['tts_bundle']


def test_complete_narration_bundle_survives_too_short_picture_window(tmp_path):
    """Execute the real narration shell: preserve finite inputs, retain failed duration check."""
    import os
    import re
    import subprocess
    run = next(s['run'] for s in _steps('match-reel.yml') if s.get('name', '').startswith('narration —'))
    values = {'github.event.inputs.slug': 'test-reel', 'github.event.inputs.voice': 'voice',
              'github.event.inputs.rate': '+6%', 'steps.paths.outputs.outdir': str(tmp_path / 'out'),
              'github.ref_name': 'main'}
    run = re.sub(r'\$\{\{\s*(.*?)\s*\}\}', lambda m: values[m[1]], run)
    (tmp_path / 'specs/reels').mkdir(parents=True)
    (tmp_path / 'specs/reels/test-reel.json').write_text('{}')
    bindir = tmp_path / 'bin'
    bindir.mkdir()
    fake = bindir / 'python'
    fake.write_text('''#!/bin/bash
if [[ "$1" == tools/build_match_reel.py ]]; then
  mkdir -p data/narration_checks
  echo '{}' > data/narration_checks/test-reel.json
  touch "$RUNNER_TEMP/test-reel-tts.zip"
  exit 1
fi
if [[ "$1" == tools/reel_tts_release.py && "$2" == publish ]]; then
  touch "$RUNNER_TEMP/published"
  exit 0
fi
exit 99
''')
    fake.chmod(0o755)
    result = subprocess.run(['bash', '-e', '-c', run], cwd=tmp_path, capture_output=True,
                            env={**os.environ, 'RUNNER_TEMP': str(tmp_path), 'PATH': f'{bindir}:{os.environ["PATH"]}'})
    assert result.returncode == 1
    assert (tmp_path / 'published').exists()
