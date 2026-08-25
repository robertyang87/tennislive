"""tools/detect_highlights.py —— T0 集锦探测（只测纯函数，yt-dlp 搜索不测）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import detect_highlights as dh  # noqa: PLC0415

    return dh


def test_query_for用姓和简称拼词():
    dh = _tool()
    q = dh.query_for("Alexandra Eala", "Jessica Pegula", "Mubadala Citi DC Open", 2026)
    assert "Eala" in q and "Pegula" in q, "用姓，不用全名"
    assert "highlights" in q
    assert "Mubadala" not in q, "赞助商前缀要被 short_event 剥掉"
    assert "2026" in q


def test_pick_highlight宁可窄不要错():
    dh = _tool()
    good = [("Eala vs Pegula Highlights | Washington 2026", "https://y/1")]
    bad_title = [("Eala vs Pegula | Washington 2026", "https://y/2")]  # 没 highlights
    wrong_player = [("Eala vs Svitolina Highlights | Washington", "https://y/3")]
    assert dh.pick_highlight(good, "Eala", "Pegula") == "https://y/1"
    assert dh.pick_highlight(bad_title, "Eala", "Pegula") is None
    assert dh.pick_highlight(wrong_player, "Eala", "Pegula") is None


def test_pick_highlight没搜到返回None():
    dh = _tool()
    assert dh.pick_highlight([], "Eala", "Pegula") is None


def test_YouTube探空要退到TennisTV短集锦(monkeypatch):
    """账号所有者定的顺序：主路 YouTube → 备选 Tennis TV 免费短集锦。

    在这条接上之前，`detect_highlights` 探空就是「跳过，下次再探」——而
    `shang-sonego`（辛辛那提 2026 R1）**YouTube 上三个官方来源一条都没有**，
    于是那场球在自动班次里永远不会被做出来，尽管 Tennis TV 一直挂着一条免费的。

    ⚠️ 判据钉两头：探空要真的退下去，**探到就不许再去碰 Tennis TV**——
    多打一次接口是小事，把 YouTube 那条 2~8 分钟的完整版换成 2 分半的剪短版
    是大事（CLAUDE.md「挑更长更完整的那版」）。
    """
    import detect_highlights as d

    touched = []
    monkeypatch.setattr(d, "search", lambda *a, **k: [])
    monkeypatch.setattr(d, "tennistv_fallback",
                        lambda h, a, **k: touched.append((h, a)) or "https://tennistv/x")

    url, via = d.find_highlight("Juncheng Shang", "Lorenzo Sonego", "Cincinnati", 2026)
    assert (url, via) == ("https://tennistv/x", "tennistv-short")
    assert touched == [("Juncheng Shang", "Lorenzo Sonego")]

    # 反面：YouTube 探到了就不许再走备选
    touched.clear()
    # ⚠️ fixture 要带赛事和年份——`pick_highlight` 现在卡这两道，
    # 而真实的官方集锦标题本来就是 `… | Cincinnati 2026` 这个样子。
    monkeypatch.setattr(d, "search", lambda *a, **k: [
        ("Shang vs Sonego Highlights | Cincinnati 2026", "https://yt/a")])
    # ⚠️ 终审（vet_candidate）现在要真跑一次 yt-dlp 拿元数据——测试里打桩成
    # 「官方频道 / 时长合格 / 1080p」，不然这条测试会真发一次子进程。
    monkeypatch.setattr(d, "probe_meta",
                        lambda u, timeout=120: ("Tennis TV", 200.0, 1080.0))
    url, via = d.find_highlight("Juncheng Shang", "Lorenzo Sonego", "Cincinnati", 2026)
    assert (url, via) == ("https://yt/a", "youtube")
    assert not touched, "YouTube 已经探到了还去查 Tennis TV——会把完整版换成剪短版"


def test_TennisTV那条备选判据要窄而且不许把编排带崩(monkeypatch):
    """两位球员的姓都要在 slug 里——和 `pick_highlight` 同一个「宁可窄」口径。

    另一头：接口挂了/回了 HTML，**返回 None 就好，不许抛**。探测这一步「没探到」
    本来就是正常态，一次网络抖动不该把整条编排班次带崩（和 `search()` 吞掉
    超时是同一个理由）。
    """
    import detect_highlights as d
    import tennistv_catalog as cat

    def _row(slug):
        return {"id": 1, "titleUrlSegment": slug, "duration": 157,
                "tags": [{"id": 0, "label": "video-type:short-highlights"}],
                "references": [{"type": "ATP_MATCH", "sid": "422_2026_MS122"}]}

    monkeypatch.setattr(cat, "rows", lambda **k: [
        _row("cincinnati-2026-r1-borges-kokkinakis-short-highlights"),
        _row("cincinnati-2026-r1-shang-sonego-short-highlights"),
    ])
    assert d.tennistv_fallback("Juncheng Shang", "Lorenzo Sonego") == (
        "https://www.tennistv.com/videos/1/cincinnati-2026-r1-shang-sonego-short-highlights")
    # 只对上一个姓的不算
    assert d.tennistv_fallback("Juncheng Shang", "Carlos Alcaraz") is None

    def _boom(**k):
        raise SystemExit("接口回了 HTML")
    monkeypatch.setattr(cat, "rows", _boom)
    assert d.tennistv_fallback("Juncheng Shang", "Lorenzo Sonego") is None, \
        "接口出问题把整条编排带崩了——探测「没探到」是正常态"


def test_优先级链只有一处实现():
    """编排器不许自己再拼一遍「搜一次然后挑一条」。

    ⚠️ 分叉的样子是**「手动跑说探到了，自动班次说没探到」**——两个入口各跑一次
    才看得出来，而没有人会为一条已经通了的路再跑一次。
    """
    from pathlib import Path
    body = Path("tools/orchestrate.py").read_text(encoding="utf-8")
    assert "find_highlight(" in body, "编排器没走那条唯一的优先级链"
    assert "pick_highlight(" not in body, (
        "编排器自己又拼了一遍挑集锦的逻辑——优先级链只该有 find_highlight 一处")


def test_挑集锦要挑这一站这一年的():
    """⚠️ **这是实跑抓到的，不是假想。**

    补这两道之前，「商竣程 vs 索内戈 / Cincinnati / 2026」探回来的是
    `Bublik Headlines; Sonego vs Shang; Khachanov & More | Hong Kong 2026 Day 4
    Highlights`——两位球员的姓都在、`Highlights` 也在，于是过关，而它是**另一站
    的当日综述片**。

    后果不是探不到，是**探到一条错的**：编排器拿它 dispatch probe，整条片子照着
    一场不相干的比赛渲出来，而流水线上没有任何一步会拦它。
    """
    dh = _tool()
    wrong_event = [(
        "Bublik Headlines; Sonego vs Shang; Khachanov & More | Hong Kong 2026 Day 4 Highlights",
        "https://y/hk")]
    right = [("Shang vs Sonego Highlights | Cincinnati 2026", "https://y/ok")]

    assert dh.pick_highlight(wrong_event, "Shang", "Sonego", "Cincinnati", 2026) is None, \
        "又把另一站的综述片当成这场的集锦收下了"
    assert dh.pick_highlight(right, "Shang", "Sonego", "Cincinnati", 2026) == "https://y/ok"
    # 年份也要卡：同一站往年的集锦同样不是这一场
    last_year = [("Shang vs Sonego Highlights | Cincinnati 2025", "https://y/old")]
    assert dh.pick_highlight(last_year, "Shang", "Sonego", "Cincinnati", 2025) == "https://y/old"
    assert dh.pick_highlight(last_year, "Shang", "Sonego", "Cincinnati", 2026) is None

    # 多词赛事名（Hong Kong）要逐词都在，别只对上一个 "hong"
    hk = [("Shang vs Sonego Highlights | Hong Kong 2026", "https://y/hk2")]
    assert dh.pick_highlight(hk, "Shang", "Sonego", "Hong Kong", 2026) == "https://y/hk2"
    assert dh.pick_highlight(hk, "Shang", "Sonego", "Cincinnati", 2026) is None

    # 老调用方不给赛事/年份时退回老行为，别把既有调用打坏
    assert dh.pick_highlight(wrong_event, "Shang", "Sonego") == "https://y/hk"


def test_生产路径要把赛事和年份传下去():
    """⚠️ **只测 `pick_highlight` 自己拦不住这个错**：两道闸写出来了、
    `find_highlight` 不传，行为测试照样全绿，而编排器照旧会拿错一条。

    ⚠️ **这条的第一版是假绿**：它断言源码里出现 `home, away, event, year)`，
    而同一个函数里 `search(query_for(home, away, event, year), …)` 本来就带着
    同一串字符——把 `pick_highlight` 那次调用改回两个参数，它照样通过。
    **判据被另一个东西满足了**，和仓库里「指纹恒真了一个月」是同一个形状；
    是反向验证（注入之后仍然绿）把它抖出来的。现在按 AST 认那一次调用。
    """
    import ast
    from pathlib import Path

    tree = ast.parse(Path("tools/detect_highlights.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "find_highlight")
    call = next(n for n in ast.walk(fn)
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "pick_highlight")
    names = [a.id for a in call.args if isinstance(a, ast.Name)]
    assert "event" in names and "year" in names, (
        "find_highlight 没把赛事和年份传给 pick_highlight——那两道闸等于没装，"
        f"实际传的是 {names}")


def test_yt_dlp没装要出声不许静默当成没搜到(monkeypatch):
    """⚠️ orchestrate.yml 一度漏装 yt-dlp，`search()` 把 FileNotFoundError 吞成
    []——于是编排器每一班都安静地零候选，**和「集锦还没发」长得一模一样**。
    「没装」和「超时」都是环境/源站错，要当场抛；只有正常空结果才返回空。"""
    import pytest

    dh = _tool()

    def _missing(*a, **k):
        raise FileNotFoundError("yt-dlp")

    monkeypatch.setattr(dh.subprocess, "run", _missing)
    with pytest.raises(RuntimeError) as exc:
        dh.search("eala pegula highlights")
    msg = str(exc.value)
    assert "yt-dlp 没装" in msg, "要说清是环境错了，不是「还没搜到」"
    assert "yt-dlp[default]" in msg, "出路要写进报错（[default] 不能省）"

    def _slow(*a, **k):
        raise dh.subprocess.TimeoutExpired(cmd="yt-dlp", timeout=1)

    monkeypatch.setattr(dh.subprocess, "run", _slow)
    with pytest.raises(dh.HighlightSourceError) as exc:
        dh.search("eala pegula highlights")
    assert "源站/网络故障" in str(exc.value) and "集锦还没发" in str(exc.value), (
        "搜索超时不能伪装成正常空结果；要明确区分源站故障和集锦未发布")


def test_yt_dlp非零退出也不许静默当空结果(monkeypatch):
    dh = _tool()
    proc = type("P", (), {"returncode": 1, "stdout": "", "stderr": "HTTP 429"})()
    monkeypatch.setattr(dh.subprocess, "run", lambda *a, **k: proc)
    import pytest
    with pytest.raises(dh.HighlightSourceError) as exc:
        dh.search("q")
    assert "HTTP 429" in str(exc.value) and "不是「集锦还没发」" in str(exc.value)


def test_搜索一次就把频道和时长带出来(monkeypatch):
    """search 用同一次 `--print` 顺手带 channel/duration——flat 模式拿不到的
    字段是 `NA`，要解析成 None（「不知道」），不是一个叫 NA 的频道。"""
    dh = _tool()
    stdout = ("A vs B Highlights ||| https://y/1 ||| Tennis TV ||| 224\n"
              "C vs D Highlights ||| https://y/2 ||| NA ||| NA\n")
    proc = type("P", (), {"returncode": 0, "stdout": stdout})()
    monkeypatch.setattr(dh.subprocess, "run", lambda *a, **k: proc)
    rows = dh.search("q")
    assert rows[0] == ("A vs B Highlights", "https://y/1", "Tennis TV", 224.0)
    assert rows[1] == ("C vs D Highlights", "https://y/2", None, None), (
        "NA 要当成「不知道」（None），留给终审补一枪，不是一个值")


def test_搬运号和合集在挑选那一步就拦():
    """搜索带出来的 channel/duration**知道就当场筛**：搬运号（频道不在官方
    白名单）、Day N 合集（超 12 分钟）都别等到终审才拒。赛事自己的官方频道
    （Cincinnati Open 这类）也算官方——那一档每站一个名字，按赛事简称逐词认。"""
    dh = _tool()
    t = "Shang vs Sonego Highlights | Cincinnati 2026"
    scraper = [(t, "https://y/s", "Tennis Clips 4K", 224.0)]
    compilation = [(t, "https://y/c", "ATP Tour", 723.0)]
    official = [(t, "https://y/ok", "ATP Tour", 224.0)]
    tourney = [(t, "https://y/t", "Cincinnati Open", 224.0)]
    unknown = [(t, "https://y/na", None, None)]
    args = ("Juncheng Shang", "Lorenzo Sonego", "Cincinnati", 2026)
    assert dh.pick_highlight(scraper, *args) is None, "搬运号要在挑选那一步就拦"
    assert dh.pick_highlight(compilation, *args) is None, "12 分钟以上按合集拒"
    assert dh.pick_highlight(official, *args) == "https://y/ok"
    assert dh.pick_highlight(tourney, *args) == "https://y/t", (
        "赛事自己的官方频道也算官方，别只认三大")
    spoof = [(t, "https://y/spoof", "Cincinnati Tennis Fan", 224.0)]
    assert dh.pick_highlight(spoof, *args) is None, (
        "频道名只要含赛事词就算官方会被搬运号轻易伪装")
    assert dh.pick_highlight(unknown, *args) == "https://y/na", (
        "flat 模式拿不到频道（None）不当场拦——留给 vet_candidate 终审补一枪")


def test_标题没有vs的不算单场集锦():
    """`X vs Y` 是单场集锦的形状；球员特辑 / Best points 这类没有 ` vs `——
    合集切不出连续窗口，根本不能当源片。"""
    dh = _tool()
    solo = [("Best of Shang and Sonego points | Cincinnati 2026 Highlights",
             "https://y/solo")]
    good = [("Shang vs Sonego Highlights | Cincinnati 2026", "https://y/1")]
    args = ("Juncheng Shang", "Lorenzo Sonego", "Cincinnati", 2026)
    assert dh.pick_highlight(solo, *args) is None, "没有 vs 的是合集/特辑"
    assert dh.pick_highlight(good, *args) == "https://y/1"


def test_终审1080p不够就等而且话要和没探到分开(monkeypatch):
    """账号所有者 2026-08-18 定死：没有 1080p 就等。终审三态：
    ok / reject（搬运号、合集）/ wait（720p、元数据探不到）。
    ⚠️ 「有集锦但只有 NNNp，等 1080p」和「还没探到」必须是两句不同的话
    ——一个是等，一个是没有，读日志的人要分得开。"""
    dh = _tool()

    monkeypatch.setattr(dh, "probe_meta",
                        lambda u, timeout=120: ("Tennis TV", 200.0, 720.0))
    verdict, why = dh.vet_candidate("https://y/1", "Cincinnati")
    assert verdict == "wait"
    assert "720" in why and "等 1080p" in why, "要说清拿到的是几 P、在等什么"
    assert "还没探到" in why, "必须把「这不是还没探到」写进那句话"

    monkeypatch.setattr(dh, "probe_meta",
                        lambda u, timeout=120: ("ATP Tour", 224.0, 1080.0))
    assert dh.vet_candidate("https://y/1", "Cincinnati")[0] == "ok"

    monkeypatch.setattr(dh, "probe_meta",
                        lambda u, timeout=120: ("Random Reuploads", 224.0, 1080.0))
    verdict, why = dh.vet_candidate("https://y/1", "Cincinnati")
    assert verdict == "reject" and "白名单" in why

    monkeypatch.setattr(dh, "probe_meta",
                        lambda u, timeout=120: ("ATP Tour", 900.0, 1080.0))
    assert dh.vet_candidate("https://y/1", "Cincinnati")[0] == "reject", (
        "12 分钟以上按 Day N 合集拒")

    monkeypatch.setattr(dh, "probe_meta", lambda u, timeout=120: None)
    verdict, why = dh.vet_candidate("https://y/1", "Cincinnati")
    assert verdict == "wait" and "元数据探不到" in why, (
        "「探不到元数据」和「元数据不合格」是两回事，话也要分开")


def test_等1080p不许退到TennisTV剪短版但搬运号要退(monkeypatch):
    """wait（只有 720p）→ 直接 (None, "")，**不退备选**：这一场明明有 YouTube
    集锦、只是还不到 1080p，退到 Tennis TV 的 2 分半剪短版等于把「等 1080p」
    这道硬门槛悄悄换成一条更短的路。reject（搬运号）→ 这条本身不能用，
    照旧走备选链。"""
    d = _tool()

    touched = []
    monkeypatch.setattr(d, "search", lambda *a, **k: [
        ("Shang vs Sonego Highlights | Cincinnati 2026", "https://yt/a")])
    monkeypatch.setattr(d, "tennistv_fallback",
                        lambda h, a, **k: touched.append((h, a)) or "https://tennistv/x")

    monkeypatch.setattr(d, "probe_meta",
                        lambda u, timeout=120: ("Tennis TV", 200.0, 720.0))
    assert d.find_highlight("Juncheng Shang", "Lorenzo Sonego",
                            "Cincinnati", 2026) == (None, "")
    assert not touched, "等 1080p 被悄悄换成了 2 分半的剪短版"

    monkeypatch.setattr(d, "probe_meta",
                        lambda u, timeout=120: ("Random Reuploads", 200.0, 1080.0))
    assert d.find_highlight("Juncheng Shang", "Lorenzo Sonego",
                            "Cincinnati", 2026) == ("https://tennistv/x",
                                                    "tennistv-short")
    assert touched, "搬运号那条本身不能用，备选链要照旧走"


def test_分辨率取整条格式表的最高档不是默认选中那一档(monkeypatch):
    """⚠️ 来路：2026-08-25 同一条视频（`Tvnwn11S4zo`），**runner 上两趟相隔
    35 分钟都报 360p，而沙箱同时段读到 1080p**——比赛 5 小时前就打完了，
    不是转码没跟上。

    `%(height)s` 报的是**默认 format 选择器挑中的那一档**，而挑法随 player
    client 变（有没有 cookies、有没有 PO token 都会换客户端）。这道闸问的是
    「这条源**有没有** 1080p」——那是格式表的属性，不是选中项的属性。

    取 max 两头都不亏：真有 1080p 就认得出；格式表本来就被截断了，max 也还是
    低档，不会假装有。
    """
    d = _tool()

    calls = []

    def _fake(cmd, capture_output, text, timeout):
        calls.append(cmd)

        class R:
            returncode = 0
            stdout = ("WTA ||| 379.0 ||| 360 ||| [144, 240, 360, 720, 1080]\n")
        return R()

    monkeypatch.setattr(d.subprocess, "run", _fake)
    meta = d.probe_meta("https://youtu.be/x")
    assert meta[2] == 1080.0, (
        "选中项是 360、格式表里有 1080——要按格式表判，不然这条源永远等不到")
    assert meta[3] == [144.0, 240.0, 360.0, 720.0, 1080.0]
    # 判据自己的判据：格式表真的是问出来的，不是猜的
    assert any("%(formats.:.height)s" in " ".join(c) for c in calls), (
        "没把格式表打进 --print 的话，上面那个 1080 是从哪来的？")


def test_分辨率不够时要把整条格式表打出来(monkeypatch):
    """**「这条源真的只有 360p」和「我们这台机器只看得见 360p」在一个数上
    长得一模一样**，而两者处置完全相反：一个是等下一班，一个是这条链断了。
    格式表分得开——只有 [360] 是被截断，[144…1080] 里挑出 360 才是选择器问题。
    """
    d = _tool()

    monkeypatch.setattr(d, "probe_meta",
                        lambda u, timeout=120: ("WTA", 300.0, 360.0,
                                                [144.0, 360.0]))
    verdict, why = d.vet_candidate("https://youtu.be/x", "Monterrey")
    assert verdict == "wait"
    assert "144p、360p" in why, f"格式表没打出来：{why}"

    # 读不出格式表也要说清楚，别打一个空串让人以为「表是空的」
    monkeypatch.setattr(d, "probe_meta",
                        lambda u, timeout=120: ("WTA", 300.0, 360.0, []))
    _v, why2 = d.vet_candidate("https://youtu.be/x", "Monterrey")
    assert "读不出格式表" in why2, why2


def test_问格式表的模板要是ytdlp真认得的语法():
    """⚠️ **判据自己的判据。** 上面两条测试喂的是我自己拼的假 stdout——它们
    证明「解析对」，证不了「yt-dlp 真会这么打」。模板写错的样子是
    `%(formats.:.height)s` 原样出现在输出里（或者整段渲成 NA），而那在
    `_ladder` 眼里就是「读不出格式表」——**和「这台机器看不全」长得一模一样**，
    于是我们会去追一个不存在的 PO token 问题。

    拿 yt-dlp 自己的模板求值器离线验一次（不联网，不碰 YouTube）。
    """
    # ⚠️ **CI 上不许 skip。** 本地没装 yt-dlp 的机器跳过没关系，但 CI 是这条
    # 判据唯一必然会跑的地方——在那儿变成 skip 就等于没有这条判据，而
    # 「一条常年跳过的检查和常年红是同一个毛病」。`ci.yml` 因此显式装了
    # yt-dlp；哪天有人把它从那行里拿掉，这里要当场红，不是安静跳过。
    import pytest  # noqa: PLC0415

    try:
        from yt_dlp import YoutubeDL  # noqa: PLC0415
    except ImportError:  # pragma: no cover —— 只在没装 yt-dlp 的本地机器上走到
        if os.environ.get("CI"):
            raise
        pytest.skip("这台机器没装 yt-dlp（CI 上装了，那儿不许跳过）")

    d = _tool()
    tmpl = [a for a in _print_template(d) if "formats" in a]
    assert tmpl, "probe_meta 的 --print 里没有格式表那一段"

    ydl = YoutubeDL({"quiet": True, "simulate": True})
    info = {"channel": "WTA", "duration": 379.0, "height": 360,
            "formats": [{"height": None}, {"height": 144}, {"height": 360},
                        {"height": 720}, {"height": 1080}]}
    out = ydl.evaluate_outtmpl("".join(tmpl), info)
    parts = out.split(" ||| ")
    assert d._ladder(parts[-1]) == [144.0, 360.0, 720.0, 1080.0], (
        f"yt-dlp 渲出来的是 {out!r}，`_ladder` 解不出整条格式表")


def _print_template(d) -> list[str]:
    """从 `probe_meta` 的源码里把 `--print` 后面那几段字符串抠出来。

    ⚠️ 用 AST 不用正则：这个模块的注释和 docstring 里反复写着
    `%(formats.:.height)s`（那正是记教训的地方），按文本扫会扫到注释，
    而「把坑记下来」不该被当成「代码里有这一段」。
    """
    import ast  # noqa: PLC0415
    import inspect  # noqa: PLC0415

    tree = ast.parse(inspect.getsource(d.probe_meta))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and "%(" in n.value]
