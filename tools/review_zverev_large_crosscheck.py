"""Six fixed Zverev public-source windows; raw ASR evidence, never review approval."""
import os
for key in ('ORT_DISABLE_TELEMETRY', 'HF_HUB_DISABLE_TELEMETRY', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    if os.environ.get(key) != '1':
        raise SystemExit(f'{key}=1 is required before process startup')

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
import wave

MODEL_ID = 'Systran/faster-whisper-large-v3'
REVISION = 'edaa852ec7e145841d8ffdb056a99866b5f0a478'
MODEL_FILES = {'config.json': (2394, 'a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9'), 'model.bin': (3087284237, '69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1'), 'preprocessor_config.json': (340, '7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711'), 'tokenizer.json': (2480617, '6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca'), 'vocabulary.json': (1068114, 'c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1')}
FIXED_PLAN_SHA256 = '813c367f87d7aec87fe0bbe54995b7ed39c21ad53d29f6ee37297e75597a2217'
EXPECTED_PLAN = {'schema': 'tennislive.zverev-large-crosscheck-plan.v1', 'source_seconds': 41.82, 'basis_run_id': 36932262107, 'native_tail_seconds': 0.18, 'items': [{'id': 'crosscheck-01-zverev-norrie-beijing-2026-r1', 'slug': 'zverev-norrie-beijing-2026-r1', 'source_url': 'https://www.youtube.com/watch?v=eciSHiQTzN8', 'source_sha256': 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 'source_from': 140.8, 'source_to': 144.2, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 44100, 'frames': 149940}}, {'id': 'crosscheck-02-zverev-norrie-beijing-2026-r1', 'slug': 'zverev-norrie-beijing-2026-r1', 'source_url': 'https://www.youtube.com/watch?v=eciSHiQTzN8', 'source_sha256': 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 'source_from': 149.6, 'source_to': 156.44, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 44100, 'frames': 301644}}, {'id': 'crosscheck-03-zverev-norrie-beijing-2026-r1', 'slug': 'zverev-norrie-beijing-2026-r1', 'source_url': 'https://www.youtube.com/watch?v=eciSHiQTzN8', 'source_sha256': 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 'source_from': 185.2, 'source_to': 190.9, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 44100, 'frames': 251370}}, {'id': 'crosscheck-04-zverev-norrie-beijing-2026-r1', 'slug': 'zverev-norrie-beijing-2026-r1', 'source_url': 'https://www.youtube.com/watch?v=eciSHiQTzN8', 'source_sha256': 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 'source_from': 191.78, 'source_to': 196.1, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 44100, 'frames': 190512}}, {'id': 'crosscheck-05-zverev-norrie-beijing-2026-r1', 'slug': 'zverev-norrie-beijing-2026-r1', 'source_url': 'https://www.youtube.com/watch?v=eciSHiQTzN8', 'source_sha256': 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 'source_from': 198.5, 'source_to': 205.98, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 44100, 'frames': 329868}}, {'id': 'crosscheck-06-zverev-norrie-beijing-2026-r1', 'slug': 'zverev-norrie-beijing-2026-r1', 'source_url': 'https://www.youtube.com/watch?v=eciSHiQTzN8', 'source_sha256': 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee', 'source_from': 219.2, 'source_to': 233.28, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 44100, 'frames': 620928}}], 'scope': 'Six exact conflicting English windows already retained by the approved reel, including existing native tails where the window reaches the retained boundary', 'raw_audio_uploaded': False, 'audio_review_pass': False, 'publication_eligible': False}
SLUG = 'zverev-norrie-beijing-2026-r1'
SOURCE_URL = 'https://github.com/robertyang87/tennislive/releases/download/source-eciSHiQTzN8/eciSHiQTzN8.mp4'
SOURCE_BYTES = 40607227
SOURCE_SHA256 = 'dd355e5dd6f25b66414c15427f5fc53d7d37785c36801939e42ca2bba15efeee'
RETAINED_WINDOWS = ((0.0, 19.28), (101.84, 156.44), (181.82, 190.9), (191.78, 215.84), (215.86, 233.28))

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def stamp():
    return datetime.now(timezone.utc).isoformat()

def valid_digest(value):
    return isinstance(value,str) and re.fullmatch(r'[0-9a-f]{64}',value) is not None

def check_wav(path,item):
    path=Path(path)
    if path.is_symlink() or path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:
        raise ValueError('WAV differs from reviewed input')
    with wave.open(str(path),'rb') as audio:
        actual={'channels':audio.getnchannels(),'sample_width_bytes':audio.getsampwidth(),'sample_rate':audio.getframerate(),'frames':audio.getnframes()}
        if audio.getcomptype()!='NONE' or actual!=item['audio']:
            raise ValueError('WAV PCM properties differ')

def check_model(model_dir):
    for name,(size,digest) in MODEL_FILES.items():
        path=Path(model_dir)/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size!=size or sha(path)!=digest:
            raise ValueError(f'Official model file failed verification: {name}')

def native_real(value):
    from numbers import Real
    if isinstance(value,bool) or not isinstance(value,Real):
        raise ValueError('ASR numeric output must be a real scalar')
    result=float(value)
    if not math.isfinite(result):
        raise ValueError('ASR numeric output must be finite')
    return result

def segment_report(segment,item):
    start=native_real(segment.start);end=native_real(segment.end)
    if end<start:
        raise ValueError('ASR segment end precedes start')
    duration=item['source_to']-item['source_from'];words=[]
    for word in segment.words or []:
        a=native_real(word.start);b=native_real(word.end);prob=native_real(word.probability)
        if b<a or not 0<=prob<=1:
            raise ValueError('Invalid ASR word interval or probability')
        outside=a<0 or b>duration
        words.append({'word':str(word.word),'start':a,'end':b,'source_start':round(item['source_from']+a,3),'source_end':round(item['source_from']+b,3),'probability':prob,'uncertain':bool(prob<.8 or outside),'outside_input_window':bool(outside)})
    return {'start':start,'end':end,'text':str(segment.text),'avg_logprob':native_real(segment.avg_logprob),'no_speech_prob':native_real(segment.no_speech_prob),'compression_ratio':native_real(segment.compression_ratio),'outside_input_window':bool(start<0 or end>duration),'words':words}

class CrosscheckError(RuntimeError):
    """Fixed error code only; never external error text or signed URLs."""


def dump(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def flags():
    return {'raw_audio_uploaded': False, 'audio_review_pass': False, 'publication_eligible': False}


def bounded_download(url, target, size, digest, kind, total_seconds):
    if kind == 'source':
        approved = (url, size, digest) == (SOURCE_URL, SOURCE_BYTES, SOURCE_SHA256)
    elif kind == 'model':
        approved = any((url, size, digest) ==
            (f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}?download=true', spec[0], spec[1])
            for name, spec in MODEL_FILES.items())
    else:
        approved = False
    if not approved:
        raise CrosscheckError('download_target_not_approved')
    target = Path(target)
    if target.exists() or target.is_symlink():
        raise CrosscheckError('download_output_already_exists')
    target.parent.mkdir(parents=True, exist_ok=True)
    class SecureRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            parsed = urlparse(newurl)
            host = parsed.hostname or ''
            allowed = host in {'github.com', 'release-assets.githubusercontent.com'} if kind == 'source' else (host == 'huggingface.co' or host.endswith('.huggingface.co') or host == 'hf.co' or host.endswith('.hf.co'))
            if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or not allowed:
                raise CrosscheckError('download_redirect_rejected')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    def timeout_handler(signum, frame):
        raise CrosscheckError('download_total_timeout')
    previous = signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, total_seconds)
    count = 0
    try:
        # Default urllib handlers retain the ordinary TLS trust store and proxy route.
        # No cookie jar, account authentication, .netrc lookup or custom CA is used.
        opener = urllib.request.build_opener(SecureRedirect())
        request = urllib.request.Request(url, headers={'User-Agent': 'tennislive-zverev-asr-crosscheck/1'})
        with opener.open(request, timeout=25) as response, target.open('xb') as output:
            if response.status != 200:
                raise CrosscheckError('download_http_status')
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > size:
                    raise CrosscheckError('download_exact_size_exceeded')
                output.write(block)
        if count != size or sha(target) != digest:
            raise CrosscheckError('download_size_or_sha256_mismatch')
    except CrosscheckError:
        raise
    except Exception:
        raise CrosscheckError('public_download_failed') from None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def read_plan(path, expected_sha):
    if expected_sha != FIXED_PLAN_SHA256 or sha(path) != FIXED_PLAN_SHA256:
        raise ValueError('Plan differs from the fixed reviewed SHA256')
    data = json.loads(Path(path).read_text())
    if data != EXPECTED_PLAN:
        raise ValueError('Plan differs from the six fixed source windows')
    for item in data['items']:
        a, b = item['source_from'], item['source_to']
        if not any(x <= a < b <= y for x, y in RETAINED_WINDOWS):
            raise ValueError('Cross-check would exceed a retained window')
        if round((b - a) * 44100) != item['audio']['frames']:
            raise ValueError('PCM frame count differs from fixed cut')
    return data


def acquire_source(workdir, report_path):
    target = Path(workdir) / f'{SLUG}.mp4'
    report = {'schema': 'tennislive.zverev-source-provenance.v1', 'slug': SLUG,
              'public_url': SOURCE_URL, 'expected_bytes': SOURCE_BYTES,
              'expected_sha256': SOURCE_SHA256, 'status': 'not_started',
              'audio_inference_started': False, **flags()}
    try:
        bounded_download(SOURCE_URL, target, SOURCE_BYTES, SOURCE_SHA256, 'source', 300)
        report.update(status='exact_source_verified', actual_bytes=target.stat().st_size,
                      actual_sha256=sha(target))
    except Exception as exc:
        report.update(status='blocked', reason=str(exc) if isinstance(exc, CrosscheckError) else 'source_acquisition_failed')
        dump(report_path, report)
        raise
    dump(report_path, report)
    return target


def extract_windows(plan, source, input_dir):
    if plan != EXPECTED_PLAN:
        raise ValueError('Only the exact six-window plan is allowed')
    source = Path(source)
    if source.is_symlink() or not source.is_file() or source.stat().st_size != SOURCE_BYTES or sha(source) != SOURCE_SHA256:
        raise ValueError('Original source size or SHA256 mismatch before clipping')
    input_dir = Path(input_dir)
    if input_dir.is_symlink():
        raise ValueError('Symlink input directory rejected')
    items = []
    for original in plan['items']:
        item = dict(original)
        rel = f'clips/{item["id"]}.wav'
        dest = input_dir / rel
        if dest.exists() or dest.is_symlink() or not dest.resolve().is_relative_to(input_dir.resolve()):
            raise ValueError('Invalid or existing clip output')
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(item['source_from']), '-i', str(source),
               '-t', str(round(item['source_to'] - item['source_from'], 3)), '-map', '0:a:0', '-vn',
               '-ac', '2', '-ar', '44100', '-c:a', 'pcm_s16le', '-n', str(dest)]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        if result.returncode:
            raise ValueError('Bounded local PCM extraction failed')
        item.update(path=rel, bytes=dest.stat().st_size, sha256=sha(dest))
        check_wav(dest, item)
        items.append(item)
    return {'schema': 'tennislive.zverev-runtime-excerpts.v1', 'items': items, 'source_seconds': 41.82,
            'planned_source_seconds': 41.82, 'available_slugs': [SLUG], 'blocked_slugs': [],
            'scope_status': 'complete_six_window_inference_input', **flags()}


