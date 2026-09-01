"""竖版赛报短片这条线上的规矩（CLAUDE.md：规则要落成测试）。

都是踩出来的：

- **成片帧率要跟着源片走**。源片 25 fps、成片硬定 30，就是每 5 帧补一帧。
- **默认不横摇**。窗口只有源片 32% 宽，一摇，画面里本该静止的底线、球网、
  广告板、看台全跟着滑，25 fps 下滑动的静止物最容易看出一格一格。
- **复制页要在 git commit 之前写**。它由 GitHub Pages 提供，没进仓库就是 404。
  run 30342567879 里推送步骤 success、日志里印着复制页链接，点开却 404——
  因为写文件那一句挤在推送步骤里，而推送排在提交之后，文件只活在 runner 的
  工作区。**这是「查信号不查产物」的又一次**：success 是信号，仓库里那个文件
  才是产物。
- **推送标题必须让人一眼看出谁赢了**，所以给了赛果就把「vs」换成比分。
"""

import ast
import hashlib
import json
import inspect
import os
import re
import subprocess
import math
import sys
from fnmatch import fnmatch
from pathlib import Path

import pytest

WORKFLOW = Path(".github/workflows/match-reel.yml")



def _quote_str(raw) -> str:
    """`quote` 现在也可以写成**按条声明**的列表（中英双语字幕，一条一行）。

    扫 spec 的判据一律先过这儿：老写法是一个字符串，新写法是 `list[str]`，
    而**两种都是要发出去的字**，规矩一视同仁。
    第一版这两处直接 `s.get("quote") or ""`，喂进 `re.search` 当场 TypeError。
    """
    if isinstance(raw, list):
        return " ".join(str(x) for x in raw)
    return str(raw or "")


def _steps(text: str) -> list[str]:
    """按 `      - name:` 切出步骤名，顺序即执行顺序。"""
    return [
        line.split("- name:", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("      - name:")
    ]


def _step_block(name: str, text: str | None = None) -> str:
    """取某一步自己那一段——**先去掉整行注释，再锚在步骤头上**。

    两个坑都真踩过：

    1. **按裸的步骤名切会先命中注释**。工作流的注释正是这个仓库记教训的地方，
       正文里必然引用别的步骤名（「中间『丢掉不进仓库的中间物』把它删了」）——
       于是 `text.index("丢掉不进仓库的中间物")` 切到的是一段注释，
       抽不出任何 `rm` 模式，六条测试一起红。
    2. **锚对了还要切对**：从 `- name:` 开始切、再按 `- name:` 分割，
       会在第 0 位截断，拿到一个空串。要按整行头 `\n      - name:` 切。
    """
    body = _yaml_only(text if text is not None else
                      WORKFLOW.read_text(encoding="utf-8"))
    head = f"      - name: {name}"
    start = body.index(head)
    return body[start:].split("\n      - name:", 1)[0]


def test_只给mode等于push不给push等于true要当场报错():
    """⚠️ **两个开关管同一件事，只拨一个 run 照样绿。**

    `mode=push` 的唯一目的就是发微信（工作流开头写着「成片已经在仓库里，
    只写复制页 → 提交 → 发微信」），可真正发消息那一步的 `if:` 认的是
    `inputs.push`。2026-08-05 我只传了 `mode=push`：run 30969384140
    **27 秒跑完、绿的**——写了复制页、提交说「没有变化」、收工，
    微信一个字都没发。

    **它和「发出去了」长得一模一样**：conclusion 是 success，日志里没有
    任何一行说「本次没有推送」——被跳过的步骤根本不进日志。又一次
    「兜底出事的时候不吭声」，只不过这次不吭声的是一个 `skipped`。

    判据钉两头，缺一头都不算：

    1. **闸存在**，而且拦的正是 `mode=push` + `push!=true` 这个组合
    2. **它排在真正干活之前**——排在后面的话，那一趟仍然会先跑一遍
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)
    guard = next((i for i, n in enumerate(names)
                  if "mode=push 就必须 push=true" in n), None)
    assert guard is not None, (
        "没有这道闸：只传 mode=push 的那趟会绿着回来，什么都没发")

    block = _step_block("mode=push 就必须 push=true", text)
    cond = block.split("run:", 1)[0]
    assert "inputs.mode == 'push'" in cond and "inputs.push != 'true'" in cond, (
        f"闸的条件不对，拦不住那个组合：{cond}")
    assert "exit 1" in block, "闸不 exit 1 等于只打了一行字"

    # **位置**：要排在写复制页 / 提交 / 推送之前，否则白跑一趟才报
    page = next(i for i, n in enumerate(names) if "写复制页" in n)
    assert guard < page, (
        f"闸排在第 {guard} 步、写复制页在第 {page} 步——"
        "排在后面的话那一趟照样先干一遍活")


def test_封面候选帧默认不跑要显式开cutout_candidates():
    """`pick_cover_frames.py` 现在只在 `cutout_candidates=true` 时才跑。

    2026-08-21 量出来的：最近 30 条 spec 全是 `layout: "solo"`，封面人物
    2026-08-16 起硬性要求官方高清实拍、不许再 `frame_at` 抽帧——上一次真正
    用这一步挑出的候选帧写进 spec 是 2026-08-19 的 `zhang-li`，之后没再用过。
    可这一步一直在 `mode=probe` 里无条件跑，71 秒白烧。

    这一步找的是 `versus.top/bottom`（`cutout` 版式的抠图人物）用的候选，
    那条路没被这道闸管——所以不是删掉，是改成显式认领：默认跳过，
    真要用 `cutout` 版式再手动开。

    判据钉两头：**输入项默认是 false**（不许悄悄变成默认开），
    **那一步的 `if:` 真的接了这个输入**（不许只加了输入没接上）。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    body = _yaml_only(text)

    m = re.search(
        r"cutout_candidates:\n(?:.*\n)*?"
        r"\s*type:\s*boolean\n"
        r"\s*default:\s*(\S+)",
        body,
    )
    assert m is not None, "没有 cutout_candidates 这个 boolean 输入"
    assert m.group(1) == "false", (
        f"默认值是 {m.group(1)!r}，不是 false——等于又变回无条件跑")

    block = _step_block("probe — 封面候选帧", text)
    cond = block.split("run:", 1)[0]
    assert "inputs.mode == 'probe'" in cond, "起码要认 mode=probe"
    assert "inputs.cutout_candidates == 'true'" in cond, (
        f"这一步没接上 cutout_candidates，条件是：{cond}")


def test_push模式按slug反查目录不按今天的日期(tmp_path):
    """`mode=push` 推的是**已经渲好、可能是好几天前的成片**，不是今天新出的。

    2026-08-07 想把 `eala-pegula-final`（8 月 4 日渲的，账号所有者说
    「推微信后再确认审核」之后一直没推）补推出去，才发现「算出目录」那一步
    一直写死 `OUT_DATE=$(TZ=Asia/Shanghai date +%F)`——render/cover/probe/
    narration 四种模式确实该按今天算（当场生成新内容），但 push 模式套用
    同一行，会拼出一个**当天根本没写过东西**的路径。下游「push 模式先确认
    成片真的落地了」那道闸会报「既不在这个 commit 里」，而真实原因是
    **问错日子了**，不是片子没渲、也不是仓库出了别的问题。

    这条判据**真跑一遍抽出来的 bash 脚本**（不是读源码字符串猜它对不对）：
    造一个临时 git 仓库，在两个不同日期的目录下放同一个 slug 的
    `render.json`（模拟 `wong-brooksby` 那种重渲过的片子），跑 `mode=push`
    要选中**较晚**那个日期——和「查产物按最新那一份，别拿被顶替掉的当基准」
    是同一条判据搬到这儿。
    """
    assert __import__("shutil").which("git"), "没有 git，这条判据跑不了"

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)

    for date in ("2026-08-04", "2026-08-06"):
        d = repo / "output" / date / "reel" / "wong-brooksby"
        d.mkdir(parents=True)
        (d / "render.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=repo, check=True)

    block = _step_block("算出目录")
    script = block.split("run: |", 1)[1]
    # 工作流里引用的是 GitHub Actions 的输入插值语法，这儿换成真实变量喂给脚本
    script = script.replace(
        '"${{ github.event.inputs.slug }}"', '"$SLUG"'
    ).replace(
        "${{ github.event.inputs.mode }}", "$MODE"
    )
    # `git sparse-checkout add` 在没有先 `init --sparse` 的仓库上会报错，
    # 这条判据只关心 OUT_DIR/OUT_DATE 怎么算出来的，不测稀疏检出本身
    # （那半条已经有别的判据在管），所以把这一行摘掉再跑。
    script = "\n".join(
        line for line in script.splitlines()
        if "sparse-checkout" not in line
    )

    def run_paths(mode: str) -> dict[str, str]:
        subprocess.run(
            ["bash", "-c", script], cwd=repo, check=True,
            capture_output=True, text=True,
            env={**os.environ, "SLUG": "wong-brooksby", "MODE": mode,
                 "GITHUB_OUTPUT": str(tmp_path / f"gh_output_{mode}")},
        )
        out = (tmp_path / f"gh_output_{mode}").read_text(encoding="utf-8")
        return dict(line.split("=", 1) for line in out.strip().splitlines())

    pushed = run_paths("push")
    assert pushed["outdir"] == "output/2026-08-06/reel/wong-brooksby", (
        f"push 模式该反查到最晚那个日期，实际算出 {pushed}")
    assert pushed["date"] == "2026-08-06"

    # 反向验证：render 模式不受这次改动影响，仍然按今天算——不能因为修好了
    # push 就把 render 也改成「查最晚的历史目录」，那会让**新渲**的片子
    # 覆盖不到今天的路径。工作流里用的是 Asia/Shanghai，这儿只需要确认它走的
    # 不是「反查历史目录」那条路，不用较真时区精确到哪一天。
    rendered = run_paths("render")
    assert rendered["outdir"] == f"output/{rendered['date']}/reel/wong-brooksby"
    assert rendered["outdir"] != pushed["outdir"], (
        "render 模式不该复用 push 模式反查出来的历史目录")

    # 没渲过的 slug，push 模式要报错交代清楚，不能悄悄退回今天的日期
    # （那样会指向一个空目录，下游那道闸的报错就变成一句误导）。
    missing = subprocess.run(
        ["bash", "-c", script], cwd=repo, capture_output=True, text=True,
        env={**os.environ, "SLUG": "nobody-rendered-this", "MODE": "push",
             "GITHUB_OUTPUT": str(tmp_path / "gh_output_missing")},
    )
    assert missing.returncode != 0, "没渲过的 slug，push 模式不该假装成功"
    # `echo "::error::..."` 只是往 stdout 写一行 GitHub Actions 认得的魔法字符串
    # ——在真实 Actions runner 上会被拎出来标红，但普通 bash 子进程里它就是
    # 平平无奇的 stdout，不会自动跑到 stderr 去。
    assert "先跑一次 mode=render" in missing.stdout


def test_复制页写在提交之前():
    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)
    page = next(i for i, n in enumerate(names) if "写复制页" in n)
    commit = next(i for i, n in enumerate(names) if "提交产物" in n)
    push = next(i for i, n in enumerate(names) if "推送到微信" in n)
    # 写 → 提交 → 推送。反过来任何一段，链接就是 404。
    assert page < commit < push, names
    assert "--stage page" in text



def test_复制页那一步不挑推不推送():
    """分支上渲的片子也要把复制页带上，否则 push-reel 又得现写现等。

    渲染那次不写复制页，它就只能在推送那一刻才第一次进仓库——Pages 从零开始
    发布，又是四分钟的原地等待。写它几乎不要钱（一个 HTML 文件），而它决定了
    后面那条三分钟的推送要不要退回十几分钟。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    block = _step_block("写复制页（必须排在提交之前）", text)
    assert "inputs.push == 'true'" not in block, (
        "「写复制页」挂在 push=true 上了——分支上 push=false 渲的片子就带不上"
        "复制页，合进 main 之后那趟 mode=push 还得现写现等 Pages 发布")
    assert "inputs.mode == 'render'" in block, "「写复制页」没覆盖 render 模式"
    # 它跟着「提交产物」一起进仓库（那一步 add 整个 outdir），所以要排在提交之前
    names = _steps(text)
    page = next(i for i, n in enumerate(names) if "写复制页" in n)
    commit = next(i for i, n in enumerate(names) if "提交产物" in n)
    assert page < commit, "复制页排在提交之后——它进不了仓库，链接就是 404"


def test_只发不重渲要有一条单独的路():
    """**「先验产物再推」意味着推是另一次动作。**

    原来只有 `mode=render` 那一条路带推送，于是「渲完看一眼，没问题再发」
    要跑两轮 render——而一轮十五分钟（装中文字体 4 分 20 秒、渲片 7 分半），
    第二轮渲出来的还得再验一次，等于把验证这件事做成了无限循环。

    `mode=push` 跳过下载和渲染，只做「写复制页 → 提交 → 发微信」这三步。

    两条判据缺一不可：

    - **顺序不能变**：复制页仍然要排在提交之前，否则链接 404（这条已经有
      `test_复制页写在提交之前` 盯着，这里只确认新模式没绕开它）
    - **前提要在最前面验**：成片必须已经在**这个 commit 里**。查 `git ls-files`
      而不是 `test -f`——只在工作区里躺着的文件，推送发出去就是 404，
      复制页在这上面栽过两次
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)

    # 档位会增减（后来加了 cover），钉「push 在不在」而不是整行字面量
    opts = re.search(r"options: \[(.*?)\]", text).group(1)
    assert "push" in [o.strip() for o in opts.split(",")], f"mode 里没有 push：{opts}"

    for step in ("写复制页", "推送到微信"):
        i = next(k for k, n in enumerate(names) if step in n)
        cond = text.split(f"- name: {names[i]}", 1)[1].split("\n", 2)[1]
        assert "'push'" in cond, f"{step} 这一步在 push 模式下不跑，等于这个模式发不出东西"

    # 渲染那一步**不能**在 push 模式下跑，否则「只发不重渲」名不副实
    render_cond = text.split("- name: render — 出成片", 1)[1].split("\n", 2)[1]
    assert "mode == 'render'" in render_cond and "push" not in render_cond, \
        "push 模式还会重渲一遍"

    # push 模式**不装渲染那套**：它不下片、不渲染、不抠图，rembg / opencv /
    # playwright / yt-dlp / ffmpeg 一个都用不上。装它们不只是白等半分钟——
    # 那几个包里任何一个装不上，都会让一条本来只是发消息的 run 挂掉。
    ffmpeg_cond = text.split("- name: 装 ffmpeg", 1)[1].split("run:", 1)[0]
    assert "mode != 'push'" in ffmpeg_cond, "push 模式还在装 ffmpeg"
    deps = text.split("- name: 装依赖", 1)[1].split("- name:", 1)[0]
    assert '= "push" ]' in deps and "pip install -q -e ." in deps, \
        "push 模式没有走「只装主依赖」那条分支"
    # 而且那条分支要**真验一次 import**，不许把失败吞掉——装少了得在第 5 秒炸。
    # **判据只看代码，不看注释**：第一版没剔注释，结果被工作流里那句解释
    # 「不许 xx」自己绊倒了——注释里提到一个反模式，不等于用了它。
    head = deps.split('= "push" ]', 1)[1].split("fi", 1)[0]
    code = "\n".join(ln for ln in head.splitlines() if not ln.strip().startswith("#"))
    assert "import requests" in code, "push 分支没有真验一次 import"
    assert "|| true" not in code and "2>/dev/null" not in code, \
        "push 分支的依赖检查把失败吞掉了，永远不会红"

    guard = next((n for n in names if "push 模式先确认成片" in n), "")
    assert guard, "push 模式没有前置检查——成片不在时会一路跑到推送才炸"
    assert names.index(guard) < names.index(
        next(n for n in names if "写复制页" in n)), "前置检查排在写复制页后面了"
    assert "git ls-files" in text, (
        "前置检查用的是 test -f——只在工作区里的文件推出去就是 404")


def test_中间物一个都不许进仓库():
    """清理这一步要**盖住**这些文件，而不是**逐字列出**它们。

    原来这条按字面名字断言（`"source.mp4" in cleanup`）。那个判据和它想拦的
    bug 是同一个毛病：**逐个列名字挡不住名字猜不出来的那些**。yt-dlp 下 DASH
    时音视频分开取，落在磁盘上的是 `source.f137.mp4.part`——format id 嵌在
    名字里，事先写不出来。于是清理漏掉它，`git add "$OUTDIR"` 照单全收，
    10 MB 的半成品连着进了两条片子的仓库（eala-zheng、potapova-venus）。

    所以改成按 glob 语义验**覆盖**：把清理里的 `rm -f` 模式抽出来，让每个
    必须死的文件名去匹配。这样工作流写成一串通配、还是拆成十行具名，测试都
    认——它只关心「这个文件会不会被删掉」。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    # 从这一步的名字切到下一步的 `- name:`，只看它自己那段
    cleanup = _step_block("丢掉不进仓库的中间物", text)

    # 抽出 rm -f 那几行里的模式，去掉 "$OUTDIR"/ 前缀和续行符
    pats = re.findall(r'"\$OUTDIR"/(\S+)', cleanup)
    pats = [p.rstrip("\\").strip() for p in pats if p.strip()]
    assert pats, "清理这一步没抽到任何 rm 模式"

    must_die = [
        "source.mp4",                 # 合过音的源片
        "source_av.mp4",
        "source.f137.mp4.part",       # ← 真正漏掉过的那个，DASH 视频流半成品
        "source.f251.webm",           # 音频流，另一种后缀
        "source.f140.m4a",
        # 多源之后每条源片各带一个键：加多源时改了下载的落盘名，没改清理，
        # 三条源片 250 MB 全靠兜底拦下（run 30603686748）。第四次同一个形状。
        "source_r1.mp4", "source_iv.mp4", "source_r2.f616.webm",
        "_cover.jpg", "_cover.html",  # 封面渲染输入，data URI 内嵌，单个 12 MB
        "poster.html",
        "voice_03.mp3",
        # yt-dlp 落的字幕原文件。名字由它自己拼（`_subs.en.vtt` / `_subs.en-orig.json3`
        # / 猜不到的第三种），所以**按前缀删**——这正是 `.part` 那次的教训。
        "_subs.en.vtt", "_subs.en-orig.json3",
        # 抠之前那张原帧：几 MB、只在报错时有用。**抠好的那张不在这儿**，
        # 它是产物，落在 `cover_src/`——见下面 test_封面素材要留在仓库里。
        "_versus_raw_bottom.png",
    ]
    for name in must_die:
        assert any(fnmatch(name, p) for p in pats), (
            f"{name} 不会被清理掉，会跟着 git add 进仓库。现有模式：{pats}")

    # **poster.jpg 要留下**：推送正文第一屏就是它，删了推送里一张图都没有。
    # 成片同理——它就是产物本身。captions.txt / captions_debug.txt 也是产物：
    # 一个是选段用的，一个是「为什么没拿到」的判据，都要跟着提交。
    # render.json 也是产物：封面停多久现在跟着配音走，**光看 spec 算不出来**，
    # check_reel_landed 拿它对片长。删了就只能拿常量猜。
    for keep in ("poster.jpg", "potapova-venus.mp4", "contact_00.jpg", "probe.json",
                 "captions.txt", "captions_debug.txt", "render.json"):
        assert not any(fnmatch(keep, p) for p in pats), f"{keep} 被误删了"


def test_封面素材要留在仓库里():
    """`cover_src/` 是**产物**，不是中间物——它买的是「封面返工不用上 runner」。

    量出来的账（shang-rublev，2026-08-05）：一条片子 98 分钟里 **31 分钟全花在
    封面上**（两趟 `mode=cover` ＋ 一趟因为封面变了而重跑的 render），而那三趟
    里帧一次都没变，改的只有钩子文案和暗角。封面之所以非上 runner 不可，
    只因为 `frame_at` 要从源片抓——把那一帧留住，链就断了，本地渲一张 6.9 秒。

    所以这条钉两头：

    1. **清理那一步不许把它删掉**（它长得很像中间物，下一个人顺手就加进 rm 了）
    2. **代码真的往那儿写**——只钉工作流的话，改成写别处它照样绿
    """
    cleanup = _step_block("丢掉不进仓库的中间物", WORKFLOW.read_text(encoding="utf-8"))
    pats = [p.rstrip("\\").strip()
            for p in re.findall(r'"\$OUTDIR"/(\S+)', cleanup) if p.strip()]
    assert pats, "清理这一步没抽到任何 rm 模式"
    reel = _reel()
    for name in (f"{reel.COVER_SRC_DIR}/portrait.jpg", f"{reel.COVER_SRC_DIR}/top.png",
                 f"{reel.COVER_SRC_DIR}/manifest.json"):
        assert not any(fnmatch(name, p) for p in pats), (
            f"{name} 被清理掉了——封面素材没了，本地就渲不出海报，"
            "封面返工又得每次上 runner。")
    # 递归的那道体积兜底仍然要盖住它：留素材不等于放开「往里塞大文件」
    assert 'find "$OUTDIR" -type f -size +8M' in cleanup, (
        "8 MB 兜底不在了——cover_src 是个新目录，正需要它管着")


def test_封面素材复用两种情况都要出声(tmp_path):
    """**命中和没命中都要说**，而且改了 `frame_at` 必须重抓。

    只在一头出声的检查证明不了它看过——「复用了旧帧」和「重新抓了一帧」在
    日志上一样的话，`frame_at` 改了却没生效就没人能发现，而海报上那一帧错了
    是**不报错**的：它看起来完全正常，只是不是你要的那一帧。

    ⚠️ 键按内容算（源 / frame_at / box / 抠图模型），不按「文件在不在」算。
    源片缓存那次栽过同一个坑：按 slug 判，改了 URL 还会命中旧文件。
    """
    reel = _reel()
    src = tmp_path / "source.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25", "-t", "8",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(src)],
        check=True)
    cover = {"eyebrow": "赛场之上", "layout": "solo", "subject": "张帅",
             "hook": "一行\n两行", "portrait": {"frame_at": 2.0}}

    def _run(cov, **kw):
        import io  # noqa: PLC0415
        from contextlib import redirect_stdout  # noqa: PLC0415
        buf = io.StringIO()
        with redirect_stdout(buf):
            reel.resolve_cover_payload(cov, tmp_path, sources={"": src},
                                       primary="", **kw)
        return buf.getvalue()

    first = _run(cover)
    assert "新抓" in first, f"第一趟没说它抓了一帧：{first!r}"
    grabbed = tmp_path / reel.COVER_SRC_DIR / "portrait.jpg"
    assert grabbed.is_file(), "抓下来的帧没落进 cover_src/"

    again = _run(cover)
    assert "复用" in again, f"第二趟没说它复用了：{again!r}"
    assert "新抓" not in again, "同一份 spec 还在重抓，缓存等于没有"

    moved = {**cover, "portrait": {"frame_at": 5.0}}
    assert "新抓" in _run(moved), (
        "改了 frame_at 还在复用旧帧——海报上会是上一版那一帧，而且不报错")


def test_本地渲封面那条路一个源片字节都不碰():
    """`render_cover_local.py` 是这轮优化的产物本身，它的价值全在「不碰源片」。

    源片在沙箱里下不动（IP 被 YouTube 挡）。这条路一旦沾上下载/抽帧，
    它在**唯一能用它的那台机器上**就跑不起来——和 `--cover-only` 那次
    「能力写出来了，能用的那台机器上没有开关」是同一个形状。

    两头都钉：**这条路真的短**，而且**海报出口和成片那条共用一个**——
    分叉的样子是「本地看着对了，成片里是另一版」，没有任何东西会报错。
    """
    body = Path("tools/render_cover_local.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in body.splitlines()
                     if not line.lstrip().startswith("#"))
    code = code.split('"""', 2)[-1]        # 去掉模块 docstring：里面正引着这些词
    for banned in ("download(", "yt_dlp", "yt-dlp", "ffmpeg", "_cut_person",
                   "synthesize", "rembg"):
        assert banned not in code, (
            f"本地渲封面那条路上出现了 {banned}——它就跑不起来了，"
            "而失败的样子会是一句看不懂的报错，不是「你要的是一帧新的」")
    assert "sources=None" in code, "没走「只认缓存」那条路，缺素材会退回抓帧"
    assert "render_poster" in code, (
        "没和成片那条路共用海报出口——写两处必分叉，"
        "而封面分叉的样子是「本地看着对了，成片里是另一版」")
    reel = _reel()
    assert hasattr(reel, "render_poster") and hasattr(reel, "resolve_cover_payload")


def test_清理之后还有大文件要报错退出():
    """模式挡的是**已知**的中间物，挡不住下一个没见过的。

    上面那条测的是覆盖，可覆盖永远是事后补的——`.part` 就是补进去的。所以
    清理之后还要再量一次，超标就 `::error::` 退出，让它红在这一步，而不是
    无声进仓库、等到推分支吃 413 才发现（那次就是被 pack 体积撑爆的）。

    「不吭声」正是这一类 bug 的共同特征：`rm` 不报错，`git add` 不报错，
    产物看起来一切正常。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    cleanup = _step_block("丢掉不进仓库的中间物", text)
    assert "find" in cleanup and "-size +8M" in cleanup, "清理之后没有再量一次大小"
    assert "::error::" in cleanup, "查出漏网只是打印，没有出声——这种检查证明不了它看过"
    assert "exit 1" in cleanup, "报了错却不退出，等于没拦"


def test_提交重试耗尽必须失败且重放按提交的diff来():
    """所有 push 都失败却继续微信步骤，会把一个 404 链接发出去。

    重放的范围**不许写死在 OUTDIR**：同一个提交里 OUTDIR 之外的文件
    （probe 自动备料写的 `specs/reels/<slug>.draft.json`）会在
    `reset --hard` 之后**静默丢失**——按 `rendered^..rendered` 的 diff 重放，
    这次提交动过什么就搬回什么，草稿以后挪位置也自动兼容。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    commit = text.split("- name: 提交产物", 1)[1].split("- name:", 1)[0]

    assert 'if git push origin "HEAD:$BRANCH"; then' in commit
    assert "exit 0" in commit
    # 重放按这次提交的 diff 来（新增/修改那半），不按写死的目录来
    assert "git diff --name-only -z --diff-filter=d rendered^ rendered" in commit
    assert 'git checkout rendered -- "$OUTDIR"' not in commit, (
        "重放又退回写死 OUTDIR——同一个提交里 OUTDIR 之外的文件（草稿 spec）"
        "会在撞车重放时被 reset --hard 静默抹掉")
    assert "git checkout rendered -- output/" not in commit
    assert "::error::连续" in commit
    assert commit.rfind("exit 1") > commit.rfind("done")


def _reel():
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def test_tts内容键同文同参数同键不同文不同键():
    """缓存键按内容算：改一个字、换一把嗓子、改一个参数都要换键——
    「改了字」和「没改字」只有内容 hash 分得开。"""
    reel = _reel()
    a = reel._tts_content_key("同一句", "v", "+0%", "+0Hz", "", "", 0.0)
    b = reel._tts_content_key("同一句", "v", "+0%", "+0Hz", "", "", 0.0)
    assert a == b, "同文同参数必须同键"
    c = reel._tts_content_key("同一句改", "v", "+0%", "+0Hz", "", "", 0.0)
    d = reel._tts_content_key("同一句", "v2", "+0%", "+0Hz", "", "", 0.0)
    e = reel._tts_content_key("同一句", "v", "+10%", "+0Hz", "", "", 0.0)
    assert len({a, c, d, e}) == 4, "文本/声音/语速任何一个变了都要换键"


def test_tts命中缓存不重合成(monkeypatch, tmp_path):
    """重渲（只改封面/字幕）时旁白文本没变，voice 不该重合成。"""
    reel = _reel()
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path))
    calls = {"n": 0}
    marks = [{"offset": 0, "duration": 100, "text": "x"}]

    def fake_uncached(text, path, *a, **k):
        calls["n"] += 1
        path.write_bytes(b"FAKE_MP3")
        return marks

    monkeypatch.setattr(reel, "_tts_one_uncached", fake_uncached)
    p1 = tmp_path / "a.mp3"
    p2 = tmp_path / "b.mp3"
    got1 = reel.tts_one("同一句", p1, "v", "+0%")
    got2 = reel.tts_one("同一句", p2, "v", "+0%")
    assert got1 == got2 == marks
    assert calls["n"] == 1, "同文同参数第二次该命中缓存，不该再合成"
    assert p2.read_bytes() == b"FAKE_MP3"


def test_tts换字就重合成(monkeypatch, tmp_path):
    """改了旁白文字就必须重合成，缓存不许给出旧音频。"""
    reel = _reel()
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path))
    calls = {"n": 0}

    def fake_uncached(text, path, *a, **k):
        calls["n"] += 1
        path.write_bytes(text.encode())
        return []

    monkeypatch.setattr(reel, "_tts_one_uncached", fake_uncached)
    reel.tts_one("第一句", tmp_path / "a.mp3", "v", "+0%")
    reel.tts_one("第二句", tmp_path / "b.mp3", "v", "+0%")
    assert calls["n"] == 2, "换字必须重合成"


def test_普通帧率跟源片高帧率整除降采样(monkeypatch):
    """硬定 30 而源片 25，就是每 5 帧补一帧、一秒卡五次。

    补出来的帧还查不出来：裁切位置每帧都在变，两帧的像素并不相同（成片 2099 帧
    里逐帧比对，完全相同的 0 帧），只有比源片和成片的帧率才看得见。高帧率则
    整除抽帧：50→25、59.94→29.97、60→30，既不造帧又把编码像素量减半。
    """
    reel = _reel()

    def fake(*args, **kwargs):
        return type("P", (), {"stdout": fake.out})()

    monkeypatch.setattr(reel, "run", fake)
    fake.out = "25/1\n"
    assert reel.resolve_fps(Path("x.mp4")) == ("25/1", 25.0)
    fake.out = "30000/1001\n"                       # 29.97 要保留分数式
    expr, value = reel.resolve_fps(Path("x.mp4"))
    assert expr == "30000/1001" and round(value, 2) == 29.97
    fake.out = "50/1\n"
    assert reel.resolve_fps(Path("x.mp4")) == ("25", 25.0)
    fake.out = "60000/1001\n"
    expr, value = reel.resolve_fps(Path("x.mp4"))
    assert expr == "30000/1001" and round(value, 2) == 29.97
    fake.out = "60/1\n"
    assert reel.resolve_fps(Path("x.mp4")) == ("30", 30.0)
    fake.out = "0/0\n"                              # 报不出来就退回 30，别硬算
    assert reel.resolve_fps(Path("x.mp4")) == ("30", 30.0)


def test_多源对不上时尺寸没有出路帧率要认领(monkeypatch):
    """两样对不上的**严重程度不同**，判据也要分开。

    - **尺寸**对不上就是裁错（裁切窗口按源片宽高算），没有出路，一律红
    - **帧率**对不上是重采样：50 → 25 整齐隔帧丢，看不出来；30 → 25 六帧丢
      一帧，**静态说话头几乎无感，回合镜头一眼看得出一顿一顿**

    所以帧率要在 spec 里**显式认领**。原来一律红——那会把采访这类素材整个挡在
    门外（采访多是 30，赛事集锦多是 25/50）；一律放行又回到「兜底出事的时候
    不吭声」。认领这一步是让这个取舍**留下判据**。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    table = {"a": (1920, 1080, "25/1", 25.0), "b": (1920, 1080, "30/1", 30.0),
             "c": (1280, 720, "25/1", 25.0)}
    monkeypatch.setattr(reel, "probe_size", lambda p: table[p.stem][:2])
    monkeypatch.setattr(reel, "resolve_fps", lambda p: table[p.stem][2:])
    p = {k: Path(f"{k}.mp4") for k in table}

    with pytest.raises(reel.ReelError, match="尺寸没有出路"):
        reel.check_sources_match({"a": p["a"], "c": p["c"]}, {})
    # 尺寸这条**认领不了**：写了 mixed_fps 也拦得住
    with pytest.raises(reel.ReelError, match="尺寸没有出路"):
        reel.check_sources_match({"a": p["a"], "c": p["c"]}, {"mixed_fps": {"c": "随便"}})

    with pytest.raises(reel.ReelError, match="mixed_fps"):
        reel.check_sources_match({"a": p["a"], "b": p["b"]}, {})
    # 认领了就放行——反面锚点，免得判据宽成「多源一律不许」
    reel.check_sources_match({"a": p["a"], "b": p["b"]},
                             {"mixed_fps": {"b": "采访的说话头"}})
    # 认领的是**别的**源，挡的那条照旧红
    with pytest.raises(reel.ReelError, match="mixed_fps"):
        reel.check_sources_match({"a": p["a"], "b": p["b"]},
                                 {"mixed_fps": {"zz": "写错了键"}})
    # 一条源片时什么都不查
    reel.check_sources_match({"a": p["a"]}, {})


def test_帧率相同但ffprobe写法不同不算不一样(monkeypatch):
    """`resolve_fps` 对同一个数值有时报 `"25/1"`、有时报 `"25"`（不同容器/remux
    路径写法不同）——`tiafoe-story` 的 qf2026 就撞过这个假阳性。25 和 25/1
    代进 `fps=` 滤镜是**同一件事，零重采样**，不该被判成"帧率不一样"逼人写一句
    撒谎的 `mixed_fps`（没有重采样却编一句"重采样看不出来"）。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    table = {"a": (1920, 1080, "25/1", 25.0), "d": (1920, 1080, "25", 25.0)}
    monkeypatch.setattr(reel, "probe_size", lambda p: table[p.stem][:2])
    monkeypatch.setattr(reel, "resolve_fps", lambda p: table[p.stem][2:])
    p = {k: Path(f"{k}.mp4") for k in table}

    # 数值相同，写法不同——不许红，不用认领
    reel.check_sources_match({"a": p["a"], "d": p["d"]}, {})

    # 反面锚点：数值真不一样时，这条判据仍然要拦住（不是被我改宽了）
    table["e"] = (1920, 1080, "30/1", 30.0)
    p["e"] = Path("e.mp4")
    with pytest.raises(reel.ReelError, match="mixed_fps"):
        reel.check_sources_match({"a": p["a"], "e": p["e"]}, {})


def test_默认不横摇():
    """窗口只有源片 32% 宽，一摇，底线球网广告板看台全跟着滑——25 fps 下
    滑动的静止物最容易看出一格一格。所以横摇改成按段显式打开。"""
    reel = _reel()
    source = Path(reel.__file__).read_text(encoding="utf-8")
    assert 'bool(s.get("track", False))' in source
    spec = json.loads(Path("specs/reels/nishikori-shang.json").read_text("utf-8"))
    assert not any(s.get("track") for s in spec["segments"])


def test_合集片子的段尾要躲开下一场的转场卡():
    """**`scene_cuts` 报的是切点被检测到的时刻，不是转场开始的时刻。**

    Tennis TV 把两场四强发成一条，中间用一张 `NORRIE v SHAPOVALOV` 的卡过渡。
    探测报的切点是 204.79，我照它把段尾收在 204.0，成片最后 1.7 秒是**下一场的
    片头**——扫入动画早在 202.3 就开始了。又一次拿信号当产物。

    边界只能**从画面量**：逐 0.2 秒采帧算大面积青色占比，202.2 还是 0.008
    （那点是蓝色场地），202.4 跳到 0.477，202.6 到 0.739。

    判据钉住「最后一段收在转场之前」，别再退回去。
    """
    spec = json.loads(Path("specs/reels/wong-gea.json").read_text("utf-8"))
    last = spec["segments"][-1]
    assert last["end"] <= 202.0, (
        f"最后一段收在 {last['end']}s，而转场卡 202.3 秒就开始扫入了——"
        "成片会带上下一场的片头")
    assert "202.3" in spec["_editing_why"], (
        "为什么不是按 scene_cuts 的 204.79 收尾，没有留下判据")
    # 源片是两场合成的，这件事本身要写在 `_source` 里，否则下一个人不会去找边界
    assert "两场" in spec["_source"], "没写清楚这条源片装着两场比赛"


def test_收尾不带播出方的片尾():
    """握手镜头放到底，但 185.92 之后是 TennisTV 的 logo 和二维码，不要。"""
    spec = json.loads(Path("specs/reels/nishikori-shang.json").read_text("utf-8"))
    assert spec["segments"][-1]["end"] <= 185.92


def _headline(**kwargs) -> str:
    sys.path.insert(0, str(Path("tools").resolve()))
    from push_reel import headline  # noqa: PLC0415

    return headline(Path("output/2026-07-28/reel/nishikori-shang"), **kwargs)


def test_有赛果时标题把vs换成比分():
    got = _headline(column="赛场之上", matchup="锦织圭 vs 商竣程", score="2:1")
    assert got == "7.28 赛场之上 | 锦织圭 2:1 商竣程"
    # 没赛果（比如赛前前瞻）就保留「vs」
    assert _headline(column="赛场之上", matchup="锦织圭 vs 商竣程").endswith(
        "锦织圭 vs 商竣程"
    )
    # 比分说不清的片子（退赛、以转折为主）改用一句话概括，顶掉末尾那一格
    assert _headline(column="赛场之上", matchup="锦织圭 vs 商竣程", score="2:1",
                     summary="复出首战打满三盘") == (
        "7.28 赛场之上 | 复出首战打满三盘")


def test_page阶段不发推送也不需要成片(tmp_path):
    outdir = tmp_path / "output" / "2026-07-28" / "reel" / "demo"
    outdir.mkdir(parents=True)
    copy = tmp_path / "demo.xhs.txt"
    copy.write_text("小红书那句标题\n\n正文第一行\n正文第二行", encoding="utf-8")
    # **栏目名从 spec 的 cover.eyebrow 读**，所以文案旁边要有它的 spec——
    # 真实布局本来就是 `specs/reels/<slug>.xhs.txt` 和 `<slug>.json` 挨着放。
    (tmp_path / "demo.json").write_text(
        json.dumps({"cover": {"eyebrow": "赛场之上"}}, ensure_ascii=False),
        encoding="utf-8")
    # 目录里没有 mp4：page 阶段不该因此失败，它要在渲染之外也能单独补跑
    subprocess.run(
        [sys.executable, str(Path("tools/push_reel.py").resolve()),
         "--stage", "page", "--outdir", str(outdir),
         "--matchup", "锦织圭 vs 商竣程", "--score", "2:1",
         "--copy", str(copy)],
        check=True, capture_output=True, text=True,
    )
    page = (outdir / "copy.html").read_text(encoding="utf-8")
    # 格式化标题就是这条帖子的标题，复制页那一格里放的是它；文案自己那句钩子
    # 退成正文第一行。（口径选择，问过之后定的。）
    assert "7.28 赛场之上 | 锦织圭 2:1 商竣程" in page   # 这一跑没传 --event
    assert "小红书那句标题" in page and "正文第二行" in page
    assert "navigator.clipboard" in page or "execCommand" in page
    # 这份 spec 没有旁白段、抽不出末屏一问，那一格就不该留个空框加一个
    # 复制不出东西的按钮（有末屏一问时才带，见 test_pin_comment.py）
    assert "复制评论" not in page


def test_文案到tag那一行为止(tmp_path):
    """**tag 之后的东西不发出去。**

    账号所有者：「推送的正文复制文案里有不需要的东西，**tag 之后就不要了**」。
    `wong-brooksby.xhs.txt` 末尾挂过一段 471 字的「素材来源（写给下一个人）」，
    跟着正文进了微信推送，也进了复制页——而复制页正是往小红书粘贴的那个出口，
    等于把仓库内部的备忘发给读者。（那段话本来就该待在 spec 的 `_source` 里，
    它现在也确实在那儿。）

    两头都要管，和「tag 最多五个」那条同一个形状：

    - **仓库里的 spec** 不许在 tag 之后还写东西——写了就在 CI 上红，
      而不是等它发出去
    - **`push_reel` 发之前再切一刀**，因为发出去就收不回来

    第二条是**真跑一遍 `--stage page`** 验的，不是 grep 源码里有没有那个函数：
    「写了」不等于「跑过」，而且这一刀必须落在两个 stage 共用的那一处读上——
    只切复制页不切微信正文，两边粘出来的就不是同一段字了。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    from push_reel import cut_at_tags  # noqa: PLC0415

    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        text = path.read_text(encoding="utf-8")
        assert cut_at_tags(text) == text.strip(), (
            f"{path.name} 在 tag 之后还写了东西——写给下一个人的备注放 spec 的 "
            f"`_source`，文案文件到 tag 那一行为止")

    outdir = tmp_path / "output" / "2026-07-28" / "reel" / "demo"
    outdir.mkdir(parents=True)
    copy = tmp_path / "demo.xhs.txt"
    copy.write_text(
        "小红书那句标题\n\n正文第一行\n\n#网球 #网球时差\n\n"
        "---\n素材来源（写给下一个人）：这段不该发出去\n",
        encoding="utf-8")
    (tmp_path / "demo.json").write_text(
        json.dumps({"cover": {"eyebrow": "赛场之上"}}, ensure_ascii=False),
        encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(Path("tools/push_reel.py").resolve()),
         "--stage", "page", "--outdir", str(outdir),
         "--matchup", "锦织圭 vs 商竣程", "--score", "2:1",
         "--copy", str(copy)],
        check=True, capture_output=True, text=True,
    )
    page = (outdir / "copy.html").read_text(encoding="utf-8")
    assert "#网球时差" in page and "正文第一行" in page, "把正文也砍掉了"
    assert "素材来源" not in page, "tag 之后那段跟着发出去了"
    # **砍掉的要出声**：默默吃掉的话，「砍对了」和「砍错了」长得一模一样。
    assert "tag 之后还有" in done.stdout, "砍了却不说砍了什么"


def test_逐分解析认的是df_mh_1那套字段():
    """**逐分不在 `df_pbp_1`，在 `df_mh_1`。**

    我先试的 `df_pbp_1` 对黄泽林那场返回 `0`，据此差点写下「这场没有逐分」——
    换个 feed 名，整份逐分连破发点标记一起出来了。**零命中先怀疑自己的查询词。**

    这条测试喂一段真实抓下来的 `df_mh_1` 片段，验解析器把四件事读对：
    局比分、发球方、谁拿下、以及 `|B1|` 破发点的个数。**真调用它一次**，
    不是 grep 源码里有没有那个函数名——「写了」不等于「跑过」。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import match_feed  # noqa: PLC0415

    assert match_feed.FS_POINTS == "df_mh_1", "逐分的 feed 名被改错了"

    # 洛斯卡沃斯那场第一盘的真实片段：他在自己的发球局被逼到 15-40 救回来
    raw = ("HA÷Set 1¬HB÷Point by point - Set 1¬~"
           "HC÷1¬HE÷0¬HG÷1¬HK÷1¬HL÷0:15, 15:15, 30:15, 30:30, 40:30, 40:40, A:40¬~"
           "HC÷3¬HE÷1¬HG÷2¬HH÷2¬HK÷1¬HL÷15:0, 30:0, 40:0 |B1|, 40:15 |B1|, 40:30 |B1|¬~"
           "HC÷4¬HE÷1¬HG÷1¬HK÷1¬HL÷15:0, 15:15, 15:30, 15:40 |B1|, 30:40 |B1|, 40:40, A:40¬~")
    games = match_feed._parse_points(raw)
    assert len(games) == 3, f"没把三局都读出来：{games}"
    hold, brk, saved = games
    assert (hold["home_games"], hold["away_games"]) == ("1", "0")
    assert brk["broken"] and brk["server"] == "away" and brk["winner"] == "home", \
        "破发那一局读错了（HH=2 是被破发，HG 是发球方，HK 是赢家）"
    assert brk["break_points"] == 3, "0-40 那三个破发点没数出来"
    assert saved["server"] == "home" and saved["winner"] == "home" \
        and saved["break_points"] == 2, "「自己发球被逼到 15-40 又救回来」这一局读错了"


def test_旁白里连下五局的起止要和逐分对得上():
    """账号所有者纠正过的那一处：「**不是连下五局到 5:1，是 1:1 之后连下五局到 6:1**」。

    逐分（`df_mh_1`）和源片记分条两边都证实：第一盘七局里他发了四局，
    布鲁克斯比只保住第 2 局，所以是 `1-0 → 1-1 → 连下五局 → 6-1`。
    而上一版旁白写「连下五局，把比分拉到五比一」，正压在屏幕上显示 1-0 / 1-1
    的那一段——**画面在打脸**。

    判据卡的是**这个跨栏的起止**，不是措辞：出现「连下五局」的那句话里，
    必须把起点（一比一）或终点（六比一）说出来，且不能说成五比一。
    只盯措辞会把下一个更好的写法也拦掉。
    """
    spec = json.loads(Path("specs/reels/wong-brooksby.json").read_text("utf-8"))
    said = [s.get("narration", "") for s in spec["segments"]]
    runs = [t for t in said if "连下五局" in t]
    assert runs, "这条片子的旁白里没有那段连下五局——改写法了就把这条一起改"
    for t in runs:
        assert "五比一" not in t, f"又写成「连下五局到五比一」了：{t}"
        assert "一比一" in t or "六比一" in t, \
            f"「连下五局」没说清从哪儿到哪儿：{t}"


# 冷开场取自源片**前这么多秒**就算「随手取了集锦的开头」。20 秒是从三条真实的
# 冷开场之间那道缝里取的：`shang-rublev` 111.6、`zhang-ostapenko` 158.8，
# 而出事的 `chwalinska-gibson` 是 2.6——两档差着一个数量级，20 落在缝里。
_COLD_OPEN_HEAD_SECONDS = 20.0

# 这条的冷开场取自源片开头，发在「开场三格的顺序」这条规矩之前——**它就是把这条
# 规矩换来的那一条**。已发的片子不为版式重渲，所以挂账而不是改。
# **只许减不许加**：新片子要么把爆点放第一格，要么在那一段写 `_head_open_why`
# 认领一句，让「又随手取了开头」变成一次看得见的决定。
_LEGACY_COLD_OPEN_FROM_HEAD = {
    "chwalinska-gibson",
}


def _cold_open(spec):
    """返回冷开场那一段（第 1 段没有旁白也没有 quote），不是冷开场就返回 None。

    ⚠️ 判「有没有旁白」要连 `quote` 一起看：原声段不配旁白但**有字幕有人声**，
    那不是冷开场。`eala-pegula-final` 的开场是六十七秒的转播原声。
    """
    segs = spec.get("segments") or []
    if not segs:
        return None
    first = segs[0]
    if str(first.get("narration", "")).strip() or first.get("quote"):
        return None
    return first


def test_冷开场不许随手取源片开头():
    """账号所有者 2026-08-05：「**以后都按这个顺序来吧**」——画面爆点 → 落点 →
    坐标。

    「最强的那一格」是判断题，**故意没有完整的测试**（和「最硬的那个事实放第 ①
    屏」同一个理由）。这条只拦一种**能量出来**的坏：官方集锦按时间顺序剪，
    开头就是比赛的开头、戏剧性最低的那一格，而爆点几乎必然靠后。

    真有例外（有些集锦开头就是最后一球的预告片段）就写 `_head_open_why` 认领。
    """
    checked = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        first = _cold_open(spec)
        if first is None:
            continue
        checked += 1
        if float(first.get("start", 0.0)) >= _COLD_OPEN_HEAD_SECONDS:
            continue
        if path.stem in _LEGACY_COLD_OPEN_FROM_HEAD:
            continue
        assert str(first.get("_head_open_why", "")).strip(), (
            f"{path.stem} 的冷开场取自源片第 {first.get('start')} 秒——那是集锦的"
            f"开头，也就是这场球戏剧性最低的一格。爆点（最后一球／赛点落地／捧杯／"
            f"那个拥抱）在集锦里几乎必然靠后。真要用开头就写一句 `_head_open_why` "
            f"说清楚为什么它是全片最强的那一格。"
        )
    assert checked >= 3, f"判据失效了：一条冷开场都没扫到（{checked}）"


def test_挂账的冷开场清单只许减不许加():
    """名单里每个 slug 都必须**真的存在、而且真的还是老样子**。

    写错一个名字，那条豁免就成了一盏恒真的绿灯——本文件里两张豁免表
    （`_LEGACY_VS_COVERS` / `_LEGACY_SOLO_NO_SCORE`）都为这个配了自检。
    """
    for slug in sorted(_LEGACY_COLD_OPEN_FROM_HEAD):
        path = Path("specs/reels") / f"{slug}.json"
        assert path.is_file(), f"{slug} 这条 spec 已经没了，把它从挂账清单里删掉"
        first = _cold_open(json.loads(path.read_text("utf-8")))
        assert first is not None, f"{slug} 的第 1 段已经不是冷开场了，可以销账"
        assert float(first.get("start", 0.0)) < _COLD_OPEN_HEAD_SECONDS, (
            f"{slug} 的冷开场已经不取自源片开头了（{first.get('start')}s），"
            f"把它从挂账清单里删掉"
        )
        assert not str(first.get("_head_open_why", "")).strip(), (
            f"{slug} 已经写了 `_head_open_why` 认领，不用再挂账"
        )


def test_冷开场里的结局必须在正文重新兑现(tmp_path):
    """冷开场放过最后一球，不等于正文可以停在赛点还没打完的时候。

    蒂亚福—穆塞蒂第一版正文收在 330.88 秒：穆塞蒂刚救完两个赛点，真正的
    制胜分 333.16–347.24 只在开头出现。容器、音轨、片尾全都完整，机器照样绿；
    但故事没有闭合。判据钉的是**源片时间线有没有重新走到冷开场末尾**，不是
    旁白关键词，所以最后几秒只有现场欢呼也不会被误报成哑场。
    """
    reel = _reel()

    broken = {
        "slug": "new-match-review",
        "editorial": {"mode": "match_review"},
        "segments": [
            {"start": 333.16, "end": 347.24, "narration": "", "quote": ["赢了"],
             "_ending_payoff_required": True},
            {"start": 15.38, "end": 23.34, "narration": "坐标"},
            {"start": 321.54, "end": 330.88, "narration": ""},
        ],
    }
    msg = reel.ending_payoff_problem(broken)
    assert msg and "冷开场是预告，不是结尾的替身" in msg

    # 只补一个时间更晚的握手，不能靠更大的 end 冒充「完整赛点已重放」。
    handshake_only = json.loads(json.dumps(broken))
    handshake_only["segments"].append(
        {"start": 348.0, "end": 350.64, "narration": ""})
    msg = reel.ending_payoff_problem(handshake_only)
    assert msg and "完整重放" in msg

    # 完整窗口可以拆段；闸看正文窗口的并集，不强迫剪辑只能写成一个 segment。
    fixed = json.loads(json.dumps(broken))
    fixed["segments"].extend([
        {"start": 330.88, "end": 340.0, "narration": ""},
        {"start": 340.0, "end": 350.64, "narration": ""},
    ])
    assert reel.ending_payoff_problem(fixed) is None

    # 真实存量里有 9.4~12.4 秒的小倒序，旧的「至少倒 20 秒」会漏掉。
    low_gap = {
        "slug": "low-gap", "editorial": {"mode": "match_review"},
        "segments": [
            {"start": 178.0, "end": 189.8, "narration": ""},
            {"start": 165.6, "end": 171.0, "narration": ""},
            {"start": 100.0, "end": 160.0, "narration": ""},
        ],
    }
    msg = reel.ending_payoff_problem(low_gap)
    assert msg and "_ending_payoff_required" in msg
    low_gap["segments"][0]["_ending_payoff_required"] = False
    msg = reel.ending_payoff_problem(low_gap)
    assert msg and "冷开场是预告" in msg

    # 省略 source 要和 parse_segments 一样归到主源；不同源的时间码不能互比。
    omitted_primary = json.loads(json.dumps(low_gap))
    omitted_primary["sources"] = {"main": "https://example.com/main.mp4"}
    omitted_primary["segments"][1]["source"] = "main"
    assert reel.ending_payoff_problem(omitted_primary)
    cross_source = {
        "slug": "two-cameras", "editorial": {"mode": "match_review"},
        "sources": {"main": "https://example.com/main.mp4",
                    "other": "https://example.com/other.mp4"},
        "segments": [
            {"source": "main", "start": 100.0, "end": 110.0, "narration": ""},
            {"source": "other", "start": 0.0, "end": 20.0, "narration": ""},
        ],
    }
    assert reel.ending_payoff_problem(cross_source) is None

    # 真实返工也要过，防止只修了测试样例、Tiafoe spec 仍停在两个赛点之后。
    tiafoe = json.loads(Path(
        "specs/reels/tiafoe-musetti-cincinnati-2026-qf.json"
    ).read_text("utf-8"))
    assert tiafoe["segments"][0]["_ending_payoff_required"] is True
    assert reel.ending_payoff_problem(tiafoe) is None
    assert tiafoe["segments"][-1]["end"] >= tiafoe["segments"][0]["end"]

    # 钉生产入口，不只钉 helper：把真实返工最后一段拿掉，validate_spec 当场红。
    broken_tiafoe = json.loads(json.dumps(tiafoe))
    broken_tiafoe["segments"].pop()
    with pytest.raises(reel.ReelError, match="冷开场是预告"):
        reel.validate_spec(broken_tiafoe)

    # 同 slug 命名：让措辞豁免继承底稿，红要红在「冷开场是预告」上
    broken_path = tmp_path / "tiafoe-musetti-cincinnati-2026-qf.json"
    broken_path.write_text(json.dumps(broken_tiafoe, ensure_ascii=False), "utf-8")
    proc = subprocess.run([
        sys.executable, "tools/build_match_reel.py", "render",
        "--spec", str(broken_path), "--outdir", str(tmp_path / "out"), "--dry-run",
    ], text=True, capture_output=True, check=False)
    assert proc.returncode != 0
    assert "冷开场是预告" in (proc.stdout + proc.stderr)
    assert not (tmp_path / "out").exists(), "硬闸应在创建产物目录之前失败"


def test_结局未兑现的旧片挂账只许减不许加():
    """挂账只准全仓盘点跳过；同 slug 重跑仍必须红，不能豁免新问题。"""
    reel = _reel()
    expected = {
        "baez-dimitrov", "bejlek-keys-cincinnati-2026-qf",
        "bucsa-chwalinska", "cirstea-bartunkova", "cobolli-jodar",
        "fonseca-ruud", "fritz-nakashima-cincinnati-2026-qf",
        "gauff-kostyuk-cincinnati-2026-qf", "jodar-fils-montreal-qf",
        "landaluce-draper", "nakashima-borges", "noskova-tauson",
        "shang-darderi-montreal-2026", "shelton-tien-montreal-sf",
        "wangxiyu-keys", "zverev-paul",
    }
    assert reel.LEGACY_MISSING_ENDING_PAYOFF == expected, (
        "这是硬闸落地当天的存量基线；合并后只许修好并减少，不能给新片加名字")
    for slug in sorted(expected):
        path = Path("specs/reels") / f"{slug}.json"
        assert path.is_file(), f"{slug} 已经不存在，可以销账"
        spec = json.loads(path.read_text("utf-8"))
        assert reel.ending_payoff_problem(spec), (
            f"{slug} 已经不再命中结尾问题，可以从挂账表删掉")
        assert reel.ending_payoff_problem(
            spec, allow_published_legacy=True) is None

    # 旧片里 120 条倒序冷开场早于 true/false 声明。名单要和仓库里的真实缺口
    # 一一对应；新 spec 没声明时不会因为盘点开了 allow 开关就被顺手吞掉。
    undeclared = reel.LEGACY_UNDECLARED_ENDING_PAYOFF
    digest = hashlib.sha256("\n".join(sorted(undeclared)).encode()).hexdigest()
    assert len(undeclared) == 120 and digest == (
        "d4728f1db023e480471c6a1825f70105f6e88181704c917e0ebfd47f6279f98a"
    ), "这是落闸当天的存量基线；只能补声明并减少，不能给新片加名字"
    specs = _reel_specs()
    found = {
        slug for slug, spec in specs.items()
        if "没声明" in str(reel.ending_payoff_problem(spec) or "")
    }
    assert found == undeclared, "挂账名单和仓库里真正没声明的冷开场分叉了"
    for slug in sorted(undeclared):
        spec = specs[slug]
        assert reel.ending_payoff_problem(spec)
        assert reel.ending_payoff_problem(
            spec, allow_published_legacy=True) is None

    unlisted = {
        "slug": "brand-new-unlisted", "editorial": {"mode": "match_review"},
        "segments": [
            {"start": 100.0, "end": 110.0, "narration": ""},
            {"start": 0.0, "end": 20.0, "narration": ""},
        ],
    }
    assert "没声明" in reel.ending_payoff_problem(
        unlisted, allow_published_legacy=True)


# 这七条发在「开场先给坐标」这条规矩之前。**只许减不许加**——加新片子要么
# 带着坐标来，要么显式往这份清单里写一笔，让「又忘了交代」变成一次看得见的决定。
_NO_SLATE_YET = {
    "eala-fernandez", "eala-zheng", "nishikori-shang", "potapova-venus",
    "wang-pareja", "wang-samsonova", "wong-lehecka",
    # ⚠️ `eala-parks` 不是「规矩之前发的」，是**带着这个毛病发出去的**：
    # 它 2026-08-06 10:12Z 就推过微信（run 31092251991 第 30 步 success），
    # 而开场那段旁白给了北京时间和赛事、**唯独没给轮次**。
    # 挂进来不是原谅，是记账——已发的片子不为措辞重渲（音轨和字幕都烧进去了），
    # 而一条常年红的检查和没有检查是同一个毛病。
    "eala-parks",
    # 同上：`shang-darderi-montreal-2026` 2026-08-07 01:36:54Z 已经推过微信
    # （run 31138555626 第 30 步 success），开场那段旁白给了赛事和轮次、
    # **一个时刻都没给**（既没有「北京时间」也没有几点几分）。
    "shang-darderi-montreal-2026",
    # 同上：`tiafoe-musetti-cincinnati-2026-qf` 2026-08-22T05:02:40Z 已经
    # 推过微信（run 32553267109，另一个并发会话发的），开场旁白给了「北京时间
    # 8月22日7点05分」——三样都有，只是钟点写成了阿拉伯数字「7」而不是中文数字，
    # 这条判据只认中文数字，所以判成「没给时刻」。真正的毛病是「报到了分钟」，
    # 归 `_CLOCK_MINUTE_LEGACY`（tests/test_reel_editorial.py）认领，这儿只是
    # 连带撞上；已发不为措辞重渲，两处一起挂账。
    "tiafoe-musetti-cincinnati-2026-qf",
    # 同上：`zheng-you-us-open-2026-q1` 2026-08-25T01:53:09Z 已经推过微信
    # （run 32799209180，`pushed.json` 在仓库里）。开场那段旁白给了「北京时间
    # 八月二十五号凌晨」和「美网资格赛女单首轮」——北京时间、日期、轮次三样有
    # 两样半，**唯独没给钟点**，所以撞在「开球时刻」这一条上。
    # ⚠️ 而补录时顺手核出来的比这条判据说的更糟：**那个日期本身就偏了**。
    # 开球是**北京 8/24 23:15**（美东 8/24 11:15，US Open 资格赛当日 11:00 ET
    # 第一场的档期），结束是北京 8/25 00:43——旁白那句「八月二十五号凌晨」
    # 描述的是**收场**那一侧，不是开球。两条独立自证：flashscore `AD`→`AO`
    # 差 88 分钟，和 US Open 官方 feed 的 `duration: "1:28"` 分秒不差；
    # 而 11:15 ET 正落在资格赛当日的首场档期上。
    # （按 CLAUDE.md「开球时刻只说个大概」那条，正确写法是「夜里十一点多」。）
    # 挂进来同样不是原谅，是记账——已发的片子不为措辞重渲，音轨和字幕都烧
    # 进去了；这一条只管以后新写的 spec 不再这么写。
    "zheng-you-us-open-2026-q1",
}

# 收尾没落在一问上、而且**已经发出去了**的。只许减不许加，底下有自检。
_ENDING_LEGACY = {
    # 同上：`eala-parks` 收在「六比二，晋级第三轮。」这句数据上。
    "eala-parks",
    # `shang-darderi-montreal-2026` 收在「四比五，他救下两个赛点。」这句数据上。
    "shang-darderi-montreal-2026",
    # `zheng-you-us-open-2026-q1` 收在「……零次被破发，是这场胜利最硬的答案。」
    # 这句数据上。它 2026-08-25T01:53:09Z 已经推过微信（run 32799209180），
    # 收尾那句烧在音轨和字幕里，不为措辞重渲。
    "zheng-you-us-open-2026-q1",
}


def test_赛场之上开场要给出北京时间赛事和轮次():
    """账号所有者：「以后赛场之上上来首先交代下时间（北京时间几月几号几点几分
    之类 开球的时间）赛事和轮次」。

    刷到片子的人不知道这是哪天哪站哪一轮，第 ① 段那十秒就是用来安置他的。

    判据只卡**三样在不在**，不卡写法：时间要认得出是北京时间的开球时刻、
    赛事名、轮次。措辞不管——这条线上已经有两条测试因为盯措辞而误伤过好写法。
    """
    import re  # noqa: PLC0415

    offenders, bad = set(), []
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        if (spec.get("cover") or {}).get("eyebrow") != "赛场之上":
            continue
        # **不再要求它必须是第 0 段。** 账号所有者 2026-08-02 定了冷开场：
        # 「还是走之前先出获胜后的动作和表情，然后再介绍比赛过程」——坐标于是
        # 挪到了冷开场之后。要守住的是「刷到的人在前 40 秒内知道这是哪天哪站
        # 哪一轮」，不是「它必须是第一句」。
        # **原声冷开场不占这四十秒。** 账号所有者 2026-08-03 把开场定成「最后
        # 一个球落地后的状态」，并要求「不要剪切掉原来英文解说的完整配音和
        # 画面」——`eala-pegula-final` 的开场是**六十七秒的转播原声**，
        # 一句中文旁白都没有。
        # 这条规矩要守的是「**我们一开口**就先安置观众」，不是「片子开始四十秒
        # 内」：没有旁白的那几段，观众听见的是现场和解说，本来就没有我们可以
        # 放坐标的地方。所以从**第一句中文旁白**起算。
        segs = spec["segments"]
        first = next((i for i, s in enumerate(segs)
                      if str(s.get("narration", "")).strip()), len(segs))
        opening, used = "", 0.0
        for seg in segs[first:]:
            if used >= 40.0:
                break
            opening += seg.get("narration", "")
            used += float(seg["end"]) - float(seg["start"])
        # ⚠️ **`两` 必须在这个字集里。** 两点钟中文只说「两点」，没人说「二点」——
        # 而第一版的字集里只有「二」，于是「凌晨两点十分」被判成**没给开球时刻**。
        # 这是一条**假阴性**：它不会告诉你「我拦错了」，只会逼下一个人把对的
        # 写法改成错的（判据宁可窄，不可宽——但窄不等于漏掉唯一正确的那个写法）。
        why = None
        if not opening.strip():
            why = "整条片子一句中文旁白都没有"
        elif "北京时间" not in opening:
            why = f"开场没说是北京时间：{opening}"
        elif not re.search(r"[一二三四五六七八九十两〇零百]+\s*[点时]", opening):
            why = f"开场没给开球时刻：{opening}"
        elif not re.search(r"[月][一二三四五六七八九十]+[号日]", opening):
            why = f"开场没给日期：{opening}"
        elif not re.search(r"(强|轮|决赛|资格赛)", opening):
            why = f"开场没给轮次：{opening}"
        if why is None:
            continue
        offenders.add(path.stem)
        if path.stem not in _NO_SLATE_YET:
            bad.append(f"{path.stem} {why}")

    assert not bad, "这些「赛场之上」开场没交代坐标：\n  " + "\n  ".join(bad)

    # ⚠️ **豁免表要自证它豁免的是真的还在违规。** 这张表的注释从第一天起就
    # 写着「只许减不许加」，**而在 2026-08-25 之前没有任何东西去证明这一点**
    # ——名字写错、或者那条片子后来补上了坐标，它都会变成一盏永远亮着的绿灯，
    # 而绿灯和「真的守住了」长得一模一样。同一个形状这个仓库栽过
    # （`_LEGACY_AMBIGUOUS_POINT` 那次），`_ENDING_LEGACY` 早就配了这一段。
    stale = _NO_SLATE_YET - offenders
    assert not stale, (
        f"{sorted(stale)} 已经不违规了（或者名字写错了），从豁免表里删掉——"
        "这张表只许减不许加")


def test_音频那套不许接进出片流程():
    """账号所有者：「这个默认不要开启，会很慢，拖慢出片速度」。

    解整条音轨要用 ffmpeg 把片子过一遍，接进 render 就是每条片子白等几十秒；
    而它换来的只是段尾秒数准一点，那个数写进 spec 之后就固定了，不必每次重算。

    所以它是**写 spec 时手工跑一次**的辅助，判据是出片路径里一处都不出现。
    """
    hot = (Path("tools/build_match_reel.py"),
           Path(".github/workflows/match-reel.yml"))
    for path in hot:
        text = path.read_text(encoding="utf-8")
        for name in ("unlag", "audio_envelope", "true_end", "check_crowd_rise"):
            assert name not in text, (
                f"{path.name} 里出现了 {name}——音频那套被接进出片流程了，"
                "它每条片子要多花几十秒解音轨，而段尾秒数写进 spec 后就固定了")


def test_渲染专用的依赖不许挂在probe路径上():
    """probe 只是下片子、出缩略图墙，**不需要中文字体、抠图模型和 Chromium**。

    原来这几步挂在所有模式前面，于是 `apt-get install fonts-noto-cjk` 挂死那次
    把 probe 拖了二十分钟——被一个它根本用不到的依赖卡住。而「in_progress 挂太久」
    读起来和「还在跑」一模一样，我等了两轮才发现。

    ffmpeg 两种模式都要，所以它不带条件；其余三样必须只在 render 时装。
    另外每个 apt 步骤都要有 `timeout-minutes`：**卡住要失败，不要空转**。
    """
    import yaml  # noqa: PLC0415

    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = {s.get("name", ""): s for s in spec["jobs"]["reel"]["steps"]}
    for name, step in steps.items():
        if any(k in name for k in ("中文字体", "抠图模型", "Chromium")):
            assert "render" in str(step.get("if", "")), (
                f"「{name}」没有限定在 render——probe 用不到它，"
                "却会被它拖住甚至卡死")
        if "apt-get" in str(step.get("run", "")):
            assert step.get("timeout-minutes"), (
                f"「{name}」是 apt 步骤但没有 timeout-minutes；"
                "它挂死过一次，空转二十分钟看起来和正常运行一样")


def _reel_specs():
    return {p.stem: json.loads(p.read_text("utf-8"))
            for p in sorted(Path("specs/reels").glob("*.json"))}


def test_让当事人自己说的那一段也要有字幕():
    """采访原声那一段**不配旁白，但必须出中文字幕**。

    字幕那条线原来只认 `narration`——没有旁白就没有字幕。于是「让他自己说」
    这一段在成片里对**大多数人是彻底空白**：听不懂英文的看不懂，而
    「静音刷是默认状态」，静音的人连声音都没有。两头都丢，**而且不报错**。

    所以原声段走 `quote`：不合成语音（也就不会闪避把他的话压下去），
    字幕按字数等比铺满整段——拿不到词边界时本来就是这么退的。

    两条判据：**行确实排出来了**，以及 **narration 和 quote 不许并存**
    （并存＝两个人同时开口，而且他的原声会被闪避压掉）。
    """
    import pytest  # noqa: PLC0415

    from tennislive.video.explainer import subtitle_cues  # noqa: PLC0415

    reel = _reel()
    quote = "这个动作叫 Vicht 吧我得去确认一下"
    cues = subtitle_cues(quote, 8.0, offset=1.0)
    assert cues, "原声段排不出字幕"
    assert cues[0][0] >= 1.0, "字幕没跟着片头偏移推"
    assert cues[-1][1] <= 1.0 + 8.0 + 0.01, "字幕甩出了这一段的窗口"

    # 排出来的行**必须回到 render 的那条路上**：只测 subtitle_cues 说明不了
    # build_match_reel 用了它——原来的 bug 恰恰是「函数在，但这条分支没调它」。
    body = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert "if seg.quote:" in body, "cue 那条循环没给原声段留分支"

    spec = {"segments": [{"start": 0, "end": 5, "narration": "我们讲",
                          "quote": "他自己讲"}],
            "cover": {}}
    with pytest.raises(reel.ReelError, match="互斥"):
        reel.parse_segments(spec, {"": 1}, "")
    # 反面锚点：各写各的要放行
    ok = {"segments": [{"start": 0, "end": 5, "quote": "他自己讲"},
                       {"start": 5, "end": 9, "narration": "我们讲"}],
          "cover": {}}
    got = reel.parse_segments(ok, {"": 1}, "")
    assert [s.quote for s in got] == ["他自己讲", ""]
    assert [s.narration for s in got] == ["", "我们讲"]


def test_收尾要落在一问上不能停在数据上():
    """账号所有者定的：「**不要平白地叙事**，要有饱满情感、激起共鸣和代入感……
    同时能引爆人们传播」。

    「饱满情感」测不了，但**产生它的那个结构测得了**：一条片子最后一句是什么。

    停在比分和数据上，读者读完就走——那是赛报的收法。落在一问上，读者会在
    评论区接话，而评论正是这类短片唯一能换来的传播。这和解说片那条
    `末屏那个问题，旁白必须问出来` 是同一条规矩，只是当时漏了剪辑线。

    **七条里六条本来就这么做了**，判据是把既有的好做法钉住，同时抓住那一次
    失手：`wong-lehecka` 原来停在「排名差九十六位，生涯排名最高胜。」

    ⚠️ 判据只看**最后一段**的末尾，不数问号个数——中间抛几问是写稿的选择。

    ⚠️ 2026-08-23 补的一条：**真正的末拍也可能是 `quote`（原声），不只是
    `narration`。** `gauff-bejlek-cincinnati-2026-sf` 的最后一段是转播原声，
    中文那半行是「这一次，她能拿下吗？」——一个真问句，而且是当事人／转播
    自己说出来的，比我们替她问一句更硬（本文件「让当事人自己说」那条早就
    偏爱这个写法）。老逻辑只扫 `narration`，量出来它落在再前一段（一句
    陈述）上，误判成了「停在数据上」。

    所以判据放宽成 **OR**：末尾一问只要落在「最后一句 narration」或者
    「真正的最后一段（不管是 narration 还是 quote）」任意一处，就算数。
    只加不减——已经靠 narration 过关的片子不受影响（`fritz-jodar-final` /
    `tiafoe-musetti-cincinnati-2026-qf` 的末段都是 quote 且不带问句，但它们
    的末句 narration 本来就问着，OR 两头有一头成立就够）。
    """
    bad, offenders = [], set()
    for slug, spec in _reel_specs().items():
        segs = spec["segments"]
        # `.get`：原声段（`quote`）根本没有 narration 这个键
        nars = [s.get("narration", "") for s in segs]
        nars = [n for n in nars if n]
        last_narration = nars[-1] if nars else ""

        true_last_text = ""
        last_seg = segs[-1] if segs else {}
        nar = str(last_seg.get("narration", "")).strip()
        if nar:
            true_last_text = nar
        else:
            quote = last_seg.get("quote")
            if isinstance(quote, str) and quote.strip():
                true_last_text = quote.strip()
            elif isinstance(quote, list) and quote:
                entry = quote[-1]
                text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
                # `text` 是「英文\n中文」，末尾一问只看中文那半行
                zh = str(text).split("\n")[-1].strip()
                true_last_text = zh or str(text).strip()

        if not last_narration and not true_last_text:
            continue

        ends_in_question = (
            ("？" in last_narration[-30:]) or ("？" in true_last_text[-30:])
        )
        if not ends_in_question:
            offenders.add(slug)
            if slug not in _ENDING_LEGACY:
                shown = true_last_text or last_narration
                bad.append(f"{slug}: …{shown[-26:]}")
    assert not bad, (
        "这些片子的收尾停在数据上，没有落在一问上：\n  " + "\n  ".join(bad))

    # ⚠️ **豁免表要自证它豁免的是真的还在违规。** 一个写错的名字就是一盏
    # 永远亮着的绿灯——这个仓库为它栽过（`_LEGACY_AMBIGUOUS_POINT` 那次）。
    stale = _ENDING_LEGACY - offenders
    assert not stale, (
        f"{sorted(stale)} 已经不违规了（或者名字写错了），从豁免表里删掉——"
        "这张表只许减不许加")


def test_旁白不许用指示语指画面():
    """拦的是**指示语**，不是「描述动作」——这两件事我一度混为一谈。

    原规矩（`test_旁白不解说画面`）是给**解说片**写的，那条线的画面是**静止图卡**，
    描述静图确实等于复读。它真正拦的是「画面里是」「镜头里」「图为」「这张图」
    这类**指示语**：把观众已经看见的东西再指一遍，一个字的信息都不加。

    **剪辑线不一样。** 它是动态画面加现场声，旁白落在关键点和关键情绪上正是
    它的本分——云见那把体育解说的嗓子就是为此选的。账号所有者的原话：
    「解说匹配画面是必要的……**针对关键点和关键情绪配合画面解说就很好**」。

    所以 `wong-lehecka` 那句「赛点，黄泽林在二区发出内角 Ace。球落地，他放下
    球拍，双手掩面。」**是好的**。我一度把它判成违规，还把 `球落地[，,]他`
    硬写进正则——**等于把一句好台词钉死成违规**。判据只留指示语。

    这条也不禁止**陈述画面外的事实**：休伊特那条里「他父亲在看台上看完全场」
    是 ATP 官方报道核过的事实，而集锦里并没有莱顿的镜头——那正是
    「画面负责一眼看懂，旁白负责讲清楚」的分工。
    """
    pointing = re.compile(r"画面(里|上|中|就是)|镜头(里|中)|图为|这张图|图片里|上图|下图")
    bad = []
    for slug, spec in _reel_specs().items():
        for seg in spec["segments"]:
            # 原声段的中文字幕（`quote`）也是我们写的，一样受这条管
            for text in (seg.get("narration") or "", _quote_str(seg.get("quote"))):
                m = pointing.search(text)
                if m:
                    bad.append(f"{slug} @{seg['start']}: …{m.group(0)}…")
    assert not bad, "旁白用指示语指画面：\n  " + "\n  ".join(bad)

    # 反面锚点：这句必须**过**——它是描述动作和情绪，不是指示语
    good = "赛点，黄泽林在二区发出内角 Ace。球落地，他放下球拍，双手掩面。"
    assert not pointing.search(good), (
        "判据又扩大化了：这句是关键点加关键情绪的解说，是这条线该有的写法")


def test_闪避的钥匙要补齐否则片尾没声音():
    """`sidechaincompress` **两路里任一路 EOF 就整个结束**，所以钥匙那一路
    必须 `apad`。

    最后一段的旁白往往说不满整段画面——伊埃拉那条末段画面 11.5s、旁白 8.8s。
    钥匙先断，现场声跟着被掐掉：成片最后 2.74 秒**一点声音都没有**，
    而那正是她抱住教练的那一下。

    **它不吭声**：画面照旧、有音轨、有码率，只有把音轨长度和画面长度摆在
    一起才看得见（`check_reel_landed.py` 报「音轨 157.86s，比画面短 2.74s」）。
    和「补位的静音盖住真音轨」是同一族——兜底和默认值出事的时候都不吭声。

    合成信号上验过闪避没变：有旁白 -38.1 dB、旁白说完 -24.0 dB。
    """
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    # 认的是**真正接进滤镜图的那一处**（`[bed][vk]sidechaincompress=`），
    # 不是注释里提到它的那几行——按第一次出现找会撞上注释，判据就废了。
    i = src.index("[bed][vk]sidechaincompress=")
    head = src[max(0, i - 1200):i]
    assert "[vk0]apad[vk]" in head, (
        "闪避的钥匙没有 apad——旁白一说完，现场声会跟着断，片尾整段没声音")
    # 报错要说出路：判据本身也得留在源码里，别只活在测试里
    assert "任一路 EOF" in src, "为什么要 apad 没有留下判据，下次会有人删掉"


# 成片那一步允许的 preset。2026-08-14 拿真素材量下来，`medium` 是最后一档
# 「比 slow 快、而画质量不出差别」的；再往快（`fast` 起）就开始掉，`veryfast`
# 同样 crf 18 出来的文件反而比 slow 小 3.3~24.9%——那不是省，那是它根本没在
# 同一个画质上编（PSNR 掉 0.85~2.76 dB）。表和来路写在 `FINAL_PRESET` 上面。
#
# 收成一个常量给三条判据共用：这个口径写两处必分叉，而分叉的样子是「一条测试
# 拦得住、另一条放行」，两条都绿的时候没人看得出来。
_FINAL_PRESET_OK = frozenset({"veryslow", "slower", "slow", "medium"})


def test_成片的编码参数不许为了压体积往下调():
    """账号所有者 2026-07-29 定的：「**不要舍弃画质，没有硬性要求 20mb**」。

    20 MB 是 jsDelivr 的单文件上限，超了就退回 raw（国内更慢）。我一度把它当成
    一个要满足的指标，还给账号所有者列了「剪短 / 降 crf」两条路——**那个前提
    本身就是错的**：这条线从来没有一条片子进得去。实测码率三条几乎一样
    （3315 / 3517 / 3779 kb/s），20 MB 只够 44 秒，而已发的 69 秒和 83 秒那两条
    是 28.8 和 32.9 MB。要真挤进去得把 crf 推到 23 上下——拿画质换一条通道，
    方向反了。

    **片长可以商量，画质不商量。** 大威那条从 2 分 38 秒剪到 1 分 35 秒
    （59 → 42.6 MB）是片长这一侧的事，编码一个字没动。

    所以把成片那一步的参数钉住。要改得先改这条测试，而改它的时候会先读到上面
    这段——这正是「留下判据」的作用：拦的不是手滑，是**下一次有人重新论证
    「压一压也看不出来」**。
    """
    reel = _reel()
    assert reel.FINAL_CRF == "18", (
        f"成片 crf 被改成了 {reel.FINAL_CRF}。20 MB 不是硬指标，别拿画质换它。")
    # ⚠️ 这一行原来钉的是 `== "slow"`。2026-08-14 量下来 preset 和 crf 是两件
    # 事——preset 换成 `medium` 快 28~38%、PSNR 只差 0.04~0.18 dB，画质量不出
    # 差别（表在 `FINAL_PRESET` 上面）。所以**这条测试只管它该管的那一半**：
    # crf 照旧钉死，preset 只拦「掉到量得出画质损失的那一档」；具体钉在哪个
    # 值，归 test_成片preset按实测定在medium不许再往快里推。
    assert reel.FINAL_PRESET in _FINAL_PRESET_OK, (
        f"成片 preset 被推到了 {reel.FINAL_PRESET}——那一档同样 crf 18 出来的"
        "文件反而更小，也就是根本没在同一个画质上编（veryfast 掉 0.85~2.76 dB）")

    # 参数要走常量，不能又硬写回调用里——硬写的那份改起来没人看得见理由
    src = Path(reel.__file__).read_text(encoding="utf-8")
    assert '"-crf", FINAL_CRF' in src, "成片那一步没用 FINAL_CRF 常量"
    assert '"-crf", "18"' not in src, "成片的 crf 又被硬写回调用里了"


def test_成片preset按实测定在medium不许再往快里推():
    """**preset 和 crf 是两件事**：preset 决定编码器花多少**时间**去找省比特的
    编法，crf 决定**留多少画质**。上一条测试管 crf（画质，不许动）；这一条管
    preset（体积换时间），2026-08-14 拿真素材量过之后把它从 `slow` 挪到
    `medium`。

    来路：一趟 render 862s，render 步 747s，而「烧字幕+成片」一步就是 **423.7s，
    占整趟 49%**——最大的一块，而它一直没被量过。`slow` 当年不是拍的：成片要塞
    进 git（100 MiB 服务端硬拒），比特省一点就多一分进仓库的机会。**2026-08-13
    起成片一律走 Release 附件（单个 2 GB），那个约束没了**，账才值得重算。

    量出来的（四核、真素材、照真实流水线的形状，两个样本分别取高运动量实拍和
    低运动量图形两头；完整两张表在 `FINAL_PRESET` 上面）：

        slow → medium   快 28~38%，大 1.6~6.1%，PSNR 差 0.04~0.18 dB

    也就是**画质量不出差别，而省下 117~163 秒**。

    ⚠️ **这条测试真正要拦的是「再往快推一档」，因为那一档伪装成两头都赚**：
    `veryfast` 同样 crf 18，出来的文件比 `slow` **还小**（−3.3% / −24.9%）。
    同一个 crf 下 preset 越快只会越大，**它反而变小就说明它根本没在同一个画质
    上编**——PSNR 跟着掉 0.85 / 2.76 dB。只看时间和体积，这看起来像是又快又省；
    只有量 SSIM/PSNR 才看得见。

    所以这条不只钉住那个值，还**把源码里那两张表读回来，验它确实支持这个决定**：
    表被人改成别的说法、或者被删掉一半，这里会当场对不上。判据自己也要有判据。
    """
    reel = _reel()
    assert reel.FINAL_PRESET == "medium", (
        f"成片 preset 被改成了 {reel.FINAL_PRESET}。它不是拍的，是量出来的："
        "medium 是最后一档「比 slow 快、而画质量不出差别」的；再快一档 veryfast "
        "同样 crf 18 出来的文件反而更小，也就是画质掉了。要改先重量一遍。")
    # crf 不许被这条顺手带下去——两件事各管各的
    assert reel.FINAL_CRF == "18", "改 preset 不许连累 crf"

    src = Path(reel.__file__).read_text(encoding="utf-8")

    # 参数要走常量。⚠️ 这两句「不许硬写」要在**去掉整行注释之后**扫：注释里
    # 正写着 `preset slow`（记的是当年为什么只能是它），连注释一起扫会把
    # 「把来路记下来」判成「又硬写回去了」。
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert '"-preset", FINAL_PRESET, "-crf", FINAL_CRF' in code, (
        "成片那一步没有同时走 FINAL_PRESET / FINAL_CRF 两个常量")
    for hard in ('"-preset", "slow"', '"-preset", "medium"'):
        assert hard not in code, f"成片的 preset 又被硬写回调用里了：{hard}"

    # —— 把源码里那两张对照表读回来 ——
    # 表长这样（一行一个 preset）：
    #     slow      32.18s   14.32 MiB       —      0.990284   46.580   ← 改前
    row = re.compile(
        r"^#\s+(veryfast|slow|medium|fast)\s+([\d.]+)s\s+([\d.]+) MiB\s+"
        r"(\S+)\s+(0\.\d+)\s+([\d.]+)")
    rows: list[tuple[str, float, float, float, float]] = []
    for line in src.splitlines():
        m = row.match(line)
        if m:
            rows.append((m.group(1), float(m.group(2)), float(m.group(3)),
                         float(m.group(5)), float(m.group(6))))

    # **判据自己的判据**：主语没了它要出声，不能变成一条恒真的绿灯。
    # 两个样本 × 四档 preset ＝ 8 行，少一行就说明表被改动过。
    assert len(rows) == 8, (
        f"`FINAL_PRESET` 上面那两张对照表只读出 {len(rows)} 行，应该是 8 行"
        "（两个样本 × slow/medium/fast/veryfast）。表被删了或者格式变了——"
        "而这个决定的全部依据就是那两张表，它没了这条测试就什么都没验")
    for name in ("slow", "medium", "fast", "veryfast"):
        got = [r for r in rows if r[0] == name]
        assert len(got) == 2, f"表里 {name} 出现了 {len(got)} 次，两个样本各该有一次"

    # 按出现顺序切成两个样本，每个样本内部 slow/medium/fast/veryfast 各一行
    for sample in (rows[:4], rows[4:]):
        by = {r[0]: r for r in sample}
        slow, medium, fast, veryfast = (
            by["slow"], by["medium"], by["fast"], by["veryfast"])

        # ① 换 medium 的理由：真的更快
        assert medium[1] < slow[1], (
            f"表里 medium 的编码时间 {medium[1]}s 并不比 slow 的 {slow[1]}s 快——"
            "那这次更换就没有依据了")
        # ② 而且画质量不出差别（0.5 dB 是「开始看得出来」的量级，实测差一个数量级）
        assert slow[4] - medium[4] < 0.5, (
            f"表里 medium 的 PSNR 比 slow 低 {slow[4] - medium[4]:.3f} dB——"
            "超过 0.5 dB 就不能再说「画质量不出差别」，这次更换要重新论证")
        # ③ 代价是体积，但要小到无所谓（成片走 Release，2 GB 额度）
        assert medium[2] > slow[2], (
            "表里 medium 反而比 slow 小——同一个 crf 下更快的 preset 只会更大，"
            "变小就说明这两行不是在同一个画质上量的，表读错了")
        assert medium[2] / slow[2] < 1.10, (
            f"表里 medium 比 slow 大 {(medium[2] / slow[2] - 1) * 100:.1f}%，"
            "超过 10% 就该重新算这笔账")

        # ④ **不许再往快推的证据**：veryfast 同样 crf 18 反而更小＝画质掉了。
        #    这一条是这张表最值钱的那一行——它拦的正是「看时间和体积都更好，
        #    那就再快一档」这个下一步。
        assert veryfast[2] < slow[2], (
            "表里 veryfast 并不比 slow 小——那「它变小＝没在同一个画质上编」"
            "这个论据就不成立了，`medium` 这个停止位要重新论证")
        assert slow[4] - veryfast[4] > 0.5, (
            f"表里 veryfast 的 PSNR 只比 slow 低 {slow[4] - veryfast[4]:.3f} dB，"
            "掉得没那么多的话，「再快一档就掉画质」这个结论撑不住")
        # ⑤ fast 是那条坡的起点：它对 medium 已经没有画质上的好处
        assert fast[4] <= medium[4] + 0.05, (
            "表里 fast 的 PSNR 比 medium 还高出一截——那 medium 就不该是停止位了")


def test_没有官方抠图时报错要指出退回照片版():
    """**报错要说出路，不能只说不行。**

    cutout 是默认版式，人物走官方半身抠图——「按球员 ID 永远拿得到」。但那句话
    有例外：大威（wta 230220）就没有，球员页搜 Torso 四次重试全零命中（同一轮
    波塔波娃的页面一次就中，所以是真空不是查错），赛事域名那条别名返回的是
    **通用人形占位剪影**，只剩一张到锁骨的头像。

    账号所有者定的兜底是**退回 `layout: diagonal` 的照片版**。所以两处报错都得
    把这条写出来——否则下一个人（或下一个我）撞上时，只会看到两条取图的 URL，
    然后要么重扫一遍已知的真空，要么拿头像硬凑。

    头像凑不了是量出来的：官方半身抠图里头占 26%，头像里占 74%，要两颗头一样大
    得把 scale 压到 0.16——一颗没有身子的浮头，而且头像是方图、三边硬边，
    `CUT_FADE` 只淡出底部 20%，救不了左右。
    """
    for path in (Path("tools/versus_poster.py"), Path("tools/build_match_reel.py")):
        src = path.read_text(encoding="utf-8")
        # 从「找不到抠图」那句报错里截一段看它说了什么
        anchor = "cutout 版式的 {key} 格"
        assert anchor in src, f"{path} 里没有这条报错了，改名了就把这条测试跟着改"
        block = src[src.index(anchor):src.index(anchor) + 700]
        assert "diagonal" in block, f"{path} 的报错没指出退回照片版"
        assert "别拿头像凑" in block, f"{path} 的报错没拦住「用头像顶」这条歪路"

    # 已知没有抠图的球员要记在册子上，避免重扫；结论会失效，所以必须带日期
    credits = json.loads(Path("assets/players/credits.json").read_text("utf-8"))
    known = credits.get("_no_torso") or {}
    assert "venus-williams" in known, "大威那次的探测结论没记下来，下次会重扫一遍"
    entry = known["venus-williams"]
    assert entry.get("checked"), "没记日期——这类结论会随时间失效（WTA 随时可能补图）"
    assert len(entry.get("probes") or []) >= 3, "只写结论不写探过哪些源，等于让人重来"


def test_push只能在main上而且要第一步就拦():
    """`push=true` 跑在特性分支上，结局是**渲十六分钟然后一个字都不发**。

    GitHub Pages 只服务 main。复制页提交在分支上，那个 URL 永远 404，而
    `wait_for_copy_page` 等不到这一版就 exit 1——这个设计是对的（宁可不发也
    不发一条带死链的消息），代价是它把失败推到最后：渲片 6 分钟 + 轮询
    10 分钟，全白跑。2026-07-29 大威那条就这么烧掉一次（run 30457284612）。

    判据当时探得很干净：同一个 Pages 站、同样的路径形状，分支上的 copy.html
    是 404，main 上 wang-pareja 的是 200，差别只有分支。

    所以这条测的是**位置**，不只是存在：闸必须排在 checkout 之前。装字体、
    装依赖、装 Chromium 加起来三分多钟——拦在它们后面就不叫「第 5 秒失败」了。
    「只测行为拦不住位置错」这一课在复制页那道闸上已经上过一次。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    guard = "push=true 必须在 main 上"
    assert guard in text, "没有这道闸"

    # 条件要同时卡住「要推送」和「不在 main」，少一个都拦错人
    block = _step_block(guard, text)
    assert "github.event.inputs.push == 'true'" in block
    assert "github.ref_name != 'main'" in block
    assert "exit 1" in block, "报了错却不退出，等于没拦"
    # 出路要说清楚：两条都写出来，别只说「不行」
    assert "push=false" in block and "合进 main" in block

    # **位置**：必须排在 checkout 之前，否则拦不住那三分多钟的安装
    assert text.index(guard) < text.index("actions/checkout@v4"), (
        "这道闸排在了 checkout 后面——装字体/依赖/Chromium 三分多钟白跑，"
        "就不叫在第 5 秒失败了")


def test_默认音色是云见():
    """定下来的是云见（体育解说那把嗓子）。默认值以前写着云希，靠每次手动传参
    盖过去——漏一次就换了个人在说话。

    ⚠️ **两处一起钉**。同一件事在工作流和 CLI 各配了一遍，而这条判据原来只钉
    工作流那半——于是 `--voice` 的默认值在代码里安安静静写了很久的云希
    （2026-08-14 才发现）。它一直没出事，是因为工作流两处调用都显式传参盖过去了；
    真正在吃这个默认值的是本地跑 `--check-narration` 的人，而那正是最该拿到云见
    的场景（拿云希估出来的余量，对真渲的那把嗓子不作数）。

    ⚠️ **代码那半用 AST 取，不按文本扫。** `zh-CN-YunxiNeural` 在这个文件里
    出现三次，全在注释和 docstring 里——那正是这个仓库记教训的地方
    （`_reject_dead_voice_keys` 的 docstring 里就摆着「同一个键、两把嗓子」的
    实测）。连注释一起扫，「把坑记下来」会被判成「又踩了这个坑」。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "zh-CN-YunjianNeural" in text
    assert "zh-CN-YunxiNeural" not in text

    tree = ast.parse(Path("tools/build_match_reel.py").read_text(encoding="utf-8"))
    defaults = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in ("--voice", "--rate")):
            continue
        for kw in node.keywords:
            if kw.arg == "default" and isinstance(kw.value, ast.Constant):
                defaults[node.args[0].value] = kw.value.value
    assert defaults.get("--voice") == "zh-CN-YunjianNeural", (
        f"CLI 的 --voice 默认值是 {defaults.get('--voice')!r}，不是云见。\n"
        "工作流那半改了、代码这半没改，就是「同一件事在两处各配一遍，只改了一处」"
        "——而它不吭声：工作流显式传参，坏的只有本地 --check-narration 那条快路。")
    assert defaults.get("--rate") == "+6%", (
        f"CLI 的 --rate 默认值是 {defaults.get('--rate')!r}；"
        "语速和音色是一对，估旁白长度的系数是按「云见 +6%」量的")


def test_cookies模式不产任何产物():
    """cookie 会过期，过期时的表现和「没配」一模一样，所以要有一条随时能跑的验证；
    但它不该往仓库里提交任何东西。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "mode == 'cookies'" in text
    for step in ("丢掉不进仓库的中间物", "上传 artifact", "提交产物"):
        block = _step_block(step, text)
        assert "mode != 'cookies'" in block, step
    # 必须**真下媒体流**再看字节数：不带 cookie 也拿得到标题和格式表，
    # 只查「命令有没有报错」会把「被挡住」读成「可用」
    check = _step_block("cookies — 只验", text)
    assert "--download-sections" in check
    assert "stat -c%s" in check and "exit 1" in check


def test_push模式不许跑清理那一步():
    """**mode=push 的 OUTDIR 是历史日期目录，清理的体积兜底会把存量成片当漏网。**

    push 模式按 slug 反查 `output/*/reel/<slug>/render.json` 落在哪个日期目录
    （见 `test_push模式按slug反查目录不按今天的日期`），而 2026-08-13 之前发的
    片子成片还留在 git 里（历史清理「存量不动，只改增量」）。稀疏检出把那一格
    add 回来之后，「丢掉不进仓库的中间物」末尾那个**递归**的 8 MB 兜底会把
    这些合法的存量 mp4 当成「漏网的大文件」`exit 1`——红在写复制页之前，
    把唯一受支持的手动推送路径杀掉。而 push 那条路本来**一个中间物都不产**
    （只写复制页、提交、发微信），清理对它没有任何事可做。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    cleanup = _step_block("丢掉不进仓库的中间物", text)
    assert "mode != 'push'" in cleanup, (
        "清理那一步没排除 mode=push——它的递归体积兜底会把 push 模式反查到的"
        "历史目录里的存量成片当成漏网文件 exit 1，杀掉手动推送")
    # 原有的两个排除不许被顺手挤掉（narration / cookies 同样零中间物）
    assert "mode != 'narration'" in cleanup and "mode != 'cookies'" in cleanup


def test_推送正文里印文案且只印一遍():
    """手机上要先能读到这一条写了什么，再决定点不点复制页——和知识帖那条推送
    同一个结构。但**同一段不能印两遍**：以前正文印一遍、灰底复制块又印一遍，
    字符串断言全过，人一看整页才发现。"""
    sys.path.insert(0, str(Path("tools").resolve()))
    from push_reel import build_html, split_copy  # noqa: PLC0415

    copy = Path("specs/reels/nishikori-shang.xhs.txt").read_text("utf-8").strip()
    title, body_text = split_copy(copy)
    page = build_html("https://v/x.mp4", "https://p/copy.html", "一句导语", copy,
                      "", "赛场之上")
    assert page.count(title) == 1
    first = body_text.splitlines()[0]
    assert page.count(first) == 1
    # 复制页的入口要在，按钮上写的是它能干嘛（标题和正文分开复制）
    assert "https://p/copy.html" in page and "分别复制标题 / 正文" in page


def test_yt_dlp装default才解得了n_challenge():
    """少了 yt-dlp-ejs 不会报「装少了」，而是 `n challenge solving failed` +
    `Only images are available`——任何视频格式选择器都匹配不上，看起来像
    「这个视频没有格式」或者「cookie 过期了」。第一次跑 cookies 模式就栽在这上面。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"yt-dlp[default]"' in text
    check = _step_block("cookies — 只验", text)
    # 报错要分因：撞机器人验证 / 解不了 challenge，是两件事
    assert "n challenge solving failed" in check
    assert "not a bot" in check


def test_回合镜头也铺满不走contain():
    """竖版短片在手机上整屏播，上下留黑边等于把冲击力先折一半。窗口只有源片
    32% 宽，球飞到两边确实会出画——**铺满仍然赢过「不丢画面」**。这一条是人
    看过两版之后定的，代码注释以前写的正好相反（「回合镜头必须用 contain」）。"""
    spec = json.loads(Path("specs/reels/nishikori-shang.json").read_text("utf-8"))
    assert all(s.get("fit", "crop") == "crop" for s in spec["segments"])
    reel = _reel()
    source = Path(reel.__file__).read_text(encoding="utf-8")
    assert "回合镜头必须用这个" not in source


def test_标题整句不超过20个字位():
    """账号所有者的原话：「标题控制在 20 个汉字内，言简意赅直达重点，精炼内容。
    讲不完的放到副标题，可以放到正文第一行，详细总结概括。」

    卡的是**整句**，不是末尾那一格——以前只卡 `summary`，前面还挂着日期、栏目、
    赛事轮次，加起来 25 个字位，通知栏里根本读不完。

    量的是小红书字位（全角 1、半角 0.5），不是 `len()`：「7.28 」五个半角只占
    2.5 个，按 `len()` 算会白白吃掉两格。两处用同一把尺，标题才不会在这儿过、
    到小红书又超。
    """
    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    from push_reel import TITLE_MAX, headline  # noqa: PLC0415
    from tennislive.render.xiaohongshu import xhs_title_len  # noqa: PLC0415

    out = Path("output/2026-07-28/reel/x")
    got = headline(out, "赛场之上", "锦织圭 vs 商竣程", "2:1", "", "商竣程复出输球")
    assert xhs_title_len(got) <= TITLE_MAX, got
    # **赛事名就是这么被挤出去的**，所以工作流里 event 默认留空
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text[text.index("      event:"):text.index("      summary:")]
    assert 'default: ""' in block, "event 默认要留空"
    with pytest.raises(SystemExit, match="字位"):
        headline(out, "赛场之上", "锦织圭 vs 商竣程", "2:1", "华盛顿 ATP500 首轮",
                 "商竣程复出输球")
    # 工作流的默认值自己也要过得了这道闸
    summary = re.search(r"      summary:.*?default: \"(.*?)\"", text, re.S).group(1)
    assert xhs_title_len(headline(out, "赛场之上", "伊埃拉 vs 郑钦文", "2:1", "",
                                  summary)) <= TITLE_MAX


def test_复制页探活要认内容不能只认200(monkeypatch):
    """**只查 200 是不够的**：这个 URL 上一版就存在，Pages 还没重新发布时照样
    立刻返回 200，探活一次就过、推送照发，人点开复制到的还是上一版的标题和正文
    （2026-07-28 真出过）。「打得开」是信号，「内容是这一版」才是产物。"""
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    class Resp:
        status_code = 200

        def __init__(self, text):
            self.text = text

    calls = {"n": 0}
    stale = '<textarea id="title">他等到第七个破发点才赢</textarea>'
    fresh = '<textarea id="title">7.28 赛场之上 | 谁赢了</textarea>'

    def fake_get(url, **kw):
        calls["n"] += 1
        return Resp(stale if calls["n"] == 1 else fresh)

    monkeypatch.setattr(push_reel.requests, "get", fake_get)
    monkeypatch.setattr(push_reel.time, "sleep", lambda _s: None)
    push_reel.wait_for_copy_page("https://p/copy.html", "7.28 赛场之上 | 谁赢了")
    assert calls["n"] == 2, "第一次拿到的是旧内容，必须继续等"

    calls["n"] = 0
    monkeypatch.setattr(push_reel.requests, "get", lambda url, **kw: Resp(stale))
    try:
        push_reel.wait_for_copy_page("https://p/copy.html", "永远不会出现的标题",
                                     attempts=2, delay=0)
    except SystemExit as exc:
        assert "上一版" in str(exc) or "没等到这一版" in str(exc)
    else:                                    # 一直是旧内容就不能放行
        raise AssertionError("旧内容也放过去了")


def test_标题末尾那句不超过二十字():
    """标题是给人扫的，不是给人读的。超了直接报错，别让它悄悄溜出去——
    和「卡片上每条不超过 16 字」同一个道理。"""
    sys.path.insert(0, str(Path("tools").resolve()))
    from push_reel import SUMMARY_MAX, headline  # noqa: PLC0415

    text = WORKFLOW.read_text(encoding="utf-8")
    default = text.split("      summary:")[1].split("default:")[1]
    default = default.split("\n")[0].strip().strip('"')
    assert len(default) <= SUMMARY_MAX, f"工作流默认那句 {len(default)} 字：{default}"

    try:
        headline(Path("output/2026-07-28/reel/x"), "赛场之上", "甲 vs 乙",
                 summary="一" * (SUMMARY_MAX + 1))
    except SystemExit as exc:
        assert "超过" in str(exc)
    else:
        raise AssertionError("超长的那句被放过去了")


def test_封面只有海报模板一条路():
    """账号所有者定的：「以后『赛场之上』封面海报都用新的模板方案。」

    所以抽帧那条分支**删掉了，不是留着兜底**。留着的后果是可预见的：哪条片子
    一时找不到照片就悄悄退回抽帧，栏目的封面从此有两副面孔，而且退回去的那次
    没人会注意到——和「兜底出事的时候不吭声」是同一个毛病。

    缺图要报错，并且把出路写在报错里：去扩检索源，不是退回抽帧。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    assert not hasattr(reel, "_render_cover_html"), "单图封面那条路还在"

    # **判据是「缺图会不会报错」，不是「源码里有没有 frame_at 这几个字」。**
    #
    # 原来这儿写的是 `assert "frame_at" not in body`——字符串粗判。2026-07-31
    # 账号所有者把抽帧放回来了（「或者从比赛中抠大图，要情绪饱满的」），我把这
    # 句写进报错文案当出路，那条断言立刻红——**它把自己注释里明确允许的情况
    # 也拦了**。这和「钩子里不许出现比分」是同一个毛病：判据比它要守的规矩宽。
    #
    # 要守的性质从来只有一条：**缺图必须报错，不能自动退回抽帧**。单格在 spec
    # 里显式写 `frame_at` 是人做的选择，不是降级——差别就在「谁决定的」。
    with pytest.raises(reel.ReelError, match="扩检索源"):
        reel.build_cover({"": Path("x.mp4")}, "", {"cover": {"hook": "无图"}},
                         Path("y.mp4"), 1920)
    # 报错要把出路说全：先扩源，四类都没有才抓帧
    with pytest.raises(reel.ReelError, match="frame_at"):
        reel.build_cover({"": Path("x.mp4")}, "", {"cover": {"hook": "无图"}},
                         Path("y.mp4"), 1920)


def test_伊埃拉按译名表写():
    """人名不要手打——`Alexandra Eala` 在 players.py 里是「伊埃拉」。"""
    table = Path("src/tennislive/zh/players.py").read_text(encoding="utf-8")
    assert '"Alexandra Eala": "伊埃拉"' in table
    for path in ("specs/reels/eala-zheng.json", "specs/reels/eala-zheng.xhs.txt"):
        text = Path(path).read_text(encoding="utf-8")
        assert "伊埃拉" in text, path
        for wrong in ("埃拉拉", "伊阿拉", "阿莱克斯"):
            assert wrong not in text, f"{path} 里出现了 {wrong}"


def test_VS拼接两格都用真实照片():
    """**封面不抽帧，而且两格都要是这场。** 1920×1080 的一帧裁 9:16 要放大 1.78 倍，
    比照片软一大截，而封面是唯一决定人点不点的那一屏。

    找图那一轮的两个假命中都记在 credits 里，别让下一个人再踩：文件名对题不等于
    画面对题；同一个 UUID 目录换五个文件名全返回 200 且大小相同，打开却是同一张
    别人的照片——**CDN 根本不认文件名**。
    """
    spec = json.loads(Path("specs/reels/eala-zheng.json").read_text("utf-8"))
    versus = spec["cover"]["versus"]
    credits = json.loads(
        Path("assets/reel/eala-zheng.credits.json").read_text("utf-8"))
    for key in ("top", "bottom"):
        side = versus[key]
        assert "frame_at" not in side, f"{key} 用了抽帧"
        image = Path(side["image"])
        assert image.is_file(), image
        entry = credits[image.name]
        assert entry["date"] == "2026-07-28", f"{image.name} 不是这场"
        assert entry["checked"], f"{image.name} 没记「打开看过」"
    # 清晰度不够的那一格要把代价写在明面上，别让人以为它是原图
    assert "不是高清原图" in credits["zheng-washington-2026.jpg"]["caveat"]
    # 为什么绕了这么大一圈，留给下一个人
    note = credits["_zheng"]["note"]
    assert "soft-404" in note and "CDN 不认文件名" in note


def test_源片太小要在开跑前挡住(monkeypatch):
    """**下到 360p 也算「下载成功」**：yt-dlp 退到低画质那一档时 returncode 0、
    文件也在，看起来一切正常，直到第一段切片撞上 `crop=810:1080` 才炸
    （run 30412173035，源片 640×360）。所以裁切窗口按源片实际高度算，
    太小的源片在开跑前就拒掉，别渲到一半才发现。"""
    reel = _reel()
    try:
        reel.resolve_crop(640, 360)
    except reel.ReelError as exc:
        assert "太小" in str(exc)
    else:
        raise AssertionError("360p 的源片被放过去了")

    reel.resolve_crop(1920, 1080)
    assert (reel.CROP_W, reel.CROP_H) == (810, 1080)
    reel.resolve_crop(1280, 720)                 # 720p 也要能跑，按比例换算
    assert (reel.CROP_W, reel.CROP_H) == (540, 720)   # 720*3/4=540


def test_下载不把编码当硬条件():
    """**「下载成功」和「只拿到 360p」曾经是同一件事。** 第一档写死
    `vcodec^=avc1` + `ext=m4a`，而 YouTube 的 1080p 多是 VP9/AV1(webm)；
    格式表不全时前两档全落空，一路掉到 `best`——它唯一预合成好的档是 itag 18，
    正好 640×360。中间没有一步会报错，直到裁切那步才炸（run 30412173035）。

    所以编码只能是**偏好**（`-S`），不能是过滤条件（`-f`）。

    **判据查的是两个常量的值，不是源码里的一段字符串。** 原来是「从
    `selector = ` 切到 `cookies: list[str]`」——两个记号在文件里都不唯一，
    后来加的 `fetch_captions` 里也有 `cookies: list[str]` 且排在更前面，
    那一刀切出来是空串：`not in` 全过、`in` 全挂。**空串上的断言不吭声地
    全部成立**，正是仓库里反复记的那种假绿。
    """
    reel = _reel()
    assert "vcodec^=avc1" not in reel.FMT_SELECTOR, "编码又被写成硬条件了"
    assert "ext=m4a" not in reel.FMT_SELECTOR
    assert "vcodec" not in reel.FMT_SELECTOR, "-f 里不许出现编码"
    assert "vcodec:h264" in reel.FMT_SORT, "h264 偏好要留着，下游 ffmpeg 最省事"
    # 常量要真的接到命令行上，不是摆在那儿
    source = Path(reel.__file__).read_text(encoding="utf-8")
    assert "selector, sort = FMT_SELECTOR" in source
    assert '"-f", selector' in source


def test_每一次yt_dlp调用都要带上同一组前提():
    """**新写的 yt-dlp 调用要继承旧调用的前提，一个都不能漏。**

    `--js-runtimes node` 是解 n challenge 的那一环。`fetch_captions` 是后加的
    第二处调用，我没带它——于是同一个 job 里 `download()` 下得动整条 294 秒的
    片子，字幕那条**八个 client 全红**，报的是「Only images are available」
    ＋「Requested format is not available」，看起来像「YouTube 把这台机器挡了」，
    其实是这一次调用少带了一个参数。

    和「加新能力就要同时改三处」是同一个毛病，只是这次漏的不是依赖，是前提。
    判据：源码里每一处 `[binary,` 开头的 yt-dlp 调用都要接 `*YTDLP_BASE`。
    """
    reel = _reel()
    assert "--js-runtimes" in reel.YTDLP_BASE
    source = Path(reel.__file__).read_text(encoding="utf-8")
    calls = re.findall(r"\[binary,[^\]]*", source)
    assert len(calls) >= 2, f"只找到 {len(calls)} 处 yt-dlp 调用，判据大概失效了"
    for call in calls:
        assert "*YTDLP_BASE" in call, f"这处 yt-dlp 调用没带上共同前提：{call[:90]}"


def test_赛场之上走固定海报模板():
    """**这是栏目的固定封面，不是一条片子的一次性设计。**

    以前是在 `build_match_reel` 里现拼一张上下两格的底图再盖字，每条片子的比例、
    压暗、名字位置都要重调。现在版式定死在 `tools/versus_poster.py`，换片子只换
    素材和文字——改版式改一处，三条片子一起重渲比一眼。
    """
    reel = _reel()
    source = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert "build_versus_poster" in source and hasattr(reel, "build_versus_poster")
    # 旧的现拼那套要真的删掉，不能留着让人以为还有第二条路
    assert not hasattr(reel, "build_versus_base"), "旧的现拼底图还在"
    poster = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    assert 'layout: str = "diagonal"' in poster, "默认版式不是斜切"


def test_海报必须写两个人的中文名():
    """只有两张脸的 VS 卡等于让人猜这是谁打谁。名字是模板的一部分。"""
    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415

    spec = json.loads(Path("specs/reels/eala-zheng.json").read_text("utf-8"))
    names = spec["cover"]["versus"]["names"]
    assert len(names) == 2 and all(n.strip() for n in names), names
    bare = json.loads(json.dumps(spec["cover"]))
    bare["versus"].pop("names")
    with pytest.raises(SystemExit, match="中文名"):
        versus_poster.build_poster(bare, Path("/tmp/never-written.jpg"))


def test_海报上的名字以译名表为准():
    """人名不手打——莱巴金娜、奥斯塔彭科都是这么错出去的。"""
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.zh import player_zh  # noqa: PLC0415

    spec = json.loads(Path("specs/reels/eala-zheng.json").read_text("utf-8"))
    top, bottom = spec["cover"]["versus"]["names"]
    assert top == player_zh("Zheng Qinwen"), top
    assert bottom == player_zh("Alexandra Eala"), bottom


def test_成片是3比4不是9比16():
    """**画幅定成 3:4，为的是尽可能多保住主体。**

    两个理由，都是量出来的：

    - 小红书的视频**静态展示就是 3:4**。9:16 的成片在信息流里被裁掉上下两条，
      海报的台头、比分、赛事行首当其冲，而那几行正是让人看懂这是哪一场的东西
    - 从 1920×1080 的源片里取窗口，9:16 只有 608px 宽，3:4 有 **810px 宽**，
      多 33% 的球场。球飞到两边出画、窗口中心偏一点就丢半个场，同时缓解

    代价是抖音/视频号不铺满。这是口径选择，问过了，选的就是这样。
    """
    reel = _reel()
    assert (reel.VIDEO_W, reel.VIDEO_H) == (1080, 1440)
    reel.resolve_crop(1920, 1080)
    assert (reel.CROP_W, reel.CROP_H) == (810, 1080), (reel.CROP_W, reel.CROP_H)
    # 解说片那条线**不受影响**：它仍是 9:16 画布 + 3:4 卡，两条线的画幅分开
    assert reel._EXPLAINER_H == 1920


def test_字幕上锚跟着画布重算():
    """**沿用 1524 就跑位了。** 那个数是在 1920 画布里、卡底（1680）往上 156px；
    这里整幅画布就是那张卡，同样是「卡底往上 156」换算成 1440-156=1284。
    保的是同一个物理位置——量出来的那组数一个没动。

    `PlayResY` 也要跟着改：写错的话 libass 按比例缩整套坐标，字幕整体跑位，
    **而且不报错**。
    """
    reel = _reel()
    assert reel._REEL_MARGIN_V == 1284, reel._REEL_MARGIN_V
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video.explainer import _ass_header  # noqa: PLC0415

    head = _ass_header(reel.VIDEO_H, reel._REEL_MARGIN_V)
    assert "PlayResY: 1440" in head and ",1284,1" in head
    # 解说片的默认值必须一个字节都没变
    assert "PlayResY: 1920" in _ass_header() and ",1524,1" in _ass_header()


def test_裁切窗口恒定取源片正中():
    """**从源片正中往左右两边等量扩到 3:4**，账号所有者定的。

    自动定心走过三版，全删了：

    1. 逐段取运动质心的中位数——一段几秒就一两个回合，谁球多中心就偏谁。
       实测九段 0.338 / 0.406 / 0.381 / 0.470 / 0.482 / 0.547 / 0.466 /
       0.455 / 0.407，1920 宽里差 400px，而机位从头到尾没动过
    2. 池化到全片，稳了，但仍偏离正中（0.455，86px），**而且解释不了**：
       转播主机位本来就对着球场架，正中才是最合理的先验
    3. 按白线剖面找球场对称轴——合成画面误差 0.001，真实素材上 108 张源片帧
       估出来的轴从 0.0 散到 0.85

    **可预期比「聪明」要紧。** 个别段要另定，spec 里显式给 `cx`。
    """
    reel = _reel()
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert not hasattr(reel, "auto_center"), "自动定心还在"
    assert not hasattr(reel, "court_center") and not hasattr(reel, "_court_axis")
    # 带式版式的窗口**也居中**（账号所有者 2026-08-27：「不要偏离中心的」）——
    # 第一版给带式配过一个左移的 BAND_DEFAULT_CX=0.385 去含住左下的记分条，
    # 被当场纠正撤掉了。带式的记分条走 score_inset 回贴，不动窗口。
    assert "seg.cx = 0.5" in src, "不摇的段没有取正中"
    assert not hasattr(reel, "BAND_DEFAULT_CX"), (
        "带式的偏心默认窗口又回来了——「不要偏离中心的」，记分条走 score_inset")


def test_海报进仓库且推送第一屏是它():
    """海报要**进仓库**：推送正文的第一屏就是它，微信里得一眼看出谁打谁、几比几。

    以前它叫 `_cover.jpg`、下划线开头，被「丢掉不进仓库的中间物」那步删掉了，
    于是推送里一张图都没有，只有两个按钮。
    """
    reel = _reel()
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    assert reel.POSTER_NAME == push_reel.POSTER_NAME == "poster.jpg"
    text = WORKFLOW.read_text(encoding="utf-8")
    clean = _step_block("丢掉不进仓库的中间物", text)
    rm = " ".join(line for line in clean.splitlines()
                  if not line.strip().startswith("#"))
    assert "poster.html" in rm, "渲染输入（十几 MB 的 data URI）没被清掉"
    assert "poster.jpg" not in rm.replace("poster.html", ""), "海报被误删了"


def test_推送版式照着知识解说那条且海报铺满():
    """账号所有者指定了参照（那条 7.29 的知识解说推送）和一条硬要求：
    「海报要铺满全屏的」。

    所以白卡的左右内边距**拆开写**——文字块各自带 `padding:0 16px`，海报单独
    一行顶到卡边。用负 margin 去抵消内边距在微信里不可靠，结构上让它没有内边距。
    """
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    body = push_reel.build_html("https://x/v.mp4", "https://x/c.html", "导语",
                                "标题一行\n\n正文一段", "https://x/poster.jpg",
                                "赛场之上")
    assert "border-top:5px solid #ff2442" in body        # 参照那条红边
    img = body[body.index("<img"):body.index(">", body.index("<img"))]
    assert "width:100%" in img and "padding" not in img, img
    assert "border-radius" not in img, "铺满就不该有圆角"
    # 正文只印一遍
    assert body.count("正文一段") == 1
    # 没有海报时退回无图版，而不是塞一个空 img
    assert "<img" not in push_reel.build_html("u", "c", "l", "标题\n\n正文",
                                             "", "赛场之上")


# 剪辑线上跑的栏目。台头那颗药丸写的就是它，而**栏目决定封面模板**。
_COLUMNS = {
    # ⚠️ **2026-08-04 起一律 solo。** 账号所有者：「以后都用 solo 版做
    # 『赛场之上』封面」「中间标题下面写上比分（带双方国旗）」。
    # VS 那几版留在表里**只为了已发的十几条**（`_LEGACY_VS_COVERS`）——
    # 新写的 spec 要退回 VS 必须写 `_layout_why`，见 test_栏目和封面模板要配对。
    "赛场之上": ("cutout", "diagonal", "split", "stack", "solo"),
    "网球有故事": ("solo",),                                 # 讲一个人 → 单人
    # 赛前前瞻。讲的也是一场对决——**两个人必须同框**，所以和赛场之上共用
    # VS 那几版；差别在内容（没有赛果，讲的是来路），不在版式。
    "开球之前": ("cutout", "diagonal", "split", "stack"),
}


def test_海报台头只写栏目名():
    """台头那颗小药丸只写**栏目名**，不带账号名。

    原来是「网球时差 · 赛场之上」——账号名在片子里已经有落款，海报上再挂一遍
    等于把最显眼的位置让给一句读者不需要的信息。首屏那点地方要留给
    「这是哪一场」。

    **判据不能写成 `== "赛场之上"`**（原来就是）。那把「只写栏目名」这条规矩
    钉成了「只能有一个栏目」，于是 2026-07-31 账号所有者说休伊特那条
    「是讲休伊特的儿子的话题，不是赛场之上的内容」时，加一个栏目就得改测试——
    而要守的性质从头到尾只有一条：**药丸里没有账号名**。
    """
    import re

    doc = Path("docs/columns.md").read_text("utf-8")
    columns = set(re.findall(r"\|\s*\*\*(.+?)\*\*\s*\|", doc))
    assert "赛场之上" in columns and "开球之前" in columns, "栏目表没解析出来"

    for path in sorted(Path("specs/reels").glob("*.json")):
        eyebrow = json.loads(path.read_text("utf-8"))["cover"]["eyebrow"]
        assert eyebrow in _COLUMNS, f"{path.name} 的台头是 {eyebrow!r}，不是栏目名"
        assert "网球时差" not in eyebrow, f"{path.name} 的台头挂了账号名"
        assert "·" not in eyebrow, f"{path.name} 的台头是一串，不是一个栏目名"


# 2026-08-04 那条「标题下面写上比分（带双方国旗）」之前，已经用 solo 发出去的
# 「赛场之上」。**这些不重渲**——微信那条消息发出去收不回来，为封面上多一行字
# 重跑一趟六分钟的 render 换不到任何东西。
#
# ⚠️ **只许减不许加。** 下面 `test_栏目和封面模板要配对` 里有自检：表里每个 slug
# 都必须真的存在、真的是赛场之上的 solo、而且真的没写 result——写错一个名字，
# 豁免就成了一盏恒真的绿灯。
_LEGACY_SOLO_NO_SCORE = frozenset({
    "eala-pegula-final", "fritz-jodar-final", "gea-shapovalov", "shang-vallejo",
})


def test_栏目和封面模板要配对():
    """**「赛场之上」从 2026-08-04 起一律用 solo**，退回 VS 才要写判据。

    ⚠️ **这条规矩当天整个翻了个面。** 账号所有者：「**以后都用 solo 版做
    「赛场之上」封面**」「中间标题下面写上比分（带双方国旗）」。

    老规矩（赛场之上一律 VS、用 solo 要认领）防的是**滑坡**：单人海报一旦能渲，
    下次哪条对决片子凑不齐两张照片就会「先用 solo 顶一下」。**那个滑坡现在
    不存在了**——solo 本来就是默认，没什么可省的。而反方向的滑坡冒出来了：
    有人手头正好有两张抠图，就顺手退回 VS，栏目的封面于是又变成两种样子。
    所以闸原样翻面：**非 solo 要写 `_layout_why`**。

    配对写死在两处，缺一不可：

    - spec 里（这一条）——已发布的片子不会悄悄漂
    - `build_cover` 里——**新写的 spec 也拦得住**，判据在下面那条
    """
    reel = _reel()
    legacy = reel._LEGACY_VS_COVERS
    checked_new = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        cover = spec["cover"]
        allowed = _COLUMNS[cover["eyebrow"]]
        assert cover.get("layout") in allowed, (
            f"{path.name}：{cover['eyebrow']} 只能用 {allowed}，"
            f"写的是 {cover.get('layout')!r}")
        if cover["eyebrow"] == "赛场之上" and cover.get("layout") != "solo":
            # 2026-08-04 之前发出去的那一批不动（微信那条消息收不回来），
            # 之后新写的要么 solo、要么写一句为什么退回 VS。
            if spec.get("slug") not in legacy:
                checked_new += 1
                assert str(cover.get("_layout_why", "")).strip(), (
                    f"{path.name} 是赛场之上却没用 solo，要写一句 "
                    "`cover._layout_why` 说清楚为什么退回 VS 版式")
        if cover.get("layout") == "solo":
            assert cover.get("subject"), f"{path.name} 的 solo 封面没写 subject"
            assert (cover.get("portrait") or {}).get("image") or \
                (cover.get("portrait") or {}).get("frame_at") is not None, \
                f"{path.name} 的 solo 封面没有 portrait"
            assert "versus" not in cover, f"{path.name} 是 solo，不该还有 versus"
            # 上下叠一张的变体（父子做同一个动作那种）：上格也要有图和名字，
            # 否则渲出来是半张空白，**而且不报错**——cover 铺不满就露底色。
            above = cover.get("portrait_above") or {}
            if above:
                assert above.get("image"), f"{path.name} 的 portrait_above 没有图"
                assert Path(above["image"]).is_file(), above["image"]
                # ⚠️ 这里原来要求上格必须写 `name`，理由是「两张脸摆在一起
                # 没有名字等于让读者猜」。账号所有者 2026-07-31 否了：「这里
                # 名字没必要」——台头那行和钩子已经说清谁是父亲谁是儿子，
                # 名条只是在两张脸上各压一块黑。判据跟着改成**不许有名条**。
                assert "name" not in above, (
                    f"{path.name} 的上格又挂上名条了——账号所有者定过不要")
            # ⚠️ **印不印赛果按栏目分，不按 layout 分。**
            #
            # 老规矩是「solo 一律不印赛果」，理由是休伊特那条六拍里比分是第 5 拍，
            # 印在封面上等于先说结局。**那条理由没被推翻，只是不管赛场之上了**：
            # 账号所有者 2026-08-04 要求这个栏目「中间标题下面写上比分（带双方
            # 国旗）」——赛场之上讲的是一场对决，赛果本来就是标题（VS 版式一直
            # 在印），而网球有故事讲的是一个人。
            if cover["eyebrow"] == "网球有故事":
                assert not cover.get("result"), (
                    f"{path.name} 是讲人的片子，封面印了赛果 {cover['result']!r}——"
                    "那是最后一拍，印在封面上等于先把结局说了")
            elif cover["eyebrow"] == "赛场之上" and \
                    spec.get("slug") not in _LEGACY_SOLO_NO_SCORE:
                assert cover.get("result"), (
                    f"{path.name} 是赛场之上的 solo 封面，要在标题底下印比分"
                    "（`cover.result`）——账号所有者 2026-08-04 定的")
                pair = cover.get("matchup") or []
                assert len(pair) == 2, (
                    f"{path.name} 的 solo 封面要 `cover.matchup` 给出对阵双方，"
                    "比分那一行要带双方国旗")
                for who in pair:
                    assert str(who.get("name", "")).strip(), \
                        f"{path.name} 的 matchup 少了名字"
                    # ⚠️ `country` 和 `rank` 一样：**键不许省，但可以显式写
                    # null**。null 的意思是「查过，他没有国旗」——中立身份的
                    # 球员就是这样（卢布列夫：ATP 自己的排名表里只有他名字后面
                    # 没有国家缩写，flashscore 的国别字段也是 `World`）。
                    # 省掉这个键的话，「查过是中立」和「忘了填」长得一模一样。
                    assert "country" in who, (
                        f"{path.name} 的 {who.get('name')} 缺 country——"
                        "比分那一行每个名字旁边都要有国旗；中立身份显式写 null")
                    assert who["country"] is None or \
                        str(who["country"]).strip(), (
                        f"{path.name} 的 {who.get('name')} 的 country 是空串——"
                        '查过确实没有就写 null，别写 ""')
                    assert "rank" in who, (
                        f"{path.name} 的 {who.get('name')} 缺 rank；"
                        "查过确实没有就显式写 null，别省掉这个键")
                names = [str(w["name"]).strip() for w in pair]
                assert str(cover.get("winner", "")).strip() in names, (
                    f"{path.name} 的 cover.winner 不在 matchup 里——"
                    "赛果行赢家在前，对不上就会把输的那个写成赢家")
    # **这张豁免表自己也要有判据。** 写错一个 slug，豁免就成了一盏恒真的绿灯：
    # 表里那个名字谁也不匹配，而真正该被拦的那条 spec 照样溜过去。
    slugs = {json.loads(p.read_text("utf-8")).get("slug")
             for p in Path("specs/reels").glob("*.json")}
    assert legacy <= slugs, f"豁免表里有不存在的 slug：{legacy - slugs}"
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        if spec.get("slug") in legacy:
            assert spec["cover"].get("layout") != "solo", (
                f"{path.name} 已经改成 solo 了，把它从 _LEGACY_VS_COVERS 里删掉"
                "——这张表只许减不许加")
    assert legacy <= slugs, f"豁免表里有不存在的 slug：{legacy - slugs}"
    assert _LEGACY_SOLO_NO_SCORE <= slugs, \
        f"没有比分那张豁免表里有不存在的 slug：{_LEGACY_SOLO_NO_SCORE - slugs}"
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        if spec.get("slug") in _LEGACY_SOLO_NO_SCORE:
            cover = spec["cover"]
            assert cover["eyebrow"] == "赛场之上" and cover.get("layout") == "solo", (
                f"{path.name} 不是赛场之上的 solo，不该在没有比分那张豁免表里")
            assert not cover.get("result"), (
                f"{path.name} 已经写上比分了，把它从 _LEGACY_SOLO_NO_SCORE 删掉"
                "——这张表只许减不许加")
    assert checked_new or legacy, "判据失效了：一条赛场之上的 spec 都没扫到"


def test_赛场之上的封面一律用solo():
    """上一条钉的是已发布的 spec，这一条钉的是**代码**：新写一个 spec 也拦得住。

    只钉 spec 的话，判据只在「有人把它写进仓库」之后才生效——而滑坡发生在
    渲染那一刻（手头正好有两张抠图 → 换个 layout 试试 → 出片了 → 才提交）。
    闸要装在出片那一步，和「复制页那道闸装在发的那一步不是渲的那一步」同理。

    ⚠️ 方向和 2026-08-04 之前是**反的**：那时拦的是「退回单人封面」，
    现在拦的是「退回 VS 版式」。账号所有者：「以后都用 solo 版做『赛场之上』封面」。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    vs = {"eyebrow": "赛场之上", "layout": "cutout",
          "versus": {"names": ["甲", "乙"], "top": {}, "bottom": {}}}
    with pytest.raises(reel.ReelError, match="一律用 solo"):
        reel.build_cover({"": Path("x.mp4")}, "", {"cover": vs},
                         Path("y.mp4"), 1920)
    # **写了判据就放行。** 反向验证这一支真的走过去了：它必须**越过栏目那道
    # 闸**、死在后面别的地方——只断言「不抛『一律用 solo』」证明不了这个，
    # 那句话改一个字就假绿。
    declared = {**vs, "_layout_why": "这一条两个人的戏份一样重，退回 VS"}
    with pytest.raises(reel.ReelError, match="frame_at|找不到|ffmpeg|封面|图"):
        reel.build_cover({"": Path("x.mp4")}, "", {"cover": declared},
                         Path("y.mp4"), 1920)
    # **老片子按 slug 豁免**，同样要验它真的越过了栏目那道闸。
    with pytest.raises(reel.ReelError, match="frame_at|找不到|ffmpeg|封面|图"):
        reel.build_cover({"": Path("x.mp4")}, "",
                         {"slug": "wong-gea", "cover": vs}, Path("y.mp4"), 1920)
    # 反面锚点：solo 就该放行（这儿只验它不再拦，渲染另有判据）
    with pytest.raises(reel.ReelError, match="portrait"):
        reel.build_cover({"": Path("x.mp4")}, "",
                         {"cover": {"eyebrow": "赛场之上", "layout": "solo"}},
                         Path("y.mp4"), 1920)


def test_赛场之上的比分行要带双方国旗():
    """比分板上：**矩形国旗 + 中文名（排名） + 英文名**，赢家那一行在上。

    账号所有者 2026-08-04：「中间标题下面写上比分（带双方国旗）」。

    ⚠️ **这条判据的主语换过一次。** 原来「赛场之上」印的是一行式赛果，国旗是
    emoji（🇨🇳🇰🇿）；`fix(reel): unify 赛场之上 scoreboard covers` 之后这个栏目
    **必须**走新版比分板，而新版的国旗是 `assets/flags/*.png` 的矩形图——
    于是老断言 `"🇨🇳" in html` 的主语没了，整条测试报 SystemExit。
    **主语没了就得换判据**，留着它就是一条常年红。

    仍然**真渲一次 HTML**，不查源码文本——查源码只能防「有人把它删了」，
    防不住「它从来没工作过」（这个仓库栽过：`_cut_person` 引了一个不存在的
    名字，测试断言 `"def _cut_person(" in reel` 照样绿，功能整天是坏的）。
    """
    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    # 用时走官方接口，单元测试不联网——打桩，别让判据依赖外网。
    vp._fetch_match_duration = lambda source, where: "1:12"  # type: ignore[assignment]
    base = {"eyebrow": "赛场之上", "hook": "钩子", "winner": "张帅",
            "result": "6-4 6-1",
            "scoreboard": {"court": "Centre Court",
                           "duration_source": {"url": "fixture"}},
            "matchup": [{"name": "张帅", "country": "CHN", "rank": 57},
                        {"name": "普汀塞娃", "country": "KAZ", "rank": 81}]}
    html = vp._solo_score_html(base)

    # 两面矩形国旗，而且真的是这两个国家那两张图（比数据 URI，不比数量）。
    assert vp._score_flag({"country": "CHN"}, "t") in html, f"没渲中国国旗：{html[:400]}"
    assert vp._score_flag({"country": "KAZ"}, "t") in html, f"没渲哈萨克国旗：{html[:400]}"
    assert "🇨🇳" not in html and "🇰🇿" not in html, "新版比分板不用 emoji 国旗"
    text = re.sub(r"<[^>]+>", "", html)
    assert "6" in text and "4" in text and "1" in text, f"盘分没渲出来：{html}"
    # **赢家在上**：`matchup` 是版式顺序，`winner` 才是赛果顺序。
    # wang-samsonova 那次海报印「萨姆索诺娃 6-2 6-2 王欣瑜」而标题算成
    # 「王欣瑜 vs 萨姆索诺娃」——比分夹在中间，等于声称输的那个人赢了。
    assert text.index("张帅") < text.index("普汀塞娃")
    h2 = re.sub(r"<[^>]+>", "", vp._solo_score_html({**base, "winner": "普汀塞娃"}))
    assert h2.index("普汀塞娃") < h2.index("张帅"), "换了赢家，比分板的上下没跟着换"
    # 中文名底下那一行英文名从受控译名表反查，不手打。
    assert "S. ZHANG" in text and "Y. PUTINTSEVA" in text, f"英文名没渲出来：{text}"
    # 场地和用时印在板头上。
    assert "Centre Court" in text and "1:12" in text

    # ---- 每盘赢的那个数字给品牌黄、输的给灰（账号所有者 2026-08-04）----
    # ⚠️ **判据是那一盘里谁的局数大，不是谁在前**。整场的赢家排在左边，
    # 而第一盘可能是另一个人赢的——按位置上色会把「1-6」涂反。
    mixed = vp._sets_html("1-6 7-6(5) 7-5")
    assert '<span class="setlose">1</span>' in mixed, \
        f"第一盘前面那个 1 是赢家输掉的局数，该置灰：{mixed}"
    assert '<span class="setwin">6</span>' in mixed, \
        f"第一盘是 6 赢的，该给品牌黄：{mixed}"
    # 抢七小分：跟在输家那个数后面，单独一个小号 span
    assert '<span class="tb">5</span>' in mixed, f"抢七小分没渲出来：{mixed}"
    assert re.sub(r"<[^>]+>", "", mixed) == "1-67-657-5"
    # 反向：认不出来的原样输出，不猜（退赛写法、老 spec 里的整句）
    assert '<span class="setplain">ret.</span>' in vp._sets_html("2-1 ret.")
    # 判据自己的判据：没有小分时不许凭空长出一个 `.tb`
    assert 'class="tb"' not in vp._sets_html("6-4 6-1")
    # 排名跟着名字走，不是另起一行
    assert "57" in html and "81" in html
    # 没有 result 就整行不要——网球有故事照旧一个像素都不变
    assert vp._solo_score_html({**base, "result": ""}) == ""
    # 缺国别 / 缺排名 / winner 对不上 / 缺 scoreboard，四样都要当场报错，
    # 不许悄悄少印，也不许静默退回老版一行式赛果。
    with pytest.raises(SystemExit, match="country"):
        vp._solo_score_html({**base, "matchup": [
            {"name": "张帅", "rank": 57},
            {"name": "普汀塞娃", "country": "KAZ", "rank": 81}]})
    with pytest.raises(SystemExit, match="rank"):
        vp._solo_score_html({**base, "matchup": [
            {"name": "张帅", "country": "CHN"},
            {"name": "普汀塞娃", "country": "KAZ", "rank": 81}]})
    with pytest.raises(SystemExit, match="winner"):
        vp._solo_score_html({**base, "winner": "别人"})
    with pytest.raises(SystemExit, match="scoreboard"):
        vp._solo_score_html({k: v for k, v in base.items() if k != "scoreboard"})
    # **而且它真的接在 solo 的正文里**——上面那些只证明函数好用，
    # 证明不了有人调它。`_solo_body` 里少写一处，海报就悄悄没有比分板。
    body, _ = vp._solo_body({**base, "subject": "张帅",
                             "portrait": {"image": "assets/logo/brand/icon.png"}})
    assert 'class="scoreboard"' in body and vp._score_flag({"country": "CHN"}, "t") in body, \
        "比分板没接进 solo 的正文——查函数好用防不住「没人调它」"
def test_商竣程那格是本场真实照片不是抽帧():
    """**上一版写过「没有任何一张商竣程的照片」——那句话是错的。**

    它的真实含义只是「赛事官方图库和日媒里没有」：官方媒体库按
    `<球员>-1920.jpg` / `<球员>-washington-2026-monday-r1.jpg` 五种拼法探过去
    全是 302（同目录已知存在的两张返回 200 image/jpeg，所以探测本身是有效的），
    日媒那边只有锦织圭。换到**中新社的图片新闻**立刻有三张他的比赛照。

    又一次「某一个源上没有 ≠ 不存在」，也是「过不了闸门是换源的信号，
    不是放弃的理由」。
    """
    spec = json.loads(Path("specs/reels/nishikori-shang.json").read_text("utf-8"))
    versus = spec["cover"]["versus"]
    credits = json.loads(
        Path("assets/reel/nishikori-shang.credits.json").read_text("utf-8"))
    assert versus["names"] == ["商竣程", "锦织圭"]
    for key in ("top", "bottom"):
        side = versus[key]
        assert "frame_at" not in side, f"{key} 还在抽帧"
        image = Path(side["image"])
        assert image.is_file(), image
        entry = credits[image.name]
        assert entry["date"] == "2026-07-27", f"{image.name} 不是这场"
        assert entry["checked"], f"{image.name} 没记「打开看过」"
        # 图注自证第二道闸门：来源自己写了「在比赛中」
        assert "在比赛中" in entry["caption_verbatim"]
    # 水印是**固定 100px**，不是按比例——按比例裁会漏
    assert "100px" in credits["shang-washington-2026.jpg"]["watermark"]


def test_文案里的tag最多五个():
    """**正文里的 tag 最多五个**，和知识帖那条线共用 `MAX_HASHTAGS`。

    reel 的文案是手写的 spec，不像知识帖那样过 `limit_hashtags`，所以两头都要管：
    这里盯住仓库里的 spec，`push_reel` 在发之前再拦一道——发出去就收不回来。
    """
    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("src").resolve()))
    sys.path.insert(0, str(Path("tools").resolve()))
    from tennislive.render.hashtags import MAX_HASHTAGS, hashtag_count  # noqa: PLC0415

    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        n = hashtag_count(path.read_text(encoding="utf-8"))
        assert n <= MAX_HASHTAGS, f"{path.name} 有 {n} 个 tag"

    import push_reel  # noqa: PLC0415

    assert push_reel.MAX_HASHTAGS == MAX_HASHTAGS, "两处上限要同源，别各写一个"
    src = Path("tools/push_reel.py").read_text(encoding="utf-8")
    assert "个 tag，超过" in src, "推送前没有拦 tag 数"


def test_下载残留不进仓库():
    """`source.f137.mp4.part` 混进过仓库（probe wang-pareja）。

    清理那一步原来按**名字**列（`source.mp4` / `source_av.mp4`），而 yt-dlp
    分轨下载留下的是 `source.fNNN.mp4.part`——名字对不上，10 MB 就跟着提交了。
    按**后缀**删才拦得住。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    clean = _step_block("丢掉不进仓库的中间物", text)
    assert '"$OUTDIR"/*.part' in clean, "yt-dlp 的 .part 残留没被清掉"
    for path in Path("output").rglob("*.part"):
        raise AssertionError(f"仓库里还有下载残留：{path}")


def test_面板可以先裁再铺():
    """`crop: [x0, y0, x1, y1]`——**照片能自己先裁好再入库，抽帧不能**。

    `focus` / `zoom` 只能在整幅图里挪窗口，挪不动主体在图里的位置。转播机位
    怎么拍就是怎么拍：近景天然居中，落到底格正好被文案块压住；换大全景又小得
    看不清。所以给面板一个裁切框，照片和抽帧共用。
    """
    import pytest  # noqa: PLC0415

    pytest.importorskip("PIL")
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "x.jpg"
        Image.new("RGB", (1000, 500), (30, 90, 60)).save(src)
        assert versus_poster._precrop(src, {}) == src, "没给 crop 就不该动原图"
        out = versus_poster._precrop(src, {"crop": [0.25, 0.0, 1.0, 0.5]})
        assert out != src and Image.open(out).size == (750, 250), Image.open(out).size
        with pytest.raises(SystemExit, match="四个数"):
            versus_poster._precrop(src, {"crop": [0.1, 0.2]})


def test_封面固定版式是官方抠图加本场视频全场机位():
    """「赛场之上」固定海报：官方抠图 + 本场比赛视频的底线全场机位。

    换的理由是 diagonal 那条路要**两张**「本场 + 比赛中 + 有冲击力 + 够清晰」的
    实拍同时到位。帕雷哈是 17 岁资格赛球员，四类源全探到底一张都没有，最后拿
    握手那一帧顶——渲出来**王欣瑜在同一张海报上出现了两次**（上格一次、下格
    握手里又一次），两个名字压在中缝上谁是谁都说不清。

    抠图按球员 ID 永远拿得到（WTA 走 `<Name>-Torso_<wta_id>.png`，文件名自带
    ID，人物这一要素由来源自己写死），所以「认人」这件事一次性解决。

    已经发出去的两条**显式钉着 diagonal**：素材是实拍照片不是抠图，
    不写死就会在下次重渲时炸在默认值上。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415

    reel = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert 'cover.get("layout", "cutout")' in reel, "默认版式不是 cutout"

    for path in sorted(Path("specs/reels").glob("*.json")):
        cover = json.loads(path.read_text(encoding="utf-8"))["cover"]
        layout = cover.get("layout")
        assert layout, f"{path.name} 没写 layout——会跟着默认值漂"
        if layout != "cutout":
            continue
        versus = cover["versus"]
        background = versus.get("background") or {}
        assert background.get("frame_at") is not None, (
            f"{path.name} 的 cutout 背景必须从本场比赛视频抽帧，不能用场馆资料图")
        assert "image" not in background, (
            f"{path.name} 的 cutout 背景写了静态图；要用本场视频的 frame_at")
        assert background.get("shot") == "wide_court", (
            f"{path.name} 的 cutout 背景必须是能看清整片球场的底线全场机位")
        for key in ("top", "bottom"):
            panel = versus[key]
            # 人物有两个来源，**首选本场抽帧**（见 test_封面人物首选本场抽帧）。
            # 官方棚拍图仍然认，那是源片里挑不出近景时的兜底。
            if panel.get("frame_at") is not None:
                continue
            cut = Path(panel["cutout"])
            assert cut.is_file(), f"{path.name} 的 {key} 格找不到抠图 {cut}"

    # 抠图的脚**按各自的横向位置**落在斜线上：线是 -7.4°，左端低右端高。
    # 两边都用同一个 y，右边那个会浮起来 2·(0.71-0.29)·540·tan7.4° ≈ 59px。
    seam = versus_poster.CUT_SEAM
    left, right = (versus_poster._cutout_geometry(cx, seam)
                   for cx in versus_poster.CUT_CX)
    assert left > right, "左端应该更低（y 更大）"
    assert 50 < left - right < 70, f"两脚高差 {left - right:.0f}px 不对"


def test_等复制页的预算要够Pages发布():
    """**「等不到」和「没等够」长得一模一样**，代价却完全不对称。

    2026-07-29 王欣瑜那条：`wait_for_copy_page` 探了 12 次 × 15 秒 = 3 分钟，
    全是 404，exit 1，微信一个字没发出去——而复制页在这一步放弃**之后**才
    发布出来（沙箱里探到 200，内容正是那一版）。多等几分钟只是让 runner 空转，
    等不够就是整条推送作废、前面六分钟的渲染白跑。

    所以默认预算至少 8 分钟，而且**上限要留在默认值之上**——上限卡在 30 时，
    环境变量把次数往上调是调不动的。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import inspect  # noqa: PLC0415

    import push_reel  # noqa: PLC0415

    sig = inspect.signature(push_reel.wait_for_copy_page)
    attempts = sig.parameters["attempts"].default
    delay = sig.parameters["delay"].default
    assert attempts * delay >= 480, f"只等 {attempts * delay:.0f} 秒，不够 Pages 发布"

    src = Path("tools/push_reel.py").read_text(encoding="utf-8")
    cap = re.search(r"min\((\d+), int\(os\.environ\.get\(\"TENNISLIVE_COPYPAGE_ATTEMPTS",
                    src)
    assert cap, "找不到次数上限"
    assert int(cap.group(1)) > attempts, "上限不能卡在默认值上，否则调不上去"


def test_旁白不能比它那一段的画面长():
    """**超一点点就会重叠，而且是两处一起坏。**

    每段语音按自己那段的开头 `adelay`，所以上一段一旦越界，下一段的语音
    照样从边界起——两个人同时说话；字幕那边两条 Dialogue 时间重叠，libass
    会一起画出来，屏幕上叠着两行。

    这儿原来只 `print` 一句「[注意]」，容差 0.35s。伊埃拉那条第 10 段只超了
    **0.29s**，够不着容差、一声不吭，成片里 88.7 秒那一帧上是实打实的两行
    字幕加两个声音。所以：容差收到 0.12s、`print` 改成 `ReelError`，并且
    **一次列出所有超出的段**——不然改一段就得再跑六分钟。

    另外**字幕要额外收进本段窗口**：边界时刻是插值出来的，末尾那条能比语音
    本身还长几分之一秒（那一段语音超 0.29s，字幕尾巴甩出去 1.02s）。
    兜底和它拦的那件事分开写。
    """
    reel = _reel()
    src = Path(reel.__file__).read_text(encoding="utf-8")
    # 盯那句 `print` 本身，别盯措辞——注释里要引用这句旧文案，用措辞判会自己撞自己
    assert 'print(f"[注意] 第' not in src, "还停在只 print 一句「注意」"
    assert "raise ReelError(" in src and "会和下一段的语音、字幕叠在一起" in src, (
        "旁白超长要报错，不是打印")
    assert "seg.length + 0.12" in src, f"容差要收紧到 0.12s，0.35 拦不住 0.29s 的超出"
    # 字幕收进本段窗口：末尾时刻要被 min(...) 夹住
    assert "min(b, limit)" in src, "字幕没有收进本段窗口"


def test_角标把两件事放进同一帧():
    """**父亲那一下只有图，没有影像**（三条官方存档集锦都扫过，都没拍到）。

    账号所有者定的做法不是切一张整屏静图，而是**压在角上**：儿子做那一下的
    同一帧里就有父亲做同一个动作，「他做了父亲的那个动作」这句话本身就是这一
    帧——而且不停三秒、不剪断片子。

    三条判据，都是「不吭声」型的错：

    - **图必须在**——路径写错时 ffmpeg 只会在切片那一步炸，而那已经是下完
      三条源片之后了
    - **corner 只能是四个角之一**——写错会被 `.get(..., "tl")` 悄悄吃掉
    - **音轨索引要跟着输入路数走**——角标插进第 1 路之后，补位静音从 `1:a:0`
      变成 `2:a:0`；取错流不报错，只是没声音
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    art = "assets/reel/lleyton-vicht-inset.png"
    assert Path(art).is_file(), "角标素材不在仓库里"
    spec = {"cover": {}, "segments": [
        {"start": 1, "end": 7, "source": "r1",
         "inset": {"image": art, "corner": "tl", "width": 0.34}}]}
    segs = reel.parse_segments(spec, {"r1": Path("a.mp4")}, "r1")
    assert segs[0].inset["corner"] == "tl"

    bad = {"cover": {}, "segments": [
        {"start": 1, "end": 7, "source": "r1",
         "inset": {"image": "assets/reel/没有这张.png"}}]}
    with pytest.raises(reel.ReelError, match="找不到文件"):
        reel.parse_segments(bad, {"r1": Path("a.mp4")}, "r1")

    corner = {"cover": {}, "segments": [
        {"start": 1, "end": 7, "source": "r1",
         "inset": {"image": art, "corner": "middle"}}]}
    with pytest.raises(reel.ReelError, match="corner"):
        reel.parse_segments(corner, {"r1": Path("a.mp4")}, "r1")

    story_text = {"cover": {}, "segments": [
        {"start": 1, "end": 7, "source": "r1",
         "inset": {"image": art, "corner": "tr", "kind": "story_text",
                   "width": 0.56, "pad": 0.085, "show_for": 3.8,
                   "motion": "editorial"}}]}
    assert reel.parse_segments(story_text, {"r1": Path("a.mp4")}, "r1")
    story_text["segments"][0]["inset"]["show_for"] = 6.0
    with pytest.raises(reel.ReelError, match="story_text"):
        reel.parse_segments(story_text, {"r1": Path("a.mp4")}, "r1")

    # 没有角标时滤镜图不变形，只是把 [base] 改名
    assert reel._overlay_chain("[0:v]x[base]", {}) == "[0:v]x[vout]"
    chain = reel._overlay_chain("[0:v]x[base]", {"image": art, "corner": "br"})
    assert "[1:v]scale=" in chain and "overlay=W-w-" in chain and "[vout]" in chain

    # 音轨索引：有角标时补位静音是第 2 路
    body = Path(reel.__file__).read_text(encoding="utf-8")
    assert 'f"{null_idx}:a:0"' in body, "补位静音的输入索引写死了，插入角标后会取错流"
    assert "null_idx = 2 if ins else 1" in body
def test_封面人物首选本场抽帧():
    """封面的两个人**首选从本场源片抠**，官方棚拍图退居兜底。

    账号所有者的原话：「因为更贴近比赛的服装，感觉会更好，用之前资料就有点
    脱节」。棚拍图的衣服、光、背景都跟这场球没关系，压在本场画面上像两张贴纸。

    顺带还赢在分辨率，这个能量（模板槽位 634px 高）：

        ATP 官方棚拍 裁到胯   265×410   → 1.55× **放大**
        本场抽帧              660×1040  → 0.61× 缩小

    看着"正规"的棚拍图其实是全套素材里最软的一档。

    挑帧的三条判据是账号所有者给的，落在 `tools/pick_cover_frames.py`：
    **正脸或稍微侧脸、上半身直立、表情读得出**。
    """
    reel = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    poster = Path("tools/versus_poster.py").read_text(encoding="utf-8")

    assert "def _cut_person(" in reel, "没有从源片抠人的那条路"
    # **`post_process_mask=True` 不能省**：不加的时候深色球衣压在深色背景墙上会
    # 留一整块方底，渲到海报上是一个看得见的矩形边。那不是模型不行，是后处理没开。
    assert "post_process_mask=True" in reel, (
        "抠图没开 post_process_mask——深色球衣会留一整块方底")
    assert 'CUT_MODEL = "isnet-general-use"' in reel, (
        "换模型要重新把 alpha 摊在棋盘格上看边：u2net 把发梢切平了一条")
    # 报错要把「首选抽帧」说出来，否则下一个人只会看到两条棚拍图的 URL
    anchor = "cutout 版式的 {key} 格"
    assert "frame_at" in reel[reel.index(anchor):reel.index(anchor) + 700]
    assert "首选本场抽帧" in poster, "海报模块的报错没指出首选是抽帧"

    # 判据三条要写在挑帧工具里，别只活在对话里
    picker = Path("tools/pick_cover_frames.py")
    assert picker.is_file(), "挑帧工具没了——这三条判据就只剩口头约定"
    text = picker.read_text(encoding="utf-8")
    for rule in ("正脸", "上半身直立", "表情"):
        assert rule in text, f"挑帧工具里没写「{rule}」这一条"


def test_抠出来只有一条残影也要报错():
    """**「抠出来是空的」有两种，`getbbox()` 只拦得住一种。**

    完全透明它拦得住。抠到一条球拍残影、一道边线，bbox 非空，于是一路绿到底——
    render success、`check_reel_landed` 0 项不合格、**海报上人没了**。
    2026-08-01 黄泽林那张就是这么出去的：138.14s 那一帧，左格只剩背景和一道白线，
    只有打开海报才看得见。又一次「兜底出事的时候不吭声」。

    判据是**不透明像素占裁切框的比例**：人物近景是一大块，残影是一条线。
    门槛从已知好素材倒推——官方半身抠图 65%，两者隔着一个数量级。

    报错要说出路（换一帧 / 退回官方抠图），别只说不行。
    """
    reel = _reel()
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")

    assert 0 < reel.CUT_MIN_SHARE < 0.2, (
        f"门槛 {reel.CUT_MIN_SHARE} 不在合理量级——太低拦不住残影，太高会误伤真人物")
    # 门槛怎么来的要留下判据，否则下一个人只会看到一个数字
    head = src[:src.index("CUT_MIN_SHARE = ")]
    assert "65%" in src[src.index("CUT_MIN_SHARE") - 400:src.index("CUT_MIN_SHARE")], \
        "没记下这个数是从哪个已知素材倒推的"
    assert "CUT_MIN_SHARE" in src[src.index("def _cut_person("):], "闸没接在抠图那一步"
    block = src[src.index("def _cut_person("):]
    block = block[:block.index("def ", 10)]
    assert "share <" in block, "没有按比例判"
    for way_out in ("换一帧", "官方抠图"):
        assert way_out in block, f"报错没说出路：{way_out}"
    # 比例要**每次都打进日志**，不只在失败时——下次调门槛才有数可依
    assert "占裁切框" in block and "print(" in block, "成功时不报比例，等于没量过"


def test_挑帧的门槛要在同一个口径下量():
    """清晰度必须**把脸缩到同一个尺寸再算**，否则门槛是反的。

    第一版直接在原尺寸 ROI 上求 Laplacian 方差，结果和放大倍率成反比——
    371px 的近景 17.6，198px 的中景 123.9。于是 40 这个门槛把**所有近景**
    判成「糊」，整条片子过闸 0 帧，而它长得和「这条片子里没有近景」一模一样。

    同一个毛病还有第二处：运动量的门槛拍了个 12，而我已经打开看过、确认站着
    不动的那几帧量出来是 19~25——门槛会把正确答案全部拒掉。所以运动量降级成
    排序里的罚分，不设闸。

    这就是「门槛的数要在同一个口径下量」和「空结果先自证是真空」的合体：
    **自己写的探测脚本报空时，先拿一个已知非空的口径对一下**。
    """
    text = Path("tools/pick_cover_frames.py").read_text(encoding="utf-8")
    assert "cv2.resize(roi, (SHARP_SIDE, SHARP_SIDE))" in text, (
        "清晰度还在原尺寸上算——脸越大分越低，门槛是反的")
    assert "MAX_MOTION" not in text, "运动量又变回闸门了；量出来 19~25，闸设不住"
    # 不合格的也要报出来：只列通过的检查，没法证明它真看过整条片子
    assert "丢弃" in text, "没有把被丢掉的帧和原因打出来"


def test_抽帧抠图要同时改代码工作流和预检():
    """「加新能力要同时改三处」——playwright、Chromium、cv2 三次都漏过。

    三次都死得很晚：下完 64MB 源片、合完原声之后才报 ModuleNotFoundError，
    每次白跑一分半。而沙箱里这些依赖恰好都装着，本地怎么试都试不出来。

    rembg 是第四次，所以三处一起钉住：

    1. 代码：`_cut_person` 用它
    2. 工作流：`pip install "rembg[cpu]"`，并缓存 176MB 的模型
    3. 预检：**在下源片之前** import 一次，让失败发生在第 5 秒
    """
    flow = Path(".github/workflows/match-reel.yml").read_text(encoding="utf-8")
    assert "cutout]" in flow, "工作流没装 cutout extra——runner 上会死在 import rembg"
    assert 'cutout = ["rembg[cpu]' in Path("pyproject.toml").read_text("utf-8"), (
        "依赖没钉在 pyproject 里；装裸包名踩过 opencv 5.x 那次")
    assert "~/.u2net" in flow, "没缓存抠图模型，每条片子都要现下 176MB"

    reel = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert "def _preflight_cutout(" in reel, "没有开跑前的依赖预检"
    body = reel[reel.index("def render("):]
    check = body.index("_preflight_cutout(spec)")
    # **别拿整句 `with stage("下载源片")` 当锚点。** 多源之后这一句成了
    # `with stage(f"下载源片 {key or '(主源)'}")`，字面量对不上，测试直接
    # ValueError——它想验的「预检排在下载之前」明明还成立。锚点只认下载那件事。
    download = body.index("下载源片")
    assert check < download, "预检排在下载之后——又是下完 64MB 才报错"


def test_挑帧要在probe那一步跑并且整帧不进仓库():
    """`pick_cover_frames.py` 得**在 runner 上**跑，而且只留候选墙。

    源片只在 runner 上有——沙箱下不动 YouTube。这一步不在 probe 里做，挑帧就
    只能拿 2 秒一格的缩略图墙用肉眼找正脸，而那正是这个工具要替掉的活。

    整帧不进仓库。量出来的（1920×1080 转播帧）：PNG 单张 0.7~0.8 MB、12 张
    约 9 MB；q92 的 JPEG 单张 132 KB、12 张 1.6 MB。**两种都过得了清理那道
    「单个 8 MB」的兜底**，却是每探一次就往仓库里加一份——和 `.part` 那次是
    同一个毛病：按单张尺寸设的闸拦不住按批次累积的量。
    """
    flow = WORKFLOW.read_text(encoding="utf-8")
    assert "tools/pick_cover_frames.py" in flow, "probe 不出封面候选帧"
    steps = _steps(flow)
    probe = next(i for i, n in enumerate(steps) if "缩略图墙" in n)
    picks = next(i for i, n in enumerate(steps) if "封面候选帧" in n)
    clean = next(i for i, n in enumerate(steps) if "丢掉不进仓库的中间物" in n)
    assert probe < picks < clean, f"挑帧要排在下载之后、清理之前：{steps}"

    cleanup = _step_block("丢掉不进仓库的中间物", flow)
    pats = re.findall(r'"\$OUTDIR"/(\S+)', cleanup)
    pats = [p.rstrip("\\").strip() for p in pats if p.strip()]
    assert any(fnmatch("cover_candidates/cand_00_t12.5.jpg", p) for p in pats), (
        f"候选整帧不会被清理掉，每探一次往仓库里加 5 MB。现有模式：{pats}")
    for keep in ("cover_candidates/sheet.jpg", "cover_candidates/candidates.json"):
        assert not any(fnmatch(keep, p) for p in pats), f"{keep} 被误删了"

    # 候选帧存 JPEG，候选墙一格要够大——它是唯一进仓库的那份
    text = Path("tools/pick_cover_frames.py").read_text(encoding="utf-8")
    assert 'f"cand_{i:02d}_t{rec[\'t\']}.jpg"' in text, "候选帧还在存 PNG，单张 2~3 MB"
    assert "tw = 640" in text, "候选墙一格太小，判不了「能不能看到表情」"


def test_封面停多久跟着配音走():
    """账号所有者定的：「这个栏目不要求〔固定几秒〕，**随着配音切换**吧」。

    在这之前封面是**定长静止 2.6 秒的哑屏**——`anullsrc` 一路铺到底，开场那
    一屏一个字都没说。改成配音驱动之后要钉住四件事，每一件都是「不吭声」型的：

    - **长度由语音算**（`cover_length`），不是 spec 里另写一个数。写两处必分叉
    - **没配音的片子退回定长，并且要出声说退了**。存量的赛场之上都没有封面
      配音，悄悄退回去的话，「封面短了」和「配音没合出来」长得一模一样
    - **封面那一路要真的混进音轨**。滤镜标签从 filters 一起攒，不在下游拿
      另一个条件重筛——原来 `names` 就是重筛的，封面那一路定义了没人接
    - **长度要落进 render.json**。跟着配音走之后从 spec 算不出来，
      `check_reel_landed.py` 拿常量对片长只会得到一个假红
    """
    reel = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    check = Path("tools/check_reel_landed.py").read_text(encoding="utf-8")

    assert "def cover_length(" in reel, "封面长度还是个常量，没有跟着配音走的那条路"
    assert "def synth_cover(" in reel, "封面那句没有单独合成——它得在渲封面之前就有"
    # 合成排在渲封面之前：反过来的话长度还没算出来，只能又退回常量
    body = reel[reel.index("def render("):]
    # **盯的是真正接收 `cover_secs` 的那次调用**，不是「第一个 build_cover(」。
    # `--cover-only` 那条快速预览路径也调 build_cover（拿默认时长渲一张海报
    # 就退出，海报本来就与时长无关），它排在最前面——按 `index()` 找会撞上它，
    # 而那是误判：production 那条路照旧先算长度。判据宁可窄，不可宽。
    production = body.index("cover_secs, tail=")
    assert body.index("cover_secs = cover_length(") < production, (
        "封面长度算在渲封面之后——那就只能拿常量渲，等于没改")
    # 定长那条路要出声
    assert "没有配音，定长停" in reel, "退回定长时不吭声，和「配音没合出来」分不开"
    # 封面那一路要接进混音，标签不能在下游重筛
    assert "voice_labels.append" in reel, "混音的标签又在下游重筛了"
    # 攒起来的标签要**原样**进滤镜图。这一句原来写在 render() 里，闪避那道
    # `apad` 修完之后整个图抽成了 `duck_filtergraph`，join 跟着搬了进去——
    # 判据要跟着搬，不是跟着删：它拦的是「下游拿另一个条件重筛一遍」，
    # 而封面那一路当年就是这么被漏掉的（定义了没人接）。
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as _reel_mod  # noqa: PLC0415

    graph = _reel_mod.duck_filtergraph(["[1:a]adelay=0|0[v0]", "[2:a]x[v1]"],
                                       ["[v0]", "[v1]"])
    assert graph.count("[v0]") == 2 and graph.count("[v1]") == 2, (
        f"攒起来的标签没有全部进滤镜图：{graph}")
    # 长度要记进产物旁边
    assert '"cover_seconds"' in reel, "封面长度没落进 render.json"
    assert "render.json" in check, "检查工具还在拿常量算封面长度"
    assert "没有 render.json" in check, "读不到 render.json 时不吭声地退回常量"


def test_封面念的就是海报上那句钩子就不另排字幕():
    """念的和印的是同一句，就别在同一帧里再写一行小字。

    但**判据是「一不一样」，不是「封面一律不出字幕」**——封面那句要是另说了
    一件事，它照样要有字幕：「静音刷是默认状态」这条对开场同样成立。
    一律不出字幕会把这个区别抹掉，而且抹掉之后不吭声。
    """
    reel = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert "drop_punctuation" in reel, "比对没有去标点——印的带换行、念的带句号，永远不等"
    assert "不另排字幕" in reel
    # else 分支必须还在：另说一件事时要排字幕
    head = reel[reel.index("[封面] 旁白就是海报上那句钩子"):]
    assert "else:" in head[:400] and "subtitle_cues(readable(cover_text)" in head[:800], (
        "封面变成一律不出字幕了——另说一件事的那种情况就没字幕了")

    spec = json.loads(Path("specs/reels/hewitt-washington.json").read_text("utf-8"))
    cover = spec["cover"]
    assert cover.get("narration"), "休伊特那条封面没有配音——那就又是一屏哑的"
    from tennislive.video.subtitle_text import drop_punctuation
    assert drop_punctuation(cover["narration"]) == drop_punctuation(
        cover["hook"].replace("\n", " ")), (
        "封面念的和印的不是同一句了。那没问题，但字幕会跟着出现——"
        "确认过排版再改这条断言")


def test_检查工具认的画布要和成片的画布是同一个():
    """`check_reel_landed.py` 一度还在要 1080×1920，而成片早改成 3:4 了。

    于是它每跑一次都在第一行报「不合格」——**一条常年红的检查等于没有检查**，
    和常年不变的 skip 数字是同一个毛病：没人真的看过。

    两个数写在两处就会分叉，所以这儿把它们钉在一起。检查脚本是**故意**只用
    标准库的（要能在任何地方跑），不能 import 过去拿，那就用测试当那根绳子。
    """
    reel = _reel()
    text = Path("tools/check_reel_landed.py").read_text(encoding="utf-8")
    assert f"VIDEO_W, VIDEO_H = {reel.VIDEO_W}, {reel.VIDEO_H}" in text, (
        f"检查工具认的画布和成片的 {reel.VIDEO_W}×{reel.VIDEO_H} 对不上")
    assert "(VIDEO_W, VIDEO_H)" in text, "画布比对又写死成字面量了"


def test_栏目名从spec读不要在命令行上另写一遍():
    """推送标题里的栏目，和海报台头上的栏目，**必须是同一个值**。

    `push_reel.py` 原来把 `--column` 默认成「赛场之上」，而工作流一个字都没传
    ——于是休伊特那条「网球有故事」的片子，海报印着网球有故事、微信标题写着
    赛场之上。**同一条推送里两个栏目名，而推送发出去就收不回来。**

    这是「栏目决定封面模板，不是素材凑手决定」那条的另一半：栏目只有一个出处
    （spec 的 `cover.eyebrow`），海报和标题都从它来。读不到要报错——悄悄退回
    一个默认值，正是上面那个错本身。
    """
    import pytest  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    assert push_reel.column_of(
        Path("specs/reels/hewitt-washington.xhs.txt")) == "网球有故事"
    assert push_reel.column_of(
        Path("specs/reels/wong-lehecka.xhs.txt")) == "赛场之上"

    # 默认值不能再是某个栏目名——那正是这条测试拦的那个错
    text = Path("tools/push_reel.py").read_text(encoding="utf-8")
    assert 'ap.add_argument("--column", default="赛场之上"' not in text, (
        "栏目名又写死默认值了；工作流不传，网球有故事就会被标成赛场之上")

    # 读不到就报错，别退回默认
    with pytest.raises(SystemExit, match="取不到栏目名"):
        push_reel.column_of(Path("specs/reels/没有这条.xhs.txt"))

    # 每条 spec 的栏目都要和它的封面模板配对（solo ↔ 网球有故事）
    for slug, spec in _reel_specs().items():
        cover = spec.get("cover") or {}
        assert str(cover.get("eyebrow", "")).strip(), (
            f"{slug} 没写 cover.eyebrow——推送标题会取不到栏目名")


def test_没有名字是凭空来的():
    """`ruff --select F821`：整个仓库不许有未定义的名字。

    一天里被这一条咬了两次，**两次 `py_compile` 和 pytest 都看不见**：

    - `build_versus_poster` 里 `_cut_person(source, …)` —— 这个作用域里根本没有
      `source`（它拿的是 `sources` 字典加 `primary`）。也就是说 #105 引进的
      「封面人物首选本场抽帧」**一次都没跑起来过**，第一次用必 NameError
    - 我自己把封面时长传给 `build_cover` 却漏了它委托的 `build_versus_poster`，
      在 runner 上下完两条源片、合完配音、渲完海报之后才炸（run 30622667742）

    这正是「加新能力就要同时改三处」和「让失败发生在第 5 秒」两条的合体，
    只是这次连第 5 秒都不用——静态就能看见。

    `cards.py` 的主题色是 `globals().update` 灌进来的，静态看不见，**排除写在
    pyproject 里**而不是藏在这儿：让它是一个看得见的决定。
    """
    import shutil  # noqa: PLC0415

    ruff = shutil.which("ruff")
    # 缺依赖就 skip 的话，这条检查会常年跳过而没人发现——和常年红是同一个毛病。
    # ruff 已经写进 dev extra，CI 的 `pip install -e ".[dev,…]"` 就带上了。
    assert ruff, 'ruff 没装。装：pip install -e ".[dev]"'
    proc = subprocess.run(
        [ruff, "check", "--select", "F821", "--output-format", "concise",
         "src", "tools", "tests"],
        capture_output=True, text=True)
    assert proc.returncode == 0, (
        "有名字是凭空来的（F821）——这类错 py_compile 和 pytest 都看不见，"
        f"只会在真跑到那一行时炸：\n{proc.stdout}{proc.stderr}")


def test_封面抽帧抠图那条路要真的被调用一次(tmp_path, monkeypatch):
    """**「写了」不等于「跑过」。**

    `_cut_person(source, …)` 里的 `source` 在 `build_versus_poster` 的作用域里
    从来就不存在（它拿的是 `sources` 字典加 `primary`）——「封面人物首选本场
    抽帧」合并了、写进文档了、还带着测试，却**一次都没跑起来过**。

    那条测试是 `assert "def _cut_person(" in reel`：**它证明的是这段代码被写
    出来了，不是它跑得起来**。所以这儿改成真调用一次，让那一行真的执行。

    走的是「源片键写错」这个分支：它在碰 ffmpeg / rembg 之前就返回，沙箱里跑
    得动，而**要执行到那句报错，`sources` 和 `primary` 必须都在作用域里**——
    正是当初炸掉的那两个名字。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    # `_grab` 会 shell 出去抓帧，沙箱没有 ffmpeg 也不需要真抓——它只按约定
    # 返回路径。挡掉之后就能走到下面那个循环。
    monkeypatch.setattr(reel, "run", lambda *a, **k: None)

    cover = {
        "layout": "cutout",
        "versus": {
            "background": {"frame_at": 12.0, "shot": "wide_court"},
            "top": {"frame_at": 30.0, "source": "拼错的键"},
            "bottom": {"cutout": "assets/reel/lleyton-vicht-inset.png"},
        },
    }
    with pytest.raises(reel.ReelError, match="拼错的键"):
        reel.build_versus_poster({"r1": Path("a.mp4")}, "r1", cover,
                                 tmp_path / "part_cover.mp4")


def test_封面可以指定谁在前压住谁():
    """两个人叠在一起时，**赢的那个画在上面**——前后关系本身就在说结果。

    压的是后面那个（z-index 2），不是把前面那个抬到 4。名字那一层是 4、
    VS 圆牌是 5：抬上去会盖住名字，而名字是这张卡在信息流里唯一能被扫到的东西。

    还要用 `img.c-x` 提一档特异性，否则后面那条 `.cut{z-index:3}` 会把它盖回去
    ——同为单类选择器时后写的赢，而 `.cut` 恰好写在后面。**这种错不报错**，
    只是叠压方向反过来，渲出来才看得见。

    顺带：这一层关系在黄泽林那条里还兼着修一道**修不掉**的切口。近景抽帧里
    人比画框大（去掉录屏 UI 后抠出来四边全贴满），侧边一定断；把前面那个放大、
    中心外移，断面就落到画布外面——**切口不能修掉，但可以让它不在画面里**。
    """
    src = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    assert 'panel.get("front")' in src, "没有「谁在前」这个开关"
    assert 'img.c-{side}{{z-index:2}}' in src, (
        "要用 img.c-x 压后面那个：写成 .c-x 会被后面的 .cut{z-index:3} 盖回去")
    for layer in ("z-index:4", "z-index:5"):      # 名字、VS 圆牌
        assert layer in src, f"{layer} 那一层没了，前后关系的前提就变了"

    spec = json.loads(Path("specs/reels/wong-brooksby.json").read_text("utf-8"))
    versus = spec["cover"]["versus"]
    assert versus["top"].get("front") is True, "黄泽林应该在前"
    assert not versus["bottom"].get("front"), "只能有一个在前"
    # **侧边的断面靠淡出解决，不靠「把人放大到溢出画布」。**
    # 第一版是后者：把前面那个放到 0.48 让左缘落到画外，代价是他占了大半张
    # 封面（账号所有者：「占得地方太大了」）。构图不该替修图背锅——所以现在
    # 钉的是淡出这条路还在，尺寸放开给版面自己定。
    src = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    assert "def _fade_cut_sides(" in src, "侧边淡出没了，抠图的断面会变回一条硬边"
    assert "_fade_cut_sides(src)" in src, "写了函数却没调用"
    # 烤进 alpha，不是 CSS 遮罩：多层遮罩合成在这条渲染路径上不生效，
    # **而且不报错**，只是安静地什么也不做，渲出来和没加一模一样。
    # 判据盯**做了什么**（改 alpha），不盯「没写某个词」——上一版按
    # `"mask-composite" not in src` 判，结果撞上了解释这条弯路的注释本身。
    # 这个文件里已经有同样的教训：盯那句本身，别盯措辞。
    assert "im.putalpha(" in src, "侧边淡出没有落到 alpha 上，多半又退回 CSS 遮罩了"
    faded = src[src.index("def _fade_cut_sides("):]
    assert "getextrema()" in faded.split("def ", 2)[0] + faded[:1200], (
        "没有先量 alpha 贴没贴到边——那样会把人物自己的轮廓也淡掉")


def test_源片自己烧了记分条时字幕要让开():
    """两层白字叠在一起，而且**只在竖版源片上才撞**。

    以前没撞过是运气：16:9 转播源片的记分条也在左下，但 3:4 的窗口只取中间
    42% 宽，整块被裁掉了。Tennis TV 的竖版短片画幅本来就是竖的，裁不掉——
    记分条量出来占 y 1281~1439，而字幕默认上锚是 1284，第一版渲出来四帧抽检
    帧帧都中：「5比1 盘点」压着 `40`，「你还 hold 住吗?」压着 `6`。

    **不做自动检测。** 记分条的位置、颜色、在不在都随播出方变，检测不到时会
    悄悄退回原位——又是「兜底出事的时候不吭声」。让写 spec 的人量一次、写死。
    """
    reel = _reel()
    src = Path(reel.__file__).read_text(encoding="utf-8")
    # 默认值从 2026-08-27 起按版式分（带式锚进底带），但 `subtitle_top` 的
    # 人工覆盖必须还在——那正是这条判据守的东西。两头都钉：
    # 读取仍然带 spec 覆盖，而默认值真的走 default_margin_v()（不许绕过它
    # 另写一个死数，那会把带式那半默认悄悄断掉）。
    assert 'spec.get("subtitle_top", default_margin)' in src, (
        "字幕上锚不能只有一个写死的值——竖版源片会撞上它自己的记分条")
    assert "default_margin = default_margin_v()" in src, (
        "字幕默认锚要从 default_margin_v() 来（按版式分），不许另写死一个数")
    # 抬高了要说出来：默认值和实际值不一样却不吭声，下次没人知道它被挪过
    assert "比默认抬高" in src, "抬了字幕却不打印，产物上看不出是有意的还是漂了"

    spec = json.loads(Path("specs/reels/wong-brooksby.json").read_text("utf-8"))
    top = spec["subtitle_top"]
    # 两行字幕占 156px，下沿必须落在记分条上沿 1281 之上
    assert top + 156 < 1281, f"字幕上锚 {top} 两行到 {top + 156}，仍然压在记分条上"

    # **这是特例，不是新默认。** 账号所有者定的：抬字幕只针对这条源片，
    # 版式本身照旧。所以两头都钉住——默认值不许被改掉，别的片子不许跟着抬。
    assert reel._REEL_MARGIN_V == 1284, (
        "默认上锚被改了。抬字幕是给「源片自带记分条」那种源片的特例，"
        "不是新的版式——改默认等于把一条片子的补丁摊给全部")
    others = [p.name for p in sorted(Path("specs/reels").glob("*.json"))
              if p.name != "wong-brooksby.json"
              and "subtitle_top" in json.loads(p.read_text("utf-8"))]
    assert not others, f"这些片子也写了 subtitle_top，特例正在扩散：{others}"


def test_每一段都收在死球之后():
    """一分打到一半切走，观众不知道这分谁赢了。

    账号所有者的原话：「很多球没有播放完成就切到下一个了，建议死球后再切换
    下一个，不然让人看的不明不白的」。而**看懂这一分归谁**是回合镜头唯一的作用。

    死球时刻不用靠看球——源片烧死的记分条在死球那一刻才翻牌，
    `tools/find_point_ends.py` 就是量它。**框只框比分那一列**：框整条记分条
    同一门槛只报 26 次，框比分列报 39 次，名字那半边从不变，把翻牌的占比稀释
    掉一个量级。又一次「门槛的数要在同一个口径下量」。

    ⚠️ **工具只给候选。** 赛点那一分它抓不到——转播在庆祝时不翻牌，记分条一直
    停在 `6 6 40`。那一段是打开看定的：172.5 秒球还在打，173.5 秒已经是握拳
    嘶吼。所以最后一步永远是人看。
    """
    tool = Path("tools/find_point_ends.py")
    assert tool.is_file(), "死球检测工具没了，段尾就只能靠猜"
    text = tool.read_text(encoding="utf-8")
    assert "dark" in text, "没有「记分条还在不在」这一判据——镜头切走也会被当成死球"
    assert "比分那一列" in text, "没记下框要框哪儿，下一个人会框整条然后漏掉一半"

    spec = json.loads(Path("specs/reels/wong-brooksby.json").read_text("utf-8"))
    # 三处切在球中间的段尾，改完不许退回去
    ends = [s["end"] for s in spec["segments"]]
    for bad, good in ((128.0, 132.7), (143.0, 147.7), (173.0, 173.0)):
        assert bad not in ends, f"{bad}s 那个段尾切在球中间，实际这一分到 {good}s 才结束"
    assert "_editing_why" in spec, "为什么这么切没有留下判据"


def test_旁白要讲清楚比赛走向():
    """账号所有者：「同时要讲清楚比赛的走向，这样大家才不会看的一头雾水」。

    赛报片不是集锦。第一版只报了几个孤立比分（「五比一」「赛点」），
    第二盘被对手压着打了大半盘这条线整个是空的，观众串不起来。

    判据取「转折」这一环——四问里最容易漏、也最要命的那个：前面赢得轻松、
    后面赢了，中间发生过什么，不说观众就不知道这场球难在哪。
    """
    spec = json.loads(Path("specs/reels/wong-brooksby.json").read_text("utf-8"))
    told = "".join(s["narration"] for s in spec["segments"])
    # **第二次栽在措辞上了。** 原来只认「转折」「反了过来」两个词；按逐分数据
    # 重写之后，稿子把转折讲得比原来细（「五平，对方发球局，零比四十。第三个
    # 破发点他拿下了」），却一个词都没撞上，测试红了——而它下面三行正写着
    # 「别按措辞判」。网球比赛的走向就是由**破发**换的手，认这一类词即可；
    # 真要判「讲没讲清」得有人读，测试只拦「整条线压根没提」。
    swing = ("转折", "反了过来", "破发", "反超", "扳回", "追平")
    assert any(w in told for w in swing), \
        f"旁白没讲这场球是怎么换的手，观众不知道难在哪（找的是 {swing}）"
    # **别按措辞判。** 上一版查「领先」，而稿子写的是「一直是布鲁克斯比在前」——
    # 意思在、词不在，测试自己红了。改成结构判据：输的那个必须在**开场之后**
    # 还被提到，也就是片子真的讲了他做过什么，而不只是开头报了个名字。
    loser = next(n for n in spec["cover"]["versus"]["names"]
                 if n != spec["cover"]["winner"])
    later = "".join(s["narration"] for s in spec["segments"][2:])
    assert loser in later, (
        f"{loser} 只在开场露过名字，中段一句没提——那就没有「对手一度领先」这条线，"
        "走向是断的")
    assert "_narration_why" in spec, "为什么这么写没有留下判据"


def test_封面别停太久():
    """`2.6` 秒会被当成图片。

    账号所有者：「封面 2.6 秒是不是有点多啊，建议缩短点，不然好多人以为是图片
    不是视频」。封面同时是信息流里的缩略图——点进来的人已经看过它了，画面迟迟
    不动，第一反应是「这是张图」，然后划走。
    """
    reel = _reel()
    assert reel.COVER_SECONDS <= 1.5, (
        f"封面停了 {reel.COVER_SECONDS} 秒，太长会被当成图片")
    src = Path(reel.__file__).read_text(encoding="utf-8")
    assert "以为是图片" in src, "为什么缩短没有留下判据，下次会有人调回去"


def test_封面跟着配音走只给网球有故事():
    """两条线的封面节奏是**分开的**，别互相牵动。

    账号所有者定的：「封面跟着配音走，是针对网球有故事类的」「赛场之上还是按
    1.2」。网球有故事讲一个人，封面念的就是海报上那句钩子，说完就切；赛场之上
    是一场对决的赛报，封面只是短亮相——**停久了会被当成图片不是视频**。

    所以赛场之上写了 `cover.narration` 要**报错**，不是默默把封面拉长：
    悄悄拉长的话，「封面怎么变长了」和「谁给它加了句配音」长得一模一样。
    """
    reel = _reel()
    src = Path(reel.__file__).read_text(encoding="utf-8")
    block = src[src.index("def synth_cover("):]
    block = block[:block.index("def cover_length(")]
    assert "赛场之上" in block and "raise ReelError(" in block, (
        "赛场之上写了封面配音不会报错，封面会被悄悄拉长")
    assert reel.COVER_SECONDS == 1.2, "赛场之上的定长封面不是 1.2 秒了"

    # 存量的赛场之上一条都不许有封面配音
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") or {}
        column = str(spec.get("column") or cover.get("eyebrow") or "")
        if "赛场之上" in column:
            assert not cover.get("narration"), f"{path.name} 是赛场之上，封面不该配音"




def _yaml_only(text: str) -> str:
    """去掉整行注释。

    工作流里的注释是这个仓库记教训的地方，正文里必然写着当年那些错值
    （`伊埃拉 vs 郑钦文`）和不该装的东西（ffmpeg）。连注释一起扫，
    「把坑记下来」就会被判成「又踩了这个坑」——判据宁可窄，不可宽。
    """
    return "\n".join(ln for ln in text.splitlines()
                      if not ln.lstrip().startswith("#"))


def test_推送元数据从spec读工作流不许挂上一条片子的默认值():
    """**对阵和比分本来就在 spec 里**，标题没有理由让人再打一遍。

    海报的两个名字读 `cover.versus.names`，比分读 `cover.result`——而工作流
    一直让人在 `--matchup "黄泽林 vs 布鲁克斯比" --score "6-1 7-5"` 里把同样
    两件事再敲一遍。这就是 `column_of` 那条注释讲的「栏目只有一个出处」，
    在这两项上一直没做。

    两处写的代价不是抽象的：这几个输入的默认值挂的是**上一条片子的**
    （`伊埃拉 vs 郑钦文`、`郑钦文首轮出局`），漏传一项就拿另一场球的标题把
    这条片子发出去——而微信那条消息发出去就收不回来。

    还有一层，复制页和微信正文现在分在两次 run 里跑，
    `wait_for_copy_page(expect=title)` 要求两次算出**同一句标题**：
    从 spec 读必然相同，靠人两次都敲对不必然。

    判据是「算出来的标题和已经发出去的那句一模一样」，不是「代码里有那个函数」
    ——查源码文本的断言只能防「有人把它删了」，防不住「它从来没工作过」。
    """
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    # 两条已发的片子，一条 VS 版式一条 solo，标题要原样重现
    for slug, outdir, want in (
        ("wong-brooksby", "output/2026-07-31/reel/wong-brooksby",
         "7.31 赛场之上 | 黄泽林首进ATP四强"),
        ("hewitt-washington", "output/2026-07-31/reel/hewitt-washington",
         "7.31 网球有故事 | 休伊特之子做了那个动作"),
    ):
        copy_path = Path(f"specs/reels/{slug}.xhs.txt")
        meta = push_reel.push_meta(copy_path)
        got = push_reel.headline(Path(outdir), push_reel.column_of(copy_path),
                                 meta["matchup"], meta["score"], meta["event"],
                                 meta["summary"])
        assert got == want, f"{slug} 从 spec 算出来的标题是「{got}」，发出去的是「{want}」"

    # 没写 push 块的老 spec 也要能算出对阵——它是从 cover 来的，不靠新字段
    old = push_reel.push_meta(Path("specs/reels/wong-lehecka.xhs.txt"))
    assert old["matchup"] == "黄泽林 vs 莱赫奇卡" and old["score"] == "1-6 6-3 6-4"

    # 工作流的默认值不许再是某条具体片子的内容。
    # **只看 YAML 的值，不看注释**——注释里正要讲这些值当年错在哪儿，
    # 连注释一起扫会把「记下这个坑」判成「又踩了这个坑」。
    # ⚠️ **只看 `default:` 那一行的值。** 拦的是「默认值是上一条片子的内容」，
    # 而 `description:` 里正要举例说明该填什么（`如「2:1」`）——连描述一起扫，
    # 「教人怎么填」会被判成「又挂了个默认值」。判据宁可窄，不可宽。
    inputs = _yaml_only(WORKFLOW.read_text(encoding="utf-8").split("permissions:")[0])
    defaults = [ln for ln in inputs.splitlines() if ln.strip().startswith("default:")]
    assert defaults, "扫不到任何 default:，判据失效了"
    for stale in ("伊埃拉 vs 郑钦文", "郑钦文首轮出局", "2:1"):
        assert not any(stale in ln for ln in defaults), (
            f"工作流输入的默认值里还挂着「{stale}」——那是上一条片子的内容，"
            "漏传一次就拿另一场球的标题发出去")


def test_快速预览的开关要在工作流里够得着():
    """**`--cover-only` 落地了，但工作流的 `mode` 里没有它，等于零。**

    源片只在 runner 上活过几分钟（沙箱下不动 YouTube），所以「能用的那台机器
    上没有开关，有开关的那台机器上没有源片」。又一次「写了不等于跑过」，
    只是这次卡在工作流入口而不是函数里。

    封面是全流程返工最多的那一屏：spec 注释里 wong-brooksby 记着
    `0.32/0.40 → 0.33/0.42 → 0.34/0.44` 三档、hewitt 记着 0.60/0.67/0.74，
    每一档在没有这条快路之前都要付一趟完整 render。

    判据两头都要钉：**入口够得着**（options 里有 cover），
    **而且那条路真的短**（不跑分段/TTS/推送）——只钉前者的话，
    有人把 cover 那一步写成完整 render 也照样绿。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    head, jobs = body.split("\njobs:", 1)

    assert "cover" in head[head.index("options:"):head.index("options:") + 80], (
        "mode 的 options 里没有 cover——`--cover-only` 在唯一能用的那台机器上"
        "够不着")

    # `_steps` 给的是步骤**名**，这儿要的是步骤**体**，所以另切一次
    blocks = re.split(r"\n(?=      - (?:name|uses):)", jobs)
    # 认**步骤名**，不是「条件里提到 cover」——装依赖那几步现在也放行 cover，
    # 按条件筛会一次筛出五个。判据宁可窄，不可宽。
    cover_steps = [b for b in blocks if b.startswith("      - name: cover")]
    assert len(cover_steps) == 1, f"cover 模式的步骤有 {len(cover_steps)} 个"
    step = cover_steps[0]
    assert "--cover-only" in step, "cover 那一步没传 --cover-only，那就是完整 render"
    for heavy in ("push_reel.py", "--voice", "--rate"):
        assert heavy not in step, (
            f"cover 那一步还在做 {heavy}——它只该下源片、出海报、退出")

    # 推送那一步不许被 cover 模式触发：海报不是成片
    push_steps = [b for b in blocks
                  if "push_reel.py" in b and "--stage page" not in b]
    assert push_steps, "找不到推送那一步，判据失效了"
    for block in push_steps:
        assert "mode == 'push'" in block, (
            "推送 POST 没钉死在 push-only 上——cover 不能发，render 只负责"
            "质检落库并另派轻量发布任务")

    # ⚠️ **「入口够得着」和「路够短」都对，它还是会红**——这一版就是这么栽的
    # （run 155）：封面走 HTML 渲染 + 抠图，要 Chromium、中文字体、rembg 模型，
    # 而这三步当时都钉在 `mode == 'render'` 上，cover 一个都拿不到。下载花了
    # 五十秒，然后死在渲染那一刻。**「加新能力就要同时改三处」的第 N 次。**
    #
    # 所以第三头：这条路要用的东西，它自己得拿得到。
    for dep in ("装中文字体", "缓存抠图模型", "缓存 Chromium", "装 Chromium"):
        blk = next(b for b in blocks if b.startswith(f"      - name: {dep}"))
        assert "'cover'" in blk, (
            f"「{dep}」没放行 cover——封面是 HTML 渲染 + 抠图，这一样都不能少，"
            "而它会在下完源片之后才死")


def test_死球时刻要趁源片还在的时候量出来(tmp_path, capsys):
    """`find_point_ends.py` 一直是**零调用方**——而段尾切错今天已经改过三处。

    `git grep find_point_ends` 只有三处：脚本自己、一条「文件在不在」的断言、
    以及 wong-brooksby 的 `_editing_why`（那三处修正
    `128.0→132.7`、`143.0→147.7`、`173.0` 正好切在赛点那一分中间）。
    **没有任何工作流或代码调用它**，而它的 `--video` 指的是源片——源片渲完
    就被清理那一步删掉，想用它得自己另下一份 400 MB。于是每一处段尾错都要
    先付一趟渲染才发现，而账号所有者点名过这件事（「很多球没有播放完成就切
    到下一个了……让人看的不明不白的」）。

    现在 probe 顺手量一遍写进 `probe.json`（**趁源片还在**）。判据要钉三头：

    1. 记分条位置**没法自动认**，不给就跳过——但要**说为什么**
    2. 给了就真的量得出来
    3. 零命中要**自证是真空**：把实测分布打出来，别让「门槛卡错 / box 框错」
       和「真的没有死球」长得一样（成片那条「找球场对称轴」就是这么栽的）
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    pytest.importorskip("cv2", reason="visualqa extra")
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了"

    # ① 不给就跳过，而且要出声
    assert reel.point_end_candidates(tmp_path / "nope.mp4", "") == []
    assert "跳过" in capsys.readouterr().out

    # 写错格式要报错，不许当成「没给」悄悄跳过
    with pytest.raises(reel.ReelError, match="x0,y0,x1,y1"):
        reel.point_end_candidates(tmp_path / "nope.mp4", "1,2,3")

    # 造一段 8 秒的片子：左上角那一格每 2 秒翻一次「牌」（黑↔白），
    # 其余画面一直不动。翻牌 = 死球。
    flip = tmp_path / "flip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=gray:s=320x240:r=25:d=8",
         "-vf", "drawbox=x=0:y=0:w=80:h=60:color=black:t=fill:"
                "enable='lt(mod(t,4),2)'",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         str(flip)], check=True)

    # ② 框住那一格 → 量得出跳变
    hits = reel.point_end_candidates(flip, "0,0,80,60")
    assert hits, "翻牌那一格量不出跳变，通路是断的"

    # ③ 框住一直不动的地方 → 零命中，而且把分布打出来自证
    capsys.readouterr()
    quiet = reel.point_end_candidates(flip, "200,150,300,230")
    assert quiet == [], f"不动的区域居然量出 {quiet}"
    out = capsys.readouterr().out
    assert "一个都没有" in out and "moved 最大的几个" in out, (
        f"零命中没有自证是真空，只说了「没有」：{out}")
    assert "box 框错" in out, "零命中要提示可能是 box 框错，不是没有死球"

    # ④ 而且这条路要在工作流里够得着——和 `--cover-only` 那次一样的坑：
    # 源片只在 runner 上活过几分钟，开关够不着就等于这条能力不存在
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    head, jobs = body.split("\njobs:", 1)
    assert "scorebox:" in head, "工作流没有 scorebox 这个输入"
    assert "--scorebox" in jobs, "probe 那一步没把 scorebox 传下去"


def test_查成片的那个脚本要真的被调用一次():
    """**`check_reel_landed.py` 写好了，一次都没跑过。**

    `grep -rn check_reel_landed .github/` 零命中。而补跑一遍九条已发的成片，
    它自己就把今天查出来的两个真缺陷全报了出来：

        「音轨 X，比画面短 N 秒」× 7 条   ← 闪避少了 apad
        「封面之后还有 38 秒是数字静音」   ← wong-brooksby 的哑源片

    也就是说这两个缺陷本来在发出去之前就该被拦下，只是**没人调它**。
    工具自己的 docstring 写着「只在成功时出声的检查，没法证明它真的看过」
    ——一个从来没被调用的检查比那还弱一档。

    位置要**排在提交之前**：提交进 main 之后 `push-reel` 就会把它发到微信，
    而微信那条消息发出去收不回来。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    jobs = body.split("\njobs:", 1)[1]
    assert "check_reel_landed.py" in jobs, (
        "没有任何一步调用 check_reel_landed.py——它就是个没人跑的脚本")

    names = _steps(jobs)
    check = next(i for i, n in enumerate(names) if "查成片本身" in n)
    render = next(i for i, n in enumerate(names) if "render — 出成片" in n)
    commit = next(i for i, n in enumerate(names) if "提交产物" in n)
    assert render < check < commit, (
        f"检查排在第 {check} 步，而 render 在 {render}、提交在 {commit}——"
        "它必须排在渲完之后、提交之前")


def test_拿不到封面时长时片长那一项要跳过不要报假红():
    """**一条常年红的检查等于没有检查**，而且它会把真问题淹掉。

    `COVER_SECONDS` 一路从 2.6 改到 1.8 再到 1.2，而老片子是按 2.6 渲的。
    读不到 `render.json` 时退回今天这个常量，于是**八条老片子全报**
    「画面 X（spec 算出来 Y）」，差值几乎恒定在 1.40~1.44s——而两条带
    `render.json` 的一条都不中。那批假红里混着的「音轨比画面短」正是今天
    查出来的那个真缺陷，差点被一起当成噪音。

    改法不是调常量（下次再改还会错），是**拿不到就不判这一项**，
    并且下游要用封面长度的地方**从产物自己量**（画面总长 − 段落总长）。
    """
    check = Path("tools/check_reel_landed.py").read_text(encoding="utf-8")
    assert "return None" in check, "读不到 render.json 时还在退回常量硬判"
    assert "片长这一项不判" in check, "跳过了却不说，和「判了但判错」分不开"
    # 其余各项不许跟着一起跳过——它们不依赖封面时长
    for keep in ("分辨率", "音轨", "数字静音"):
        assert keep in check, f"{keep} 这一项没了"


def test_源片没有现场声要出声不能默默出一条哑片(tmp_path):
    """`_has_audio` 只查**流存不存在**，查不出「有流但是数字静音」。

    wong-brooksby 就栽在这儿：spec 的 `_source` 白纸黑字写着「带原声」，而成片
    里**没有旁白的段落全是数字静音**——按 3 秒一格采样，29 个窗里 12 个低于
    −70 dB，其余八条片子是 0/23~0/39。整套 `sidechaincompress` 闪避对它空转，
    **而两条分支都不打印**，「源片是哑的」和「源片正常」在日志上一模一样。

    这和「补位的静音盖住真音轨」是同一个形状，只是这次补位的不是我们，
    是源片自己。所以判据要量**信号**，不是量**流**——而且必须**真造两个文件
    量一遍**：`_has_audio` 对哑轨返回的是 True，查源码是查不出这个差别的。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    def _ff(*args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)

    loud, silent, mute = (tmp_path / n for n in
                          ("loud.mp4", "silent.mp4", "mute.mp4"))
    common = ("-f", "lavfi", "-i", "testsrc2=size=160x120:rate=25:duration=3")
    _ff(*common, "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(loud))
    # **有音频流，但整条是数字静音**——就是 wong-brooksby 那一种
    _ff(*common, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-t", "3", str(silent))
    _ff(*common, "-c:v", "libx264", "-preset", "ultrafast", "-an", str(mute))

    # ① `_has_audio` 分不出前两个——这正是为什么要另量一次
    assert reel._has_audio(loud) and reel._has_audio(silent), (
        "造出来的样本不对：两个都该有音频流")
    assert not reel._has_audio(mute)

    # ② 量信号就分得出
    peak = reel.audio_peak_db(loud)
    assert peak is not None and peak > reel.SILENT_PEAK_DB, f"有声的量成 {peak}"
    quiet = reel.audio_peak_db(silent)
    assert quiet is not None and quiet < reel.SILENT_PEAK_DB, (
        f"数字静音量成 {quiet} dBFS，没落在门槛下面")
    assert reel.audio_peak_db(mute) is None, "没有音频流该返回 None"

    # ③ 门槛要留够余量：真实比赛音轨峰值贴近 0，别把录得轻的源片误伤
    assert reel.SILENT_PEAK_DB <= -40, "门槛太靠近正常音量了，会误伤"

    # ⚠️ 这道闸不许拦住「只出封面」那条快路：封面一个音频样本都不碰，
    # 拿「源片是哑的」去拦一次快速预览，等于把这条路的用处废掉。
    # 和 `_preflight_cutout` 那次同一个错——别把无关的检查塞进它前面。
    body = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    render_body = body[body.index("\ndef render("):]
    assert render_body.index("if cover_only:") < \
        render_body.index("require_live_sound(source, spec)"), (
        "原声那道闸排在「只出封面」之前——封面不碰音频，这一拦就把快速预览废了")

    # ④ 闸本身：哑的要报错并**说出路**，认领过的放行，有声的一路畅通
    import pytest  # noqa: PLC0415

    reel.require_live_sound(loud, {})  # 有声：不该拦
    for bad in (silent, mute):
        with pytest.raises(reel.ReelError) as caught:
            reel.require_live_sound(bad, {})
        # **报错要说出路，不能只说不行**
        for way in ("source_audio", "silent_source", "换一个带声音的源片"):
            assert way in str(caught.value), f"报错没给出路 {way}：{caught.value}"
        reel.require_live_sound(bad, {"silent_source": "屏录，本来就没有声道"})


def test_渲完的成片不许因为清理那一步失败而整趟丢掉():
    """`if:` 里不含状态函数时，GitHub 会**隐式和上 `success()`**。

    「丢掉不进仓库的中间物」末尾有个体积兜底会 `exit 1`（连着栽过四次，最近
    一次是多源之后源片改名 `source_r1.mp4`，run 30603686748）。那一刻**成片
    已经渲完了**，可上传和提交都被跳过——六分钟整趟作废，只能重跑。

    判据两头都要钉：

    - 上传要带 `always()`，否则前面一红它就不跑
    - 而且**位置不许往前挪**：清理那一步先 `rm` 再做体积检查，所以走到上传
      时源片已经删干净了。挪到清理之前，392 MB 的源片会一起传上去——
      「修好」的方向反了一样是坏的
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    jobs = body.split("\njobs:", 1)[1]
    blocks = re.split(r"\n(?=      - (?:name|uses):)", jobs)

    upload = [b for b in blocks if "actions/upload-artifact" in b]
    assert len(upload) == 1, f"上传 artifact 的步骤有 {len(upload)} 个"
    assert "always()" in upload[0], (
        "上传 artifact 没带 always()——清理那一步的体积兜底一 exit 1，"
        "渲完的成片就既不上传也不提交，整趟白跑")

    names = _steps(jobs)
    clean = next(i for i, n in enumerate(names) if "丢掉不进仓库的中间物" in n)
    up = next(i for i, n in enumerate(names) if "上传 artifact" in n)
    assert clean < up, (
        "上传排在清理之前——那会把 392 MB 的源片一起传上去")


def test_现场声不许在最后一句话结束时断掉(tmp_path):
    """**九条已发的成片里七条，结尾 2~4.5 秒完全没有声音。**

    `sidechaincompress` 在 **sidechain 输入结束的那一刻就收口**，于是 `[duck]`
    只活到最后一句旁白说完，下游 `amix` 跟着收口——整条现场声在那儿断掉：

        eala-fernandez −4.50s   wang-pareja −2.98s   hewitt-washington −2.97s
        wang-samsonova −2.66s   potapova-venus −2.64s
        wong-brooksby  −1.98s   eala-zheng     −1.95s

    削掉的正是握手、庆祝、观众声——CLAUDE.md 里「收尾那句要提前起、跨进末屏」
    保的就是这几秒，也就是整条片子的情绪落点。**而 ffmpeg 不报错**，画面是
    全长的，成片时长看着完全正常。

    **判据必须真跑一次混音**：造一段 20 秒有声画面 + 一句 7 秒就说完的旁白，
    拿**生产用的那个滤镜图**（`duck_filtergraph`）过一遍 ffmpeg，然后
    ① 音轨要跟画面一样长 ② 旁白结束之后那几秒要**真的有声音**（不是 apad
    补出来的数字静音）。查源码里有没有 `apad` 是拦不住这个的——
    「写了」不等于「跑过」。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    # 缺 ffmpeg 要红，不许 skip——一条常年跳过的检查和常年红是同一个毛病。
    # CI 的 apt 那一步装了它（和 match-reel 同一个包）。
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    def _ff(*args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)

    def _dur(path, stream):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(path)],
            check=True, capture_output=True, text=True).stdout.strip()
        return float(out) if out else 0.0

    bed, voice, mixed = (tmp_path / n for n in
                         ("bed.mp4", "voice.m4a", "mixed.m4a"))
    # 20 秒画面 + 20 秒现场声；旁白 7 秒就说完
    _ff("-f", "lavfi", "-i", "testsrc2=size=320x240:rate=25:duration=20",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=20",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
        "-shortest", str(bed))
    _ff("-f", "lavfi", "-i", "sine=frequency=800:duration=7",
        "-c:a", "aac", str(voice))

    _ff("-i", str(bed), "-i", str(voice), "-filter_complex",
        reel.duck_filtergraph(["[1:a]adelay=0|0[v0]"], ["[v0]"]),
        "-map", "0:v:0", "-map", "[out]", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", reel.AUDIO_RATE,
        "-shortest", str(mixed))

    # ① 音轨要跟画面一样长
    video, audio = _dur(mixed, "v:0"), _dur(mixed, "a:0")
    assert abs(video - audio) < 0.3, (
        f"音轨 {audio:.2f}s 比画面 {video:.2f}s 短了 {video - audio:.2f}s"
        "——现场声在最后一句旁白结束时就断了")

    # ② 旁白之后那几秒要真的有声音，不是 apad 补出来的数字静音。
    # 只验「音轨够长」是不够的：补一段静音同样能让 ① 通过。
    for at in (8, 15):
        chunk = tmp_path / f"at{at}.wav"
        _ff("-i", str(mixed), "-ss", str(at), "-t", "1", "-vn",
            "-c:a", "pcm_s16le", str(chunk))
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(chunk), "-af", "volumedetect",
             "-f", "null", os.devnull], capture_output=True, text=True).stderr
        found = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
        assert found, f"量不出 t={at}s 的响度：{out[-300:]}"
        level = float(found.group(1))
        assert level > -60, (
            f"t={at}s（旁白早就说完了）响度 {level} dB——那是数字静音，"
            "现场声并没有放回来")


def _published_reels() -> list[Path]:
    """仓库里已发的成片目录——**CI 上是空的，这是正常的**。

    `ci.yml` 的稀疏检出从来不含 `output/`（一 GB 多的公开产物存档），所以任何
    读产物的测试在 CI 上都会拿到空列表。**空列表不等于「没有成片」**，
    它等于「这台机器没把产物拉下来」——两者长得一模一样，正是这个仓库反复
    踩的那个坑，我 2026-08-01 又踩了一次（run 30707236335：`只校到 0 条`）。

    所以读产物的断言一律**当加餐**：核心判据必须只吃 `specs/`，在 CI 上真的
    跑起来；产物在的时候（本地沙箱）再多验一层。写成 `skip` 是不行的——
    一条常年跳过的检查和常年红是同一个毛病。
    """
    return sorted(Path("output").glob("*/reel/*"))


def test_成片链接发之前要自己探一次(monkeypatch):
    """**那个 ▶ 按钮是这条推送的全部，而它从来没有被校验过。**

    `pushplus.wait_for_images` 只校 `<img>` 和 **jsDelivr 域名**的 `<a>`
    （`jsdelivr_link_sources`）。而成片超过 20 MB 就退回
    `raw.githubusercontent.com`——仓库里十条成片 28~54 MB，**十条全超**。
    也就是说那条 jsDelivr 分支在真实数据上一次都没走到过，成片链接等于裸奔。
    又一次「兜底出事的时候不吭声」。

    复制页取不到时只摘按钮、正文照发；**成片取不到必须整条不发**——文案没了
    还有正文，片子没了这条推送就没有内容了。

    判据分三层，缺一层都可能变成假绿：
    1. 存量成片确实全都超 20 MB（否则「从来没校验过」这句话不成立）
    2. `wait_for_images` 拿到推送正文时，成片那条链接确实不在它的清单里
    3. 探不到就 `SystemExit`，探得到就放行
    """
    import pytest  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    from tennislive.publish.pushplus import jsdelivr_link_sources  # noqa: PLC0415

    # ① 超过 20 MB 的成片一律退回 raw——这是「校验从来没生效过」的前提。
    # 拿一个稀疏文件量，不依赖 `output/`（CI 上它不在，见 `_published_reels`）。
    import tempfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        big = Path(tmp) / "x.mp4"
        big.touch()
        os.truncate(big, push_reel.JSDELIVR_MAX_BYTES + 1)
        url = push_reel.video_url(big.parent, big.name)
    assert url.startswith("https://raw.githubusercontent.com/"), url

    # 产物在的时候（本地沙箱）再验一层：**存量十条真的一条都没进 jsDelivr**
    reels = [p / f"{p.name}.mp4" for p in _published_reels()]
    reels = [p for p in reels if p.is_file()]
    if reels:
        small = [p for p in reels
                 if p.stat().st_size <= push_reel.JSDELIVR_MAX_BYTES]
        assert not small, (
            "有成片能走 jsDelivr 了——那 `wait_for_images` 对它是管用的，"
            f"这条测试的前提要重写：{[p.name for p in small]}")

    # ② 推送正文里那条成片链接，`wait_for_images` 看不见
    body = push_reel.build_html(url, "https://example.invalid/copy.html",
                                "", "标题\n\n正文", "", "赛场之上")
    assert url not in jsdelivr_link_sources(body), (
        "成片链接居然进了 jsDelivr 清单——这条测试的前提要重写")

    # ③ 探不到就整条不发，探得到就放行
    class _Resp:
        def __init__(self, code):
            self.status_code = code

        def close(self):
            pass

    monkeypatch.setattr(push_reel.time, "sleep", lambda *_: None)
    monkeypatch.setattr(push_reel.requests, "get", lambda *a, **k: _Resp(404))
    with pytest.raises(SystemExit, match="取不到"):
        push_reel.wait_for_video(url, attempts=2, delay=0)
    monkeypatch.setattr(push_reel.requests, "get", lambda *a, **k: _Resp(206))
    push_reel.wait_for_video(url, attempts=1, delay=0)

    # ④ 而且这道闸要真的装在发送那一步上，不是写了个函数没人调
    source = Path("tools/push_reel.py").read_text(encoding="utf-8")
    # 锚点跟着代码走：走 Release 的片子链接来自 render.json，这一行现在是
    # `url = released or video_url(...)`。锚字符串写死过一次，改代码就红——
    # 那不是「测试拦住了 bug」，是测试自己在挡路。取最短的稳定前缀。
    stage = source[source.index("url = released or video_url("):]
    assert stage.index("wait_for_video(") < stage.index("push(title"), (
        "wait_for_video 没排在 push 之前——「写了」不等于「跑过」")


def _poster_name_order(cover: dict, names: list) -> list:
    """海报的赛果那一行**实际印出来**的名字顺序。

    不是读 `winner` 再自己推一遍——那样两边会用同一个假设，一起错。
    直接调 `versus_poster._result_block`（渲海报走的就是它），把标签剥掉，
    按名字在文本里出现的先后排。新写法（`winner` + `result`）和老写法
    （一整句 `score`）都走得通，因为量的是**印出来的那句**。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415

    text = re.sub(r"<[^>]+>", "", versus_poster._result_block(cover, names))
    seen = [(text.index(n), n) for n in names if n in text]
    return [n for _, n in sorted(seen)]


def test_solo封面的对阵名字也要能算出来():
    """2026-08-04 起「赛场之上」一律 solo，而 solo **没有 `versus`**。

    `push_meta` 原来只从 `cover.versus.names` 取两个名字。不跟着改的话，
    solo 那批 spec 的 `matchup` 会是**空字符串，而且不报错**——有 `summary`
    的时候 `headline` 根本不看 matchup，于是它会一直「正常」，直到哪条 spec
    忘了写 summary 才现形（CLAUDE.md 记着这个坑：退路一空，标题当场变成
    `8.2 赛场之上 | `）。

    所以判据要**把 summary 拿掉**再看——留着 summary 测，这条恒绿。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    meta = push_reel.push_meta(Path("specs/reels/zhang-putintseva.xhs.txt"))
    assert meta["matchup"] == "张帅 vs 普汀塞娃", (
        f"solo 封面算不出对阵：{meta['matchup']!r}——"
        "`push_meta` 只认 versus.names 的话，这里会是空的")
    # **赢家在前。** `matchup` 是版式顺序，`winner` 才是赛果顺序。
    title = push_reel.headline(Path("output/x/reel/zhang-putintseva"), "赛场之上",
                               meta["matchup"], meta["score"], meta["event"],
                               "", "2026-08-04")
    assert title.index("张帅") < title.index("6-4") < title.index("普汀塞娃"), (
        f"退路里的赛果顺序反了：{title}——"
        "比分夹在两个名字中间，顺序错就是在声称输的那个人赢了")


def test_标题里的赛果顺序要和海报印的一样():
    """**海报说谁赢，标题就得说谁赢。**

    `versus.names` 是**版式顺序**（上格/下格），不是赛果顺序。海报的赛果行按
    `cover.winner` 排（`versus_poster._result_block`：`loser = 另一个名字`），
    而 `headline` 把比分插在两个名字中间——这个栏目的规矩是**赢家在前**。
    两边各读各的，就会在同一条推送里说反：

    - `wang-samsonova`：`names[0]` 是王欣瑜，`winner` 是萨姆索诺娃。
      海报印「萨姆索诺娃 6-2 6-2 王欣瑜」，标题算出来是「王欣瑜 vs 萨姆索诺娃」
    - `eala-zheng` / `nishikori-shang`（老写法，只有一整句 `cover.score`）：
      海报印「伊埃拉 4-6 6-4 6-1 郑钦文」，标题算出来是「郑钦文 vs 伊埃拉」
      ——**比分整个丢了，而且赢家写反了**

    而微信那条消息发出去就收不回来。
    """
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    checked = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") or {}
        names = [str(n).strip() for n in
                 ((cover.get("versus") or {}).get("names") or []) if str(n).strip()]
        printed = _poster_name_order(cover, names)
        if len(printed) < 2:  # solo 版式、或这条片子的封面不印赛果
            continue
        matchup = push_reel.push_meta(path.parent / f"{path.stem}.xhs.txt")["matchup"]
        assert matchup == " vs ".join(printed), (
            f"{path.stem}：海报印的是「{' '.join(printed)}」，"
            f"标题算出来是「{matchup}」——同一条推送里两种赛果")
        checked += 1
    # **判据自己也要有判据**：主语没了要出声，别变成一条恒真的绿灯。
    assert checked >= 7, f"只校到 {checked} 条印赛果的 spec，判据失效了"


def test_每条spec都算得出一句过得了闸的标题():
    """**每条 spec 都要能算出标题，而且当场就过闸**——不能等到重推那一刻才炸。

    `headline` 有两道闸（末尾那格 13 字、整句 20 字位）。缺 `push.summary` 时
    它退回「对阵 + 比分」，而那一句往往更长：`萨姆索诺娃 6-2 6-2 王欣瑜`
    加上日期和栏目是 20.5 字位，顶破闸门直接 `SystemExit`。也就是说
    **一条没写 summary 的 spec，重推时是在 runner 上才报错的**。

    这条测试只吃 `specs/`，所以它在 CI 上真的跑得起来（见 `_published_reels`：
    `output/` 从来不在 CI 的稀疏检出里）。产物在的时候再多验一层：
    算出来的那一句要和**已经发出去的那一句**逐字相同。

    比的是每个 slug **最新的那一份**：`nishikori-shang` 在 7.28 发过一版
    30 字位的长标题（那时标题闸还不存在），7.29 重发时已经收成了短的。
    拿被顶替掉的那一版当判据，等于要求今天的代码去重现一个已经改掉的错。
    """
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    # ① 只吃 spec：每条都算得出、都过得了闸。日期随便给一个合法的目录名——
    # 闸门量的是整句宽度，而日期那一格所有片子都一样宽。
    # ⚠️ **只校写了 `push` 块的那些。** 后来新增的 spec 走的是「工作流传参」
    # 那条路（`resolve_meta` 里命令行覆盖 spec），标题由 `push=true 必须自己
    # 填标题` 那道守卫兜着。把它们一起要求「从 spec 就能算出标题」，等于给
    # 另一条合法的路判红——判据宁可窄，不可宽。
    titles: dict[str, str] = {}
    for path in sorted(Path("specs/reels").glob("*.json")):
        if not (json.loads(path.read_text(encoding="utf-8")).get("push") or {}):
            continue
        copy_path = path.parent / f"{path.stem}.xhs.txt"
        meta = push_reel.push_meta(copy_path)
        titles[path.stem] = push_reel.headline(
            Path("output/2026-07-31/reel") / path.stem,
            push_reel.column_of(copy_path), meta["matchup"], meta["score"],
            meta["event"], meta["summary"])
    assert len(titles) >= 9, f"只校到 {len(titles)} 条 spec，判据失效了"

    # ② 产物在的时候（本地沙箱）再验一层：和已经发出去的那句逐字相同
    latest: dict[str, Path] = {}
    for outdir in _published_reels():
        if (outdir / "copy.html").is_file():
            latest[outdir.name] = outdir  # 按日期升序，留最后一份
    for slug, outdir in sorted(latest.items()):
        copy_path = Path(f"specs/reels/{slug}.xhs.txt")
        if not copy_path.is_file():  # 已停产的片子，spec 不在了
            continue
        want = re.search(r'<textarea id="title"[^>]*>(.*?)</textarea>',
                         (outdir / "copy.html").read_text(encoding="utf-8"),
                         re.DOTALL).group(1).strip()
        meta = push_reel.push_meta(copy_path)
        got = push_reel.headline(outdir, push_reel.column_of(copy_path),
                                 meta["matchup"], meta["score"], meta["event"],
                                 meta["summary"])
        assert got == want, (
            f"{slug}：从 spec 算出来的是「{got}」，已经发出去的是「{want}」")


def test_写错的push字段要报错不许悄悄不生效():
    """`sumary` 写漏一个 m，标题就悄悄退回「对阵 + 比分」——而那和「这条片子
    本来就没写 summary」长得一模一样。**兜底出事的时候不吭声**是这个仓库
    反复踩的那个坑，所以认不出来的字段一律报错。

    `_` 开头的是写给下一个人的备注（仓库里到处都是 `_why`），不算字段。
    """
    import pytest  # noqa: PLC0415

    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    import tempfile  # noqa: PLC0415

    # 存量 spec 里的 push 块都得认得出来，每条都要真跑一遍
    for path in sorted(Path("specs/reels").glob("*.json")):
        push_reel.push_meta(path.parent / f"{path.stem}.xhs.txt")

    def _meta_for(push_block):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "x.json").write_text(json.dumps(
                {"cover": {"eyebrow": "赛场之上",
                           "versus": {"names": ["甲", "乙"]}},
                 "push": push_block}, ensure_ascii=False), encoding="utf-8")
            (root / "x.xhs.txt").write_text("标题\n\n正文", encoding="utf-8")
            return push_reel.push_meta(root / "x.xhs.txt")

    with pytest.raises(SystemExit, match="认不出来的字段"):
        _meta_for({"sumary": "打错了"})
    # 备注不算字段，也不能被当成值灌进去
    assert _meta_for({"_why": "写给下一个人的", "summary": "对的"})["summary"] == "对的"



def test_checkout不许把整个output拉下来():
    """HEAD 上 `output/` 就有 1.36 GB，checkout 因此每次要 1 分 35 秒到
    2 分 44 秒（run 30622667742 / 30624808733）——而渲染一个字节都用不到
    别人的成片。

    稀疏检出把它挡在外面，剩下的全部加起来 161 MB。本次的 outdir 由
    「算出目录」那一步 `git sparse-checkout add` 进来（新目录没有历史 blob
    要下；重渲已有的片子才取它自己那几十 MB）。**两半都要在**：只写
    `sparse-checkout` 不 add，`git add "$OUTDIR"` 会被判在稀疏范围之外。

    ⚠️ 排除的只有 `output`。assets 155 MB 看着也不小，但它是渲染真要读的
    东西——少一个就是第 5 分钟才炸的 FileNotFoundError。
    """
    for path in (WORKFLOW,):
        text = path.read_text(encoding="utf-8")
        head = text[:text.index("actions/setup-python@v5")]
        assert "sparse-checkout:" in head, f"{path.name} 的 checkout 没做稀疏检出"
        listed = head[head.index("sparse-checkout:"):]
        assert "\n            output\n" not in listed, (
            f"{path.name} 把整个 output/ 列进了稀疏范围，1.36 GB 又要下一遍")
        assert "git sparse-checkout add" in text, (
            f"{path.name} 没把本次的 outdir 加进稀疏范围，git add 会被判在范围之外")

    # 渲染要读的那几个目录一个都不能少
    text = WORKFLOW.read_text(encoding="utf-8")
    listed = text[text.index("sparse-checkout:"):text.index("- uses: actions/setup-python")]
    for needed in ("assets", "data", "specs", "src", "tools"):
        assert f"\n            {needed}\n" in listed, (
            f"稀疏检出漏了 {needed}/——渲染读它，少了就是第 5 分钟才炸")


def test_中间段的编码参数要往快里调不是往省比特里调():
    """**中间产物要花的是比特，不是时间。**

    分段和封面拼完之后整片还要以 `slow`/`crf 18` 重编一次，所以中间段省下来的
    比特一点用都没有——它唯一的作用是别把画质提前丢掉。preset 决定编码器花
    多少**时间**去找省比特的编法，crf 决定留多少**画质**，两件事各管各的：
    preset 推到最快、crf 压到很低，就是又快又更保真。

    量出来的（10 秒 1080×1440/60fps 素材，四核）：

        medium   / crf 20   14.73s   最终 SSIM 0.993110 / PSNR 47.09  ← 改前
        ultrafast/ crf 12    2.92s   最终 SSIM 0.993212 / PSNR 48.01  ← 改后

    **5 倍快，而且最终成片比改前更接近源片。** 这条测试拦的不是手滑，是下一次
    有人照着「preset 越慢画质越好」的直觉，把它改回 medium/slow——那会把
    runner 上的分段编码从 ~47s 拉回 176.7s，换来一个更差的成片。

    成片那一步（`FINAL_*`）不在这条的管辖范围，那儿由
    `test_成片的编码参数不许为了压体积往下调` 守着。
    """
    reel = _reel()
    fast = ("ultrafast", "superfast", "veryfast")
    assert reel.PART_PRESET in fast, (
        f"中间段 preset 被改成了 {reel.PART_PRESET}。它是马上要被重编的临时文件，"
        "在这儿花时间找省比特的编法是白花——量过：medium 慢 5 倍，成片还更差。")
    assert int(reel.PART_CRF) <= 14, (
        f"中间段 crf 被推到了 {reel.PART_CRF}。快 preset + 高 crf 是两头都丢："
        "既没省时间，又把画质提前丢在一个临时文件里。")
    # 成片那一步不许被中间段连累着一起推到快档
    # （原来这儿写死 `== "slow"`；2026-08-14 成片 preset 按实测换成了 `medium`，
    #  所以这条只钉它该钉的那件事：**成片没有被拖进中间段那一档**。crf 照旧钉死。）
    assert reel.FINAL_CRF == "18", (
        "改中间段不许连累成片——省时间要从中间产物上省，不能从交出去的那一份上省")
    assert reel.FINAL_PRESET in _FINAL_PRESET_OK, (
        f"成片 preset 跟着中间段一起跑到了 {reel.FINAL_PRESET}。中间段马上要被"
        "重编，成片是交出去的那一份，两者的账完全不同——量过：那一档的成片"
        "同样 crf 18 反而更小，也就是画质掉了")


def _checkout_block(text: str) -> str | None:
    """切出 `- uses: actions/checkout` 那一步（含它的 `with:`）。

    **不用 PyYAML。** 这个文件里其他扫工作流的判据（`_steps`、`_yaml_only`）
    一直是按文本切的，而 yaml 不是这个仓库的依赖——为一条断言加一个运行时
    依赖，代价比收益大。第一版真加了 `import yaml`，沙箱里装着、CI 里没有，
    于是 CI 红：**又一次「本地装着不等于 CI 装着」**（run 30648727062）。
    """
    # **先去掉整行注释。** 注释里正写着「原来这儿写着 `fetch-depth: 0`」，
    # 连注释一起扫会把「把坑记下来」判成「又踩了这个坑」——同一个错这一天
    # 犯了三次（工作流输入的旧默认值、push-reel 里的 ffmpeg、这里）。
    lines = _yaml_only(text).splitlines()
    for i, line in enumerate(lines):
        if line.startswith("      - uses:") and "checkout" in line:
            block = [line]
            for nxt in lines[i + 1:]:
                if nxt.startswith("      - "):
                    break
                block.append(nxt)
            return "\n".join(block)
    return None


def test_不碰产物的工作流不许把output拉下来():
    """HEAD 上 `output/` 就有 1.36 GB，checkout 因此每次要一分半上下
    （daily 量到 1:31，match-reel 2:44）——**而多数工作流一个字节都不碰它**。

    这条按「这条工作流碰不碰 `output/`」自动分类，不维护白名单：

    - **提都不提的**：必须稀疏检出，且不需要 `sparse-checkout add`
    - **要写产物的**：稀疏之后得把自己那一格 add 回来，那是每条各自的活，
      这条只要求「要么两半都有，要么老老实实全量」——**半个是最坏的情况**，
      `git add` 会说路径在稀疏范围之外，而那是在跑完之后才炸

    顺带钉住 `fetch-depth`：`0` 是把 1.77 GiB 的完整历史全拉下来。
    `player-name-sync` 原来就是这样，而它唯一的 git 读操作是
    `git diff -- <被跟踪的文件>`——工作区对 HEAD，一条历史都不需要。
    """
    workflows = sorted(Path(".github/workflows").glob("*.yml"))
    assert workflows, "找不到工作流"
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        block = _checkout_block(text)
        if block is None:
            continue
        sparse = "sparse-checkout:" in block

        # **唯一的豁免：archive-media.yml**（2026-08-13 加的媒体归档线）。
        # 它的业务就是 `git filter-repo` 重写整个历史——浅克隆重写不了没拉
        # 下来的那半截；而且它只有手动 dispatch 一个入口、是一次性操作，
        # 不在任何定时/出片路径上，慢的 checkout 不压在关键路径上。
        # 豁免按文件名点名，只这一条：下一条要拉全史的工作流，先把理由写成
        # 自己的豁免，不许搭这趟车。
        if path.name != "archive-media.yml":
            assert not re.search(r"fetch-depth:\s*0\b", block), (
                f"{path.name} 用 fetch-depth: 0，会把 1.77 GiB 的完整历史拉下来。"
                "确认真的需要历史再加回来——`git diff -- <文件>` 和提交推送都不需要。")

        # 三处收窄，全是「判据宁可窄，不可宽」当场踩出来的：
        # 1. 连注释一起扫——注释里正写着「别把 output/ 拉下来」，于是被判成
        #    「写产物」，然后要求它 add 一个它根本不写的目录
        # 2. 按整份文本扫——`ci.yml` 的 `paths-ignore: output/**` 是**触发
        #    条件**，不是产物路径。只看 `jobs:` 以后
        # 3. 裸的 `"output/" in body`——`probe.yml` 写的是 **`probe-output/`**，
        #    从中间匹配上了。要词边界
        body = _yaml_only(text)
        body = body[body.index("\njobs:"):] if "\njobs:" in body else body
        writes_output = re.search(r"(?<![\w-])output/", body) is not None

        if not writes_output:
            assert sparse, (
                f"{path.name} 一个字节都不碰 output/，却做了全量 checkout——"
                "白等一分半。照 assets.yml 那段加稀疏检出。")
            assert "git sparse-checkout add" not in body, (
                f"{path.name} 不写产物，不该 add 任何 output 目录")
        elif sparse:
            # 把产物那一格弄进 cone 有两种写法，都算数：
            # - 目录要按日期／slug 算 → `git sparse-checkout add "$OUT_DIR"`
            # - 目录是固定的（`output/voice-samples`）→ 直接列进 sparse-checkout
            # `/?` 是给**非 cone 模式**留的：那儿写的是 gitignore 语义的
            # pattern（`/output/interviews/`），带前导斜杠。ci.yml 2026-08-05
            # 换了过去——`output/interviews` 331 MB 里 328 MB 是从不打开的 mp4，
            # 而 cone 模式挑不掉后缀。少了这个 `/?`，那条工作流会被判成
            # 「没把自己那一格弄进 cone」，而它其实弄进去了。
            listed_statically = re.search(
                r"\n\s+/?output/\S+", block[block.index("sparse-checkout:"):])
            assert "git sparse-checkout add" in body or listed_statically, (
                f"{path.name} 做了稀疏检出却没把自己那一格弄进 cone——"
                "`git add` 只会警告并退出 0，产物静默丢掉，而那是跑完之后才发现。")

        # 排除的必须只有 output：assets 155 MB 看着也不小，但渲染真要读它
        if sparse:
            listed = block[block.index("sparse-checkout:"):]
            assert "\n            output\n" not in listed, (
                f"{path.name} 把 output/ 列进了稀疏范围，1.36 GB 又要下一遍")


# pip 包名 → import 名。只列这个仓库真用到的那几个，别去猜没用到的。
_DIST_TO_MODULE = {
    "pillow": "PIL", "opencv-python-headless": "cv2", "yt-dlp": "yt_dlp",
    "gtts": "gtts", "edge-tts": "edge_tts", "imageio-ffmpeg": "imageio_ffmpeg",
    "pypdf": "pypdf", "requests": "requests", "rich": "rich",
    "pytest": "pytest", "ruff": "ruff", "playwright": "playwright",
    "rembg": "rembg", "pyyaml": "yaml",
}


def test_测试里不许import没声明的包():
    """**本地装着不等于 CI 装着。** 沙箱是长期攒出来的环境，runner 每次都是
    干净的——这个文件里一度写了 `import yaml`，沙箱里绿、CI 里
    `ModuleNotFoundError`，整条 PR 红（run 30648727062）。

    判据不是「别 import yaml」（那种写法拦不住下一个包，而且我自己那句
    docstring 就把它误伤了一次）：**扫 AST 里真正的 import 语句**，每个
    顶层模块名必须是标准库、`pyproject` 声明过的依赖、或者本仓库自己的模块。

    工作流的判据一律按文本切（`_steps` / `_yaml_only` / `_checkout_block`），
    别为一条断言把 PyYAML 拖进依赖。
    """
    import ast  # noqa: PLC0415
    import sys as _sys  # noqa: PLC0415

    declared = set()
    for line in Path("pyproject.toml").read_text(encoding="utf-8").splitlines():
        for hit in re.findall(r'"([A-Za-z0-9_.\-]+)\s*(?:\[[^\]]*\])?\s*[><=!]', line):
            declared.add(_DIST_TO_MODULE.get(hit.lower(), hit.lower().replace("-", "_")))

    local = {p.stem for p in Path("tools").glob("*.py")}
    local |= {p.stem for p in Path("src/tennislive").glob("*.py")}
    # `tests/` 下的也算本地——`conftest` 就是（`make_match` 那个共用夹具）。
    local |= {p.stem for p in Path("tests").glob("*.py")}
    # `from tools.X import` 是既有写法（test_release_orchestration_claim就在用），
    # CI 上也走得通——包名本身要放行。
    local |= {"tennislive", "tests", "tools"}
    allowed = set(_sys.stdlib_module_names) | declared | local

    tree = ast.parse(Path("tests/test_match_reel.py").read_text(encoding="utf-8"))
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            used |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            used.add(node.module.split(".")[0])

    stray = sorted(used - allowed)
    assert not stray, (
        f"这些包 import 了却没在 pyproject 里声明：{stray}。\n"
        "沙箱里装着不代表 runner 上有——CI 会 ModuleNotFoundError。\n"
        "要么加进 pyproject 的某个 extra，要么换个不用它的写法"
        "（扫工作流按文本切，见 _checkout_block）。")
    # 反过来也验一下：这个判据真的认得出 stdlib 和本地模块，不是恒真
    assert {"json", "pathlib"} <= allowed and "push_reel" in allowed


def test_稀疏检出之后git_add要带sparse():
    """**裸的 `git add output/` 在稀疏模式下只警告、退出码 0。**

    合成仓库上验过：cone 外的路径，`git add output/` 打一句
    "The following paths ... will not be updated in the index"，然后**成功退出**。
    接着 `git diff --cached --quiet` 说「没有变化」，工作流打印「没有新内容」
    正常结束——**这一轮的产物就这么静默丢了**。

    和「兜底出事的时候不吭声」是同一种病，只是这次兜底的是 git 自己。
    所以凡是整棵 `git add output/` 的，必须带 `--sparse`；按目录 add 的
    （`git add "$OUTDIR"`）靠上一条测试保证那一格在 cone 里。
    """
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        if "sparse-checkout:" not in body:
            continue
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped.startswith("git add "):
                continue
            # 只管整棵 output/ 那种；`git add "$OUTDIR"` 由稀疏范围保证
            if re.search(r"git add\s+(--sparse\s+)?output/\s", stripped + " "):
                assert "--sparse" in stripped, (
                    f"{path.name}：`{stripped}` 在稀疏模式下什么也不会暂存，"
                    "而且退出码是 0——产物会静默丢掉。要带 --sparse。")


def test_读产物的步骤不能排在sparse_add前面():
    """**稀疏检出把 `output/` 挡在外面之后，「读它」和「它不存在」长得一模一样。**

    `daily.yml` 的幂等检查（备份班次用）就踩在这上面：它在 checkout 之后立刻
    `[ -f "$OUT_DIR/digest.json" ]` 判断今天是不是已经生成过。目录不在工作区，
    这些判断**全是假**，`CONTENT_READY` 永远 false——幂等检查永远不跳过，
    备份班次会把当天内容重新生成、微信**重复推一遍**。而它不报错，
    看起来只是「今天又跑了一次」。

    所以这条按行号盯顺序：任何读 `$OUT_DIR` / `output/` 的判断，都必须排在
    把它加进稀疏范围之后。判据是行号，不是「有没有」——「只测行为拦不住
    位置错」这一课在复制页那道闸上已经上过一次。
    """
    reads = re.compile(r'\$\{?(OUT_DIR|OUTDIR|RADAR_DIR)\b|(?<![\w-])output/')
    tests = re.compile(r'\[\s*-[fdse]\s|test\s+-[fdse]\s')
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if "sparse-checkout:" not in text:
            continue
        code = [(i, ln) for i, ln in enumerate(text.splitlines())
                if not ln.lstrip().startswith("#")]
        # 固定目录直接列进 cone 的，从第一行起就在范围内
        if any(ln.strip().startswith("output/") for _, ln in code[:45]):
            continue
        add_at = next((i for i, ln in code if "sparse-checkout add" in ln), None)
        if add_at is None:
            continue
        early = [(i + 1, ln.strip()) for i, ln in code
                 if i < add_at and reads.search(ln) and tests.search(ln)]
        assert not early, (
            f"{path.name} 在把产物目录加进稀疏范围之前就去读它了：{early[:2]}\n"
            "目录不在工作区，这些判断全是假的，而且不报错。")


def test_Pages只发复制页不发整个仓库():
    """Pages 发布的内容里**只许有 html**——其余 2.25 GB 一个字节都不该进去。

    量出来的构成（2026-08-03，`output/` 2.26 GB / 2902 个文件）：

        mp4  1367.8 MB (60.6%)   png 480.5 MB (21.3%)   jpg 399.1 MB (17.7%)
        html   0.66 MB (0.03%)  ← Pages 真正要服务的只有这个

    图片和视频走 jsDelivr / raw，Pages 用不到；它们被卷进来只是因为 Pages
    默认发布整个仓库。账单落在推送上——冠军版那条**推送步骤 6 分 44 秒，
    其中 6 分半在等 Pages 重建**，而真正发微信只要几秒。

    这条钉三样：

    1. **只收 html**——收集那一步的 `find` 多选一类，就把那 2.25 GB 搬回去了
    2. **路径原样**（`_site/$f`，不是 `basename`）——URL 就是路径，改一个字符，
       已经发出去的微信链接全死，**而那些消息收不回来**
    3. **一个页面都没收到时必须红**。稀疏模式写错会得到空的 `_site`，而把空站
       部署上去是**清空整站**——它和部署成功在日志上长得一模一样
    """
    path = Path(".github/workflows/pages.yml")
    assert path.exists(), (
        "pages.yml 没了。Pages 会退回「发布整个仓库」，"
        "于是每次推送又要为 2.26 GB 的重建等 6~12 分钟。")
    body = _yaml_only(path.read_text(encoding="utf-8"))

    # ⚠️ 第一版这儿写的是 `... or ".html" in body`——**恒真**（body 里当然有
    # `.html`）。查「收集那一步的 find 到底选了什么」才是真判据。
    picked = re.findall(r"find\s+output\s+-name\s+'([^']+)'", body)
    assert picked == ["*.html"], (
        f"收复制页的 find 必须只选 html，拿到 {picked}——"
        "多选一类就把那 2.25 GB 的一部分搬回 Pages 了")

    assert 'cp "$f" "_site/$f"' in body, (
        "复制页的路径必须原样保留：URL 就是路径，改了等于把已发出去的微信链接弄死。")
    assert "basename" not in body, "拍平目录会改掉 URL"

    assert re.search(r'"\$n" -eq 0', body), (
        "没有「一个页面都没收到就红」的闸。稀疏模式写错会得到空的 _site，"
        "而把空站部署上去是**清空整站**——它和部署成功长得一模一样。")
    assert "touch _site/.nojekyll" in body, (
        "少了 .nojekyll，Jekyll 会逐个文件处理一遍")


def test_日报这条线不许回来():
    """**2026-07-31 账号所有者停掉了日报**：「不要日报了，都说过了，日报的形式
    太落后了，**任务重且没收益没人愿意深入看**」。

    所以 `daily.yml` 整个删掉了，不是停掉定时——我上一版只摘了触发器还回头
    问了一遍知识帖要不要留，被指出「都说过了」。**对方重申过的事就是决定，
    别再拿它去换一次确认。**

    连带删掉的：
    - 三条只为 daily.yml 存在的守卫测试（纪念日告警、封面闸门顺序、失败不吞）
      ——主语没了，留着就是常年红
    - `push-existing.yml` 的 `main` / `knowledge` 两个 scope 和盯
      `output/**/knowledge/**` 的 push 触发——日报停产后没人再产它们

    **没删的**：`tennislive digest` 命令还在（`probe.yml` 拿它做数据源覆盖率
    探测，`--no-cards`），卡片渲染器还在（解说片 / 赛程包 / 知识帖共用）。
    停的是这个栏目，不是底下那套工具。

    要恢复日报，从 git 历史里把 `daily.yml` 取回来，**并且改掉这条测试**——
    让它是一次看得见的决定。
    """
    assert not Path(".github/workflows/daily.yml").exists(), (
        "daily.yml 又回来了。账号所有者 2026-07-31 明确停掉了日报"
        "（「任务重且没收益没人愿意深入看」）——要恢复请连这条测试一起改。")
    # 别再有第二条工作流去产日报那个包（output/<date>/push.html 那一份）
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        assert "tennislive digest" not in body or "--no-cards" in body, (
            f"{path.name} 又在出带卡片图的日报包了——digest 现在只留给 "
            "probe.yml 做覆盖率探测（--no-cards）")



def test_即时赛果推送已经停掉():
    """**2026-07-31：「即时赛果推送也不要了」。**

    内容雷达（`flash.yml`）一天两种产出，各占一个名额：`result` 是刚完赛的
    高价值比赛（即时赛果），`preview` 是赛前焦点。停的**只有前者**——同一句话
    里还有「其他的可以保留」，赛前焦点不是赛果。

    判据落在名额本身而不是工作流：`select_content` 按名额取，`RESULT_DAILY_LIMIT`
    是 0 就一条都取不进去。改回 1 要连这条测试一起改。

    **真调一次，不查源码文本**——「写了」不等于「跑过」。
    """
    from datetime import UTC, datetime  # noqa: PLC0415

    from tennislive.content_ops import (  # noqa: PLC0415
        PREVIEW_DAILY_LIMIT,
        RESULT_DAILY_LIMIT,
        select_content,
    )

    assert RESULT_DAILY_LIMIT == 0, (
        "即时赛果推送又开回来了。账号所有者 2026-07-31 停掉了它——"
        "要恢复请连这条测试一起改。")
    assert PREVIEW_DAILY_LIMIT >= 1, "赛前焦点是「其他的可以保留」那一半，别一起关了"

    # 喂一场刚完赛的重点比赛进去，确认它一条都取不出来。
    # 用 conftest 的 make_match，别自己搓一个——模型改了它会跟着改。
    from datetime import timedelta  # noqa: PLC0415

    from conftest import make_match  # noqa: PLC0415

    from tennislive.render.hotspot import (  # noqa: PLC0415
        HOTSPOT_THRESHOLD,
        hotspot_score,
    )

    from tennislive.timeutil import BEIJING  # noqa: PLC0415

    now = datetime(2026, 7, 31, 20, 0, tzinfo=BEIJING)
    just_finished = make_match(start_utc=now.astimezone(UTC) - timedelta(hours=2))
    # **排名要补上。** `make_match` 的默认值只给了 seed，`hotspot_score` 算出来
    # 是 49，而门槛是 50——差一分。第一版就栽在这儿：把开关拧回 1 重新跑，
    # 这场球**照样一条都选不出来**，于是下面这句断言是恒真的，等于没测。
    # 反向验证救回来的，又一次「断言全绿不等于页面对」。
    just_finished.home[0].rank = 1
    just_finished.away[0].rank = 2
    assert hotspot_score(just_finished) >= HOTSPOT_THRESHOLD, (
        f"这场球只有 {hotspot_score(just_finished)} 分，够不着热点门槛 "
        f"{HOTSPOT_THRESHOLD}——那下面那句断言就白写了")

    picks = select_content([just_finished], now=now, state={})
    assert not [p for p in picks if p.kind == "result"], (
        f"刚完赛的重点比赛还是被选成了即时赛果：{picks}")


def test_今日赛程没有发布出口了():
    """**2026-07-31：「昨日赛果和今日赛程都要拿掉了」。**

    昨日赛果随 `daily.yml` 一起删了。今日赛程（赛程包）的生成器
    （`tennislive schedule` → `output/<date>/schedule`）**没有任何工作流会自动
    跑它**，它唯一的发布出口是 `push-existing.yml` 的 `schedule` scope——
    删掉那个 scope，这个栏目就发不出去了。

    生成器和它那一整套判据（跨日窗口、`NEXT_DAY_CUTOFF_HOUR`、按组轮流收口）
    **故意留着**：那些教训写在 CLAUDE.md 里，代码是它的判据。停的是发布，
    不是把知识铲掉。
    """
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        # GitHub 事件名 schedule 只说明「这条工作流由 cron 触发」，不是已经停掉的
        # 「今日赛程」内容 scope。按裸字符串扫会把任何定时编排工作流误伤。
        body = body.replace('${{ github.event_name }}" = "schedule"', "")
        assert "tennislive schedule" not in body, (
            f"{path.name} 又在自动产今日赛程了")
        assert '/schedule"' not in body and "= \"schedule\"" not in body, (
            f"{path.name} 又给今日赛程开了发布出口")


def test_每日网球知识分出来单独跑():
    """**「所以要分开啊……其他的可以保留」。**

    知识帖一直搭日报的顺风车（同一趟 `tennislive digest`，分两条 PushPlus 推），
    所以我第一版把 daily 整个删掉时，它跟着一起没了。账号所有者纠正的正是这个：
    **要拿掉的是昨日赛果和今日赛程，不是 daily 干的每一件事。**

    分出来几乎不用改代码——`knowledge-adhoc.yml` 跑的就是同一个
    `generate_knowledge_package`，而且本来就支持 slug 留空自动选题。缺的只是
    一个定时。

    ⚠️ **2026-08-11 这条定时被错误地停过一天。** 那天 cincinnati 那条静态卡片
    撞上了「网球有故事视频优先」的新决定，我把**输出形态该改**和**定时该停**
    这两件事合成了一个决定去处理，停掉了定时（PR #282）。账号所有者当场纠正：
    「自动选题的定时任务可以留着啊」——**要淘汰的是「自动选出的题一律渲成
    静态卡片」这个输出形态，不是每天自动选题这件事本身**。两者是两个独立的
    问题，只有前者需要解决（具体怎么解决还没有答案），后者不该被一起停掉。
    这条测试因此断言恢复原样：cron 必须在。
    """
    text = Path(".github/workflows/knowledge-adhoc.yml").read_text(encoding="utf-8")
    body = _yaml_only(text)
    assert "schedule:" in body and "cron:" in body, (
        "knowledge-adhoc 没有定时——每日网球知识就断了")
    cron = re.search(r'cron:\s*"([^"]+)"', body).group(1)
    minute, hour = cron.split()[0], cron.split()[1]
    assert minute not in ("0", "30"), (
        f"定时落在 :{minute}——GitHub 在整点半点最容易延迟或丢弃，"
        "这是 daily 当年留下的经验")
    # 推送那一步不能被定时触发挡住（schedule 事件下 inputs.push 是空的）
    push_block = text[text.index("- name: PushPlus 推送到微信"):]
    assert "inputs.push != 'false'" in push_block, (
        "推送条件改了——定时触发时 inputs.push 是空的，别写成 == 'true'")


def test_查赛果的命令留着卡片和推送不留():
    """**2026-07-31：「可以用命令查赛果，但没必要做卡片图然后推送微信了」。**

    这条把边界划在**产物**上，不是划在功能上：

    | 命令 | 干什么 | 处置 |
    |---|---|---|
    | `today` / `schedule` / `results` / `live` | 终端里列出来给人看 | ✅ 留 |
    | `flash`（即时战报） | 检测热点 → 渲赛果卡 → 推微信 | ❌ 删 |
    | `schedule-cards`（今日赛程卡） | 渲赛程卡 → 写 push.html → 推微信 | ❌ 删 |
    | `publish flash` | 发已提交的热点包 | ❌ 删别名 |

    ⚠️ **`flash-card` 不是赛果卡，别删错。** 它渲的是**场外快讯卡**
    （`render/flashcard.py`，带敏感话题闸门），配的是 `flash-radar` 那条线——
    那条线是「其他的可以保留」里的。我差一点按名字把它一起删了：
    名字里都有 flash，一个是即时战报（赛果），一个是场外快讯（新闻）。

    `cmd_publish_flash` 这个**函数**留着——`publish content`（内容雷达的
    赛前焦点）还在用它，删掉的只是 `flash` 那个 channel 别名。
    """
    from tennislive import cli  # noqa: PLC0415

    for gone in ("cmd_flash", "cmd_schedule_cards"):
        assert not hasattr(cli, gone), (
            f"{gone} 又回来了——它渲卡片并推微信，2026-07-31 停掉了")
    # 查询那几条必须还在
    for keep in ("cmd_today", "cmd_day"):
        assert hasattr(cli, keep), f"{keep} 不见了——「可以用命令查赛果」这半边丢了"
    # 场外快讯那条线一个零件都不许少
    assert hasattr(cli, "cmd_flash_card"), (
        "cmd_flash_card 被删了——它是场外快讯卡，不是赛果卡，属于要保留的那条线")
    from tennislive.render import flashcard  # noqa: PLC0415

    assert hasattr(flashcard, "generate_flash_card")
    # 赛果卡的渲染器该没有了
    from tennislive.render import cards  # noqa: PLC0415

    assert not hasattr(cards, "generate_flash_card"), (
        "赛果卡渲染器又回来了（render.cards.generate_flash_card）")
    # publish content 还得能用
    assert hasattr(cli, "cmd_publish_flash"), (
        "cmd_publish_flash 被连坐删了——publish content（赛前焦点）还在用它")


def test_日报生成器换成了只出覆盖率的命令():
    """**`tennislive digest` 删了，`tennislive coverage` 顶上。**

    `probe.yml` 原来跑 `tennislive digest --no-cards` 只为拿一张
    `coverage.txt`——**为了一张覆盖率报告跑一整套日报**。日报停产之后把这段
    抽成自己的命令：抓一天数据、写一张报告，就这些。

    钉两头：`digest` 不许回来，`coverage` 必须在，而且 probe 那条线要接上。
    """
    from tennislive import cli  # noqa: PLC0415

    assert not hasattr(cli, "cmd_digest"), "日报生成器又回来了"
    assert hasattr(cli, "cmd_coverage"), (
        "覆盖率命令没了——probe.yml 的数据源探测就断了")

    # **真跑一遍，别只断言符号存在。** 第一版就只写了上面那句 hasattr，
    # 而命令本身是坏的：`fetch_day` 给的是 `DailyData`，`coverage_report`
    # 要的是 `Digest`，一上 runner 就 AttributeError（run 30653131605）。
    # 「写了」不等于「跑过」——查符号的断言只能防「有人把它删了」。
    import argparse  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    from datetime import date  # noqa: PLC0415

    from conftest import make_match  # noqa: PLC0415

    import tennislive.digest as digest_mod  # noqa: PLC0415
    from tennislive.digest import Digest  # noqa: PLC0415

    fake = Digest(today=date(2026, 7, 31), results=[make_match()],
                  live=[], schedule=[], source="espn")
    real = digest_mod.build_digest
    digest_mod.build_digest = lambda *a, **k: fake
    try:
        with tempfile.TemporaryDirectory() as tmp:
            rc = cli.cmd_coverage(argparse.Namespace(
                date="2026-07-31", source="auto", outdir=tmp))
            written = Path(tmp) / "2026-07-31" / "coverage.txt"
            assert rc == 0 and written.is_file() and written.read_text(
                encoding="utf-8").strip(), "coverage 命令跑不出报告"
    finally:
        digest_mod.build_digest = real

    probe = _yaml_only(
        Path(".github/workflows/probe.yml").read_text(encoding="utf-8"))
    assert "tennislive coverage" in probe and "tennislive digest" not in probe, (
        "probe.yml 还在用 tennislive digest")


def test_停产栏目的历史产物清掉了活栏目一个不动():
    """**删产物要按栏目分，和停产那次是同一条。**

    我一开始把整个 `output/`（1.33 GB）当成「历史日报产物」报给账号所有者——
    **错得离谱**：日报本体加上它带的知识帖、赛程包、即时战报一共只有 148 MB，
    剩下 1.18 GB 是解说片（576M）、成片（440M）这些**还在用的栏目**，
    而它们的链接挂在**已经发出去的微信消息里**，删了就是把老消息变成死链。

    所以判据钉的是「活栏目还在」，不是「output 变小了」。

    ⚠️ **粒度是「这条线还有没有产物」，不是逐个文件。** 反向验证过：删掉
    reel 的一个 mp4 它不红，把 reel 整个目录拿掉才红。它拦的是「一次清理
    把整条线扫了」，不是手滑删一个文件。
    """
    live = ("reel", "explainer", "queue", "knowledge_adhoc", "flash_radar")
    tracked = subprocess.run(
        ["git", "ls-files", "--", "output"],
        capture_output=True, text=True, check=True).stdout.splitlines()
    for name in live:
        assert any(f"/{name}/" in p for p in tracked), (
            f"output/ 里 {name} 的产物没了——那条线还在用，"
            "链接挂在已发出去的消息里")
    # 停产的四类不许再有。**判据要锚在日期目录正下方**——裸的 `"/cards/" in p`
    # 会把 `output/<date>/queue/<pick>/cards/`（内容雷达自己的卡片，活的）
    # 一起扫进去。同一天第五次「判据扫得太宽」，这次是路径。
    for dead in ("cards", "knowledge", "schedule", "flash", "video"):
        stale = [p for p in tracked
                 if re.match(rf"output/\d{{4}}-\d\d-\d\d/{dead}/", p)]
        assert not stale, f"停产栏目 {dead} 的历史产物还在：{stale[:3]}"
    # 日期目录正下方的散件（wechat.md / xiaohongshu.txt 那些）也该没了
    loose = [p for p in tracked
             if re.match(r"output/\d{4}-\d\d-\d\d/[^/]+$", p)]
    assert not loose, f"日报包的散件还在：{loose[:3]}"


def test_停掉的定时不许自己回来():
    """**2026-08-02：账号所有者「这两个任务停掉吧，不需要了」。**

    停的是**定时**，不是这两条线的代码——`workflow_dispatch` 都留着，
    随时能手动跑一趟。所以这条测试只钉两件事：cron 不许回来、手动入口不许
    一起被摘掉。

    ⚠️ 这条替掉的是 `test_内容雷达的间隔要按发布窗口算`（钉 6 次/天那个
    cron 是不是按 165 分钟的发布窗口算出来的）。**主语没了就得换判据**：
    cron 一删，那条测试的 `re.search(...).group(1)` 当场 `AttributeError`
    ——一条常年红的检查和一条常年跳过的检查是同一个毛病。

    定时归零之后，`preview_candidates` 的窗口只在手动跑的那一趟里起作用，
    不再需要一个间隔去配它。⚠️ 而 2026-08-05 那个窗口从 165 分钟放宽到了
    **48 小时**（「排期出来就决定」），所以「间隔要比窗口窄」这个约束现在
    基本不咬人了。要恢复定时，得连这条测试一起改——那时**按新窗口重算**，
    别照抄当年那行 cron，也别照抄那个 165。
    """
    # ⚠️ `news-radar` 2026-08-05 改名成 `news-brief`（两条推送合成一条）。
    # **改的是内容形态，不是那个「停掉定时」的决定**，所以它照旧受这条管。
    # 手写文件名的名单会在改名当天变成 FileNotFoundError——这个仓库在
    # `test_every_workflow_that_commits_generated_files_has_a_size_gate`
    # 上已经栽过一次，那次的解法是改成自动推导。这儿推导不出来（「哪几条
    # 是被停掉的」不写在文件里），所以名单留着，但改名时必须一起改。
    for name in ("flash", "news-brief"):
        body = _yaml_only(
            Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8"))
        head = body.split("\njobs:")[0]
        assert "schedule:" not in head, (
            f"{name} 的定时又回来了——2026-08-02 账号所有者停掉的")
        assert "workflow_dispatch:" in head, (
            f"{name} 停的是定时，手动入口不能一起摘掉")


def test_没有下游在读的定时任务不许一直跑():
    """**采集了没人读，和空跑是一回事。**

    - `player-name-sync`：六月至今译名表只变过一次，还是人手改的——照旧摘掉定时

    ⚠️ **`oncourt-interviews` 2026-08-18 恢复了定时，这条判据跟着改**：当时停的
    理由是「`data/oncourt_interviews.json` 攒到 4551 条，除了 oncourt 自己那套
    采集工具，没有任何代码 import 它」——那条理由现在是假的。`tools/oncourt_feed.py`
    / `tools/pick_oncourt_clips.py` 都真的读 `data/oncourt_interviews.json`，
    而且分别接在 `interview-auto-render.yml` / `news-brief.yml` /
    `oncourt-interviews.yml` 三条工作流里，不是孤立脚本。「赛后开麦」需要持续
    采集才有新素材，没有定时的话候选永远是空的——这正是当初这条判据自己
    docstring 里写的第二条出路：「先给它找个下游，或者把这条测试一起改」，
    下游已经有了，改的是这条。

    这条测试只剩 `player-name-sync` 那一半——真给它接上下游，或者也把测试改掉，
    别顺手把 cron 加回来又没人管。
    """
    for name in ("player-name-sync",):
        body = _yaml_only(
            Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8"))
        head = body.split("\njobs:")[0]
        assert "schedule:" not in head, (
            f"{name} 又挂上定时了——它的产出没有下游在读（2026-07-31 停的）")
        assert "workflow_dispatch:" in head, f"{name} 的手动入口不能一起摘掉"

    # `oncourt-interviews` 现在**要求**有定时（不是禁止），并且要求下游真的存在。
    body = _yaml_only(
        Path(".github/workflows/oncourt-interviews.yml").read_text(encoding="utf-8"))
    head = body.split("\njobs:")[0]
    assert "schedule:" in head, (
        "oncourt-interviews 没有定时了——「赛后开麦」需要持续采集，缺了定时"
        "候选永远是空的")
    consumers = "\n".join(
        Path(p).read_text(encoding="utf-8")
        for p in ("tools/oncourt_feed.py", "tools/pick_oncourt_clips.py")
    )
    assert "oncourt_interviews.json" in consumers, (
        "oncourt_feed.py / pick_oncourt_clips.py 不再读 oncourt_interviews.json 了"
        "——定时采集又变回没有下游，该重新摘掉")


def test_昨日一分这条线不许回来():
    """**2026-07-31：「昨日一分全功能拿掉」。**

    停之前查过根因，不是频次问题：skip 诊断里十个检索源有五个直接 error
    （全是 YouTube 系，和 match-reel 那条「机房 IP 被挡」同一个病），唯一能
    拿到候选的 Tennis TV 卡在缺 `TENNISTV_JWT`——**11 天 66 趟只出 3 条片**。
    出路是接源不是降频，账号所有者选了整条拿掉。

    删掉的：工作流、`tennislive point` 命令、`video/daily_point.py`（1937 行）、
    `tests/test_daily_point.py`（57 条）、`test_cli` 里三条、历史产物 45 个文件。

    **没删的**：`video/pipeline.py` 的 `render_ass` 和 `subtitle_text.py`——
    视频本地化那条线还在用。停的是栏目，不是底下那套工具。
    """
    assert not Path(".github/workflows/yesterday-point.yml").exists()
    assert not Path("src/tennislive/video/daily_point.py").exists()
    assert not Path("tests/test_daily_point.py").exists()

    from tennislive import cli  # noqa: PLC0415

    assert not hasattr(cli, "cmd_yesterday_point"), "昨日一分的命令又回来了"

    # 共用的字幕/ASS 那套要还在——视频本地化靠它
    from tennislive.video import pipeline  # noqa: PLC0415
    from tennislive.video.subtitle_text import drop_punctuation  # noqa: PLC0415

    assert hasattr(pipeline, "render_ass") and callable(drop_punctuation), (
        "把共用的字幕工具一起删了——视频本地化那条线还在用")

    # 历史产物也清了
    tracked = subprocess.run(["git", "ls-files", "--", "output"],
                             capture_output=True, text=True, check=True).stdout
    assert "yesterday-point" not in tracked, "昨日一分的历史产物还在"




def test_海报的裁切中间物一个都不许进仓库():
    """`versus_poster.py` 把裁切/抠图/淡出的中间物**存在原图旁边**
    （`image.with_suffix(...)`），而原图在 `assets/players/` 里是被跟踪的
    ——中间物只要没被 gitignore 挡住，就会跟着一起被 `git add` 进仓库。

    **判据自己推导，不维护名单。** `.gitignore` 原来手写着 `.crop.jpg` 和
    `.crop.png`，而同一条链上的第三个 `_fade_cut_sides` 存的是
    `X.crop.png` → `X.crop.faded.png`，`*.crop.png` 匹配不上它，于是两张
    中间物躺在 `assets/players/` 里等着被提交。逐个列名字挡不住下一个——
    和 outdir 里 `source*` 那个坑连栽四次是同一个形状。

    所以这条扫源码里真正的 `with_suffix("...")`，每个图片后缀都必须被
    `.gitignore` 挡住。**加一个新的中间物后缀就会红**，逼你同时改 gitignore。
    """
    src = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    suffixes = set(re.findall(r'with_suffix\(\s*"(\.[a-z.]+)"\s*\)', src))
    images = {s for s in suffixes if s.endswith((".png", ".jpg", ".jpeg"))}
    assert images, "没扫到任何图片中间物，判据失效了"

    ignored = [ln.strip() for ln in Path(".gitignore").read_text(encoding="utf-8")
               .splitlines() if ln.strip() and not ln.startswith("#")]
    for suffix in sorted(images):
        assert f"*{suffix}" in ignored, (
            f"`with_suffix(\"{suffix}\")` 存的中间物落在原图旁边，"
            f"而 .gitignore 里没有 `*{suffix}`——它会跟着 assets/ 一起进仓库")

    # 反过来：这些中间物此刻真的一个都不在索引里
    tracked = subprocess.run(["git", "ls-files"], capture_output=True,
                             text=True, check=True).stdout
    for suffix in sorted(images):
        stray = [ln for ln in tracked.splitlines() if ln.endswith(suffix)]
        assert not stray, f"仓库里已经有 {suffix} 的中间物：{stray[:3]}"


def test_spec形状校验排在下载之前():
    """**今天返工的直接来源：错误发现得太晚。**

    `parse_segments` 原来在第 1543 行，而下载源片在第 1516 行——可它只用
    `sources` 的**键**去校验段落引用（`{s.source} - set(sources)`），一个下载
    下来的文件都不碰。于是段落字段写错、`inset.corner` 写错、缺字段、贴图路径
    不存在这四类错，每一类都要先付一次 392 MB 的下载才报出来。

    eala-fernandez 今天渲了 3 轮、wang-samsonova 2 轮；最近 30 趟 match-reel
    合计 211 分钟。**「渲到一半才发现」变成「第 5 秒报错」是这条线上最便宜的
    一笔改动。**

    这条盯**位置**：`validate_spec` 和 `_preflight_cutout` 都必须排在下载之前。
    「只测行为拦不住位置错」——复制页那道闸上已经上过这一课。
    """
    reel = _reel()
    src = Path(reel.__file__).read_text(encoding="utf-8")
    body = src[src.index("def render("):]
    body = body[:body.index("\ndef ", 1)]

    validate_at = body.index("validate_spec(spec)")
    preflight_at = body.index("_preflight_cutout(spec)")
    download_at = body.index("download(url, path, archival=")
    assert validate_at < download_at, "spec 形状校验排到下载后面了"
    assert preflight_at < download_at, "缺依赖的预检排到下载后面了"

    # 形状校验里**不许**混进环境检查——否则本地想 dry-run 一下 spec，
    # 得先装 176 MB 的抠图模型
    shape = src[src.index("def validate_spec("):]
    shape = shape[:shape.index("\ndef ", 1)]
    assert "_preflight_cutout" not in shape.split('"""')[-1], (
        "validate_spec 里混进了环境检查——那是「这台机器行不行」，"
        "不是「这份 spec 对不对」")


def test_dry_run要拿probe查选段(tmp_path):
    """选段的机械判据全在 probe.json 里躺着，而 dry-run 原来不看它。

    代价是量过的：wong-brooksby 那三处段尾修正**每一处都先付了一趟渲染才
    发现**；郑钦文那条三处跨镜头**渲染一次都没报错**，直接发了出去。
    又一次「工具写出来了、判据算出来了，就是没人在该用的时候用它」——
    `point_ends` 在这之前是**零消费者**。

    ⚠️ **按源片 URL 认领 probe，不按 slug 或日期。** 同一条 spec 会跨多个
    日期目录重跑，而 probe.json 自己记着它探的是哪条 URL——那才是内容身份。
    按 slug 认会在换了源片地址之后静静命中**别的片子**的切点，而那不报错。
    """
    reel = _reel()
    spec = {
        "slug": "t", "source_url": "https://x.invalid/a.mp4",
        "segments": [{"start": 10.0, "end": 20.0, "narration": "一句话"}],
    }
    probe = {"url": "https://x.invalid/a.mp4", "duration": 30.0,
             "scene_cuts": [15.0], "point_ends": []}
    other = {"url": "https://x.invalid/OTHER.mp4", "duration": 30.0,
             "scene_cuts": [11.0, 12.0, 13.0], "point_ends": []}

    def _probes(_spec):
        return {probe["url"]: probe}, []

    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(reel, "probes_for_spec", _probes)
        segs = reel.parse_segments(spec, {"": Path("x")}, "")
        buf = io.StringIO()
        with redirect_stdout(buf):
            hard = reel.probe_dry_run(spec, segs)
        out = buf.getvalue()
        assert hard is False, "跨切点不是硬闸——它会把一批已发的好 spec 挡在门外"
        assert "15.00s 换了镜头" in out, f"没报出中途换镜头：{out}"

        # **写过源片末尾才是硬的**：ffmpeg 越界不报错，只给一段短的，
        # 而后面每一句旁白和字幕都跟着整体错位。
        long_spec = {**spec, "segments": [
            {"start": 10.0, "end": 44.0, "narration": "一句话"}]}
        segs = reel.parse_segments(long_spec, {"": Path("x")}, "")
        buf = io.StringIO()
        with redirect_stdout(buf):
            assert reel.probe_dry_run(long_spec, segs) is True
        # ⚠️ 断言里那个 **14.18** 不是随手写的：段尾 44.0 + `SEG_FADE` 0.18
        # 减去源片的 30.0。**它同时钉住了「dry-run 把溶解底料算进去了」**——
        # 少算那 0.18 秒的话这儿会印 14.00，而那正是 run 680 白跑一趟的原因
        # （dry-run 报「没有硬伤」，render 到了 runner 上才红）。
        assert "第 1 段" in buf.getvalue()
        assert "超出 14.18s" in buf.getvalue(), \
            f"没把溶解底料算进去，或者根本没报：{buf.getvalue()}"

        # **一份都没认领上要出声**——空结果先自证是真空。
        monkey.setattr(reel, "probes_for_spec", lambda _s: ({}, [""]))
        buf = io.StringIO()
        with redirect_stdout(buf):
            reel.probe_dry_run(spec, segs)
        assert "都没认领上" in buf.getvalue(), "没 probe 却和「全都合格」长得一样"
    finally:
        monkey.undo()

    # 认领必须按 URL：喂一份**别的 URL** 的 probe，不许拿它的切点来判
    assert reel.probes_for_spec({"source_url": other["url"]})[0].keys() != {
        probe["url"]}, "按 URL 认领的口径不对"


def test_源片分辨率不到1080p要硬拦():
    """账号所有者 2026-08-18：「视频一定要选 1080p 及以上的清晰度，如果没有
    的话就等」——这是这个仓库里说得最重的一条门槛，`probe.json` 从探测那一刻
    起就记着 `height`，可这条闸一直没写：`--dry-run` 对 720p 的源片一声不吭。

    只查 `segments` 真正引用到的源，别碰封面（`cover_photo_problem` 管的是
    另一件事——官方高清实拍 vs 抽帧，和源片分辨率无关）。
    """
    reel = _reel()
    spec = {
        "slug": "t", "source_url": "https://x.invalid/720p.mp4",
        "segments": [{"start": 10.0, "end": 20.0, "narration": "一句话"}],
        "cover": {"portrait": {"image": "assets/x.jpg"}},
    }
    low = {"url": spec["source_url"], "width": 1280, "height": 720,
           "duration": 30.0, "scene_cuts": [], "point_ends": []}

    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(reel, "probes_for_spec", lambda _s: ({low["url"]: low}, []))
        segs = reel.parse_segments(spec, {"": Path("x")}, "")
        buf = io.StringIO()
        with redirect_stdout(buf):
            hard = reel.probe_dry_run(spec, segs)
        out = buf.getvalue()
        assert hard is True, f"720p 源片没被拦下：{out}"
        assert "1280x720" in out and "低于 1080p" in out, f"没报出分辨率：{out}"

        # 反面锚点：1080p 和 4K 都要放行，缺 height 字段也不许误报
        for height, expect_hard in ((1080, False), (2160, False)):
            hi = {**low, "height": height}
            monkey.setattr(reel, "probes_for_spec", lambda _s, hi=hi: ({hi["url"]: hi}, []))
            buf = io.StringIO()
            with redirect_stdout(buf):
                got = reel.probe_dry_run(spec, segs)
            assert got is expect_hard, f"{height}p 判错了：{buf.getvalue()}"

        no_height = {k: v for k, v in low.items() if k != "height"}
        monkey.setattr(reel, "probes_for_spec",
                        lambda _s, nh=no_height: ({nh["url"]: nh}, []))
        buf = io.StringIO()
        with redirect_stdout(buf):
            got = reel.probe_dry_run(spec, segs)
        assert got is False, f"没探到分辨率不该被当成不合格：{buf.getvalue()}"
    finally:
        monkey.undo()


def test_没量过死球的源片要把猜到的候选翻出来提醒(tmp_path):
    """`point_ends` 空着有两种成因，长得一模一样：**没给** `--scorebox`，
    或者给了但记分条检出真的是空的。`bouzkova-jovic` 那条是前一种——
    `suggest_scorebox()` 猜到了候选（`--scorebox 90,870,416,980`），只印在
    probe 那趟 run 的日志里，没人再翻，`--dry-run` 对这一层完全不吭声。

    账号所有者 2026-08-19：「剪辑的时候要等死球了再去切下一段视频，切记」——
    这条把猜到的候选存进 `probe.json`（`scorebox_guess`），`--dry-run` 翻出来
    当提醒。⚠️ **仍然只报不拦**：`--scorebox` 给了也可能因为记分条滞后／
    镜头切走而检出为空，做成硬闸会重复 `crosses_cut` 那次的错
    （见 `probe_dry_run` 的 docstring）。
    """
    reel = _reel()
    spec = {
        "slug": "t", "source_url": "https://x.invalid/a.mp4",
        "segments": [{"start": 10.0, "end": 20.0, "narration": "一句话"}],
    }
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415

    def _run(point_ends, scorebox_guess):
        probe = {"url": spec["source_url"], "duration": 30.0,
                 "scene_cuts": [], "point_ends": point_ends,
                 "scorebox_guess": scorebox_guess}
        monkey = pytest.MonkeyPatch()
        monkey.setattr(reel, "probes_for_spec", lambda _s: ({probe["url"]: probe}, []))
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                hard = reel.probe_dry_run(spec, segs)
        finally:
            monkey.undo()
        return hard, buf.getvalue()

    # 猜到了候选、没人拿去重跑——要点出那个候选
    hard, out = _run([], "90,870,416,980")
    assert hard is False, "没量过死球不许是硬闸，会把批量存量片子挡在门外"
    assert "90,870,416,980" in out, f"猜到的候选没被翻出来：{out}"
    assert "还没有人拿它重跑" in out, f"没说清这是「猜了没确认」：{out}"

    # 猜不出候选（可能没有常驻记分条）——要说清是这种情况，不是「忘了猜」
    hard, out = _run([], None)
    assert hard is False
    assert "猜不出记分条" in out, f"没区分「猜不出来」和「猜到了没确认」：{out}"

    # **量过、真的有死球数据**——不该再报这条提醒
    hard, out = _run([15.5, 30.2], "90,870,416,980")
    assert hard is False
    assert "还没有人拿它重跑" not in out, f"已经量出数据了，不该还提醒去重跑：{out}"
    assert "猜不出记分条" not in out


def test_suggest_scorebox要把猜到的候选返回不能只打印(monkeypatch, tmp_path):
    """`probe.json` 要存住这个候选，返回值必须是真的——查源码文本防不住
    「函数签名改了返回值，调用点却还按 None 处理」这种半吊子重构。
    """
    reel = _reel()

    class _FakeDetect:
        DARK_FREQ = 0.65
        MIN_FILL = 0.70

        @staticmethod
        def detect(_video):
            return [{"box": (10, 20, 30, 40), "fill": 0.91}]

    monkeypatch.setitem(sys.modules, "detect_scorebox", _FakeDetect)
    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415
    buf = io.StringIO()
    with redirect_stdout(buf):
        guess = reel.suggest_scorebox(tmp_path / "x.mp4")
    assert guess == "10,20,30,40", f"没把猜到的候选原样返回：{guess!r}"

    class _EmptyDetect:
        DARK_FREQ = 0.65
        MIN_FILL = 0.70

        @staticmethod
        def detect(_video):
            return []

    monkeypatch.setitem(sys.modules, "detect_scorebox", _EmptyDetect)
    assert reel.suggest_scorebox(tmp_path / "x.mp4") is None, \
        "猜不出候选时必须返回 None，不能返回一个假值"


def test_窗口对齐源片镜头边界不算中途换镜头():
    """⚠️ **这个容差是量出来的，不是拍的。**

    20 条已发 spec、72 处未声明的跨切点，按「离最近那条边界多远」排开是
    0.01 / 0.02×4 / 0.03 / 0.04×3 / 0.05 / 0.07 / 0.08 / 0.10 / 0.12，
    然后跳到 0.16。前面那一簇是 0~3 帧（25 fps 一帧 0.04s）——那正是
    CLAUDE.md 说该做的事：「窗口本来就该切在源片自己的镜头边界上」。

    不滤掉它们的话，报告里一半是噪音，而**人会为了压掉噪音去写
    `crosses_cut`，顺手把真检查一起关掉**。
    """
    reel = _reel()
    assert 0.12 < reel.CUT_EDGE_TOL < 0.16, (
        f"容差 {reel.CUT_EDGE_TOL} 不在量出来的那道缝里（0.12~0.16）")

    spec = {"slug": "t", "source_url": "u",
            "segments": [{"start": 10.0, "end": 20.0, "narration": "话"}]}
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415

    def _run(cuts):
        monkey = pytest.MonkeyPatch()
        monkey.setattr(reel, "probes_for_spec", lambda _s: (
            {"u": {"url": "u", "duration": 99.0, "scene_cuts": cuts,
                   "point_ends": []}}, []))
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                reel.probe_dry_run(spec, segs)
        finally:
            monkey.undo()
        return buf.getvalue()

    assert "换了镜头" not in _run([10.02, 19.98]), "贴着边界的切点被当成中途换镜头"
    assert "换了镜头" in _run([15.0]), "真的中途换镜头没报出来"


def test_溶解底料跨切点不会被错报成源片没查成():
    """`segments_straddling_cuts` 返回 `(straddling, unchecked, tail_cuts)`，
    而 `probe_dry_run` 里调它的那行一度写成
    `straddling, tail_cuts, unchecked = segments_straddling_cuts(...)`——
    第二、三个返回值被换了位置。probe 认领成功时真正的 `unchecked` 恒为
    `[]`，所以这个调换不会崩，只会把 `tail_cuts`（一堆「溶解底料跨了切点」
    的 dict）错扣上「⚠️ 这几条源片的切点没查成」的帽子，吓人但不假死——
    正是「判据自己也要有判据」防的那类：调用方的解包顺序，函数自己的
    返回值签名管不住。

    造一个只在**溶解底料**（`SEG_FADE=0.18s`）里蹭到切点、段体本身没跨
    的段：`end=20.0`，切点在 `20.05`。
    """
    reel = _reel()
    spec = {"slug": "t", "source_url": "u",
            "segments": [{"start": 10.0, "end": 20.0, "narration": "一句话"},
                         {"start": 25.0, "end": 30.0, "narration": "另一句"}]}
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    import io  # noqa: PLC0415
    from contextlib import redirect_stdout  # noqa: PLC0415

    monkey = pytest.MonkeyPatch()
    try:
        monkey.setattr(reel, "probes_for_spec", lambda _s: (
            {"u": {"url": "u", "duration": 99.0, "scene_cuts": [20.05],
                   "point_ends": []}}, []))
        buf = io.StringIO()
        with redirect_stdout(buf):
            hard = reel.probe_dry_run(spec, segs)
        out = buf.getvalue()
    finally:
        monkey.undo()

    assert hard is False
    assert "溶解底料跨了切点" in out, f"该报的没报：{out}"
    assert "没查成" not in out, f"probe 明明认领上了，不许报成没查成：{out}"


def test_dry_run秒级返回且一个字节都不下载(tmp_path):
    """**真跑一遍**，喂一个绝对下不动的 URL——它必须照样成功返回。

    这是「写了不等于跑过」：断言 `--dry-run` 这个开关存在，证明不了它没去下载。
    所以给一个 `http://0.0.0.0/nope.mp4`，能秒回就说明它真的没碰网络。
    """
    import json as _json
    import subprocess as _sp
    import sys as _sys
    import time as _time

    # ⚠️ **底稿要挑一条今天还渲得出来的。** 原来用的是 `wong-lehecka`，而
    # 「赛场之上 solo 封面必须有 `cover.scoreboard`」这条规矩（#368）是在它发出去
    # 之后才立的——底稿一旦过不了形状闸，这条测试量的就不再是「dry-run 快不快」，
    # 而是「底稿旧不旧」。后来换的 `boisson-krueger` 又早于结局冷开场声明闸，
    # 同样不再能当干净底稿。蒂亚福这条已经显式声明并完整重放结局。
    spec = _json.loads(
        Path("specs/reels/tiafoe-musetti-cincinnati-2026-qf.json").read_text(
            encoding="utf-8"))
    spec["source_url"] = "http://0.0.0.0/绝对下不动.mp4"
    # 临时文件用底稿自己的 slug 命名：措辞豁免按 slug 查（spec_wording），
    # 这条底稿挂着「7点05分」的账，换名克隆就丢豁免、dry-run 会红在措辞上
    path = tmp_path / "tiafoe-musetti-cincinnati-2026-qf.json"
    path.write_text(_json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    outdir = tmp_path / "out"

    started = _time.perf_counter()
    proc = _sp.run(
        [_sys.executable, "tools/build_match_reel.py", "render",
         "--spec", str(path), "--outdir", str(outdir), "--dry-run"],
        capture_output=True, text=True, timeout=60)
    elapsed = _time.perf_counter() - started

    assert proc.returncode == 0, f"dry-run 失败了：{proc.stderr[-400:]}"
    assert "spec 形状没问题" in proc.stdout, proc.stdout
    assert elapsed < 20, f"dry-run 花了 {elapsed:.1f}s——它不该碰网络"
    assert not outdir.exists(), "dry-run 建了 outdir——它什么都不该产"


def test_cover_only排在分段和TTS之前():
    """封面是全流程返工最多的那一屏（CLAUDE.md 里 68 行、10 个专门段落，
    每段都是一轮返工换来的），而它在完整 render 里**第 63 秒就完成了**，
    却要等满 6 分钟才看得见——run 30624808733 的时间线：
    10:52:54 开跑 → 10:53:57 封面编码完 → 11:00:15 成片。

    `build_cover` 不依赖 segments / tracks / TTS / voice（查过，一个都不用），
    所以「下载 → 出海报 → 退出」是干净的一条路。本地实测 4.3 秒，
    渲出来的海报打开看过：台头、双抠图、VS 牌、中文名、钩子、比分、级别牌全对。

    这条盯**位置**：早退必须排在 `parse_segments` 和 TTS 之前，否则那些活白干。
    """
    reel = _reel()
    src = Path(reel.__file__).read_text(encoding="utf-8")
    body = src[src.index("def render("):]
    body = body[:body.index("\ndef ", 1)]

    early_return = body.index("if cover_only:")
    for later, why in (("parse_segments(spec", "分段解析"),
                       ("synth_cover(", "封面 TTS"),
                       ("cut_segment(", "分段编码")):
        assert early_return < body.index(later), (
            f"cover_only 的早退排在了{why}后面——那些活白干了")
    assert "cover_only: bool = False" in src, "render 没有 cover_only 参数"
    assert '"--cover-only"' in src, "命令行没有 --cover-only"


def test_同一个提交不许跑两趟CI():
    """`push`（不限分支）＋ `pull_request` ＝ 开着 PR 的分支每推一次起**两趟**。

    量出来的（2026-08-05 那半小时）：run 2338/2339、2335/2336、2333/2334…
    成对出现，创建时刻只差 3 秒，每趟 4 分 10 秒，跑的是同一个 commit。

    两趟并行，所以它吃的不是墙钟而是**并发位**——而并发位被自己占满时，
    排在后面的 `match-reel` 就要排队，那才吃墙钟。

    ⚠️ **main 上的 CI 不许被掐**：那儿每个提交都要有自己的一趟绿，
    掐掉等于让一个从没跑过测试的提交留在主干上，而且不吭声。
    """
    ci = (WORKFLOW.parent / "ci.yml").read_text(encoding="utf-8")
    head = ci[:ci.index("jobs:")]
    push = head[head.index("push:"):head.index("pull_request:")]
    assert "branches:" in push and "main" in push, (
        "`push` 没收在 main 上——分支上每推一次仍然会跑两趟一样的 CI")
    assert "concurrency:" in head, "没有 concurrency，旧的那趟不会被掐掉"
    group = head[head.index("concurrency:"):]
    assert "cancel-in-progress" in group
    assert "main" in group.split("cancel-in-progress", 1)[1], (
        "main 上的 CI 也会被掐——一个没跑过测试的提交会留在主干上")


def _excluded_modes(step: str) -> set[str]:
    """这一步的 `if:` 把哪几个 mode 排除在外。"""
    head = step.split("run:", 1)[0]
    return set(re.findall(r"inputs\.mode\s*!=\s*'([a-z-]+)'", head))


def test_装Chromium不许没有超时和重试():
    """`playwright install --with-deps` 里的 `--with-deps` **会跑 apt**。

    而这个仓库的 apt 会抽风——CLAUDE.md 里记着「一次静静烧了 13 分 42 秒」。
    那条教训当时只套在显式的 `apt-get` 步骤上，**漏了这一处**：八条工作流都调
    它，没有一条设超时或重试，于是任何一条都能一路烧到 job 的预算用完。
    run 30973785219 就是这么死的——卡在这一步 13 分钟，其余步骤全在 1 分钟内
    跑完，而日志上一个字都没说。

    两头都要：**超时**（不然它能烧到 job 预算见底），**加一次重试**
    （CLAUDE.md：「硬超时只把『静静烧半小时』换成『红掉、要人重跑』——
    方向对了但停在一半」）。

    ⚠️ 超时的数**别调小**：正常 5~60 秒，但第一版 apt 重试写 3×100 秒当场把
    CI 弄红了，因为 apt 一直在推进、只是慢。**把「慢」误判成「挂死」，
    重试就从救场变成三倍的浪费。**
    """
    checked = {}
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if not ln.lstrip().startswith("#")]
        for i, ln in enumerate(lines):
            if "playwright install" not in ln:
                continue
            timed = re.search(r"timeout\s+(\d+)\s+python -m playwright install", ln)
            assert timed, (
                f"{path.name} 第 {i + 1} 行装 Chromium 没有超时——"
                f"apt 一抽风它就烧到 job 预算见底：{ln.strip()}")
            assert int(timed.group(1)) >= 180, (
                f"{path.name} 的超时只有 {timed.group(1)} 秒，太紧。"
                "正常 5~60 秒，但 apt 慢起来会被误判成挂死——"
                "重试于是从救场变成三倍的浪费")
            back = "\n".join(lines[max(0, i - 12):i])
            assert re.search(r"for\s+i\s+in\s+1\s+2", back), (
                f"{path.name} 装 Chromium 有超时但没有重试——"
                "卡住的正确处置是换一次重试，不是整趟失败")
            checked[path.name] = True
    assert len(checked) >= 6, (
        f"只扫到 {len(checked)} 条工作流装 Chromium，判据的主语像是没了")


def test_装Chromium重试之前要等dpkg锁():
    """⚠️ **第一次超时会毒死第二次**，所以「重试」原来根本没重试成。

    `timeout` 杀掉的是 `playwright install` 那层壳，**它派生的 apt-get 活着**
    并攥着 `/var/lib/dpkg/lock-frontend`。run 31003290962 的日志一清二楚：

        12:01:21  装 Chromium 第 1 次没跑完        ← 240 秒被杀
        12:01:36  E: Could not get lock ... held by process 4285 (apt-get)
        12:01:53  装 Chromium 两次都没成功         ← 第 2 次只活了 2 秒

    也就是说那次 `sleep 15` 之后的重试是**必然失败**的，而它看起来和
    「apt 真的挂了」一模一样。上一条判据（超时 + 重试）当时是绿的——
    **两头都装了，中间那一环是空的。**

    所以这条钉的是：重试之前必须**等锁真的松开**，不许拿 `sleep` 猜。

    ⚠️ 判据**自己推导，不维护白名单**：凡是有那个重试循环的工作流都算。
    """
    checked = {}
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if not ln.lstrip().startswith("#")]
        body = "\n".join(lines)
        if "playwright install" not in body:
            continue
        checked[path.name] = True
        assert "pgrep -x apt-get" in body and "pgrep -x dpkg" in body, (
            f"{path.name} 装 Chromium 的重试没有等 dpkg 锁——"
            "第一次超时留下的 apt-get 会把第二次两秒钟毒死")
        # 循环体里不许只剩一个裸 sleep 当等待手段
        loop = body.split("装 Chromium 第", 1)
        assert len(loop) > 1, f"{path.name} 找不到那条重试的告警行"
        after = loop[1].split("done", 1)[0]
        assert "pw_wait_apt" in after, (
            f"{path.name} 重试之间没调等锁那一步（拿 sleep 猜等于没等）")
    assert len(checked) >= 6, (
        f"只扫到 {len(checked)} 条工作流装 Chromium，判据的主语像是没了")


def test_等dpkg锁的预算够长又不许撑爆步骤预算():
    """⚠️ **等 60 秒不够。** 2026-08-06 run 31058902174：

        00:15:55  装 Chromium 开跑（--with-deps 去下 21 MB 字体包）
        00:17:39  fonts-freefont-ttf 5.6 MB —— 一个包花了 74 秒，镜像在爬
        00:19:55  第 1 次没跑完          ← 240 秒被杀，派生的 apt-get 活着
        00:20:19  fonts-wqy-zenhei 7.5 MB 还在下   ← **孤儿进程仍在推进**
        00:20:55  等了 60 秒还没松开，硬着头皮再试
        00:20:57  E: Could not get lock ... held by process 4342 (apt-get)
        00:21:57  装 Chromium 两次都没成功

    上一条判据（重试之前要等锁）当时**是绿的**——等是等了，只是**等得不够长**。
    而孤儿不是挂死，是在慢慢下载：多等一会儿它自己就松手了，
    「硬着头皮再试」等于把仅剩的那次尝试扔进一个必然失败的口。

    ⚠️ **上界同样要钉**：步骤 `timeout-minutes: 10`，两次安装各 240 秒，
    留给等待的只有 120 秒。等待写过头，第 2 次会在**眼看要成的时候**被步骤
    预算掐掉——那和「装不上」长得一模一样（工作流注释里记着这条）。

    所以这条钉的是 **110 ≤ 等待预算 ≤ 120**，两头都不许被人单方面改动。
    """
    import re as _re  # noqa: PLC0415

    INSTALL_TIMEOUT, ATTEMPTS, STEP_BUDGET = 240, 2, 10 * 60
    checked = {}
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if not ln.lstrip().startswith("#")]
        body = "\n".join(lines)
        if "pw_wait_apt" not in body:
            continue
        loop = _re.search(r"pw_wait_apt\(\)\s*\{.*?for _ in \$\(seq 1 (\d+)\).*?"
                          r"sleep (\d+)", body, _re.S)
        assert loop, f"{path.name} 的 pw_wait_apt 形状变了，判据的主语没了"
        budget = int(loop.group(1)) * int(loop.group(2))
        checked[path.name] = budget
        assert budget >= 110, (
            f"{path.name} 等 dpkg 锁只等 {budget} 秒——60 秒那一版实测不够："
            "被超时杀掉的 apt-get 还在慢慢下包，重试会在两秒内撞锁（run 31058902174）")
        assert INSTALL_TIMEOUT * ATTEMPTS + budget <= STEP_BUDGET, (
            f"{path.name} 等 {budget} 秒 + {ATTEMPTS}×{INSTALL_TIMEOUT} 秒安装 "
            f"＞ 步骤预算 {STEP_BUDGET} 秒——第 2 次会在眼看要成的时候被掐掉，"
            "而那和「装不上」长得一模一样")
    assert len(checked) >= 6, (
        f"只扫到 {len(checked)} 条工作流有 pw_wait_apt，判据的主语像是没了")


def test_等满dpkg锁的预算之后要主动杀掉不能只是继续等():
    """⚠️⚠️ **上一条判据（110~120 秒）当时是绿的——等是等够了，等法本身错了。**

    2026-08-19（run 32211814483，tnns-stats）：`pw_wait_apt` 等满 110 秒，
    锁**仍然**没松——被 `timeout` 杀掉的那层壳没能把信号传给它派生出来的
    apt-get（同一条注释早写着「派生的 apt-get 活了下来」），那个孤儿不是
    挂死，是在镜像上慢慢下一个字体包，110 秒不够它下完；重试的第二次立刻
    死在 `Could not get lock ... held by process 2657 (apt-get)`。

    而这一层已经贴着步骤预算的上限（上一条判据钉的 110~120 秒——
    `INSTALL_TIMEOUT×ATTEMPTS + 等待预算 ≤ STEP_BUDGET`）。**继续往上加
    等待时间不是出路**：上一次就是从 60 秒加到 110 秒才有的这一版，这次
    撞上同一个天花板，说明「多等一会」这条路本身已经走到头了——被动等待
    追的是一个移动的靶子（镜像多久能下完那个包，我们控制不了）。

    真正能做的是**不再指望孤儿自己让开，等满就主动结束它**：我们不需要
    保住它的下载进度——被杀掉那次已经下进 `/var/cache/apt/archives` 的包，
    下一次重试照样会复用（ci.yml 那条注释早说过）。`sudo pkill -9 apt-get`
    + `sudo pkill -9 dpkg` + `sudo dpkg --configure -a` 把状态收拾干净，
    比继续等一个不知道还要多久的下载快得多，也不会撞步骤超时。

    ⚠️ 判据**自己推导，不维护白名单**：凡是有 `pw_wait_apt` 的工作流都算，
    而且要求这三行**紧跟在等待循环之后、`pw_wait_apt` 函数体收尾之前**
    ——写在别处（比如只在 `pw_retry` 外层收尾时才清一次）救不了「等满就
    立刻重试、必死在两秒内」这个场景，因为下一次重试是在 `pw_wait_apt`
    返回之后立刻发生的。
    """
    checked = {}
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                 if not ln.lstrip().startswith("#")]
        body = "\n".join(lines)
        if "pw_wait_apt" not in body:
            continue
        checked[path.name] = True
        fn = re.search(r"pw_wait_apt\(\)\s*\{(.*?)\n {10}\}", body, re.S)
        assert fn, f"{path.name} 的 pw_wait_apt 函数体形状变了，判据的主语没了"
        tail = fn.group(1).split("等了 110 秒 dpkg 锁还没松开", 1)
        assert len(tail) > 1, f"{path.name} 找不到那句等满 110 秒的告警"
        after_warning = tail[1]
        assert "pkill -9 apt-get" in after_warning, (
            f"{path.name} 等满 110 秒之后只是继续等——2026-08-19 那次实测证明"
            "等法本身不够，得在等满之后主动杀掉孤儿 apt-get，不能指望它自己让开")
        assert "pkill -9 dpkg" in after_warning, (
            f"{path.name} 只杀了 apt-get 没杀 dpkg——两边 pgrep 都在查，"
            "杀的时候也要两边都杀")
        assert "dpkg --configure -a" in after_warning, (
            f"{path.name} 杀了孤儿却没有 `dpkg --configure -a` 收拾半装状态——"
            "SIGKILL 打断 apt-get 可能留下半配置好的包，下一次重试会撞见它")
    assert len(checked) >= 6, (
        f"只扫到 {len(checked)} 条工作流有 pw_wait_apt，判据的主语像是没了")


def test_装ffmpeg和字体一律先试本地缓存不能只靠重试():
    """⚠️⚠️ 2026-08-19 一天里连中**三次**同一个坑，三条不同的工作流：

        PR #448（ci.yml，run 32218612883）       `apt-get install` 两次吃满 150 秒
        PR #451（match-reel.yml render 那趟）    `apt-get update`  两次吃满 150 秒
        interview-clip.yml mode=subs（run 32212794304/32213180838）
                                                  `apt-get install` 两次吃满 150 秒

    三次都是**零字节进度**——`Acquire::http::Timeout=20` 那道防线对着一个
    彻底不响应的镜像没能生效（连接本身没在配置的超时内收敛，是 DNS 还是
    TCP 层面卡住，从这台机器上看不出来）。继续调重试参数治不了根：
    这层防线已经调过好几轮（3×100s → 2×150s，`Retries=3`＋`Timeout=20`），
    还是照样两次都吃满。

    真正的杠杆是**大多数 run 根本不用碰这个镜像**。`apt-get update`／
    `install` 的产物（索引 + 下载好的 .deb）缓存住之后，装的时候直接从
    本地满足，一次网络请求都不用发。`tools/ci_apt_install.sh` 就是干这个的：
    `apt_install_cached` 先试一次零网络的本地安装，只有缓存没命中或不全，
    才回退到会摸网的 `apt_retry`（那套重试逻辑没扔——真第一次冷启动、
    或者缓存被清过，还是需要它）。

    索引和下载缓存**不用 `/var/cache/apt/archives` / `/var/lib/apt/lists`
    这两个系统路径**——它们是 root 建的，`actions/cache@v4` 的 save/restore
    步骤是非 root 用户跑的，写不进去。改用 `Dir::Cache::Archives` /
    `Dir::State::lists` 把 apt 这两块状态重定向到 `$HOME/.cache/apt-*`，
    那两个目录由脚本自己先 `mkdir -p`（普通用户建的，普通用户能写），
    `sudo apt-get` 写进去的文件默认 644（世界可读），缓存步骤读得到。

    判据钉四头：

    - **不许再有内联的 `apt_retry() {`**：那份逻辑现在只活在共享脚本里，
      写两处必分叉（`Acquire::http::Timeout` 只加在 update 那行、install
      没跟着加，就是这个仓库自己啃过两次的坑）
    - **调 `apt_install_cached` 或 `ensure_ffmpeg` 之前必须先 `source`
      那份脚本**——这两个函数都不会凭空存在
    - **每个用到它的文件，前面必须有一个真的 `actions/cache@v4` 步骤**，
      缓存路径里带着 `apt-archives`——没有缓存步骤，「先试本地缓存」这句话
      就是一句空话，`apt_install_cached` 每次都会走到摸网那条回退路。
      `ensure_ffmpeg` 一样要这条：它自己的静态构建落空之后落回的还是
      `apt_install_cached`
    - 判据自己的判据：扫到的文件数不许掉下 8——这是共享脚本落地那天覆盖的
      全部工作流数量

    ⚠️ **`ensure_ffmpeg` 上线那天这条判据也要跟着换主语，理由和它的邻居
    `test_装ffmpeg和字体那批步骤都走共享脚本不留手搓的调用` 一样**：
    ffmpeg 那几处调用从 `apt_install_cached ffmpeg` 换成了 `ensure_ffmpeg`
    （先试 GitHub Releases 上的静态构建，落空才退回 apt 这条老路），
    只认 `apt_install_cached` 这一个名字会让 `frame-grab.yml`／
    `voice-sample.yml` 两个文件从「校过」变成「没校」——**换个函数名不该
    让判据的覆盖面跟着缩水**。
    """
    files_with_cache_calls = []
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        raw = path.read_text(encoding="utf-8")
        body = _yaml_only(raw)
        calls_ensure_ffmpeg = bool(re.search(r"(?<![\w-])ensure_ffmpeg(?![\w-])", body))
        calls_apt_cached = "apt_install_cached" in body
        if not (calls_ensure_ffmpeg or calls_apt_cached):
            continue
        files_with_cache_calls.append(path.name)

        assert "apt_retry() {" not in body, (
            f"{path.name} 还留着一份内联的 apt_retry()——共享脚本装好了，"
            "这份该删掉，不然下次改重试逻辑又要记着改两处")

        cache_step_seen = False
        for name in _steps(body):
            block = _step_block(name, raw)
            block_yaml_only = _yaml_only(block)
            if "actions/cache@v4" in block_yaml_only and "apt-archives" in block_yaml_only:
                cache_step_seen = True
                continue
            calls_here = ("apt_install_cached" in block_yaml_only
                          or re.search(r"(?<![\w-])ensure_ffmpeg(?![\w-])", block_yaml_only))
            if not calls_here:
                continue
            assert cache_step_seen, (
                f"{path.name} 的步骤「{name}」调了 apt_install_cached 或 ensure_ffmpeg，"
                "但前面没有一个真的 actions/cache@v4 步骤缓存 apt-archives——"
                "『先试本地缓存』就成了一句空话，每次都会走到摸网那条回退路")
            assert "source tools/ci_apt_install.sh" in block_yaml_only, (
                f"{path.name} 的步骤「{name}」调了 apt_install_cached 或 ensure_ffmpeg "
                "却没有先 source 共享脚本——这两个函数都不会凭空存在")

    assert len(files_with_cache_calls) >= 8, (
        f"只扫到 {len(files_with_cache_calls)} 个文件用了 apt_install_cached/ensure_ffmpeg，"
        "判据的主语像是没了")


#: interview-clip.yml 的两把固定键已经在另一条并行分支上换成了滚动键
#: （v1 → v2，键里带 `run_id`）——这张表因此空了。**只许减不许加**：
#: 新加一条 apt 缓存必须直接用滚动键，别往这张表里塞。
_LEGACY_FIXED_APT_KEYS: set[tuple[str, str]] = set()


def test_apt缓存键一律滚动固定键存下半份就永远补不进新包():
    """actions/cache 的**主键不可变**：固定键第一趟存下什么，以后就永远是什么。

    坑长这样：第一趟只攒下 ffmpeg，后面哪趟把字体包补进目录，post step 也
    **不能覆盖同名缓存**——于是那些趟仍要重新摸 apt 镜像，而「缓存 apt 包」
    这一步的全部意义就是**别碰那个会抽风的镜像**（2026-08-19 一天三条工作流
    零字节进度各烧 300 秒）。match-reel.yml 当天换成滚动键（run_id 进 key ＋
    restore-keys 按前缀捞回上一份），其余六条还是 v1 固定键——同一个坑六个
    入口。**这条判据自己扫全部工作流，不维护名单**：以后新加一条带 apt 缓存
    的工作流，它会替人记得。

    豁免表 `_LEGACY_FIXED_APT_KEYS` 只有 interview-clip 的两把（那个文件归
    另一条并行分支管），**只许减不许加**，而且自带自检：表里的键必须真的还在、
    真的还是固定键——写错一个名字，豁免就成了一盏恒真的绿灯。
    """
    seen_fixed: set[tuple[str, str]] = set()
    checked = 0
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        body = _yaml_only(path.read_text(encoding="utf-8"))
        for m in re.finditer(r"^\s*key: (apt-pkgs-[^\n]+?)\s*$", body, re.M):
            key = m.group(1)
            checked += 1
            if (path.name, key) in _LEGACY_FIXED_APT_KEYS:
                seen_fixed.add((path.name, key))
                continue
            assert "${{ github.run_id }}" in key, (
                f"{path.name} 的 apt 缓存键是固定的：{key}——主键不可变，"
                "后面补装的包永远写不回去。照 match-reel.yml 的形状换滚动键")
            prefix = key.split("${{ github.run_id }}")[0]
            assert re.search(r"restore-keys: \|\n\s*" + re.escape(prefix), body), (
                f"{path.name} 的滚动键没配 restore-keys 前缀 {prefix}——"
                "没有它每一趟都是冷缓存，滚动键就白滚了")
    assert checked >= 9, f"只扫到 {checked} 把 apt 缓存键，判据的主语像是没了"
    assert seen_fixed == _LEGACY_FIXED_APT_KEYS, (
        "豁免表和现实对不上："
        f"{sorted(_LEGACY_FIXED_APT_KEYS - seen_fixed)} 已经不在或已改成滚动键"
        "——从表里删掉，别留一盏恒真的绿灯")


def test_共享的apt安装脚本形状要对():
    """`tools/ci_apt_install.sh` 是给工作流 `source` 的，形状变了要在这儿先炸，
    不要等下一次真跑 CI 才发现。

    ⚠️ **2026-08-19 又加了一条**：重定向到 `$HOME/.cache/apt-*` 撞上了
    apt 自己的沙箱降权——`_apt` 用户进不去 `runner` 的主目录，于是每个文件
    都要先撞一次权限、警告、再退回 root 下载，表现和「镜像不响应」一模一样
    （run 32236503405 attempt 4 才第一次在日志里露出来：
    `couldn't be accessed by user '_apt'. - pkgAcquire::Run (13: Permission
    denied)`）。`APT::Sandbox::User=root` 让 apt 直接用 root 下载，
    不走这套降权折腾——**这条判据钉的是「别把这一行删掉」，不是「重新发现
    这个坑」**：这个坑够贵，值得有一条专门的判据挡住它复发。
    """
    script = Path("tools/ci_apt_install.sh")
    assert script.is_file(), "共享脚本不见了，match-reel.yml 等 8 个文件都在 source 它"
    body = script.read_text(encoding="utf-8")
    assert "apt_install_cached()" in body or "apt_install_cached ()" in body
    assert "apt_retry()" in body or "apt_retry ()" in body
    # 重定向到非 root 目录才是 actions/cache 能读写的那一半，别退回系统路径。
    # ⚠️ 先去掉整行注释再查——注释里正解释着「为什么不用系统路径」，
    # 连注释一起扫会把「把坑记下来」判成「又踩了这个坑」
    code_only = "\n".join(
        ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
    assert "Dir::Cache::Archives" in code_only
    assert "Dir::State::lists" in code_only
    assert "/var/cache/apt/archives" not in code_only
    assert "/var/lib/apt/lists" not in code_only
    assert "APT::Sandbox::User=root" in code_only, (
        "少了这一行，`_apt` 沙箱用户写不进 $HOME/.cache/apt-lists，"
        "会重新表现成「apt 卡住了」")
    # 这个选项要跟着 `_apt_opts` 一起进每一次 apt-get 调用，不能只出现在
    # 某一行——否则「缓存命中那条快路径」和「走网络那条慢路径」只有一条
    # 真的免了降权折腾，另一条照样撞权限。
    assert "_apt_opts=(" in code_only and "APT::Sandbox::User=root" in code_only.split(
        "_apt_opts=(", 1)[1].split(")", 1)[0], (
        "APT::Sandbox::User=root 要写进 _apt_opts 数组本身，"
        "这样三处调用（缓存检查 / update / install）才能共用同一份")
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_Chromium缓存都要有restore_keys():
    """键钉在整份 `pyproject.toml` 上太宽，**加一个依赖就把六条线的缓存全废掉**。

    决定装哪个 Chromium 的只有 playwright 的版本，可那个键是整份文件的哈希——
    加一个依赖、改一行注释，六条工作流的 150 MB Chromium 缓存同时失效，
    下一趟每条都要重下一遍。2026-08-05 往 pyproject 里加 certifi 和 pytest-xdist
    时当场撞上（run 30973785219 卡在「安装 Chromium」）。

    `restore-keys` 就够：主键没中就退到上一份，Chromium 已经在盘上，
    `playwright install` 是个空操作；真换了 playwright 版本它会自己去下对的那
    一版，所以退旧缓存也不会拿错。比另起一步算版本号便宜，也不用动步骤顺序。

    **判据自己推导，不维护名单**：凡是缓存 Chromium 的工作流都要有。
    以后多一条出海报／渲卡片的线，它会替人记得。
    """
    hits = {}
    for path in sorted(WORKFLOW.parent.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        body = "\n".join(ln for ln in text.splitlines()
                         if not ln.lstrip().startswith("#"))
        if "playwright-chromium-" not in body:
            continue
        hits[path.name] = "restore-keys: playwright-chromium-" in body
    assert hits, "一条缓存 Chromium 的工作流都没扫到，判据的主语没了"
    missing = sorted(n for n, ok in hits.items() if not ok)
    assert not missing, (
        f"这几条缓存了 Chromium 却没有 restore-keys：{missing}。"
        "改一次 pyproject 就要重下一遍 150 MB，而它只表现为「今天怎么慢了点」。")


def test_源片缓存的键要按URL算():
    """两层缓存的口径必须一致，否则外层每趟都白传一份 50~70 MB。

    代码里那层（`_cached_source`）的注释白纸黑字写着「键取 URL 的哈希：换了
    URL 自然是另一个键」。而 Actions 那层原来用的是
    `hashFiles(specs/reels/<slug>.json)`——**改一个字的旁白，spec 哈希就变**，
    主键必然未命中，这一趟结束时又把同一个源片重新上传一份。
    shang-rublev 那条光 spec 就改了六次。

    仓库缓存上限 10 GB、LRU 淘汰，所以这些重复条目会把 Chromium（150 MB）
    和抠图模型（176 MB）挤出去——而那表现为「今天 CI 怎么慢了点」，
    **没有任何东西会说是缓存被挤掉了**。

    判据钉两头：键不许再从整份 spec 来，而且算键那一步要**复用
    `spec_sources()`**——单源写 `source_url`、多源写 `sources`，
    在这儿再解析一遍必分叉。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    cache = _step_block("缓存源片（同一条片子只下一次）", text)
    key = next(ln for ln in cache.splitlines() if ln.strip().startswith("key:"))
    assert "hashFiles" not in key, (
        "源片缓存的键还在按整份 spec 算——改一个字的旁白就会让主键失效，"
        f"于是每趟都重传一份源片：{key.strip()}")
    assert "srckey" in key, f"键没接上按 URL 算的那一步：{key.strip()}"

    keystep = _step_block("算出源片缓存的键", text)
    assert "spec_sources" in keystep, (
        "算键那一步自己解析了一遍 spec——单源 `source_url` 和多源 `sources` "
        "两种写法，写两处必分叉。复用 `spec_sources()`。")
    # **两种情况都要出声**：算出来了和没算出来，日志上必须分得开，
    # 否则「缓存没生效」和「生效了」长得一模一样。
    assert keystep.count("print(") >= 1 and "源片缓存键" in keystep, (
        "算键那一步不打印它算出了什么——缓存没生效时看不出来")
    # 算不出键不许把整趟带崩：spec 真有问题的话，后面几步会报说人话的错
    assert "except Exception" in keystep, (
        "spec 读不出来会让这一步炸，而它排在 render 前面——"
        "报错会变成一句和 spec 无关的缓存错误")


def _reel_download_stub(monkeypatch, tmp_path, resolved):
    """把 `download()` 除「取哪个地址」以外的每一步都打桩，返回真跑过的命令表。

    只打桩，不改判据：`_resolve_media_url` 换成一个认得出的常量，其余
    （yt-dlp 在不在、下到的够不够高、存不存缓存）都不是这几条要验的东西。
    """
    import build_match_reel as m  # noqa: PLC0415

    cmds: list[list[str]] = []

    def _fake_run(cmd, **kw):
        cmds.append(list(cmd))
        if cmd and cmd[0] == "curl":
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"not a video")
        else:
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"x" * 64)
        return type("P", (), {"returncode": 0, "stderr": "", "stdout": ""})()

    monkeypatch.setattr(m, "_resolve_media_url", lambda u: resolved)
    monkeypatch.setattr(m.shutil, "which", lambda name: "/usr/bin/yt-dlp")
    monkeypatch.setattr(m.subprocess, "run", _fake_run)
    monkeypatch.setattr(m, "probe_size", lambda p: (1920, 1080))
    return m, cmds


TENNISTV_PAGE = (
    "https://www.tennistv.com/videos/4560312/"
    "cincinnati-2026-r2-paul-hurkacz-short-highlights")


def test_下载那一步要先把TennisTV的页面地址解成HLS(monkeypatch, tmp_path):
    """**只测 `media_url` 自己对拦不住位置错**：它写出来了、`download()` 不调，
    行为测试照样绿，而出片那一步会拿页面地址去喂 yt-dlp，报
    `This video is only available for registered users`——一句指向
    「cookie 过期了」的错，而真相是这条路根本没接上。

    这条线 2026-08-16 起要吃 Tennis TV：`library/short-highlights` 那批标着
    `data-entitlement="free"` 的单场短集锦（实测 20/20 全 free、2 分半、
    1920×1080），是 ATP「赛场之上」第一条不用订阅也不看 YouTube 脸色的源。
    采访线 2026-08-05 就接了这一步，出片线一直没有——而
    `_reject_signed_source_urls` 的报错正文里早写着「Tennis TV 库里标着
    `free` 的条目」这条出路。**出路写出来了，代码自己不走。**
    """
    monkeypatch.delenv("TENNISLIVE_SOURCE_CACHE", raising=False)
    m, cmds = _reel_download_stub(monkeypatch, tmp_path, "https://cdn.example/x.m3u8")
    monkeypatch.setattr(m, "_keep_source", lambda u, s: None)

    m.download(TENNISTV_PAGE, tmp_path / "s.mp4")

    assert cmds, "一条命令都没跑"
    assert cmds[-1][-1] == "https://cdn.example/x.m3u8", (
        "download() 没走 _resolve_media_url，页面地址直接喂给了 yt-dlp："
        f"{cmds[-1][-1]}")


def test_播放列表不许先走curl那条直链(monkeypatch, tmp_path):
    """`.m3u8` **不是一个文件，是一张播放列表**。

    curl 下回来是几 KB 文本，必然过不了那道 ffprobe，白挨一次请求，
    还在日志里留一句指错方向的「直链下到 0.0 MB，ffprobe 读不出视频流」——
    下一个人会去查源片是不是坏了，而它好好的。

    ⚠️ 判的是**这个东西本身是不是播放列表**，不是「哪些站要交给 yt-dlp」。
    域名名单会过期，而过期的名单和一条常年红的检查是同一个毛病。
    """
    monkeypatch.delenv("TENNISLIVE_SOURCE_CACHE", raising=False)
    m, cmds = _reel_download_stub(monkeypatch, tmp_path, "https://cdn.example/x.m3u8")
    monkeypatch.setattr(m, "_keep_source", lambda u, s: None)

    m.download(TENNISTV_PAGE, tmp_path / "s.mp4")

    assert not [c for c in cmds if c and c[0] == "curl"], (
        "解出来的是 .m3u8，却还先 curl 了一遍——那一趟必然失败且日志指错方向")

    # 反面：普通直链**照旧**走 curl，别顺手把这条路一起关掉。
    # ⚠️ 解析这一步也要跟着还原成「原样返回」——不还原的话这半条验的还是
    # 那个 m3u8，测试会因为**错误的原因**变红（或变绿）。
    cmds.clear()
    monkeypatch.setattr(m, "_resolve_media_url", lambda u: u)
    m.download("https://pan.example/a.mp4", tmp_path / "d.mp4")
    assert cmds and cmds[0][0] == "curl", (
        "普通直链不再走 curl 了——这条路是被逼出来的（YouTube 封着，"
        "人只能自己下好传到网盘），不许连坐")


def test_解出来的带令牌地址不许当缓存键(monkeypatch, tmp_path):
    """缓存按 URL 的哈希认领，而 Tennis TV 解出来的 manifest **带一个只活
    60 秒的令牌**（实测 `exp - iat = 60`）。

    拿它当键的话**每一趟都是新键，缓存永远不命中**——而缓存正是为了省下
    「同一条源片 probe / cover / render 各下一次」那三趟里的两趟（实测一个
    70 MB 的源片要下 100.86 秒）。更糟的是缓存目录会被一堆一次性条目撑满，
    把 Chromium 和抠图模型挤出仓库缓存，**而那表现为「今天 CI 怎么慢了点」**。

    页面地址是稳定的，它才是键。判据钉的就是「进出缓存用的都是页面地址」。
    """
    monkeypatch.setenv("TENNISLIVE_SOURCE_CACHE", str(tmp_path / "cache"))
    token_url = "https://cdn.example/x.m3u8?token=" + "a" * 40
    m, _cmds = _reel_download_stub(monkeypatch, tmp_path, token_url)

    keyed: list[str] = []
    real_cached, real_keep = m._cached_source, m._keep_source

    def _spy_cached(url, suffix):
        keyed.append(url)
        return real_cached(url, suffix)

    def _spy_keep(url, src):
        keyed.append(url)
        return real_keep(url, src)

    monkeypatch.setattr(m, "_cached_source", _spy_cached)
    monkeypatch.setattr(m, "_keep_source", _spy_keep)

    m.download(TENNISTV_PAGE, tmp_path / "s.mp4")

    assert keyed, "缓存那两步一次都没被调到"
    assert all(u == TENNISTV_PAGE for u in keyed), (
        "缓存键用了解析之后那个带令牌的地址，60 秒后就是另一个键——"
        f"缓存永远不会命中：{[u[:60] for u in keyed if u != TENNISTV_PAGE]}")


def test_认TennisTV要按主机名而且只有一份实现():
    """两条线（赛后开麦、赛场之上）共用 `official.media_url`。

    写两处必分叉，而**分叉的样子是「采访线能下、出片线报『注册用户才能看』」**
    ——两个入口各自试一次才看得出来，而没有人会为一条已经通了的线再试一次。

    顺带钉住「按主机名认」：`https://example.com/?ref=tennistv.com` 会从中间
    匹配上，而它不是 Tennis TV。
    """
    from tennislive.video import official  # noqa: PLC0415

    assert official.TENNISTV_HOST not in ("", None)
    # 非 Tennis TV 一律原样返回，一次网络都不许发
    for url in ("https://www.youtube.com/watch?v=abc",
                "https://example.com/?ref=tennistv.com",
                "https://cdn.example/already.m3u8"):
        assert official.media_url(url) == url, url

    # 两条线都不许自己再抄一份解析逻辑。
    # ⚠️ **用 AST，不按文本扫**：`build_match_reel.py` 的报错正文里正写着
    # 「见 `official.fetch_tennistv_video_metadata`」——那是**出路**，不是调用。
    # 按文本扫会把「把出路写清楚」判成「又抄了一份」，这个仓库为「判据扫得太宽、
    # 被自己的注释误伤」栽过五次。字符串常量不进 Name/Attribute。
    for tool in (Path("tools/build_match_reel.py"),
                 Path("tools/build_interview_clip.py")):
        tree = ast.parse(tool.read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                names.update(a.name for a in node.names)
        assert "fetch_tennistv_video_metadata" not in names, (
            f"{tool} 自己又抄了一份 Tennis TV 解析——正文只该有 "
            "`official.media_url` 一份，这儿只做异常翻译")


def test_不下源片的模式不许等PO_token():
    """`起 PO token provider` 是给**下载**用的（docker pull ＋ 探活，实测 11 秒）。

    不碰源片的模式等它就是纯浪费。`narration` 正是这样一档——它比的是
    「TTS 时长 vs spec 里的段长」，`--check-narration` 的注释白纸黑字写着
    「一个源片字节都不碰」，可它一直在这儿站着等。整趟 narration 只有 1 分 37 秒，
    这 11 秒是 11%。**又一次「加新能力时新入口没继承前提」**：narration 这一档
    是后加的，这行 `if` 没跟着改。

    **判据自己推导，不维护名单**：拿「缓存源片」那一步当基准——连源片缓存都
    不恢复的模式，必然不下源片。以后再加一档模式，它会替人记得。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    no_source = _excluded_modes(_step_block("缓存源片（同一条片子只下一次）", text))
    assert no_source, "「缓存源片」那一步没抽到 mode 条件，基准没了"
    pot = _excluded_modes(_step_block("起 PO token provider", text))
    assert no_source <= pot, (
        f"这些模式不下源片却还在等 PO token provider：{sorted(no_source - pot)}")


def test_查旁白那条路装的依赖要真的够():
    """narration 只装它用得上的那点（实测 31s → 约 10s），**但不许装少**。

    ⚠️ **numpy 缺了不报错**：`voice_prosody` 抓 ImportError 之后逐段打
    「量不了」，于是这条 run 的产物——那张音高表——静静地退成十一行空白。
    是在**干净 venv** 里照工作流那一行原样装一遍才看见的，沙箱里 numpy 一直
    装着（「本地装着不等于 CI 装着」的第 N 次，只是这次它不红、只是变哑）。

    判据两头：**预检 import 的每一样都要真的装**（少一样就是第 5 秒炸 vs
    一分半后炸），而且**这条路上会用到的第三方包都要在预检里**。
    """
    install = _step_block("装依赖", WORKFLOW.read_text(encoding="utf-8"))
    branch = install[install.index('= "narration" ]'):]
    branch = branch[:branch.index("exit 0")]
    installed = set(re.findall(r"pip install -q (?:-e )?(.+)", branch))
    installed = {w for line in installed for w in line.split()} | {"tennislive"}
    checked = set(re.findall(r"python -c \"import ([^\"]+)\"", branch))
    checked = {m.strip().split(".")[0] for line in checked for m in line.split(",")}
    assert checked, "narration 那一支没有预检 import，装少了要到一分半后才炸"
    for mod in checked:
        assert any(mod.replace("_", "-") in pkg or mod in pkg for pkg in installed), (
            f"预检要 import {mod}，而这一支没装它：{sorted(installed)}")
    # **量音高那一段用的包必须在预检里。** 它是这条 run 的产物，
    # 而缺了它只会变哑不会变红——只测「装了什么」拦不住这一种。
    reel = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    prosody = reel[reel.index("def voice_prosody("):]
    prosody = prosody[:prosody.index("\ndef ", 1)]
    for mod in set(re.findall(r"^\s+import (\w+)", prosody, re.M)):
        assert mod in checked or mod in sys.stdlib_module_names, (
            f"voice_prosody 要 {mod}，而 narration 那一支的预检没查它——"
            "缺了它音高表会静静退成一片「量不了」")


def test_cookies和probe装依赖走轻装而TTS缓存只给会合语音的两档():
    """probe / cookies 两档各装各的，别把 rembg（176 MB 模型）和 playwright 铺进去。

    和「push 模式只装主依赖」「narration 只装合语音那几样」同一个理由：装全套
    不只是慢（31 秒），更是把失败面铺大——那几个包里任何一个装不上，都会让一条
    **本来只是验 cookie / 探测**的 run 挂掉。cookies 只拿 yt-dlp 下 30 秒试块，
    probe 要 yt-dlp + ffmpeg + cv2（cutout 只有「封面候选帧」那一步用，而它由
    `cutout_candidates` 控制）。

    另外两头，都是缓存口径：
    ① srckey / 缓存源片要排除 cookies——它不走 `download()`（自己往
      `$RUNNER_TEMP` 下试块），恢复源片缓存对它是纯开销，结束时还把这份缓存
      重传一遍挤 10 GB LRU 池；
    ② TTS 缓存只给真会合语音的两档（render / narration）——probe、cover、
      cookies 一个字都不合成，而滚动键（run_id 进 key）每趟都会存一份新条目，
      白占池子把 Chromium（150 MB）和抠图模型（176 MB）往外挤，被挤掉的样子
      只是「今天 CI 怎么慢了点」。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    install = _step_block("装依赖", text)

    # cookies 分支：主依赖 + yt-dlp[default]，别的一个都不装
    ck = install[install.index('= "cookies" ]'):]
    ck = ck[:ck.index("exit 0")]
    assert "yt-dlp[default]" in ck, (
        "cookies 分支必须装 yt-dlp[default]——少了 yt-dlp-ejs，n challenge 解不了，"
        "报出来像「cookie 过期了」")
    for heavy in ("webrender", "cutout", "playwright", "edge-tts"):
        assert heavy not in ck, f"cookies 分支装了它用不上的 {heavy}"

    # probe 分支：visualqa + yt-dlp[default] + cv2 预检；cutout 按需
    pb = install[install.index('= "probe" ]'):]
    pb = pb[:pb.index("exit 0")]
    assert "[visualqa]" in pb and "yt-dlp[default]" in pb
    assert "visualqa,cutout" in pb and "cutout_candidates" in pb, (
        "probe 的 cutout 只在封面候选帧那趟才要，而那一趟由 cutout_candidates 控制")
    assert "import cv2" in pb, "probe 分支没预检 cv2——装少了要到下完源片才炸"
    assert "webrender" not in pb, "probe 不渲 HTML 封面，playwright 用不上"

    # 全量那行必须还在（render / cover 走它），且排在所有轻装分支后面
    full_at = install.index('".[webrender,visualqa,cutout]"')
    assert full_at > install.index('= "cookies" ]')
    assert full_at > install.index('= "probe" ]')

    # ① 源片缓存那两步都要排除 cookies（连同 push / narration）
    for name in ("算出源片缓存的键", "缓存源片（同一条片子只下一次）"):
        excluded = _excluded_modes(_step_block(name, text))
        missing = {"push", "narration", "cookies"} - excluded
        assert not missing, f"「{name}」的 if 少排除了 {sorted(missing)}"

    # ② TTS 缓存放行的模式恰好是 render / narration，一个不多一个不少
    tts = _step_block("缓存 TTS（同文旁白跨趟不重合成）", text)
    head = tts.split("uses:", 1)[0]
    allowed = set(re.findall(r"inputs\.mode\s*==\s*'([a-z-]+)'", head))
    assert allowed == {"render", "narration"}, (
        f"TTS 缓存放行的是 {sorted(allowed)}，该恰好是 render / narration")
    assert not _excluded_modes(tts), (
        "TTS 缓存该用 == 白名单——用 != 黑名单的话，以后加一档新模式它会静默放进来")


def test_dry_run闸在runner上排在重准备之前且拉回probe产物():
    """`--dry-run` 0.2 秒能拦的错，runner 上不许等到装完 Chromium、下完源片才红。

    「本地先跑 dry-run」靠的是人记得——而这个仓库为「靠人记得」栽过的次数
    本文件数不过来。这一步让 runner 自己也拦一遍：spec 形状错、选段硬伤、
    文案超限、旁白一定装不下，全死在第 30 秒，不是第 5 分钟。

    判据钉三头：
    ① 放行的模式**恰好**是读 spec 的那三档（render / cover / narration）——
      probe 常常还没有 spec，cookies / push 不读 spec；
    ② probe 产物要按 slug 从 HEAD 里拉回来（稀疏检出把 output/ 挡在外面，
      不拉的话 dry-run 的 probe 层是哑的，而「没查」和「查过没问题」在日志上
      长得一模一样——所以查不到还必须出声）；
    ③ **位置**：排在缓存 Chromium / 缓存源片 / 起 PO token provider 之前——
      排在后面的话，拦住了也已经白付了那几分钟的准备。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    gate = _step_block("dry-run — 先把 spec 的形状错拦在编码之前", text)

    # ① == 白名单，恰好三档
    head = gate.split("run:", 1)[0]
    allowed = set(re.findall(r"inputs\.mode\s*==\s*'([a-z-]+)'", head))
    assert allowed == {"render", "cover", "narration"}, (
        f"dry-run 闸放行的是 {sorted(allowed)}，该恰好是 render/cover/narration")
    assert not _excluded_modes(gate), "该用 == 白名单，不是 != 黑名单"

    # ② 真调 --dry-run；probe 产物按 slug 拉回，查不到要出声
    assert "--dry-run" in gate, "这一步没调 --dry-run，名不副实"
    assert "git ls-tree" in gate and "sparse-checkout add" in gate, (
        "没把这条 slug 的 probe 产物从 HEAD 拉回来——probe 层会是哑的")
    assert re.search(r"/reel/\$\{SLUG\}/probe\\\.json", gate), (
        "拉的不是这条 slug 自己的 probe.json——按 slug 收窄，别把整棵 output/ 抬回来")
    assert "::warning::" in gate, (
        "查不到 probe 时不出声——「没查」和「查过没问题」在日志上就长一样了")

    # ③ 位置：排在三样重准备之前
    yml = _yaml_only(text)
    gate_at = yml.index("- name: dry-run — 先把 spec 的形状错拦在编码之前")
    for later in ("- name: 缓存 Chromium",
                  "- name: 缓存源片（同一条片子只下一次）",
                  "- name: 起 PO token provider"):
        assert gate_at < yml.index(later), f"dry-run 闸排到「{later}」后面去了"


def test_挂代理CA要排在导入edge_tts之前(tmp_path, monkeypatch, capsys):
    """`--check-narration` 那道闸**一个源片字节都不碰**，本来就能在本地跑。

    挡着它的不是「被 YouTube 挡」——CLAUDE.md 里「edge-tts 同理」那半句是
    推出来的，不是量出来的。实测报的是 `CERTIFICATE_VERIFY_FAILED`：
    这台机器的出网走一个做 TLS 拦截的代理，而 edge-tts 认的是 certifi 自带的
    根证书。挂上代理的 CA 当场就通了（实测本地跑完一条 11 段的 spec 29 秒，
    对比 runner 上 1 分 37 秒的 run 外加一次完整往返）。

    ⚠️ **顺序是这条的全部。** edge-tts 在**模块导入那一刻**就
    `ssl.create_default_context(cafile=certifi.where())` 建好了 context，
    之后再挂 CA 一点用都没有——而那种失败长得和「没挂」一模一样。
    所以两件事一起钉：调用排在最前面，且没有任何模块级的 `import edge_tts`。
    """
    from tennislive import localca  # noqa: PLC0415

    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    call = body.index("trust_local_proxy_ca()")
    assert call < body.index("ArgumentParser"), "挂 CA 没排在 main 的最前面"
    # **模块级 import 会让上面那个顺序失效**——import 在 main 跑起来之前就发生了
    for path in ("tools/build_match_reel.py", "src/tennislive/video/explainer.py"):
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            assert not line.startswith("import edge_tts"), (
                f"{path} 里 edge_tts 是模块级 import，挂 CA 再早也来不及了")

    # ① 这台机器没有代理 CA（＝runner）：no-op，而且**一个字都不打**。
    #    恒真的告警会把真正该看见的那次淹掉。
    monkeypatch.setattr(localca, "_done", None)
    monkeypatch.setattr(localca, "_WELL_KNOWN", (str(tmp_path / "nope.crt"),))
    monkeypatch.delenv("TENNISLIVE_EXTRA_CA", raising=False)
    capsys.readouterr()
    assert localca.trust_local_proxy_ca() is None
    assert capsys.readouterr().out == "", "runner 上不该出声"

    # ② 有 CA：三处都要设——requests / 标准库 / edge-tts 各认各的，
    #    只设一处的样子是「有的能通有的不通」，比全都不通更难查。
    ca = tmp_path / "proxy.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n")
    monkeypatch.setattr(localca, "_done", None)
    monkeypatch.setattr(localca, "_CACHE", tmp_path / "bundle.pem")
    monkeypatch.setenv("TENNISLIVE_EXTRA_CA", str(ca))
    got = localca.trust_local_proxy_ca()
    import certifi  # noqa: PLC0415
    assert got == os.environ["SSL_CERT_FILE"] == os.environ["REQUESTS_CA_BUNDLE"]
    assert certifi.where() == got, "edge-tts 认的是 certifi.where()，它没被指过来"
    merged = Path(got).read_text(encoding="utf-8")
    assert "ZmFrZQ==" in merged and "BEGIN CERTIFICATE" in merged
    assert len(merged) > len(ca.read_text(encoding="utf-8")), (
        "只写了代理那张，原来的根证书全丢了——那会把别的站点全部弄不通")

    # ③ 显式指了却不存在＝**配错了**，不是「这台机器没有」。悄悄 no-op 的话，
    #    「配了没生效」和「本来就没配」长得一模一样。
    monkeypatch.setattr(localca, "_done", None)
    monkeypatch.setenv("TENNISLIVE_EXTRA_CA", str(tmp_path / "missing.crt"))
    try:
        localca.trust_local_proxy_ca()
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("配错了路径却不吭声")


def test_探代理CA不许把CLI带崩(monkeypatch):
    """⚠️ **`Path.is_file()` 会抛，不是只返回 False。**

    它只吞 ENOENT / ENOTDIR / EBADF / ELOOP 那几类，**不吞 EACCES**——而 runner
    上跑测试的用户根本进不去 `/root`，于是 `os.stat('/root/.ccr/ca-bundle.crt')`
    抛的是 `PermissionError`。

    而这个探测排在 `main()` 的**第一行**，所以它一抛就是**每一次 CLI 调用都崩**：
    整条 match-reel 会死在还没解析参数的时候。CI 当场逮到（run 30971701644，
    两条 dry-run 测试红在 `PermissionError: '/root/.ccr/ca-bundle.crt'`）——
    也就是说这个「本地跑得好好的」改动，会在 runner 上打爆所有出片。

    **探一个「众所周知的位置」失败就等于这台机器没有它**，任何 OSError 都一样：
    这条路只是猜，猜不中是常态。显式配的那条不同，那儿配错了要报（见上一条）。

    ⚠️ 判据不能靠 `chmod 000` 造场景——沙箱里跑测试的是 root，而 **root 绕过
    权限检查**，那样造出来的「不可读」在这儿是可读的，测试会因为错误的原因变绿。
    所以直接让 `is_file` 抛，那才是 runner 上真实发生的事。
    """
    from tennislive import localca  # noqa: PLC0415

    monkeypatch.setattr(localca, "_done", None)
    monkeypatch.setattr(localca, "_WELL_KNOWN", ("/root/.ccr/ca-bundle.crt",))
    monkeypatch.delenv("TENNISLIVE_EXTRA_CA", raising=False)

    real = Path.is_file

    def boom(self):
        if str(self).startswith("/root/"):
            raise PermissionError(13, "Permission denied")
        return real(self)

    monkeypatch.setattr(Path, "is_file", boom)
    assert localca.trust_local_proxy_ca() is None, (
        "探不到就该当成「这台机器没有」，不许把异常抛给调用方——"
        "它排在 main() 第一行，抛一次就是所有 CLI 调用全崩")


def test_挂CA那句话不许替合语音打包票(monkeypatch, capsys, tmp_path):
    """**它挂的是证书链，不是「本地能合语音」。这两件事会分叉。**

    原来那句是 `挂上代理 CA…；本地也能合语音了`。2026-08-06 实测它是假的：

        can_verify()      → (True, '握手通过')          ← 证书链这一关过了
        --check-narration → WSServerHandshakeError: 403 ← 应用层把 WSS 端点挡了

    也就是**代理放行 TLS、拦住那个 WebSocket**，跟证书一点关系没有。而那句话
    印在每一次 CLI 调用的第一行，下一个人看见它就不会再去跑 `mode=narration`
    ——CLAUDE.md 里「没量过的推断写进文档，之后每个人都拿它当判据」栽过一次，
    这是同一个形状搬进了 stdout。

    所以判据只有一条、而且很窄：**这句话只许说它自己做完的那一步**。
    它一个 `edge_tts` 都没 import，凭什么替 TTS 打包票。
    """
    import certifi  # noqa: PLC0415

    from tennislive import localca  # noqa: PLC0415

    ca = tmp_path / "proxy.crt"
    ca.write_text("-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n")
    # ⚠️ `trust_local_proxy_ca` 把 `certifi.where` **永久**指到自己的缓存上，
    #    而上一条测试指的是它那个 tmp_path——那个目录跑完就没了。同进程里的下一条
    #    于是死在 `FileNotFoundError`，看起来像本条测试写错了。喂一份自己的根证书。
    root = tmp_path / "roots.pem"
    root.write_text("-----BEGIN CERTIFICATE-----\ncm9vdA==\n-----END CERTIFICATE-----\n")
    monkeypatch.setattr(certifi, "where", lambda: str(root))
    monkeypatch.setattr(localca, "_done", None)
    monkeypatch.setattr(localca, "_CACHE", tmp_path / "bundle.pem")
    monkeypatch.setenv("TENNISLIVE_EXTRA_CA", str(ca))
    capsys.readouterr()
    localca.trust_local_proxy_ca()
    banner = capsys.readouterr().out

    assert str(ca) in banner and str(tmp_path / "bundle.pem") in banner, (
        "得说清楚挂的是哪张、写到哪儿了——不然出问题时无从查起")
    # ⚠️ **先把两个路径抠掉再扫。** `tmp_path` 里带着这条测试自己的名字，
    #    而名字里就有「合语音」三个字——直接扫整句话，判据会被自己的名字误伤。
    #    CLAUDE.md 里「判据扫得太宽，被自己的注释误伤」的又一个实例，只不过
    #    这次伤它的是 pytest 拿函数名拼出来的目录。
    said = banner.replace(str(ca), "").replace(str(localca._CACHE), "")
    # 这个模块碰不到 TTS，就不许在这一行里提它。
    for claim in ("合语音", "语音", "旁白", "TTS", "narration"):
        assert claim not in said, (
            f"这句话替「{claim}」打了包票，而这个模块只动证书链——"
            "证书链通了、WSS 端点被 403 挡住的情况实测存在（2026-08-06）")


def test_旁白超长的闸排在分段编码之前():
    """**撞一次这道闸，白编 50–60 秒。**

    它原来排在分段编码之后（TTS 在第 115 行、闸在 141，而 `cut_segment` 循环
    在 101），可 TTS 只要 6 秒、一个源片像素都不碰。白编的是封面海报 2.6s +
    抠图 8.4s + **分段编码 47s** + 拼接——而「旁白写长了」本来是改一行文案
    的事，代价却是一整轮六分钟。

    挪到前面之后同样这条错在开跑后一分半就报出来，而且一次把所有超出的段
    都列出来（原设计就是如此，别改一段跑一次）。
    """
    reel = _reel()
    body = _render_body(reel)
    tts = body.index("synthesize(segments")
    gate = body.index("有旁白比它那一段的画面长")
    encode = body.index("cut_segment(")
    assert tts < encode, "TTS 又排到分段编码后面了——撞闸时白编 47 秒"
    assert gate < encode, "旁白超长那道闸排在分段编码之后"


def test_段落不许写过源片末尾(monkeypatch):
    """**ffmpeg 越界时退出码是 0**，只会安安静静出一段短的。

    而每段旁白按 `seg.length`（spec 里写的长度）算偏移，所以一旦某段被悄悄
    截短，**它后面每一句解说和字幕都整体错位**——症状是「后半段配音对不上」，
    人还未必定位得到是哪一段。踩一次至少一整轮六分钟。

    `probe_duration` 本来就在 render 里算了五次，却从来没跟段落比过。
    这条**真调一次**函数，不是查源码有没有那个名字。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    assert "_check_segments_fit" in _render_body(reel), "render 没接这道检查"

    seg = _seg(reel, 0.0, 5.0)
    fake = Path("/nowhere/fake.mp4")

    # 5 秒的段配 10 秒的源片：过
    monkeypatch.setattr(reel, "probe_duration", lambda _p: 10.0)
    reel._check_segments_fit([seg], {"": fake})

    # 同一段配 3 秒的源片：必须炸，而且要说出超了多少
    monkeypatch.setattr(reel, "probe_duration", lambda _p: 3.0)
    with pytest.raises(reel.ReelError, match="超出"):
        reel._check_segments_fit([seg], {"": fake})

    # 容差：源片时长有帧级误差，卡太死会误伤贴着片尾的那一段。
    #
    # ⚠️ **基准是 `end + SEG_FADE`，不是 `end`。** 这里原来喂 4.98——那时
    # 「末段不留溶解底料」，单段就是末段，所以 5.0 秒的段配 4.98 秒的源片刚好
    # 落在容差里。2026-08-05 片尾品牌页接上之后**每个分段后面都跟着东西**
    # （下一段，或者片尾页），所以每段都要那 `SEG_FADE` 秒底料，需求变成 5.18。
    # 这条断言的**前提变了，不是它写错了**——跟着改基准，容差本身照旧验。
    need = 5.0 + reel.SEG_FADE
    monkeypatch.setattr(reel, "probe_duration", lambda _p: need - 0.02)
    reel._check_segments_fit([seg], {"": fake})

    # 而超出容差的那一头仍然要炸：差 0.2s 已经够 xfade 落到流末尾之外
    monkeypatch.setattr(reel, "probe_duration", lambda _p: need - 0.2)
    with pytest.raises(reel.ReelError, match="超出"):
        reel._check_segments_fit([seg], {"": fake})


def test_写过源片末尾这条规矩只有一处实现():
    """`--dry-run` 和 render 那道闸判的必须是**同一条**规矩。

    ⚠️ **这条测试是一次白跑的 render 换来的**（run 680，2026-08-15）。在那之前
    「段落不许写过源片末尾」写在两处，而两处的算式不一样：

        --dry-run          seg.end             > dur      ← 少算溶解底料
        _check_segments_fit  seg.end + SEG_FADE > dur

    于是 `bejlek-pliskova` 的末段（171.6–176.0s，源片 176.08s）在本地
    **报「选段这一层没有硬伤（片长）」**，到了 runner 上 render 第 2 秒当场红。

    dry-run 存在的全部意义就是「0.2 秒、在本地、把形状错拦下来」。一条它拦不住
    而 render 拦得住的规矩，把这个承诺打了个洞——**而洞的样子是「本地全绿，
    远端红」**，跟仓库里「一个数写两处必分叉」记过的那几次一模一样。

    判据钉两头：**同一个函数**（不许谁再另写一遍），而且**它真的算上了
    `SEG_FADE`**（只钉前一头的话，两处一起少算照样绿）。
    """
    import ast  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    reel = _reel()

    # ① 行为：贴着源片末尾、只差溶解底料那 0.18 秒的段，必须被认出来
    seg = _seg(reel, 0.0, 5.0)
    assert reel.segments_over_source_end([seg], {"": 5.02}), \
        "少算了 SEG_FADE：5.0s 的段配 5.02s 的源片，溶解底料取不到还说没事"
    assert not reel.segments_over_source_end([seg], {"": 5.0 + reel.SEG_FADE + 0.1}), \
        "留够底料的也被拦了，判据太宽"
    assert not reel.segments_over_source_end([seg], {"": None}), \
        "源片没探过就不该判——宁可漏报，别拿一个不存在的时长去拦"

    # ② 两处都得走这一个函数
    src = inspect.getsource(reel)
    callers = {
        node.parent_func
        for node in _calls_named(ast.parse(src), "segments_over_source_end")
    }
    assert "_check_segments_fit" in callers, "render 那道闸没走共用的那个函数"
    assert any("dry" in name or "cut" in name for name in callers), \
        f"dry-run 那条路没走共用的那个函数，调用方只有 {sorted(callers)}"

    # ③ 谁也不许在别处把这条规矩再写一遍。`seg.end` 和源片时长直接比大小的
    #    地方，只许出现在共用的那个函数里。
    tree = ast.parse(src)
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        if func.name == "segments_over_source_end":
            continue
        body = ast.get_source_segment(src, func) or ""
        body = re.sub(r'"""[\s\S]*?"""', "", body)          # docstring 里写着教训
        body = "\n".join(ln for ln in body.splitlines()
                         if not ln.lstrip().startswith("#"))
        assert not re.search(r"seg\.end\s*>\s*dur", body), \
            f"{func.name} 又把「写过源片末尾」自己写了一遍"


def test_比分板的英文名只在名里缩写姓整个留下():
    """`Elena-Gabriela Ruse` 曾经被印成 **`E. -. G. RUSE`**。

    老写法先 `replace("-", " - ")` 再按空格切，于是**连字符自己变成了一个「名」**，
    多出一个 `-.`；带连字符的姓（`Pavlyuchenkova-Smith`）同样会被拦腰切成
    `P. -. SMITH`。**两种都不报错**——渲染照常、质检照常，只有打开海报才看得见，
    正是这个仓库反复记的那种「不吭声」。

    钉两头：**名**里的连字符要缩成 `E.-G.`（不是 `E. -. G.`），**姓**里的连字符
    一个字都不许动。另外已经缩好的（第一段就带 `.`）原样放行。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    cases = {
        "Elena-Gabriela Ruse": "E.-G. RUSE",
        "Jean-Julien Rojer": "J.-J. ROJER",
        "Maja Chwalinska": "M. CHWALINSKA",
        "Alexandra Eala": "A. EALA",
        "Anastasia Pavlyuchenkova-Smith": "A. PAVLYUCHENKOVA-SMITH",
        "E.-G. Ruse": "E.-G. RUSE",
    }
    for full, want in cases.items():
        got = vp._english_display("某人", {"name_en": full}, "test")
        assert got == want, f"{full!r} 缩成了 {got!r}，应该是 {want!r}"
    assert " -." not in vp._english_display(
        "某人", {"name_en": "Elena-Gabriela Ruse"}, "test"), (
        "又出现了那个孤零零的 `-.`——连字符被当成一个名字了")


def test_赛场之上的比分板形状要在dry_run就拦下来():
    """`cover.scoreboard` 缺不缺，`--dry-run` 就要报，不许留到 runner 上。

    ⚠️ **这条测试是一次白跑的 cover run 换来的**（run 687，2026-08-15）。
    「赛场之上 solo 封面必须有 scoreboard」这条规矩当时只写在 `versus_poster`
    的渲染路径上，而那条路排在**下载源片之后**：`maria-yastremska` 漏了这个块，
    本地 `--dry-run` 报「spec 形状没问题」，到 runner 上第 84 秒才红——
    checkout、装依赖、装 Chromium、下源片全白付。

    和 `test_写过源片末尾这条规矩只有一处实现` 是同一个形状，只是那次两处**算法
    不同**、这次是**只有一处**：两种毛病的长相一模一样，都是「本地全绿，远端红」。

    判据钉四头：**拦得住**（三种缺法各一）、**不许误伤**（网球有故事那条线照旧
    走老退路）、**`validate_spec` 真的调了它**（只测行为的话，检查排在下载后面
    照样绿）、**渲染那一路走的是同一个函数**（不然又是写两处必分叉）。
    """
    import ast  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    reel = _reel()
    good = json.loads(Path("specs/reels/maria-yastremska.json").read_text("utf-8"))
    cover = good["cover"]
    assert vp.solo_scoreboard_shape_error(cover) is None, "好的那份反而被拦了"

    def _tweak(**changes):
        c = json.loads(json.dumps(cover))
        for path, value in changes.items():
            node, *rest = path.split("__")
            target, key = (c, node) if not rest else (c[node], rest[0])
            target.pop(key, None) if value is None else target.__setitem__(key, value)
        return c

    # ① 三种缺法都要拦住
    assert vp.solo_scoreboard_shape_error(_tweak(scoreboard=None)), "整块没写也放行了"
    assert vp.solo_scoreboard_shape_error(_tweak(scoreboard__court="")), \
        "`scoreboard.court` 空着也放行了"
    assert vp.solo_scoreboard_shape_error(
        _tweak(scoreboard__duration_source={"provider": "wta"})), \
        "`duration_source` 没有 url 也放行了——比赛时长会被手填"

    # ② 不许误伤：网球有故事的 solo 封面照旧走老退路，不该被这条拦
    story = _tweak(scoreboard=None)
    story["eyebrow"] = "网球有故事"
    assert vp.solo_scoreboard_shape_error(story) is None, \
        "判据扩大化了——它只管「赛场之上」这一个栏目"

    # ③ `validate_spec` 真的调了它（钉位置，不只钉行为）
    assert "_solo_scoreboard_shape(" in inspect.getsource(reel.validate_spec), \
        "validate_spec 没调这道闸——那 dry-run 就还是拦不住"
    hollow = json.loads(json.dumps(good))
    hollow["cover"].pop("scoreboard")
    with pytest.raises(reel.ReelError, match="scoreboard"):
        reel.validate_spec(hollow)

    # ④ 渲染那一路走的是同一个函数，别人不许再写一遍那句话
    poster_src = inspect.getsource(vp)
    callers = {
        node.parent_func
        for node in _calls_named(ast.parse(poster_src), "solo_scoreboard_shape_error")
    }
    assert "_solo_score_html" in callers and "_scoreboard_html" in callers, \
        f"渲染那两处没走共用的那个函数，调用方只有 {sorted(callers)}"
    for func in ast.walk(ast.parse(poster_src)):
        if not isinstance(func, ast.FunctionDef) or \
                func.name == "solo_scoreboard_shape_error":
            continue
        body = ast.get_source_segment(poster_src, func) or ""
        body = re.sub(r'"""[\s\S]*?"""', "", body)          # docstring 里写着教训
        body = "\n".join(ln for ln in body.splitlines()
                         if not ln.lstrip().startswith("#"))
        assert "cover.scoreboard 不能省略" not in body, \
            f"{func.name} 又把这条规矩自己写了一遍"


def _calls_named(tree, name: str):
    """AST 里所有对 `name` 的调用，每个挂上它所在的函数名。"""
    import ast  # noqa: PLC0415

    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == name:
                node.parent_func = func.name  # type: ignore[attr-defined]
                yield node


def _render_body(reel) -> str:
    import inspect  # noqa: PLC0415

    return inspect.getsource(reel.render)


def _seg(reel, start: float, end: float):
    """按 Segment 的真实字段构一段，缺省值从 dataclass 自己拿——
    字段增删了它跟着走，不用回来改。"""
    import dataclasses  # noqa: PLC0415

    kwargs = {}
    for f in dataclasses.fields(reel.Segment):
        if f.name == "start":
            kwargs[f.name] = start
        elif f.name == "end":
            kwargs[f.name] = end
        elif f.default is not dataclasses.MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not dataclasses.MISSING:  # type: ignore[misc]
            kwargs[f.name] = f.default_factory()  # type: ignore[misc]
        else:
            kwargs[f.name] = "" if f.type in ("str", str) else 0
    return reel.Segment(**kwargs)


def test_多源spec每一段都要说清自己从哪条源片剪(tmp_path):
    """「开球之前」是多源的常态：比赛还没打，画面只能来自两边各自的比赛。

    郑钦文 VS 塔拉鲁迪那条用了四条源片——两人各自最近的一场，加各自的高光。
    这时候「这一段从哪条源片剪」就不能有默认值：**猜错了剪出来是另一场比赛的
    画面，而画面本身不会报错**，只会静静地对不上旁白。所以少写一个 `source`
    要当场报错，并且把有哪些源列出来。

    单源的老 spec 一个字都不用改：`source_url` 那条路走空串这个键，和
    `Segment.source` 的默认值对上。
    """
    reel = _reel()

    good = tmp_path / "good.json"
    good.write_text(json.dumps({
        "slug": "t", "cover": {"versus": {}},
        "sources": {"a": "https://x/a", "b": "https://x/b"},
        "segments": [{"start": 0, "end": 1, "source": "a"},
                     {"start": 0, "end": 1, "source": "b"}],
    }), encoding="utf-8")
    assert reel.load_spec(good)["sources"]["b"] == "https://x/b"

    for bad_seg, why in (({"start": 0, "end": 1}, "漏写 source"),
                         ({"start": 0, "end": 1, "source": "c"}, "写了不存在的源")):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({
            "slug": "t", "cover": {"versus": {}},
            "sources": {"a": "https://x/a"},
            "segments": [bad_seg],
        }), encoding="utf-8")
        try:
            reel.load_spec(bad)
        except reel.ReelError as exc:
            assert "sources" in str(exc), f"{why}：报错没说清有哪些源"
        else:
            raise AssertionError(f"{why} 应当报错")

    # 单源老 spec 仍然走得通
    old = tmp_path / "old.json"
    old.write_text(json.dumps({
        "slug": "t", "cover": {"versus": {}},
        "source_url": "https://x/one",
        "segments": [{"start": 0, "end": 1}],
    }), encoding="utf-8")
    assert reel.load_spec(old)["source_url"].endswith("one")

    # 两条都不给才算缺
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"slug": "t", "cover": {}, "segments": []}),
                     encoding="utf-8")
    try:
        reel.load_spec(empty)
    except reel.ReelError as exc:
        assert "sources" in str(exc) and "source_url" in str(exc)
    else:
        raise AssertionError("既没有 sources 也没有 source_url，应当报错")


def test_每一段都要待在同一个镜头里():
    """跨场景切点的那一段中途会换镜头，而换过去的那个镜头里常常是另一个人。

    郑钦文那条第一版踩了三处，**渲染一次都没报错**：末屏那句「你定闹钟吗？」
    压在对手握拳庆祝的近景上（源片 148.2 有切点，窗口取的 144.3–150.0）；
    「往回爬」那句前两秒是对手走开的背影；巴黎那段最重的「亚洲的第一枚奥运
    网球单打金牌」整句落在维基奇身上。画面和旁白对不上不会让 ffmpeg 失败，
    只会静静地发出去。

    挑段仍然要靠眼睛看缩略图墙，这一条只拦「窗口中途换了镜头而我没看见」。
    """
    reel = _reel()
    probes = [{"url": "u://a", "scene_cuts": [10.0, 20.0]},
              {"url": "u://b", "scene_cuts": [5.0]}]
    spec = {
        "sources": {"a": "u://a", "b": "u://b"},
        "segments": [
            {"start": 11.0, "end": 19.0, "source": "a", "narration": "干净"},
            {"start": 18.0, "end": 22.0, "source": "a", "narration": "跨了"},
            {"start": 0.0, "end": 9.0, "source": "b", "narration": "也跨了"},
        ],
    }
    bad, unchecked, tails = reel.segments_straddling_cuts(spec, probes)
    assert unchecked == []
    assert [b["index"] for b in bad] == [1, 2], "跨切点的段没被抓出来"
    assert bad[0]["cuts"] == [20.0] and bad[1]["cuts"] == [5.0]
    assert tails == [], "这三段的段尾之后没有切点，不该报溶解底料"

    # 真要跨（两边是同一个人）就显式挂账，别默默跨过去
    spec["segments"][1]["crosses_cut"] = "两边都是她，只是机位换了"
    bad, _, _ = reel.segments_straddling_cuts(spec, probes)
    assert [b["index"] for b in bad] == [2]

    # **probe 给不全时不许假绿**：零命中和「全都合格」长得一模一样，
    # 所以没查成的源片要单独报出来（CLAUDE.md：空结果先自证是真空）。
    bad, unchecked, _ = reel.segments_straddling_cuts(spec, probes[:1])
    assert unchecked == ["b"], "缺 probe 的源片没有被报出来"
    assert all(b["source"] == "a" for b in bad)

    # **溶解的底料单独报，不并进上面那一档。** 段尾之后 SEG_FADE 秒是下一个
    # 接缝的底，那几秒跨了切点只是溶解里多叠进一两帧半透明的画面，和「整句
    # 旁白压在另一个人身上」差着量级。并成一档的后果是可预见的：为了压掉
    # 这条噪音去写 `crosses_cut`，把段体那条真检查一起关掉。
    near = {
        "sources": {"a": "u://a"},
        "segments": [
            {"start": 11.0, "end": 19.95, "source": "a", "narration": "尾巴跨了"},
            {"start": 11.0, "end": 12.0, "source": "a", "narration": "末段不留尾巴"},
        ],
    }
    bad, _, tails = reel.segments_straddling_cuts(near, probes)
    assert bad == [], "尾巴跨切点不该判成段体跨切点"
    assert [t["index"] for t in tails] == [0], "溶解底料跨切点没被报出来"
    assert tails[0]["cuts"] == [20.0]
    # 末段不多切，所以它后面有没有切点都不算
    near["segments"] = [near["segments"][0]]
    _, _, tails = reel.segments_straddling_cuts(near, probes)
    assert tails == [], "末段没有尾巴，不该报"


def test_成片超过git的上限要走Release而不是砍片长(tmp_path):
    """账号所有者：「我的基础要求是保证内容和画面质量，文件多大都没关系」
    「不要砍片长」。

    而 git 有个 **100 MiB 的服务端硬拒**，绕不过去。所以成片改传 GitHub
    Release 附件（单个 2 GB，公开仓库下载不计流量额度），链接写进
    `render.json`，推送那一步优先读它。原来只有超过 95 MiB 的才走这条路，
    2026-08-13 起不分体积一律走（来路见 test_成片一律走Release不进git）。

    这条盯三件事，每一件都出过同类的错：

    1. **`push_reel` 要认 Release 那条链接。** 走了 Release 之后本地那份 mp4
       就删了，按文件大小算链接会直接炸；更坏的一种是算出一个 raw 链接发出去
       ——那个路径上根本没有文件，微信里是个 404，而消息收不回来。
    2. **上传要排在提交之前**，删本地文件也是。排在之后的话，那 100 多 MiB
       会先被 `git add` 吃进去，push 照样被拒——「闸装在哪一步」那条。
    3. **两条落脚点都要认。** `mode=push` 的预检只认仓库那条的话，走了 Release
       的片子会被判成「还没渲」。
    """
    import yaml  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    outdir = tmp_path / "output" / "2026-08-02" / "reel" / "x"
    outdir.mkdir(parents=True)
    (outdir / "render.json").write_text(json.dumps({
        "film_seconds": 220.0,
        "video_url": "https://github.com/o/r/releases/download/reel-x/x.mp4",
    }), encoding="utf-8")
    # 本地那份 mp4 **不存在**——走了 Release 就是这个状态
    assert push_reel.released_video_url(outdir).endswith("/x.mp4")
    assert push_reel.video_url(outdir, "x.mp4") == push_reel.released_video_url(outdir), \
        "video_url 没有优先用 Release 那条链接"

    # 没写 video_url 的（存量的十几条片子）照旧按仓库路径算，一个字都别动
    (outdir / "render.json").write_text(json.dumps({"film_seconds": 100.0}),
                                        encoding="utf-8")
    (outdir / "x.mp4").write_bytes(b"0" * (30 * 1024 * 1024))
    assert "raw.githubusercontent.com" in push_reel.video_url(outdir, "x.mp4")

    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)
    release = next(i for i, n in enumerate(names) if n.startswith("成片发到 Release"))
    clean = next(i for i, n in enumerate(names) if n.startswith("丢掉不进仓库"))
    commit = next(i for i, n in enumerate(names) if n.startswith("提交产物"))
    assert release < clean < commit, \
        f"上传 Release 排在了提交之后（{release} / {clean} / {commit}）"

    spec = yaml.safe_load(text)
    steps = {s.get("name", ""): s for s in spec["jobs"]["reel"]["steps"]}
    step = next(s for n, s in steps.items() if n.startswith("成片发到 Release"))
    assert "gh release upload" in step["run"]
    assert 'rm -f "$REEL"' in step["run"], \
        "传完没把本地那份删掉，它还会被 git add 吃进去"
    assert step.get("if") == "github.event.inputs.mode == 'render'"

    pre = next(s for n, s in steps.items() if n.startswith("push 模式先确认"))
    assert "video_url" in pre["run"], \
        "预检只认仓库那条，走 Release 的片子会被判成没渲"


def test_成片一律走Release不进git():
    """账号所有者 2026-08-13：「当前代码库太大了，好多资源是不是不用放在这里
    代码库里」。

    量出来 .git 已 6.0 GB，其中 **4.93 GB 是 mp4 blob（130 个）**。根因是
    Release 那一步原来只在成片超过 95 MiB 时才走：成片普遍 30~80 MiB，
    **从来够不着门槛**，于是「太大才走 Release」在真实数据上几乎一次都没
    走到，每条成片都进了 git，仓库每月胖一两个 GB——一个几乎从来走不到的
    兜底，正是「兜底出事的时候不吭声」的形状。存量动不了（▶ 链接钉在 main
    的文件路径上，已发的微信消息收不回来），只改增量：**以后一律走 Release，
    不再进 git**。

    判据钉四头，少一头就会退回老样子：

    1. Release 那一步**没有体积早退**——去注释后不许出现 `LIMIT=`、不许出现
       「不到 95」那类放行分支。体积闸一回来，95 MiB 以下（也就是几乎全部
       成片）又开始进 git。`SZ=$(stat …)` 要留着：`render.json` 的
       `video_bytes` 从它来
    2. `gh release upload` 还在——别把闸拆成「谁都不传」
    3. `rm -f "$REEL"` 还在——不删，下面的 `git add` 照样把它吃进去，白传一趟
    4. 「丢掉不进仓库的中间物」不再给 `$SLUG.mp4` 留白名单 continue——
       成片在上一步就该被发走并删掉，仍然出现在清理这一步就是漏网
       （Release 步骤被跳过或拆掉），8 MB 兜底要当场拦红，而那行白名单
       正是让它静默溜进提交的口子

    ⚠️ 判据宁可窄：`_step_block` 已经先去掉整行注释——两步的注释里都如实
    记着旧门槛那段来路（95、LIMIT 这些词都在），连注释一起扫会被自己的
    注释误伤，这个仓库同一个形状犯过五次。
    """
    release = _step_block("成片发到 Release（不进 git）")
    # ① 没有体积早退
    assert "LIMIT=" not in release, \
        "体积闸回来了——成片普遍 30~80 MiB 够不着门槛，会重新进 git"
    assert "不到 95" not in release and "照旧进仓库" not in release, \
        "「不够大就放行」的早退分支回来了"
    assert 'SZ=$(stat -c%s "$REEL")' in release, \
        "SZ 没了——render.json 的 video_bytes 从它来，别连它一起删"
    # ② 还在传
    assert "gh release upload" in release, \
        "这一步不传 Release 附件了？成片就没有落脚点了"
    # ③ 传完删本地那份
    assert 'rm -f "$REEL"' in release, \
        "传完没把本地那份删掉，它还会被 git add 吃进去"
    # ④ 清理兜底不再给成片开白名单
    cleanup = _step_block("丢掉不进仓库的中间物")
    assert "$SLUG.mp4" not in cleanup, (
        "清理兜底又提到成片了——它该在上一步就被发走并删掉；留白名单等于"
        "给「Release 步骤被跳过、成片静默进仓库」开口子，漏网就该被 8 MB "
        "兜底拦红")


# 规矩定下来**之前**已经发出去的那批文件。已发的片子不为了措辞重渲
# （那条规矩在别处），所以它们挂在这儿——**只许减不许加**：新写的 spec 要么
# 用新叫法，要么显式把自己加进来，让「又用了旧叫法」变成一次看得见的决定。
from tools.spec_wording import (  # noqa: E402
    FRACTION_ROUND_LEGACY as _LEGACY_ROUND_NAMES,
)


# 规矩定下来**之前**已经发出去的封面。已发的片子不为了这个重渲，所以它们
# 挂在这儿——**只许减不许加**。
_LEGACY_NO_FLAG = {
    "eala-fernandez.json", "eala-svitolina.json", "eala-zheng.json",
    "hewitt-washington.json", "nishikori-shang.json", "potapova-venus.json",
    "wang-pareja.json", "wang-samsonova.json", "wong-brooksby.json",
    "wong-gea.json", "wong-lehecka.json", "zheng-lanlana.json",
}


def test_封面上每个球员都要有国旗和即时排名():
    """账号所有者 2026-08-02：「以后封面上所有球员的名字旁边要加上他的国旗，
    对阵的同时在后面括号里面加上他的即时的世界排名」。

    两样都必填，因为**漏掉的失败方式都不吭声**：没有国旗，海报看着只是「少了点
    什么」；没有排名，读者没法判断这场胜利有多重——伊埃拉赢大坂，是 28 赢 13，
    不是随便两个人。

    `rank` 允许显式 `null`＝「查过，他没有排名」（资格赛、掉出榜单）。
    和 `mixed_fps` / `silent_source` 一样：**认领这一步把「查过没有」和「忘了填」
    分开**，漏写这个键会报错，写 null 会渲成只有国旗和名字并且在日志里出声。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415

    missing = {}
    checked = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        if path.name in _LEGACY_NO_FLAG:
            continue
        cover = json.loads(path.read_text(encoding="utf-8")).get("cover") or {}
        # **单人封面没有名条**（`_solo_body` 只有照片 + 药丸 + 钩子，
        # 一个球员名都不印），所以「名字旁边加国旗和排名」这条规矩管不到它。
        # 账号所有者的原话本来就是「**对阵**的同时在后面括号里面加上排名」。
        # 判据宁可窄，不可宽：扫到 solo 上只会逼下一个人往一张没有名字的
        # 海报里塞两个查不到用处的字段。
        if cover.get("layout") == "solo":
            continue
        versus = cover.get("versus") or {}
        checked += 1
        for side in ("top", "bottom"):
            panel = versus.get(side) or {}
            gaps = [k for k in ("country", "rank") if k not in panel]
            if gaps:
                missing.setdefault(path.name, []).append(f"{side} 缺 {gaps}")
    assert not missing, f"封面缺国旗/排名：{missing}"
    # **判据自己的判据**：上面那两个 `continue` 一旦写宽（比如把整族 spec
    # 都跳过），这条测试会变成一盏恒真的绿灯而不出声。
    assert checked >= 1, "一条对阵封面都没校到——是不是跳过的条件写宽了？"

    # 行为：给全了就渲出「旗 + 名 +（排名）」
    html = versus_poster._name_html("伊埃拉", {"country": "PHI", "rank": 28}, "t")
    assert "\U0001F1F5\U0001F1ED" in html, "国旗没渲出来"
    assert "（28）" in html, "排名没进括号"
    # 显式 null：只有旗和名，不报错
    assert "（" not in versus_poster._name_html("某人", {"country": "PHI", "rank": None}, "t")
    # 漏写：两个键各自都要报错，而且要说清出路
    import pytest  # noqa: PLC0415

    with pytest.raises(SystemExit, match="country"):
        versus_poster._name_html("某人", {"rank": 1}, "versus.top")
    with pytest.raises(SystemExit) as err:
        versus_poster._name_html("某人", {"country": "PHI"}, "versus.top")
    assert "null" in str(err.value), "报错没说「查过没有就写 null」这条出路"


def _rank_claims(text: str) -> list[int]:
    """把一段文案里**声称的排名**抠出来（阿拉伯和汉字都认）。

    ⚠️ **只认「世界第N」「世界排名N」「排名…N」这三种说法**，别放宽：

    - `第N号种子` / `N号种子` 是**种子序号不是排名**。卢布列夫在蒙特利尔是
      十号种子、世界第十六——两个数都对，混成一件事就成了假话
    - 「第一次打进四强」「两个盘点」里的数跟排名无关，扫进来只会误伤

    判据宁可窄，不可宽：扩大化的判据不吭声，它不会说「我拦错了」，
    只会让下一个人把对的写法改成错的。
    """
    import re  # noqa: PLC0415

    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video.explainer import _num_value  # noqa: PLC0415

    out: list[int] = []
    # 「排名」和数字之间允许隔一个动词（掉到 / 升到 / 来到 / 是），
    # 但**不允许隔任意字符**——隔开了就未必还在说同一件事
    pat = re.compile(r"(?:世界第|世界排名|排名(?:掉到|升到|来到|是)?)"
                     r"\s*([0-9]+|[一二三四五六七八九十百千两]+)")
    for m in pat.finditer(text):
        run = m.group(1)
        if run.isdigit():
            out.append(int(run))
            continue
        value = _num_value(run)
        # 读不出来（比如「排名最高」被切到「高」）就跳过，别猜
        if value is not None:
            out.append(int(value))
    return out


def test_钩子和文案里写的排名要和matchup对得上():
    """账号所有者 2026-08-05：「主要是封面选图和文案要**贴近比赛事实**，
    且有吸引力」。

    这条测的是**前半句里能量出来的那一半**：钩子和推送文案里写的排名，必须
    和 `cover.matchup` / `cover.versus` 里登记的那个数一样。后半句「有吸引力」
    是判断题，故意没有测试——理由写在 CLAUDE.md 里。

    **这不是假想的风险，是当天差点发出去的错**：查卢布列夫排名时我读的是
    维基百科榜单里的**变化列**，得出「世界第九」，而他是**第十六**。
    海报的名条从 `matchup` 渲，钩子是手写的——**两个出处**，于是那一版海报
    会在同一张图上把同一个人写成两个名次，而**渲染、质检、全量测试一律不出声**。

    ⚠️ 只校**登记过排名**的那些 spec。老片子（`_LEGACY_NO_FLAG` 那一批）
    连 `matchup` 都没有，没有基准可比——**跳过它们不等于放过**：新写的封面
    从 2026-08-02 起一律要填国旗和排名，所以这道闸对以后每一条都成立。

    ⚠️ **只扫钩子和 `push.summary`，不扫 `lead` 和小红书正文。** 第一版把四个
    出口一起扫了，当场四条全红——**四条全是误伤**：伊埃拉正文里的「世界第 140」
    是 2025 年迈阿密那一周的她，霍达尔正文里的「世界第 8」是德米纳尔，张帅
    `lead` 里的「五百九十五」是 2024 年夏天。

    分界不是「哪个字段更重要」，是**这句话有没有地方放上下文**：钩子 27 字、
    `summary` 20 字位，塞不下第三个人也塞不下年份，所以里面的排名**必然**是
    这两个人的当期名次；正文有几百字，同一个说法在那儿完全可以是三年前的。
    又一次「判据宁可窄，不可宽」——扫宽了它不会说「我拦错了」。
    """
    checked = 0
    bad: dict[str, str] = {}
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        cover = spec.get("cover") or {}
        registered: set[int] = set()
        for who in cover.get("matchup") or []:
            if isinstance(who, dict) and isinstance(who.get("rank"), int):
                registered.add(who["rank"])
        versus = cover.get("versus") or {}
        for side in ("top", "bottom"):
            panel = versus.get(side) or {}
            if isinstance(panel.get("rank"), int):
                registered.add(panel["rank"])
        if not registered:
            continue

        push = spec.get("push") or {}
        texts = {"cover.hook": str(cover.get("hook", "")),
                 "push.summary": str(push.get("summary", ""))}
        for where, text in texts.items():
            for claimed in _rank_claims(text):
                checked += 1
                if claimed not in registered:
                    bad[f"{path.name}:{where}"] = (
                        f"写着世界第 {claimed}，而 matchup 登记的是 "
                        f"{sorted(registered)}")
    assert not bad, f"钩子/文案里的排名和 matchup 对不上：{bad}"
    # **判据自己的判据。** 上面两个 `continue` 一旦写宽，或者 `_rank_claims`
    # 的正则写死，这条测试会变成一盏恒真的绿灯——而它拦的正是「不吭声」那一类。
    assert checked >= 1, "一处排名都没校到——是不是跳过的条件或正则写宽了？"

    # 抠取本身要正反都对：认得出该认的，也不许把种子序号当排名
    assert _rank_claims("他掀翻了世界第十六") == [16]
    assert _rank_claims("排名掉到两百七十") == [270]
    assert _rank_claims("落后一盘，隔夜掀翻世界第 3") == [3]
    assert _rank_claims("这一站的十号种子卢布列夫") == [], "种子序号被当成了排名"
    assert _rank_claims("第一次打进四强，两个盘点都救了") == []


def test_渲海报的工作流都要装emoji字体():
    """**缺了 emoji 字体不报错。** Chromium 回退到没有旗帜字形的字体，
    🇵🇭 渲成两个方框或者裸的「PH」两个字母，海报照样出得来、工作流照样绿。

    判据不数包名，**按「谁渲海报」自动推**：凡是 run 脚本里出现
    `versus_poster` / `build_match_reel` 的工作流，apt 行就必须带
    `fonts-noto-color-emoji`。这样以后多一条出海报的线，它会替人记得。
    """
    import re  # noqa: PLC0415

    for path in sorted(Path(".github/workflows").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        runs = "\n".join(re.findall(r"^\s*run:\s*\|?(.*(?:\n(?:\s{2,}).*)*)",
                                    text, re.M))
        runs = "\n".join(ln for ln in runs.splitlines()
                          if not ln.lstrip().startswith("#"))
        if not any(k in runs for k in ("versus_poster", "build_match_reel.py")):
            continue
        assert "fonts-noto-color-emoji" in runs, (
            f"{path.name} 渲海报却没装 fonts-noto-color-emoji——"
            "国旗会悄悄变成方框，而这一步不会红")


def test_轮次写N强不写分数式():
    """账号所有者 2026-09-01：「**以后，8 强、4 强、决赛，这种这样说，
    不要说 1/4 决赛和什么 1/8 决赛之类的了。**」

    ⚠️ 这条**整个翻了个面**，判据的形状没变、主语换了。2026-08-02 他定的是
    反过来的那一套（「以后不要用四强八强之类的，国内通常用半决赛 1／4 决赛
    1/8 决赛之类的」），这条测试当年叫 `test_轮次要写半决赛不写四强`、拦的是
    「四强/八强/十六强」。今天拦的是旧那套，放行的是「N 强」——和
    `test_赛场之上的封面一律用solo`（2026-08-04 把 solo 从例外翻成默认）
    是同一个形状：**闸原样翻面，不是新增一条**。

    「半决赛」也在拦的范围里：他列的三档（8 强 / 4 强 / 决赛）里「4 强」正是
    这一档，不拦它的话同一个账号会把同一轮叫两个名字。「决赛」两套叫法相同，
    不动；32 强再往前照旧写「第几轮」（那半条没被推翻）。

    **只查会发出去的字段**——旁白、封面上印的字、推送那几栏、小红书文案。
    `_source` / `_why` / `_match` 这些是写给下一个人看的注解，里面正引着账号
    所有者那两句原话（含被废掉的旧叫法），连它一起扫就会把「把规矩记下来」
    判成「又违反了规矩」——同一个错在这个仓库里犯过三次。
    """
    # 正则/扫描面的单一出处在 tools/spec_wording.py（validate_spec 和
    # promote_reel_draft 用同一份——自动链在发布前也执行这批判据）。
    # ⚠️ outward_deep 必须包含 push 的非注解字段：第一版这儿读的是
    # `_push`，真正发进微信的 `push.summary`/`push.lead` 一条都没被
    # 扫到——判据的主语错了，而它绿着。
    from tools.spec_wording import FRACTION_ROUND as bad  # noqa: PLC0415
    from tools.spec_wording import outward_deep as outward  # noqa: PLC0415

    offenders = {}
    for path in sorted(Path("specs/reels").glob("*.json")):
        hits = sorted({m.group(0) for text in outward(
            json.loads(path.read_text(encoding="utf-8"))) for m in bad.finditer(text)})
        if hits:
            offenders[path.name] = hits
    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        hits = sorted({m.group(0)
                       for m in bad.finditer(path.read_text(encoding="utf-8"))})
        if hits:
            offenders[path.name] = hits

    fresh = {k: v for k, v in offenders.items() if k not in _LEGACY_ROUND_NAMES}
    assert not fresh, (
        f"这些地方还在写分数式轮次或「半决赛」：{fresh}。"
        "改成 8 强 / 4 强 / 决赛，再往前写「第几轮」。")
    # **清单只许减不许加**：修好一个就从上面删掉一个，别让它变成一张许可证
    assert set(offenders) <= _LEGACY_ROUND_NAMES, "清单里有已经修好的条目？"


def test_轮次那道闸要盖住烧在画面上的顶栏():
    """`topbar.line1` 写的就是「<年> <赛事> <轮次>」，**整个比赛段一直烧在
    画面上**——它比封面那一行还显眼，是这条规矩最该盖住的一面。

    ⚠️ 而它 2026-09-01 之前不在扫描面里：`outward_deep` 只收 segments /
    cover / push，于是 `promote_reel_draft` 往 line1 写一句「半决赛」照样过闸。
    补它的代价当场量过是**零**——46 条 topbar 带旧写法的 spec 全部已经在豁免
    表里（它们的 `cover.topic` 也写着同一句），「爱局」在 topbar 里零命中。

    判据钉两头，缺一头都是恒真：**topbar 真的在扫描面里**（拿一条只在 topbar
    里犯规的 spec 验，只钉这头的话把 line2 也收进来照样绿），
    **而注解（`_` 开头）不许被扫**（这个仓库为「判据扫得太宽、被自己的注释
    误伤」栽过五次）。
    """
    from tools.spec_wording import FRACTION_ROUND as bad  # noqa: PLC0415
    from tools.spec_wording import outward_deep as outward  # noqa: PLC0415

    only_topbar = {"topbar": {"line1": "2026 辛辛那提 ATP1000 1/8决赛",
                              "line2": "甲 6-4 6-4 乙"}}
    assert any(bad.search(t) for t in outward(only_topbar)), \
        "topbar.line1 烧在画面上，轮次那道闸必须扫得到它"

    annotated = {"topbar": {"line1": "2026 辛辛那提 ATP1000 8强",
                            "_line1_why": "原来写的是 1/8 决赛，2026-09-01 翻面"}}
    assert not any(bad.search(t) for t in outward(annotated)), \
        "`_` 开头的是写给下一个人看的注解，扫它等于把「把规矩记下来」判成违规"


def test_自动链写进封面的轮次要先过对外写法那张表():
    """内部那两套轮次名（`zh.terms.round_zh`、`oncourt_feed.parse_round`）产出的
    是「半决赛」「四分之一决赛」，而它们经 `promote_reel_draft` 的
    `cover.topic` / `topbar.line1`、`promote_interview_draft` 的 `cover.sub`
    **流进会发出去的字段**。

    ⚠️ 翻面之后不转换的话，**自动链产的每一条草稿都会被同一个文件里那道零豁免
    的措辞闸拦下**——草稿转不了正，链子静静卡住，而它和「今天没有候选」长得
    一模一样（本文件反复记的「走不到的路怎么查都是绿的」的反面：这次是走得到，
    而且每次都撞）。

    ⚠️ **只转换出口，不改内部的键**：「半决赛」在 `KEY_ROUNDS`、排序表、覆盖率
    表、`LEAD_ROUND_PTS` 里是当**标识符**用的，跟着改是拿一条文案规矩去动一批
    不相干的判据，而那种改动坏起来不吭声。

    判据钉三头：转换表本身对得上、**两个出口真的调了它**（只钉转换表的话，
    出口忘了调照样绿——「一个数写两处必分叉」的老账）、认不出的原样透出去
    （别在转换器里猜写法，让闸去拦）。
    """
    import ast  # noqa: PLC0415

    from tools.spec_wording import FRACTION_ROUND as bad  # noqa: PLC0415
    from tools.spec_wording import round_display  # noqa: PLC0415

    # ① 两套内部轮次名的产出，转换之后都要过得了闸
    from tennislive.zh.terms import round_zh  # noqa: PLC0415
    from tools.oncourt_feed import parse_round  # noqa: PLC0415
    produced = {round_zh(x) for x in
                ("SF", "QF", "R16", "R32", "Final", "Semifinal", "Quarterfinal",
                 "Round of 16", "Round of 32", "1st Round")}
    produced |= {parse_round({"title": f"On-Court Interview | Event 2026 {x}"})
                 for x in ("Final", "Semi-Final", "Quarter-Final", "Round of 16",
                           "Third Round", "Second Round", "First Round")}
    for label in sorted(filter(None, produced)):
        out = round_display(label)
        assert not bad.search(out), (
            f"内部轮次名「{label}」转出来还是「{out}」——会被措辞闸拦下，"
            f"自动链的草稿转不了正")
    # 他点名的那三档要转成他要的那三个词
    assert round_display("半决赛") == "4强"
    assert round_display("四分之一决赛") == "8强"
    assert round_display("决赛") == "决赛"
    # 认不出来的原样透出去（资格赛、第几轮、英文原文都从这条走）
    for passthrough in ("决赛", "第一轮", "资格赛", "小组赛", "Round Robin", ""):
        assert round_display(passthrough) == passthrough

    # ② 两个出口真的调了它——只验 ① 的话，出口忘了调照样绿
    for tool, field in (("promote_reel_draft.py", "cover.topic / topbar.line1"),
                        ("promote_interview_draft.py", "cover.sub")):
        src = (Path("tools") / tool).read_text(encoding="utf-8")
        tree = ast.parse(src)
        called = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                     and n.func.id == "round_display" for n in ast.walk(tree))
        assert called, (
            f"tools/{tool} 往 {field} 写轮次，必须先过 round_display()——"
            f"不然自动链的草稿会被措辞闸拦下")


def test_零封的局不许翻译成爱局():
    """账号所有者 2026-08-24：「以后 love game 不要翻译成中文。记录下来」。

    来路：`gauff-pegula-cincinnati-2026-final` 已发的旁白和小红书正文里，
    「一局对手一分未得」被字面直译成了**「爱局」**——`love` 在网球计分里是
    「零」，不是「爱」，读起来像在说一个浪漫的局，和术语毫无关系。逐分
    （15:0/30:0/40:0）本身已经把「零封」讲清楚了，不需要再造一个字面翻译的
    标签。**要收尾用一个词，选「零封」，别选任何带「爱」字的直译。**

    只查会发出去的字段（旁白 / 封面 / 推送 / 小红书正文），和
    `test_轮次写N强不写分数式` 同一套 `outward()`——`_why` 这类写给下一个人
    看的注解允许提到「爱局」这个反例本身，不算违规。
    """
    from tools.spec_wording import LOVE_GAME as bad  # noqa: PLC0415
    from tools.spec_wording import outward_deep as outward  # noqa: PLC0415

    offenders = {}
    for path in sorted(Path("specs/reels").glob("*.json")):
        hits = sorted({m.group(0) for text in outward(
            json.loads(path.read_text(encoding="utf-8"))) for m in bad.finditer(text)})
        if hits:
            offenders[path.name] = hits
    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        hits = sorted({m.group(0)
                       for m in bad.finditer(path.read_text(encoding="utf-8"))})
        if hits:
            offenders[path.name] = hits

    assert not offenders, (
        f"这些地方把 love game 字面直译成了「爱局」：{offenders}。"
        "改成「零封」，或者直接靠前面的逐分（15:0/30:0/40:0）讲清楚，不用另造标签。")


#: 规矩之前就发出去的片子。账号所有者 2026-08-06：「**历史视频就不要那个管了**」
#: 「**保证以后正常就行**」——微信那条消息收不回来，不为一个动词重渲。
#: **只许减不许加**，而且下面有自检：写错一个名字，豁免就成了一盏恒真的绿灯。
from tools.spec_wording import YAODAO_LEGACY as _LEGACY_YAODAO  # noqa: E402


def test_小红书正文不许用markdown():
    """账号所有者 2026-08-06：「**正文里复制的内容，不要用 markdown 格式，复制过去
    显示会有问题**」。

    `.xhs.txt` 是**给人复制走的纯文本**——复制页那个 `<textarea>` 和微信正文都不过
    markdown 渲染器。所以 `**加粗**` 粘到小红书里就是**原样的四个星号**，
    表格那几行竖线更是一堆乱码。

    ⚠️ **这条和「画面上不写标点」是一家的**：都不是排版洁癖，都是「出口不渲染这个
    记号」。当天扫下来八个文件里有 `**` 共 80 处，还有一处 `>` 引用块。

    ⚠️ **判据只认出口不渲染、粘过去会露出来的那几种记号**：星号、反引号、下划线
    强调、表格竖线、`# ` 标题、`> ` 引用、`[]()` 链接。**不管 `-` 开头的行**——
    那粘过去就是一个横杠，读起来正常。判据宁可窄，不可宽。

    ⚠️ tag 行 `#网球时差` 不许误伤：`#` 后面没有空格，和 markdown 的 ATX 标题
    （`# ` 必须带空格）分得开。反向验证里专门有这一条。
    """
    import re  # noqa: PLC0415

    marks = (
        ("星号（**加粗** / *斜体*）", re.compile(r"\*")),
        ("反引号", re.compile(r"`")),
        ("下划线强调 __", re.compile(r"__")),
        ("表格竖线", re.compile(r"^\s*\|", re.M)),
        ("# 标题", re.compile(r"^#{1,6}\s", re.M)),
        ("> 引用", re.compile(r"^>\s", re.M)),
        ("[]() 链接", re.compile(r"\[[^\]]*\]\([^)]*\)")),
    )

    offenders, checked = {}, 0
    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        checked += 1
        text = path.read_text(encoding="utf-8")
        hits = [f"{name}×{len(pat.findall(text))}"
                for name, pat in marks if pat.search(text)]
        if hits:
            offenders[path.name] = hits
    assert checked >= 15, f"只扫到 {checked} 份文案——目录写错了？"
    assert not offenders, (
        f"这几份文案里还有 markdown 记号：{offenders}。"
        "`.xhs.txt` 是给人复制走的纯文本，出口不渲染 markdown，粘过去会原样露出来。")


def test_破发点盘点赛点一律写拿到不写要到():
    """账号所有者 2026-08-06：「**以后不要用「要到」，都用「拿到」**」。

    这是同一条规矩的第二次。第一次是 shang-rublev 那条被读者当众吐槽
    （「什么叫 三个盘点都没救下来」），当时账号所有者的原话就是「改成卢布列夫
    **拿到**三个盘点」——我改了那一条，**没把它变成规矩**，于是 zverev-griekspoor
    又写了一次「一口气要到三个破发点」。CLAUDE.md 里「规矩要落成测试，别只写在
    文档里」说的正是这个。

    ⚠️ **判据只认「点」那个语义，不禁「要到」这个词。** 中文里
    「巡回赛这条线**要到** 2033 年才走完」「**要到** 9-7 必经 7-7」都是对的，
    那是「直到／需要达到」，跟破发点没关系。扫得宽一点就会把这些一起判红——
    「判据宁可窄，不可宽」这个仓库犯过五次。

    ⚠️ 和上面那条一样**只查会发出去的字段**：`_why` / `_facts` 里正引着账号
    所有者这句原话和当年那个错写法，连注解一起扫就是把「记下来」判成「又犯了」。
    """
    from tools.spec_wording import YAODAO_POINT as bad  # noqa: PLC0415
    from tools.spec_wording import outward_flat as outward  # noqa: PLC0415

    offenders = {}
    for path in sorted(Path("specs/reels").glob("*.json")):
        hits = sorted({m.group(0) for text in outward(
            json.loads(path.read_text(encoding="utf-8"))) for m in bad.finditer(text)})
        if hits:
            offenders[path.name] = hits
    for path in sorted(Path("specs/reels").glob("*.xhs.txt")):
        hits = sorted({m.group(0)
                       for m in bad.finditer(path.read_text(encoding="utf-8"))})
        if hits:
            offenders[path.name] = hits

    fresh = {k: v for k, v in offenders.items() if k not in _LEGACY_YAODAO}
    assert not fresh, (
        f"这几处还在写「要到」：{fresh}。破发点／盘点／赛点一律写「拿到」。")
    # **豁免表要自证它豁免的是真的**：名字写错的话它什么也没拦，而测试照样绿。
    assert set(_LEGACY_YAODAO) <= set(offenders), (
        f"豁免表里这几条已经不含「要到…点」了，删掉：{set(_LEGACY_YAODAO) - set(offenders)}")


def test_重放不许把已经删掉的成片救活():
    """push 撞车之后的重放路径**只加不减**的话，走了 Release、已经 `rm` 掉的
    成片会被 `reset --hard` 从 origin 上放回来，再也删不掉。

    run 30727483963 的日志把这件事写得清清楚楚：第一次提交是对的——
    `delete mode 100644 output/…/eala-osaka.mp4`；push 撞车（另一条提交先到），
    重放之后那条 delete 没了。结果仓库里躺着 2 分 39 秒的旧片，而真正发出去的
    是 Release 上 3 分 53 秒的那一版。**两个地址两条片子，谁也没说哪个是哪个。**

    老修法是 `rm -rf "$OUTDIR"` 先清场再整目录 checkout——**减法的范围写死在
    OUTDIR**，和「只重放 OUTDIR 会把草稿 spec 静默丢掉」是同一个洞的两面。
    现在删除由这次提交的 diff 自己说：`--diff-filter=D` 列出该提交删掉的
    每一个文件，`git rm` 把 `reset --hard` 刚救活的那份再删掉并进索引。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text[text.index("push 被拒（第 $attempt 次）"):]
    block = block[:block.index("sleep $((attempt")]
    assert "--diff-filter=D rendered^ rendered" in block, (
        "重放没把「这次提交删掉的文件」再删一遍——reset --hard 救活的旧成片"
        "会一直留在仓库里（run 30727483963）")
    assert "git rm" in block and "--ignore-unmatch" in block, (
        "删除那半要走 git rm 进索引；--ignore-unmatch 兜住"
        "「新 origin 上本来就没有它」那一支，别让重试红在一个已经了结的删除上")
    assert "--sparse" in block, (
        "稀疏检出下 git rm 不带 --sparse 动不了 cone 外的索引条目——"
        "静默陷阱和「裸 git add 只警告不报错」同族")


def test_片长不设上限而且每条spec都要报走Release(tmp_path, capsys):
    """账号所有者 2026-08-02：「我的基础要求是保证内容和画面质量，文件多大都
    没关系」「不要砍片长」「我怕故事讲解不完整」。

    **所以这条不许再拦人。** 它的前一版按 git 的 100 MiB 硬上限反推出一个片长
    上限并直接报错——那正好把账号所有者要的东西挡在门外，而且更早的一版余量
    留太狠，当场把已经发出去、实际只有 81.9 MiB 的 eala-svitolina 判成不合格。
    「判据宁可窄，不可宽」在这儿的极端形式是：**这个判据根本不该存在**，
    100 MiB 是 git 的限制，不是内容的限制，换一条路（Release 附件）就没了。

    出声那一半 2026-08-13 也跟着变了：原来按 95 MiB 分「进仓库 / 走 Release」
    两条路，而成片普遍 30~80 MiB 从来够不着门槛，几乎每条都进了 git
    （.git 6.0 GB 里 4.93 GB 是 mp4 blob，来路见
    test_成片一律走Release不进git）。现在**路只有一条**：不管估出来多大，
    load_spec 对任何 spec 都要说「走 Release 附件」——体积只是提前报出来
    给人看量级，不再决定去向。
    """
    reel = _reel()

    long_spec = {
        "source_url": "u://x",
        "cover": {},
        "segments": [{"start": 0.0, "end": 400.0, "narration": "很长"}],
    }
    tmp = tmp_path / "long.json"
    tmp.write_text(json.dumps(long_spec, ensure_ascii=False), encoding="utf-8")
    # **不许抛**——四百秒是编辑的决定，不是错误
    spec = reel.load_spec(tmp)
    seconds, _ = reel.reel_length_verdict(spec)
    assert seconds > 400
    assert "走 Release 附件" in capsys.readouterr().out, \
        "很长的 spec 没报走 Release"

    # 随便一条正常长度的 spec 也一样报 Release——不再有「不到 95 就进仓库」那一支
    short_spec = {
        "source_url": "u://x",
        "cover": {},
        "segments": [{"start": 0.0, "end": 60.0, "narration": "正常长度"}],
    }
    tmp2 = tmp_path / "short.json"
    tmp2.write_text(json.dumps(short_spec, ensure_ascii=False), encoding="utf-8")
    reel.load_spec(tmp2)
    out = capsys.readouterr().out
    assert "走 Release 附件" in out, f"正常长度的 spec 没报走 Release：{out!r}"
    assert "进仓库" not in out, f"「进仓库」那一支又回来了：{out!r}"

    # 每条 spec 都要算得出来（估体积仍然有用：提前看见量级）
    for path in sorted(Path("specs/reels").glob("*.json")):
        s, m = reel.reel_length_verdict(json.loads(path.read_text(encoding="utf-8")))
        assert s > 0 and m > 0, path.name

    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    body = src[src.index("def load_spec("):src.index("def segments_straddling_cuts(")]
    # 去掉整行注释再扫：load_spec 里那段注释正写着「一律走 Release 附件」，
    # 连注释一起扫的话，把 print 删掉它照样绿——被自己的注释满足的假绿
    code = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "走 Release 附件" in code, "load_spec 没报成片走 Release"
    assert "raise ReelError" not in body.split("[片长]")[0].split("reel_length_verdict")[-1], \
        "片长又变成一道闸了——账号所有者明说过不要砍片长"


def test_跨切点检查器对单源的赛场之上也要跑得起来(tmp_path):
    """上面那条只测了库函数；**检查器本身**对单源的 spec 从来没跑起来过。

    `check_reel_cuts.py` 打印那一行按 `seg['source']` 硬取，而 `source` 只有
    多源的 spec 才写（采访那条线）。「赛场之上」是单源，段里根本没有这个键——
    于是它在第一段就 KeyError，**一条都还没查完**。CLAUDE.md 里「每一段都要
    待在同一个镜头里」那条规矩，对整条赛场之上等于一直没有工具。

    又是「查的东西和跑的东西不是一回事」：库函数全绿（它一直用 `.get`），
    命令行入口炸——所以这一条走 subprocess，跑真的那个入口。
    """
    single = [p for p in sorted(Path("specs/reels").glob("*.json"))
              if not json.loads(p.read_text(encoding="utf-8")).get("sources")]
    assert single, "specs/reels 里一条单源的 spec 都没有？那这条测试该改了"
    spec_path = single[0]
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({"url": spec["source_url"], "duration": 300.0,
                                 "scene_cuts": []}), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": "tools"}
    out = subprocess.run([sys.executable, "tools/check_reel_cuts.py",
                          str(spec_path), str(probe)],
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, f"检查器自己炸了：\n{out.stdout}\n{out.stderr}"
    # **合格的也要列出来**：只在失败时出声的检查没法证明它真的看过每一段。
    for index in range(len(spec["segments"])):
        assert f"第 {index:>2} 段" in out.stdout, \
            f"第 {index} 段没有被列出来——检查器没查完就返回了"


def test_要发的片子必须有小红书文案():
    """推送那一步 `test -f "$COPY"` 会挡住缺文案的 slug，但那是六分钟之后的事——
    渲染、合成、拼片全跑完才发现没得发。spec 和文案是一对，缺一个就该在这儿红。
    """
    for spec in sorted(Path("specs/reels").glob("*.json")):
        copy = spec.with_suffix(".xhs.txt")
        assert copy.is_file(), f"{spec.name} 没有配套的 {copy.name}"
        assert copy.read_text(encoding="utf-8").strip(), f"{copy.name} 是空的"


def test_推送卡的台头跟着栏目走():
    """台头小药丸原来写死「赛场之上」。这个工作流现在也发「开球之前」——
    标题里的栏目名是对的，卡片上那个药丸却是另一个，两处对不上。

    和「兜底和默认值出事的时候不吭声」同一类：它不报错，只是印错。
    """
    sys.path.insert(0, "tools")
    import push_reel  # noqa: PLC0415

    import pytest  # noqa: PLC0415

    html = push_reel.build_html(
        "https://v/x.mp4", "https://p/copy.html", "",
        "标题\n\n正文一段", poster="", column="开球之前")
    assert "开球之前" in html
    assert "赛场之上" not in html, "台头还写死着别的栏目名"

    # **不留默认值**：给不出栏目名就该报错。默认一个栏目名，正是
    # 「同一条推送里两个栏目名」那个错留在原地不吭声的样子。
    with pytest.raises(TypeError):
        push_reel.build_html("https://v/x.mp4", "https://p/copy.html", "",
                             "标题\n\n正文一段")

    # 标题和药丸要取同一个值，别一个走 column_of、一个另取默认
    src = Path("tools/push_reel.py").read_text(encoding="utf-8")
    assert "column = args.column or column_of(Path(args.copy))" in src
    # ⚠️ 不锚在紧跟的 `)` 上——那道闸只在 `build_html(...)` 调用没有别的
    # 关键字参数（如后来加的 `stat_card=`）时才成立，加一个新参数就会把这条
    # 判据带崩，而它想拦的错（药丸另取默认值）跟这件事无关。
    assert re.search(r"\bcolumn=column\b", src), "药丸没和标题共用那一个栏目名"


def test_推送的文案输入不许留上一条片子的默认值():
    """`matchup` / `score` / `summary` / `push_lead` 装的是**这一条片子的文案**，
    而默认值只能是**上一条片子的文案**——不传就顶着别人的话发出去，不报错。

    2026-08-01 郑钦文那条赛前前瞻就是这么发错的：标题印着「郑钦文首轮出局」
    （上一条华盛顿赛报留下的 summary 默认值），而那场球当晚 00:30 才开打。
    **说了一件没发生的事，微信收不回来。**

    更阴的一层：**传空串盖不住默认值**。`github.event.inputs.X` 收到空串时退回
    default，所以显式传 `summary: ""` 用的还是那句旧话。唯一可靠的做法是默认值
    本身就是空的——再加一道「两个都空就别发」的闸，在第 3 秒红，而不是渲染完
    十分钟之后发出去一条错的。
    """
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    inputs = doc[True]["workflow_dispatch"]["inputs"]   # `on:` 被 yaml 读成 True
    for name in ("matchup", "score", "summary", "push_lead"):
        assert inputs[name].get("default", "") == "", (
            f"{name} 又带上了默认值 {inputs[name].get('default')!r}——"
            "那是上一条片子的文案，下一条不填就顶着它发出去")

    # ⚠️ **不许再要求「命令行上至少填一个」。** 原来有一道这样的闸，而
    # matchup / summary / lead 的正确出处是 spec（对阵从 cover.versus.names 算，
    # 其余写在 push 块里）。那道闸等于强制手打，而**手打的字任何测试都看不见**
    # ——2026-08-02 我就在输入里把「十九岁」打成了「九岁」。
    yaml_only = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    assert "inputs.matchup == ''" not in yaml_only, (
        "又要求在命令行上填标题了——那会逼着人手打 spec 该带的字，"
        "而手打的字不过任何一条内容测试")


def test_查旁白那条路不许碰源片也不许写产物():
    """**问「哪几段旁白写长了」不该付一条新成片的代价。**

    这道闸比的是「TTS 时长 vs spec 里的段长」，两样都**不需要源片**。可它原来
    只活在 `render()` 里，于是想知道答案就得跑一趟完整 render——而在**通过**的
    情况下那一趟会顺手渲出一条新成片并提交。对已经发过的片子，那就是白白往
    仓库里多塞一个几十 MB 的 blob（`.git` 已经 1.77 GiB）。

    判据钉三头：

    1. 这条路上**不出现下载**（`download(`）——碰了源片就不成立
    2. 语音落**临时目录**，`output/` 一个字节都不动
    3. 入口在工作流里**够得着**，而且它不走清理/上传/提交那三步
       （和 `--cover-only` 那次同一个坑：开关够不着等于这条能力不存在）
    """
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    body = src[src.index("if args.check_narration:"):src.index("if args.dry_run:")]
    assert "download(" not in body, "查旁白那条路碰了源片——它不需要"
    assert "TemporaryDirectory" in body, (
        "语音没落临时目录——查一次旁白就往 output/ 里写一遍 voice_*.mp3")
    assert "narration_overruns(" in body, "没有复用那道闸本身，等于另写了一份"

    # 复用的必须是**同一个函数**：render 里也得走它，否则两处判据迟早分叉。
    # ⚠️ 只切到 `def main(` 为止——切到文件末尾会把上面那个 `check_narration`
    # 块里的调用也算进来，于是把 render 里的删掉这条也照样绿（第一版就是这样，
    # 反向验证时才发现）。又一次「判据宁可窄，不可宽」。
    render_body = src[src.index("\ndef render("):src.index("\ndef main(")]
    assert "narration_overruns(" in render_body, (
        "render 没走同一个函数——查出来「装得下」而真渲时又被拦，判据就废了")

    yml = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    head, jobs = yml.split("\njobs:", 1)
    opts = re.search(r"options: \[(.*?)\]", head).group(1)
    assert "narration" in [o.strip() for o in opts.split(",")], (
        f"mode 里够不着 narration：{opts}")
    blocks = re.split(r"\n(?=      - (?:name|uses):)", jobs)
    # ⚠️ 选块要按「整行 if 恰好就是 narration」认：TTS 缓存那一步的 if 是
    # `mode == 'render' || mode == 'narration'`（复合条件），裸子串 `mode ==
    # 'narration'` 会把它一起数进来，这条就误报「narration 的步骤有 2 个」。
    step = [
        b for b in blocks
        if re.search(r"^        if: github\.event\.inputs\.mode == 'narration'\s*$",
                     b, re.M)
    ]
    assert len(step) == 1, f"narration 的步骤有 {len(step)} 个"
    assert "--check-narration" in step[0]
    # 它什么都不产，所以清理/上传/提交都要放它过
    for name in ("丢掉不进仓库的中间物", "上传 artifact", "提交产物"):
        blk = next(b for b in blocks if b.startswith(f"      - name: {name}"))
        assert "mode != 'narration'" in blk, (
            f"「{name}」没排除 narration 模式——这条路一个产物都没有")


def test_同一条源片不许下第二次(tmp_path, monkeypatch, capsys):
    """**一半的 render 时间花在重下同一个文件上。**

    同一条源片会被下两到三次：probe 一次、cover 一次、render 一次——中间
    「丢掉不进仓库的中间物」把它删了，而它本来就不进仓库。实测一个 70 MB 的
    源片要下 **100.86 秒**（YouTube 限速，不是带宽），而 render 整步才 198 秒。

    判据要**真走一遍 `download()`**，不是查源码里有没有那个函数：

    1. 没配缓存目录 → 旧行为，该下还得下
    2. 配了 → 第一次下完存一份，第二次**一个字节都不再下**
    3. 换一条 URL → 不许命中（键是 URL 的哈希，不是「有没有缓存」）
    4. 缓存写不进去**不算失败**（它只是个加速），但要出声
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    calls: list[str] = []

    def _fake_ytdlp(args, **kw):
        # 冒充 yt-dlp：把 `-o` 指的那个文件造出来
        calls.append(args[-1])
        out = Path(args[args.index("-o") + 1])
        out.write_bytes(b"\0" * 2048)
        return subprocess.CompletedProcess(args, 0, "", "")

    import subprocess  # noqa: PLC0415

    monkeypatch.setattr(reel.shutil, "which", lambda _n: "/usr/bin/yt-dlp")
    monkeypatch.setattr(reel.subprocess, "run", _fake_ytdlp)
    monkeypatch.setattr(reel, "probe_size", lambda _p: (1920, 1080))
    url = "https://www.youtube.com/watch?v=AAAAAAAAAAA"

    # ① 没配缓存目录：两次都要下
    monkeypatch.delenv(reel._SOURCE_CACHE_ENV, raising=False)
    reel.download(url, tmp_path / "a" / "source.mp4")
    reel.download(url, tmp_path / "b" / "source.mp4")
    assert len(calls) == 2, f"没配缓存却只下了 {len(calls)} 次"

    # ② 配上：第一次下、第二次命中
    monkeypatch.setenv(reel._SOURCE_CACHE_ENV, str(tmp_path / "cache"))
    calls.clear()
    reel.download(url, tmp_path / "c" / "source.mp4")
    assert len(calls) == 1, "第一次就该真下"
    assert "存了一份" in capsys.readouterr().out
    reel.download(url, tmp_path / "d" / "source.mp4")
    assert len(calls) == 1, "第二次又下了一遍——缓存没生效"
    hit = capsys.readouterr().out
    assert "命中" in hit, f"命中了却不出声：{hit}"
    assert (tmp_path / "d" / "source.mp4").stat().st_size == 2048, "命中但文件是空的"

    # ③ 换 URL 不许命中
    reel.download(url.replace("AAAAAAAAAAA", "BBBBBBBBBBB"),
                  tmp_path / "e" / "source.mp4")
    assert len(calls) == 2, "换了 URL 还命中——键不是按 URL 算的"

    # ④ **`~` 要展开**——工作流里写的就是 `~/.cache/tennislive-sources`，而
    # Python 不展开波浪号：`Path("~/…")` 是个**名叫 `~` 的相对目录**，落在仓库
    # 工作区里，`actions/cache` 找真的 $HOME 自然找不到，于是一个字节都没存过
    # 而两趟 run 全绿（run 156/158）。**上一版这条判据喂的是绝对路径，
    # 正好绕过这一半。**
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv(reel._SOURCE_CACHE_ENV, "~/.cache/tennislive-sources")
    calls.clear()
    reel.download(url, tmp_path / "g" / "source.mp4")
    assert len(calls) == 1
    assert not (Path.cwd() / "~").exists(), (
        "在工作区里造了个名叫 `~` 的目录——波浪号没展开，缓存等于没有")
    saved = list((tmp_path / "home" / ".cache" / "tennislive-sources").glob("*.mp4"))
    assert saved, "展开之后该落在真的 $HOME 底下，却没有"
    reel.download(url, tmp_path / "h" / "source.mp4")
    assert len(calls) == 1, "`~` 展开之后第二次仍然重下了"

    # ⑤ 写不进去只是慢一点，不该让一趟下载成功的 run 变红
    monkeypatch.setenv(reel._SOURCE_CACHE_ENV, "/proc/nope/nowhere")
    calls.clear()
    capsys.readouterr()
    reel.download(url, tmp_path / "f" / "source.mp4")   # 不许抛
    assert len(calls) == 1
    assert "存不进去" in capsys.readouterr().out, "存不进去要出声，别悄悄退回重下"


def test_低清源片不许固化进缓存(tmp_path, monkeypatch, capsys):
    """**一次瞬时的降档，不许变成永久故障。**

    缓存键只有 URL，而同一条 URL 在不同一趟里能下到不同的高度（PO token /
    n challenge 偶发没打通时 yt-dlp 会退到低画质那档）。原来低清兜底那份
    **照样 `_keep_source`**、命中那支**从不复查高度**——于是一趟偶发的 480p
    写进缓存之后，之后每一趟都命中它、红在 `resolve_crop` 的「高 ≥ 700」上，
    报错还指向「换 client 重下」，而重下根本走不到：缓存把坏结果固化了
    （和 `test_直链下到的网页不许当成源片还存进缓存` 是同一个形状，
    只是那次固化的是网页、这次是低清）。

    判据**真造文件、真走 `download()`**，四层：

    1. 低清兜底（没认领 archival）**不写缓存**，而且要出声
    2. 认领了 `archival` 的才写——那是素材本来的样子，缓存它是对的
    3. 命中之后按认领挑地板复查：480p 对 archival（地板 400）是命中
    4. 同一份 480p 对没认领的（地板 700）要**弃用重下**并删掉旧缓存，
       重下拿到高清后缓存自愈
    """
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    calls: list[str] = []
    quality = {"h": 480}

    def _fake_ytdlp(args, **kw):
        calls.append(args[-1])
        out = Path(args[args.index("-o") + 1])
        # 文件大小就是「高度」——缓存复制/改名都保得住它，
        # 于是 probe_size 对缓存里那份读到的正是当年下它时的高度
        out.write_bytes(b"\0" * quality["h"])
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(reel.shutil, "which", lambda _n: "/usr/bin/yt-dlp")
    monkeypatch.setattr(reel.subprocess, "run", _fake_ytdlp)
    monkeypatch.setattr(reel, "probe_size",
                        lambda p: (854, Path(p).stat().st_size))
    monkeypatch.setenv(reel._SOURCE_CACHE_ENV, str(tmp_path / "cache"))
    url = "https://www.youtube.com/watch?v=CCCCCCCCCCC"
    cached = reel._cached_source(url, ".mp4")
    assert quality["h"] < reel.MIN_SOURCE_H, "fixture 前提变了：480 不再算低清"

    # ① 低清兜底不进缓存（没认领 archival）
    got = reel.download(url, tmp_path / "a" / "source.mp4")
    assert got.stat().st_size == 480, "低清兜底那份该照旧交付（判它的是 resolve_crop）"
    assert not cached.is_file(), (
        "480p 的兜底被写进了缓存——下一趟起每次都命中这份低清，"
        "一次瞬时降档从此固化")
    assert "不进缓存" in capsys.readouterr().out, "不写缓存要出声，别静默"

    # ② 认领了 archival 的才写（那是素材本来的样子）
    n = len(calls)
    reel.download(url, tmp_path / "b" / "source.mp4", archival=True)
    assert len(calls) > n, "认领过的这一趟该真下"
    assert cached.is_file() and cached.stat().st_size == 480, (
        "认领了 archival 的低清素材该进缓存——它不是事故")
    capsys.readouterr()

    # ③ 命中复查按认领挑地板：480 ≥ MIN_ARCHIVAL_H(400)，对 archival 是命中
    assert reel.MIN_ARCHIVAL_H <= 480 < reel.MIN_SOURCE_H, "fixture 前提变了"
    n = len(calls)
    reel.download(url, tmp_path / "b2" / "source.mp4", archival=True)
    assert len(calls) == n, "archival 命中 480p 缓存却还在重下"
    assert "命中" in capsys.readouterr().out

    # ④ 同一份 480p 对没认领的要弃用重下，重下到高清后缓存自愈
    quality["h"] = 1080
    n = len(calls)
    reel.download(url, tmp_path / "c" / "source.mp4")
    out = capsys.readouterr().out
    assert len(calls) == n + 1, "该弃用缓存重下一次"
    assert "弃用重下" in out and "480" in out, (
        f"弃用旧缓存要把「缓存里是几 p」说出来：{out!r}")
    assert cached.is_file() and cached.stat().st_size == 1080, (
        "重下拿到高清之后缓存该自愈成好的那份")
    n = len(calls)
    reel.download(url, tmp_path / "d" / "source.mp4")
    assert len(calls) == n, "自愈之后第二次该命中，不该再下"

    # ⑤ render 那头要真的把认领传下来——download 的 archival 形参没人传就等于没有
    #    （「算得对」和「算出来被用上了」是两件事；行为那半在上面四层里）
    body = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert "archival=key in claimed_archival" in body, (
        "render() 没把 archival 认领传给 download()——形参成了摆设")


def test_只扫一段时切点要换算回源片的绝对秒数(tmp_path):
    """`probe --from/--to`：**`-ss` 放在 `-i` 前面，`pts_time` 会从 0 重新起算。**

    不把 `start` 加回去的话，切点全部往前偏移 `start` 秒——而它**不报错**，
    只会让照着 probe.json 排的每一段都切在错的地方。

    为什么要能只扫一段：WTA 的单场集锦**不是每场都发**，Day N 合集才是全覆盖的
    （王欣瑜对卡萨金娜那场只在 61 分钟的 Day 2 合集里，章节
    `2371–2553  X. Wang Vs. D. Kasatkina`）。整片扫一遍缩略图墙会出七十多张、
    绝大多数是别人的比赛。

    判据**真造一段视频、真跑一次 `scene_changes`**：造一个第 10 秒换色的片子，
    只扫 5–15 秒那一段，报出来必须是 ~10 而不是 ~5。
    """
    import shutil as _shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    if not _shutil.which("ffmpeg"):
        raise AssertionError(
            "这条测试要 ffmpeg（ci.yml 里装了）。"
            "**不许 skip**——一条常年跳过的检查和常年红是同一个毛病")

    clip = tmp_path / "two.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=navy:s=320x240:r=25:d=10",
         "-f", "lavfi", "-i", "color=c=orange:s=320x240:r=25:d=10",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
         "-pix_fmt", "yuv420p", str(clip)], check=True)

    whole = reel.scene_changes(clip)
    assert any(9.5 <= t <= 10.5 for t in whole), f"整片都没认出那一刀：{whole}"

    part = reel.scene_changes(clip, start=5.0, stop=15.0)
    assert part, "只扫 5–15 秒反而一个切点都没有"
    assert any(9.5 <= t <= 10.5 for t in part), (
        f"切点没换算回绝对秒数：{part}——`-ss` 在 `-i` 前面时 pts_time 从 0 起算，"
        "不把 start 加回去，每一段都会切偏 start 秒，而且不报错")
    assert not any(t < 5.0 for t in part), f"区间外的切点漏进来了：{part}"


def test_横摇的段也要有裁切中心():
    """`track: true` 的段 `cx` 不许留 `None`——`cut_segment` 无条件先算兜底的 x。

    run 30877075310：第 11 段写了 `track: true`，分段编码跑到它才炸

        x = int(round(seg.cx * source_w - CROP_W / 2))
        TypeError: unsupported operand type(s) for *: 'NoneType' and 'int'

    前面十段全白编了。真因是 `track_shots` 里那句 `not s.track`——**只给不摇的
    段填 `cx`**。而 `cut_segment` 里那个 `x` 是给「拿不到 path 时」兜底用的，
    它排在 `if path:` **前面**，所以摇不摇都会被求值。

    ⚠️ **存量九条 spec 一条都没用过 `track`**，所以这条路从「自动定心改成固定
    中心」那天起就是坏的，一直没人踩到——又一次「写了不等于跑过」：那次改动
    只保证了它自己走的那条路，另一条路的前提被顺手拿掉了，**而且不报错**，
    因为根本没有输入会走到那儿。

    判据**真跑一遍 `track_shots`**（跟踪那一步打桩，不碰源片）：查源码里有没有
    `not s.track` 只能防「有人把它加回来」，防不住下一次换个写法再漏一遍。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    segs = [reel.Segment(start=0.0, end=5.0, cx=None, narration="甲",
                         source="main", track=False),
            reel.Segment(start=5.0, end=10.0, cx=None, narration="乙",
                         source="main", track=True)]
    assert all(s.cx is None for s in segs), "fixture 前提变了：cx 默认不再是 None"
    # 跟踪那一步要解码源片，这儿只验 cx 有没有被填——打桩成「跟不出路径」，
    # 那正是兜底的 x 唯一真的会被用到的情形。
    reel.track_run = lambda *a, **k: []
    reel.track_shots({"main": Path("nope.mp4")}, segs, 1280)
    for i, s in enumerate(segs):
        assert s.cx is not None, (
            f"第 {i + 1} 段（track={s.track}）的 cx 是 None——"
            "cut_segment 里那个兜底的 x 会当场 TypeError")
        assert 0.0 <= s.cx <= 1.0, s.cx


def test_直链下到的网页不许当成源片还存进缓存(tmp_path, monkeypatch, capsys):
    """**「下到了」不等于「下到的是视频」，而坏结果会被缓存固化。**

    run 30838371382：`source_url` 给的是 Brightcove 的播放页
    （`players.brightcove.net/<账号>/<player>/index.html?videoId=…`），
    直链那条路 curl 下来 **0.3 MB 的网页**，打印「[ok] 直链下到 0.3 MB」，
    `_keep_source` 还把它**存进了缓存**，一直到下一步 ffprobe 才报
    `Invalid data found`。于是「换个参数重跑」永远重现同一个错——
    因为重跑第一件事就是命中那个坏缓存。

    老判据只看**前 64 字节**里有没有 `<!doctype html` / `<html`，
    所以这条测试喂的网页**故意不以 `<!doctype` 开头、前 64 字节里也没有
    `<html`** —— 那正是漏过去的那种形状。

    判据必须**真造两个文件、真跑一遍 `download()`**：查源码里有没有 probe
    只能防「有人把它删了」，防不住「它从来没工作过」。
    """
    import shutil as _shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    if not _shutil.which("ffmpeg") or not _shutil.which("ffprobe"):
        raise AssertionError(
            "这条测试要 ffmpeg/ffprobe（ci.yml 里装了）。"
            "**不许 skip**——一条常年跳过的检查和常年红是同一个毛病")

    # ① 播放页：不以 `<!doctype` 开头，前 64 字节里也没有 `<html`
    page = tmp_path / "index.html"
    page.write_text("\n<!-- Brightcove player bootstrap -->\n" + " " * 90
                    + "\n<html><body>player</body></html>\n", encoding="utf-8")
    assert b"<html" not in page.read_bytes()[:64], "这个 fixture 没重现老判据的漏洞"

    # ② 一个真视频，用来反向验证这道闸没有把好的也拦掉
    real = tmp_path / "real.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=320x240:rate=25", "-t", "1",
                    "-pix_fmt", "yuv420p", str(real), "-y"], check=True)

    cache = tmp_path / "cache"
    monkeypatch.setenv(reel._SOURCE_CACHE_ENV, str(cache))

    with pytest.raises(reel.ReelError) as err:
        reel.download(f"file://{page}", tmp_path / "out1.mp4")
    printed = capsys.readouterr().out
    msg = str(err.value)
    assert "ffprobe 读不出视频流" in msg, f"报错没说清楚是什么问题：{msg}"
    # ⚠️ **出路要代码自己走，不是写在报错里让人去走。**
    #
    # 老版本在这儿直接抛错，正文写着「这类要交给 yt-dlp」——出路已经写出来了，
    # 只是没人走。张帅那条就撞在这儿：`players.brightcove.net/…/index.html`
    # 不含 youtube，走 curl 拿回 0.3 MB 网页，render 第 12 秒就红
    # （run 30875896980）；而同一条 URL 交给 yt-dlp 一次就下来了。
    #
    # 现在 curl 拿到的东西读不出视频流就**当场退回 yt-dlp**。按结果分路，
    # 不按域名分路——一张「哪些站是播放页」的名单会过期，
    # 而「ffprobe 读不读得出视频流」这个判据永远新鲜。
    # ⚠️ **判据要挑两种环境都成立的那个。** 第一版断言报错里有 `player client`
    # （yt-dlp 逐档试完的那句），本地绿、**CI 红**——CI 上根本没装 yt-dlp
    # （同一份日志里就有一条 `这台机器没装 yt-dlp` 的 skip），退路走到一半就
    # 停在「找不到 yt-dlp」。又一次「本地装着不等于 CI 装着」。
    #
    # 而 `"yt-dlp" in msg` 单独也**证明不了**退路走过：老版本那句
    # 「这类要交给 yt-dlp」里同样有这四个字。真正只在退路上出现的是那行 stdout。
    assert "改交给 yt-dlp 再试一次" in printed, (
        f"没退回 yt-dlp（老版本会直接抛错，根本不试）：{printed!r}")
    assert "player client" in msg or "找不到 yt-dlp" in msg, (
        f"退路走了一半就丢了线索：{msg}")
    assert not (tmp_path / "out1.mp4").exists(), "坏文件没删干净"
    assert not list(cache.glob("*")), (
        "网页被存进了缓存——下一趟会直接命中它，「重跑」永远重现同一个错")

    # ③ 反向：真视频要过，而且要进缓存（别把闸装成一律不放行）
    got = reel.download(f"file://{real}", tmp_path / "out2.mp4")
    assert got.is_file() and got.stat().st_size > 0
    assert len(list(cache.glob("*"))) == 1, "真视频没被缓存下来"


def test_双语字幕要真的排成两行(tmp_path):
    """**换行是「这一条排两行」，不是一个空格。**

    中英双语的原声字幕（`quote` 写成列表）靠元素里的换行分上英下中。
    第一版我拿 `pipeline.render_ass` 验的——**那是另一个写入器**：成片走的是
    `explainer.write_subtitles`（Style `TL`，带逐词字号标签），而它当时写着
    `shown.replace(chr(10), ' ')`，把换行压成空格。渲出来长的那两条靠
    `WrapStyle=0` 自动折**碰巧**断在中英之间，短的干脆不断——同一条片子里
    两种样子，而且断点由宽度决定，不由作者决定。
    **又一次「查的东西和跑的东西不是一回事」。**

    ⚠️ 也不能直接把 ASS 的换行符写进文本：`_ass_text` 会把它后面那个 N 当成
    一个拉丁词、包上字号标签，画面上多出一个字母 N。所以要**按行分别过
    `_ass_text` 再拼**。

    判据真写一份 ASS 出来读，钉两头：双行的要有换行符、**单行的一个字节都不许
    变**（存量的解说片和赛场之上都走这个写入器）。
    """
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video.explainer import write_subtitles  # noqa: PLC0415

    nl = chr(92) + "N"          # ASS 的换行符，写成字面量免得被当转义
    path = write_subtitles(
        [(0.0, 3.0, "A first ever tour title\n生涯第一个巡回赛冠军"),
         (3.0, 5.0, "普通单行字幕")],
        tmp_path / "s.ass", height=1440)
    rows = [line for line in path.read_text("utf-8").splitlines()
            if line.startswith("Dialogue")]
    assert len(rows) == 2

    assert nl in rows[0], f"双语那条没排成两行：{rows[0]}"
    head, _, tail = rows[0].partition(nl)
    assert "title" in head and "生涯第一个巡回赛冠军" in tail, \
        f"英文和中文没落在各自那一行：{rows[0]}"
    assert r"{\fs46}A first ever tour title" in head, \
        f"双语字幕的英文仍按单行字幕放大，会折行把中文顶出画布：{rows[0]}"
    assert r"{\fs78}" not in head, \
        f"英文行里的逐词放大标签盖掉了双语小字号：{rows[0]}"
    assert ",0,0,1240,," in rows[0], \
        f"双语事件没有单独抬高，第二行仍可能被长英文挤出安全区：{rows[0]}"
    assert chr(92) + "{" not in rows[0], \
        f"换行符被当成拉丁词包了字号标签，画面上会多出个 N：{rows[0]}"

    assert rows[1].endswith(",普通单行字幕"), \
        f"单行的输出变了，会连累解说片那条线：{rows[1]}"


def test_缓存源片的开关要在工作流里够得着():
    """和 `--cover-only` 那次同一个坑：代码里加了，工作流没接上等于没有。

    三条要源片的路（probe / cover / render）都得拿到缓存目录，而
    push / narration 两条**根本不碰源片**，不该为它们恢复缓存。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    jobs = body.split("\njobs:", 1)[1]
    blocks = re.split(r"\n(?=      - (?:name|uses):)", jobs)

    cache = [b for b in blocks if "tennislive-sources" in b and "actions/cache" in b]
    assert len(cache) == 1, f"缓存源片那一步有 {len(cache)} 个"
    for skip in ("'push'", "'narration'"):
        assert skip in cache[0], f"{skip} 那条路不碰源片，不该恢复缓存"

    for name in ("probe — 下载", "cover — 只出封面海报", "render — 出成片"):
        blk = next(b for b in blocks if b.startswith(f"      - name: {name}"))
        assert "TENNISLIVE_SOURCE_CACHE" in blk, f"「{name}」没拿到缓存目录"


def test_复制页打不开时消息本身留得住文案():
    """复制页走 `github.io`，**那条链路沙箱量不到**（这里探是 200，账号所有者
    在微信里点开是 404）。所以它只能是加分项，不能是文案唯一的出口。

    正文本来就整段内联，问题出在标题——它原来只活在那个按钮后面。现在大标题
    底下标一行「长按这一行即可复制」：**不另印一遍**（那是「同一段印两遍」
    那个老毛病），只是把已经在页面上的那一行标成出口。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    title = "8.1 开球之前 | 郑钦文 vs 塔拉鲁迪"
    body = "第一段正文。\n\n第二段正文。"
    html = push_reel.build_html("https://v/x.mp4", "https://p/copy.html", "",
                                f"{title}\n\n{body}", "", "开球之前")

    # 标题在，而且**只印一遍**——多印一遍就是那个老毛病
    assert html.count(title) == 1, "标题印了不止一遍"
    assert "长按" in html.split(title, 1)[1][:200], (
        "大标题底下没有「长按可复制」那一行——复制页打不开时标题就没有出口了")

    # 正文也要整段在消息里，别只留一个按钮
    assert "第一段正文。" in html and "第二段正文。" in html
    assert "长按整段即可复制" in html


def test_赛前前瞻的封面要写清几点开球():
    """「开球之前」的封面必须写**开赛时刻**——账号所有者定的（首页问题下面的
    小字：时间、赛事名称、轮次）。这类片子唯一的行动信息就是那个时刻。

    `versus_poster` 原来只有 `tier`/`round` 那条路读 `meta`，写了 `event_badge`
    的 spec 里那个时刻**静静地不见了**：海报看着是完整的，少的恰恰是那一样。
    """
    src = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    head, _, tail = src.partition("if event_badge:")
    branch = tail.split("else:")[0]
    assert 'cover.get("meta"' in branch, (
        "event_badge 那条路没有读 meta——赛前前瞻的开赛时刻会被吞掉")

    for path in sorted(Path("specs/reels").glob("*.json")):
        cover = json.loads(path.read_text(encoding="utf-8")).get("cover") or {}
        if str(cover.get("eyebrow", "")).strip() != "开球之前":
            continue
        meta = str(cover.get("meta", "")).strip()
        assert meta, f"{path.name} 是开球之前，封面没写开赛时刻（cover.meta）"
        assert any(k in meta for k in ("时间", ":", "：")), (
            f"{path.name} 的 cover.meta 看不出是个时刻：{meta!r}")


def test_接缝要溶解不许淡到黑(tmp_path):
    """**淡入淡出不等于淡到黑。**

    第一版把账号所有者要的转场做成了「每段各自淡到黑再淡回来」，于是每个接缝
    中间都有一小段全黑。已发的 jodar-fritz 18 个接缝挨个采样，最黑的五个平均
    亮度 `0.0`（62.191s 那一帧是整幅纯黑），谷值平均 8.3——账号所有者看到的
    「接缝画面的时候有轻微的闪烁」就是它。

    要的是**溶解**：前一段直接化进后一段，中间一帧黑都不许有。

    四条断言，缺一不可，都反向验证过（反向的记录在提交说明里）：

    1. **总长不许变。** 溶解会吃掉时间，而旁白的 `adelay`、字幕的 cue、
       `check_reel_landed` 那句「画面总长 − 段落总长 ＝ 封面」全按
       `seg.length` 累加。所以每段多切 `SEG_FADE` 秒当底料、末段不留——
       长度账见 `dissolve_filtergraph`。这一条要是破了，症状是**后半段配音
       整体错位**，而 ffmpeg 一声不吭
    2. **接缝上不许变黑。** 拿三段纯色真跑一次滤镜图，量接缝前后的亮度：
       溶解的话红→绿此消彼长，亮度基本不动；淡到黑会掉到 0
    3. **声音也不许掉到静音。** 老写法的 `afade` 两头各淡一次，接缝正中是真
       静音；`acrossfade` 是此消彼长
    4. 另加一条盯**位置**的：`cut_segment` 里不许再出现 `fade=`。只测行为
       拦不住「有人又把淡入淡出搬回每一段自己身上」——那正是这次的错法
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    fade = reel.SEG_FADE
    # 三段纯色：末段不留尾巴，前两段各多切 fade 秒
    plan = [("red", 4.0, fade), ("green", 3.0, fade), ("blue", 5.0, 0.0)]
    parts = []
    for i, (colour, length, tail) in enumerate(plan):
        part = tmp_path / f"p{i}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i",
             f"color=c={colour}:s=320x426:r=25:d={length + tail + 1}",
             "-f", "lavfi", "-i",
             f"sine=frequency={300 + 200 * i}:sample_rate={reel.AUDIO_RATE}",
             "-t", f"{length + tail:.3f}",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", reel.AUDIO_RATE,
             str(part)], check=True)
        parts.append(part)

    lengths = [length for _, length, _ in plan]
    film = tmp_path / "film.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         *[a for p in parts for a in ("-i", str(p))],
         "-filter_complex", reel.dissolve_filtergraph(lengths, fade),
         "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", reel.AUDIO_RATE,
         str(film)], check=True)

    def _dur(stream):
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", stream,
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
            check=True, capture_output=True, text=True).stdout.strip()
        return float(out.rstrip(","))

    # ① 总长不许变
    want = sum(lengths)
    assert abs(_dur("v:0") - want) < 0.08, (
        f"溶解之后画面 {_dur('v:0'):.2f}s，而各段加起来是 {want:.2f}s"
        "——每一段在成片里占的时间必须和 seg.length 一样，"
        "否则后面每一句旁白和字幕都整体错位")

    # ② 接缝上不许变黑
    seam = lengths[0]
    lows = []
    for step in range(9):
        moment = seam - 0.02 + step * (fade / 6)
        shot = tmp_path / "f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{moment:.3f}",
                        "-i", str(film), "-frames:v", "1", str(shot)],
                       check=True)
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(shot), "-vf",
             "format=gray,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
             "-f", "null", "-"], capture_output=True, text=True).stderr
        got = re.search(r"YAVG=(\S+)", out)
        assert got, "量不到亮度"
        lows.append((moment, float(got.group(1))))
    floor = min(v for _, v in lows)
    assert floor > 40, (
        f"接缝上掉到了 {floor:.1f} 亮度——这是淡到黑，不是溶解。"
        f"逐帧：{[(round(t, 3), round(v, 1)) for t, v in lows]}")

    # ③ 声音也不许掉到静音
    peaks = []
    for step in range(7):
        moment = seam - 0.05 + step * (fade / 5)
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", f"{moment:.3f}", "-i", str(film),
             "-t", "0.05", "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True).stderr
        got = re.search(r"max_volume: (\S+)", out)
        assert got, "量不到音量"
        peaks.append(float(got.group(1)))
    assert max(peaks) - min(peaks) < 6.0 and min(peaks) > -40, (
        f"接缝上现场声掉下去了：{peaks}——acrossfade 是此消彼长，"
        "两头各淡一次才会在正中变成静音")

    # ④ 闸装在拼接那一步，不是装在每一段自己身上
    #
    # ⚠️ **先去掉注释行再扫。** 第一版直接扫源码，被我自己写在 `cut_segment`
    # 里那句「这儿不许再出现 `fade=`」判成违规——注释正是这个仓库记教训的地方，
    # 连注释一起扫，「把坑记下来」会被读成「又踩了这个坑」。同一个形状本文件
    # 里已经犯过四次。
    body = "\n".join(
        line for line in inspect.getsource(reel.cut_segment).splitlines()
        if not line.lstrip().startswith("#"))
    assert "fade=" not in body, (
        "`cut_segment` 里又出现了 `fade=`——在每一段自己身上淡就是「各自淡到黑」，"
        "接缝中间必然有一帧全黑。转场收在拼接那一步的 dissolve_filtergraph")


def test_片尾接上之后每个分段都要留溶解底料(tmp_path):
    """账号所有者 2026-08-05：「每个视频最后都加一页并配上关注的口播」。

    **片尾页接在所有分段之后，于是「最后一段」换人了。**
    `dissolve_filtergraph` 的长度账要求**只有末段不留尾巴**（末段那个 f 正好
    被吃掉，总长才等于 Σ Lᵢ）。加片尾之前末段是最后一个分段，加之后是片尾页。

    要是还写着 `tail=0.0 if index == len(segments) - 1`，最后一个分段就少
    `SEG_FADE` 秒底料，`xfade` 的 offset 落到流的末尾之外——**整条片子在那个
    接缝上截断**。2026-08-02 那两趟就是这么来的：段落加起来 114.46s、
    成片 12.44s，**而日志里一个字都没说**。

    两条断言：

    1. **盯位置**：切分段那个循环里不许再出现「最后一段不留尾巴」的条件。
       只测行为拦不住这个错法——真跑一遍长度账是拿纯色跑的，它不知道
       生产代码给每一段传了什么 tail。
    2. **真跑一次长度账**：cover + 两段 + 片尾，四个 part 走一遍生产用的
       `dissolve_filtergraph`，总长必须等于 Σ lengths。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    # ① 盯位置：那个「末段不留」的条件必须已经从分段循环里拿掉
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    body = "\n".join(line for line in src.splitlines()
                     if not line.lstrip().startswith("#"))
    assert "0.0 if index == len(segments) - 1" not in body, (
        "切分段的循环里还写着「最后一个分段不留溶解底料」——片尾页接上之后，"
        "末段是片尾不是分段。这么写最后一个分段会少 "
        f"{reel.SEG_FADE}s 底料，xfade 的 offset 落到流末尾之外，"
        "整条片子在那个接缝上截断，而 ffmpeg 不报错")
    assert "parts.append(build_outro(" in body, "片尾页没有接进 parts"
    # 片尾必须是**最后**一个 part：长度账全靠这个顺序。分段现在是并行编码后
    # 按 index 排序统一 `parts += ...`，所以锚点从 `parts.append(cut_segment(`
    # 换成那行 sorted 的追加——但「片尾最后」这个不变式不变。
    assert body.index("parts.append(build_outro(") > body.index(
        "parts += [p for _, p in sorted(encoded"), (
        "片尾页要排在所有分段之后——它是末段，长度账按这个顺序算")

    # ② 真跑一次长度账
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    fade = reel.SEG_FADE
    # cover 1.2s + 两段 + 片尾 3.85s，**只有片尾不留尾巴**
    plan = [("red", 1.2, fade), ("green", 3.0, fade),
            ("blue", 2.5, fade), ("gray", 3.85, 0.0)]
    parts = []
    for i, (colour, length, tail) in enumerate(plan):
        part = tmp_path / f"q{i}.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i",
             f"color=c={colour}:s=320x426:r=25:d={length + tail + 1}",
             "-f", "lavfi", "-i",
             f"sine=frequency={300 + 150 * i}:sample_rate={reel.AUDIO_RATE}",
             "-t", f"{length + tail:.3f}",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", reel.AUDIO_RATE,
             str(part)], check=True)
        parts.append(part)

    lengths = [length for _, length, _ in plan]
    film = tmp_path / "with_outro.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         *[a for p in parts for a in ("-i", str(p))],
         "-filter_complex", reel.dissolve_filtergraph(lengths, fade),
         "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "12",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", reel.AUDIO_RATE,
         str(film)], check=True)
    got = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
        check=True, capture_output=True, text=True).stdout.strip().rstrip(","))
    want = sum(lengths)
    assert abs(got - want) < 0.08, (
        f"接上片尾之后画面 {got:.2f}s，而各段加起来是 {want:.2f}s——"
        "长度账破了，后面每一句旁白和字幕都会整体错位")


def test_片尾的动效每一层都要按时出现(tmp_path):
    """账号所有者 2026-08-05：「最后最好有一个动效出来这一屏」。

    **真跑一遍生产用的那个滤镜图**，量每一层在自己该出现的时刻之前是不是还没
    出现、之后是不是出来了。查源码里有没有 `fade=` 只能防「有人把它删了」，
    防不住「它从来没工作过」——这个仓库里「签名对了、实现是空的」是常客。

    ⚠️ 拿**纯色块**当层，不渲真页面：这条判据要在 CI 上跑得起来，而 CI 上
    没有 Chromium 也没有品牌字体。它验的是滤镜图的时序，不是版式好不好看。

    ⚠️ **必须按 30fps 跑，不能用 25。** 静图输入不给 `-framerate` 时 ffmpeg
    按 25fps 解 `-loop 1`，而 `zoompan` 输出标的是目标帧率——帧数不够，画面
    就缩成 `total × 25/fps`。**fps 恰好是 25 时两者相等，这个 bug 完全看不见**：
    第一版就是拿 25 跑的，绿得很干净，而真跑一次解说片（30fps）当场量到
    画面 3.57s、音轨 4.29s。判据的参数选在「恰好掩盖缺陷」的那一档上，
    和没有判据是一回事。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    secs, fps = 3.85, 30
    # 底层纯黑，三层各是一条横带，落在互不重叠的高度上——这样量某一条带的
    # 亮度就等于量那一层出没出来。
    base = tmp_path / "base.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=black:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
                    "-frames:v", "1", str(base)], check=True)
    bands = {}
    layer_files = []
    for i, (key, st, dur, _rise) in enumerate(outro_page.LAYERS):
        y0 = 200 + i * 300
        bands[key] = (y0, y0 + 160, st, dur)
        f = tmp_path / f"l{i}.png"
        # 透明底 + 一条白带
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=black@0.0:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
             "-vf", f"drawbox=x=0:y={y0}:w={outro_page.VIDEO_W}:h=160:"
                    "c=white@1.0:t=fill",
             "-frames:v", "1", "-pix_fmt", "rgba", str(f)], check=True)
        layer_files.append(f)

    film = tmp_path / "outro.mp4"
    args = ["ffmpeg", "-v", "error", "-y",
            "-framerate", str(fps), "-loop", "1", "-t", f"{secs}", "-i", str(base)]
    for f in layer_files:
        args += ["-framerate", str(fps), "-loop", "1", "-t", f"{secs}", "-i", str(f)]
    args += ["-filter_complex", outro_page.motion_filter(secs, str(fps), float(fps)),
             "-map", "[vout]", "-c:v", "libx264", "-preset", "ultrafast",
             "-crf", "12", "-pix_fmt", "yuv420p", str(film)]
    subprocess.run(args, check=True)

    # ① **画面必须真有那么长。** 少给 `-framerate` 时它会缩成 total×25/fps，
    # 而 ffmpeg 不报错——真跑解说片时量到画面 3.57s、音轨 4.29s 就是这个。
    got = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(film)],
        check=True, capture_output=True, text=True).stdout.strip().rstrip(","))
    assert abs(got - secs) < 0.12, (
        f"片尾画面 {got:.2f}s，要的是 {secs:.2f}s——"
        f"差 {secs / got if got else 0:.3f} 倍。静图输入少了 `-framerate`，"
        "帧数按 25fps 铺、时长按目标帧率标，画面就比音轨短一截")

    def band_brightness(moment: float, y0: int, y1: int) -> float:
        shot = tmp_path / "s.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{moment:.3f}",
                        "-i", str(film), "-frames:v", "1", str(shot)], check=True)
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(shot), "-vf",
             f"crop={outro_page.VIDEO_W}:{y1 - y0}:0:{y0},"
             "format=gray,signalstats,metadata=print:key=lavfi.signalstats.YAVG",
             "-f", "null", "-"], capture_output=True, text=True).stderr
        got = re.search(r"YAVG=(\S+)", out)
        assert got, f"量不到 {moment}s 的亮度"
        return float(got.group(1))

    for key, (y0, y1, st, dur) in bands.items():
        # 入场之前：还没出来（留 0.06s 余量给取帧的量化误差）
        before = band_brightness(max(0.0, st - 0.10), y0, y1)
        # 淡完之后：出来了
        after = band_brightness(min(secs - 0.05, st + dur + 0.25), y0, y1)
        assert before < 12, (
            f"「{key}」层在 {st}s 之前就已经出现了（亮度 {before:.1f}）——"
            "淡入没生效，那一层从第 0 帧就是满的")
        assert after > 90, (
            f"「{key}」层淡完之后还没出来（亮度 {after:.1f}）——"
            "这一层根本没被合进去，或者 fade 把 alpha 弄反了")
        assert after - before > 60, (
            f"「{key}」层前后差得太小（{before:.1f} → {after:.1f}），淡入没在动")


def test_片尾片段的画面要和它自己要的一样长(tmp_path):
    """**真调一次 `render_clip`**，量它出来的画面有多长。

    ⚠️ 这条是补上一条判据的漏洞的。`test_片尾的动效每一层都要按时出现` 验的是
    `motion_filter`（滤镜图），而真出问题的地方在 `render_clip` 拼的那串
    **ffmpeg 参数**里——静图输入少了 `-framerate`，ffmpeg 就按 25fps 铺
    `-loop 1`，而 `zoompan` 输出标的是目标帧率，画面于是缩成 `total×25/fps`。

    实测（解说片，30fps，目标 4.29s）：**画面 3.57s，音轨 4.29s。**
    ffmpeg 不报错，成片能出来，只是最后 0.72 秒没有画面。

    而那条老判据**抓不到它**：测试自己拼命令行、自己带了 `-framerate`，
    把生产代码里的两处全拿掉照样绿。查的东西和跑的东西不是一回事。

    喂现成的 PNG 当层（`layers=`），所以这条不碰 Chromium，CI 上跑得起来。

    ⚠️ **必须按 30fps 跑**：fps 恰好是 25 时 `total×25/fps == total`，
    这个 bug 完全看不见。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    layers = {}
    for name in ["base"] + [k for k, *_ in outro_page.LAYERS]:
        f = tmp_path / f"{name}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=gray:s={outro_page.VIDEO_W}x{outro_page.VIDEO_H}",
             "-frames:v", "1", "-pix_fmt", "rgba", str(f)], check=True)
        layers[name] = f

    want, fps = 4.29, 30
    dest = outro_page.render_clip(
        tmp_path, want,
        fps_expr=str(fps), fps=float(fps), chromium="", dest=tmp_path / "o.mp4",
        audio_rate="24000", preset="ultrafast", crf="26",
        audio_bitrate="64k", layers=layers,
    )
    got = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration", "-of", "csv=p=0", str(dest)],
        check=True, capture_output=True, text=True).stdout.strip().rstrip(","))
    assert abs(got - want) < 0.12, (
        f"片尾画面 {got:.2f}s，要的是 {want:.2f}s（差 {want / got if got else 0:.3f} "
        f"倍，25/{fps} = {25 / fps:.3f}）——静图输入少了 `-framerate`，"
        "帧数按 25fps 铺、时长按目标帧率标，画面就比音轨短一截，而 ffmpeg 不报错")


def test_片尾卡的画幅要和几条线的卡对得上():
    """片尾页搬进 `src/tennislive/video/` 之后，画幅是**另写的一份**。

    原来它 `from versus_poster import VIDEO_W, VIDEO_H`，import 本身就保证了
    一致。搬进包里之后这条路断了，两头都不能走：

    - `explainer` 稍后要反过来用这个模块，import 回去就**成环**
    - `versus_poster` 在 `tools/` 里，而 `src` 不该依赖 `tools`

    所以一致性从「import 保证」降级成了「另写一份」，**必须有判据接上**——
    否则哪天有人改了海报画幅，片尾会静静地变形或者留黑边，而这一族毛病的
    共同点就是不吭声。

    三处必须相等：
    - `outro_page.VIDEO_W/VIDEO_H` —— 片尾卡
    - `versus_poster.VIDEO_W/VIDEO_H` —— 剪辑片的整幅画布（3:4）
    - `explainer.VIDEO_W` × `explainer.CARD_H` —— 解说片那张 3:4 的卡
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415
    from tennislive.video import explainer, outro_page  # noqa: PLC0415

    assert (outro_page.VIDEO_W, outro_page.VIDEO_H) == (
        versus_poster.VIDEO_W, versus_poster.VIDEO_H), (
        f"片尾卡 {outro_page.VIDEO_W}×{outro_page.VIDEO_H} 和剪辑片画布 "
        f"{versus_poster.VIDEO_W}×{versus_poster.VIDEO_H} 对不上——"
        "片尾接进成片会变形或留黑边")
    assert (outro_page.VIDEO_W, outro_page.VIDEO_H) == (
        explainer.VIDEO_W, explainer.CARD_H), (
        f"片尾卡 {outro_page.VIDEO_W}×{outro_page.VIDEO_H} 和解说片那张 3:4 的卡 "
        f"{explainer.VIDEO_W}×{explainer.CARD_H} 对不上——"
        "片尾在解说片里 pad 到 9:16 时会和别的屏不一样大")
    # 3:4 本身也钉住：上面两条都对、但三处一起改错了比例，仍然是坏的
    assert outro_page.VIDEO_W * 4 == outro_page.VIDEO_H * 3, (
        f"片尾卡不是 3:4（{outro_page.VIDEO_W}×{outro_page.VIDEO_H}）")


def test_片尾口播说的话画面上要印得全():
    """**片尾不排字幕，这个决定的前提必须钉住。**

    封面那条规矩说的是「念的就是画面上印的那句，就别再排一行字幕；
    判据是**一不一样**」。片尾走的是同一条：屏幕上有「网球时差」四个大字
    加那句小字，把口播的每个字都覆盖住了，所以不排字幕——静音刷的人照样
    读得到全部信息。

    **要是有人改了口播文案、让它说出画面上没有的东西，这条就必须红**，
    否则「不排字幕」会从一个想清楚的决定，悄悄变成一次信息丢失，
    而它不会报错（静音的人拿不到那句话，我们也看不出来）。

    这就是「判据自己也要有判据」：断言某个东西可以不做之前，
    先证明不做它的前提还成立。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415
    from tennislive.video import outro_page  # noqa: PLC0415

    spoken = reel.OUTRO_NARRATION
    printed = outro_page.TAGLINE
    # 画面上还有品牌名那四个大字
    on_screen = printed + "网球时差"

    # **唯一认领的例外：「关注」。** 它是动作号召，不是信息——这一页的存在
    # 本身就是关注入口（台标 + 品牌名 + @handle 都在画面上），少了这两个字
    # 静音的人不会丢掉任何事实。和 `mixed_fps` / `silent_source` / `rank: null`
    # 一个形状：**认领这一步把「想清楚了」和「凑合一下」分开**。
    # 白名单只许减不许加——多认领一个词，就是多一句静音的人听不见的话。
    allowed = "关注"
    leftover = [ch for ch in spoken
                if ch not in on_screen and ch not in allowed
                and ch not in "，。！？、 "]
    assert not leftover, (
        f"片尾口播里这些字画面上没有：{''.join(sorted(set(leftover)))}\n"
        f"  口播：{spoken}\n  画面：{printed} ＋「网球时差」\n"
        f"  已认领可以不印的只有：{allowed}\n"
        "片尾不排字幕的前提是「说的每个字画面上都印着」。要么把文案改回去，"
        "要么给片尾也排字幕（那就要重新排版，小字那行会被压住）")
    assert printed in spoken, (
        f"画面上印的那句「{printed}」不在口播里——两处对不上，"
        "读者听到的和看到的会是两句话")


def test_渲染失败也要在耗时台账上留一行():
    """**只统计成功那一趟，等于统计不到真正贵的那部分。**

    2026-08-24 复盘量出来的：那天 `output/2026-08-24/reel/` 下 4 份
    `render.json` **全是 `met: true`**、中位 346s，`pipeline_health.sla_health()`
    看过去一片绿；而同一天 `match-reel` 真实跑了二十多趟——
    `gauff-pegula-cincinnati-2026-final` 渲了三趟（两趟白烧、约 14.5 分钟机器
    时间），`zheng-us-open-outlook` 从早到晚渲推了五轮。

    根子是两样计时**都只在成功那一趟才落地**：`report_timings()` 是 `render()`
    的最后一行，中途抛异常就走不到；`production_sla` 写在 `render.json` 里，
    而 `render.json` 是渲成了才写的。又一次「只在成功时出声的检查，没法证明
    它真的看过」。

    判据钉两头（**只测行为拦不住位置错**，这条本文件反复栽过）：

    1. **行为**：失败那一行要记得下 outcome、死在哪一步、每一步花了多久；
       报表要把「渲了几趟、白烧多少」摆出来——那正是今天那份报表缺的数
    2. **位置**：写台账那句必须在 `finally:` 里（在 `try` 里就又只剩成功那半），
       而且失败那一支要补打 `report_timings()`，不然耗时明细照旧丢掉
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import pipeline_timing  # noqa: PLC0415

    # ① 行为：失败那一行留得住「死在哪一步」
    bad = pipeline_timing.build_record(
        pipeline="match-reel", slug="demo", mode="render", outcome="ReelError",
        error="数字静音", stages=[("下载源片", 100.9), ("分段编码", 47.0)],
        elapsed_seconds=439.0)
    assert bad["outcome"] == "ReelError"
    assert bad["last_stage"] == "分段编码", (
        "失败那一行没记住走到哪一步——死在「下载源片」和死在「成片编码」"
        "浪费的机器时间差一个量级，混在一起统计什么都看不出来")
    # 同名步骤（每段切片那种）要合并，否则十几行淹掉重点
    assert bad["stage_seconds"]["下载源片"] == 100.9

    ok = pipeline_timing.build_record(
        pipeline="match-reel", slug="demo", mode="render", outcome="success",
        stages=[("下载源片", 100.0)], elapsed_seconds=396.0)
    report = pipeline_timing.summarize([ok, bad])
    assert "失败 1 趟" in report, f"报表把失败那一半吞了：\n{report}"
    assert "白烧" in report and "2 趟" in report, (
        f"报表没算「这条片子渲了几趟、白烧多少」——那正是今天缺的那个数：\n{report}")

    # ② 位置：写台账在 finally 里，且失败那一支补打了耗时明细
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    tail = src[src.index("    started = time.perf_counter()\n    outcome"):]
    finally_at = tail.index("finally:")
    assert "pipeline_timing.write(" in tail[finally_at:], (
        "写台账那句不在 finally 里——那它就又只在成功那一趟才执行，"
        "而这条判据要拦的恰恰是「统计口径只剩成功那一半」")
    assert "report_timings()" in tail[finally_at:tail.index("pipeline_timing.write(")], (
        "失败那一支没补打 report_timings()——`render()` 末尾那次走不到，"
        "耗时明细照旧丢在最想看它的时候")


def test_口播尾音渐弱不许被算成片尾要停多久(tmp_path):
    """gauff-pegula-cincinnati-2026-final 两次独立渲染，片尾逐秒响度表
    一字不差（run 32681014183 / 32684580629）——`OUTRO_NARRATION` 走 TTS
    内容哈希缓存，说明这不是某一次合成的运气差，是这句文案配这把嗓子这个
    语速固定带出来的一截渐弱到近乎无声的尾音。

    `outro_length()` 原来直接拿 `probe_duration()`（文件总长）当「口播说了
    多久」，把这截尾音也算进「口播」，`OUTRO_TAIL` 又在它后面**再**叠一层
    0.45s——两层静音叠加，check_reel_landed 的数字静音闸在片尾整整一秒钟
    读不到声音。真造两个 mp3 验：一个尾音渐弱到静音（模拟真实 TTS 的衰减
    尾巴），一个从头响到尾（没有尾音可裁，退回老行为）。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    def _ff(*args):
        subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)

    tail_off, tail_on = (tmp_path / n for n in ("tail_off.mp3", "tail_on.mp3"))
    # 3 秒响的调子接上 1.5 秒数字静音——真正说完是在第 3 秒，不是文件末尾
    _ff("-f", "lavfi", "-i", "sine=frequency=440:duration=3",
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-filter_complex", "[0][1]concat=n=2:v=0:a=1[out]",
        "-t", "4.5", "-map", "[out]", str(tail_off))
    # 从头响到尾，没有尾音要裁
    _ff("-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(tail_on))

    end = reel._speech_tail_end(tail_off)
    assert end is not None and 2.8 < end < 3.2, (
        f"该在第 3 秒附近找到真正说完的时刻，量到 {end}")
    assert reel._speech_tail_end(tail_on) is None, (
        "整段都有声音，不该凭空裁出一个尾巴——找不到就该退回 None，"
        "不许比 probe_duration 那条老路更保守")

    # `outro_length()` 要真的用上这个更短的时刻，不是算出来没人接
    naive = reel.OUTRO_TAIL + reel.probe_duration(tail_off)
    fixed = reel.outro_length(tail_off)
    assert fixed < naive - 1.0, (
        f"outro_length 该按真正说完的时刻算，不是文件总长——"
        f"量到 {fixed:.2f}s，该比按总长算的 {naive:.2f}s 短至少 1 秒")


def test_屏幕上的数字不许把字吃掉():
    """账号所有者：「有些字幕没有补全」。

    已发的两条片子里各有一处，都是 `arabic_numerals` 换算换错了：

        eala-pegula 第 12 条   生涯唯一一个巡回赛决赛 → 「生涯唯1个巡回赛决赛」
        jodar-fritz 第 16 条   上一个十几岁走到这一步 → 「上一个10几岁…」

    第一处**真的少了一个字**：「一一」被 `_num_value` 读成 1，配上量词就把两个
    字压成一个。这正是那个函数 docstring 第一段举的「唯一一次」，只是量词从
    「次」换成「个」就漏了过去——**规矩写对了，实现是空的**。第二处是把约数
    当成了数。

    顺带把「一号种子」也归到数字那一路：同一条片子里有「7号种子」「3号种子」，
    只有它是中文，半中半洋（老账：「北京时间8月三号零点」）。

    下半张表是**不许被误伤的**——判据宁可窄，不可宽。
    """
    from tennislive.video.explainer import arabic_numerals  # noqa: PLC0415

    要改的 = [
        ("现在轮到一号种子", "现在轮到1号种子"),
        ("本站一号种子", "本站1号种子"),
    ]
    不许动的 = [
        "生涯唯一一个巡回赛决赛",      # ← 少字的那一处
        "唯一一次拿到冠军",
        "上一个十几岁就走到这一步的",   # ← 约数的那一处
        "二十几场比赛",
        "统一号召大家",                # 「一号」不是每次都是号码
        "一场首轮",
        "第四轮两盘落后",
        "他是家里第四个",
        "有一点点慢",
    ]
    还要照旧转的 = [
        ("七号种子费尔南德斯", "7号种子费尔南德斯"),
        ("二〇二四年美网亚军", "2024年美网亚军"),
        ("世界第一百四十的外卡", "世界第140的外卡"),
        ("十九岁", "19岁"),
        ("先输一比六", "先输1比6"),
        ("抢七七比九", "抢七7比9"),
        ("四百六十九块", "469块"),
        ("整场他只让对手拿到四局", "整场他只让对手拿到4局"),
    ]
    for src, want in 要改的 + 还要照旧转的:
        assert arabic_numerals(src) == want, (
            f"{src!r} 换算成了 {arabic_numerals(src)!r}，应该是 {want!r}")
    for src in 不许动的:
        assert arabic_numerals(src) == src, (
            f"{src!r} 被换成了 {arabic_numerals(src)!r}——屏幕上会少字或者写出"
            "一个没写完的数")


def test_旁白里的百分号要在dry_run前拦住():
    """屏幕可以写 49%，中文配音原文必须写「百分之四十九」。"""
    reel = _reel()
    spec = json.loads(
        Path("specs/reels/zheng-you-us-open-2026-q1.json").read_text(
            encoding="utf-8"
        )
    )
    spec["segments"][2]["narration"] = "拿下了她四十九%的发球分。"

    with pytest.raises(reel.ReelError, match="百分之四十九"):
        reel.validate_spec(spec)


def test_百分之要换成百分号不许换成一百分之():
    """`swiatek-arango` 渲完抽帧才看见的：屏幕上写着「一发得分率是100分之100」。

    旁白里那句是「百分之百」——**写法是对的**，CLAUDE.md 2026-08-16 起要求
    「百分比写百分之 N，不写几成几」，而且账号所有者那句原话是「就说百分之多少
    **用数字写上**」。坏的是换算：`arabic_numerals` 的通用那一轮把「百分之」
    里的那个「百」也当成了数，于是「百分之百」→「100分之100」。

    ⚠️ **它一个字都不报**：`--dry-run`、`--check-narration`、全量测试、
    `check_reel_landed` 全绿——那句话在 spec 里是对的，错的只有烧进画面的那一份。
    是把成片从 Release 拉回来抽帧、放大读字幕才看见的（CLAUDE.md「片子做完要
    抽帧看」）。

    ⚠️ 而这条规矩立起来之后，**每一条带百分比的 spec 都会走到这儿**——所以它
    不是一个边角，是新规矩自带的一个坑。

    下半张表是**不许被误伤的**——判据宁可窄，不可宽。
    """
    from tennislive.video.explainer import arabic_numerals  # noqa: PLC0415

    要换成百分号的 = [
        ("一发得分率是百分之百", "一发得分率是100%"),
        ("从百分之六十四涨到百分之百", "从64%涨到100%"),
        ("百分之五十", "50%"),
        ("百分之七十七", "77%"),
        # 两个百分比夹着一个「比」——不先换的话，比分那一轮会从中间把它劈开
        ("百分之六十四比百分之五十", "64%比50%"),
    ]
    不许被误伤的 = [
        ("生涯唯一一个巡回赛决赛", "生涯唯一一个巡回赛决赛"),
        ("抢七七比九", "抢七7比9"),
        ("世界第一百四十的外卡", "世界第140的外卡"),
        ("四百六十九块", "469块"),
    ]
    for src, want in 要换成百分号的 + 不许被误伤的:
        assert arabic_numerals(src) == want, (
            f"{src!r} 换算成了 {arabic_numerals(src)!r}，应该是 {want!r}")

    # 这一步必须**排在最前面**：要在「四位年份」和「比分」两轮之前跑完，
    # 否则「百分之」里那个「百」会先被别人吃掉。位置这一头单独钉一次——
    # 只测行为的话，把它挪到比分那一轮之后只有上面第 5 条会红，而那一条
    # 很容易被下一个人当成「这种写法本来就不支持」删掉。
    import inspect  # noqa: PLC0415

    from tennislive.video import explainer  # noqa: PLC0415
    body = inspect.getsource(explainer.arabic_numerals)
    assert body.index("百分之(") < body.index("(?=年|赛季|届)"), (
        "换百分比那一步要排在年份/比分之前，不然「百分之」里的「百」会被当成数")


def test_百分点是一个词不是数():
    """上一条的同族漏网词：「二十二个百分点」被换成了「22个100分点」。

    「百分点」没有「之」，进不了上一条那个 `百分之(...)` 的正则，走的是通用
    那一轮 `one()`——而「百」命中那里的 `_STRUCTURED`（含十/百/千），于是被
    换成 100。屏幕上是一句不通的话。

    ⚠️ **它躺了多久，是量出来的**：`arabic_numerals` 里原来就有一条注释点名
    说过「百分点」不在范围里，还写着「量过：全仓库三处全在注解和小红书正文里，
    一处都没进 `narration`」，据此判定它是个**没被触发过的坑**，并留了一句
    「真要用这个词，先把它一起收进来」。**那个量后来过期了**：
    `tiafoe-nakashima-cincinnati-2026-sf` 的第 10 段旁白写着「比对手高出十五个
    百分点」，那条片子的字幕**已经带着「15个100分点」发出去了**（已发不重渲）；
    `chwalinska-townsend-us-open-2026-r1` 渲完抽帧又撞了一次。带数字的注释会
    过期，而它过期的时候不吭声——CLAUDE.md 记过同一个形状。

    ⚠️ 和上一条一样，**四道闸一道都没响**：spec 里那句话是对的，错的只有烧进
    画面的那一份，只有把成片拉回来抽帧读字幕才看得见。

    下半张表是**不许被误伤的**：裸的「百」在别处照旧当数换。
    """
    from tennislive.video.explainer import arabic_numerals  # noqa: PLC0415

    百分点不许当数 = [
        ("比对面高出二十二个百分点", "比对面高出22个百分点"),
        ("比对手高出十五个百分点", "比对手高出15个百分点"),
        ("差四十个百分点", "差40个百分点"),
    ]
    不许被误伤的 = [
        # 裸的「百」照旧是数
        ("一发平均只有一百三十九公里", "一发平均只有139公里"),
        ("排名掉到两百七十位", "排名掉到270位"),
        ("第一百场", "第100场"),
        # 「百分之」那一条不受影响
        ("百分之百", "100%"),
        ("百分之八十二", "82%"),
    ]
    for src, want in 百分点不许当数 + 不许被误伤的:
        assert arabic_numerals(src) == want, (
            f"{src!r} 换算成了 {arabic_numerals(src)!r}，应该是 {want!r}")


def test_硬地的地要读四声():
    """账号所有者 2026-08-02：「『硬地』这里的『地』是读 dì（四声）。配音要记住。」

    「硬」是形容词，合成器就把「地」当成状语助词读成了轻声 de。可这儿它是名词
    ——硬地、红土、草地是三种场地。这个词在「开球之前」里到处都是（「换到硬地」
    「第一个硬地决赛」），**不能靠每条片子改一次文案**，所以收在 `speakable`。

    两条断言：换给合成器的那一份要改，**屏幕上那一份不许动**；而且
    **字数必须一样**——字幕时间轴是按字位从合成那份映射回显示那份的，
    长度一变整段字幕就漂了（换成「硬场地」就是这么坏的）。
    """
    from tennislive.video.explainer import readable, speakable  # noqa: PLC0415

    for line in ("这一周他换到硬地。", "这是她第一个硬地决赛。",
                 "硬地赛季从这里开始"):
        said, shown = speakable(line), readable(line)
        assert "硬地" not in said, (
            f"{line!r} 交给合成器的还是「硬地」，那个「地」会被读成轻声 de")
        assert "硬地" in shown, f"{line!r} 屏幕上的那一份被改掉了，只能改配音那份"
        assert len(said) == len(shown), (
            f"{line!r} 两份字数不一样（{len(said)} vs {len(shown)}）"
            "——字幕时间轴按字位映射，长度一变整段就漂")


def test_年份里的圈零要换成零否则合成器认不出这是年份():
    """账号所有者 2026-08-27：「tts 里 2002 年读音错误」。

    旁白按仓库惯例写「二〇〇二年」（`〇` 是 U+3007）。量出来问题不在写法对不对，
    在**合成器认不认得它是个年份**——同一把嗓子同一语速，只换这一个字，切词
    完全变了（edge-tts 的 WordBoundary，实测）：

        二〇〇二年   二｜〇｜〇｜二年   ← 「二年」被黏成一个词    二零零二年   整体
        二〇二四     二｜〇｜二｜四    ← 四个孤立字             二零二四     整体
        一九九九年   一九九九年（本来就整体）——**它没有 〇**

    末行是反证：唯一不带 `〇` 的年份本来就被整体识别，所以是 `〇` 把年份打散的。
    而 **2002 是唯一一个把「二年」黏成一个词的**，那正是「两年」那个量词短语的
    形状——账号所有者点的正是这一年。

    判据钉三头，缺一头都是恒真：
    ① 交给合成器的那份不许再有 `〇`；② **屏幕上那份不许动**；
    ③ **字数必须一样**——和「硬地→硬帝」同一个前提，字幕时间轴按字位从合成那份
    映射回显示那份，长度一变整段就漂。

    ⚠️ 非年份的 `〇` 一并换掉是安全的：这个仓库里 `〇` 只当数字零用（年份、赛季、
    比分），而 `六比〇`→`六比零` 实测字节数一模一样，没有回归。
    """
    from tennislive.video.explainer import readable, speakable  # noqa: PLC0415

    for line in ("他二〇〇二年转的职业。", "整个二〇二二赛季报销。",
                 "一九八九、二〇二四。", "六比二、六比〇，七十一分钟。"):
        said, shown = speakable(line), readable(line)
        assert "〇" not in said, (
            f"{line!r} 交给合成器的还带着 〇，年份会被打散成孤立字")
        assert said.count("零") == shown.count("〇") + shown.count("零"), (
            f"{line!r} 换得不干净")
        assert "〇" in shown, f"{line!r} 屏幕上那一份被改掉了，只能改配音那份"
        assert len(said) == len(shown), (
            f"{line!r} 两份字数不一样（{len(said)} vs {len(shown)}）"
            "——字幕时间轴按字位映射，长度一变整段就漂")

    # 判据自己的判据：这条规矩要真的盖住存量，不是只对我编的例句成立
    import json  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    seen = 0
    for f in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(f.read_text(encoding="utf-8"))
        for seg in spec.get("segments", []):
            text = seg.get("narration") or ""
            if "〇" in text:
                seen += 1
                assert "〇" not in speakable(text), f"{f.name} 没换干净"
    # 存量里 reel 这条线用 〇 的段落不多，但一条都不许漏；真降到 0 说明主语没了
    assert seen >= 1, "没有一条 spec 的旁白带 〇 了——这条判据的主语没了，该换判据"


def test_封面那一路的溶解底料不许在委托链上掉队():
    """`build_cover` 有**两个** return，两个都委托给 `build_versus_poster`：
    上面那个是 solo（网球有故事），下面那个是 VS（赛场之上／开球之前）。

    加 `tail`（溶解底料）时只改了上面那个，于是**这两个栏目的封面片段没有多切
    那 0.18 秒**。`xfade` 的 offset 正好落在封面流的末尾，整条溶解链塌掉：

        段落加起来 114.46s，成片 12.44s（run 30752134514 / 30752131692）

    而 `ruff --select F821` 抓不到——`tail` 在 `build_cover` 的作用域里是有定义
    的，只是没往下传，被调方悄悄用了默认值 0.0。**同一对函数栽的第三次**
    （前两次是 `seconds` 和 `_cut_person` 的 `source`）。

    所以判据盯**每一个** return：`build_cover` 里凡是调 `build_versus_poster`
    的，都必须把 `tail` 带上。参数一多、出路一多，`replace(..., 1)` 这种改法
    就会挑错一个。
    """
    reel = _reel()
    body = inspect.getsource(reel.build_cover)
    calls = [line for line in body.splitlines()
             if "build_versus_poster(" in line and not line.lstrip().startswith("#")]
    assert len(calls) >= 2, (
        f"`build_cover` 里只找到 {len(calls)} 处 build_versus_poster 调用，"
        "判据失效了——出路变了就回来重写这条")
    # 调用是跨行的，所以按「从调用处到该 return 结束」整块看
    blocks = re.findall(r"build_versus_poster\((?:[^()]|\([^()]*\))*\)", body)
    assert len(blocks) == len(calls), "有调用跨行跨得更狠，正则没框住"
    for block in blocks:
        assert "tail=" in block, (
            "`build_cover` 有一条 return 没把 `tail` 传下去：\n  "
            + " ".join(block.split())
            + "\n封面片段就会少切那几秒溶解底料，xfade 的 offset 落到流的末尾，"
              "整条片子在第一个接缝上截断——而 ffmpeg 一个字都不说")

    # 被调方真的用它：signature 里有，而且用在了传给 _still_to_clip 的时长上
    poster = inspect.getsource(reel.build_versus_poster)
    assert "tail: float" in poster, "`build_versus_poster` 没有收 tail 的口子"
    assert "seconds + tail" in poster, (
        "`build_versus_poster` 收了 tail 却没用在时长上——签名对了，实现是空的")


def test_推送的标题和正文出处是spec不是命令行():
    """`matchup` / `summary` / `lead` 的出处是 spec，不是工作流输入。

    2026-08-02 我在工作流输入里手打推送正文，把「十九岁的霍达尔」打成
    「**九岁**的霍达尔」，还把「8 号种子 / 四号种子」混着写——在微信发出去之前
    取消了那趟 run 才没出事。

    **根子不是手滑，是那句话没有judge能看见它**：写进 spec 的字会被
    `test_轮次写N强不写分数式`（推送那几栏）和 `test_人名要以译名表为准`
    扫到；敲在 workflow_dispatch 输入里的字，**一条测试都过不了**，直接进微信。

    所以判据钉三样：

    1. 对阵**算得出来**，不用填——`push_meta` 从 `cover.versus.names` 拼
    2. 每条**已经推送过**的 spec 都要自带 `summary` 或 `lead`，否则下次推它
       又得手打
    3. 两样都没有时 `resolve_meta` 要**抛错并说清去补哪个字段**，别静静发一条
       标题末尾空着的消息
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    from push_reel import push_meta, resolve_meta  # noqa: PLC0415
    from types import SimpleNamespace  # noqa: PLC0415

    checked = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if not ((spec.get("cover") or {}).get("versus") or {}).get("names"):
            continue          # solo 版式（网球有故事）算不出对阵，靠 summary
        meta = push_meta(path)
        assert meta["matchup"], (
            f"{path.name} 有 cover.versus.names 却算不出对阵——"
            "那就只能在命令行上手打，而手打的字不过任何一条内容测试")
        checked += 1
    assert checked >= 10, f"只校到 {checked} 条 spec，判据失效了"

    # 两样都没有 → 必须抛错，而且要说清去补哪儿
    import tempfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "x.json"
        fake.write_text(json.dumps({"cover": {"eyebrow": "赛场之上"}}),
                        encoding="utf-8")
        args = SimpleNamespace(matchup="", score="", event="", summary="", lead="")
        try:
            resolve_meta(Path(tmp) / "x.copy.html", args)
        except SystemExit as exc:
            assert "summary" in str(exc), (
                f"报错没说去补哪个字段：{exc}")
        else:
            raise AssertionError("spec 里什么都没有，还是算出了标题——这条会发出"
                                 "一条末尾空着的消息")


def test_一段里的长留白要提示但不再阻断渲染():
    """账号所有者 2026-08-02：「不是补全的问题，我是说有些没有字幕了，给漏掉了」
    「利用完整区域，整个里面去读一下」。

    按时间轴通读已发的成片：**jodar-fritz 68.7s / 185.4s（37%）屏幕上没有字**。
    不是字幕丢了——**是那几秒没人在说话**，集中在每段后半截（短句配了长窗口）。

    最刺眼的一点：**这个数一直印在 `mode=narration` 的输出里**（「余量 +6.44s」），
    只是被当成「还很宽裕」读了，没有人把它读成「这里有六秒半的哑场」。
    所以这一条不需要新数据、不需要新一趟渲染，只需要**把同一个数的另一头也判一次**。

    门槛卡「单段最长」，不卡总占比——1~3 秒是句子之间正常的换气，填满反而赶。
    分布很干净，4.0s 两头都不贴边：

        补之前 jodar   最长一段 6.44s，>4s 的有 5 段
        补之后 jodar   最长一段 2.89s
        eala-pegula    最长一段 2.99s

    没有旁白的段**不算**：那是故意留给现场声的（「有原声的片子：说话时压，
    不说话时放开」），不是忘了写。
    """
    reel = _reel()
    from types import SimpleNamespace  # noqa: PLC0415

    def seg(length, narration="一句话"):
        return SimpleNamespace(length=length, narration=narration)

    # ① 已发那一版的真实数字必须被提示出来
    was = [seg(11.0), seg(11.5), seg(17.0), seg(10.5), seg(10.0)]
    spoken = {0: 4.56, 1: 5.18, 2: 11.68, 3: 5.47, 4: 5.71}
    caught = reel.silent_stretches(was, spoken)
    assert len(caught) == 5, (
        f"补之前那五段哑场只抓到 {len(caught)} 段——门槛松了")
    assert "6.4" in caught[0], f"报错里没写清楚空了多久：{caught[0]}"

    # ② 补之后的真实数字必须放行（门槛不能收得太狠）
    now = [seg(11.0), seg(8.0), seg(12.0), seg(9.0)]
    assert reel.silent_stretches(
        now, {0: 8.37, 1: 6.08, 2: 9.89, 3: 5.70}) == [], (
        "补完之后（单段最长 3.30s）被误判成哑场——1~3 秒是正常换气")

    # ③ 整段没有旁白的不算：那是故意留给现场声的
    assert reel.silent_stretches([seg(20.0, "")], {}) == [], (
        "整段没有旁白的被判成哑场了——那是留给现场声的，不是忘了写")

    # ④ 提示要**排在编码之前**，让人尽早看见；但有现场声时不能因此失败。
    body = "\n".join(
        line for line in inspect.getsource(reel.render).splitlines()
        if not line.lstrip().startswith("#"))
    assert "silent_stretches(" in body, "render 里没接这道闸"
    assert body.index("silent_stretches(") < body.index("cut_segment("), (
        "长留白提示排在分段编码之后了——它一个源片都不用碰，应该提前报")
    after_idle = body.split("idle = silent_stretches(segments, spoken_of)", 1)[1]
    before_encode = after_idle.split("tracks = track_shots", 1)[0]
    assert "raise ReelError" not in before_encode, (
        "超过 4 秒的旁白留白仍会阻断 render；有现场声时它只能提示")


# 发在这条规矩之前的那一条，**只许减不许加**。它是那次翻车的现场，留着当锚点：
# eala-svitolina 12 段里 7 段在报幕（58%），读者的原话是
# 「她发球，她接发。。。她发球，她接发。她发球，对面接发。。。」——几乎是原文引用。
#
# ⚠️ **名单里只有它一条，是量出来的，不是估的。** 我一开始按一个更宽的正则
# （把「他的发球局」也算上）以为 eala-osaka 35%、wong-gea 30% 也超标，顺手写进
# 了名单——`_BOARD_LEGACY` 那条自检当场报「wong-gea 已经不超标了」。
# **豁免名单也要自证它豁免的是真的超标**，否则拦的是空气。
_BOARD_LEGACY = {"eala-svitolina"}

# 一条片子里最多多少段可以提「谁在发球」。
#
# **卡的是密度，不是单次出现**——单次往往是有信息的：「轮到自己发球，三十比
# 四十——帕雷哈的第二个盘点」讲的是**保发被逼到悬崖**，和「没能兑现破发点」
# 完全是两回事。第一版我禁了任何一次出现，当场误伤这句好台词。
#
# 量出来两档分得很开，25% 落在中间不贴边：
#
#     ❌ eala-svitolina 58%（7/12）
#     ✅ wong-gea 20%   wang-pareja 11%   gea-shapovalov 6%   最近三条 0%
_BOARD_SHARE_MAX = 0.25


def test_旁白不许把每一局都念一遍():
    """**「轮到她发球」这类话，记分牌上一直写着——一段两段是信息，半条片子是流水账。**

    小红书读者 2026-08-02 的评论：「她发球，她接发。。。她发球，她接发。
    她发球，对面接发。。。😂😂😂😂」，底下跟着一句「这解说，，」。量下来
    他没夸张——`eala-svitolina` **12 段里 7 段（58%）**在报谁发球。

    这和已经被禁的「画面里是」是**同一族**：把观众已经看见的东西再指一遍，
    只不过那条指的是画面，这条指的是**烧在画面上的记分条**。

    ⚠️ **卡密度不卡单次，是踩出来的。** 第一版禁了任何一次出现，当场误伤
    `wang-pareja` 那句「轮到自己发球，三十比四十——帕雷哈的第二个盘点」——
    在**自己的发球局**被逼到盘点，和「破发点没兑现」是两件事，说清楚是有信息的。
    又一次「判据宁可窄，不可宽」。

    ⚠️ **这条也不禁比分。** CLAUDE.md 早就救回过「5-6 落后，三个盘点她一个也
    没让」——比分在那儿是**制造张力**的手段。

    ⚠️ **它拦不住「平淡」本身。** 顺序、有没有立场、钩子留没留，都是编辑判断，
    机械挡不住（见 CLAUDE.md「最硬的那个事实放第 ① 屏」那条为什么故意没有
    测试）。这条只拦一种**能量出来**的坏：把每一局按顺序念一遍。

    根子记在 CLAUDE.md：仓库里「旁白要把比赛走向讲清楚」被我执行成了「把每一局
    念一遍」。**走向是四个点**（谁领先 → 谁追上 → 转折在哪 → 怎么收），
    不是九局流水。
    """
    announce = re.compile(
        r"轮到.{0,4}发球"
        r"|自己的?发球局"
        r"|对面的?发球局"
        r"|对面发球(?!局)"
        r"|(?:紧接着|下一局|这一局)[^。；]{0,6}发球局")
    bad = []
    for slug, spec in sorted(_reel_specs().items()):
        if slug in _BOARD_LEGACY:
            continue
        segs = [s for s in spec["segments"] if (s.get("narration") or "").strip()]
        if len(segs) < 5:
            continue
        hit = [s for s in segs
               if announce.search((s.get("narration") or "")
                                  + _quote_str(s.get("quote")))]
        share = len(hit) / len(segs)
        if share > _BOARD_SHARE_MAX:
            bad.append(f"{slug}：{len(hit)}/{len(segs)} 段（{share:.0%}）在报"
                       f"「谁在发球」，第一处 @{hit[0]['start']}")
    assert not bad, (
        "旁白把每一局按顺序念了一遍——记分条上一直写着，说了等于没说：\n  "
        + "\n  ".join(bad)
        + "\n\n走向讲**四个点**（谁领先 → 谁追上 → 转折在哪 → 怎么收），"
          "不是每一局都交代一次开球权。")

    # 反面锚点：这些必须**过**——比分和保发是制造张力的手段，不是报幕
    for keeper in ("五比六落后，三个盘点她一个也没让",
                   "先输一比六，再掀翻头号种子",
                   "赛点，黄泽林在二区发出内角 Ace。球落地，他放下球拍，双手掩面。"):
        assert not announce.search(keeper), f"误伤了一句好台词：{keeper}"

    # 判据自己的判据：三条 legacy 必须真的超标，否则这条测试拦的是空气
    for slug in _BOARD_LEGACY:
        spec = _reel_specs()[slug]
        segs = [s for s in spec["segments"] if (s.get("narration") or "").strip()]
        hit = sum(1 for s in segs if announce.search(s.get("narration") or ""))
        assert hit / len(segs) > _BOARD_SHARE_MAX, (
            f"{slug} 已经不超标了，把它从 _BOARD_LEGACY 里去掉")


# 离线估旁白长度 ------------------------------------------------------------
# 判据的样本从**已发的成片**里取：每一段旁白的真实秒数就是闸自己量到的那个数
# （`narration_overruns` 拿 mp3 时长），而它落在 `subtitles.ass` 里——这一段的
# 最后一条字幕正好收在「本段起点 + 旁白时长」上。
#
# ⚠️ 不用 `voice_NN.words.json` 的末事件：那是**词末**，比 mp3 短一个固定的
# 0.83 秒（从 9 条片子 121 段反解出来，min 0.800 / 中位 0.829 / max 0.851），
# 照它标定会把整条模型往短里拉。


def _ass_cues(path: Path) -> list[tuple[float, float]]:
    def sec(t: str) -> float:
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    def shown(raw: str) -> str:
        """字幕那一格真正画出来的字：去掉 `{\\fs78}` 这类覆盖标签和换行。"""
        return re.sub(r"\{[^}]*\}", "", raw).replace("\\N", "").strip()

    return [(sec(f[1]), sec(f[2]), shown(f[9]))
            for f in (line.split(",", 9)
                      for line in path.read_text("utf-8").splitlines()
                      if line.startswith("Dialogue:"))]


def _measured_narration() -> list[tuple[str, int, int, int, float]]:
    """`[(slug, 段序号, 字数, 句读数, 实测秒数)]`，取自已发成片。

    **CI 上是空的**（`output/` 不在稀疏检出里），所以它只当加餐——核心判据是
    下面那张冻结下来的表。
    """
    reel = _reel()
    out: list[tuple[str, int, int, int, float]] = []
    for rj_path in sorted(Path("output").glob("*/reel/*/render.json")):
        outdir = rj_path.parent
        spec_path = Path(f"specs/reels/{outdir.name}.json")
        ass = outdir / "subtitles.ass"
        if not spec_path.is_file() or not ass.is_file():
            continue
        spec = json.loads(spec_path.read_text("utf-8"))
        cues = _ass_cues(ass)
        render_json = json.loads(rj_path.read_text("utf-8"))
        # ⚠️ **`render.json` 现在有两种，别拿硬下标去索引。** 2026-08-13
        # `archive-media` 把历史成片迁上 Release 时，会把链接写进同目录的
        # `render.json`，**不存在就从 `{}` 建一份**——而 `render.json` 是
        # 2026-08-02 才开始写的，07-28~07-30 那八条早期片子根本没有，于是
        # 落下八个只有 `video_url` / `video_bytes` 的存根。那是合法数据
        # （`push_reel.released_video_url()` 就靠它找成片），只是没有渲染
        # 元数据。原来这儿写的是 `render_json["cover_seconds"]`，迁移完当场
        # KeyError——**加餐把整条测试带崩了**，而它本来的契约是「产物读不了
        # 就跳过」。
        # ⚠️ **别的 TTS 后端渲出来的成片，不是今天这个模型的证据。** 系数按
        # `SPEECH_FITTED_BACKEND` 拟合（现在是 Azure），而 2026-08-04 之前那
        # 十三条走的是 edge-tts。同一把 `YunjianNeural`、同样 `+6%`，两个后端
        # 的中位差 **0.6 秒**（edge +0.13 / azure −0.49）——混在一起校，量到的
        # 是后端差不是模型差，而它长得就像「模型漂了」。2026-08-15 那次
        # `abs(mid) <= 0.4` 报红就是这么来的：老系数对 edge-tts 一直准
        # （中位 +0.04），只是 Azure 占了 81% 把池化中位数拖过了线。
        #
        # 没记 `narration_backend` 的一律算「对不上」：那个字段是和 Azure 一起
        # 加进来的，缺它就说明这条渲在切换之前。**跳过要出声**，否则「这批不算
        # 数」和「取法写错了」长得一模一样——下面 `len(live) >= 60` 那道底也是
        # 为这个留的。
        backend = render_json.get("narration_backend")
        if "cover_seconds" in render_json and backend != reel.SPEECH_FITTED_BACKEND:
            print(f"  [跳过] {outdir.name} 是 {backend or '(没记后端)'} 渲的，"
                  f"而系数按 {reel.SPEECH_FITTED_BACKEND} 拟合——"
                  "换后端的成片校不了这个模型")
            continue
        offset = render_json.get("cover_seconds")
        if offset is None:
            print(f"  [跳过] {outdir.name} 的 render.json 只有 Release 链接，"
                  "没有渲染元数据（archive-media 建的存根）")
            continue
        # 2026-08-02 之后渲的片子把闸自己量到的秒数直接记进了 `render.json`，
        # 不用再从字幕反解。老片子没有这一项，退回反解。
        recorded = render_json.get("narration_seconds") or {}
        if recorded:
            segs = spec.get("segments") or []
            # ⚠️ **产物可能是上一版的，而且「序号还在」比「序号越界」更坏。**
            # 改 spec 不重渲是常事（措辞、注解、规矩追认、重排段落）。
            # `eala-pegula-final` 从 14 段重排成 8 段时，越界的那几个会 IndexError
            # ——那还算出声；**没越界的那几个会静默指到另一段身上**，于是这条
            # 测试报「最坏一段差 6.63s」，看起来像模型不准，其实是产物对错了人。
            # 又一次「voice 文件要按内容认领，不按序号」，只是换到了 render.json。
            #
            # `render.json` 自己记着渲的时候那份 spec 的画面总长，拿它对一下就
            # 能自证是不是同一版。对不上就**整个 outdir 跳过并出声**——这一段
            # 本来就是加餐，核心判据是下面那张冻结的样本表。
            # 段长走 `seg_seconds`（成片口径）：慢放段按速度换算，speed=1 不变
            spec_secs = round(sum(reel.seg_seconds(s) for s in segs), 2)
            was = round(float(render_json.get("segments_seconds", -1)), 2)
            if abs(was - spec_secs) > 0.05:
                print(f"  [跳过] {outdir.name} 的产物是上一版的："
                      f"渲的时候画面 {was}s，现在的 spec 是 {spec_secs}s")
                continue
            # ⚠️ **画面总长对得上，不等于说的是同一句话。** 2026-08-05 我按
            # 读者反馈改了 `shang-rublev` 第 9、10 段的措辞——**窗口一个字节
            # 没动**，所以上面那道「渲的时候画面几秒」的自证一路放行，而
            # `narration_seconds` 记的还是旧稿的秒数，这条测试当场报
            # 「最坏一段差 2.13s」，看起来像模型不准。
            #
            # `subtitles.ass` 里存着**真正念出去的那句话**，拿它按内容认领——
            # 和下面那条路（`words.json` 的 `joined != plain`）是同一个办法，
            # 只是这一支之前漏了。**「碰巧对」和「真的接上了」长得一模一样。**
            starts, acc = {}, float(offset)
            for index, seg in enumerate(segs):
                starts[index] = acc
                acc += reel.seg_seconds(seg)
            for key, secs in recorded.items():
                index = int(key)
                seg = segs[index]
                text = str(seg.get("narration", ""))
                plain = "".join(c for c in text if c not in
                                reel._SPEECH_PUNCT + reel._SPEECH_QUIET)
                head = starts[index]
                # 段窗长度走 seg_seconds（成片口径）——整屏证据段没有
                # start/end，读 seg["end"] 会 KeyError（cincinnati 落库当天
                # 这条就是这么红的），而 starts 那头本来就用的它
                span = reel.seg_seconds(seg)
                said = "".join(c[2] for c in cues
                               if head - 0.01 <= c[0] < head + span - 0.01)
                said = "".join(c for c in said if c not in
                               reel._SPEECH_PUNCT + reel._SPEECH_QUIET + " ")
                # 字幕把汉字数字换成了阿拉伯数字，所以比不了逐字——比长度就够：
                # 改措辞必然改字数，而这正是要拦的那一类
                if said and abs(len(said) - len(plain)) > max(4, len(plain) // 6):
                    print(f"  [跳过] {outdir.name} 第 {index + 1} 段的产物是"
                          f"上一版的：字幕里念的 {len(said)} 字，"
                          f"现在的 spec 是 {len(plain)} 字")
                    continue
                body = "".join(c for c in text if c not in reel._SPEECH_QUIET)
                punct = sum(1 for c in body if c in reel._SPEECH_PUNCT)
                # ⚠️ 按词念的拉丁串单算一维（`Law Roach` / `QueenWen`），
                # 全大写的缩写（ACE / WTA / ATP）仍然算在汉字那一维里——
                # 它们逐字母念，和汉字一个价。见 reel_timing.SPEECH_PER_LATIN。
                latin = reel.latin_word_letters(text)
                out.append((outdir.name, index, len(body) - punct - latin,
                            latin, punct, round(float(secs), 2)))
            continue
        for index, seg in enumerate(spec.get("segments") or []):
            length = float(seg["end"]) - float(seg["start"])
            text = str(seg.get("narration", "")).strip()
            words = outdir / f"voice_{index:02d}.words.json"
            start, offset = offset, offset + length
            inside = [c for c in cues if start - 0.01 <= c[0] < start + length - 0.01]
            if not text or not words.is_file() or not inside:
                continue
            # **按内容认领，不按序号。** 跨次重渲的目录里留着旧的 voice 文件，
            # 只比个数会被骗过去（CLAUDE.md 记过；这一轮真剔掉了 9 段）。
            events = json.loads(words.read_text("utf-8"))
            joined = "".join(e["text"] for e in events).replace(" ", "")
            plain = "".join(c for c in text
                            if c not in reel._SPEECH_PUNCT + reel._SPEECH_QUIET)
            spoken = max(c[1] for c in inside) - start
            # 字幕被收进本段窗口，贴着段尾的那些量出来是截断值，不是旁白长度
            if not events or joined != plain or spoken >= length - 0.02:
                continue
            body = "".join(c for c in text if c not in reel._SPEECH_QUIET)
            punct = sum(1 for c in body if c in reel._SPEECH_PUNCT)
            out.append((outdir.name, index, len(body) - punct, punct,
                        round(spoken, 2)))
    return out


# 从上面那套办法里挑出来冻结的一份，按字数从短到长铺开（1.42s ~ 30.19s）。
# **这一份必须留在测试里**：`output/` 在 CI 上不存在，判据的主语没了就会变成
# 一盏恒真的绿灯——2026-08-01 那次「只校到 0 条」就是这么来的。
#
# ⭐ 2026-08-15 **整张表换过一次**：原来那 17 条里 16 条是 edge-tts 渲的，而
# 系数已经按 Azure 重拟合（见 `build_match_reel.py` 里 `SPEECH_FITTED_BACKEND`
# 上面那段）。**留着它们等于让 CI 拿一个已经不生产任何东西的后端来判卷**——
# 老样本在新系数下中位 +0.60、最坏 2.37，两条断言一起红，而模型对今天的产物
# 是准的。所以表跟着系数走：现在每一条都出自 `narration_backend == "azure"`
# 的成片，取法和以前一样（按字数铺开 + 两头的极端）。
_SPEECH_FIXTURE = [
    ("eala-story", 16, 4, 1, 1.42),
    ("chwalinska-gibson", 7, 14, 2, 3.48),
    ("rybakina-osaka", 5, 17, 2, 3.94),
    ("svitolina-alexandrova", 5, 20, 3, 4.82),
    ("zhang-sabalenka", 5, 23, 4, 6.12),
    ("eala-story", 2, 25, 3, 5.57),
    ("gauff-korneeva", 2, 27, 3, 5.88),
    ("zverev-griekspoor", 9, 29, 4, 6.89),
    ("osaka-fernandez", 2, 31, 4, 7.06),
    ("wangxiyu-timofeeva", 1, 33, 6, 7.42),
    ("eala-story", 6, 37, 3, 7.94),
    ("wangxiyu-timofeeva", 6, 42, 6, 9.10),
    ("baez-dimitrov", 9, 50, 7, 12.10),
    # 长的那一头也要有：154 字是目前最长的一段，短样本再多也证明不了长句上
    # 系数没跑偏（老系数正是「长段估得太长」栽的，见 speech_seconds 的注释）。
    ("swiatek-rybakina-toronto-final", 7, 154, 13, 30.19),
    # 两头的极端也要在表里——**样本不带尾巴，误差带子就没法自证不虚高**。
    # 580 段里最偏的就这两条（−1.49 / +1.64），而 `SPEECH_EST_ERR` 正是按
    # 后者定的：漏掉它，那道「不许比冻结样本最坏还宽出半秒」的自检会当场
    # 把带子判成虚高——两条闸互相打架，闸本身就失效了。
    ("rybakina-osaka", 6, 44, 4, 7.54),
    ("wang-kasatkina", 11, 34, 6, 9.65),
    # ⭐ 2026-08-31 的新尾巴，也是**唯一一条超出旧带子的**：数字密集的句子，
    # 模型看不见这一维（九个数挤在一句，实测 0.245 秒/字 对模型的 0.166）。
    # 它在表里是为了让「带子不许虚高」那条自检有据可依——不放进来，
    # SPEECH_EST_ERR=2.20 会被判成宽出太多，两条闸互相打架。
    ("chwalinska-townsend-us-open-2026-r1", 9, 66, 8, 16.15),
]


def test_离线估旁白长度要对得上真产物():
    """`speech_seconds` 的系数是从已发成片拟合的，不是拍的。

    CLAUDE.md 里那条「`字数 × 0.23 + 句读 × 0.25`，再留 0.3 秒余量」错得有
    方向：长段估得太长（gea-shapovalov 第 5 段 91 字估 21.4s、实测 16.7s），
    短段估得太短。照它排段，长段白留五秒空白，短段要等六分钟的 render 才知道
    装不下。

    这条测试钉两件事：

    1. **系数真的对得上实测**——每一段的误差都在 `SPEECH_EST_ERR` 以内，
       而且中位数贴近 0（宽带子谁都过得了，得证明它是准的不是松的）。
    2. **`SPEECH_EST_ERR` 不许比实测误差还小**——它是 dry-run 判「估得再乐观
       也装不下」的那把尺，写小了就会把好 spec 判红。
    """
    reel = _reel()

    def check(rows, where):
        # ⚠️ 行有两种宽度，**这是故意的**：
        # `_SPEECH_FIXTURE` 是**冻结的基线**（5 元组，纯中文计数），而 2026-09-01
        # 给模型加了「按词念的拉丁串」这一维之后实测那一路变成 6 元组。冻结表里
        # 一条带小写拉丁词的样本都没有（逐条核过：`WTA`/`ACE`/`ATP` 是全大写，
        # 走的还是汉字那一档），所以它照旧成立——**在改模型的同一个提交里重写
        # 基线表，等于把基线本身作废掉**，那就没有东西能证明系数没漂了。
        errs = []
        for row in rows:
            chars, punct, secs = row[2], row[-2], row[-1]
            latin = row[3] if len(row) == 6 else 0
            # 合成一段等价的文本再过 speech_seconds——比在这儿重抄一遍公式好：
            # 公式改了这条判据自己就会跟着走，不会两处分叉。小写的 "a" 串会被
            # 认成「按词念」，正是要校的那一维。
            errs.append(secs - reel.speech_seconds(
                "一" * chars + "a" * latin + "，" * punct))
        worst = max(abs(e) for e in errs)
        assert worst <= reel.SPEECH_EST_ERR, (
            f"{where}：最坏一段差 {worst:.2f}s，超过声明的误差 "
            f"±{reel.SPEECH_EST_ERR}s。要么改系数，要么把这个数调大——"
            "但别只调大，那等于把这道闸松掉")
        mid = sorted(errs)[len(errs) // 2]
        assert abs(mid) <= 0.4, (
            f"{where}：误差中位数 {mid:+.2f}s，模型整体偏了。"
            "系数要重新拟合，不是把误差带子放宽")
        return worst

    assert len(_SPEECH_FIXTURE) >= 12, "冻结的样本太少，判据失效了"
    worst = check(_SPEECH_FIXTURE, "冻结样本")
    # 误差带子也不许虚高：写成 10 秒谁都过得了，那道闸就等于没装
    assert reel.SPEECH_EST_ERR <= worst + 0.5, (
        f"SPEECH_EST_ERR={reel.SPEECH_EST_ERR} 比实测最坏 {worst:.2f}s 宽出太多，"
        "dry-run 那道闸会形同虚设")

    # 加餐：产物在的时候（本地沙箱）拿全量再验一遍。CI 上这里是空的，正常。
    live = _measured_narration()
    if live:
        assert len(live) >= 60, f"只取到 {len(live)} 段实测，八成是取法错了"
        check(live, f"已发成片 {len(live)} 段")


def test_按词念的拉丁串比逐字母念的缩写便宜():
    """`Law Roach` 不能按 `A A A A A A A A A` 收费。

    来路：`osaka-iverson-tribute` 第 ⑦ 段「造型师 Law Roach 牵的线，找的是纽约
    一个牌子，Who Decides War。」——21 个拉丁字母按汉字价收是 3.49 秒，离线估
    7.39 秒而真语音只有 **5.14 秒**，一段就把 ±2.2 的误差带子顶穿了。

    分档的依据是**怎么念**，不是「是不是拉丁字母」：

    - `ACE` / `WTA` / `ATP` 是**逐字母念**的缩写，一个字母约等于一个汉字
      ——已发成片里 60 多段是这一类，老模型对它一直准，所以一个字都不能动；
    - `Law` / `Roach` / `QueenWen` 是**按词念**的，一整个词往往还不到一个
      汉字的工夫。

    ⚠️ 这条钉的是**两档之间的关系**，不是某个具体的秒数——系数以后重新拟合
    时它不该跟着红。

    三个方向反向验证过，红在哪一行是**跑出来的不是推的**：把真词也按汉字价收
    → 红在第 ① 条；把真词做成零成本 → 红在第 ② 条；把 `isupper()` 那道判据
    拆掉（缩写也按词价收）→ **也红在第 ① 条**，因为那时 `Ace` 和 `ACE` 估出来
    一样，① 先撞上。第 ③ 条守的是另一头（有人只调便宜缩写那一档），单独拆它
    才轮得到它出声。
    """
    reel = _reel()

    han = "他发了三个"          # 5 个汉字，两档共用的底
    acro = reel.speech_seconds(han + "ACE。")
    word = reel.speech_seconds(han + "Ace。")
    plain = reel.speech_seconds(han + "。")

    # ① 真词要比同样长的缩写便宜——这是这条修正的全部内容
    assert word < acro - 0.1, (
        f"「Ace」估 {word:.3f}s、「ACE」估 {acro:.3f}s，两档没分开："
        "按词念的拉丁串被当成逐字母念的缩写在收费")

    # ② 但真词不是免费的：三个字母总得有点工夫，不然长英文名会被严重低估
    assert word > plain + 0.05, (
        f"「Ace」估 {word:.3f}s、什么都不加估 {plain:.3f}s：拉丁词被当成零成本，"
        "长英文名会被低估到装不下")

    # ③ 缩写那一档不许被顺手改便宜——60 多段已发成片是靠它校准的
    assert abs(acro - (plain + 3 * reel.SPEECH_PER_CHAR)) < 1e-6, (
        f"「ACE」估 {acro:.3f}s，不等于三个汉字的价钱：全大写缩写是逐字母念的，"
        "它的收费不该跟着真词那一档走")

    # ④ 落单的字母也走缩写档（`W100` 的 W 是念出来的 “double-u”）
    lone = reel.speech_seconds(han + "W。")
    assert abs(lone - (plain + reel.SPEECH_PER_CHAR)) < 1e-6, (
        f"单个字母估 {lone:.3f}s：它是逐字母念的，该走缩写那一档")


def test_估体积的码率只许按实测往上调():
    """`MEASURED_REEL_KBPS` 是**估走哪条路**用的，低估的方向是危险的那一头。

    4990 是按 25 fps 那批片子量的。gea-shapovalov 的源片 59.94 fps，按 4990
    估出来 147 MiB、实际 **168.4 MiB**——低估 14%。贴着 95 MiB 的片子会被估成
    「进仓库」，然后在 `git push` 那一刻才被服务端拒（100 MiB 硬上限），
    五分钟白跑（run 30725160625）。

    所以这个常量只许按实测往上调。这条拦的不是手滑，是下一次有人为了让某条
    片子「看起来能进仓库」把它调回去。
    """
    reel = _reel()
    assert reel.MEASURED_REEL_KBPS >= 5698, (
        f"MEASURED_REEL_KBPS={reel.MEASURED_REEL_KBPS}，低于实测最高的 "
        "5698 kb/s（gea-shapovalov：168.4 MiB / 247.9s，源片 59.94 fps）")

    # 加餐：每条已发成片的实测码率都不许超过这个常量
    checked = 0
    for rj_path in sorted(Path("output").glob("*/reel/*/render.json")):
        data = json.loads(rj_path.read_text("utf-8"))
        size, secs = data.get("video_bytes"), data.get("film_seconds")
        if not size or not secs:
            continue
        checked += 1
        kbps = size * 8 / secs / 1000
        assert kbps <= reel.MEASURED_REEL_KBPS, (
            f"{rj_path.parent.name} 实测 {kbps:.0f} kb/s，比常量还高——"
            "常量要取实测最高的那一条，见它上面那段注释")
    if checked:
        print(f"[加餐] 拿 {checked} 条成片的实测码率对过")


def test_真字段表要盖住每条spec里出现过的字段():
    """`_REAL_FIELDS` 不许靠人记着维护。

    它是「拿掉下划线正好是个真字段」那道闸的主语。少一个名字，那道闸对这个
    字段就是哑的——而**一个会过期的名单和一条常年红的检查是同一个毛病**。
    所以判据从 `specs/reels/*.json` 里实际出现过的字段自动推：新写一个字段
    就必须同时挂进这张表。
    """
    reel = _reel()
    seen: dict[str, set[str]] = {"spec": set(), "cover": set(), "segment": set()}
    for spec in _reel_specs().values():
        seen["spec"] |= set(spec)
        seen["cover"] |= set(spec.get("cover") or {})
        for seg in spec.get("segments") or []:
            seen["segment"] |= set(seg)
    for level, names in seen.items():
        real = {n for n in names if not n.startswith("_")}
        missing = sorted(real - set(reel._REAL_FIELDS[level]))
        assert not missing, (
            f"`_REAL_FIELDS[{level!r}]` 少了 {missing}——这几个字段写成 "
            f"`_xxx` 时不会被拦住，会静静地不生效")
        assert real, f"{level} 一个字段都没扫到，判据失效了"


def test_整改期顶栏要有复盘契约且比分不许漂移():
    """顶栏继续保留，但不能让它把纯比分流水账包装成复盘。"""
    import pytest  # noqa: PLC0415

    reel = _reel()
    spec = _reel_specs()["eala-parks"]
    reel._validate_editorial_contract(spec, required=True)
    assert spec["editorial"]["human_context"]["facts"]
    assert spec["editorial"]["human_context"]["sources"]
    # ⚠️ line1 只是原样读出真实 spec 再传一遍，这条测试真正要护的是
    # line2 的机械一致性（下面 bad_score 那段）——line1 的具体文字不是它的
    # 判据，那是 `test_同一届赛事顶栏的中文名要统一` 的地盘。写死这个字符串
    # 曾经在赛事名统一那次改动时把这条测试带崩，改成从 spec 自己读。
    assert reel._topbar_lines(spec) == (
        spec["topbar"]["line1"], "伊埃拉 6-1 4-6 6-2 帕克斯")

    bad_score = json.loads(json.dumps(spec))
    bad_score["topbar"]["line2"] = "帕克斯 6-1 4-6 6-2 伊埃拉"
    with pytest.raises(reel.ReelError, match="line2"):
        reel._topbar_lines(bad_score)

    missing_contract = json.loads(json.dumps(spec))
    del missing_contract["editorial"]
    with pytest.raises(reel.ReelError, match="editorial"):
        reel._validate_editorial_contract(missing_contract, required=True)

    missing_context = json.loads(json.dumps(spec))
    del missing_context["editorial"]["human_context"]
    with pytest.raises(reel.ReelError, match="human_context"):
        reel._validate_editorial_contract(missing_context, required=True)


def test_顶栏版式用两种字体且只覆盖比赛区(tmp_path):
    reel = _reel()
    ass = reel.write_topbar_ass(
        ("WTA 1000 加拿大站 第二轮", "伊埃拉 6-1 4-6 6-2 帕克斯"),
        1.2, 51.2, tmp_path / "topbar.ass")
    text = ass.read_text(encoding="utf-8")
    assert "Style: HEAD,得意黑,54" in text
    assert "Style: BODY,Noto Sans CJK SC,38" in text
    assert "Dialogue: 0,0:00:01.20,0:00:51.20,HEAD" in text
    assert "Dialogue: 0,0:00:01.20,0:00:51.20,BODY" in text

    graph = reel.topbar_filtergraph(1.2, 50.0, ass, tmp_path / "subtitles.ass")
    assert "trim=start=0:end=1.200" in graph
    assert "trim=start=1.200:end=51.200" in graph
    assert "trim=start=51.200" in graph
    assert "[cover][match_canvas][outro]concat=n=3" in graph


def test_下划线开头的字段名等于没写(tmp_path):
    """`_push` 这种键**整整对了一个月**，因为退路刚好给出了对的答案。

    `push_meta` 读的是 `push`，而 spec 里写的是 `_push`——`_` 开头一律当注解，
    读都不读。没有 `summary` 时标题退回「对阵 + 比分」，而那一句正是
    `cover.versus.names` + `cover.result` 拼出来的，看起来完全正常。是换成
    单人封面、退路一空，标题当场变成 `8.2 赛场之上 | ` 才把它抖出来。

    ⚠️ 判据要窄：`_inset` 在 `hewitt-washington` 第 3 段是**真的注解**（就贴在
    真的 `inset` 旁边，写的是为什么压左上角）。所以只认**值是个对象**的那种。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()

    def spec_with(**extra):
        return {"cover": {}, "segments": [{"start": 0, "end": 1}],
                "source_url": "u", **extra}

    with pytest.raises(reel.ReelError, match="`_push`"):
        reel._reject_underscored_fields(spec_with(_push={"summary": "x"}))
    with pytest.raises(reel.ReelError, match="`_versus`"):
        reel._reject_underscored_fields(
            spec_with(cover={"_versus": {"names": ["a", "b"]}}))
    with pytest.raises(reel.ReelError, match="`_inset`"):
        reel._reject_underscored_fields(
            {"cover": {}, "source_url": "u",
             "segments": [{"start": 0, "end": 1, "_inset": {"image": "x"}}]})

    # 反过来：这三种都是仓库里真实存在的注解写法，一个都不许被判红
    reel._reject_underscored_fields(spec_with(_source="这条源片是官方集锦"))
    reel._reject_underscored_fields(spec_with(_push_why="为什么这么写标题"))
    reel._reject_underscored_fields(
        {"cover": {}, "source_url": "u",
         "segments": [{"start": 0, "end": 1, "inset": {"image": "x"},
                       "_inset": "为什么把角标压在左上角"}]})

    # **而且这道闸真的接在 `load_spec` 上。** 上面那些只证明函数会抛错；
    # 反向验证时把 `load_spec` 里那一句调用整个拆掉，六条测试**全绿**——
    # 又一次「写了不等于跑过」。所以这里真走一遍读 spec 的那条路。
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(
        {"cover": {}, "segments": [{"start": 0, "end": 1}], "source_url": "u",
         "_push": {"summary": "x"}}, ensure_ascii=False), "utf-8")
    with pytest.raises(reel.ReelError, match="`_push`"):
        reel.load_spec(path)

    # 而且每条已有的 spec 现在都得过——三条踩了这个坑的已经改掉了
    for slug, spec in _reel_specs().items():
        try:
            reel._reject_underscored_fields(spec)
        except reel.ReelError as exc:  # pragma: no cover - 出错时要说是哪条
            raise AssertionError(f"{slug}: {exc}") from None


def test_疑似切点要趁源片还在的时候量出来():
    """0.35 那个门槛认不出「同一场地、同一机位」的换镜头。

    gea-shapovalov 那次很直白：474.5 秒他还穿着白 polo 在场上，476.5 秒已经
    换上蓝外套在捧杯——**中间必然有一刀**，而 `scene_cuts` 只报了 473.07 和
    482.67。挑段的时候只能靠人在缩略图墙上看出来。

    所以另出一份低门槛的候选写进 `probe.json`。三件事都要钉：

    1. **门槛真的更低**，否则它和 `scene_cuts` 是同一份。
    2. **不并进 `scene_cuts`**——那是判据（存量 spec 的 `crosses_cut` 照着它
       挂账），这是线索。混在一起等于把一批想清楚的声明变成噪音。
    3. **趁源片还在的时候量**。源片渲完就删（清理那一步），事后想查得自己
       再下一份几百 MB——`find_point_ends.py` 就是这么零调用方了一个月的。
    """
    reel = _reel()
    assert reel.LOOSE_CUT_THRESHOLD < reel.CUT_THRESHOLD

    src = inspect.getsource(reel.main)
    probe = src[src.index('if args.mode == "probe"'):src.index("spec = load_spec")]
    assert "scene_cuts_loose" in probe, "probe.json 里没有这一份"
    assert "LOOSE_CUT_THRESHOLD" in probe, (
        "疑似切点没有在 probe 里量——源片渲完就删，事后再下一份就是几百 MB")
    assert "abs(t - c)" in probe, (
        "疑似切点没有把已经在 `scene_cuts` 里的那些排掉，两份会重复")

    # 判据那一份只认 `scene_cuts`，线索不许漏进去
    straddle = inspect.getsource(reel.segments_straddling_cuts)
    assert "scene_cuts_loose" not in straddle, (
        "跨切点那道判据读到了疑似切点——线索当判据用，会把一批合法的段判红")


def _with_legacy_soft_cover(slug: str, spec: dict) -> dict:
    """存量封面的豁免表在**工具里**（`build_match_reel.LEGACY_SOFT_COVERS`），
    不在这儿——`--dry-run` 也要能跑存量。这里只留一个占位函数保持调用点不变。"""
    return spec


#: 用 Tennis TV 源片、而且发在「片尾和台标要剪掉」这条规矩（账号所有者 2026-08-16）
#: 之前的片子。已发的不重渲——**只许减不许加**，自检在下面那条测试里。
_LEGACY_TENNISTV = {
    "baez-dimitrov", "djokovic-tirante", "eala-svitolina", "fonseca-ruud",
    "fritz-jodar-final", "gea-shapovalov", "hewitt-washington",
    "hijikata-monfils", "kovacevic-khachanov",
    "landaluce-draper", "medvedev-zandschulp", "nakashima-jodar-montreal-sf",
    "shang-darderi-montreal-2026", "shang-vallejo", "shelton-fonseca",
    "shelton-nakashima-montreal-final", "shelton-tien-montreal-sf",
    "tirante-fritz", "tsitsipas-royer", "wang-samsonova", "wong-brooksby",
    "wong-gea", "wong-lehecka", "zverev-griekspoor",
}


def _uses_tennistv(spec: dict) -> bool:
    """这条 spec 的源片是不是 Tennis TV 的。

    ⚠️ **只看 `_source` 和 `_editing_why` 这两栏**（我们自己写的来路交代），
    不扫整份 spec——`_no_repeat` 里会点名别的片子，那些片子的名字里带 Tennis TV
    就会把这一条误判成「也用了 Tennis TV」。判据宁可窄，不可宽。
    """
    blob = " ".join(str(spec.get(k) or "") for k in ("_source", "_editing_why"))
    return "Tennis TV" in blob or "TennisTV" in blob


def test_用TennisTV的源片要说清片尾和台标怎么剪掉():
    """账号所有者 2026-08-16：「**如果用 Tennis TV 的视频的话，需要把它的片尾和它的
    logo 剪掉。**」

    两样东西，两个位置：

    - **片尾**是那张订阅／品牌卡，挂在源片末尾。它一旦落进任何一段窗口，成片里就会
      出现别人的品牌页——而 ffmpeg 不会报错，只有打开成片才看得见。
    - **台标**是烧在画面角上的水印。3:4 的取景窗只取 1920 里的 810px，居中时右上角
      那块本来就在窗外；可 `cx` 一往那边挪就会把它框进来。

    所以用 Tennis TV 源片的 spec 必须写一句 `_tennistv_trim`，说清这两样各自怎么
    处理的（末段收在第几秒、离片尾多远；取景窗有没有把角上那块框进来）。
    **和 `mixed_fps` / `silent_source` / `_frame_why` 一个形状：认领这一步把
    「想清楚了」和「凑合一下」分开。**

    ⚠️ 已发的挂在 `_LEGACY_TENNISTV` 里，只许减不许加，表自带自检。
    """
    specs = _reel_specs()
    for slug in sorted(_LEGACY_TENNISTV):
        assert slug in specs, (
            f"`_LEGACY_TENNISTV` 里的 {slug!r} 找不到对应的 spec"
            "——写错一个名字，豁免就成了一盏恒真的绿灯")
        assert _uses_tennistv(specs[slug]), (
            f"{slug} 已经不是 Tennis TV 的源片了，从 `_LEGACY_TENNISTV` 里删掉")

    fresh = sorted(
        slug for slug, spec in specs.items()
        if _uses_tennistv(spec) and slug not in _LEGACY_TENNISTV
        and not str(spec.get("_tennistv_trim") or "").strip())
    assert not fresh, (
        f"这几条用了 Tennis TV 的源片，却没写 `_tennistv_trim`：{fresh}。\n"
        "账号所有者 2026-08-16 定的：**片尾和台标都要剪掉**。写一句说清"
        "末段离片尾多远、取景窗有没有把角上那块台标框进来——"
        "「忘了看」和「看过了没问题」在成片上分不出来。")


def test_封面大图一律用官方高清图不许抽帧():
    """账号所有者 2026-08-16，一条消息里说了三遍：「封面一定要选高清大图，不然
    没人愿意点进去看」「抽帧的图都不太清晰啊」「**都说了**不要用截图抽帧的这种
    方式去做封面大图，非常的不清晰啊！去找官方的」。

    ⚠️ 「都说了」是给我的——CLAUDE.md 里「封面用真实照片，不要从视频里抽帧」
    一直写着，连账都算过（1080p 抽帧铺 3:4 要放大 1.33~1.78 倍，而源片是压缩
    转播流，换帧、锐化都救不回来）。**规矩没变，是实现漂了**：solo 版式给了
    `frame_at` 这条近路，于是六十条片子全走了它。所以这次要落成闸。

    ⚠️⚠️ **2026-08-17 这条的第 ① 头翻了面。** 账号所有者：「还是要**找到对应
    比赛的高清大图**是最重要的**前置条件**，不然封面不清晰没有吸引力」——
    抽帧**认领了也不再放行**。翻面的来路和数据（100 条 solo 里 74 条走了抽帧）
    在 `test_抽帧当封面不许再靠一句话放行` 的 docstring 里，这儿不抄第二遍。

    钉四头：

    ① **行为**：抽帧一律红——**写不写 `_frame_why` 都拦**
    ② **行为**：照片撑不满卡片 → 红（换个来源不算过关）；够大 → 过
    ③ **位置**：`validate_spec` 真的调了它——只测行为的话，闸排在下载后面
       照样全绿，而真实代价是每次都要先等几百 MB 下完（本仓库栽过两次）
    ④ **范围**：只管 `cover.portrait`（封面大图），不管 `versus.top/bottom`
       那两格抠图——那儿的账是反的（本场抽帧 0.61× 缩小，官方棚拍图 1.55×
       放大），判据宁可窄，不可宽
    """
    reel = _reel()

    def solo(portrait: dict) -> dict:
        return {"cover": {"layout": "solo", "portrait": portrait}}

    # ① 抽帧要认领
    assert reel.cover_photo_problem(solo({"frame_at": 152.5})), \
        "抽帧没认领也放行了——这道闸等于没装"
    assert "去找官方的" in reel.cover_photo_problem(solo({"frame_at": 152.5})), \
        "报错没说出路：四类源怎么翻、WTA 那条路怎么走"
    # ⚠️ 这两条 2026-08-17 翻了面：`_frame_why` 不再放行（前置条件，不是事后声明）
    assert reel.cover_photo_problem(
        solo({"frame_at": 152.5, "_frame_why": "四类源都翻过，见 _source"})), \
        "写了 `_frame_why` 又把抽帧放行了——前置条件被写回成了事后声明"
    assert reel.cover_photo_problem(
        solo({"frame_at": 152.5, "_frame_why": "   "})) is not None, \
        "空白的 `_frame_why` 当然也要拦"

    # ② 照片不许放大（拿真图量，别手搓）
    from PIL import Image  # noqa: PLC0415

    big = Path("assets/players/aryna-sabalenka.jpg")
    with Image.open(big) as raw:
        assert min(raw.size[0] / reel.COVER_FILL_W,
                   raw.size[1] / reel.COVER_FILL_H) < 1.0, (
            f"{big.name} 现在够大了，这条断言要换一张更小的图当样本")
    assert reel.cover_photo_problem(solo({"image": str(big)})), \
        "撑不满卡片的照片也放行了——那正是「非常的不清晰」那一类"
    assert reel.cover_photo_problem(
        solo({"image": str(big), "_low_res_why": "只有这一张"})) is None, \
        "认领过的取舍还拦"

    # ③ 位置：dry-run 那条路真的走得到
    assert "cover_photo_problem(" in inspect.getsource(reel.validate_spec), \
        "validate_spec 没调这道闸——那 dry-run 就还是拦不住，要等下载完才报"

    # ④ 范围：抠图那两格不归它管
    assert reel.cover_photo_problem(
        {"cover": {"versus": {"top": {"frame_at": 12.0},
                              "bottom": {"frame_at": 34.0}}}}) is None, \
        "把 VS 版式的抠图也拦了——那两格本来就该用本场抽帧（0.61× 缩小更锐）"

    # ⑤ 豁免表自检：每个 slug 必须真的存在，而且真的还过不了这道闸
    specs = _reel_specs()
    for slug in sorted(reel.LEGACY_SOFT_COVERS):
        assert slug in specs, (
            f"`LEGACY_SOFT_COVERS` 里的 {slug!r} 找不到对应的 spec"
            "——写错一个名字，豁免就成了一盏恒真的绿灯")
        naked = json.loads(json.dumps(specs[slug]))
        naked.pop("slug", None)          # 绕开豁免，看它本身过不过得了
        assert reel.cover_photo_problem(naked) is not None, (
            f"{slug} 的封面已经过得了这道闸了，从 `LEGACY_SOFT_COVERS` 里删掉"
            "——这张表只许减不许加")

    # ⑥ 而**没进表的 spec 一律要过**：立规矩的那天顺手扫一遍存量，
    #   不留给下一个人去撞（CLAUDE.md「立一条新的形状规矩时，顺手拿它扫一遍 specs/」）
    left = sorted(s for s, sp in specs.items()
                  if s not in reel.LEGACY_SOFT_COVERS
                  and reel.cover_photo_problem(sp) is not None)
    assert not left, f"这几条既不在豁免表里、封面又过不了闸：{left}"

    # ⑦ **认领了抽帧的，必须说清四类源各自查了什么**——一句「找不到」不算认领
    for slug, sp in specs.items():
        why = str((((sp.get("cover") or {}).get("portrait") or {})
                   .get("_frame_why")) or "")
        if not why:
            continue
        assert len(why) >= 60, (
            f"{slug} 的 `_frame_why` 太短（{len(why)} 字）——"
            "这一栏要写清楚四类源各自查了什么、结果如何，不是写一句「没找到」")


def test_spec引的图不许放在output里CI上看不见():
    """⚠️ **`ci.yml` 的稀疏检出不含 `output/`**，所以一条指到那儿的图片路径
    **在本地存在、在 CI 上不存在**——而上面那道 `cover_photo_problem` 是真去
    `Path(...).exists()` 的，于是它在 CI 上报「封面大图找不到」。

    `swiatek-sakkari` 就是这么红的：官方实拍图我顺手落在了 probe 产物那一格
    （`output/<date>/reel/<slug>/cover_src/portrait.jpg`），而**另外 26 条 spec
    全放在 `assets/`**。本地全量 2146 绿、CI 两条红，两条同一个根因。

    ⚠️ **这条是「测试不许拿 `output/` 当判据的主语」的镜像**：那条说的是判据
    自己的主语在 CI 上不在（表现是**假绿**，`glob` 恒空）；这条是**被判据检查的
    那个东西**在 CI 上不在（表现是**红**）。两种都只在 CI 上现形，而这一种更
    值得装闸——它拦得住的是「本地过了、远端才红」这一整趟往返。

    ⚠️ 判据只认**图片后缀**（渲染真要读的那种），不认 `probe.json` /
    `captions.txt` 这类文本引用——`_editing_why` / `_source` 里提到产物路径是常事。

    ⚠️ 跳过 `_` 开头的键是**预防，不是实测**：量过一遍，现在 114 条 spec 里
    它一条都没排除掉（注解里的路径嵌在句子中间，`startswith("output/")` 本来
    就够不着）。写在这儿是因为哪天有人写 `"_alt": "output/….jpg"`，那是注解
    不是素材——别让下一个人以为这一行已经拦下过什么。
    """
    import re as _re  # noqa: PLC0415

    IMG = _re.compile(r"\.(jpg|jpeg|png|webp)$", _re.I)
    offenders: list[str] = []

    def walk(node, slug: str, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                # `_` 开头的是写给下一个人看的注解，不是素材路径
                if not str(k).startswith("_"):
                    walk(v, slug, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, slug, f"{path}[{i}]")
        elif isinstance(node, str) and node.startswith("output/") and IMG.search(node):
            offenders.append(f"{slug}{path} = {node}")

    specs = _reel_specs()
    for slug, spec in specs.items():
        walk(spec, slug, "")
    assert not offenders, (
        "这些图片路径指到 output/ 里，而 CI 的稀疏检出看不见它 —— 渲染那一刻会报"
        "「找不到」，可本地一切正常：\n  " + "\n  ".join(offenders)
        + "\n把图挪进 assets/（另外那些 spec 都是这么放的），别留在产物目录里")

    # 判据自己的判据：主语真的在。specs 读不到的话上面那句恒真，
    # 而「一条恒真的绿灯」和「真的没问题」长得一模一样。
    assert len(specs) >= 100, f"只扫到 {len(specs)} 条 spec，判据的主语没了"


#: 「赛场之上 solo 封面必须有 `cover.scoreboard`」这条规矩（#368）立起来**之前**
#: 发出去的十九条。已发的片子不为版式重渲——微信那条消息发出去收不回来，所以它们
#: 就停在这个样子；**只许减不许加**，表自己带自检（见 `_with_legacy_scoreboard`）。
#:
#: ⚠️ 这张表**只放过封面那道形状闸**，别的一律照旧。它存在的理由是：这条规矩是
#: 在渲染路径上立的，而那条路排在下载源片之后，所以立的时候没人发现存量过不了。
#: 2026-08-15 把同一份判据搬进 `validate_spec`（好让 dry-run 秒级就报）时才现形。
_LEGACY_NO_SCOREBOARD = {
    "chwalinska-gibson", "eala-fernandez", "eala-osaka", "eala-svitolina",
    "medvedev-zandschulp", "noskova-mcnally", "potapova-venus",
    "rybakina-kasatkina", "shang-rublev", "tirante-fritz", "wang-kasatkina",
    "wang-pareja", "wang-samsonova", "wong-brooksby", "wong-gea",
    "wong-lehecka", "zhang-ostapenko", "zhang-putintseva", "zverev-griekspoor",
}


def _with_legacy_scoreboard(slug: str, spec: dict) -> dict:
    """存量里没有 `cover.scoreboard` 的那十九条，补一个占位块再往下走。

    ⚠️ **占位块只为让 `validate_spec` 能走到旁白那一问**，一个像素都不会渲出来；
    补的是形状不是内容。不在表里的 spec 一个字都不动。

    ⚠️ **表自带自检**：名字写错、或者哪条后来补上了真的 scoreboard，都会当场红。
    一个写错的名字就是一盏永远亮着的绿灯——这个仓库为它栽过。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    stale = slug in _LEGACY_NO_SCOREBOARD and \
        vp.solo_scoreboard_shape_error(spec.get("cover") or {}) is None
    assert not stale, (
        f"{slug} 已经有合格的 `cover.scoreboard` 了（或者名字写错了），"
        "从 `_LEGACY_NO_SCOREBOARD` 里删掉——这张表只许减不许加")
    if slug not in _LEGACY_NO_SCOREBOARD:
        return spec
    patched = json.loads(json.dumps(spec))
    patched["cover"]["scoreboard"] = {
        "court": "（占位：这条 spec 发在 #368 之前，不会重渲）",
        "duration_source": {"url": "https://example.invalid/legacy"},
    }
    return patched


def test_每条spec的旁白都还估得下():
    """**每条 spec 都要现在还渲得出来**，不只是发的那天渲得出来。

    `wong-lehecka` 第 10 段就是这么坏掉的：成片 7.30 发出去，之后为了「收尾要
    落在一问上」把那一问补进旁白，字数从 22 涨到 48，**没有再渲过**。于是这条
    spec 从那天起就渲不出来了——真闸（TTS）要跑一趟 render 才出声，而没人再渲
    它，所以它一直躺在仓库里假装是好的。

    改 spec 不重渲是常事（措辞、注解、规矩追认），所以这条要**每次 CI 都跑**。
    它只吃 `specs/` 和 `tools/`，不联网、不碰产物。

    ⚠️ **被源禁令拦下的 spec 不参与这一问**，因为它按设计就渲不出来了
    （2026-08-14 起，换取签名令牌拉受控流那条路禁掉，见
    `_reject_signed_source_urls`）。**但不许静静跳过**：这里把它们收成一张
    表并断言它**恰好**是已知那一份——多出一条就是有人又写了一个换签名 URL 的
    源，当场红。豁免表带自检，只许减不许加，和这个仓库其余几张一个形状。
    """
    reel = _reel()
    # 只有这一条：`_source` 自己写着「通过 Sky 页面公开 API 换取短时签名 HLS」，
    # 它是**反面先例**（spec 里的 `_source_denied` 记着全部来路），片子不删、
    # 但也不该再渲一次。
    known_denied = {"shang-darderi-montreal-2026"}
    broken: list[str] = []
    denied: set[str] = set()
    checked = 0
    for slug, spec in _reel_specs().items():
        try:
            reel.spec_sources(spec)
        except reel.ReelError as exc:
            # ⚠️ 只放过**源禁令**这一种，别把 ReelError 整类都吞掉——
            # 那会把「这条 spec 真的坏了」也一起变成绿灯。
            if "换取签名令牌" not in str(exc):
                raise
            denied.add(slug)
            continue
        spec = _with_legacy_soft_cover(slug, _with_legacy_scoreboard(slug, spec))
        for index, secs, room in reel.narration_estimates(reel.validate_spec(
                spec, allow_published_legacy=True)):
            checked += 1
            if room < -reel.SPEECH_EST_ERR:
                broken.append(f"{slug} 第 {index + 1} 段：画面 "
                              f"{spec['segments'][index]['end'] - spec['segments'][index]['start']:.1f}s"
                              f"，估旁白 {secs:.2f}s")
    assert denied == known_denied, (
        f"被源禁令拦下的 spec 变了：现在是 {sorted(denied)}，"
        f"名单里写的是 {sorted(known_denied)}。\n"
        "多出来的那条多半是又写了一个换签名令牌拿到的源——那条路是禁的，"
        "换未签名的公开地址或换源；少掉的那条修好了就把它从名单里划掉。")
    assert checked >= 100, f"只估到 {checked} 段，判据失效了"
    assert not broken, (
        "这几段的旁白比自己那段画面长（离线估，已经扣掉 "
        f"±{reel.SPEECH_EST_ERR}s 的误差）：\n  " + "\n  ".join(broken))


def test_dry_run要把装不下的旁白当场报出来(tmp_path):
    """**旁白写长了不该等六分钟的 render，也不该等 TTS。**

    `--check-narration` 要合语音（联网、一分半），`render` 更是八到十一分钟。
    而「这段话装不装得下」离线就能估个八九不离十——误差 ±1.5s，够回答
    「估得再乐观也装不下」这一种问题。

    两个方向都验：真 spec 要过，把一段旁白撑长要当场报错并 `exit 1`。
    """
    reel_path = Path("tools/build_match_reel.py")
    spec_path = Path("specs/reels/gea-shapovalov.json")
    spec = json.loads(spec_path.read_text("utf-8"))

    def dry_run(data) -> subprocess.CompletedProcess:
        # 底稿 slug 命名：措辞豁免按 slug 查，换名克隆会红在措辞不红在旁白
        path = tmp_path / "gea-shapovalov.json"
        path.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        return subprocess.run(
            [sys.executable, str(reel_path), "render", "--spec", str(path),
             "--outdir", str(tmp_path / "out"), "--dry-run"],
            capture_output=True, text=True, check=False)

    ok = dry_run(spec)
    assert ok.returncode == 0, f"真 spec 没过 dry-run：\n{ok.stdout}\n{ok.stderr}"
    assert "[估旁白]" in ok.stdout, "dry-run 没有报旁白余量"

    # 反过来：把最短的那一段撑长，必须当场红
    blown = json.loads(json.dumps(spec))
    index = min((i for i, s in enumerate(blown["segments"])
                 if str(s.get("narration", "")).strip()),
                key=lambda i: float(blown["segments"][i]["end"])
                - float(blown["segments"][i]["start"]))
    blown["segments"][index]["narration"] = "这句话写得很长，" * 12
    bad = dry_run(blown)
    assert bad.returncode == 1, f"撑长了还是绿的：\n{bad.stdout}"
    assert "装不下" in bad.stdout, bad.stdout


def test_封面正中不许压暗但文字那两条边要留(tmp_path):
    """账号所有者 2026-08-17：「以后**所有封面都不要用遮罩效果**」。

    ## 这条判据自己被数据翻过一次，翻的过程比结论值钱

    我先按字面把整层拆了（`_scrim_css` 直接回一条没有 `background` 的规则），
    还写了一条测试钉住它。**依据是一张照片**：`svitolina-valentova` 渲出来量
    三条带子（台头 50~69、钩子 84~100、比分板 108），于是写下「照片本身就够暗」。

    把 **31 张已发封面的原图**按同一套裁法量一遍，结论反过来：

        比分板那一带   中位 132，**最亮 219**（arango-venus）、214（djokovic-tirante）
        台头那一带     中位  72，最亮 147（boisson-krueger）
        任一带 > 150   **8 张 / 31 张 ＝ 26%**

    再拿一张**纯白照片**渲到底：比分板整块几乎消失——中文名、英文名、场地名、
    盘分数字全是浅色压浅色，只剩描边的光晕。**每四张封面就有一张的赛果读不出来，
    而它一个字都不报。**

    ⚠️ 这是本仓库那条「查了一场就写成了一类」的又一次，**而且是同一天里第三次**
    （前两次已经写进 CLAUDE.md：flashscore 的统计项、赛事图库的文件名）。
    一张照片量出来的结论，不配当一类照片的判据。

    ## 所以钉的是「正中不压、两头要留」，不是「一层都不许有」

    1. **正中那道 radial 永远不画**——它才是账号所有者说的那层，压在照片主体上，
       把实拍洗成背景板（`dim_centre` 两个取值都不许把它带回来）
    2. **中段要接近透明**：32%~66% 恒定 `.08`
    3. **上下两条必须还在**——这一头就是上面那 8 张封面的判据；
       只钉第 1 条的话，把整层删光照样绿（我上一版正是这么绿的）
    4. **文字自己的描边不许跟着削**：它和这两条边一起托住可读性
    5. **解说片那半边是另一份 `.scrim`**，同一天 #423 修的是同一个形状——
       两条线各有一份，修一条不等于修完了；那边的判据是
       `test_封面不许再压一层居中的阴影`，这里只钉「它没被整层删掉」
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    for flag in (False, True):
        css = vp._scrim_css(flag)
        assert "radial-gradient" not in css, (
            f"`_scrim_css({flag})` 又把正中那道椭圆带回来了：{css}")
        assert "linear-gradient" in css, (
            f"`_scrim_css({flag})` 把上下两条也删了——比分板那一带中位 132、"
            f"最亮 219，删掉之后每四张封面有一张读不出赛果：{css}")

    stops = dict((int(h), int(a)) for a, h in
                 re.findall(r"rgba\(6,28,20,\.(\d+)\) (\d+)%", vp._scrim_css(False)))
    assert stops.get(32, 99) <= 10 and stops.get(66, 99) <= 10, (
        f"中段不许压暗（照片主体就在这儿）：{stops}")
    assert stops.get(0, 0) >= 40, f"台头那一条太浅，压不住 147 那种亮顶：{stops}"
    assert stops.get(100, 0) >= 40, f"比分板那一条太浅，压不住 219 那种亮底：{stops}"

    from PIL import Image  # noqa: PLC0415

    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1920, 1080), (90, 120, 90)).save(photo)
    base = {"eyebrow": "赛场之上", "subject": "某人", "hook": "一行钩子",
            "portrait": {"image": str(photo)}}
    for extra in ({}, {"scrim": "dim"}, {"scrim": "clear"}):
        _, css = vp._solo_body({**base, **extra})
        block = css.split(".scrim{")[1].split("}")[0]
        assert "radial-gradient" not in block, (
            f"`{extra}` 这条路上正中那道椭圆还在：{block}")

    # ④ 文字的描边不许跟着一起削——它和那两条边一起托住可读性
    src = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    story = src.split(".storytitle{")[1].split("}")[0]
    assert story.count("rgba(0,0,0") >= 2, (
        f"钩子的 text-shadow 被削了：{story}——中段基本不压暗，全靠它")
    head = src.split(".head{")[1].split("}")[0]
    assert "text-shadow" in head, "台头的 text-shadow 没了，浅色画面上会读不出"

    # ⑤ 解说片那半边是另一份 scrim，不许被整层删掉（那边的曲线归它自己的判据）
    from tennislive.render.tournament_story import find_story_by_slug  # noqa: PLC0415
    from tennislive.video.explainer import (  # noqa: PLC0415
        _slide_html, explainer_script,
    )

    segs = explainer_script(find_story_by_slug("hawkeye"))
    cover_doc = _slide_html(0, segs[0])
    cover_rule = cover_doc.split(".cover .scrim{")[1].split("}")[0]
    assert "radial-gradient" not in cover_rule and "gradient" in cover_rule, (
        f"解说片封面那道 scrim 形状不对（正中不许压、两头要留）：{cover_rule}")

def test_信箱式垫层不许再压暗而且两处是同一个出处(tmp_path):
    """账号所有者 2026-08-17：「**背景图不要再加前面阴影，导致背景图看着模糊啊**」。

    ⚠️ **这和上一条（`.scrim` 的中心暗角）不是同一层。** 他说的是
    `fit: "width"` 那几张的**垫底层**：照片按宽度铺时上下会空出来，底下垫同一张
    照片的放大版——原来带着 `brightness(.42)`，于是上下两条变成又黑又糊的带子，
    读起来像渲坏了，而不像照片的延续。`wangxiyu-fernandez` 那张就是。

    四版渲出来摆一起比过（本地 7 秒一版）：`blur44+暗.42`（改前，上下近黑）／
    `blur44+不压暗`（亮回来但仍糊成一片）／**`blur16+不压暗`**（现在这档，
    底色和照片连成一片）／`不糊不压暗`（**裁判的头在顶上重复了一次**，
    一眼看出是两张图）。

    ## 判据三头

    1. **不许再有 `brightness`**——这是他点名的那一样
    2. **blur 要在 (0, 16] 之间**：往 0 推不是「更清楚」，是那份复制品认得出来、
       和上层那张打架；往回推就又变成一条糊带子
    3. **两处必须共用同一个出处**（`PAD_FILTER`）——solo 一处、VS 分格一处，
       写两处必分叉，而分叉的样子是「有的封面上下发黑、有的不发黑」

    ⚠️ **`.bg` 那一层（VS 版式背后的球场）没动**：它不是垫层，是给棚拍抠图
    一个「这是一场球」的语境，`blur 12 / dim .72` 是当年渲了三档比出来的
    （源码注释里记着 `blur 22 + dim .5` 会糊到看不出是球场）。12 条用它的
    spec 全是 2026-08-14 及以前的，solo 早就是默认版式了。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    pad = vp.PAD_FILTER
    assert "brightness" not in pad, (
        f"垫层又压暗了：{pad!r}——账号所有者点名的就是这一样")
    m = re.search(r"blur\((\d+)px\)", pad)
    assert m, f"垫层的 blur 读不出来：{pad!r}"
    blur = int(m.group(1))
    assert 0 < blur <= 16, (
        f"垫层 blur={blur}px。往 0 推那份复制品会认得出来（裁判的头重复一次），"
        "往回推又变成一条糊带子——16 是比出来的那一档")

    src = Path("tools/versus_poster.py").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert body.count("PAD_FILTER") >= 3, (
        "垫层只剩一处调用了——solo 和 VS 分格两处都要用它")
    assert "blur(44px)" not in body, (
        "还有一处写着 blur(44px) 的字面量——两处必分叉，得走 PAD_FILTER")

    # 真走一遍 `_solo_body`：`fit: width` 那条路上不许再出现 brightness
    from PIL import Image  # noqa: PLC0415

    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1920, 1080), (60, 90, 140)).save(photo)
    base = {"eyebrow": "赛场之上", "subject": "某人", "hook": "一行钩子",
            "portrait": {"image": str(photo), "fit": "width"}}
    _, css = vp._solo_body(base)
    before = css.split(".hero::before{")[1].split("}")[0]
    assert "brightness" not in before, f"垫层那条规则还压着暗：{before}"
    assert pad.split(";")[0] in before, "垫层没走 PAD_FILTER——改了常量海报不跟着变"


def test_装yt_dlp一律要带default():
    """**`pip install yt-dlp` 少了 `[default]`，报出来是「这条片子没有格式」。**

    `[default]` 带的是 `yt-dlp-ejs`——解 YouTube 的 n challenge 要跑一段 JS。
    少了它 yt-dlp **不会说「装少了」**：格式表里只剩故事板，于是任何选择器
    （连 `worst`）都匹配不上，报的是 `Requested format is not available`。

    **它长得和「片源只有 DRM」一模一样，而我照着后者写下了结论。**
    frame-grab 头两趟（run 30791003879 / 30791363067）八个 client 全红，
    我据此在调研文档里写「卡在片源，不是卡在管线」——方向反了，是那条
    `pip install -q -e . yt-dlp` 漏了 `[default]`。而 match-reel.yml 里
    那句注释早就把这个坑写清楚了：**新工作流没继承旧工作流的前提**，
    又一次「加新能力就要同时改三处」。

    判据**自动推导，不维护白名单**（和「凡是 `git commit` 的工作流都要有
    体积闸」同一个形状）：凡是 `pip install` 里出现 yt-dlp 的，都要带
    `[default]`。就算某条线只取元数据，带上它也没有代价——而漏掉它的代价
    是一趟看起来完全合理的错误结论。
    """
    seen = 0
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        for line in _yaml_only(path.read_text(encoding="utf-8")).splitlines():
            if "pip install" not in line or "yt-dlp" not in line:
                continue
            seen += 1
            for token in re.findall(r'"?yt-dlp[^"\s]*"?', line):
                assert "[default]" in token, (
                    f"{path.name}：`{line.strip()}` 装的是裸的 yt-dlp。"
                    "少了 [default] 就没有 yt-dlp-ejs，n challenge 解不了，"
                    "格式表只剩故事板——报出来是「Requested format is not "
                    "available」，看着像片源的问题，其实是这一行的问题。")
    # 判据自己的判据：主语没了要出声，别变成一条恒真的绿灯
    assert seen >= 3, f"只扫到 {seen} 处 yt-dlp 安装——是不是路径写错了"


def test_提交产物的工作流一律用Claude的身份():
    """**GitHub 会把不是 `noreply@anthropic.com` 的提交标成 Unverified。**

    这些提交是工作流里的 bot 打的（成片、候选帧、采集数据），原来一律写着
    `github-actions[bot]`。改身份要改在**工作流里**，不能回头改历史——
    2026-08-03 那次 stop hook 让我 `--reset-author` 六个提交，其中五个是
    bot 的、一个是 GitHub 自己的 squash 提交，而且**十分钟前那条微信推送里
    的图片和成片链接是钉在 commit SHA 上的**（`TENNISLIVE_ASSET_REV`）：
    换 SHA 等于把一条已经发出去、收不回来的消息里每个链接变成死链。

    判据**自动推导，不维护白名单**：凡是 `git config user.email` 的工作流，
    邮箱都必须是 noreply@anthropic.com。
    """
    seen = 0
    for path in sorted(Path(".github/workflows").glob("*.yml")):
        for line in _yaml_only(path.read_text(encoding="utf-8")).splitlines():
            stripped = line.strip()
            if not stripped.startswith("git config user."):
                continue
            seen += 1
            if "user.email" in stripped:
                assert "noreply@anthropic.com" in stripped, (
                    f"{path.name}：`{stripped}` —— GitHub 会把它标成 Unverified。"
                    "改这里，别去改已经推上去的历史。")
            else:
                assert '"Claude"' in stripped, (
                    f"{path.name}：`{stripped}` 的提交者名字应该是 Claude")
    # 判据自己的判据：主语没了要出声
    assert seen >= 20, f"只扫到 {seen} 行 git config user.*——路径写错了吗"


def test_Azure那条路的词边界要和edge_tts同一个单位():
    """字幕整条线读的是 `{offset, duration, text}`，而 **edge-tts 给的是
    100 纳秒**为单位的整数。Azure SDK 的 `audio_offset` 同样是 100ns 的 tick，
    但 `duration` 在新版里是 `timedelta`、老版是毫秒整数——**不换算的话字幕
    会整体错位，而且不报错**。

    这条测试**真调一次换算函数**，不查源码文本：查源码只能防「有人把它删了」，
    防不住「它从来没工作过」（`_cut_person` 那次引了一个不存在的名字，
    `assert "def _cut_person(" in reel` 照样绿，功能整天是坏的）。
    """
    import datetime  # noqa: PLC0415

    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video import azure_tts  # noqa: PLC0415

    # timedelta（新版 SDK）：0.5 秒 = 5,000,000 个 100ns
    assert azure_tts._ticks(datetime.timedelta(seconds=0.5)) == 5_000_000
    # 毫秒整数（老版 SDK）：500 毫秒 = 同一个数
    assert azure_tts._ticks(500) == 5_000_000
    # 认不出来的记 0，不猜（字幕只用 offset 排序，duration 缺了不致命）
    assert azure_tts._ticks(None) == 0


def test_拼错的风格名要在写spec时就拦下来():
    """⚠️ **Azure 对拼错的 `style` 是静默忽略的**——合成照样成功、时长照样正常，
    只是没有情绪。而「拼错了」和「这个风格听起来本来就平」**在成片上一模一样**，
    等于又一个「兜底出事的时候不吭声」。

    所以判据装在**写 spec 的那一刻**（`_seg_voice`），不等到听成片。那十个
    名字是 2026-08-04 在 runner 上逐个问过的（run 30892017944，10/10 通过），
    不是从文档抄的——文档列的是**语音的能力表**，不是**定价层的权限表**。
    """
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video import azure_tts  # noqa: PLC0415

    assert azure_tts.check_styles(["sports-commentary-excited"]) == []
    assert azure_tts.check_styles(["sports_commentary_excited"]) == \
        ["sports_commentary_excited"], "下划线写法要被拦住"
    assert azure_tts.check_styles(["excited"]) == ["excited"]
    # 判据自己的判据：这张表不许空，否则它对任何名字都放行
    assert len(azure_tts.KNOWN_STYLES) == 10


def test_要了情绪风格却没配Azure必须报错不许悄悄退回():
    """**悄悄退回 edge-tts 等于发一条和 spec 说的不一样的片子，而且不吭声。**

    Edge 免费端点对 `mstts:express-as` 和 `<break/>` 一律拒绝（实测
    run 30884267406，四个风格全被拒）；Azure F0 十个全过（run 30892017944）。
    所以 spec 里写了 `style` / `lead_pause` 就是**明确要了 Azure 那条路**，
    这时候没有 key 只有两条出路：去掉这两个键，或者配好再渲。**不能是第三条**。

    ⚠️ 判据要**真跑一次 `tts_one`**（把 Azure 判成不可用），不是查源码里
    有没有那个 `raise`。
    """
    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    import build_match_reel as reel  # noqa: PLC0415
    from tennislive.video import azure_tts  # noqa: PLC0415

    real = azure_tts.available
    azure_tts.available = lambda: False
    try:
        with pytest.raises(reel.ReelError, match="只有 Azure"):
            reel.tts_one("一句话", Path("/tmp/never-written.mp3"),
                         "zh-CN-YunjianNeural", "+6%", "+0Hz",
                         style="sports-commentary-excited")
        with pytest.raises(reel.ReelError, match="只有 Azure"):
            reel.tts_one("一句话", Path("/tmp/never-written.mp3"),
                         "zh-CN-YunjianNeural", "+6%", "+0Hz", lead_pause=0.5)
    finally:
        azure_tts.available = real
    # 反面锚点：**只调语速音高的照旧走 edge-tts**，不许被这道闸误伤
    assert not Path("/tmp/never-written.mp3").exists(), \
        "报错之前不许已经写出音频"


def test_整段全单字要被报出来():
    """整段每个 token 都是一个字——切词器完全没拿到上下文，读音风险最高。

    2026-08-04 账号所有者问「切分词和短句，以及多音字等等，F0 能解决么？」。
    不能：F0 只量音高。切词的判据一直在手上（`words.json` 的 `text` 就是合成器
    自己报的切词），可**那道闸只保护人名**（出处是 spec 的 `cover.matchup`）。
    王欣瑜那条手工扫出 6 处切错的，**一个人名都没有**，闸一声没吭。

    ⚠️ **第一版还写了一条「同词两切」，拿存量验完撤掉了。** 那条判据是
    「这一段是一个词、那一段被切开，合成器自己的两次输出打架」——不用维护词表，
    看着很漂亮。实测 15 条片子：wong-gea 10 段报 7 处、zheng-lanlana 20 段报
    7 处，而**报出来的几乎全是读音没变的**（`六 ｜ 比 ｜ 三` 照样念 liù bǐ sān）。
    全套里真有歧义的只有 `二 ｜ 发`（fā / fà）一处。**一条天天误报的检查等于
    没有检查。**

    这条测试同时钉住那个撤除：判据里不许再出现跨段比对。
    """
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video import explainer  # noqa: PLC0415

    hit = explainer.all_single_char_segments(
        [(9, "抢七输掉了。", ["抢", "七", "输", "掉", "了"])])
    assert any("第 10 段" in s for s in hit), f"没认出全单字：{hit}"

    # ⚠️ 三条反面锚点，判据宁可窄不可宽：
    # ① 三个 token 以下不算——「六比一。」本来就没上下文可用
    assert not explainer.all_single_char_segments(
        [(0, "六比一。", ["六", "比", "一"])]), "三个字的短句不该报"
    # ② 有一个多字 token 就不算
    assert not explainer.all_single_char_segments(
        [(0, "盘点。二十九分钟。", ["盘点", "二十九", "分", "钟"])]), \
        "有多字 token 的不该报"
    # ③ **撤掉的那条不许自己回来**：跨段比对一出现，误报就跟着回来
    body = inspect.getsource(explainer.all_single_char_segments)
    assert "token_spans" not in body, \
        "又在跨段比对了——那条判据实测误报率过半，撤掉是量出来的决定"


def test_全单字那条判据在真产物上不误报():
    """判据要拿**真渲染器的输出**验，不能只喂手搓的 token 列表。

    上一条撤掉的「同词两切」就是这么倒的：单元测试里两段 fixture 一验就绿，
    拿存量 15 条片子一跑，误报占了一半以上的段。**加判据之前先拿存量验一遍。**

    ⚠️ **主语在 `output/` 里，而 CI 的稀疏检出不含它**——所以核心断言放在上面
    那条（只吃 `src/`），这条是**加餐**：产物在的时候（本地沙箱）多验一层，
    不在就跳过那一段。但**整条测试不许 skip**，一条常年跳过的检查和常年红是
    同一个毛病。
    """
    sys.path.insert(0, str(Path("src").resolve()))
    sys.path.insert(0, str(Path("tools").resolve()))
    from tennislive.video.explainer import all_single_char_segments  # noqa: PLC0415
    from build_match_reel import speakable  # noqa: PLC0415

    checked = noisy = 0
    for words in sorted(Path("output").glob("*/reel/*/voice_00.words.json")):
        outdir = words.parent
        spec = Path("specs/reels") / f"{outdir.name}.json"
        if not spec.is_file():
            continue
        data = json.loads(spec.read_text("utf-8"))
        segs = []
        for i, seg in enumerate(data.get("segments") or []):
            text = (seg.get("narration") or "").strip()
            path = outdir / f"voice_{i:02d}.words.json"
            if not text or not path.is_file():
                continue
            marks = json.loads(path.read_text("utf-8"))
            toks = [t for t in (str(m.get("text", "")).strip() for m in marks) if t]
            if toks:
                segs.append((i, speakable(text), toks))
        if len(segs) < 3:
            continue
        hits = all_single_char_segments(segs)
        # 判据不是「一条都不报」——真有问题就该报。拦的是**淹没式误报**：
        # 一条片子报出四分之一以上的段，人就不看它了。实测存量全部远低于这个数
        # （15 条片子里只有 1 条命中 1 段）。
        assert len(hits) <= max(1, len(segs) // 4), (
            f"{outdir.name}：{len(segs)} 段报了 {len(hits)} 处，太吵了\n{hits}")
        noisy += len(hits)
        checked += 1

    # 产物不在就只验上面那条；在的话至少要真校到一条，别变成恒真的绿灯
    if Path("output").is_dir() and list(Path("output").glob("*/reel/*")):
        assert checked >= 5, f"有成片目录却只校到 {checked} 条——主语找错了"


def test_成片要记下是哪条路配的音():
    """`tts_one` 是「Azure 可用就**整条片子**都走 Azure」。

    所以同一份 spec、同一个 `narration_voice`，配了 key 之前和之后合出来的
    **不是同一条音轨**——而那个字段两边一模一样，光看产物分不出来。解说片那条线
    早有 `tools/check_explainer_voice.py` 读产物里的 `narration.json`
    （CLAUDE.md：查产物，不查信号），这条线一直漏着。

    ⚠️ **`voiced_by` 第一版打印「[不合格]」却不计进末尾那个总数**，末行仍然说
    「共 0 项不合格」——正是这个脚本自己要拦的那种不一致。所以判据钉的是
    **返回值**，不是它印了什么。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_reel_landed as chk  # noqa: PLC0415

    import tempfile  # noqa: PLC0415
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        film = out / "x.mp4"                       # 不用真存在，只用它的 parent
        styled = {"segments": [{"voice": {"style": "sad", "_why": "崩"}}]}
        plain = {"segments": [{"voice": {"rate": "-3%", "_why": "慢一点"}}]}

        def meta(**kw):
            (out / "render.json").write_text(json.dumps(kw), encoding="utf-8")

        # ① spec 要了风格，成片却是 edge 配的 → **风格一个都没生效**，要计一项
        meta(narration_backend="edge-tts")
        assert chk.voiced_by(film, styled) == 1

        # ② 同一份 spec、Azure 配的 → 正常
        meta(narration_backend="azure")
        assert chk.voiced_by(film, styled) == 0

        # ③ 没要风格的走 edge-tts 是**正当的**（没配 key 就该退回），不许误伤
        meta(narration_backend="edge-tts")
        assert chk.voiced_by(film, plain) == 0

        # ④ 老片子没记这个字段 → 跳过，不许当成不合格（那会变成一条常年红）
        meta(narration_voice="zh-CN-YunjianNeural")
        assert chk.voiced_by(film, styled) == 0

        # ⑤ 连 render.json 都没有 → 同样跳过
        (out / "render.json").unlink()
        assert chk.voiced_by(film, styled) == 0

    # **它真的被接进总数里**：只测函数拦不住「算出来了没人用」，
    # 而那正是这条测试要防的第一版毛病
    body = inspect.getsource(chk.main)
    assert re.search(r"bad\s*=\s*voiced_by\(", body), \
        "voiced_by 的返回值没有接进 bad——又是「算出来了没人用」"


def test_推送前也要查数据图头像挂没挂错名字(tmp_path):
    """`sonmez-anisimova` / `tsitsipas-royer` 两次真事故——数据图把赢球的
    那个人印成了对手的数字，图上每个数单看都对，只有把名字和数字对起来才
    看得出来。CI 里有一条测试干这件事（`test_数据图的头像和matchup里的名字
    必须是同一个人`），但**这道推送前的最后关卡从来没有这一项**——
    `tsitsipas-royer` 那条错的成片是真的发出去了，而 `check_reel_landed`
    全绿。

    ⚠️ 只有「和别的 spec 矛盾」才算不合格；「第一次出现，没有第二处可比」
    只报一句提醒，不拦——不然每一个新球员的首秀都会被判成不合格。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_reel_landed as chk  # noqa: PLC0415

    reels = tmp_path / "specs" / "reels"
    reels.mkdir(parents=True)

    def _write(slug, names, a_shot, b_shot):
        (reels / f"{slug}.json").write_text(json.dumps({
            "cover": {"matchup": [{"name": names[0]}, {"name": names[1]}]},
            "stats": {"a": {"headshot": a_shot}, "b": {"headshot": b_shot}},
        }), encoding="utf-8")

    # 已经落库的一条：wta-1.jpg 挂着"甲"，wta-2.jpg 挂着"乙"
    _write("existing", ["甲", "乙"], "assets/headshots/wta-1.jpg",
           "assets/headshots/wta-2.jpg")

    # ① 新的一条把 a/b 填反了——同一张 wta-1.jpg 这次挂"乙"，和已有的矛盾
    reversed_spec = {
        "cover": {"matchup": [{"name": "乙"}, {"name": "甲"}]},
        "stats": {"a": {"headshot": "assets/headshots/wta-1.jpg"},
                  "b": {"headshot": "assets/headshots/wta-2.jpg"}},
    }
    got = chk.stat_card_headshot_problem(reversed_spec, reels)
    assert got is not None and got[0] is True, f"填反了却没拦住：{got}"
    assert "不合格" in got[1] and "wta-1.jpg" in got[1]

    # ② 新的一条填对了——同样引用 wta-1.jpg/wta-2.jpg，名字和已有的一致
    correct_spec = {
        "cover": {"matchup": [{"name": "甲"}, {"name": "乙"}]},
        "stats": {"a": {"headshot": "assets/headshots/wta-1.jpg"},
                  "b": {"headshot": "assets/headshots/wta-2.jpg"}},
    }
    assert chk.stat_card_headshot_problem(correct_spec, reels) is None, \
        "填对了不该报"

    # ③ 全新的头像，没有第二处可比——只报提醒，不算不合格
    fresh_spec = {
        "cover": {"matchup": [{"name": "丙"}, {"name": "丁"}]},
        "stats": {"a": {"headshot": "assets/headshots/wta-99.jpg"},
                  "b": {"headshot": "assets/headshots/wta-98.jpg"}},
    }
    got = chk.stat_card_headshot_problem(fresh_spec, reels)
    assert got is not None and got[0] is False, f"第一次出现不该算不合格：{got}"
    assert "注意" in got[1] and "第一次出现" in got[1]

    # ④ 双打（headshot 是列表）跳过——不是"填反了"，是团队照
    doubles_spec = {
        "cover": {"matchup": [{"name": "甲组"}, {"name": "乙组"}]},
        "stats": {"a": {"headshot": ["assets/headshots/wta-1.jpg",
                                      "assets/headshots/wta-3.jpg"]},
                  "b": {"headshot": ["assets/headshots/wta-2.jpg",
                                      "assets/headshots/wta-4.jpg"]}},
    }
    assert chk.stat_card_headshot_problem(doubles_spec, reels) is None, \
        "双打头像不该被当成填反了"

    # ⑤ **`self_path` 不传，"我在扫我自己"会把"第一次出现"永远判成哑的。**
    # `check_reel_landed.py` 查的那条 spec 早就已经提交进仓库了——真实场景
    # 里它自己就在 `reels_dir` 里，不排除的话 `seen` 永远至少包含它自己，
    # `first_seen` 从此恒假。这条钉住"传了 self_path 就该排除自己"。
    self_file = reels / "fresh.json"
    self_file.write_text(json.dumps(fresh_spec), encoding="utf-8")
    # 不传 self_path：扫描会撞见自己刚写下的 fresh.json，把自己当成了
    # "已有先例"——`prior` 因此非空，`first_seen` 那条分支走不到，
    # 整个函数悄悄返回 None，**提醒消失了，而且不报错**
    without_self = chk.stat_card_headshot_problem(fresh_spec, reels)
    assert without_self is None, (
        "这一步是在钉住那个坑本身：不排除自己时，扫描会把这条 spec 自己"
        f"算成先例，'第一次出现'的提醒会静悄悄地消失：{without_self}")
    with_self = chk.stat_card_headshot_problem(
        fresh_spec, reels, self_path=self_file)
    assert with_self is not None and with_self[0] is False, \
        f"排除自己之后应该正确报'第一次出现'：{with_self}"
    assert "第一次出现" in with_self[1]

    # **它真的被接进总数里，而且只在真矛盾时才计**——同一个「算出来了没人用」
    body = inspect.getsource(chk.main)
    assert re.search(r"stat_card_headshot_problem\(", body), \
        "stat_card_headshot_problem 没被调用——又是「算出来了没人用」"
    assert re.search(r"if\s+is_clash:\s*\n\s*bad\s*\+=\s*1", body), \
        "没把真矛盾接进 bad，或者把「第一次出现」的提醒也算成了不合格"


def test_ffprobe的csv输出带尾随逗号也解析得出来():
    """2026-08-19 撞的：`ensure_ffmpeg` 第一版装的是 BtbN/FFmpeg-Builds 的
    `latest` 标签——那是**每天跟着 master 重新构建**的快照，不是钉死的版本。
    当天下到的 ffprobe 对 `-show_entries stream=duration -of csv=p=0` 吐出
    `117.480000,`（带一个尾随空字段），`float()` 直接 `ValueError`，
    整条 render 在最后一步（`查成片本身合不合格`）崩掉（run 32307313856）。

    根因换成 johnvansickle.com 的稳定版之后不会再犯，但解析本身不该赌
    「下一个 ffprobe 版本永远只吐一个干净的数」——这条测试真喂那个坏字符串，
    钉住 `_ffprobe_float` 不管尾巴上多出什么都取得出第一个数。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_reel_landed as chk  # noqa: PLC0415

    # ① 正常的干净输出（apt 那个稳定版、johnvansickle 那个稳定版都是这样）
    assert chk._ffprobe_float("117.480000\n") == pytest.approx(117.48)
    # ② 当天真炸的那个字符串——多一个尾随逗号（空字段）
    assert chk._ffprobe_float("117.480000,\n") == pytest.approx(117.48)
    # ③ 反向验证：换回没有这层保护的写法，②这个真实样本会崩
    with pytest.raises(ValueError):
        float("117.480000,\n".strip())


def test_屏幕上的次也要写成数字而分发强成不许写():
    """同一行里两种写法，是「转了一半」——和「北京时间8月三号零点」同一个毛病。

    2026-08-04 抽帧看见 `前5局又破了三次 4比1`：三个数都是在数数，「局」和
    「比」转了，「次」没转，因为 `_NUM_UNITS` 里漏了它。

    ⚠️ **同一轮扫存量时另外几个字必须不转**，所以这条测试两头都钉：

    | | | |
    |---|---|---|
    | 「三分之一」 | 加「分」就成 **「3分之一」** | 分数不是数数 |
    | 「一发」「二发」 | 术语 | 加「发」就成「2发」 |
    | 「四强」「三成」 | 术语／约数 | |
    | 「十七分」→「17分」 | **本来就转** | 走「含十百千」那条，不靠这张表 |
    """
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video.explainer import arabic_numerals  # noqa: PLC0415

    for raw, want in (("前五局又破了三次", "前5局又破了3次"),
                      ("来回打了三次平分", "来回打了3次平分"),
                      ("连续七次交手", "连续7次交手")):
        assert arabic_numerals(raw) == want, f"{raw} → {arabic_numerals(raw)}"

    # 反面锚点：这些一个字都不许动
    for raw in ("三分之一", "一发", "二发", "四强", "三成", "七成",
                "唯一一次", "第一次", "一次", "两次",
                "依次", "其次", "层次", "档次", "多次", "这次", "首次"):
        assert arabic_numerals(raw) == raw, f"{raw} 被误伤成 {arabic_numerals(raw)}"

    # 「十七分」不靠量词表——它走「含十百千」那条，别为它去加「分」
    assert arabic_numerals("只赢了十七分") == "只赢了17分"


# 「分」在这个栏目里有三个意思，而**只有一个会被误读**。
# 账号所有者 2026-08-04：「『15 分之后结束』，可能会给人误导，以为打了 15 分钟，
# 其实是打了 15 point」，随后又划清了边界：「得分 71 比 64，只差 7 分。这个 ok，
# 没啥歧义，但 15 分后结束这一局类似的说话可能会有歧义」。
#
# 判据因此**不是「出现了 N 分」**，是「**这个 N 分的意思有没有被钉住**」：
#
# | | 例 | 为什么 |
# |---|---|---|
# | ✅ 放行 | 赢了十七分 / 拿到六十二分 / 只差七分 / 连拿四分 | **分钟不能「赢」也不能「拿」**，动词把它钉死了 |
# | ✅ 放行 | 一小时三十四分 / 上午十点三十五分 / 二十九分钟 | 前面有小时、点，或者后面有钟 |
# | ✅ 放行 | 那一局，**一**分没拿到 / 赢下最后**一**分 | 单数的那一分，说的是场上正在打的一分 |
# | ❌ 拦 | **打了十四分** / **十五分之后** / **最后十分** / 那一局，十三分 | 换成分钟读一样通顺 |
#
# ⚠️ **「一」必须排除**，不然「赢下最后一分」这种好句子会被误伤——第一版就是
# 这么来的，16 处里 4 处是它。判据宁可窄，不可宽。
_AMBIGUOUS_POINT = (
    (r"打了\s*[二三四五六七八九十百千两〇零0-9][二三四五六七八九十百千两〇零0-9]*\s*分(?!钟)",
     "打了N分"),
    (r"(?<![一])[二三四五六七八九十百千两〇零0-9]+\s*分\s*(?:之?后)", "N分之后"),
    (r"最后\s*[二三四五六七八九十百千两〇零0-9]+\s*分(?!钟)", "最后N分"),
    (r"局[，,]\s*[二三四五六七八九十百千两〇零0-9]+\s*分(?![钟里])", "那一局，N分"),
)

# 规矩之前发出去的六条，**只许减不许加**。已发的片子不为措辞重渲——而且它们的
# `copy.html` 已经提交进 main，改 xhs 会打红「算出来的和已经发出去的一模一样」
# 那道判据。
_LEGACY_AMBIGUOUS_POINT = {
    "eala-osaka", "eala-svitolina", "eala-zheng",
    "fritz-jodar-final", "shang-vallejo", "wong-gea",
}


def test_旁白里的分不许读成分钟():
    """见上面那张表。改法是账号所有者给的：**用「几次平分」说**。

    「这一局打了十四分」→「这一局来回打了四次平分」——既不歧义，又比一个抽象的
    点数有画面。这条片子第 5 段本来就是这么写的（「四比一之后那一局，来回打了
    三次平分」），所以不是新发明，是把已经在用的写法立成规矩。
    """
    sys.path.insert(0, str(Path("src").resolve()))

    offenders: dict[str, list[str]] = {}
    checked = 0
    for spec in sorted(Path("specs/reels").glob("*.json")):
        data = json.loads(spec.read_text("utf-8"))
        texts = [str(s.get("narration") or "") for s in data.get("segments") or []]
        copy = Path(f"specs/reels/{spec.stem}.xhs.txt")
        if copy.is_file():
            texts.append(copy.read_text("utf-8"))
        checked += 1
        for text in texts:
            for pattern, name in _AMBIGUOUS_POINT:
                for m in re.finditer(pattern, text):
                    offenders.setdefault(spec.stem, []).append(
                        f"[{name}] {m.group(0)}")

    # 判据自己的判据：主语不许为空，否则这条测试是一盏恒真的绿灯
    assert checked >= 15, f"只扫到 {checked} 条 spec——目录写错了？"

    fresh = {k: v for k, v in offenders.items()
             if k not in _LEGACY_AMBIGUOUS_POINT}
    assert not fresh, (
        "这些「N 分」换成「N 分钟」读一样通顺，读者分不出是点数还是时间：\n"
        + "\n".join(f"  {k}: {' / '.join(v)}" for k, v in fresh.items())
        + "\n改法（账号所有者定的）：**用「几次平分」说**——"
        "「这一局打了十四分」→「这一局来回打了四次平分」。\n"
        "写不成平分就写「N 个小分」；说的要真是时间就写「N 分钟」。")

    # ⚠️ **豁免表要自证它豁免的是真的还在违规。** 一个写错的名字就是一盏
    # 永远亮着的绿灯——这个仓库为它栽过。
    stale = _LEGACY_AMBIGUOUS_POINT - set(offenders)
    assert not stale, (
        f"{sorted(stale)} 已经不违规了（或者名字写错了），从豁免表里删掉——"
        "这张表只许减不许加")


def test_韵律报告要认得出哪几段带风格():
    """账号所有者 2026-08-04：「成片音轨听着行不行——这个怎么评判？」

    「听着行不行」拆得开：音高、响度、语速三样能量，音色和自然度不能。
    `prosody_report` 报前三样，并把**带风格的和不带的**摆在一起比——这是
    「情绪弧做出来没有 / 有没有做过头」唯一不用耳朵的答案。

    ⚠️ 这条测试拦的是一个**会静默失效**的写法：第一版取的是 `seg.voice`
    （一个不存在的字段）加 `hasattr` 兜底，于是每段都取到空串，
    「带风格」那一组永远是空的，**报告照样出得来、一个字的错都不报**。
    又一次「签名对了、实现是空的」。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    import build_match_reel as reel

    segs = [
        reel.Segment(start=0.0, end=6.0, cx=None, narration="第一段没有风格。"),
        reel.Segment(start=6.0, end=12.0, cx=None, narration="第二段很激动。",
                     voice_style="sports-commentary-excited"),
    ]
    voices = [(Path("/nonexistent-0.mp3"), []), (Path("/nonexistent-1.mp3"), [])]
    lines = reel.prosody_report(segs, voices, {0: 5.0, 1: 5.0})
    body = "\n".join(lines)

    # 风格名必须真的出现在报告里——取错字段的话这里是空的
    assert "sports-commentary-excited" in body, (
        "报告里没有风格名，多半是取错了字段"
        "（`Segment` 上是平铺的 `voice_style`，不是 `voice` 字典）")
    # 量不了要**说量不了**，不许猜一个数出来
    assert "量不了" in body, "文件不存在时应当明说量不了，而不是给一个编的数"
    # 音色那一句不能省：一张全绿的表不许被读成「已经验过了」
    assert "音色" in body and "只能听" in body

    # 位置：这个报告必须真的接在查旁白那条路上。**只测行为拦不住没接线**
    src = Path("tools/build_match_reel.py").read_text("utf-8")
    head = src.index("if args.check_narration:")
    region = src[head:head + 4000]
    assert "prosody_report(" in region, (
        "`mode=narration` 那条路上没有调用 prosody_report——"
        "语音只在那一刻还在临时目录里，错过就只能去量混了现场声的成片")
    # ⚠️ **而且要在 `with tempfile.TemporaryDirectory()` 里面。** 第一版印在
    # 外面，语音早被删了，十一段全报「文件不在」（run 30901516117）——
    # 调用接上了、位置错了，**而报告照样出得来**。缩进就是判据：
    # `with` 里是 12 格，外面是 8 格。
    call = next(ln for ln in region.splitlines() if "prosody_report(segments" in ln)
    assert len(call) - len(call.lstrip()) >= 12, (
        f"prosody_report 调用的缩进是 {len(call) - len(call.lstrip())} 格，"
        "说明它在临时目录那个 with 外面——那时语音已经删了")


def test_栏目基调只填空位不许盖掉段级风格():
    """账号所有者 2026-08-04：「以后所有配音都能自适应情绪么？」

    分三层，只做第三层：

    | | 做不做 | 为什么 |
    |---|---|---|
    | 每段都能带风格 | ✅ 已经能 | 额度够（已发 21 条 8352 字，F0 免费 50 万字符/月） |
    | **按文本自动判情绪** | ❌ **不做** | 判错了不吭声，还会把「机器猜的」伪装成「你想清楚了」 |
    | **按栏目定基调** | ✅ 做 | **栏目是已知的，情绪不是** |

    ⚠️ 基调**只填空位**：段级 `voice.style` 是编辑判断（「第 7 段要 excited」），
    一个按栏目算出来的默认值不许盖掉它。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    import build_match_reel as reel
    import pytest  # noqa: PLC0415
    from tennislive.video import azure_tts

    # ① 基调必须是**服务端实测通过**的风格，不能是随手写的名字——
    #    ⚠️ 拼错的风格名 Azure 是**静默忽略**的，合成照样成功，只是没有情绪
    # ⚠️ **空串是「实测之后决定不设」**，不是漏填——它和「根本没登记」处置一样
    # 但说法必须不一样，靠 `is_registered()` 分开
    def _vet(table: dict[str, tuple[str, str]]) -> None:
        """基调表的三条规矩。抽出来是因为**现在表里一条活的都没有**——
        直接写成断言的话它们会恒真，而一条恒真的检查和没有检查是同一个毛病。"""
        live = {k: v for k, v in table.items() if v[0]}
        styles = {v[0] for v in live.values()}
        assert styles <= set(azure_tts.KNOWN_STYLES), (
            f"{sorted(styles - set(azure_tts.KNOWN_STYLES))} 不在实测通过的表里"
            "——⚠️ 拼错的风格名 Azure 是**静默忽略**的，合成照样成功只是没有情绪")
        # ⚠️ 满档太重（实测抬 50% 音高），设了基调就要显式写 degree
        assert all(v[1] for v in live.values()), (
            "基调必须显式写 styledegree——默认 1.0 实测把八段从 115–128 Hz "
            "抬到 184–188，那不是基调是换了个人念")
        # 那五个「时长和基线几乎一样」的不许当基调（服务端认 ≠ 听起来对）
        suspect = {"narration-relaxed", "serious", "angry", "disgruntled",
                   "cheerful"}
        assert not (styles & suspect), (
            "这几个风格实测时长和基线几乎一样，别拿来当整条片子的基调")

    _vet(azure_tts.COLUMN_BASE_STYLE)
    # ⚠️ **判据自己的判据。** 2026-08-04 之后两个栏目都是「不设」，上面那三条
    # 于是一条都咬不到东西。拿三个**故意写坏**的表各喂一次，证明它们还活着——
    # 不然这段检查会在表被重新填上的那天悄悄放行。
    for bad, hint in (
        ({"x": ("no-such-style", "0.5")}, "拼错的风格名"),
        ({"x": ("documentary-narration", "")}, "没写 styledegree"),
        ({"x": ("cheerful", "0.5")}, "时长和基线几乎一样的那五个"),
    ):
        with pytest.raises(AssertionError):
            _vet(bad)

    assert azure_tts.is_registered("赛场之上") and not azure_tts.base_style_for("赛场之上")[0], (
        "赛场之上是**登记过的「不设」**（三趟实测），不许退化成「没登记」——"
        "那样日志会说「漏了」，而它是想清楚的")
    # ⚠️ 网球有故事同理：它是**账号所有者听完撤掉的**（2026-08-04「不要改成那种
    # 情绪化的，还用原来的那种配音」），不是没人顾上。退化成「没登记」就把一个
    # 听过之后的决定抹成了「漏了」。
    assert azure_tts.is_registered("网球有故事") and not azure_tts.base_style_for("网球有故事")[0], (
        "网球有故事是**登记过的「不设」**，见 azure_tts 里那段注")
    assert not azure_tts.is_registered("没这个栏目")
    # ③ 登记过的栏目要真的在 spec 里出现过——一张会过期的表和一条常年红的
    #    检查是同一个毛病
    used = {str((json.loads(p.read_text("utf-8")).get("cover") or {})
                .get("eyebrow") or "")
            for p in Path("specs/reels").glob("*.json")}
    stale = set(azure_tts.COLUMN_BASE_STYLE) - used
    assert not stale, f"{sorted(stale)} 这些栏目在 specs 里根本不存在"
    assert azure_tts.base_style_for("没这个栏目") == ("", "")

    # ④ 段级永远赢：给基调，带 style 的那段必须还是自己的
    seen: list[str] = []
    degrees: list[str] = []

    def fake_tts(text, path, voice, rate, pitch="+0Hz", style="",
                 styledegree="", lead_pause=0.0):
        seen.append(style)
        degrees.append(styledegree)
        path.write_bytes(b"x")
        return []

    segs = [
        reel.Segment(start=0.0, end=6.0, cx=None, narration="没写风格的一段。"),
        reel.Segment(start=6.0, end=12.0, cx=None, narration="写了风格的一段。",
                     voice_style="sports-commentary-excited"),
    ]
    import tempfile
    orig = reel.tts_one
    reel.tts_one = fake_tts
    try:
        with tempfile.TemporaryDirectory() as tmp:
            reel.synthesize(segs, Path(tmp), "v", "+6%",
                            base_style="sports-commentary", base_degree="0.5")
    finally:
        reel.tts_one = orig
    assert seen == ["sports-commentary", "sports-commentary-excited"], (
        f"基调应该只填空位、段级永远赢，实际拿到 {seen}")
    # ⚠️ **degree 要跟着 style 走**：段级风格配基调的 degree 是张冠李戴
    assert degrees == ["0.5", ""], f"degree 没跟着 style 走，实际 {degrees}"


def test_没有Azure的时候不许硬套基调():
    """⚠️ 硬套的话 `tts_one` 会对**每一段**抛「这一段要 voice.style」——

    一个本来只是「音色朴素一点」的降级，会变成整条片子渲不出来。
    而且「没配基调」和「配了但没生效」长得一模一样，所以两条路都要打日志。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    import build_match_reel as reel

    spec = {"cover": {"eyebrow": "赛场之上"}}
    src = Path("tools/build_match_reel.py").read_text("utf-8")
    body = src[src.index("def column_base_style("):src.index("def synthesize(")]
    assert "azure_tts.available()" in body and 'return "", ""' in body, (
        "没有 Azure 的时候必须返回空基调")
    assert "print(" in body and "why_unavailable" in body, (
        "两条路都要出声——「没配基调」和「配了但没生效」长得一模一样")
    assert reel.column_base_style(spec) == ("", "") or reel.azure_tts.available()


def test_情绪风格要写谁听过不是写为什么想用():
    """⚠️ **量得出来的三维，没有一维在量「糙不糙」。**

    2026-08-04：王欣瑜那条的第 7/9/10 段上了 excited / sad / depressed。理由写得
    很足，还配了三维实测——基频 219.2 Hz、响度 −24.2 dB、语速 5.38 字每秒——我据此
    论证「不吵、不快、只是高」并建议发。账号所有者听完的原话是
    **「配音真的是太粗细了，还是不要改成那种情绪化的，还用原来的那种配音」**。

    那三个数都量对了。**它们只是都不在量音色自不自然**，而那正是唯一要紧的那一维。
    所以 `_why`（为什么想用）不够，得有 `_heard`（谁听过、听下来怎么样）——和
    `mixed_fps` / `silent_source` / `rank: null` 一个形状：认领这一步把
    「听下来行」和「量下来应该行」分开。

    ⚠️ 只管 `style`。`rate` / `pitch` / `lead_pause` 不改音色，`_why` 管得住。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel
    import pytest  # noqa: PLC0415

    def seg(**voice):
        return {"start": 0.0, "end": 9.0, "narration": "随便一句。",
                "voice": voice}

    # ① 有 style 没 _heard → 报错，而且要说出两条不改音色的出路
    with pytest.raises(reel.ReelError) as err:
        reel._seg_voice(seg(style="sad", _why="崩盘那一段"), 0)
    msg = str(err.value)
    assert "_heard" in msg
    for way in ("断句", "气口", "lead_pause"):
        assert way in msg, f"报错要指出「{way}」这条不改音色的路，现在只有：{msg}"

    # ② 写了 _heard 就放行
    assert reel._seg_voice(
        seg(style="sad", _why="崩盘", _heard="账号所有者 8/4 听过，可以"), 0
    )[2] == "sad"

    # ③ ⚠️ 反向：不带 style 的不受这道闸管——扩大化的判据不吭声，它只会让
    #    下一个人把「降个速」也当成要听一遍的事
    assert reel._seg_voice(seg(rate="-10%", _why="落点，慢下来"), 0)[0] == "-10%"
    assert reel._seg_voice(seg(lead_pause=0.4, _why="进第二盘留口气"), 0)[4] == 0.4

    # ④ 存量里凡是写了 style 的，都得有 _heard——这条测试要有主语
    styled = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        for i, s in enumerate(json.loads(path.read_text("utf-8")).get("segments", [])):
            voice = s.get("voice") or {}
            if str(voice.get("style", "") or "").strip():
                styled += 1
                assert str(voice.get("_heard", "") or "").strip(), (
                    f"{path.name} 第 {i + 1} 段写了 style 却没有 _heard")
    # ⚠️ 这里**不要求 styled > 0**：现在全仓库一条都没有（都撤了），而那正是
    #    这条规矩想要的状态。①②③ 已经直接喂函数验过，主语不在存量上。


def test_气口要算进旁白的离线估():
    """⚠️ `lead_pause` 占的是**同一个窗口**的时间，不算进去就是一条乐观的估。

    `speech_seconds()` 只看文本，而 `lead_pause` 是段首那个真 `<break>`。不加的话
    这条离线估**正好乐观 `lead_pause` 秒**，然后在六分钟之后的真 render 里才炸——
    又是「兜底出事的时候不吭声」，只不过这次不吭声的是估算本身。

    ⚠️ 加在 `narration_estimates` 而不是 `speech_seconds`：后者的系数是拿**已发
    成片**拟合并钉住的（`test_离线估旁白长度要对得上真产物`），掺进段级参数就没法
    再和那批产物对账了。这条测试连**加在哪一层**一起钉。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel
    import pytest  # noqa: PLC0415

    text = "然后她连丢四局。"
    plain = reel.Segment(start=0.0, end=9.0, cx=None, narration=text)
    winded = reel.Segment(start=0.0, end=9.0, cx=None, narration=text,
                          voice_lead_pause=0.6)
    (_, a, room_a), = reel.narration_estimates([plain])
    (_, b, room_b), = reel.narration_estimates([winded])
    assert b - a == pytest.approx(0.6, abs=1e-6), (
        f"气口没算进去：带 0.6s lead_pause 估出来 {b}，不带是 {a}")
    assert room_a - room_b == pytest.approx(0.6, abs=1e-6), "余量也要跟着缩"

    # ⚠️ 层次：`speech_seconds` 必须还是「纯文本进、秒数出」
    assert reel.speech_seconds(text) == pytest.approx(a, abs=1e-6), (
        "`speech_seconds` 不许自己去读段级参数——它的系数是拿已发成片拟合的")
    import inspect as _inspect
    assert list(_inspect.signature(reel.speech_seconds).parameters) == ["text"], (
        "`speech_seconds` 只该收文本；气口加在 `narration_estimates` 那一层")


def test_中立身份的球员可以显式声明没有国旗():
    """⚠️ **`country: null` 是「查过，他没有国旗」，不是「忘了填」。**

    2026-08-05 卢布列夫那条查下来：**ATP 自己的排名表里，他是唯一一个名字后面
    没有国家缩写的**（同一页 Musetti (ITA)、Ruud (NOR)、Jódar (ESP) 都有），
    flashscore 给的国别字段也是 `World`。他是中立身份。

    印俄罗斯旗等于**替这项运动做了一个它自己没做的声明**；而「中立旗」这个
    emoji 并不存在。所以留空——但必须**显式认领并且出声**，和
    `rank: null` / `mixed_fps` / `silent_source` 一个形状。

    ⚠️ 键不许省：省掉之后「查过是中立身份」和「手滑漏了」长得一模一样。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    sys.path.insert(0, str(Path("src").resolve()))
    import pytest  # noqa: PLC0415
    import versus_poster as vp

    # ① 中立：渲得出来，而且**不留空的 <b></b>**（那会在旗位留一块空白）
    out = vp._name_html("卢布列夫", {"country": None, "rank": 16}, "t")
    assert "卢布列夫" in out and "（16）" in out
    assert "<b>" not in out, f"中立不该留空的旗位标签，实际 {out}"

    # ② 正常那条不许被带坏
    ok = vp._name_html("商竣程", {"country": "CHN", "rank": 270}, "t")
    assert "<b>🇨🇳</b>" in ok and "（270）" in ok

    # ③ 省掉键 → 报错，**而且要指出 null 这条出路**（报错要说出路）
    with pytest.raises(SystemExit) as err:
        vp._name_html("x", {"rank": 1}, "t")
    assert "null" in str(err.value) and "中立" in str(err.value)

    # ④ ⚠️ 空串**不等于** null：前者是手滑，后者是认领过的。两支要分开
    with pytest.raises(SystemExit) as err2:
        vp._name_html("x", {"country": "", "rank": 1}, "t")
    assert "空字符串" in str(err2.value)

    # ⑤ 认了国旗但写错码，照旧要红（别把这道闸一起放宽了）
    with pytest.raises(SystemExit):
        vp._name_html("x", {"country": "ZZZ", "rank": 1}, "t")

    # ⑥ 出声：走中立那支必须打日志——不然「中立」和「渲丢了」看不出区别
    src = Path("tools/versus_poster.py").read_text("utf-8")
    body = src[src.index("def _name_html("):src.index("_SET_RE")]
    assert "country: null" in body and "print(" in body, (
        "走中立那条路要在日志里出声")


def test_文案的闸要在dry_run里就报不许等渲完():
    """⚠️ **文案的两道闸原来只活在 render 之后。**

    `push_reel.py --stage page` 校「正文 ≤1000 字」和「tag ≤5 个」，而那一步
    在工作流里排在 **render 之后**。2026-08-05 `chwalinska-gibson` 的文案写了
    6 个 tag，**渲完两分半才报**（run 30974892914：render success 2:36，
    第 23 步 0 秒红）。

    **文案是一个纯文本文件，判它一个源片像素都不用碰**——没有理由让它等在
    编码后面。这就是「返工比慢更贵」：让失败发生在第 0.2 秒。

    判据钉三头：
    1. `--dry-run` 真的读文案并把两个数打出来
    2. tag 超标时**退出码是 1**（只打一行字等于没拦）
    3. ⚠️ **闸本身不许在 dry-run 里重写**——直接调 `push_reel` 那两个函数。
       写两遍必分叉，而分叉的那天没人会知道
    """
    import subprocess  # noqa: PLC0415

    body = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    head = body.index("if args.dry_run:")
    tail = body.index("est = narration_estimates(segments)", head)
    block = body[head:tail]
    assert "push_reel" in block, "dry-run 没有校文案"
    assert "MAX_HASHTAGS" in block and "hashtag_count" in block, (
        "tag 那道闸在 dry-run 里被重写了一遍——要调 push_reel 的，别自己写")
    assert re.search(r"return 1", block), "tag 超标只打字不返回 1，等于没拦"

    # 行为：真跑一次，两个方向
    # 不再拿字母序第一条：它是规则落地前的存量冷开场，生产 dry-run 按设计会红。
    # 用已经显式声明并完整兑现结局的干净底稿，才是在单独测文案闸。
    spec = Path("specs/reels/tiafoe-musetti-cincinnati-2026-qf.json")
    assert spec.with_suffix(".xhs.txt").is_file()
    copy = spec.with_suffix(".xhs.txt")
    original = copy.read_text(encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": "src:tools"}
    cmd = ["python3", "tools/build_match_reel.py", "render", "--spec", str(spec),
           "--outdir", "/tmp/_dryrun_probe", "--dry-run"]
    try:
        ok = subprocess.run(cmd, capture_output=True, text=True, env=env)
        assert ok.returncode == 0, f"干净的文案不该红：{ok.stdout[-400:]}"
        assert "文案" in ok.stdout and "tag" in ok.stdout, (
            f"dry-run 没把文案那两个数打出来：{ok.stdout[-300:]}")
        # 反向：塞进第六个 tag
        copy.write_text(original.rstrip("\n") + " #多加一个\n", encoding="utf-8")
        bad = subprocess.run(cmd, capture_output=True, text=True, env=env)
        assert bad.returncode == 1, (
            f"tag 超标了却没红（退出码 {bad.returncode}）：{bad.stdout[-300:]}")
    finally:
        copy.write_text(original, encoding="utf-8")


def test_盘点赛点谁救的必须写出来():
    """⚠️ **第一条真实读者反馈换来的判据。**

    小红书评论（2026-08-05，商竣程那条）：「**什么叫 三个盘点都没救下来**」。

    我写的是——旁白第 9 段「卢布列夫要到三个盘点。」第 10 段「三个都没能救
    下来。」**主语中途换了人，而且跨了一次镜头切换**。中文承前省略主语，
    读者只能把「没救下来」接成卢布列夫，而**那不通**：盘点是他自己拿到的，
    他没有什么可救。

    判据落在**「点」前面那个动词**上，这一条是机械的：

    | 写法 | 救的是谁 | |
    |---|---|---|
    | 他**面对** 7 个破发点，救下 6 个（`gea-shapovalov`） | 同一个人 | ✅ 不用重写主语 |
    | 卢布列夫**拿到**三个盘点，都没救下来 | **另一个人** | ❌ 必须写出来 |

    「拿到 / 要到 / 得到 / 握有」的点是**他自己的**，救它的必然是对手；
    「面对 / 面临」的点才是他自己要救的。所以只扫前一类。

    ⚠️ **只扫「救 / 保住」，不扫「兑现」**：兑现自己拿到的点，主语没变，
    `chwalinska-gibson` 那句「赫瓦林斯卡拿到三个破发点——一个都没兑现」是对的。
    第一版把「面对…救下」也扫进来，当场误伤 `gea-shapovalov`——
    又一次「判据宁可窄，不可宽」。
    """
    # 正则和判定的单一出处在 tools/spec_wording.py（validate_spec 和
    # promote_reel_draft 用同一份）。
    from tools.spec_wording import OWN_POINT as own  # noqa: PLC0415
    from tools.spec_wording import (  # noqa: PLC0415
        save_subject_flag,
        spec_player_names,
    )
    bad, checked = [], 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        names = spec_player_names(spec)
        text = "".join(s.get("narration", "") for s in spec["segments"])
        copy = path.with_suffix(".xhs.txt")
        if copy.is_file():
            text += "\n" + copy.read_text(encoding="utf-8")
        checked += sum(1 for _ in own.finditer(text))
        bad += [f"{path.stem}: {frag}"
                for frag in save_subject_flag(text, names)]
    assert not bad, (
        "「拿到 N 个盘点」之后接「救/保住」，中间没有写出是谁在救——"
        "读者会把主语接成拿到点的那个人：\n  " + "\n  ".join(bad))
    # **判据自己的判据**：正则一旦写死，这条会变成恒真的绿灯
    assert checked >= 1, "一处「拿到 N 个盘点」都没扫到——正则是不是写宽/写死了？"

    # 行为：正反两个方向
    def _flag(text: str, names: list[str]) -> bool:
        return bool(save_subject_flag(text, names))

    who = ["商竣程", "卢布列夫"]
    assert _flag("卢布列夫拿到三个盘点。三个都没能救下来。", who), "该拦的没拦住"
    assert not _flag("卢布列夫拿到三个盘点。三个商竣程一个都没保住。", who), (
        "写出主语了还拦，误伤")
    assert not _flag("他面对七个破发点，救下六个。", who), (
        "「面对…救下」主语没变，不该拦")
    assert not _flag("她拿到三个破发点，一个都没兑现。", ["她"]), (
        "「拿到…兑现」主语没变，不该拦")
def test_有母版就不许再渲一遍(tmp_path, monkeypatch):
    """账号所有者 2026-08-05：「就做好一个带口播的视频段，每次都拼接到最后
    不行么？」——对的，实测账（沙箱，一条片子付一遍）：

        TTS 0.92s ＋ 渲页 7.58s ＋ 编码 5.88s ＝ **14.38s**
        从母版转码                              ＝ **1.1~2.5s**

    比省时间更硬的理由是**一致性**：每次重新跑 edge-tts，服务端合成的输出可能
    有微小差异，而「强化记忆」靠的正是每条片子结尾一模一样的那一下。

    所以这条判据钉的是「母版在的时候，Chromium 和 TTS 一次都不许被碰」——
    **省时间的全部来源就是这两样没跑**。只验产物出来了的话，一个偷偷还在渲
    Chromium 的实现照样绿，而它慢 12 秒且不吭声。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    from tennislive.video import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    assert outro_page.MASTER.is_file(), (
        f"母版不在：{outro_page.MASTER}——跑一次 "
        "PYTHONPATH=src python3 tools/build_outro_master.py 并把它提交上去")

    touched = []
    monkeypatch.setattr(outro_page, "render_layers",
                        lambda *a, **k: touched.append("chromium"))
    monkeypatch.setattr(outro_page, "render_clip",
                        lambda *a, **k: touched.append("render_clip"))

    dest = tmp_path / "o.mp4"
    outro_page.build_with_voice(
        tmp_path, chromium="", dest=dest, fps=25.0, audio_rate="48000",
        preset="ultrafast", crf="26", audio_bitrate="128k", audio_channels=2)

    assert not touched, (
        f"母版在，却还是走了 {touched}——那条路要 14.4 秒，"
        "而从母版转码只要 2 秒")
    assert dest.is_file(), "母版那条路没出片"

    # 转出来的参数要真的是要的那一组（`-c copy` 的 concat 对这个最挑）
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=r_frame_rate,sample_rate,channels", "-of", "csv=p=0", str(dest)],
        check=True, capture_output=True, text=True).stdout
    assert "25/1" in info, f"帧率没转对：{info}"
    assert "48000" in info, f"采样率没转对：{info}"


def test_母版要按上界存():
    """母版的帧率/采样率必须**不低于**任何一条线要的那一档。

    转码只能往下走：60→25 是抽帧，25→60 是插帧（动效会顿）；
    48000→24000 无损失，24000→48000 补不出信息。所以母版按上界存，
    **改任何一条线的参数时这条会替人记得回来看一眼**。
    """
    import subprocess  # noqa: PLC0415

    from tennislive.video import outro_page  # noqa: PLC0415

    assert outro_page.MASTER.is_file(), "母版不在"
    fps_s, rate_s = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=r_frame_rate,sample_rate", "-of", "csv=p=0", str(outro_page.MASTER)],
        check=True, capture_output=True, text=True).stdout.split()
    num, den = (fps_s.rstrip(",").split("/") + ["1"])[:2]
    fps = float(num) / float(den)
    rate = int(rate_s.rstrip(",").split(",")[0])

    # 三条线各自要的那一档（改这儿就要重跑 build_outro_master.py）
    assert fps >= 60, f"母版只有 {fps}fps，而剪辑片有 60fps 的源片——插帧会顿"
    assert rate >= 48000, f"母版只有 {rate}Hz，而采访片要 48000——升采样补不出信息"


def test_文案块的位置不跟着比分板漂(monkeypatch: pytest.MonkeyPatch):
    """`.storycopy` **锚在一个常量上**，不再整块垂直居中。

    居中的时候文案块的 y 是「(画布 − 整块高) ÷ 2」，也就是**内容一变它就动**。
    量已发的三张海报（当时量的是台头药丸的顶边）：

        eala-parks    502   老版一行赛果（≈56px）
        shang-rublev  536   同上，钩子字号不同
        zhang-sabalenka 410 换上新版比分板（≈295px）—— 被顶上去 92~126px

    账号所有者 2026-08-07：「比分板和标题都往下移动一点，『赛场之上』的标签
    还是按原来模板的位置，然后再跟标题文案和比分板」。

    ⚠️ **2026-08-14 换了主语**：账号所有者「把赛场之上那个黄色的药丸整体移除」，
    `.storycopy` 的第一个孩子从药丸变成了 `.storytitle`。这条判据原来叫
    `test_台头药丸的位置不跟着比分板漂`——**主语没了就得换判据，留着它就是
    一条常年红**。它守的行为一个字没变：换掉比分板，文案块不许跟着漂。

    ⚠️ **判据不是「CSS 里写了个数」，是「换掉比分板整块不动」**——所以这儿
    拿同一条 cover 生成三份 CSS（两盘 / 三盘 / 根本没有比分板），
    `.storycopy` 那条规则必须**逐字节相同**。渲染要 Chromium，CI 上没有，
    但这一条不用渲：文案块的 y 完全由这条规则决定。
    （本地真渲过：删药丸前后，标题墨迹的顶边都是 y=759。）
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "1:16")
    base = {
        "eyebrow": "赛场之上", "layout": "solo", "subject": "张帅",
        "hook": "三十七岁，一个非受迫失误\n世界第一双误四个，却赢了",
        "winner": "萨巴伦卡", "result": "6-3 6-4",
        "scoreboard": {"court": "Centre Court", "duration_source": {"url": "fixture"}},
        "matchup": [{"name": "萨巴伦卡", "country": "BLR", "rank": 1},
                    {"name": "张帅", "country": "CHN", "rank": 62}],
        "portrait": {"image": "assets/logo/brand/icon.png"},
    }

    def storycopy(cover: dict) -> str:
        _, css = vp._solo_body(cover)
        hit = re.search(r"\.storycopy\{[^}]*\}", css)
        assert hit, f"生成的 CSS 里找不到 .storycopy：{css[:300]}"
        return hit.group(0)

    two = storycopy(base)
    three = storycopy({**base, "result": "6-3 4-6 6-4"})
    none = storycopy({k: v for k, v in base.items()
                      if k not in ("result", "scoreboard")})
    assert two == three == none, (
        "比分板变了 `.storycopy` 也跟着变——文案块会重新跟着内容漂：\n"
        f"  两盘 {two}\n  三盘 {three}\n  无板 {none}")

    assert f"top:{vp.STORYCOPY_TOP}px" in two, f"文案块没有钉在常量上：{two}"
    assert "transform:none" in two, f"还留着位移，文案块位置就不是这个数：{two}"
    assert "top:50%" not in two and "translateY(-50%)" not in two, (
        f"退回整块居中了——比分板一变高就会把文案块顶上去：{two}")

    # 老版一行赛果时药丸落在 502~536；2026-08-09 账号所有者要求药丸也跟着
    # 标题/比分板一起往下移，STORYCOPY_TOP 从 520 改成 580——**这条上限本身
    # 就是那次改动要推翻的旧前提**，别拿旧区间去卡新值。
    # 2026-08-14 药丸整块删掉之后这个常量又换了主语（量的从药丸顶边变成标题
    # 顶边），610→750 是把药丸原来占的那一截折进锚点、好让标题一个像素不动，
    # **不是又往下移了一次**。
    #
    # ⚠️ **下限跟着从 490 抬到 700，这一条是有意收紧的**：药丸时代的三个值
    # （520 / 580 / 610）量的都是药丸顶边，现在粘回任何一个，标题就会**整块
    # 上移约 140px**——而账号所有者为「文案再往下一点、别遮住主体」反馈过四次
    # （08-07/08-08/08-09/08-12）。反向验证时把它退回 610，旧的宽安全带
    # （490~800）一声不吭地放行了，所以这个下限是**那次反向验证补上的**。
    assert 700 <= vp.STORYCOPY_TOP <= 800, (
        f"STORYCOPY_TOP={vp.STORYCOPY_TOP} 超出合理范围（700~800）。"
        "低于 700 多半是粘回了药丸时代的值（520/580/610）——那三个数量的是"
        "药丸顶边，现在这个常量量的是标题顶边，直接用会让文案整块上移 140px。")

    # 最坏情况要装得下：钩子 ＋ 间距 34 ＋ 比分板（板头 76 ＋ 网格 214）。
    # 溢出的话下面那截会被切在画布外。
    # ⚠️ 药丸那两项（64 ＋ gap 34 ＋ 额外间距 40 = 138）从这笔账里拿掉了，
    # 同时 STORYCOPY_TOP 加了 140——**加法的两边一起改，总数才不动**：
    # 改前 610+819=1429，改后 750+679=1429，余量仍是 11px。
    #
    # ⚠️ **2026-08-31 账号所有者第五次要求「标题往下再挪一点」（750→790），
    # 而这笔账的分子跟着换了主语：从「三行 96px」换成「两行 124px」。**
    # 换得动的唯一理由是**行数现在有闸了**（`SOLO_HOOK_MAX_LINES`，零豁免，
    # 装在 `build_match_reel._hook_lines_fit_the_title`）——在那之前 3 行只是
    # 「没人写过」，不是「写不出来」。所以这两行断言是一对，缺哪一头都不行：
    # 只留下面那条，有人加一行钩子就静默溢出；只留上面那条，常量往下挪就没有
    # 上限了。
    #
    # ⚠️ **2026-08-31 同一天晚些时候，分子又小了一档**：账号所有者「〔封面
    # 钩子〕高度再小 20%」，钩子的字号从「行越短字越大（≤2 行封顶 124）」收成
    # 一个数 `HOOK_TITLE_PX = 94`。这笔账因此从 308px 掉到 233px，余量一下子
    # 宽出 75px——**但 `STORYCOPY_TOP` 没跟着往下挪**，那是另一件事，
    # 见它上面那段注释里 08-31 那一条。
    assert vp.SOLO_HOOK_MAX_LINES == 2, (
        "solo 钩子的行数上限变了，下面这笔『装不装得下』的账要跟着重算——"
        f"它现在按两行 {vp.HOOK_TITLE_PX}px 算。")
    worst = round(2 * vp.HOOK_TITLE_PX * 1.24) + 34 + (76 + 214)
    assert vp.STORYCOPY_TOP + worst <= 1440, (
        f"最坏情况排到 {vp.STORYCOPY_TOP + worst}px，超出 1440 的画布")


def test_台头药丸不许自己回来():
    """账号所有者 2026-08-14：「把赛场之上那个黄色的药丸整体移除」。

    ⚠️ **栏目名没有丢**——它一直同时印在左上角那行 `网球时差 · 赛场之上` 里，
    药丸只是第二遍。所以这条判据钉两头：药丸的 markup 和 CSS 都不许回来，
    **而左上角那行必须还在**。只钉前一半的话，下一个人可以把整个台头一起删掉
    还是绿的。

    ⚠️ **两头都要在「去掉注释之后」的源码上量。** 第一版后一半写成在整份
    文件文本里找 `网球时差 · {column}`——而上面这段 docstring 自己就写着这
    七个字，于是把左上角那行整个删掉它照样绿。反向验证第二个方向当场抓到。
    「判据被自己的注释骗过去」这个仓库记过五次，这是第六次。
    """
    body = Path("tools/versus_poster.py").read_text("utf-8")
    code = re.sub(r'"""[\s\S]*?"""', "", body)   # 先剥 docstring
    code = re.sub(r"#[^\n]*", "", code)          # 再剥整行/行尾注释
    assert "kicker" not in code, (
        "台头药丸回来了（`kicker`）。账号所有者 2026-08-14 要求整块移除；"
        "栏目名在左上角那行 `网球时差 · X` 里已经有了，药丸是第二遍。")
    assert "网球时差 · {column}" in code, (
        "左上角那行栏目名被一起删掉了——药丸删得对，但栏目名不能跟着没。")


def test_赛场之上的比赛画面必须带比赛信息顶栏():
    """账号所有者 2026-08-07：「比赛视频里顶部要加上比赛信息啊」。

    ⚠️ 顶栏的机器**早就建好了**——`spec.topbar` 两行、`line2` 还必须和
    `cover.winner/result/matchup` 机械一致、`write_topbar_ass` 只盖比赛画面
    不盖封面和片尾。问题是这个字段是**可选**的：忘了写就静静地渲出一条没有
    顶栏的片子，没有任何东西出声。量下来 32 条 spec 里**只有 2 条带顶栏**
    （eala-parks / shang-darderi），而它们是整改期那两条。
    又一次「兜底出事的时候不吭声」，所以改成缺了就报错。

    豁免表只给**已经发出去的**片子（已发的不为版式重渲，微信那条消息收不回来），
    而且这条判据**自己查那张表**：名字必须真的存在、真的还没有 topbar——
    写错一个名字，豁免就成了一盏恒真的绿灯。
    """
    reel = _reel()

    def spec_of(slug: str) -> dict:
        return json.loads(
            Path(f"specs/reels/{slug}.json").read_text(encoding="utf-8"))

    # ---- 豁免表的自检：每个名字都要真的存在、且真的还没有顶栏 ----
    for slug in sorted(reel._LEGACY_NO_TOPBAR):
        path = Path(f"specs/reels/{slug}.json")
        assert path.is_file(), f"豁免表里的 {slug} 已经不存在了——名字过期就是恒真的绿灯"
        spec = spec_of(slug)
        assert spec.get("topbar") is None, (
            f"{slug} 已经补上顶栏了，把它从 _LEGACY_NO_TOPBAR 里删掉（只许减不许加）")
        assert str((spec.get("cover") or {}).get("eyebrow", "")).strip() == "赛场之上", (
            f"{slug} 不是「赛场之上」，本来就不受这条闸管，不该出现在豁免表里")

    # ---- 新写的「赛场之上」缺顶栏必须当场报错 ----
    fresh = {"slug": "全新的一条", "cover": {"eyebrow": "赛场之上", "winner": "萨巴伦卡",
                                       "result": "6-3 6-4",
                                       "matchup": [{"name": "萨巴伦卡"}, {"name": "张帅"}]}}
    with pytest.raises(reel.ReelError, match="顶栏"):
        reel._topbar_lines(fresh)
    # 报错要说出路：给出字段形状和一句能照抄的例子。
    try:
        reel._topbar_lines(fresh)
    except reel.ReelError as exc:
        text = str(exc)
    assert "line1" in text and "line2" in text and "萨巴伦卡 6-3 6-4 张帅" in text, text

    # ---- 别的栏目不受这条管（「网球有故事」讲人，「开球之前」还没打完）----
    for column in ("网球有故事", "开球之前"):
        assert reel._topbar_lines({"slug": "x", "cover": {"eyebrow": column}}) is None

    # ---- 写了就要过原来那几关：两行、非空、line2 和 cover 一致 ----
    good = {"slug": "x", "cover": {"eyebrow": "赛场之上", "winner": "萨巴伦卡",
                                   "result": "6-3 6-4",
                                   "matchup": [{"name": "萨巴伦卡"}, {"name": "张帅"}]},
            "topbar": {"line1": "WTA 1000 加拿大站 第三轮", "line2": "萨巴伦卡 6-3 6-4 张帅"}}
    assert reel._topbar_lines(good) == ("WTA 1000 加拿大站 第三轮", "萨巴伦卡 6-3 6-4 张帅")
    with pytest.raises(reel.ReelError, match="一致"):
        reel._topbar_lines({**good, "topbar": {**good["topbar"], "line2": "张帅 6-3 6-4 萨巴伦卡"}})


def test_同一届赛事顶栏的中文名要统一():
    """账号所有者 2026-08-12：「视频顶部一直显示的赛事中文名字要统一啊」。

    量了一遍——同一届赛事（National Bank Open，男单在蒙特利尔、女单在
    多伦多）的 `topbar.line1`，26 条里有 7 条各写各的：`WTA 1000 加拿大站`、
    `WTA1000国家银行公开赛`、`ATP1000加拿大公开赛`、`ATP 1000 加拿大站`——
    连"WTA1000"和"WTA 1000"这种空格都没对齐，同一场赛事在不同视频里顶栏
    印着四五种不同的名字。

    根子是每条 spec 的 `topbar.line1` 都是手打的，没有一个共用的出处——
    和"排名/比分一个数写两处必分叉"是同一个毛病，只是这次分叉的是赛事名。

    **判据不是硬编码 26 个文件名**，是自动识别"属于这一届赛事的 spec"
    （spec 全文出现 National Bank Open 相关关键词，或"多伦多"/"蒙特利尔"
    分别配上"WTA1000"/"ATP1000"），再要求同一巡回赛的 `topbar.line1`
    统一成同一个前缀——这样以后加新的这一届赛事的 spec，判据自动接管，
    不用回来给这个测试加名字；换到别的赛事（比如辛辛那提）不会被误伤，
    因为它们的正文里不会出现这些关键词。

    ⚠️ 2026-08-14 补的一处：上面那句"正文里不会出现这些关键词"是这条测试
    自己的假设，`landaluce-draper`（辛辛那提 ATP1000）第一次把它证伪——
    `human_context.facts` 里合理提到了德雷珀"蒙特利尔外卡首轮出局"（他本赛季
    另一站的伤病史，和这条片子讲的辛辛那提无关），blob 扫描是**整份 spec**，
    于是"蒙特利尔"+这条片子自己的"ATP1000"（辛辛那提也是 1000 级）撞在一起，
    把一条辛辛那提的 spec 误判成"属于国家银行公开赛"。**背景事实提一句别的
    赛事，不等于这条片子在讲那个赛事**——和"贴近比赛事实"那节里"只查会发出去
    的字段"是同一个教训，只是这次连"发出去"的 push.lead 也会踩中（合理引用
    别的赛事作背景），所以不是排除 `_` 开头字段就够，而是要排除"背景事实"这几个
    容器本身：`_facts`（顶层注解）、`editorial.human_context`（facts/sources
    本来就是给这场比赛找上下文用的，会引别的赛事）、`push`（微信正文，同样会
    引背景）。真正描述"这条片子在讲哪一站"的字段留着：`topbar`、
    `editorial.question/thesis/beats`、`cover`、`segments` 的旁白——这些字段
    没有理由点别的赛事的名字，除非这条片子真的是那一届赛事的。
    """
    reel = _reel()
    canonical = {"WTA": "WTA1000 多伦多", "ATP": "ATP1000 蒙特利尔"}
    keywords = ("National Bank Open", "国家银行公开赛", "加拿大公开赛", "Rogers Cup")

    def _outward_blob(spec: dict) -> str:
        outward = {
            "topbar": spec.get("topbar"),
            "cover": {k: v for k, v in (spec.get("cover") or {}).items()
                      if not str(k).startswith("_")},
            "editorial": {k: v for k, v in (spec.get("editorial") or {}).items()
                          if k in ("question", "thesis", "beats")},
            "segments": [{"narration": s.get("narration", "")}
                         for s in spec.get("segments") or []],
        }
        return json.dumps(outward, ensure_ascii=False)

    def belongs_to_this_event(blob: str, line1: str) -> bool:
        """⚠️ **只认顶栏那一行，不扫整份 spec。**

        顶栏写的就是「这条片子讲的是哪一站」；而正文里提到多伦多是常事——
        `eala-ruse` 讲的是**辛辛那提**，只是在来路那一句里说了「多伦多打进第四轮」，
        第一版按整份 blob 扫，把它判成了多伦多那一届，然后要求它把顶栏改成
        `WTA1000 多伦多`。**判据宁可窄，不可宽**：扫得太宽的判据不吭声，
        只会让下一个人把对的写法改成错的。
        """
        if any(k in line1 for k in keywords):
            return True
        return ("多伦多" in line1 and "WTA1000" in line1) or \
               ("蒙特利尔" in line1 and "ATP1000" in line1)

    checked = 0
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        line1 = (spec.get("topbar") or {}).get("line1", "")
        if not line1:
            continue
        blob = _outward_blob(spec)
        if not belongs_to_this_event(blob, line1):
            continue
        checked += 1
        tour = "WTA" if "WTA1000" in line1 else ("ATP" if "ATP1000" in line1 else None)
        assert tour, f"{path.name} 的顶栏 {line1!r} 认不出是哪个巡回赛"
        assert line1.startswith(canonical[tour]), (
            f"{path.name} 的顶栏写着 {line1!r}，"
            f"这一届赛事的{tour}赛事名要统一成 {canonical[tour]!r} 开头")
    assert checked >= 20, "一条属于这一届赛事的 spec 都没扫到，是不是关键词或路径写错了"


def test_全称断言必须认领一份能穷举的出处():
    """「零胜」「一场没赢过」「史上第一」这类话，**一个反例就倒**。

    ⚠️ 这条判据是 2026-08-07 一次真实事故换来的。`chwalinska-gibson` 说赫瓦林斯卡
    「硬地巡回赛正赛零胜」，读者在小红书评论区当场指出来，账号所有者公开更正并道歉。
    真实记录是**至少三胜**：2026-02 克鲁日那波卡正赛 6-3 6-2 胜博格丹、
    6-1 1-6 6-2 胜 7 号种子达尼洛维奇（打进八强），2024-10 梅里达正赛胜马里诺——
    其中前两场还落在片子自己划的「2025-01 至今」窗口里。

    **错法很具体**：拿「场地＋级别」的**合计数**（6 胜 4 负）去支撑一个**轮次**
    层面的断言（「那 6 场全部是资格赛」）。合计数天生分不出 Q1/Q2 和 R32/R16，
    **而轮次那一列就在同一张逐场表里**——不是查不到，是没往下看一层。

    所以闸不是「不许说」，是**说了就要认领一份能穷举的出处**（带 URL）——
    和 `mixed_fps` / `silent_source` / `rank: null` 一个形状：把「查过整张表」
    和「看了几场就下结论」分开。
    """
    reel = _reel()

    # ---- 豁免表自检：名字要真的存在，而且真的还带着那种断言 ----
    for slug in sorted(reel._LEGACY_UNSOURCED_CLAIMS):
        path = Path(f"specs/reels/{slug}.json")
        assert path.is_file(), f"豁免表里的 {slug} 不存在了——过期的名字就是恒真的绿灯"
        spec = json.loads(path.read_text(encoding="utf-8"))
        texts = reel.spec_outward_text(spec)
        assert any(reel._ABSOLUTE_CLAIM_RE.search(t) for t in texts), (
            f"{slug} 已经没有全称断言了，把它从 _LEGACY_UNSOURCED_CLAIMS 删掉（只许减不许加）")

    # ---- 存量里没被豁免的，一条都不许漏 ----
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        reel._absolute_claims_need_a_source(spec)   # 漏了就抛

    # ---- 新写的：说了不认领 → 当场报错 ----
    bad = {"slug": "全新的一条",
           "cover": {"hook": "硬地的巡回赛正赛，她零胜"}, "segments": []}
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source(bad)

    # 认领了但没给 URL —— 「查过了」三个字不算出处
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source({**bad, "_claims": {"零胜": "查过了"}})

    # ⚠️ 只给一个源不够——账号所有者 2026-08-07：「最好经过多个信息源交叉验证」。
    # 赫瓦林斯卡那次单看 tennisabstract 一个源就下了结论，第二个源（维基引 WTA
    # 官方标题）一句话就能推翻它。同一个主机名重复给两次也不算两个源。
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source({
            **bad, "_claims": {"零胜": "逐场核过 https://www.tennisabstract.com/x"}})
    with pytest.raises(reel.ReelError, match="全称断言"):
        reel._absolute_claims_need_a_source({
            **bad, "_claims": {"零胜": "https://www.tennisabstract.com/x 和 "
                                      "https://www.tennisabstract.com/y"}})

    # 认领了、给了**两个不同主机**的穷举源 → 放行
    reel._absolute_claims_need_a_source({
        **bad, "_claims": {"零胜": "逐场核过 https://www.tennisabstract.com/x ；"
                                  "维基百科生涯正文 https://en.wikipedia.org/wiki/x"}})

    # ---- 注解不算「发出去的」：`_` 开头的字段里出现这种词不该被拦 ----
    reel._absolute_claims_need_a_source({
        "slug": "只在注解里提", "segments": [],
        "cover": {"hook": "正常的一句钩子"},
        "_why": "上一版写了「零胜」，是错的，这儿记一笔"})

    # ---- 判据宁可窄：主观话不拦（机械挡不住，硬凑会被绕过）----
    reel._absolute_claims_need_a_source({
        "slug": "主观话", "segments": [],
        "cover": {"hook": "这是他今年打得最好的一场"}})


def _synthetic_cut(bg_rgb, hair_rgb, size=(100, 150), person_top=40, person_cols=(20, 80)):
    """造一张"抠图之前"（RGB，还留着背景色）和"抠图之后"（RGBA，alpha 标出人）
    的合成图，专给 `_hair_background_contrast` 用——不碰 ffmpeg/rembg。"""
    from PIL import Image  # noqa: PLC0415

    im = Image.new("RGB", size, bg_rgb)
    px = im.load()
    for y in range(person_top, size[1]):
        for x in range(person_cols[0], person_cols[1]):
            px[x, y] = hair_rgb if y < person_top + 12 else (80, 80, 80)
    cut = Image.new("RGBA", size, (0, 0, 0, 0))
    cpx = cut.load()
    for y in range(person_top, size[1]):
        for x in range(person_cols[0], person_cols[1]):
            cpx[x, y] = (255, 255, 255, 255)
    return im, cut


def test_头顶和背景撞色会报出低对比度():
    """对应黄泽林那次真实事故：白发带压白背景，发丝被 post_process_mask 一起
    切掉，人变成了光头——`pick_cover_frames.py` 的四条闸门查不到这个。

    这条判据**真造两张合成图调用函数**，不是查源码里有没有这个名字——
    「`assert "def _cut_person(" in reel` 照样绿，功能整天是坏的」是这个仓库
    自己记过的教训。
    """
    reel = _reel()
    im, cut = _synthetic_cut(bg_rgb=(250, 250, 250), hair_rgb=(245, 245, 245))
    contrast = reel._hair_background_contrast(im, cut)
    assert contrast is not None
    assert contrast < reel.HAIR_BG_CONTRAST_WARN


def test_头顶和背景反差大不报警():
    reel = _reel()
    im, cut = _synthetic_cut(bg_rgb=(250, 250, 250), hair_rgb=(15, 15, 15))
    contrast = reel._hair_background_contrast(im, cut)
    assert contrast is not None
    assert contrast >= reel.HAIR_BG_CONTRAST_WARN


def test_完全没有不透明像素返回None不抛错():
    from PIL import Image  # noqa: PLC0415

    reel = _reel()
    im = Image.new("RGB", (50, 50), (255, 255, 255))
    cut = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    assert reel._hair_background_contrast(im, cut) is None


def test_预警只印警告不阻断渲染():
    """这条只是预警，不是硬闸——`_cut_person` 里必须只 `print`，不 `raise`。

    仍然要求渲出来人眼终审（CLAUDE.md「最后一步是人打开看」），机械检查
    只是把线索提前到抠图这一步，不是替代终审。
    """
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    block = src[src.index("def _cut_person("):]
    block = block[:block.index("def ", 10)]
    assert "_hair_background_contrast(im, cut)" in block, "闸没接在抠图那一步"
    assert "HAIR_BG_CONTRAST_WARN" in block
    warn_line = block[block.index("if contrast is not None"):]
    warn_line = warn_line[:warn_line.index("\n\n")]
    assert "raise" not in warn_line, "撞色预警不许挡渲染，只能 print"
    assert "黄泽林" in warn_line, "警告文案要指出这是哪次真实事故的同类问题"


def _narrated(reel, start, end, narration):
    import dataclasses  # noqa: PLC0415

    return dataclasses.replace(_seg(reel, start, end), narration=narration)


def test_中文数字常用词不会被误判成数据句():
    """「一直」「一样」这类日常词含中文数字字符，按"有没有数字字符"判会让
    几乎每句话都命中——`_STAT_PATTERN` 只认比分/破发点/百分比这几种具体写法。"""
    reel = _reel()
    for word in ("他一直没有放弃", "两个人打法很不一样", "现场气氛热闹得不像话",
                 "第一次站上这个舞台"):
        assert not reel._STAT_PATTERN.search(word), f"「{word}」不该被判成数据句"


def test_比分和破发点等具体写法会被识别成数据句():
    reel = _reel()
    for text in ("六比四拿下首盘", "3:6", "第二个破发点", "一个盘点都没给",
                 "一发得分率百分之六十", "世界第十六"):
        assert reel._STAT_PATTERN.search(text), f"「{text}」应该被判成数据句"


def test_中段全在报数据时提示中段缺情绪停顿():
    reel = _reel()
    segs = [
        _narrated(reel, 0, 5, "开场钩子，没有数据。"),
        _narrated(reel, 5, 10, "六比三拿下首盘。"),
        _narrated(reel, 10, 15, "第二盘破发点没能兑现。"),
        _narrated(reel, 15, 20, "一发得分率只有百分之四十。"),
        _narrated(reel, 20, 25, "收尾一问，同样没有数据。"),
    ]
    hint = reel.narration_density_hint(segs)
    assert hint is not None
    assert "节奏" in hint and "不是判定" in hint


def test_中段有情绪句就不提示():
    reel = _reel()
    segs = [
        _narrated(reel, 0, 5, "开场钩子。"),
        _narrated(reel, 5, 10, "六比三拿下首盘。"),
        _narrated(reel, 10, 15, "他放下球拍，双手掩面。"),
        _narrated(reel, 15, 20, "一发得分率只有百分之四十。"),
        _narrated(reel, 20, 25, "收尾一问。"),
    ]
    assert reel.narration_density_hint(segs) is None


def test_首尾两段不算进中段密度():
    """首尾都写成数据句、中段大半不是——首尾若被误算进比例会把中段的
    "没有情绪句"这件事盖住。"""
    reel = _reel()
    segs = [
        _narrated(reel, 0, 5, "六比四。"),
        _narrated(reel, 5, 10, "他松了一口气。"),
        _narrated(reel, 10, 15, "教练席传来欢呼。"),
        _narrated(reel, 15, 20, "破发点没能兑现。"),
        _narrated(reel, 20, 25, "七比五拿下。"),
    ]
    # 中段（索引 1~3）三段里只有一段是数据句，33% < 75% 门槛——不该提示；
    # 把首尾也算进去会变成 3/5=60%，仍然不够，所以换一组更极端的边界数据
    assert reel.narration_density_hint(segs) is None

    segs_boundary = [
        _narrated(reel, 0, 5, "六比四。"),          # 首，数据句
        _narrated(reel, 5, 10, "破发点没能兑现。"),   # 中，数据句
        _narrated(reel, 10, 15, "教练席传来欢呼。"),   # 中，非数据句
        _narrated(reel, 15, 20, "又一个盘点。"),       # 中，数据句
        _narrated(reel, 20, 25, "七比五拿下。"),       # 尾，数据句
    ]
    # 只看中段（索引 1~3）：2/3 ≈ 67% < 75%，不提示；
    # 若错把首尾也算进 5 段：4/5 = 80% ≥ 75%，会误报——这条测试锁死"只看中段"
    assert reel.narration_density_hint(segs_boundary) is None


def test_段落太少不判断():
    reel = _reel()
    segs = [_narrated(reel, 0, 5, "六比三。"), _narrated(reel, 5, 10, "七比五。")]
    assert reel.narration_density_hint(segs) is None


def test_没有旁白的段不计入分母():
    reel = _reel()
    segs = [
        _narrated(reel, 0, 5, "开场钩子。"),
        _seg(reel, 5, 10),                          # 没有旁白（原声段之类）
        _narrated(reel, 10, 15, "六比三。"),
        _narrated(reel, 15, 20, "破发点没能兑现。"),
        _narrated(reel, 20, 25, "收尾一问。"),
    ]
    # 有旁白的只有 4 段，掐头去尾中段只剩「六比三」「破发点没能兑现」两段，
    # 全是数据句——应该提示
    hint = reel.narration_density_hint(segs)
    assert hint is not None


def test_中段情绪停顿提示只print不阻断dry_run():
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    start = src.index("density_hint = narration_density_hint(segments)")
    block = src[start:src.index("[看画面]", start)]
    assert "return" not in block, "中段情绪停顿提示不许阻断 dry-run"


def _find_point_ends():
    sys.path.insert(0, str(Path("tools").resolve()))
    import find_point_ends  # noqa: PLC0415

    return find_point_ends


def test_转折点收尾用climax_tail普通段用tail():
    """账号所有者 2026-08-08：「赢球后多给情绪一点篇幅」——`suggest_cut` 是这条
    规矩第一次变成可执行参数：`--climax` 里点名的那几个用更长的尾巴。"""
    fpe = _find_point_ends()
    ends = [10.0, 50.0]
    普通 = fpe.suggest_cut(9.8, ends, tail=1.2, climax_tail=2.2, climax_wants=set())
    转折点 = fpe.suggest_cut(49.8, ends, tail=1.2, climax_tail=2.2, climax_wants={49.8})
    assert 普通["tail"] == 1.2
    assert 普通["cut_to"] == 10.0 + 1.2
    assert 普通["climax"] is False
    assert 转折点["tail"] == 2.2
    assert 转折点["cut_to"] == 50.0 + 2.2
    assert 转折点["climax"] is True


def test_climax_tail比tail长():
    """默认值本身要体现「多给情绪一点篇幅」，不能改完还是一样长。"""
    import inspect  # noqa: PLC0415

    fpe = _find_point_ends()
    src = inspect.getsource(fpe.main)
    assert '"--climax-tail", type=float, default=2.2' in src
    assert '"--tail", type=float, default=1.2' in src
    assert 2.2 > 1.2, "climax-tail 的默认值必须比普通 tail 长"


def test_之后没有死球时返回None不是抛错():
    fpe = _find_point_ends()
    got = fpe.suggest_cut(999.0, [10.0, 20.0], tail=1.2, climax_tail=2.2, climax_wants=set())
    assert got is None


def test_climax_wants按精确值匹配不做容差():
    """转折点是人显式挑出来的 --ends 值，不该靠"差不多"去猜——传的是 49.8
    就必须精确等于 49.8，写成 49.7 不该被当成同一个点。"""
    fpe = _find_point_ends()
    got = fpe.suggest_cut(49.8, [50.0], tail=1.2, climax_tail=2.2, climax_wants={49.7})
    assert got["climax"] is False


def _vp():
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster  # noqa: PLC0415

    return versus_poster


def _title_px(vp, hook: str) -> int:
    _, css = vp._solo_body({"eyebrow": "网球有故事", "layout": "solo", "hook": hook,
                            "portrait": {"image": "assets/logo/brand/icon.png"}})
    hit = re.search(r"\.storytitle\{font-size:(\d+)px", css)
    assert hit, f"CSS 里没有 storytitle 字号：{css[:200]}"
    return int(hit.group(1))


def test_钩子的字号只有一个数不随行长变大():
    """账号所有者 2026-08-31：「〔封面钩子〕**高度再小 20%**」。

    钩子原来是「行越短字越大」：≤2 行封顶 124px、≥3 行封顶 96px，再按
    940/行长 缩。于是同一个栏目的封面一条一个大小——两字爆点 124px、
    八字 117px、十字 94px。他 2026-08-14 说的本来就是「字号**就保持这种**」
    （`townsend-osorio`，十字行 → 94px），所以这次是把那句话做到位：
    **≤10 个字一律 94px**，而 8 字那行 117×0.8 = 93.6 正好落回来，
    刚好就是他要的那 20%。

    ⚠️ 上限收了，**下限那一半原样保留**——见下一条。
    """
    vp = _vp()
    assert _title_px(vp, "赢了") == vp.HOOK_TITLE_PX == 94
    assert _title_px(vp, "两次差点丢掉一盘\n三个盘点一个没给") == 94
    # 八个字那一行按老公式是 940/8=117px，两行 1.24 行高共 290px；
    # 现在 94px 共 233px——**正好是账号所有者要的那 20%**。
    assert round(1 - (2 * 94 * 1.24) / (2 * 117 * 1.24), 3) == 0.197


def test_一行超过十个字仍然按宽度缩下去():
    """上限收成一个数之后，**别把「太长就缩」那一半也一起收掉**：
    存量 48 条长钩子的老海报靠它才排得下（`white-space:nowrap`，
    不缩就直接顶出画布），`_hook_lines_fit_the_title` 那道闸也靠
    「渲出来低于 94」认出它们。"""
    vp = _vp()
    long_line = "这是一句写得很长很长根本用不上抬高上限的钩子文案"
    assert _title_px(vp, long_line) < vp.HOOK_TITLE_PX
    assert _title_px(vp, "一" * 25) == 37


def test_封面口播和海报上印的钩子必须是同一句话():
    """2026-09-01 `osaka-four-slams-2026` 差 15 分钟就把这个错渲出去。

    账号所有者说「标题钩子写得不明不白」，我改了 `cover.hook`（**印在海报
    上那两行**），`cover.narration` 原样留着上一版——渲出来是海报印一句、
    声音念另一句，而且去标点后两者不同，封面还会再叠一条字幕说第三件事。

    ⚠️ **两处各自都合格，所以没有任何一道既有的闸比得着它们**：`hook` 那头
    有行长行数的闸，`narration` 那头有哑场和超长的闸。`--dry-run`、全量测试、
    `check_reel_landed` 一律绿。

    钉三头，缺一头都能单独变绿：

    ① **行为**——真错法（字集重合度 0.154）必须被认出来；
    ② **不许误伤**——存量那种「印出来的比念出来的少几个虚词」必须放行
       （只钉 ① 的话，把判据收成「逐字相同」照样过，而那会红掉一半存量）；
    ③ **闸真的接在 `validate_spec` 上**——只钉函数的话，函数写对了、
       没人调它，线上照样渲错（本仓库为「写了不等于跑过」栽过好几次）。
    """
    reel = _reel()
    good = {
        "slug": "x", "cover": {
            "layout": "solo",
            "hook": "这一身缝满纸片\n全是她自己的旧报道",
            "narration": "这一身缝满纸片，全是她自己的旧报道。"}}
    assert reel.cover_voice_matches_hook_problem(good) is None

    # ① 真错法：改了钩子、口播还是上一版
    bad = json.loads(json.dumps(good))
    bad["cover"]["narration"] = "嫁衣拆了做和服，旧报纸缝成长袍。"
    problem = reel.cover_voice_matches_hook_problem(bad)
    assert problem and "不是同一句话" in problem
    assert "cover.narration" in problem and "_narration_why" in problem, (
        "报错要说出路：改哪个字段、真要另说一件事怎么认领")

    # ② 不许误伤：口播比海报多几个虚词是这条线的常态
    for hook, voice in (
            ("全美第三大网球赛事\n办在一个三万多人的小镇",
             "全美第三大的网球赛事，办在一个三万多人的小镇。"),
            ("两年前，输给辛纳\n今天，他回来了",
             "两年前，他输给了辛纳。今天，他回来了。")):
        assert reel.cover_voice_matches_hook_problem(
            {"slug": "x", "cover": {
                "layout": "solo", "hook": hook, "narration": voice}}) is None, (
            f"「{voice}」只是把「{hook}」念顺了，不是另说一件事")

    # ②' 认领的出口要真的管用（本文件写着「另说一件事时它照样要有字幕」）
    claimed = json.loads(json.dumps(bad))
    claimed["cover"]["_narration_why"] = "封面这句故意另说一件事，所以它有字幕"
    assert reel.cover_voice_matches_hook_problem(claimed) is None

    # ③ 闸接在 validate_spec 上，而且排在下载源片之前（dry-run 0.2 秒就报）
    src = inspect.getsource(reel.validate_spec)
    assert "cover_voice_matches_hook_problem" in src, (
        "判据写出来了不等于有人调它")

    # 存量一条都不许红——这条闸装上是零豁免的
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        assert reel.cover_voice_matches_hook_problem(spec) is None, path


#: 比分板那几道框线共用的白色。**一个出处**：每一条 `border` 都得是它。
_BOARD_LINE = "rgba(244,251,247,"
#: 品牌绿的两种写法（描边用 hex，垫底用 rgb 三元组）。决胜盘那块绿两样都用过。
_BRAND_GREEN = ("#c6f65a", "198,246,90")


def _board_rules(vp) -> dict[str, str]:
    """从**真渲出来的 CSS** 里解出比分板那些规则：`{选择器: 声明块}`。

    ⚠️ **先剥掉 `/* */`。** 这块 CSS 的注释正是这个仓库记教训的地方，它此刻
    就写着「曾经是 8px 品牌绿描边」——连注释一起扫，「把坑记下来」会被判成
    「又踩了这个坑」（同一个形状本仓库栽过六次）。

    只收选择器里带 `.score…` 的规则：`.setwin{color:#c6f65a}` 是**盘分数字**
    的强调色，那个绿要留着，不在这条判据的射程里（`.storyscore` 同理，
    它的类名不是以 `score` 起头的）。
    """
    _, css = vp._solo_body({
        "eyebrow": "赛场之上", "layout": "solo", "hook": "赢了",
        "portrait": {"image": "assets/logo/brand/icon.png"},
        "winner": "萨巴伦卡", "result": "6-3 4-6 6-4",
        "scoreboard": {"court": "Centre Court", "duration_source": {"url": "fixture"}},
        "matchup": [{"name": "萨巴伦卡", "country": "BLR", "rank": 1},
                    {"name": "张帅", "country": "CHN", "rank": 62}],
    })
    css = re.sub(r"/\*[\s\S]*?\*/", "", css)
    rules = {}
    for hit in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector = " ".join(hit.group(1).split())
        if re.search(r"\.score[\w-]*", selector):
            rules[selector] = hit.group(2)
    return rules


def test_比分板不许给某一盘单开样式(monkeypatch):
    """账号所有者 2026-08-14：「把最后一盘比分前面的绿色竖线变成和其他框线
    一样的白色」「**以后都这样固定下来**」。

    在这之前决胜盘那一格挂 `score-set--deciding`：左边框 8px 品牌绿 + 一层
    14% 的品牌绿垫底（量过：单剩那层绿，那一格的色相从 200.6° 偏到 185.5°、
    饱和度 .379 → .257，渲两版摆一起看，读起来是「这一格脏了」不是「这一格
    重要」）。

    ⚠️ **换了主语**（2026-08-29）：账号所有者指着一张美网官方赛果图定了新版式
    ——两行、赢家那一行整条高亮、**没有格子也没有框线**。原来这条判据钉的是
    「每一格的竖线都一样」，而竖线整块不存在了，判据得跟着换。它守的东西一个
    字没变：**每一盘一视同仁，不许给某一盘单开一套颜色。**

    判据钉四头，四个方向分别反向验证过：

    1. **markup**：每一盘在两行里各一个格子，class 只有 `setwin`/`setlose`
       两种，谁都不多一个类
    2. **CSS 不许点名某一盘**：`nth-child` / `--deciding` / `:last-child`
       这类选择器一出现就红——这一条不认类名，换个名字把绿线加回来照样拦得住
    3. **框线整块没有了**：`.score…` 的任何一条规则都不许再声明 `border*`。
       新版式靠「哪一行亮着」分主次，不靠格子；再画一道框线就是把旧表格搬回来
    4. **板上一点绿都不许有**。⚠️ 这一头 2026-08-29 一天里换过**三次**主语，
       记全了才看得懂它现在拦什么：
         ① 第一版端帽是品牌绿 → 判据写「绿只许在 `.score-cap` 上」
         ② 「完整复刻、不要自己配色」→ 端帽改成量来的 `#739365`，品牌绿
            一处不剩 → 判据改成「板上不许有品牌绿」
         ③ 「可以不要获胜方两边的绿色边条」「不要两边的绿色竖条了」（一条
            消息里说了两遍）→ **端帽整块拿掉**，`.score-cap` 这个选择器都
            没有了 → 判据现在拦的是「有人看着参考图又把绿加回来」，
            品牌绿和端帽那个绿**两个都拦**。
       ⚠️ 盘分数字的绿在裸的 `.setwin` 上，那条规则的选择器不带 `.score`，
       本来就不在 `_board_rules` 的射程里（顶栏和数据图那两条视频路径上的
       品牌绿一个字没动，见 CLAUDE.md）。
    """
    vp = _vp()
    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "1:16")
    cover = {
        "winner": "萨巴伦卡", "result": "6-3 4-6 6-4",
        "scoreboard": {"court": "Centre Court", "duration_source": {"url": "fixture"}},
        "matchup": [{"name": "萨巴伦卡", "country": "BLR", "rank": 1},
                    {"name": "张帅", "country": "CHN", "rank": 62}],
    }

    # ① 三盘 × 两行 → 六个格子，class 只有两种，一个字都不许多
    html_out = vp._scoreboard_html(cover)
    cells = re.findall(r'<span class="(score-number[^"]*)"', html_out)
    assert sorted(cells) == sorted(["score-number setwin"] * 3
                                   + ["score-number setlose"] * 3), (
        f"每一盘在两行里各一个格子、class 只有输赢两种，解出来却是 {cells}：\n{html_out}")

    rules = _board_rules(vp)
    # 判据自己的判据：主语还在（选择器改名或者 CSS 拿不到时，下面几条会变成
    # 恒真的绿灯，而那和"守住了"长得一模一样）
    assert ".score-number" in rules, f"比分板的 CSS 没解出来，解到的是：{sorted(rules)}"
    assert ".score-fill" in rules, f"长条那条规则没解出来：{sorted(rules)}"
    # ⚠️ 端帽整块拿掉了（2026-08-29），markup 和 CSS 里都不许再有
    assert "score-cap" not in html_out and not any(
        "score-cap" in sel for sel in rules), (
        "端帽又回来了：账号所有者 2026-08-29 说了两遍「不要两边的绿色竖条」。\n"
        "⚠️ 别为了「让两行左边缘对齐」把隐形端帽加回来当占位——两行都没有，"
        "对齐自然成立。")

    for selector, decls in rules.items():
        # ② 选择器不许点名某一盘
        for singled in (":nth-child", ":nth-of-type", ":last-child", ":first-child",
                        "--deciding"):
            assert singled not in selector, (
                f"`{selector}` 点名了某一盘：账号所有者要的是每一盘一视同仁，"
                "别再给决胜盘单开一套样式。")
        for decl in decls.split(";"):
            if ":" not in decl:
                continue
            prop, value = (part.strip() for part in decl.split(":", 1))
            # ③ 框线：`border-radius`（端帽的圆角）和 `box-sizing` 不算
            assert prop not in {"border", "border-top", "border-right",
                                "border-bottom", "border-left"}, (
                f"`{selector}` 又画了一道框线（{prop}:{value}）。\n"
                "2026-08-29 起比分板没有格子也没有框线——主次靠"
                "「哪一行亮着」，不靠画格子。")
        # ④ 板上一点绿都不许有：品牌绿，和参考图那两颗端帽的浅绿
        for green in (*_BRAND_GREEN, "#739365"):
            if green in decls.lower():
                assert False, (
                    f"`{selector}` 里出现了品牌绿 {green}：{decls.strip()!r}\n"
                    "2026-08-29 起这块板上一点绿都没有——端帽拿掉了，"
                    "配色照参考图量的那三个值。别看着参考图又把它加回来，"
                    "也别给某一盘的格子单独上色。")


def test_顶栏比分逐盘上色赢盘绿输盘灰():
    """和比分板同一套判据——那一盘里谁的局数大，不是谁赢了整场。"""
    reel = _reel()
    # 萨巴伦卡赢下整场；result "6-3 4-6 6-4" 是赢家视角：第二盘她输了（4<6）
    line = reel.colorize_topbar_score("萨巴伦卡 6-3 4-6 6-4 张帅")
    # 赢家名字挂高亮（2026-08-15 起），输家名字仍然一个标签都不沾
    assert line.startswith(f"{reel.TOPBAR_WINNER_ASS}萨巴伦卡")
    assert line.endswith(" 张帅")
    # 第一盘 6-3：赢家那一盘也赢了，左边（6）应该是 setwin 色并**加粗**；
    # 连字符压暗（和比分板 `.setdash` 同一个理由）而且**不许跟着粗**，
    # 整盘结束才复位。
    #
    # ⚠️ **按顺序断言，不比一整串。** 2026-08-29 加了「赢的那一盘加粗」之后，
    # 颜色标签之间插进了 `\b1`/`\b0`——原来那种「一整串逐字相同」的写法会因为
    # 中间多了一对粗体标签而红，而它守的东西（**哪个数字上哪个色**）一个字
    # 没变。判据改成钉相对顺序，粗体单独钉一条。
    def order(*tags: str) -> bool:
        pos = -1
        for tag in tags:
            pos = line.find(tag, pos + 1)
            if pos < 0:
                return False
        return True

    assert order(f"{reel.TOPBAR_SCORE_BOLD_ASS}{reel.TOPBAR_SETWIN_ASS}6",
                 reel.TOPBAR_SCORE_PLAIN_ASS,
                 f"{reel.TOPBAR_SETDASH_ASS}-",
                 f"{reel.TOPBAR_SCORE_LIGHT_ASS}{reel.TOPBAR_SETLOSE_ASS}3"), (
        f"第一盘 6-3：6 加粗、3 走 Light、连字符压暗且走常规档\n{line}")
    # 第二盘 4-6：赢家那一盘输了，左边（4）应该是 setlose 色、走 Light
    assert order(f"{reel.TOPBAR_SCORE_LIGHT_ASS}{reel.TOPBAR_SETLOSE_ASS}4",
                 reel.TOPBAR_SCORE_PLAIN_ASS,
                 f"{reel.TOPBAR_SETDASH_ASS}-",
                 f"{reel.TOPBAR_SCORE_BOLD_ASS}{reel.TOPBAR_SETWIN_ASS}6"), (
        f"第二盘 4-6：赢的是右边那个 6，加粗的也该是它；连字符不许跟着细\n{line}")
    # 粗体一定要关掉：不关的话后面输家的名字会跟着变粗，看起来像"输家也高亮了"
    assert line.rstrip().endswith("张帅") and reel.TOPBAR_SCORE_BOLD_ASS not in \
        line[line.rfind(reel.TOPBAR_SCORE_FONT_RESET_ASS):], (
        f"最后一次复位之后还留着粗体标签，输家名字会跟着变粗\n{line}")


def test_顶栏上色带抢七小分():
    """⚠️ 抢七小分：**裸数字、印在大分的右上角**（账号所有者 2026-08-31 连着
    三句：「不要带()」→「小分不带括号」→「小分在大分的右上角」）。

    ASS 没有行内上标标签——`\\fs` 小字坐在基线上是右**下**角——所以「小而高」
    做进了 `TL Score` 的字形本身（`build_fonts.add_superscript_digits` 合成的
    上标码位），顶栏写 `⁵` 这个字符就行。字形几何由
    `test_TLScore的上标数字真的又小又高` 单独钉；这条钉的是 colorize 那一头：

    - 不带括号、不留基线上的裸数字（「7-65」那种）
    - 两个方向都走**常规档**（`TOPBAR_SCORE_PLAIN_ASS`）——它是附注不是比分，
      跟着前一个数字走粗/走细都会被读成「这一盘是赢的/输的」
    - 上标必须在 `TOPBAR_SCORE_FONT_RESET_ASS`（切回正文字体）**之前**：
      正文字体（Noto Sans CJK SC）没有这些码位，切出去就是 fontconfig
      随便回退一支，样子悄悄换掉
    """
    reel = _reel()

    for raw, who in (("甲 7-6(5) 甲 乙", "左边"), ("甲 6-7(5) 甲 乙", "右边")):
        line = reel.colorize_topbar_score(raw)
        assert "(" not in line, (
            f"顶栏的抢七小分还带着括号：{line}\n"
            "账号所有者 2026-08-31：「小分不带括号」——用字体里的上标码位。")
        want = f"{reel.TOPBAR_SCORE_PLAIN_ASS}⁵"
        assert want in line, (
            f"{who}赢的那一盘，小分没走「常规档＋上标码位」：{line}\n"
            "小分是注脚：常规字重、写 `SUP_DIGITS` 映射出的上标字符——"
            "写裸的 5 它就掉回基线（右下角），跟着数字的字重走会被读成输赢。")
        assert line.index("⁵") < line.index(reel.TOPBAR_SCORE_FONT_RESET_ASS), (
            f"上标排在切回正文字体之后了：{line}\n"
            "正文字体没有上标码位，libass 会 fontconfig 回退到别的字体。")


def test_顶栏上色不会把人名当成比分():
    reel = _reel()
    # 人名里没有 "数字-数字" 这个形状，_SET_RE 匹配不上，不会被当成一盘比分
    line = reel.colorize_topbar_score("萨巴伦卡 6-3 张帅")
    # **输家的名字一个标签都不沾**地穿过去
    assert line.endswith(" 张帅"), \
        f"输家名字被套上标签了——_SET_RE 不该匹配人名：{line}"
    # 赢家的名字整块高亮，而且是**当成名字**高亮的，不是被拆成"比分"上色：
    # 名字和它的高亮标签之间不许插进 setdash（那是比分里连字符的颜色）
    assert line.startswith(f"{reel.TOPBAR_WINNER_ASS}萨巴伦卡{reel.TOPBAR_RESET_ASS}"), \
        f"赢家名字没有整块高亮：{line}"
    assert reel.TOPBAR_SETDASH_ASS not in line.split(" ")[0], \
        f"名字被按比分拆开上色了：{line}"


def test_顶栏赢家名字整块高亮而且没有比分就不涂():
    """账号所有者 2026-08-15：「赢球的球员名字要高亮出来」。

    两头都要钉：

    1. **名字里有空格也整块高亮。** `split(" ")[0]` 会把带空格的译名劈成两半，
       高亮半个名字比不高亮更难看——**而且不报错**。
    2. **一盘比分都没有就一个字都不涂。** 那时"开头那一串非比分 token"正好是
       整行，照着涂就是把整行刷绿，同样不报错。
    """
    reel = _reel()
    win = reel.TOPBAR_WINNER_ASS

    two = reel.colorize_topbar_score("大 威廉姆斯 6-3 6-4 阿朗戈")
    assert two.startswith(f"{win}大 威廉姆斯{reel.TOPBAR_RESET_ASS}"), \
        f"带空格的名字没有整块高亮：{two}"

    for plain in ("完全没有比分的一行", "退赛", "甲 乙"):
        assert reel.colorize_topbar_score(plain) == plain, \
            f"这一行里一盘比分都没有，不该涂任何颜色：{plain}"


def test_顶栏赢家色跟着赛后开麦走():
    """赢家名字和赢盘的颜色，2026-08-18 起不再跟着比分板的 CSS 走。

    账号所有者拿"赛场之上"和"赛后开麦"两条线的顶栏截图对比，要求"赢的人的
    颜色、赢一盘的颜色都改成和赛后开麦一样"。在这之前这条测试（当时叫
    `test_顶栏配色跟着比分板走`）从 `versus_poster.py` 的 `.setwin` CSS 里
    现抠现折算——那条路径现在已经不成立了：两条线的颜色出处本来就是各自
    独立起的（一条接封面比分板的品牌绿，一条另起一支青绿），这次是显式
    指定"以赛后开麦为准"，不是"发现两边本该一致却漂了"。

    ⚠️ **这条必须从 `build_interview_clip._MARK_COLOUR` 里现抠，不能写死
    hex。** 写死的判据只能防"有人把它删了"，防不住"赛后开麦那边又改了、
    这边没跟着"——而这正是上一版栽过的那个坑，只是换了个出处。
    """
    reel = _reel()
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_interview_clip  # noqa: PLC0415

    # `_MARK_COLOUR` 是内联标签的内容（`\c&H8CDC4A&`），不带外层花括号——
    # 补齐花括号才是一个完整的 ASS 覆盖标签，和 `TOPBAR_SETWIN_ASS` 同一种形状。
    mark = "{" + build_interview_clip._MARK_COLOUR + "}"
    assert reel.TOPBAR_SETWIN_ASS == mark
    assert reel.TOPBAR_WINNER_ASS == mark

    # 连字符和输盘这次没有改动范围，仍然跟着比分板的口径走
    css = Path("tools/versus_poster.py").read_text(encoding="utf-8")

    def poster_hex(cls: str) -> str:
        hit = re.search(rf"^\.{cls}\{{{{?color:(#[0-9a-fA-F]{{6}})", css, re.M)
        assert hit, f"比分板 CSS 里找不到 .{cls} 的颜色——选择器改名了？"
        return hit.group(1).lower()

    def to_ass(hexcolor: str) -> str:
        h = hexcolor.lstrip("#")
        return "{\\c&H00" + (h[4:6] + h[2:4] + h[0:2]).upper() + "&}"

    # 连字符：这次没改，仍然压暗一档
    assert reel.TOPBAR_SETDASH_ASS == to_ass(poster_hex("setdash"))

    # 输盘：比分板的口径是「用**那个表面自己的正文色**，靠色相和赢盘分开，
    # 不靠压暗」。两个表面正文色本来就不同（海报 #f4fbf7 / 顶栏 #d5e2db），
    # 所以这一条比的是**口径**不是字节：顶栏的输盘色必须等于顶栏自己的正文色。
    assert reel.TOPBAR_SETLOSE_ASS == "{\\c" + reel.TOPBAR_BODY_COLOUR + "&}"
    # 而且不许退回「压暗」那一档——`.setdash` 那个灰就是压暗档的代表
    assert reel.TOPBAR_SETLOSE_ASS != reel.TOPBAR_SETDASH_ASS, (
        "输盘又被压暗了：2026-08-09 比分板专门改掉这个（压缩视频里读不出来），"
        "顶栏是直接烧进 H.264 的，更吃这个问题")
    # 反过来也要成立：赢盘和输盘必须真的不同色，不然上色等于没上
    assert reel.TOPBAR_SETWIN_ASS != reel.TOPBAR_SETLOSE_ASS


def test_比分数字全站同一支字体而且加粗真的生效(tmp_path, monkeypatch):
    """账号所有者 2026-08-29：「比分的数字字体都用这种，**包括以后所有视频里的
    其他地方的比分都用这种字体**，赢的一盘的加粗」——指的是美网那张官方赛果图。

    **换哪一支是量出来的**，不是挑的：把参考图那个粗「6」和细「3」的墨迹二值化、
    归一到 200×200，跟手上每一支字体逐个算 IoU——

        粗 6：Noto Sans CJK SC 0.719 ｜ NotoSansSC-sub（封面那支）0.716
              ｜ Noto Sans 0.790 ｜ Barlow Condensed SemiBold 0.689
        细 3：Noto Sans CJK SC 0.640 ｜ NotoSansSC-sub 0.641
              ｜ Noto Sans 0.581 ｜ Barlow Condensed SemiBold **0.440**

    两档合起来 Noto Sans CJK SC 最好，而且**和封面那支是同一套设计**（差 0.003）
    ——顶栏和封面从此不会再是两种数字。

    ⚠️⚠️ **同一天下午又换了一次：`Noto Sans CJK SC` → `TL Score`。** 账号所有者
    「输掉那一盘的分数的数字需要再细一点，和加粗的区分开」——而系统的
    `fonts-noto-cjk` **只有 Regular 和 Bold 两档**，Light 在几百 MB 的
    `-extra` 里。所以三档做成了仓库里的小文件（`assets/fonts/TLScore-*.ttf`，
    从 `NotoSansSC[wght]` 实例化、只留 ASCII ＋ 全角括号，三个约 200 KB）。
    `TL Score` 和 `Noto Sans CJK SC` 是同一套设计，上面那张 IoU 表照旧成立；
    换来的是**浏览器和 libass 读同一批文件**，比分数字不再靠机器上装了哪个
    apt 包。

    判据钉四头：

    1. **四处比分是同一支**：封面比分板（浏览器）、视频顶栏、赛后开麦顶栏、
       数据图的分盘比分
    2. **两条视频线一个字都不许分叉**——账号所有者 2026-08-18 要求过
       「改成和赛后开麦一样」，那条约束没有被这次换字体推翻
    3. **三处的「输掉那一盘」字重是同一个数**（封面 / 顶栏 / 赛后开麦）
    4. ⚠️ **粗细必须真的分得开**，这一条**真渲两帧量墨迹**。
       `TOPBAR_WINNER_ASS` 上面那段注释记着一个真事：给中文名挂 `{\b1}` 渲出来
       是 216px → 216px，**什么都没发生**——libass 解不到那个字体的 Bold face
       时不报错也不合成。所以"写了 `\b1`"和"真的变粗了"是两件事，只有量渲染
       出来的宽度才分得开（同一条命令实测：中文名 0px，数字 +7px）。
       谁哪天把比分字体换成一支解不到 Bold（或者解不到 `\b300`）的，
       这条会当场红。
       ⚠️ 量的是**墨的量**不是宽度：Light 和 Bold 的外接框宽度只差几个像素
       （360 vs 395），而墨迹面积差一倍（2141 vs 4773）——拿宽度当判据，
       换成一支解不到 Light 的字体照样能过。
    """
    reel = _reel()
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_interview_clip as clip  # noqa: PLC0415
    import versus_poster as vp  # noqa: PLC0415

    # ① 封面比分板（浏览器那一侧）和数据图：同一个 family，赢的那一盘更粗
    monkeypatch.setattr(vp, "_fetch_match_duration", lambda source, where: "1:16")
    board = _board_rules(vp)
    hit = re.search(r"font-family:([^;]+);", board[".score-number"])
    assert hit and hit.group(1).split(",")[0].strip() == "'TL Score'", (
        f"封面比分板的数字不是 `TL Score`：{board['.score-number']!r}")
    # 排名数字也走同一支——账号所有者「排名的数字也可以用这统一的数字，
    # 这样就只用一种数字字体」
    hit = re.search(r"font-family:([^;]+);", board[".score-rank"])
    assert hit and hit.group(1).split(",")[0].strip() == "'TL Score'", (
        f"排名那几个数字不是 `TL Score`：{board['.score-rank']!r}")
    win_w = re.search(r"font-weight:(\d+)", board[".score-number.setwin"])
    lose_w = re.search(r"font-weight:(\d+)", board[".score-number.setlose"])
    assert win_w and lose_w and int(win_w.group(1)) > int(lose_w.group(1)), (
        "封面比分板上赢下那一盘的数字没有更粗："
        f"{board['.score-number.setwin']!r} / {board['.score-number.setlose']!r}")
    # ⚠️ 这一条要把 `font-family` **整条抠出来比第一项**，不能拿子串 `in`：
    #    `'TL Numeral','TL Sans SC',sans-serif` 里就含着 `'TL Sans SC',sans-serif`，
    #    退回 Montserrat 照样能过——反向验证时当场抓到它是恒真的。
    card = Path("tools/render_stat_card.py").read_text("utf-8")
    hit = re.search(r"\.h2h-set-row\{\{font-family:([^;]+);", card)
    assert hit, "数据图里找不到 `.h2h-set-row` 的 font-family——选择器改名了？"
    first = hit.group(1).split(",")[0].strip()
    assert first == "'TL Score'", (
        f"数据图那一列分盘比分的第一支字体是 {first}，不是 'TL Score'："
        "比分数字全站要同一支")

    # ② 两条视频线共用同一支（2026-08-18 定的，这次换字体不推翻它）
    assert clip._ASS_NAME["num"] == reel.TOPBAR_SCORE_FONT, (
        f"赛后开麦的比分字体是 {clip._ASS_NAME['num']!r}，"
        f"而这条线是 {reel.TOPBAR_SCORE_FONT!r}——两条线分叉了")

    # ③ 「输掉那一盘」的字重，三处必须是同一个数。写三处必分叉，而分叉的
    #    样子是「同一个账号出去的比分，封面和成片粗细不一样」。
    weights = {"封面比分板": vp.SCORE_LOSE_WEIGHT,
               "视频顶栏": reel.TOPBAR_SCORE_LOSE_WEIGHT,
               "赛后开麦": clip._SCORE_LOSE_WEIGHT}
    assert len(set(weights.values())) == 1, f"输掉那一盘的字重分叉了：{weights}"
    assert vp.SCORE_LOSE_WEIGHT < vp.SCORE_WIN_WEIGHT, (
        f"输掉那一盘的字重 {vp.SCORE_LOSE_WEIGHT} 不比赢的 "
        f"{vp.SCORE_WIN_WEIGHT} 细——账号所有者要的是「再细一点，和加粗的区分开」")

    # ③ 加粗真的生效：真渲一帧量墨迹宽度
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    np = pytest.importorskip("numpy")
    pil = pytest.importorskip("PIL.Image")
    fonts = Path("assets/fonts").resolve()

    def ink(tag: str) -> tuple[int, int]:
        """渲一帧，返回（墨迹像素数，外接框宽度）。"""
        head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 200\n"
                "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, "
                "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
                "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
                "Alignment, MarginL, MarginR, MarginV, Encoding\n"
                f"Style: T,{reel.TOPBAR_SCORE_FONT},{reel.TOPBAR_SCORE_SIZE},"
                "&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,"
                "10,10,10,1\n[Events]\nFormat: Layer, Start, End, Style, Name, "
                "MarginL, MarginR, MarginV, Effect, Text\n")
        stem = tag.strip("{}").replace("\\", "")
        ass = tmp_path / f"n{stem}.ass"
        ass.write_text(head + "Dialogue: 0,0:00:00.00,0:00:02.00,T,,0,0,0,,"
                       f"{tag}6 3 6 4 6 0\n", "utf-8")
        png = tmp_path / f"n{stem}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "color=c=black:s=1080x200:d=1",
                        "-vf", f"subtitles={ass}:fontsdir={fonts}",
                        "-frames:v", "1", str(png)], check=True)
        a = np.asarray(pil.open(png).convert("L"))
        xs = np.where(a.max(axis=0) > 120)[0]
        assert xs.size, "一个数字都没渲出来"
        return int((a > 120).sum()), int(xs[-1] - xs[0] + 1)

    light_ink, _ = ink(reel.TOPBAR_SCORE_LIGHT_ASS)
    plain_ink, _ = ink(reel.TOPBAR_SCORE_PLAIN_ASS)
    bold_ink, _ = ink(reel.TOPBAR_SCORE_BOLD_ASS)
    # 参考图量出来「粗/细」的墨迹比是 2.14；我们原来 Regular vs Bold 只有 1.5，
    # 换成 Light vs Bold 之后实测 2.2。留 1.8 当地板：够分得开，又不至于
    # 一换字体就红。
    assert bold_ink / light_ink >= 1.8, (
        f"`{reel.TOPBAR_SCORE_BOLD_ASS}` 的墨 {bold_ink} ÷ "
        f"`{reel.TOPBAR_SCORE_LIGHT_ASS}` 的墨 {light_ink} = "
        f"{bold_ink / light_ink:.2f}，**粗细没分开**。\n"
        f"libass 解不到 {reel.TOPBAR_SCORE_FONT!r} 的 Bold / Light 那一档时"
        "既不报错也不合成，写上去只会得到一个「看起来做了、其实没做」的粗细。\n"
        "换比分字体之前先跑这条判据。")
    assert light_ink < plain_ink < bold_ink, (
        f"三档字重没有各就各位：Light {light_ink} / 常规 {plain_ink} / "
        f"Bold {bold_ink}。连字符和抢七小分走的是中间那一档，"
        "它塌到任何一头都会被读成「这一盘赢了/输了」。")


def test_TLScore的上标数字真的又小又高():
    """⭐ 账号所有者 2026-08-31：「**小分在大分的右上角**」。

    ASS 没有行内上标标签，`\\fs` 小字坐在基线上是右**下**角——所以「小而高」
    做进了 `TL Score` 的字形本身（`build_fonts.add_superscript_digits` 把 0-9
    缩到 0.65、抬到顶对齐，落在 Unicode 标准的上标码位上）。

    这条判据量的是**仓库里那三份 TTF**，不是生成它们的代码：
    - 三档字重都要有全部十个码位——libass 碰到缺字会走 fontconfig 回退到
      随便哪支有这个码位的字体（DejaVu 就有 ⁵），**不报错、只是样子悄悄换**；
      `\\b300`/`\\b1` 挑到别的字重时同理，所以三份都得查
    - 上标要**小**（墨高 ≤ 0.75 × 数字）而且**高**（顶和数字的顶对齐、
      底离开基线）——缺了字形时 `.notdef` 是个全高的框，高度那一头会当场红
    - 两条视频线的映射表必须是同一张（写两处必分叉，而这张表连排会写错：
      1/2/3 在 Latin-1 区不在 207x 区）
    """
    np = pytest.importorskip("numpy")
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415
    reel = _reel()
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_interview_clip as clip  # noqa: PLC0415

    assert clip._SUP_DIGITS == reel.SUP_DIGITS, "两条视频线的上标映射分叉了"
    sup_chars = "0123456789".translate(reel.SUP_DIGITS)
    assert sup_chars == "⁰¹²³⁴⁵⁶⁷⁸⁹", (
        f"映射不是 Unicode 标准的上标码位：{sup_chars!r}")

    def ink(font, text) -> tuple[int, int, int, int]:
        im = Image.new("L", (400, 240), 0)
        ImageDraw.Draw(im).text((30, 60), text, font=font, fill=255)
        a = np.asarray(im)
        ys, xs = np.where(a > 100)
        assert ys.size, f"{text!r} 一点墨都没有——字体里根本没有这个字形？"
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

    for weight in ("Regular", "Bold", "Light"):
        font = ImageFont.truetype(f"assets/fonts/TLScore-{weight}.ttf", 100)
        _, by0, _, by1 = ink(font, "8")
        base_h = by1 - by0
        for ch in sup_chars:
            _, sy0, _, sy1 = ink(font, ch)
            assert sy1 - sy0 <= base_h * 0.75, (
                f"[{weight}] {ch!r} 的墨高 {sy1 - sy0} 不比数字（{base_h}）小"
                "——多半是缺字渲成了 .notdef 的全高框，或者合成时没缩")
            assert abs(sy0 - by0) <= base_h * 0.08, (
                f"[{weight}] {ch!r} 的顶（{sy0}）没和数字的顶（{by0}）对齐"
                "——上标要顶对齐才是「右上角」")
            assert sy1 < by1 - base_h * 0.2, (
                f"[{weight}] {ch!r} 的底（{sy1}）贴着基线（{by1}）"
                "——没抬起来就是右下角，正是这条要防的")


def test_顶栏比分数字切到赛后开麦同一支字体():
    """比分数字（连字符也算）要切到 `TOPBAR_SCORE_FONT`，切完还要切回来。

    ⚠️ **切回去的必须是字体和字号两样都复位，不能只复位字体。** Barlow
    Condensed 是窄身，`TOPBAR_SCORE_SIZE`（44）比正文的 `TOPBAR_BODY_SIZE`
    （38）大一档——只切字体不切字号，比分数字之后紧跟的输家名字会被
    Barlow 的字号"续"下去，读起来像输家名字也放大了。
    """
    reel = _reel()
    out = reel.colorize_topbar_score("莱巴金娜 6-4 7-6(4) 弗雷赫")

    fn_switch = rf"\fn{reel.TOPBAR_SCORE_FONT}\fs{reel.TOPBAR_SCORE_SIZE}"
    fn_reset = rf"\fn{reel.TOPBAR_BODY_FONT}\fs{reel.TOPBAR_BODY_SIZE}"
    assert out.count(fn_switch) == 2, "两个 set 各自的比分数字都要切一次字体"
    assert out.count(fn_reset) == 2, "每次切完都要切回正文字体/字号，一次都不能漏"
    # 连字符必须落在"切字体"和"切回来"之间——"6-4"整体切字体，不是数字切、
    # 连字符漏在外面
    switch_pos = out.find(fn_switch)
    dash_pos = out.find("-", switch_pos)
    reset_pos = out.find(fn_reset, switch_pos)
    assert switch_pos < dash_pos < reset_pos, "连字符必须落在切字体和切回来之间"


def test_关键分脉冲相对事件起点转毫秒():
    reel = _reel()
    tags = reel._topbar_pulse_tags([50.0], start=10.0, end=200.0)
    # 50s 相对 10s 起点是 40000ms
    assert "\\t(39800,40000,\\fscx115\\fscy115)" in tags
    assert "\\t(40000,40200,\\fscx100\\fscy100)" in tags


def test_关键分脉冲落在窗口外时丢弃并出声(capsys):
    reel = _reel()
    tags = reel._topbar_pulse_tags([5.0, 999.0], start=10.0, end=200.0)
    assert tags == ""
    assert "落在比赛画面窗口" in capsys.readouterr().out


def test_没有pulse_at时脉冲标签是空字符串():
    reel = _reel()
    assert reel._topbar_pulse_tags([], start=10.0, end=200.0) == ""


def test_write_topbar_ass不传pulse_at行为不变(tmp_path):
    reel = _reel()
    path = reel.write_topbar_ass(("赛事 轮次", "萨巴伦卡 6-3 6-4 张帅"),
                                  10.0, 200.0, tmp_path / "t.ass")
    text = path.read_text(encoding="utf-8")
    assert "\\t(" not in text, "不给 pulse_at 就不该出现任何缩放动画标签"
    assert reel.TOPBAR_SETWIN_ASS.strip("{}") in text, "比分逐盘上色是默认行为，不是可选项"


def test_write_topbar_ass给了pulse_at会写进body那一行(tmp_path):
    reel = _reel()
    path = reel.write_topbar_ass(("赛事 轮次", "萨巴伦卡 6-3 6-4 张帅"),
                                  10.0, 200.0, tmp_path / "t.ass", pulse_at=[50.0])
    text = path.read_text(encoding="utf-8")
    assert "\\fscx115\\fscy115" in text
    # 脉冲标签必须出现在 BODY 那一行的 Dialogue 里，不能串到 HEAD 那一行
    head_line = next(ln for ln in text.splitlines() if ",HEAD,," in ln)
    body_line = next(ln for ln in text.splitlines() if ",BODY,," in ln)
    assert "\\fscx115" not in head_line
    assert "\\fscx115" in body_line


def test_顶栏的body底色只有一个出处():
    """样式行的 PrimaryColour 和"复位"标签必须来自同一个常量。

    写两处必分叉，而分叉的样子是「复位之后颜色和这一行本来的颜色差一点点」
    ——肉眼几乎看不出来，只有把两个 hex 摆在一起才发现。
    """
    reel = _reel()
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert reel.TOPBAR_RESET_ASS == "{\\c" + reel.TOPBAR_BODY_COLOUR + "&}"
    assert "{TOPBAR_BODY_COLOUR}" in src, "样式行没有从常量取底色"
    bare = [ln for ln in src.splitlines()
            if "&H00DBE2D5" in ln and "TOPBAR_BODY_COLOUR =" not in ln]
    assert not bare, f"底色 hex 又被写死了第二处：{bare}"


def test_顶栏复位不许用r否则脉冲被清掉(tmp_path):
    """**`{\\r}` 会把同一行上还在跑的 `\\t()` 动画一起清掉。**

    CLAUDE.md 那条「同一行里换字体／颜色，每一段都要先 `\\r`」的前提是这一行
    **没有动画**；`pulse_at` 正是往同一行挂 `\\t()`。两者撞在一起时 `\\r` 赢，
    而且**不报错**——ASS 文本里 `\\fscx115` 明明白白写着。

    第一版就是这么写的，真渲出来量宽度才发现（1080×1440 黑底，
    `萨巴伦卡 6-3 4-6 6-4 张帅`，脉冲 115%）：

        不上色（没有任何复位标签）   292px → 336px   +15.1%  ← 满量程
        上色 + `{\\r}` 复位          292px → 311px   +6.5%   ← 只有名字在动
        上色 + 只复位颜色（现在）    292px → 336px   +15.1%  ← 修好了

    也就是说 `\\r` 那一版里，还在脉冲的恰好是前面那个球员名字，而**比分一动
    不动**——脉冲存在的全部理由就是让比分那一下被多看一眼，方向正好反了。

    所以这条判据**真渲两帧量宽度**，不查 ASS 文本：查文本的断言（`\\fscx115`
    在不在）对这个 bug 完全是哑的，它两版都成立。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    reel = _reel()
    # 缺 ffmpeg 要红，不许 skip——一条常年跳过的检查和常年红是同一个毛病。
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    np = pytest.importorskip("numpy")
    pil = pytest.importorskip("PIL.Image")

    line2 = "萨巴伦卡 6-3 4-6 6-4 张帅"
    ass = reel.write_topbar_ass(("WTA 1000 加拿大站 第三轮", line2),
                                 0.0, 20.0, tmp_path / "tb.ass", pulse_at=[10.0])

    def width_at(second: float) -> int:
        """渲一帧，量 BODY 那一行文字的横向跨度。"""
        png = tmp_path / f"f_{second}.png"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", "color=c=black:s=1080x1440:d=20:r=25",
             "-vf", f"subtitles={ass}",
             "-ss", str(second), "-frames:v", "1", str(png)], check=True)
        # ⚠️ 取样带从常量推，别写死行号。原来这儿是 `[80:150]`，而
        # `TOPBAR_BODY_TOP` 2026-08-15 从 92 收到了 72——写死的带子会从上边
        # 切掉第二行的头几行像素，而**它只会让量出来的宽度小一点，不会报错**。
        top = reel.TOPBAR_BODY_TOP - 2
        band = np.asarray(pil.open(png).convert("RGB"))[top:top + 80, :, :]
        cols = np.where(band.sum(axis=2) > 60)[1]
        assert cols.size, f"{second}s 这一帧 BODY 行没渲出任何字"
        return int(cols.max() - cols.min())

    base, peak = width_at(5.0), width_at(10.0)
    grew = peak / base
    want = reel.TOPBAR_PULSE_SCALE / 100
    assert grew == pytest.approx(want, abs=0.02), (
        f"脉冲峰值只放大到 {grew:.4f}，而 TOPBAR_PULSE_SCALE 要的是 {want:.2f}——"
        "多半是复位标签换回了 `{\\r}`，它会把同一行的 `\\t()` 一起清掉，"
        "于是只有比分前面那个名字在动")

    # 另一头：上色本身没被这个修法弄丢
    text = ass.read_text(encoding="utf-8")
    assert reel.TOPBAR_SETWIN_ASS in text and reel.TOPBAR_SETLOSE_ASS in text


def test_顶栏盒子要装得下两行字并且留出余量(tmp_path):
    """账号所有者 2026-08-15：「顶部比分栏高度建议再调小一些」。150 → 126。

    **收的是留白，不是字号**——量出来那 150px 里只有 101px 是字（第一行墨迹
    27~71、第二行 99~128），一半以上是留白。顶栏是全片曝光最长的元素，缩字号
    是拿可读性换高度。

    这条判据钉的不是「等于 126」，是**「还装得下」**：把一个量出来的数写死，
    下一个人想再调就只能改判据，而改判据的人不会知道 126 是怎么来的。所以它
    真渲一帧量墨迹，只要求三处留白都还在。谁把 `TOPBAR_H` 再往下调到字贴边、
    或者反过来把字号调大到撑破盒子，都会在这儿红。

    ⚠️ **必须带 `fontsdir`**，和 `topbar_filtergraph` 一样：不带的话字体解析
    看这台机器上装了什么，量出来的行高在沙箱和 CI 上不是一回事。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    reel = _reel()
    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    np = pytest.importorskip("numpy")
    pil = pytest.importorskip("PIL.Image")

    fonts = Path("assets/fonts").resolve()
    ass = reel.write_topbar_ass(("WTA1000 辛辛那提 第一轮", "王曦雨 6-0 3-0 季莫费耶娃"),
                                0.0, 2.0, tmp_path / "tb.ass")
    png = tmp_path / "tb.png"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=c=black:s={reel.VIDEO_W}x{reel.VIDEO_H}:d=1",
         "-vf", f"subtitles={ass}:fontsdir={fonts}",
         "-frames:v", "1", str(png)], check=True)

    # 逐行找墨迹，切成连续段；黑底上任何字都亮，阈值给低一点也不会误收
    rows = np.asarray(pil.open(png).convert("L"))[: reel.TOPBAR_H + 60]
    lit = np.where(rows.max(axis=1) > 40)[0]
    assert lit.size, "顶栏一个字都没渲出来"
    bands, start = [], lit[0]
    for i in range(1, lit.size):
        if lit[i] != lit[i - 1] + 1:
            bands.append((int(start), int(lit[i - 1])))
            start = lit[i]
    bands.append((int(start), int(lit[-1])))
    bands = [b for b in bands if b[1] - b[0] >= 3]

    assert len(bands) == 2, (
        f"顶栏应该正好两行字，量到 {len(bands)} 段：{bands}——"
        "多半是两行挤到一起了（行间留白被调没），或者有一行没渲出来")
    (h0, h1), (b0, b1) = bands
    top_pad, mid_gap, bottom_pad = h0, b0 - h1, reel.TOPBAR_H - b1
    where = (f"上留白 {top_pad}px、行间 {mid_gap}px、下留白 {bottom_pad}px"
             f"（盒高 {reel.TOPBAR_H}，墨迹 {bands}）")
    assert b1 < reel.TOPBAR_H, f"第二行已经戳出盒子外面了：{where}"
    # 12px 是下界不是目标：现在是 21/16/19，还留着一档余量。实测 118px 那一版
    # 是 15/16/17，看着已经是「挤」不是「紧」——所以下界压在它下面一点。
    for name, got in (("上", top_pad), ("行间", mid_gap), ("下", bottom_pad)):
        assert got >= 12, f"{name}留白只剩 {got}px，字快贴边了：{where}"


def test_赛场之上的quote段不许是赛后采访():
    """栏目是承诺：复盘回答「这场球怎么赢的」，赛后采访归赛后开麦。

    账号所有者 2026-08-10 review 当天的片子：「比赛信息很少，很难把比赛
    过程讲述清楚，却把采访放上了，采访要放到赛后开麦里啊」。中招的四条
    （rybakina-samsonova 两段、alexandrova-sabalenka / osaka-mertens /
    swiatek-kostyuk 各一段）有个共同点：quote 窗口全部落在源片 310 秒
    之后——正是 WTA 纯集锦的定长边界，尾巴上的采访被当情绪素材剪了进来，
    还挤掉了比赛过程的篇幅（rybakina 那条决胜盘一句都没讲）。

    闸：赛场之上的 quote 段必须认领 `_quote_kind`，只认两种——
    broadcast（转播解说原声，弗里茨决赛那种冠军宣告）/ ceremony
    （颁奖、夺冠时刻现场声）。赛后采访没有合法值：那是赛后开麦的素材，
    发现集锦尾巴带采访的正确动作是记成赛后开麦候选另出一条。
    已发的四条不重渲，挂 legacy 表，只许减不许加。
    """
    legacy = {"rybakina-samsonova", "alexandrova-sabalenka",
              "osaka-mertens", "swiatek-kostyuk"}
    allowed = {"broadcast", "ceremony"}
    checked = 0
    legacy_seen = set()
    for p in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(p.read_text(encoding="utf-8"))
        if (spec.get("cover") or {}).get("eyebrow") != "赛场之上":
            continue
        for i, seg in enumerate(spec.get("segments") or [], 1):
            if not seg.get("quote"):
                continue
            checked += 1
            if p.stem in legacy:
                legacy_seen.add(p.stem)
                continue
            kind = seg.get("_quote_kind")
            assert kind in allowed, (
                f"{p.name} 段{i} 的 quote 没认领 _quote_kind（broadcast/"
                f"ceremony）。赛后采访不进复盘——那是赛后开麦的素材，"
                f"另出一条；转播原声/颁奖现场声才许留，写上认领")
    # 判据自己的判据：主语没了要出声，别变成恒真的绿灯
    assert checked >= 7, f"只扫到 {checked} 个 quote 段，spec 目录是不是不对"
    # legacy 表自检：写错一个名字，豁免就成了一盏恒真的绿灯
    assert legacy_seen == legacy, (
        f"legacy 表和现实对不上：表里有而没扫到 {legacy - legacy_seen}。"
        f"哪条 spec 改掉了 quote 段就把它从表里删掉——只许减不许加")


def test_mute段的源声要压到地板但不许死寂(tmp_path):
    """`"mute": true` 的段把源声乘 MUTE_FLOOR——配乐宣传片的音乐不是现场声，
    切碎再拼会在接缝上跳，所以要压下去；**但不许压成数字静音**：第一版走
    anullsrc，旁白说完到段尾的空隙成了 -99 dB 死寂，被 check_reel_landed
    拦下（run 31622119788，门槛 SILENCE_FLOOR_DB=-60）。真切两段量响度：

    - 对照组（不写 mute）必须是响的——先证明量的东西正常情况下真的存在
    - mute 段要比对照组低至少 18 dB（真的压了）
    - 但要高于 -80 dB（不是数字死寂——那正是这次改语义要防的）
    - 字符串 `"true"` 要报错，和 `"auto": "true"` 那次同一个理由
    反向验证过：把 volume 那支拆掉 mute 段和对照组一样响（第②条红）；
    换回 anullsrc 则第③条红。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    def _ff(*args):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        *args], check=True)

    def _mean_db(path):
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect",
             "-f", "null", os.devnull], capture_output=True, text=True).stderr
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", out)
        assert m, f"量不出响度：{out[-300:]}"
        return float(m.group(1))

    src = tmp_path / "source.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25:duration=5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
        "-c:a", "aac", "-shortest", str(src))

    loud = reel.Segment(0.5, 2.5, 0.5, "", track=False)
    quiet = reel.Segment(0.5, 2.5, 0.5, "", track=False, mute=True)
    out_loud, out_quiet = tmp_path / "loud.mp4", tmp_path / "quiet.mp4"
    reel.cut_segment(src, loud, out_loud, 1920)
    reel.cut_segment(src, quiet, out_quiet, 1920)

    db_loud, db_quiet = _mean_db(out_loud), _mean_db(out_quiet)
    assert db_loud > -40, (
        f"对照组只有 {db_loud} dB——源片的声音本来就没进来，"
        "这个测试量不到它想量的东西")
    assert db_quiet < db_loud - 18, (
        f"mute 段 {db_quiet} dB，对照组 {db_loud} dB——地板音量没生效")
    assert db_quiet > -80, (
        f"mute 段量到 {db_quiet} dB——那是数字死寂，check_reel_landed 会拦"
        "（mute 的语义是压到地板，不是换成 anullsrc）")

    with pytest.raises(reel.ReelError, match="mute"):
        reel._seg_mute({"mute": "true"}, 0)


def test_conform声明的源要真的被统一到基准尺寸(tmp_path):
    """`conform: {源键: 为什么}` 是尺寸闸的唯一出路——等比放大铺满再中央裁。

    真造两条不同高度的源片跑一遍：查源码只能防「有人删了它」，防不住
    「它从来没工作过」。四头都钉：
    ① 声明过的源变成基准尺寸，之后 check_sources_match 放行
    ② 没声明的尺寸不一致照样红（闸没有被顺手放松）
    ③ 全部声明进去要报错（没有基准）
    ④ 光列名字不写原因要报错（认领要留下判据）
    ⑤ render() 里 conform 必须排在尺寸闸**前面**——①~④都是直接调函数，
      拆掉 render() 里的调用它们照样绿（反向验证时抓到的），所以位置单独钉。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    def _ff(*args):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        *args], check=True)

    wide, tall = tmp_path / "src_a.mp4", tmp_path / "src_b.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=size=960x506:rate=24:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", str(wide))       # 电影画幅
    _ff("-f", "lavfi", "-i", "testsrc2=size=960x540:rate=24:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", str(tall))       # 基准

    # ② 不声明：照样红
    with pytest.raises(reel.ReelError, match="尺寸"):
        reel.check_sources_match({"a": wide, "b": tall}, {})

    # ① 声明了：统一到基准，闸放行
    paths = {"a": wide, "b": tall}
    spec = {"conform": {"a": "电影画幅的宣传片，1.07×放大加两侧裁边对b-roll可用"}}
    reel.conform_sources(paths, spec, tmp_path)
    assert reel.probe_size(paths["a"]) == (960, 540), "conform 没把尺寸统一到基准"
    assert paths["a"] != wide, "conform 应该产出新文件，不许原地改写缓存过的源片"
    reel.check_sources_match(paths, spec)  # 不抛 = 放行

    # ③ 全声明进去：没有基准
    with pytest.raises(reel.ReelError, match="基准"):
        reel.conform_sources({"a": wide, "b": tall},
                             {"conform": {"a": "x", "b": "y"}}, tmp_path)

    # ④ 不写原因：认领不算数
    with pytest.raises(reel.ReelError, match="判据"):
        reel.conform_sources({"a": wide, "b": tall},
                             {"conform": {"a": ""}}, tmp_path)

    # ⑤ 位置：conform 排在尺寸闸前面，且真的在 render() 里被调用
    body = inspect.getsource(reel.render)
    assert "conform_sources(" in body, "render() 里没有 conform 调用——写了不等于接上了"
    assert body.index("conform_sources(") < body.index("check_sources_match("), (
        "conform 排在尺寸闸后面等于没有——闸先红，永远走不到它")


def test_整屏证据段要整屏切走而不是贴在画面上(tmp_path):
    """账号所有者 2026-08-12：「为啥要把图片贴在比赛上啊」——参照的『2发网球』
    原版证据是**整屏切走看**的，贴图（inset）只是当时管线没有这个能力的替代。
    `{"image": 路径, "seconds": N}` 段：深色底+卡片居中，整屏一段静片。

    真渲一段量出来：尺寸必须是成片画幅、时长=seconds+tail、带音轨（占位
    anullsrc，旁白在混音那步叠上去）。形状闸四头：
    ① 窗口类字段（start/source/inset…）一概报错——它没有源片窗口
    ② 没写 seconds 报错 ③ 没有 narration 报错（静图没有现场声，没旁白=死寂）
    ④ seg_seconds 对 image 段认 seconds（口径只有一个）
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    card = tmp_path / "card.png"
    im = Image.new("RGBA", (400, 260), (0, 0, 0, 0))
    for x in range(60, 340):
        for y in range(40, 220):
            im.putpixel((x, y), (200, 230, 200, 255))
    im.save(card)

    base = {"slug": "t", "sources": {"a": "http://x/v"},
            "cover": {"eyebrow": "网球有故事"}}

    def seg(**kw):
        return reel.parse_segments(
            {**base, "segments": [kw]}, {"a": tmp_path / "a.mp4"}, "a")

    # ① 窗口类字段一概不认
    with pytest.raises(reel.ReelError, match="窗口类"):
        seg(image=str(card), seconds=3.0, narration="x", start=1.0)
    # ② 没写 seconds
    with pytest.raises(reel.ReelError, match="seconds"):
        seg(image=str(card), narration="x")
    # ③ 没有旁白
    with pytest.raises(reel.ReelError, match="narration"):
        seg(image=str(card), seconds=3.0)
    # ④ 口径
    assert reel.seg_seconds({"image": str(card), "seconds": 3.25}) == 3.25

    parsed = seg(image=str(card), seconds=2.0, narration="一句旁白")[0]
    assert parsed.image and parsed.length == 2.0

    dest = tmp_path / "part.mp4"
    reel.cut_still_segment(parsed, dest, tail=0.18)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=width,height,codec_type,duration", "-of", "json", str(dest)],
        check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    kinds = {st["codec_type"] for st in info["streams"]}
    assert kinds == {"video", "audio"}, f"流不齐：{kinds}"
    v = next(st for st in info["streams"] if st["codec_type"] == "video")
    assert (v["width"], v["height"]) == (reel.VIDEO_W, reel.VIDEO_H), (
        "整屏证据段的画幅必须和成片一致，不然 concat 那步会拼不上")
    assert abs(float(v["duration"]) - 2.18) < 0.1, f"时长 {v['duration']}"


def test_证据段的地板静音要豁免但口播必须响过():
    """run 31626149097 的两层红，一次钉住：

    ① `quiet_windows` 读 `seg["end"]` 在整屏证据段上 KeyError——长度一律走
      `seg_film_seconds`，证据段不进「无解说窗口」表（它必有旁白，也没有
      源片起点可报）。
    ② 证据段的底轨是 anullsrc，旁白说完后的余量秒是**设计出来的静音**
      （同封面），当天 [25, 32, 39, 85, 91] 五秒全落在五张证据卡的口播
      间隙里，却被「数字静音」判成不合格。豁免只给证据段窗口**里面**的
      整秒；窗口外的数字静音照报——两头都在这条测试里钉住。

    反向验证（都做过）：`dead_seconds` 不传 evidence 时两个静音秒全进
    dead（豁免那支真的在起作用）；把 in_ev 恒真则窗口外那秒也被豁免、
    第二段断言红（豁免没有扩大化）。
    """
    import check_reel_landed as landed

    spec = {"segments": [
        {"start": 0.0, "end": 4.0, "narration": "有旁白"},
        {"image": "assets/x.png", "seconds": 6.0, "narration": "证据段旁白"},
        {"start": 10.0, "end": 14.0},              # 无解说的窗口段
    ]}
    cover = 2.0

    # ① 不再 KeyError，而且证据段不混进无解说窗口表
    quiet = landed.quiet_windows(spec, cover)
    assert quiet == [(12.0, 4.0, 10.0)], quiet

    ev = landed.evidence_windows(spec, cover)
    assert ev == [(6.0, 12.0)], ev

    # ② 窗口里的静音豁免、窗口外的照报
    levels = [-20.0] * 20
    levels[11] = -99.0     # 证据段口播间隙（6.0–12.0 里面）
    levels[15] = -99.0     # 窗口段里的数字静音——真缺陷
    dead, exempt = landed.dead_seconds(levels, after=3, evidence=ev)
    assert exempt == [11], exempt
    assert dead == [15], "窗口外的数字静音必须照报，豁免不许扩大化"

    # 不给 evidence 时一个都不豁免——证明豁免那支真的在起作用
    dead0, exempt0 = landed.dead_seconds(levels, after=3, evidence=[])
    assert dead0 == [11, 15] and exempt0 == []

    # ③ 口播那道闸的账：整段全静音的证据窗口必须还能被 main 里那道
    #    逐窗口 max 检出（这里验切窗口的算术和它用的门槛是同一个）
    silent = [-99.0] * 20
    lo, hi = int(ev[0][0] + 0.5), int(ev[0][1])
    assert max(silent[lo:hi]) <= landed.SILENCE_FLOOR_DB, (
        "全静音的证据窗口在这个门槛下必须判得出来")


def test_整屏证据卡的出图宽度要跟着画布算不能各写各的():
    """`render_evidence_card.CARD_SHOW_W` 必须等于 `cut_still_segment` 里那个
    `int(VIDEO_W * 0.94)`——**两处写死必分叉，而分叉的样子是「字比设计的小」**。

    第一版把出图宽度拍成 1600，缩到 1015 就是 0.63 折：设计成 46px 的正文渲到
    画面上只剩 29px（屏宽 2.7%，比字幕还小一半），渲出来摆在一起才看见。
    现在 2× 出图、缩放比恒为 0.5，字号除以 2 就是画面上的真实像素。

    顺带钉住引语卡那道闸：**没有 credit 不许渲**。一句没有出处的话正是这个
    仓库反复栽过的那种，闸要在渲之前拦，不能指望写卡的人记得。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import render_evidence_card as card  # noqa: PLC0415

    reel = _reel()
    # ① 出图宽度和画布口径同源
    assert card.CARD_SHOW_W == int(reel.VIDEO_W * 0.94), (
        f"卡按 {card.CARD_SHOW_W} 宽出图，而 cut_still_segment 缩到 "
        f"{int(reel.VIDEO_W * 0.94)}——字号就全算错了")
    assert card.CARD_W % card.CARD_SHOW_W == 0, (
        "出图宽度必须是显示宽度的整数倍，否则字号换算不成立")

    # ② 引语卡没有出处 → 报错（真调 build_html，不查源码文本）
    with pytest.raises(SystemExit) as bad:
        card.build_html({"kind": "quote", "quote": "no source", "zh": "没有出处"})
    assert "credit" in str(bad.value)

    # ③ 三种 kind 都渲得出内容，认不出来的要报错
    html = card.build_html({"kind": "quote", "quote": "hi", "zh": "嗨",
                            "credit": "—— 某某 · 某年"})
    assert "hi" in html and "嗨" in html and "某某" in html
    facts = card.build_html({"kind": "facts",
                             "rows": [{"value": "12 岁", "label": "夺冠"}]})
    assert "12 岁" in facts and "夺冠" in facts
    tl = card.build_html({"kind": "timeline",
                          "rows": [{"when": "2020", "what": "澳网女双冠军"}]})
    assert "2020" in tl and "澳网女双冠军" in tl
    with pytest.raises(SystemExit):
        card.build_html({"kind": "photo", "image": "x.png"})


def test_算不出标题时文案字数不许估得比真推送松():
    """dry-run 的正文字数必须和真推送量的是**同一段文字**。

    真推送会在正文前面粘一句自己算出来的标题（`push_reel.main` 里
    `copy_text = f"{title}\\n\\n{copy_text}"`），`split_copy` 甩掉第一行加空行
    当标题——所以文件自己的第一段在真推送里**是正文的一部分**。

    dry-run 算标题要读产物目录的日期，取不到就走退路。那条退路原来写的是
    「不拼标题，直接 split_copy」，于是文件第一段被当成标题免费甩掉，
    估出来少一整段：eala-story 这儿报 859 字、真闸报 1019 字
    （run 31658290756）。**它打了警告，但同时给了一个具体数字，而具体数字
    就是会被当成结论。**

    现在退路拼一个占位标题，算出来的 body 和真推送**逐字相同**。判据就钉
    这一条：同一份文案，两条路（算得出标题 / 算不出标题）量出来的正文
    长度必须一样。

    反向验证：把退路改回 `text_with_title = text`，第二个断言当场红
    （少掉第一段的长度）。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    copy_text = "第一段是钩子，真推送里它算正文。\n\n中间一段。\n\n#网球 #网球时差\n"

    # 真推送的口径：前面粘一句标题
    _t, real = push_reel.split_copy(f"8.13 网球有故事 | 某某某\n\n{copy_text}")
    # dry-run 算不出标题时的退路：占位标题
    _t2, fallback = push_reel.split_copy(f"（占位标题）\n\n{copy_text}")
    assert fallback == real, "占位标题这条退路量的必须是同一段正文"

    # 而「不拼标题」那条老退路会把第一段甩掉——正是要拦的那个偏松
    _t3, naive = push_reel.split_copy(copy_text)
    assert len(naive) < len(real), "老退路本来就偏松，这条断言证明差距真的存在"

    body = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert 'text_with_title = f"（占位标题）\\n\\n{text}"' in body, (
        "dry-run 算不出标题时必须拼占位标题，不能直接把文件第一段当标题甩掉")


def test_不许再印没验证过的投递查询接口():
    """发送成功那行日志里，**不许再给出一个没验证过的查询 URL**。

    来路：那儿原来印着
    `https://www.pushplus.plus/api/send/queryMessage?token=…&id=…`，说「要查
    微信有没有真的送达就问它」。2026-08-13 账号所有者问「还没推送么」，我
    照着那句话建了工具和工作流、合进 main、跑到 runner 上（token 在 secret
    里，只有那儿查得了）——实测 `code=903 用户令牌不正确`；再翻官方 API
    文档，**根本没有这个查询接口**（只说「可以用流水号查最终发送结果」，
    端点、参数、鉴权一概没写）。

    那句提示把人引向一条不存在的路，而且印了很久——正是「没量过的推断写进
    注释，之后每个人都拿它当判据」（同「edge-tts 同理」那条）。工具和工作流
    都删了：一条永远失败的路留在仓库里，和一条常年红的检查是同一个毛病。

    判据钉两头：① 那个 URL 不许再出现在会印进日志的地方；② 但**「收下 ≠
    送达」这句必须还在**——删掉查询路不等于可以假装接口成功就是送到了。
    """
    src = Path("src/tennislive/publish/pushplus.py").read_text(encoding="utf-8")
    body = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "queryMessage" not in body, (
        "这个查询接口官方文档里没有、实测 903——不许再印给下一个人")
    assert "不代表微信推到了手机上" in body, (
        "「接口收下 ≠ 微信送达」这句不能跟着删——它是真的")


def test_contain的横向窗口要从源片宽度算不许写死1920():
    """`keep = int(1920 * CONTAIN_KEEP)` 隐含「源片一定是 1920 宽」。

    854×480 的存档素材照这个算出 **1190px 的窗口，比源片本身还宽**，
    ffmpeg 直接拒掉 `crop`；就算老老实实按比例算出 528px，放到 1080 宽也是
    **放大 2.05 倍**——而整幅不裁只放大 1.26 倍。也就是说 contain 那句
    「先横向留一点再缩，画面大一圈」的前提**在低清源片上是反的**：
    裁完更糊，而糊掉的正是主体。

    判据钉三头：
      ① 1920 的源片**一格都不动**（这条改动不许悄悄改掉存量片子的构图）
      ② 窗口永远不超过源片宽度
      ③ 横向放大不许超过 `CONTAIN_MAX_UPSCALE`，除非源片整幅铺进来都还不够
    """
    reel = _reel()
    assert reel.contain_keep_width(1920) == int(1920 * reel.CONTAIN_KEEP) // 2 * 2, (
        "1920 的源片按老口径算出来就是 1190，改动不许碰它")
    for w in (640, 854, 1080, 1280, 1920):
        keep = reel.contain_keep_width(w)
        assert 0 < keep <= w, f"{w} 宽的源片算出 {keep} 的窗口，裁不出来"
        upscale = reel.VIDEO_W / keep
        assert upscale <= reel.CONTAIN_MAX_UPSCALE + 1e-9 or keep == w // 2 * 2, (
            f"{w} 宽的源片裁到 {keep}，放大 {upscale:.2f} 倍——"
            "顶到上限就该少裁，一路少到整幅铺满为止")
    # 源片窄到整幅铺进来都超上限时，只能整幅铺——不许因此裁得更狠
    assert reel.contain_keep_width(640) == 640


def test_低清存档源要显式认领而且它的段一律整幅铺(tmp_path):
    """`MIN_SOURCE_H` 拦的是**下载事故**（yt-dlp 悄悄退到 360p，换 client 重下
    就好）。而 2012 年赛事官方频道上传的那批片子**本来就只有 854×480**——
    八种 player client 全试过，两种下得下来的都是这个尺寸
    （run 31690907495 等六趟）。

    拿前者的闸去拦后者，等于把一整段只此一份的历史挡在门外，而这条线的规矩是
    **精准优先于清晰**。所以低清不是自动放行，是**显式认领**，和 `mixed_fps` /
    `silent_source` / `conform` 一个形状。

    ⚠️ 认领之后还有第二道：那些段必须 `fit: "contain"`。3:4 裁切从 854×480
    里取的是 360×480，放到 1080×1440 是**放大 3 倍**——正是 `resolve_crop`
    那句报错说的「糊得没法看」。**只放行不管取景，等于把闸换了个地方漏。**
    """
    reel = _reel()

    # ① 没认领：照旧拒掉，而且报错要说出路
    with pytest.raises(reel.ReelError) as got:
        reel.resolve_crop(854, 480)
    assert "太小" in str(got.value) and "archival" in str(got.value), (
        "报错要指出「真的只有这么高就认领下来」这条出路，不能只说不行")

    # ② 认领了：放行，窗口按 480 高换算
    reel.resolve_crop(854, 480, None, "2012 年赛事官方上传，八种 client 全试过")
    assert (reel.CROP_W, reel.CROP_H) == (360, 480)
    reel.resolve_crop(1920, 1080)                 # 还原全局，别污染同进程的别人

    # ③ 认领过的源，段还在按 3:4 裁 → 当场红
    def spec(fit):
        return {
            "slug": "t", "sources": {"a": "https://x/a", "b": "https://x/b"},
            "archival": {"a": "2012 年的上传只有 480p"},
            "segments": [{"start": 0, "end": 5, "source": "a", "fit": fit,
                          "narration": "一句话"},
                         {"start": 0, "end": 5, "source": "b",
                          "narration": "另一句"}],
        }
    segs = reel.parse_segments(spec("crop"), {"a": 1, "b": 1}, "a")
    with pytest.raises(reel.ReelError) as got:
        reel.check_archival_fit(spec("crop"), segs)
    assert "整幅铺" in str(got.value) or "contain" in str(got.value)

    ok = spec("contain")
    reel.check_archival_fit(ok, reel.parse_segments(ok, {"a": 1, "b": 1}, "a"))

    # ④ 认领表本身要校形状：名字写错的认领是一盏恒真的绿灯
    bad = spec("contain")
    bad["archival"] = {"nosuch": "理由"}
    with pytest.raises(reel.ReelError) as got:
        reel.check_archival_fit(bad, reel.parse_segments(bad, {"a": 1, "b": 1}, "a"))
    assert "不在 sources 里" in str(got.value)

    empty = spec("contain")
    empty["archival"] = {"a": "   "}
    with pytest.raises(reel.ReelError):
        reel.check_archival_fit(empty, reel.parse_segments(empty, {"a": 1, "b": 1}, "a"))


def test_认领低清那道闸排在下载之前():
    """又是「闸装在哪一步」那条老账。这是 spec 的**形状**问题——
    「你认领了 a 是低清，却让 a 的段按 3:4 裁」，一个源片字节都不用碰就能判。

    排在下载后面的话，每写错一次都要先等几百 MB 下完；而这条线上的存档素材
    动辄六七条源。所以它必须在 `validate_spec` 里，`--dry-run` 就该红。
    """
    reel = _reel()
    body = inspect.getsource(reel.validate_spec)
    assert "check_archival_fit" in body, (
        "这道闸要在 validate_spec 里跑，dry-run 才够得着")


def test_八档都只有低画质时要把最好的那份收下不要全扔掉(tmp_path, monkeypatch, capsys):
    """下载这一步**不判「够不够高」**，它只负责把能拿到的最好那份拿回来。

    原来的写法是：高度不够就 `unlink` 接着试下一档，八档试完抛
    「都下不下来」。对「yt-dlp 悄悄退到 360p」这条是对的（换个 client 就有
    高清）；对「这条素材本来就只有这么高」是错的——2012 年赛事官方频道那批
    片子八种 client 全试过，能下的都是 854×480（run 31690907495 等六趟），
    于是一整段只此一份的历史被一句「太小了」挡在门外，**而报错说的是
    「多半是 yt-dlp 退到了低画质那一档」，把人引向一个不存在的病因**。

    这两件事在这一层长得一模一样，分得清的是 spec（`archival` 认领）。
    所以判据钉两头：
      ① 八档全低清 → 收下最高的那份，并且**说清楚收的是什么**
      ② 但「够不够」的闸**没有松**：没认领的话 `resolve_crop` 照旧红
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    heights = iter([360, 480, 480, 360, 240, 480, 360, 240])
    served: list[int] = []

    def _fake_ytdlp(args, **kw):
        out = Path(args[args.index("-o") + 1])
        out.write_bytes(b"\0" * 2048)
        served.append(next(heights, 240))
        return subprocess.CompletedProcess(args, 0, "", "")

    import subprocess  # noqa: PLC0415

    monkeypatch.delenv(reel._SOURCE_CACHE_ENV, raising=False)
    monkeypatch.setattr(reel.shutil, "which", lambda _n: "/usr/bin/yt-dlp")
    monkeypatch.setattr(reel.subprocess, "run", _fake_ytdlp)
    monkeypatch.setattr(reel, "probe_size",
                        lambda _p: (served[-1] * 16 // 9, served[-1]))

    dest = tmp_path / "source.mp4"
    got = reel.download("https://www.youtube.com/watch?v=CCCCCCCCCCC", dest)
    assert got == dest and dest.is_file(), "八档全低清就把素材全扔了"
    out = capsys.readouterr().out
    assert "480" in out and "这一步不判它够不够" in out, (
        f"收下了却没说清收的是什么：{out}")
    # 中间那些低清副本不许留在目录里当垃圾
    assert not list(tmp_path.glob("*_lowres*")), "临时副本没清干净"

    # ② 闸没松：没认领照旧红，认领了才放行
    with pytest.raises(reel.ReelError):
        reel.resolve_crop(854, 480)
    reel.resolve_crop(854, 480, None, "2012 年的赛事官方上传")
    reel.resolve_crop(1920, 1080)                 # 还原全局


def test_合语音被限流要重试而明确拒绝不许重试(monkeypatch, tmp_path):
    """Azure 一次 429 不许把整趟 render 报销掉，而密钥错也不许重试四遍。

    来路（2026-08-13，李娜那条）：连着四趟 run 死在同一行——

        AzureTTSError: Azure 合成失败（ResultReason.Canceled）
        CancellationReason.Error: WebSocket upgrade failed: Too many requests (429)

    我一开始当成「配额用完了，等」，等了两个小时四趟全红。真去读代码才看见
    **`azure_tts.synthesize` 一次重试都没有**，而 `build_match_reel.synthesize`
    是贴着发的：一条片子三四十段，F0 的限是「20 次/60 秒」，所以典型的失败
    形状就是「前二十段顺利、之后一路 429」。一次瞬时限流报销掉的是五分钟的
    render 外加几百 MB 的下载——和 `pushplus` 那条「保护了不重要的那一步，
    没保护唯一重要的那一步」是同一个毛病。

    判据钉三头，三头都反向验证过：

    1. **429 要重试，而且真的能救回来**（第二次成功 → 不抛）
    2. **401/403 不许重试**（重发只会把同一个错误重复四遍）
    3. **重试要出声**——不然「今天 Azure 慢」和「这条被限流重试了三次」
       在日志上一模一样

    ⚠️ 反向验证第 ② 项自己先漏了一次：我只把 `"429"` 从可重试清单里拿掉，
    **测试照样绿**——因为同一条错误文本里还有 `Too many requests`，另一个
    关键词把它接住了。判据没被断开，验的就不是它。两个关键词一起拿掉才真的红。
    「拆掉一道闸还能通过，先怀疑自己拆得不干净，再怀疑判据恒真」。
    """
    import logging  # noqa: PLC0415
    import sys  # noqa: PLC0415
    import types  # noqa: PLC0415

    from tennislive.video import azure_tts  # noqa: PLC0415

    calls: list[str] = []

    def _sdk(script: list[str]):
        """一个刚好够 `synthesize` 用的假 SDK；`script` 是每次调用的结果。"""
        mod = types.ModuleType("azure.cognitiveservices.speech")

        class Reason:
            SynthesizingAudioCompleted = "ok"
            Canceled = "canceled"

        class Cancel:
            def __init__(self, detail: str) -> None:
                self.reason = "CancellationReason.Error"
                self.error_details = detail

        class Result:
            def __init__(self, detail: str, out: Path) -> None:
                if detail == "":
                    self.reason = Reason.SynthesizingAudioCompleted
                    out.write_bytes(b"\0" * 64)
                else:
                    self.reason = Reason.Canceled
                    self.cancellation_details = Cancel(detail)

        class Synth:
            def __init__(self, speech_config=None, audio_config=None):  # noqa: ANN001
                self._out = audio_config

                class _Sig:
                    def connect(self, _fn):  # noqa: ANN001
                        return None

                self.synthesis_word_boundary = _Sig()

            def speak_ssml_async(self, _ssml):  # noqa: ANN001
                detail = script[min(len(calls), len(script) - 1)]
                calls.append(detail)
                res = Result(detail, self._out)
                return types.SimpleNamespace(get=lambda: res)

        mod.SpeechConfig = lambda **kw: types.SimpleNamespace(
            set_speech_synthesis_output_format=lambda _f: None)
        mod.SpeechSynthesisOutputFormat = types.SimpleNamespace(
            Audio24Khz48KBitRateMonoMp3="mp3")
        mod.ResultReason = Reason
        mod.SpeechSynthesizer = Synth
        mod.SpeechSynthesisBoundaryType = None
        mod.audio = types.SimpleNamespace(
            AudioOutputConfig=lambda filename: Path(filename))
        return mod

    def _install(script: list[str]) -> None:
        calls.clear()
        pkg = types.ModuleType("azure")
        sub = types.ModuleType("azure.cognitiveservices")
        leaf = _sdk(script)
        monkeypatch.setitem(sys.modules, "azure", pkg)
        monkeypatch.setitem(sys.modules, "azure.cognitiveservices", sub)
        monkeypatch.setitem(sys.modules, "azure.cognitiveservices.speech", leaf)

    monkeypatch.setenv("AZURE_SPEECH_KEY", "k")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "eastus")
    # 退避真等下去这条测试要跑一分多钟；等多久由 `_BACKOFF` 决定，这里只关心
    # 「重试了没有」，所以把 sleep 打桩掉并**记下每次等了多久**。
    slept: list[float] = []
    monkeypatch.setattr(azure_tts.time, "sleep", slept.append)
    monkeypatch.setattr(azure_tts, "_paced_gap", 0.0)

    kw = dict(voice="zh-CN-YunxiNeural", rate="+6%", pitch="+0Hz")
    throttled = ("CancellationReason.Error: WebSocket upgrade failed: "
                 "Too many requests (429). Please check subscription information.")

    # ① 第一次 429、第二次成功 —— 必须救回来
    _install([throttled, ""])
    with caplog_at(logging.WARNING) as records:
        marks = azure_tts.synthesize("测试一句", tmp_path / "a.mp3", **kw)
    assert marks == [] and (tmp_path / "a.mp3").is_file(), "重试之后没有落盘"
    assert len(calls) == 2, f"429 之后没有重试：只发了 {len(calls)} 次"
    # ⚠️ `slept` 里除了退避那一档，还会多一次自适应间隔——**那是打桩造出来的**：
    # 真跑的时候退避那 5 秒是真的过去了，`time.monotonic() - _last_call` 已经
    # 大于 3 秒，补间隔那一句一秒都不会等。这里把 sleep 换成了记录器，
    # 挂钟没动，所以它看得见。判据只钉退避那一档。
    assert slept[0] == azure_tts._BACKOFF[0], f"退避没按阶梯来：{slept}"
    assert all(x <= azure_tts._BACKOFF[0] for x in slept[1:]), (
        f"除了退避还等了别的：{slept}")
    said = " ".join(r.getMessage() for r in records)
    assert "429" in said and "重试" in said, f"重试了却没出声：{said!r}"
    # ⚠️ **这一条才是「认出 429」唯一改变行为的地方**，别漏。重试本身是
    # 「除非确定没救，否则都重发」——所以把 429 从可重试清单里拿掉，它会落进
    # `unknown` 照样重试，**上面那几句断言全都还是绿的**（反向验证时当场发现的）。
    # 真正只有认出限流才会发生的是**给后面的调用留间隔**：退避只救得了这一段，
    # 救不了这一趟——下一段照样贴着发，照样 429。
    assert azure_tts._paced_gap >= 3.0, (
        f"认出了限流却没给后面的调用留间隔（_paced_gap={azure_tts._paced_gap}）；"
        f"F0 是 20 次/60 秒，一条片子三四十段，不留间隔就是退避完立刻再撞一次")

    # ② 一路 429 —— 用尽阶梯之后要说清是「重试 N 次仍被挡回来」
    slept.clear()
    monkeypatch.setattr(azure_tts, "_paced_gap", 0.0)
    _install([throttled])
    with pytest.raises(azure_tts.AzureTTSError) as exc:
        azure_tts.synthesize("测试一句", tmp_path / "b.mp3", **kw)
    assert len(calls) == len(azure_tts._BACKOFF) + 1, (
        f"没有把阶梯走完：发了 {len(calls)} 次")
    assert [x for x in slept if x in azure_tts._BACKOFF] == list(azure_tts._BACKOFF), (
        f"三档退避没有按顺序走完：{slept}")
    assert "仍被挡回来" in str(exc.value), str(exc.value)

    # ③ 密钥错 —— **一次就该停**，重发只会把同一个错误重复四遍
    slept.clear()
    monkeypatch.setattr(azure_tts, "_paced_gap", 0.0)
    _install(["CancellationReason.Error: WebSocket upgrade failed: "
              "Authentication error (401). Please check subscription key."])
    with pytest.raises(azure_tts.AzureTTSError) as exc:
        azure_tts.synthesize("测试一句", tmp_path / "c.mp3", **kw)
    assert len(calls) == 1, f"明确拒绝还重试了 {len(calls)} 次"
    assert slept == [], f"明确拒绝还等了 {slept}"
    assert "重试没有意义" in str(exc.value), str(exc.value)


import contextlib  # noqa: E402


@contextlib.contextmanager
def caplog_at(level):
    """收这个模块的日志。

    ⚠️ **档位必须和那句告警一致**：告警是 WARNING，收在 ERROR 上它根本进不来，
    而那样坏代码也能让测试变绿（这个仓库栽过一次）。
    """
    import logging  # noqa: PLC0415

    logger = logging.getLogger("tennislive.video.azure_tts")
    records: list[logging.LogRecord] = []

    class _Grab(logging.Handler):
        def emit(self, record):  # noqa: ANN001
            records.append(record)

    handler = _Grab(level)
    logger.addHandler(handler)
    old, logger.level = logger.level, level
    try:
        yield records
    finally:
        logger.removeHandler(handler)
        logger.level = old


def test_传Release附件要重试而且不许用会被errexit杀掉的写法():
    """一次 GitHub 5xx 不许把一趟 14 分钟的 render 报销掉。

    来路（2026-08-13，李娜那条，run 31709569579）：render 跑完 14 分 27 秒、
    `check_reel_landed` 也过了，死在这一行——

        成片 175 MiB 超过 95 MiB —— 发到 Release reel-lina-cincinnati-2012
        HTTP 500 (https://api.github.com/…/releases/assets/512914137)

    `--clobber` 是「先删旧的再传」，删那一下撞上 GitHub 自己的 5xx。和
    `azure_tts.synthesize` 那条「一次 429 报销掉五分钟」是同一个毛病，
    处置也一样：**没送到就重发**（`--clobber` 幂等，删到一半再传一遍就好）。

    判据钉两头：

    1. 那一行外面**真的套着重试循环**，而且退避是涨的
    2. 循环里**不许出现 `] && break` 这种写法**——`bash -e` 下 AND 列表整条
       为假会直接把整步杀掉，看起来像「传失败了」，其实是第一圈就被踢出去了。
       这个坑同一个步骤里已经踩过一次（探活那段的注释写着），别在它上面再踩
    """
    block = _step_block("成片发到 Release（不进 git）")
    body = _yaml_only(block)
    assert "gh release upload" in body, "这一步不传 Release 附件了？判据要跟着换"

    # ① 上传那一行必须在 for 循环里，而且循环里要有 sleep（退避）
    upload = body.index("gh release upload")
    loop = body.rfind("for ", 0, upload)
    assert loop != -1, "`gh release upload` 外面没有重试循环"
    tail = body[loop:]
    assert "sleep" in tail[:tail.index("URL=")], (
        "重试循环里没有退避——贴着重发四次，撞上的同一个 5xx 多半还在")
    assert "WAIT=$((5 * i * i))" in body, (
        "退避不是涨的：等长的重试对一次持续几十秒的服务端故障没有用")

    # ② 不许用 `] && break`：bash -e 下这一条会把整步杀掉
    for line in tail.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "&&" in stripped:
            raise AssertionError(
                f"`bash -e` 下这一行整条为假会直接杀掉这一步，用 if：{stripped!r}")

    # ③ 用尽之后要报错，不许静静往下走——往下走会把一个 404 的链接写进
    #    render.json，然后发到微信，而消息发出去收不回来
    assert 'UPLOADED" = 1 ]' in body and "exit 1" in body, (
        "四次都没传上去却没有拦住：下游会把一个取不到的链接写进 render.json")


def test_换取签名URL拉受控流这条源禁掉():
    """**公开 URL 当公开 URL 取是一回事；程序化换一个短时令牌是另一回事。**

    2026-08-14 账号所有者定的。来路是 `shang-darderi-montreal-2026`——它的
    `_source` 自己写着「通过 Sky 页面公开 API **换取短时签名 HLS** 后探测
    成功」，而仓库里其余 89 条源全是「点开就能取的地址」。差的不是画质也不是
    稳定性，是**法律类别**：后者规避的是发布方的访问控制（DMCA §1201 那一类），
    而对家是 Sky Italia。CLAUDE.md 里「源片从哪儿来」那张表（WTA 官方 YouTube /
    Tennis TV 官方频道 / ATP 官方 YouTube / Tennis TV 标 `free` 的条目）从来
    没有「换签名令牌」这一档——它是一次没人认领过的越界。

    ⚠️ **这道闸没有「显式认领」的出路**，和 `mixed_fps` / `silent_source` /
    `conform` 不是一族：那几条是**取舍**（两个选择都说得通，认领一下把「想清楚
    了」和「凑合一下」分开），这一条是**禁令**——没有哪份 spec 值得开这个口子。

    ⚠️ **判据宁可窄，不可宽。** 下半张表是**不许被误伤的**那些：短 `token=`
    是分页游标不是签名，`foosignature=` 不是参数、只是名字里带这个词，
    查询串里的 `secure/` 是噪音。三个方向都反向验证过——放宽任何一条，
    下半张表当场有一行红。
    """
    reel = _reel()

    # ① 该拦的：五个特征各一条，外加真实那一条（带完整 Akamai 令牌串）
    must_reject = {
        "Akamai hdnts": "https://acdn.example.it/hls/x/master.m3u8"
                        "?hdnts=st=1786073073~exp=1786073373~hmac=8e28dd73",
        "AWS SigV4": "https://s3.example.com/v.m3u8?X-Amz-Signature=8e28dd73ae0f",
        "CloudFront": "https://d1.cloudfront.net/v.m3u8?Signature=abc~Key-Pair-Id=K1",
        "长 token": "https://x.example.com/v.m3u8?token=" + "a" * 40,
        "受控路径": "https://acdn.example.it/secure/hls/2026/08/06/1116425/master.m3u8",
        "真实那条": "https://acdn.ak-stream-videoplatform.sky.it/secure/hls/"
                    "2026/08/06/1116425/master.m3u8?hdnts=st=1786073073~"
                    "exp=1786073373~acl=/secure/hls/2026/08/06/1116425/*~"
                    "hmac=8e28dd738ae0fb792a37a330146374b57e1b9fb2f2b136a3a98",
    }
    for label, url in must_reject.items():
        with pytest.raises(reel.ReelError) as got:
            reel.spec_sources({"source_url": url})
        assert "禁掉" in str(got.value), f"{label} 拦下来了，但报错没说这条路是禁的"
        # **报错要说出路**，只说不行等于让下一个人再去猜一遍
        assert "未签名" in str(got.value) and "换源" in str(got.value), (
            f"{label} 的报错没给出路（①换未签名的公开地址 ②换源）")

    # ② 多源那一支也要拦——写两处必分叉，而分叉那半边是静静放行
    with pytest.raises(reel.ReelError):
        reel.spec_sources({"sources": {"a": "https://www.youtube.com/watch?v=ok",
                                       "b": must_reject["Akamai hdnts"]}})

    # ③ 不许误伤：仓库里其余 89 条源的形状，加三条容易撞上的
    must_pass = [
        "https://www.youtube.com/watch?v=OvjNXy1mQjY",
        "https://youtu.be/OvjNXy1mQjY",
        "https://players.brightcove.net/1/x_default/index.html?videoId=6402850037112",
        "https://www.youtube.com/watch?v=abc&token=short",     # 短 token 是游标
        "https://api.example.com/v?next=1&foosignature=abc",   # 不贴参数边界
        # ⚠️ 这一条要写成 `next=/secure/…`，**前后都得有斜杠**才验得到「只看
        # 路径」这件事。第一版写的是 `utm=secure/thing`——那串里压根没有
        # `/secure/`，把 `^[^?#]*` 拆掉它照样过，**守卫是死的**。是反向验证
        # 才发现的：一个自己不成立的守卫，和没有守卫一模一样。
        "https://x.example.com/hls/master.m3u8?next=/secure/thing",
    ]
    for url in must_pass:
        reel.spec_sources({"source_url": url})                 # 不许抛

    # ④ 仓库里现有的源，除了那条反面先例，一条都不许被拦
    hit = []
    for slug, spec in _reel_specs().items():
        try:
            reel.spec_sources(spec)
        except reel.ReelError as exc:
            if "换取签名令牌" in str(exc):
                hit.append(slug)
    assert hit == ["shang-darderi-montreal-2026"], (
        f"被这道闸拦下的 spec 是 {hit}，应该只有那条反面先例。"
        "多出来说明判据放宽了、误伤了合规的源。")


def test_签名源那道闸排在下载之前():
    """又是「闸装在哪一步」那条老账——**只测行为拦不住位置错**。

    这是 spec 的**形状**问题：一个源片字节都不用碰就能判。排在下载后面的话，
    每写错一次都要先等几百 MB 下完；而这条线上「返工比慢更贵」是整套优化的
    出发点。所以它必须在 `--dry-run` 就红。

    判据钉三头：
    ① 它收在 `spec_sources`——那是「spec → 源片地址」的唯一出处，
       `validate_spec` / `render` / `check_archival_fit` 全走它，装一处
       每个消费者自动护住，不用挨个记得加；
    ② `render()` 里 `validate_spec(spec)` 排在 `download(` 前面（既有判据
       已经钉过，这里连着这条一起钉，免得有人把 `spec_sources` 挪走）；
    ③ **`--dry-run` 那条路真的走得到**——它调 `validate_spec`，而
       `validate_spec` 调 `spec_sources`。
    """
    reel = _reel()
    src = Path(reel.__file__).read_text(encoding="utf-8")

    # ① 闸收在 spec_sources 里（去掉 docstring 再看，注释里提到函数名是常事）
    body = inspect.getsource(reel.spec_sources)
    assert "_reject_signed_source_urls" in body.split('"""')[-1], (
        "这道闸不在 `spec_sources` 里——那是 spec 转源片地址的唯一出处，"
        "装在别处就会漏掉某个消费者")

    # ② render() 里形状校验排在下载前面
    render_body = src[src.index("def render("):]
    render_body = render_body[:render_body.index("\ndef ", 1)]
    assert render_body.index("validate_spec(spec)") < render_body.index("download(url, path, archival="), (
        "spec 形状校验排到下载后面了——这道闸跟着一起失效")

    # ③ validate_spec 真的走到 spec_sources；dry-run 真的走到 validate_spec
    assert "spec_sources(spec)" in inspect.getsource(reel.validate_spec).split('"""')[-1], (
        "validate_spec 不再调 spec_sources，dry-run 就够不着这道闸了")
    main_body = src[src.index("def main("):]
    dry = main_body[main_body.index("if args.dry_run:"):]
    assert "validate_spec(spec)" in dry[:400], "--dry-run 那条路没调 validate_spec"

    # ④ 真跑一遍 dry-run 的第一步：不联网、不碰源片，当场红
    with pytest.raises(reel.ReelError):
        reel.validate_spec(json.loads(
            Path("specs/reels/shang-darderi-montreal-2026.json").read_text("utf-8")))


# ── 会下载源片的那条路，一律经过 spec_sources ──────────────────────────────
#
# 来路（2026-08-14）：`tools/build_match_reel.py` 里躺着一个零调用方的
# `resolve_sources(spec, outdir)`——2026-08-01 加多源支持时写的，`render()`
# 后来把这段内联重写成走 `spec_sources(spec)` 的版本，**没把旧的删掉**。
#
# 它单独存在只是浪费 17 行；真正的问题是**它绕过了签名源那道闸**：
# `_reject_signed_source_urls` 收在 `spec_sources()` 里，而它自己读
# `spec["source_url"]` 就直接交给 `download()`。而它的名字看着**正是**
# 「把源片下下来」该调的那个——下一个人复活它，那道禁令对这条路就是哑的，
# 而且不吭声。**死代码不吭声，被绕过的闸也不吭声，两个叠在一起就是陷阱。**


def _download_paths_without_the_gate(source: str) -> list[str]:
    """一份 Python 源码里，「自己解析源片字段 + 自己下载 + 不走闸」的函数名。

    判据**宁可窄，不可宽**，三个条件缺一不可：

    - 调了 `download(` / `yt_download(`——只解析不下载的那几处不算。
      `load_spec` / `check_segment_cuts` / `probes_for_spec` / `--dry-run` 那段
      和 `tools/check_reel_cuts.py` 各自都抄着一份同样的回退，**但它们只用来按
      URL 认领 probe.json，一个字节都不下载**，绕过闸没有后果；而它们要的恰恰是
      「spec 有毛病也别把诊断带崩」，硬改成调 `spec_sources()` 反而会让
      `--dry-run` 在本该报出问题的地方先抛出来。
    - 出现了 **`"source_url"` / `"sources"` 这两个字面量之一**，也就是它在自己
      解析 spec 的源片字段。按**整串相等**比，不按子串——docstring 里提到这两个
      词是常事，而这个仓库为「连注释一起扫，把坑记下来被判成又踩了这个坑」栽过
      五次。`render()` 和 `main()` 都不含这两个字面量，所以都不进这张网。
    - 没有调 `spec_sources(`。

    ⚠️ 嵌套函数算在外层函数头上（`ast.walk` 不分层）——**偏严的方向**：
    真出现「外层下载、内层解析」也会被点名，那正是该点名的。
    """
    tree = ast.parse(source)
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        calls = {c.func.id for c in ast.walk(node)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        if not calls & {"download", "yt_download"}:
            continue
        if "spec_sources" in calls:
            continue
        literals = {n.value for n in ast.walk(node)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        if literals & {"source_url", "sources"}:
            bad.append(node.name)
    return bad


def test_下载源片一律走spec_sources():
    """既自己解析 spec 的源片字段、又自己 `download()` 的函数，一个都不许有。

    判据钉三头，**第三头是它不恒真的证明**：

    ① **主语自证**：这个文件里真的扫得到会下载的函数，而且 `render()` 在里面、
       它真的调了 `spec_sources()`。少了这一条，有人把 `download` 改个名字、
       或者这条扫描写错了路径，禁令那一半就会安安静静地全绿——
       「空列表和一份都没有长得一模一样」。
    ② **禁令**：整个 `tools/` 下一个违规都没有。今天是 0 条，这正是目标状态。
    ③ **反向锚点**：把删掉的那个 `resolve_sources` 原样喂回探测器，它必须被点名。
       ②本身是一条空断言，只有③能证明它**咬得动**——这个仓库为「拆掉一道闸测试
       照样绿」栽过好几次（`stop_reason == refusal` 那条、`_cut_person` 那条）。

    ⚠️ 这道闸只覆盖 reel 这条线的 `spec_sources`。采访片（`build_interview_clip`）
    的源片字段是另一套 schema，够不着这个函数——**那不是漏，是分工**：
    凭据形状那一层由 `tests/test_no_signed_urls.py` 全仓库扫（`specs/**/*.json`
    连采访 spec 一起盖住），这条管的是「解析和下载写在同一个函数里」这个形状。
    """
    tools = Path("tools")

    # ① 主语自证
    reel_src = (tools / "build_match_reel.py").read_text(encoding="utf-8")
    tree = ast.parse(reel_src)
    downloaders = {
        node.name: {c.func.id for c in ast.walk(node)
                    if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and {c.func.id for c in ast.walk(node)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} & {"download"}
    }
    assert len(downloaders) >= 2, (
        f"只扫到 {sorted(downloaders)} 会下载——判据失效了（`download` 改名了？）")
    assert "render" in downloaders, "扫不到 render() 会下载，判据的主语没了"
    assert "spec_sources" in downloaders["render"], (
        "render() 不再从 `spec_sources()` 取源片地址了——签名源那道闸对出片这条"
        "唯一真会下载的路就是哑的")

    # ② 禁令：tools/ 下一个都没有
    offenders: list[str] = []
    for path in sorted(tools.glob("*.py")):
        offenders += [f"{path.name}::{name}" for name
                      in _download_paths_without_the_gate(path.read_text(encoding="utf-8"))]
    assert not offenders, (
        "这几个函数自己解析 spec 的源片字段、自己下载，却没走 `spec_sources()`：\n  "
        + "\n  ".join(offenders)
        + "\n\n`_reject_signed_source_urls`（禁掉换签名令牌拉受控流那条源）收在"
          "`spec_sources()` 里，绕过去这道闸就是哑的，而且不吭声。\n"
          "补法：`urls = spec_sources(spec)` 之后再挨个 `download()`，"
          "别自己抄一份 `sources or {\"\": source_url}` 的回退。")

    # ③ 反向锚点：删掉的那个原样喂回来，必须被点名
    删掉的那个 = (
        "def resolve_sources(spec: dict, outdir: Path) -> dict[str, Path]:\n"
        '    """把 spec 里的源片全下下来，返回 {名字: 路径}。"""\n'
        '    urls = dict(spec.get("sources") or {})\n'
        "    if not urls:\n"
        '        urls = {"": spec["source_url"]}\n'
        "    paths: dict[str, Path] = {}\n"
        "    for name, url in urls.items():\n"
        '        dest = outdir / (f"source_{name}.mp4" if name else "source.mp4")\n'
        "        if not dest.is_file():\n"
        "            dest = download(url, dest)\n"
        "        paths[name] = dest\n"
        "    return paths\n"
    )
    assert _download_paths_without_the_gate(删掉的那个) == ["resolve_sources"], (
        "探测器认不出它想拦的那个形状——②那条断言因此是一盏恒真的绿灯")
    assert not _download_paths_without_the_gate(
        删掉的那个.replace("    urls = dict", "    urls = spec_sources(spec)\n    _ = dict")), (
        "走了 `spec_sources()` 还被点名，这个判据会逼下一个人去绕开它")


def test_数据图的头像和matchup里的名字必须是同一个人():
    """`stats.a` 对应 `cover.matchup[0]`，而 `headshot` 就在 `stats` 块里——
    两边错位的话，数据图上会**用甲的脸和乙的名字，配甲的数字**。

    2026-08-15 `sonmez-anisimova` 真踩过：`stats.a/b` 按 flashscore 的
    home/away 填（森梅兹在前），而 `cover.matchup` 是版式顺序（阿尼西莫娃在前），
    于是那张图把赢球的阿尼西莫娃印成「2 个 ACE、47 分」——**输的那个人的数据**。
    渲染、`--dry-run`、全量测试、`check_reel_landed` 一律不出声：图上每个数
    单看都对，只有把名字和数字对起来才看得出来。

    ⚠️ 判据**自己从 `specs/` 推**，不维护名单：同一个头像文件在别的 spec 里
    挂过哪个中文名，这里就必须还是那个名。谁把 a/b 填反，那张头像就会同时
    挂上两个名字，当场红。新球员第一次出现时这条是哑的（没有第二处可比），
    那是它天然的边界——它拦的是**和已有产物矛盾**，不是拦「填错」本身。
    """
    import collections

    seen: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        stats = spec.get("stats") or {}
        names = [m.get("name") for m in (spec.get("cover", {}).get("matchup") or [])]
        if len(names) != 2:
            continue
        for key, idx in (("a", 0), ("b", 1)):
            shot = (stats.get(key) or {}).get("headshot")
            # ⚠️ **双打（headshot 是列表）不进这张表**——这条判据的前提是
            # 「一张脸只对应一个名字」，团队照恰好打破这个前提：同一张
            # Venus Williams 的头像，单打 spec 里配的名字是「大威廉姆斯」，
            # 双打 spec 里配的是团队标签「威廉姆斯姐妹」——两个名字都对，
            # 不是 a/b 填反。真按列表登记会把这种正常情况当成假阳性打红
            # （2026-08-18 williams-sisters-cincinnati 加团队头像时踩过）。
            # 代价：双打的 a/b 真填反了，这条测试对它是哑的——和「新球员
            # 第一次出现时这条是哑的」同一个边界，单打那半的保护不受影响。
            if isinstance(shot, list):
                continue
            if shot and names[idx]:
                seen[Path(shot).name][names[idx]] += 1

    clashes = {k: dict(v) for k, v in seen.items() if len(v) > 1}
    assert not clashes, (
        "同一张官方头像挂到了两个中文名下——十有八九是某条 spec 的 stats.a/b "
        f"填反了（a 必须对应 cover.matchup[0]）：{clashes}"
    )
    assert len(seen) >= 8, f"判据失效了：只扫到 {len(seen)} 张头像"


def test_手动推送也要记下已推送否则自动闸会再发一次():
    """⚠️ **两条推送路径共用同一个「发过了」的判据，而只有一条在写它。**

    来路：2026-08-16 补发 `bucsa-chwalinska` / `eala-ruse`（被「一趟最多一条」
    拦下之后在仓库里躺了 13 小时）时发现——`auto_push_gate` 判「发过了」的
    **唯一**依据是 `<outdir>/pushed.json` 在仓库里，而写它的步骤只在
    `auto-push-reel.yml` 里有，`match-reel.yml` 全文一个字都没提过它。

    于是**凡是走手动 `mode=push` 发出去的片子，在自动闸眼里永远是「没发过」**：
    哪天它的 `render.json` 再被合进 main 一次，自动闸就会再发一条微信，
    而消息收不回来。当天量了一遍，`push.auto:true` 且没有标记的有 9 条。

    ⚠️ 判据钉**两头**：这一步存在，**而且排在推送之后**。只钉存在的话，
    有人把它挪到推送前面照样绿——而那更坏：推送失败会留下一个「已经发过」的
    假标记，这条片子从此再也发不出去，**而且不吭声**。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)
    assert "推送到微信（可选）" in names, "推送那一步的名字变了，判据的主语没了"
    assert "记下已经推送过" in names, (
        "`match-reel.yml` 没有「记下已经推送过」这一步——手动推的片子在自动闸"
        "眼里永远是「没发过」，`render.json` 再动一次就会重复发一条微信。")
    assert names.index("记下已经推送过") > names.index("推送到微信（可选）"), (
        "「记下已经推送过」排在了推送**之前**——推送失败会留下一个「已经发过」的"
        "假标记，这条片子从此再也发不出去，而且不吭声。")

    block = _step_block("记下已经推送过", text)
    assert "auto_push_gate.py" in block and "--record" in block, (
        "没走 `auto_push_gate.py --record`——那是「发过了」这个标记的唯一出处，"
        "另写一份必分叉，而分叉那天自动闸会重复发一条微信。")
    # 标记只有进了仓库才算数（`auto_push_gate` 判的是 `git ls-files`，不是工作区）
    assert "git push" in block, "标记没推回仓库，等于没记"
    # ⚠️ 不许带 always()：上一步红了就不该记
    assert "always()" not in block, (
        "这一步不许带 `always()`——推送红了还记标记，就是那个「假标记」。")


def test_记推送标记撞车要重试而真失败不许吞():
    """**这一步的失败＝「微信已发、标记没落库」，两头都要堵。**

    ① 原来只 `git pull --rebase` + `git push` 各一次——排在微信**已经发出去**
    之后的一次推送，撞上并行提交就红，红完标记没落库：下一次 `render.json`
    被合并，自动闸把这条当「没发过」**再发一条微信**，而消息收不回来。
    pushed.json 是纯文本，rebase 必然干净，所以照「提交产物」那个循环重试。

    ② 原来 `git commit -m … || exit 0` 把**一切** commit 失败（钩子炸了、
    磁盘满、身份没配上）都吞成绿——只有「没有变化」这一种配 exit 0，
    要用 `git diff --cached --quiet` 显式放行，别拿 `||` 一勺烩。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    block = _step_block("记下已经推送过", text)
    # ① 重试循环 + 耗尽必须红着退出（照 test_提交重试耗尽必须失败 的形状）
    assert "for attempt in $(seq 1 5)" in block, (
        "标记那一步没有撞车重试——单推一次撞上并行提交就把「已发未记」留给自动闸")
    assert "git pull --rebase origin main" in block, "重试之间没有 rebase，重推必然还是被拒"
    assert block.rfind("exit 1") > block.rfind("done"), (
        "重试耗尽没有红着退出——静默吞掉的样子和「记上了」一模一样")
    assert "::error::" in block, "耗尽要出声说清「微信已发、标记要人工补」"
    # ② commit 失败不许被 `|| exit 0` 吞掉
    assert "|| exit 0" not in block, (
        "`git commit … || exit 0` 会把真正的 commit 失败也吞成绿——"
        "只有「没有变化」配 exit 0")
    assert "git diff --cached --quiet" in block, (
        "「没有变化」要用 `git diff --cached --quiet` 显式放行，不是靠 `||`")


def test_push模式重发要显式仓库里有pushed标记就拦():
    """**人工重跑一次 mode=push 就是重复发一条微信，而消息收不回来。**

    自动那条路有「pushed.json 在仓库里就不再发」的闸（`auto_push_gate`），
    手动 `mode=push` 一直没有对应物——手滑重跑、忘了已经发过，都会把同一条
    消息再推一遍。现在预检先查标记，拦下并说清出路（删掉 pushed.json 再来，
    让重发是一次**显式的决定**）。

    ⚠️ 判据钉「`git ls-files` 查 pushed.json」：稀疏检出下 `test -f` 恒假
    （auto_push_gate 那次栽的），而且只在工作区、没提交的标记本来不算数。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    block = _step_block("push 模式先确认成片真的落地了", text)
    assert 'git ls-files -- "$OUTDIR/pushed.json"' in block, (
        "push 预检没查 pushed.json（或者不是用 git ls-files 查的）——"
        "手动重跑 mode=push 会把同一条微信再发一遍")
    assert 'test -f "$OUTDIR/pushed.json"' not in block, (
        "查标记不许用 test -f：稀疏检出下工作区那份恒不在，闸等于没装")
    gate = block.index("pushed.json")
    assert "exit 1" in block[gate:gate + 600], "查到标记却不拦，等于只是提了一嘴"


def test_抓帧点不许贴着源片的最后一帧():
    """来路：2026-08-21，`swiatek-rybakina-cincinnati-injury` 那条片子的源片是
    一条 34.5 秒的 YouTube Shorts（探测报的整数位是「34.5s」，真实浮点值比它
    略大）——probe 第一次真的撞上短素材，`contact_sheet` 在贴着 duration 的
    那一格抓帧时 ffmpeg 直接非零退出：`[enc:mjpeg] Could not open encoder
    before EOF`。

    ⚠️ **这不是本文件别处那种「-t 落过末尾，ffmpeg 退出码 0 悄悄输出短一截」**——
    这次是抓单帧的 `-ss ... -frames:v 1` 贴着 duration 时编码器直接报错退出，
    是一个不同的失败形状，说明「贴着源片末尾」这类坑不止一种长相，得分别防。

    ⚠️ **`duration=34.5` 这个整数边界本身反而复现不了这个 bug**——`_frange`
    从 0.5 起按 1.0 累加不会有浮点误差，算出来的最后一格干干净净停在 33.5，
    离 34.5 有整整一秒。真正会撞线的是**非整数**的 duration（比如 34.52，
    ffprobe 探出来正好会被 `.1f` 显示成「34.5s」）——`_frange` 走到 34.5 时
    `34.5 < 34.52` 成立，于是最后一格贴到只剩 0.02 秒余量，这才是线上那次
    崩溃真正的形状。所以判据用 `3.52` 这个非整数边界，不用 `3.5`。
    这一条本身也是「查了一场就写成了一类」的一个小实例：先按整数边界试过，
    量出来发现**不复现**，才改用非整数边界重新量。

    判据两层：① `sheet_stamps` 算出来的最后一格必须留出 `FRAME_END_MARGIN` 的
    余量，不能贴到 duration 本身——这一层在本地能反向验证（去掉 margin，
    `sheet_stamps(3.52, every=1.0)` 会把最后一格算到 3.5，只剩 0.02 秒余量）；
    ② 真跑一次 `contact_sheet`，在这条边界附近的合成短片上确认端到端仍然
    抓得出帧——ffmpeg 具体哪个版本会不会真的报错是环境相关的（这台沙箱的
    ffmpeg 在 0.02 秒余量下没有复现线上那次崩溃），所以这一层只当**回归
    冒烟测试**，不当「必须曾经炸过」的证据——真正的崩溃证据是线上那趟
    run 的日志。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    # ① 纯算术：非整数 duration 贴着一个整数秒边界，`_frange` 的累加正好在
    # 这里够到它——这一层反向验证过（去掉 FRAME_END_MARGIN 会让它算到 3.5）
    stamps = reel.sheet_stamps(3.52, every=1.0)
    assert stamps, "空列表也是这条判据要防的一种坏——先确认它真的抓到帧"
    assert max(stamps) <= 3.52 - reel.FRAME_END_MARGIN + 1e-9, (
        f"最后一格 {max(stamps)} 贴到了 duration 3.52 附近，"
        f"留的余量不够 FRAME_END_MARGIN={reel.FRAME_END_MARGIN}")

    # ② 端到端冒烟：同样贴边界的合成短片，contact_sheet 走完整套（下载→
    # ffprobe 量 duration→抓帧→拼墙）不许抛异常、不许出空文件
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        clip = tmp / "short.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", "testsrc2=size=320x240:rate=25:duration=3.52",
             "-c:v", "libx264", "-preset", "ultrafast", str(clip)],
            check=True)
        outdir = tmp / "out"
        sheets = reel.contact_sheet(clip, outdir, every=1.0)
        assert sheets, "没有抓到任何帧——contact_sheet 本身就没跑起来"
        frames = sorted((outdir / "frames").glob("*.jpg"))
        assert frames, "帧目录是空的"
        for f in frames:
            assert f.stat().st_size > 0, f"{f} 是空文件——ffmpeg 没真的写出内容"


def test_缩略图墙的格子顺序不许靠文件名排序(tmp_path, monkeypatch):
    """来路：2026-08-25，`usq-2026-kei14`（锦织圭 2014 美网半决赛，8677 秒、
    2893 格）。`preview_segments_local.py` 按我写的窗口 2959~2968s 摆出来的
    格子，烧着的却是 **5418.5 / 5421.5 / 5424.5s**；而同一批里 223 秒的
    `dimitrov` 一格都没错。

    真因是 `contact_sheet` 里这一对：帧写成 `f{index:03d}.jpg`，拼墙前
    `sorted(frames.glob("*.jpg"))`。**过了一千帧文件名变成四位，而字典序里
    `f1000.jpg` 排在 `f100.jpg` 和 `f101.jpg` 中间**，于是整墙的顺序被打散。
    拿真产物验过，三张墙的第一格逐个对上：

        sheet 32 → 帧 1781 → 5343.5s     sheet 95 → 帧 957 → 2871.5s
        sheet 96 → 帧 987  → 2961.5s

    ⚠️ **它一个字都不报**：墙照样出得来、每一格照样烧着自己那一秒的时间码、
    张数和格数也都对——错的只有「第几张墙上装的是哪一段时间」。而
    `sheet_stamps()` 反推「这一秒在第几张第几格」时假定的正是顺序排列，
    于是预览、挑段、`_editing_why` 里记的那些秒数会整条指到别的画面上，
    **而那和「这一段我看过了」长得一模一样**。

    ⚠️ **短片子永远踩不到**：要 1000 格才够得着，按 every=2.0 算是 33 分钟以上
    的源片。这条线绝大多数源片是三五分钟的官方集锦，所以它躺了很久。

    判据钉的是**顺序**，不是文件名的位数：拼墙拿到的那串帧，烧上去的秒数
    必须严格递增、而且和 `sheet_stamps()` 算出来的那一串逐个相同。把实现
    退回 `f{index:03d}` + `sorted(glob)`，这条当场红（反向验证过）。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    duration = 1500.0          # every=1.0 → 1499 格，足够越过一千那道坎
    stamps = reel.sheet_stamps(duration, every=1.0)
    assert len(stamps) > 1000, (
        f"样本只有 {len(stamps)} 格，够不着一千那道坎——这条判据会恒真")

    stamp_of: dict[str, float] = {}
    listings: list[list[str]] = []

    def fake_run(*args):
        args = [str(a) for a in args]
        if "-frames:v" in args and "-f" not in args:
            out = Path(args[-1])
            vf = next(a for a in args if "drawtext" in a)
            secs = float(re.search(r"drawtext=text='([\d.]+)s'", vf).group(1))
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"x")
            stamp_of[out.name] = secs
            return
        if "concat" in args:                       # 拼墙那一次
            listing = Path(args[args.index("-i") + 1])
            listings.append([
                line.split("'")[1].rsplit("/", 1)[-1]
                for line in listing.read_text(encoding="utf-8").splitlines()
                if line.strip()])
            Path(args[-1]).write_bytes(b"x")
            return
        raise AssertionError(f"没预料到的 ffmpeg 调用：{args[:6]}")

    monkeypatch.setattr(reel, "run", fake_run)
    monkeypatch.setattr(reel, "probe_duration", lambda _p: duration)

    sheets = reel.contact_sheet(tmp_path / "src.mp4", tmp_path / "out", every=1.0)
    assert sheets, "一张墙都没拼出来"

    order = [stamp_of[name] for sheet in listings for name in sheet]
    assert len(order) == len(stamps), (
        f"拼进墙里的格数 {len(order)} 和 sheet_stamps 算的 {len(stamps)} 对不上")
    assert order == stamps, (
        "墙上的格子不是按时间顺序排的——第一处对不上：" + next(
            f"第 {i} 格烧着 {a}s，应该是 {b}s"
            for i, (a, b) in enumerate(zip(order, stamps)) if a != b))


def test_推送链接的CDN主机只有一处出处不许再写死cdn域名(tmp_path, monkeypatch):
    """push_reel 里三处拼 jsDelivr 链接的地方（成片 video_url / 海报 poster_url /
    数据图 stat_card_url）原来都写死 `cdn.jsdelivr.net`——而 CLAUDE.md
    「CDN 主机名一个地方定」那节早把主机收进了 `tennislive/cdn.py`
    （默认 gcore 镜像，`TENNISLIVE_JSDELIVR_HOST` 可覆盖）。写死的三处等于把
    镜像开关废掉一半：校验和钉版本按 `.jsdelivr.net` 认（照常绿），链接却停在
    旧域名——**分叉不报错，只是国内取图慢**。

    两头钉，反向验证过两个方向、红在不同的断言行：
    ① 行为：三个 URL 构建器的主机必须跟着 `TENNISLIVE_JSDELIVR_HOST` 走
      （把 poster_url 退回写死的域名 → 这一头红）；
    ② 代码：push_reel.py 的 AST 里不许再出现含 `cdn.jsdelivr.net` 的字符串
      常量（往代码里塞一个 `_X = "cdn.jsdelivr.net"` → 只有这一头红，
      证明它不被 ① 覆盖）。⚠️ 用 AST 不用文本扫——教训注释里正写着这个
      域名（本文件反复栽过「判据扫得太宽，被自己的注释误伤」）；docstring
      也是记教训的地方，所以摘掉再扫。
    """
    import ast  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    # ① 行为：主机跟着环境变量走。conftest 的 autouse fixture 不管这个变量，
    #    所以显式设/删两档各验一次。
    monkeypatch.setenv("TENNISLIVE_JSDELIVR_HOST", "fastly.jsdelivr.net")
    outdir = tmp_path / "output" / "2026-08-21" / "reel" / "demo"
    outdir.mkdir(parents=True)
    (outdir / "demo.mp4").write_bytes(b"0" * 1024)  # 远小于 20 MB → 走 jsDelivr 支
    for built in (
        push_reel.video_url(outdir, "demo.mp4"),
        push_reel.poster_url(outdir),
        push_reel.stat_card_url(outdir),
    ):
        assert built.startswith("https://fastly.jsdelivr.net/gh/"), (
            f"链接没跟着 TENNISLIVE_JSDELIVR_HOST 走：{built}\n"
            "多半是有人把主机名又写死回了 push_reel.py——"
            "主机只有一处出处：tennislive/cdn.py 的 jsdelivr_base()")

    monkeypatch.delenv("TENNISLIVE_JSDELIVR_HOST")
    from tennislive.cdn import jsdelivr_host  # noqa: PLC0415
    default = jsdelivr_host()
    assert push_reel.poster_url(outdir).startswith(f"https://{default}/gh/"), (
        "不设环境变量时要落回 cdn.py 的默认镜像，而不是另一个写死的域名")

    # ② 代码：摘掉 docstring 之后，AST 里的字符串常量不许含 cdn.jsdelivr.net。
    src = Path("tools/push_reel.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    doc_ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (body and isinstance(node, (ast.Module, ast.FunctionDef,
                                       ast.AsyncFunctionDef, ast.ClassDef))
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            doc_ids.add(id(body[0].value))
    bad = [n.lineno for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str)
           and "cdn.jsdelivr.net" in n.value and id(n) not in doc_ids]
    assert not bad, (
        f"push_reel.py 第 {bad} 行又把 cdn.jsdelivr.net 写进了代码——"
        "主机名只许从 tennislive.cdn.jsdelivr_base() 来")

def test_握手后只许接固定品牌片尾():
    """握手结束比赛叙事；固定品牌页可以紧接其后，但不能再插比赛内容。"""
    spec = json.loads(Path(
        "specs/reels/zheng-burel-us-open-2026-q2.json"
    ).read_text(encoding="utf-8"))
    assert spec.get("outro", True) is not False, (
        "这条片握手后仍要保留固定“网球时差”品牌片尾")



def test_带式版式的段真的落在画面带里(tmp_path):
    """spec 顶层 `"layout": "band"`（美网记分条那轮定的，账见
    docs/us-open-scoreboard-aspect.md）：外框仍 1080×1440，段落改裁 9:8
    （1214×1080，2026-08-31 从 6:5 收窄）缩进画面带（1080×960、y=132 起），
    上下由带底色补齐——顶带给顶栏、底带给字幕，两样都不再压在画面上。

    **真跑一遍 cut_segment**（合成 1920×1080 纯白源片），两种版式都量像素：

    - band：顶带(y 30~100)和底带(y 1150~1350，画面带底边 1092 之下)近黑、
      画面带(y 560~640)是白的。
      查像素不查滤镜串——把 pad 换成别的写法照样得红
    - 默认（不写 layout）：同一批坐标全是白的。**全出血一个字节不许变**，
      这半张是回归钉：巡回赛片子不许被这次改动碰到

    反向验证过：把 `_canvas_fit()` 的 band 分支拆掉 → band 那半红在「上下带
    该近黑」；把默认分支也改成 band → full 那半红在「全出血被改了」。
    """
    import shutil  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    reel = _reel()
    src = tmp_path / "white.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=white:s=1920x1080:r=25", "-t", "0.6",
         "-pix_fmt", "yuv420p", str(src)], check=True)
    saved = (reel.CROP_W, reel.CROP_H, reel.CROP_Y, reel.LAYOUT)
    try:
        for layout in ("band", "full"):
            reel.resolve_crop(1920, 1080, None, "", layout=layout)
            seg = reel.Segment(start=0.0, end=0.4, cx=None, narration="",
                               track=False)
            seg.cx = 0.5
            out = tmp_path / f"seg_{layout}.mp4"
            reel.cut_segment(src, seg, out, 1920)
            frame = tmp_path / f"f_{layout}.png"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(out),
                 "-frames:v", "1", str(frame)], check=True)
            im = Image.open(frame).convert("L")
            assert im.size == (1080, 1440), f"{layout}: 画布变了 {im.size}"
            t = np.asarray(im.crop((0, 30, 1080, 100))).mean()
            m = np.asarray(im.crop((0, 560, 1080, 640))).mean()
            b = np.asarray(im.crop((0, 1150, 1080, 1350))).mean()
            assert m > 200, f"{layout}: 画面带该是白的，量到 {m:.0f}"
            if layout == "band":
                assert t < 60 and b < 60, (
                    f"band: 上下带该是带底色（近黑），量到 顶 {t:.0f} / 底 {b:.0f}"
                    "——pad 没画出来，字幕和顶栏就还压在画面上")
            else:
                assert t > 200 and b > 200, (
                    f"full: 全出血被改了（顶 {t:.0f} / 底 {b:.0f}）——"
                    "不写 layout 的巡回赛片子一个字节都不许变")
    finally:
        reel.CROP_W, reel.CROP_H, reel.CROP_Y, reel.LAYOUT = saved


def test_带式的字幕锚顶栏角标都进带_全出血原样(monkeypatch):
    """带式版式的三个「放到画面外/画面内」的落位，各钉一头（都反向验证过）：

    - 字幕默认锚：band 进底带（BAND_MARGIN_V=1124），full 仍是画面内 1284。
      `subtitle_top` 的人工覆盖不在这条判据里——那条口子归 render 里的读取
    - 顶栏滤镜：band 不画那层半透明 drawbox（顶带已是实色，画了会在
      y=126~132 露一道两色接缝）；full 照画（顶栏压在画面上要它保可读性）
    - inset 角标：band 贴**画面带**的四角（纵向各让开一条带），full 贴画布四角
    """
    reel = _reel()
    ins = {"image": "i.png", "corner": "tl", "animate": False}
    ins_bl = {"image": "i.png", "corner": "bl", "animate": False}
    pad = int(round(0.043 * reel.VIDEO_W))
    band_bot = reel.VIDEO_H - reel.BAND_TOP - reel.BAND_PIC_H

    monkeypatch.setattr(reel, "LAYOUT", "band")
    assert reel.default_margin_v() == reel.BAND_MARGIN_V
    assert reel.BAND_MARGIN_V == reel.BAND_TOP + reel.BAND_PIC_H + 32
    assert reel.BAND_TOP >= reel.TOPBAR_H, "顶栏落不进顶带"
    g = reel.topbar_filtergraph(1.2, 10.0, Path("t.ass"), Path("s.ass"))
    assert "drawbox" not in g, "带式的顶带已是实色，再画 drawbox 会露两色接缝"
    assert f"overlay={pad}:{reel.BAND_TOP + pad}" in reel._overlay_chain(
        "[0:v]null[base]", ins), "band 的 tl 角标要贴画面带顶角，不是画布顶角"
    assert f"H-h-{band_bot + pad}" in reel._overlay_chain(
        "[0:v]null[base]", ins_bl), "band 的 bl 角标要贴画面带底角"

    monkeypatch.setattr(reel, "LAYOUT", "full")
    assert reel.default_margin_v() == reel._REEL_MARGIN_V
    g2 = reel.topbar_filtergraph(1.2, 10.0, Path("t.ass"), Path("s.ass"))
    assert "drawbox" in g2, "全出血的顶栏要那层半透明黑保可读性"
    assert f"overlay={pad}:{pad}" in reel._overlay_chain(
        "[0:v]null[base]", ins), "全出血的角标落位不许被带式改动牵动"


def test_带式的品牌脚注真的渲出来而且只在带式(tmp_path, monkeypatch):
    """带式底带的品牌脚注（2026-08-31「下半部分黑的地方很多」那轮定的，账在
    docs/us-open-scoreboard-aspect.md 文末）。三头，缺一头都是恒真：

    - **条本身有墨**：`band_foot_strip` 真渲一条（球标 + 「网球时差 ·
      赛场之上」），透明底、有不透明像素——查文件在不在防不住「渲出来一张
      全透明的空条」
    - **真跑一遍滤镜图**：给了 `foot_input` 时脚注落在 BAND_FOOT_Y 竖直中心
      （白底源片上量非白像素）——只查滤镜串防不住 overlay 表达式写错
    - **不给 foot_input 的路一个字不变**：同一坐标带纯白。全出血和没脚注的
      带式不许被这条改动牵动

    反向验证过：把 `foot` 那截从滤镜图里拆掉 → 第二头红（脚注带全白）；
    把 BAND_FOOT_Y 挪到 1200 → 第二头红在「落错了行」；把 strip 的 fill
    改成全透明 → 第一头红。
    """
    import shutil  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    reel = _reel()

    strip = reel.band_foot_strip(tmp_path / "foot.png")
    im = Image.open(strip)
    arr = np.asarray(im)
    assert im.mode == "RGBA" and im.width > im.height, f"脚注条形状不对 {im.size}"
    assert (arr[..., 3] > 128).mean() > 0.05, "脚注条没有墨——渲出来是一张空透明图"

    # 极简 ASS（零对白）——滤镜图里那两次 subtitles 要真的能跑
    ass = tmp_path / "empty.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1440\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        "Style: X,Arial,20,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,"
        "0,0,1,0,0,2,10,10,10,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n", encoding="utf-8")
    src = tmp_path / "white.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=white:s=1080x1440:r=25", "-t", "1.0",
         "-pix_fmt", "yuv420p", str(src)], check=True)

    monkeypatch.setattr(reel, "LAYOUT", "band")
    foot_rows = (reel.BAND_FOOT_Y - 30, reel.BAND_FOOT_Y + 30)
    for case, extra, foot_in in (("with", ["-i", str(strip)], 2), ("without", [], None)):
        g = reel.topbar_filtergraph(0.2, 0.6, ass, ass, foot_input=foot_in)
        out = tmp_path / f"foot_{case}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-i", str(src),
             *extra, "-filter_complex", g, "-map", "[out]", "-frames:v", "12",
             str(out)], check=True)
        frame = tmp_path / f"foot_{case}.png"
        # 第 8 帧落在比赛区间（0.2s 封面之后），封面帧上本来就没有脚注
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", "0.3", "-i", str(out),
             "-frames:v", "1", str(frame)], check=True)
        band = np.asarray(Image.open(frame).convert("L").crop(
            (0, foot_rows[0], 1080, foot_rows[1])))
        dark = (band < 200).mean()
        if case == "with":
            assert dark > 0.005, (
                f"带式给了脚注输入，BAND_FOOT_Y={reel.BAND_FOOT_Y} 那一带"
                f"该有脚注的墨，量到暗像素占比 {dark:.4f}——overlay 没接上"
                "或落错了行")
            ctrl = np.asarray(Image.open(frame).convert("L").crop(
                (0, 1150, 1080, 1250)))
            assert (ctrl < 200).mean() < 0.001, "脚注糊到了字幕那一带"
        else:
            assert dark < 0.001, (
                f"没给脚注输入的路（全出血/无顶栏）不许有脚注，量到暗像素 "
                f"{dark:.4f}")


def test_常驻角标就是封面台头那一块_落位也是封面那个位置(tmp_path, monkeypatch):
    """账号所有者 2026-09-01：「**视频播放时候左上角保留网球时差的 logo**」，
    随后一句「**用封面上的 logo 和位置**」。

    ⚠️ 第二句推翻了第一版：那一版用的是横版 lockup（球标 ＋ 网球时差 ＋
    TENNIS JETLAG）贴在 (22, 22)——**另一个 logo、另一个位置**。现在是封面
    `.head` 那一块原样搬过来：球标 52 ＋ gap 14 ＋「网球时差 · 栏目」38px 得意黑，
    落在 `left:70 / top:44`。

    五头，**缺一头都是恒真**（六个方向分别反向验证过，各红在自己的断言行）：

    ① **和真封面逐像素对得上**——这一头是这条判据的主语，而且**判据拿的是真
       渲染器的输出**（`render_poster` 渲一张真海报），不是手搓一份 CSS 去比。
       球标的墨和字标的墨在封面上落在哪儿，角标贴在 `watermark_xy(0)` 就得落在
       哪儿（±2px）。手抄一份尺寸到别处、或者把 `BRAND_ICON_DROP_PX` 调回
       「和字标居中」，这一头当场红。

    ② **阴影是能压在任何画面上的前提，不是装饰。** 「网球时差」这几个字是近白的
       （`#f4fbf7`），压在**纯白**上（白球衣、亮天空、浅色看台）会整个消失。
       ⚠️ **封面那份 `text-shadow:0 2px 12px rgba(0,0,0,.6)` 不能照抄**——它依赖
       一个播放时不存在的前提（封面顶上那条带被 scrim 压暗着）。这正是本仓库
       记过的「抄了规则，没抄它依赖的前提」。

    ③ **纵向要让开顶部那条带。** 三种版式各让开各的（band 让开 BAND_TOP、
       全出血带顶栏让开 TOPBAR_H、没顶栏就是封面那个位置）。压上去**不报错**，
       只是角标和顶栏的字叠在一起。

    ④ **两条编码路都要接上，而且这一头是位置判据。** 没顶栏那条原来是
       `-vf subtitles=…` 一句话，`-vf` 只吃 0 号流、接不了第二路输入——所以它
       必须改走 `filter_complex` ＋ 显式 `[out]`。⚠️ 只测「有顶栏那条接上了」
       拦不住「没顶栏那条还是老样子」，而**网球有故事这个栏目走的正是没顶栏那条**。
       同一头还钉住 **一条链里不许有两个 `overlay=`**：写成
       `[a][2:v]overlay=…,[3:v]overlay=…` 时 ffmpeg 把标签**按顺序绑到那个滤镜
       自己的输入上**，于是 `[3:v]` 绑成了第二个 overlay 的**主画面**，角标当场
       变成画布。它响得很大声（concat 报 `Input link in0:v0 parameters … do not
       match`），**但那句话指的是 concat，读起来完全不像「overlay 的输入接反了」**。

    ⑤ **只盖比赛画面区间**，封面和片尾不带：封面自己就印着这一块，品牌片尾整屏
       就是这个 logo，两处再压一遍是把同一个标识说三遍。真跑一遍 ffmpeg 在三个
       时刻各量一帧——**查滤镜串里有没有 `enable=` 防不住区间写反**。

    ⚠️ 尺寸、阴影、几何**只有一处出处**（`src/tennislive/video/watermark.py`），
    赛后开麦那条线也从那儿拿；这条判据顺手钉住两个工具都不许自己再抄一份。
    """
    import shutil  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    reel = _reel()
    sys.path.insert(0, str(Path("src").resolve()))
    from tennislive.video import watermark as wm_mod  # noqa: PLC0415

    column, topic = "网球有故事", "台头底下那一行"
    png = wm_mod.brand_watermark(tmp_path / "wm.png", column, topic)
    art = Image.open(png).convert("RGBA")

    def lime_box(im, box):
        """品牌绿球标的墨。"""
        a = np.asarray(im.convert("RGB").crop(box), dtype=int)
        m = ((a[..., 1] > 150) & (a[..., 1] - a[..., 2] > 40)
             & (a[..., 1] - a[..., 0] > 15))
        ys, xs = np.where(m)
        assert len(xs), f"这一块里没有球标：{box}"
        return xs.min() + box[0], ys.min() + box[1]

    def ink_box(im, box):
        """近白字标的墨。"""
        a = np.asarray(im.convert("L").crop(box), dtype=float)
        ys, xs = np.where(a > 200)
        assert len(xs), f"这一块里没有字标：{box}"
        return xs.min() + box[0], ys.min() + box[1], xs.max() + box[0]

    # ── ① 和真封面逐像素对得上 ────────────────────────────────────────
    # **拿真渲染器渲一张真海报**——手搓一份 CSS 去比，验的是「我抄对了自己写的
    # 那份」，验不了「它和封面对不对得上」（本仓库为手搓 fixture 栽过一次）。
    poster = tmp_path / "poster.jpg"
    hero = tmp_path / "hero.jpg"
    Image.new("RGB", (1080, 1440), (14, 34, 24)).save(hero)
    try:
        reel.render_poster(
            {"eyebrow": column, "topic": "台头底下那一行",
             "subject": "大坂直美",
             "hook": "一件缝着旧报纸\n一件是旧球衣改的",
             "portrait": {"image": str(hero)}}, poster, "solo")
    except Exception as exc:                       # noqa: BLE001
        pytest.skip(f"渲不出封面（多半是没装 Chromium）：{exc}")
    cover_im = Image.open(poster)
    assert cover_im.size == (1080, 1440)

    # 角标贴在 `watermark_xy(0)`（没顶栏 ＝ 封面那个位置）
    monkeypatch.setattr(reel, "LAYOUT", "full")
    wx, wy = reel.watermark_xy(has_topbar=False)
    pasted = Image.new("RGB", cover_im.size, (0, 0, 0))
    pasted.paste(art, (wx, wy), art)

    # ⚠️ 球标要避开顶上那条 12px 彩虹条——它左端就是品牌绿，连它一起量会把
    # 球标的 bbox 拉到 x=0。
    icon_box = (0, 20, 200, 190)
    ci = lime_box(cover_im, icon_box)
    wi = lime_box(pasted, icon_box)
    assert abs(wi[0] - ci[0]) <= 2 and abs(wi[1] - ci[1]) <= 2, (
        f"球标没落在封面那个位置：封面 {ci}，角标 {wi}。"
        "「用封面上的 logo 和位置」——落位和封面逐像素对得上才算数")
    # ⚠️ **两行都要量**（账号所有者 2026-09-01「副标题不要消失啊」）：主行
    # y25~90、副标题 y90~140。只量第一行的话，第二行整个丢掉也照样绿——
    # 而那正是这条判据加这一头之前的样子。
    for what, text_box in (("主行", (130, 25, 620, 90)),
                           ("副标题", (130, 90, 620, 140))):
        ct = ink_box(cover_im, text_box)
        wt = ink_box(pasted, text_box)
        assert abs(wt[0] - ct[0]) <= 2 and abs(wt[1] - ct[1]) <= 2, (
            f"{what}没落在封面那个位置：封面 {ct[:2]}，角标 {wt[:2]}")
    ct = ink_box(cover_im, (130, 25, 620, 90))
    wt = ink_box(pasted, (130, 25, 620, 90))
    # ⚠️ 宽度按**比例**给余量，不给一个绝对像素数：PIL 量出来是个定值，而
    # Chromium 的排版**跨环境会差一点点**——同一份封面沙箱渲出来 304、CI 渲出来
    # **300**（run 33506517362 上真红过一次，绝对余量 3px 差一点）。这就是
    # CLAUDE.md 记过的「PIL 比 Chromium 稳定小 1~2px」，`SCORE_NAME_SLACK_PX`
    # 是同一件事。3% 拦得住它要拦的那一类：换掉得意黑量出来是 402 vs 304
    # （差 32%），反向验证过。
    cover_w, wm_w = ct[2] - ct[0], wt[2] - wt[0]
    assert abs(wm_w - cover_w) <= 0.03 * cover_w, (
        f"字标宽度和封面对不上（封面 {cover_w}，角标 {wm_w}，"
        f"差 {abs(wm_w - cover_w) / cover_w:.1%}）"
        "——多半是字体、字号或者 letter-spacing 抄漏了")

    # ── ② 阴影：贴在纯白上，字标那一带必须还有暗像素 ──────────────────
    on_white = Image.alpha_composite(
        Image.new("RGBA", art.size, (255, 255, 255, 255)), art)
    # 只看球标之后那一段——球标是绿的，天然和白底有对比，会把「字标看不看得见」
    # 这件事盖掉（反向验证时整幅量出来照样过）。
    x0 = wm_mod.WATERMARK_SHADOW_PAD + wm_mod.BRAND_ICON_PX + wm_mod.BRAND_GAP_PX
    word = np.asarray(on_white.convert("L").crop(
        (x0, 0, art.width, art.height)), dtype=float)
    assert word.min() < 150, (
        f"字标贴在纯白上最暗才 {word.min():.0f}——阴影没了，"
        "近白的「网球时差」在白球衣/亮天空上会整个消失")
    assert (word < 200).mean() > 0.05, (
        f"字标那一带暗像素只占 {(word < 200).mean():.4f}，阴影太淡撑不住白底")

    # ── ③ 纵向让开顶栏 ──────────────────────────────────────────────
    for layout, has_topbar, occupied in (
            ("band", True, reel.BAND_TOP),
            ("full", True, reel.TOPBAR_H),
            ("full", False, 0)):
        monkeypatch.setattr(reel, "LAYOUT", layout)
        x, y = reel.watermark_xy(has_topbar=has_topbar)
        assert x == wm_mod.WATERMARK_LEFT - wm_mod.WATERMARK_SHADOW_PAD, (
            f"{layout}/{has_topbar}: 横向不是封面的 left:{wm_mod.WATERMARK_LEFT}")
        assert y >= occupied, (
            f"{layout}/topbar={has_topbar}: 角标 PNG 顶边在 y={y}，"
            f"而顶部那条带占到 {occupied}——连阴影都要落在带外面，"
            "压上去不报错，只是和顶栏的字叠在一起")
        assert y - occupied == wm_mod.WATERMARK_TOP - wm_mod.WATERMARK_SHADOW_PAD, (
            f"{layout}/topbar={has_topbar}: 让开之后不是封面的 "
            f"top:{wm_mod.WATERMARK_TOP}（阴影那一圈没减掉，或者减了两遍）")
    # 赛后开麦那条线让开的是它自己的 VIDEO_TOP，出处是同一个函数
    assert wm_mod.watermark_xy(150) == (wx, 150 + wy)

    # ── ④ 位置：两条编码路都接上，而且不许一条链里两个 overlay ────────
    src = Path("tools/build_match_reel.py").read_text("utf-8")
    assert '"-vf", f"subtitles=' not in src, (
        "没顶栏那条路还在用 `-vf subtitles=`——`-vf` 只吃 0 号流，"
        "接不了角标那一路输入，于是网球有故事这个栏目的片子没有角标")
    body = inspect.getsource(reel.render)
    assert "plain_filtergraph(" in body and "wm_input=wm_input" in body, (
        "render 里两条编码路没有都把角标接进去")
    monkeypatch.setattr(reel, "LAYOUT", "full")
    plain = reel.plain_filtergraph(Path("s.ass"), 0.4, 1.0, 2)
    assert "[out]" in plain and "[2:v]overlay=" in plain and "enable=" in plain, (
        f"没顶栏那条滤镜图不完整：{plain}")
    bar = reel.topbar_filtergraph(0.4, 0.6, Path("t.ass"), Path("s.ass"),
                                  foot_input=2, wm_input=3)
    assert "[3:v]overlay=" in bar, "有顶栏那条没把角标接进去"
    for chain in bar.split(";"):
        assert chain.count("overlay=") <= 1, (
            f"一条链里出现两个 overlay：{chain}\n"
            "ffmpeg 会把 `[3:v]` 绑成第二个 overlay 的主画面，"
            "角标当场变成画布——报错指着 concat，读起来完全不像这回事")

    # ── ⑤ 只盖比赛区间：真跑一遍，三个时刻各量一帧 ────────────────────
    ass = tmp_path / "empty.ass"
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1440\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
        "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        "Style: X,Arial,20,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,"
        "0,0,1,0,0,2,10,10,10,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n", encoding="utf-8")
    white = tmp_path / "white.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=white:s=1080x1440:r=25", "-t", "1.4",
         "-pix_fmt", "yuv420p", str(white)], check=True)

    cover_secs, match_secs = 0.4, 0.6
    cases = {
        "有顶栏": (reel.topbar_filtergraph(
            cover_secs, match_secs, ass, ass, wm_input=2),
            reel.watermark_xy(has_topbar=True)),
        "没顶栏": (reel.plain_filtergraph(
            ass, cover_secs, cover_secs + match_secs, 2),
            reel.watermark_xy(has_topbar=False)),
    }
    for name, (graph, (px, py)) in cases.items():
        out = tmp_path / f"wm_{len(name)}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(white), "-i", str(white),
             "-i", str(png), "-filter_complex", graph, "-map", "[out]",
             "-pix_fmt", "yuv420p", str(out)], check=True)
        seen = {}
        for label, at in (("封面", 0.2), ("比赛", 0.7), ("片尾", 1.2)):
            frame = tmp_path / f"{len(name)}_{label}.png"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", str(out),
                 "-frames:v", "1", str(frame)], check=True)
            box = np.asarray(Image.open(frame).convert("L").crop(
                (px, py, px + art.width, py + art.height)), dtype=float)
            seen[label] = float((box < 235).mean())
        assert seen["比赛"] > 0.05, (
            f"{name}：比赛画面上没有角标（左上角非白像素占 "
            f"{seen['比赛']:.4f}）——overlay 没接上或落错了位置")
        for label in ("封面", "片尾"):
            assert seen[label] < 0.005, (
                f"{name}：{label}那一段也压了角标（{seen[label]:.4f}）。"
                "封面自己就印着这一块、品牌片尾整屏都是这个 logo，再压一遍是说三遍")

    # ── 出处只有一份：两个工具都不许自己再抄一份尺寸/阴影 ──────────────
    itw = Path("tools/build_interview_clip.py").read_text("utf-8")
    for path, text in (("build_match_reel.py", src),
                       ("build_interview_clip.py", itw)):
        assert "from tennislive.video.watermark import" in text, (
            f"{path} 没从共享模块拿角标——两条线各配一份的样子是"
            "「同一个账号出去的片子 logo 一大一小」，而且不报错")
        assert not re.search(r"^\s*(WATERMARK|BRAND_ICON|BRAND_GAP|BRAND_TEXT)_"
                             r"\w*\s*=", text, re.M), (
            f"{path} 里自己定义了角标的常量——出处只许有一处")


def test_layout只认band且band不和contain混():
    """spec.layout 的值域和兼容性，`--dry-run`（parse_segments）就拦：

    - 只认 "band"；写错值当场报，别静默当成全出血渲出去（那样「写错了」和
      「没写」长得一模一样）
    - band × `fit: contain` 拒掉：带式的画面带本来就是 9:8 宽画幅，contain
      要解决的「两个人分得很开」它本来就装得下
    - band 要求源片装得下 9:8 窗口（resolve_crop 那道，方形/竖版源直接拒）
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    base_seg = [{"start": 1, "end": 7, "source": "r1"}]
    ok = {"cover": {}, "layout": "band", "segments": list(base_seg)}
    assert reel.parse_segments(ok, {"r1": Path("a.mp4")}, "r1")

    with pytest.raises(reel.ReelError, match="layout"):
        reel.parse_segments({"cover": {}, "layout": "wide",
                             "segments": list(base_seg)},
                            {"r1": Path("a.mp4")}, "r1")

    with pytest.raises(reel.ReelError, match="contain"):
        reel.parse_segments(
            {"cover": {}, "layout": "band",
             "segments": [{"start": 1, "end": 7, "source": "r1",
                           "fit": "contain"}]},
            {"r1": Path("a.mp4")}, "r1")

    saved = (reel.CROP_W, reel.CROP_H, reel.CROP_Y, reel.LAYOUT)
    try:
        with pytest.raises(reel.ReelError, match="9:8"):
            reel.resolve_crop(1080, 1080, None, "", layout="band")
    finally:
        reel.CROP_W, reel.CROP_H, reel.CROP_Y, reel.LAYOUT = saved


def test_记分条按实际大小裁原比例贴回左下角(tmp_path, capsys):
    """带式窗口**居中**（「不要偏离中心的」），美网那条浮在左下的板会被窗口
    左缘裁掉名字——`score_inset` 从同一帧把整条板抠出来，**按原比例**贴回
    左下、纵坐标不动。

    ⭐ 2026-08-28 这块地方被账号所有者点了四次，最后一句定了型：「根据比分板
    实际大小剪切然后贴到左下角，纵坐标不变」。中间试过、被否掉的两条也钉在
    这条判据里，别再走一遍：

      ① 缩到残条宽（一寸球场都不多占）→ 板只有画面宽的 27%，按手机尺寸
         渲出来是一条读不出字的深色块——「马赛克」
      ② 干脆不贴 → 比分清楚了，但名字被画面左缘裁掉——「比分板没展示全」

    判据**真跑 ffmpeg 量像素**，不查滤镜串。合成源片在板的位置画四截色块——
    绿 [104,360]、红 [360,616]、蓝 [616,736]（蓝＝深盘长出来的比分列），
    外加**品红 [736,944]**：那一截是板右边的**球场**。三条断言各钉一头：

    ① 被裁掉的板左半（绿）要贴回来——不贴的对照组那儿只有红
    ② 贴片是**原比例**：蓝列必须落在 (616−104)×0.8896≈455 到 562，
       缩过就不在那儿了（这一条钉的是「不许再缩」）
    ③ `x1` 按板的真实右缘写时，板右边的球场（品红）**不许**被抠进贴片；
       写宽到 944 时它就会被贴到画面上另一个位置——那正是要防的

    反向验证过：把 scale 换回缩到残条宽 → ② 红；把 x1 放宽到 944 → ③ 红；
    把 overlay 落点的 BAND_TOP 拿掉 → ① 红（贴错了行盖不住采样区）。
    """
    import shutil  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    reel = _reel()
    src = tmp_path / "board.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=white:s=1920x1080:r=25,"
         "drawbox=x=104:y=888:w=256:h=90:color=green:t=fill,"
         "drawbox=x=360:y=888:w=256:h=90:color=red:t=fill,"
         "drawbox=x=616:y=888:w=120:h=90:color=blue:t=fill,"
         "drawbox=x=736:y=888:w=208:h=90:color=magenta:t=fill",
         "-t", "0.6", "-pix_fmt", "yuv420p", str(src)], check=True)

    def _mean_rgb(frame: Path, box: tuple[int, int, int, int]):
        arr = np.asarray(Image.open(frame).convert("RGB").crop(box), float)
        return arr[..., 0].mean(), arr[..., 1].mean(), arr[..., 2].mean()

    saved = (reel.CROP_W, reel.CROP_H, reel.CROP_Y, reel.LAYOUT)
    try:
        reel.resolve_crop(1920, 1080, None, "", layout="band")
        # 采样区（画布坐标），按 9:8 的缩放比 1080/1214≈0.8896 排：
        # 贴片原比例：板 [104,736] → 画面带 [0,562]，纵向 y∈[922,1002]
        # （源片 888×0.8896 + 顶带 132）。
        green_box = (20, 940, 110, 990)     # 板的左半：窗口自己看不见的那截
        blue_box = (465, 940, 522, 988)     # 深盘那几列，落在原比例该在的位置
        court_box = (580, 940, 680, 990)    # 板右边的球场（品红）该在的地方
        for case in ("real", "toowide", "off"):
            box = {"real": (104, 888, 736, 978),
                   "toowide": (104, 888, 944, 978),
                   "off": None}[case]
            seg = reel.Segment(start=0.0, end=0.4, cx=0.5, narration="",
                               track=False, score_inset=box)
            out = tmp_path / f"seg_{case}.mp4"
            reel.cut_segment(src, seg, out, 1920)
            frame = tmp_path / f"f_{case}.png"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", str(out),
                 "-frames:v", "1", str(frame)], check=True)
            r, g, b = _mean_rgb(frame, green_box)
            if case == "off":
                assert r > 150 and g < 90, (
                    f"不贴的对照组那儿该只剩红（板的左半在窗外），量到 "
                    f"RGB=({r:.0f},{g:.0f},{b:.0f})——对照组不成立的话，"
                    "下面那半张绿的证明不了回贴")
                rb, gb, bb = _mean_rgb(frame, blue_box)
                assert rb > 110 and bb > 110 and gb < 90, (
                    f"不贴时 465~522 那一带是**球场**（品红，源片 876~940），"
                    f"量到 RGB=({rb:.0f},{gb:.0f},{bb:.0f})——这一头不成立的话，"
                    "②量到的蓝就可能本来就在那儿，证明不了贴片是原比例")
                continue
            assert g > 90 and r < 80, (
                f"① {case}: 被裁掉的板左半（绿）要贴回来，量到 "
                f"RGB=({r:.0f},{g:.0f},{b:.0f})")
            rb, gb, bb = _mean_rgb(frame, blue_box)
            assert bb > 90 and rb < 80, (
                f"② {case}: 贴片要**原比例**——深盘那几列（蓝）该落在 "
                f"455~562，量到 RGB=({rb:.0f},{gb:.0f},{bb:.0f})。"
                "缩过（比如缩到残条宽）它就不在这儿了，而缩完的板在手机上"
                "读不出字，账号所有者管那叫「马赛克」")
            rc, gc, bc = _mean_rgb(frame, court_box)
            if case == "real":
                assert min(rc, gc, bc) > 200, (
                    f"③ x1 按板的真实右缘写时，贴片到 562 就结束了，"
                    f"这儿该是主窗口的白，量到 ({rc:.0f},{gc:.0f},{bc:.0f})")
            else:
                assert rc > 110 and bc > 110 and gc < 90, (
                    f"③ x1 写宽到 944 时，板右边的**球场**（品红）被抠进贴片、"
                    f"贴到了画面上另一个位置，量到 "
                    f"RGB=({rc:.0f},{gc:.0f},{bc:.0f})——这一条画的就是"
                    "「要按板的实际大小裁」没做到时的样子，不是要修的 bug")

        # 窗口左缘没越过板左缘时**跳过回贴并出声**（贴了反而叠重影）
        seg = reel.Segment(start=0.0, end=0.4, cx=0.36, narration="",
                           track=False, score_inset=(104, 888, 616, 978))
        reel.cut_segment(src, seg, tmp_path / "skip.mp4", 1920)
        assert "跳过回贴" in capsys.readouterr().out, (
            "窗口本来就含住整条板时要跳过回贴并说一声——"
            "不吭声的话「贴了」和「不用贴」在日志上一样")
    finally:
        reel.CROP_W, reel.CROP_H, reel.CROP_Y, reel.LAYOUT = saved


# ⭐⭐ 走**烧进片子**那条路的 spec。账号所有者 2026-08-29 在两条路里选了
# 「平台曲库」——成片不带音乐，上传视频号／抖音之后在它们自己的曲库里加。
# 所以这张表**现在是空的**，加一条就是一次看得见的决定（要自己解决授权，
# 而且那份授权只对这个号成立）。整段账在 CLAUDE.md
# 「背景音乐走平台曲库，不烧进片子」。
_MUSIC_BURNED_IN: set[str] = set()


def test_背景音乐默认走平台曲库不烧进片子():
    """账号所有者 2026-08-29：在「A 烧进片子 / B 平台曲库」两条路里选了 **B**。

    B 的形状是：成片一路**不带音乐**，上传视频号／抖音之后在**平台自己的
    曲库**里加 BGM——不用重渲、不用自己找授权，而那份授权是平台拿的
    （视频号的曲库由 QQ 音乐供）。⚠️ 抖音那份是「限站内自用」，所以 B 是把
    风险压得很低，不是压到零，也不跟着片子换平台走。

    混音那套实现（`music_chain` / `music_problem` / `MUSIC_GAIN_PCT`）**留着
    不删**——它是 A 的现成能力。可留着的东西会被下一个人当成「可以顺手打开的
    开关」，而这条线默认根本不该走到那儿。所以这条判据钉两头：

    ① 存量一条 spec 都不许带 `music`（真要走 A，先把 slug 加进
       `_MUSIC_BURNED_IN`——那一刻就是一次看得见的决定，不是手滑）
    ② 缺 `_license` 时的报错要**先说 B 那条路**：十有八九「补上这个字段」
       是错的答案，「不加音乐」才是。只教人补字段的报错会把人推去找授权

    ⚠️ 豁免表自己也要有判据（这个仓库里「写错一个名字，豁免就成了一盏恒真的
    绿灯」栽过），所以表里每个 slug 必须真的存在、真的还带着 `music`。
    """
    reel = _reel()

    burned = set()
    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if spec.get("music") is not None:
            burned.add(path.stem)
    assert burned <= _MUSIC_BURNED_IN, (
        f"这几条 spec 把背景音乐烧进了片子：{sorted(burned - _MUSIC_BURNED_IN)}。\n"
        "账号所有者 2026-08-29 选的是「平台曲库」那条路——成片不带音乐，"
        "上传视频号／抖音之后在它们自己的曲库里加。真要走烧进片子那条，"
        "先把 slug 加进 _MUSIC_BURNED_IN 并写清授权来路。")
    assert _MUSIC_BURNED_IN <= burned, (
        f"豁免表里这几个 slug 已经不带 music 了：{sorted(_MUSIC_BURNED_IN - burned)}。"
        "一个过期的豁免就是一盏恒真的绿灯，删掉它。")

    problem = reel.music_problem({"music": {"file": "tools/build_match_reel.py"}})
    assert problem and "曲库" in problem, (
        "缺 `_license` 的报错要先把「平台曲库」那条路说出来——只教人补字段，"
        f"读的人会去找授权，而正确答案多半是「不加」。实际报的是：{problem!r}")


def test_板的右缘按每一段实际的宽度现量不是写死三档(tmp_path, capsys):
    """⭐ 账号所有者 2026-08-29：「比分板的宽度会变化的，所以不能固定宽度去切，
    要自适应。」

    在这之前右缘是**手量三档写进 spec** 的（美网的板每打完一盘 +38px：这条
    片子实测一盘 583、二盘 618、决胜盘 656）——每条新片子都要把成片拉回本地
    逐帧放大读边框，而这个仓库反复说过「修法不是提醒自己下次记得抄，是把
    手抄这一步去掉」。现在 `resolve_board_insets` 在渲染时逐段现量。

    判据**真跑 ffmpeg 量像素**，合成源片里让板在三个时间段是三种宽度，
    右端各带一格**白色**小分（那正是真板的样子）：

    ① 三段各自量到自己那一档，不是三段都退回顶层 scorebox 的最宽值
    ② **白格要算进板里**——按「暗块」找边缘会在深蓝底结束处就停下，实测
       少 53px（2026-08-28 手量时踩过一次）。这一条钉的就是白格没被漏掉
    ③ 板整段不在画面里（回放/切走）时退回 spec 的兜底右缘**并出声**——
       「量不出来」和「量出来就是这么宽」在产物上分不出来
    ④ 留了余量往**宽**里去，永远不许裁窄：裁窄是**静默**的失败（最右那几列
       比分被贴片藏在自己底下，没有任何闸会响），裁宽只是多盖几像素球场
    ⑤ ⭐⭐ **scorebox 的高度是奇数也要量得出来**（2026-08-31 德约那条整趟
       量空换来的）：spec 写 y∈[887,980]（高 93），yuv420p 上 crop 奇数高度
       被 ffmpeg 静默舍成偶数，每帧少一行、字节数不足，「不足就当没抓到」的
       守卫把 60/60 帧全判成 None——十个段全部退回最宽兜底，成片里每一段的
       贴片都是固定 528px，第一盘白盖一大截球场。修法是 `format=rgb24` 排在
       crop 前面。**这条测试的合成几何因此故意用奇数**（y0=887、高 93），
       偶数几何量不出这个坑（zheng-burel 的 [888,978] 高 90 就是这么全绿的）

    反向验证过四个方向：**不现量**（一律退回顶层 scorebox）→ ① 红；
    **只认暗块**（`hit` 上再加一条「亮度 < 120」，白格就被漏掉）→ 也红在 ①
    的区间断言上，报出来是「量到 552，该在 584~596」——那 40px 正是白格，
    实测那个坑少 53px；**把量不出来那一支的 print 拆掉** → ③ 红；
    **把 `format=rgb24,` 从滤镜链里拿掉** → ⑤ 让 ① 当场红（三段全退回 660，
    正是线上那次的样子）。
    """
    import shutil  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    reel = _reel()
    src = tmp_path / "board.mp4"
    # 板：深蓝底 + 右端一格白色小分。三档右缘 584 / 619 / 657，
    # 而**深蓝底**分别只到 544 / 579 / 617——白格宽 40。
    # ⚠️ y=887、高 93 是故意的奇数（见 docstring ⑤），别「顺手」改成偶数。
    plates = []
    for k, (dark_end, white_end, lo, hi) in enumerate(
            [(544, 584, 0, 2), (579, 619, 2, 4), (617, 657, 4, 6)]):
        on = f"between(t,{lo},{hi})"
        plates.append(f"drawbox=x=104:y=887:w={dark_end - 104}:h=93:"
                      f"color=0x1B2A5E:t=fill:enable='{on}'")
        plates.append(f"drawbox=x={dark_end}:y=887:w={white_end - dark_end}:h=93:"
                      f"color=white:t=fill:enable='{on}'")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
         "color=c=0x6E8B6E:s=1920x1080:r=25," + ",".join(plates),
         "-t", "8", "-pix_fmt", "yuv420p", str(src)], check=True)

    box = (104, 887, 660, 980)          # 顶层 scorebox：这场最宽那一档 + 兜底
                                        # ⚠️ 高 93（奇数）是判据 ⑤ 的主语
    segs = [reel.Segment(start=lo, end=hi, cx=0.5, narration="", track=False,
                         score_inset=box, score_inset_auto=True)
            for lo, hi in [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0), (6.0, 8.0)]]
    reel.resolve_board_insets({"": src}, segs)
    out = capsys.readouterr().out
    got = [s.score_inset[2] for s in segs]

    for i, (want, seg) in enumerate(zip([584, 619, 657], segs[:3])):
        assert want <= seg.score_inset[2] <= want + reel.BOARD_EDGE_PAD + 4, (
            f"① 第 {i + 1} 段该量到自己那一档（板右缘 {want}，留余量往宽里去），"
            f"量到 {seg.score_inset[2]}。三段一样宽就说明它没在现量、"
            f"退回了顶层的 {box[2]}——那正是被账号所有者点掉的「固定宽度去切」。"
            f"\n{out}")
        assert seg.score_inset[2] >= want, (
            f"④ 第 {i + 1} 段裁窄了（{seg.score_inset[2]} < {want}）——"
            "裁窄会把最右那几列比分藏在贴片底下，而且一声不吭")

    assert len(set(got[:3])) == 3, (
        f"① 三段量出来该是三个不同的宽度（板每盘 +38px），拿到 {got[:3]}")
    assert got[0] > 544 + 20, (
        f"② 白色小分格要算进板里——量到 {got[0]}，而深蓝底只到 544。"
        "按「暗块」找边缘会在这儿停下，实测少 53px（2026-08-28 手量时踩过）")

    assert segs[3].score_inset[2] == box[2] and "量不出板的右缘" in out, (
        "③ 板不在画面里的那一段要退回 spec 的兜底右缘**并出声**——"
        f"不吭声的话「量不出来」和「板就这么宽」分不出来。实际：{out}")


def test_板右缘抓帧短读要单独出声不许装成板不在(monkeypatch, capsys):
    """「抓帧短了」和「板不在画面里」在返回值上是同一个 None——而 2026-08-31
    德约那条正是把前者读成了后者（奇数高度被 ffmpeg 舍行、60/60 帧短读，
    日志却说「板可能整段不在画面里（回放/切走）」），十个段静默退回最宽兜底。

    钉两头：短读的帧照样返回 None（下游按「量不出」处理，兜底不变），
    **但必须单独出声**、点名是抓帧失败——不吭声的话下一个人会照着
    「回放/切走」去把 score_inset 改成 false，把真板也一起关掉。

    反向验证过：把 board_right_edges 里那句短读的 print 拆掉 → 红在「出声」
    那一条断言上。
    """
    reel = _reel()
    monkeypatch.setattr(reel, "probe_size", lambda _p: (1920, 1080))

    class _Short:
        stdout = b"\x00" * 100          # 远小于 bw*bh*3——短读

    edges = reel.board_right_edges(
        Path("no-such.mp4"), (104, 887, 736, 980), [1.0, 2.0],
        runner=lambda *a, **k: _Short())
    out = capsys.readouterr().out
    assert edges == [(1.0, None), (2.0, None)], (
        f"短读的帧要按「量不出」返回 None（下游退兜底），拿到 {edges}")
    assert "抓取不完整" in out and "板不在画面里" not in out.replace(
        "不是「板不在画面里」", ""), (
        "短读必须单独出声、点名是抓帧失败——和「板不在（回放/切走）」混成"
        f"一句话，下一个人就会去把真板的 score_inset 关掉。实际输出：{out!r}")


def test_量不出的段按时间单调性从邻段补不再退最宽兜底(tmp_path, monkeypatch, capsys):
    """⭐⭐ 账号所有者 2026-08-31：「现在固定长度不太合适啊，会截取太多空的
    画面遮挡了真实画面」「以后所有赛场之上视频都能做到自适应裁切比分么」。

    某一段自己量不出（特写做背景、球员贴板——德约那条第 4 段的真实形状：
    6 帧散在 892~1608 各一票）时，原来退回 spec 的最宽兜底 736：十个段里
    九个自适应、一个贴最宽的空板，还是「固定长度」，而自动链上没有人去手工
    钉 `{"x2": N}`。同一条源片是按时间顺序剪的集锦，板每打完一盘 +38px、
    **从不变窄**，所以「后面段可信读数的最小值」是本段真宽的安全上界。钉四头：

    ① 可信段（两票起步）照旧按自己的读数裁——自适应的主路不动，可信读数
       永远不被邻段改写（互相钳制会成环）
    ② 只有孤票的段 → 用后面段可信读数的最小值，**不是**最宽兜底 736，
       也**不是**那张孤票（噪声 1400）
    ③ 补齐用的是**后面段**的下确界（上界，偏宽安全）——用前面段补会在
       「中间正好打完一盘」时把新长出来的比分列藏在贴片底下，静默失败
    ④ 后面也没有可信读数的段照旧退最宽兜底**并出声**（老行为不变）

    反向验证过两个方向：把 `_later_floor` 那一支拆掉 → ② 红（拿到 736）；
    把「后面段的最小值」换成「前面段的最大值」 → ②/③ 红（拿到 544，裁窄）。
    """
    import numpy as np  # noqa: PLC0415

    reel = _reel()
    monkeypatch.setattr(reel, "probe_size", lambda _p: (1920, 1080))
    box = (104, 887, 736, 980)              # 高 93——奇数几何照旧
    x0, _y0, _x1, y1 = box
    bw, bh = 1920 - x0, y1 - box[1]
    court = np.array([110, 150, 110], np.uint8)

    def band_with_edge(src_edge):
        b = np.tile(court, (bh, bw, 1))
        b[:, :src_edge - x0] = (20, 35, 90)
        return b

    # 「花屏」：每一列都离球场参考色很远 → 检测一路走到带尾 → 这一帧 None
    clutter = np.zeros((bh, bw, 3), np.uint8)
    clutter[:, 0::2] = (250, 20, 20)
    clutter[:, 1::2] = (20, 20, 250)

    def runner(cmd, capture_output=True, check=False):
        t = float(cmd[cmd.index("-ss") + 1])
        if t < 2.0:
            band = band_with_edge(536)                     # 第一盘，可信 ×6
        elif t < 4.0:
            # 德约 seg4 的形状：五帧花屏 + 一张孤票宽噪声（球员贴板那种）
            band = band_with_edge(1400) if 3.4 < t < 3.6 else clutter
        elif t < 6.0:
            band = band_with_edge(616)                     # 第二盘，可信 ×6
        else:
            band = clutter                                 # 量不出且后面没有
        class _R:
            stdout = band.tobytes()
        return _R()

    src = tmp_path / "stub.mp4"
    src.write_bytes(b"x")
    segs = [reel.Segment(start=a, end=b, cx=0.5, narration="", track=False,
                         score_inset=box, score_inset_auto=True)
            for a, b in [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0), (6.0, 8.0)]]
    reel.resolve_board_insets({"": src}, segs, runner=runner)
    out = capsys.readouterr().out

    pad = reel.BOARD_EDGE_PAD
    assert segs[0].score_inset[2] == 536 + pad, (
        f"① 可信段要按自己的读数裁，拿到 {segs[0].score_inset[2]}\n{out}")
    assert segs[2].score_inset[2] == 616 + pad, (
        f"① 可信段要按自己的读数裁，拿到 {segs[2].score_inset[2]}\n{out}")
    assert segs[1].score_inset[2] == 616 + pad, (
        f"② 孤票段该按时间单调性拿后面段可信读数的最小值 616（安全上界），"
        f"拿到 {segs[1].score_inset[2]}。736 就是被账号所有者点掉的「固定长度"
        f"贴最宽空板」；544 是拿前面段补（③ 裁窄，会藏比分列）；1408 是把"
        f"孤票噪声当了真。\n{out}")
    assert "单调性" in out, f"补齐要出声说明来路，不然读日志的人以为量到了：{out}"
    assert segs[3].score_inset[2] == box[2] and "量不出板的右缘" in out, (
        f"④ 后面没有可信读数的段照旧退最宽兜底并出声。\n{out}")


def test_板右缘的取值规则两票起步且取最宽():
    """`segment_board_edge` 的取值规则，钉三头（不用跑 ffmpeg，秒级）。

    ① **取最宽**：裁窄了是**静默**的失败（最右那几列比分被贴片藏在自己底下，
       没有任何闸会响），裁宽了只是多盖几像素球场，看得见、而且被调用方按
       spec 的 scorebox 封了顶。所以板在一段中途长了一列时按宽的裁
    ② **两票起步**：只取最宽的话噪声会被一起取上。这条片子的 104 格记分条
       缩略图墙实测——82 格量到板、三大簇占 72 格，剩下 10 格是散的，而其中
       635/640/650/700 那几格正好读得比真值宽。一段采 6 帧，真值拿 5~6 票、
       噪声拿 1 票，「两票」把它们分得很干净（真跑过：第 4 段那个 636、
       第 5 段那个 700 都被挡掉了，两段都正确落在 580）
    ③ **直方图要给出来**：两簇就说明板在这一段中途长过，人才知道要不要拆段

    反向验证过：把「两票」放宽到一票 → ② 红（噪声被取中）；把 max 改成 min
    → ① 红；不返回直方图 → ③ 红。
    """
    reel = _reel()
    noisy = [(0.0, 584), (1.0, 583), (2.0, 585), (3.0, 584), (4.0, 650)]
    edge, hist = reel.segment_board_edge(noisy)
    assert edge is not None and 583 <= edge <= 585, (
        f"② 只有一票的 650（球员贴着板走过那种）不该被取中，拿到 {edge}；"
        f"直方图 {hist}")
    edge2, hist2 = reel.segment_board_edge(
        [(0.0, 584), (1.0, 584), (2.0, 619), (3.0, 619), (4.0, 620)])
    assert edge2 is not None and edge2 >= 619, (
        f"① 板在这一段中途长了一列、两档都有两票以上时要按**宽的**裁"
        f"（裁窄会静默藏掉比分列），拿到 {edge2}")
    assert len(hist2) >= 2, "③ 两簇要在直方图里看得见，人才知道要不要拆段"
    assert reel.segment_board_edge([(0.0, None), (1.0, None)])[0] is None
    # 一票都撑不起两票时退回最宽的那一帧（段太短、采样点大半落在切走的镜头上）
    assert reel.segment_board_edge([(0.0, 516), (1.0, 652)])[0] == 652


def test_score_inset的形状校验和scorebox的死键闸(capsys):
    """`score_inset` / `scorebox` 的形状规矩全在 parse_segments（--dry-run
    0.2 秒就报，不用等下载）：

    - score_inset 只在带式里有意义；带式外写了当场报（不是静默不生效）
    - 开了 score_inset 就必须有 spec 顶层 scorebox（格式 [x0,y0,x1,y1]）
    - scorebox 写在非带式 spec 里是死键，当场报
    - `{"x2": N}` 把这一段的板右缘**钉死**，解析成 (x0,y0,N,y1)。⭐ 它退成
      「现量不准时人来钉」的口子了——主路是 `true`＋渲染时现量
      （`resolve_board_insets`，账号所有者 2026-08-29：「不能固定宽度去切，
      要自适应」）
    - **没开回贴的段要逐段点名**（只报不拦）：带式的居中窗口会把板的名字裁掉，
      所以比赛画面的段都该开；回放/切走的段不开是对的，机器分不出这两种，
      漏开的样子（左下一截被裁掉名字的板）在 --dry-run 里要看得见
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    srcs = {"r1": Path("a.mp4")}
    box = [104, 888, 616, 978]

    with pytest.raises(reel.ReelError, match="score_inset"):
        reel.parse_segments(
            {"cover": {}, "segments": [
                {"start": 1, "end": 7, "source": "r1", "score_inset": True}]},
            srcs, "r1")
    with pytest.raises(reel.ReelError, match="scorebox"):
        reel.parse_segments(
            {"cover": {}, "layout": "band", "segments": [
                {"start": 1, "end": 7, "source": "r1", "score_inset": True}]},
            srcs, "r1")
    with pytest.raises(reel.ReelError, match="死键"):
        reel.parse_segments(
            {"cover": {}, "scorebox": box,
             "segments": [{"start": 1, "end": 7, "source": "r1"}]},
            srcs, "r1")
    with pytest.raises(reel.ReelError, match="scorebox"):
        reel.parse_segments(
            {"cover": {}, "layout": "band", "scorebox": [104, 888, 616],
             "segments": [{"start": 1, "end": 7, "source": "r1"}]},
            srcs, "r1")
    with pytest.raises(reel.ReelError, match="x2"):
        reel.parse_segments(
            {"cover": {}, "layout": "band", "scorebox": box, "segments": [
                {"start": 1, "end": 7, "source": "r1",
                 "score_inset": {"x2": 80}}]},
            srcs, "r1")

    segs = reel.parse_segments(
        {"cover": {}, "layout": "band", "scorebox": box, "segments": [
            {"start": 1, "end": 7, "source": "r1", "score_inset": True},
            {"start": 7, "end": 12, "source": "r1",
             "score_inset": {"x2": 655}},
            {"start": 12, "end": 15, "source": "r1"}]},
        srcs, "r1")
    assert segs[0].score_inset == (104, 888, 616, 978)
    assert segs[1].score_inset == (104, 888, 655, 978), "x2 放宽没落到这一段"
    assert segs[2].score_inset is None
    out = capsys.readouterr().out
    assert "现量" in out and "左缘和上下沿" in out, (
        "带式 + scorebox 要在 --dry-run 里说清这四个数现在只给**板的左缘和"
        "上下沿**（不随盘数变）＋ 量不出来时的兜底右缘，**右缘渲染时逐段"
        "现量**（账号所有者 2026-08-29：「不能固定宽度去切，要自适应」）。\n"
        "还写着「顶层按最宽那一档写、浅盘的段自己去 x2 收窄」的话，读的人"
        f"会回去手量三档——那正是这次要去掉的那一步。实际打出来的是：{out!r}")
    assert "第 [3] 段不回贴" in out, (
        "不回贴的段要被点名——那几段的左下角是转播原样露出来的板（名字被"
        "居中窗口裁掉），得让人一眼看见有哪几段。⚠️ 美网那条线上「漏写」已经"
        "是硬闸了（test_美网的每一段都要显式表态score_inset），这一行只剩"
        f"「让人看见」这一个职责。实际打出来的是：{out!r}")
    assert "第 [1, 2] 段" in out and "第 [2] 段" in out and "钉死" in out, (
        "提醒里要点名**开了回贴**的那几段，并单独点出哪几段用 `{\"x2\": N}` "
        "把右缘钉死了——钉死的段现量不生效，而「钉了」和「没钉」在产物上"
        f"分不出来。实际打出来的是：{out!r}")


def test_美网的每一段都要显式表态score_inset():
    """⭐⭐ 账号所有者 2026-08-29：「**以后美网期间的「赛场之上」比赛视频
    比分板都按这个方式处理**」。

    「这个方式」＝板的左缘上下沿取顶层 `scorebox`、**右缘渲染时逐段现量**、
    原比例贴回左下。要让它真成为「以后都」，`score_inset` 就不能再是可漏的：
    带式的居中窗口固定切掉板左边 **208px**（正是名字那一段），漏写的样子正是
    账号所有者点过的那句「你这比分板没展示全啊」——而在这之前它只在 dry-run
    里报一句，埋在几十行输出中间。

    所以每一段比赛画面都要**显式表态**，钉四头：

    ① `score_inset` 一个字都没写 → 当场红（「忘了写」和「想过了不贴」在产物
       上长得一模一样：都是左下角一截被裁掉名字的板）
    ② 写 `false` 或 `{"x2": N}` 却没说为什么 → 当场红。`false` 要说清板为什么
       不在（哪一刀之后收走的），`x2` 要说清现量哪儿不准——和 `mixed_fps` /
       `silent_source` / `_frame_why` 一个形状
    ③ `true` 不用写理由（它是主路），`false` ＋ `_score_inset_why` 放行
    ④ **只管美网**：别的赛事的带式 spec 不受这条约束（这条规矩是账号所有者
       给美网期间定的）

    ⚠️ 整屏证据段（image）在闸里被跳过，**这一头没有判据，是因为今天造不出
    这个场景**：image 段写死 `fit="contain"`，而带式明令拒绝 contain，所以
    band × image 的 spec 根本活不到这道闸。那个 `continue` 是防两道闸打架用的
    ——整屏证据段那道闸把 `score_inset` 列进了「不认的窗口类字段」，不跳过的话
    这条闸会去要一个那边禁止写的键。哪天带式支持了整屏证据段，这一头要补判据。

    反向验证过：把整段闸拆掉 → ①② 红；把美网那个前提去掉（所有带式都查）
    → ④ 红。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    srcs = {"r1": Path("a.mp4")}

    def _spec(segs, line1="2026 美网资格赛 决胜轮"):
        return {"cover": {}, "layout": "band", "slug": "uso-x",
                "scorebox": [104, 888, 660, 978],
                "topbar": {"line1": line1, "line2": "甲 6-4 乙"},
                "segments": segs}

    base = {"start": 1, "end": 7, "source": "r1"}
    with pytest.raises(reel.ReelError, match="一个字都没写"):
        reel.parse_segments(_spec([dict(base)]), srcs, "r1")
    with pytest.raises(reel.ReelError, match="没说为什么"):
        reel.parse_segments(
            _spec([dict(base, score_inset=False)]), srcs, "r1")
    with pytest.raises(reel.ReelError, match="没说为什么"):
        reel.parse_segments(
            _spec([dict(base, score_inset={"x2": 588})]), srcs, "r1")

    # ③ true 不用理由；false + 理由放行
    segs = reel.parse_segments(_spec([
        dict(base, score_inset=True),
        dict(base, start=7, end=12, score_inset=False,
             _score_inset_why="76 秒那一刀之后转播把板收走了，接着是全屏图形"),
    ]), srcs, "r1")
    assert segs[0].score_inset and segs[0].score_inset_auto
    assert segs[1].score_inset is None

    # ④ 只管美网：别的赛事的带式 spec 漏写不红
    reel.parse_segments(_spec([dict(base)], line1="辛辛那提 第二轮"), srcs, "r1")


def test_美网的比赛一律带式版式():
    """账号所有者 2026-08-28：「**美网期间的比赛都用这个比例做视频**」。

    美网比赛的 reel（topbar.line1 写着美网/US Open）不写 layout: band 就在
    --dry-run 当场红——只记在对话里拦不住下一个会话，自动链也会自己产美网的
    片子（注入在 promote_reel_draft，判据同一份 reel_facts.us_open_match_line）。

    钉四头：① 美网 + 全出血 → 红（中英两种写法都认）；② 美网带式但没
    scorebox → 红（居中窗口把板裁成残条、回贴无从谈起）；③ archival 存档
    故事片豁免（老素材的图形包不是这套账量的）；④ 豁免表自检——slug 要
    真的存在、line1 真的写着美网、layout 真的还不是 band，写错一个名字
    豁免就成了恒真的绿灯。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    srcs = {"r1": Path("a.mp4")}
    seg = [{"start": 1, "end": 7, "source": "r1"}]

    for line1 in ("2026 美网 女单第二轮", "2026 US Open R2"):
        with pytest.raises(reel.ReelError, match="带式"):
            reel.parse_segments(
                {"cover": {}, "topbar": {"line1": line1, "line2": "x"},
                 "segments": list(seg)}, srcs, "r1")

    with pytest.raises(reel.ReelError, match="scorebox"):
        reel.parse_segments(
            {"cover": {}, "layout": "band",
             "topbar": {"line1": "2026 美网 男单第三轮", "line2": "x"},
             "segments": list(seg)}, srcs, "r1")

    ok = reel.parse_segments(
        {"cover": {}, "layout": "band", "scorebox": [104, 888, 736, 978],
         "topbar": {"line1": "2026 美网 男单第三轮", "line2": "x"},
         "segments": [{"start": 1, "end": 7, "source": "r1",
                       "score_inset": True}]}, srcs, "r1")
    assert ok[0].score_inset == (104, 888, 736, 978)

    # 存档故事片（archival）不在此列；非美网的赛事也不受影响
    assert reel.parse_segments(
        {"cover": {}, "archival": "usq-2014",
         "topbar": {"line1": "2014 美网 半决赛", "line2": "x"},
         "segments": list(seg)}, srcs, "r1")
    assert reel.parse_segments(
        {"cover": {}, "topbar": {"line1": "WTA1000 辛辛那提 第二轮",
                                 "line2": "x"},
         "segments": list(seg)}, srcs, "r1")

    # 豁免表自检（只许减不许加）
    for slug in reel._LEGACY_USO_FULLBLEED:
        spec_path = Path("specs/reels") / f"{slug}.json"
        assert spec_path.is_file(), f"豁免表里的 {slug} 根本不存在"
        legacy = json.loads(spec_path.read_text(encoding="utf-8"))
        line1 = str((legacy.get("topbar") or {}).get("line1", ""))
        assert "美网" in line1 or "us open" in line1.lower(), (
            f"{slug} 的 line1 没写美网——它不该在豁免表里")
        assert legacy.get("layout") != "band", (
            f"{slug} 已经是带式了——从豁免表里把它删掉（只许减不许加）")
        # 豁免真的在起作用：这条老 spec 的形状今天仍过得了闸
        reel.parse_segments(
            {"cover": {}, "slug": slug, "topbar": {"line1": line1, "line2": "x"},
             "segments": list(seg)}, srcs, "r1")


def test_背景音乐要真的落在现场声的4个百分点上(tmp_path):
    """账号所有者 2026-08-28：「配上背景音乐，音量是原声的 4.0%」。

    **判据必须真跑一次混音**——查源码里有没有 `volume=0.0288` 只能防「有人把
    它删了」，防不住「它从来没工作过」（`_push` 键名写错、`_cut_person` 从来
    没跑起来过，都是这个形状）。

    量法走了两版弯路，记在这儿免得下一个人重走：

    ① **按频段劈开各自量**（现场声 300 Hz / 音乐 4000 Hz，高通低通分别量）
       ——滤波器本身在衰减被测信号，三级 highpass 把 4000 Hz 的音乐压掉了
       14 dB，量出来的比值直接偏一个量级。**band 比值这个量法有偏，别用。**
    ② **门槛写成绝对分贝**（「没音乐时高频档要 < −60 dB」）——AAC 192k 的
       量化噪底本来就在 −50 dB 上下，这条会红在噪底上而不是红在缺陷上。

    现在的量法不经过任何滤波器：混两遍（给音乐 / 不给音乐），**相减**。
    `amix=normalize=0` 是线性相加，所以 `有 − 没有` 按定义就是音乐那一路
    本身。两份都写成 WAV，相减是精确的，噪底掉到 −90 dB 以下。
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel as reel  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    def _ff(*args):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        *args], check=True)

    def _peak_db(path, *pre):
        """量 10~16s 的峰值：旁白 7 秒就说完了（现场声开在满刻度 BED_LOUD），
        而淡出要 17s 才开始——这个窗口量到的就是「音乐 ÷ 现场声」本身。"""
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-ss", "10", "-t", "6", *pre,
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, check=True).stderr
        line = [x for x in out.splitlines() if "max_volume" in x]
        assert line, f"量不到 max_volume：{out[-400:]}"
        return float(line[0].split("max_volume:")[1].split("dB")[0])

    bed = tmp_path / "bed.mp4"
    _ff("-f", "lavfi", "-i", "color=c=black:s=64x64:d=20",
        "-f", "lavfi", "-i", "sine=frequency=300:duration=20",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(bed))
    voice = tmp_path / "voice.wav"
    _ff("-f", "lavfi", "-i", "sine=frequency=900:duration=7",
        "-c:a", "pcm_s16le", str(voice))
    # 音乐**故意只有 5 秒**（片子 20 秒）：量的窗口在 10~16s，不循环的话
    # 那里是静音——所以下面那条比值断言同时钉住了「电平对」和「真的循环了」。
    music = tmp_path / "music.wav"
    _ff("-f", "lavfi", "-i", "sine=frequency=4000:duration=5",
        "-c:a", "pcm_s16le", str(music))

    def _mix(with_music):
        # 无损写出：相减要精确，AAC 的量化噪声会把噪底抬到 −50 dB。
        dest = tmp_path / f"mix_{int(with_music)}.wav"
        chain = reel.music_chain(2, 20.0) if with_music else ""
        args = ["-i", str(bed), "-i", str(voice)]
        if with_music:
            # 和生产一样在**输入那一层**循环（滤镜里的 aloop 要把整首歌
            # 缓存进内存）；music_chain 的 atrim 给这条无限输入封上界。
            args += ["-stream_loop", "-1", "-i", str(music)]
        _ff(*args, "-filter_complex",
            reel.duck_filtergraph(["[1:a]adelay=0|0[v0]"], ["[v0]"], chain),
            "-map", "[out]", "-c:a", "pcm_s16le", "-t", "20", str(dest))
        return dest

    on, off = _mix(True), _mix(False)

    # 有 − 没有 ＝ 音乐那一路本身（volume=-1 反相之后相加）。
    diff = tmp_path / "music_only.wav"
    _ff("-i", str(on), "-i", str(off), "-filter_complex",
        "[1:a]volume=-1[inv];[0:a][inv]amix=inputs=2:normalize=0[d]",
        "-map", "[d]", "-c:a", "pcm_s16le", str(diff))

    music_only = _peak_db(diff, "-i", str(diff))
    bed_only = _peak_db(off, "-i", str(off))

    # ① 反面锚点：音乐真的混进去了。把 `[music]` 从 amix 里摘掉的话，两次混音
    #    逐字节相同，相减是 16 位的数字静音（−91 dB）——这条当场红。
    #    ⚠️ 门槛不能按「源文件是满刻度」去拍：ffmpeg 的 `sine` 源实测只有
    #    −18 dB，第一版写 `> -45` 就是这么红在自己的假设上的。−70 是「离数字
    #    静音有 20 dB 以上」，和源文件多大无关。
    assert music_only > -70, (
        f"相减之后是数字静音（{music_only:.1f} dB）：音乐根本没混进 amix")

    # ② 音乐 ÷ 现场声 = 4.0%，也就是 20·log10(0.04) ≈ −27.96 dB。
    #    ⚠️ 这条同时是**循环**的判据：音乐源只有 5 秒，而量的是 10~16s。
    #    拿掉 `-stream_loop -1`，这一段就是数字静音，① 先红。
    got = music_only - bed_only
    want = 20 * math.log10(reel.MUSIC_GAIN_PCT / 100)
    assert abs(got - want) < 1.0, (
        f"音乐应该落在现场声的 {reel.MUSIC_GAIN_PCT}%（{want:.1f} dB），"
        f"实测 {got:.1f} dB")

    # ③ 现场声没被音乐挤掉。要拦的是 `normalize=1`——那会把三路按平均算，
    #    现场声当场掉好几个 dB。**这条只能是单向的**：峰值往上抬一点是两路
    #    信号同相叠加的物理（4% 时约 0.25 dB、8% 时 0.7 dB），第一版写成
    #    `abs(...) < 0.5` 的双向门槛，一调大增益就红在物理上而不是红在缺陷上。
    assert _peak_db(on, "-i", str(on)) > bed_only - 0.5, (
        f"加了音乐之后现场声掉了（{bed_only:.1f} → "
        f"{_peak_db(on, '-i', str(on)):.1f} dB）——amix 把它按平均算了？")


def test_音乐那一路要循环喂而且索引按数i算():
    """上一条判据验的是**滤镜链**（它自己拼 ffmpeg 参数），覆盖不到 `render()`
    里那两行接线——「只测行为拦不住位置错」，这个仓库为它栽过好几次
    （`_push` 键名、`_cut_person`、复制页那道闸装错步骤）。

    钉两样：

    ① **`-stream_loop -1`**：循环要在输入那一层做。滤镜里的 `aloop` 要把
       整首歌缓存进内存，而这条线跑在 runner 上。
    ② **索引按 `count("-i")` 算**，不是 `len(mix_inputs)//2`。加了
       `-stream_loop -1` 之后这一项占四个元素，除以二会把音乐接到旁白那一路
       上——**而 ffmpeg 不报错**，成片只是音乐没了、某段旁白响两遍。
    """
    body = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    block = body[body.index("music_spec = spec.get(\"music\")"):]
    block = block[:block.index("with stage(\"混音\")")]

    assert '"-stream_loop", "-1"' in block, (
        "音乐那一路没有 `-stream_loop -1`：曲子比片子短就铺不满，"
        "而滤镜里的 aloop 要把整首歌缓存进内存")
    assert 'mix_inputs.count("-i")' in block, (
        "音乐的输入索引要数 `-i` 的个数——`-stream_loop -1` 让这一项占了"
        "四个元素，`len(mix_inputs)//2` 会错位到别的输入上")
    assert "len(mix_inputs) // 2" not in block, (
        "音乐这一段不许再用 `len(mix_inputs)//2` 算索引")
