#!/usr/bin/env python3
"""Build the public, secret-free snapshot consumed by dashboard/index.html."""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "robertyang87/tennislive"
WORKFLOW_GROUPS = [
    ("发现", ["oncourt-interviews", "official-social-images", "source-health"]),
    ("编排", ["orchestrate"]),
    ("Spec", ["probe", "reel-dispatch-queue"]),
    ("渲染", ["match-reel", "interview-auto-render", "explainer"]),
    ("质检", ["match-reel", "interview-auto-render", "explainer"]),
    ("推送", ["auto-push-reel", "auto-push-interview", "auto-push-explainer"]),
    ("监控", ["pipeline-health", "pages"]),
]
FAILURES = {"failure", "cancelled", "timed_out", "action_required", "startup_failure"}

def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))

def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def github_runs(token: str | None):
    url = f"https://api.github.com/repos/{REPO}/actions/runs?per_page=100"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "tennislive-dashboard"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
            return json.load(response).get("workflow_runs", [])
    except Exception as exc:  # snapshot still ships repo-backed evidence
        print(f"::warning::dashboard could not read Actions: {exc}")
        return []

def latest_attempt(ledger):
    attempts = ledger.get("attempts") or []
    return max(attempts, key=lambda x: x.get("at", ""), default=None)

def collect_content(root: Path):
    items = {}
    type_dirs = {
        "reel": root / "data/reel_publish_ledger",
        "interview": root / "data/interview_publish_ledger",
        "explainer": root / "data/explainer_publish_ledger",
    }
    for kind, directory in type_dirs.items():
        for path in directory.glob("*.json"):
            ledger = read_json(path, {})
            slug = ledger.get("slug") or path.stem
            attempt = latest_attempt(ledger)
            key = (kind, slug)
            item = items.setdefault(key, {"type": kind, "slug": slug})
            if attempt:
                platform_status = attempt.get("platform_status")
                if not platform_status and attempt.get("status") == "sent":
                    # Legacy ledgers used ``sent`` for a successful PushPlus API
                    # response.  That is platform acceptance, not evidence that a
                    # phone received the message.
                    platform_status = "accepted"
                item.update({
                    "pushed": platform_status in {"accepted", "delivered", "confirmed"},
                    "platform_status": platform_status,
                    "delivery_status": attempt.get("delivery_status") or (
                        "unverified" if platform_status == "accepted" else platform_status
                    ),
                    "updated_at": attempt.get("at"),
                    "url": attempt.get("run"),
                })

    for path in root.glob("output/**/render.json"):
        manifest = read_json(path, {})
        parts = path.parts
        kind = next((k for k in ("reel", "interview", "explainer") if k in parts), "reel")
        slug = manifest.get("production_sla", {}).get("slug") or path.parent.name
        item = items.setdefault((kind, slug), {"type": kind, "slug": slug})
        sla = manifest.get("production_sla") or {}
        item.update({
            "rendered": True,
            "qc": bool(manifest.get("qc_attestation_sha256")),
            "sla_met": sla.get("met"),
            "sla_seconds": sla.get("elapsed_seconds"),
            "updated_at": max(filter(None, [item.get("updated_at"), sla.get("artifact_ready_at")]), default=None),
            "url": item.get("url") or manifest.get("video_url"),
        })

    specs = defaultdict(set)
    for path in root.glob("specs/**/*.json"):
        specs[path.stem].add(path)
    state = read_json(root / "data/orchestration_state.json", {})
    dispatched = state.get("dispatched") or {}
    for item in items.values():
        slug = item["slug"]
        item["spec"] = slug in specs
        item["orchestrated"] = slug in dispatched
        item["discovered"] = item["orchestrated"] or item["spec"] or item.get("rendered", False)
        item.setdefault("rendered", False)
        item.setdefault("qc", False)
        item.setdefault("pushed", False)
        item.setdefault("platform_status", None)
        item.setdefault("delivery_status", None)
        item.setdefault("updated_at", None)
    return sorted(items.values(), key=lambda x: x.get("updated_at") or "", reverse=True), state

def run_state(run):
    if run.get("status") != "completed":
        return "running", "运行中"
    conclusion = run.get("conclusion") or "unknown"
    if conclusion in FAILURES:
        return "failure", "失败"
    if conclusion == "success":
        return "success", "正常"
    return "warning", "未知"

