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

账号所有者 2026-09-27 ~23:00Z 对 Q9 微信阻塞推送的四条答复（有约束力）：

1. **只推无人值守链的失败**：`schedule` 触发的 run，和编排器／队列 `gh workflow run`
   派发的 run；会话手动拨的 run 一律不推（`is_unattended`）。**看板照旧显示每一处红**，
   只有微信收窄。判据是 run 对象自己带的 `event` ＋ `triggering_actor`，不是标题：
   2026-09-27 实测（list_workflow_runs，只读）——`interview-clip` 36337385713 /
   `auto-push-interview` 36336727963 由编排链派发，`triggering_actor` 是
   `github-actions[bot]`（派发步骤都用 `GH_TOKEN: github.token`）；会话拨的
   `match-reel` 36333879418 等是 `robertyang87`；而 `reel-auto-ready` 的 schedule run
   36352155523 的 actor **也是** `robertyang87`（最后改 cron 的人）——所以先看 event。
   run 标题里没有派发者标记（出片 run-name 只有 mode · slug），读不出来。
2. **阻塞按片子去重**：键是 工作流 × mode × slug（`blocked_key`）——A 的 render 红了，
   之后 B 的 render 绿了，A 照样阻塞，直到 A 自己绿了或滚出 24 小时。
3. **已经按阻塞报过的工作流，不再推它的每小时趋势告警**（Q9「不重复已有告警」，
   `pipeline_health.trend_alerts_to_push`）。
