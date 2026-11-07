import base64
import datetime
import hashlib
import html
import json
import subprocess
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path('/workspace/jodar-finals-production')
DEST = ROOT / 'final/publication'
SLUG = 'jodar-finals-road-2026'
FINGERPRINT = json.loads((ROOT / 'final/published-metadata/render.json').read_text())['film_sha256']
REPO = 'robertyang87/tennislive'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'tennislive-publication-verification'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.status, response.read()

def from_main_blob(relative):
    result = json.loads(subprocess.check_output([
        'gh', 'api', f'repos/{REPO}/contents/{relative}?ref=main',
        '-H', 'Cache-Control: no-cache'], text=True))
    return base64.b64decode(result['content'])

def from_main(relative):
    raw = from_main_blob(relative)
    return raw, json.loads(raw)

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('src', 'href', 'poster') and value:
                self.values.append(html.unescape(value))

ledger_bytes, ledger = from_main(f'data/reel_publish_ledger/{SLUG}.json')
pushed_bytes, pushed = from_main(f'output/2026-11-07/reel/{SLUG}/pushed.json')
attempts = [a for a in ledger['attempts'] if a['fingerprint'] == FINGERPRINT]
assert len(attempts) == 1, attempts
attempt = attempts[0]
assert attempt['status'] == 'sent', attempt
assert all(pushed[k] == attempt[k] for k in ('pushplus_receipt', 'message_url', 'run', 'at'))
DEST.mkdir(parents=True, exist_ok=True)
(DEST / 'ledger.json').write_bytes(ledger_bytes)
(DEST / 'pushed.json').write_bytes(pushed_bytes)
status, body = fetch(attempt['message_url'])
assert status == 200
(DEST / 'actual-message.html').write_bytes(body)
text = html.unescape(body.decode('utf-8'))
assert SLUG in text and '霍达尔' in text
metadata = json.loads((ROOT / 'final/published-metadata/render.json').read_text())
assert metadata['film_sha256'] == FINGERPRINT
assert metadata['video_url'] in text
remote = json.loads((DEST / 'release-entire-file-verification.json').read_text())
assert remote['sha256'] == FINGERPRINT and remote['url'] == metadata['video_url']
parser = Links()
parser.feed(text)
posters = [u for u in parser.values if SLUG in u and 'poster.jpg' in u]
copies = [u for u in parser.values if SLUG in u and 'copy.html' in u]
assert posters and copies, parser.values
assets = {}
for kind, url, filename in (
    ('poster', posters[0], 'poster.jpg'), ('copy', copies[0], 'copy.html')
):
    if url.startswith('//'):
        url = 'https:' + url
    code, payload = fetch(url)
    if kind == 'copy':
        expected = from_main_blob(f'output/2026-11-07/reel/{SLUG}/copy.html')
        copied_text = html.unescape(payload.decode('utf-8'))
        publication_copy = json.loads((ROOT / 'final/publication/expected-copy.json').read_text())
        assert publication_copy['copy_title'] in copied_text
        assert publication_copy['xhs_body'].strip() in copied_text
    else:
        expected = (ROOT / 'final/published-metadata' / filename).read_bytes()
    assert code == 200 and digest(payload) == digest(expected), (kind, code, digest(payload), digest(expected))
    (DEST / ('remote-' + filename)).write_bytes(payload)
    assets[kind] = {'url': url, 'http_status': code, 'bytes': len(payload), 'sha256': digest(payload), 'correct_asset': True}
report = {
    'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'status': 'pass', 'fingerprint': FINGERPRINT,
    'this_film_send_attempts': len(attempts), 'history_attempts': len(ledger['attempts']),
    'native_attempt': attempt, 'message_http_status': status,
    'correct_player_and_slug': True,
    'movie_url_matches_entire_remote_hashed_file': True,
    'assets': assets,
    'scope': 'Native receipt confirms platform acceptance; not a claim of delivery to a particular phone.'
}
(DEST / 'root-publication-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(report, ensure_ascii=False))
