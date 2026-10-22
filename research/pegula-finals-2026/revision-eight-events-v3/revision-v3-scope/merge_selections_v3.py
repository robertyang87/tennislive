"""Read-only v3 selection merge. Importing/running never rewrites v2 selections.
New package: {selections:[{key,start,end,source_name,captions,...}], source_index:[...]}
or a bare keyed dict; --package can point to any final agent delivery.
"""
from pathlib import Path
from copy import deepcopy
import argparse
import hashlib
import json

ROOT = Path('/workspace/pegula-finals-production')
HERE = Path(__file__).resolve().parent
VIDEO_KEYS = ('cold-quote', 'ao', 'dubai-final', 'dubai-speech',
 'charleston-final-extra', 'charleston-final', 'rg-r1', 'berlin-sf',
 'wimbledon-qf', 'cincy-sf', 'cincy-final', 'us-qf', 'us-qf-matchpoint',
 'us-qf-reaction', 'us-qf-interview', 'us-sf', 'us-sf-matchpoint')
NEW_KEYS = {'rg-r1', 'wimbledon-qf'}
DEFAULT_PACKAGES = (HERE/'rg/rg-matchpoint-selection.json', HERE/'wimbledon/wimbledon-matchpoint-selection.json')
DEFAULT_INDEXES = (HERE/'rg/source-index.json', HERE/'wimbledon/source-index.json')

def read_json(path):
    return json.loads(Path(path).read_text())

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(payload):
    if isinstance(payload, list):
        return payload
    for field in ('selections', 'primary_selections'):
        if field in payload:
            value = payload[field]
            return [dict(v, key=k) for k,v in value.items()] if isinstance(value,dict) else value
    return [dict(v, key=k) for k,v in payload.items() if isinstance(v,dict) and 'start' in v]

def normalize(row):
    r = deepcopy(row)
    r['source_name'] = r.get('source_name') or r.get('source_key') or r.get('source')
    r['captions'] = r.get('captions') or r.get('captions_absolute') or []
    r['audio_review_packet'] = r.get('audio_review_packet') or r.get('foreground_packet') or r.get('foreground_audio_review')
    if isinstance(r['audio_review_packet'], dict):
        ref = r['audio_review_packet']
        if ref.get('sha256') and sha256(ref['path']) != ref['sha256']:
            raise ValueError('Foreground packet SHA mismatch')
        r['audio_review_packet'] = ref['path']
    window = r.get('label_safe_window') or r.get('live_label_window') or r.get('live_label')
    if isinstance(window,dict):
        window = [window.get('source_start',window.get('start')),window.get('source_end',window.get('end'))]
    if window is not None:
        r['label_safe_window'] = window
    if r.get('quote_kind') == 'commentary':
        r['quote_kind'] = 'broadcast'
    return r

def load_selections(packages=()):
    previous = read_json(ROOT/'production/selections.json')
    selected = {k:deepcopy(v) for k,v in previous.items() if k in VIDEO_KEYS and k not in NEW_KEYS}
    evidence = []
    paths = list(DEFAULT_PACKAGES)+[Path(p) for p in packages]
    for path in dict.fromkeys(paths):
        if not path.is_file():
            continue
        data = read_json(path)
        evidence.append({'path':str(path),'sha256':sha256(path)})
        for row in rows(data):
            key = row.get('key') or row.get('id') or row.get('_id')
            if key in NEW_KEYS:
                selected[key] = normalize(row)
    return selected, evidence

def index_rows(data):
    if isinstance(data,list):
        return data
    for field in ('source_index','sources'):
        if field in data:
            return index_rows(data[field])
    return [dict(value,key=key) for key,value in data.items() if isinstance(value,dict)]

def load_source_index(packages=(), indexes=()):
    result = {}
    paths = [ROOT/'source-index.json', ROOT/'production/middle-source-index.json', *DEFAULT_INDEXES]
    paths += [Path(p) for p in indexes]
    for path in dict.fromkeys(paths):
        if path.is_file():
            for row in index_rows(read_json(path)):
                if row.get('key'):
                    result[row['key']] = row
    for path in dict.fromkeys([*DEFAULT_PACKAGES, *map(Path,packages)]):
        if path.is_file():
            payload = read_json(path)
            if isinstance(payload,dict) and ('source_index' in payload or 'sources' in payload):
                for row in index_rows(payload.get('source_index',payload.get('sources'))):
                    result[row['key']] = row
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', action='append', default=[])
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    selected,evidence = load_selections(args.package)
    payload = {'selections':selected,'package_evidence':evidence,
               'missing':[k for k in VIDEO_KEYS if k not in selected]}
    if args.output:
        args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    else:
        print(json.dumps({'keys':list(selected),'missing':payload['missing']},ensure_ascii=False))

if __name__ == '__main__':
    main()
