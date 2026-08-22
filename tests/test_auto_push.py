"""「合进 main 就自动发微信」的五道闸。

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

    ⚠️ **海报要有。** 一条真渲完的片子必然带着 `poster.jpg`（render 生成它，
    `match-reel.yml` 的清理那步还特意留着它），所以这个 fixture 也得有——
    这样「该发的照发」那几条验的才是它们各自那道闸，而不是被海报闸拦下。
    """
    (tmp_path / "specs/reels").mkdir(parents=True)
    (tmp_path / "specs/reels/demo.xhs.txt").write_text("文案", encoding="utf-8")
    outdir = tmp_path / "output/2026-08-03/reel/demo"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text("{}", encoding="utf-8")
    (outdir / "poster.jpg").write_bytes(b"\xff\xd8\xff not-a-real-jpeg")
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


def _second_reel(repo: Path, slug: str = "demo2") -> Path:
    """再造一条**渲完的**片子（spec + 文案 + render.json + 海报）。

    海报在这儿是必需品，不是装饰：少了它「海报在仓库里」那道闸会把这条
    候选筛掉，于是「一趟带进来两条」那类测试只剩一个候选、恒绿——一道
    真闸就这么被另一道闸悄悄遮住了。收在一处，别在每个测试里各写一遍。
    """
    _spec(repo, {"auto": True}, slug=slug)
    (repo / f"specs/reels/{slug}.xhs.txt").write_text("文案", encoding="utf-8")
    outdir = repo / f"output/2026-08-03/reel/{slug}"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text("{}", encoding="utf-8")
    (outdir / "poster.jpg").write_bytes(b"\xff\xd8\xff not-a-real-jpeg")
    return outdir


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


# ---------------------------------------------------------------- 闸 4：海报

def test_海报不在仓库里就不发(repo: Path, capsys):
    """**2026-08-13 那次 purge 抖出来的。**

    `archive-media.yml mode=purge` 用 git filter-repo 从全史抹掉了 output/ 下
    所有 jpg（认领过的取舍，17 GB → 789 MB），于是**仓库里一张 poster.jpg
    都不剩**。新渲的片子没事（render 会重新生成并提交），撞上的是
    **purge 之前渲好、purge 之后才推**的老片子。

    海报是推送正文的第一屏，没有它这条消息只剩两个按钮，看不出这是谁打谁。
    """
    _spec(repo, {"auto": True})
    (repo / "output/2026-08-03/reel/demo/poster.jpg").unlink()
    _git(repo, "rm", "-q", "--cached",
         "output/2026-08-03/reel/demo/poster.jpg")
    _commit_all(repo)

    assert gate.pick(CHANGED, repo) is None, (
        "海报不在仓库里还照发——推出去就是一条没有第一屏的消息，"
        "而微信那条消息收不回来")
    out = capsys.readouterr().out
    assert "poster.jpg" in out, f"跳过了却没说是海报的问题：{out}"
    # 报错要说出路，不能只说不行——这条的出路是重渲一次把海报渲回来
    assert "mode=render" in out, f"没说怎么把它救回来：{out}"


def test_海报在就照发(repo: Path):
    """反向验证上一条：同样的输入，只把海报放回去，就该发。

    没有这一条的话，「一条都不发」可以由任何一个 bug 造成——**证明不了
    是海报那道闸在起作用**（`test_写了auto才发` 那条的同款理由）。
    """
    _spec(repo, {"auto": True})
    picked = gate.pick(CHANGED, repo)
    assert picked is not None, "海报好好地在仓库里，却被拦下了"
    assert picked[0] == "demo"


def test_稀疏检出下海报也要认得出(repo: Path):
    """**这道闸最容易写错的地方，而写错的后果比漏发大得多。**

    这个脚本跑在工作流的「挑出该自动发的那一条」那一步，排在
    `git sparse-checkout add` **之前**——`output/` 那一格根本不在工作区。
    按 `(outdir / "poster.jpg").is_file()` 判就是**恒为假**：不是漏发一条，
    是**每一条都不发**，整条自动推送静静地死掉，而 run 还是绿的。

    这条把工作区里那份删掉（模拟稀疏检出的样子）、索引里留着，要求照常发。
    反向验证过：把 `tracked()` 换成 `is_file()` 当场红。
    """
    _spec(repo, {"auto": True})
    _commit_all(repo)
    (repo / "output/2026-08-03/reel/demo/poster.jpg").unlink()

    picked = gate.pick(CHANGED, repo)
    assert picked is not None, (
        "海报在仓库里、只是没检出到工作区，就被判成「没有海报」——"
        "按 is_file() 判的话每一条都会这样")
    assert picked[0] == "demo"


def test_两条推送路径对缺海报的口径要一致():
    """**手动那条路一直是硬拦的，自动这条以前一道检查都没有。**

    `match-reel.yml` 的「push 模式先确认成片真的落地了」里写着
    `test -f .../poster.jpg || { echo "::error::海报不在…"; exit 1; }`。
    同一个问题两条路给两个答案，就是「一个数写两处必分叉」的政策版：
    同一条片子手动推被拦下、自动推却降级发了出去。

    所以这条钉的是**手动那头别被拆掉**——自动这头由上面几条盯着。

    ⚠️ 扫之前先去掉整行注释：`match-reel.yml` 的注释里正写着
    「**poster.jpg 要留下**：推送正文的第一屏就是它」，连注释一起扫的话，
    把这道闸整个删掉也照样绿（这个仓库为「注释制造假绿」栽过）。
    """
    body = _yaml_only(
        Path(".github/workflows/match-reel.yml").read_text(encoding="utf-8"))
    assert re.search(r"test -f[^\n]*poster\.jpg[^\n]*\|\|[^}]*exit 1", body), (
        "match-reel 的 push 预检不再硬拦缺海报的片子了——"
        "两条推送路径的口径又分叉了")


