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

import json
import inspect
import os
import re
import subprocess
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


def test_提交重试耗尽必须失败且只重放本条成片():
    """所有 push 都失败却继续微信步骤，会把一个 404 链接发出去。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    commit = text.split("- name: 提交产物", 1)[1].split("- name:", 1)[0]

    assert 'if git push origin "HEAD:$BRANCH"; then' in commit
    assert "exit 0" in commit
    assert 'git checkout rendered -- "$OUTDIR"' in commit
    assert "git checkout rendered -- output/" not in commit
    assert "::error::连续" in commit
    assert commit.rfind("exit 1") > commit.rfind("done")


def _reel():
    sys.path.insert(0, str(Path("tools").resolve()))
    import build_match_reel  # noqa: PLC0415

    return build_match_reel


def test_成片帧率跟着源片走(monkeypatch):
    """硬定 30 而源片 25，就是每 5 帧补一帧、一秒卡五次。

    补出来的帧还查不出来：裁切位置每帧都在变，两帧的像素并不相同（成片 2099 帧
    里逐帧比对，完全相同的 0 帧），只有比源片和成片的帧率才看得见。
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
    table = {"a": (1920, 1080, "25/1"), "b": (1920, 1080, "30/1"),
             "c": (1280, 720, "25/1")}
    monkeypatch.setattr(reel, "probe_size", lambda p: table[p.stem][:2])
    monkeypatch.setattr(reel, "resolve_fps", lambda p: (table[p.stem][2], 0.0))
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
    # 这条线没有置顶评论，那一格就不该留个空框加一个复制不出东西的按钮
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


# 这七条发在「开场先给坐标」这条规矩之前。**只许减不许加**——加新片子要么
# 带着坐标来，要么显式往这份清单里写一笔，让「又忘了交代」变成一次看得见的决定。
_NO_SLATE_YET = {
    "eala-fernandez", "eala-zheng", "nishikori-shang", "potapova-venus",
    "wang-pareja", "wang-samsonova", "wong-lehecka",
}


