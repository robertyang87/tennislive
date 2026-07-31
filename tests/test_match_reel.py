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
        "_cover.jpg", "_cover.html",  # 封面渲染输入，data URI 内嵌，单个 12 MB
        "poster.html",
        "voice_03.mp3",
        "_versus_bg.jpg",             # 背景抓帧
        "_versus_cut_top.png",        # 抽帧抠图，**后缀和上一个不一样**
        "_versus_raw_bottom.png",     # 抠之前那张原帧，报错时会留下
    ]
    for name in must_die:
        assert any(fnmatch(name, p) for p in pats), (
            f"{name} 不会被清理掉，会跟着 git add 进仓库。现有模式：{pats}")

    # **poster.jpg 要留下**：推送正文第一屏就是它，删了推送里一张图都没有。
    # 成片同理——它就是产物本身。
    for keep in ("poster.jpg", "potapova-venus.mp4", "contact_00.jpg", "probe.json"):
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
    copy = tmp_path / "copy.txt"
    copy.write_text("小红书那句标题\n\n正文第一行\n正文第二行", encoding="utf-8")
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
    source = Path(reel.__file__).read_text(encoding="utf-8")
    assert not hasattr(reel, "_render_cover_html"), "单图封面那条路还在"
    body = source.split("def build_cover")[1].split("\ndef ")[0]
    assert "frame_at" not in body, "build_cover 里还留着抽帧的兜底"
    # 模板的**单格**仍可显式给 frame_at（某人一张照片都找不到时的最后一招），
    # 但那是 spec 里写死的选择，不是自动降级——差别就在这儿
    with pytest.raises(reel.ReelError, match="扩检索源"):
        reel.build_cover(Path("x.mp4"), {"cover": {"hook": "无图"}},
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
    """
    reel = _reel()
    source = Path(reel.__file__).read_text(encoding="utf-8")
    picker = source[source.index("selector = "):source.index("cookies: list[str]")]
    assert "vcodec^=avc1" not in picker, "编码又被写成硬条件了"
    assert "ext=m4a" not in picker
    assert "vcodec:h264" in picker, "h264 偏好要留着，下游 ffmpeg 处理最省事"


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


def test_海报台头只写栏目名():
    """台头那颗小药丸只写**栏目名**，不带账号名。

    原来是「网球时差 · 赛场之上」——账号名在片子里已经有落款，海报上再挂一遍
    等于把最显眼的位置让给一句读者不需要的信息。首屏那点地方要留给
    「这是哪一场」。
    """
    for path in sorted(Path("specs/reels").glob("*.json")):
        eyebrow = json.loads(path.read_text("utf-8"))["cover"]["eyebrow"]
        assert eyebrow == "赛场之上", f"{path.name} 的台头是 {eyebrow!r}"


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
    download = body.index('with stage("下载源片")')
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
