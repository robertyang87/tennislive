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

    uploads = [s for s in _steps('match-reel.yml')
               if s.get('uses', '').startswith('actions/upload-artifact@')
               and s.get('name') == '上传 artifact']
    assert len(uploads) == 1  # 审片分片另有明确allowlist，失败排查仍只认主artifact。
    upload = uploads[0]
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
