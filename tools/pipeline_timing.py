"""渲染耗时台账：**每一趟都记一行，不只记成功的那一趟。**

来路（2026-08-24 复盘）。这条线本来就有两样计时，而**两样都只在成功那一趟
才落地**：

- `build_match_reel.stage()` 按步记时、末尾 `report_timings()` 打一张表——
  可它是 `render()` 的最后一行，中途抛异常就永远走不到，**失败那一趟的耗时
  明细直接丢掉**，而那正是最想知道「跑到哪一步、花在哪儿」的时候；
- `video_sla.py` 算一个 `production_sla` 塞进 `render.json`，而 `render.json`
  是**渲成了才写的**。

于是 `pipeline_health.sla_health()` 的样本天生只有成功那一半。2026-08-24
当天实测：`output/2026-08-24/reel/` 下 4 份 `render.json` **全是 `met: true`**，
中位 346s，报表一片绿——而同一天 `match-reel` 真实跑了二十多趟：
`gauff-pegula-cincinnati-2026-final` 渲了三趟（两趟白烧）、
`zheng-us-open-outlook` 从早到晚渲推了五轮。**报表是绿的，账不是。**

这正是本仓库反复记的那个形状——「只在成功时出声的检查，没法证明它真的看过」。
所以这份台账的第一条规矩就是**失败也要留下一行**，而且要记清楚
「跑到哪一步」：一趟死在「下载源片」和一趟死在「成片编码」，浪费的机器时间
差一个量级，混在一起统计什么都看不出来。

⚠️ **这是仪器，不是闸。** 写台账失败**永远不许**把一趟渲染带崩——出声，然后
继续。一个会让生产失败的埋点，下一个人一定会把它拆掉。
"""

from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path

# 和 `render.json` 并排放在 outdir 里。成功那一趟工作流本来就 `git add "$OUTDIR"`，
# 所以**不额外多一次提交**（每趟渲染都单独 commit 一次会给 main 制造提交噪音，
# 还会连带触发一堆 CI）。失败那一趟 outdir 不进仓库，但 `actions/upload-artifact`
# 是 `if: always()` 的，这一行仍然躺在构件里，要查的时候下得到。
TIMING_NAME = "timing.json"

SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_record(*, pipeline: str, slug: str, mode: str, outcome: str,
                 stages: list[tuple[str, float]], elapsed_seconds: float,
                 error: str | None = None) -> dict:
    """把一趟的耗时攒成一行。**纯函数**，不碰磁盘——好测。

    `stages` 直接收 `build_match_reel._TIMINGS`（`[(名字, 秒), …]`）。同名的
    步骤（每段切片这种）在这儿**不合并**：合并是报表那一层的事，台账要留原始
    粒度，不然以后想按「第几段特别慢」查就查不了了。
    """
    merged: dict[str, list[float]] = {}
    for name, spent in stages:
        merged.setdefault(str(name).split("#")[0].strip(), []).append(float(spent))
    return {
        "schema": SCHEMA_VERSION,
        "at": _utc_now(),
        "pipeline": pipeline,
        "slug": slug,
        "mode": mode,
        "outcome": outcome,
        "error": error,
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        # **最后一步走到哪儿** —— 失败那一趟全靠它定位「死在哪」。
        "last_stage": stages[-1][0] if stages else None,
        "stage_seconds": {k: round(sum(v), 3) for k, v in merged.items()},
        "stage_counts": {k: len(v) for k, v in merged.items()},
        # 机器和运行环境：跨趟比耗时之前先看看是不是同一档机器
        "cpu_count": os.cpu_count(),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "on_runner": bool(os.environ.get("GITHUB_ACTIONS")),
    }


def write(outdir: Path, record: dict) -> Path | None:
    """落盘。**写不进去只出声，不抛**——见模块 docstring 最后那条。"""
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        path = outdir / TIMING_NAME
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path
    except OSError as exc:                                   # pragma: no cover
        print(f"[耗时台账] 写不进去（{exc}）——只影响统计，不影响这条片子")
        return None


def harvest(root: Path | str = "output") -> list[dict]:
    """把仓库里所有 `timing.json` 收上来。坏行跳过并出声，不整个崩。"""
    rows: list[dict] = []
    for path in sorted(Path(root).glob(f"*/*/*/{TIMING_NAME}")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            print(f"[耗时台账] 读不动 {path}（{exc}），跳过")
    return rows


def summarize(rows: list[dict]) -> str:
    """跨趟统计。**报表要把失败那半边也列出来**——那是这份台账存在的理由。"""
    if not rows:
        return ("[耗时台账] 一行都没有。\n"
                "⚠️ 这不等于「没有渲过」——这份台账 2026-08-24 才立，"
                "在那之前的成片都没有这一行；而失败那一趟的记录只在 Actions "
                "构件里，没有进仓库。")
    lines = [f"=== 渲染耗时台账（{len(rows)} 趟）==="]

    ok = [r for r in rows if r.get("outcome") == "success"]
    bad = [r for r in rows if r.get("outcome") != "success"]
    lines.append(f"成功 {len(ok)} 趟，失败 {len(bad)} 趟")

    def _median(values: list[float]) -> float:
        return statistics.median(values) if values else 0.0

    if ok:
        spent = [float(r.get("elapsed_seconds") or 0) for r in ok]
        lines.append(f"成功那些趟：中位 {_median(spent):.0f}s，"
                     f"最慢 {max(spent):.0f}s")

    # **一条片子渲了几趟才成**——今天真正贵的就是这个数，不是单趟多快
    by_slug: dict[str, list[dict]] = {}
    for row in rows:
        by_slug.setdefault(str(row.get("slug") or "?"), []).append(row)
    retried = {k: v for k, v in by_slug.items() if len(v) > 1}
    if retried:
        lines.append("\n渲了不止一趟的：")
        for slug, attempts in sorted(retried.items(),
                                     key=lambda kv: -len(kv[1])):
            wasted = sum(float(a.get("elapsed_seconds") or 0)
                         for a in attempts if a.get("outcome") != "success")
            lines.append(f"  {slug}：{len(attempts)} 趟，"
                         f"白烧 {wasted / 60:.1f} 分钟")

    if bad:
        lines.append("\n失败死在哪一步：")
        died: dict[str, int] = {}
        for row in bad:
            died[str(row.get("last_stage") or "还没进第一步")] = \
                died.get(str(row.get("last_stage") or "还没进第一步"), 0) + 1
        for name, count in sorted(died.items(), key=lambda kv: -kv[1]):
            lines.append(f"  ×{count}  {name}")

    # 哪一步最慢：只拿成功那些趟算，失败那趟是半截的，混进来会把中位数拉偏
    if ok:
        per_stage: dict[str, list[float]] = {}
        for row in ok:
            for name, spent in (row.get("stage_seconds") or {}).items():
                per_stage.setdefault(name, []).append(float(spent))
        if per_stage:
            lines.append("\n哪一步最慢（只算成功的趟，中位）：")
            ranked = sorted(per_stage.items(),
                            key=lambda kv: -_median(kv[1]))[:8]
            for name, values in ranked:
                lines.append(f"  {_median(values):7.1f}s  ×{len(values):<3d} {name}")
    return "\n".join(lines)


def main() -> int:
    print(summarize(harvest()))
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
