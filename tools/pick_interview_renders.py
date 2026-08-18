#!/usr/bin/env python3
"""扫 `specs/interviews/*.json`（正式 spec）→ 挑出还没 dispatch render 的 slug。

这是 interview-auto-render 的最后一环：把「提升成正式 spec 的采访」转成
`interview-clip.yml` 的 dispatch 列表。每 slug 一个 run，interview-clip 的
concurrency 按 slug 分组 → 不同采访天然并行。

已 dispatch 过的记在 `data/interview_render_dispatched.json`（slug 列表），
跑一次记一次，防重复 dispatch。

用法：
    python tools/pick_interview_renders.py               # 只打印待 dispatch 的
    python tools/pick_interview_renders.py --mark        # 打印 + 更新 dispatch 记录
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs" / "interviews"
STATE = ROOT / "data" / "interview_render_dispatched.json"


def _rendered_slugs() -> set[str]:
    """仓库里 `output/interviews/<slug>/render.json` 已存在的 slug（已 render 过）。

    用 `git ls-files` 从 index 读，**不受 sparse-checkout 影响**——workflow 的
    checkout 没拉 output/（1.36 GB），但 index 里全量文件都在。
    """
    import subprocess

    try:
        out = subprocess.run(["git", "ls-files", "output/interviews/"],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001 —— 拿不到就当没有，宁可多 dispatch 一次
        return set()
    return {line.split("/")[2] for line in out.splitlines()
            if line.count("/") >= 3 and "/render.json" in line}


def todo_slugs() -> list[str]:
    """正式 spec（非 .draft.json）里还没 render 也没 dispatch 过的 slug。"""
    done = set()
    if STATE.is_file():
        try:
            done = set(json.loads(STATE.read_text(encoding="utf-8")).get("slugs", []))
        except (OSError, ValueError):
            done = set()
    done |= _rendered_slugs()
    specs = sorted(p for p in SPECS.glob("*.json")
                   if not p.name.endswith(".draft.json"))
    return [p.stem for p in specs if p.stem not in done]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mark", action="store_true",
                    help="打印待 dispatch 列表，并把它们记进 dispatch 记录")
    args = ap.parse_args()

    todo = todo_slugs()
    print(f"待 dispatch {len(todo)} 条：")
    if args.mark and todo:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        done = set()
        if STATE.is_file():
            try:
                done = set(json.loads(STATE.read_text(encoding="utf-8"))
                           .get("slugs", []))
            except (OSError, ValueError):
                done = set()
        STATE.write_text(json.dumps({"slugs": sorted(done | set(todo))},
                                    ensure_ascii=False, indent=2),
                         encoding="utf-8")
    for s in todo:
        print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
