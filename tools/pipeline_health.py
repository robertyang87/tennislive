#!/usr/bin/env python3
"""汇总关键 Actions 的近期成功率、耗时、慢步骤与 600 秒成片告警。

阈值异常只产生 warning/通知，不改变任何生产或发布资格；真正的发布资格仍由
L0/L2/L3 门禁决定。API 本身不可用则返回非零，因为“监控失明”和“系统健康”
不能长得一样。
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import statistics
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 「阻塞」只在看板那边定义一次，这儿直接用它（账号所有者 Q9：看板转阻塞就推微信）。
# ⚠️ pipeline-health.yml 是逐文件稀疏检出的，这个文件要在列表里——
# 判据 test_健康检查的阻塞定义就是看板那一份_工作流检出了它
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_dashboard_snapshot as dashboard  # noqa: E402

DEFAULT_WORKFLOWS = (
    "oncourt-interviews.yml",
    "interview-auto-render.yml",
    "interview-clip.yml",
    "match-reel.yml",
    "auto-push-interview.yml",
    "auto-push-reel.yml",
    "auto-push-explainer.yml",
    # 解说片那条线原来整个不在监控里：`explainer.yml` 是它唯一的出片入口。
    # ⚠️ 这儿原来还有一条 `knowledge-adhoc.yml`（图文知识帖，全库唯一的定时
    # 产出线）——**那条线 2026-09-15 随瘦身停产、工作流文件删掉了，而这份名单
    # 没跟着改**，于是监控表一直在点名一个不存在的工作流。删了东西不改它的
    # 消费者，是这个仓库的老形状。判据 `test_监控名单不许点名不存在的工作流`。
    "explainer.yml",
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
    latest_failure: bool = False

    @property
    def failure_rate(self) -> float:
        return self.failures / self.runs if self.runs else 0.0


#: 出片工作流里**不出片、只做自检**的 mode（按 run-name 的 mode 段认）。它们的红绿
#: 由阻塞那一路按 `<工作流>:<mode>` 单独报；混进出片的趋势里，一趟定时的 cookies
#: 绿会把 render 的连续失败清零、一趟 cookies 红会撑高失败率，中位耗时和步骤抽样
#: 也被三十秒的自检拉偏（2026-09-28 复审：source-health 每 6 小时派一趟
#: `match-reel mode=cookies`）。判据 `test_自检mode不进出片工作流的趋势`。
SELF_CHECK_MODES = frozenset({"cookies"})


def _is_self_check(run: dict) -> bool:
    return dashboard.run_name_fields(run).get("mode") in SELF_CHECK_MODES


def workflow_health(api: GitHubAPI, workflow: str, limit: int,
                    step_runs: int) -> tuple[WorkflowHealth, list[dict]]:
    encoded = urllib.parse.quote(workflow, safe="")
    # 多取一倍：自检 run 滤掉之后，出片 run 仍凑得够 `limit` 条
    payload = api.get(
        f"actions/workflows/{encoded}/runs?status=completed&per_page={min(100, 2 * limit)}")
    runs = [row for row in (payload.get("workflow_runs") or [])
            if not _is_self_check(row)][:limit]
    durations = [v for row in runs
                 if (v := elapsed(row.get("created_at"), row.get("updated_at"))) is not None]
    conclusions = [str(row.get("conclusion") or "") for row in runs]
    # ⚠️ `cancelled` **不是失败**，而这条报表原来把它当失败算。
    #
    # 名单里的 `interview-clip.yml` / `explainer.yml` 都开着
    # `cancel-in-progress: true`：同一个 slug 重渲一版，旧 run 会被**主动取消**。
    # 于是一条片子返工三次，报表就报「近 10 次失败率 50%、连续失败 3」——
    # **一条天天喊狼来了的告警，最后的下场是没人看**，而它要守的那些真失败
    # 就藏在噪音里（这条来自 #573，2026-09-15 移植；那条 PR 基于历史重写之前的
    # main，不能 merge，只能把改动重新落一次）。
    #
    # ⚠️ 同时把这个集合收成**一处出处**：它原来在这个函数里写了三遍
    # （bad / streak / latest_failure），而「一个数写两处必分叉」。
    ok = {"success", "skipped", "neutral"}
    # 取消既不算成功也不算失败：从失败率、连续失败、最新状态里一并排除。
    judged = [c for c in conclusions if c != "cancelled"]
    bad = [c for c in judged if c not in ok]
    streak = 0
    for conclusion in judged:
        if conclusion in ok:
            break
        streak += 1
    health = WorkflowHealth(
        name=workflow, runs=len(runs),
        successes=sum(c == "success" for c in conclusions), failures=len(bad),
        median_seconds=statistics.median(durations) if durations else 0.0,
        consecutive_failures=streak,
        # 是否重复发微信由跨 run 的 active_keys 判断；这里必须保持“仍异常”，
        # 直到一趟成功 run 真正把它恢复，不能按一小时后自动过期。
        latest_failure=bool(judged and judged[0] not in ok),
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


ORCHESTRATOR_STATE = Path("data/orchestration_state.json")
# 一天没点过就该问一句。选 24 小时而不是更短：真的连着几小时没有够格的候选
# 是常态（资格赛周、赛事间歇），而**一整天一条都没点**在正常赛季里不合理。
ORCHESTRATOR_SILENT_HOURS = 24.0


def orchestrator_productivity(
        now: datetime | None = None,
        path: Path | None = None) -> tuple[str | None, float | None]:
    """编排器最近一次**真的点过 run** 是多久以前。返回 (时刻, 过了几小时)。

    ⚠️ **这一项测的是产出，不是绿不绿——而这正是本文件此前整个看不见的那一半。**
    2026-08-25 量出来：`orchestrate` 定时跑了 330 趟，`conclusion` 趟趟
    `success`，而 `data/orchestration_state.json` 至今是 `{"dispatched": {}}`
    ——**一条 run 都没点过**，169 条 spec 没有一条是它产的。本文件原来只统计
    工作流的成功率和耗时，于是它给这条线打的分是满分：**绿正是它坏掉的样子，
    它每一趟都成功地什么都没做。**

    这跟 `sla_health` 那次幸存者偏差（只统计渲成了的趟）是同一个病高一层：
    「只在成功时出声的检查，没法证明它真的看过」。

    读不到 / 没有这个字段 → `(None, None)`，调用方按「从来没点过」处置。
    ⚠️ 不能拿 `dispatched` 里有没有条目判——那些条目 `STATE_TTL_DAYS` 天就
    过期清掉了，「从来没点过」和「点过但都过期了」在它上面分不开。
    """
    now = now or datetime.now(timezone.utc)
    path = path or ORCHESTRATOR_STATE
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    at = instant(str(state.get("last_dispatch_at") or "")) \
        if state.get("last_dispatch_at") else None
    if at is None:
        return None, None
    return state["last_dispatch_at"], (now - at).total_seconds() / 3600


INTERVIEW_DISPATCH_STATE = Path("data/interview_render_dispatched.json")
PARKED_SUBS = "采访 subs 停着："


def parked_interview_subs(path: Path | None = None) -> list[str]:
    """采访自动链「先投 subs」**停下来**的（同一份转写输入投满次数还没交判定）→ 告警句。

    `pick_interview_renders.sync_subs_state` 在全量那一趟把它们标成 `parked`，这里只读标记——
    次数上限只在 pick 那边定义一次。原来停下之后只在 auto-render 的 stderr（等待名单）里印一行，
    不翻日志就看不见（复审 2026-09-28 nit 3）；而停下的原因（下不动源片、判定绑的指纹对不上）
    自动链自己修不好，要人。读不到状态文件＝没有（这一栏不许把监控整个带红）。"""
    try:
        state = json.loads((path or INTERVIEW_DISPATCH_STATE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    book = state.get("subs") if isinstance(state, dict) else None
    out: list[str] = []
    for slug, rec in sorted((book or {}).items() if isinstance(book, dict) else []):
        if isinstance(rec, dict) and rec.get("parked"):
            out.append(f"{PARKED_SUBS}{slug}（同一份转写输入投了 {rec.get('tries')} 趟 mode=subs 还没交"
                       f"判定，最后一趟 {rec.get('at')}）——看「interview-clip · subs · {slug}」的日志，"
                       "修好后手动 dispatch 一次 mode=subs")
    return out


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
                # 保持异常为 active，直到台账真的离开 sending。微信去重由
                # notification_transition 负责；若在这里按一小时窗口让它消失，
                # 下一班会把“时间过去了”误报成“已经恢复”。
                if row.get("status") == "sending" and hours < age:
                    stale.append(f"{directory}/{slug}: sending 已持续 {age:.1f}h")
    return stale


PENDING_DRAFTS = "specs/reels/pending/*.draft.json"
#: `feed_retry_stuck` 那一类告警的开头——`alert_keys` 按它认，按 slug 去重
FEED_RETRY_ALERT = "自动草稿的 flashscore 备料要人看"
#: 人处置完之后怎么让它重来（告警和报表里都印这一句，不让人去翻 skill）
FEED_RETRY_REARM = ("python tools/retry_feed_blocks.py --draft "
                    "specs/reels/pending/<slug>.draft.json --rearm --write，推 main")


def feed_retry_stuck(now: datetime | None = None) -> list[str]:
    """自动草稿里 flashscore 备料**停手、要人看**、而这场球还新鲜的那几份。

    来路（2026-09-28 复审 D1）：probe 那一趟 flashscore 抖一下，草稿照写、留在 waiting；
    编排器认得草稿、永不重 probe。reel-auto-ready 现在按 `_feed_retry` 只重跑读失败的块，
    最多 `FEED_RETRY_MAX` 次——试满了它就不再碰，这儿接着点名：**不能静静地躺到
    PENDING_MAX_AGE 过期**（那时这场球已经不做了，告警也跟着消失）。
    第三轮复审补上另外几种同样没人再碰的：补齐后撤了文案、重读也一样的错、重跑本身崩了
    ——都记在 `_feed_retry.needs_human`（`assemble_spec.flag_feed_retry`）。

    过期了的不报：`promote_reel_draft.PENDING_MAX_AGE` 是新鲜窗唯一的出处（reel-auto-ready
    也 import 它）。判据 `tests/test_feed_retry.py`。"""
    from promote_reel_draft import PENDING_MAX_AGE  # noqa: PLC0415

    now = now or datetime.now(timezone.utc)
    out: list[str] = []
    for draft in _tracked_jsons(PENDING_DRAFTS):
        ledger = draft.get("_feed_retry") if isinstance(draft, dict) else None
        if not isinstance(ledger, dict):
            continue
        why = [str(x) for x in ledger.get("needs_human") or ()]
        if ledger.get("exhausted_at") and ledger.get("blocks"):
            why.insert(0, f"{'、'.join(ledger['blocks'])} 没读到，"
                          f"{ledger['exhausted_at']} 停了自动重跑（试了 {ledger.get('tries')} 次）")
        if not why:
            continue
        try:
            received = instant(str((draft.get("_production") or {}).get("received_at") or ""))
        except ValueError:
            received = None
        if received is None or now - received > PENDING_MAX_AGE:
            continue
        out.append(f"{FEED_RETRY_ALERT}：{draft.get('slug') or '?'}（{'；'.join(why)}）")
    return sorted(out)


def render_report(health: list[WorkflowHealth], steps: list[dict],
                  sla: tuple[int, int, float], stale: list[str],
                  orchestrator: tuple[str | None, float | None] | None = None,
                  *, feed_stuck: list[str] | None = None,
                  parked_subs: list[str] | None = None,
                  ) -> tuple[str, list[str]]:
    # `feed_stuck` 只收关键字：别的分支也在这个位置后面加列表参数（采访字幕停车那一项），两边都留下
    # 合并时，按位置传的那一份会落进对方的形参——报表点名点错一栏，不报错。
    alerts: list[str] = []
    lines = ["## 自动视频流水线健康度", "", "| 工作流 | 样本 | 成功 | 失败率 | 中位耗时 | 连续失败 |",
             "|---|---:|---:|---:|---:|---:|"]
    for row in health:
        lines.append(f"| {row.name} | {row.runs} | {row.successes} | {row.failure_rate:.0%} | "
                     f"{row.median_seconds/60:.1f}m | {row.consecutive_failures} |")
        # 告警列表表达“当前仍然异常”，不能只活一小时。否则持久化去重会在
        # 第二小时把同一个未修故障当成恢复。是否重复发微信在报告之外判断。
        if (row.runs >= 3 and row.latest_failure
                and (row.failure_rate >= .40 or row.consecutive_failures >= 3)):
            alerts.append(f"{row.name}：近 {row.runs} 次失败率 {row.failure_rate:.0%}，连续失败 {row.consecutive_failures}")
    n, misses, median = sla
    lines += ["", f"- 600 秒成片：最近 {n} 条中 {misses} 条超线，中位 {median:.0f}s。"
              "超线只告警，不阻断 L2、发布或微信推送。"]
    # SLA miss 只留 Actions warning/summary，不发微信：metadata 不变时每小时扫到
    # 的仍是同一批 miss，拿它做 PushPlus alert 会形成告警风暴。
    if orchestrator is not None:
        at, hours = orchestrator
        if at is None:
            lines += ["", "- **编排器：从来没有真正点过一条 run。**"
                      "全绿不等于有产出——这条线的每一趟都成功地什么都没做。"]
            alerts.append("编排器从来没点过 run：自动选题链是哑的，"
                          "所有片子都要人从头带")
        else:
            lines += ["", f"- 编排器最近一次点 run：{at}（{hours:.1f} 小时前）。"]
            if hours > ORCHESTRATOR_SILENT_HOURS:
                alerts.append(f"编排器已 {hours:.0f} 小时没点过 run"
                              f"（阈值 {ORCHESTRATOR_SILENT_HOURS:.0f}h）")
    if stale:
        alerts.extend(stale)
        lines += ["", "### 发布账本待核实", *[f"- {item}" for item in stale]]
    if feed_stuck:
        alerts.extend(feed_stuck)
        lines += ["", "### 自动草稿的 flashscore 备料停手了（reel-auto-ready 不会再碰）",
                  *[f"- {item}" for item in feed_stuck],
                  "", f"人处置完之后重新布置：`{FEED_RETRY_REARM}`"]
    if parked_subs:
        alerts.extend(parked_subs)
        lines += ["", "### 采访 subs 停着（自动链不再重投，要人看）",
                  *[f"- {item}" for item in parked_subs]]
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


def alert_keys(alerts: list[str]) -> list[str]:
    """把会随时间变化的告警文案压成可持久化的语义键。

    编排器的“25 小时”每班都会增长、sending 的年龄也一样；这些数字变化不算
    新故障。工作流失败率/连续失败只会在有新 run 时改变，保留数值，让恶化或
    改善中的异常能再通知一次。
    """
    keys: set[str] = set()
    for item in alerts:
        if item.startswith("编排器"):
            keys.add("orchestrator")
        elif ": sending 已持续" in item:
            keys.add("publication:" + item.split(": sending 已持续", 1)[0])
        elif item.startswith(FEED_RETRY_ALERT + "："):
            keys.add("feed_retry:" + item.split("：", 1)[1].split("（", 1)[0])
        elif "：近 " in item and "失败率" in item:
            keys.add("workflow:" + item)
        elif item.startswith(PARKED_SUBS):
            keys.add("interview-subs:" + item[len(PARKED_SUBS):].split("（", 1)[0])
        else:
            digest = hashlib.sha256(item.encode("utf-8")).hexdigest()[:16]
            keys.add("other:" + digest)
    return sorted(keys)


def notification_transition(
        alerts: list[str], state_path: Path,
        now: datetime | None = None) -> tuple[bool, str, str]:
    """只在首次异常、异常集合变化或全部恢复时通知，并写下一班的状态。

    状态由 workflow 的跨 run cache 保存，不提交进 main，避免健康检查每小时
    制造一次仓库提交。损坏/缺失的 cache 按首次运行处置。
    """
    previous = _read_state(state_path)
    before = sorted(str(v) for v in previous.get("active_keys") or [])
    current = alert_keys(alerts)
    message = "；".join(alerts).replace("\n", " ")[:1800]

    notify = current != before and bool(current or before)
    if current:
        title = "⚠️ 网球视频流水线趋势异常"
        notification = message
    elif before:
        title = "✅ 网球视频流水线恢复正常"
        old = str(previous.get("message") or "此前报告的流水线异常")
        notification = ("此前异常已解除：" + old)[:1800]
    else:
        title, notification = "", ""

    _write_state(state_path, {
        **previous,
        "active_keys": current,
        "message": message,
        "checked_at": _stamp(now or datetime.now(timezone.utc)),
    })
    return notify, title, notification


def _read_state(state_path: Path) -> dict:
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(state_path: Path, saved: dict) -> None:
    # 趋势告警和阻塞推送共用这一份（跨 run 的 cache），各写各的键，谁都不许整份覆盖
    state_path.parent.mkdir(parents=True, exist_ok=True)
    temp = state_path.with_suffix(state_path.suffix + ".tmp")
    temp.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(state_path)


def _stamp(at: datetime) -> str:
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 流水线阻塞 → 微信（账号所有者 Q9，2026-09-27）────────────────────────────
#
# 看板在 github.io，他在国内打不开；网页留作备用，阻塞摘要推到微信。
# 「阻塞」的定义是看板那一份（`dashboard.blocked_runs`），不在这儿另写。
#
# 账号所有者 2026-09-27 ~23:00Z 的四条答复（看板 build_dashboard_snapshot 顶注有全文和实测证据）：
# (1) 只推无人值守链的红（`pushable`）(2) 按片子去重 (3) 已按阻塞报的工作流不再推趋势
# （`trend_alerts_to_push`）(4) 6 小时冷却按片子算（`_key` 含 slug）。
#
# 只在**转入**阻塞时推，恢复不推（他要的是「卡住了」这一声，不是来回播报）。
# 两道防刷屏，**都是推迟、不是丢掉**：
# - 同一处（工作流 × mode，`_key`）恢复后又在 BLOCKED_REPEAT_COOLDOWN 内红回来（来回抖），
#   冷却期内不推——否则一条时好时坏的线一天能刷十几条；但**不记成已知**：过了冷却还红着，
#   就当一次新的转入推出去。
#   ⚠️ 原来是记成已知，于是永远不推（复核 FIX ROUND 1 的 nit）：键里没有 slug，08:00 render A
#   红了（推过）、09:00 片子 B 的 render 绿了、10:00 片子 C 的 render 红了一直卡着——
#   他收到的唯一一条微信点的是 A，C 在 10:00、16:00、28:00 都不响。
#   判据 test_冷却期内红回来是推迟不是丢_过了冷却还红就推
# - 两次阻塞推送之间至少隔 BLOCKED_MIN_INTERVAL：被压下的新阻塞**不记成已推**，
#   下一班过了间隔还阻塞就补推，不会丢
BLOCKED_MIN_INTERVAL = timedelta(minutes=30)
BLOCKED_REPEAT_COOLDOWN = timedelta(hours=6)
NO_SLUG = "run 标题里没写是哪条"


# 说法和键都用看板那一份：「match-reel（probe）」、`match-reel:probe`
_which = dashboard.which


def _key(b: dict) -> str:
    """去重和 6 小时冷却都按「工作流 × mode × 片子」，和 `blocked_runs` 取「最近一条」的键
    是同一个（`blocked_key`）。
    ⚠️ 原来按工作流去重：match-reel 的 render 已经报过、之后它的 probe 也红了，
    第二条会被当成「已知」吞掉。键里没有 slug 时，片子 C 的 render 红了会落进片子 A 那一声
    的冷却里压 6 小时（账号所有者 2026-09-27 答复 (4)：冷却按片子算）。"""
    if b.get("key"):
        return str(b["key"])  # `blocked_runs` 算好的，slug 只认 run-name 段位读出来的
    return dashboard.blocked_key(str(b.get("workflow") or ""), b.get("mode"), b.get("slug"))


def pushable(blocked: list[dict]) -> list[dict]:
    """只推无人值守链的红（账号所有者 2026-09-27 答复 (1)）：schedule 和编排器／队列派发的
    run；会话手动拨的 run 红了不推——看板照旧显示它。没带 `unattended` 的按推：
    认不出来时宁可多推一声。判据 `test_会话手动拨的run红了不推微信_看板照旧红`。"""
    return [b for b in blocked if b.get("unattended", True)]


def trend_alerts_to_push(alerts: list[str], blocked: list[dict]) -> list[str]:
    """已经按阻塞报的工作流，它的每小时趋势告警不再推（Q9「不重复已有告警」，
    账号所有者 2026-09-27 答复 (3)）。只去掉「<工作流>.yml：近 N 次失败率…」那一类，
    编排器沉默、账本卡 sending 这些不是同一件事，照推；报表和 `::warning::` 照旧全列。"""
    stems = {str(b.get("workflow") or "") for b in blocked}
    return [a for a in alerts
            if not any(a.startswith(f"{w}.yml：近 ") for w in stems if w)]


def blocked_summary(blocked: list[dict], still: int = 0) -> tuple[str, str]:
    """短摘要：哪个阶段失败、哪条片子卡住、失败的 run 链接。HTML（PushPlus template=html）。"""
    stages = list(dict.fromkeys(s for b in blocked for s in b.get("stages") or []))
    title = "⛔ 网球流水线阻塞：" + (" / ".join(stages) or "未知阶段")
    lines = []
    for b in blocked:
        where = " / ".join(b.get("stages") or []) or b.get("workflow", "")
        line = (f"{html.escape(where)} · {html.escape(_which(b))} 失败"
                f" · 卡住：{html.escape(b.get('slug') or NO_SLUG)}")
        if b.get("url"):
            line += f' · <a href="{html.escape(b["url"], quote=True)}">打开失败的 run</a>'
        lines.append(line)
    if still:
        lines.append(f"另有 {still} 条此前已报过、仍在阻塞")
    return title, "<br>".join(lines)


def blocked_transition(blocked: list[dict], state_path: Path,
                       now: datetime | None = None) -> tuple[bool, str, str]:
    """看板从「不阻塞」转入「阻塞」（或多了一处新阻塞：工作流 × mode）时推一次。"""
    now = now or datetime.now(timezone.utc)
    state = _read_state(state_path)
    known = {str(k) for k in state.get("blocked_active") or []}
    last_push = {str(k): str(v) for k, v in (state.get("blocked_last_push") or {}).items()}
    pushed_at = instant(state.get("blocked_pushed_at"))

    current = {_key(b): b for b in blocked}
    new = [w for w in current if w not in known]
    flapping = [w for w in new if (at := instant(last_push.get(w)))
                and now - at < BLOCKED_REPEAT_COOLDOWN]
    fresh = [w for w in new if w not in flapping]
    notify = bool(fresh) and (pushed_at is None or now - pushed_at >= BLOCKED_MIN_INTERVAL)

    # 恢复了的自动出列：再红就是新的转入。来回抖的（flapping）也不进——它只是推迟，
    # 过了冷却还红着就是 fresh（见上面那段注）
    active = known & set(current)
    title = message = ""
    if notify:
        still = len(active)
        active |= set(fresh)
        for w in fresh:
            last_push[w] = _stamp(now)
        pushed_at = now
        title, message = blocked_summary([current[w] for w in fresh], still)
    _write_state(state_path, {
        **state,
        "blocked_active": sorted(active),
        "blocked_last_push": last_push,
        "blocked_pushed_at": _stamp(pushed_at) if pushed_at else None,
    })
    return notify, title, message


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    ap.add_argument("--workflows", nargs="*", default=list(DEFAULT_WORKFLOWS))
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--step-runs", type=int, default=3)
    ap.add_argument("--summary", default=os.environ.get("GITHUB_STEP_SUMMARY", ""))
    ap.add_argument("--alert-state", default=os.environ.get("PIPELINE_ALERT_STATE", ""))
    args = ap.parse_args(argv)
    if not args.repo or not args.token:
        raise SystemExit("需要 --repo/GITHUB_REPOSITORY 与 --token/GITHUB_TOKEN")
    api = GitHubAPI(args.repo, args.token)
    health, steps = [], []
    for workflow in args.workflows:
        row, these_steps = workflow_health(api, workflow, args.limit, args.step_runs)
        health.append(row)
        steps.extend(these_steps)
    sla = sla_health()
    # 新加的段一律按关键字传（`*` 之后）：几条分支各往这儿加一段，合的时候不会串位
    report, alerts = render_report(health, steps, sla, stale_publications(),
                                   orchestrator_productivity(), feed_stuck=feed_retry_stuck(),
                                   parked_subs=parked_interview_subs())
    # 和看板同一份数据（每条受监控工作流 24 小时内的 run）、同一个定义。
    # ⚠️ 原来取的是全仓最近 100 条——忙时只够回溯一个半小时，而这一班实际两三个小时
    # 才来一趟，一处没人重试的失败滚出列表就永远不推（`monitored_runs` 顶注）。
    # 读失败就让它抛：「读不到」≠「没阻塞」，监控失明要红给人看（模块顶注）。
    # 这儿的稀疏检出里没有 spec 清单，不给 `known`——「哪条卡住」靠出片 run 的 run-name
    # 按段位读（两段的 slug 也认得出），判据 test_两段的slug也要进微信摘要_不许说标题里没写
    runs = dashboard.monitored_runs(api.get)
    blocked = dashboard.blocked_runs(runs)  # 报表全列（和看板一样）
    to_push = pushable(blocked)             # 微信只推无人值守链的（答复 (1)）
    trend = trend_alerts_to_push(alerts, to_push)  # 已按阻塞报的工作流不再推趋势（答复 (3)）
    report += "\n### 流水线阻塞（和看板同一个定义）\n\n" + ("\n".join(
        f"- {' / '.join(b['stages'])} · {_which(b)} · {b.get('slug') or NO_SLUG} · {b.get('url') or ''}"
        + ("" if b.get("unattended", True) else "（会话手动拨的，不推微信）")
        for b in blocked) or "- 没有阻塞。") + "\n"
    print(report, end="")
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(report)
    output = os.environ.get("GITHUB_OUTPUT")
    if args.alert_state:
        notify, title, message = notification_transition(
            trend, Path(args.alert_state))
        blocked_notify, blocked_title, blocked_message = blocked_transition(
            to_push, Path(args.alert_state))
    else:
        notify = bool(trend)
        title = "⚠️ 网球视频流水线趋势异常" if trend else ""
        message = "；".join(trend).replace("\n", " ")[:1800]
        blocked_notify = bool(to_push)
        blocked_title, blocked_message = blocked_summary(to_push) if to_push else ("", "")
    if blocked_notify:
        # 阻塞摘要排最前、标题用它；同一班恰好也有趋势变化就跟在后面，一条消息说完
        message = blocked_message + ("<br><br>" + message if notify else "")
        title, notify = blocked_title, True
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"alert={'true' if alerts else 'false'}\n")
            fh.write(f"notify={'true' if notify else 'false'}\n")
            fh.write("title=" + title.replace("\n", " ") + "\n")
            fh.write("message=" + message + "\n")
    for item in alerts:
        print(f"::warning::{item}")
    sla_n, sla_misses, _ = sla
    if sla_misses:
        print(f"::warning::600 秒目标最近 {sla_n} 条有 {sla_misses} 条超线；"
              "只告警，不阻断质检或发布")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
