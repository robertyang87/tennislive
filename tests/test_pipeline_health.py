from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.pipeline_health import (
    DEFAULT_WORKFLOWS,
    WorkflowHealth,
    elapsed,
    render_report,
    workflow_health,
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


def test_superseded_cancellations_are_visible_but_do_not_trigger_failure_alert():
    rows = [WorkflowHealth(
        "match-reel.yml", 10, 5, 2, 317.9, 2, True, cancellations=3)]
    report, alerts = render_report(rows, [], (10, 0, 317.9), [])
    assert alerts == []
    assert "| match-reel.yml | 10 | 5 | 3 | 29%" in report
    assert "排除 `cancelled`" in report


class _FakeAPI:
    def __init__(self, runs: list[dict]):
        self.runs = runs
        self.job_run_ids: list[int] = []

    def get(self, path: str) -> dict:
        if "/runs?" in path:
            return {"workflow_runs": self.runs}
        if path.startswith("actions/runs/"):
            self.job_run_ids.append(int(path.split("/")[2]))
            return {"jobs": []}
        raise AssertionError(path)


def _ago(now: datetime, seconds: int) -> str:
    return (now - timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def test_workflow_health_ignores_cancelled_runs_without_hiding_real_failures():
    now = datetime.now(timezone.utc)
    runs = [
        {"id": 5, "conclusion": "cancelled",
         "created_at": _ago(now, 700), "updated_at": _ago(now, 100)},
        {"id": 4, "conclusion": "failure",
         "created_at": _ago(now, 400), "updated_at": _ago(now, 300)},
        {"id": 3, "conclusion": "cancelled",
         "created_at": _ago(now, 900), "updated_at": _ago(now, 500)},
        {"id": 2, "conclusion": "failure",
         "created_at": _ago(now, 800), "updated_at": _ago(now, 700)},
        {"id": 1, "conclusion": "success",
         "created_at": _ago(now, 1000), "updated_at": _ago(now, 900)},
    ]
    api = _FakeAPI(runs)

    health, steps = workflow_health(api, "match-reel.yml", limit=10, step_runs=3)

    assert health.runs == 5
    assert health.cancellations == 2
    assert health.evaluated_runs == 3
    assert health.successes == 1
    assert health.failures == 2
    assert health.failure_rate == 2 / 3
    assert health.consecutive_failures == 2
    assert health.latest_failure_recent is True
    assert health.median_seconds == 100
    assert api.job_run_ids == [4, 2, 1], "慢步骤诊断不应再抓已取消的旧渲染"
    assert steps == []


def test_health_monitor_covers_every_auto_publish_column():
    assert {"auto-push-reel.yml", "auto-push-interview.yml",
            "auto-push-explainer.yml"} <= set(DEFAULT_WORKFLOWS)


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
