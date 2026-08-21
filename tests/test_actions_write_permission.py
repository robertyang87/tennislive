"""`actions: write` 只许给真的要点 Pages 的那几条工作流，一条不多一条不少。

**为什么这个权限存在：** GitHub 明文规定，用仓库自带的 `GITHUB_TOKEN` 推的 push
**不创建 workflow run**（防递归）。而复制页正是工作流自己 commit + push 的，
于是 `pages.yml` 的 `push` 触发器对**唯一重要的那条路径**是空的。解法是
`trigger_pages_build()` 主动 `workflow_dispatch` 一下——那正是那条禁令明文列出的
例外，而**发 dispatch 需要 `actions: write`**。

**两个方向都要拦，而且第二个方向是功能 bug 不是安全问题：**

| 方向 | 后果 |
|---|---|
| 给了却用不着 | 白扩一圈权限面 |
| 用得着却没给 | dispatch 静静失败 → Pages 不重建 → 探活探不到 → **复制页那颗按钮被摘掉** |

第二个方向这个仓库真栽过：伊埃拉那条推送连吃七次 404，按钮没了，而日志上和
「今天 Pages 慢」长得一模一样。

## ⚠️ 这条判据不声称权限还能再收窄——那是量过的

2026-08-14 逐条核过，**没有可收的地方**，别再重新论证一遍：

- **九条全部名副其实**：每一条都真的会跑到 `tennislive publish pushplus` /
  `tools/push_reel.py` / `tools/check_pages_trigger.py` 之一。删掉任何一条的
  `actions: write`，那条线的复制页按钮就会开始静默消失。
- **全部是单 job**，所以 workflow 级和 job 级是同一个东西，挪到 job 上收不窄。
- **九条里七条同时有 `contents: write`**，而 `contents: write` 严格更强（能往
  仓库里推代码）。在那七条上，`actions: write` 的**边际风险接近零**。
- 只有 `pages-selftest.yml` 和 `push-existing.yml` 是 `contents: read`，
  也就是这个权限没被压住的那两条——而它们恰好是全仓库**最不碰外部素材**的两条
  （一条只发一次 dispatch，16 秒；一条只发已经提交好的内容）。
- 再往下收要么换细粒度 PAT、要么换 GitHub App——**那是 GitHub 权限模型的粒度
  问题，不是这里偷懒**：`actions` 这个 scope 本身就是仓库级的，没有「只许 dispatch
  某一条工作流」这种粒度。

所以这条判据的职责是**守住现状不让它蔓延**（新工作流复制粘贴一个权限块是最常见的
走样方式），不是宣称还有余地。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

#: 真的会走到 `trigger_pages_build()` 的三个入口。
#:
#: 是按 (文件, 函数) 逐个扒调用链量出来的，不是按名字猜的——⚠️ **第一版按裸
#: 函数名跨模块做不动点，`main` 一进集合就把每个模块的 `main` 都染上了**，
#: 扒出来 `mp4_duration.py`、`fetch_flags.py` 全都「会走到」。收窄到本文件内
#: 传播之后，`pushmsg` 里只有 `drop_dead_copy_button`、`push_reel` 里只有
#: `main` / `wait_for_copy_page`、`cli` 里只有 `cmd_publish_pushplus`。
_PAGES_ENTRIES = (
    (r"tennislive\s+publish\s+pushplus", "tennislive publish pushplus"),
    (r"push_reel\.py", "tools/push_reel.py"),
    (r"check_pages_trigger\.py", "tools/check_pages_trigger.py"),
)

#: `actions: write` 的**第二种**正当理由：这条工作流自己要派发别的工作流。
#:
#: ⚠️ **2026-08-16 补的，而补它的方式值得记一笔。** 这条判据的原始前提是
#: 「`actions: write` 只为点 Pages 而存在」——那句话在写它的时候是真的，
#: `orchestrate.yml`（编排器的 apply 分支 `gh workflow run` 派发生产工作流）
#: 一进 main 就不成立了，于是它被判成「权限块是从别处复制粘贴来的」，
#: 而报错还教人去**删掉那行 `actions: write`**——照做的话 apply 那条路
#: 会静静地 dispatch 失败，正是这条判据下半截专门要防的那种功能 bug。
#:
#: **判据要跟着结构走，不是跟着当初那一版的数走**（CLAUDE.md 记过同一个形状：
#: 解读卡的门槛按两张卡定，砍成一张之后就成了一条常年红）。所以不是放宽成
#: 「谁要谁拿」，是**把第二个正当理由显式登记进来，两个方向照旧都钉**：
#: 给了就必须落在这两类里的某一类，用得着就必须给。
#:
#: ⚠️ **按工具入口写，不按 `gh workflow run` 这个字面写**，和 `_PAGES_ENTRIES`
#: 完全同一个形状：真正 dispatch 的那一句在 `tools/orchestrate.py:243`
#: （`["gh", "workflow", "run", wf, …]`），**YAML 里只出现工具名**。
#: 第一版我按字面扫，当场还是红——因为 `orchestrate.yml` 里 `gh workflow run`
#: 只出现在**注释**里（第 6 行和第 63 行），而 `_yaml_only` 正好把注释剥掉了。
#: 又一次「查的东西和跑的东西不是一回事」。
_DISPATCH_ENTRIES = (
    (r"orchestrate\.py", "tools/orchestrate.py"),
    # ⚠️ **必须排除 `test_` 前缀**：`tests/test_dispatch_reel_queue.py` 这个
    # 文件名本身，从下标 5 开始读就是裸的 `dispatch_reel_queue.py`——一个不带
    # 词边界的子串正则会把「跑测试」误判成「真的在 dispatch」。
    (r"(?<!test_)dispatch_reel_queue\.py", "tools/dispatch_reel_queue.py"),
    (r"gh\s+workflow\s+run", "gh workflow run（直接写在 run: 里）"),
    (r"gh\s+api\b[^\n]*/dispatches", "gh api …/dispatches"),
)


def _yaml_only(text: str) -> str:
    """去掉注释再扫。

    ⚠️ **这个仓库的注释正是教训的存放处**，正文里必然写着当年那些错值和不该装的
    东西——连注释一起扫，「把坑记下来」会被判成「又踩了这个坑」（同一个错这里
    犯过五次）。

    ⚠️ **剥完注释要把行尾的空白一起收掉。** 少了这一步，写成

        actions: write    # apply 分支 gh workflow run 派发别的生产工作流

    的那一行剥完是 `  actions: write    `——**尾巴上那四个空格还在**，而下面那条
    权限块的正则要求值后面直接换行，于是整个 `permissions:` 块匹配不上，报出来
    是「有 actions: write 却找不到顶层 permissions 块」。`orchestrate.yml`
    2026-08-16 就是这么红的：**权限块写得好好的，判据自己剥出来的残渣把它挡住了。**
    这跟本文件上面那条「注释被误伤」是一家的，只不过误伤它的不是注释本身，
    是**去掉注释之后剩下的那点空白**。
    """
    lines = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    return "\n".join(re.sub(r"#.*", "", l).rstrip() for l in lines)


def _run_scripts(path: Path) -> str:
    """这条工作流里**真正会执行的那些 `run:` 脚本**，拼成一份文本。

    ⚠️ **`_PAGES_ENTRIES` / `_DISPATCH_ENTRIES` 只许扫这个，不许扫整份
    `_yaml_only` 文本。** `reel-queue-ci.yml` 2026-08-20 就是这么误报的：
    它的 `on.pull_request.paths` 里为了「这个文件变了就跑一下」写着
    `"tools/dispatch_reel_queue.py"`——那是**触发条件**，这条工作流自己
    一次 dispatch 都没发，job 里只跑了 `pytest -q
    tests/test_dispatch_reel_queue.py`（测试那个脚本的逻辑，不是执行它）。
    整份文本一起扫会把「提到过这个文件名」和「真的调用了它」混成一件事。

    和 `test_interview_clip.py::_run_scripts` 是同一个函数，只是这份
    接受 `Path` 而不是相对工作流名——两处各自维护是因为一个读单个工作流、
    一个要跨着 32 个文件循环，共用一份还得先对齐参数形状，不值当。
    """
    import yaml  # noqa: PLC0415

    wf = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for job in (wf.get("jobs") or {}).values():
        for step in job.get("steps") or []:
            for ln in str(step.get("run") or "").splitlines():
                if not ln.lstrip().startswith("#"):
                    out.append(ln)
    return "\n".join(out)


def test_给了actions_write的工作流都真的要点Pages():
    """两个方向一起钉：给了就必须用得着，用得着就必须给。"""
    files = sorted(WORKFLOWS.glob("*.yml"))
    # 判据自己的判据：目录改名 / glob 写错的样子就是空列表，而那时这条测试
    # 会安安静静地全绿。
    assert len(files) >= 15, f"只扫到 {len(files)} 条工作流，判据失效了"

    granted, needed = set(), {}
    pages_only = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        body = _yaml_only(text)
        if re.search(r"^\s*actions:\s*write", body, re.M):
            granted.add(path.name)
        # ⚠️ `hits` 只吃 `_run_scripts`，不吃整份 `body`——见 `_run_scripts`
        # 的 docstring，`on.paths` 里的文件名不算「用得着」。
        run_body = _run_scripts(path)
        hits = [label for pat, label in _PAGES_ENTRIES if re.search(pat, run_body)]
        if hits:
            pages_only.add(path.name)
        hits += [label for pat, label in _DISPATCH_ENTRIES
                 if re.search(pat, run_body)]
        if hits:
            needed[path.name] = hits

    # 判据自己的判据②：一条都没扫出来的话下面两个集合差恒为空。
    assert granted, "一条 actions: write 都没扫到——权限块的写法变了？"
    assert pages_only, "一条会点 Pages 的工作流都没扫到——三个入口的名字变了？"

    多给 = sorted(granted - set(needed))
    assert not 多给, (
        f"这几条有 actions: write 却既不点 Pages 也不派发别的工作流：{多给}\n"
        "要么是权限块从别处复制粘贴来的（最常见的走样方式），要么是那条线不再"
        "推送了。删掉它那行 `actions: write`。")

    少给 = sorted(set(needed) - granted)
    assert not 少给, (
        "这几条要么点 Pages 要么派发别的工作流，却没有 `actions: write`："
        + "".join(f"\n  {name} → {needed[name]}" for name in 少给)
        + "\n\n⚠️ **这是功能 bug 不是安全问题**：dispatch 会静静失败。"
          "点 Pages 那一支的后果是 Pages 不重建 → 探活探不到 → 复制页那颗按钮"
          "被摘掉，而日志上它和「今天 Pages 慢」长得一模一样；派发那一支的后果是"
          "编排器报告说「已 dispatch」而实际上一条都没发出去。给它加上 "
          "`actions: write`。")

    print(f"  {len(granted)} 条给了 actions: write，和真正用得着的那 "
          f"{len(needed)} 条完全重合（其中 {len(pages_only)} 条是为点 Pages）")


def test_点Pages那几条不许再多要别的权限():
    """⚠️ 复制粘贴一个权限块的时候，跟着来的往往不止一行。

    所以除了 `contents` 和 `actions`，这几条不许出现别的 scope——真需要
    （比如哪天要 `packages: write`）就在这儿显式放行，让它是一次看得见的决定。
    `pages.yml` 自己不在这张网里：它是被点的那一条，`pages: write` +
    `id-token: write` 正是它的本分。
    """
    允许 = {"contents", "actions"}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        if not re.search(r"^\s*actions:\s*write", body, re.M):
            continue
        # ⚠️ 用 `[ \t]` 不用 `\s`：`\s` 吃换行，`\s*\S+` 会从空行一路跨到
        # `jobs:` 底下的 job 名，于是权限块被读成「还有 jobs / runs-on /
        # timeout-minutes 三个 scope」。第一版就是这么误报的——**判据宁可窄，
        # 不可宽**，而这次糊掉的不是范围，是行边界。
        block = re.search(r"^permissions:\n((?:[ \t]+[\w-]+:[ \t]*[\w-]+\n)+)",
                          body, re.M)
        assert block, f"{path.name} 有 actions: write 却找不到顶层 permissions 块"
        scopes = {m.group(1)
                  for m in re.finditer(r"^[ \t]+([\w-]+):", block.group(1), re.M)}
        多余 = sorted(scopes - 允许)
        assert not 多余, (
            f"{path.name} 的权限块里除了 {sorted(允许)} 还有 {多余}——"
            "权限块是复制粘贴的重灾区，多的那几行八成不是想清楚才加的。"
            "真需要就把它加进这条判据的白名单，让它是一次看得见的决定")
