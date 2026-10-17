#!/usr/bin/env python3
"""Seal completed, finite visual reviews of the explicitly supplied current film.

This script does not perform viewing, set viewing flags, approve publication,
upload files, or replace either reviewer's observations. No work happens on
import. It deliberately fails until both actual reviews are finished.

Example (fill paths/hashes from the actual native download):
  python seal_joint_review.py --movie ACTUAL.mp4 --metadata-dir NATIVE_DIR \
    --spec CURRENT_SPEC.json --slug CURRENT_SLUG --expected-source-sha main=SHA256

The external locator remains pending until a separate, verified service upload.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile


class SealError(RuntimeError):
    pass


def need(condition, message):
    if not condition:
        raise SealError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    need(isinstance(value, dict), f'Expected JSON object: {path}')
    return value


def beneath(path, parent):
    path = Path(path).resolve(strict=True)
    need(path.is_relative_to(parent.resolve()), f'Not in current partition: {path}')
    need(path.is_file(), f'Not a regular evidence file: {path}')
    return path


def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timecode(value):
    h, m, s = value.split(':')
    return 3600 * int(h) + 60 * int(m) + float(s)


def ass_cues(path):
    result = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.startswith('Dialogue:'):
            continue
        fields = line.split(',', 9)
        need(len(fields) == 10, 'Malformed actual ASS Dialogue line')
        start, end = timecode(fields[1]), timecode(fields[2])
        need(end > start >= 0, 'Invalid actual ASS time interval')
        result.append({'index': len(result) + 1, 'start': start,
                       'end': end, 'text': fields[9]})
    need(bool(result), 'Actual ASS has no Dialogue cues')
    return result


def cue_index(cue):
    values = [cue[k] for k in ('global_cue', 'cue_global_index') if k in cue]
    need(bool(values) and len(set(values)) == 1, 'Cue index missing or ambiguous')
    need(type(values[0]) is int, 'Cue index must be integer')
    return values[0]


def check_identity(record, identity, label, *, require_geometry=False):
    for key in ('movie_sha256', 'movie_bytes', 'ass_sha256',
                'render_inputs_sha256', 'native_qc_sha256'):
        need(record.get(key) == identity[key], f'{label}: mismatched {key}')
    spec_fields = [record[k] for k in
                   ('native_spec_sha256', 'spec_file_sha256', 'spec_sha256')
                   if k in record]
    need(bool(spec_fields) and all(v == identity['native_spec_sha256']
                                  for v in spec_fields),
         f'{label}: missing/stale current spec identity')
    if 'source_sha256' in record:
        need(record['source_sha256'] == identity['source_sha256'],
             f'{label}: stale source identity')
    if 'movie' in record:
        need(Path(record['movie']).resolve() == identity['movie_path'],
             f'{label}: stale movie path')
    if require_geometry:
        for key in ('fps', 'canvas', 'total_movie_frames', 'film_seconds'):
            need(key in record, f'{label}: missing {key}')
    if 'slug' in record:
        need(record['slug'] == identity['slug'], f'{label}: wrong episode slug')


def check_partition(label, directory, manifest_path, review_path, identity, actual_cues):
    manifest = read(manifest_path)
    review = read(review_path)
    check_identity(manifest, identity, f'{label} manifest', require_geometry=True)
    check_identity(review, identity, f'{label} review')
    need(review.get('visual_pass') is True, f'{label}: no finished positive visual review')
    need(review.get('publication_approved') is False,
         f'{label}: review must not claim publication approval')
    need(review.get('frame_manifest_sha256') == sha(manifest_path),
         f'{label}: review does not bind this exact manifest')
    need(review.get('partition') == manifest.get('partition'),
         f'{label}: review/manifest partitions differ')
    need(bool(review.get('reviewer')), f'{label}: reviewer missing')
    need(review.get('blocking_findings', []) == [], f'{label}: blocking findings remain')
    # Other finding styles remain in the original report, not silently converted
    # to a joint pass. Any explicit blocking/error flag also stops sealing.
    for finding in review.get('findings', []):
        if isinstance(finding, dict):
            need(finding.get('blocking') is not True and
                 str(finding.get('severity', '')).lower() not in {'blocking', 'error'},
                 f'{label}: unresolved blocking/error finding')
    need(review.get('human_review_claimed', False) is False,
         f'{label}: this automated seal does not certify human review')
    if 'source_sha256' not in review:
        # Root's schema may omit source hashes: its exact render_inputs hash,
        # checked above, is the binding to the independently checked native sources.
        source_binding = 'Exact native render_inputs + audio_review_binding identity'
    else:
        source_binding = 'Explicit source hashes and exact native render_inputs identity'

    samples = manifest.get('samples')
    walls = manifest.get('walls')
    need(isinstance(samples, list) and bool(samples), f'{label}: no samples')
    need(isinstance(walls, list) and bool(walls), f'{label}: no contact sheets')
    fps, frame_total = manifest['fps'], manifest['total_movie_frames']
    need(isinstance(fps, (int, float)) and fps > 0, f'{label}: invalid fps')
    need(type(frame_total) is int and frame_total > 0, f'{label}: invalid frame count')
    by_frame, files, original_pngs = {}, [], []
    for sample in samples:
        k = sample.get('frame_index')
        need(type(k) is int and 0 <= k < frame_total, f'{label}: invalid sample frame')
        need(k not in by_frame, f'{label}: duplicated sample row {k}')
        need(sample.get('actually_viewed_on_contact_sheet') is True,
             f'{label}: frame {k} was not marked actually viewed')
        need(abs(sample['film_time_s'] - k / fps) < 0.00001,
             f'{label}: frame time does not agree with final film index')
        image = beneath(sample['image'], directory)
        need(image.suffix.lower() in {'.png', '.jpg', '.jpeg'}, 'Non-image sample file')
        need(sha(image) == sample.get('image_sha256'), f'{label}: altered frame {k}')
        by_frame[k] = sample
        files.append((image, f'{label}/frames/{image.name}'))
        if sample.get('original_png_actually_viewed') is True:
            original_pngs.append(k)

    sheet_coverage = set()
    for wall in walls:
        need(wall.get('actually_viewed') is True, f'{label}: unviewed contact sheet')
        image = beneath(wall.get('path') or wall.get('image'), directory)
        need(image.suffix.lower() in {'.png', '.jpg', '.jpeg'}, 'Non-image contact sheet')
        need(sha(image) == (wall.get('sha256') or wall.get('image_sha256')),
             f'{label}: altered contact sheet')
        frame_indices = wall.get('frame_indices')
        need(isinstance(frame_indices, list) and bool(frame_indices),
             f'{label}: contact sheet lacks frame membership')
        need(all(type(k) is int and k in by_frame for k in frame_indices),
             f'{label}: contact sheet refers to missing/other-episode sample')
        sheet_coverage.update(frame_indices)
        files.append((image, f'{label}/contact-sheets/{image.name}'))
    need(sheet_coverage == set(by_frame), f'{label}: sample rows not all on viewed sheets')

    assigned = manifest.get('assigned_ass_cues')
    need(isinstance(assigned, list), f'{label}: assigned cues missing')
    indices = set()
    for declared in assigned:
        index = cue_index(declared)
        need(1 <= index <= len(actual_cues) and index not in indices,
             f'{label}: duplicate/out-of-range assigned ASS index {index}')
        indices.add(index)
        actual = actual_cues[index - 1]
        start = declared.get('cue_start_s', declared.get('start'))
        end = declared.get('cue_end_s', declared.get('end'))
        text = declared.get('cue_text', declared.get('text'))
        need(start == actual['start'] and end == actual['end'] and text == actual['text'],
             f'{label}: cue {index} differs from actual ASS Dialogue')
        mid = (actual['start'] + actual['end']) / 2
        k = max(0, min(frame_total - 1, round(mid * fps)))
        need(k in by_frame, f'{label}: cue {index} has no actual midpoint sample')
        reasons = by_frame[k].get('reasons', [])
        need(any((r.get('global_cue') == index or r.get('cue_global_index') == index)
                 for r in reasons), f'{label}: cue {index} midpoint reason missing')

    # Dynamic summaries are computed from evidence; optional reviewer counters
    # must agree rather than being copied blindly from an earlier episode.
    scope = review.get('scope', {})
    groups = [(len(samples), ('movie_frame_samples_actually_viewed',
                              'actual_movie_samples_on_contact_sheets')),
              (len(walls), ('contact_sheets_actually_viewed', 'actual_walls_viewed')),
              (len(indices), ('assigned_ass_cue_midpoints_actually_viewed',
                              'actual_assigned_ASS_midpoints_inspected')),
              (len(original_pngs), ('original_full_movie_pngs_actually_viewed',
                                   'actual_original_pngs_viewed'))]
    for count, keys in groups:
        for key in keys:
            if key in scope:
                need(scope[key] == count, f'{label}: stale scope count {key}')
    for key in ('all_movie_frames_reviewed', 'all_movie_frames_viewed', 'audio_listened'):
        need(scope.get(key, False) is False, f'{label}: out-of-scope whole-film/listening claim')
    entry = {'reviewer': review['reviewer'], 'partition': manifest['partition'],
             'manifest_path': f'{label}/frame_manifest.json',
             'manifest_sha256': sha(manifest_path),
             'review_path': f'{label}/{review_path.name}', 'review_sha256': sha(review_path),
             'sample_rows': len(samples), 'walls': len(walls),
             'assigned_cue_indices': sorted(indices),
             'original_pngs_viewed': sorted(original_pngs), 'source_identity_binding': source_binding,
             'observations_attribution': 'Only the named reviewer claims the recorded viewing.'}
    files.extend([(manifest_path, entry['manifest_path']), (review_path, entry['review_path'])])
    return manifest, review, indices, entry, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--movie', type=Path, required=True)
    parser.add_argument('--metadata-dir', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--expected-source-sha', action='append', required=True,
                        metavar='SOURCE=SHA256', help='Repeat for every actual source')
    args = parser.parse_args()
    out, md = args.out.resolve(), args.metadata_dir.resolve(strict=True)
    need(out.is_dir(), 'Review output directory missing')
    movie, specpath = args.movie.resolve(strict=True), args.spec.resolve(strict=True)
    spec = read(specpath)
    need(spec.get('slug') == args.slug, 'Current spec has a different episode slug')
    expected_sources = {}
    for item in args.expected_source_sha:
        name, sep, digest = item.partition('=')
        need(sep and name and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest),
             'Expected source needs SOURCE=lowercase64charSHA256')
        need(name not in expected_sources, 'Duplicate expected source name')
        expected_sources[name] = digest
    paths = {name: md / name for name in ('render_inputs.json', 'render.json',
             'qc_attestation.json', 'audio_review_binding.json', 'subtitles.ass')}
    inputs, render, qc, binding = (read(paths[n]) for n in
                  ('render_inputs.json', 'render.json', 'qc_attestation.json', 'audio_review_binding.json'))
    actual_movie_hash, spec_hash = sha(movie), sha(specpath)
    need(inputs.get('film_sha256') == render.get('film_sha256') ==
         qc.get('film_sha256') == actual_movie_hash, 'Actual native film hashes differ')
    need(inputs.get('film_bytes') == movie.stat().st_size, 'Actual native film size differs')
    need(inputs.get('spec_sha256') == spec_hash, 'Spec differs from actual native input')
    need(render.get('render_inputs_sha256') == sha(paths['render_inputs.json']),
         'render.json refers to different render_inputs')
    need(render.get('qc_attestation_sha256') == sha(paths['qc_attestation.json']),
         'render.json refers to different native QC')
    need(qc.get('status') == 'pass', 'Actual native QC has not passed')
    need(inputs.get('artifacts', {}).get('subtitles.ass') ==
         qc.get('ass_sha256') == sha(paths['subtitles.ass']), 'Actual ASS identity differs')
    need(binding.get('sources') == expected_sources, 'Actual source bindings differ from supplied SHA')
    need(inputs.get('projection', {}).get('sources') == spec.get('sources'),
         'Actual native sources differ from current spec')
    for doc in (inputs, render, qc, binding):
        if 'slug' in doc:
            need(doc['slug'] == args.slug, 'Native metadata contains another episode slug')
        if 'spec_sha256' in doc:
            need(doc['spec_sha256'] == spec_hash, 'Native document has a stale spec hash')
    identity = {'slug': args.slug, 'movie_path': movie, 'movie_sha256': actual_movie_hash,
                'movie_bytes': movie.stat().st_size, 'native_spec_sha256': spec_hash,
                'ass_sha256': sha(paths['subtitles.ass']), 'source_sha256': expected_sources,
                'render_inputs_sha256': sha(paths['render_inputs.json']),
                'native_qc_sha256': sha(paths['qc_attestation.json'])}
    cues = ass_cues(paths['subtitles.ass'])
    configs = [('source-action', out, out/'frame_manifest.json', out/'source-action-review.json'),
               ('root', out/'root', out/'root/frame_manifest.json', out/'root/root-review.json')]
    checked = [check_partition(*cfg, identity, cues) for cfg in configs]
    a, b = checked[0][0], checked[1][0]
    for key in ('fps', 'canvas', 'film_seconds', 'total_movie_frames'):
        need(a[key] == b[key], f'Partitions describe different film {key}')
    first, second = checked[0][2], checked[1][2]
    need(not first & second, 'ASS cue assignments overlap across partitions')
    need(first | second == set(range(1, len(cues)+1)), 'ASS cue union is incomplete or stale')
    need(max(c['end'] for c in cues) <= a['film_seconds'] + 1 / a['fps'],
         'ASS extends beyond actual film')

    unique, bundle_files = {}, []
    for (label, _, _, _), (m, _, _, _, files) in zip(configs, checked):
        bundle_files.extend(files)
        for sample in m['samples']:
            k = sample['frame_index']
            if k in unique:
                need(unique[k]['image_sha256'] == sample['image_sha256'],
                     'Same actual movie frame has different partition image hashes')
            else:
                unique[k] = {key: sample[key] for key in ('frame_index', 'film_time_s', 'image_sha256')}
                unique[k]['review_partitions'] = []
            unique[k]['review_partitions'].append(label)
    partitions = [item[3] for item in checked]
    counts = {'sample_rows_across_partitions': sum(p['sample_rows'] for p in partitions),
              'unique_movie_frames_actually_viewed': len(unique),
              'contact_sheets_actually_viewed_across_partitions': sum(p['walls'] for p in partitions),
              'all_ASS_cue_midpoint_windows_actually_viewed': len(cues),
              'full_original_png_viewings': sum(len(p['original_pngs_viewed']) for p in partitions),
              'whole_movie_frame_by_frame_reviewed': False, 'audio_listened': False,
              'human_review_claimed': False, 'loudness_gain_RMS_peak_silence_PCM_checks': False}
    shared = {k: v for k, v in identity.items() if k != 'movie_path'}
    manifest = {'schema': 'tennislive.joint-partitioned-final-movie-visual-manifest.v1',
                **shared, 'film_seconds': a['film_seconds'], 'canvas': a['canvas'], 'fps': a['fps'],
                'total_movie_frames': a['total_movie_frames'], 'scope': counts,
                'all_movie_frames_reviewed': False, 'partitions': partitions,
                'unique_frame_index': sorted(unique.values(), key=lambda x: x['frame_index']),
                'actual_ass_dialogue_indices': list(range(1, len(cues)+1))}
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    review = {'schema': 'tennislive.joint-partitioned-final-movie-visual-review.v1',
              'reviewed_at_utc': stamp(), 'status': 'passed_with_explicit_finite_sampling_limits',
              'visual_pass': True, 'publication_approved': False, **shared,
              'film_seconds': a['film_seconds'], 'canvas': a['canvas'], 'fps': a['fps'],
              'joint_manifest_path': 'final-visual-manifest.json', 'joint_manifest_sha256': manifest_sha,
              'scope': counts, 'review_partitions': partitions, 'blocking_findings': [],
              'observations': 'Refer to each exact-hash partition report; no extra visual observations inferred by the sealer.',
              'limitations': ['Finite actual-movie samples only; no full-frame/full-court visibility claim.',
                             'Source speech, pronunciation and fact checking remain separate evidence.',
                             'This seal is not merge, publication or WeChat delivery approval.',
                             'External archive remains pending until a verified service upload receipt.']}
    review_bytes = (json.dumps(review, ensure_ascii=False, indent=2)+'\n').encode()
    # Allowlist only the five current native identity documents and current spec.
    # Do not recurse into native directories or include source/movie/audio files.
    bundle_files += [(path, 'actual-native-metadata/'+name) for name, path in paths.items()]
    for name in ('native_input_archive.json', 'native-public-input-verification.json'):
        if (md / name).is_file():
            bundle_files.append((md / name, 'actual-native-metadata/' + name))
    bundle_files += [(specpath, 'actual-native-metadata/current-spec.json'),
                     (Path(__file__).resolve(), 'scripts/seal_joint_review.py')]
    seen_names = set()
    for path, arcname in bundle_files:
        need(path.suffix.lower() in {'.json', '.ass', '.txt', '.png', '.jpg', '.jpeg', '.py'},
             f'Unexpected non-evidence bundle file: {path}')
        need(arcname not in seen_names, f'Duplicate archive filename: {arcname}')
        seen_names.add(arcname)
    # Avoid creating an incomplete archive when scratch space is already tight.
    # PNG/JPEG are compressed already; do not count on dramatic ZIP savings.
    input_bytes = sum(path.stat().st_size for path, _ in bundle_files)
    free = shutil.disk_usage(out).free
    need(free > input_bytes * 1.08 + 8 * 1024 * 1024,
         f'Insufficient free space for bounded evidence ZIP: need about {input_bytes} bytes')
    finalzip, tempzip = out/'visual-qc-evidence.zip', out/'visual-qc-evidence.zip.partial'
    need(not finalzip.exists() and not tempzip.exists(), 'Evidence ZIP already exists; refuse to overwrite silently')
    # No outputs are written until all input, flag, identity and coverage checks pass.
    with zipfile.ZipFile(tempzip, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
        z.writestr('final-visual-manifest.json', manifest_bytes)
        z.writestr('final-visual-review.json', review_bytes)
        for path, arcname in bundle_files:
            z.write(path, arcname)
    os.replace(tempzip, finalzip)
    (out/'final-visual-manifest.json').write_bytes(manifest_bytes)
    (out/'final-visual-review.json').write_bytes(review_bytes)
    locator = {'schema': 'tennislive.pending-external-evidence-locator.v1',
               'pending': True, 'publication_upload_pending': True,
               'slug': args.slug, 'film_sha256': actual_movie_hash,
               'zip_path': str(finalzip), 'zip_sha256': sha(finalzip),
               'zip_bytes': finalzip.stat().st_size,
               'review_sha256': hashlib.sha256(review_bytes).hexdigest(),
               'manifest_sha256': manifest_sha, 'service_receipt': None,
               'note': 'Local bundle only; fill external locator only after verified actual service upload.'}
    (out/'external_locator.pending.json').write_text(json.dumps(locator, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(locator, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (SealError, OSError, KeyError, ValueError) as exc:
        raise SystemExit(f'NOT SEALED: {exc}') from exc
