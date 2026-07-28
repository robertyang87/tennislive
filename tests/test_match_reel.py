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
    assert "小红书那句标题" in page and "正文第二行" in page
    assert "navigator.clipboard" in page or "execCommand" in page
    # 微信那条消息的标题不进复制页：小红书标题上限 20 字，这一句二十多字，
    # 塞进去还会把文案自己那句真标题挤成正文第一行
    assert "赛场之上" not in page
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
    # 复制页的入口要说清楚它是干嘛的
    assert "复制页" in page and "https://p/copy.html" in page


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
