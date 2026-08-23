#!/usr/bin/env python3
"""汇总关键 Actions 的近期成功率、耗时、慢步骤与 600 秒成片告警。

阈值异常只产生 warning/通知，不改变任何生产或发布资格；真正的发布资格仍由
L0/L2/L3 门禁决定。API 本身不可用则返回非零，因为“监控失明”和“系统健康”
不能长得一样。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_WORKFLOWS = (
    "oncourt-interviews.yml",
    "interview-auto-render.yml",
    "interview-clip.yml",
    "match-reel.yml",
    "auto-push-interview.yml",
    "auto-push-reel.yml",
    "auto-push-explainer.yml",
)


def instant(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def elapsed(start: str | None, end: str | None) -> float | None:
    a, b = instant(start), instant(end)
    return (b - a).total_seconds() if a and b else None


class GitHubAPI:
    def __init__(self, repo: str, token: str, opener=urllib.request.urlopen):
        self.repo, self.token, self.opener = repo, token, opener

    def get(self, path: str) -> dict:
        url = f"https://api.github.com/repos/{self.repo}/{path.lstrip('/')}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tennislive-pipeline-health",
        })
        try:
            with self.opener(req, timeout=30) as response:
                return json.load(response)
        except (urllib.error.URLError, ValueError) as exc:
            raise RuntimeError(f"GitHub API 读取失败：{url}（{exc}）") from exc


@dataclass
class WorkflowHealth:
    name: str
    runs: int
    successes: int
    failures: int
    median_seconds: float
    consecutive_failures: int
    latest_failure_recent: bool = False

    @property
    def failure_rate(self) -> float:
        return self.failures / self.runs if self.runs else 0.0


def workflow_health(api: GitHubAPI, workflow: str, limit: int,
                    step_runs: int) -> tuple[WorkflowHealth, list[dict]]:
    encoded = urllib.parse.quote(workflow, safe="")
    payload = api.get(
        f"actions/workflows/{encoded}/runs?status=completed&per_page={limit}")
    runs = (payload.get("workflow_runs") or [])[:limit]
    durations = [v for row in runs
                 if (v := elapsed(row.get("created_at"), row.get("updated_at"))) is not None]
    conclusions = [str(row.get("conclusion") or "") for row in runs]
    bad = [c for c in conclusions if c not in {"success", "skipped", "neutral"}]
    streak = 0
    for conclusion in conclusions:
        if conclusion in {"success", "skipped", "neutral"}:
            break
        streak += 1
    latest_age = (elapsed(runs[0].get("updated_at"),
                          datetime.now(timezone.utc).isoformat())
                  if runs else None)
    health = WorkflowHealth(
        name=workflow, runs=len(runs),
        successes=sum(c == "success" for c in conclusions), failures=len(bad),
        median_seconds=statistics.median(durations) if durations else 0.0,
        consecutive_failures=streak,
        # 健康检查每小时跑一次。只有“上一小时刚发生”的失败趋势发微信，
        # 同一批旧失败继续留在 summary，但不会每小时重复轰炸。
        latest_failure_recent=bool(
            runs and conclusions and conclusions[0] not in {"success", "skipped", "neutral"}
            and latest_age is not None and 0 <= latest_age <= 3600),
    )
    steps: list[dict] = []
    for run in runs[:step_runs]:
        jobs = api.get(f"actions/runs/{run['id']}/jobs?per_page=100").get("jobs") or []
        for job in jobs:
            for step in job.get("steps") or []:
                seconds = elapsed(step.get("started_at"), step.get("completed_at"))
                if seconds is not None:
                    steps.append({
                        "workflow": workflow, "run_id": run["id"],
                        "job": job.get("name", ""), "step": step.get("name", ""),
                        "seconds": seconds, "conclusion": step.get("conclusion", ""),
                    })
    return health, steps


def _tracked_jsons(pattern: str) -> list[dict]:
    proc = subprocess.run(["git", "ls-files", pattern], capture_output=True,
                          text=True, check=True)
    paths = [line for line in proc.stdout.splitlines() if line]
    missing = [rel for rel in paths if not Path(rel).is_file()]
    from_head: dict[str, bytes] = {}
    if missing:
        # 稀疏检出时可能有几百份 metadata 只在 index/HEAD。逐文件 git show 会
        # 启动几百个进程，健康检查自己就跑几十秒；cat-file --batch 一次读齐。
        batch = subprocess.Popen(
            ["git", "cat-file", "--batch"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        assert batch.stdin is not None and batch.stdout is not None
        batch.stdin.write("".join(f"HEAD:{rel}\n" for rel in missing).encode())
        batch.stdin.close()
        for rel in missing:
            header = batch.stdout.readline().decode("utf-8", "replace").strip()
            fields = header.rsplit(" ", 2)
            if len(fields) != 3 or not fields[2].isdigit():
                continue
            size = int(fields[2])
            from_head[rel] = batch.stdout.read(size)
            batch.stdout.read(1)  # batch 在每个对象后补一个换行
        batch.wait(timeout=30)
    rows: list[dict] = []
    for rel in paths:
        path = Path(rel)
        try:
            raw = path.read_bytes() if path.is_file() else from_head[rel]
            rows.append(json.loads(raw))
        except (OSError, ValueError, KeyError):
            continue
    return rows


def sla_health(limit: int = 20) -> tuple[int, int, float]:
    rows = _tracked_jsons("output/**/render.json")
    slas = [row["production_sla"] for row in rows
            if isinstance(row.get("production_sla"), dict)]
    slas.sort(key=lambda row: str(row.get("artifact_ready_at") or ""), reverse=True)
    recent = slas[:limit]
    misses = sum(row.get("met") is False for row in recent)
    values = [float(row["elapsed_seconds"]) for row in recent
              if row.get("elapsed_seconds") is not None]
    return len(recent), misses, statistics.median(values) if values else 0.0


def stale_publications(now: datetime | None = None, hours: float = 1.5) -> list[str]:
    now = now or datetime.now(timezone.utc)
    stale: list[str] = []
    for directory in ("data/interview_publish_ledger", "data/reel_publish_ledger",
                      "data/explainer_publish_ledger"):
        for ledger in _tracked_jsons(f"{directory}/*.json"):
            slug = str(ledger.get("slug") or "unknown")
            for row in ledger.get("attempts") or []:
                at = instant(row.get("at"))
                age = (now - at).total_seconds() / 3600 if at else 0.0
                # 只在首次越过阈值后的一个小时窗口通知；更老的 sending 已经在
                # 首次窗口报过，避免永久悬挂的一条账本每小时重复推微信。
                if row.get("status") == "sending" and hours < age <= hours + 1:
                    stale.append(f"{directory}/{slug}: sending 已持续 {age:.1f}h")
    return stale


def render_report(health: list[WorkflowHealth], steps: list[dict],
                  sla: tuple[int, int, float], stale: list[str]) -> tuple[str, list[str]]:
    alerts: list[str] = []
    lines = ["## 自动视频流水线健康度", "", "| 工作流 | 样本 | 成功 | 失败率 | 中位耗时 | 连续失败 |",
             "|---|---:|---:|---:|---:|---:|"]
    for row in health:
        lines.append(f"| {row.name} | {row.runs} | {row.successes} | {row.failure_rate:.0%} | "
                     f"{row.median_seconds/60:.1f}m | {row.consecutive_failures} |")
        if (row.runs >= 3 and row.latest_failure_recent
                and (row.failure_rate >= .40 or row.consecutive_failures >= 3)):
            alerts.append(f"{row.name}：近 {row.runs} 次失败率 {row.failure_rate:.0%}，连续失败 {row.consecutive_failures}")
    n, misses, median = sla
    lines += ["", f"- 600 秒成片：最近 {n} 条中 {misses} 条超线，中位 {median:.0f}s。"
              "超线只告警，不阻断 L2、发布或微信推送。"]
    # SLA miss 只留 Actions warning/summary，不发微信：metadata 不变时每小时扫到
    # 的仍是同一批 miss，拿它做 PushPlus alert 会形成告警风暴。
    if stale:
        alerts.extend(stale)
        lines += ["", "### 发布账本待核实", *[f"- {item}" for item in stale]]
    slow = sorted(steps, key=lambda row: row["seconds"], reverse=True)[:10]
    lines += ["", "### 最近最慢步骤", "", "| 工作流 / job / step | 耗时 | 结果 |",
              "|---|---:|---|"]
    for row in slow:
        lines.append(f"| {row['workflow']} / {row['job']} / {row['step']} | "
                     f"{row['seconds']/60:.1f}m | {row['conclusion']} |")
    if alerts:
        lines += ["", "### ⚠️ 需要修复", *[f"- {item}" for item in alerts]]
    else:
        lines += ["", "- 当前没有达到告警阈值的趋势。"]
    return "\n".join(lines) + "\n", alerts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    ap.add_argument("--workflows", nargs="*", default=list(DEFAULT_WORKFLOWS))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--step-runs", type=int, default=3)
    ap.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    args = ap.parse_args(argv)
    if not args.repo or not args.token:
        raise SystemExit("需要 --repo/GITHUB_REPOSITORY 与 --token/GITHUB_TOKEN")
    api = GitHubAPI(args.repo, args.token)
    health, steps = [], []
    for workflow in args.workflows:
        row, these_steps = workflow_health(api, workflow, args.limit, args.step_runs)
        health.append(row); steps.extend(these_steps)
    sla = sla_health()
    report, alerts = render_report(health, steps, sla, stale_publications())
    print(report, end="")
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"alert={'true' if alerts else 'false'}\n")
            fh.write("message=" + "；".join(alerts).replace("\n", " ")[:1800] + "\n")
    for item in alerts:
        print(f"::warning::{item}")
    sla_n, sla_misses, _ = sla
    if sla_misses:
        print(f"::warning::600 秒目标最近 {sla_n} 条有 {sla_misses} 条超线；"
              "只告警，不阻断质检或发布")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
