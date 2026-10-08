"""CI-only frozen publication diagnostics; never a render or publish permission.

Only explicitly diagnosed rules for exact, already-sent snapshots can be omitted
from a current-source inventory scan. Every changed or new input fails closed.
The separate historical diagnostics test reports these known findings as debt.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data/production_history_snapshot.json'
TEXT_EVIDENCE = frozenset({'.json', '.json3', '.ass', '.txt', '.md'})


def _load() -> dict:
    try:
        data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get('version') == 1 else {}


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_entries(pathspecs: list[str]) -> dict[str, dict] | None:
    """Read local index identities/skip-worktree bits; never materialize blobs."""
    result = subprocess.run(
        ['git', '-C', str(ROOT), '-c', 'core.fsmonitor=false', 'ls-files',
         '-v', '--stage', '-z', '--', *pathspecs], capture_output=True,
        env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})
    if result.returncode:
        return None
    entries = {}
    try:
        for item in result.stdout.decode('utf-8').split('\0'):
            if not item:
                continue
            meta, path = item.split('\t', 1)
            flag, mode, oid, stage = meta.split()
            if stage != '0' or path in entries:
                return None
            entries[path] = {'mode': mode, 'oid': oid,
                             'skip_worktree': flag.upper() == 'S'}
    except (ValueError, UnicodeError):
        return None
    return entries


def _worktree_blob(path: Path, mode: str, oid: str) -> str | None:
    """Compare present local bytes with their Git blob identity, without fetch."""
    try:
        if mode == '120000':
            if not path.is_symlink():
                return None
            data = os.readlink(path).encode('utf-8')
            h = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
            h.update(f'blob {len(data)}\0'.encode()); h.update(data)
            return h.hexdigest()
        if mode not in {'100644', '100755'} or not path.is_file() or path.is_symlink():
            return None
        h = hashlib.sha1() if len(oid) == 40 else hashlib.sha256()
        h.update(f'blob {path.stat().st_size}\0'.encode())
        with path.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _repository_inputs_match(row: dict) -> bool:
    expected = row.get('repository_inputs')
    if not isinstance(expected, dict) or not expected:
        return False
    slug = row['slug']
    current = _git_entries([*expected, f'output/*/reel/{slug}/*'])
    if current is None:
        return False
    nontext = sorted(p for p in current if p.startswith('output/')
                     and f'/reel/{slug}/' in p and Path(p).suffix not in TEXT_EVIDENCE)
    if nontext != row.get('output_repository_paths'):
        return False
    # Newly created, not-yet-staged output binaries count as changes too.
    local = {p.relative_to(ROOT).as_posix()
             for p in (ROOT / 'output').glob(f'*/reel/{slug}/*')
             if p.is_file() and p.suffix not in TEXT_EVIDENCE}
    if not local <= set(nontext):
        return False
    for rel, identity in expected.items():
        path = ROOT / rel
        target = path.resolve()
        if not target.is_relative_to(ROOT.resolve()):
            return False
        actual = current.get(rel)
        if identity is None:
            if actual is not None or path.exists() or path.is_symlink():
                return False  # explicit absent-path marker, including unstaged additions
            continue
        if not isinstance(identity, dict) or not actual or any(
                identity.get(k) != actual.get(k) for k in ('mode', 'oid')):
            return False
        if path.exists() or path.is_symlink():
            if _worktree_blob(path, actual['mode'], actual['oid']) != identity['oid']:
                return False
        elif not actual['skip_worktree']:
            return False  # a local deletion is not a sparse checkout
    return True


def frozen_row(rule: str, spec_path: Path) -> dict | None:
    """Return an exact diagnostic row, or None so the caller runs its real gate."""
    try:
        rel = Path(spec_path).resolve().relative_to(ROOT.resolve()).as_posix()
        rows = _load().get('rows', [])
        matches = [r for r in rows if isinstance(r, dict) and r.get('spec_path') == rel]
        if len(matches) != 1:
            return None
        row = matches[0]
        if rule not in row.get('known_findings', {}):
            return None
        slug = row['slug']
        if rel != f'specs/reels/{slug}.json' or Path(slug).name != slug:
            return None
        files = row['files']
        required = {rel, row['copy_path'], row['ledger_path'], row['pushed_path']}
        if not isinstance(files, dict) or not required <= files.keys():
            return None
        for path, digest in files.items():
            target = (ROOT / path).resolve()
            if not target.is_relative_to(ROOT.resolve()) or _digest(target) != digest:
                return None
        # New output evidence (including a new run/date) must re-enable checks.
        evidence = sorted(p.relative_to(ROOT).as_posix()
                          for p in (ROOT / 'output').glob(f'*/reel/{slug}/*')
                          if p.is_file() and p.suffix in TEXT_EVIDENCE)
        if evidence != row['output_evidence'] or not _repository_inputs_match(row):
            return None
        pushed = json.loads((ROOT / row['pushed_path']).read_text(encoding='utf-8'))
        ledger = json.loads((ROOT / row['ledger_path']).read_text(encoding='utf-8'))
        receipt = row['receipt']
        if not isinstance(receipt, str) or not receipt or pushed.get('pushplus_receipt') != receipt:
            return None
        if pushed.get('at') != row['published_at'] or ledger.get('slug') != slug:
            return None
        if not any(a.get('status') == 'sent' and a.get('pushplus_receipt') == receipt
                   for a in ledger.get('attempts', []) if isinstance(a, dict)):
            return None
        return row
    except (KeyError, TypeError, ValueError, OSError):
        return None


def should_check(rule: str, spec_path: Path) -> bool:
    return frozen_row(rule, spec_path) is None


def diagnostics() -> list[dict]:
    """Expose old findings explicitly, without running or certifying media QC."""
    records = []
    for row in _load().get('rows', []):
        for rule, finding in row.get('known_findings', {}).items():
            state = 'frozen_known_finding' if not should_check(rule, ROOT / row['spec_path']) else 'must_recheck'
            records.append({'slug': row['slug'], 'rule': rule, 'state': state, 'finding': finding})
    return records


def print_diagnostics() -> None:
    print('Historical published findings (not a QA pass or old-media revalidation):')
    records = diagnostics()
    if not records:
        raise SystemExit('Historical snapshot is unavailable or empty; current inventory checks remain strict')
    for row in records:
        print(f"  {row['slug']} | {row['state']} | {row['rule']} | {row['finding']}")


if __name__ == '__main__':
    print_diagnostics()
