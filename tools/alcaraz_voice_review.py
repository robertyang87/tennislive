"""Scoped native audio evidence for one frozen Alcaraz reel; never publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'tools' / 'alcaraz_voice_review'
SLUG = 'bergs-alcaraz-shanghai-2026-r3'
FINGERPRINT = '8eb988f93e710b3be4999a67c4f9474a3118c06cee82deae1007fb29d7e638e6'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['prepare', 'analyze'], required=True)
    parser.add_argument('--outdir', type=Path, required=True)
    args = parser.parse_args()
    spec_path = ROOT / 'specs' / 'reels' / f'{SLUG}.json'
    spec = json.loads(spec_path.read_text())
    utterances = [
        {'edit_id': seg['_edit_id'], 'narration': seg['narration'], 'voice': seg.get('voice') or {}}
        for seg in spec['segments'] if seg.get('narration')
    ]
    payload = json.dumps(utterances, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    actual = hashlib.sha256(payload).hexdigest()
    assert spec['slug'] == SLUG and actual == FINGERPRINT and len(utterances) == 9, 'Frozen voice scope changed'
    assert spec.get('outro') is False and not spec.get('cover', {}).get('narration'), 'Extra voice is outside scope'
    for row in utterances:
        voice = row['voice']
        assert voice.get('rate', '+6%') == '+6%' and voice.get('pitch', '+0Hz') == '+0Hz'
        assert not voice.get('style') and not voice.get('styledegree') and not voice.get('lead_pause')
    out = args.outdir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update(ALCARAZ_VOICE_REVIEW_DIR=str(out), TENNISLIVE_TTS_BACKEND='edge',
               POLYPHONE_CACHE=str(out / 'fresh-reference-cache'),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env['PYTHONPATH'] = os.pathsep.join([str(BUNDLE / 'runtime'), str(ROOT / 'src'), str(ROOT / 'tools'), env.get('PYTHONPATH', '')])
    scope = {'slug': SLUG, 'voice_input_fingerprint': actual, 'utterance_count': len(utterances),
             'voice': 'zh-CN-YunjianNeural', 'rate': '+6%', 'pitch': '+0Hz',
             'spec_sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest(),
             'original_repo_root': str(ROOT), 'original_artifact_root': str(out),
             'github_run_id': os.environ.get('GITHUB_RUN_ID'),
             'github_run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
             'github_commit_sha': os.environ.get('GITHUB_SHA'),
             'edge_synthesis_transport': 'wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1',
             'edge_transport_migration_reference': 'https://github.com/rany2/edge-tts/pull/491',
             'human_listening_claimed': False, 'pronunciation_release_pass_claimed': False,
             'forbidden_services_called': False, 'publishing_enabled': False}
    (out / 'scope.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2) + '\n')

    def run(script, *extra):
        subprocess.run([sys.executable, str(BUNDLE / script), *map(str, extra)], env=env, cwd=ROOT, check=True)

    if args.stage == 'prepare':
        frozen = out / 'frozen-initial-spec.json'
        frozen.write_bytes(spec_path.read_bytes())
        run('prepare_native.py', '--spec', frozen)
        run('audit_native.py', '--names', BUNDLE / 'names.json', '--prepare-only')
    else:
        assert (out / 'native-bindings.json').is_file(), 'Prepare native audio before analysis'
        run('audit_native.py', '--names', BUNDLE / 'names.json')
        run('consolidate.py', spec_path)
    print(json.dumps({'stage': args.stage, 'outdir': str(out), 'scope': scope}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
