#!/usr/bin/env python3
"""Compose verified native video and native audio by stream copy; never publish/send.

Both inputs must be original match-reel runs of this slug. Their immutable native
manifests, source assets, recipes, timelines and compressed packets are checked.
The resulting movie gets a NEW native input manifest and MUST pass native QC.
"""
from __future__ import annotations
import argparse
import base64
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_inputs as ri
from foreground_audio_gate import bind_sources, plan_hash, record_timeline, require
from stage_reel_sources import stage_one, reviewed_source_hashes
from build_match_reel import spec_source_fallbacks, _seg_voice, _tts_content_key, speakable

ROOT = Path(__file__).resolve().parents[1]
REPO = 'robertyang87/tennislive'


def run(*args):
    subprocess.run(list(map(str, args)), check=True)


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', f'repos/{REPO}/{path}'], text=True))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def source_run(slug, run_id):
    record = api(f'actions/runs/{int(run_id)}')
    if (record['event'] != 'workflow_dispatch' or record['path'] != '.github/workflows/match-reel.yml'
            or record['status'] != 'completed' or record['conclusion'] not in ('success', 'failure')):
        raise ValueError('Input is not a completed native match-reel render run')
    artifacts = []
    page = 1
    while True:
        batch = api(f'actions/runs/{int(run_id)}/artifacts?per_page=100&page={page}')['artifacts']
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    native_name = f"native-input-{slug}-{record['run_number']}"
    native = [a for a in artifacts if a['name'] == native_name]
    # An expired/ambiguous native archive is an error, not permission to hide
    # it behind the mutable canonical Release or old diagnostic artifact.
    if native and (len(native) != 1 or native[0]['expired']):
        raise ValueError('Exactly one unexpired original native input archive is required')
    name = native_name if native else f"reel-{slug}-{record['run_number']}"
    matches = [a for a in artifacts if a['name'] == name and not a['expired']]
    if len(matches) != 1:
        raise ValueError('Exactly one actual native reel artifact is required')
    record['_native_input_archive'] = bool(native)
    return record, matches[0]


def source_spec(slug, head):
    doc = api(f'contents/specs/reels/{slug}.json?ref={head}')
    return base64.b64decode(doc['content'])


def fetch(slug, run_id, directory):
    record, artifact = source_run(slug, run_id)
    if directory.exists():
        raise ValueError('Refusing to overwrite an existing artifact directory')
    directory.mkdir(parents=True)
    run('gh', 'run', 'download', run_id, '--repo', REPO, '--name', artifact['name'], '--dir', directory)
    write(directory / 'native-run-origin.json', {'run': record, 'artifact': artifact})


def _scoreboard_rows(directory):
    """没有记分板改动的片子（规则图、纯解说剪辑）不写 scoreboard_qc.json：没有蒙版就没有要核的行。"""
    path = directory / 'scoreboard_qc.json'
    return json.loads(path.read_text()).get('segments', []) if path.is_file() else []


