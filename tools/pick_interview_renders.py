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
`slugs` 是名单，`at` 记每条是什么时候投的，`spec_sha256` 记这趟实际投的
输入指纹——**投一条记一条**
（`--mark-one`，dispatch 成功之后才记），不是先记后投：先记后投的下场是
dispatch 失败的那条从此再也不会被投，而且不吭声。
`--stale` 拿 `at` 反查「投出去超过 N 分钟还没有当前输入的成片」的条目；这些
条目同时会自动释放回 dispatch 队列，下一次成功 dispatch 刷新时刻——
「投了」只是信号，render.json 落库才是产物。

⚠️ **render.json 存在不等于当前 spec 已经出片。** 同一个 slug 修字幕、封面或
空档销账后，旧逻辑只看目录里有没有 render.json，于是 workflow 绿着早退，
新 spec 永远不会重渲。现在有 QC 的新产物必须满足
`qc_attestation.spec_sha256 == 当前 spec sha256` 才算已 render；历史产物没有
QC 的仍按已 render 兼容，避免上线时把几十条存量一起重跑。

用法：
    python tools/pick_interview_renders.py               # 打印待 dispatch 的
    python tools/pick_interview_renders.py --mark-one X  # X dispatch 成功后记一笔
    python tools/pick_interview_renders.py --stale       # 投了很久没产物的（查产物）

stdout 协议（workflow 靠它切）：第一行是给人看的题头，**第二行起每行一个
待 dispatch 的 slug**；「等自动补齐 / 例外复核」走 stderr，不混进这份名单。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
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
OUTPUT = ROOT / "output" / "interviews"
LEGACY_INPUT_BASELINE = ROOT / "data" / "interview_render_legacy_baseline.json"

# 「投出去多久还没有当前输入的成片才自动释放」。普通采访约 9 分钟，今天这条
# 28 分钟完整致辞也在一小时内完成；固定 3 小时会让一次红灯拖掉半天。60 分钟
# 给长片留足预算。
# ⚠️ 必须**大于** interview-clip.yml 的 `timeout-minutes`（65）：那条工作流是
# `cancel-in-progress`，窗口比 job 超时短的话，一趟还在跑的长片会在第 60 分钟
# 被重投的那趟掐掉——同一个形状这文件头部记过一次（45 对 49）。
STALE_MINUTES = 70


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_bytes(path: Path) -> bytes | None:
    """读工作区或 HEAD 里的文件，兼容 workflow 的 sparse checkout。"""
    if path.is_file():
        return path.read_bytes()
    try:
        rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None
    proc = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"HEAD:{rel}"],
        capture_output=True, check=False, timeout=30,
    )
    return proc.stdout if proc.returncode == 0 else None


def _render_matches_current_spec(slug: str) -> bool:
    """有 QC 的产物必须绑定当前 spec；无 QC 的历史产物保守兼容。"""
    spec_path = SPECS / f"{slug}.json"
    if not spec_path.is_file():
        # 没有正式 spec 的旧产物不会进入 todo；这里保守视为已落地。
        return True
    qc_raw = _repo_bytes(OUTPUT / slug / "qc_attestation.json")
    if qc_raw is None:
        # 2026-08-15 之前的 58 条采访没有 QC。不能因为部署本规则就批量重渲。
        return True
    try:
        qc = json.loads(qc_raw)
    except (ValueError, UnicodeDecodeError):
        return False
    if not isinstance(qc, dict) or qc.get("status") != "pass":
        return False
    landed_sha = str(qc.get("spec_sha256") or "")
    current_sha = _sha256(spec_path)
    if landed_sha and landed_sha == current_sha:
        return True
    # 指纹规则上线前有极少数已发布产物在同一次旧工作流里“先写 QC、后补 spec
    # 运营字段”，导致两份 SHA 天生不同。部署新规则不能把这些旧消息重新推一遍。
    # 基线只豁免当时那一份明确 SHA；spec 再改一个字就立刻失效并重新渲染。
    try:
        baseline = json.loads(LEGACY_INPUT_BASELINE.read_text(encoding="utf-8"))
        row = (baseline.get("slugs") or {}).get(slug) or {}
    except (OSError, ValueError, AttributeError):
        row = {}
    return row.get("spec_sha256") == current_sha


def _current_rendered_slugs(rendered: set[str] | None = None) -> set[str]:
    rendered = _rendered_slugs() if rendered is None else rendered
    return {slug for slug in rendered if _render_matches_current_spec(slug)}


