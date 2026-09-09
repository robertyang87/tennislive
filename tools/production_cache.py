"""Small, content-addressed production checkpoints; never cache a QC verdict."""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
from pathlib import Path


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def file_digest(path: Path) -> str:
    if not path.is_file():
        return ''
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def root() -> Path:
    return Path(os.environ.get('TENNISLIVE_PRODUCTION_CACHE',
                               '~/.cache/tennislive-production')).expanduser()


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.checkpoint-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def cached_json(namespace: str, key, produce):
    path = root() / namespace / (digest(key) + '.json')
    try:
        record = json.loads(path.read_text())
        if record['sha256'] == digest(record['value']):
            print(f'[cache] {namespace}: hit')
            return record['value']
    except (OSError, ValueError, KeyError, TypeError):
        pass
    value = produce()
    atomic_json(path, {'sha256': digest(value), 'value': value})
    return value
