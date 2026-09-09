"""Run the publisher's own cheap checks before any media/model work."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_copy(copy: Path, column: str, *, date: str = '') -> None:
    date = date or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    subprocess.run([sys.executable, str(ROOT / 'tools/push_reel.py'), '--stage', 'check',
                    '--copy', str(copy), '--outdir', 'output/preflight',
                    '--column', column, '--date', date], check=True)


def check_request(req: dict) -> None:
    # No download, fonts, browser or ASR import required here.
    cov = req.get('cover') or {}
    zoom, focus = float(cov.get('zoom', 1)), float(cov.get('focus_y', .5))
    if not 1 <= zoom <= 2.4 or not 0 <= focus <= 1:
        raise ValueError('cover zoom/focus_y 超出安全范围')
    if cov.get('shot_type') == 'close_up' and zoom < 1.5:
        raise ValueError('close_up 封面 zoom 必须至少1.5')
    start, end = float(req.get('start') or 0), req.get('end')
    if start < 0 or (end is not None and float(end) <= start):
        raise ValueError('正文时间窗无效')
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / 'request'
        base.with_suffix('.json').write_text(json.dumps(req, ensure_ascii=False))
        copy = base.with_suffix('.xhs.txt')
        copy.write_text(str(req.get('xhs') or ''), encoding='utf-8')
        check_copy(copy, '赛后开麦')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--column', required=True)
    args = ap.parse_args()
    path = Path(args.spec)
    check_copy(path.with_suffix('.xhs.txt'), args.column)


if __name__ == '__main__':
    main()
