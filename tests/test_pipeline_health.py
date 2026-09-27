from pathlib import Path

from tools.pipeline_health import (
    DEFAULT_WORKFLOWS,
    WorkflowHealth,
    elapsed,
    notification_transition,
    render_report,
)


def test_elapsed_uses_real_timestamps():
    assert elapsed("2026-08-23T00:00:00Z", "2026-08-23T00:02:03Z") == 123


def test_failure_trend_alerts_but_sla_wording_is_warning_only():
    rows = [WorkflowHealth("oncourt-interviews.yml", 5, 0, 5, 1056, 5, True)]
    report, alerts = render_report(rows, [], (7, 2, 609), [])
    assert alerts and "失败率 100%" in alerts[0]
    assert "超线只告警，不阻断 L2、发布或微信推送" in report
    assert not any("600 秒" in item for item in alerts), "SLA miss 不得每小时重复推微信"


def test_healthy_trend_does_not_alert():
    rows = [WorkflowHealth("match-reel.yml", 10, 9, 1, 430, 0)]
    _report, alerts = render_report(rows, [], (10, 0, 430), [])
    assert alerts == []


def test_health_monitor_covers_every_auto_publish_column():
    assert {"auto-push-reel.yml", "auto-push-interview.yml",
            "auto-push-explainer.yml"} <= set(DEFAULT_WORKFLOWS)


def test_health_monitor_covers_the_explainer_line_and_the_only_cron_producer():
    """解说片线原来整个不在监控里——`explainer.yml` 是它唯一的出片入口。

    ⚠️ **这条判据 2026-09-15 收窄了一档，而收窄的过程本身值得记。**

    原文断言 `{"explainer.yml", "knowledge-adhoc.yml"} <= set(DEFAULT_WORKFLOWS)`，
    理由是「`knowledge-adhoc.yml` 是全库唯一的定时产出线」。那条线随瘦身停产、
    **工作流文件删掉了**，于是这个前提不成立了。

    ⚠️⚠️ **而它在那次删除时一声都没吭**：它只查「这个名字在不在名单里」，
    不查「这个文件在不在」——名单和文件同时腐烂，它两头都够不着。于是监控表
    带着一个指向不存在工作流的条目跑了下去，**拿回来的永远是空，而「空」和
    「这条线很健康」长得一模一样**。

    所以真正管用的那一半在 `test_监控名单不许点名不存在的工作流`：
    **按文件存不存在推导，不维护名字白名单**。这条只留它管得住的那件事——
    解说片那条出片入口不许再从监控里掉出去。
    """
    assert "explainer.yml" in DEFAULT_WORKFLOWS


def test_stale_publication_is_reported():
    rows = [WorkflowHealth("match-reel.yml", 3, 3, 0, 420, 0)]
    report, alerts = render_report(rows, [], (3, 0, 420), ["demo: sending 已持续 2.0h"])
    assert "发布账本待核实" in report
    assert any("sending" in item for item in alerts)


def test_kick_render_without_checkout_passes_repo_explicitly():
    body = Path(".github/workflows/oncourt-interviews.yml").read_text(encoding="utf-8")
    block = body.split("- name: 立即提升并派发本批赛后开麦", 1)[1]
    assert 'gh workflow run interview-auto-render.yml' in block
    assert '--repo "$GITHUB_REPOSITORY"' in block, (
        "kick-render 没有 checkout；gh 缺 --repo 会报 not a git repository")


def test_oncourt_only_serializes_collect_and_commits_cursor_and_claims():
    body = Path(".github/workflows/oncourt-interviews.yml").read_text(encoding="utf-8")
    before_jobs, jobs = body.split("jobs:", 1)
    assert "concurrency:" not in before_jobs, "workflow 级锁会让长 ASR 阻住下一轮资源扫描"
    collect = jobs.split("  draft:", 1)[0]
    assert "group: oncourt-interviews-collect" in collect
    assert "data/oncourt_scan_state.json" in collect
    assert "data/interview_candidate_claims.json" in collect


# ── 编排器产出率：这一项测的是**产出**，不是绿不绿（2026-08-25）──────────────
#
# 来路：`orchestrate` 定时跑了 330 趟，`conclusion` 趟趟 `success`，而
# `data/orchestration_state.json` 至今是 `{"dispatched": {}}`——一条 run 都没
# 点过。本文件原来只统计工作流的成功率和耗时，于是它给这条线打的是满分：
# **绿正是它坏掉的样子，它每一趟都成功地什么都没做。**
# 和 `sla_health` 那次幸存者偏差（只统计渲成了的趟）是同一个病高一层。

