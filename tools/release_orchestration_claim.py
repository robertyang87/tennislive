#!/usr/bin/env python3
"""从编排 state 释放一条失败的 probe claim。

只做纯 JSON 变更；工作流负责先检出远端最新 state、提交并用乐观重试推回。
这样下游 workflow_dispatch 固定在旧 SHA 上启动时，也不会再出现「失败了，但旧
checkout 里还没有 claim，所以摘不掉；随后 main 又把它记成已做过」的死锁。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_STATE = Path("data/orchestration_state.json")


def release_claim(path: Path, slug: str) -> bool:
    """删除 ``slug`` 的 claim；有变化返回 True，幂等无变化返回 False。"""
    if not path.is_file():
        print(f"没有 {path}，无需摘")
        return False
    state = json.loads(path.read_text(encoding="utf-8"))
    dispatched = state.setdefault("dispatched", {})
    if slug not in dispatched:
        print(f"{slug} 不在远端最新 state 里，无需摘")
        return False
    del dispatched[slug]
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已把 {slug} 从远端最新 orchestration_state 摘掉，下次 cron 可重试")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    args = parser.parse_args()
    release_claim(args.state, args.slug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