def validate_runtime(data, plan, input_dir):
    expected_keys = {'schema', 'items', 'source_seconds', 'planned_source_seconds', 'available_slugs',
                     'blocked_slugs', 'scope_status', *flags()}
    if plan != EXPECTED_PLAN or set(data) != expected_keys:
        raise ValueError('Unexpected runtime fields or plan')
    expected = {'schema': 'tennislive.zverev-runtime-excerpts.v1', 'source_seconds': 41.82,
                'planned_source_seconds': 41.82, 'available_slugs': [SLUG], 'blocked_slugs': [],
                'scope_status': 'complete_six_window_inference_input', **flags()}
    if any(data.get(k) != v for k, v in expected.items()) or any(data.get(k) is not False for k in flags()):
        raise ValueError('Runtime scope or evidence status differs')
    if len(data.get('items', [])) != 6:
        raise ValueError('All six exact windows are required')
    for expected_item, item in zip(plan['items'], data['items']):
        if set(item) != set(expected_item) | {'path', 'bytes', 'sha256'} or any(item.get(k) != v for k, v in expected_item.items()):
            raise ValueError('Runtime source window differs from fixed plan')
        if item['path'] != f'clips/{item["id"]}.wav' or not valid_digest(item['sha256']):
            raise ValueError('Unsafe runtime path or SHA256')
        if type(item['bytes']) is not int or not 44 < item['bytes'] <= expected_item['audio']['frames'] * 4 + 4096:
            raise ValueError('Unbounded PCM size')
        path = Path(input_dir) / item['path']
        if not path.resolve().is_relative_to(Path(input_dir).resolve()):
            raise ValueError('Runtime excerpt escapes isolated input directory')
        check_wav(path, item)
    return data


