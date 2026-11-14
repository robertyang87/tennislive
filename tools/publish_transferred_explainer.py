"""Restore exact reviewed bytes to Release before the existing native sender runs.

The content-addressed chunks are transport only; movies never enter a git tree.
This step runs before reserving a send, so a failed transfer cannot mark a message sent.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess

from voice_quality_gate import require_publish


def publish(outdir: Path, *, restore_only: bool = False) -> None:
    meta = json.loads((outdir / 'render.json').read_text())
    transfer = json.loads((outdir / 'transfer.json').read_text())
    slug = outdir.name
    if meta.get('slug') != slug or not re.fullmatch(r'[a-z0-9-]+', slug):
        raise ValueError('Invalid exact episode identity')
    if transfer.get('film_sha256') != meta['film_sha256'] or transfer.get('film_bytes') != meta['video_bytes']:
        raise ValueError('Transfer differs from reviewed movie')
    qc = json.loads((outdir / 'qc_attestation.json').read_text())
    audio = json.loads((outdir / 'actual-audio-binding.json').read_text())
    if qc.get('film_sha256') != meta['film_sha256'] or qc.get('black_frames_detected') is not False:
        raise ValueError('Current film visual QC is missing')
    if audio.get('film_sha256') != meta['film_sha256'] or audio.get('all_pass') is not True:
        raise ValueError('Current actual-film speech binding is missing')
    require_publish(outdir)
    film = outdir / f'{slug}.mp4'
    temp = outdir / f'{slug}.transfer.tmp'
    digest = hashlib.sha256()
    with temp.open('wb') as handle:
        for chunk in transfer['chunks']:
            sha = chunk['sha']
            if not re.fullmatch(r'[a-f0-9]{40}', sha):
                raise ValueError('Invalid content-addressed chunk')
            encoded = subprocess.check_output(['gh', 'api', f'repos/robertyang87/tennislive/git/blobs/{sha}', '--jq', '.content'])
            data = base64.b64decode(encoded)
            if len(data) != chunk['bytes'] or hashlib.sha256(data).hexdigest() != chunk['sha256']:
                raise ValueError('Actual transport bytes differ')
            digest.update(data)
            handle.write(data)
    if temp.stat().st_size != meta['video_bytes'] or digest.hexdigest() != meta['film_sha256']:
        raise ValueError('Restored movie identity differs')
    temp.replace(film)
    require_publish(outdir)
    if restore_only:
        print('Exact reviewed movie restored; native gate passed.')
        return
    subprocess.run(['gh', 'release', 'upload', slug, str(film), str(outdir / 'poster.jpg'), str(outdir / 'analysis.txt'), '--clobber'], check=True)
    assets = json.loads(subprocess.check_output(['gh', 'release', 'view', slug, '--json', 'assets']))['assets']
    asset = next(a for a in assets if a['name'] == film.name)
    if asset['size'] != meta['video_bytes']:
        raise ValueError('Uploaded movie size differs')
    if asset.get('digest') and asset['digest'] != 'sha256:' + meta['film_sha256']:
        raise ValueError('Uploaded movie digest differs')
    subprocess.run(['gh', 'release', 'edit', slug, '--draft=false', '--notes-file', str(outdir / 'analysis.txt')], check=True)
    print('Exact reviewed movie is on Release; native sender remains mandatory.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--restore-only', action='store_true')
    args = parser.parse_args()
    publish(args.outdir, restore_only=args.restore_only)
