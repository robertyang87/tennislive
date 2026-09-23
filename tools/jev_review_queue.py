#!/usr/bin/env python3
"""Durable Jev suggestions and explicit visual-review handoff. No model approvals."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / 'data/jev_review_queue.json'


def identity(item):
    # Discovery time and model scores do not alter the source identity.
    return hashlib.sha256(json.dumps({k: item.get(k) for k in
        ('id', 'url', 'title', 'source', 'duration_s')},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_queue(path):
    if not path.exists():
        return {'version': 1, 'items': {}}
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('items'), dict):
        raise ValueError('invalid Jev queue')
    return data


def merge_report(queue, report, verdicts, *, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc).isoformat()
    added = unchanged = resolved = 0
    for row in report.get('review_queue', []):
        if row.get('jev', {}).get('suggestion') != 'interview':
            continue
        vid = str(row.get('id') or '')
        if not vid or not row.get('url') or not row.get('source'):
            continue
        # A previous final visual decision is authoritative, including rejection.
        if verdicts.get(vid, {}).get('verdict', 'unknown') != 'unknown':
            resolved += 1
            continue
        digest = identity(row)
        old = queue['items'].get(vid)
        if old and old.get('input_sha256') == digest:
            unchanged += 1
            continue
        queue['items'][vid] = {
            'item': {k: v for k, v in row.items() if k not in ('jev', 'requires_visual_review')},
            'input_sha256': digest, 'suggestion': row['jev'],
            'discovered_at': (old or {}).get('discovered_at') or row.get('discovered_at') or now,
            'status': 'pending_visual_review',
        }
        added += 1
    return {'added': added, 'unchanged': unchanged, 'existing_visual_decisions': resolved}


def approved_items(path, verdicts, cfg):
    try:
        queue = read_queue(path)
    except (OSError, ValueError, TypeError, AttributeError):
        print('::warning::Jev review queue unreadable; original collection continues')
        return []
    sources = {s['name']: s for s in cfg['sources']}
    approved = []
    for vid, record in queue['items'].items():
        if not isinstance(record, dict) or not isinstance(record.get('item'), dict):
            continue
        item = record['item']
        if not all(isinstance(item.get(k), str) and item[k] for k in ('id', 'source', 'url', 'title')):
            continue
        try:
            stamp = datetime.datetime.fromisoformat(record.get('discovered_at', '').replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                continue
        except (ValueError, TypeError, AttributeError):
            continue
        verdict = verdicts.get(vid, {})
        if not isinstance(verdict, dict):
            continue
        source = sources.get(item.get('source'))
        # No new automatic L0 method: require explicit human evidence bound to
        # the same metadata, then still run normal source/sport/freshness gates.
        if (not source or source.get('verified') is not True or
            source.get('provenance') not in ('official', 'broadcaster') or
            source.get('unofficial') or vid in cfg.get('deny_ids', [])):
            continue
        if (verdict.get('verdict') != 'oncourt' or
            verdict.get('method') != 'human_visual_verdict' or
            not verdict.get('by') or not verdict.get('evidence') or
            verdict.get('jev_input_sha256') != identity(item) or
            record.get('input_sha256') != identity(item) or
            str(item.get('id')) != vid):
            continue
        approved.append(dict(item, discovered_at=record['discovered_at'],
                             discovery_method='jev_human_visual_review',
                             jev_input_sha256=record['input_sha256']))
    return approved


def review_items(queue, verdicts, limit=5):
    # Oldest unresolved first; unknowns remain pending instead of being excluded.
    rows = []
    for vid, record in sorted(queue['items'].items(), key=lambda kv: (kv[1].get('last_frames_at', ''), kv[1]['discovered_at'], kv[0])):
        if verdicts.get(vid, {}).get('verdict', 'unknown') != 'unknown':
            continue
        item = record['item']
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
            continue  # Site posters cannot establish actual footage identity.
        rows.append(dict(item, jev_input_sha256=record['input_sha256']))
        if len(rows) >= limit:
            break
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--queue', type=Path, default=QUEUE)
    args = parser.parse_args()
    queue = read_queue(args.queue)  # Corruption must never overwrite existing review work.
    verdicts = json.loads((ROOT / 'data/oncourt_verify.json').read_text()).get('verdicts', {})
    result = merge_report(queue, json.loads(args.report.read_text()), verdicts)
    args.queue.parent.mkdir(parents=True, exist_ok=True)
    temp = args.queue.with_suffix('.tmp')
    temp.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(args.queue)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
