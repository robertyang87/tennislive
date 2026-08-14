"""赛后开麦「合进 main 就自动发微信」的五道闸。

**这条线 2026-08-14 之前一条自动推送都没有**，而且不是配漏了，是
**结构性够不着**：`auto-push-reel` 的路径正则写着
`output/<日期>/reel/<slug>/render.json`，采访产物却在
`output/interviews/<slug>/`——没有日期那一层。量出来的代价是 18 条 spec
里 0 条写了 `push.auto`、18 个产物目录里 0 个 `pushed.json`，而赛后开麦是
时效最紧的一条。

所以这份测试有两件事要盯，缺一不可：

1. **五道闸各自真的在拦**（每道都反向验证：不只验「该发的发了」，
   更要验「不该发的一条都没发」）；
2. **路径正则真的匹配得到这条线的目录形状**——用仓库里**真实的**产物路径验，
   不拿手搓的字符串。手搓的只能证明「我写的正则符合我以为的形状」，
   而这次出事的正是「我以为的形状」本身。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import auto_push_gate as reel_gate  # noqa: E402
import auto_push_interview_gate as gate  # noqa: E402

WORKFLOW = Path(".github/workflows/auto-push-interview.yml")


def _yaml_only(text: str) -> str:
    """去掉整行注释再扫。

    这个仓库的工作流注释正是记教训的地方，正文里必然写着当年那些错值；
    而这一次更要紧的是反方向：注释里出现 `auto` / `main` / `--record`
    会让漏配的写法**假绿**。
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args],
                   check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """一个最小的**真 git 仓库**：一条 spec、一份文案、一个渲好的 outdir。

    ⚠️ 必须是真 git：「已经推过」和「海报在不在」两道闸查的都是
    `git ls-files`，不是 `test -f`——喂一个普通目录就把它们绕过去了，
    而绕过去之后测试**照样绿**。

    ⚠️ **海报要有。** 一条真渲完的采访必然带着 `poster.jpg`
    （`interview-clip.yml` 的清理那步按后缀删 html、按前缀删 `_*`，
    特意把它留着），所以这个 fixture 也得有——这样「该发的照发」那几条
    验的才是它们各自那道闸，而不是被海报闸拦下。
    """
    (tmp_path / "specs/interviews").mkdir(parents=True)
    (tmp_path / "specs/interviews/demo.xhs.txt").write_text(
        "文案", encoding="utf-8")
    outdir = tmp_path / "output/interviews/demo"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text(
        json.dumps({"video_url": "https://example/x.mp4"}), encoding="utf-8")
    (outdir / "poster.jpg").write_bytes(b"\xff\xd8\xff not-a-real-jpeg")
    _git(tmp_path, "init", "-q")
    # render.json 提交进仓库——现实里它就是先由 interview-clip 提交、随 PR
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
    # 采访 spec 的栏目名在**顶层 `column`**，不是 `cover.eyebrow`——
    # 两条线放在不同字段，`push_reel.column_of` 在那儿收口。
    body: dict = {"column": "赛后开麦"}
    if push is not None:
        body["push"] = push
    (repo / f"specs/interviews/{slug}.json").write_text(
        json.dumps(body, ensure_ascii=False), encoding="utf-8")


def _second_interview(repo: Path, slug: str = "demo2") -> Path:
    """再造一条**渲完的**采访（spec + 文案 + render.json + 海报）。

    海报在这儿是必需品，不是装饰：少了它「海报在仓库里」那道闸会把这条
    候选筛掉，于是「一趟带进来两条」那类测试只剩一个候选、恒绿——一道
    真闸就这么被另一道闸悄悄遮住了。收在一处，别在每个测试里各写一遍。
    """
    _spec(repo, {"auto": True}, slug=slug)
    (repo / f"specs/interviews/{slug}.xhs.txt").write_text(
        "文案", encoding="utf-8")
    outdir = repo / f"output/interviews/{slug}"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text("{}", encoding="utf-8")
    (outdir / "poster.jpg").write_bytes(b"\xff\xd8\xff not-a-real-jpeg")
    return outdir


CHANGED = ["output/interviews/demo/render.json"]


# ------------------------------------------------- 闸 1：路径（真实产物形状）

