"""Controlled local HTTP benchmark; no external Pages trigger or message send."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import types
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=Path('/tmp/reel-delivery-readiness-benchmark.json'))
args = parser.parse_args()
repo = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode().strip())
sys.path.insert(0, str(repo / 'tools'))
sys.path.insert(0, str(repo / 'src'))
base_sha = '7a1dbdb47261e25c01b8e98a98ef1625c1ab78bc'
old_source = subprocess.check_output(['git', '-C', str(repo), 'show', f'{base_sha}:tools/push_reel.py'])
old = types.ModuleType('benchmark_base_push_reel')
old.__file__ = str(repo / 'tools/push_reel.py')
exec(compile(old_source, old.__file__, 'exec'), old.__dict__)
new = importlib.import_module('push_reel')
os.environ['TENNISLIVE_COPYPAGE_ATTEMPTS'] = '3'
os.environ['TENNISLIVE_COPYPAGE_RETRY_SECONDS'] = '0.05'

def measure(mod, scenario, mode):
    trace = []
    lock = threading.Lock()
    counts = {'/copy': 0, '/video': 0}
    active, peak = 0, 0
    trigger_count = []
    mod.trigger_pages_build = lambda: trigger_count.append(True)
    mod.PagesWatchdog = lambda: types.SimpleNamespace(tick=lambda: None)
    original_video = mod.wait_for_video
    # Use the identical shortened retry budget in both variants; it is not a production measurement.
    mod.wait_for_video = lambda url: original_video(url, attempts=3, delay=0.05, timeout=2)
    started = 0

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                counts[self.path] += 1
                attempt = counts[self.path]
            began = time.perf_counter() - started
            time.sleep(0.20)
            ready = (time.perf_counter() - started >= 0.45 if scenario == 'both-ready-at-0.45s'
                     else scenario == 'already-ready' or attempt >= 3)
            if self.path == '/copy':
                status = 200
                payload = b'current &amp; title' if ready else b'previous-title'
            else:
                status = 206 if ready and scenario != 'video-unavailable' else 404
                payload = b'movie' if status == 206 else b'not-found'
            self.send_response(status)
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            with lock:
                trace.append({'path': self.path, 'attempt': attempt, 'begin_seconds': began,
                              'end_seconds': time.perf_counter() - started, 'status': status,
                              'payload': payload.decode(), 'request_headers': dict(self.headers)})
                active -= 1

        def do_POST(self):
            raise AssertionError('No send is allowed in this benchmark')

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    outcome = 'pass'
    error = None
    started = time.perf_counter()
    try:
        if mode == 'serial':
            mod.wait_for_copy_page(base + '/copy', 'current & title', timeout=2)
            mod.wait_for_video(base + '/video')
        else:
            mod.wait_for_delivery(base + '/copy', 'current & title', base + '/video')
    except SystemExit as exc:
        outcome = 'blocked'
        error = str(exc)
    duration = time.perf_counter() - started
    server.shutdown()
    server.server_close()
    server_thread.join(timeout=3)
    mod.wait_for_video = original_video
    assert len(trigger_count) == 1
    assert active == 0 and not server_thread.is_alive()
    assert outcome == ('blocked' if scenario == 'video-unavailable' else 'pass')
    return {'seconds': duration, 'outcome': outcome, 'error': error,
            'peak_in_flight': peak, 'trace': trace, 'pages_triggers': len(trigger_count),
            'post_count': 0}

rows = []
for scenario in ('already-ready', 'both-ready-at-0.45s', 'stale-page-and-delayed-video', 'video-unavailable'):
    for repeat in range(3):
        for mode, mod in [('serial', old), ('parallel', new)]:
            rows.append({'scenario': scenario, 'repeat': repeat, 'mode': mode, **measure(mod, scenario, mode)})

summary = []
for scenario in ('already-ready', 'both-ready-at-0.45s', 'stale-page-and-delayed-video', 'video-unavailable'):
    medians = {mode: statistics.median(r['seconds'] for r in rows if r['scenario'] == scenario and r['mode'] == mode)
               for mode in ('serial', 'parallel')}
    summary.append({'scenario': scenario, 'median_seconds': medians,
                    'saved_seconds': medians['serial'] - medians['parallel']})

evidence = {'base_sha': base_sha, 'old_push_reel_sha256': hashlib.sha256(old_source).hexdigest(),
            'new_push_reel_sha256': hashlib.sha256((repo / 'tools/push_reel.py').read_bytes()).hexdigest(),
            'benchmark_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'limits': ['Local HTTP latency simulation only, no production network speed claim',
                       'Exactly same shortened attempts=3 retry=0.05s and 0.20s response delay in both paths',
                       'Pages deployment trigger/watchdog mocked; current escaped title and video Range use real HTTP',
                       'No movie generated and no external WeChat/PushPlus POST performed',
                       'Original and new wait functions retain production retry budgets in committed source'],
            'rows': rows, 'summary': summary}
path = args.out
path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(summary, ensure_ascii=False, indent=2))