4. **6 小时冷却按片子算**：冷却键和去重键是同一个 `blocked_key`，含 slug。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "robertyang87/tennislive"
#: 阶段 → 工作流**文件名**（不带 .yml）。按文件名认，不按 `name:`——
#: 判据 `test_看板阶段表点名的工作流文件都存在_pages按名字订阅它们`。
#:
#: ⚠️ Spec 这一格原来挂的是 `probe.yml`——它是 `probe-data-sources`，手动跑的
#: Sportradar／RapidAPI 覆盖率诊断，不是写 spec 的那一步；它红了微信会报
#: 「阻塞：Spec」，而真正把 pending 草稿提升成 spec 的 `reel-auto-ready`（每 10 分钟
#: 一班）一直没人盯。`interview-clip`（手动拨的采访片出片线）原来也不在表里，
#: 它红了既不上看板也不推微信。
#: 出片那三条的 run 按 mode 另认阶段（`MODE_STAGES`），这里写的是认不出 mode 时的默认。
WORKFLOW_GROUPS = [
    ("发现", ["oncourt-interviews", "official-social-images", "source-health"]),
    ("编排", ["orchestrate"]),
    ("Spec", ["reel-auto-ready", "reel-dispatch-queue"]),
    ("渲染", ["match-reel", "interview-auto-render", "interview-clip", "explainer"]),
    ("质检", ["match-reel", "interview-auto-render", "interview-clip", "explainer"]),
    ("推送", ["auto-push-reel", "auto-push-interview", "auto-push-explainer"]),
    ("监控", ["pipeline-health"]),
]
#: 只由 workflow_dispatch 触发、`run-name` 是我们自己写死的出片工作流：标题按「 · 」
#: 切开，第一段是 `name:`，后面每一段是哪个输入登记在这儿。**「哪条卡住」先从这儿按
#: 段位读**，不靠 `slug_of` 去猜——两段的 slug（`zverev-sonego`、`ranking-math`，
#: 自动链的 pending 草稿 126 条里 114 条是两段）按启发式永远认不出来，而
#: `pipeline_health` 那边没有 spec 清单可以拿来当 `known`。
#: 判据 `test_run标题的段位表和工作流里写的run_name对得上`（和 yml 对账，不许各写各的）。
RUN_NAME_FIELDS = {
    "match-reel": ("mode", "slug"),
    "interview-clip": ("mode", "slug"),
    "explainer": ("slug",),
}
#: 出片工作流的 mode → 阶段（mode 在 run 标题里）。match-reel 的 `probe` 是下载源片、
#: 出缩略图墙，给写 spec 用的——它红了是 Spec 卡住，不是「渲染 / 质检」。
#: 表里没有的 mode 退回 WORKFLOW_GROUPS 的默认。
MODE_STAGES = {
    "probe": ["Spec"],        # match-reel：下载源片、缩略图墙
    "narration": ["Spec"],    # match-reel：只查 spec 的旁白装不装得下
    "subs": ["Spec"],         # interview-clip：取字幕切行，写进 spec
    "cookies": ["发现"],      # match-reel：只验 YouTube 还能不能下（和 source-health 同一类）
    "cover": ["渲染"],        # 只出封面海报
    "render": ["渲染", "质检"],
    "push": ["推送"],
    # match-reel：只改注解的 spec 重核对、不重渲（O1）——重建 ASS／plan、逐字节比对、复用成片、
    # 重发质检凭证，不编码。它绿了不代表那一条 render 的红修好了，所以不进「取代」那张表
    "reattest": ["质检"],
}
#: 这几个 mode 不针对哪一条片子：`match-reel` 的 slug 输入是 required、默认
#: `eala-zheng`，cookies 模式拨的时候没人改它——照读就会在微信里说
#: 「卡住：eala-zheng」，还把那条片子的卡片标成「发现 ✕」。
SLUGLESS_MODES = {"cookies"}
#: 同一条片子（同一个工作流 × 同一个 slug）后来 render **成功**了，它前面那几步的红就已经
#: 被取代：render 自己要过 spec、旁白装不装得下、封面那几道闸，它绿了就说明 probe／
#: narration／cover／subs 那一红修好了。和取消同一个待遇——不算阻塞、不占阶段卡片、
#: 不占「自动任务」那一行（复核 FIX ROUND 1 的 nit：narration 红了、改完 spec 同一条
#: render 绿了，Spec 那一格和首屏还一直写阻塞，微信点名一条已经渲出来的片子）。
#: ⚠️ render 的红**不**让之后的 push 绿取代：推出去的可能是上一版成片，这一版没落地。
#: 判据 `test_同一条片子后来render绿了_前面几步的红不再算阻塞`。
SUPERSEDED_BY = {"render": frozenset({"probe", "narration", "cover", "subs"})}
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
#: run 标题里按段位读出来的 slug：单段的也算（解说片有 `hawkeye`、`roof` 这种老 slug）
_SLUG_EXACT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


#: 按工作流取 run 时一页多少条、最多翻几页（24 小时里 match-reel 实测 64 条，一页就够；
#: 翻到顶还满就出声，不静默截断）
RUNS_PER_PAGE = 100
MAX_PAGES = 3
#: 一次读失败（502、限流抖一下）先等这么久再试**一次**；第二次还失败才抛。
RETRY_SLEEP_SECONDS = 3.0


def get_with_retry(get, path: str, sleep=None) -> dict:
    """`get(path)`，失败了等 `RETRY_SLEEP_SECONDS` 再试一次，第二次还失败就照原样抛。

    按工作流取 run 之后，看板一趟、健康检查一班各多出 14 次调用（复核 FIX ROUND 2 的
    nit）：任何一次读失败都整份当「读不到」——看板写「Actions 状态暂不可见」、
    pipeline-health 红一班，下一班它就成了「监控」那一处阻塞、推一条微信。
    「读不到」≠「健康」这条不变（第二次还失败照样抛），只是一次瞬时的 502 不再
    被放大成一条微信。判据 `test_按工作流取run_一次瞬时失败重试一次_两次都失败才抛`。
    """
    try:
        return get(path)
    except Exception as exc:  # noqa: BLE001 — 什么错都只重试一次，第二次原样抛
        print(f"::warning::读 {path.split('?', 1)[0]} 失败，{RETRY_SLEEP_SECONDS:g} 秒后重试一次：{exc}")
        (sleep or time.sleep)(RETRY_SLEEP_SECONDS)
        return get(path)


