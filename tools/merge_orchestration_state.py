#!/usr/bin/env python3
"""三方合并 orchestration_state.json——orchestrate.yml 的 state 推送重试用。

来路（2026-08-26 run #360）：orchestrate 点完 run 提交 state，push 被拒后拿
`git pull --rebase` 重试——而冲突就发生在 state 这个文件本身（另一方是
match-reel 的失败自愈 `release_orchestration_claim`，或相邻的 orchestrate
班次）。**rebase 对同一个 JSON 的内容冲突无解**：abort 之后什么都没变，
重试只会撞同一个冲突，五次全撞、state 丢失、下一班重复 dispatch。

所以换成 JSON 级的三方合并（和 match-reel 释放 claim 用的「重取远端、
在最新之上重放修改」是同一个思路，只是这边的「修改」要算出来）：

- result = theirs（远端最新）为底
- ours − base（本趟真正新增/改写的条目）逐个加回——run 已经点出去了，不能丢
- **不做裸 union**：远端刚 release 的 claim（theirs 里没有、base/ours 里有、
  而本趟没碰它）必须保持消失——union 会把它复活，那条失败的 probe 就
  永远不重试了
- 本趟的删除（load_state 的 TTL 清理）**不带过去**：远端要是还留着过期
  条目，下一趟 load_state 照样清，晚一轮无所谓；把删除混进合并只会把
  「谁删的、为什么删」搅浑
- `last_dispatch_at` 取两边较大的（都是 UTC ISO 串，字典序就是时间序）
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

EMPTY: dict = {"dispatched": {}}


def _load(path: Path) -> dict:
    """读一份 state；文件不在/空/坏 JSON 一律按空 state 处置——
    这个工具跑在 push 重试的路上，抛异常等于把重试整个带崩。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(EMPTY)
    if not isinstance(data, dict):
        return dict(EMPTY)
    return data


def merge_states(base: dict, ours: dict, theirs: dict) -> dict:
    merged = json.loads(json.dumps(theirs))
    if not isinstance(merged, dict):
        merged = dict(EMPTY)
    dispatched = merged.setdefault("dispatched", {})
    base_d = base.get("dispatched") or {}
    ours_d = ours.get("dispatched") or {}
    for slug, entry in ours_d.items():
        if base_d.get(slug) != entry:
            # 本趟新增或改写的条目：run 已经点出去了，必须落库
            dispatched[slug] = entry
    # `blocked`（被别人的 probe 挡下、缓存着探到的源片）：本趟新挡下的加回（丢了只是
    # 下一班多探一次，但没理由丢）；**本趟摘掉的也带过去**——和上面「本趟的删除不带过去」
    # 反着，因为这一栏的删除有意思：挡它的没了、这一班照常点了（`drop_already_probed`／
    # `mark_dispatched` 摘的）。不带的话远端那条留到 STATE_TTL_DAYS，「复查」那一行天天
    # 印一个早就点出去的 slug。远端自己改过那一条（theirs ≠ base）就听远端的
    base_b = base.get("blocked") or {}
    ours_b = ours.get("blocked") or {}
    theirs_b = theirs.get("blocked") or {}
    for slug, entry in ours_b.items():
        if base_b.get(slug) != entry:
            merged.setdefault("blocked", {})[slug] = entry
    for slug, entry in base_b.items():
        if slug not in ours_b and theirs_b.get(slug) == entry:
            (merged.get("blocked") or {}).pop(slug, None)
    stamps = [s for s in (ours.get("last_dispatch_at"),
                          merged.get("last_dispatch_at")) if s]
    if stamps:
        merged["last_dispatch_at"] = max(stamps)
    return merged


def merge_interview_states(base: dict, ours: dict, theirs: dict) -> dict:
    """重放本次采访派发；时间和 spec 指纹作为一个记录，不拆开合并。"""
    merged = json.loads(json.dumps(theirs))
    slugs = set(theirs.get("slugs", []))
    def record(state, slug):
        return (slug in state.get("slugs", []),
                state.get("at", {}).get(slug),
                state.get("spec_sha256", {}).get(slug))
    for slug in ours.get("slugs", []):
        current = record(ours, slug)
        if current == record(base, slug):
            continue
        remote = record(theirs, slug)
        # 时间均由 mark_one 写为 UTC ISO；相同时间优先远端，避免旧任务盖新任务。
        if remote[0] and (remote[1] or "") >= (current[1] or ""):
            continue
        slugs.add(slug)
        for key, value in zip(("at", "spec_sha256"), current[1:]):
            target = merged.setdefault(key, {})
            if value is None:
                target.pop(slug, None)
            else:
                target[slug] = value
    merged["slugs"] = sorted(slugs)
    # 停车账（`pick_interview_renders.note_autopick_failure`，interview-clip 的 render 红在封面
    # 自动换帧时记）：本趟改过的条目加回去——不加的话 interview-clip 记账撞上 auto-render 的
    # dispatch 提交，重放以远端为底，这一笔就丢了，停车永远攒不满（D2）。两边都改过同一条
    # 取 `at` 晚的那一份（同一个 slug 的 render 按 concurrency 串行，晚的就是后记的）。
    base_f = base.get("autopick_failed") or {}
    theirs_f = theirs.get("autopick_failed") or {}
    for slug, entry in (ours.get("autopick_failed") or {}).items():
        if base_f.get(slug) == entry:
            continue
        remote = theirs_f.get(slug)
        if (isinstance(remote, dict) and remote != base_f.get(slug) and isinstance(entry, dict)
                and str(remote.get("at") or "") > str(entry.get("at") or "")):
            continue
        merged.setdefault("autopick_failed", {})[slug] = entry
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base", type=Path, required=True,
                        help="本趟开跑时 HEAD 上的那份 state")
    parser.add_argument("--ours", type=Path, required=True,
                        help="本趟写出的 state（含刚 dispatch 的条目）")
    parser.add_argument("--theirs", type=Path, required=True,
                        help="远端最新的 state（FETCH_HEAD 上那份）")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--kind", choices=("orchestration", "interview"),
                        default="orchestration")
    args = parser.parse_args()
    if args.kind == "interview":
        # 账本损坏不能静默当空并覆盖远端，失败时保留快照供恢复。
        snapshots = [json.loads(p.read_text(encoding="utf-8"))
                     for p in (args.base, args.ours, args.theirs)]
        for state in snapshots:
            if (not isinstance(state, dict)
                    or not isinstance(state.get("slugs", []), list)
                    or not isinstance(state.get("at", {}), dict)
                    or not isinstance(state.get("spec_sha256", {}), dict)
                    or not isinstance(state.get("autopick_failed", {}), dict)):
                raise ValueError("Invalid interview dispatch state")
        merged = merge_interview_states(*snapshots)
    else:
        merged = merge_states(_load(args.base), _load(args.ours),
                              _load(args.theirs))
    args.out.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    entries_key = "slugs" if args.kind == "interview" else "dispatched"
    added = sorted(set((merged.get(entries_key) or {}))
                   - set((_load(args.theirs).get(entries_key) or {})))
    print(f"[merge] 以远端为底，补回本趟条目：{added or '（无新增）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
