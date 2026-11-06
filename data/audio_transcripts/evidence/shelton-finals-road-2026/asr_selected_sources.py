from pathlib import Path
import argparse
import datetime
import hashlib
import json

from faster_whisper import WhisperModel, decode_audio


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tasks', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--threads', type=int, default=2)
    args = parser.parse_args()
    tasks = json.loads(Path(args.tasks).read_text())
    outroot = Path(args.out)
    outroot.mkdir(parents=True, exist_ok=True)
    prepared = []
    for task in tasks:
        source = Path(task['source_path'])
        actual_sha = sha(source)
        assert actual_sha == task['source_sha256'], (task['id'], actual_sha)
        start, end = task['clip']
        audio = decode_audio(str(source), sampling_rate=16000)[int(start * 16000):int(end * 16000)]
        prepared.append((task, source, start, end, actual_sha, audio))
    for modelname in ['small.en', 'medium.en']:
        print('MODEL', modelname, flush=True)
        model = WhisperModel(modelname, device='cpu', compute_type='int8',
                             cpu_threads=args.threads, num_workers=1,
                             local_files_only=True)
        for task, source, start, end, actual_sha, audio in prepared:
            dest = outroot / task['id'] / f'{modelname}.json'
            if dest.exists():
                existing = json.loads(dest.read_text())
                if (existing.get('source_sha256') == actual_sha
                        and existing.get('clip') == [start, end]
                        and existing.get('model') == modelname):
                    print('REUSE_EXACT_EXISTING_RAW', dest, flush=True)
                    continue
                raise RuntimeError(f'Refuse overwrite of different-identity raw: {dest}')
            segments, info = model.transcribe(
                audio, language='en', word_timestamps=True, vad_filter=False,
                beam_size=5, condition_on_previous_text=False)
            rows = [{
                'start': round(segment.start + start, 2),
                'end': round(segment.end + start, 2),
                'text': segment.text.strip(),
                'avg_logprob': segment.avg_logprob,
                'no_speech_prob': segment.no_speech_prob,
                'words': [{'w': word.word,
                           's': round(word.start + start, 2),
                           'e': round(word.end + start, 2),
                           'p': word.probability}
                          for word in segment.words or []]
            } for segment in segments]
            result = {
                'schema': 'native-faster-whisper-actual-source.v1',
                'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'model': modelname, 'source_sha256': actual_sha,
                'source_path': str(source), 'clip': [start, end],
                'duration': info.duration, 'language_requested': 'en',
                'detected_language': info.language,
                'parameters': {'word_timestamps': True, 'vad_filter': False,
                               'beam_size': 5, 'condition_on_previous_text': False,
                               'compute_type': 'int8', 'cpu_threads': args.threads},
                'segments': rows,
            }
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
            print(json.dumps({'id': task['id'], 'path': str(dest),
                              'sha256': sha(dest),
                              'segments': [(row['start'], row['end'], row['text']) for row in rows]},
                             ensure_ascii=False), flush=True)
        del model


if __name__ == '__main__':
    main()
