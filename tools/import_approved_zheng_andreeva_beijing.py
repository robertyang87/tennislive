#!/usr/bin/env python3
"""Restore the exact Zheng master from Git blobs; prepare Release/pages, never send.

Reuse the pinned native spec/QC/assets and actual audio findings unchanged.
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
from import_approved_rna10 import download_chunk
import render_inputs as ri

SLUG = 'zheng-andreeva-beijing-2026-final'
DATE = '2026-10-11'
REPOSITORY = 'robertyang87/tennislive'
OUTDIR = Path('output') / DATE / 'reel' / SLUG
SPEC = Path('specs/reels') / f'{SLUG}.json'
AUDIO = Path('data/evidence/zheng-andreeva-beijing-2026-final/final-audio-review-manifest.json')
AUTHORIZATION = 'data/evidence/zheng-andreeva-beijing-2026-final/owner-publication-instruction.json'
# Exact final native film/QC/audio pins, sealed after real source and waveform checks.
EXPECTED_SPEC = 'd7cb28a69493fc15c63e92f0c6025af81c755c7acce37bd49055d7dced12a51b'
EXPECTED_QC = '27f73e0d771710ae2a843664e4083490c89858a70aa9f74849e462a2360406ee'
EXPECTED_MANIFEST = 'a6455c85b5efe174e93c8f6bd83886e2e6f249ceff8e181ff4ca5f54b8f838a8'
EXPECTED_RENDER = 'b9fbc260706f1c7f51989c5ce2f6c3e944d01050c42bc5d662e3f9e929d84c07'
EXPECTED_AUDIO = '47647f22953d2c89853c8db7c494aa043278063c3391a62069e288a78ce3c164'
EXPECTED_ASSETS = {'zheng-andreeva-beijing-2026-final.mp4': (67425605, '2431d8edc4b527e6bde115f9308e7ee193f189b775d9ee30260340842368dc13'), 'zheng-andreeva-beijing-2026-final-review.mp4': (26796239, 'e0dc1d34ffcd5334ef6660a403c84df3c49007207e11d6e84830dec8bd962eb5')}
EXPECTED_UNRESOLVED = 43
EXPECTED_PRONUNCIATION_STATUS = 'no_confident_misreads_detected_with_calibration_limits'
MASTER = f'{SLUG}.mp4'


def require_armed():
    hashes = (EXPECTED_SPEC, EXPECTED_QC, EXPECTED_MANIFEST, EXPECTED_RENDER, EXPECTED_AUDIO)
    valid_hash = lambda value: isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None
    if (not all(valid_hash(value) for value in hashes)
            or set(EXPECTED_ASSETS) != {MASTER, f'{SLUG}-review.mp4'}
            or any(type(size) is not int or size <= 0 or not valid_hash(digest)
                   for size, digest in EXPECTED_ASSETS.values())
            or type(EXPECTED_UNRESOLVED) is not int or EXPECTED_UNRESOLVED < 0
            or not isinstance(EXPECTED_PRONUNCIATION_STATUS, str)
            or not EXPECTED_PRONUNCIATION_STATUS):
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
    return m


def native_evidence():
    require_armed()
    for path, expected in [(SPEC, EXPECTED_SPEC), (OUTDIR/'qc_attestation.json', EXPECTED_QC), (OUTDIR/'render_inputs.json', EXPECTED_MANIFEST)]:
        pinned(path, expected)
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
    if audio.get('pronunciation_status') != EXPECTED_PRONUNCIATION_STATUS:
        raise RuntimeError('Actual pronunciation status changed')
    if audio.get('render_json_sha256') not in (EXPECTED_RENDER, sha(render_path)):
        raise RuntimeError('Audio evidence binds a different render')
    normalized = dict(audio, render_json_sha256=EXPECTED_RENDER)
    if hashlib.sha256(json_bytes(normalized)).hexdigest() != EXPECTED_AUDIO:
        raise RuntimeError('Original audio evidence changed beyond Release render binding')
    return render, audio


def no_prior_delivery():
    tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    if (any(p.endswith(f'/reel/{SLUG}/pushed.json') for p in tracked)
            or (OUTDIR/'pushed.json').exists()
            or Path(f'data/reel_publish_ledger/{SLUG}.json').exists()):
        raise RuntimeError('Delivery already recorded: refusing an automatic duplicate import')


def verify_file(path, name):
    require_armed()
    size, digest = EXPECTED_ASSETS[name]
    if Path(path).stat().st_size != size or sha(path) != digest:
        raise RuntimeError(f'Asset bytes differ from pinned identity: {name}')


def assemble(request):
    m = manifest(request)
    no_prior_delivery()
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
    if url != f'https://github.com/{REPOSITORY}/releases/download/reel-{SLUG}/{name}':
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
    no_prior_delivery()
    render, audio = native_evidence()
    for a in m['assets']:
        verify_file(OUTDIR/a['name'], a['name'])
    run(sys.executable, 'tools/push_reel.py', '--stage', 'check', '--outdir', str(OUTDIR), '--copy', str(SPEC.with_suffix('.xhs.txt')))
    tag = f'reel-{SLUG}'
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
