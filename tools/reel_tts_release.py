#!/usr/bin/env python3
"""Transport the finite, already validated TTS bundle; never approve audio/QC."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))
from tennislive.video.tts_bundle import validate_bundle  # noqa: E402

REPO = 'robertyang87/tennislive'
ASSET = 'tts_bundle.zip'
SCHEMA = 'tennislive.frozen-tts-bundle.v1'


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def gh(*args: str) -> str:
    proc = subprocess.run(['gh', *args, '--repo', REPO], capture_output=True, text=True)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or 'GitHub transport failed')
    return proc.stdout


def identity(slug: str, record: dict) -> tuple[str, str]:
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,150}', slug):
        raise ValueError('Invalid reel slug')
    if not isinstance(record, dict):
        raise ValueError('Invalid producer bundle identity')
    sha = record.get('bundle_sha256', '')
    if (record.get('schema') != SCHEMA or not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{64}', sha)
            or record.get('artifact_kind') != 'native_tts_inputs'
            or record.get('quality_approval') is not False):
        raise ValueError('Missing producer bundle identity; this is not a QC approval')
    tag = f'reel-tts-{slug}-{sha[:16]}'
    return tag, f'https://github.com/{REPO}/releases/download/{tag}/{ASSET}'


def verify_producer(slug: str, record: dict, bundle: Path) -> None:
    report = validate_bundle(bundle, decode_audio=False)
    if (report['bundle_sha256'] != record['bundle_sha256']
            or report['request_count'] != record.get('request_count')
            or report['metadata'].get('slug') != slug
            or report['metadata'].get('kind') != 'reel_native_tts'):
        raise ValueError('Bundle producer manifest differs from slug/record identity')


def download(tag: str, sha: str, output: Path, *, slug: str, record: dict) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        gh('release', 'download', tag, '--pattern', ASSET, '--dir', tmp)
        downloaded = Path(tmp) / ASSET
        if digest(downloaded) != sha:
            raise ValueError('Release bundle hash mismatch; refusing fresh synthesis fallback')
        verify_producer(slug, record, downloaded)
        os.replace(downloaded, output)


def restore(slug: str, metadata: Path, output: Path, fallback_metadata: Path | None = None) -> bool:
    data = json.loads(metadata.read_text()) if metadata.exists() else {}
    record = data.get('tts_bundle')
    if record is None and fallback_metadata is not None and fallback_metadata.exists():
        record = json.loads(fallback_metadata.read_text()).get('tts_bundle')
    if record is None:
        if output.exists():
            raise ValueError('Unclaimed frozen bundle already exists at output')
        print('No frozen TTS bundle recorded; normal first synthesis applies.')
        return False
    tag, url = identity(slug, record)
    if record.get('release_tag') != tag or record.get('url') != url or record.get('file_name') != ASSET:
        raise ValueError('Frozen bundle locator missing or inconsistent; rerun narration to publish it')
    if not output.exists() or digest(output) != record['bundle_sha256']:
        download(tag, record['bundle_sha256'], output, slug=slug, record=record)
    else:
        verify_producer(slug, record, output)
    print(f'Restored exact TTS bytes: {record["bundle_sha256"]}')
    return True


def publish(slug: str, bundle: Path, metadata: Path) -> dict:
    data = json.loads(metadata.read_text())
    record = data.get('tts_bundle', {})
    tag, url = identity(slug, record)
    sha = record['bundle_sha256']
    if digest(bundle) != sha:
        raise ValueError('Producer/export bundle hash mismatch')
    verify_producer(slug, record, bundle)
    try:
        release = json.loads(gh('release', 'view', tag, '--json', 'assets'))
    except RuntimeError as exc:
        if not any(text in str(exc).lower() for text in ('release not found', 'http 404')):
            raise
        # No clobber: a concurrent publication must be verified before reuse.
        try:
            gh('release', 'create', tag, '--target', os.environ.get('GITHUB_SHA', 'main'),
               '--title', f'{slug} · 实际配音快照', '--notes',
               'Only native TTS inputs and WordBoundary marks. This is not a film or QC approval.',
               '--latest=false')
        except RuntimeError:
            gh('release', 'view', tag, '--json', 'assets')
        release = json.loads(gh('release', 'view', tag, '--json', 'assets'))
    existing = any(asset.get('name') == ASSET for asset in release.get('assets', []))
    if not existing:
        with tempfile.TemporaryDirectory() as tmp:
            named = Path(tmp) / ASSET
            shutil.copyfile(bundle, named)
            try:
                gh('release', 'upload', tag, str(named))
            except RuntimeError:
                # Concurrent same-tag upload is safe only after exact byte verification.
                download(tag, sha, Path(tmp) / 'verified.zip', slug=slug, record=record)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            download(tag, sha, Path(tmp) / ASSET, slug=slug, record=record)
    record.update(release_tag=tag, url=url, file_name=ASSET)
    if os.environ.get('GITHUB_RUN_ID'):
        record['source_run'] = f'https://github.com/{REPO}/actions/runs/{os.environ["GITHUB_RUN_ID"]}'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=metadata.parent, delete=False) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        temp = Path(stream.name)
    os.replace(temp, metadata)
    print(f'Frozen TTS bundle: {url} ({sha})')
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('publish', 'restore'):
        cli = sub.add_parser(command)
        cli.add_argument('--slug', required=True)
        cli.add_argument('--metadata', required=True, type=Path)
        cli.add_argument('--bundle' if command == 'publish' else '--output', required=True, type=Path)
        if command == 'restore':
            cli.add_argument('--fallback-metadata', type=Path,
                             help='Previous render metadata, only when narration has no bundle claim')
    args = parser.parse_args()
    if args.command == 'publish':
        publish(args.slug, args.bundle, args.metadata)
    else:
        restore(args.slug, args.metadata, args.output, args.fallback_metadata)


if __name__ == '__main__':
    main()
