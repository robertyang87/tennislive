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
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

WORKFLOW = Path(".github/workflows/match-reel.yml")


def _steps(text: str) -> list[str]:
    """按 `      - name:` 切出步骤名，顺序即执行顺序。"""
    return [
        line.split("- name:", 1)[1].strip()
        for line in text.splitlines()
        if line.startswith("      - name:")
    ]


def test_复制页写在提交之前():
    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)
    page = next(i for i, n in enumerate(names) if "写复制页" in n)
    commit = next(i for i, n in enumerate(names) if "提交产物" in n)
    push = next(i for i, n in enumerate(names) if "推送到微信" in n)
    # 写 → 提交 → 推送。反过来任何一段，链接就是 404。
    assert page < commit < push, names
    assert "--stage page" in text


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

    assert "options: [probe, render, push, cookies]" in text, "mode 里没有 push"

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
    cleanup = text[text.index("丢掉不进仓库的中间物"):].split("- name:")[0]

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
        "_versus_bg.jpg",             # 背景抓帧
        "_versus_cut_top.png",        # 抽帧抠图，**后缀和上一个不一样**
        "_versus_raw_bottom.png",     # 抠之前那张原帧，报错时会留下
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


def test_清理之后还有大文件要报错退出():
    """模式挡的是**已知**的中间物，挡不住下一个没见过的。

    上面那条测的是覆盖，可覆盖永远是事后补的——`.part` 就是补进去的。所以
    清理之后还要再量一次，超标就 `::error::` 退出，让它红在这一步，而不是
    无声进仓库、等到推分支吃 413 才发现（那次就是被 pack 体积撑爆的）。

    「不吭声」正是这一类 bug 的共同特征：`rm` 不报错，`git add` 不报错，
    产物看起来一切正常。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    cleanup = text[text.index("丢掉不进仓库的中间物"):].split("- name:")[0]
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
        opening = spec["segments"][0].get("narration", "")
        assert "北京时间" in opening, f"{path.stem} 开场没说是北京时间：{opening}"
        assert re.search(r"[一二三四五六七八九十〇零百]+\s*[点时]", opening), \
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
            for text in (seg.get("narration") or "", seg.get("quote") or ""):
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
    block = text[text.index(guard):].split("- name:")[0]
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
        block = text[text.index(step):].split("- name:")[0]
        assert "mode != 'cookies'" in block, step
    # 必须**真下媒体流**再看字节数：不带 cookie 也拿得到标题和格式表，
    # 只查「命令有没有报错」会把「被挡住」读成「可用」
    check = text[text.index("cookies — 只验"):].split("- name:")[0]
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
    check = text[text.index("cookies — 只验"):].split("- name:")[0]
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
    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    assert reel.POSTER_NAME == push_reel.POSTER_NAME == "poster.jpg"
    text = WORKFLOW.read_text(encoding="utf-8")
    clean = text.split("丢掉不进仓库的中间物", 1)[1].split("- name:", 1)[0]
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
    "赛场之上": ("cutout", "diagonal", "split", "stack"),   # 讲一场对决 → VS
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


def test_栏目和封面模板要配对():
    """**「赛场之上」仍然只能用 VS 模板**，`solo` 不是它缺图时的兜底。

    账号所有者 2026-07-31 给的是**新增一个栏目**（「当前对话历史都是网球有故事
    的话题」「只是这次网球有故事的主题要用视频方式呈现」），不是给赛场之上
    松绑。这两件事很容易混：单人海报一旦能渲，下次哪条对决片子凑不齐两张照片，
    就会「先用 solo 顶一下」——正是 `test_封面只有海报模板一条路` 拦的那个滑坡，
    只是换了个滑法。

    所以配对写死在两处，缺一不可：

    - spec 里（这一条）——已发布的片子不会悄悄漂
    - `build_cover` 里——**新写的 spec 也拦得住**，判据在下面那条
    """
    for path in sorted(Path("specs/reels").glob("*.json")):
        cover = json.loads(path.read_text("utf-8"))["cover"]
        allowed = _COLUMNS[cover["eyebrow"]]
        assert cover.get("layout") in allowed, (
            f"{path.name}：{cover['eyebrow']} 只能用 {allowed}，"
            f"写的是 {cover.get('layout')!r}")
        if cover.get("layout") == "solo":
            # 单人海报讲的是一个人：主角、他的照片，**而且不许印赛果**——
            # 「德米纳尔 6-2 6-3」是六拍里的第 5 拍，印在封面上等于先说结局。
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
            assert not cover.get("result"), (
                f"{path.name} 是讲人的片子，封面印了赛果 {cover['result']!r}——"
                "那是最后一拍，印在封面上等于先把结局说了")


def test_赛场之上不许退回单人封面():
    """上一条钉的是已发布的 spec，这一条钉的是**代码**：新写一个 spec 也拦得住。

    只钉 spec 的话，判据只在「有人把它写进仓库」之后才生效——而滑坡发生在
    渲染那一刻（缺图 → 换个 layout 试试 → 出片了 → 才提交）。闸要装在出片
    那一步，和「复制页那道闸装在发的那一步不是渲的那一步」是同一条。
    """
    import pytest  # noqa: PLC0415

    reel = _reel()
    solo = {"eyebrow": "赛场之上", "layout": "solo", "subject": "谁",
            "portrait": {"image": "x.jpg"}}
    with pytest.raises(reel.ReelError, match="VS 模板"):
        reel.build_cover({"": Path("x.mp4")}, "", {"cover": solo},
                         Path("y.mp4"), 1920)
    # 反面锚点：换成讲人的栏目就该放行（这儿只验它不再拦，渲染另有判据）
    with pytest.raises(reel.ReelError, match="portrait"):
        reel.build_cover({"": Path("x.mp4")}, "",
                         {"cover": {"eyebrow": "网球有故事", "layout": "solo"}},
                         Path("y.mp4"), 1920)


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
    clean = text.split("丢掉不进仓库的中间物", 1)[1].split("- name:", 1)[0]
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

    cleanup = flow[flow.index("丢掉不进仓库的中间物"):].split("- name:")[0]
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
    assert body.index("cover_secs = cover_length(") < body.index("build_cover("), (
        "封面长度算在渲封面之后——那就只能拿常量渲，等于没改")
    # 定长那条路要出声
    assert "没有配音，定长停" in reel, "退回定长时不吭声，和「配音没合出来」分不开"
    # 封面那一路要接进混音，标签不能在下游重筛
    assert "voice_labels.append" in reel, "混音的标签又在下游重筛了"
    assert 'names = "".join(voice_labels)' in reel
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
    bad, unchecked = reel.segments_straddling_cuts(spec, probes)
    assert unchecked == []
    assert [b["index"] for b in bad] == [1, 2], "跨切点的段没被抓出来"
    assert bad[0]["cuts"] == [20.0] and bad[1]["cuts"] == [5.0]

    # 真要跨（两边是同一个人）就显式挂账，别默默跨过去
    spec["segments"][1]["crosses_cut"] = "两边都是她，只是机位换了"
    bad, _ = reel.segments_straddling_cuts(spec, probes)
    assert [b["index"] for b in bad] == [2]

    # **probe 给不全时不许假绿**：零命中和「全都合格」长得一模一样，
    # 所以没查成的源片要单独报出来（CLAUDE.md：空结果先自证是真空）。
    bad, unchecked = reel.segments_straddling_cuts(spec, probes[:1])
    assert unchecked == ["b"], "缺 probe 的源片没有被报出来"
    assert all(b["source"] == "a" for b in bad)


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
