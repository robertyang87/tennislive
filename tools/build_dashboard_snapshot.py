#!/usr/bin/env python3
"""Build the public, secret-free snapshot consumed by dashboard/index.html.

「阻塞」在这儿只定义一次（`blocked_runs`）：看板首屏用它，每小时的
`tools/pipeline_health.py` 也 import 它来决定要不要推微信（账号所有者 Q9，
2026-09-27：国内打不开 github.io，阻塞摘要推到微信、网页留作备用）。
两处各写一份的话，看板说阻塞、微信不响（或反过来）只是时间问题。

2026-09-27 UI 评审 WP1 一并修掉的几处「看板不诚实」：

- **看板在监控自己**：`pages` 占了最近 run 的一半，而本趟 pages 永远是
  「运行中」——于是「运行中」恒 ≥1、监控那一格恒蓝。现在 `pages` 这条工作流
  和本趟 run（`--self-run-id`，工作流里传 `GITHUB_RUN_ID`）一律不算。
- **按 `name` 认工作流，有两条认不出来**：`probe.yml` 的名字是
  `probe-data-sources`、`explainer.yml` 是 `explainer-video`，于是 Spec 那一格
  常年「暂无运行证据」、解说片的失败永远进不了首屏。现在按 run 的 `path`
  （`.github/workflows/<文件>.yml`）认文件名，`name` 只是没有 path 时的退路。
- **取消不算失败**：`explainer` / `interview-clip` 开着 cancel-in-progress，同一条
  片子重渲一版旧 run 就被取消——`pipeline_health.workflow_health` 早就不把它算
  失败了（#573），看板这边还算，于是一次返工就把首屏打成「阻塞」。
- **采访条目重复、两条状态互相矛盾**：采访的产物目录是复数 `output/interviews/`，
  原来按单数 `interview` 去认，认不出就落成 `reel`——同一个 slug 出两条。
- **卡片主行是 slug**：改读 spec 的 `cover.topic`（采访没有 topic 的读 `cover.title`）。
- **没有成片数据时达标率报 0%**：现在是 `None`，页面显示「—」。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "robertyang87/tennislive"
#: 阶段 → 工作流**文件名**（不带 .yml）。按文件名认，不按 `name:`——
#: 判据 `test_看板阶段表点名的工作流文件都存在_pages按名字订阅它们`。
WORKFLOW_GROUPS = [
    ("发现", ["oncourt-interviews", "official-social-images", "source-health"]),
    ("编排", ["orchestrate"]),
    ("Spec", ["probe", "reel-dispatch-queue"]),
    ("渲染", ["match-reel", "interview-auto-render", "explainer"]),
    ("质检", ["match-reel", "interview-auto-render", "explainer"]),
    ("推送", ["auto-push-reel", "auto-push-interview", "auto-push-explainer"]),
    ("监控", ["pipeline-health"]),
]
#: 阶段标签 → 内容条目上的字段（卡片上那颗「质检 ✓ · 下一步 推送」芯片用的是同一套词）
STAGE_FIELDS = {"发现": "discovered", "编排": "orchestrated", "Spec": "spec",
                "渲染": "rendered", "质检": "qc", "推送": "pushed"}
#: 看板自己：部署它的那条工作流不进任何一格、任何一个计数
SELF_WORKFLOWS = {"pages"}
MONITORED = {name for _, names in WORKFLOW_GROUPS for name in names}
#: `cancelled` 不在这儿——理由见模块顶注，和 `pipeline_health.workflow_health` 一致
FAILURES = {"failure", "timed_out", "action_required", "startup_failure"}
OK = {"success", "skipped", "neutral"}
BLOCKED_WINDOW = timedelta(hours=24)
KIND_DIRS = {"reel": "reel", "interview": "interview", "interviews": "interview",
             "explainer": "explainer"}
SPEC_DIRS = {"reel": "reels", "interview": "interviews", "explainer": "explainers"}
#: 小写连字符词（`bu-majchrzak-hangzhou-2026-r2`、`ranking-math`）
_SLUGGY = re.compile(r"(?<![a-z0-9-])[a-z0-9]+(?:-[a-z0-9]+)+(?![a-z0-9-])")


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


def workflow_of(run: dict) -> str:
    """run 属于哪个工作流**文件**。API 给的 `path` 是
    `.github/workflows/match-reel.yml`（有时带 `@<ref>`）；没有 path 才退回 `name`。"""
    path = str(run.get("path") or "").split("@", 1)[0]
    if path:
        return Path(path).stem
    return str(run.get("name") or "")


def is_self(run: dict, self_run_id=None) -> bool:
    if workflow_of(run) in SELF_WORKFLOWS:
        return True
    return bool(self_run_id) and str(run.get("id")) == str(self_run_id)


def run_state(run):
    if run.get("status") != "completed":
        return "running", "运行中"
    conclusion = run.get("conclusion") or "unknown"
    if conclusion in FAILURES:
        return "failure", "失败"
    if conclusion == "cancelled":
        return "cancelled", "已取消"
    if conclusion in OK:
        return "success", "正常"
    return "warning", "未知"


def slug_of(title: str, known=(), exclude=()) -> str | None:
    """run 标题里写的是哪条片子。先认仓库里真有的 slug（取最长的那个），
    再退回「至少三段」的连字符词（两段的 `alcaraz-fritz` 这种提交标题里的简称
    不够格）；工作流自己的文件名和 `name:`（`auto-push-reel`、`probe-data-sources`）
    不算。都没有就是 None——**不猜**，页面和微信照实说「run 标题里没写是哪条」。"""
    text = str(title or "").lower()
    skip = MONITORED | SELF_WORKFLOWS | {str(e).lower() for e in exclude if e}
    tokens = [t for t in _SLUGGY.findall(text) if t not in skip]
    known = set(known)
    hits = [t for t in tokens if t in known]
    pool = hits or [t for t in tokens if t.count("-") >= 2]
    return max(pool, key=len) if pool else None


def blocked_runs(runs, now=None, *, self_run_id=None, known=()) -> list[dict]:
    """「流水线阻塞」的唯一定义：每个受监控的工作流，取 24 小时内最近一条
    **有结论、不是取消**的 run；它失败了，这条工作流就算阻塞。按最早失败排前。

    看板首屏和 `pipeline_health` 的微信推送都用它（Q9）。
    """
    now = now or datetime.now(timezone.utc)
    latest: dict[str, dict] = {}
    for run in runs:
        wf = workflow_of(run)
        if wf not in MONITORED or is_self(run, self_run_id):
            continue
        if run.get("status") != "completed" or run.get("conclusion") == "cancelled":
            continue
        created = parse_time(run.get("created_at"))
        if created is None or created < now - BLOCKED_WINDOW:
            continue
        if wf not in latest or (run.get("updated_at") or "") > (latest[wf].get("updated_at") or ""):
            latest[wf] = run
    out = []
    for wf, run in latest.items():
        if run.get("conclusion") not in FAILURES:
            continue
        title = run.get("display_title") or run.get("name") or wf
        out.append({
            "workflow": wf,
            "stages": [label for label, names in WORKFLOW_GROUPS if wf in names],
            "slug": slug_of(title, known, exclude=(run.get("name"),)),
            "title": title,
            "url": run.get("html_url"),
            "at": run.get("updated_at"),
            "created_at": run.get("created_at"),
        })
    out.sort(key=lambda b: b.get("created_at") or "")
    return out


def latest_attempt(ledger):
    attempts = ledger.get("attempts") or []
    return max(attempts, key=lambda x: x.get("at", ""), default=None)


def _spec_title(spec: dict) -> str | None:
    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    topic = cover.get("topic")
    if isinstance(topic, str) and topic.strip():
        return topic.strip()
    title = cover.get("title")
    if isinstance(title, list):
        title = " ".join(str(t).strip() for t in title if str(t).strip())
    if isinstance(title, str) and title.strip():
        return title.strip()
    plain = spec.get("title")
    return plain.strip() if isinstance(plain, str) and plain.strip() else None


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
        parts = path.relative_to(root).parts
        # ⚠️ 采访的产物目录是复数 `output/interviews/<slug>/`——按单数去认会落成
        # reel，同一个 slug 出两条（判据 `test_采访产物目录是复数也只出一条_类型是interview`）
        kind = next((KIND_DIRS[p] for p in parts[:-1] if p in KIND_DIRS), "reel")
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

    specs: dict[str, dict[str, list[Path]]] = defaultdict(lambda: defaultdict(list))
    for path in root.glob("specs/**/*.json"):
        top = path.relative_to(root / "specs").parts[0]
        specs[path.stem][top].append(path)
    state = read_json(root / "data/orchestration_state.json", {})
    dispatched = state.get("dispatched") or {}
    for item in items.values():
        slug = item["slug"]
        own = specs.get(slug, {}).get(SPEC_DIRS.get(item["type"], ""), [])
        # 同一个 stem 在 reels/ 和 interviews/ 各有一份是常态（同一场球两条线）；
        # 标题只认自己这条线的，正式 spec 优先于 pending 草稿。
        own = sorted(own, key=lambda p: ("pending" in p.parts, len(p.parts)))
        item["spec"] = bool(own) or slug in specs
        item["title"] = next(filter(None, (_spec_title(read_json(p, {}) or {}) for p in own)), None) \
            if own else None
        item["orchestrated"] = slug in dispatched
        item["discovered"] = item["orchestrated"] or item["spec"] or item.get("rendered", False)
        item.setdefault("rendered", False)
        item.setdefault("qc", False)
        item.setdefault("pushed", False)
        item.setdefault("platform_status", None)
        item.setdefault("delivery_status", None)
        item.setdefault("updated_at", None)
        item.setdefault("failed_stage", None)
    return sorted(items.values(), key=lambda x: x.get("updated_at") or "", reverse=True), state, set(specs)


def build(root: Path, token: str | None, *, self_run_id=None):
    now = datetime.now(timezone.utc)
    runs = [r for r in github_runs(token) if not is_self(r, self_run_id)]
    content, state, spec_slugs = collect_content(root)
    known = {x["slug"] for x in content} | spec_slugs
    blocked = blocked_runs(runs, now, known=known)
    blocked_by_wf = {b["workflow"]: b for b in blocked}

    by_workflow = defaultdict(list)
    for run in runs:
        by_workflow[workflow_of(run)].append(run)
    for rows in by_workflow.values():
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)

    stages = []
    for label, names in WORKFLOW_GROUPS:
        failing = [blocked_by_wf[n] for n in names if n in blocked_by_wf]
        # 取消的 run 已经被后一趟取代，不代表这一格现在的状态
        candidates = [r for n in names for r in by_workflow.get(n, []) if r.get("conclusion") != "cancelled"]
        candidates.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        running = [r for r in candidates if r.get("status") != "completed"]
        if failing:
            worst = failing[0]
            stages.append({"label": label, "status": "failure", "detail": worst["workflow"],
                           "slug": worst["slug"], "updated_at": worst["at"], "url": worst["url"]})
        elif running:
            r = running[0]
            stages.append({"label": label, "status": "running", "detail": workflow_of(r), "slug": None,
                           "updated_at": r.get("updated_at"), "url": r.get("html_url")})
        elif candidates:
            r = candidates[0]
            status, _ = run_state(r)
            stages.append({"label": label, "status": status, "detail": workflow_of(r), "slug": None,
                           "updated_at": r.get("updated_at"), "url": r.get("html_url")})
        else:
            stages.append({"label": label, "status": "warning", "detail": "暂无运行证据", "slug": None,
                           "updated_at": None, "url": None})

    # 自动任务：每个工作流只留最新一条，失败的排前面，再是运行中
    rank = {"failure": 0, "running": 1}
    workflow_rows = []
    for wf in sorted(MONITORED):
        rows = by_workflow.get(wf)
        if not rows:
            continue
        run = rows[0]
        status, status_label = run_state(run)
        if wf in blocked_by_wf and status != "running":
            status, status_label = "failure", "失败"
        name = run.get("name") or wf
        title = run.get("display_title") or ""
        workflow_rows.append({
            "label": name, "workflow": wf,
            "detail": title if title and title != name else (run.get("event") or ""),
            "status": status, "status_label": status_label, "updated_at": run.get("updated_at"),
            "url": run.get("html_url"),
        })
    workflow_rows.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    workflow_rows.sort(key=lambda x: rank.get(x["status"], 2))

    # 卡住的那条片子，卡片上也标出来（只认 run 标题里真写了的 slug）
    for b in blocked:
        field = STAGE_FIELDS.get(b["stages"][0]) if b["stages"] else None
        for item in content:
            if field and b["slug"] and item["slug"] == b["slug"] and \
                    (item.get("updated_at") or "") <= (b.get("at") or ""):
                item["failed_stage"] = field

    active = [r for r in runs if r.get("status") != "completed"]
    accepted_24h = sum(1 for x in content if x.get("pushed") and parse_time(x.get("updated_at")) and parse_time(x["updated_at"]) >= now - timedelta(hours=24))
    sla_items = [x for x in content if x.get("sla_met") is not None]
    sla_met = sum(1 for x in sla_items if x["sla_met"])
    pending = len(state.get("dispatched") or {}) + len(list((root / "data/reel-dispatch-queue").glob("*.json")))

    if blocked:
        labels = list(dict.fromkeys(s for b in blocked for s in b["stages"]))
        health = {"status": "failed", "title": "流水线存在阻塞",
                  "message": f"{' · '.join(labels)} {len(labels)} 个阶段失败",
                  "blocked": blocked, "action_url": blocked[0]["url"]}
    elif active:
        health = {"status": "running", "title": "流水线正在运行", "message": f"当前有 {len(active)} 个自动任务运行中，未发现已确定失败。"}
    elif not runs:
        health = {"status": "warning", "title": "Actions 状态暂不可见", "message": "仓库产物可读，但本次快照未取得 GitHub Actions 运行记录。"}
    else:
        health = {"status": "healthy", "title": "流水线运行正常", "message": "最近 24 小时未发现生产工作流失败；页面只把有证据的阶段标记为完成。"}

    return {
        "schema_version": 3, "generated_at": now.isoformat().replace("+00:00", "Z"), "repository": REPO,
        "health": health,
        "summary": {"active": len(active), "accepted_24h": accepted_24h, "pending": pending, "sla_met": sla_met,
                    "sla_total": len(sla_items),
                    # 没有样本就是「不知道」，不是 0%
                    "sla_rate": round(100 * sla_met / len(sla_items)) if sla_items else None},
        "stages": stages, "content": content[:100], "workflows": workflow_rows[:40],
        "sources": ["GitHub Actions", "data/orchestration_state.json", "specs/**/*.json", "output/**/render.json", "data/*_publish_ledger/*.json"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-runs", type=Path)
    parser.add_argument("--self-run-id", default=os.environ.get("GITHUB_RUN_ID", ""),
                        help="本趟部署自己的 run id：它不算「运行中」（工作流里传 GITHUB_RUN_ID）")
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if args.fixture_runs:
        fixture = read_json(args.fixture_runs, {})
        global github_runs

        def github_runs(_token):
            return fixture.get("workflow_runs", [])
    data = build(args.root, token, self_run_id=args.self_run_id or None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"dashboard snapshot: {len(data['content'])} content items, {len(data['workflows'])} workflow rows")

if __name__ == "__main__":
    main()