def _rendered_slugs() -> set[str]:
    """仓库里 `output/interviews/<slug>/render.json` 已存在的 slug（已 render 过）。

    用 `git ls-files` 从 index 读，**不受 sparse-checkout 影响**——workflow 的
    checkout 没拉 output/（1.36 GB），但 index 里全量文件都在。
    """
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
        return {"slugs": [], "at": {}, "spec_sha256": {}}
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"slugs": [], "at": {}, "spec_sha256": {}}
    data.setdefault("slugs", [])
    data.setdefault("at", {})
    data.setdefault("spec_sha256", {})
    if not isinstance(data["spec_sha256"], dict):
        data["spec_sha256"] = {}
    return data


def _fresh_dispatches(*, now: datetime, rendered: set[str],
                      changed_inputs: set[str] | None = None) -> set[str]:
    """同一份输入已 dispatch 且仍在合理窗口内的 slug。"""
    state = _load_state()
    changed_inputs = changed_inputs or set()
    fresh: set[str] = set()
    for slug in state.get("slugs", []):
        if slug in rendered:
            continue
        spec_path = SPECS / f"{slug}.json"
        current_sha = _sha256(spec_path) if spec_path.is_file() else ""
        dispatched_sha = str(state.get("spec_sha256", {}).get(slug) or "")
        if dispatched_sha and current_sha and dispatched_sha != current_sha:
            # 这条状态认领的是旧 spec，新输入不该被它再拦一个小时。
            continue
        if slug in changed_inputs and current_sha and not dispatched_sha:
            # 迁移前的状态没有输入指纹；QC 已明确证明产物绑定的是旧 spec，
            # 所以让证据胜过那个无指纹的“投过了”信号，立即恢复。
            continue
        raw = state.get("at", {}).get(slug, "")
        try:
            at = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        if now - at < timedelta(minutes=STALE_MINUTES):
            fresh.add(slug)
    return fresh


def todo_slugs(*, now: datetime | None = None) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """→ (该 dispatch 的, [(还差自动补齐/复核的 slug, 缺什么)])。

    两份都不含「已 render」和「最近刚 dispatch」的。dispatch 超过 STALE_MINUTES 仍无
    render.json 的自动释放回 ready；再次 mark 会刷新时刻，实现环境抖动自愈。
    """
    rendered = _rendered_slugs()
    current_rendered = _current_rendered_slugs(rendered)
    changed_inputs = rendered - current_rendered
    blocked = current_rendered | _fresh_dispatches(
        now=now or datetime.now(timezone.utc), rendered=current_rendered,
        changed_inputs=changed_inputs)
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
    spec_path = SPECS / f"{slug}.json"
    if spec_path.is_file():
        state["spec_sha256"][slug] = _sha256(spec_path)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")


def stale_dispatches(*, now: datetime | None = None) -> list[tuple[str, str]]:
    """投出去超过 `STALE_MINUTES` 还没有当前成片的 → [(slug, 投出时刻)]。

    「投了」只是信号，render.json 才是产物——run 可以死在编辑闸上、被
    concurrency 顶掉、或者干脆没跑起来，而这些在状态文件上长得和「正在渲」
    一模一样。⚠️ 老状态里没有 `at` 的条目（bulk --mark 时代记的）查不了
    时刻，一律算 stale——它们至少投出去一整天了。
    """
    state = _load_state()
    rendered = _current_rendered_slugs()
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
            if at is not None and now - at < timedelta(minutes=STALE_MINUTES):
                continue
        out.append((slug, at_raw or "时刻没记（老状态）"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mark-one", default="",
                    help="这条 slug dispatch 成功了，记进状态（投一条记一条）")
    ap.add_argument("--at", default="",
                    help="配合 --mark-one：写入这次 dispatch 的 UTC 时刻")
    ap.add_argument("--stale", action="store_true",
                    help="列出投了超过 %d 分钟还没有当前成片的" % STALE_MINUTES)
    args = ap.parse_args()

    if args.mark_one:
        mark_one(args.mark_one, now=args.at)
        print(f"已记：{args.mark_one}")
        return 0

    if args.stale:
        stale = stale_dispatches()
        print(f"投出去超过 {STALE_MINUTES} 分钟还没有当前成片的：{len(stale)} 条")
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
