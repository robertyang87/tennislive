"""Ten fixed Nishikori and Shang public-source windows; ASR evidence only."""

import os

for key in ('ORT_DISABLE_TELEMETRY', 'HF_HUB_DISABLE_TELEMETRY', 'HF_HUB_OFFLINE', 'TRANSFORMERS_OFFLINE'):
    if os.environ.get(key) != '1':
        raise SystemExit(f'{key}=1 is required before process startup')

PUBLIC_SOURCES = {'nishikori-tiafoe-tokyo-2026-r1': ('https://github.com/robertyang87/tennislive/releases/download/source-tennistv-4584955/4584955.mp4', 144247263, '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02'), 'shang-baez-beijing-2026-r1': ('https://github.com/robertyang87/tennislive/releases/download/source-tennistv-4585070/4585070.mp4', 120347402, 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f')}

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

FIXED_PLAN_SHA256 = '85257996ebafbefad5c7a5ff9887fa616c321e105f59251b58f1614811d28c13'

EXPECTED_PLAN = {'schema': 'tennislive.approved-ttv-retained-window-plan.v3', 'source_seconds': 185.51, 'items': [{'id': 'clip-01-nishikori-tiafoe-tokyo-2026-r1', 'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', 'source_sha256': '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 'source_from': 0.0, 'source_to': 23.88, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 1146240}}, {'id': 'clip-02-nishikori-tiafoe-tokyo-2026-r1', 'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', 'source_sha256': '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 'source_from': 31.95, 'source_to': 57.53, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 1227840}}, {'id': 'clip-03-nishikori-tiafoe-tokyo-2026-r1', 'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', 'source_sha256': '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 'source_from': 85.8, 'source_to': 95.48, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 464640}}, {'id': 'clip-04-nishikori-tiafoe-tokyo-2026-r1', 'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', 'source_sha256': '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 'source_from': 99.66, 'source_to': 110.2, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 505920}}, {'id': 'clip-05-nishikori-tiafoe-tokyo-2026-r1', 'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', 'source_sha256': '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 'source_from': 137.0, 'source_to': 179.98, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 2063040}}, {'id': 'clip-06-shang-baez-beijing-2026-r1', 'slug': 'shang-baez-beijing-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'source_sha256': 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 'source_from': 12.2, 'source_to': 23.88, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 560640}}, {'id': 'clip-07-shang-baez-beijing-2026-r1', 'slug': 'shang-baez-beijing-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'source_sha256': 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 'source_from': 52.2, 'source_to': 68.58, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 786240}}, {'id': 'clip-08-shang-baez-beijing-2026-r1', 'slug': 'shang-baez-beijing-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'source_sha256': 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 'source_from': 86.0, 'source_to': 99.78, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 661440}}, {'id': 'clip-09-shang-baez-beijing-2026-r1', 'slug': 'shang-baez-beijing-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'source_sha256': 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 'source_from': 116.5, 'source_to': 124.98, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 407040}}, {'id': 'clip-10-shang-baez-beijing-2026-r1', 'slug': 'shang-baez-beijing-2026-r1', 'source_url': 'https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'source_sha256': 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 'source_from': 125.5, 'source_to': 148.03, 'audio': {'channels': 2, 'sample_width_bytes': 2, 'sample_rate': 48000, 'frames': 1081440}}], 'scope': 'Only the two not-yet-transcribed ATP FREE sources; exact retained windows including native tails. Zverev full-window evidence already exists and is not rerun.', 'spec_bindings': [{'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'spec_sha256': 'b91feea870973e0a31564f37c99bca977450f0c30ec947aa2cec1d39426e74ec', 'production_plan_sha256': 'a8f896e0f2539766407204c68dfa8f44a5b430533975624440f7e2f9c5e308a7', 'retained_source_segments': [{'index': 0, 'start': 170.8, 'end': 179.8, 'native_tail_to': 179.98}, {'index': 1, 'start': 0, 'end': 10.8, 'native_tail_to': 10.98}, {'index': 2, 'start': 10.8, 'end': 20.4, 'native_tail_to': 20.58}, {'index': 3, 'start': 20.4, 'end': 23.7, 'native_tail_to': 23.88}, {'index': 4, 'start': 31.95, 'end': 50.95, 'native_tail_to': 51.13}, {'index': 5, 'start': 50.95, 'end': 57.35, 'native_tail_to': 57.53}, {'index': 6, 'start': 85.8, 'end': 95.3, 'native_tail_to': 95.48}, {'index': 7, 'start': 99.66, 'end': 105.5, 'native_tail_to': 105.68}, {'index': 8, 'start': 105.5, 'end': 110.02, 'native_tail_to': 110.2}, {'index': 9, 'start': 137.0, 'end': 161.5, 'native_tail_to': 161.68}, {'index': 10, 'start': 161.5, 'end': 166.6, 'native_tail_to': 166.78}, {'index': 11, 'start': 166.6, 'end': 170.8, 'native_tail_to': 170.98}, {'index': 12, 'start': 170.8, 'end': 179.8, 'native_tail_to': 179.98}], 'merged_seconds': 112.66}, {'slug': 'shang-baez-beijing-2026-r1', 'spec_sha256': '035a42fa3dd97e85010d3fe9c0a1a8aec9762294bd78db7e9906eda55797f688', 'production_plan_sha256': '9290955ae8aa78d6c199d5240c09406f6505adf5b2c956f266cf458acd6f81e7', 'retained_source_segments': [{'index': 0, 'start': 144.0, 'end': 147.85, 'native_tail_to': 148.03}, {'index': 1, 'start': 138.2, 'end': 143.9, 'native_tail_to': 144.08}, {'index': 2, 'start': 12.2, 'end': 23.7, 'native_tail_to': 23.88}, {'index': 3, 'start': 52.2, 'end': 68.4, 'native_tail_to': 68.58}, {'index': 4, 'start': 86.0, 'end': 99.6, 'native_tail_to': 99.78}, {'index': 5, 'start': 116.5, 'end': 124.8, 'native_tail_to': 124.98}, {'index': 6, 'start': 125.5, 'end': 132.3, 'native_tail_to': 132.48}, {'index': 7, 'start': 132.3, 'end': 147.85, 'native_tail_to': 148.03}], 'merged_seconds': 72.85}], 'audio_uploaded': False, 'format_selection_evidence': [{'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'public_url': 'https://www.tennistv.com/videos/4584955/tokyo-2026-r1-nishikori-tiafoe-short-highlights', 'entry_id': '2ff43dc5-5094-4bb5-b4f6-ed8ce4511c20', 'entitlement': 'free', 'selected_video_format_id': '6464', 'selected_audio_format_id': 'audio-aacl-125-audio', 'recovered_bytes': 144247263, 'recovered_sha256': '108cb26d27777495da69dbc5118a00fd89074aee43d9a405e3738fbe16565b02', 'recovered_duration_seconds': 188.928, 'metadata_observed_at': '2026-10-01T22:17:24.941074+00:00'}, {'slug': 'shang-baez-beijing-2026-r1', 'public_url': 'https://www.tennistv.com/videos/4585070/beijing-2026-r1-shang-baez-short-highlights', 'entry_id': 'fe2d2459-46d3-4f4d-ac2f-49115527a5b0', 'entitlement': 'free', 'selected_video_format_id': '6488', 'selected_audio_format_id': 'audio-aacl-125-audio', 'recovered_bytes': 120347402, 'recovered_sha256': 'f9600f72b97012fb3107525792b5ba34a4158bc7b586dee5354b661baa178b8f', 'recovered_duration_seconds': 157.056, 'metadata_observed_at': '2026-10-01T22:14:00.883974+00:00'}]}

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
        approved = (url, size, digest) in PUBLIC_SOURCES.values()
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
        request = urllib.request.Request(url, headers={'User-Agent': 'tennislive-ttv-large-asr-crosscheck/1'})
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
    if data != EXPECTED_PLAN or len(data['items']) != 10:
        raise ValueError('Plan differs from the ten fixed source windows')
    if round(sum(x['source_to'] - x['source_from'] for x in data['items']), 2) != 185.51:
        raise ValueError('Unexpected retained source seconds')
    for item in data['items']:
        if item['source_sha256'] != PUBLIC_SOURCES[item['slug']][2]:
            raise ValueError('Plan source identity differs')
        if round((item['source_to'] - item['source_from']) * item['audio']['sample_rate']) != item['audio']['frames']:
            raise ValueError('PCM frame count differs from fixed cut')
    return data

