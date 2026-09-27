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


def check_interview_claims(spec_path: Path) -> None:
    """采访线的全称断言要认领两个独立源——和竖版短片、解说片同一份判据。

    来路：这道闸原来只装在竖版短片那条线上（`build_match_reel.validate_spec`），
    采访线一道都没有；2026-09-27 扫出 2 份已发的采访 spec 带着没认领的断言
    （挂在 `absolute_claims.INTERVIEW_LEGACY`）。引号里的话是受访者说的，不算。

    ⚠️ **自动转正的采访 spec 也硬拦，没有竖版短片那种「自动 spec 只报」的分流**——
    那一刀是因为模型写不了 `_claims`，而采访线**没有模型写的文案**：
    `draft_interview_spec` 不写 push/cover/takeaway，`promote_interview_draft` 只填模板
    （模板里没有全称断言，`test_采访线自动转正的模板文案过得了全称断言那道闸` 钉着）；
    带文案的草稿来自人工请求（`build_interview_request` 原样抄），人写得了 `_claims`。
    哪天草稿开始带模型写的文案，先在 promote 那一关分流。
    """
    sys.path.insert(0, str(ROOT / 'tools'))
    from absolute_claims import interview_problem  # noqa: PLC0415

    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    problem = interview_problem(spec, spec_path.stem)
    if problem:
        raise SystemExit(problem)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--column', required=True)
    args = ap.parse_args()
    path = Path(args.spec)
    if args.column == '赛后开麦' and path.is_file():
        check_interview_claims(path)
    check_copy(path.with_suffix('.xhs.txt'), args.column)


if __name__ == '__main__':
    main()
