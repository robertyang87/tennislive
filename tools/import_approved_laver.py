#!/usr/bin/env python3
"""Import the approved Laver Cup master without transcoding or bypassing native QC.

Input data/approved_reel_imports/laver-cup-history-2026/request.json:
  {"slug": "laver-cup-history-2026", "date": "2026-09-22",
   "bytes": <repaired-master-bytes>, "sha256": "<repaired-master-sha256>",
   "chunks": [{"sha": "<Git blob SHA>", "bytes": 3145728}, ...]}
Adjacent inputs: spec.json, render.json, subtitles.ass, poster.jpg, copy.txt.
Unreferenced Git blobs are transfer objects; no movie bytes enter the Git tree.
"""
from __future__ import annotations
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import requests

SLUG = 'laver-cup-history-2026'
REPOSITORY = 'robertyang87/tennislive'
EXPECTED_BYTES = 0  # Fill only from repaired master after native QC passes.
EXPECTED_SHA = 'AWAITING_NATIVE_QC_PASSED_MASTER'

def run(*args):
    subprocess.run(args, check=True)

def json_read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def json_write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def manifest(path):
    if EXPECTED_BYTES <= 0 or not re.fullmatch(r'[a-f0-9]{64}', EXPECTED_SHA):
        raise RuntimeError('Importer not armed: repaired master QC identity is not pinned')
    m = json_read(path)
    if m['slug'] != SLUG or m['sha256'] != EXPECTED_SHA or m['bytes'] != EXPECTED_BYTES:
        raise ValueError('Request does not identify the approved master')
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', m['date']):
        raise ValueError('Invalid output date')
    chunks = m['chunks']
    if not chunks or sum(c['bytes'] for c in chunks) != EXPECTED_BYTES:
        raise ValueError('Chunk byte totals do not match master')
    for c in chunks:
        if not re.fullmatch(r'[a-f0-9]{40}', c['sha']) or not 0 < c['bytes'] <= 3*1024*1024:
            raise ValueError('Invalid chunk descriptor')
    return m

def git_blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()

