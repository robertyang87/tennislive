#!/usr/bin/env python3
"""Preserve raw local ASR evidence; never certify a complete editorial review.

Examples (isolated venv):
  python transcribe_source.py --source source.mp4 --url URL --out raw-small.json
  python transcribe_source.py --source source.mp4 --url URL --model base --no-vad --from 20 --to 40 --out raw-base-window.json

Outputs source-absolute timestamps and a hash of the untouched original source.
Does not claim to hear English when a Chinese model hallucinates an English word.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
import wave
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--url', required=True)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--model', default='small')
    parser.add_argument('--cache', default='/workspace/eala-research/asr-models')
    parser.add_argument('--language', default='auto', help='auto / zh / en; no forced English for Chinese commentary')
    parser.add_argument('--no-vad', action='store_true')
    parser.add_argument('--from', dest='start', type=float, default=0)
    parser.add_argument('--to', dest='end', type=float)
    parser.add_argument('--threads', type=int, default=8)
    args = parser.parse_args()
    if not args.source.is_file() or args.start < 0 or args.end is not None and args.end <= args.start:
        parser.error('source missing or invalid range')

    from faster_whisper import WhisperModel
    import numpy as np

    with args.source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    begin = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='eala-asr-') as folder:
        audio = Path(folder) / 'window.wav'
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(args.start), '-i', str(args.source)]
        if args.end is not None:
            command += ['-t', str(args.end-args.start)]
        command += ['-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(audio)]
        subprocess.run(command, check=True)
        print(f'Loading {args.model}, CPU int8, VAD={not args.no_vad}', flush=True)
        model = WhisperModel(args.model, device='cpu', compute_type='int8', cpu_threads=args.threads,
                             download_root=args.cache)
        # ffmpeg already decoded to 16 kHz PCM. Passing samples directly avoids
        # the incompatible metadata_errors argument in faster-whisper/PyAV 19.
        with wave.open(str(audio), 'rb') as waveform:
            assert waveform.getframerate() == 16000 and waveform.getnchannels() == 1 and waveform.getsampwidth() == 2
            samples = np.frombuffer(waveform.readframes(waveform.getnframes()), dtype=np.int16).astype(np.float32)/32768.0
        segments, info = model.transcribe(samples, language=None if args.language=='auto' else args.language,
                                          beam_size=5, word_timestamps=True, vad_filter=not args.no_vad,
                                          condition_on_previous_text=False)
        rows = []
        for segment in segments:
            row = {'id': segment.id, 'start': round(segment.start+args.start, 3),
                   'end': round(segment.end+args.start, 3), 'text': segment.text,
                   'avg_logprob': segment.avg_logprob, 'no_speech_prob': segment.no_speech_prob,
                   'compression_ratio': segment.compression_ratio,
                   'words': [{'start': round(w.start+args.start, 3), 'end': round(w.end+args.start, 3),
                              'word': w.word, 'probability': w.probability} for w in segment.words or []]}
            rows.append(row)
            print(f"{row['start']:.2f}–{row['end']:.2f}: {row['text']}", flush=True)
    packet = {'schema':'tennislive.raw-asr-evidence.v1', 'source_url':args.url,
              'source_path':str(args.source.resolve()), 'source_sha256':digest,
              'model':args.model, 'device':'cpu', 'compute_type':'int8',
              'word_timestamps':True, 'vad_filter':not args.no_vad,
              'condition_on_previous_text':False, 'requested_language':args.language,
              'detected_language':info.language, 'language_probability':info.language_probability,
              'range_from':args.start, 'range_to':args.end,
              'created_at':datetime.now(timezone.utc).isoformat(),
              'elapsed_seconds':round(time.monotonic()-begin, 2),
              'review_status':'raw_asr_only_not_certified', 'segments':rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(packet, ensure_ascii=False, indent=2)+'\n')
    print(f'Saved raw ASR evidence -> {args.out}', flush=True)


if __name__ == '__main__':
    main()
