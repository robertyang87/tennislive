"""「合进 main 就自动发微信」的四道闸。

这条路省掉的是人的往返（合完还要记得回来点一次 dispatch），而它是整条链上
**唯一新增的风险点**——微信那条消息发出去收不回来。所以每一道闸都在这儿
反向验证一次：不只验「该发的发了」，更要验「不该发的一条都没发」。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import auto_push_gate as gate  # noqa: E402

WORKFLOW = Path(".github/workflows/auto-push-reel.yml")


def _yaml_only(text: str) -> str:
    """去掉整行注释再扫。

    这个仓库的工作流注释正是记教训的地方，正文里必然写着当年那些错值；
    而这一次更要紧的是反方向：注释里出现 `auto` / `main` 会让漏配的写法**假绿**。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args],
                   check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """一个最小的**真 git 仓库**：一条 spec、一份文案、一个渲好的 outdir。

    ⚠️ 必须是真 git：「已经推过」那道闸查的是 `git ls-files`，不是
    `test -f`——喂一个普通目录就把那道闸绕过去了，而绕过去之后测试**照样绿**。
    """
    (tmp_path / "specs/reels").mkdir(parents=True)
    (tmp_path / "specs/reels/demo.xhs.txt").write_text("文案", encoding="utf-8")
    outdir = tmp_path / "output/2026-08-03/reel/demo"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text("{}", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    # render.json 提交进仓库——现实里它就是先由 render 工作流提交、随 PR
    # 进 main 的；「已删除的产物不算候选」那道闸查的是 git ls-files，
    # 不提交的话所有用这个 fixture 的测试都会被那道闸拦下。
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "base")
    return tmp_path


def _commit_all(repo: Path) -> None:
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c", "commit", "-qm", "x")


def _spec(repo: Path, push: dict | None, slug: str = "demo") -> None:
    body: dict = {"cover": {"eyebrow": "赛场之上"}}
    if push is not None:
        body["push"] = push
    (repo / f"specs/reels/{slug}.json").write_text(
        json.dumps(body, ensure_ascii=False), encoding="utf-8")


CHANGED = ["output/2026-08-03/reel/demo/render.json"]


# ---------------------------------------------------------------- 闸 2：认领

def test_没写auto的一条都不发(repo: Path, capsys):
    """**默认关。** 现在仓库里 16 条 spec 一条都没写 `push.auto`，
    也就是说这条工作流合并之后**什么都不会发**——要开得再动一次手。
    """
    _spec(repo, {"summary": "伊埃拉进决赛"})
    assert gate.pick(CHANGED, repo) is None
    out = capsys.readouterr().out
    assert "没写 push.auto=true" in out, f"跳过了却没说为什么：{out}"
    # 报错要说出路，不能只说不行
    assert '"auto": true' in out


def test_写了auto才发(repo: Path):
    """反向验证上一条：同样的输入，只加一行 `auto: true`，就该发。

    没有这一条的话，「一条都不发」可以由任何一个 bug 造成——**证明不了
    是那道闸在起作用**。
    """
    _spec(repo, {"auto": True})
    picked = gate.pick(CHANGED, repo)
    assert picked is not None, "写了 auto 还是不发，那这个开关根本没接上"
    assert picked[0] == "demo"


def test_auto写成字符串要报错(repo: Path):
    """`"auto": "true"` 在 Python 里是真值，`is True` 判它是假。

    两种处理都说得通，但**悄悄不发**和「这条本来就没开」长得一模一样——
    又一次不吭声的兜底。所以报错。
    """
    _spec(repo, {"auto": "true"})
    with pytest.raises(SystemExit, match="只能是 true 或 false"):
        gate.pick(CHANGED, repo)


# ---------------------------------------------------------------- 闸 3：别重发

