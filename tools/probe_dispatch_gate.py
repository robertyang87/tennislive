#!/usr/bin/env python3
"""probe 跑完之后要不要替它派发 render——match-reel.yml「probe 正式 spec 就绪后自动派发 render」那一步。

四种结果（stdout 最后一行是动作，说明走 stderr）：

| spec | 动作 | 退出码 |
|---|---|---|
| `specs/reels/<slug>.json` 不存在 | `waiting`：严格生产证据未齐，正常结果 | 0 |
| **手写 spec**（没有 `_production`） | `skip`：会话自己写的、自己派 render，probe 不替它派 | 0 |
| 自动 spec，`_production.status == "ready_for_render"` 且 `push.auto is True` | `dispatch` | 0 |
| 自动 spec 但不是 ready / 没有 push.auto | 合同对不上，红 | 1 |

来路（2026-09-28 返工审计）：run 36331363124，会话为 `cobolli-mensik-doubles-laver-cup-2026`
（手写 spec，307 条手写里的一条）在 main 上重 probe，这一步把 spec 当成自动链的产物去
`assert _production.status == "ready_for_render"`，裸 `AssertionError` 红掉整趟 probe——
probe 产物其实已经提交了，红的只是「要不要替它派 render」这个问题，而手写 spec 的答案
本来就是「不派」。自动 spec 那半的合同（ready ＋ push.auto）照旧是硬的。

用法::

    python tools/probe_dispatch_gate.py --spec specs/reels/<slug>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def decide(spec: dict | None) -> tuple[str, str]:
    """`(动作, 说明)`；动作是 waiting / skip / dispatch / error。"""
    if spec is None:
        return "waiting", "[waiting] 严格生产证据未齐；本次不 dispatch render"
    production = spec.get("_production")
    if not production:
        return "skip", ("[skip] 手写 spec（没有 `_production`）：它由会话自己派 render，"
                        "probe 不替它派——这一趟 probe 的产物已经提交")
    status = (production or {}).get("status") if isinstance(production, dict) else None
    if status != "ready_for_render":
        return "error", (f"自动 spec 的 `_production.status` 是 {status!r}，不是 ready_for_render"
                         "——promote 只该把 ready 的草稿落成正式 spec，合同对不上")
    if (spec.get("push") or {}).get("auto") is not True:
        return "error", "自动 spec 没有 `push.auto: true`——自动链的片子质检通过就要推，合同对不上"
    return "dispatch", "正式 spec + 自动推送合同已确认"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True)
    args = ap.parse_args(argv)
    path = Path(args.spec)
    spec = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    action, why = decide(spec)
    if action == "error":
        print(f"::error::{why}", file=sys.stderr)
        return 1
    print(why, file=sys.stderr)
    print(action)
    return 0


if __name__ == "__main__":
    sys.exit(main())
