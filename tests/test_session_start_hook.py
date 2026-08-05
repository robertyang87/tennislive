"""会话启动钩子的规矩。

账号所有者 2026-08-05：「之前好像有好几次都要重新安装配置环境……浪费了很多
时间」。容器每次是干净的，而这个仓库真跑起来要三样东西（项目依赖、中文字体、
ffmpeg）。CLAUDE.md 里「沙箱跑全量测试前先装依赖，别把缺依赖当成『已知红』」
那一节记的就是不装的下场：常年 26 条红被当成环境噪音，里面埋着一个真 bug。

钩子把这件事做成一次性的。这份判据管两件事：**它装的东西不能比 CI 少**，
以及**它的幂等检查不能被自己的机制废掉**。
"""

from __future__ import annotations

import json
import re
import stat
from pathlib import Path

HOOK = Path(".claude/hooks/session-start.sh")
SETTINGS = Path(".claude/settings.json")
CI = Path(".github/workflows/ci.yml")


def _sh_only(text: str) -> str:
    """去掉整行注释再扫。

    这个仓库的注释就是教训的存放处，正文里必然写着当年那些错的写法
    （这份钩子的注释里就原样写着 `fc-list | grep -qi X`）。连注释一起扫，
    「把坑记下来」会被判成「又踩了这个坑」——同一个形状在工作流那边栽过四次。
    """
    return "\n".join(line for line in text.splitlines()
                     if not line.lstrip().startswith("#"))


def test_钩子注册了而且可执行():
    assert HOOK.is_file(), "没有会话启动钩子"
    assert HOOK.stat().st_mode & stat.S_IXUSR, (
        "钩子没有可执行位——注册了也跑不起来，而且失败得很安静")
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["SessionStart"]
    cmds = [h["command"] for entry in hooks for h in entry["hooks"]]
    assert any(HOOK.name in c for c in cmds), f"settings.json 里没挂上它：{cmds}"


def test_会话启动钩子装的东西要和CI对齐():
    """**沙箱不许装得比 CI 少。**

    这个仓库反复栽在「本地装着不等于 CI 装着」上（playwright、Chromium、cv2、
    fonts-noto-core、pip 行漏了 `-e .`）。装少了的样子是「本地跑不了 CI 能跑的
    测试」，于是那几条永远被当成「这里跑不了」——正是 CLAUDE.md 那一节
    要防的事。

    **判据自己推导，不维护名单**：从 `ci.yml` 里把 apt 包和 pip extra 抽出来，
    钩子必须每样都有。以后 CI 加一个包，这条会替人记得。
    """
    ci = _sh_only(CI.read_text(encoding="utf-8"))
    hook = _sh_only(HOOK.read_text(encoding="utf-8"))

    apt = set(re.findall(r"fonts-[\w-]+", ci)) | (
        {"ffmpeg"} if "ffmpeg" in ci else set())
    assert apt, "从 ci.yml 里没抽到 apt 包，基准没了"
    missing = sorted(p for p in apt if p not in hook)
    assert not missing, (
        f"CI 装了这些、钩子没装：{missing}。沙箱会跑不了依赖它们的测试，"
        "而那几条会被读成「这里跑不了」。")

    extras = set(re.findall(r'-e "?\.\[([\w,]+)\]"?', ci))
    assert extras, "从 ci.yml 里没抽到 pip extra，基准没了"
    ci_extras = {e.strip() for group in extras for e in group.split(",")}
    hook_extras = {e.strip()
                   for group in re.findall(r'-e "?\.\[([\w,]+)\]"?', hook)
                   for e in group.split(",")}
    assert ci_extras <= hook_extras, (
        f"CI 装了这些 extra、钩子没装：{sorted(ci_extras - hook_extras)}")


def test_钩子的幂等检查不许被自己的管道废掉():
    """⚠️ `fc-list | grep -qi X` 在 `set -o pipefail` 下**匹配上了也算失败**。

    `grep -q` 一命中就退出，`fc-list` 随即吃 SIGPIPE，管道退出码 141，
    `pipefail` 把它判成失败——于是「装好了」被读成「没装」。第一版就是这么
    写的，实测退出码 141。

    **它错的方向是「白跑一次 apt」**：慢一点、不报错、永远没人发现。
    和 CLAUDE.md 里 `until ! pgrep -f 'X'` 会匹配到它自己那条同一个形状——
    检查自己的机制把检查本身废掉了。

    所以只要钩子开了 `pipefail`，判据里就不许出现 `| grep -q`。
    """
    hook = _sh_only(HOOK.read_text(encoding="utf-8"))
    if "pipefail" not in hook:
        return
    bad = [line.strip() for line in hook.splitlines()
           if re.search(r"\|\s*grep\s+-[a-zA-Z]*q", line)]
    assert not bad, (
        "开着 pipefail 还用 `| grep -q` 做判断，匹配上了反而算失败：\n  "
        + "\n  ".join(bad)
        + "\n先把输出落成变量再匹配（`out=\"$(cmd)\"` + `case`）。")


def test_钩子只在远程容器上动手():
    """本地开发机不归它管——它装的是一次性容器要的东西。

    而且**守卫要排在所有 install 前面**：排在后面就等于没有守卫，
    本地机器照样被 apt 一遍。
    """
    hook = _sh_only(HOOK.read_text(encoding="utf-8"))
    assert "CLAUDE_CODE_REMOTE" in hook, "没有远程守卫，本地机器也会被装一遍"
    guard = hook.index("CLAUDE_CODE_REMOTE")
    for step in ("apt-get", "pip install"):
        assert guard < hook.index(step), f"{step} 排在远程守卫前面，守卫等于没有"


def test_钩子装完要真import一遍():
    """**查产物，不查信号。** `pip install` 退出码 0 不保证 import 得进来。

    opencv 那次就是：随手装到 5.x，`CascadeClassifier` 没了，
    红得和「没装」一模一样。所以装完要真 import 一遍，缺了当场退非零——
    只在成功时出声的检查，没法证明它真的看过。
    """
    hook = HOOK.read_text(encoding="utf-8")
    assert "__import__" in hook or "import " in hook.split("pip install")[-1], (
        "装完没有验证 import")
    assert "sys.exit(1)" in hook, (
        "验证不通过却不退非零——启动看起来是成功的，问题留到第一次跑测试才炸")