def test_健康报表要盯编排器有没有产出不是绿不绿(tmp_path):
    from datetime import datetime, timezone  # noqa: PLC0415

    from tools.pipeline_health import orchestrator_productivity  # noqa: PLC0415

    now = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)

    # ① 从来没点过（今天线上的真实状态）→ 报「从来没有」并告警
    never = tmp_path / "never.json"
    never.write_text('{"dispatched": {}}', encoding="utf-8")
    assert orchestrator_productivity(now, never) == (None, None)
    report, alerts = render_report([], [], (0, 0, 0.0), [],
                                   orchestrator_productivity(now, never))
    assert "从来没有真正点过" in report
    assert any("从来没点过 run" in a for a in alerts)

    # ② 刚点过 → 不告警
    fresh = tmp_path / "fresh.json"
    fresh.write_text('{"dispatched": {}, "last_dispatch_at": '
                     '"2026-08-25T11:00:00Z"}', encoding="utf-8")
    at, hours = orchestrator_productivity(now, fresh)
    assert at == "2026-08-25T11:00:00Z" and abs(hours - 1.0) < 1e-6
    report, alerts = render_report([], [], (0, 0, 0.0), [], (at, hours))
    assert "最近一次点 run" in report
    assert not any("编排器" in a for a in alerts), "刚点过就告警会变成告警风暴"

    # ③ 哑了一整天 → 告警。⚠️ 门槛不能只验 ① —— 只有 ① 的话，把这一支整个
    #    删掉测试照样绿，而「哑了三天」正是这条线真正会出现的样子。
    stale = tmp_path / "stale.json"
    stale.write_text('{"dispatched": {}, "last_dispatch_at": '
                     '"2026-08-22T12:00:00Z"}', encoding="utf-8")
    at, hours = orchestrator_productivity(now, stale)
    assert hours == 72.0
    _, alerts = render_report([], [], (0, 0, 0.0), [], (at, hours))
    assert any("没点过 run" in a for a in alerts)

    # ④ **不许拿 `dispatched` 里有没有条目来判**：条目 7 天就过期清掉，
    #    「从来没点过」和「点过但都过期了」在它上面分不开。
    expired = tmp_path / "expired.json"
    expired.write_text('{"dispatched": {"a-b": {"date": "2026-08-25"}}}',
                       encoding="utf-8")
    assert orchestrator_productivity(now, expired) == (None, None), \
        "有条目就当成「点过」了——那正是这个字段要分开的两种情况"


def test_健康报表真的把编排器那一项传进去了():
    """⚠️ 「写了不等于跑过」：函数写对了、`main()` 不传，报表上永远看不见。"""
    body = Path("tools/pipeline_health.py").read_text("utf-8")
    call = body[body.index("report, alerts = render_report("):]
    assert "orchestrator_productivity()" in call[:260], \
        "main() 没把编排器产出率传给 render_report——这一项等于没装"


def test_健康工作流真的检出编排状态并跨run保存微信状态():
    body = Path(".github/workflows/pipeline-health.yml").read_text("utf-8")
    checkout = body.split("actions/checkout@v4", 1)[1].split("- name:", 1)[0]
    assert "data/orchestration_state.json" in checkout, (
        "脚本会读编排状态，但 sparse checkout 没检出它——"
        "读不到和从来没 dispatch 会长得一样，并且每小时误报一次")
    assert "actions/cache/restore@v4" in body
    assert "actions/cache/save@v4" in body
    assert "steps.health.outputs.notify == 'true'" in body


def test_微信只在异常变化和真正恢复时发一次(tmp_path):
    state = tmp_path / "alert.json"

    notify, title, message = notification_transition(
        ["编排器已 25 小时没点过 run（阈值 24h）"], state)
    assert notify and "趋势异常" in title and "25 小时" in message

    # 时间每小时增长不是新故障，不能再轰一条微信。
    notify, _title, _message = notification_transition(
        ["编排器已 26 小时没点过 run（阈值 24h）"], state)
    assert not notify

    # 加入一类真正不同的异常要重新通知。
    notify, title, message = notification_transition([
        "编排器已 27 小时没点过 run（阈值 24h）",
        "match-reel.yml：近 10 次失败率 50%，连续失败 3",
    ], state)
    assert notify and "趋势异常" in title and "match-reel" in message

    # 全部恢复只发一次；下一班仍健康时不重复发恢复消息。
    notify, title, message = notification_transition([], state)
    assert notify and "恢复正常" in title and "此前异常已解除" in message
    assert notification_transition([], state)[0] is False