def acquire_sources(workdir, report_path):
    paths, rows = {}, []
    for slug, (url, size, digest) in PUBLIC_SOURCES.items():
        target = Path(workdir) / f'{slug}.mp4'
        report = {'slug': slug, 'public_url': url, 'expected_bytes': size,
                  'expected_sha256': digest, 'status': 'not_started'}
        try:
            bounded_download(url, target, size, digest, 'source', 300)
            report.update(status='exact_source_verified', actual_bytes=target.stat().st_size,
                          actual_sha256=sha(target))
            paths[slug] = target
        except Exception as exc:
            report.update(status='blocked', reason=str(exc) if isinstance(exc, CrosscheckError) else 'source_acquisition_failed')
        rows.append(report)
        dump(report_path, {'schema': 'tennislive.ttv-large-source-provenance.v1',
                          'sources': rows, 'audio_inference_started': False, **flags()})
    if not paths:
        raise CrosscheckError('no_exact_source_available')
    return paths

def runtime_metadata(paths):
    available = sorted(paths)
    if not available or len(available) != len(set(available)) or not set(available).issubset(PUBLIC_SOURCES):
        raise ValueError('Invalid available-source subset')
    items = [x for x in EXPECTED_PLAN['items'] if x['slug'] in available]
    return {'schema': 'tennislive.ttv-large-runtime-excerpts.v1',
            'source_seconds': round(sum(x['source_to'] - x['source_from'] for x in items), 2),
            'planned_source_seconds': 185.51, 'available_slugs': available,
            'blocked_slugs': sorted(set(PUBLIC_SOURCES) - set(available)),
            'scope_status': 'complete_ten_window_inference_input' if len(available) == 2 else 'partial_five_window_inference_input',
            **flags()}

