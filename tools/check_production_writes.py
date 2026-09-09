"""Reject stale generated writes if the same files changed upstream meanwhile."""
import argparse
import subprocess


def changed(*args):
    return set(subprocess.check_output(['git', 'diff', '--name-only', *args], text=True).splitlines())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--remote', required=True)
    args = ap.parse_args()
    local = changed('HEAD') | set(subprocess.check_output(
        ['git', 'ls-files', '--others', '--exclude-standard'], text=True).splitlines())
    upstream = changed('HEAD', args.remote)
    conflicts = sorted(p for p in local & upstream
                       if p.startswith(('specs/', 'requests/', 'output/')))
    if conflicts:
        raise SystemExit('正式稿在任务运行期间已更新，拒绝覆盖：' + ', '.join(conflicts))


if __name__ == '__main__':
    main()