def test_持久故障超过一小时仍是active而不是假恢复():
    row = WorkflowHealth("match-reel.yml", 10, 5, 5, 400, 4,
                         latest_failure=True)
    _report, alerts = render_report([row], [], (0, 0, 0), [])
    assert any("match-reel.yml" in item for item in alerts)


def test_取消的run不算失败():
    """**`cancelled` 不是失败，而这条报表原来把它当失败算。**

    监控名单里的 `interview-clip.yml` / `explainer.yml` 都开着
    `cancel-in-progress: true`——同一个 slug 重渲一版，旧 run 会被**主动取消**。
    于是一条片子返工三次，报表就报「近 10 次失败率 50%、连续失败 3」。

    ⚠️ **一条天天喊狼来了的告警，最后的下场是没人看**，而它要守的那些真失败
    就藏在噪音里。这是从 #573 移植过来的（那条 PR 基于 2026-09-15 历史重写
    之前的 main，**不能 merge**——合并会把整份旧历史重新挂回 main）。
    """
    from tools.pipeline_health import workflow_health  # noqa: PLC0415

    class _FakeApi:
        def __init__(self, concs):
            self._concs = concs

        def get(self, path):
            if "/runs?" in path:
                return {"workflow_runs": [
                    {"id": i, "conclusion": c,
                     "created_at": "2026-09-15T00:00:00Z",
                     "updated_at": "2026-09-15T00:05:00Z"}
                    for i, c in enumerate(self._concs)]}
            return {"jobs": []}

    # 三次返工取消 + 一次成功：一个失败都没有
    h, _ = workflow_health(_FakeApi(["cancelled", "cancelled", "cancelled", "success"]),
                           "explainer.yml", limit=10, step_runs=0)
    assert h.failures == 0, f"取消被当成失败了：failures={h.failures}"
    assert h.consecutive_failures == 0, (
        f"取消把连续失败撑起来了：{h.consecutive_failures}——正是 #573 报的那个假警报")
    assert not h.latest_failure, "最新一条是取消，不该报成仍在失败"

    # ⚠️ 反向那一头：取消**不许遮住**它后面的真失败
    h2, _ = workflow_health(_FakeApi(["cancelled", "failure", "failure", "success"]),
                            "explainer.yml", limit=10, step_runs=0)
    assert h2.failures == 2, f"真失败被一起吞了：failures={h2.failures}"
    assert h2.consecutive_failures == 2, (
        f"最新一条是取消就把后面的连续失败清零了：{h2.consecutive_failures}")
    assert h2.latest_failure, "取消之后紧接着就是真失败，必须仍报异常"


def test_监控名单不许点名不存在的工作流():
    """**删了工作流不改它的消费者**——这个仓库的老形状，2026-09-15 又犯一次。

    `knowledge-adhoc.yml`（图文知识帖，全库唯一的定时产出线）随瘦身停产、
    工作流文件删掉了，而 `DEFAULT_WORKFLOWS` 还在点名它。监控表点名一个不存在
    的工作流，**拿回来的永远是空**——而「空」和「这条线很健康」长得一模一样。

    判据**自己推导，不维护白名单**：名单里每一条都必须在 `.github/workflows/`
    下真的存在。
    """
    import pathlib  # noqa: PLC0415
    import re  # noqa: PLC0415

    src = pathlib.Path("tools/pipeline_health.py").read_text("utf-8")
    block = re.search(r"DEFAULT_WORKFLOWS = \((.*?)^\)", src, re.S | re.M)
    assert block, "DEFAULT_WORKFLOWS 找不到了——判据的主语没了"
    # ⚠️ 只认真正的字符串项，不扫注释：这个仓库的注释正是教训的存放处，
    # 上面那段就写着被删掉的 `knowledge-adhoc.yml`，连注释一起扫会把
    # 「把坑记下来」判成「又踩了这个坑」。
    body = "\n".join(ln for ln in block.group(1).splitlines()
                     if not ln.lstrip().startswith("#"))
    listed = re.findall(r'"([^"]+\.yml)"', body)
    assert len(listed) >= 6, f"只解析出 {len(listed)} 条，判据可能失效了"

    missing = [w for w in listed
               if not (pathlib.Path(".github/workflows") / w).exists()]
    assert not missing, (
        f"监控名单点名了不存在的工作流 {missing}——拿回来的永远是空，"
        "而「空」和「这条线很健康」长得一模一样")


# ── 流水线阻塞 → 微信（账号所有者 Q9，2026-09-27）─────────────────────────────
#
# 看板在 github.io，他在国内打不开；阻塞摘要推到微信、网页留作备用。
# 扩的是这条已有的告警链（同一步 PushPlus、同一份跨 run 去重状态），不另起一条。

