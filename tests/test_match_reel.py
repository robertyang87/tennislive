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


def test_封面固定版式是抠图不是抽帧():
    """「赛场之上」的固定海报 2026-07-29 换成 cutout：官方抠图 + 本场画面当底。

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
        assert (versus.get("background") or {}).get("frame_at") is not None, (
            f"{path.name} 的 cutout 背景要给本场的一帧")
        for key in ("top", "bottom"):
            cut = Path(versus[key]["cutout"])
            assert cut.is_file(), f"{path.name} 的 {key} 格找不到抠图 {cut}"
            assert "frame_at" not in versus[key], f"{path.name} 的 {key} 格还在抽帧"

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