def verified_input(slug, directory, record, original_spec):
    manifest = json.loads((directory / 'render_inputs.json').read_text())
    meta = json.loads((directory / 'render.json').read_text())
    binding = json.loads((directory / 'audio_review_binding.json').read_text())
    if (not ri.same_rules(manifest) or manifest['slug'] != slug
            or manifest['code_sha'] != record['head_sha']
            or manifest['spec_sha256'] != ri.sha256_bytes(original_spec)
            or meta['render_inputs_sha256'] != ri.sha256_file(directory / 'render_inputs.json')
            or manifest['projection_sha256'] != ri.sha256_bytes(ri.canonical(manifest['projection']).encode())
            or ri.canonical(ri.project(json.loads(original_spec))) != ri.canonical(manifest['projection'])):
        raise ValueError('Native run/head/spec/manifest identity differs')
    for name, digest in manifest['artifacts'].items():
        path = directory / name
        if Path(name).name != name or not path.is_file() or ri.sha256_file(path) != digest:
            raise ValueError(f'Native artifact bytes differ: {name}')
    for row in _scoreboard_rows(directory):
        mask = directory / 'score_masks' / Path(row['mask']).name
        if not mask.is_file() or ri.sha256_file(mask) != row['mask_sha256']:
            raise ValueError('Original video scoreboard mask differs')
    film = directory / f'{slug}.mp4'
    if record.get('_native_input_archive'):
        verify_native_archive(slug, directory, record, manifest)
    if not film.is_file():
        url = meta.get('video_url')
        expected = f'https://github.com/{REPO}/releases/download/reel-{slug}/{slug}.mp4'
        if url != expected:
            raise ValueError('No exact native movie or canonical Release URL')
        with requests.get(url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()
            with film.open('wb') as handle:
                for block in response.iter_content(1024 * 1024): handle.write(block)
    if ri.sha256_file(film) != manifest['film_sha256'] or film.stat().st_size != manifest['film_bytes']:
        raise ValueError('Actual input movie SHA/bytes differ from native manifest')
    return manifest, meta, binding, film


def _archive_qc(directory, manifest):
    meta = json.loads((directory / 'render.json').read_text())
    path = directory / 'qc_attestation.json'
    qc = json.loads(path.read_text())
    if (qc.get('status') != 'pass' or qc.get('slug') != manifest['slug']
            or qc.get('spec_sha256') != manifest['spec_sha256']
            or qc.get('film_sha256') != manifest['film_sha256']
            or qc.get('film_bytes') != manifest['film_bytes']
            or qc.get('ass_sha256') != ri.sha256_file(directory / 'subtitles.ass')
            or qc.get('render_inputs_sha256') != ri.sha256_file(directory / 'render_inputs.json')
            or meta.get('qc_attestation_sha256') != ri.sha256_file(path)):
        raise ValueError('Native archive needs actual matching passing QC')


def native_archive_paths(slug, directory, record, original_spec):
    """Whitelist original files in place; no source/cookie/media staging copies."""
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug):
        raise ValueError('Invalid archive slug')
    manifest, meta, _, film = verified_input(slug, directory, record, original_spec)
    _archive_qc(directory, manifest)
    if not set(manifest['artifacts']).issubset(ri.ARTIFACTS):
        raise ValueError('Native render archive has unknown declared output files')
    names = {film.name, 'render.json', 'render_inputs.json', 'qc_attestation.json', *manifest['artifacts']}
    for row in _scoreboard_rows(directory):
        names.add('score_masks/' + Path(row['mask']).name)
    names.update(archive_voice_names(manifest['projection'], meta))
    for name in names:
        path = directory / name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f'Missing/unsafe actual native archive file: {name}')
    identity = {'schema': 'tennislive.native-input-archive.v1', 'slug': slug,
                'run_id': int(record['id']), 'run_number': int(record['run_number']),
                'head_sha': record['head_sha'], 'film_sha256': manifest['film_sha256'],
                'files': {name: ri.sha256_file(directory / name) for name in sorted(names)}}
    write(directory / 'native_input_archive.json', identity)
    return [directory / name for name in sorted(names | {'native_input_archive.json'})]


def archive_voice_names(projection, meta):
    """Same enabled cover/outro semantics as render; never glob voice files."""
    prefixes = [f'voice_{index:02d}' for index, segment in enumerate(projection.get('segments', []))
                if str(segment.get('narration') or '').strip()]
    cover_enabled = bool(str((projection.get('cover') or {}).get('narration') or '').strip())
    if meta.get('cover_narrated') is not cover_enabled:
        raise ValueError('Native cover narration disagrees with render projection')
    if cover_enabled:
        prefixes.append('voice_cover')
    seconds = meta.get('outro_seconds')
    if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds) or seconds < 0
            or (seconds > 0) != (projection.get('outro', True) is not False)):
        raise ValueError('Native outro narration disagrees with actual render duration/projection')
    if seconds > 0:
        prefixes.append('voice_outro')
    return {prefix + suffix for prefix in prefixes for suffix in ('.mp3', '.words.json')}