def _fake_github(runs, global_runs=None):
    """GitHub API 的桩：按工作流取 run（`actions/workflows/<文件>.yml/runs?…created=>=…`，
    `monitored_runs` 走的那个端点）按 `path` 分给各条工作流、只给第一页、按 `created`
    过滤；全仓那个列表（`actions/runs?`）给 `global_runs`（不给就是全部）；
    `workflow_health` 那条（不带 `created=`）一律空——趋势那一半不是这几条测的东西。"""
    import re  # noqa: PLC0415
    import urllib.parse  # noqa: PLC0415

    def get(self, path):
        if path.startswith("actions/runs?"):
            return {"workflow_runs": list(runs if global_runs is None else global_runs)}
        m = re.match(r"actions/workflows/([^/?]+)\.yml/runs\?(.*)$", path)
        if m and "created=" in m.group(2):
            q = urllib.parse.parse_qs(m.group(2))
            if q.get("page", ["1"])[0] != "1":
                return {"workflow_runs": []}
            since = q["created"][0].removeprefix(">=")
            return {"workflow_runs": [r for r in runs
                                      if r["path"] == f".github/workflows/{m.group(1)}.yml"
                                      and r["created_at"] >= since]}
        return {"workflow_runs": [], "jobs": []}
    return get


def _blocked(workflow="match-reel", slug="bu-majchrzak-hangzhou-2026-r2", stages=("渲染", "质检")):
    return {"workflow": workflow, "stages": list(stages), "slug": slug,
            "url": f"https://github.com/o/r/actions/runs/{abs(hash(workflow)) % 1000}",
            "title": workflow, "at": "2026-09-27T08:00:00Z"}


def test_看板转阻塞时推一条短摘要_只在转入时推(tmp_path):
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from tools.pipeline_health import blocked_transition  # noqa: PLC0415

    state = tmp_path / "alert.json"
    t0 = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
    b = _blocked()

    notify, title, message = blocked_transition([b], state, t0)
    assert notify and "阻塞" in title and "渲染" in title
    assert "bu-majchrzak-hangzhou-2026-r2" in message and b["url"] in message
    assert "打开失败的 run" in message and "\n" not in message, "GITHUB_OUTPUT 只认一行"
    assert len(message) < 400, "要的是短摘要"

    # 还阻塞着：不再推（每小时一班，不许每小时轰一条）
    assert blocked_transition([b], state, t0 + timedelta(hours=1))[0] is False
    # 恢复：不推（他要的是「卡住了」这一声）
    assert blocked_transition([], state, t0 + timedelta(hours=2))[0] is False
    # 6 小时内又红回来（来回抖）：冷却期内不推
    assert blocked_transition([b], state, t0 + timedelta(hours=3))[0] is False
    assert blocked_transition([b], state, t0 + timedelta(hours=5))[0] is False
    # 过了冷却还红着：推迟的那一声补上（原来记成已知、永远不推——FIX ROUND 1 的 nit）
    assert blocked_transition([b], state, t0 + timedelta(hours=10))[0] is True, "推迟不是丢"
    assert blocked_transition([b], state, t0 + timedelta(hours=11))[0] is False, "补过一次就是已知"
    # 恢复、过了冷却再红：是新的一次转入，推
    blocked_transition([], state, t0 + timedelta(hours=12))
    assert blocked_transition([b], state, t0 + timedelta(hours=16, minutes=30))[0] is True

    # 另一条工作流也红了，但离上一条阻塞推送不到 30 分钟：先压着、不丢
    other = _blocked("orchestrate", None, ("编排",))
    t1 = t0 + timedelta(hours=16, minutes=40)
    assert blocked_transition([b, other], state, t1)[0] is False
    notify, title, message = blocked_transition([b, other], state, t1 + timedelta(minutes=25))
    assert notify and "编排" in title and "run 标题里没写是哪条" in message, "slug 不知道就照实说"
    assert "另有 1 条" in message and "bu-majchrzak" not in message, "只报新转入的，旧的一句带过"


def test_阻塞推送和趋势告警共用一份状态文件互不覆盖(tmp_path):
    import json  # noqa: PLC0415

    from tools.pipeline_health import blocked_transition  # noqa: PLC0415

    state = tmp_path / "alert.json"
    notification_transition(["编排器已 25 小时没点过 run（阈值 24h）"], state)
    blocked_transition([_blocked()], state)
    notification_transition(["编排器已 26 小时没点过 run（阈值 24h）"], state)
    saved = json.loads(state.read_text("utf-8"))
    assert saved["active_keys"] == ["orchestrator"]
    assert saved["blocked_active"] == ["match-reel"], "趋势那一步把阻塞的去重状态冲掉了——会每小时重推"
    assert blocked_transition([_blocked()], state)[0] is False