def build(root: Path, token: str | None):
    now = datetime.now(timezone.utc)
    runs = github_runs(token)
    content, state = collect_content(root)
    runs_by_name = defaultdict(list)
    for run in runs:
        runs_by_name[run.get("name", "")].append(run)

    stages = []
    for label, names in WORKFLOW_GROUPS:
        candidates = [r for name in names for r in runs_by_name.get(name, [])]
        candidates.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        latest = candidates[0] if candidates else None
        if latest:
            status, _ = run_state(latest)
            detail = latest.get("name", label)
            stages.append({"label": label, "status": status, "detail": detail, "updated_at": latest.get("updated_at"), "url": latest.get("html_url")})
        else:
            stages.append({"label": label, "status": "warning", "detail": "暂无运行证据", "updated_at": None, "url": None})

    selected_names = {name for _, names in WORKFLOW_GROUPS for name in names}
    workflow_rows = []
    for run in runs:
        if run.get("name") not in selected_names:
            continue
        status, status_label = run_state(run)
        workflow_rows.append({
            "label": run.get("name"), "detail": run.get("display_title") or run.get("event"),
            "status": status, "status_label": status_label, "updated_at": run.get("updated_at"),
            "url": run.get("html_url"),
        })
    workflow_rows.sort(key=lambda x: x.get("updated_at") or "", reverse=True)

    recent_runs = [r for r in runs if parse_time(r.get("created_at")) and parse_time(r["created_at"]) >= now - timedelta(hours=24)]
    latest_by_name = {}
    for run in recent_runs:
        name = run.get("name")
        if name and (name not in latest_by_name or (run.get("updated_at") or "") > (latest_by_name[name].get("updated_at") or "")):
            latest_by_name[name] = run
    failed = [r for name, r in latest_by_name.items() if name in selected_names and r.get("conclusion") in FAILURES]
    active = [r for r in runs if r.get("status") != "completed"]
    accepted_24h = sum(1 for x in content if x.get("pushed") and parse_time(x.get("updated_at")) and parse_time(x["updated_at"]) >= now - timedelta(hours=24))
    sla_items = [x for x in content if x.get("sla_met") is not None]
    sla_met = sum(1 for x in sla_items if x["sla_met"])
    pending = len(state.get("dispatched") or {}) + len(list((root / "data/reel-dispatch-queue").glob("*.json")))

    if failed:
        first = min(failed, key=lambda r: r.get("created_at") or "")
        health = {"status": "failed", "title": "流水线存在阻塞", "message": f"最早失败：{first.get('name')}。点击下方任务可直接查看对应 run。"}
    elif active:
        health = {"status": "healthy", "title": "流水线正在运行", "message": f"当前有 {len(active)} 个自动任务运行中，未发现已确定失败。"}
    elif not runs:
        health = {"status": "warning", "title": "Actions 状态暂不可见", "message": "仓库产物可读，但本次快照未取得 GitHub Actions 运行记录。"}
    else:
        health = {"status": "healthy", "title": "流水线运行正常", "message": "最近 24 小时未发现生产工作流失败；页面只把有证据的阶段标记为完成。"}

    return {
        "schema_version": 2, "generated_at": now.isoformat().replace("+00:00", "Z"), "repository": REPO,
        "health": health,
        "summary": {"active": len(active), "accepted_24h": accepted_24h, "pending": pending, "sla_met": sla_met, "sla_total": len(sla_items), "sla_rate": round(100 * sla_met / len(sla_items)) if sla_items else 0},
        "stages": stages, "content": content[:100], "workflows": workflow_rows[:40],
        "sources": ["GitHub Actions", "data/orchestration_state.json", "specs/**/*.json", "output/**/render.json", "data/*_publish_ledger/*.json"],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-runs", type=Path)
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if args.fixture_runs:
        fixture = read_json(args.fixture_runs, {})
        global github_runs
        github_runs = lambda _token: fixture.get("workflow_runs", [])
    data = build(args.root, token)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dashboard snapshot: {len(data['content'])} content items, {len(data['workflows'])} workflow rows")

if __name__ == "__main__":
    main()
