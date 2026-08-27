#!/usr/bin/env bash
# 供工作流 `source` 的共享脚本：顺手叫醒挨饿的定时班次。
#
# 来路（2026-08-27「编排器已 25 小时没点过 run」的告警）：orchestrate 的 cron
# 写的是每 10 分钟，GitHub 实际给的班次是 40 分钟到 5 小时一趟——schedule
# 事件在平台高峰期会被丢弃（实测最饿的窗口是 17:00–03:00 UTC，恰好是美网
# 比赛打完、集锦上线的时段），这不是 cron 表达式能修的。而各条 cron 工作流
# 的挨饿是**互相错开**的：昨夜 orchestrate 01:02 有班、reel-auto-ready 03:24
# 有班。让每一班顺手看一眼别的时间敏感班次是不是太久没跑、是就用
# workflow_dispatch 叫醒它——workflow_dispatch 不吃 schedule 的丢弃，效果是
# 时间敏感班次的实际频率变成**全部 cron 班次的并集**。
#
# 边界（每条都是方向验过的）：
# - 目标在跑/在排队 → 不点：点了也只是排一趟重复的。
# - 目标 stale_min 分钟内跑过 → 不点：它没挨饿。
# - 读不到运行列表 → 不点并说明：「读不到」≠「没跑」（CLAUDE.md 的老规矩，
#   两者处置相反）——把一次 API 抖动放大成 dispatch 风暴，比漏一次 nudge
#   坏得多；漏了就是现状，目标自己的 cron 仍是兜底。
# - 点失败 → 出声、不重试、不报错：nudge 是顺手帮一把，不是保证。
# - 任何路径都 return 0，不许把宿主步骤带红。

# nudge_if_stale <workflow-file> <stale-minutes> [传给 gh workflow run 的额外参数...]
nudge_if_stale() {
  local wf="$1"; local stale_min="$2"; shift 2
  local info status started started_epoch age=""
  info=$(gh api "repos/${GITHUB_REPOSITORY}/actions/workflows/${wf}/runs?per_page=1" \
           --jq '.workflow_runs[0] | if . == null then "never" else "\(.status) \(.run_started_at)" end' \
           2>/dev/null) \
    || { echo "[nudge] 读不到 ${wf} 的运行列表，跳过（读不到≠该点，别把 API 抖动变成风暴）"; return 0; }
  if [ "$info" != "never" ]; then
    status="${info%% *}"
    started="${info#* }"
    case "$status" in
      queued|in_progress|waiting|pending|requested)
        echo "[nudge] ${wf} 已经在跑/在排队，不用叫"; return 0 ;;
    esac
    started_epoch=$(date -u -d "$started" +%s 2>/dev/null) \
      || { echo "[nudge] ${wf} 的 run_started_at 读不懂（${started}），跳过"; return 0; }
    age=$(( ( $(date -u +%s) - started_epoch ) / 60 ))
    if [ "$age" -lt "$stale_min" ]; then
      echo "[nudge] ${wf} ${age} 分钟前刚跑过（阈值 ${stale_min}），不用叫"
      return 0
    fi
  fi
  if gh workflow run "$wf" --ref main "$@"; then
    echo "[nudge] ${wf} 已 ${age:-从来没} 分钟没班（schedule 被 GitHub 丢弃了），已代点一趟"
  else
    echo "[nudge] 点 ${wf} 没成（权限/瞬时抖动），不重试——真正的兜底仍是它自己的 cron"
  fi
  return 0
}