def test_健康检查的阻塞定义就是看板那一份_工作流检出了它():
    """「阻塞」写两份，看板说阻塞、微信不响（或反过来）只是时间问题。"""
    import tools.pipeline_health as ph  # noqa: PLC0415

    src = Path(ph.dashboard.__file__).resolve()
    assert src == Path("tools/build_dashboard_snapshot.py").resolve()
    body = Path("tools/pipeline_health.py").read_text("utf-8")
    assert "dashboard.blocked_runs(runs)" in body
    assert "def blocked_runs" not in body, "不许在这儿另写一份定义"
    wf = Path(".github/workflows/pipeline-health.yml").read_text("utf-8")
    checkout = wf.split("actions/checkout@v4", 1)[1].split("- name:", 1)[0]
    assert "tools/build_dashboard_snapshot.py" in checkout, (
        "逐文件稀疏检出漏了它，runner 上 import 直接炸——监控线自己常年红")


def test_main把阻塞摘要写进GITHUB_OUTPUT(tmp_path, monkeypatch):
    """「写了不等于跑过」：`main()` 真的拉了 run、算了阻塞、把标题和一行摘要交给
    推送那一步（`steps.health.outputs.notify == 'true'` 才推）。"""
    import json  # noqa: PLC0415
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    import tools.pipeline_health as ph  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    iso = lambda m: (now - timedelta(minutes=m)).isoformat().replace("+00:00", "Z")  # noqa: E731
    failing = {"id": 8, "name": "match-reel", "path": ".github/workflows/match-reel.yml",
               "status": "completed", "conclusion": "failure", "created_at": iso(20),
               "updated_at": iso(10), "html_url": "https://github.com/o/r/actions/runs/8",
               "display_title": "match-reel · render · bu-majchrzak-hangzhou-2026-r2"}

    monkeypatch.setattr(ph.GitHubAPI, "get", _fake_github([failing]))
    monkeypatch.setattr(ph, "sla_health", lambda: (0, 0, 0.0))
    monkeypatch.setattr(ph, "stale_publications", lambda: [])
    monkeypatch.setattr(ph, "orchestrator_productivity", lambda: ("2026-09-27T00:00:00Z", 1.0))
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    state = tmp_path / "state.json"
    assert ph.main(["--repo", "o/r", "--token", "x", "--workflows", "match-reel.yml",
                    "--step-runs", "0", "--alert-state", str(state)]) == 0
    got = dict(line.split("=", 1) for line in out.read_text("utf-8").splitlines())
    assert got["notify"] == "true" and "阻塞" in got["title"]
    assert "bu-majchrzak-hangzhou-2026-r2" in got["message"] and "runs/8" in got["message"]
    # 去重的键是「工作流 × mode」（`blocked_key`），和看板取「最近一条」的键是同一个
    assert json.loads(state.read_text("utf-8"))["blocked_active"] == ["match-reel:render"]
    # 下一班还是同一条阻塞：不再推
    out.write_text("")
    ph.main(["--repo", "o/r", "--token", "x", "--workflows", "match-reel.yml",
             "--step-runs", "0", "--alert-state", str(state)])
    got = dict(line.split("=", 1) for line in out.read_text("utf-8").splitlines())
    assert got["notify"] == "false"


