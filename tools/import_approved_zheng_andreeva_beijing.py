#!/usr/bin/env python3
"""Restore the exact Zheng master from Git blobs; prepare Release/pages, never send.

Prepare only the explicitly requested full-frame-v2 revision, retaining old delivery.
Publication authorization never creates a human listening or pronunciation pass.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import requests
from tennislive.video.crop_policy import require_fixed_center, require_reel_center
from import_approved_rna10 import download_chunk
import render_inputs as ri

SLUG = 'zheng-andreeva-beijing-2026-final'
DATE = '2026-10-11'
REPOSITORY = 'robertyang87/tennislive'
OUTDIR = Path('output') / DATE / 'reel' / SLUG
SPEC = Path('specs/reels') / f'{SLUG}.json'
REVISION = 'full-frame-v2'
RELEASE_TAG = f'reel-{SLUG}-{REVISION}'
REVISION_DIR = Path('data/evidence') / SLUG / REVISION
AUDIO = REVISION_DIR / 'final-audio-review-manifest.json'
AUTHORIZATION = str(REVISION_DIR / 'owner-publication-instruction.json')
PREVIOUS_PUBLICATION = REVISION_DIR / 'previous-publication.json'
LEDGER = Path('data/reel_publish_ledger') / f'{SLUG}.json'
PREVIOUS_FILM = '2431d8edc4b527e6bde115f9308e7ee193f189b775d9ee30260340842368dc13'
PREVIOUS_RECEIPT = '3a9d637d82d7429bb0f911fdb8617672'
EXPECTED_PREVIOUS_PUBLICATION = 'e573f7ef7c23c5433578cf40e96e2edcce1c35a5ff4b48fe507014f2ef73b087'
# Fail closed until the main operator seals actual v2 film/QC/audio identities.
EXPECTED_SPEC = '7e5cefa57c88aaee949a6958690a9d4fd227b07e6e3e1d406d206c4bcebe70b1'
EXPECTED_QC = '01174e2911434c6ea01743d945d39ab80d88802646c54a40978be2a9933e1121'
EXPECTED_MANIFEST = '760d2012708e9c21742cc639f29e0b1ce0d0f70e83f0866bc5f912c6e0b5ea78'
EXPECTED_RENDER = 'b806ea43b5d8fffdbbc8c50a1defa29eec8f0cdd35bd788af2cb603e0e4839c0'
EXPECTED_AUDIO = '76607c7f7ca7a20941f5935776be924e008d5b2c84ed5c2d83d7ee5def99188e'
EXPECTED_ASSETS = {'zheng-andreeva-beijing-2026-final.mp4': (89428917, 'a077bf723fb8cde97c48ecea3a7e600ec46bcd05dc1321e4511445ad264bc4ad'), 'zheng-andreeva-beijing-2026-final-review.mp4': (27764184, 'ce4428af7a3e2d8cbcdcc83fcf7568507e30da9517cb0b99f668df5de6b05b3b')}
EXPECTED_UNRESOLVED = 43
EXPECTED_PRONUNCIATION_STATUS = 'no_confident_misreads_detected_with_calibration_limits'
MASTER = f'{SLUG}.mp4'
# Exact existing source coverage, including continuous sound/geometry splits.
EXPECTED_SOURCE_PLAN = (
    (0, 'main', 270, 276.1), (2, 'main', 0, 10), (3, 'main', 10, 26.6),
    (4, 'main', 132.4, 144.7), (5, 'main', 144.7, 149.2),
    (6, 'main', 149.2, 156.2), (7, 'main', 156.2, 172.12),
    (8, 'main', 172.12, 173.36), (9, 'main', 173.36, 185.28),
    (10, 'main', 185.28, 189.8), (11, 'main', 189.8, 193.0),
    (12, 'main', 193.0, 201.3), (13, 'main', 201.3, 207.8),
    (14, 'main', 207.8, 228.2), (15, 'main', 228.2, 233.08),
    (16, 'main', 248.12, 263.44), (18, 'main', 263.44, 276.1),
    (19, 'main', 276.1, 292.64), (20, 'main', 292.64, 299.4),
)
EXPECTED_CARDS = ((1, 5.5), (17, 12.0))


def require_armed():
    hashes = (EXPECTED_SPEC, EXPECTED_QC, EXPECTED_MANIFEST, EXPECTED_RENDER,
              EXPECTED_AUDIO, EXPECTED_PREVIOUS_PUBLICATION)
    valid_hash = lambda value: isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None
    if (not all(valid_hash(value) for value in hashes)
            or set(EXPECTED_ASSETS) != {MASTER, f'{SLUG}-review.mp4'}
            or any(type(size) is not int or size <= 0 or not valid_hash(digest)
                   for size, digest in EXPECTED_ASSETS.values())
            or EXPECTED_ASSETS.get(MASTER, (0, ''))[1] == PREVIOUS_FILM
            or type(EXPECTED_UNRESOLVED) is not int or EXPECTED_UNRESOLVED != 43
            or EXPECTED_PRONUNCIATION_STATUS != 'no_confident_misreads_detected_with_calibration_limits'):
        raise RuntimeError('Importer not armed: actual final Zheng film and native evidence are not pinned')


def run(*args):
    subprocess.run(args, check=True)


def json_bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    Path(path).write_bytes(json_bytes(data))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def pinned(path, expected):
    if sha(path) != expected:
        raise RuntimeError(f'Pinned native evidence changed: {path}')


def previous_publication():
    """Allow one immutable historical sent record, never an arbitrary prior attempt."""
    pinned(PREVIOUS_PUBLICATION, EXPECTED_PREVIOUS_PUBLICATION)
    baseline = read(PREVIOUS_PUBLICATION)
    ledger = baseline.get('previous_ledger', {})
    attempts = ledger.get('attempts', [])
    pushed = baseline.get('previous_pushed', {})
    render = baseline.get('previous_render', {})
    if (baseline.get('schema') != 'tennislive.reel-revision-baseline.v1'
            or baseline.get('revision') != REVISION
            or baseline.get('historical_evidence_only') is not True
            or baseline.get('user_request') != '要都用铺满画布的竖屏画面，重新做'
            or ledger.get('slug') != SLUG or ledger.get('channel') != 'pushplus'
            or not isinstance(attempts, list) or len(attempts) != 1):
        raise RuntimeError('Invalid exact previous-publication baseline')
    attempt = attempts[0]
    if (attempt.get('key') != f'pushplus:reel:{SLUG}:{PREVIOUS_FILM}'
            or attempt.get('fingerprint') != PREVIOUS_FILM
            or attempt.get('status') != 'sent'
            or attempt.get('pushplus_receipt') != PREVIOUS_RECEIPT
            or pushed.get('pushplus_receipt') != PREVIOUS_RECEIPT
            or pushed.get('message_url') != f'https://www.pushplus.plus/shortMessage/{PREVIOUS_RECEIPT}'
            or any(attempt.get(key) != pushed.get(key) for key in ('at', 'run', 'pushplus_receipt', 'message_url'))
            or not pushed.get('at') or not pushed.get('run')
            or render.get('film_sha256') != PREVIOUS_FILM
            or render.get('film_bytes') != 67425605
            or render.get('video_url') != f'https://github.com/{REPOSITORY}/releases/download/reel-{SLUG}/{MASTER}'):
        raise RuntimeError('Previous sent film/receipt identity differs')
    return baseline


def revision_authorization(m):
    baseline = previous_publication()
    auth = read(AUTHORIZATION)
    for obj in (m, auth):
        if (obj.get('revision') != REVISION
                or obj.get('previous_publication_path') != str(PREVIOUS_PUBLICATION)
                or obj.get('previous_publication_sha256') != EXPECTED_PREVIOUS_PUBLICATION):
            raise ValueError('Missing exact full-frame-v2 previous-publication binding')
    if auth.get('user_instruction') != baseline['user_request']:
        raise ValueError('Owner instruction does not identify this explicit remake request')
    size, digest = EXPECTED_ASSETS[MASTER]
    if ((auth.get('film_bytes'), auth.get('film_sha256')) != (size, digest)
            or digest == PREVIOUS_FILM
            or auth.get('unresolved_occurrences') != EXPECTED_UNRESOLVED
            or auth.get('pronunciation_status') != EXPECTED_PRONUNCIATION_STATUS
            or auth.get('human_listening_claimed') is not False):
        raise ValueError('Revision authorization must bind the new film and actual uncertainty')
    return baseline


def full_frame_spec(spec):
    segments = spec.get('segments', [])
    videos = [(i, s) for i, s in enumerate(segments) if 'start' in s or 'end' in s]
    plan = tuple((i, s.get('source'), s.get('start'), s.get('end')) for i, s in videos)
    cards = tuple((i, s.get('seconds')) for i, s in enumerate(segments) if 'title_card' in s)
    if (len(segments) != 21 or plan != EXPECTED_SOURCE_PLAN or cards != EXPECTED_CARDS
            or spec.get('sources') != {'main': 'https://www.youtube.com/watch?v=Vq_UC0n5DKQ'}
            or spec.get('track') is not False or spec.get('outro') is not False
            or 'source_scorebox' in spec):
        raise RuntimeError('Full-frame-v2 source coverage/cards changed')
    for i, segment in videos:
        if (segment.get('fit') != 'crop' or type(segment.get('cx')) not in (float, int)
                or segment['cx'] != 0.5 or segment.get('track') is not False
                or any(key in segment for key in ('crop_track', 'contain_keep', 'image', 'stat_card', 'title_card'))):
            raise RuntimeError(f'Full-frame-v2 requires fixed center crop: segment {i}')
    try:
        require_fixed_center(spec, where='full-frame-v2')
        require_reel_center(spec)
    except ValueError as exc:
        raise RuntimeError(f'Full-frame-v2 center policy: {exc}') from exc


def manifest(path):
    require_armed()
    m = read(path)
    size, digest = EXPECTED_ASSETS[MASTER]
    if (m.get('slug'), m.get('date'), m.get('bytes'), m.get('sha256')) != (SLUG, DATE, size, digest):
        raise ValueError('Request does not identify this exact approved master')
    for key, want in [('spec_sha256', EXPECTED_SPEC), ('qc_attestation_sha256', EXPECTED_QC), ('render_inputs_sha256', EXPECTED_MANIFEST)]:
        if m.get(key) != want:
            raise ValueError(f'Request evidence mismatch: {key}')
    assets = m.get('assets', [])
    if len(assets) != len(EXPECTED_ASSETS) or {a.get('name') for a in assets} != set(EXPECTED_ASSETS):
        raise ValueError('Request must contain exactly the pinned assets')
    for asset in assets:
        if (asset.get('bytes'), asset.get('sha256')) != EXPECTED_ASSETS[asset['name']]:
            raise ValueError(f'Asset identity mismatch: {asset["name"]}')
        chunks = asset.get('chunks', [])
        if not chunks or any(not re.fullmatch(r'[a-f0-9]{40}', str(c.get('sha', ''))) or type(c.get('bytes')) is not int or not 0 < c['bytes'] <= 3 * 1024 * 1024 for c in chunks):
            raise ValueError('Invalid chunk descriptors')
        if sum(c['bytes'] for c in chunks) != asset['bytes']:
            raise ValueError('Chunk byte totals differ')
    master = next(a for a in assets if a['name'] == MASTER)
    if m.get('chunks') != master['chunks']:
        raise ValueError('Top-level master chunks differ from asset descriptors')
    if m.get('authorization_path') != AUTHORIZATION or not re.fullmatch(r'[a-f0-9]{64}', str(m.get('authorization_sha256', ''))):
        raise ValueError('Missing exact owner authorization binding')
    pinned(AUTHORIZATION, m['authorization_sha256'])
    auth = read(AUTHORIZATION)
    if (auth.get('film_sha256'), auth.get('film_bytes')) != (digest, size) or not auth.get('user_instruction'):
        raise ValueError('Owner instruction is not bound to this film')
    if auth.get('unresolved_occurrences') != EXPECTED_UNRESOLVED or auth.get('human_listening_claimed') is not False or auth.get('pronunciation_status') != EXPECTED_PRONUNCIATION_STATUS:
        raise ValueError('Owner authorization must preserve pronunciation uncertainty')
    revision_authorization(m)
    return m


def native_evidence():
    require_armed()
    for path, expected in [(SPEC, EXPECTED_SPEC), (OUTDIR/'qc_attestation.json', EXPECTED_QC), (OUTDIR/'render_inputs.json', EXPECTED_MANIFEST)]:
        pinned(path, expected)
    full_frame_spec(read(SPEC))
    render_path = OUTDIR/'render.json'
    before = OUTDIR/'render.before-release.json'
    original = before if before.exists() else render_path
    pinned(original, EXPECTED_RENDER)
    baseline, render = read(original), read(render_path)
    # Only Release transport fields may change; native render/QC data is immutable.
    current_native = {k: v for k, v in render.items() if k not in ('video_url', 'video_bytes')}
    baseline_native = {k: v for k, v in baseline.items() if k not in ('video_url', 'video_bytes')}
    if current_native != baseline_native:
        raise RuntimeError('Native render metadata changed')
    qc, inputs = read(OUTDIR/'qc_attestation.json'), read(OUTDIR/'render_inputs.json')
    size, digest = EXPECTED_ASSETS[MASTER]
    if qc.get('status') != 'pass' or qc.get('spec_sha256') != EXPECTED_SPEC or qc.get('render_inputs_sha256') != EXPECTED_MANIFEST or qc.get('film_sha256') != digest or qc.get('film_bytes') != size:
        raise RuntimeError('Native QC chain is inconsistent')
    if inputs.get('spec_sha256') != EXPECTED_SPEC or inputs.get('film_sha256') != digest or inputs.get('film_bytes') != size:
        raise RuntimeError('Native render-input film chain is inconsistent')
    if render.get('qc_attestation_sha256') != EXPECTED_QC or render.get('render_inputs_sha256') != EXPECTED_MANIFEST or render.get('film_sha256') != digest or render.get('film_bytes') != size:
        raise RuntimeError('Native render chain is inconsistent')
    problems = ri.spec_problems(SPEC.read_bytes(), inputs) + ri.asset_problems(SPEC.read_bytes(), inputs, Path.cwd())
    if problems:
        raise RuntimeError(f'Native spec/assets changed: {problems}')
    for name, expected in inputs['artifacts'].items():
        if Path(name).name != name:
            raise RuntimeError('Invalid native artifact name')
        pinned(OUTDIR/name, expected)
    audio = read(AUDIO)
    if (audio.get('pronunciation_status') != EXPECTED_PRONUNCIATION_STATUS
            or audio.get('unresolved_occurrences') != EXPECTED_UNRESOLVED
            or audio.get('human_listening_claimed') is not False):
        raise RuntimeError('Actual pronunciation status changed')
    if audio.get('render_json_sha256') not in (EXPECTED_RENDER, sha(render_path)):
        raise RuntimeError('Audio evidence binds a different render')
    normalized = dict(audio, render_json_sha256=EXPECTED_RENDER)
    if hashlib.sha256(json_bytes(normalized)).hexdigest() != EXPECTED_AUDIO:
        raise RuntimeError('Original audio evidence changed beyond Release render binding')
    return render, audio


def no_prior_delivery(m):
    # manifest() already pins the owner instruction; recheck here before mutation.
    pinned(AUTHORIZATION, m['authorization_sha256'])
    baseline = revision_authorization(m)
    tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    if (any(p.endswith(f'/reel/{SLUG}/pushed.json') for p in tracked)
            or (OUTDIR/'pushed.json').exists()):
        raise RuntimeError('Delivery already recorded: refusing an automatic duplicate import')
    # Missing history is also an error: the old sent receipt must remain intact.
    if not LEDGER.exists() or read(LEDGER) != baseline['previous_ledger']:
        raise RuntimeError('Delivery ledger differs: refusing new, unknown or unfinished attempts')


def verify_file(path, name):
    require_armed()
    size, digest = EXPECTED_ASSETS[name]
    if Path(path).stat().st_size != size or sha(path) != digest:
        raise RuntimeError(f'Asset bytes differ from pinned identity: {name}')


def assemble(request):
    m = manifest(request)
    no_prior_delivery(m)
    native_evidence()
    cache = Path(os.environ.get('RUNNER_TEMP', '.'))/'approved-zheng-andreeva-beijing-2026-final-chunks'
    cache.mkdir(parents=True, exist_ok=True)
    # Deduplicate by Git SHA so concurrent workers never race on a .part file.
    chunks = {c['sha']: c for a in m['assets'] for c in a['chunks']}
    if any(chunks[c['sha']] != c for a in m['assets'] for c in a['chunks']):
        raise ValueError('Conflicting descriptors for one Git blob')
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda c: download_chunk(c, cache), chunks.values()))
    for asset in m['assets']:
        film = OUTDIR/asset['name']
        if film.exists():
            verify_file(film, asset['name'])
            continue
        temporary = film.with_suffix(film.suffix + '.part')
        with temporary.open('wb') as stream:
            for c in asset['chunks']:
                stream.write((cache/c['sha']).read_bytes())
        verify_file(temporary, asset['name'])
        temporary.replace(film)
    run(sys.executable, 'tools/push_reel.py', '--stage', 'check', '--outdir', str(OUTDIR), '--copy', str(SPEC.with_suffix('.xhs.txt')))
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'json', str(OUTDIR/MASTER)], text=True))
    if (probe['streams'][0]['width'], probe['streams'][0]['height']) != (1080, 1440):
        raise RuntimeError('Imported master canvas changed')
    write(OUTDIR/'import-provenance.json', {
        'film_sha256': EXPECTED_ASSETS[MASTER][1], 'film_bytes': EXPECTED_ASSETS[MASTER][0],
        'original_native_qc_sha256': EXPECTED_QC, 'original_render_inputs_sha256': EXPECTED_MANIFEST,
        'original_render_json_sha256': EXPECTED_RENDER, 'original_audio_review_manifest_sha256': EXPECTED_AUDIO,
        'qc_status': 'original-local-pass-preserved', 'new_audio_review': False,
        'authorization_path': AUTHORIZATION, 'authorization_sha256': m['authorization_sha256'],
        'revision': REVISION, 'previous_publication_path': str(PREVIOUS_PUBLICATION),
        'previous_publication_sha256': EXPECTED_PREVIOUS_PUBLICATION,
        'pronunciation_status': EXPECTED_PRONUNCIATION_STATUS, 'unresolved_occurrences': EXPECTED_UNRESOLVED,
        'human_listening_claimed': False, 'transport': m.get('transport', ''),
        'assets': [{k: a[k] for k in ('name', 'bytes', 'sha256')} for a in m['assets']],
        'message_sent_by_importer': False,
    })
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(f'outdir={OUTDIR}\nslug={SLUG}\n')
    print('Exact pinned assets and original native QC verified; no message sent.', flush=True)


def remote_verify(asset, name):
    require_armed()
    expected_bytes, expected_sha = EXPECTED_ASSETS[name]
    if asset.get('size') != expected_bytes:
        raise RuntimeError(f'Release metadata byte count differs: {name}')
    url = asset['url']
    if url != f'https://github.com/{REPOSITORY}/releases/download/{RELEASE_TAG}/{name}':
        raise RuntimeError('Unexpected Release download URL')
    for attempt in range(3):
        try:
            with requests.get(url, timeout=(15, 120), stream=True) as response:
                response.raise_for_status()
                digest, size = hashlib.sha256(), 0
                for block in response.iter_content(1024 * 1024):
                    digest.update(block)
                    size += len(block)
            break
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            transient = isinstance(exc, (requests.ConnectionError, requests.Timeout)) or status in (404, 429) or (status is not None and 500 <= status < 600)
            if not transient or attempt == 2:
                raise RuntimeError(f'Release GET failed for {name}; HTTP status {status}') from None
            time.sleep(3)
    if (size, digest.hexdigest()) != (expected_bytes, expected_sha):
        raise RuntimeError(f'Remote asset differs; refusing overwrite: {name}')
    return {'name': name, 'url': url, 'bytes': size, 'sha256': digest.hexdigest(), 'method': 'remote-streaming-GET'}


def release_assets(tag):
    result = subprocess.check_output(['gh', 'release', 'view', tag, '--json', 'assets,isDraft'], text=True)
    data = json.loads(result)
    if data.get('isDraft'):
        raise RuntimeError('Draft Release is not publicly downloadable; refusing metadata publication')
    return data['assets']


def release(request):
    m = manifest(request)
    no_prior_delivery(m)
    render, audio = native_evidence()
    for a in m['assets']:
        verify_file(OUTDIR/a['name'], a['name'])
    run(sys.executable, 'tools/push_reel.py', '--stage', 'check', '--outdir', str(OUTDIR), '--copy', str(SPEC.with_suffix('.xhs.txt')))
    tag = RELEASE_TAG
    existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets,isDraft'], text=True, capture_output=True)
    if existing.returncode:
        # Distinguish absent Release from authorization/network errors before mutation.
        error = existing.stderr.lower()
        if 'release not found' not in error and 'not found' not in error:
            raise RuntimeError(f'Cannot inspect Release: {existing.stderr.strip()}')
        run('gh', 'release', 'create', tag, '--title', '赛场之上 · 郑钦文 vs 安德烈耶娃', '--notes', '本场原生成片与审片版。原生质检及实际语音证据逐字节保留。')
    assets = release_assets(tag)
    verified = []
    for a in m['assets']:
        matches = [x for x in assets if x['name'] == a['name']]
        if len(matches) > 1:
            raise RuntimeError(f'Duplicate Release asset names: {a["name"]}')
        if matches:
            verified.append(remote_verify(matches[0], a['name']))
        else:
            # Deliberately omit --clobber: existing public bytes cannot be replaced.
            run('gh', 'release', 'upload', tag, str(OUTDIR/a['name']))
            assets = release_assets(tag)
            uploaded = next(x for x in assets if x['name'] == a['name'])
            verified.append(remote_verify(uploaded, a['name']))
    master = next(a for a in verified if a['name'] == MASTER)
    before = OUTDIR/'render.before-release.json'
    if not before.exists():
        pinned(OUTDIR/'render.json', EXPECTED_RENDER)
        before.write_bytes((OUTDIR/'render.json').read_bytes())
    pinned(before, EXPECTED_RENDER)
    render.update(video_url=master['url'], video_bytes=master['bytes'])
    write(OUTDIR/'render.json', render)
    audio['render_json_sha256'] = sha(OUTDIR/'render.json')
    write(AUDIO, audio)
    # Verify the rebind changed no acoustic findings, native QC or artifacts.
    native_evidence()
    write(OUTDIR/'release-verification.json', {
        'video_url': master['url'], 'bytes': master['bytes'], 'sha256': master['sha256'],
        'method': 'remote-streaming-GET', 'assets': verified,
        'same_native_master_and_audio': True, 'render_json_sha256': sha(OUTDIR/'render.json'),
        'audio_review_manifest_sha256': sha(AUDIO), 'pronunciation_status': audio['pronunciation_status'],
        'unresolved_occurrences': EXPECTED_UNRESOLVED, 'message_sent_by_importer': False,
    })
    run(sys.executable, 'tools/push_reel.py', '--stage', 'page', '--outdir', str(OUTDIR), '--copy', str(SPEC.with_suffix('.xhs.txt')))
    module_spec = importlib.util.spec_from_file_location('native_push_reel', 'tools/push_reel.py')
    native = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(native)
    copy_path = SPEC.with_suffix('.xhs.txt')
    column, title, body = native.prepare_copy(copy_path, OUTDIR)
    meta = native.push_meta(copy_path)
    page = native.build_html(master['url'], native.copy_page_url(OUTDIR), meta.get('lead', ''), f'{title}\n\n{body}', 'poster.jpg', column, stat_card='stat_card.jpg')
    (OUTDIR/'push.html').write_text(page, encoding='utf-8')
    print(f'Release GET verified and native pages prepared: {master["url"]}; no message sent.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['assemble', 'release'])
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
        raise SystemExit('Importer is scoped to robertyang87/tennislive')
    {'assemble': assemble, 'release': release}[args.stage](args.request)