def verify_native_archive(slug, directory, record, manifest):
    archive = json.loads((directory / 'native_input_archive.json').read_text())
    if (archive.get('schema') != 'tennislive.native-input-archive.v1'
            or archive.get('slug') != slug or archive.get('run_id') != record['id']
            or archive.get('run_number') != record['run_number']
            or archive.get('head_sha') != record['head_sha']
            or archive.get('film_sha256') != manifest['film_sha256']):
        raise ValueError('Native archive run/head/movie identity differs')
    files = archive.get('files')
    required = {f'{slug}.mp4', 'render.json', 'render_inputs.json', 'qc_attestation.json', *manifest['artifacts']}
    meta = json.loads((directory / 'render.json').read_text())
    required.update(archive_voice_names(manifest['projection'], meta))
    if not isinstance(files, dict) or not required.issubset(files):
        raise ValueError('Native archive missing declared original files or voice pair')
    for name, digest in files.items():
        path = directory / name
        if (path.is_symlink() or not path.resolve().is_relative_to(directory.resolve())
                or not path.is_file() or ri.sha256_file(path) != digest):
            raise ValueError(f'Native archive actual file differs: {name}')
    _archive_qc(directory, manifest)


def video_projection(projection):
    result = copy.deepcopy(projection)
    # Only bed can differ; source windows, crop, captions, voices and all other
    # renderer inputs remain checked. Bed has no effect on pixels.
    for segment in result.get('segments', []): segment.pop('bed', None)
    return result


def verify_recipes(spec, video, audio, video_meta, audio_meta, video_binding, audio_binding, repo):
    if ri.canonical(video_projection(ri.project(spec))) != ri.canonical(video_projection(video['projection'])):
        raise ValueError('Current video recipe differs from the input video')
    if plan_hash(spec) != audio_binding['plan_sha256'] or plan_hash(audio['projection']) != plan_hash(spec):
        raise ValueError('Current audio recipe differs from the input audio')
    if video_binding['sources'] != audio_binding['sources'] or video_binding['timeline'] != audio_binding['timeline']:
        raise ValueError('Input source identity/timeline differs')
    # Audio plan does not include voice settings or card/cover speech parameters.
    # Everything else in the projections may differ ONLY in subtitle positioning.
    visual_keys = {'subtitle_bottom', 'subtitle_bottom_windows'}
    left, right = copy.deepcopy(ri.project(spec)), copy.deepcopy(audio['projection'])
    for value in (left, right):
        for segment in value.get('segments', []):
            for key in visual_keys: segment.pop(key, None)
            # Caption revision can reinsert bed at another key position. Its
            # value is still checked; segment bed lookup never iterates keys.
            if 'bed' in segment: segment['bed'] = segment.pop('bed')
    if ri.canonical(left) != ri.canonical(right):
        raise ValueError('Input audio voice/content or another unchecked setting differs')
    for key in ('cover_seconds', 'outro_seconds', 'film_seconds', 'segments_seconds',
                'narration_voice', 'narration_rate', 'narration_backend', 'narration_seconds'):
        if video_meta.get(key) != audio_meta.get(key):
            raise ValueError(f'Input runtime audio/timing differs: {key}')
    if video['assets'] != audio['assets'] or ri.asset_problems(json.dumps(spec).encode(), video, repo):
        raise ValueError('Input assets differ from each other/current assets')


def packets(film, stream):
    rows = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', stream, '-show_packets', '-show_data_hash', 'sha256',
        '-show_entries', 'packet=pts_time,dts_time,duration_time,size,data_hash', '-of', 'json', str(film)], text=True))['packets']
    if not rows or any(not r.get('data_hash', '').startswith('SHA256:') for r in rows):
        raise ValueError('No actual compressed packet hash evidence')
    return rows


def packet_proof(input_film, output_film, stream):
    original, composed = packets(input_film, stream), packets(output_film, stream)
    if original != composed:
        raise ValueError(f'Compressed payload or packet timestamps changed: {stream}')
    digest = ri.sha256_bytes(ri.canonical(original).encode())
    return {'stream': stream, 'packet_count': len(original), 'payload_and_timestamps_sha256': digest,
            'input_film_sha256': ri.sha256_file(input_film), 'output_film_sha256': ri.sha256_file(output_film),
            'exact_payload_and_timestamps_match': True}


