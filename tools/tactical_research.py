"""Bounded, cached tactical reading. Discovery is not match verification."""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from production_cache import atomic_json, digest, root
from tennislive.research.article import fetch_article, _UA
from tennislive.names import surname_en

SOURCES = {
    'brain_game': {'domain': 'braingametennis.com', 'feed': 'https://braingametennis.com/feed/', 'index': 'https://braingametennis.com/features/blog/', 'role': 'tactical_analysis'},
    'tennis_abstract': {'domain': 'tennisabstract.com', 'feed': 'https://www.tennisabstract.com/blog/feed/', 'index': 'https://www.tennisabstract.com/blog/', 'role': 'sampled_analysis'},
    'hugh_clarke': {'domain': 'hughclarke.substack.com', 'feed': 'https://hughclarke.substack.com/feed', 'index': 'https://hughclarke.substack.com/archive', 'role': 'technical_background'},
    'atp': {'domain': 'atptour.com', 'index': 'https://www.atptour.com/en/news', 'role': 'official_report'},
    'wta': {'domain': 'wtatennis.com', 'index': 'https://www.wtatennis.com/news/analysis', 'role': 'official_report'},
    'usopen': {'domain': 'usopen.org', 'index': 'https://www.usopen.org/en_US/news/index.html', 'role': 'official_report'},
    'australian_open': {'domain': 'ausopen.com', 'index': 'https://ausopen.com/articles', 'role': 'official_report'},
    'roland_garros': {'domain': 'rolandgarros.com', 'index': 'https://www.rolandgarros.com/en-us/', 'role': 'official_report'},
    'wimbledon': {'domain': 'wimbledon.com', 'index': 'https://www.wimbledon.com/en_GB/news/index.html', 'role': 'official_report'},
}
TACTIC = re.compile(r'\b(serv\w*|return\w*|forehand|backhand|baseline|rall\w*|volley\w*|net|depth|wide|crosscourt|slice|position\w*)\b', re.I)


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.lower()) if not unicodedata.combining(c))


def allowed(url):
    p = urlparse(url)
    host = (p.hostname or '').lower().removeprefix('www.')
    return p.scheme == 'https' and any(host == v['domain'] for v in SOURCES.values())


def feed_items(content, home, away):
    names = [normalize(surname_en(n)) for n in (home, away)]
    result = []
    for item in ET.fromstring(content).findall('.//item'):
        title, url = item.findtext('title', ''), item.findtext('link', '')
        if allowed(url) and any(re.search(r'\b' + re.escape(n) + r'\b', normalize(title)) for n in names):
            result.append({'title': title, 'url': url, 'published_at': item.findtext('pubDate', '')})
    return result[:3]


def collect(payload):
    import requests
    statuses = {}
    def discover(name, source):
        try:
            rows = []
            note = ''
            if 'feed' in source:
                r = requests.get(source['feed'], headers={'User-Agent': _UA}, timeout=5)
                if r.status_code == 200:
                    rows = feed_items(r.content, payload['home'], payload['away'])
                else:
                    note = f"feed HTTP {r.status_code}; "
            if not rows and source.get('index'):
                # Publisher links only; never follow Google News wrapper pages.
                r = requests.get(source['index'], headers={'User-Agent': _UA}, timeout=5)
                if r.status_code != 200:
                    return name, [], note + f"index HTTP {r.status_code}"
                from html.parser import HTMLParser
                from urllib.parse import urljoin
                class Links(HTMLParser):
                    def __init__(self):
                        super().__init__(); self.urls = []
                    def handle_starttag(self, tag, attrs):
                        if tag == 'a':
                            self.urls.extend(v for k, v in attrs if k == 'href' and v)
                parser = Links(); parser.feed(r.text)
                names = [normalize(surname_en(n)) for n in (payload['home'], payload['away'])]
                rows = [{'url': urljoin(source['index'], u), 'title': '', 'published_at': ''}
                        for u in dict.fromkeys(parser.urls)
                        if any(n in normalize(u) for n in names)]
                rows = [v for v in rows if allowed(v['url'])][:3]
            return name, rows, note + ('ok' if rows else 'no_matching_article')
        except Exception as exc:
            return name, [], type(exc).__name__
    candidates = [{'url': u, 'title': '', 'published_at': '', 'provided': True}
                  for u in payload.get('source_urls', []) if allowed(u)]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, rows, status in pool.map(lambda pair: discover(*pair), SOURCES.items()):
            statuses[name] = status
            candidates.extend(rows)
    names = [normalize(surname_en(n)) for n in (payload['home'], payload['away'])]
    def priority(row):
        url = normalize(row['url'])
        official = any(v['role'] == 'official_report' and v['domain'] in url for v in SOURCES.values())
        return (not row.get('provided', False), -sum(n in url for n in names), not official)
    candidates.sort(key=priority)
    seen = set(); selected = []
    for row in candidates:
        if row['url'] not in seen and not re.search(r'draw|preview|prediction|schedule|where-to-watch', row['url'], re.I):
            seen.add(row['url']); selected.append(row)
    selected = selected[:6]
    def read(row):
        text, note = fetch_article(row['url'], timeout=5)
        if not text:
            return {**row, 'status': 'unavailable', 'note': note}
        names = [normalize(surname_en(n)) for n in (payload['home'], payload['away'])]
        # Both players must occur in the readable article; a headline alone is insufficient.
        both = all(re.search(r'\b' + re.escape(n) + r'\b', normalize(text)) for n in names)
        paras = [p for p in text.splitlines()
                 if len(TACTIC.findall(p)) >= 2
                 and any(re.search(r'\b' + re.escape(n) + r'\b', normalize(p)) for n in names)]
        paragraphs = sorted(paras, key=lambda p: -len(TACTIC.findall(p)))[:2]
        return {**row, 'status': 'read', 'text_sha256': digest(text),
                'scope': 'candidate_match_report' if both and all(n in normalize(row['url']) for n in names) else 'player_background',
                'excerpts': [p[:1200] for p in paragraphs], 'note': note,
                'match_verified': False}
    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(read, selected))
    return {'version': 1, 'identity': payload, 'sources': records, 'source_status': statuses,
            'status': 'ready' if any(r.get('excerpts') for r in records) else 'no_readable_analysis',
            'collected_at': datetime.now(timezone.utc).isoformat()}


