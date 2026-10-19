#!/usr/bin/env python3
"""Actual-byte speech approval. Preparation never approves; publication is read only.

Prepare with the real --bundle before native render_inputs seals
voice_quality_inventory.json. A cleaned bundle is accepted only through that
sealed artifact and the current render's exact frozen-bundle identity.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'voice_quality_inventory.json'
REVIEW = 'voice_quality_review.json'
SCHEMA = 'tennislive.voice-quality.v1'
REQUEST_FIELDS = {'text', 'voice', 'rate', 'pitch', 'style', 'styledegree',
                  'lead_pause', 'backend', 'cache_key'}


class VoiceQualityError(ValueError):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file_sha(path):
    with Path(path).open('rb') as handle:
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
        return digest.hexdigest()


def _read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise VoiceQualityError(f'Missing/invalid {path}') from exc
    if not isinstance(value, dict):
        raise VoiceQualityError(f'Expected object: {path}')
    return value


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def _request(value):
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise VoiceQualityError('Need complete actual synthesis request, not inferred defaults')
    for key in REQUEST_FIELDS - {'lead_pause'}:
        if not isinstance(value[key], str):
            raise VoiceQualityError(f'Invalid request {key}')
    pause = value['lead_pause']
    if isinstance(pause, bool) or not isinstance(pause, (float, int)) or not math.isfinite(pause) or pause < 0:
        raise VoiceQualityError('Invalid actual lead_pause')
    if not value['text'] or not value['voice'] or value['backend'] not in {'azure', 'edge'}:
        raise VoiceQualityError('Empty/invalid actual speech request')
    fields = ['text', 'voice', 'rate', 'pitch', 'style', 'styledegree', 'lead_pause']
    key = _sha('\x1f'.join(str(value[k]) for k in fields).encode())[:32]
    if key != value['cache_key']:
        raise VoiceQualityError('Request cache key differs from actual parameters')
    return value


def _native(outdir):
    return sorted(p for p in outdir.rglob('voice_*.mp3') if p.is_file())


def _words(path):
    for p in (path.with_suffix('.words.json'), path.with_suffix('.marks.json')):
        if p.is_file():
            return p
    raise VoiceQualityError(f'Actual paired words missing: {path}')


def _bundle(path):
    raw = Path(path).read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise VoiceQualityError('Frozen bundle too large')
    try:
        with zipfile.ZipFile(Path(path)) as z:
            if len(z.namelist()) != len(set(z.namelist())):
                raise VoiceQualityError('Duplicate bundle members')
            manifest = json.loads(z.read('manifest.json'))
            if (manifest.get('schema') != 'tennislive.frozen-tts-bundle.v1'
                    or manifest.get('quality_approval') is not False
                    or manifest.get('artifact_kind') != 'native_tts_inputs'):
                raise VoiceQualityError('Invalid input-bundle identity')
            entries = []
            for item in manifest.get('entries') or []:
                request = _request(item['request'])
                rid = _sha(_canonical(request))
                if item.get('request_id') != rid:
                    raise VoiceQualityError('Frozen request ID mismatch')
                audio = z.read(f'requests/{rid}/audio.mp3')
                words = z.read(f'requests/{rid}/marks.json')
                if (not audio or _sha(audio) != item['audio_sha256']
                        or _sha(words) != item['marks_sha256']):
                    raise VoiceQualityError('Frozen actual audio/words hash mismatch')
                marks = json.loads(words)
                if not isinstance(marks, list) or not marks:
                    raise VoiceQualityError('Missing actual word boundaries')
                entries.append({'id': f'bundle:{rid}', 'request_id': rid,
                                'request': request, 'audio_sha256': _sha(audio),
                                'words_sha256': _sha(words)})
            if not entries or len({e['id'] for e in entries}) != len(entries):
                raise VoiceQualityError('Empty/duplicate frozen request inventory')
            return _sha(raw), entries
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        if isinstance(exc, VoiceQualityError):
            raise
        raise VoiceQualityError(f'Cannot verify actual frozen bundle: {exc}') from exc


def _bundle_path(outdir, root, render, supplied=None):
    if supplied:
        return Path(supplied)
    digest = (render.get('tts_bundle') or {}).get('bundle_sha256', '')
    candidates = [outdir / 'tts_bundle.zip', root / 'assets/tts-bundles' /
                  outdir.name / digest / 'tts_bundle.zip'] if digest else []
    return next((p for p in candidates if p.is_file()), None)


def _make_inventory(outdir, root, render, supplied=None):
    path = _bundle_path(outdir, root, render, supplied)
    frozen = render.get('tts_bundle') or {}
    entries, bundle_sha = [], None
    if path:
        bundle_sha, entries = _bundle(path)
        if (bundle_sha != frozen.get('bundle_sha256')
                or len(entries) != frozen.get('request_count')):
            raise VoiceQualityError('Actual bundle differs from current render')
    locals_ = []
    for audio in _native(outdir):
        words = _words(audio)
        ah = _file_sha(audio)
        wh = _file_sha(words)
        if path:
            matches = [e for e in entries if e['audio_sha256'] == ah]
            if not matches:
                raise VoiceQualityError(f'Unbound native speech: {audio}')
            # Native JSON formatting may differ; bytes remain separately bound.
            with zipfile.ZipFile(path) as z:
                valid = [e for e in matches if json.loads(words.read_bytes()) == json.loads(
                    z.read(f"requests/{e['request_id']}/marks.json"))]
            if len(valid) != 1:
                raise VoiceQualityError(f'Unbound/ambiguous actual words: {words}')
            request = valid[0]['request']
        else:
            request = _request(_read(audio.with_suffix('.request.json')))
        locals_.append({'id': audio.relative_to(outdir).as_posix(),
                        'audio_sha256': ah, 'words_sha256': wh,
                        'words_path': words.relative_to(outdir).as_posix(),
                        'request': request})
    if frozen and not path:
        raise VoiceQualityError('Real frozen bundle required for preparation; use --bundle')
    if not entries and not locals_:
        raise VoiceQualityError('No verified complete native speech inventory')
    return {'schema': SCHEMA + '.inventory', 'bundle_sha256': bundle_sha,
            'bundle_request_count': len(entries), 'entries': entries + locals_}


def _identity(outdir, root, render):
    manifest = _read(outdir / 'render_inputs.json')
    manifest_sha = _file_sha(outdir / 'render_inputs.json')
    if render.get('render_inputs_sha256') != manifest_sha:
        raise VoiceQualityError('Current render_inputs hash mismatch')
    film_sha = render.get('film_sha256')
    if not re.fullmatch('[0-9a-f]{64}', str(film_sha)) or film_sha != manifest.get('film_sha256'):
        raise VoiceQualityError('Current film identity is not sealed')
    # Formal movie only: source clips/temporary segment MP4s are not the film.
    film = outdir / f'{outdir.name}.mp4'
    if film.is_file() and (_file_sha(film) != film_sha
                          or film.stat().st_size != manifest.get('film_bytes')):
        raise VoiceQualityError(f'Local formal film differs from current render: {film}')
    spec_sha = manifest.get('spec_sha256')
    candidates = [root / f'specs/{kind}/{outdir.name}.json'
                  for kind in ('reels', 'interviews', 'explainers')]
    spec = next((p for p in candidates if p.is_file()), None)
    if spec is None:
        raise VoiceQualityError('Current reel/interview spec is unavailable; other lanes need explicit native provenance support')
    if _file_sha(spec) != spec_sha:
        raise VoiceQualityError('Current spec differs from actual render')
    if not re.fullmatch('[0-9a-f]{64}', str(spec_sha)):
        raise VoiceQualityError('Missing actual spec identity')
    return {'render_sha256': _file_sha(outdir / 'render.json'),
            'render_inputs_sha256': manifest_sha, 'spec_sha256': spec_sha,
            'film_sha256': film_sha}, manifest


def capture_inventory(outdir, *, spec=None, bundle=None, root=ROOT):
    """Capture actual native inputs before normal manifest sealing; no approval."""
    outdir, root = Path(outdir).resolve(), Path(root).resolve()
    inventory = _make_inventory(outdir, root, _read(outdir / 'render.json'), bundle)
    path = outdir / INVENTORY
    encoded = json.dumps(inventory, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') != encoded:
        raise VoiceQualityError('Existing inventory differs; preserve original actual inputs')
    path.write_text(encoded, encoding='utf-8')
    return path


def _sealed_inventory(outdir, render, manifest):
    inventory = _read(outdir / INVENTORY)
    if (manifest.get('artifacts') or {}).get(INVENTORY) != _file_sha(outdir / INVENTORY):
        raise VoiceQualityError('Native speech inventory must be sealed by render_inputs artifacts')
    frozen = render.get('tts_bundle') or {}
    if frozen and (inventory.get('bundle_sha256') != frozen.get('bundle_sha256')
                   or inventory.get('bundle_request_count') != frozen.get('request_count')):
        raise VoiceQualityError('Sealed inventory differs from rendered frozen bundle')
    return inventory


def prepare(outdir, *, root=ROOT, bundle=None):
    outdir, root = Path(outdir).resolve(), Path(root).resolve()
    review_path = outdir / REVIEW
    if review_path.exists():
        raise VoiceQualityError('Review already exists; preserve it, do not overwrite approval')
    render = _read(outdir / 'render.json')
    identity, manifest = _identity(outdir, root, render)
    archive = outdir / INVENTORY
    if archive.exists() and bundle is None:
        inventory = _sealed_inventory(outdir, render, manifest)
    else:
        capture_inventory(outdir, root=root, bundle=bundle)
        inventory = _read(archive)
    identity['inventory_sha256'] = _file_sha(archive)
    scope = {'status': 'pending', 'method': '', 'reviewer': '',
             'reviewed_at': '', 'whole_audio': False,
             'audio_sha256': '', 'observations': ''}
    review = {'schema': SCHEMA, 'identity': identity,
              'film_review': {'status': 'pending', 'method': '', 'reviewer': '',
                              'reviewed_at': '', 'film_sha256': '',
                              'whole_narration_and_seams': False, 'observations': ''},
              'entries': [{'id': e['id'], 'phonetics': dict(scope),
                           'prosody': dict(scope)} for e in inventory['entries']]}
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return review_path


def require_publish(outdir, *, root=ROOT):
    """Read-only, fail closed; never fetch, synthesize or manufacture approval."""
    outdir, root = Path(outdir).resolve(), Path(root).resolve()
    render = _read(outdir / 'render.json')
    identity, manifest = _identity(outdir, root, render)
    inventory = _read(outdir / INVENTORY)
    identity['inventory_sha256'] = _file_sha(outdir / INVENTORY)
    sealed = (manifest.get('artifacts') or {}).get(INVENTORY)
    if sealed != identity['inventory_sha256']:
        raise VoiceQualityError('Native speech inventory must be sealed by render_inputs artifacts')
    if inventory.get('schema') != SCHEMA + '.inventory' or not inventory.get('entries'):
        raise VoiceQualityError('Missing complete actual speech inventory')
    frozen = render.get('tts_bundle') or {}
    if frozen:
        if (inventory.get('bundle_sha256') != frozen.get('bundle_sha256')
                or inventory.get('bundle_request_count') != frozen.get('request_count')):
            raise VoiceQualityError('Sealed inventory differs from rendered frozen bundle')
        bundled = [e for e in inventory['entries'] if e['id'].startswith('bundle:')]
        if len(bundled) != frozen['request_count']:
            raise VoiceQualityError('Incomplete frozen request inventory')
    actual = {p.relative_to(outdir).as_posix(): p for p in _native(outdir)}
    recorded = {e['id']: e for e in inventory['entries']}
    if len(recorded) != len(inventory['entries']):
        raise VoiceQualityError('Duplicate speech inventory entries')
    for key, audio in actual.items():
        if key not in recorded:
            raise VoiceQualityError(f'Unreviewed native speech appeared: {key}')
        e = recorded[key]
        if _file_sha(audio) != e['audio_sha256'] or _file_sha(_words(audio)) != e['words_sha256']:
            raise VoiceQualityError(f'Actual native bytes changed: {key}')
    review = _read(outdir / REVIEW)
    if review.get('schema') != SCHEMA or review.get('identity') != identity:
        raise VoiceQualityError('Voice approval is stale for current spec/render/film/inventory')
    film_review = review.get('film_review') or {}
    if (film_review.get('status') != 'pass'
            or film_review.get('method') != 'full_audio_listening'
            or film_review.get('whole_narration_and_seams') is not True
            or film_review.get('film_sha256') != identity['film_sha256']
            or not str(film_review.get('reviewer') or '').strip()
            or not str(film_review.get('observations') or '').strip()):
        raise VoiceQualityError('Actual complete film narration/seams listening is pending')
    try:
        stamp = datetime.fromisoformat(str(film_review.get('reviewed_at')).replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timezone missing')
    except ValueError as exc:
        raise VoiceQualityError('Actual film review timestamp required') from exc
    rows = review.get('entries') or []
    approvals = {r.get('id'): r for r in rows}
    if len(approvals) != len(rows) or set(approvals) != set(recorded):
        raise VoiceQualityError('Review must cover every actual native speech entry')
    for key, entry in recorded.items():
        _request(entry['request'])
        for name in ('phonetics', 'prosody'):
            scope = approvals[key].get(name) or {}
            if (scope.get('status') != 'pass' or scope.get('method') != 'full_audio_listening'
                    or scope.get('whole_audio') is not True
                    or scope.get('audio_sha256') != entry['audio_sha256']
                    or not str(scope.get('reviewer') or '').strip()
                    or not str(scope.get('observations') or '').strip()):
                raise VoiceQualityError(f'{key} {name}: actual complete audio review is pending')
            try:
                stamp = datetime.fromisoformat(str(scope.get('reviewed_at')).replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    raise ValueError('timezone missing')
            except ValueError as exc:
                raise VoiceQualityError(f'{key} {name}: real review timestamp required') from exc
    return identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--spec', type=Path)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--capture', action='store_true', help='Capture actual inputs only, before normal render_inputs sealing')
    choice.add_argument('--prepare', action='store_true')
    choice.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.capture:
            result = capture_inventory(args.outdir, spec=args.spec, root=args.root, bundle=args.bundle)
        elif args.prepare:
            result = prepare(args.outdir, root=args.root, bundle=args.bundle)
        else:
            result = require_publish(args.outdir, root=args.root)
        print(result)
        return 0
    except (VoiceQualityError, OSError, ValueError, KeyError) as exc:
        print(f'waiting_voice_quality_review: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
