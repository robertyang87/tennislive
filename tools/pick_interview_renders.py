#!/usr/bin/env python3
"""扫 `specs/interviews/*.json`（正式 spec）→ 挑出**能 render 而且还没 dispatch**的 slug。

这是 interview-auto-render 的最后一环：把「提升成正式 spec 的采访」转成
`interview-clip.yml` 的 dispatch 列表。每 slug 一个 run，interview-clip 的
concurrency 按 slug 分组 → 不同采访天然并行。

⚠️ **只放行生产契约完整的 spec。** render 那头有来源、字幕和内容完整性闸
（opening / transcript_verified / takeaway，见 `build_interview_clip.main`），
字段不全的 spec dispatch 出去**必死在闸上**——而 2026-08-21 之前这里不查，
`swiatek-shnaider-tor2026-qf`（一个只有骨架的 spec）就这么被 dispatch、
永久记进了「已 dispatch」状态：**死在闸上的 run 不产 render.json，于是它
既不算「已 render」、又因为记了状态永远不会再被投**，整条卡死且不吭声。
所以判定和闸**用同一张豁免表**（从 `build_interview_clip` import，
不抄第二份——写两处必分叉）；不齐的列成「等自动补齐 / 例外复核」打到 stderr，
让每一趟 run 的日志都看得见还有谁在等。

已 dispatch 过的记在 `data/interview_render_dispatched.json`：
`slugs` 是名单，`at` 记每条是什么时候投的——**投一条记一条**
（`--mark-one`，dispatch 成功之后才记），不是先记后投：先记后投的下场是
dispatch 失败的那条从此再也不会被投，而且不吭声。
`--stale` 拿 `at` 反查「投出去超过 N 小时还没有 render.json」的条目；这些
条目同时会自动释放回 dispatch 队列，下一次成功 dispatch 刷新时刻——
「投了」只是信号，render.json 落库才是产物。

用法：
    python tools/pick_interview_renders.py               # 打印待 dispatch 的
    python tools/pick_interview_renders.py --mark-one X  # X dispatch 成功后记一笔
    python tools/pick_interview_renders.py --stale       # 投了很久没产物的（查产物）

stdout 协议（workflow 靠它切）：第一行是给人看的题头，**第二行起每行一个
待 dispatch 的 slug**；「等自动补齐 / 例外复核」走 stderr，不混进这份名单。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# 三道编辑闸的豁免表从闸自己那儿 import（`build_interview_clip` 顶层只 import
# 标准库，system python 就能跑——interview-auto-render 的「没活就早退」靠这个，
# 别往那个模块顶层加第三方 import）。
from build_interview_clip import (  # noqa: E402
    _LEGACY_NO_OPENING,
    _NO_TAKEAWAY_LEGACY,
    check_lead_in,
)
from interview_source_gate import SourceContractError, validate_source_contract  # noqa: E402

SPECS = ROOT / "specs" / "interviews"
STATE = ROOT / "data" / "interview_render_dispatched.json"

# 「投出去多久没 render.json 才算可疑」。一趟 render 约 9 分钟、排队和重试
# 撑死几十分钟——3 小时还没有产物，几乎一定是 run 挂了或死在编辑闸上。
STALE_HOURS = 3


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


def missing_for_render(slug: str, spec: dict) -> list[str]:
    """render 的三道编辑闸 + 推送要的文案，这条 spec 还缺哪几样。

    **判定必须和闸同一个口径**（含豁免表）：这儿判「齐了」而闸判「不齐」，
    dispatch 出去就是白烧一趟 runner 再永久卡死；反过来（这儿更严）会把
    豁免过的老 spec 拦在门外。
    """
    missing: list[str] = []
    try:
        validate_source_contract(spec)
    except SourceContractError as exc:
        missing.append(f"L0 本场场上采访身份（{exc}）")
    if not spec.get("opening") and slug not in _LEGACY_NO_OPENING:
        missing.append("opening（开场认领，check_opening 那道闸）")
    if not spec.get("zh"):
        # zh 空时 `build_interview_clip.main` 打印一份英文行就 return 0——
        # 不渲、不报错、不产 render.json，dispatch 出去就是一趟静默的空跑
        missing.append("zh（中文字幕还没填）")
    if spec.get("transcript_verified") is not True and \
            spec.get("transcript_verification") != "auto_pending":
        missing.append("transcript_verified / auto_pending（转写没有核验路径）")
    if not spec.get("takeaway") and slug not in _NO_TAKEAWAY_LEGACY:
        missing.append("takeaway（收尾解读卡）")
    if not spec.get("cover"):
        missing.append("cover（封面）")
    if not (SPECS / f"{slug}.xhs.txt").is_file():
        missing.append("xhs.txt（推送文案）")
    # 独立场上采访必须配同场获胜画面和解说。复用 render 的同一条闸，不在
    # 调度器里另抄一份字段判断；否则两处迟早分叉。
    try:
        check_lead_in(spec)
    except SystemExit as exc:
        missing.append(f"lead_in（{str(exc).splitlines()[0]}）")
    return missing


def _load_state() -> dict:
    if not STATE.is_file():
        return {"slugs": [], "at": {}}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"slugs": [], "at": {}}
    data.setdefault("slugs", [])
    data.setdefault("at", {})
    return data


def _fresh_dispatches(*, now: datetime, rendered: set[str]) -> set[str]:
    """已经 dispatch 且还在合理运行窗口内的 slug；过期的自动释放重试。"""
    state = _load_state()
    fresh: set[str] = set()
    for slug in state.get("slugs", []):
        if slug in rendered:
            continue
        raw = state.get("at", {}).get(slug, "")
        try:
            at = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if now - at < timedelta(hours=STALE_HOURS):
            fresh.add(slug)
    return fresh


def todo_slugs(*, now: datetime | None = None) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """→ (该 dispatch 的, [(还差自动补齐/复核的 slug, 缺什么)])。

    两份都不含「已 render」和「最近刚 dispatch」的。dispatch 超过 3 小时仍无
    render.json 的自动释放回 ready；再次 mark 会刷新时刻，实现环境抖动自愈。
    """
    rendered = _rendered_slugs()
    blocked = rendered | _fresh_dispatches(
        now=now or datetime.now(timezone.utc), rendered=rendered)
    ready: list[str] = []
    waiting: list[tuple[str, list[str]]] = []
    for p in sorted(SPECS.glob("*.json")):
        if p.name.endswith(".draft.json") or p.stem in blocked:
            continue
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            waiting.append((p.stem, ["spec 读不了（JSON 坏了）"]))
            continue
        missing = missing_for_render(p.stem, spec)
        if missing:
            waiting.append((p.stem, missing))
        else:
            ready.append(p.stem)
    return ready, waiting


def mark_one(slug: str, *, now: str = "") -> None:
    """X dispatch **成功之后**记一笔。先投后记，顺序不许反：
    先记后投的话，dispatch 失败的那条从此再也不会被投，而且不吭声。"""
    state = _load_state()
    if slug not in state["slugs"]:
        state["slugs"] = sorted({*state["slugs"], slug})
    state["at"][slug] = now or datetime.now(timezone.utc).strftime("%FT%TZ")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def stale_dispatches(*, now: datetime | None = None) -> list[tuple[str, str]]:
    """投出去超过 `STALE_HOURS` 还没有 render.json 的 → [(slug, 投出时刻)]。

    「投了」只是信号，render.json 才是产物——run 可以死在编辑闸上、被
    concurrency 顶掉、或者干脆没跑起来，而这些在状态文件上长得和「正在渲」
    一模一样。⚠️ 老状态里没有 `at` 的条目（bulk --mark 时代记的）查不了
    时刻，一律算 stale——它们至少投出去一整天了。
    """
    state = _load_state()
    rendered = _rendered_slugs()
    now = now or datetime.now(timezone.utc)
    out: list[tuple[str, str]] = []
    for slug in state.get("slugs", []):
        if slug in rendered:
            continue
        at_raw = state.get("at", {}).get(slug, "")
        if at_raw:
            try:
                at = datetime.strptime(at_raw, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
            except ValueError:
                at = None
            if at is not None and now - at < timedelta(hours=STALE_HOURS):
                continue
        out.append((slug, at_raw or "时刻没记（老状态）"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mark-one", default="",
                    help="这条 slug dispatch 成功了，记进状态（投一条记一条）")
    ap.add_argument("--stale", action="store_true",
                    help="列出投了超过 %d 小时还没有 render.json 的" % STALE_HOURS)
    args = ap.parse_args()

    if args.mark_one:
        mark_one(args.mark_one)
        print(f"已记：{args.mark_one}")
        return 0

    if args.stale:
        stale = stale_dispatches()
        print(f"投出去超过 {STALE_HOURS} 小时还没有 render.json 的：{len(stale)} 条")
        for slug, at in stale:
            print(f"  {slug}（投于 {at}）——去查那趟 interview-clip run 的日志，"
                  "或人工重新 dispatch")
        return 0

    ready, waiting = todo_slugs()
    print(f"待 dispatch {len(ready)} 条：")
    for s in ready:
        print(s)
    # 等自动补齐/例外复核的走 stderr：stdout 第二行起是给 workflow 切的名单，混进去就会把
    # 一条不齐的 spec dispatch 出去——正是这次要修的那个卡死
    if waiting:
        print(f"[等自动补齐 / 例外复核] {len(waiting)} 条（不 dispatch）：", file=sys.stderr)
        for slug, missing in waiting:
            print(f"  {slug}：缺 {'、'.join(missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