def test_赛场之上开场要给出北京时间赛事和轮次():
    """账号所有者：「以后赛场之上上来首先交代下时间（北京时间几月几号几点几分
    之类 开球的时间）赛事和轮次」。

    刷到片子的人不知道这是哪天哪站哪一轮，第 ① 段那十秒就是用来安置他的。

    判据只卡**三样在不在**，不卡写法：时间要认得出是北京时间的开球时刻、
    赛事名、轮次。措辞不管——这条线上已经有两条测试因为盯措辞而误伤过好写法。
    """
    import re  # noqa: PLC0415

    for path in sorted(Path("specs/reels").glob("*.json")):
        spec = json.loads(path.read_text("utf-8"))
        if (spec.get("cover") or {}).get("eyebrow") != "赛场之上":
            continue
        if path.stem in _NO_SLATE_YET:
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
        assert opening.strip(), f"{path.stem} 整条片子一句中文旁白都没有"
        assert "北京时间" in opening, f"{path.stem} 开场没说是北京时间：{opening}"
        # ⚠️ **`两` 必须在这个字集里。** 两点钟中文只说「两点」，没人说「二点」——
        # 而第一版的字集里只有「二」，于是「凌晨两点十分」被判成**没给开球时刻**。
        # 这是一条**假阴性**：它不会告诉你「我拦错了」，只会逼下一个人把对的
        # 写法改成错的（判据宁可窄，不可宽——但窄不等于漏掉唯一正确的那个写法）。
        assert re.search(r"[一二三四五六七八九十两〇零百]+\s*[点时]", opening), \
            f"{path.stem} 开场没给开球时刻：{opening}"
        assert re.search(r"[月][一二三四五六七八九十]+[号日]", opening), \
            f"{path.stem} 开场没给日期：{opening}"
        assert re.search(r"(强|轮|决赛|资格赛)", opening), \
            f"{path.stem} 开场没给轮次：{opening}"


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
    """
    bad = []
    for slug, spec in _reel_specs().items():
        # `.get`：原声段（`quote`）根本没有 narration 这个键
        nars = [s.get("narration", "") for s in spec["segments"]]
        nars = [n for n in nars if n]
        if not nars:
            continue
        if "？" not in nars[-1][-30:]:
            bad.append(f"{slug}: …{nars[-1][-26:]}")
    assert not bad, (
        "这些片子的收尾停在数据上，没有落在一问上：\n  " + "\n  ".join(bad))


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
    assert reel.FINAL_PRESET == "slow"

    # 参数要走常量，不能又硬写回调用里——硬写的那份改起来没人看得见理由
    src = Path(reel.__file__).read_text(encoding="utf-8")
    assert '"-crf", FINAL_CRF' in src, "成片那一步没用 FINAL_CRF 常量"
    assert '"-crf", "18"' not in src, "成片的 crf 又被硬写回调用里了"


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
    盖过去——漏一次就换了个人在说话。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "zh-CN-YunjianNeural" in text
    assert "zh-CN-YunxiNeural" not in text


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
    assert "seg.cx = 0.5" in src, "不摇的段没有取正中"


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
    """标题底下那一行：**国旗 + 名字（排名） 比分 国旗 + 名字（排名）**。

    账号所有者 2026-08-04：「中间标题下面写上比分（带双方国旗）」。

    **真渲一次 HTML**，不查源码文本——查源码只能防「有人把它删了」，
    防不住「它从来没工作过」（这个仓库栽过：`_cut_person` 引了一个不存在的
    名字，测试断言 `"def _cut_person(" in reel` 照样绿，功能整天是坏的）。
    """
    import pytest  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415
    base = {"eyebrow": "赛场之上", "hook": "钩子", "winner": "张帅",
            "result": "6-4 6-1",
            "matchup": [{"name": "张帅", "country": "CHN", "rank": 57},
                        {"name": "普汀塞娃", "country": "KAZ", "rank": 81}]}
    html = vp._solo_score_html(base)
    assert "🇨🇳" in html and "🇰🇿" in html, f"国旗没渲出来：{html}"
    text = re.sub(r"<[^>]+>", "", html)
    assert "6-4" in text and "6-1" in text, f"盘分没渲出来：{html}"
    # **赢家在前**：`matchup` 是版式顺序，`winner` 才是赛果顺序。
    # wang-samsonova 那次海报印「萨姆索诺娃 6-2 6-2 王欣瑜」而标题算成
    # 「王欣瑜 vs 萨姆索诺娃」——比分夹在中间，等于声称输的那个人赢了。
    assert text.index("张帅") < text.index("6-4") < text.index("普汀塞娃")
    flipped = {**base, "winner": "普汀塞娃"}
    h2 = re.sub(r"<[^>]+>", "", vp._solo_score_html(flipped))
    assert h2.index("普汀塞娃") < h2.index("6-4") < h2.index("张帅"), \
        "换了赢家，赛果行的顺序没跟着换"

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
    # 缺国别 / 缺排名 / winner 对不上，三样都要当场报错，不许悄悄少印
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
    # **而且它真的接在 solo 的正文里**——上面那些只证明函数好用，
    # 证明不了有人调它。`_solo_body` 里少写一处，海报就悄悄没有比分行。
    body, _ = vp._solo_body({**base, "subject": "张帅",
                             "portrait": {"image": "assets/logo/brand/icon.png"}})
    assert "storyscore" in body and "🇨🇳" in body, \
        "比分行没接进 solo 的正文——查函数好用防不住「没人调它」"


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
    assert 'spec.get("subtitle_top", _REEL_MARGIN_V)' in src, (
        "字幕上锚不能只有一个写死的值——竖版源片会撞上它自己的记分条")
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
        assert "mode == 'render'" in block, "推送那一步没钉死在 render 上"

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
    # 成片那一步一个字都不许跟着动
    assert reel.FINAL_PRESET == "slow" and reel.FINAL_CRF == "18", (
        "改中间段不许连累成片——省时间要从中间产物上省，不能从交出去的那一份上省")


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
    local |= {"tennislive", "tests"}
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

    定时归零之后，`preview_candidates` 那 165 分钟的窗口只在手动跑的那一趟
    里起作用，不再需要一个间隔去配它。要恢复定时，得连这条测试一起改——
    那时**间隔仍然要按窗口重算**，别照抄当年那行 cron。
    """
    for name in ("flash", "news-radar"):
        body = _yaml_only(
            Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8"))
        head = body.split("\njobs:")[0]
        assert "schedule:" not in head, (
            f"{name} 的定时又回来了——2026-08-02 账号所有者停掉的")
        assert "workflow_dispatch:" in head, (
            f"{name} 停的是定时，手动入口不能一起摘掉")


def test_没有下游在读的定时任务不许一直跑():
    """**采集了没人读，和空跑是一回事。**

    - `oncourt-interviews`：`data/oncourt_interviews.json` 攒到 4551 条，
      而除了 oncourt 自己那套采集工具，**没有任何代码 import 它**
    - `player-name-sync`：六月至今译名表只变过一次，还是人手改的

    两条都摘掉定时、留手动。这条测试拦的是「顺手把 cron 加回来」——
    要恢复，先给它找个下游，或者把这条测试一起改。
    """
    for name in ("oncourt-interviews", "player-name-sync"):
        body = _yaml_only(
            Path(f".github/workflows/{name}.yml").read_text(encoding="utf-8"))
        head = body.split("\njobs:")[0]
        assert "schedule:" not in head, (
            f"{name} 又挂上定时了——它的产出没有下游在读（2026-07-31 停的）")
        assert "workflow_dispatch:" in head, f"{name} 的手动入口不能一起摘掉"


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
    download_at = body.index("download(url, path)")
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
        assert "超出源片末尾" in buf.getvalue()

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


def test_dry_run秒级返回且一个字节都不下载(tmp_path):
    """**真跑一遍**，喂一个绝对下不动的 URL——它必须照样成功返回。

    这是「写了不等于跑过」：断言 `--dry-run` 这个开关存在，证明不了它没去下载。
    所以给一个 `http://0.0.0.0/nope.mp4`，能秒回就说明它真的没碰网络。
    """
    import json as _json
    import subprocess as _sp
    import sys as _sys
    import time as _time

    spec = _json.loads(Path("specs/reels/wong-lehecka.json").read_text(encoding="utf-8"))
    spec["source_url"] = "http://0.0.0.0/绝对下不动.mp4"
    path = tmp_path / "fake.json"
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

    而 git 有个 **100 MiB 的服务端硬拒**，绕不过去。所以超过 95 MiB 的成片改传
    GitHub Release 附件（单个 2 GB，公开仓库下载不计流量额度），链接写进
    `render.json`，推送那一步优先读它。

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
    release = next(i for i, n in enumerate(names) if n.startswith("成片太大"))
    clean = next(i for i, n in enumerate(names) if n.startswith("丢掉不进仓库"))
    commit = next(i for i, n in enumerate(names) if n.startswith("提交产物"))
    assert release < clean < commit, \
        f"上传 Release 排在了提交之后（{release} / {clean} / {commit}）"

    spec = yaml.safe_load(text)
    steps = {s.get("name", ""): s for s in spec["jobs"]["reel"]["steps"]}
    step = next(s for n, s in steps.items() if n.startswith("成片太大"))
    assert "gh release upload" in step["run"]
    assert 'rm -f "$REEL"' in step["run"], \
        "传完没把本地那份删掉，它还会被 git add 吃进去"
    assert step.get("if") == "github.event.inputs.mode == 'render'"

    pre = next(s for n, s in steps.items() if n.startswith("push 模式先确认"))
    assert "video_url" in pre["run"], \
        "预检只认仓库那条，走 Release 的片子会被判成没渲"


# 规矩定下来**之前**已经发出去的九个文件。已发的片子不为了措辞重渲
# （那条规矩在别处），所以它们挂在这儿——**只许减不许加**：新写的 spec 要么
# 用新叫法，要么显式把自己加进来，让「又用了强字」变成一次看得见的决定。
_LEGACY_QUALIFIER_NAMES = {
    "eala-svitolina.json", "wong-brooksby.json", "wong-gea.json",
    "zheng-lanlana.json", "eala-fernandez.xhs.txt", "eala-svitolina.xhs.txt",
    "wong-brooksby.xhs.txt", "wong-gea.xhs.txt", "zheng-lanlana.xhs.txt",
}


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


def test_轮次要写半决赛不写四强():
    """账号所有者 2026-08-02：「以后不要用四强八强之类的，国内通常用半决赛
    1／4 决赛 1/8 决赛之类的。再往前就第几轮好了」。

    「四强」「八强」是港台和赛事方的说法，国内观众看的是**半决赛 / 1/4 决赛 /
    1/8 决赛**，再往前直接说第几轮。这不是同义词替换的洁癖：叫法不对，读者要多
    想一步「四强是打到哪一步」，而这条片子的封面只有一行字的位置。

    **只查会发出去的字段**——旁白、封面上印的字、推送那几栏、小红书文案。
    `_source` / `_why` / `_match` 这些是写给下一个人看的注解，里面正引着账号
    所有者那句原话，连它一起扫就会把「把规矩记下来」判成「又违反了规矩」——
    同一个错在这个仓库里犯过三次（工作流输入的旧默认值、push-reel 里的 ffmpeg、
    查 `-e .` 那条）。
    """
    import re  # noqa: PLC0415

    bad = re.compile(r"[四八]强|十六强|三十二强|(?<!\d)(?:16|32|64)\s*强")

    def outward(spec: dict):
        for seg in spec.get("segments") or []:
            yield seg.get("narration", "")
        for key, value in (spec.get("cover") or {}).items():
            if key.startswith("_"):
                continue
            for item in ([value] if isinstance(value, str)
                         else list(value.values()) if isinstance(value, dict)
                         else []):
                if isinstance(item, str):
                    yield item
                elif isinstance(item, list):
                    yield from (x for x in item if isinstance(x, str))
        # ⚠️ **这儿原来读的是 `_push`，而 push_reel 读的是 `push`。**
        # `_` 开头的按本仓库的约定是写给下一个人的注解，只有三条 spec 有；
        # 真正会发进微信的 `push.summary` / `push.lead` 有十一条，**一条都没被
        # 扫到**。docstring 明明写着「推送那几栏」——判据的主语错了，而它绿着。
        for key, value in (spec.get("push") or {}).items():
            if not key.startswith("_") and isinstance(value, str):
                yield value

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

    fresh = {k: v for k, v in offenders.items() if k not in _LEGACY_QUALIFIER_NAMES}
    assert not fresh, (
        f"这些地方还在写强字轮次：{fresh}。"
        "改成 半决赛 / 1/4 决赛 / 1/8 决赛，再往前写「第几轮」。")
    # **清单只许减不许加**：修好一个就从上面删掉一个，别让它变成一张许可证
    assert set(offenders) <= _LEGACY_QUALIFIER_NAMES, "清单里有已经修好的条目？"


def test_重放不许把已经删掉的成片救活():
    """push 撞车之后的重放路径**只加不减**，于是走了 Release、已经 `rm` 掉的
    成片会被 `reset --hard` 从 origin 上放回来，再也删不掉。

    run 30727483963 的日志把这件事写得清清楚楚：第一次提交是对的——
    `delete mode 100644 output/…/eala-osaka.mp4`；push 撞车（另一条提交先到），
    重放之后那条 delete 没了。结果仓库里躺着 2 分 39 秒的旧片，而真正发出去的
    是 Release 上 3 分 53 秒的那一版。**两个地址两条片子，谁也没说哪个是哪个。**

    `git checkout <ref> -- <dir>` 只恢复 ref 里**存在**的文件，不会删掉 ref 里
    没有的——所以重放前要先把这个目录清空。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text[text.index("push 被拒（第 $attempt 次）"):]
    block = block[:block.index("sleep $((attempt")]
    assert 'rm -rf "$OUTDIR"' in block, (
        "重放之前没清空 outdir——`git checkout <ref> -- <dir>` 不会删文件，"
        "上一句 reset --hard 放回来的旧成片会一直留着")
    assert block.index('rm -rf "$OUTDIR"') < block.index("git checkout rendered"), \
        "清空要排在 checkout 之前，否则等于什么都没做"


def test_片长不设上限但要说清这一版走哪条路(tmp_path):
    """账号所有者 2026-08-02：「我的基础要求是保证内容和画面质量，文件多大都
    没关系」「不要砍片长」「我怕故事讲解不完整」。

    **所以这条不许再拦人。** 它的前一版按 git 的 100 MiB 硬上限反推出一个片长
    上限并直接报错——那正好把账号所有者要的东西挡在门外，而且更早的一版余量
    留太狠，当场把已经发出去、实际只有 81.9 MiB 的 eala-svitolina 判成不合格。
    「判据宁可窄，不可宽」在这儿的极端形式是：**这个判据根本不该存在**，
    100 MiB 是 git 的限制，不是内容的限制，换一条路（Release 附件）就没了。

    留下来的只有「出声」：两条落脚点的链接长得完全不一样（raw vs
    releases/download），日志里不写就只能靠猜。
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
    seconds, mib = reel.reel_length_verdict(spec)
    assert seconds > 400 and mib > reel.REPO_INLINE_MIB

    # 每条 spec 都要算得出来，而且要报清楚走哪条路
    for path in sorted(Path("specs/reels").glob("*.json")):
        s, m = reel.reel_length_verdict(json.loads(path.read_text(encoding="utf-8")))
        assert s > 0 and m > 0, path.name

    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    body = src[src.index("def load_spec("):src.index("def segments_straddling_cuts(")]
    assert "REPO_INLINE_MIB" in body, "load_spec 没报这一版走哪条路"
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
    assert "column=column)" in src, "药丸没和标题共用那一个栏目名"


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
    step = [b for b in blocks if "mode == 'narration'" in b]
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
    # 片尾必须是**最后**一个 part：长度账全靠这个顺序
    assert body.index("parts.append(build_outro(") > body.index(
        "parts.append(cut_segment("), (
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
    """
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    sys.path.insert(0, str(Path("tools").resolve()))
    import outro_page  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"

    secs, fps = 3.85, 25
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
            "-loop", "1", "-t", f"{secs}", "-i", str(base)]
    for f in layer_files:
        args += ["-loop", "1", "-t", f"{secs}", "-i", str(f)]
    args += ["-filter_complex", outro_page.motion_filter(secs, str(fps), float(fps)),
             "-map", "[vout]", "-c:v", "libx264", "-preset", "ultrafast",
             "-crf", "12", "-pix_fmt", "yuv420p", str(film)]
    subprocess.run(args, check=True)

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
    import outro_page  # noqa: PLC0415

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
    `test_轮次要写半决赛不写四强`（推送那几栏）和 `test_人名要以译名表为准`
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


def test_一段里不许有整段的哑场():
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

    # ① 已发那一版的真实数字必须被拦下来
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

    # ④ 闸要**排在编码之前**：它用的是 TTS 时长，一个源片都不用碰，
    #    在这之前红掉省的是整趟渲染。
    body = "\n".join(
        line for line in inspect.getsource(reel.render).splitlines()
        if not line.lstrip().startswith("#"))
    assert "silent_stretches(" in body, "render 里没接这道闸"
    assert body.index("silent_stretches(") < body.index("cut_segment("), (
        "哑场那道闸排在分段编码之后了——它一个源片都不用碰，"
        "应该和「旁白超长」那道一起排在编码之前")


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

    return [(sec(f[1]), sec(f[2]))
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
        offset = render_json["cover_seconds"]
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
            spec_secs = round(sum(float(s["end"]) - float(s["start"])
                                  for s in segs), 2)
            was = round(float(render_json.get("segments_seconds", -1)), 2)
            if abs(was - spec_secs) > 0.05:
                print(f"  [跳过] {outdir.name} 的产物是上一版的："
                      f"渲的时候画面 {was}s，现在的 spec 是 {spec_secs}s")
                continue
            for key, secs in recorded.items():
                seg = segs[int(key)]
                body = "".join(c for c in str(seg.get("narration", ""))
                               if c not in reel._SPEECH_QUIET)
                punct = sum(1 for c in body if c in reel._SPEECH_PUNCT)
                out.append((outdir.name, int(key), len(body) - punct, punct,
                            round(float(secs), 2)))
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


# 从上面那套办法里挑出来冻结的一份，按字数从短到长铺开（2.95s ~ 17.57s）。
# **这一份必须留在测试里**：`output/` 在 CI 上不存在，判据的主语没了就会变成
# 一盏恒真的绿灯——2026-08-01 那次「只校到 0 条」就是这么来的。
_SPEECH_FIXTURE = [
    ("gea-shapovalov", 0, 8, 3, 2.95),
    ("eala-pegula", 12, 13, 2, 3.48),
    ("eala-pegula", 7, 18, 3, 5.02),
    ("wong-brooksby", 2, 20, 3, 5.33),
    ("eala-pegula", 9, 23, 4, 6.41),
    ("jodar-fritz", 16, 25, 5, 6.70),
    ("eala-pegula", 0, 29, 6, 7.87),
    ("jodar-fritz", 0, 32, 6, 8.21),
    ("jodar-fritz", 6, 35, 5, 8.54),
    ("hewitt-washington", 9, 39, 5, 9.92),
    ("zheng-lanlana", 14, 43, 5, 10.15),
    ("gea-shapovalov", 6, 50, 8, 11.18),
    ("gea-shapovalov", 3, 60, 9, 13.90),
    ("gea-shapovalov", 4, 81, 10, 17.57),
    # 两头的极端也要在表里——**样本不带尾巴，误差带子就没法自证不虚高**。
    # 121 段里最偏的就这两条（−1.27 / +1.42）。
    ("gea-shapovalov", 5, 67, 10, 14.40),
    ("wong-gea", 3, 42, 9, 12.67),
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
        errs = [secs - reel.speech_seconds("一" * chars + "，" * punct)
                for _slug, _i, chars, punct, secs in rows]
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


def test_每条spec的旁白都还估得下():
    """**每条 spec 都要现在还渲得出来**，不只是发的那天渲得出来。

    `wong-lehecka` 第 10 段就是这么坏掉的：成片 7.30 发出去，之后为了「收尾要
    落在一问上」把那一问补进旁白，字数从 22 涨到 48，**没有再渲过**。于是这条
    spec 从那天起就渲不出来了——真闸（TTS）要跑一趟 render 才出声，而没人再渲
    它，所以它一直躺在仓库里假装是好的。

    改 spec 不重渲是常事（措辞、注解、规矩追认），所以这条要**每次 CI 都跑**。
    它只吃 `specs/` 和 `tools/`，不联网、不碰产物。
    """
    reel = _reel()
    broken: list[str] = []
    checked = 0
    for slug, spec in _reel_specs().items():
        for index, secs, room in reel.narration_estimates(reel.validate_spec(spec)):
            checked += 1
            if room < -reel.SPEECH_EST_ERR:
                broken.append(f"{slug} 第 {index + 1} 段：画面 "
                              f"{spec['segments'][index]['end'] - spec['segments'][index]['start']:.1f}s"
                              f"，估旁白 {secs:.2f}s")
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
        path = tmp_path / "spec.json"
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


def test_单人封面的暗角可以按条关掉但两头要留(tmp_path):
    """账号所有者 2026-08-03：「不要虚化背景，铺满全 3:4 的画」。

    「铺满」本来就成立（solo 是 `background-size:cover`，照片顶到四边、没有垫层）；
    让实拍看起来发虚的是盖在整幅上的 `.scrim`——它的第二道 radial 在**画面正中**
    压 58% 的暗，一张真实照片被洗成一层背景板。

    ⚠️ **不许直接改那个默认值。** 那段 CSS 是从解说片的 cover 屏整段抄过来的，
    源码注释写着「一个数都没动，各调各的就会慢慢漂开」。所以做成**按条声明**
    （`cover.scrim: "clear"`），没声明的片子和解说片仍然是同一个样子。

    判据三头，缺一头都可能变成假绿：

    1. 关掉的**只有正中那一道**——上下两头必须留着，台头压在顶上、钩子压在
       中间偏下，浅色字压在浅色画面上会没。
    2. **默认仍然带中心暗角**（不声明的片子不受影响）。
    3. **这个开关真的接在 `_solo_body` 上**——只测 `_scrim_css` 证明不了海报
       读了它。这是这个仓库反复栽的「写了不等于跑过」。
    """
    sys.path.insert(0, str(Path("tools").resolve()))
    import versus_poster as vp  # noqa: PLC0415

    CENTRE = "radial-gradient(128% 40% at 50% 50%"
    TOP_BOTTOM = "linear-gradient(180deg,rgba(6,28,20,.62)"

    assert CENTRE in vp._scrim_css(False), "默认那一版没有中心暗角了"
    assert CENTRE not in vp._scrim_css(True), "clear 没有关掉中心暗角"
    for flag in (False, True):
        assert TOP_BOTTOM in vp._scrim_css(flag), (
            "上下两头的渐变被一起关掉了——台头和钩子会压在浅色画面上看不见")

    # ③ 真走一遍 `_solo_body`：声明了就不带，没声明就带
    from PIL import Image  # noqa: PLC0415

    photo = tmp_path / "p.jpg"
    Image.new("RGB", (1920, 1080), (90, 120, 90)).save(photo)
    base = {"eyebrow": "赛场之上", "subject": "某人", "hook": "一行钩子",
            "portrait": {"image": str(photo)}}
    _, plain = vp._solo_body(dict(base))
    _, cleared = vp._solo_body({**base, "scrim": "clear"})
    assert CENTRE in plain, "不声明 scrim 的封面丢了中心暗角"
    assert CENTRE not in cleared, (
        "`cover.scrim: \"clear\"` 没接进 `_solo_body`——开关写了但海报没读")


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
    spec = next(p for p in sorted(Path("specs/reels").glob("*.json"))
                if p.with_suffix(".xhs.txt").is_file())
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
