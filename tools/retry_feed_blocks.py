#!/usr/bin/env python3
"""reel-auto-ready 的一步：替 pending 草稿**只重跑读失败的 flashscore 备料块**。

probe 那一趟 `assemble_spec` 读 flashscore 失败（5xx／超时，可重试的那种）时，草稿照写、
留在 waiting，并在 `_feed_retry` 里记下哪几块没读到。编排器认得这份草稿、永不重 probe，
所以要有人回来补——而重 probe 要重下源片，这里只重读那几块 feed（几个 HTTP 请求）：

    python tools/retry_feed_blocks.py --draft specs/reels/pending/<slug>.draft.json --write

stdout 最后一行是这一班的结果（`none` / `healed` / `dropped` / `retry` / `gave_up` /
`exhausted`，语义见 `assemble_spec.retry_feed_blocks`）。试满 `FEED_RETRY_MAX` 次仍没读通的，
打 `::warning::` 并写进 run 摘要（`$GITHUB_STEP_SUMMARY`）；pipeline_health 另外按
`_feed_retry.exhausted_at` 点名——**不静静地等到 PENDING_MAX_AGE 过期**。

退出码恒为 0（草稿本身坏了除外）：重读失败是「这一班没读到」，不是这一班的故障。
判据 `tests/test_feed_retry.py`。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assemble_spec import FEED_RETRY_MAX, retry_feed_blocks  # noqa: E402


def _summary(line: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--draft", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    slug = str(draft.get("slug") or args.draft.name)
    status = retry_feed_blocks(draft)
    ledger = draft.get("_feed_retry") or {}
    blocks = "、".join(ledger.get("blocks") or ())
    if status == "none":
        print(f"[feed] {slug}: 备料没有欠账")
    elif status == "healed":
        print(f"[feed] {slug}: 备料重跑读通了")
    elif status == "dropped":
        print(f"::warning::{slug} 备料重跑读到了，但剩下的是重读也一样的错"
              "（见草稿 _notes），留在 waiting 等人")
    elif status == "retry":
        print(f"[feed] {slug}: 还没读到 {blocks}（第 {ledger.get('tries')}/{FEED_RETRY_MAX} 次），"
              "下一班再来")
    else:  # gave_up / exhausted
        errors = "；".join(f"{k}: {v}" for k, v in (ledger.get("errors") or {}).items())
        line = (f"{slug}：flashscore 备料重跑 {FEED_RETRY_MAX} 次仍没读到 {blocks}"
                f"（{errors}）——不再自动重跑，要人看一眼")
        print(f"::warning::{line}")
        _summary(f"- ⚠️ {line}")
    if args.write and status not in ("none", "exhausted"):
        args.draft.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
