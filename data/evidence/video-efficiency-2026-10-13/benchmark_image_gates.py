import hashlib
import json
import sys
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'src')]
mode = sys.argv[1]
if mode not in {'baseline', 'optimized'}:
    raise SystemExit('mode must be baseline or optimized')
if mode == 'baseline':
    source = subprocess.check_output(['git', '-C', str(ROOT), 'show', '6402c4ae:tools/reel_asset_gates.py'], text=True)
    namespace = {'__name__': 'baseline_image_gates', '__file__': str(ROOT / 'tools/reel_asset_gates.py')}
    exec(compile(source, namespace['__file__'], 'exec'), namespace)
    check = namespace['image_problems']
else:
    import reel_asset_gates
    check = reel_asset_gates.image_problems
specs = [json.loads(p.read_text()) for p in sorted((ROOT / 'specs/reels').glob('*.json'))]
scans = []
for n in range(2):
    t = time.perf_counter()
    results = [(s['slug'], check(s)) for s in specs]
    elapsed = time.perf_counter() - t
    payload = json.dumps(results, ensure_ascii=False, sort_keys=True).encode()
    scans.append({'seconds': elapsed, 'results_sha256': hashlib.sha256(payload).hexdigest(),
                  'specs': len(specs), 'problem_count': sum(len(r) for _, r in results)})
print(json.dumps({'mode': mode, 'scans': scans}, indent=2))
