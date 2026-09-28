#!/usr/bin/env python3
"""reel-auto-ready 的一步：替 pending 草稿**只重跑读失败的 flashscore 备料块**。

probe 那一趟 `assemble_spec` 读 flashscore 失败（5xx／超时，可重试的那种）时，草稿照写、
留在 waiting，并在 `_feed_retry` 里记下哪几块没读到。编排器认得这份草稿、永不重 probe，
所以要有人回来补——而重 probe 要重下源片，这里只重读那几块 feed（几个 HTTP 请求）：

    python tools/retry_feed_blocks.py --draft specs/reels/pending/<slug>.draft.json --write

stdout 最后一行是这一班的结果（`none` / `later` / `healed` / `copy_dropped` / `dropped` /
`retry` / `gave_up` / `exhausted` / `broken`，语义见 `assemble_spec.retry_feed_blocks`；
`later`＝还在退避，`broken`＝重跑本身崩了）。

- **退避**：第一次下一班就来，之后按 `FEED_RETRY_BACKOFF` 隔 20、40 分钟（`feed_retry_due_at`）
- **墙钟上限**：工作流给这一步套 `timeout`；被掐掉时另起一次 `--timed-out 秒数` 补记这一趟
  （`tries`＋1，试满照样停手）——被掐的进程没写草稿
- **要人看**的几种（试满、撤了文案、重读也一样的错、重跑崩了）打 `::warning::` ＋ 写 run 摘要
  （`$GITHUB_STEP_SUMMARY`），**只在第一次**；草稿里记 `_feed_retry.needs_human`，
  pipeline_health 按它点名——不静静地等到 PENDING_MAX_AGE 过期
- 人处置完：`--rearm --write` 清零重来（账上没有要重读的块就整个摘掉），推 main

退出码恒为 0（草稿本身读不出来除外）：重读失败是「这一班没读到」，不是这一班的故障。
判据 `tests/test_feed_retry.py`。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assemble_spec import (  # noqa: E402
    FEED_RETRY_MAX,
    _one_line,
    feed_retry_due_at,
    flag_feed_retry,
    rearm_feed_retry,
    record_feed_timeout,
    retry_feed_blocks,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summary(line: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _write(path: Path, draft: dict) -> None:
    """先写临时文件再换名：工作流的 `timeout` 掐在写到一半时，留下的是旧草稿，不是半截 JSON。"""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--draft", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--timed-out", type=int, metavar="SECONDS",
                    help="上一次调用被工作流的 timeout 掐掉了：只补记这一趟，不读 feed")
    ap.add_argument("--rearm", action="store_true",
                    help="人看过之后重新布置：tries 清零，摘掉 exhausted_at／needs_human")
    args = ap.parse_args(argv)
    raw = args.draft.read_text(encoding="utf-8")
    draft = json.loads(raw)
    slug = str(draft.get("slug") or args.draft.name)
    before = list((draft.get("_feed_retry") or {}).get("needs_human") or [])

    if args.rearm:
        status = "rearmed" if rearm_feed_retry(draft) else "none"
        print(f"[feed] {slug}: " + ("重新布置了备料重跑" if status == "rearmed" else "账上没东西可重置"))
    elif args.timed_out is not None:
        status = record_feed_timeout(draft, args.timed_out)
    else:
        ledger = draft.get("_feed_retry") or {}
        due = feed_retry_due_at(ledger) if ledger.get("blocks") \
            and not ledger.get("exhausted_at") else None
        if due is not None and _now() < due:
            print(f"[feed] {slug}: 第 {ledger.get('tries')} 次没读到，退避到 "
                  f"{due.strftime('%H:%MZ')} 之后再重跑")
            print("later")
            return 0
        try:
            status = retry_feed_blocks(draft)
        except Exception as exc:  # noqa: BLE001 —— 崩了也要记账、停手、点名，不许每一班重演
            draft = json.loads(raw)  # 崩在半路的草稿可能已经改了一半，从盘上那份记
            flag_feed_retry(draft, f"retry_feed_blocks 崩了：{_one_line(exc)}", stop=True)
            status = "broken"

    ledger = draft.get("_feed_retry") or {}
    blocks = "、".join(ledger.get("blocks") or ())
    if status == "none":
        print(f"[feed] {slug}: 备料没有欠账")
    elif status == "healed":
        print(f"[feed] {slug}: 备料重跑读通了")
    elif status == "retry":
        print(f"[feed] {slug}: 还没读到 {blocks}（第 {ledger.get('tries')}/{FEED_RETRY_MAX} 次），"
              "退避之后再来")
    elif status == "exhausted":
        # 试满那一班已经打过 warning、写过摘要，pipeline_health 在点名——这儿不再每一班刷一遍
        print(f"[feed] {slug}: 已经试满 {FEED_RETRY_MAX} 次，不再重跑（pipeline_health 在点名）")
    elif status == "gave_up":
        errors = "；".join(f"{k}: {v}" for k, v in (ledger.get("errors") or {}).items())
        line = (f"{slug}：flashscore 备料重跑 {FEED_RETRY_MAX} 次仍没读到 {blocks}"
                f"（{errors}）——不再自动重跑，要人看一眼")
        print(f"::warning::{line}")
        _summary(f"- ⚠️ {line}")
    for why in (ledger.get("needs_human") or ()):
        if why in before:
            continue
        line = f"{slug}：{why}——草稿留在 waiting，要人看一眼"
        print(f"::warning::{line}")
        _summary(f"- ⚠️ {line}")
    if args.write and status not in ("none", "exhausted"):
        _write(args.draft, draft)
    print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
