"""push 重试的共享脚本判据（2026-08-26 盘点无人值守链落下的）。

当时 push 重试在八个工作流里有四种写法，三种是坏的：
- `git pull --rebase` 裸调没有 `|| abort`：`bash -e` 下 rebase 一失败整步
  立刻死，重试循环一次都轮不到（interview-auto-render、oncourt-interviews）
- 干脆没有重试：auto-push 链由 push 事件触发，失败没有任何东西会重触发，
  裸 push 撞车一次那条片子就静默不发了（auto-push-explainer 的预占/记账、
  auto-push-reel 的复制页/记账、knowledge-adhoc 的每日知识帖）
- `pull --rebase || abort` 再重试：对同一个文件的内容冲突无解——那一类
  （orchestration_state）走 tools/merge_orchestration_state.py 的三方合并，
  不归这份脚本管

逻辑收成一份 tools/git_push_retry.sh（照 ci_apt_install.sh 的先例），
判据也只有一份：形状钉在脚本上，接线钉在「转换过的工作流不许再手搓」。
"""

from pathlib import Path

SCRIPT = Path("tools/git_push_retry.sh")

# 已转换的工作流：它们提交的都是各写各的文件（per-slug 账本、复制页、spec
# 草稿、采集数据），push 被拒几乎总是时序撞车，rebase 一次就过。
# ⚠️ 名单里**不含** orchestrate.yml（state 是共享 JSON，走三方合并那条路，
# 判据在 test_orchestrate）和 match-reel.yml / interview-clip.yml（各有
# 自己钉过判据的「重取远端重放修改」循环，见 test_match_reel / test_interview_clip）。
CONVERTED = [
    "auto-push-reel.yml",
    "auto-push-interview.yml",
    "auto-push-explainer.yml",
    "interview-auto-render.yml",
    "oncourt-interviews.yml",
    "reel-auto-ready.yml",
    "knowledge-adhoc.yml",
]


def _yaml_only(text: str) -> str:
    """去掉整行注释再扫——工作流注释正是记教训的地方，正文里必然写着
    当年的坏写法（`git pull --rebase` 就在好几条注释里）。"""
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith("#"))


def test_共享的push重试脚本形状要对():
    body = SCRIPT.read_text(encoding="utf-8")
    code = _yaml_only(body)
    assert "push_with_rebase_retry()" in code
    assert "--autostash" in code, (
        "工作树常有未跟踪/未暂存的产物，没有 --autostash 的 rebase 会报"
        " unstaged changes 直接失败（真踩过）")
    assert "git rebase --abort" in code, (
        "rebase 失败不 abort 的话，半截 rebase 会把之后每一轮重试毒死——"
        "全部报 rebase in progress")
    assert "::error::" in code, "重试耗尽要出声，静默返回和「推上了」长得一样"
    assert code.index("git push origin") < code.index("git pull --rebase"), (
        "push 在前 rebase 在后：第一次 push 大多直接成功，别每次先白拉一趟")
    assert "return 1" in code and "exit 1" not in code, (
        "脚本自己不许 exit——它是被 source 的，exit 会把调用方整个带走；"
        "失败与否由调用方按自己步骤的语义决定")


def test_自动链的push一律走共享重试不留手搓():
    """转换过的工作流里不许再出现手搓的 push/rebase——
    「同一件事在几处各写一遍，必然分叉」，这次分叉出的三种坏写法就是来路。"""
    checked = 0
    for name in CONVERTED:
        body = _yaml_only(
            Path(".github/workflows", name).read_text(encoding="utf-8"))
        assert "source tools/git_push_retry.sh" in body, (
            f"{name} 没有 source 共享脚本——push_with_rebase_retry 会是"
            "未定义函数，步骤当场死")
        assert "push_with_rebase_retry" in body, f"{name} 没用共享重试"
        assert "git pull --rebase" not in body, (
            f"{name} 又手搓了一份 rebase 重试——重试逻辑只许有一份")
        assert "git push origin" not in body, (
            f"{name} 有绕开共享脚本的裸 push——撞车一次这条链就静默断掉")
        checked += 1
    assert checked == len(CONVERTED)


def test_每个source共享脚本的工作流都真的调用了它():
    """反过来钉：source 了却没调用，说明有人把调用改回手搓——上一条抓
    手搓的形状，这一条抓「接了线没通电」。自己推导，不维护名单。"""
    hits = 0
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        if "source tools/git_push_retry.sh" not in body:
            continue
        assert "push_with_rebase_retry" in body, (
            f"{path.name} source 了共享脚本却一次没调用")
        hits += 1
    assert hits >= len(CONVERTED), "判据的主语没了——没有工作流在用共享脚本"


def _dispatch_input_names(text: str) -> list[str]:
    """数一份工作流的 workflow_dispatch inputs。纯文本解析，不引 yaml
    （tests 里不许 import 没声明的包）。"""
    names: list[str] = []
    in_dispatch = in_inputs = False
    for ln in _yaml_only(text).splitlines():
        if not ln.strip():
            continue
        indent = len(ln) - len(ln.lstrip())
        stripped = ln.strip()
        if indent == 2 and stripped.startswith("workflow_dispatch:"):
            in_dispatch, in_inputs = True, False
            continue
        if in_dispatch and indent <= 2:
            in_dispatch = in_inputs = False
        if in_dispatch and indent == 4 and stripped == "inputs:":
            in_inputs = True
            continue
        if in_inputs:
            if indent < 6:
                in_inputs = False
            elif indent == 6 and stripped.endswith(":"):
                names.append(stripped[:-1])
    return names


def test_所有工作流的dispatch表单都不许超过github的25项硬限制():
    """来路（2026-08-26）：match-reel.yml 的 inputs 涨过 25 个，**整份工作流
    文件失效**——所有 run（含 push 触发的）开跑即死、0 秒 failure，出片主线
    连死 14 趟才被 #606 抓到。#606 的判据只钉了 match-reel 一个文件；这一条
    把**那一类**防住：任何工作流都不许越线（自己推导，不维护名单）。"""
    counted = {}
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        names = _dispatch_input_names(path.read_text(encoding="utf-8"))
        counted[path.name] = len(names)
        assert len(names) <= 25, (
            f"{path.name} 的 workflow_dispatch 有 {len(names)} 个 inputs，"
            f"超过 GitHub 25 个的硬限制——整份文件会失效，"
            f"这条工作流的**每一个** run（含定时/push 触发）都会 0 秒死掉：{names}")
    # 判据自己的判据：解析器要真的数得出东西，不然上面那条恒真。
    assert counted.get("match-reel.yml", 0) >= 20, (
        f"match-reel.yml 只数出 {counted.get('match-reel.yml')} 个 inputs——"
        "解析器多半坏了，这条判据在假绿")
    assert sum(1 for n in counted.values() if n > 0) >= 5, (
        "带 dispatch 表单的工作流数不出五个，解析器的主语没了")
