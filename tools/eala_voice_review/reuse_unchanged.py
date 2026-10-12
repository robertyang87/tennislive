"""Reuse exact current-episode controls after exactly two frozen CN revisions.

Prepared native audio is required in both directories. Records are copied
byte-for-byte only when the entire utterance, actual native MP3 and reference
set match. Changed utterance results are not copied or promoted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding_identity(binding):
    return tuple(binding[key] for key in [
        'edit_id', 'display_text', 'text', 'voice', 'rate', 'pitch',
        'actual_mp3_sha256', 'actual_marks_sha256', 'native_zip_marks_raw_sha256',
    ])


def target_identity(target):
    return (
        binding_identity(target['actual_binding']), target['sentence'],
        target['at'], target['char'], target['intended'], target['wrong'],
        tuple(target['ok_refs']), tuple(target['bad_refs']), target['check_kind'],
        target.get('reference_validity_limited', False),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', type=Path, required=True)
    parser.add_argument('--new', type=Path, required=True)
    parser.add_argument('--changed-id', action='append', required=True)
    args = parser.parse_args()
    if args.old.resolve() == args.new.resolve():
        raise ValueError('Retain the old frozen history in a separate directory')
    declared = set(args.changed_id)
    if len(declared) != 2:
        raise ValueError('This revision authorizes exactly two changed utterances')
    old = json.loads((args.old / 'native-bindings.json').read_text())
    new = json.loads((args.new / 'native-bindings.json').read_text())
    old_rows = {row['edit_id']: row for row in old['bindings']}
    new_rows = {row['edit_id']: row for row in new['bindings']}
    if set(old_rows) != set(new_rows) or len(new_rows) != 9:
        raise ValueError('Exactly the same nine edit IDs must remain in scope')
    changed = {
        key for key in old_rows
        if binding_identity(old_rows[key]) != binding_identity(new_rows[key])
    }
    if changed != declared:
        raise ValueError(f'Actual changed speech IDs {changed} != declared {declared}')
    for binding in new_rows.values():
        if sha(binding['bound_snapshot_path']) != binding['actual_mp3_sha256']:
            raise ValueError('New prepared MP3 does not match its native binding')
    old_job = json.loads((args.old / 'native-job.json').read_text())
    new_job = json.loads((args.new / 'native-job.json').read_text())
    index = {target_identity(row): i for i, row in enumerate(old_job['targets'])}
    copied = []
    target_dir = args.new / 'native-targets'
    target_dir.mkdir(exist_ok=True)
    for new_index, target in enumerate(new_job['targets']):
        if target['edit_id'] in declared:
            continue
        old_index = index.get(target_identity(target))
        if old_index is None:
            continue
        source = args.old / 'native-targets' / f'target-{old_index:03}.json'
        result = json.loads(source.read_text())
        if target_identity(result) != target_identity(target):
            raise ValueError('Old actual result differs from its declared target')
        for audio in result['control_audio_provenance']:
            for field, hash_field in [
                ('mp3_snapshot_path', 'mp3_sha256'),
                ('marks_snapshot_path', 'marks_sha256'),
            ]:
                path = Path(audio[field])
                if not audio.get(hash_field) or sha(path) != audio[hash_field]:
                    raise ValueError('Exact old control audio/marks provenance missing')
                destination = args.new / 'reference-audio' / path.name
                destination.parent.mkdir(exist_ok=True)
                if destination.exists() and sha(destination) != audio[hash_field]:
                    raise ValueError('Reference snapshot filename identity collision')
                shutil.copy2(path, destination)
        destination = target_dir / f'target-{new_index:03}.json'
        if destination.exists() and sha(destination) != sha(source):
            raise ValueError('New target already has a different actual measurement')
        shutil.copy2(source, destination)
        copied.append({
            'edit_id': target['edit_id'], 'source_path': str(source),
            'destination_path': str(destination), 'record_sha256': sha(source),
            'actual_mp3_sha256': target['actual_binding']['actual_mp3_sha256'],
            'old_target_index': old_index, 'new_target_index': new_index,
        })
    report = {
        'schema': 'tennislive.same-episode-exact-utterance-reuse.v1',
        'slug': 'eala-shi', 'status': 'exact_unchanged_current_utterance_controls_only',
        'changed_edit_ids': sorted(declared),
        'unchanged_edit_ids': sorted(set(new_rows) - declared),
        'old_native_bindings_sha256': sha(args.old / 'native-bindings.json'),
        'new_native_bindings_sha256': sha(args.new / 'native-bindings.json'),
        'old_native_job_sha256': sha(args.old / 'native-job.json'),
        'new_native_job_sha256': sha(args.new / 'native-job.json'),
        'reused_raw_record_count': len(copied), 'records': copied,
        'old_changed_utterance_verdicts_promoted': False,
        'human_listening_claimed': False, 'pronunciation_release_pass_claimed': False,
        'method': 'Byte-for-byte original raw results and hash-verified paired controls. Full edit ID/display/spoken sentence/voice/rate/pitch/native MP3 identity, occurrence position/intended/wrong/reference lists and diagnostic reference flags all match. Changed sentence results remain old history and are never copied.',
    }
    (args.new / 'unchanged-current-utterance-reuse.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in [
        'status', 'changed_edit_ids', 'unchanged_edit_ids', 'reused_raw_record_count',
    ]}), flush=True)


if __name__ == '__main__':
    main()
