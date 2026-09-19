"""Reproduce local transition evidence; no network or model calls."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

source = Path('goat-7686680149357579529.mp4')
expected = 'b291bd5cae52d2f6721279b2268c8724ea6acc0e0d14462f1ffe7f0d28369dbd'
actual = hashlib.file_digest(source.open('rb'), 'sha256').hexdigest()
if actual != expected:
    raise SystemExit('Source hash mismatch; stop')
result = subprocess.run([
    'ffmpeg', '-hide_banner', '-i', str(source), '-vf',
    "select='gt(scene,0.25)',showinfo", '-an', '-f', 'null', '-'
], capture_output=True, text=True, check=True)
times = [float(x) for x in re.findall(r'pts_time:([0-9.]+)', result.stderr)]
report = {
    'source_sha256': actual,
    'scene_threshold': 0.25,
    'scene_change_candidates_seconds': times,
    'scene_change_candidate_count': len(times),
    'verified_shot_count': None,
    'median_shot_duration_seconds': None,
    'warning': 'Graphic geometry and flashes trigger candidates; these are not a shot list.',
    'frame_review_ranges': [
        {'start': 19.1, 'end': 19.7, 'frames': 19, 'source_fps': 30,
         'image': 'goat-transition-19.png', 'coverage': 'every decoded source frame within range'},
        {'start': 51.5, 'end': 52.466667, 'frames': 30, 'source_fps': 30,
         'image': 'goat-transition-51-52.png', 'coverage': 'every decoded source frame within range'}
    ],
    'audio_listened': False,
    'production_consumed': False,
}
for entry in report['frame_review_ranges']:
    entry['image_sha256'] = hashlib.file_digest(Path(entry['image']).open('rb'), 'sha256').hexdigest()
Path('goat-transition-evidence-20260919.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'candidates': len(times), 'source_hash_ok': actual == expected}))