def test_两段的slug也要进微信摘要_不许说标题里没写(tmp_path, monkeypatch):
    """复核 FIX ROUND 1 的 blocking：`main()` 调 `blocked_runs(runs)` 不给 `known`
    （这条线的稀疏检出里没有 spec 清单），原来 `slug_of` 只认三段以上的连字符词——
    自动链 pending 草稿 126 条里 114 条是两段（`zverev-sonego`），解说片账本 15 份里
    7 份也是（`ranking-math`）。于是微信说「run 标题里没写是哪条」，而 run-name
    明明写了——Q9 要的「哪条卡住」没答上，还说了一句假话。"""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    import tools.pipeline_health as ph  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    iso = lambda m: (now - timedelta(minutes=m)).isoformat().replace("+00:00", "Z")  # noqa: E731

    def run(rid, stem, name, title):
        return {"id": rid, "name": name, "path": f".github/workflows/{stem}.yml",
                "status": "completed", "conclusion": "failure", "created_at": iso(20 + rid),
                "updated_at": iso(10 + rid), "html_url": f"https://github.com/o/r/actions/runs/{rid}",
                "display_title": title}

    runs = [run(1, "match-reel", "match-reel", "match-reel · probe · zverev-sonego"),
            run(2, "explainer", "explainer-video", "explainer-video · ranking-math")]

    monkeypatch.setattr(ph.GitHubAPI, "get", _fake_github(runs))
    monkeypatch.setattr(ph, "sla_health", lambda: (0, 0, 0.0))
    monkeypatch.setattr(ph, "stale_publications", lambda: [])
    monkeypatch.setattr(ph, "orchestrator_productivity", lambda: ("2026-09-27T00:00:00Z", 1.0))
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert ph.main(["--repo", "o/r", "--token", "x", "--workflows", "match-reel.yml",
                    "--step-runs", "0", "--alert-state", str(tmp_path / "state.json")]) == 0
    got = dict(line.split("=", 1) for line in out.read_text("utf-8").splitlines())
    assert got["notify"] == "true"
    assert "zverev-sonego" in got["message"] and "ranking-math" in got["message"], got["message"]
    assert ph.NO_SLUG not in got["message"], got["message"]
    # probe 红了是 Spec 卡住，不是「渲染 / 质检」；mode 也写进去
    assert "Spec · match-reel（probe） 失败" in got["message"], got["message"]
    assert "Spec" in got["title"]


# ── FIX ROUND 2：阻塞按「工作流 × mode」认 ───────────────────────────────────
def test_render红了之后别的片子probe绿了_微信照样推(tmp_path, monkeypatch):
    """复核 FIX ROUND 2 的 blocking 在微信这一头的样子：`blocked_runs` 原来按工作流
    文件只留最近一条，match-reel 的 render 红了、之后另一条片子的 probe 绿了，
    这一班就算「没有阻塞」——看板底下两格红着，微信一声不响（Q9 要的正是这一声）。"""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    import tools.pipeline_health as ph  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    iso = lambda m: (now - timedelta(minutes=m)).isoformat().replace("+00:00", "Z")  # noqa: E731

    def run(rid, minutes, conclusion, title):
        return {"id": rid, "name": "match-reel", "path": ".github/workflows/match-reel.yml",
                "status": "completed", "conclusion": conclusion, "created_at": iso(minutes + 5),
                "updated_at": iso(minutes), "html_url": f"https://github.com/o/r/actions/runs/{rid}",
                "display_title": title}

    runs = [run(5, 5, "success", "match-reel · probe · zverev-sonego"),       # 最新的一条是绿的
            run(30, 30, "failure", "match-reel · render · bu-majchrzak-hangzhou-2026-r2")]

    monkeypatch.setattr(ph.GitHubAPI, "get", _fake_github(runs))
    monkeypatch.setattr(ph, "sla_health", lambda: (0, 0, 0.0))
    monkeypatch.setattr(ph, "stale_publications", lambda: [])
    monkeypatch.setattr(ph, "orchestrator_productivity", lambda: ("2026-09-27T00:00:00Z", 1.0))
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert ph.main(["--repo", "o/r", "--token", "x", "--workflows", "match-reel.yml",
                    "--step-runs", "0", "--alert-state", str(tmp_path / "state.json")]) == 0
    got = dict(line.split("=", 1) for line in out.read_text("utf-8").splitlines())
    assert got["notify"] == "true", got
    assert "bu-majchrzak-hangzhou-2026-r2" in got["message"] and "runs/30" in got["message"], got["message"]
    assert "渲染 / 质检 · match-reel（render） 失败" in got["message"], got["message"]
    assert "zverev-sonego" not in got["message"], "绿的那条 probe 不是阻塞"


def test_同一个工作流另一个mode也红了_是新的一处_不许当成已知吞掉(tmp_path):
    """去重按「工作流 × mode」：match-reel 的 render 已经报过，之后它的 probe 也红了——
    那是另一处卡住（Spec），要推；而 render 那条还红着，只一句带过、不重报。"""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from tools.pipeline_health import blocked_transition  # noqa: PLC0415

    state = tmp_path / "alert.json"
    t0 = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
    render = {**_blocked(), "mode": "render"}
    probe = {**_blocked(slug="zverev-sonego", stages=("Spec",)), "mode": "probe"}
    assert blocked_transition([render], state, t0)[0] is True
    notify, title, message = blocked_transition([render, probe], state, t0 + timedelta(hours=1))
    assert notify and "Spec" in title, (notify, title)
    assert "match-reel（probe）" in message and "zverev-sonego" in message, message
    assert "bu-majchrzak" not in message and "另有 1 条" in message, message
    # 两处都还红着：下一班不再推
    assert blocked_transition([render, probe], state, t0 + timedelta(hours=2))[0] is False


