"""定时工作流的开关与告警规则（CLAUDE.md：规则要落成测试）。

2026-07-25 审查确认的两类静默故障：
- daily.yml 把视频开关硬编码成字面量 'off'，仓库设置里无法打开，
  07-24 起视频"静默消失"；
- flash.yml / news-radar.yml 失败与空产零告警，诊断只存在于会过期的
  Actions 日志里。

yesterday-point.yml 的告警由独立改造负责，不在本文件覆盖。
"""

from pathlib import Path


def _workflow(name: str) -> str:
    return (Path(".github/workflows") / name).read_text(encoding="utf-8")


def test_daily_video_switches_use_repo_vars_with_default_on():
    workflow = _workflow("daily.yml")

    assert (
        "TENNISLIVE_DAILY_VIDEO: ${{ vars.TENNISLIVE_DAILY_VIDEO || 'on' }}"
        in workflow
    )
    assert (
        "TENNISLIVE_OFFICIAL_VIDEO: ${{ vars.TENNISLIVE_OFFICIAL_VIDEO || 'on' }}"
        in workflow
    )
    # 不允许退回成无法从仓库 Variables 打开的硬编码字面量
    assert "TENNISLIVE_DAILY_VIDEO: 'off'" not in workflow
    assert "TENNISLIVE_OFFICIAL_VIDEO: 'off'" not in workflow


def test_scheduled_radar_workflows_alert_on_failure():
    for name in ("flash.yml", "news-radar.yml"):
        workflow = _workflow(name)
        failure_step = workflow.index("if: failure()")
        # 失败告警必须同时具备：PushPlus 主动推送 + 运行摘要兜底
        assert "pushplus.plus/send" in workflow[failure_step:], name
        assert "GITHUB_STEP_SUMMARY" in workflow[failure_step:], name


def test_scheduled_radar_workflows_summarize_empty_runs():
    for name in ("flash.yml", "news-radar.yml"):
        workflow = _workflow(name)
        empty_step = workflow.index("空产摘要")
        # 空产必须把原因写进运行摘要，而不是只留在会过期的日志正文里
        assert "GITHUB_STEP_SUMMARY" in workflow[empty_step:], name


def test_external_source_health_is_strict_and_separate_from_pr_ci():
    ci = _workflow("ci.yml")
    health = _workflow("source-health.yml")

    # PR 单测必须可重复，不依赖实时比分源；运行时健康由独立定时任务负责。
    assert "tennislive today" not in ci
    assert "真实抓取" not in ci

    assert 'cron: "17 */6 * * *"' in health
    assert "fetch_day(day)" in health
    assert "source_status" in health
    assert "if: failure()" in health
    assert "GITHUB_STEP_SUMMARY" in health
    assert "pushplus.plus/send" in health
    # 主探测不能吞失败；只有告警通道自身允许降级为 warning。
    probe = health.split("- name: 严格检查比分数据源", 1)[1].split("- name:", 1)[0]
    assert "||" not in probe
