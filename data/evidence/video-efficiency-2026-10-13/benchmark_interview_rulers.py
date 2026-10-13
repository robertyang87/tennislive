import hashlib
import json
import sys
import subprocess
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT / 'tools'), str(ROOT / 'src')]
import test_interview_segment_ruler as T
mode = sys.argv[1]
if mode not in {'baseline', 'optimized'}:
    raise SystemExit('mode must be baseline or optimized')
if mode == 'baseline':
    source = subprocess.check_output(['git', '-C', str(ROOT), 'show', '6402c4ae:tools/build_interview_clip.py'], text=True)
    old = types.ModuleType('baseline_interview_clip')
    old.__file__ = str(ROOT / 'tools/build_interview_clip.py')
    sys.modules[old.__name__] = old
    exec(compile(source, old.__file__, 'exec'), old.__dict__)
    T.clip = old
legacy = T.clip.legacy_segment_rulers()
corpus = T._rendered_corpus()
before = time.perf_counter()
rows = []
for spec, words, bounds, current in corpus:
    for ruler in [T.clip.segment_ruler(spec)] + ([T.clip.SEGMENT_RULER] if spec['slug'] in legacy else []):
        lines, bad = T._resegment(spec, words, ruler)
        rows.append({'slug': spec['slug'], 'ruler': ruler, 'lines': lines, 'en_fixed_misaligned': bad,
                     'width_problems': T.clip.en_problems(lines, ruler)})
elapsed = time.perf_counter() - before
payload = json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()
# Complete output is hashed below; do not write production artifacts.
print(json.dumps({'mode': mode, 'corpus_size': len(corpus), 'resegments': len(rows),
                  'seconds': elapsed, 'outputs_bytes': len(payload),
                  'outputs_sha256': hashlib.sha256(payload).hexdigest()}, indent=2))