# ── 复核 FIX ROUND 1（第二轮复核）：滚出全仓最近 100 条的失败、推迟不是丢 ────────────
def test_失败滚出全仓最近100条_按工作流取回来照样推(tmp_path, monkeypatch):
    """复核的 blocking：`main()` 原来只取**全仓**最近 100 条 run——忙时只回溯 80~119 分钟
    （pages 31%、ci 25%），而 pipeline-health 的「每小时」一班实际 145~402 分钟一趟。
    09:00 一条没人重试的 render 红了，14:19 那一班全仓列表只回到 12:00——按
    `blocked_runs` 自己的定义它仍是 `match-reel:render` 最近的一条，微信却一声不响。
    这里全仓列表是 100 条更新的 ci，失败只有按工作流取才拿得回来：必须推。"""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    import tools.pipeline_health as ph  # noqa: PLC0415

    now = datetime.now(timezone.utc)
    iso = lambda m: (now - timedelta(minutes=m)).isoformat().replace("+00:00", "Z")  # noqa: E731
    failing = {"id": 900, "name": "match-reel", "path": ".github/workflows/match-reel.yml",
               "status": "completed", "conclusion": "failure", "created_at": iso(5 * 60 + 25),
               "updated_at": iso(5 * 60 + 19), "html_url": "https://github.com/o/r/actions/runs/900",
               "display_title": "match-reel · render · bu-majchrzak-hangzhou-2026-r2"}
    ci = [{"id": 1000 + i, "name": "ci", "path": ".github/workflows/ci.yml", "status": "completed",
           "conclusion": "success", "created_at": iso(i), "updated_at": iso(i),
           "html_url": f"https://github.com/o/r/actions/runs/{1000 + i}", "display_title": "ci"}
          for i in range(100)]
    monkeypatch.setattr(ph.GitHubAPI, "get", _fake_github([failing, *ci], global_runs=ci))
    monkeypatch.setattr(ph, "sla_health", lambda: (0, 0, 0.0))
    monkeypatch.setattr(ph, "stale_publications", lambda: [])
    monkeypatch.setattr(ph, "orchestrator_productivity", lambda: ("2026-09-27T00:00:00Z", 1.0))
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert ph.main(["--repo", "o/r", "--token", "x", "--workflows", "match-reel.yml",
                    "--step-runs", "0", "--alert-state", str(tmp_path / "state.json")]) == 0
    got = dict(line.split("=", 1) for line in out.read_text("utf-8").splitlines())
    assert got["notify"] == "true", got
    assert "bu-majchrzak-hangzhou-2026-r2" in got["message"] and "runs/900" in got["message"], got

    # 24 小时之外的不算（和 `blocked_runs` 的窗口是同一个）
    old = {**failing, "id": 901, "created_at": iso(25 * 60), "updated_at": iso(25 * 60 - 5)}
    monkeypatch.setattr(ph.GitHubAPI, "get", _fake_github([old, *ci], global_runs=ci))
    out.write_text("")
    ph.main(["--repo", "o/r", "--token", "x", "--workflows", "match-reel.yml",
             "--step-runs", "0", "--alert-state", str(tmp_path / "state2.json")])
    got = dict(line.split("=", 1) for line in out.read_text("utf-8").splitlines())
    assert got["notify"] == "false", got


def test_按工作流取run_每条受监控的都问到了_翻页有顶():
    """`monitored_runs` 是看板和健康检查共用的那一份：14 条受监控的工作流每条都问、
    都带 24 小时的 `created` 过滤；一页满了才翻，翻到顶还满就出声，不静默截断。"""
    from datetime import datetime, timezone  # noqa: PLC0415

    import tools.pipeline_health as ph  # noqa: PLC0415

    d = ph.dashboard
    now = datetime(2026, 9, 27, 14, 19, 12, tzinfo=timezone.utc)
    asked = []

    def get(path):
        asked.append(path)
        if path.startswith("actions/workflows/match-reel.yml/"):
            base = 100 * int(path.split("&page=")[1].split("&")[0])
            return {"workflow_runs": [{"id": base + i} for i in range(d.RUNS_PER_PAGE)]}
        return {"workflow_runs": [{"id": 1}]}  # 同一个 id 各条都给：按 id 合并

    runs = d.monitored_runs(get, now)
    wfs = {p.split("/")[2].removesuffix(".yml") for p in asked}
    assert wfs == d.MONITORED, wfs ^ d.MONITORED
    assert all("created=%3E%3D2026-09-26T14:19:12Z" in p for p in asked), asked[:2]
    reel = [p for p in asked if "/match-reel.yml/" in p]
    assert len(reel) == d.MAX_PAGES, reel
    assert len(runs) == len({r["id"] for r in runs}), "按 id 合并"


