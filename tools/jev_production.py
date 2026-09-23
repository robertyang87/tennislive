#!/usr/bin/env python3
"""Jev production advisory stage. Never promotes inventory or dispatches media."""
import argparse
import json
import os
from pathlib import Path

import collect_oncourt_interviews as collector
import jev_selective as selective


def evaluate(items, cache, *, enabled=True):
    ledger = selective.Ledger(cache)
    try:
        report = selective.run([{k: v for k, v in item.items() if k not in ('description', 'transcript')} for item in items], collector.load_sources(), ledger,
                               live=enabled, max_calls=5, daily_limit=20)
    finally:
        ledger.db.close()
    report['mode'] = 'production_advisory'
    report['activation'] = ('disabled' if not enabled else
                            'enabled' if os.getenv('TYPESAFE_API_KEY') else 'missing_secret')
    by_id = {str(item['id']): item for item in items}
    report['review_queue'] = [
        dict(by_id[row['id']], jev=row, requires_visual_review=True)
        for row in report['records']
        if row.get('suggestion') == 'interview'
    ]
    # Even a confident title classification cannot establish on-court footage.
    report['inventory_promotions'] = 0
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    items = json.loads(args.input.read_text(encoding='utf-8'))['items']
    if not isinstance(items, list) or any(not isinstance(i, dict) for i in items):
        parser.error('invalid candidate input')
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    report = evaluate(items, args.cache, enabled=os.getenv('JEV_ENABLED', '1') != '0')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    summary = (f"Jev: {report['activation']}; candidates={report['total']}; "
               f"API attempts={report['api_attempts']}; "
               f"cache hits={report['counts'].get('cache_hit', 0)}; "
               f"interview review queue={len(report['review_queue'])}; "
               f"unconfirmed billing calls={report['unconfirmed_billing_calls']}. "
               "Inventory promotions=0; original production gates retained.")
    print(summary)
    if report['activation'] == 'missing_secret':
        print('::warning::Jev inactive: configure repository secret TYPESAFE_API_KEY')
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write(summary + '\n')


if __name__ == '__main__':
    main()