def research(*, home, away, event, year, source_urls=(), budget=35):
    payload = {'home': home, 'away': away, 'event': event, 'year': year, 'source_urls': list(source_urls)}
    if os.environ.get('TENNISLIVE_TACTICAL_RESEARCH', '1') == '0':
        return {'status': 'disabled', 'sources': []}
    key = digest({'payload': payload, 'version': 1})
    cache = root() / 'tactical-reading' / (key + '.json')
    try:
        saved = json.loads(cache.read_text())
        # Short negative-cache TTL avoids waiting for a fresh article across retries.
        if time.time() - cache.stat().st_mtime < (1800 if saved.get('status') == 'ready' else 180):
            return {**saved, 'cache_hit': True}
    except (OSError, ValueError):
        pass
    start = time.monotonic()
    try:
        run = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--worker'],
                             input=json.dumps(payload), text=True, capture_output=True,
                             timeout=budget, check=True)
        result = json.loads(run.stdout)
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        result = {'version': 1, 'identity': payload, 'sources': [],
                  'status': 'timeout' if isinstance(exc, subprocess.TimeoutExpired) else 'unavailable',
                  'reason': type(exc).__name__}
    result['elapsed_seconds'] = round(time.monotonic() - start, 3)
    atomic_json(cache, result)
    return result


def start_research(**kwargs):
    # Overlap the bounded subprocess with score/source/ASR preparation.
    if os.environ.get("TENNISLIVE_TACTICAL_RESEARCH", "1") == "0":
        from concurrent.futures import Future
        future = Future()
        future.set_result({"status": "disabled", "sources": []})
        return future
    pool = ThreadPoolExecutor(max_workers=1)
    future = pool.submit(research, **kwargs)
    pool.shutdown(wait=False)
    return future


def verified_context(packet, *, identity=None):
    """Only explicitly reviewed, exact-match evidence can enter voice-bound facts.

    Discovery itself never toggles match_verified. Editors supply match verification
    and a timecoded shot; historical analysis remains research, not a current-match claim.
    """
    if not identity or any(packet.get('identity', {}).get(k) != v for k, v in identity.items()):
        return ''
    out = []
    for row in packet.get('claims', []):
        source = next((s for s in packet.get('sources', []) if s.get('url') == row.get('url')), None)
        if not source or not allowed(str(row.get('url', ''))) or source.get('status') != 'read' or row.get('match_verified') is not True:
            continue
        quote = str(row.get('evidence_excerpt') or '').strip()
        footage = row.get('footage') or {}
        if (not quote or not any(quote in p for p in source.get('excerpts', []))
                or not footage.get('source_url')
                or not isinstance(footage.get('start'), (int, float))
                or not isinstance(footage.get('end'), (int, float))
                or not 0 <= footage['start'] < footage['end']):
            continue
        if row.get('claim'):
            out.append(f"- 技战术已核观点：{row['claim']}；报道证据：{quote}；来源：{row['url']}；画面：{footage}")
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--worker', action='store_true')
    ap.add_argument('--home'); ap.add_argument('--away'); ap.add_argument('--event', default='')
    ap.add_argument('--year', type=int, default=0); ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    result = collect(json.load(sys.stdin)) if args.worker else research(
        home=args.home, away=args.away, event=args.event, year=args.year)
    if args.out:
        atomic_json(args.out, result)
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