def test_冷却期内红回来是推迟不是丢_过了冷却还红就推(tmp_path):
    """复核的 nit，复现原样：08:00 render A 红了（推过）、09:00 片子 B 的 render 绿了、
    10:00 片子 C 的 render 红了一直卡着。去重键是「工作流 × mode」、没有 slug，
    C 落在 A 那一声的 6 小时冷却里——原来记成已知，10:00／11:00／16:00／22:00／28:00
    一次都不推，他收到的唯一一条微信点的是 A。冷却是**推迟**：过了冷却还红着就推，点名 C。"""
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from tools.pipeline_health import blocked_transition  # noqa: PLC0415

    state = tmp_path / "alert.json"
    t0 = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
    a = {**_blocked(slug="alpha-beta-r1"), "mode": "render"}
    c = {**_blocked(slug="gamma-delta-r1"), "mode": "render"}
    assert blocked_transition([a], state, t0)[0] is True
    assert blocked_transition([], state, t0 + timedelta(hours=1))[0] is False   # B 的 render 绿了
    assert blocked_transition([c], state, t0 + timedelta(hours=2))[0] is False, "冷却期内先压着"
    assert blocked_transition([c], state, t0 + timedelta(hours=3))[0] is False
    notify, _title, message = blocked_transition([c], state, t0 + timedelta(hours=8))
    assert notify and "gamma-delta-r1" in message and "alpha-beta-r1" not in message, (notify, message)
    # 补过一次就是已知：之后每一班不再轰
    for h in (14, 20):
        assert blocked_transition([c], state, t0 + timedelta(hours=h))[0] is False


def test_按工作流取run_一次瞬时失败重试一次_两次都失败才抛():
    """复核 FIX ROUND 2 的 nit：按工作流取之后一班多 14 次调用，任何一次读失败都让这一班红、
    下一班把「监控」当阻塞推一条微信。一次瞬时的 502 先等一下重试一次；两次都失败照样抛——
    「读不到」≠「健康」这条不变。"""
    from datetime import datetime, timezone  # noqa: PLC0415

    import pytest  # noqa: PLC0415

    import tools.pipeline_health as ph  # noqa: PLC0415

    d = ph.dashboard
    now = datetime(2026, 9, 27, 14, 19, 12, tzinfo=timezone.utc)
    slept, calls = [], []

    def flaky(path):
        calls.append(path)
        if "/match-reel.yml/" in path and calls.count(path) == 1:
            raise RuntimeError("GitHub API 读取失败：502 Bad Gateway")
        return {"workflow_runs": [{"id": len(calls)}]}

    try:
        runs = d.monitored_runs(flaky, now, sleep=slept.append)
    except RuntimeError as exc:
        pytest.fail(f"一次瞬时 502 就让整班失败——没有重试：{exc}")
    assert slept == [d.RETRY_SLEEP_SECONDS], slept
    assert sum("/match-reel.yml/" in p for p in calls) == 2
    assert len(runs) == len(d.MONITORED), "重试之后每条工作流都拿到了"

    calls.clear()
    slept.clear()

    def down(path):
        calls.append(path)
        if "/match-reel.yml/" in path:
            raise RuntimeError("GitHub API 读取失败：502 Bad Gateway")
        return {"workflow_runs": []}

    with pytest.raises(RuntimeError):
        d.monitored_runs(down, now, sleep=slept.append)
    assert sum("/match-reel.yml/" in p for p in calls) == 2, "只重试一次，不无限重试"
    assert slept == [d.RETRY_SLEEP_SECONDS]


def test_健康检查不许被后来的一班掐掉_推过没存状态会重推():
    """复核 FIX ROUND 2 的 nit：三个宿主都会叫醒 pipeline-health，一趟迟到的 schedule 落在
    「PushPlus 推过、actions/cache/save 还没跑」之间把它掐掉，告警状态没存下，下一班同一条
    阻塞再推一遍。排队只多等几分钟。"""
    import re  # noqa: PLC0415

    body = Path(".github/workflows/pipeline-health.yml").read_text("utf-8")
    block = body.split("\nconcurrency:", 1)[1].split("\njobs:", 1)[0]
    assert re.search(r"^\s+group:\s*pipeline-health\s*$", block, re.M), block
    assert re.search(r"^\s+cancel-in-progress:\s*false\s*$", block, re.M), block
