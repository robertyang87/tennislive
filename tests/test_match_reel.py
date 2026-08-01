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


def test_复制页排在渲染之前而且当场提交():
    """**它不依赖成片，所以没有理由排在成片后面等。**

    `push_reel.py --stage page` 的内容只来自 `specs/reels/<slug>.xhs.txt` 和
    从 spec 算出来的标题——全程没碰过 mp4。可它原来排在渲染之后，于是 Pages
    要等渲染 + 提交都完事才开始发布，推送那一步只能站着等：run 30624808733
    的日志是连续 12 次 `HTTP 404`、第 13 次才中，**240 秒纯空转**，占了整条
    十六分钟 run 的四分之一。

    挪到渲染前面并**当场提交**，Pages 的发布就和七分二十二秒的渲染并行了。
    两件事都要钉住——只挪写、不挪提交，Pages 照样要等到最后那次提交才动。

    顺带钉住第二个好处：这一步是标题字数、tag 个数、spec 有没有 push 块的
    第一道校验，排在渲染前面意味着这些错死在第 3 分钟而不是第 12 分钟。
    """
    names = _steps(WORKFLOW.read_text(encoding="utf-8"))
    page = next(i for i, n in enumerate(names) if "写复制页" in n)
    page_commit = next(i for i, n in enumerate(names) if "提交复制页" in n)
    render = next(i for i, n in enumerate(names) if n.startswith("render"))
    assert page < page_commit < render, (
        f"复制页要「写→提交」都排在渲染之前，现在是 {names}")


