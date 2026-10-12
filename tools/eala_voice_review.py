"""Current Eala/Shi native speech evidence; explicit frozen fingerprint required.

No historical episode verdict or delivery operation is imported. The caller
must freeze the actual Chinese narration before invoking either stage.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'tools' / 'eala_voice_review'
SLUG = 'eala-shi'


def validate_scope(spec, expected_fingerprint):
    if spec.get('slug') != SLUG:
        raise ValueError('Only the current eala-shi episode is authorized')
    if spec.get('outro') is not False or spec.get('cover', {}).get('narration'):
        raise ValueError('Extra cover or brand speech is outside current scope')
    rows = [
        {'edit_id': segment['_edit_id'], 'narration': segment['narration'],
         'voice': segment.get('voice') or {}}
        for segment in spec['segments'] if segment.get('narration')
    ]
    if not rows or len({row['edit_id'] for row in rows}) != len(rows):
        raise ValueError('Narration needs distinct stable edit IDs')
    for row in rows:
        voice = row['voice']
        if (voice.get('rate', '+6%') != '+6%' or
                voice.get('pitch', '+0Hz') != '+0Hz' or
                voice.get('style') or voice.get('styledegree') or
                voice.get('lead_pause')):
            raise ValueError('Only standard Yunjian +6%, +0Hz is authorized')
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode()
    fingerprint = hashlib.sha256(payload).hexdigest()
    if fingerprint != expected_fingerprint:
        raise ValueError('Frozen narration fingerprint changed; review first')
    return rows, fingerprint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'analyze'], required=True)
    parser.add_argument('--spec', type=Path,
                        default=ROOT / 'specs' / 'reels' / f'{SLUG}.json')
    parser.add_argument('--expected-fingerprint', required=True)
    parser.add_argument('--outdir', type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    rows, fingerprint = validate_scope(spec, args.expected_fingerprint)
    out = args.outdir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    scope_path = out / 'scope.json'
    if scope_path.exists():
        existing = json.loads(scope_path.read_text())
        if existing['voice_input_fingerprint'] != fingerprint:
            raise ValueError('Output directory contains another frozen utterance set')
    scope = {
        'slug': SLUG, 'voice_input_fingerprint': fingerprint,
        'utterance_count': len(rows), 'voice': 'zh-CN-YunjianNeural',
        'rate': '+6%', 'pitch': '+0Hz',
        'spec_sha256_at_preparation': hashlib.sha256(args.spec.read_bytes()).hexdigest(),
        'original_repo_root': str(ROOT), 'original_artifact_root': str(out),
        'github_run_id': os.environ.get('GITHUB_RUN_ID'),
        'github_commit_sha': os.environ.get('GITHUB_SHA'),
        'edge_synthesis_transport': 'wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1',
        'edge_transport_migration_reference': 'https://github.com/rany2/edge-tts/pull/491',
        'human_listening_claimed': False, 'pronunciation_release_pass_claimed': False,
        'forbidden_services_called': False, 'publishing_enabled': False,
    }
    if not scope_path.exists():
        scope_path.write_text(json.dumps(scope, ensure_ascii=False, indent=2) + '\n')
    env = dict(os.environ)
    env.update(EALA_VOICE_REVIEW_DIR=str(out), TENNISLIVE_TTS_BACKEND='edge',
               POLYPHONE_CACHE=str(out / 'fresh-reference-cache'),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    # measure_polyphone directly calls edge_tts; its controls use the same new
    # endpoint adapter and inherited HTTPS proxy as the actual native speech.
    env['PYTHONPATH'] = os.pathsep.join([
        str(ROOT / 'tools' / 'alcaraz_voice_review' / 'runtime'),
        str(ROOT / 'src'), str(ROOT / 'tools'), env.get('PYTHONPATH', '')])

    def run(script, *extra):
        subprocess.run([sys.executable, str(BUNDLE / script), *map(str, extra)],
                       env=env, cwd=ROOT, check=True)

    if args.stage == 'prepare':
        frozen = out / 'frozen-initial-spec.json'
        if frozen.exists() and frozen.read_bytes() != args.spec.read_bytes():
            raise ValueError('Existing initial spec differs; retain it and use a new output directory')
        frozen.write_bytes(args.spec.read_bytes())
        run('prepare_native.py', '--spec', frozen)
        run('audit_native.py', '--names', BUNDLE / 'names.json', '--prepare-only')
    else:
        if not (out / 'native-bindings.json').is_file():
            raise ValueError('Prepare current actual native speech before analysis')
        run('audit_native.py', '--names', BUNDLE / 'names.json')
        run('consolidate.py', args.spec)
    print(json.dumps({'stage': args.stage, 'outdir': str(out), 'scope': scope},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