def verify_remote_release(url, expected_sha, expected_bytes, asset_id, *, retry_wait=2):
    """Verify actual full bytes, avoiding a stale canonical redirect after clobber.

    A digest-bearing public query is a cache key, never a relaxation of SHA.
    The exact new API asset ID provides an independent transport fallback.
    """
    published_url = f'{url}?v={expected_sha[:12]}'
    candidates = [published_url, f'https://api.github.com/repos/{REPO}/releases/assets/{int(asset_id)}',
                  f'{published_url}&verification_attempt={time.time_ns()}']
    asset_id_verified = False
    for index, candidate in enumerate(candidates):
        headers = {}
        if candidate.startswith('https://api.github.com/'):
            headers['Accept'] = 'application/octet-stream'
            token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
            if token: headers['Authorization'] = f'Bearer {token}'
        try:
            digest = hashlib.sha256(); size = 0
            with requests.get(candidate, headers=headers, stream=True, timeout=(15, 120)) as response:
                response.raise_for_status()
                for block in response.iter_content(1024 * 1024): digest.update(block); size += len(block)
            if digest.hexdigest() == expected_sha and size == expected_bytes:
                if index == 1:
                    # The API proves the asset, not the public button URL.
                    asset_id_verified = True
                    continue
                return {'sha256': digest.hexdigest(), 'bytes': size, 'asset_id': int(asset_id),
                        'canonical_url': url, 'published_url': candidate,
                        'asset_id_verified': asset_id_verified,
                        'verification_transport': 'digest_bound_public_url'}
            print(f'[Release] Attempt {index+1}: stale/different bytes, refusing acceptance')
        except requests.RequestException:
            print(f'[Release] Attempt {index+1}: transport error, no acceptance')
        if index + 1 < len(candidates) and retry_wait: time.sleep(retry_wait)
    raise ValueError('Actual remote Release bytes differ after bounded independent full-hash verification')


def import_voice_pairs(spec, audio_meta, audio_dir, outdir, audio_film=None, timeline=None):
    from natural_quiet_audio import _complete_voice_pair, pcm
    cache = Path(os.environ.get('TENNISLIVE_TTS_CACHE', str(Path.home() / '.cache/tennislive-tts'))).expanduser()
    proofs = []
    final = pcm(audio_film) if audio_film is not None else None
    for index, segment in enumerate(spec.get('segments', [])):
        if not segment.get('narration'): continue
        voice = audio_dir / f'voice_{index:02d}.mp3'
        marks_path = voice.with_suffix('.words.json')
        rate, pitch, style, degree, lead = _seg_voice(segment, index)
        key = _tts_content_key(speakable(segment['narration']), audio_meta['narration_voice'],
                               rate or audio_meta['narration_rate'], pitch or '+0Hz', style, degree, lead)
        archive = audio_dir / f'voice_{index:02d}.native.zip'
        candidate = archive if archive.exists() else cache / f'{key}-edge-v2.zip'
        matched = False
        if candidate.is_file():
            with zipfile.ZipFile(candidate) as bundle:
                matched = (bundle.read('audio.mp3') == voice.read_bytes()
                           and json.loads(bundle.read('marks.json')) == json.loads(marks_path.read_text()))
        if matched:
            if candidate != archive: shutil.copy2(candidate, archive)
            pair_source = 'actual_matching_native_pair_archive'
        else:
            if audio_film is None or timeline is None:
                raise ValueError('Artifact pair repack requires actual native movie authentication')
            # These two files were exported by the SAME authenticated native
            # run artifact. Only their transport wrapper is new. No synthesis,
            # inferred tokens/marks or local substitute MP3 is permitted.
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as bundle:
                bundle.writestr('audio.mp3', voice.read_bytes())
                bundle.writestr('marks.json', marks_path.read_bytes())
            pair_source = 'native_run_artifact_pair_repack'
        auth = _complete_voice_pair(spec, audio_film, index, float(timeline['offsets'][index]), final)
        if auth is None:
            raise ValueError('Actual paired whole utterance/marks do not match the native input AAC')
        for path in (voice, marks_path): shutil.copy2(path, outdir / path.name)
        shutil.copy2(archive, outdir / f'voice_{index:02d}.native.zip')
        proofs.append({'segment': index, 'mp3_sha256': ri.sha256_file(voice),
                       'marks_sha256': ri.sha256_file(marks_path), 'native_zip_sha256': ri.sha256_file(archive),
                       'pair_source': pair_source, 'wrapper_sha256': ri.sha256_file(archive),
                       'original_cache_archive_claimed': matched and candidate.parent == cache,
                       'actual_input_aac_correlation': auth['voice_correlation'],
                       'actual_input_aac_gain': auth['voice_gain'], 'complete_text_and_monotonic_word_marks_authenticated': True})
    return proofs