def test_复制页那一步不挑推不推送():
    """分支上渲的片子也要把复制页带上，否则 push-reel 又得现写现等。

    渲染那次不写复制页，它就只能在推送那一刻才第一次进仓库——Pages 从零开始
    发布，又是四分钟的原地等待。写它几乎不要钱（一个 HTML 文件），而它决定了
    后面那条三分钟的推送要不要退回十几分钟。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    for step in ("写复制页", "提交复制页"):
        block = text[text.index(f"- name: {step}"):].split("\n      - name:")[0]
        assert "inputs.push == 'true'" not in block, (
            f"「{step}」挂在 push=true 上了——分支上渲的片子就带不上复制页，"
            "合进 main 之后 push-reel 还得现写现等 Pages")
        assert "inputs.mode == 'render'" in block, f"「{step}」没限定在 render 模式"


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
    page = build_html("https://v/x.mp4", "https://p/copy.html", "一句导语", copy)
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
                                "标题一行\n\n正文一段", "https://x/poster.jpg")
    assert "border-top:5px solid #ff2442" in body        # 参照那条红边
    img = body[body.index("<img"):body.index(">", body.index("<img"))]
    assert "width:100%" in img and "padding" not in img, img
    assert "border-radius" not in img, "铺满就不该有圆角"
    # 正文只印一遍
    assert body.count("正文一段") == 1
    # 没有海报时退回无图版，而不是塞一个空 img
    assert "<img" not in push_reel.build_html("u", "c", "l", "标题\n\n正文")


# 剪辑线上跑的栏目。台头那颗药丸写的就是它，而**栏目决定封面模板**。
_COLUMNS = {
    "赛场之上": ("cutout", "diagonal", "split", "stack"),   # 讲一场对决 → VS
    "网球有故事": ("solo",),                                 # 讲一个人 → 单人
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
    # **盯的是真正接收 `cover_secs` 的那次调用**，不是「第一个 build_cover(」。
    # `--cover-only` 那条快速预览路径也调 build_cover（拿默认时长渲一张海报
    # 就退出，海报本来就与时长无关），它排在最前面——按 `index()` 找会撞上它，
    # 而那是误判：production 那条路照旧先算长度。判据宁可窄，不可宽。
    production = body.index("cover_secs)]")
    assert body.index("cover_secs = cover_length(") < production, (
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
    assert "转折" in told or "反了过来" in told, "旁白没讲转折，观众不知道这场球难在哪"
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


PUSH_WORKFLOW = Path(".github/workflows/push-reel.yml")


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
    inputs = _yaml_only(WORKFLOW.read_text(encoding="utf-8").split("permissions:")[0])
    for stale in ("伊埃拉 vs 郑钦文", "郑钦文首轮出局", "2:1"):
        assert stale not in inputs, (
            f"工作流输入里还挂着「{stale}」——那是上一条片子的内容，"
            "漏传一次就拿另一场球的标题发出去")


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
                                "", "标题\n\n正文", "")
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
    stage = source[source.index("url = video_url(outdir, name)"):]
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
    sys.path.insert(0, str(Path("tools").resolve()))
    import push_reel  # noqa: PLC0415

    # ① 只吃 spec：每条都算得出、都过得了闸。日期随便给一个合法的目录名——
    # 闸门量的是整句宽度，而日期那一格所有片子都一样宽。
    titles: dict[str, str] = {}
    for path in sorted(Path("specs/reels").glob("*.json")):
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


def test_推送不用重渲一遍():
    """**合进 main 之后重跑整条 match-reel，等于把七分钟的渲染白付一遍。**

    判据摆得很干净：wong-brooksby 在 PR #108（分支上渲的）里是 55,028,417
    字节，run 30623994190 在 main 上重渲出来是 55,028,980 字节——差 563 字节
    的同一条片子，外加往仓库里再塞一个 55 MB 的 blob。hewitt-washington 同样
    来了一次（56,953,265 → 57,297,653）。.git 涨到 1.77 GiB、checkout 每次要
    两分多钟，就是这么攒出来的。

    所以要有一条**只推送、不渲染**的线：它不下载源片、不合成语音、不装
    Chromium/ffmpeg/OpenCV，失败重跑三分钟。
    """
    assert PUSH_WORKFLOW.is_file(), "没有只推送的工作流，合进 main 就只能重渲"
    text = PUSH_WORKFLOW.read_text(encoding="utf-8")

    # 不许把渲染那套东西拖进来——拖进来它就不是三分钟了。
    # 同样只看 YAML 的值：注释里写着「这里不装 ffmpeg/Chromium」，那是判据本身。
    body = _yaml_only(text)
    for heavy in ("build_match_reel", "yt-dlp", "edge-tts", "playwright",
                  "ffmpeg", "visualqa", "cutout", "webrender"):
        assert heavy not in body, f"只推送的工作流里出现了 {heavy}，它不该渲染任何东西"

    # Pages 只服务 main，这道闸和 match-reel 那道同一个理由、同一个位置
    guard = "- name: 只能在 main 上跑"
    assert guard in body, "没有这道闸"
    assert body.index(guard) < body.index("actions/checkout@v4"), (
        "这道闸排在 checkout 后面了")
    block = body[body.index(guard):].split("- name:")[1]
    assert "github.ref_name != 'main'" in block and "exit 1" in block

    # 查产物不查信号：成片和文案真的在这个目录里才推
    assert ".mp4" in body and "找不到成片" in body


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
    for path in (WORKFLOW, PUSH_WORKFLOW):
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
            listed_statically = re.search(
                r"\n\s+output/\S+", block[block.index("sparse-checkout:"):])
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
    "rembg": "rembg",
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


def test_内容雷达的间隔要按发布窗口算():
    """**72 次/天换来 1 个包。**

    run 30643007873 全程 3 分 44 秒，checkout 占 3 分 02 秒（81%），而真正
    「自动选题并生成」只用了 **3 秒**。产出是每天雷打不动 1 个（就是日限），
    即时赛果停掉后只剩赛前焦点——**上限就是 1 个/天**。

    间隔不是拍的：`preview_candidates` 收赛前 45–210 分钟的对阵，窗口宽
    165 分钟。这条测试钉住「间隔和窗口是一起算的」——改窗口就得回来看间隔，
    别让它们各走各的。
    """
    from tennislive.content_ops import preview_candidates  # noqa: PLC0415

    sig = inspect.signature(preview_candidates)
    window = (sig.parameters["max_lead_minutes"].default
              - sig.parameters["min_lead_minutes"].default)
    assert window == 165, f"发布窗口改成了 {window} 分钟——间隔要跟着重算"

    body = _yaml_only(Path(".github/workflows/flash.yml").read_text(encoding="utf-8"))
    cron = re.search(r'cron:\s*"([^"]+)"', body).group(1)
    minute, hours = cron.split()[0], cron.split()[1]
    assert "," in hours or hours.startswith("*/"), (
        f"内容雷达又变成每小时跑了：{cron}")
    per_day = len(hours.split(","))
    assert per_day <= 8, (
        f"内容雷达一天 {per_day} 次——日限只有 1 个包，多跑的都是空转")
    assert minute not in ("0", "30"), "定时落在整点半点，GitHub 最容易延迟或丢弃"
    # 间隔要匀，别六次全挤在半天里
    hs = sorted(int(h) for h in hours.split(","))
    gaps = [(b - a) for a, b in zip(hs, hs[1:])] + [24 - hs[-1] + hs[0]]
    assert max(gaps) - min(gaps) <= 1, f"班次间隔不匀：{gaps}"


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


def test_并行装依赖要分别检两边的退出码():
    """apt（42s）和 pip（25s）装的东西互不相干，串起来是白等。丢到后台并行
    之后取长的那个，量出来 1:07 → 0:44 上下。

    ⚠️ **`wait` 不带参数只返回最后一个后台任务的状态。** apt 挂了而 pip 成功，
    这一步照样绿，然后 render 在第 5 分钟死在「找不到 ffmpeg」——**又一次
    「兜底出事的时候不吭声」**。所以必须按 PID 分别 wait，谁挂了报谁。

    这条测的是那个模式，不是某一行字：只要还并行装，就得两个 PID 都 wait。
    """
    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    step = body[body.index("- name: 装系统依赖和 Python 依赖"):]
    step = step.split("\n      - ")[0]
    assert step.count("&\n") >= 2 or step.count(" &") >= 2, "没有并行装"
    pids = re.findall(r"^\s*(\w+)=\$!", step, re.M)
    assert len(pids) >= 2, f"只捕获到 {pids}——两边都要留 PID 才能分别 wait"
    for pid in pids:
        assert re.search(rf"wait \${pid}\b\s*\|\|", step), (
            f"`wait ${pid}` 没检退出码——它挂了这一步会照样绿，"
            "然后 render 在第 5 分钟才死")
    # 装完当场自证：ffmpeg 真的在
    assert "ffmpeg -version" in step, "并行装完没验 ffmpeg，装没装上要到 render 才知道"


def test_PO_token_探活挪到了render之前():
    """容器是 `docker run -d` 起的，原地轮询最多 50 秒纯属空转——它下一次被
    用到是 render 里下载源片那一刻。探活挪到 render 前面，启动和中间那几步
    并行，实测那 12 秒基本被吃掉。

    **起不来仍然不算失败**：退回 client 梯子，让下载那一步去报真正的原因。
    """
    names = _steps(WORKFLOW.read_text(encoding="utf-8"))
    start = next(i for i, n in enumerate(names) if "起 PO token provider" in n)
    wait = next(i for i, n in enumerate(names) if "等 PO token provider" in n)
    render = next(i for i, n in enumerate(names) if n.startswith("render"))
    assert start < wait < render, f"探活的位置不对：{names}"
    assert wait - start >= 2, (
        "探活紧挨着启动——那和原地等是一回事，中间要隔几步给它启动时间")

    body = _yaml_only(WORKFLOW.read_text(encoding="utf-8"))
    block = body[body.index("- name: 起 PO token provider"):].split("\n      - ")[0]
    assert "for i in $(seq" not in block, "启动那一步又在原地轮询了"


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

    # 容差：源片时长有帧级误差，卡太死会误伤最后一段
    monkeypatch.setattr(reel, "probe_duration", lambda _p: 4.98)
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