def monitored_runs(get, now=None, *, sleep=None) -> list[dict]:
    """每条受监控工作流在 `BLOCKED_WINDOW`（24 小时）里的全部 run，按 id 合并。

    `get(path)` 拿 `repos/<repo>/` 之后的那一截路径、返回解析好的 JSON；读失败重试一次
    （`get_with_retry`），还失败就抛——
    「读不到」≠「没失败」，调用方自己决定怎么出声。看板（`github_runs`）和每小时的
    `pipeline_health` 都从这儿取，**同一份数据、同一个定义**。

    ⚠️ 原来两边都只取**全仓**最近 100 条（复核 FIX ROUND 1 的 blocking）：忙时 100 条
    只回溯 80~119 分钟（pages 占 31%、ci 占 25%），夜里 169~283 分钟；而
    pipeline-health 的「每小时」一班实际 145~402 分钟才来一趟（schedule 被 GitHub 丢弃）。
    一处没人重试的失败，只要不落在某一班之前那一百来分钟里，就滚出列表、永远不推——
    而按 `blocked_runs` 自己的定义它仍是那一处最近的一条。看板首屏同一个根子：
    一个半小时后转绿，还写「最近 24 小时未发现生产工作流失败」。
    按工作流取用的是 `nudge_stale_ticks.sh`／`workflow_health` 同一个端点，一班 14 次调用。
    判据 `test_失败滚出全仓最近100条_按工作流取回来照样推`。
    """
    now = now or datetime.now(timezone.utc)
    since = (now - BLOCKED_WINDOW).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pages = []
    for wf in sorted(MONITORED):
        for page in range(1, MAX_PAGES + 1):
            rows = get_with_retry(get, f"actions/workflows/{wf}.yml/runs?per_page={RUNS_PER_PAGE}"
                                  f"&page={page}&created=%3E%3D{since}", sleep).get("workflow_runs") or []
            pages.append(rows)
            if len(rows) < RUNS_PER_PAGE:
                break
        else:
            print(f"::warning::{wf} 24 小时内超过 {RUNS_PER_PAGE * MAX_PAGES} 条 run，"
                  "只取了最近这些——更早的失败看不见")
    return merge_runs(*pages)


def merge_runs(*lists) -> list[dict]:
    """几份 run 列表按 id 合并（先出现的留下）；没有 id 的照留，不猜它是不是重复。"""
    seen, out = set(), []
    for rows in lists:
        for run in rows or []:
            rid = run.get("id")
            if rid is not None:
                if rid in seen:
                    continue
                seen.add(rid)
            out.append(run)
    return out


