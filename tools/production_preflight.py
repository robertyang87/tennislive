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


def check_copy(copy: Path, column: str, *, date: str = '', quiet: bool = False) -> None:
    # quiet：把 push_reel 的输出收进异常里，不写到 stdout——
    # `interview_preflight` 被 `pick_interview_renders` 调，后者的 stdout 是 dispatch 名单。
    date = date or datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    subprocess.run([sys.executable, str(ROOT / 'tools/push_reel.py'), '--stage', 'check',
                    '--copy', str(copy), '--outdir', 'output/preflight',
                    '--column', column, '--date', date], check=True,
                   **({'capture_output': True, 'text': True} if quiet else {}))


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
    # 收尾卡那一句要一行放得下——和 render 的 `check_takeaway`、picker 的预检**同一份
    # 判据**（`interview_spec_gates.takeaway_point_problems`，含豁免表和 `_wrap_ok`）。
    # 原来请求里写长了，要等自动链把它建成 spec、picker 预检报红才知道，多花一整趟循环。
    # 只要 PIL ＋ 仓库里的字体，不下载、不开浏览器。
    if problems := _takeaway_wrap(req):
        raise ValueError('解读卡的字放不下一行：' + '；'.join(problems))
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / 'request'
        base.with_suffix('.json').write_text(json.dumps(req, ensure_ascii=False))
        copy = base.with_suffix('.xhs.txt')
        copy.write_text(str(req.get('xhs') or ''), encoding='utf-8')
        check_copy(copy, '赛后开麦')


def _takeaway_wrap(req: dict) -> list[str]:
    if not req.get('takeaway'):
        return []
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        from interview_spec_gates import takeaway_point_problems  # noqa: PLC0415
        return takeaway_point_problems(
            {'slug': str(req.get('slug') or ''), 'takeaway': req['takeaway']})
    except (ImportError, OSError) as exc:
        # 判不了要出声，但不在这儿拦：render 的 `check_takeaway` 是同一道闸，照样会跑。
        print(f'[预检] 收尾卡一行放不放得下这次判不了（{type(exc).__name__}: {exc}），'
              '留给 render 那道同样的闸', file=sys.stderr)
        return []


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--spec', required=True)
    ap.add_argument('--column', required=True)
    args = ap.parse_args()
    path = Path(args.spec)
    check_copy(path.with_suffix('.xhs.txt'), args.column)


if __name__ == '__main__':
    main()
