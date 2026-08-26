#!/usr/bin/env bash
# 供工作流 `source` 的共享脚本，别在各个 .github/workflows/*.yml 里各写一份。
#
# 来路（2026-08-26 盘点无人值守链）：push 重试这件事当时在八个工作流里有
# 四种写法，三种是坏的，而且坏法各不相同：
#   - `git pull --rebase` 裸调、没有 `|| abort`（interview-auto-render、
#     oncourt-interviews 采集步）：`bash -e` 下 rebase 一失败整步立刻死，
#     重试循环一次都轮不到；就算不带 -e，rebase 停在半路，后面每次重试
#     都报 "rebase in progress"，循环被毒死
#   - 干脆没有重试（auto-push-explainer 的预占/记账、auto-push-reel 的
#     复制页/记账）：main 现在每小时被自动任务提交好几次，裸 push 撞车
#     的概率早就不是当年的量级；发布链在这儿红一次，那条片子就静默不发了
#     （auto-push-* 由 push 事件触发，失败没有任何东西会重触发）
#   - `pull --rebase || abort` 再重试（orchestrate 的 state 步）：对**同一个
#     文件的内容冲突**无解——abort 之后什么都没变，重试只会撞同一个冲突。
#     那一处不该用这份脚本，见 tools/merge_orchestration_state.py
#
# 这份脚本管的是前两类：**各写各的文件、冲突本来就极少**的提交（per-slug
# 的账本、复制页、spec 草稿、采集数据）。对它们，push 被拒几乎总是「别的
# run 刚推过 main」的时序撞车，rebase 一次就过，重试就是全部所需。
# 真正会内容冲突的共享 JSON（orchestration_state）走三方合并那条路。

# push_with_rebase_retry <ref> [attempts]
#   把已经 commit 好的 HEAD 推到 origin/<ref>；被拒就 rebase 到最新再试。
#   rebase 失败（冲突/锁）时 abort 干净再进下一轮——别把半截 rebase 留给
#   下一次重试。全部失败返回 1，让调用方自己决定这算不算整步失败。
push_with_rebase_retry() {
  local ref="$1"
  local attempts="${2:-5}"
  local attempt
  for attempt in $(seq 1 "$attempts"); do
    if git push origin "HEAD:${ref}"; then
      return 0
    fi
    echo "push 被拒（第 ${attempt}/${attempts} 次），rebase 到最新再试"
    # --autostash：工作树常有未跟踪/未暂存的产物（临时文件、别的步骤的
    # 中间物），没有它 rebase 会报 unstaged changes 直接失败（真踩过）。
    git pull --rebase --autostash origin "$ref" \
      || { git rebase --abort 2>/dev/null || true; }
    sleep $((attempt * 3 + RANDOM % 5))
  done
  echo "::error::连续 ${attempts} 次都没能推上 origin/${ref}"
  return 1
}