def _real_render_json() -> list[str]:
    """仓库里**真实**的采访 render.json 路径。

    ⚠️ 用 `git ls-files`，不是 `Path("output").glob(...)`。两个理由：
    ① CI 的检出是**非 cone 稀疏模式**，而这条线还有别的工作流按别的模式检出
      ——按文件系统扫会随检出方式变；索引不受稀疏影响（条目只是被标了
      skip-worktree），`git ls-files` 在哪种模式下都数得到同一批。
    ② 这正是闸自己判「在不在仓库里」用的那把尺（`tracked()`），
      判据和被判的东西用同一个口径。
    """
    done = subprocess.run(
        ["git", "ls-files", "output/interviews/*/render.json"],
        capture_output=True, text=True, check=True)
    return [line for line in done.stdout.splitlines() if line.strip()]


def test_路径正则认得出真实的采访产物形状(tmp_path: Path):
    """**这条测试就是这次问题的判据本身。**

    `auto-push-reel` 够不着这条线，不是因为谁把配置写错了，是因为两条线的
    目录形状不一样：reel 是 `output/<日期>/reel/<slug>/`，采访是
    `output/interviews/<slug>/`——**没有日期那一层**（`push_reel.headline`
    的注释写着这是故意的：同一场采访哪天发都可能）。

    所以拿仓库里**真实**的路径来验，不拿手搓的字符串：手搓的只能证明
    「我写的正则符合我以为的形状」，而出事的正是「我以为的形状」。
    """
    real = _real_render_json()
    # **判据自己的判据。** 主语没了（换了目录、glob 写错、CI 上没检出）时
    # 要当场出声，而不是变成一条恒真的绿灯——空列表和「全都匹配」在
    # `all()` 下长得一模一样，这个仓库为它栽过。
    assert len(real) >= 10, (
        f"只数到 {len(real)} 条真实的采访 render.json，判据失效了——"
        "要么路径变了，要么这条 git ls-files 没数到东西")

    for path in real:
        slug, outdir = gate.candidate(path, tmp_path)
        # slug 要和目录名对得上，outdir 要指回同一格
        assert path == f"output/interviews/{slug}/render.json"
        assert outdir == tmp_path / "output" / "interviews" / slug


def test_reel那条路结构性够不着采访产物(tmp_path: Path):
    """**这条钉的是「为什么要单独开一条」，不是重复上一条。**

    如果哪天 `auto_push_gate` 真的兼容了这个形状（比如参数化成一份代码），
    这条会红——那正是该来删掉这份工作流和这份判据的时候，而不是让两条路
    悄悄都能匹配、同一条采访被发两次。
    """
    real = _real_render_json()
    assert len(real) >= 10, "判据失效了：没数到真实的采访 render.json"
    for path in real:
        with pytest.raises(reel_gate.Skip):
            reel_gate.candidate(path, tmp_path)


@pytest.mark.parametrize("path", [
    "output/interviews/demo/poster.jpg",          # 不是 render.json
    "output/interviews/demo/sub/render.json",     # 多了一层
    "output/2026-08-03/reel/demo/render.json",    # 那是 reel，走另一条路
    "output/2026-08-03/knowledge/demo/render.json",
    "specs/interviews/demo.json",                 # 压根不在 output 下
])
def test_形状不对的路径一律不发(repo: Path, path: str):
    _spec(repo, {"auto": True})
    assert gate.pick([path], repo) is None


# ---------------------------------------------------------------- 闸 2：认领

