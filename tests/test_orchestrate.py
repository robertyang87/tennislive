"""tools/orchestrate.py —— 无人值守编排器的纯函数（不联网、不 dispatch）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import orchestrate  # noqa: PLC0415

    return orchestrate


def _match(status):
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    return Match(
        match_id="x", tour=Tour.WTA,
        tournament=Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000"),
        home=[Player(name="Alexandra Eala", country="PHI", seed=5)],
        away=[Player(name="Jessica Pegula", country="USA", seed=2)],
        status=status, round_name="Final", sets=[SetScore(6, 4)])


def test_路由完赛进reel未开赛进preview进行中不路由():
    from tennislive.models import MatchStatus
    o = _tool()
    assert o.route(_match(MatchStatus.FINISHED)) == "reel"
    assert o.route(_match(MatchStatus.SCHEDULED)) == "preview"
    assert o.route(_match(MatchStatus.LIVE)) == "", "进行中的比赛不该被路由"


def test_candidates跳过进行中的比赛():
    from tennislive.digest import Digest
    from tennislive.models import MatchStatus
    o = _tool()
    # ⚠️ 完赛和未开赛必须用**不同的球员对**——同 slug 会被去重并成一条，
    # 而这条测试要验的是「live 被跳过」不是「同场去重」。
    finished = _match(MatchStatus.FINISHED)
    scheduled = _match(MatchStatus.SCHEDULED)
    scheduled.home[0].name = "Qinwen Zheng"
    scheduled.away[0].name = "Aryna Sabalenka"
    d = Digest(today=None,
               results=[finished],
               live=[_match(MatchStatus.LIVE)],
               schedule=[scheduled],
               source="x")
    cands = o.candidates(d)
    assert len(cands) == 2, "只该有完赛 + 未开赛两条，live 要跳过"
    assert {c["column"] for c in cands} == {"reel", "preview"}


def test_工作流映射按栏目对上生产线():
    o = _tool()
    assert o._workflow_for("reel") == "match-reel.yml"
    assert o._workflow_for("preview") == "preview-reel.yml", (
        "开球之前要独立管线（08-08 定了单独走），别混进 match-reel，"
        "也别走 explainer 的卡片视频")


def test_slug取姓拼横杠():
    o = _tool()
    m = _match(0)
    assert o.slug_for(m) == "eala-pegula"


def test_slug缩写名取第一个词当姓():
    """ESPN 缩写名「Kenin S.」姓在第一个词，取最后一个词会得到 s. 垃圾 slug。"""
    from tennislive.models import Match, Player, Tour, Tournament
    o = _tool()
    m = Match(
        match_id="x", tour=Tour.WTA,
        tournament=Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000"),
        home=[Player(name="Kenin S.", country="USA")],
        away=[Player(name="Lys E.", country="GER")],
        status=0)
    assert o.slug_for(m) == "kenin-lys", "缩写名要取第一个词当姓，不是最后一个"


def test_candidates同场去重且留全名():
    from tennislive.digest import Digest
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    o = _tool()
    tour = Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000")

    def _m(home, away):
        return Match(
            match_id="x", tour=Tour.WTA, tournament=tour,
            home=[Player(name=home, country="X")],
            away=[Player(name=away, country="Y")],
            status=MatchStatus.FINISHED, round_name="Final",
            sets=[SetScore(6, 4)])

    full = _m("Sofia Kenin", "Eva Lys")
    abbr = _m("Kenin S.", "Lys E.")
    d = Digest(today=None, results=[full, abbr], live=[], schedule=[], source="x")
    cands = o.candidates(d)
    slugs = [c["slug"] for c in cands]
    assert slugs == ["kenin-lys"], f"同场去重后只该有一条，实际 {slugs}"
    assert cands[0]["home"] == "sofia kenin", "去重要留全名版，不是缩写版"


def test_candidates缩写名还原成全名():
    """ESPN 缩写名（Kovacevic A.）要还原成全名——detect_highlights 的搜索词和
    assemble 的译名都要全名，缩写直接拿去搜会搜错。"""
    from tennislive.digest import Digest
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    o = _tool()
    m = Match(
        match_id="x", tour=Tour.WTA,
        tournament=Tournament(name="Cincinnati", tour=Tour.WTA, level="W1000"),
        home=[Player(name="Kovacevic A.", country="USA")],
        away=[Player(name="Khachanov K.", country="RUS")],
        status=MatchStatus.FINISHED, round_name="Final",
        sets=[SetScore(6, 4)])
    d = Digest(today=None, results=[m], live=[], schedule=[], source="x")
    cands = o.candidates(d)
    assert cands[0]["home"] == "aleksandar kovacevic", "缩写名要还原成全名"
    assert cands[0]["away"] == "karen khachanov"


def test_beijing_today是date():
    o = _tool()
    import datetime as dt
    assert isinstance(o._beijing_today(), dt.date)


def test_main把今天传给build_digest(monkeypatch, capsys):
    """编排器从没真跑过：build_digest() 必填 today，裸调会 TypeError。钉住
    main 必须传北京时间的今天，否则这条工具在 CI 上一触发就崩。"""
    o = _tool()
    captured = {}

    def fake_build(today):
        captured["today"] = today
        return type("D", (), {"results": [], "schedule": []})()

    monkeypatch.setattr(o, "build_digest", fake_build)
    monkeypatch.setattr(o, "candidates", lambda dig: [])
    monkeypatch.setattr(sys, "argv", ["orchestrate.py"])
    rc = o.main()
    assert rc == 0
    assert "today" in captured, "build_digest 必须收到 today 参数"


def test_assemble_draft跳过出声(monkeypatch):
    o = _tool()
    notes = o.assemble_draft({"slug": "x"}, skip=True)
    assert notes == ["[assemble] 已跳过（--no-assemble）"]


def test_assemble_draft成功返回备料notes(monkeypatch):
    o = _tool()

    def _fake_assemble(**kw):
        return {"_notes": ["flashscore id：A"]}

    fake = type("M", (), {"assemble": staticmethod(_fake_assemble)})()
    monkeypatch.setitem(sys.modules, "assemble_spec", fake)
    notes = o.assemble_draft({"slug": "eala-pegula", "home": "A E", "away": "B R",
                              "event": "C", "year": 2026})
    assert notes[0] == "[assemble] eala-pegula 草稿备好（未落盘）"
    assert "flashscore id：A" in notes


def test_assemble_draft失败不抛出声(monkeypatch):
    o = _tool()

    class Boom:
        def assemble(self, **kw):
            raise RuntimeError("network down")

    monkeypatch.setitem(sys.modules, "assemble_spec", Boom())
    notes = o.assemble_draft({"slug": "x", "home": "A", "away": "B",
                              "event": "C", "year": 2026})
    assert any("备料没成" in n and "network down" in n for n in notes), (
        "备料失败必须出声且不抛——dispatch 已经点下去了，别让便宜的备料把整趟带崩")


# ---------------------------------------------------------------------------
# 下面这批是 2026-08-21 编排链修复的判据。
# 造比赛用 _match2（可控级别/轮次/排名/种子/时间），别改上面那个老 _match——
# 既有测试的分数账是按它算的。


def _match2(home="Anna Kalinskaya", away="Emma Navarro", *, level="W1000",
            status=None, round_name="Final", h_country="RUS", a_country="USA",
            h_rank=None, a_rank=None, h_seed=None, a_seed=None,
            start=None, sets=((6, 4),), winner=None, mid="x", tour=None):
    from tennislive.models import (Match, MatchStatus, Player, SetScore, Tour,
                                   Tournament)
    status = MatchStatus.FINISHED if status is None else status
    tour = tour or Tour.WTA
    return Match(
        match_id=mid, tour=tour,
        tournament=Tournament(name="Cincinnati", tour=tour, level=level),
        home=[Player(name=home, country=h_country, rank=h_rank, seed=h_seed)],
        away=[Player(name=away, country=a_country, rank=a_rank, seed=a_seed)],
        status=status, round_name=round_name,
        sets=[SetScore(*s) for s in sets], start_utc=start, winner=winner)


def _digest(*matches, schedule=()):
    from tennislive.digest import Digest
    return Digest(today=None, results=list(matches), live=[],
                  schedule=list(schedule), source="x")


def test_ATP500这一档不许被裸档位名静默筛掉():
    """级别解析器吐的是 `ATP500/WTA500/ATP250/WTA250` 这类全称，从来不产裸的
    "500"/"250"——第一版 TOUR_LEVELS 写了裸档位名，整个 500/250 档被静默过滤，
    而漏掉的样子和「今天没有 500/250 的候选」一模一样。"""
    import datetime as dt

    from tennislive.models import Tour
    o = _tool()
    # 常量本身：全称在、裸档位不在（写裸档位等于一个永远匹配不上的名字）
    assert "ATP500" in o.TOUR_LEVELS and "WTA250" in o.TOUR_LEVELS
    assert "500" not in o.TOUR_LEVELS and "250" not in o.TOUR_LEVELS, (
        "裸 '500'/'250' 是解析器永远不产的值，留着只会骗人以为盖住了这一档")
    # 行为：一场 ATP500 决赛（德米纳尔 8 vs 谢尔顿 10）必须进候选
    m = _match2(home="Alex de Minaur", away="Ben Shelton", level="ATP500",
                h_country="AUS", a_country="USA", h_rank=8, a_rank=10,
                tour=Tour.ATP, winner=0,
                start=dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3))
    cands = o.candidates(_digest(m))
    assert [c["slug"] for c in cands] == ["minaur-shelton"], (
        f"ATP500 的候选被静默筛掉了：{cands}")


def test_上一个比赛日的完赛不入候选():
    """「上一个比赛日的不要做了」（2026-08-17）落到机器上：完赛超过
    FRESH_RESULT_HOURS 的不入候选。⚠️ start_utc 缺失**不算过期**——
    「判不了」和「过期了」是两回事，缺时间全 drop 的样子和「今天没有候选」
    一模一样。"""
    import datetime as dt
    o = _tool()
    now = dt.datetime.now(dt.timezone.utc)
    stale = _match2(home="Iga Swiatek", away="Maria Sakkari",
                    h_rank=2, a_rank=60, start=now - dt.timedelta(hours=30),
                    mid="s1")
    fresh = _match2(home="Elena Rybakina", away="Magdalena Frech",
                    h_rank=10, a_rank=41, start=now - dt.timedelta(hours=5),
                    mid="s2")
    undated = _match2(home="Jessica Pegula", away="Emma Navarro",
                      h_rank=3, a_rank=28, start=None, mid="s3")
    # 判据自己的判据：过期那场热度和分数本来都够，被拦只能是因为过期
    assert o.hot_enough(stale), "fixture 要先自证「不是热度不够」"
    slugs = {c["slug"] for c in o.candidates(_digest(stale, fresh, undated))}
    assert "swiatek-sakkari" not in slugs, "30 小时前的完赛是上一个比赛日的"
    assert "rybakina-frech" in slugs
    assert "pegula-navarro" in slugs, (
        "start_utc 缺失不算过期——「判不了」不等于「过期了」")


def test_调度侧热度预筛拦住无名对局():
    """W1000 R64 两个无名种子（45 分）过得了打分门槛，却注定死在渲染侧
    `_players_are_worth_a_reel` 的热度闸上——调度侧不预筛就是白烧一趟 probe。
    五个出口逐个验：中国球员 / 世界前20 / 热点名单 / 半决赛及以上 / 爆冷。"""
    import datetime as dt

    from tennislive.render.rating import match_score
    o = _tool()
    now = dt.datetime.now(dt.timezone.utc)
    base = _match2(round_name="Round of 64", h_rank=40, a_rank=45,
                   h_seed=5, a_seed=6, sets=((6, 4), (6, 4)),
                   start=now - dt.timedelta(hours=3))
    # 判据自己的判据：base 分数过门槛（种子对决 +15 + W1000 30 = 45 ≥ 38），
    # 被拦只能是因为热度预筛——不钉这一句，断言「不出现」就可能是恒真。
    assert match_score(base) >= 38
    assert o.hot_enough(base) == ""
    assert o.candidates(_digest(base)) == [], "无名对局要在调度侧就拦下"

    assert o.hot_enough(_match2(h_country="CHN")) == "中国球员"
    assert o.hot_enough(_match2(a_rank=15,
                                round_name="Round of 64")) == "世界前20"
    assert o.hot_enough(_match2(home="Alexandra Eala", h_country="PHI",
                                round_name="Round of 64")) == "热点名单", (
        "热点名单按姓认（Eala）——注意霍达尔是 Jodar 不是 Fils")
    assert "jodar" in o.HOT_SURNAMES and "fils" not in o.HOT_SURNAMES, (
        "霍达尔是 Rafael Jodar；Fils 是菲斯，按音译猜会认错人")
    assert o.hot_enough(_match2(round_name="Semifinals")) == "半决赛及以上"
    upset = _match2(home="Sonay Kartal", away="Marketa Vondrousova",
                    h_country="GBR", a_country="CZE", a_rank=25, a_seed=6,
                    winner=0, round_name="Round of 64")
    assert o.hot_enough(upset) == "爆冷", "非种子掀翻种子要走爆冷那个出口"


def test_爆冷这条出口要求输的那个人排得进前30():
    """种子支（`l.seed and not w.seed`）一个名次差都不要求，于是巡回赛首轮的
    常态被判成「爆冷」。2026-08-25 拿 8 天真实赛果量过：`hot_enough` 判成爆冷
    的 6 场里 **5 场只有种子支中**，名次差 4 / 6 / 14 / 20 位——
    `#29 胜 #23`、`#92 胜 #88` 这种。账号所有者 2026-08-15 点名否掉过同一个
    形状（「博尔特这种没有话题啊，排名也不高没必要做」），2026-08-16 又明说
    「他是种子」不许当 `_heat_why`。

    门槛复用 `is_upset` 名次支本来就在用的那个 30，不另发明一个数。
    """
    o = _tool()

    def _seed_fall(w_rank, l_rank):
        # 输的那个是 6 号种子、赢的那个没种子 —— is_upset 的种子支必中
        return _match2(home="Winner Name", away="Loser Name",
                       h_rank=w_rank, a_rank=l_rank, a_seed=6, winner=0,
                       round_name="Round of 64")

    from tennislive.render.rating import is_upset
    # 判据自己的判据：这两场**都**过得了 is_upset 的种子支——被拦下只能是
    # 因为新加的名次线，不是因为它们本来就不算冷门。
    keeps, drops = _seed_fall(208, 25), _seed_fall(50, 36)
    assert is_upset(keeps) and is_upset(drops), "两场都要先自证种子支中了"

    assert o.hot_enough(keeps) == "爆冷", "输家排进前 30（波塔波娃 #25）要留住"
    assert o.hot_enough(drops) == "", (
        "输家 #36、只差 14 位（帕里胜韦基奇那种）不算爆冷——"
        "这正是 2026-08-25 量到的那 5 场噪音")

    # 排名读不出来时按「不算爆冷」处置：「没依据」不许变成「放行」。
    blind = _match2(home="Winner Name", away="Loser Name",
                    a_seed=6, winner=0, round_name="Round of 64")
    assert is_upset(blind), "fixture 要先自证种子支中了"
    assert o.hot_enough(blind) == "", "排名读不出来就没有依据说它是爆冷"

    # 只收紧调度侧：rating.is_upset 一个字没动，内容雷达那边照旧。
    assert is_upset(drops), "rating.is_upset 不许被这条改动连坐"


def test_调度侧热度线和渲染侧那道闸是同一个数():
    """orchestrate.HEAT_TOP_RANK 必须等于 build_match_reel.HEAT_TOP_RANK——
    两侧不同的话，调度放行的候选注定死在下游 --dry-run 的热度闸上，
    白烧一趟 probe。故意不 import 共享（orchestrate.yml 只装 pip install -e .，
    不该背上 build_match_reel 的依赖漂移），等值由这条测试钉住。"""
    o = _tool()
    import build_match_reel as bmr
    assert o.HEAT_TOP_RANK == bmr.HEAT_TOP_RANK, (
        f"调度侧 {o.HEAT_TOP_RANK} ≠ 渲染侧 {bmr.HEAT_TOP_RANK}——"
        "改哪边都要两边一起改")


def test_state条目七天过期同slug再交手不被永久压住(monkeypatch, tmp_path):
    """老版本按裸 slug 永久去重：同对手再交手（或王曦雨/王欣瑜同姓撞 slug）
    被一条老记录永久压住，`date` 字段写了从来没读过。现在条目 7 天过期，
    同 slug 靠比赛日分辨（±1 天算同一场，跨午夜的夜场会落到相邻两天）。"""
    import datetime as dt
    import json
    o = _tool()
    today = dt.date.today()
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"dispatched": {
        "old-slug": {"date": (today - dt.timedelta(days=10)).isoformat()},
        "new-slug": {"date": today.isoformat()},
        "bad-slug": {},
    }}), encoding="utf-8")
    monkeypatch.setattr(o, "STATE_PATH", state_file)
    monkeypatch.setattr(o, "SPECS_DIR", tmp_path / "specs")

    state = o.load_state()
    assert set(state["dispatched"]) == {"new-slug"}, (
        "10 天前的条目要过期清掉；date 读不出来的也按过期清")

    same = {"slug": "new-slug", "date": today.isoformat()}
    assert o.dispatch_plan([same], state) == [], "同一场（同比赛日）要被压住"
    next_day = {"slug": "new-slug",
                "date": (today + dt.timedelta(days=1)).isoformat()}
    assert o.dispatch_plan([next_day], state) == [], (
        "±1 天算同一场——跨午夜的夜场在两次扫描里会落到相邻两天")
    rematch = {"slug": "new-slug",
               "date": (today + dt.timedelta(days=5)).isoformat()}
    assert o.dispatch_plan([rematch], state) == [rematch], (
        "差 5 天是再交手，不许被老条目永久压住")


def test_已有spec的候选跳过并出声(monkeypatch, tmp_path, capsys):
    """人工会话可能已经做过这一场：specs/reels/<slug>.json、pending/ 候车室、
    pending/ 草稿，任一存在就不用再 dispatch probe 备料——跳过要出声。"""
    o = _tool()
    specs = tmp_path / "reels"
    (specs / "pending").mkdir(parents=True)
    (specs / "a-b.json").write_text("{}", encoding="utf-8")
    (specs / "pending" / "c-d.draft.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(o, "SPECS_DIR", specs)
    cands = [{"slug": "a-b", "date": "2026-08-21"},
             {"slug": "c-d", "date": "2026-08-21"},
             {"slug": "e-f", "date": "2026-08-21"}]
    fresh = o.dispatch_plan(cands, {"dispatched": {}})
    assert [c["slug"] for c in fresh] == ["e-f"]
    out = capsys.readouterr().out
    assert "已有 spec" in out, "跳过不出声的样子和「没扫到」一模一样"


def test_文件名和slug对不上但球员相同也要跳过(monkeypatch, tmp_path, capsys):
    """2026-08-23 干跑实测撞上的：`gauff-bejlek-cincinnati-2026-sf.json` 刚
    合并进 main，`--dry-run` 还是把「贝莱克 vs 高芙」报成一条全新候选——
    `slug_for` 拼出来的是 `bejlek-gauff`（home 姓在前），文件名是赢家在前
    还带轮次后缀，`_already_specced` 按裸 slug 精确匹配根本查不到。

    真跑起来（`--apply`）就是一次白白的重复 dispatch，而且不报错，
    看起来和「这是条新比赛」一模一样。判据是**按姓的集合**去比对
    `cover.matchup`，不管文件名怎么起。
    """
    import json  # noqa: PLC0415
    o = _tool()
    specs = tmp_path / "reels"
    specs.mkdir(parents=True)
    (specs / "gauff-bejlek-cincinnati-2026-sf.json").write_text(json.dumps({
        "cover": {"matchup": [{"name": "高芙", "name_en": "Coco Gauff"},
                              {"name": "贝莱克", "name_en": "Sara Bejlek"}]},
    }), encoding="utf-8")
    monkeypatch.setattr(o, "SPECS_DIR", specs)

    cand = _fake_cand("bejlek-gauff", "Sara Bejlek", "Coco Gauff")
    fresh = o.dispatch_plan([cand], {"dispatched": {}})
    assert fresh == [], "同一对球员，只是文件名和 slug 顺序不一样，应该跳过"
    out = capsys.readouterr().out
    assert "同一对球员" in out, "跳过不出声的样子和「没扫到」一模一样"

    # 反面锚点：真的是另外两个人，不能被误伤
    other = _fake_cand("swiatek-pegula", "Iga Swiatek", "Jessica Pegula")
    fresh = o.dispatch_plan([other], {"dispatched": {}})
    assert fresh == [other], "不同球员不该被这层新加的检查误伤"

    # `home`/`away` 缺失时（老测试喂的最小候选字典）不该崩，也不该误判
    minimal = {"slug": "e-f", "date": "2026-08-21"}
    fresh = o.dispatch_plan([minimal], {"dispatched": {}})
    assert fresh == [minimal], "候选缺 home/away 时这层新检查要能优雅地放行"


def _fake_cand(slug, home, away):
    return {"slug": slug, "column": "reel", "score": 80, "heat": "世界前20",
            "level": "W1000", "round": "Final", "home": home, "away": away,
            "status": "finished", "event": "Cincinnati", "year": 2026,
            "date": "2026-08-21"}


def test_每条dispatch成功立即落盘(monkeypatch, tmp_path):
    """第 N 条 gh 失败时前 N-1 条已经点出去了——攒到循环后一次性记 state 的话，
    一条失败让之前全部失忆，下一班同一场 probe 重复点。所以每条成功立即落盘。"""
    import json
    import subprocess as sp

    import pytest
    o = _tool()
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(o, "STATE_PATH", state_file)
    monkeypatch.setattr(o, "SPECS_DIR", tmp_path / "specs")
    c1, c2 = _fake_cand("a-b", "A B", "C D"), _fake_cand("e-f", "E F", "G H")
    monkeypatch.setattr(o, "build_digest", lambda today: object())
    monkeypatch.setattr(o, "candidates", lambda dig: [c1, c2])
    fake_dh = type("M", (), {
        "HighlightSourceError": RuntimeError,
        "find_highlight": staticmethod(
            lambda h, a, e, y: ("https://yt/x", "youtube")),
    })()
    monkeypatch.setitem(sys.modules, "detect_highlights", fake_dh)

    def fake_run(cmd, check=True, **kw):
        if any("slug=e-f" in str(x) for x in cmd):
            raise sp.CalledProcessError(1, cmd)

    monkeypatch.setattr(sp, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["orchestrate.py", "--apply"])
    with pytest.raises(sp.CalledProcessError):
        o.main()
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert "a-b" in saved["dispatched"], (
        "第 1 条成功之后就该已经落盘——不落的话第 2 条一炸全部失忆")
    assert "e-f" not in saved["dispatched"], "失败的那条不许被记成已 dispatch"
    assert saved["dispatched"]["a-b"]["date"] == "2026-08-21", (
        "记的要是比赛日期，不是 dispatch 日期")


def test_探不到源的候选不占配额(monkeypatch, tmp_path):
    """配额切片要排在「真的会 dispatch」的过滤之后——老版本先切 [:max] 再跳过
    探不到源的，探不到的白占配额，探得到的反而排不进本班。"""
    import json
    import subprocess as sp
    o = _tool()
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(o, "STATE_PATH", state_file)
    monkeypatch.setattr(o, "SPECS_DIR", tmp_path / "specs")
    c1, c2 = _fake_cand("a-b", "A B", "C D"), _fake_cand("e-f", "E F", "G H")
    monkeypatch.setattr(o, "build_digest", lambda today: object())
    monkeypatch.setattr(o, "candidates", lambda dig: [c1, c2])
    fake_dh = type("M", (), {
        "HighlightSourceError": RuntimeError,
        "find_highlight": staticmethod(
            lambda h, a, e, y: (None, "") if h == "A B"
            else ("https://yt/2", "youtube")),
    })()
    monkeypatch.setitem(sys.modules, "detect_highlights", fake_dh)
    calls = []
    monkeypatch.setattr(sp, "run",
                        lambda cmd, check=True, **kw: calls.append(cmd))
    monkeypatch.setattr(sys, "argv", ["orchestrate.py", "--apply", "--max", "1"])
    assert o.main() == 0
    assert any("slug=e-f" in str(x) for cmd in calls for x in cmd), (
        "探得到源的那条被探不到的白占了配额（--max 1 全给了探空的 a-b）")
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert "e-f" in saved["dispatched"] and "a-b" not in saved["dispatched"]


def test_单场资源故障不阻塞其他比赛但整班要失败告警(monkeypatch, tmp_path, capsys):
    """源站错不能伪装成「还没发」，也不能让同批其他比赛失去时效性。"""
    import json
    import subprocess as sp
    o = _tool()
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(o, "STATE_PATH", state_file)
    monkeypatch.setattr(o, "SPECS_DIR", tmp_path / "specs")
    bad = _fake_cand("a-b", "A B", "C D")
    good = _fake_cand("e-f", "E F", "G H")
    monkeypatch.setattr(o, "build_digest", lambda today: object())
    monkeypatch.setattr(o, "candidates", lambda dig: [bad, good])

    class SourceError(RuntimeError):
        pass

    fake_dh = type("M", (), {
        "HighlightSourceError": SourceError,
        "find_highlight": staticmethod(
            lambda h, a, e, y: (_ for _ in ()).throw(SourceError("HTTP 429"))
            if h == "A B" else ("https://yt/2", "youtube")),
    })()
    monkeypatch.setitem(sys.modules, "detect_highlights", fake_dh)
    calls = []
    monkeypatch.setattr(sp, "run", lambda cmd, check=True, **kw: calls.append(cmd))
    monkeypatch.setattr(sys, "argv", ["orchestrate.py", "--apply"])

    assert o.main() == 2, "有源站错误时整班要返回非零，工作流才能告警"
    out = capsys.readouterr().out
    assert "a-b] 资源探测故障" in out and "HTTP 429" in out
    assert "a-b] 集锦还没探到" not in out, "故障不能伪装成资源尚未发布"
    assert any("slug=e-f" in str(x) for cmd in calls for x in cmd), (
        "一场源站错不该阻塞同批其他可用比赛")
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert "e-f" in saved["dispatched"] and "a-b" not in saved["dispatched"]


# ---------------------------------------------------------------------------
# 工作流判据。⚠️ 扫之前先剥整行注释——工作流注释正是记教训的地方，正文里
# 必然写着当年那些错值（CLAUDE.md「判据扫得太宽」那族）。不 import yaml
# （PyYAML 不在依赖里，CI 上会 ModuleNotFoundError）。


def _wf_text(name: str) -> str:
    body = (Path(".github/workflows") / name).read_text(encoding="utf-8")
    return "\n".join(l for l in body.splitlines()
                     if not l.lstrip().startswith("#"))


def test_编排工作流要装yt_dlp而且带default():
    body = _wf_text("orchestrate.yml")
    assert 'pip install -q -e . "yt-dlp[default]"' in body, (
        "orchestrate.yml 不装 yt-dlp 的话，detect_highlights 的探测每一班都"
        "安静地零候选——和「集锦还没发」长得一模一样；[default] 也不能省")


def test_编排工作流并发锁pipefail和state推送重试():
    """三样各拦一类静默坏：并发锁（两班并跑同一批候选点两遍 run）、
    pipefail（`python | tee` 的退出码是 tee 的，编排器崩了照样绿）、
    state 推送重试（裸 git push 一撞就红，而 run 已经点完、state 不落库
    下一班全部失忆重点）。

    ⚠️ 重试**不许**用 `git pull --rebase`：冲突就发生在 state 这个文件本身
    （match-reel 的失败自愈 release_orchestration_claim、相邻班次都改它），
    rebase 对同一个 JSON 的内容冲突无解——abort 之后什么都没变，重试只会撞
    同一个冲突。2026-08-26 run #360 连撞 5 次，state 丢失，下一班重复
    dispatch。重试要走 JSON 级三方合并（tools/merge_orchestration_state.py）
    并在 FETCH_HEAD 上重建提交。"""
    body = _wf_text("orchestrate.yml")
    assert "group: orchestrate" in body
    assert "cancel-in-progress: false" in body, (
        "掐掉正在 dispatch 的那班就是「点了 run 没记账」")
    assert "set -o pipefail" in body
    assert "seq 1 5" in body, "push 被拒要重试，不是一撞就红"
    state = _step_block("提交 state（定时或手动 apply）", "orchestrate.yml")
    assert "merge_orchestration_state.py" in state, (
        "state 推送重试没走三方合并——rebase 撞 state 自己的内容冲突时"
        "重试全灭，run 已点、state 丢，下一班重复 dispatch")
    assert "--base" in state and "--ours" in state and "--theirs" in state, (
        "三方合并三份快照缺一不可：少 base 分不出「本趟新增」和「远端已删」，"
        "会把 match-reel 刚 release 的 claim 复活")
    assert "git pull --rebase" not in _yaml_only(state), (
        "state 那一步又写回了 `git pull --rebase`——对同一个 JSON 的内容冲突"
        "它无解，见 docstring 里 run #360 的来路")
    assert "git reset --mixed FETCH_HEAD" in state, (
        "合并完要在远端最新之上重建提交；不 reset 的话旧提交还在，"
        "push 照样非快进被拒")


def test_定时编排每十分钟真apply且失败也提交已派发state():
    import re
    body = _wf_text("orchestrate.yml")
    cron = re.search(r'cron:\s*"([^"]+)"', body).group(1)
    minutes = sorted(int(x) for x in cron.split()[0].split(","))
    gaps = [b - a for a, b in zip(minutes, minutes[1:])]
    gaps.append(60 - minutes[-1] + minutes[0])
    assert max(gaps) <= 10, f"赛果探测最坏间隔仍有 {max(gaps)} 分钟，吃满出片 SLA"
    scan = _step_block("扫赛果/赛程并报告候选", "orchestrate.yml")
    assert 'github.event_name }}" = "schedule"' in scan
    assert "ARGS+=(--apply)" in scan, "定时班次仍然只 dry-run，不会启动任何制作"
    state = _step_block("提交 state（定时或手动 apply）", "orchestrate.yml")
    assert "if: always()" in state and "github.event_name == 'schedule'" in state, (
        "部分比赛源站失败时，已成功派发的 state 仍要落库，避免下一班重复制作")


def test_自动编排失败要通知微信():
    block = _step_block("扫描或派发失败时通知", "orchestrate.yml")
    assert "failure() || cancelled()" in block
    assert "PUSHPLUS_TOKEN" in block and "pushplus.plus/send" in block


def test_工作流max默认值和CLI是同一个数():
    """workflow 默认 3 / CLI 默认 8 分叉过：CLI 干跑按 8 排、工作流真点 run
    按 3 砍，后几场排到下一班白等 30 分钟。两处必须同一个数。"""
    import re
    o = _tool()
    body = _wf_text("orchestrate.yml")
    seg = body.split("max:", 1)[1].split("no_assemble:", 1)[0]
    m = re.search(r"default:\s*(\d+)", seg)
    assert m, "orchestrate.yml 的 max 输入找不到数字默认值"
    assert int(m.group(1)) == o.DEFAULT_MAX, (
        f"工作流 max 默认 {m.group(1)} ≠ CLI DEFAULT_MAX {o.DEFAULT_MAX}")


def _step_block(name: str, wf: str = "match-reel.yml") -> str:
    """取一个步骤块：先剥整行注释、锚在 `      - name: X` 步骤头上、按下一个
    整行步骤头切（CLAUDE.md「判据扫得太宽，被自己的注释误伤」那节的三条）。"""
    text = _wf_text(wf)
    anchor = f"      - name: {name}"
    i = text.index(anchor)
    rest = text[i + len(anchor):]
    j = rest.find("\n      - name:")
    return rest if j < 0 else rest[:j]


def test_probe备料要传cover自动抓官方封面():
    """assemble_spec 的 --cover（自动抓 WTA 官方实拍封面）写出来了，probe
    工作流一直没传——「能用的那台机器上没有开关」（CLAUDE.md 记过同形状）。
    抓不到时 assemble 自己留空出声，不会把 probe 带崩。"""
    import re
    block = _step_block("probe — 自动备料写 spec 草稿")
    assert "assemble_spec.py" in block
    assert re.search(r"--cover\s", block), (
        "probe 的自动备料没传 --cover——封面自动抓取那条路等于零")
    assert "--write" in block, "草稿要落盘，不然备料白跑"


def test_草稿提交路径指向pending不指向specs正下方():
    """specs/reels/ 正下方被一批非递归 glob("*.json") 判据扫着，`.draft.json`
    会被 `*.json` 命中——2026-08-18 一份草稿把 main CI 红过 2 小时
    （specs/reels/pending/README.md 记着来路）。"""
    body = _wf_text("match-reel.yml")
    assert ("specs/reels/pending/${{ github.event.inputs.slug }}.draft.json"
            in body), "草稿的提交路径要指向 pending/"
    assert ("specs/reels/${{ github.event.inputs.slug }}.draft.json"
            not in body), (
        "还有引用指着 specs/reels/ 正下方的草稿路径——那儿会把 main CI 打红")


def test_probe自动抓到的官方封面也要随草稿提交():
    block = _step_block("提交产物")
    assert 'assets/reel/${{ github.event.inputs.slug }}-cover.jpg' in block
    assert 'git add "$COVER_ASSET"' in block, (
        "assemble_spec 抓到的官方头图在 OUTDIR/pending 之外；不单独 add，"
        "草稿会引用一张 runner 消失后不存在的图片")


def test_场上采访每十五分钟探一次新资源():
    import re
    body = _wf_text("oncourt-interviews.yml")
    cron = re.search(r'cron:\s*"([^"]+)"', body).group(1)
    minutes = sorted(int(x) for x in cron.split()[0].split(","))
    gaps = [b - a for a, b in zip(minutes, minutes[1:])]
    gaps.append(60 - minutes[-1] + minutes[0])
    assert max(gaps) <= 15, (
        "采访采集本身就等 30 分钟，再叠加草稿/渲染/发布，很容易超过一小时")


# ── 无人值守链的两条「哑掉不吭声」判据（2026-08-25）─────────────────────────
#
# 来路：orchestrate 定时跑了 **330 趟，趟趟 success**，而
# `data/orchestration_state.json` 至今是 `{"dispatched": {}}`——一条 run 都没
# 点过，169 条 spec 没有一条是它产的。真因印在每一趟日志里：
#     [vet] <url> 元数据探不到（重试过一次）——先不用，下一班再探
#     [<slug>] 集锦还没探到，跳过，下次再探
# 同一条 URL 在沙箱里探得到（官方频道 / 379s / 1080p，三项全过），也就是候选
# 和集锦都在，**只有 runner 看不见**。`detect_highlights._cookie_args()` 本来就
# 读 `YT_COOKIES`，只是从来没人给它。

def _orchestrate_yml() -> str:
    return Path(".github/workflows/orchestrate.yml").read_text("utf-8")


def _yaml_only(text: str) -> str:
    """去掉整行注释再扫。

    ⚠️ 这个仓库的工作流注释正是记教训的地方——上面那段就写着 `YT_COOKIES`
    和「集锦还没探到」，连注释一起扫会把「把坑记下来」判成「已经接上了」。
    """
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith("#"))


def test_编排器要拿得到YouTube的钥匙否则探集锦每一班都静默零候选():
    body = _yaml_only(_orchestrate_yml())
    assert "YT_COOKIES_TXT" in body, (
        "orchestrate.yml 没有落 cookies 那一步——探集锦元数据会被 YouTube 的"
        "机房 IP 封锁挡住，而挡住的样子是「集锦还没探到，下次再探」，"
        "和「真的还没发布」分不开。330 趟 0 产出就是这么来的。")
    assert "YT_COOKIES:" in body, (
        "cookies 写到磁盘上了却没传给扫描那一步——"
        "detect_highlights._cookie_args() 读的是 `YT_COOKIES` 环境变量。")
    # ⚠️ **位置也要钉**：cookies 必须落在扫描之前，否则那一步拿到的是空串，
    # 而空串和「没配 Secret」的行为一模一样——又一次「写了不等于跑过」。
    assert body.index("YT_COOKIES_TXT") < body.index("扫赛果/赛程并报告候选"), \
        "落 cookies 那一步排在扫描之后了，扫描那一刻还拿不到路径"


def test_编排器点过run要留一个不过期的时刻(tmp_path, monkeypatch):
    """`last_dispatch_at` 是给监控用的：`dispatched` 里的条目 7 天后会被清掉，
    于是「从来没点过」和「点过但都过期了」在 state 上长得一模一样——而这两件事
    差着一整条产线。"""
    o = _tool()

    path = tmp_path / "state.json"
    monkeypatch.setattr(o, "STATE_PATH", path)

    state = {"dispatched": {}}
    o.mark_dispatched(state, [])
    assert "last_dispatch_at" not in json.loads(path.read_text("utf-8")), \
        "一条都没点却记了时刻——那就成了一盏恒亮的绿灯"

    o.mark_dispatched(state, [{"slug": "a-b", "column": "reel", "score": 60,
                               "date": "2026-08-25"}])
    saved = json.loads(path.read_text("utf-8"))
    assert saved.get("last_dispatch_at"), "真点了 run 却没留下时刻"

    # 条目过期之后这个时刻必须还在——否则监控又分不出上面那两种情况
    saved["dispatched"]["a-b"]["date"] = "2000-01-01"
    path.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
    reloaded = o.load_state()
    assert reloaded["dispatched"] == {}, "过期清理没生效，这条判据的前提没了"
    assert reloaded.get("last_dispatch_at"), \
        "TTL 清理把 last_dispatch_at 一起清掉了——它必须不过期"


def test_排名一个都没补上要当场喊出来(capsys):
    """⚠️ 排名整条取不到时，**候选列表照样打印得整整齐齐**，和正常那天长得
    一模一样——而 `match_score()` 的热度分档和爆冷判定这一轮全是瞎的。
    `fetch_rankings` 失败只有一句没人读的 `logger.warning`。这一行是那个
    「看得见」。
    """
    o = _tool()

    class _Dig:
        def __init__(self, matches):
            self.results, self.live, self.schedule = matches, [], []

    from tennislive.models import Player  # noqa: PLC0415

    def _m(ranks):
        m = _match2()
        m.home = [Player(name="A", rank=ranks[0])]
        m.away = [Player(name="B", rank=ranks[1])]
        return m

    o._report_rank_coverage(_Dig([_m((1, 5)), _m((None, None))]))
    out = capsys.readouterr().out
    assert "[排名] 覆盖 2/4" in out, f"没报覆盖率：{out!r}"
    assert "::warning::" not in out, "补上了一部分还告警，会变成告警风暴"

    o._report_rank_coverage(_Dig([_m((None, None))]))
    out = capsys.readouterr().out
    assert "[排名] 覆盖 0/2" in out
    assert "::warning::" in out and "瞎的" in out, \
        f"一个都没补上却不吭声——那正是这一行存在的理由：{out!r}"


def test_大满贯候选缺round和court时从官方feed补(monkeypatch, capsys):
    """美网期间 49 份 pending 草稿 49/49 卡在「缺 court」——flashscore 不给这两个
    字段。补上就是自动链在大满贯活过来的那半天。"""
    o = _tool()
    monkeypatch.setenv("TENNISLIVE_SLAM_FEED", "1")
    calls = []

    def fake(event, year, a, b):
        calls.append((event, year, a, b))
        return {"round": "第二轮", "court": "Court 4", "duration": "2:16", "source": "s"}

    cands = [
        {"slug": "wu-duckworth", "event": "US Open", "year": 2026, "home": "yibing wu",
         "away": "james duckworth", "round": "", "court": ""},
        {"slug": "a-b", "event": "Cincinnati Open", "year": 2026, "home": "a a", "away": "b b",
         "round": "", "court": ""},
        {"slug": "c-d", "event": "US Open", "year": 2026, "home": "c c", "away": "d d",
         "round": "第一轮", "court": "Court 5"},
    ]
    o.enrich_slam_fields(cands, lookup=fake)
    assert calls == [("US Open", 2026, "wu", "duckworth")], "只查认得的赛事、只查缺字段的"
    assert cands[0]["round"] == "第二轮" and cands[0]["court"] == "Court 4"
    assert cands[2]["round"] == "第一轮", "本来有的不许被覆盖"
    assert "补上 round=第二轮、court=Court 4" in capsys.readouterr().out


def test_官方feed挂了或查不到都出声不带崩(monkeypatch, capsys):
    o = _tool()
    monkeypatch.setenv("TENNISLIVE_SLAM_FEED", "1")
    cands = [{"slug": "x-y", "event": "US Open", "year": 2026, "home": "x x", "away": "y y",
              "round": "", "court": ""},
             {"slug": "p-q", "event": "US Open", "year": 2026, "home": "p p", "away": "q q",
              "round": "", "court": ""}]

    def boom(event, year, a, b):
        if a == "x":
            raise RuntimeError("HTTP 403")
        return None

    o.enrich_slam_fields(cands, lookup=boom)
    out = capsys.readouterr().out
    assert "补 round/court 失败" in out and "RuntimeError: HTTP 403" in out
    assert "没找到这一场" in out
    assert cands[0]["round"] == "" and cands[1]["court"] == ""


def test_环境变量关掉时一次都不查(monkeypatch):
    o = _tool()
    monkeypatch.setenv("TENNISLIVE_SLAM_FEED", "0")
    cands = [{"slug": "x-y", "event": "US Open", "year": 2026, "home": "x x", "away": "y y",
              "round": "", "court": ""}]

    def never(*a):
        raise AssertionError("关掉了还在查")

    o.enrich_slam_fields(cands, lookup=never)


def test_main在候选之后先补大满贯字段再排dispatch(monkeypatch):
    o = _tool()
    seen = {}
    monkeypatch.setattr(o, "build_digest", lambda today: type("D", (), {"results": [], "schedule": []})())
    monkeypatch.setattr(o, "candidates", lambda dig: [{"slug": "s", "column": "reel", "score": 50,
                                                       "home": "a", "away": "b", "event": "US Open",
                                                       "year": 2026, "round": "", "court": ""}])
    monkeypatch.setattr(o, "enrich_slam_fields", lambda cands, **kw: seen.setdefault("cands", list(cands)))
    # 只补还没 dispatch 的：dispatch_plan 说 s 已做过 → enrich 拿到的是空表
    monkeypatch.setattr(o, "dispatch_plan", lambda cands, state: [c for c in cands if c["slug"] != "s"])
    monkeypatch.setattr(o, "load_state", lambda: {})
    monkeypatch.setattr(sys, "argv", ["orchestrate.py"])
    assert o.main() == 0
    assert seen.get("cands") == [], "已经 dispatch 过的候选不该再去查官方 feed（每班 50 次白花的请求）"
    seen.clear()
    monkeypatch.setattr(o, "dispatch_plan", lambda cands, state: list(cands))
    assert o.main() == 0
    assert seen.get("cands") and seen["cands"][0]["slug"] == "s", "main 要真的调 enrich，不然闸永远缺 round/court"


def test_缩写名取姓取第一个词_全名取最后一个词():
    """2026-09-03 干跑：`Gorzny S.` / `Bu Y.` / `Sakamoto R.` 三条按末词取到 `S.`，官方 feed 当然查空。"""
    o = _tool()
    assert o._surname("Gorzny S.") == "Gorzny"
    assert o._surname("Bu Y.") == "Bu"
    assert o._surname("daniil medvedev") == "medvedev"
    assert o._surname("alex de minaur") == "minaur"
    assert o._surname("") == ""