def read_runtime(path, plan, input_dir):
    return validate_runtime(json.loads(Path(path).read_text()), plan, input_dir)


def model_download(model_dir):
    for name, (size, digest) in MODEL_FILES.items():
        url = f'https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}?download=true'
        bounded_download(url, Path(model_dir) / name, size, digest, 'model', 900)
    check_model(model_dir)


def infer(data, input_dir, model_dir, outdir):
    validate_runtime(data, EXPECTED_PLAN, input_dir)
    check_model(model_dir)
    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(str(model_dir), device='cpu', compute_type='int8', cpu_threads=2,
                         num_workers=1, local_files_only=True)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    versions = {name: importlib.metadata.version(name) for name in
                ('faster-whisper', 'ctranslate2', 'onnxruntime', 'numpy', 'huggingface-hub', 'tokenizers', 'av')}
    completed = []
    for item in data['items']:
        print(json.dumps({'stage': 'infer_window', 'clip': item['id'], 'review_pass': False}), flush=True)
        decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(Path(input_dir) / item['path']),
            '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], check=True, capture_output=True, timeout=30)
        audio = np.frombuffer(decoded.stdout, dtype=np.float32)
        expected_samples = round((item['source_to'] - item['source_from']) * 16000)
        if audio.size != expected_samples or not np.isfinite(audio).all():
            raise ValueError('Decoded audio differs from exact fixed duration')
        segments, info = model.transcribe(audio, language='en', beam_size=5, temperature=0.0,
            condition_on_previous_text=False, initial_prompt=None, word_timestamps=True, vad_filter=False)
        rows = [segment_report(segment, item) for segment in segments]
        report = {'schema': 'tennislive.asr-evidence-only.zverev-large-crosscheck.v1', 'created_at': stamp(),
            'input': item, 'basis_run_id': 36932262107,
            'model': {'id': MODEL_ID, 'revision': REVISION, 'model_sha256': MODEL_FILES['model.bin'][1]},
            'versions': versions, 'language': 'en', 'segments': rows, 'status': 'inference_only_not_verified',
            'empty_output_is_not_silence_proof': not rows,
            'uncertainty_note': 'Raw model evidence can omit or hallucinate speech. It does not settle conflicting words or verify foreground audio.', **flags()}
        dump(outdir / f'{item["id"]}.json', report)
        completed.append(item['id'])
        print(json.dumps({'completed': item['id'], 'segments': len(rows), 'review_pass': False}), flush=True)
    dump(outdir / 'batch.json', {'schema': 'tennislive.zverev-large-crosscheck-batch.v1',
        'created_at': stamp(), 'completed': completed, 'source_seconds': 41.82, 'planned_source_seconds': 41.82,
        'available_slugs': [SLUG], 'scope_status': 'complete_six_window_inference_only', **flags()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['inputs', 'acquire', 'download-model', 'infer'], required=True)
    parser.add_argument('--plan', type=Path, default=Path('assets/asr-review-20261001/zverev-large-crosscheck.json'))
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--workdir', type=Path)
    parser.add_argument('--outdir', type=Path)
    args = parser.parse_args()
    plan = read_plan(args.plan, args.plan_sha256)
    if args.mode == 'inputs':
        print(json.dumps({'clips': 6, 'source_seconds': 41.82, 'validated_plan': args.plan_sha256, **flags()}))
        return
    if args.workdir is None or args.outdir is None:
        parser.error('--workdir and --outdir are required')
    if args.workdir.is_symlink() or args.outdir.is_symlink():
        raise ValueError('Symlink runtime directories rejected')
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.outdir.mkdir(parents=True, exist_ok=True)
    input_dir = args.workdir / 'inputs'
    model_dir = args.workdir / 'model'
    runtime = args.outdir / 'runtime-inputs.json'
    if args.mode == 'acquire':
        source = acquire_source(args.workdir / 'sources', args.outdir / 'sources.json')
        dump(runtime, extract_windows(plan, source, input_dir))
        return
    data = read_runtime(runtime, plan, input_dir)
    if args.mode == 'download-model':
        model_download(model_dir)
        return
    infer(data, input_dir, model_dir, args.outdir)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never include external exception text, URLs, paths or credentials in reports.
        failure = {'status': 'blocked', 'error_type': type(exc).__name__,
                   'reason': str(exc) if isinstance(exc, CrosscheckError) else 'crosscheck_validation_or_inference_failed', **flags()}
        print(json.dumps(failure), flush=True)
        if '--outdir' in sys.argv:
            failure_dir = Path(sys.argv[sys.argv.index('--outdir') + 1])
            if failure_dir.is_dir() and not failure_dir.is_symlink():
                dump(failure_dir / 'batch.json', failure)
        raise SystemExit(1) from None