def test_没写auto的一条都不发(repo: Path, capsys):
    """**默认关。** 现在 `specs/interviews/` 下 18 条 spec 一条都没写
    `push.auto`，也就是说这条工作流合并之后**什么都不会发**——要开得再动
    一次手，一条一条想清楚。
    """
    _spec(repo, {"summary": "伊埃拉六连胜"})
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
    甚至 2026-08-13 那次「历史成片迁上 Release，链接写进 render.json」
    一口气改了 17 份。没有这道闸，已经发过的采访会被再发一次。
    """
    _spec(repo, {"auto": True})
    gate.record(repo / "output/interviews/demo",
                "https://example/run/1", "2026-08-14T00:00:00Z")
    _commit_all(repo)
    assert gate.pick(CHANGED, repo) is None
    out = capsys.readouterr().out
    assert "已经推过了" in out and "example/run/1" in out, (
        f"跳过了却没说是哪一趟发的，出问题时无从查起：{out}")


def test_没提交的标记不算数(repo: Path):
    """只写在工作区、没进仓库的 `pushed.json` **不能**算「已经发过」。

    如果认它，一次失败的 run 留下的半截文件就会把这条采访永久锁死，
    而且不吭声。反过来说，这也正是它必须查 `git ls-files` 的另一半理由。
    """
    _spec(repo, {"auto": True})
    gate.record(repo / "output/interviews/demo", "run", "now")
    # 故意不提交
    assert gate.pick(CHANGED, repo) is not None


def test_稀疏检出下也要拦得住(repo: Path):
    """这条工作流是稀疏检出的：判断的时候 `output/` 那一格还没
    `git sparse-checkout add` 回来，文件根本不在工作区——按
    `(outdir / MARKER).is_file()` 判那道闸**恒为假，会重复发**。

    这条测试把工作区里那份删掉（模拟稀疏检出的样子），索引里留着，
    要求照样拦得住。反向验证过：退回 `is_file()` 当场红。
    """
    _spec(repo, {"auto": True})
    marker = gate.record(repo / "output/interviews/demo", "run", "now")
    _commit_all(repo)
    marker.unlink()  # ← 稀疏检出之后工作区里就是没有它
    assert gate.pick(CHANGED, repo) is None


# ---------------------------------------------------------------- 闸 4：海报

def test_海报不在仓库里就不发(repo: Path, capsys):
    """**这条线现在一张海报都没有，所以这道闸上来就会拦下所有存量。**

    2026-08-13 `archive-media.yml mode=purge` 用 git filter-repo 从全史抹掉了
    output/ 下所有 jpg（认领过的取舍，17 GB → 789 MB）。量过（2026-08-14）：
    `git ls-files 'output/interviews/*/poster*'` **零命中**，18 个产物目录
    一张不剩。

    海报是推送正文的第一屏，没有它这条消息只剩两个按钮，看不出这是谁的采访。
    """
    _spec(repo, {"auto": True})
    (repo / "output/interviews/demo/poster.jpg").unlink()
    _git(repo, "rm", "-q", "--cached", "output/interviews/demo/poster.jpg")
    _commit_all(repo)

    assert gate.pick(CHANGED, repo) is None, (
        "海报不在仓库里还照发——推出去就是一条没有第一屏的消息，"
        "而微信那条消息收不回来")
    out = capsys.readouterr().out
    assert "poster.jpg" in out, f"跳过了却没说是海报的问题：{out}"
    # 报错要说出路，不能只说不行。这条线的出路比 reel 便宜：`mode=cover`
    # 下源片、抽帧、渲海报、删源片，一个 mp4 都不产生。
    assert "mode=cover" in out, f"没说怎么把它救回来：{out}"


def test_海报在就照发(repo: Path):
    """反向验证上一条：同样的输入，只把海报放回去，就该发。

    没有这一条的话，「一条都不发」可以由任何一个 bug 造成——**证明不了
    是海报那道闸在起作用**。
    """
    _spec(repo, {"auto": True})
    picked = gate.pick(CHANGED, repo)
    assert picked is not None, "海报好好地在仓库里，却被拦下了"
    assert picked[0] == "demo"


def test_稀疏检出下海报也要认得出(repo: Path):
    """**这道闸最容易写错的地方，而写错的后果比漏发大得多。**

    这个脚本排在 `git sparse-checkout add` **之前**——`output/` 那一格根本
    不在工作区。按 `(outdir / "poster.jpg").is_file()` 判就是**恒为假**：
    不是漏发一条，是**每一条都不发**，整条自动推送静静地死掉，而 run 还是绿的。

    这条把工作区里那份删掉（模拟稀疏检出的样子）、索引里留着，要求照常发。
    反向验证过：把 `tracked()` 换成 `is_file()` 当场红。
    """
    _spec(repo, {"auto": True})
    _commit_all(repo)
    (repo / "output/interviews/demo/poster.jpg").unlink()

    picked = gate.pick(CHANGED, repo)
    assert picked is not None, (
        "海报在仓库里、只是没检出到工作区，就被判成「没有海报」——"
        "按 is_file() 判的话每一条都会这样")
    assert picked[0] == "demo"


# ---------------------------------------------------------------- 闸 5：只发一条

def test_一趟带进来两条就一条都不发(repo: Path):
    """批量自动发微信，错一次就是错一片。

    这条线尤其撞得上：2026-08-13 那次「历史成片迁上 Release」一个提交改了
    **17 份** render.json。
    """
    _spec(repo, {"auto": True})
    _second_interview(repo)
    _commit_all(repo)

    with pytest.raises(SystemExit):
        gate.pick(CHANGED + ["output/interviews/demo2/render.json"], repo)


def test_删除的render_json不算候选(repo: Path, capsys):
    """清理旧版产物的合并会把**删除**的 render.json 也带进 changed 列表。
    被删的产物不是新渲完的片子——它的 spec 往往还写着 auto:true、目录里
    又没有 pushed.json，不拦的话会凑成「一次 N 条」把真该发的一起拦死。
    """
    _spec(repo, {"auto": True})
    _git(repo, "rm", "-rq", "output/interviews/demo")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "清理旧产物")
    assert gate.pick(CHANGED, repo) is None
    assert "已不在仓库里" in capsys.readouterr().out, "跳过要说出为什么"


def test_同一批里删一条活一条要发活的那条(repo: Path):
    """删掉被顶替的旧版 + 新渲的一条。删除项被滤掉后，活的那条必须照常发
    ——别把防批量的闸误触发。"""
    _spec(repo, {"auto": True})
    _second_interview(repo)
    _commit_all(repo)
    _git(repo, "rm", "-rq", "output/interviews/demo")
    _git(repo, "-c", "user.email=a@b", "-c", "user.name=c",
         "commit", "-qm", "清理旧产物")

    picked = gate.pick(CHANGED + ["output/interviews/demo2/render.json"], repo)
    assert picked is not None and picked[0] == "demo2", (
        "删除项混进来把活的那条也拦死了——防批量的闸不该被幽灵候选触发")


def test_工作流的diff要滤掉删除项():
    """第一层在 workflow：`--diff-filter=AM`。没有它，删除的 render.json
    一样进 changed 列表——闸挡得住，但一趟 run 会红着结束，真该发的那条
    要等人来查。"""
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    line = next(l for l in body.splitlines()
                if "git diff" in l and "render.json" in l)
    assert "--diff-filter=AM" in line, (
        "auto-push-interview 的 diff 少了 --diff-filter=AM：删除的 render.json "
        "会被当成候选")


# ------------------------------------------------- 共用的部分：import，不抄

def test_共用的那几样是import来的不是抄的():
    """`Skip` / `tracked` / `MARKER` / `record` 跟哪条线无关，两条路必须是
    **同一个对象**。

    判据用 `is`，不是「行为一样」：抄一份的话行为一开始当然一样，
    分叉是后来发生的，而分叉的样子是——改了 reel 那头的标记名，这头静默
    失配，于是同一条采访被发第二次。`Skip` 更硬：抄一份的话
    `except Skip` 根本捕不到对方那个类。
    """
    assert gate.Skip is reel_gate.Skip
    assert gate.tracked is reel_gate.tracked
    assert gate.record is reel_gate.record
    assert gate.MARKER == reel_gate.MARKER == "pushed.json"


def test_两条线分叉的只有路径形状和spec目录():
    """反过来钉一头：真正该各写各的只有这两样。

    没有这条的话，上一条只证明「共用的没抄」，证明不了「没共用的确实
    只有这两样」——下一个人往这个文件里再抄一段 reel 的逻辑，两条都绿。
    """
    assert gate.SPEC_DIR == Path("specs/interviews")
    assert reel_gate.SPEC_DIR == Path("specs/reels")
    assert gate.SPEC_DIR != reel_gate.SPEC_DIR


# ------------------------------------------------- 标题日期：算一次，两处共用

def test_标题日期算一次两处共用(tmp_path: Path, monkeypatch):
    """**这条线独有的一个数。**

    采访产物目录里没有日期（故意的），所以 `push_reel` 解不出来、必须显式
    传 `--date`。而 `--stage page` 和真正发微信那次**各算一遍标题**，
    `wait_for_copy_page(expect=title)` 要求两次算出同一句——两步之间跨过
    上海午夜的话，两次 `date +%F` 会给出两个日期，于是复制页去等一句
    **永远不会出现**的话，等满 40 分钟再静静把按钮摘掉，**run 还是绿的**。

    所以日期从 gate 出一次，两步都引它。这条钉两头：gate 真的出了这个值，
    而工作流那两步真的引的是它、不是各自 `date +%F`。
    """
    out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    gate._emit("demo", Path("output/interviews/demo"))
    written = dict(
        line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines())
    assert written["date"] == gate.shanghai_today()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", written["date"])

    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    dates = re.findall(r"--date [^\n]*", body)
    assert len(dates) == 2, f"写复制页和推送各要一次 --date，数到 {len(dates)} 次"
    for line in dates:
        assert "steps.gate.outputs.date" in line, (
            f"这一步自己算了日期，没引 gate 那一份：{line}\n"
            "两处各算一次，跨过上海午夜就分叉——而分叉的样子是「复制页按钮"
            "偶尔没有」，run 照样绿")
    assert "date +%F" not in body, (
        "工作流里还有人自己算标题日期——这个数只许有一个出处")


def test_上海日期不靠tzdata():
    """用固定的 UTC+8，不用 `ZoneInfo("Asia/Shanghai")`。

    中国 1991 年起不再实行夏令时，这个偏移是恒定的；而 `ZoneInfo` 要系统的
    tzdata，缺了它抛 `ZoneInfoNotFoundError`——排在最前面的一步抛出一个跟
    日期毫无关系的错，表现就是整条自动推送不发。
    """
    body = Path("tools/auto_push_interview_gate.py").read_text(encoding="utf-8")
    src = re.sub(r'"""[\s\S]*?"""', "", body)
    src = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert "ZoneInfo" not in src, "别把 tzdata 拖进这条路"
    assert "timedelta(hours=8)" in src


# ---------------------------------------------------------------- 工作流本身

def test_自动推送只在main上跑():
    """GitHub Pages 只服务 main（复制页在分支上永远 404），而海报链接钉在
    commit sha 上——未合并的 commit 有被 GC 的风险。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    trigger = body.split("permissions:")[0]
    assert "branches: [main]" in trigger, "没限定 main"
    assert "output/interviews/*/render.json" in trigger, (
        "触发路径不是采访产物的形状")
    assert "workflow_dispatch" not in trigger, (
        "别再给它开手动入口——手动推送走 interview-clip mode=push，"
        "那条路有完整的预检和参数")


