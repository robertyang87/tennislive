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
    """解说片线原来整个不在监控里；`knowledge-adhoc.yml` 是全库唯一的定时
    产出线，它连红六天（2026-08-26 之前）报表一个字没说。"""
    assert {"explainer.yml", "knowledge-adhoc.yml"} <= set(DEFAULT_WORKFLOWS)


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
