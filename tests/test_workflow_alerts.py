"""定时工作流的开关与告警规则（CLAUDE.md：规则要落成测试）。

2026-07-25 审查确认的静默故障：flash.yml / news-radar.yml 失败与空产零告警，
诊断只存在于会过期的 Actions 日志里。

（另一条「daily.yml 把视频开关硬编码成 'off'」随日报 2026-07-31 停产一起删了。）

yesterday-point.yml 的告警由独立改造负责，不在本文件覆盖。
"""

from pathlib import Path


def _workflow(name: str) -> str:
    return (Path(".github/workflows") / name).read_text(encoding="utf-8")


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


def test_every_workflow_that_commits_generated_files_has_a_size_gate():
    """跑完一整趟再被 GitHub 拒收，是最贵的一种失败。

    **判据自己推导，不维护白名单。** 原来这里手写着十一个文件名，daily.yml
    停产删掉之后它当场变成 FileNotFoundError——**一个会过期的名单，和一条
    常年红的检查是同一个毛病**。现在改成「凡是 `git commit` 的工作流都要有
    这道闸」，新加工作流自动被覆盖。

    加这条推导的当天就抓到一个：我自己新写的 `push-reel.yml` 漏了闸。
    """
    committers = [
        path for path in sorted(Path(".github/workflows").glob("*.yml"))
        if "git commit" in path.read_text(encoding="utf-8")
    ]
    assert len(committers) >= 8, f"只找到 {len(committers)} 条会提交的工作流，判据可能失效了"
    for path in committers:
        assert "python tools/check_staged_file_sizes.py" in path.read_text(
            encoding="utf-8"), (
            f"{path.name} 会 git commit 却没有体积闸——"
            "渲完一整趟才被 GitHub 拒收是最贵的失败")