# ---------------------------------------------------------------- 闸 5：只发一条

def test_一趟带进来两条就一条都不发(repo: Path):
    """批量自动发微信，错一次就是错一片。"""
    _spec(repo, {"auto": True})
    _second_reel(repo)
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
    _second_reel(repo)
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


def test_自动推送的超时盖得住Pages最坏而且被掐也要告警():
    """三头一起钉，缺一头都是「等待窗口结构性地短于 Pages 的发布时间」重演。

    ① **job 超时要盖住复制页探活的账**：实测 Pages 最坏一次发布 14 分钟，
      reel 这条 20 分钟的老预算只剩几分钟余量；explainer 的探活窗口本身就是
      26×30s ≈ 13 分钟，20 分钟同样贴着边。
    ② **探活的环境变量要真的被 push_reel 读**，而且值不许超过代码里的钳位
      （`min(60, …)` / `min(60.0, …)`）——超了会被**静默钳掉**，工作流里写的
      数和真实生效的数从此对不上，正是 `_push` 键名写错那一族的形状。
    ③ **超时被掐的 run 是 cancelled 不是 failure**：告警只挂 `failure()` 的话，
      恰恰是「等满预算被掐」这种最该告警的失败静默溜走。
    """
    reel = WORKFLOW.read_text(encoding="utf-8")
    reel_body = _yaml_only(reel)
    expl = Path(".github/workflows/auto-push-explainer.yml").read_text(
        encoding="utf-8")
    expl_body = _yaml_only(expl)

    # ① 超时下限（只许更宽，不许悄悄缩回去）
    reel_timeout = int(re.search(r"timeout-minutes: (\d+)", reel_body).group(1))
    assert reel_timeout >= 35, f"auto-push-reel 超时 {reel_timeout} < 35"
    expl_timeout = int(re.search(r"timeout-minutes: (\d+)", expl_body).group(1))
    assert expl_timeout >= 25, f"auto-push-explainer 超时 {expl_timeout} < 25"

    # ② 探活环境变量：名字要和 push_reel 里读的一致，值不许超过钳位
    push_reel_src = Path("tools/push_reel.py").read_text(encoding="utf-8")
    m = re.search(r'TENNISLIVE_COPYPAGE_ATTEMPTS"?,', push_reel_src)
    assert m, "push_reel 不再读 TENNISLIVE_COPYPAGE_ATTEMPTS——工作流里配了也白配"
    attempts_cap = int(re.search(
        r"min\((\d+), int\(os\.environ\.get\(\"TENNISLIVE_COPYPAGE_ATTEMPTS",
        push_reel_src).group(1))
    delay_cap = float(re.search(
        r"min\((\d+(?:\.\d+)?), float\(os\.environ\.get\(\s*\n?"
        r"\s*\"TENNISLIVE_COPYPAGE_RETRY_SECONDS", push_reel_src).group(1))
    attempts = int(re.search(
        r'TENNISLIVE_COPYPAGE_ATTEMPTS: "(\d+)"', reel_body).group(1))
    delay = float(re.search(
        r'TENNISLIVE_COPYPAGE_RETRY_SECONDS: "(\d+(?:\.\d+)?)"',
        reel_body).group(1))
    assert attempts <= attempts_cap, (
        f"工作流写 {attempts} 次，而 push_reel 的钳位是 {attempts_cap}——"
        "多出来的会被静默钳掉，两个数从此对不上")
    assert delay <= delay_cap, f"间隔 {delay}s 超过钳位 {delay_cap}s，会被静默钳掉"
    # 探活总窗口要真的盖住实测最坏（14 分钟），否则调超时是白调
    assert attempts * delay >= 14 * 60, (
        f"探活窗口 {attempts}×{delay}s = {attempts * delay / 60:.0f} 分钟，"
        "盖不住实测 Pages 最坏的 14 分钟")
    # 这两个变量要挂在**发微信那一步**的 env 里（挂错步骤等于没配）
    send_step = reel_body[reel_body.index("- name: 推送到微信"):]
    send_step = send_step[:send_step.index("- name: ", 10)]
    assert "TENNISLIVE_COPYPAGE_ATTEMPTS" in send_step, (
        "探活变量没挂在「推送到微信」那一步的 env 里")

    # ③ 两条告警都要接住 cancelled
    for name, body in (("auto-push-reel", reel_body),
                       ("auto-push-explainer", expl_body)):
        alarm = body[body.index("- name: 失败时告警"):]
        if_line = re.search(r"if: (.+)", alarm).group(1)
        assert "failure()" in if_line and "cancelled()" in if_line, (
            f"{name} 的告警条件是 `{if_line}`——超时被掐是 cancelled，"
            "只挂 failure() 会让最该告警的那一种静默溜走")
