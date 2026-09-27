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


def check_taste(spec: dict) -> None:
    """账号所有者的口味闸（采访线）：标题和推送标题的数字一致（硬）；封面大标题的
    术语只报（等账号所有者确认，见 `taste_gates.interview_taste_findings`）。

    2026-09-27「形成一个通用的规则在做视频前就拦掉，而不是说做了一半又返工」——
    所以它排在任何下载、ASR、渲染之前。判据单一出处 tools/taste_gates.py。
    """
    sys.path.insert(0, str(ROOT / 'tools'))
    from taste_gates import interview_taste_findings  # noqa: PLC0415
    hard, soft = interview_taste_findings(spec)
    for note in soft:
        print(f"[口味] {spec.get('slug', '?')} 只报：{note}")
    if hard:
        raise ValueError('不合账号所有者的口味：' + '；'.join(hard))


def check_request(req: dict) -> None:
    """请求预检（任何下载之前）。

    ⚠️ 口味闸读的必须是**这一趟真会写进 spec 的**标题和推送标题：调用方传进来的
    `req` 在「只改元数据」那条路上是 `{**请求, **按请求差量改过的现有 spec}`
    （现有 spec 手改过的标题赢），在重建那条路上就是请求本身（`build_spec` 原样
    抄请求的 cover/push）。所以这里不另去读 specs/ 下的旧稿。
    """
    # No download, fonts, browser or ASR import required here.
    check_taste(req)
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
    if args.column == '赛后开麦' and path.is_file():
        check_taste(json.loads(path.read_text(encoding='utf-8')))
    check_copy(path.with_suffix('.xhs.txt'), args.column)


if __name__ == '__main__':
    main()