def test_已经推过的不许再发一次(repo: Path, capsys):
    """判据是**产物**（`pushed.json` 在仓库里），不是「工作流跑成功过」。

    这条路会被任何一次动到 `render.json` 的提交触发——重渲、改 spec、
    甚至我自己顺手改一行。没有这道闸，同一条片子会被发第二次，
    而收件人只能看到两条一样的消息。
    """
    _spec(repo, {"auto": True})
    gate.record(repo / "output/2026-08-03/reel/demo",
                "https://example/run/1", "2026-08-03T00:00:00Z")
    _commit_all(repo)
    assert gate.pick(CHANGED, repo) is None
    out = capsys.readouterr().out
    assert "已经推过了" in out and "example/run/1" in out, (
        f"跳过了却没说是哪一趟发的，出问题时无从查起：{out}")


def test_没提交的标记不算数(repo: Path):
    """只写在工作区、没进仓库的 `pushed.json` **不能**算「已经发过」。

    如果认它，一次失败的 run 留下的半截文件就会把这条片子永久锁死，
    而且不吭声。反过来说，这也正是它必须查 `git ls-files` 的另一半理由。
    """
    _spec(repo, {"auto": True})
    gate.record(repo / "output/2026-08-03/reel/demo", "run", "now")
    # 故意不提交
    assert gate.pick(CHANGED, repo) is not None


def test_稀疏检出下也要拦得住(repo: Path):
    """**这是真踩到的那个 bug。**

    第一版按 `(outdir / MARKER).is_file()` 判，而这条工作流是稀疏检出的：
    判断的时候 `output/` 那一格还没 `git sparse-checkout add` 回来，
    文件根本不在工作区——那道闸**恒为假，会重复发**。

    这条测试把工作区里那份删掉（模拟稀疏检出的样子），索引里留着，
    要求照样拦得住。反向验证过：退回 `is_file()` 当场红。
    """
    _spec(repo, {"auto": True})
    marker = gate.record(repo / "output/2026-08-03/reel/demo", "run", "now")
    _commit_all(repo)
    marker.unlink()  # ← 稀疏检出之后工作区里就是没有它
    assert gate.pick(CHANGED, repo) is None


# ---------------------------------------------------------------- 闸 4：只发一条

def test_一趟带进来两条就一条都不发(repo: Path):
    """批量自动发微信，错一次就是错一片。"""
    _spec(repo, {"auto": True})
    _spec(repo, {"auto": True}, slug="demo2")
    (repo / "specs/reels/demo2.xhs.txt").write_text("文案", encoding="utf-8")
    second = repo / "output/2026-08-03/reel/demo2"
    second.mkdir(parents=True)
    (second / "render.json").write_text("{}", encoding="utf-8")
    _commit_all(repo)

    with pytest.raises(SystemExit):
        gate.pick(CHANGED + ["output/2026-08-03/reel/demo2/render.json"], repo)


def test_删除的render_json不算候选(repo: Path, capsys):
    """清理旧版产物的合并会把**删除**的 render.json 也带进 changed 列表
    （workflow 那头 `git diff --name-only` 含 D 条目；已补 --diff-filter=AM，
    这儿是第二层）。被删的产物不是新渲完的片子——它的 spec 往往还写着
    auto:true、目录里又没有 pushed.json，不拦的话会凑成「一次 N 条」把
    真该发的一起拦死。2026-08-12 zheng-lanlana 的合并差点踩到：同一批
    改动里带着三份被顶替旧版的删除。"""
    _spec(repo, {"auto": True})
    _git(repo, "rm", "-rq", "output/2026-08-03/reel/demo")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "清理旧产物")
    assert gate.pick(CHANGED, repo) is None
    assert "已不在仓库里" in capsys.readouterr().out, "跳过要说出为什么"


