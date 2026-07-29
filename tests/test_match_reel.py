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
import subprocess
import sys
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


def test_中间物清单包含封面渲染输入():
    # _cover.html 把封面图以 data URI 内嵌，单个 12 MB，不能每出一版就进一次仓库
    text = WORKFLOW.read_text(encoding="utf-8")
    # 从这一步的名字切到下一步的 `- name:`，只看它自己那段
    cleanup = text[text.index("丢掉不进仓库的中间物"):].split("- name:")[0]
    for name in ("source.mp4", "source_av.mp4", "_cover.jpg", "_cover.html"):
        assert name in cleanup, name


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
    got = _headline(column="赛场之上", matchup="锦织圭 vs 商竣程", score="2:1",
                    event="华盛顿 ATP500 首轮")
    assert got == "7.28 赛场之上 | 华盛顿 ATP500 首轮 | 锦织圭 2:1 商竣程"
    # 没赛果（比如赛前前瞻）就保留「vs」
    assert _headline(column="赛场之上", matchup="锦织圭 vs 商竣程").endswith(
        "锦织圭 vs 商竣程"
    )
    # 比分说不清的片子（退赛、以转折为主）改用一句话概括，顶掉末尾那一格
    assert _headline(column="赛场之上", matchup="锦织圭 vs 商竣程", score="2:1",
                     event="华盛顿 ATP500 首轮",
                     summary="复出首战打满三盘") == (
        "7.28 赛场之上 | 华盛顿 ATP500 首轮 | 复出首战打满三盘")


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


def test_标题默认不带赛事名且别太长():
    """「7.28 赛场之上 | 华盛顿 ATP500 首轮 | 锦织圭 2:1 商竣程」被判定太长。
    赛事名文案里本来就有，标题这一格留给**人物 + 结果 + 抓得住人的那句**。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    block = text[text.index("      event:"):text.index("      summary:")]
    assert 'default: ""' in block, "event 默认要留空"
    sys.path.insert(0, str(Path("tools").resolve()))
    from push_reel import headline  # noqa: PLC0415

    got = headline(Path("output/2026-07-28/reel/x"), "赛场之上",
                   "锦织圭 vs 商竣程", "2:1", "", "商竣程复出输球，总分只差 8 分")
    assert "ATP500" not in got
    assert len(got) <= 32, f"{len(got)} 字，太长：{got}"


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


def test_封面没给cx时自动定心():
    """源片在本地看不到时（YouTube 对沙箱一律 403），cx 只能靠猜，
    猜错就是把人裁到画面边上。所以封面和分段一样，缺 cx 就按运动质心自动定。"""
    reel = _reel()
    source = Path(reel.__file__).read_text(encoding="utf-8")
    assert 'cover.get("cx") is None' in source
    assert "auto_center(source, probe, source_w)" in source
    spec = json.loads(Path("specs/reels/eala-zheng.json").read_text("utf-8"))
    assert "cx" not in spec["cover"]


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


def test_固定中心全片共用一个():
    """**一段一个中心才是那个毛病。**

    逐段取运动质心的中位数，一段只有几秒、往往就一两个回合，谁那边球多中心就
    偏谁：实测九段是 0.338 / 0.406 / 0.381 / 0.470 / 0.482 / 0.547 / 0.466 /
    0.455 / 0.407，1920 宽里前后差 400px，而**转播机位从头到尾没动过**。

    池化到全片才对：一整场球的落点对称于球场中轴，样本一多就收敛（这批是 0.455）。

    ⚠️ 曾经写过一版按白线剖面找对称轴的检测器，合成画面上误差 0.001，
    **真实素材上完全不成立**（108 张真源片帧估出来的轴从 0.0 散到 0.85）。
    机位一旦偏离中轴，球场在画面里本来就不再左右对称——"找对称轴"找的不是
    球场中轴。已经删掉，别再走这条路。
    """
    reel = _reel()
    assert not hasattr(reel, "court_center") and not hasattr(reel, "_court_axis")
    src = Path("tools/build_match_reel.py").read_text(encoding="utf-8")
    assert "全片共用一个固定中心" in src
    # 签名收的是一批段，不是一段——池化本身就写在类型里
    import inspect  # noqa: PLC0415

    params = list(inspect.signature(reel.auto_center).parameters)
    assert params[1] == "segs", params


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
