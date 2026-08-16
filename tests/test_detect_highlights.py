"""tools/detect_highlights.py —— T0 集锦探测（只测纯函数，yt-dlp 搜索不测）。"""

from __future__ import annotations

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
