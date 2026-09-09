"""Concurrent dispatch receipts must survive without reverting newer runs."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from merge_orchestration_state import merge_interview_states


def state(**entries):
    return {'slugs': sorted(entries), 'at': {s: v[0] for s, v in entries.items()},
            'spec_sha256': {s: v[1] for s, v in entries.items()}}


def test_different_slugs_and_remote_release():
    base = state(old=('2026-09-09T01:00:00Z', 'old'))
    ours = state(old=('2026-09-09T01:00:00Z', 'old'), zheng=('2026-09-09T02:00:00Z', 'z'))
    theirs = state(rybakina=('2026-09-09T03:00:00Z', 'r'))
    assert merge_interview_states(base, ours, theirs) == state(
        zheng=('2026-09-09T02:00:00Z', 'z'), rybakina=('2026-09-09T03:00:00Z', 'r'))


def test_same_slug_latest_timestamp_and_hash_stay_together():
    base = state(zheng=('2026-09-09T01:00:00Z', 'base'))
    older = state(zheng=('2026-09-09T02:00:00Z', 'older'))
    newer = state(zheng=('2026-09-09T03:00:00Z', 'newer'))
    assert merge_interview_states(base, older, newer) == newer
    assert merge_interview_states(base, newer, older) == newer
    tie = state(zheng=('2026-09-09T03:00:00Z', 'remote'))
    assert merge_interview_states(base, newer, tie) == tie


def test_real_git_conflict_recovery_preserves_remote_other_file(tmp_path):
    root = Path(__file__).resolve().parents[1]
    def git(cwd, *args, check=True):
        return subprocess.run(['git', *args], cwd=cwd, check=check,
                              text=True, capture_output=True)
    remote = tmp_path / 'remote.git'
    git(tmp_path, 'init', '--bare', str(remote))
    local = tmp_path / 'local'
    other = tmp_path / 'other'
    git(tmp_path, 'clone', str(remote), str(local))
    git(local, 'checkout', '-b', 'main')
    for k, v in [('user.name', 'Test'), ('user.email', 'test@example.com')]:
        git(local, 'config', k, v)
    (local / 'tools').mkdir()
    (local / 'data').mkdir()
    for name in ['git_push_retry.sh', 'merge_orchestration_state.py']:
        shutil.copy(root / 'tools' / name, local / 'tools' / name)
    ledger = Path('data/interview_render_dispatched.json')
    (local / ledger).write_text(json.dumps(state()))
    git(local, 'add', '.')
    git(local, 'commit', '-m', 'base')
    git(local, 'push', '-u', 'origin', 'main')
    git(tmp_path, 'clone', '-b', 'main', str(remote), str(other))
    for k, v in [('user.name', 'Test'), ('user.email', 'test@example.com')]:
        git(other, 'config', k, v)
    base, ours = tmp_path / 'base.json', tmp_path / 'ours.json'
    base.write_text(json.dumps(state()))
    ours.write_text(json.dumps(state(zheng=('2026-09-09T02:00:00Z', 'z'))))
    shutil.copy(ours, local / ledger)
    git(local, 'add', '.')
    git(local, 'commit', '-m', 'local receipt')
    (other / ledger).write_text(json.dumps(state(rybakina=('2026-09-09T03:00:00Z', 'r'))))
    (other / 'unrelated.txt').write_text('keep remote content')
    git(other, 'add', '.')
    git(other, 'commit', '-m', 'concurrent receipt')
    git(other, 'push', 'origin', 'main')
    # Establish this is a real overlapping JSON conflict, not merely non-FF.
    assert git(local, 'pull', '--rebase', 'origin', 'main', check=False).returncode != 0
    git(local, 'rebase', '--abort')
    subprocess.run(['bash', '-c', 'source tools/git_push_retry.sh; push_interview_dispatch_retry main "$1" "$2" 3',
                    'test', str(base), str(ours)], cwd=local, check=True, capture_output=True, text=True)
    git(other, 'pull', '--ff-only', 'origin', 'main')
    assert json.loads((other / ledger).read_text()) == state(
        zheng=('2026-09-09T02:00:00Z', 'z'), rybakina=('2026-09-09T03:00:00Z', 'r'))
    assert (other / 'unrelated.txt').read_text() == 'keep remote content'