def test_同一批里删一条活一条要发活的那条(repo: Path):
    """zheng-lanlana 那次合并的真实形状：删掉被顶替的旧版 + 新渲的一条。
    删除项被滤掉后，活的那条必须照常发——别把防批量的闸误触发。"""
    _spec(repo, {"auto": True})
    _spec(repo, {"auto": True}, slug="demo2")
    (repo / "specs/reels/demo2.xhs.txt").write_text("文案", encoding="utf-8")
    second = repo / "output/2026-08-03/reel/demo2"
    second.mkdir(parents=True)
    (second / "render.json").write_text("{}", encoding="utf-8")
    _commit_all(repo)
    _git(repo, "rm", "-rq", "output/2026-08-03/reel/demo")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "清理旧产物")

    picked = gate.pick(
        CHANGED + ["output/2026-08-03/reel/demo2/render.json"], repo)
    assert picked is not None and picked[0] == "demo2", (
        "删除项混进来把活的那条也拦死了——防批量的闸不该被幽灵候选触发")


def test_工作流的diff要滤掉删除项():
    """第一层在 workflow：`--diff-filter=AM`。没有它，删除的 render.json
    一样进 changed 列表——闸挡得住，但一趟 run 会红着结束，真该发的那条
    要等人来查。"""
    body = Path(".github/workflows/auto-push-reel.yml").read_text(
        encoding="utf-8")
    line = next(l for l in body.splitlines()
                if "git diff" in l and "render.json" in l and "#" not in l.split("git diff")[0])
    assert "--diff-filter=AM" in line, (
        "auto-push 的 diff 少了 --diff-filter=AM：删除的 render.json 会被当成候选")


# ---------------------------------------------------------------- 闸 1：路径

@pytest.mark.parametrize("path", [
    "output/2026-08-03/reel/demo/poster.jpg",      # 不是 render.json
    "output/2026-08-03/knowledge/demo/render.json",  # 不是 reel
    "specs/reels/demo.json",                       # 压根不在 output 下
])
def test_形状不对的路径一律不发(repo: Path, path: str):
    _spec(repo, {"auto": True})
    assert gate.pick([path], repo) is None


# ---------------------------------------------------------------- 工作流本身

def test_自动推送只在main上跑():
    """GitHub Pages 只服务 main（复制页在分支上永远 404），而成片链接钉在
    commit sha 上——未合并的 commit 有被 GC 的风险，微信里那个 ▶ 会变死链。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    trigger = body.split("permissions:")[0]
    assert "branches: [main]" in trigger, "没限定 main"
    assert "workflow_dispatch" not in trigger, (
        "别再给它开手动入口——手动推送走 match-reel mode=push，"
        "那条路有完整的预检和参数")


def test_自动推送不许取消正在跑的():
    """取消一个已经发出 POST 的 run，只会让「发没发出去」变成未知，
    而 `pushed.json` 那一笔可能没记上——下一次触发就会再发一遍。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert re.search(r"cancel-in-progress:\s*false", body), (
        "自动推送不许 cancel-in-progress: true")


def test_自动推送这条路不装出片那一堆():
    """它不下源片、不合语音、不编码——装 ffmpeg / Chromium / 抠图模型
    就是白等三分钟，而这条路的全部意义就是那 43 秒。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    for heavy in ("ffmpeg", "playwright", "chromium", "rembg", "yt-dlp"):
        assert heavy not in body.lower(), f"自动推送这条路不该出现 {heavy}"


def test_发完要把已推送记进仓库():
    """**记不进仓库就等于没记。** 只活在 runner 工作区里的标记，下一次触发
    读不到——同一个毛病在复制页上踩过两次（日志印着链接、步骤 success、
    人点开是 404）。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    record = body[body.index("--record"):]
    assert "git commit" in record and "git push" in record, (
        "记了 pushed.json 却没提交，下一次触发会再发一遍")


def test_记已推送要排在发微信之后():
    """反过来（先记后发）的话，推送失败会留下一个「已经发过」的假标记，
    这条片子从此再也发不出去，而且不吭声。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert body.index("--stage page") < body.index("--record")
    send = body.index("TENNISLIVE_ASSET_REV")
    assert send < body.index("--record"), "记已推送排到了发微信前面"