def compose(args):
    slug = args.slug
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', slug): raise ValueError('Invalid slug')
    spec_path = ROOT / f'specs/reels/{slug}.json'
    spec = json.loads(spec_path.read_text())
    require(spec, root=ROOT)
    origins = []
    inputs = []
    for role, run_id, directory in [('video', args.video_run, args.video_dir), ('audio', args.audio_run, args.audio_dir)]:
        record, artifact = source_run(slug, run_id)
        if os.environ.get('GITHUB_REF_NAME') and record['head_branch'] != os.environ['GITHUB_REF_NAME']:
            raise ValueError('Input run is from another branch')
        inputs.append(verified_input(slug, directory, record, source_spec(slug, record['head_sha'])))
        origins.append({'role': role, 'run_id': int(run_id), 'head_sha': record['head_sha'], 'artifact_id': artifact['id']})
    video, video_meta, video_binding, video_film = inputs[0]
    audio, audio_meta, audio_binding, audio_film = inputs[1]
    verify_recipes(spec, video, audio, video_meta, audio_meta, video_binding, audio_binding, ROOT)
    out = args.outdir
    if out.exists() and any(out.iterdir()): raise ValueError('Output must be a new empty directory')
    out.mkdir(parents=True, exist_ok=True)
    for name in video['artifacts']:
        if name != 'audio_review_binding.json': shutil.copy2(args.video_dir / name, out / name)
    shutil.copytree(args.video_dir / 'score_masks', out / 'score_masks')
    film = out / f'{slug}.mp4'
    run('ffmpeg', '-v', 'error', '-y', '-i', video_film, '-i', audio_film,
        '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', '-movflags', '+faststart', film)
    proof = {'schema': 'tennislive.native-stream-composition.v1', 'slug': slug, 'input_runs': origins,
             'input_movies': [{'role': role, 'sha256': m['film_sha256'], 'bytes': m['film_bytes']}
                              for role, m in [('video', video), ('audio', audio)]],
             'streams': [packet_proof(video_film, film, 'v:0'), packet_proof(audio_film, film, 'a:0')],
             'film_sha256': ri.sha256_file(film), 'film_bytes': film.stat().st_size,
             'audio_plan_sha256': plan_hash(spec), 'source_sha256': audio_binding['sources'],
             'timeline': audio_binding['timeline'], 'voice_pairs': import_voice_pairs(spec, audio_meta, args.audio_dir, out, audio_film, audio_binding['timeline']),
             'qc_status': 'not_checked', 'method': 'Actual verified native input compressed streams; ffmpeg copy; exact packet bytes and timestamps'}
    for row in proof['voice_pairs']:
        row['native_origin'] = next(origin for origin in origins if origin['role'] == 'audio')
    hashes = reviewed_source_hashes(spec, root=ROOT)
    if hashes != audio_binding['sources']: raise ValueError('Current reviewed sources differ')
    fallbacks = spec_source_fallbacks(spec); sources = {}
    for key, url in (spec.get('sources') or {'': spec.get('source_url')}).items():
        target = out / (f'source_{key}.mp4' if key else 'source.mp4')
        stage_one(key, url, target, [], expected_sha=hashes.get(key), fallback=fallbacks.get(key)); sources[key] = target
    bind_sources(spec, sources, out, root=ROOT)
    timeline = audio_binding['timeline']
    record_timeline(spec, out, timeline['cover_seconds'], timeline['offsets'], timeline['lengths'])
    meta = copy.deepcopy(video_meta)
    for key in ('qc_attestation_sha256', 'qc_attestation', 'film_sha256', 'film_bytes', 'video_url', 'video_bytes', '_release_tag_note'):
        meta.pop(key, None)
    meta['composition_provenance'] = 'composition_provenance.json'
    write(out / 'render.json', meta)
    write(out / 'composition_provenance.json', proof)
    ri.record(spec_path, out, film, ROOT)
    # Extend the native manifest with this composition's immutable provenance;
    # the native QC/reattest gates verify every declared artifact hash.
    manifest = json.loads((out / 'render_inputs.json').read_text())
    manifest['artifacts']['composition_provenance.json'] = ri.sha256_file(out / 'composition_provenance.json')
    digest = ri.write(out, manifest)
    meta = json.loads((out / 'render.json').read_text()); meta['render_inputs_sha256'] = digest
    write(out / 'render.json', meta)
    print(json.dumps({'outdir': str(out), 'film_sha256': proof['film_sha256'], 'qc': 'MUST RUN NEW NATIVE QC'}))


