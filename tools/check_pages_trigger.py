#!/usr/bin/env python3
"""在 runner 上真跑一趟 `trigger_pages_build()`，把它到底有没有生效说清楚。

**为什么要单独有这个入口。** 这条修复的判据是「`pages.yml` 里出现一条
`actor=github-actions[bot]` 的运行记录」，可它只在**真推送**的时候才走到——
而真推送会发微信。于是「验一下」和「发一条收不回来的消息」被绑在了一起，
这个修复因此在仓库里躺了一天，状态是「写了，没跑过」。这条路把验证从发布
里拆出来：只点 Pages，不发微信、不出片、不提交。

**它不信 `trigger_pages_build()` 的返回值。** 那个函数自己也会确认一次，
但「函数说它成功了」仍然是信号；这里自己前后各查一次运行列表，拿**集合差**
认出新的那条，再读它的 `actor`。判据和被判据的东西分开，才证明得了事。

⚠️ 副作用只有一个：Pages 真的会重新发布一次（实测 20~27 秒，幂等）。

⚠️ **在本地拿 PAT 跑，actor 会是你自己的名字**，那不算数——这条修复要证明
的恰恰是「工作流自带的 `GITHUB_TOKEN` 点得动」。所以默认要求 actor 是
`github-actions[bot]`，本地试手请显式 `--expect-actor <你的名字>`。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tennislive.render.pushmsg import (  # noqa: E402
    _PAGES_WORKFLOW,
    pages_runs,
    trigger_pages_build,
)

DEFAULT_ACTOR = "github-actions[bot]"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--expect-actor", default=DEFAULT_ACTOR,
                    help=f"新出现的那条 run 的 actor 应该是谁（默认 {DEFAULT_ACTOR}）")
    ap.add_argument("--wait", type=float, default=40.0,
                    help="等新 run 出现的秒数上限")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        print("[FATAL] 没有 GITHUB_TOKEN——这条自检要的就是「工作流自带的那个 "
              "token 点不点得动 Pages」，没有它什么都证明不了。"
              "工作流里加 `env: GITHUB_TOKEN: ${{ github.token }}`。")
        return 1
    repo = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")

    before = pages_runs(token, repo, per_page=10)
    if before is None:
        print(f"[FATAL] 读不到 {_PAGES_WORKFLOW} 的运行列表——"
              "工作流要有 `permissions: actions: write`（它含读）。")
        return 1
    known = {rid for rid, _, _ in before}
    newest = f"，最新 run {before[0][0]} actor={before[0][1]}" if before else ""
    print(f"点之前 {_PAGES_WORKFLOW} 已有 {len(known)} 条运行记录{newest}")

    # 这一句就是被验的东西。返回值只打印，不作为判据。
    said_ok = trigger_pages_build()
    print(f"trigger_pages_build() 自报：{said_ok}")

    deadline = time.monotonic() + args.wait
    fresh: tuple[int, str, str] | None = None
    while fresh is None:
        for run in pages_runs(token, repo, per_page=10) or []:
            if run[0] not in known:
                fresh = run
                break
        if fresh is not None or time.monotonic() >= deadline:
            break
        time.sleep(2.0)

    if fresh is None:
        print(f"[FATAL] {args.wait:.0f} 秒内没有出现新的运行记录。"
              "dispatch 的 204 只保证请求被收下，不保证它跑起来——"
              f"确认 `{_PAGES_WORKFLOW}` 在默认分支上、没有被停用。")
        return 1

    rid, actor, event = fresh
    print(f"新运行记录：run {rid}  actor={actor}  event={event}")
    print(f"  https://github.com/{repo}/actions/runs/{rid}")

    ok = True
    if event != "workflow_dispatch":
        print(f"[FATAL] event 是 {event}，不是 workflow_dispatch——"
              "这条新记录多半是别的东西触发的，不能算作判据。")
        ok = False
    if actor != args.expect_actor:
        print(f"[FATAL] actor 是 {actor}，不是 {args.expect_actor}。"
              "本地拿 PAT 跑会是你自己的名字，那证明不了工作流那条路。")
        ok = False
    if not said_ok:
        # 反过来的一头：产物出现了，函数却说失败。同样是 bug，只是方向相反。
        print("[FATAL] run 真的出现了，但 trigger_pages_build() 报了 False——"
              "它的确认逻辑比实际情况悲观，会让日志说谎。")
        ok = False

    print("✅ Pages 点得动，而且是这段代码点的" if ok else "❌ 不合格，见上面")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
