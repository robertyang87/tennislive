"""Regression for the failed Eala push: stage declared packets, not guessed dirs."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import reel_review_files as R
from foreground_audio_gate import SCHEMA, _sha, plan_hash


def fixture(root):
    spec = {'slug': 'example-match', 'source_url': 'https://example.test/original',
            'segments': [{'start': 0, 'end': 4, 'narration': '比赛开始。'}]}
    packet = {'source_url': spec['source_url'], 'source_sha256': 'a' * 64,
              'method': 'asr_cross_checked', 'reviewer': 'fixture',
              'reviewed_at': '2026-10-12T12:00:00Z', 'status': 'complete',
              'reviewed_from': 0, 'reviewed_to': 4, 'foreground_english': [],
              'no_foreground_english_reason': 'Fixture has only court ambience.'}
    # Deliberately outside both audio_reviews/<slug> and the current OUTDIR.
    path = root / 'output/2026-10-11/reel/example-match/review.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(packet))
    review = {'schema': SCHEMA, 'plan_sha256': plan_hash(spec), 'segments': [
        {'index': 0, 'transcript_path': path.relative_to(root).as_posix(),
         'transcript_sha256': _sha(path)}]}
    index = root / 'data/audio_reviews/example-match.json'
    index.parent.mkdir(parents=True)
    index.write_text(json.dumps(review))
    sp = root / 'specs/reels/example-match.json'
    sp.parent.mkdir(parents=True)
    sp.write_text(json.dumps(spec))
    return path, index, sp


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout


def test_actual_declared_files_stage_without_sibling_directory_or_media(tmp_path):
    packet, index, _ = fixture(tmp_path)
    (packet.parent / 'source.mp4').write_bytes(b'media must not enter Git')
    git(tmp_path, 'init', '-q')
    old = subprocess.run(['git', 'add', index.relative_to(tmp_path).as_posix(),
                          'data/audio_reviews/example-match'], cwd=tmp_path,
                         capture_output=True, text=True)
    assert old.returncode and 'did not match any files' in old.stderr
    names = R.review_files('example-match', root=tmp_path)
    R.stage_files(names, root=tmp_path)
    assert git(tmp_path, 'diff', '--cached', '--name-only').splitlines() == sorted([
        packet.relative_to(tmp_path).as_posix(), index.relative_to(tmp_path).as_posix()])
    assert not (tmp_path / 'data/audio_reviews/example-match').exists()


@pytest.mark.parametrize('change,reason', [
    ('bytes', '字节已变'), ('missing', '文件不存在'),
    ('plan', '当前剪辑'), ('source', '源片身份'), ('coverage', '整个选用窗口'),
])
def test_packet_failure_prevents_any_git_staging(tmp_path, change, reason):
    packet, index, _ = fixture(tmp_path)
    doc = json.loads(packet.read_text())
    review = json.loads(index.read_text())
    if change == 'bytes':
        packet.write_text(packet.read_text() + ' ')
    elif change == 'missing':
        packet.unlink()
    elif change == 'plan':
        review['plan_sha256'] = 'b' * 64
    else:
        doc.update({'source_url': 'https://example.test/wrong'} if change == 'source'
                   else {'reviewed_to': 3})
        packet.write_text(json.dumps(doc))
        review['segments'][0]['transcript_sha256'] = _sha(packet)
    index.write_text(json.dumps(review))
    git(tmp_path, 'init', '-q')
    with pytest.raises(ValueError, match=reason):
        names = R.review_files('example-match', root=tmp_path)
        R.stage_files(names, root=tmp_path)
    assert not git(tmp_path, 'diff', '--cached', '--name-only')


@pytest.mark.parametrize('name', ['../outside.json', '/absolute.json',
                                  '.git/config.json', 'data/source.mp4'])
def test_paths_cannot_escape_repository_or_stage_media(tmp_path, name):
    with pytest.raises(ValueError, match='仓库内 JSON'):
        R._file(tmp_path, name)
    (tmp_path / 'link.json').symlink_to(tmp_path / 'target.json')
    with pytest.raises(ValueError, match='符号链接'):
        R._file(tmp_path, 'link.json')


def test_sparse_checkout_restores_only_declared_tracked_json(tmp_path):
    packet, index, _ = fixture(tmp_path)
    media = packet.parent / 'source.mp4'
    media.write_bytes(b'existing historical media sibling')
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'add', '.')
    git(tmp_path, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '-qm', 'fixture')
    git(tmp_path, 'sparse-checkout', 'set', 'data', 'specs')
    assert not packet.exists() and not media.exists()
    assert R.review_files('example-match', root=tmp_path) == [
        index.relative_to(tmp_path).as_posix(), packet.relative_to(tmp_path).as_posix()]
    assert packet.exists() and not media.exists()
    packet.write_text(packet.read_text() + ' ')
    # Modified evidence must fail rather than silently reverting to HEAD.
    with pytest.raises(ValueError, match='字节已变'):
        R.review_files('example-match', root=tmp_path)
    git(tmp_path, 'sparse-checkout', 'disable')
    packet.unlink()
    # A normally checked-out file removed by the producer is a missing packet,
    # not a sparse omission that may be restored from historical HEAD evidence.
    with pytest.raises(ValueError, match='文件不存在'):
        R.review_files('example-match', root=tmp_path)


def test_explicit_rebind_reuses_immutable_review_after_card_copy_change(tmp_path):
    packet, index, sp = fixture(tmp_path)
    before_packet = packet.read_bytes()
    before_review = json.loads(index.read_text())
    spec = json.loads(sp.read_text())
    spec['segments'].append({'image': 'chapter.png', 'title_card': {'title': '第三轮'},
                             'narration': '下一场争夺第三轮席位。'})
    sp.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='当前剪辑'):
        R.review_files('example-match', root=tmp_path)
    R.review_files('example-match', root=tmp_path, rebind=True)
    after = json.loads(index.read_text())
    assert after == {**before_review, 'plan_sha256': plan_hash(spec)}
    assert packet.read_bytes() == before_packet
    # Repeating the readiness check does not rewrite any valid evidence.
    before = index.read_bytes()
    R.review_files('example-match', root=tmp_path, rebind=True)
    assert index.read_bytes() == before
    source = tmp_path / 'source.mp4'; source.write_bytes(b'different source bytes')
    with pytest.raises(ValueError, match='源片字节'):
        R.require(spec, root=tmp_path, sources={'': source})


@pytest.mark.parametrize('fault,reason', [
    ('packet-bytes', '字节已变'), ('source-url', '源片身份'),
    ('window', '整个选用窗口'), ('partial-sentence', '切断'),
    ('missing-caption', '缺完整中英字幕'), ('uncertain', '不确定'),
    ('removed-window', '没有可重绑定'), ('extra-window', '每个保留原声'),
])
def test_rebind_failure_does_not_write_or_stage_an_index(tmp_path, fault, reason):
    packet, index, sp = fixture(tmp_path)
    spec = json.loads(sp.read_text())
    doc = json.loads(packet.read_text())
    review = json.loads(index.read_text())
    if fault == 'source-url':
        spec['source_url'] += '/new'
    elif fault == 'window':
        spec['segments'][0]['end'] = 5
    elif fault in {'partial-sentence', 'missing-caption'}:
        spec['segments'][0].pop('narration')
        doc['foreground_english'] = [{'start': 1, 'end': 3, 'en': 'Great shot!', 'zh': '精彩一拍'}]
        if fault == 'partial-sentence':
            spec['segments'][0]['start'] = 2
        else:
            spec['segments'][0]['quote'] = [{'at': 1, 'end': 3, 'text': 'Wrong words\n错误字幕'}]
    elif fault == 'uncertain':
        doc['uncertain_spans'] = [[1, 2]]
    elif fault == 'removed-window':
        spec['segments'] = []
    elif fault == 'extra-window':
        spec['segments'].append(dict(spec['segments'][0]))
    packet.write_text(json.dumps(doc))
    review['segments'][0]['transcript_sha256'] = _sha(packet)
    if fault == 'packet-bytes':
        packet.write_text(packet.read_text() + ' ')
    index.write_text(json.dumps(review))
    sp.write_text(json.dumps(spec))
    before = index.read_bytes()
    git(tmp_path, 'init', '-q')
    with pytest.raises(ValueError, match=reason):
        names = R.review_files('example-match', root=tmp_path, rebind=True)
        R.stage_files(names, root=tmp_path)
    assert index.read_bytes() == before
    assert not git(tmp_path, 'diff', '--cached', '--name-only')


def test_explicit_rebind_cannot_create_an_unreviewed_index(tmp_path):
    _packet, index, _spec = fixture(tmp_path)
    index.unlink()
    git(tmp_path, 'init', '-q')
    with pytest.raises(ValueError, match='已有审听索引'):
        R.review_files('example-match', root=tmp_path, rebind=True)
    assert not index.exists()


def test_missing_index_keeps_optional_history_but_required_native_gate_fails(tmp_path):
    _, index, _ = fixture(tmp_path)
    index.unlink()
    assert R.review_files('example-match', root=tmp_path) == []
    with pytest.raises(ValueError, match='waiting_audio_review'):
        R.review_files('example-match', root=tmp_path, require_review=True)