def release(args):
    out = args.outdir; slug = args.slug; film = out / f'{slug}.mp4'
    # Run the actual native checker here as well; an imported pass JSON is not
    # authority to upload. Publication's tracked-file gate runs after commit.
    run(sys.executable, ROOT / 'tools/check_reel_landed.py', '--slug', slug,
        '--spec', ROOT / f'specs/reels/{slug}.json', '--film', film)
    qc = json.loads((out / 'qc_attestation.json').read_text())
    if (qc.get('status') != 'pass' or qc.get('slug') != slug
            or qc['film_sha256'] != ri.sha256_file(film)
            or qc['spec_sha256'] != ri.sha256_file(ROOT / f'specs/reels/{slug}.json')
            or qc['ass_sha256'] != ri.sha256_file(out / 'subtitles.ass')):
        raise ValueError('New native QC is not bound to actual composed film/current spec')
    tag = f'reel-{slug}'
    view = json.loads(subprocess.check_output(['gh', 'release', 'view', tag, '--repo', REPO, '--json', 'isDraft'], text=True))
    if view['isDraft']: raise ValueError('Release must be public')
    run('gh', 'release', 'upload', tag, film, '--repo', REPO, '--clobber')
    url = f'https://github.com/{REPO}/releases/download/{tag}/{slug}.mp4'
    assets = json.loads(subprocess.check_output(['gh', 'release', 'view', tag, '--repo', REPO, '--json', 'assets'], text=True))['assets']
    matches = [a for a in assets if a['name'] == film.name]
    if len(matches) != 1: raise ValueError('Exactly one new native Release asset required')
    asset_id = int(matches[0]['apiUrl'].rsplit('/', 1)[1])
    verified = verify_remote_release(url, qc['film_sha256'], film.stat().st_size, asset_id)
    meta = json.loads((out / 'render.json').read_text());meta.update(video_url=verified['published_url'], video_bytes=verified['bytes']);write(out / 'render.json', meta)
    write(out / 'composition_release_verification.json', {'qc_status':'pass', 'qc_attestation_sha256':ri.sha256_file(out/'qc_attestation.json'), 'remote_sha256':verified['sha256'], 'remote_bytes':verified['bytes'], 'composition_provenance_sha256':ri.sha256_file(out/'composition_provenance.json'), 'transport':verified})
    run(sys.executable, ROOT / 'tools/push_reel.py', '--stage', 'page', '--outdir', out, '--copy', ROOT / f'specs/reels/{slug}.xhs.txt')
    # Movies/voice/masks remain in scratch; caller stages a strict small-file list.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['fetch', 'compose', 'release'])
    parser.add_argument('--slug', required=True)
    parser.add_argument('--video-run', required=True)
    parser.add_argument('--audio-run', required=True)
    parser.add_argument('--video-dir', type=Path, required=True)
    parser.add_argument('--audio-dir', type=Path, required=True)
    parser.add_argument('--outdir', type=Path, required=True)
    args = parser.parse_args()
    if args.stage == 'fetch':
        fetch(args.slug, args.video_run, args.video_dir);fetch(args.slug, args.audio_run, args.audio_dir)
    elif args.stage == 'compose': compose(args)
    else: release(args)


if __name__ == '__main__': main()
