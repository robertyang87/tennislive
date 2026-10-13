"""Controlled local HTTP benchmark; never calls PushPlus or external URLs."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import threading
import time
import types
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import requests
from tennislive.publish import pushplus

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, default=Path('/tmp/reel-asset-readiness-benchmark.json'))
args = parser.parse_args()
ROOT = Path(subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).decode().strip())
BASE = '7a1dbdb47261e25c01b8e98a98ef1625c1ab78bc'
relative = 'src/tennislive/publish/pushplus.py'
before = subprocess.check_output(['git', 'show', f'{BASE}:{relative}'], cwd=ROOT)
baseline = types.ModuleType('tennislive.publish._benchmark_baseline')
baseline.__package__ = 'tennislive.publish'
exec(compile(before, relative, 'exec'), baseline.__dict__)
lock = threading.Lock()
state = {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with lock:
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
            state['requests'][self.path] += 1
            count = state['requests'][self.path]
        time.sleep(.08)
        content_type = 'image/png' if self.path.endswith('.png') else 'video/mp4'
        # A duplicate fallback link must not excuse an HTML image error page.
        if state['retry'] and self.path.endswith('card0.png') and count == 1:
            content_type = 'text/html'
        with lock:
            state['active'] -= 1
            state['results'].append({'path': self.path, 'status': 200,
                                     'content_type': content_type})
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', '4')
        self.end_headers()
        self.wfile.write(b'data')

    def log_message(self, *args):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
real_get = requests.get

def local_get(url, **kwargs):
    # Requests still use actual HTTP sockets, response headers and close.
    path = urlparse(url).path
    return real_get(f'http://127.0.0.1:{server.server_port}{path}', **kwargs)

def forbid_post(*args, **kwargs):
    raise AssertionError('Benchmark must not send any message')

requests.get = local_get
os.environ['TENNISLIVE_PUSHPLUS_IMAGE_SETTLE_SECONDS'] = '0'
real_post = requests.post
requests.post = forbid_post
rows = []
try:
    for label, count, retry in [('reel_two_cards_and_movie', 2, False),
                                ('explainer_twelve_cards', 12, False),
                                ('reel_html_image_then_ready', 2, True)]:
        cards = [f'https://cdn.jsdelivr.net/gh/owner/repo@abc/card{i}.png'
                 for i in range(count)]
        html = ''.join(f'<img src="{url}"><a href="{url}">原图</a>'
                       for url in cards)
        if label.startswith('reel'):
            html += '<a href="https://github.com/owner/repo/releases/download/tag/movie.mp4">视频</a>'
        samples = {}
        for variant, function in [('before', baseline.wait_for_images),
                                  ('after', pushplus.wait_for_images)]:
            trials = []
            for _ in range(3):
                state = {'active': 0, 'peak': 0, 'requests': Counter(),
                         'retry': retry, 'results': []}
                started = time.perf_counter()
                function(html, attempts=2, delay=.03, timeout=3)
                elapsed = time.perf_counter() - started
                trials.append({'seconds': elapsed, 'request_count': sum(state['requests'].values()),
                               'peak_delayed_requests': state['peak'],
                               'requests_by_path': dict(state['requests']),
                               'responses': list(state['results'])})
                assert state['active'] == 0
            samples[variant] = {'median_seconds': statistics.median(t['seconds'] for t in trials),
                                'trials': trials}
        rows.append({'scenario': label, 'html': html, **samples})
finally:
    requests.get = real_get
    requests.post = real_post
    server.shutdown()
    server.server_close()
    thread.join()

document = {'kind': 'controlled_local_http_benchmark', 'base_commit': BASE,
            'before_source_sha256': hashlib.sha256(before).hexdigest(),
            'after_source_sha256': hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(),
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'latency_per_request_seconds': .08, 'trials_per_variant': 3,
            'message_posts': 0, 'external_http_requests': 0,
            'limits': 'Controlled transport, not a measured CDN/Pages production run or end-to-end SLA.',
            'scenarios': rows}
out = args.out
out.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
for row in rows:
    print(row['scenario'], row['before']['median_seconds'], row['after']['median_seconds'],
          row['before']['trials'][0]['request_count'], row['after']['trials'][0]['request_count'])
