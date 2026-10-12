#!/usr/bin/env python3
"""probe 之后、写 spec 之前：备好逐分对齐输入（pbp.json）。

这是「配音不脱节」链条（docs/scoreboard-alignment.md）的接缝：`fetch_match_pbp`
按球员姓反查 WTA 逐分 → pbp.json，写进 outdir。

比分板读数（scoreboard.json）原来在这一步用视觉模型读 contact 帧——该通道已于
2026-10-12 随模型整体移除；scoreboard.json 如需使用，由外部备料落盘后交给
assemble 的机械对齐（⑥）。逐分拿不到 → **退出码 0，只出声**——对齐是「给
segments 加料」，不是硬闸。ATP 场没有 WTA 逐分通路，find_match 查不到就是
正常空，不算错。

用法：
    python tools/prepare_alignment.py --home "Maria Timofeeva" \
        --away "Xiyu Wang" --outdir output/2026-08-15/reel/wangxiyu-timofeeva
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _surname(full: str) -> str:
    from tennislive.names import surname_en  # noqa: PLC0415
    return surname_en(full) or full


def fetch_pbp(home: str, away: str, outdir: Path) -> bool:
    """WTA 逐分 → outdir/pbp.json。查不到（ATP 场/没在窗口）返回 False，不抛。"""
    import datetime

    import requests

    from fetch_match_pbp import find_match, get

    session = requests.Session()
    today = date.today()
    surnames = [_surname(home), _surname(away)]
    # 找最近 3 天到明天这一窗口（reel 都是赛后快做，比赛日就在这一两天内），
    # 找不到就放宽到 7 天。窗口要按**比赛日**算，别按「今天」——凌晨结束的比赛
    # 在 UTC 里算昨天甚至前天，back=3 有时正好把它卡在窗口外。
    last = ""
    for back, ahead in ((3, 1), (7, 1)):
        try:
            ev, year, mid, _row = find_match(
                session, surnames, today - timedelta(days=back),
                today + timedelta(days=ahead))
            payload = get(session, f"tournaments/{ev}/{year}/matches/{mid}/point-by-point")
            (outdir / "pbp.json").write_text(
                json.dumps({"raw": payload}, ensure_ascii=False), encoding="utf-8")
            print(f"逐分拿到：{ev}/{year}/{mid}，{len(payload.get('points', []))} 分")
            return True
        except SystemExit as exc:  # find_match 找不到就 raise SystemExit，不是 Exception
            last = str(exc)
        except Exception as exc:  # noqa: BLE001 —— 换个窗口再试，都不行就降级
            last = f"{type(exc).__name__}: {exc}"
    print(f"⚠️ 逐分没拿到（可能 ATP 场或不在窗口）：{last}")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--home", required=True, help="英文全名，如 Maria Timofeeva")
    ap.add_argument("--away", required=True, help="英文全名，如 Xiyu Wang")
    ap.add_argument("--outdir", required=True, help="probe 产物目录（有 contact_*.jpg）")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ok_pbp = fetch_pbp(args.home, args.away, outdir)
    if ok_pbp:
        print("对齐备料：pbp.json 已落盘（scoreboard.json 由外部备料提供）。")
    else:
        print("逐分没备到（见上），assemble 的机械对齐这一步跳过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