def extract_windows(plan, paths, input_dir):
    if plan != EXPECTED_PLAN:
        raise ValueError('Only the exact ten-window plan is allowed')
    metadata = runtime_metadata(paths)
    for slug, source in paths.items():
        source = Path(source)
        _, size, digest = PUBLIC_SOURCES[slug]
        if source.is_symlink() or not source.is_file() or source.stat().st_size != size or sha(source) != digest:
            raise ValueError('Original source size or SHA256 mismatch before clipping')
    input_dir = Path(input_dir)
    if input_dir.is_symlink():
        raise ValueError('Symlink input directory rejected')
    items = []
    for original in plan['items']:
        if original['slug'] not in paths:
            continue
        item = dict(original)
        rel = f'clips/{item["id"]}.wav'
        dest = input_dir / rel
        if dest.exists() or dest.is_symlink() or not dest.resolve().is_relative_to(input_dir.resolve()):
            raise ValueError('Invalid or existing clip output')
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd = ['ffmpeg', '-nostdin', '-v', 'error', '-ss', str(item['source_from']), '-i', str(paths[item['slug']]),
               '-t', str(round(item['source_to'] - item['source_from'], 3)), '-map', '0:a:0', '-vn',
               '-ac', '2', '-ar', '48000', '-c:a', 'pcm_s16le', '-n', str(dest)]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        if result.returncode:
            raise ValueError('Bounded local PCM extraction failed')
        item.update(path=rel, bytes=dest.stat().st_size, sha256=sha(dest))
        check_wav(dest, item)
        items.append(item)
    return {**metadata, 'items': items}

def validate_runtime(data, plan, input_dir):
    if plan != EXPECTED_PLAN:
        raise ValueError('Unexpected runtime plan')
    expected = runtime_metadata(data.get('available_slugs', []))
    if set(data) != set(expected) | {'items'}:
        raise ValueError('Unexpected runtime fields')
    if any(data.get(k) != v for k, v in expected.items()) or any(data.get(k) is not False for k in flags()):
        raise ValueError('Runtime scope or evidence status differs')
    expected_items = [x for x in plan['items'] if x['slug'] in expected['available_slugs']]
    if len(data.get('items', [])) != len(expected_items):
        raise ValueError('All five windows of each available source are required')
    for expected_item, item in zip(expected_items, data['items']):
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
    model = WhisperModel(str(model_dir), device='cpu', compute_type='int8', cpu_threads=1,
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
        report = {'schema': 'tennislive.asr-evidence-only.ttv-large-crosscheck.v1', 'created_at': stamp(),
            'input': item, 'basis_evidence': 'prior medium.en evidence for the same ten retained source windows',
            'model': {'id': MODEL_ID, 'revision': REVISION, 'model_sha256': MODEL_FILES['model.bin'][1]},
            'versions': versions, 'language': 'en', 'segments': rows, 'status': 'inference_only_not_verified',
            'empty_output_is_not_silence_proof': not rows,
            'uncertainty_note': 'Raw model evidence can omit or hallucinate speech. It does not settle conflicting words or verify foreground audio.', **flags()}
        dump(outdir / f'{item["id"]}.json', report)
        completed.append(item['id'])
        print(json.dumps({'completed': item['id'], 'segments': len(rows), 'review_pass': False}), flush=True)
    dump(outdir / 'batch.json', {'schema': 'tennislive.ttv-large-crosscheck-batch.v1',
        'created_at': stamp(), 'completed': completed, 'source_seconds': data['source_seconds'], 'planned_source_seconds': 185.51,
        'available_slugs': data['available_slugs'], 'blocked_slugs': data['blocked_slugs'],
        'scope_status': 'complete_ten_window_inference_only' if len(data['available_slugs']) == 2 else 'partial_five_window_inference_only', **flags()})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['inputs', 'acquire', 'download-model', 'infer'], required=True)
    parser.add_argument('--plan', type=Path, default=Path('assets/asr-review-20261001/ttv-retained-windows-v3.json'))
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--workdir', type=Path)
    parser.add_argument('--outdir', type=Path)
    args = parser.parse_args()
    plan = read_plan(args.plan, args.plan_sha256)
    if args.mode == 'inputs':
        print(json.dumps({'clips': 10, 'source_seconds': 185.51, 'validated_plan': args.plan_sha256, **flags()}))
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
        paths = acquire_sources(args.workdir / 'sources', args.outdir / 'sources.json')
        dump(runtime, extract_windows(plan, paths, input_dir))
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
