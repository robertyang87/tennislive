#!/usr/bin/env python3
"""Restore verified transfer objects and publish exact master to Release; never send WeChat."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import requests

SLUG = 'nishikori-career-farewell'
EXPECTED_BYTES = 168982327
EXPECTED_SHA = '39349036a6976639a43fd6d0245b75662ab88cedd8b33827e46683a870e3eabf'
REPOSITORY = 'robertyang87/tennislive'
TAG = 'reel-' + SLUG

def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()

def git_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--proof', required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.request.read_text())
    require(set(manifest) == {'slug', 'bytes', 'sha256', 'chunks'}, 'Unexpected manifest fields')
    require(manifest['slug'] == SLUG and manifest['bytes'] == EXPECTED_BYTES and manifest['sha256'] == EXPECTED_SHA, 'Pinned original master identity differs')
    chunks = manifest['chunks']
    require(chunks and sum(c['bytes'] for c in chunks) == EXPECTED_BYTES, 'Transfer lengths differ')
    for c in chunks:
        require(set(c) == {'sha', 'bytes'} and len(c['sha']) == 40 and all(x in '0123456789abcdef' for x in c['sha']) and 0 < c['bytes'] <= 3145728, 'Invalid transfer object')
    require(os.environ.get('GITHUB_REPOSITORY') == REPOSITORY, 'Unexpected destination repository')
    token = os.environ['GH_TOKEN']
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    directory = Path(os.environ['RUNNER_TEMP']) / 'nishikori-release-import'
    directory.mkdir(parents=True, exist_ok=True)
    def download(c):
        path = directory / c['sha']
        if path.is_file():
            data = path.read_bytes()
            if len(data) == c['bytes'] and git_sha(data) == c['sha']:
                return path
        r = requests.get(f'https://api.github.com/repos/{REPOSITORY}/git/blobs/{c["sha"]}', headers=headers, timeout=(15, 120))
        r.raise_for_status()
        obj = r.json()
        require(obj.get('encoding') == 'base64', 'Unexpected transfer encoding')
        data = base64.b64decode(obj['content'])
        require(len(data) == c['bytes'] and git_sha(data) == c['sha'], 'Transfer object integrity differs')
        path.write_bytes(data)
        return path
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(download, chunks))
    film = directory / (SLUG + '.mp4')
    with film.open('wb') as output:
        for path in paths:
            with path.open('rb') as f:
                for block in iter(lambda: f.read(1048576), b''):
                    output.write(block)
    require(film.stat().st_size == EXPECTED_BYTES and digest(film) == EXPECTED_SHA, 'Reconstructed master differs')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(film)]))
    video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    require((video['width'], video['height']) == (1080, 1440) and video['avg_frame_rate'] == '25/1', 'Canvas/frame rate differs')
    require(abs(float(probe['format']['duration']) - 323.48) <= .08, 'Movie duration differs')
    endpoint = f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{TAG}'
    response = requests.get(endpoint, headers=headers, timeout=30)
    response.raise_for_status()
    release = response.json()
    require(not release.get('draft') and release.get('tag_name') == TAG, 'Expected existing public Release')
    asset = next((a for a in release['assets'] if a['name'] == film.name), None)
    if asset is None:
        subprocess.run(['gh', 'release', 'upload', TAG, str(film), '--repo', REPOSITORY], check=True)
        response = requests.get(endpoint, headers=headers, timeout=30)
        response.raise_for_status()
        asset = next(a for a in response.json()['assets'] if a['name'] == film.name)
    require(asset['size'] == EXPECTED_BYTES and asset.get('digest') == 'sha256:' + EXPECTED_SHA, 'Release asset metadata differs; no clobber attempted')
    canonical = f'https://github.com/{REPOSITORY}/releases/download/{TAG}/{film.name}'
    require(asset['browser_download_url'] == canonical, 'Unexpected canonical Release URL')
    remote = requests.get(canonical, stream=True, timeout=(15, 120))
    remote.raise_for_status()
    h = hashlib.sha256(); size = 0
    for block in remote.iter_content(1048576):
        size += len(block); h.update(block)
    remote.close()
    require(size == EXPECTED_BYTES and h.hexdigest() == EXPECTED_SHA, 'Remote Release bytes differ')
    proof = {'slug': SLUG, 'status': 'release_verified_not_wechat_published', 'video_url': canonical, 'bytes': size, 'sha256': h.hexdigest(), 'asset_digest': asset['digest'], 'asset_id': asset['id'], 'method': 'reconstructed-transfer-objects-and-remote-streaming-GET', 'verified_at': datetime.now(timezone.utc).isoformat(), 'request_sha256': digest(args.request), 'movie_in_git_tree': False, 'wechat_sent': False, 'run_url': f'https://github.com/{REPOSITORY}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'}
    args.proof.parent.mkdir(parents=True, exist_ok=True)
    args.proof.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
        summary.write('\nVerified original master on GitHub Release: ' + canonical + '\n\nNo WeChat notification was sent.\n')
    print('Original master Release asset and remote bytes verified; no WeChat send.')

if __name__ == '__main__':
    main()
