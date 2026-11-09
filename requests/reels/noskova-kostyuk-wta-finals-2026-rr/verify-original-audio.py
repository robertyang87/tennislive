"""Independent original-track recognition; never changes a production approval."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import imageio_ffmpeg
import requests

root = Path(os.environ['AUDIO_DIR'])
source = next(p for p in root.iterdir() if p.suffix in {'.webm', '.m4a', '.opus'})
key, region = os.environ.get('AZURE_SPEECH_KEY'), os.environ.get('AZURE_SPEECH_REGION')
report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'source_file': source.name, 'provider_available': bool(key and region),
          'scope': 'Recognition evidence only; not a production review or approval.', 'rows': []}
if key and region:
    for label, start, end in [('closing', 267.5, 279.2), ('score', 172.6, 175.0),
                              ('set', 98.5, 114.08)]:
        wav = root / f'verify-{label}.wav'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error',
                        '-ss', str(start), '-i', str(source), '-t', str(end-start),
                        '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
        for language in ['en-GB', 'en-US']:
            response = requests.post(
                f'https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1',
                params={'language': language, 'format': 'detailed'},
                headers={'Ocp-Apim-Subscription-Key': key,
                         'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=16000'},
                data=wav.read_bytes(), timeout=90)
            try:
                data = response.json()
            except ValueError:
                data = {'response_text': response.text[:300]}
            report['rows'].append({'label': label, 'start': start, 'end': end,
                                   'language': language, 'http_status': response.status_code,
                                   'response': data})
            print(label, language, response.status_code, data, flush=True)
(root / 'original-audio-stt.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
