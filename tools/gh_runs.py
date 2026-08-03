#!/usr/bin/env python3
"""把 GitHub MCP 返回的那坨 JSON 挑成几行能看的。

**为什么要有这个脚本**，两条限制叠在一起：

1. 这台沙箱 `curl` 到 `api.github.com` 是 403（`GitHub access is not enabled
   for this session`），只有 MCP 那条路通——所以没法写一个自己去抓的工具
2. 而 MCP 的 `actions_list` 给每条 run 塞一整份 repository 元数据：
   **三条 run 就 400 KB**，直接超上下文，只能落到文件里

于是每次查 CI 都要现搓一段 `json.load` + 挑字段的 python。今天搓了五遍，
每遍都一样。收在这儿。

    # MCP 调用超上下文时会把返回体存成文件，把那个路径喂进来
    python3 tools/gh_runs.py <那个文件> --branch main --limit 5

两种返回体都认（今天两种都用到了）：

    list_workflow_runs  ->  {"workflow_runs": [...]}          每行一条 run
    list_workflow_jobs  ->  {"jobs": {"jobs": [{steps: []}]}} 每行一步

后者正是「**第 12 步 success 才算已推送，触发成功不算**」那条要查的东西——
`--steps` 会把每一步的结论和耗时列出来，一眼看得出卡在哪一步。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def _secs(a: str | None, b: str | None) -> str:
    """两个 ISO 时刻之间隔了多久。缺一个就不算——**别报一个编出来的 0**。"""
    if not a or not b:
        return "—"
    try:
        d = datetime.fromisoformat(b.replace("Z", "+00:00")) - datetime.fromisoformat(
            a.replace("Z", "+00:00")
        )
    except ValueError:
        return "—"
    total = int(d.total_seconds())
    return f"{total // 60}:{total % 60:02d}"


def _unwrap(payload):
    """剥掉 MCP 的 content-block 信封。

    超上下文时落盘的不再是裸 payload，而是 `[{"type": "text", "text": "<json 串>"}]`
    ——真正的返回体是那个**字符串**。这个脚本的全部用途就是解析这种文件，
    而它 2026-08-03 在这个形状上直接 `AttributeError: 'list' object has no
    attribute 'get'`：**报的是 Python 的类型错，不是「格式不认识」**，
    看起来像脚本坏了，而不是像喂错了东西。

    两种形状都认，认不出就原样退回去，让下游那句「顶层键是什么」去报。
    """
    if isinstance(payload, list):
        for block in payload:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                try:
                    return _unwrap(json.loads(block["text"]))
                except ValueError:
                    continue
    return payload


def _runs(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    return payload.get("workflow_runs") or []


def _jobs(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    outer = payload.get("jobs")
    if isinstance(outer, dict):
        return outer.get("jobs") or []
    return outer or []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", help="MCP 返回体落盘的那个文件")
    ap.add_argument("--branch", help="只看这条分支的 run")
    ap.add_argument("--sha", help="只看这个 commit 的 run（前缀匹配）")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--steps", action="store_true", help="列出每一步（jobs 返回体）")
    args = ap.parse_args(argv)

    try:
        payload = _unwrap(json.loads(Path(args.path).read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"读不出来：{exc}", file=sys.stderr)
        return 2

    runs, jobs = _runs(payload), _jobs(payload)
    if not runs and not jobs:
        # 空结果先自证是真空：把顶层键报出来，别只说「没有」——喂错文件和
        # 「真的一条都没有」长得一模一样。
        shape = sorted(payload) if isinstance(payload, dict) else type(payload).__name__
        print(f"这个文件里既没有 workflow_runs 也没有 jobs。顶层：{shape}",
              file=sys.stderr)
        return 2

    shown = 0
    for run in runs:
        if args.branch and run.get("head_branch") != args.branch:
            continue
        if args.sha and not str(run.get("head_sha", "")).startswith(args.sha):
            continue
        if shown >= args.limit:
            break
        shown += 1
        print(
            f"{str(run.get('head_sha',''))[:8]}  {run.get('event',''):<13} "
            f"{run.get('status')}/{run.get('conclusion')}  "
            f"{run.get('created_at','')}  用时 {_secs(run.get('created_at'), run.get('updated_at'))}"
            f"  id={run.get('id')}"
        )
    if runs:
        skipped = len(runs) - shown
        # 截断了就说一声——静默截断读起来像「一共就这些」。
        print(f"（{shown}/{len(runs)} 条"
              + (f"，另有 {skipped} 条未显示）" if skipped > 0 else "）"))

    for job in jobs:
        print(
            f"job {job.get('id')}  {job.get('name')}  "
            f"{job.get('status')}/{job.get('conclusion')}  "
            f"用时 {_secs(job.get('started_at'), job.get('completed_at'))}"
        )
        if not args.steps:
            continue
        for step in job.get("steps") or []:
            print(
                f"   {step.get('number'):>3}. {step.get('conclusion'):<9} "
                f"{_secs(step.get('started_at'), step.get('completed_at')):>6}  "
                f"{step.get('name')}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