def test_自动推送不许取消正在跑的():
    """取消一个已经发出 POST 的 run，只会让「发没发出去」变成未知，
    而 `pushed.json` 那一笔可能没记上——下一次触发就会再发一遍。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert re.search(r"cancel-in-progress:\s*false", body), (
        "自动推送不许 cancel-in-progress: true")


def test_自动推送这条路不装出片那一堆():
    """它不下源片、不转写、不烧字幕、不编码——装那一堆就是白等几分钟，
    而这条路的全部意义就是省掉人的往返。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    for heavy in ("ffmpeg", "playwright", "chromium", "rembg", "yt-dlp",
                  "faster-whisper", "edge-tts", "fonts-noto"):
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
    这条采访从此再也发不出去，而且不吭声。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert body.index("--stage page") < body.index("--record"), (
        "复制页写在了记标记之后")
    send = body.index("TENNISLIVE_ASSET_REV")
    assert send < body.index("--record"), "记已推送排到了发微信前面"


def test_等复制页的窗口要装得进job的超时():
    """**60 × 40s = 40 分钟**，照抄 `interview-clip.yml`（这条线的 Pages
    实测能慢到 14 分钟以上）。而 job 的 `timeout-minutes` 必须比它大——
    小了的话等待还没走完 job 就被砍，**砍掉的时机正好在「复制页已提交、
    微信一个字没发」那一段**，而且没有任何「已发过」标记会记下这件事。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    attempts = int(re.search(r'TENNISLIVE_COPYPAGE_ATTEMPTS:\s*"(\d+)"',
                             body).group(1))
    delay = int(re.search(r'TENNISLIVE_COPYPAGE_RETRY_SECONDS:\s*"(\d+)"',
                          body).group(1))
    timeout = int(re.search(r"timeout-minutes:\s*(\d+)", body).group(1))
    assert timeout * 60 > attempts * delay, (
        f"等复制页最长 {attempts * delay}s，而 job 只给 {timeout * 60}s——"
        "等待走不完就会被砍在「已提交、没发消息」那一段")


# **2026-08-14 冻结：这 17 条在自动推送上线之前就已经推过微信了。**
#
# 判据不是记忆，是产物：`git ls-files output/interviews/<slug>/copy.html`
# ——复制页是推送流程写的，它在仓库里就说明这条走过那条路（`swiatek-shnaider-
# tor2026-qf` 没有，它只到 `--stage subs`，push 块也是空的）。
#
# **给它们开 `push.auto` 是这条线上唯一能造成重发的动作**：闸 3 查的是
# `pushed.json`，而这 17 条一个都没有（自动推送那天才有这个机制），拦不住。
# 而微信那条消息发出去收不回来。
#
# ⚠️ **只许减不许加。** 减是有意义的（哪条真要重发，那是一次看得见的决定）；
# 加进来只会把「以后新写的采访也不许开」偷偷变成规矩，而这条线本来就该开。
_ALREADY_PUSHED = frozenset({
    "alexandrova-sabalenka-tor2026-r16",
    "eala-mcnally-toronto-2026-r3",
    "eala-mcnally-toronto-2026-r3-presser",
    "eala-mcnally-toronto-2026-r3-presser-full",
    "eala-osaka-dc2026-sf",
    "eala-osaka-dc2026-sf-studio",
    "eala-parks-toronto-2026",
    "eala-pegula-dc2026-final",
    "eala-pegula-dc2026-final-presser",
    "eala-svitolina-dc2026-qf",
    "pegula-eala-dc2026-final",
    "rybakina-gauff-tor2026-sf",
    "rybakina-osaka-tor2026-qf",
    "sabalenka-uchijima-tor2026-r64",
    "sabalenka-zhang-tor2026-r3",
    "shang-rublev-mtl2026-r2",
    "shelton-mensik-mtl2026-qf",
})


def test_已经推过的老spec不许开自动推送():
    """**这条线上唯一能造成重发的动作，就是给这 17 条开 `auto`。**

    闸 3（没推过）查的是 `pushed.json`，而它们一个都没有——自动推送是
    2026-08-14 才有的，之前每一次推送都是人手动 dispatch，没有任何东西
    记下「发过了」。所以那道闸对存量是哑的，只能在 spec 这头拦。

    ⚠️ **这条不拦新写的采访。** 给一条还没发过的采访写 `"auto": true` 正是
    这套机制存在的理由；它推过一次之后 `pushed.json` 会进仓库，闸 3 从那时起
    接管，`auto` 留着完全正常——所以这里**不能**去断言「开了 auto 的都还没
    pushed.json」，那会在第一条自动推送成功的当天变成一条常年红。
    """
    for slug in sorted(_ALREADY_PUSHED):
        push = json.loads(
            (Path("specs/interviews") / f"{slug}.json").read_text(
                encoding="utf-8")).get("push") or {}
        assert push.get("auto") is not True, (
            f"{slug} 在自动推送上线之前就推过微信了，而它没有 pushed.json——"
            "开了 auto 就是把同一条消息再发一遍，而消息收不回来")


def test_那张已推送名单自己要立得住():
    """**一个会过期的名单和一条常年红的检查是同一个毛病。**

    名字写错一个，上面那条对它就是哑的（读的是一个不存在的 slug，
    `FileNotFoundError` 倒还算出声）——更坏的是**漏掉一条**：那条老 spec
    就不在任何判据的射程里了。所以两头都自证：

    - 名单里每个 slug 都还是一条真 spec；
    - 仓库里**每一个**有 `copy.html`（＝走过推送流程）的 slug 都在名单里。
    """
    done = subprocess.run(["git", "ls-files", "output/interviews/*/copy.html"],
                          capture_output=True, text=True, check=True)
    published = {line.split("/")[2] for line in done.stdout.split() if line}
    assert len(published) >= 10, (
        f"只数到 {len(published)} 条有复制页的采访，判据失效了")

    for slug in sorted(_ALREADY_PUSHED):
        assert (Path("specs/interviews") / f"{slug}.json").is_file(), (
            f"名单里的 {slug} 已经不是一条 spec 了——名字写错的豁免是一盏恒真的绿灯")
    missing = sorted(published - _ALREADY_PUSHED)
    assert not missing, (
        f"这些采访走过推送流程却不在名单里：{missing}——"
        "它们同样没有 pushed.json，给它们开 auto 一样会重发")


def test_只add自己那一格():
    """`git add --sparse`，而且只 add 本次那个 outdir。

    ⚠️ **`--sparse` 不能漏**：稀疏模式下裸的 `git add` 对 cone 外的路径只
    警告、退出码 0，然后 `git diff --cached --quiet` 说「没有变化」——
    `pushed.json` 静默丢掉，下一次触发就再发一遍。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    adds = [l.strip() for l in body.splitlines() if l.strip().startswith("git add")]
    assert adds, "工作流里一句 git add 都没有？"
    for line in adds:
        assert "--sparse" in line, f"稀疏检出下 git add 要带 --sparse：{line}"
        assert "steps.gate.outputs.outdir" in line, (
            f"add 的不是本次那一格：{line}")
