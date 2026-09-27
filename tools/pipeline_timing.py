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

SCHEMA_VERSION = 2

# ⭐⭐ **墙钟 vs 并行累加**（2026-09-27，schema 1 → 2）。
#
# `分段编码` 那一步是 4 个 worker 的线程池（`build_match_reel.render`），而
# 原来 `stage("分段编码")` 包的是**每一段**——台账里记下的是 13 段各自耗时的
# **总和**，不是这一步占掉的墙钟。于是报表把它排成「最慢的一步」：最近 40 条
# 成功的 `timing.json`（09-27 量）占整趟墙钟的份额 分段编码 63.3% ＋ 烧字幕
# 52.0% ＋ 拼接 15.1%，**加起来超过 100%**。拿 14 份 stage 齐全的成功 render
# 日志（09-22 之后）按 `[耗时]` 时间戳重建墙钟：烧字幕＋成片 **51%**（中位
# 120s）、分段编码墙钟 **18%**（中位 42s，累加却是 150s）、拼接 14%、
# **没有任何 stage 包着的一段 8%**（中位 20s，最长 40s——比分板蒙版那次
# 逐段扫描，`resolve_*_masks` 一直没计时；run 36284220097 里 TTS 之后到封面
# 之间 29 秒一行 `[耗时]` 都没有）。照旧报表去优化的人会去砍一个只占 18% 的
# 东西，而真正的大头和那段看不见的时间都不在榜上。
#
# 所以现在两件事分开记：
# - 名字里带 `PARALLEL_MARK` 的 stage 是**多个 worker 的累加**（每一段各记一行，
#   留着按「第几段特别慢」查），**不进墙钟合计、不进「哪一步最慢」**；
#   它外面另有一个同名不带记号的 stage 记这一步的**墙钟**；
# - `untimed_seconds` ＝ 整趟墙钟 − 各墙钟 stage 之和：没被 stage 包住的时间
#   从此在报表里有名有姓，下一次再有人漏包一段扫描，它会自己冒出来。
PARALLEL_MARK = "·并行"

#: 报表里「没被任何 stage 包住的时间」那一行的名字
UNTIMED = "（未计时：没有 stage 包着）"

# schema 1 的台账里，`分段编码` 就是上面说的那个累加（那时还没有墙钟那一行）。
# **只许减不许加**：新的并行 stage 一律带 `PARALLEL_MARK`，别往这张表里塞。
_LEGACY_PARALLEL_STAGES = frozenset({"分段编码"})


def is_parallel_stage(name: str, schema: int = SCHEMA_VERSION) -> bool:
    """这一行记的是多个 worker 的累加（不是墙钟）吗。"""
    if PARALLEL_MARK in name:
        return True
    return schema < 2 and name in _LEGACY_PARALLEL_STAGES


def split_stages(stage_seconds: dict[str, float], schema: int = SCHEMA_VERSION
                 ) -> tuple[dict[str, float], dict[str, float]]:
    """拆成 (墙钟那些, 并行累加那些)。"""
    wall: dict[str, float] = {}
    parallel: dict[str, float] = {}
    for name, spent in stage_seconds.items():
        (parallel if is_parallel_stage(name, schema) else wall)[name] = float(spent)
    return wall, parallel


def stage_table(stages: list[tuple[str, float]]) -> str:
    """`build_match_reel.report_timings()` 打的那张表。**份额按墙钟算**，
    并行累加单列在后面、不进合计——原来一起算，四个 worker 的累加能把一步
    撑到 60% 以上，整张表加起来超过 100%。"""
    buckets: dict[str, tuple[int, float]] = {}
    for name, spent in stages:
        key = str(name).split("#")[0].strip()
        count, acc = buckets.get(key, (0, 0.0))
        buckets[key] = (count + 1, acc + float(spent))
    wall = {k: v for k, v in buckets.items() if not is_parallel_stage(k)}
    parallel = {k: v for k, v in buckets.items() if is_parallel_stage(k)}
    total = sum(acc for _, acc in wall.values())
    lines = [f"=== 耗时明细（墙钟合计 {total:.1f}s，{os.cpu_count()} 核）==="]
    for key, (count, acc) in sorted(wall.items(), key=lambda kv: -kv[1][1]):
        share = acc / total * 100 if total else 0
        times = f" ×{count}" if count > 1 else ""
        lines.append(f"  {acc:7.1f}s  {share:5.1f}%  {key}{times}")
    for key, (count, acc) in sorted(parallel.items(), key=lambda kv: -kv[1][1]):
        lines.append(f"  {acc:7.1f}s  （并行累加 ×{count}，已含在上面的墙钟里，不计份额）"
                     f"  {key}")
    return "\n".join(lines)


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
    stage_seconds = {k: round(sum(v), 3) for k, v in merged.items()}
    wall, _parallel = split_stages(stage_seconds)
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
        "stage_seconds": stage_seconds,
        "stage_counts": {k: len(v) for k, v in merged.items()},
        # 哪几行是并行累加（不是墙钟）——读台账的人不用背这条约定
        "parallel_stages": sorted(k for k in stage_seconds if is_parallel_stage(k)),
        # 没被任何 stage 包住的墙钟：漏计时的那一段在这儿现形
        "untimed_seconds": round(max(0.0, float(elapsed_seconds) - sum(wall.values())), 3),
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

    # 哪一步最慢：只拿成功那些趟算，失败那趟是半截的，混进来会把中位数拉偏。
    # **只排墙钟**——并行累加不是这一步占掉的时间，排进来会把优化引到错的地方
    # （见 `PARALLEL_MARK` 那段）；没被 stage 包住的那段以「（未计时）」上榜。
    if ok:
        per_stage: dict[str, list[float]] = {}
        per_parallel: dict[str, list[float]] = {}
        for row in ok:
            wall, parallel = split_stages(row.get("stage_seconds") or {},
                                          int(row.get("schema") or 1))
            for name, spent in wall.items():
                per_stage.setdefault(name, []).append(spent)
            for name, spent in parallel.items():
                per_parallel.setdefault(name, []).append(spent)
            if row.get("untimed_seconds") is not None:
                per_stage.setdefault(UNTIMED, []).append(float(row["untimed_seconds"]))
        if per_stage:
            lines.append("\n哪一步最慢（只算成功的趟，墙钟中位）：")
            ranked = sorted(per_stage.items(),
                            key=lambda kv: -_median(kv[1]))[:8]
            for name, values in ranked:
                lines.append(f"  {_median(values):7.1f}s  ×{len(values):<3d} {name}")
        if per_parallel:
            lines.append("\n并行累加（几个 worker 同时跑的总和，不是墙钟——别拿它排优先级）：")
            for name, values in sorted(per_parallel.items(),
                                       key=lambda kv: -_median(kv[1])):
                lines.append(f"  {_median(values):7.1f}s  ×{len(values):<3d} {name}")
    return "\n".join(lines)


def main() -> int:
    print(summarize(harvest()))
    return 0


if __name__ == "__main__":                                   # pragma: no cover
    raise SystemExit(main())