def _api_get(token: str | None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "tennislive-dashboard"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get(path: str) -> dict:
        url = f"https://api.github.com/repos/{REPO}/{path.lstrip('/')}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as response:
            return json.load(response)
    return get


def github_runs(token: str | None):
    """全仓最近 100 条（「运行中」要数到不受监控的 ci 这类）∪ 受监控工作流 24 小时内的
    全部 run（`monitored_runs`，阻塞和阶段卡片靠它）。

    任何一次读失败都整份当「读不到」：只拿到一半就写「最近 24 小时未发现失败」，
    比首屏老实说「Actions 状态暂不可见」坏得多。"""
    get = _api_get(token)
    try:
        return merge_runs(get_with_retry(get, "actions/runs?per_page=100").get("workflow_runs") or [],
                          monitored_runs(get))
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
    不算。都没有就是 None——**不猜**，页面和微信照实说「run 标题里没写是哪条」。

    ⚠️ 这是**退路**：出片那三条（`RUN_NAME_FIELDS`）的标题是我们写死的 run-name，
    `blocked_runs` 先按段位读（`run_name_fields`），两段的 slug 在这儿认不出来。"""
    text = str(title or "").lower()
    skip = MONITORED | SELF_WORKFLOWS | {str(e).lower() for e in exclude if e}
    tokens = [t for t in _SLUGGY.findall(text) if t not in skip]
    known = set(known)
    hits = [t for t in tokens if t in known]
    pool = hits or [t for t in tokens if t.count("-") >= 2]
    return max(pool, key=len) if pool else None


def _title_parts(run: dict) -> list[str] | None:
    """出片 run 的标题按「 · 」切开的各段；段数对不上、第一段不是 `name:`、或者这条
    工作流不在 `RUN_NAME_FIELDS` 里，就是 None。"""
    fields = RUN_NAME_FIELDS.get(workflow_of(run))
    title = str(run.get("display_title") or "")
    if not fields or not title:
        return None
    parts = [p.strip() for p in title.split(" · ")]
    if len(parts) != 1 + len(fields):
        return None
    if run.get("name") and parts[0] != run["name"]:
        return None
    return parts


def is_legacy_title(run: dict) -> bool:
    """出片工作流（`RUN_NAME_FIELDS`）里、标题还是改 run-name 之前那种的老 run
    （标题就是一个 `match-reel`，切不出 mode 和 slug）。"""
    return workflow_of(run) in RUN_NAME_FIELDS and _title_parts(run) is None


def run_name_fields(run: dict) -> dict[str, str]:
    """按 `RUN_NAME_FIELDS` 把出片 run 的标题切成 {mode, slug}。

    只认段数对得上、第一段就是这条工作流 `name:` 的标题（改 run-name 之前的老 run
    标题就是一个 `match-reel`，切不出东西）；slug 那一段必须是小写连字符词。
    切不出就是 {}——调用方再退回 `slug_of` 的启发式。
    """
    parts = _title_parts(run)
    if parts is None:
        return {}
    out = {k: v for k, v in zip(RUN_NAME_FIELDS[workflow_of(run)], parts[1:]) if v}
    if "slug" in out and (not _SLUG_EXACT.match(out["slug"]) or out.get("mode") in SLUGLESS_MODES):
        out.pop("slug")
    return out


def run_stages(run: dict) -> list[str]:
    """这条 run 算哪个（些）阶段：出片 run 按标题里的 mode 认，其余按工作流的默认。"""
    mode = run_name_fields(run).get("mode")
    if mode in MODE_STAGES:
        return list(MODE_STAGES[mode])
    wf = workflow_of(run)
    return [label for label, names in WORKFLOW_GROUPS if wf in names]


def superseded_ids(runs) -> dict:
    """被后来一趟取代了的失败 run：{失败 run 的 id: 取代它的那一趟 run}。
    `blocked_runs` 和阶段卡片都按它跳过——两边跳的是同一批，首屏和卡片才不会各说各的；
    阶段卡片那一格只剩被取代的红时，指向取代它的那一趟（不写「暂无运行证据」）。

    两种取代：
    - 同一条片子后来那趟成功的 render（`SUPERSEDED_BY`）。
    - **老标题**的失败（`is_legacy_title`：改 run-name 之前的 run，标题就是一个
      `interview-clip`，切不出 mode）被同一条工作流之后任何一趟**有结论、不是取消**的
      run 取代。它的阻塞键是光秃秃的 `interview-clip`，合并之后的新 run 永远不会再用
      这个键——不取代的话，合并前最后一条老 run 红着，就一直按「最近一条」阻塞满 24
      小时（后面 render 绿了也顶不掉），微信还点名「卡住：run 标题里没写是哪条」。
      之后那一趟自己红了，它按自己的键照样报；绿了，这条工作流就是好的。
      「之后」按 `updated_at`（跑完的时刻）比，不按 `created_at`——判据
      `test_合并前最后一条老标题的run红了_之后新标题的run一来就取代`、
      `test_老标题的红_晚开先跑完的绿不算取代`。
    """
    later_ok: dict[tuple[str, str], list[tuple[str, str, dict]]] = defaultdict(list)
    later_any: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    failed, legacy_failed = [], []
    for run in runs:
        if run.get("status") != "completed" or run.get("conclusion") == "cancelled":
            continue
        wf, at = workflow_of(run), run.get("created_at") or ""
        if wf in RUN_NAME_FIELDS:
            # 老标题的取代按**结束**时刻排（复核 nit）：一趟比它晚 2 秒开、却先跑完的 run，
            # 跑完的那一刻老 run 还没红，证明不了「红了之后好了」
            later_any[wf].append((run.get("updated_at") or "", run))
        if is_legacy_title(run):
            if run.get("conclusion") in FAILURES:
                legacy_failed.append(run)
            continue
        fields = run_name_fields(run)
        if not fields.get("slug") or not fields.get("mode"):
            continue
        key = (wf, fields["slug"])
        if run.get("conclusion") == "success" and fields["mode"] in SUPERSEDED_BY:
            later_ok[key].append((fields["mode"], at, run))
        elif run.get("conclusion") in FAILURES:
            failed.append((run, key, fields["mode"]))
    out: dict = {}
    for run, key, mode in failed:
        at_fail = run.get("created_at") or ""
        by = [(at_ok, ok) for ok_mode, at_ok, ok in later_ok.get(key, ())
              if mode in SUPERSEDED_BY[ok_mode] and at_ok > at_fail]
        if run.get("id") is not None and by:
            out[run["id"]] = min(by, key=lambda x: x[0])[1]  # 最早取代它的那一趟
    for run in legacy_failed:
        at_fail = run.get("updated_at") or ""
        by = [(at, r) for at, r in later_any.get(workflow_of(run), ()) if at > at_fail]
        if run.get("id") is not None and by:
            out[run["id"]] = min(by, key=lambda x: x[0])[1]
    return out


def blocked_key(workflow: str, mode: str | None = None, slug: str | None = None) -> str:
    """一处「阻塞」的身份：工作流文件 ＋ 出片 mode ＋ 片子（`match-reel:render@zverev-sonego`）；
    没有的段就不写（`orchestrate`、`match-reel:cookies`、`explainer@ranking-math`）。
    `blocked_runs` 按它取「最近一条」，`pipeline_health` 按它去重、算 6 小时冷却——
    同一个键，才不会一边说阻塞、一边说没事。

    slug 只认 run-name 按段位读出来的那个（`run_name_fields`），不认 `slug_of` 的启发式：
    `auto-push-reel` 这类的标题是提交信息，拿猜出来的词当键，同一条线的红绿就对不上了。
    账号所有者 2026-09-27 答复 (2)(4)：去重和冷却都按片子算。"""
    key = f"{workflow}:{mode}" if mode else workflow
    return f"{key}@{slug}" if slug else key


#: 派发者是机器人（编排器／队列用 `GH_TOKEN: github.token` 派发 → `github-actions[bot]`）
_BOT_SUFFIX = "[bot]"


def is_unattended(run: dict) -> bool:
    """这趟 run 是不是**无人值守链**跑的（账号所有者 2026-09-27 答复 (1)：只有这种红才推微信）。

    - `event == "schedule"` → 是。⚠️ 要先看 event：schedule run 的 actor 是最后改 cron 的人
      （实测 reel-auto-ready 36352155523 的 actor 是 `robertyang87`）
    - 否则看 `triggering_actor`（重跑时它是点重跑的人，`actor` 还是第一次的派发者），
      没有再看 `actor`：登录名以 `[bot]` 结尾（或 `type == "Bot"`）→ 是，编排器／队列派发的；
      是个人 → 不是，会话或人手动拨的
    - 两个都没有 → 按是：认不出派发者时宁可多推一声，不许把一处无人值守的红静默吞掉
    """
    if run.get("event") == "schedule":
        return True
    who = run.get("triggering_actor") or run.get("actor")
    if not isinstance(who, dict) or not who.get("login"):
        return True
    return str(who["login"]).endswith(_BOT_SUFFIX) or who.get("type") == "Bot"


def which(b: dict) -> str:
    """`match-reel（probe）`：同一个工作流跑的是哪一步。首屏、阶段卡片、微信同一个说法。"""
    wf = str(b.get("workflow") or "")
    return f"{wf}（{b['mode']}）" if b.get("mode") else wf


def blocked_runs(runs, now=None, *, self_run_id=None, known=()) -> list[dict]:
    """「流水线阻塞」的唯一定义：每个受监控的**工作流 × 出片 mode × 片子**
    （`blocked_key`），取 24 小时内最近一条**有结论、不是取消**的 run；它失败了，
    这一处就算阻塞。按最早失败排前。

    ⚠️ 键里有 slug（账号所有者 2026-09-27 答复 (2)）：片子 A 的 render 红了，之后片子 B 的
    render 绿了，A 照样阻塞，直到 A 自己绿了或滚出 24 小时——判据
    `test_阻塞按片子去重_B绿了A照样红`。每一处带 `unattended`（`is_unattended`）：
    看板照旧全显示，微信只推无人值守的（`pipeline_health`）。

    看板首屏和 `pipeline_health` 的微信推送都用它（Q9）。

    ⚠️ 键里必须有 mode（复核 FIX ROUND 2 的 blocking）：阶段卡片按 mode 认阶段
    （`run_stages`），原来这儿却按工作流**文件**只留一条——自动链最常见的形状
    「match-reel render 红了，之后另一条片子的 probe 绿了」里，那条绿的 probe 把红的
    render 顶掉，首屏写「流水线运行正常」，底下渲染／质检两格是红的，微信也不响。
    阶段是 (工作流, mode) 的函数，所以按这个键分组，同一阶段里「最近一条」和阶段卡片
    看到的是同一条——判据 `test_后一条别的mode绿了不许顶掉前一条mode的红`。
    """
    now = now or datetime.now(timezone.utc)
    latest: dict[str, dict] = {}
    replaced = superseded_ids(runs)
    for run in runs:
        wf = workflow_of(run)
        if wf not in MONITORED or is_self(run, self_run_id):
            continue
        if run.get("status") != "completed" or run.get("conclusion") == "cancelled":
            continue
        if run.get("id") in replaced:
            continue  # 同一条片子后来 render 绿了：和取消一样，已经被后一趟取代
        created = parse_time(run.get("created_at"))
        if created is None or created < now - BLOCKED_WINDOW:
            continue
        fields = run_name_fields(run)
        key = blocked_key(wf, fields.get("mode"), fields.get("slug"))
        if key not in latest or (run.get("updated_at") or "") > (latest[key].get("updated_at") or ""):
            latest[key] = run
    out = []
    for run in latest.values():
        if run.get("conclusion") not in FAILURES:
            continue
        wf = workflow_of(run)
        title = run.get("display_title") or run.get("name") or wf
        fields = run_name_fields(run)
        slugless = fields.get("mode") in SLUGLESS_MODES  # 标题里那个默认 slug 也不许被启发式捡回来
        out.append({
            "workflow": wf,
            "mode": fields.get("mode"),
            "key": blocked_key(wf, fields.get("mode"), fields.get("slug")),
            "stages": run_stages(run),
            # 标题是我们写死的 run-name：按段位读；别的标题才退回启发式（不猜）
            "slug": None if slugless else (
                fields.get("slug") or slug_of(title, known, exclude=(run.get("name"),))),
            "title": title,
            "url": run.get("html_url"),
            "at": run.get("updated_at"),
            "created_at": run.get("created_at"),
            # 只决定推不推微信，看板照旧显示（答复 (1)）
            "unattended": is_unattended(run),
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
    # 一个工作流可以有好几处阻塞（match-reel 的 render 和 probe 各红一条）：
    # 「自动任务」那一行指向最早那条失败，不指向恰好最新的那条绿 run
    first_blocked: dict[str, dict] = {}
    for b in blocked:
        first_blocked.setdefault(b["workflow"], b)

    by_workflow = defaultdict(list)
    by_stage = defaultdict(list)
    replaced = superseded_ids(runs)  # 和 blocked_runs 跳的是同一批（SUPERSEDED_BY）
    replaced_in = defaultdict(list)  # 阶段 → 这一格里被取代的红（只在这一格别无 run 时用）
    for run in runs:
        if run.get("id") in replaced:
            for label in run_stages(run):
                replaced_in[label].append(run)
            continue
        by_workflow[workflow_of(run)].append(run)
        for label in run_stages(run):
            by_stage[label].append(run)
    for rows in by_workflow.values():
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)

    stages = []
    for label, _names in WORKFLOW_GROUPS:
        # 出片 run 按 mode 认阶段：match-reel 的 probe 红了是 Spec 这一格红
        failing = [b for b in blocked if label in b["stages"]]
        # 取消的 run 已经被后一趟取代，不代表这一格现在的状态
        candidates = [r for r in by_stage.get(label, []) if r.get("conclusion") != "cancelled"]
        candidates.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        running = [r for r in candidates if r.get("status") != "completed"]
        if failing:
            worst = failing[0]
            # 和首屏、微信同一个说法：「match-reel（probe）」
            stages.append({"label": label, "status": "failure", "detail": which(worst),
                           "slug": worst["slug"], "updated_at": worst["at"], "url": worst["url"]})
        elif running or candidates:
            r = (running or candidates)[0]
            status = "running" if running else run_state(r)[0]
            fields = run_name_fields(r)
            stages.append({"label": label, "status": status,
                           "detail": which({"workflow": workflow_of(r), "mode": fields.get("mode")}),
                           "slug": fields.get("slug"),
                           "updated_at": r.get("updated_at"), "url": r.get("html_url")})
        elif replaced_in.get(label):
            # 这一格只剩被取代的红（narration 红了、同一条 render 绿了）：它的现状是
            # 取代它的那一趟，不是「暂无运行证据」——指过去，说清是被谁取代的。
            # 取代它的那一趟自己红了（老标题的红被一条新标题的红取代），红记在那一趟
            # 自己的阶段上（`blocked` 里有它），这一格不跟着红：卡片和首屏同一个判断
            gone = max(replaced_in[label], key=lambda r: r.get("updated_at") or "")
            by = replaced[gone["id"]]
            fields = run_name_fields(by)
            stages.append({"label": label,
                           "status": "success" if run_state(by)[0] == "success" else "warning",
                           "detail": "已被 " + which({"workflow": workflow_of(by),
                                                     "mode": fields.get("mode")}) + "取代",
                           "slug": fields.get("slug"),
                           "updated_at": by.get("updated_at"), "url": by.get("html_url")})
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
        name = run.get("name") or wf
        title = run.get("display_title") or ""
        row = {
            "label": name, "workflow": wf,
            "detail": title if title and title != name else (run.get("event") or ""),
            "status": status, "status_label": status_label, "updated_at": run.get("updated_at"),
            "url": run.get("html_url"),
        }
        if wf in first_blocked and status != "running":
            # 最新一条是别的 mode 的绿 run 时，红标签要指向真失败的那一条，不指向这条绿的
            b = first_blocked[wf]
            row.update({"status": "failure", "status_label": "失败", "updated_at": b["at"], "url": b["url"],
                        "detail": b["title"] if b["title"] != name else row["detail"]})
        workflow_rows.append(row)
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