def download_chunk(c, cache):
    target = cache / c['sha']
    def valid(data):
        return len(data) == c['bytes'] and git_blob_sha(data) == c['sha']
    if target.exists() and valid(target.read_bytes()):
        return target
    token = os.environ['GH_TOKEN']
    error = None
    for attempt in range(3):
        try:
            response = requests.get(
                f'https://api.github.com/repos/{REPOSITORY}/git/blobs/{c["sha"]}',
                headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'},
                timeout=(15, 90))
            response.raise_for_status()
            data = base64.b64decode(response.json()['content'])
            if not valid(data):
                raise ValueError(f'Chunk integrity failure: {c["sha"]}')
            temporary = target.with_suffix('.part')
            temporary.write_bytes(data)
            temporary.replace(target)
            return target
        except (requests.RequestException, ValueError, KeyError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(3 * (attempt+1))
    raise RuntimeError(f'Could not restore chunk {c["sha"]}') from error

def assemble(request):
    m = manifest(request)
    source = request.parent
    outdir = Path('output') / m['date'] / 'reel' / SLUG
    spec = Path('specs/reels') / f'{SLUG}.json'
    tracked = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    already_pushed = any(p.endswith(f'/reel/{SLUG}/pushed.json') for p in tracked)
    if already_pushed or Path(f'data/reel_publish_ledger/{SLUG}.json').exists():
        raise RuntimeError('Existing delivery record: inspect it before importing; never automatically overwrite it')
    cache = Path(os.environ.get('RUNNER_TEMP', '.')) / 'approved-laver-chunks'
    cache.mkdir(parents=True, exist_ok=True)
    outdir.mkdir(parents=True, exist_ok=True)
    spec.parent.mkdir(parents=True, exist_ok=True)
    required = ['spec.json', 'render.json', 'subtitles.ass', 'poster.jpg', 'copy.txt']
    for name in required:
        if not (source / name).is_file():
            raise FileNotFoundError(source / name)
    with ThreadPoolExecutor(max_workers=6) as pool:
        paths = list(pool.map(lambda c: download_chunk(c, cache), m['chunks']))
    film = outdir / f'{SLUG}.mp4'
    digest = hashlib.sha256()
    with film.open('wb') as stream:
        for p in paths:
            data = p.read_bytes()
            digest.update(data)
            stream.write(data)
    if film.stat().st_size != EXPECTED_BYTES or digest.hexdigest() != EXPECTED_SHA:
        raise RuntimeError('Assembled master does not match the approved video')
    shutil.copyfile(source / 'spec.json', spec)
    shutil.copyfile(source / 'copy.txt', spec.with_suffix('.xhs.txt'))
    for name in ['render.json', 'subtitles.ass', 'poster.jpg']:
        shutil.copyfile(source / name, outdir / name)
    for folder in ['subtitle_sources']:
        if (source / folder).is_dir():
            shutil.copytree(source / folder, outdir / folder, dirs_exist_ok=True)
    # These are provenance, never a replacement for native check_reel_landed.py.
    for name in ['import-provenance.json', 'research.md', 'storyboard.md', 'manual-qc.json', 'subtitle_provenance.json']:
        if (source / name).is_file():
            shutil.copyfile(source / name, outdir / name)
    run(sys.executable, 'tools/push_reel.py', '--stage', 'check', '--outdir', str(outdir), '--copy', str(spec.with_suffix('.xhs.txt')))
    run(sys.executable, 'tools/check_reel_landed.py', '--slug', SLUG, '--film', str(film), '--spec', str(spec))
    print(f'Approved master reconstructed and native QC passed: {film}', flush=True)
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as stream:
            stream.write(f'outdir={outdir}\nslug={SLUG}\n')

def release(request):
    m = manifest(request)
    outdir = Path('output') / m['date'] / 'reel' / SLUG
    film = outdir / f'{SLUG}.mp4'
    attestation = json_read(outdir / 'qc_attestation.json')
    if attestation.get('status') != 'pass':
        raise RuntimeError('Native QC has not passed')
    tag = f'reel-{SLUG}'
    existing = subprocess.run(['gh', 'release', 'view', tag, '--json', 'assets'], text=True, capture_output=True)
    if existing.returncode:
        run('gh', 'release', 'create', tag, '--title', '网球有故事 · 拉沃尔杯宿敌同队', '--notes', '已审定竖版成片；按原生质检与微信发布门禁导入。')
        assets = []
    else:
        assets = json.loads(existing.stdout)['assets']
    asset = next((x for x in assets if x['name'] == film.name), None)
    if asset:
        # Never clobber an existing potentially published asset; verify it instead.
        response = requests.get(asset['url'], timeout=(15, 120), stream=True)
        response.raise_for_status()
        digest, size = hashlib.sha256(), 0
        for data in response.iter_content(1024*1024):
            digest.update(data); size += len(data)
        if size != EXPECTED_BYTES or digest.hexdigest() != EXPECTED_SHA:
            raise RuntimeError('Existing Release asset differs; refusing to overwrite')
    else:
        run('gh', 'release', 'upload', tag, str(film))
    result = subprocess.check_output(['gh', 'release', 'view', tag, '--json', 'assets'], text=True)
    asset = next(x for x in json.loads(result)['assets'] if x['name'] == film.name)
    if asset['size'] != EXPECTED_BYTES:
        raise RuntimeError('Release asset byte count mismatch')
    url = asset['url']
    render = json_read(outdir / 'render.json')
    render.update(video_url=url, video_bytes=EXPECTED_BYTES)
    json_write(outdir / 'render.json', render)
    run(sys.executable, 'tools/push_reel.py', '--stage', 'page', '--outdir', str(outdir), '--copy', f'specs/reels/{SLUG}.xhs.txt')
    module_spec = importlib.util.spec_from_file_location('native_push_reel', 'tools/push_reel.py')
    native = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(native)
    copy_path = Path(f'specs/reels/{SLUG}.xhs.txt')
    meta = native.push_meta(copy_path)
    column = native.column_of(copy_path)
    title = native.headline(outdir, column, meta.get('matchup', ''), meta.get('score', ''), meta.get('event', ''), meta['summary'])
    body = native.copy_body_only(native.cut_at_tags(copy_path.read_text(encoding='utf-8')), title)
    page = native.build_html(url, native.copy_page_url(outdir), meta.get('lead', ''), f'{title}\n\n{body}', 'poster.jpg', column)
    (outdir / 'push.html').write_text(page, encoding='utf-8')
    print(f'Release and native pages ready: {url}', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['assemble', 'release'])
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_REPOSITORY', REPOSITORY) != REPOSITORY:
        raise SystemExit('This importer is scoped to robertyang87/tennislive')
    {'assemble': assemble, 'release': release}[args.stage](args.request)
