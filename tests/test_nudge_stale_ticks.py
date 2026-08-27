"""挨饿的定时班次互相叫醒（2026-08-27「编排器 25h 没点过 run」落下的）。

cron 写的每 10 分钟，GitHub 高峰期实际给的班次是 40 分钟到 5 小时一趟——
schedule 事件在忙时会被平台丢弃，而各条 cron 工作流的挨饿互相错开。修法是
每一班顺手用 workflow_dispatch（不吃 schedule 的丢弃）叫醒太久没跑的时间
敏感班次，实际频率变成全部 cron 班次的并集。

逻辑收成一份 tools/nudge_stale_ticks.sh（照 ci_apt_install.sh / git_push_retry.sh
的先例）；判据两半：行为（拿 gh 桩真跑一遍脚本）+ 接线（宿主都 source 它、
orchestrate 那一档必须带 apply=true）。
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

SCRIPT = Path("tools/nudge_stale_ticks.sh").resolve()

#: 宿主 → 该叫醒谁。频繁 cron 的班次都当宿主，目标是内容链的两个时间敏感
#: 班次；orchestrate/reel-auto-ready 互相叫（自己叫自己没有意义）。
HOSTS = {
    "orchestrate.yml": ["reel-auto-ready.yml"],
    "reel-auto-ready.yml": ["orchestrate.yml"],
    "official-social-images.yml": ["orchestrate.yml", "reel-auto-ready.yml"],
    "pipeline-health.yml": ["orchestrate.yml", "reel-auto-ready.yml"],
    "oncourt-interviews.yml": ["orchestrate.yml", "reel-auto-ready.yml"],
    "interview-auto-render.yml": ["orchestrate.yml", "reel-auto-ready.yml"],
}

_STUB = """#!/usr/bin/env bash
if [ "$1" = api ]; then
  [ -n "$STUB_API_FAIL" ] && exit 1
  printf '%s\\n' "$STUB_API_OUT"
  exit 0
fi
if [ "$1" = workflow ] && [ "$2" = run ]; then
  shift 2
  echo "$@" >> "$STUB_RUN_LOG"
  [ -n "$STUB_RUN_FAIL" ] && exit 1
  exit 0
fi
exit 9
"""


def _nudge(tmp_path, api_out="", api_fail="", run_fail="",
           args="orchestrate.yml 20 -f apply=true") -> tuple[str, list[str]]:
    """gh 桩真跑一遍脚本，返回 (输出, 记录到的 dispatch 调用)。"""
    gh = tmp_path / "bin" / "gh"
    gh.parent.mkdir(exist_ok=True)
    gh.write_text(_STUB, encoding="utf-8")
    gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "runs.log"
    env = dict(
        os.environ,
        PATH=f"{gh.parent}:{os.environ['PATH']}",
        GITHUB_REPOSITORY="o/r",
        STUB_API_OUT=api_out, STUB_API_FAIL=api_fail,
        STUB_RUN_FAIL=run_fail, STUB_RUN_LOG=str(log),
    )
    proc = subprocess.run(
        ["bash", "-euo", "pipefail", "-c",
         f'source "{SCRIPT}" && nudge_if_stale {args}'],
        capture_output=True, text=True, env=env, timeout=30)
    assert proc.returncode == 0, (
        f"nudge 任何路径都不许把宿主步骤带红：{proc.stdout}{proc.stderr}")
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return proc.stdout, calls


def test_挨饿才叫_在跑或刚跑过或读不到都不叫(tmp_path):
    # ① 目标在跑 → 不点
    out, calls = _nudge(tmp_path, api_out="in_progress 2026-08-27T01:00:00Z")
    assert not calls and "在跑" in out
    # ② 刚跑过（5 分钟前）→ 不点
    import datetime as dt
    fresh = (dt.datetime.now(dt.timezone.utc)
             - dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out, calls = _nudge(tmp_path, api_out=f"completed {fresh}")
    assert not calls and "刚跑过" in out
    # ③ 读不到运行列表 → 不点，并且说的是「读不到」不是「没跑」
    #    （两者处置相反——API 抖动不许被放大成 dispatch 风暴）
    out, calls = _nudge(tmp_path, api_fail="1")
    assert not calls and "读不到" in out
    # ④ 时间戳读不懂 → 不点（含糊时宁可漏，漏了=现状）
    out, calls = _nudge(tmp_path, api_out="completed null")
    assert not calls and "读不懂" in out


def test_真挨饿就代点一趟_额外参数原样带上(tmp_path):
    out, calls = _nudge(tmp_path, api_out="completed 2026-08-27T00:00:00Z")
    assert calls == ["orchestrate.yml --ref main -f apply=true"], calls
    assert "已代点一趟" in out
    # 从来没跑过的班次（cron 存在却零 run）也算挨饿
    out, calls = _nudge(tmp_path, api_out="never")
    assert calls and "已代点一趟" in out
    # 点失败：出声、不重试、不报错——真正的兜底仍是目标自己的 cron
    out, calls = _nudge(tmp_path, api_out="never", run_fail="1")
    assert "没成" in out and "cron" in out


def test_挨饿的定时班次要互相叫醒():
    """接线：每个宿主都 source 共享脚本并叫醒该叫的班次；orchestrate 那一档
    必须带 apply=true——它 workflow_dispatch 的 apply 默认 false，裸点一趟
    只扫候选不派发，看起来醒了其实什么都没做。"""
    for host, targets in HOSTS.items():
        body = Path(f".github/workflows/{host}").read_text(encoding="utf-8")
        assert "source tools/nudge_stale_ticks.sh" in body, host
        for target in targets:
            assert f"nudge_if_stale {target}" in body, (host, target)
        if "orchestrate.yml" in targets:
            assert "nudge_if_stale orchestrate.yml 20 -f apply=true" in body, (
                f"{host}: 叫醒 orchestrate 不带 apply=true 等于白叫")
    # pipeline-health 原来只有 actions: read——gh workflow run 要 write，
    # 少了它 nudge 每次都「没成」，而那和「没挨饿」在结果上长得一样
    health = Path(".github/workflows/pipeline-health.yml").read_text("utf-8")
    assert "actions: write" in health
