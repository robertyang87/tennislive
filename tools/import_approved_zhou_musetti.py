#!/usr/bin/env python3
"""Restore the exact Zhou master from Git blobs; prepare Release/pages, never send.

Reuse the tracked native spec/QC/assets. Publication authorization does not turn
seven unresolved pronunciation occurrences into a human listening pass.
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

SLUG = 'zhou-musetti'
DATE = '2026-10-10'
REPOSITORY = 'robertyang87/tennislive'
OUTDIR = Path('output') / DATE / 'reel' / SLUG
SPEC = Path('specs/reels') / f'{SLUG}.json'
AUDIO = Path('data/evidence/zhou-musetti/final-audio-review-manifest.json')
AUTHORIZATION = 'data/evidence/zhou-musetti/owner-publication-instruction.json'
EXPECTED_SPEC = 'f3226b67ff78ead32bca91fe9fcd42418bc1012ccb79d749e8d66e1c6b838e6f'
EXPECTED_QC = '698904cc87362078f7148cefceabb43b0b18c84614ee57e7b481fca05e1eb605'
EXPECTED_MANIFEST = 'bc390a605fe57bc65ad1e3868f68ade80478becb808d5f4e472c5a25335361f7'
EXPECTED_RENDER = '160881153396918bce1734ea031a7c8adf2e35b9ce5b66b9cf49bddb59fa9cff'
EXPECTED_AUDIO = 'df4a264725247c81b3f16a32a1833a63a461ba9b396626f2ac87692a02eee9db'
EXPECTED_ASSETS = {
    'zhou-musetti.mp4': (64463858, '83a62d6a3573ab8e568a38b855ff687d8261eee0215c361cbd42c6092186cb52'),
    'zhou-musetti-review.mp4': (27156871, '3e6c0d0196deeeefe7042e59679aed8dff2214aaf7bbc7aedcaaf013aeda651f'),
    'zhou-musetti-pronunciation.mp3': (162044, '37e31884e60282174c6d9174648aea729c3a0b574362ee99383f0694fa30ad03'),
}
MASTER = f'{SLUG}.mp4'


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
    m = read(path)
    size, digest = EXPECTED_ASSETS[MASTER]
    if (m.get('slug'), m.get('date'), m.get('bytes'), m.get('sha256')) != (SLUG, DATE, size, digest):
        raise ValueError('Request does not identify this exact approved master')
    for key, want in [('spec_sha256', EXPECTED_SPEC), ('qc_attestation_sha256', EXPECTED_QC), ('render_inputs_sha256', EXPECTED_MANIFEST)]:
        if m.get(key) != want:
            raise ValueError(f'Request evidence mismatch: {key}')
    assets = m.get('assets', [])
    if len(assets) != 3 or {a.get('name') for a in assets} != set(EXPECTED_ASSETS):
        raise ValueError('Request must contain exactly the three pinned assets')
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
    if auth.get('unresolved_occurrences') != 7 or auth.get('human_listening_claimed') is not False or auth.get('pronunciation_status') != 'incomplete_uncertain_not_release_pass':
        raise ValueError('Owner authorization must preserve pronunciation uncertainty')
    return m


def native_evidence():
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
    if audio.get('render_json_sha256') not in (EXPECTED_RENDER, sha(render_path)):
        raise RuntimeError('Audio evidence binds a different render')
    normalized = dict(audio, render_json_sha256=EXPECTED_RENDER)
    if hashlib.sha256(json_bytes(normalized)).hexdigest() != EXPECTED_AUDIO:
        raise RuntimeError('Original audio evidence changed beyond Release render binding')
    return render, audio


def no_prior_delivery():
    tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    if any(p.endswith(f'/reel/{SLUG}/pushed.json') for p in tracked) or Path(f'data/reel_publish_ledger/{SLUG}.json').exists():
        raise RuntimeError('Delivery already recorded: refusing an automatic duplicate import')


def verify_file(path, name):
    size, digest = EXPECTED_ASSETS[name]
    if Path(path).stat().st_size != size or sha(path) != digest:
        raise RuntimeError(f'Asset bytes differ from pinned identity: {name}')


def assemble(request):
    m = manifest(request)
    no_prior_delivery()
    native_evidence()
    cache = Path(os.environ.get('RUNNER_TEMP', '.'))/'approved-zhou-musetti-chunks'
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
        'pronunciation_status': 'incomplete_uncertain_not_release_pass', 'unresolved_occurrences': 7,
        'human_listening_claimed': False, 'transport': m.get('transport', ''),
        'assets': [{k: a[k] for k in ('name', 'bytes', 'sha256')} for a in m['assets']],
        'message_sent_by_importer': False,
    })
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(f'outdir={OUTDIR}\nslug={SLUG}\n')
    print('Exact three assets and original native QC verified; no message sent.', flush=True)


def remote_verify(asset, name):
    expected_bytes, expected_sha = EXPECTED_ASSETS[name]
    if asset.get('size') != expected_bytes:
        raise RuntimeError(f'Release metadata byte count differs: {name}')
    url = asset['url']
    if not url.startswith(f'https://github.com/{REPOSITORY}/releases/download/reel-{SLUG}/'):
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
                raise
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
        run('gh', 'release', 'create', tag, '--title', '赛场之上 · 周意 vs 穆塞蒂', '--notes', '原生成片与审片、读音片段。保留原生质检；七处读音待确认，按用户明确指令发布。')
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
        'unresolved_occurrences': 7, 'message_sent_by_importer': False,
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
