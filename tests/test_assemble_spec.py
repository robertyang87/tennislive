"""tools/assemble_spec.py —— 备料批处理（只测不联网的半截）。

不联网：assemble 只 mock 掉 `resolve_match_id` / `stats_block` / `collect` /
`points` / `rank_games`，验的是**拼装逻辑和退化出声**，不是 flashscore 的真调用。
（文案起草与窗口起草的模型步已于 2026-10-12 整体移除：assemble 不再产
`editorial`，只在 notes 里出声说明。）
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import assemble_spec as a  # noqa: PLC0415

    # 默认桩掉两个网络源：单元测试不许碰外网（conftest 清了 token，这里清网络）。
    # 想测聚合逻辑的测试再自己 monkeypatch 覆盖这两处。
    monkeypatch.setattr(a, "fetch_rankings",
                        lambda: type("R", (), {"atp": [], "wta": []})())
    monkeypatch.setattr(a, "fetch_zh_hot",
                        lambda **kw: type("H", (), {"hits": [], "scanned": 0})())
    return a


def test_surname取最后一个词():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["assemble_spec"] = mod  # dataclass 注解解析要回 sys.modules 查本模块
    spec.loader.exec_module(mod)
    assert mod._surname("Alexandra Eala") == "Eala"
    assert mod._surname("Elena-Gabriela Ruse") == "Ruse"
    assert mod._surname("单名") == "单名"
    # 缩写名（feed 的形状）姓在第一个词——出处只有一份 tennislive.names.surname_en
    assert mod._surname("Bu Y.") == "Bu" and mod._surname("Wolf J.J.") == "Wolf"


def test_facts_text把狠数据拼成行():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["assemble_spec"] = mod  # dataclass 注解解析要回 sys.modules 查本模块
    spec.loader.exec_module(mod)
    txt = mod.facts_text([
        {"label": "总分差", "detail": "甲 60 - 乙 50，净差 10 分"},
        {"label": "破发点兑现", "detail": "6/11（55%）"},
    ])
    assert "- 总分差: 甲 60 - 乙 50，净差 10 分" in txt
    assert "- 破发点兑现: 6/11（55%）" in txt
    assert mod.facts_text([]) == ""


def test_逐局表提取最终盘分并拦模型编错比分():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["assemble_spec"] = mod  # dataclass 注解解析要回 sys.modules 查本模块
    spec.loader.exec_module(mod)
    games = [
        {"set": "Set 1", "home_games": "1", "away_games": "0"},
        {"set": "Set 1", "home_games": "4", "away_games": "6"},
        {"set": "Set 2", "home_games": "6", "away_games": "1"},
        {"set": "Set 3", "home_games": "6", "away_games": "1"},
    ]
    scores = mod.final_set_scores(games)
    assert scores == [(4, 6), (6, 1), (6, 1)]
    assert "4-6 6-1 6-1" in mod.score_fact(scores, "斯瓦泰克", "萨卡里")
    wrong = {"thesis": "她最终以6-4、3-6、6-4险胜", "narration": []}
    assert "不一致" in mod.editorial_score_problem(wrong, scores)
    right = {"thesis": "她最终以4-6、6-1、6-1逆转", "narration": []}
    assert mod.editorial_score_problem(right, scores) is None
    reversed_right = {"thesis": "对手视角是6-4、1-6、1-6", "narration": []}
    assert mod.editorial_score_problem(reversed_right, scores) is None


def test_总分方向机械事实与medvedev_damm回归(tool):
    stats = {"a": {"pts_won": 56}, "b": {"pts_won": 67}}
    matchup = [{"name": "梅德韦杰夫"}, {"name": "小马丁·达姆"}]
    scores = [(5, 7), (3, 6)]
    fact = tool.total_points_fact(stats, matchup)
    assert "小马丁·达姆比梅德韦杰夫多 11 分" in fact
    wrong = {
        "thesis": "梅德韦杰夫总分多拿11分，却连丢两盘",
        "narration": ["总分领先也没能挽回败局"],
    }
    assert "方向写反" in tool.editorial_total_points_problem(
        wrong, stats, matchup, scores)
    right = {
        "thesis": "小马丁·达姆全场多拿11分，以5-7、3-6获胜",
        "narration": ["梅德韦杰夫56比67落后11分"],
    }
    assert tool.editorial_total_points_problem(right, stats, matchup, scores) is None


def test_总分领先者也是赢家时拦无主语领先却输(tool):
    stats = {"a": {"pts_won": 56}, "b": {"pts_won": 67}}
    matchup = [{"name": "梅德韦杰夫"}, {"name": "小马丁·达姆"}]
    content = {"lead": "全场多拿11分，却最终输掉比赛"}
    assert "也是比赛赢家" in tool.editorial_total_points_problem(
        content, stats, matchup, [(5, 7), (3, 6)])


def test_爆冷封面优先明星输家还在拼的近景(tool):
    """账号所有者 2026-08-15（arango-venus）：拍输家拍他在拼，不拍他垮掉。"""
    matchup = [
        {"name": "梅德韦杰夫", "name_en": "Daniil Medvedev", "rank": 8},
        {"name": "小马丁·达姆", "name_en": "Martin Damm", "rank": 92},
    ]
    brief = tool.upset_cover_brief(matchup, [(5, 7), (3, 6)])
    assert brief["preferred_subject"] == "梅德韦杰夫"
    assert "仍在拼" in brief["preferred_moment"]
    assert "不要低头垮掉" in brief["preferred_moment"]
    assert "失落" not in brief["preferred_moment"]
    assert brief["fallback_subject"] == "小马丁·达姆"


def test_普通比赛不误套爆冷明星封面(tool):
    close_rank = [{"name": "甲", "rank": 8}, {"name": "乙", "rank": 21}]
    assert tool.upset_cover_brief(close_rank, [(4, 6), (6, 3), (4, 6)]) is None
    non_star = [{"name": "甲", "rank": 55}, {"name": "乙", "rank": 100}]
    assert tool.upset_cover_brief(non_star, [(4, 6), (6, 3), (4, 6)]) is None


def test_无字幕时从probe切点生成不跨镜头窗口(tool, tmp_path):
    probe = tmp_path / "probe.json"
    probe.write_text(json.dumps({
        "duration": 158.4,
        "scene_cuts": [2.07, 14.0, 29.83, 33.8, 45.53, 49.9, 57.73,
                       69.13, 78.8, 81.77, 85.57, 91.7, 95.63, 104.03,
                       107.93, 111.27, 128.07, 132.17, 136.67, 149.5],
    }), encoding="utf-8")
    narration = [
        "第一段旁白需要装得下。", "第二段旁白也不能跨切点。", "最后是比赛结果。"]
    segments = tool.scene_cut_segments(str(probe), narration)
    assert [s["narration"] for s in segments] == narration
    assert [s["_beat"] for s in segments] == [1, 2, 3], "章节卡按 _beat 定位"
    assert all(segments[i]["end"] <= segments[i + 1]["start"]
               for i in range(len(segments) - 1))
    cuts = json.loads(probe.read_text(encoding="utf-8"))["scene_cuts"]
    assert not any(s["start"] < cut < s["end"] for s in segments for cut in cuts)


def test_tennistv封面从本场官方页请求4000宽原图(tool, tmp_path):
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4000, 2666), "#123456").save(buf, format="JPEG")
    calls = []

    class Response:
        def __init__(self, *, text="", content=b""):
            self.text = text
            self.content = content

        def raise_for_status(self):
            return None

    def get(url, **kwargs):
        calls.append(url)
        if "tennistv.com" in url:
            return Response(text=(
                '<span itemprop="thumbnailUrl" content="https://resources.prod.'
                'atpmedia.pulselive.com/photo/Winston-Salem-Damm.jpg?'
                'height=268&amp;width=451">'))
        return Response(content=buf.getvalue())

    out = tmp_path / "cover.jpg"
    note = tool.fetch_tennistv_cover(
        "https://www.tennistv.com/videos/1/demo", "Winston-Salem", out, get=get)
    assert out.is_file()
    assert "4000×2666" in note
    assert calls[-1].endswith("width=4000") and "height=" not in calls[-1]


def test_tennistv封面拒绝别站资料图(tool, tmp_path):
    class Response:
        text = ('<span itemprop="thumbnailUrl" content="https://resources.prod.'
                'atpmedia.pulselive.com/photo/2026-Washington-Damm.jpg?width=451">')

        def raise_for_status(self):
            return None

    with pytest.raises(ValueError, match="拒绝资料图"):
        tool.fetch_tennistv_cover(
            "https://www.tennistv.com/videos/1/demo", "Winston-Salem",
            tmp_path / "cover.jpg", get=lambda *a, **kw: Response())


def test_matchup_order按flashscore的home归位(monkeypatch):
    """核心判据：stats.a 跟 flashscore 的 home，而 render_stat_card 的 a 跟
    matchup[0]——所以 matchup 顺序必须跟 flashscore 的 home/away，不是命令行。
    命令行传反了（--home 是 feed 里的 away），数据图会把 a 的数字挂在错的人名下。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["assemble_spec"] = mod  # dataclass 注解解析要回 sys.modules 查本模块
    spec.loader.exec_module(mod)
    # feed 里 home = Baez S.，away = Dimitrov G.；命令行传反了顺序
    monkeypatch.setattr(mod, "fs_feed", lambda name, mid: "FH÷Baez S.¬FK÷Dimitrov G.¬~...")
    ordered = mod.matchup_order("Grigor Dimitrov", "Sebastian Baez", "v51JjQ2D")
    assert [en for en, zh in ordered] == ["Sebastian Baez", "Grigor Dimitrov"], (
        "matchup 顺序必须跟 flashscore 的 home(Baez)/away(Dimitrov)，"
        "不是命令行传入的顺序——否则 stats.a 会挂在 Dimitrov 名下")


def test_matchup_order_selects_requested_match_before_historical_reverse(tool, monkeypatch):
    body = ("SA÷2¬~KP÷8QYQMw6l¬FH÷Sabalenka A.¬FK÷Noskova L.¬~"
            "KP÷oldmatch¬FH÷Noskova L.¬FK÷Sabalenka A.¬")
    monkeypatch.setattr(tool, "fs_feed", lambda *args: body)
    ordered = tool.matchup_order("Linda Noskova", "Aryna Sabalenka", "8QYQMw6l")
    assert [name for name, _ in ordered] == ["Aryna Sabalenka", "Linda Noskova"]


def test_matchup_order核不出顺序就抛_不退回命令行顺序(monkeypatch):
    """命令行顺序和 feed 的 home/away 是两回事：核不出就说核不出，由 assemble
    跳过按 home/away 排的几块（原来退回命令行顺序，赛果事实会把赢家算反——
    整条回放见 test_source_probe_robustness 的 `test_df_hh_1读不到时不许出result_verified`）。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["assemble_spec"] = mod  # dataclass 注解解析要回 sys.modules 查本模块
    spec.loader.exec_module(mod)

    def _boom(name, mid):
        raise RuntimeError("net down")

    def _exit(name, mid):
        raise SystemExit("https://x/df_hh_1_x\n  HTTP 503 —— 被挡还是不存在")

    for feed, want in ((_boom, "net down"), (_exit, "HTTP 503")):
        monkeypatch.setattr(mod, "fs_feed", feed)
        with pytest.raises(mod.MatchupOrderUnverified, match=want):
            mod.matchup_order("A E", "B R", "x")
    # 没给 FH/FK、两边真分不开（同姓、缩写名首字母也一样），都是核不出——不是命令行顺序
    monkeypatch.setattr(mod, "fs_feed", lambda *_a: "SA÷2¬~")
    with pytest.raises(mod.MatchupOrderUnverified, match="FH/FK"):
        mod.matchup_order("A E", "B R", "x")
    monkeypatch.setattr(mod, "fs_feed",
                        lambda *_a: "KP÷x¬FH÷Wang X.¬FK÷Wang X.¬~")
    with pytest.raises(mod.MatchupOrderUnverified, match="按姓认不出"):
        mod.matchup_order("Xinyu Wang", "Xiyu Wang", "x")
    # 同姓但缩写名分得开（2026-10-14 speedcheck 的 FH='Wang Xiy.' FK='Wang Xin.'）：按名字归位，
    # 命令行顺序反着传也照 feed 的 home/away 排
    monkeypatch.setattr(mod, "fs_feed",
                        lambda *_a: "KP÷x¬FH÷Wang Xiy.¬FK÷Wang Xin.¬~")
    assert [n for n, _zh in mod.matchup_order("Xinyu Wang", "Xiyu Wang", "x")] == [
        "Xiyu Wang", "Xinyu Wang"]


def test_狠数据和转折局的名字按feed的home_away给(tool, monkeypatch):
    """`collect` / `_label` 拿 home 那个名字去标 feed 里 SH / server=home 那一列。
    matchup 重排过（命令行 --home 是 feed 的 away）时还按命令行顺序传，赢家的
    总分、破发点兑现就标在输家名下，还喂进文案 facts。"""
    a = tool
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(aw, a.player_zh(aw)), (h, a.player_zh(h))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    got = {}
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: got.update(names=(h, aw)) or {
        "candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [{
        "set": "1", "home_games": "5", "away_games": "6",
        "server": "home", "winner": "away", "broken": True,
        "points": "", "break_points": 1, "set_points": 0, "match_points": 0}])
    monkeypatch.setattr(a, "rank_games", lambda games: [{
        **games[0], "density": 2, "tags": []}])
    monkeypatch.setattr(a, "set_pairs", lambda mid: [])

    draft = a.assemble(slug="x", home="Alexandra Eala", away="Elena-Gabriela Ruse",
                       event="Cincinnati", year=2026, fixture="北京时间",
                       flashscore_id="4CYI9Ick", tactical_packet={"status": "skipped"})
    eala, ruse = a.player_zh("Alexandra Eala"), a.player_zh("Elena-Gabriela Ruse")
    assert [p["name"] for p in draft["cover"]["matchup"]] == [ruse, eala]
    assert got["names"] == (ruse, eala), "collect 的 home 名字要是 feed 的 home（matchup[0]）"
    label = draft["_turning_points"][0]["label"]
    assert f"{ruse}发球，{eala}拿下" in label, label


def test_assemble无id时跳过三块并出声(tool, monkeypatch):
    a = tool
    # 反查失败 → 无 id → stats/狠数据/转折局都该跳过，但仍写草稿 + 出声
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: None)
    draft = a.assemble(slug="x", home="Alexandra Eala", away="Elena-Gabriela Ruse",
                       event="Cincinnati", year=2026, fixture="北京时间",
                       flashscore_id=None)
    assert draft["_draft"] is True
    assert "_match" not in draft
    assert "stats" not in draft and "_hit_data" not in draft
    assert "_turning_points" not in draft
    joined = "\n".join(draft["_notes"])
    assert "没反查到 flashscore id" in joined, "缺 id 必须出声，不许静默"
    assert "文案起草已随模型通道移除" in joined, "文案那一步没了也要出声，不许装作本来就没有"
    assert draft["cover"]["matchup"][0]["name_en"] == "Alexandra Eala"


def test_assemble有id时各块拼装(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {"aces": 0}, "b": {"aces": 0},
        "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {
        "candidates": [{"label": "总分差", "detail": "净差 10 分"}],
        "durations": [("全场", "1:31")]})
    monkeypatch.setattr(a, "points", lambda mid: [{
        "set": "1", "home_games": "5", "away_games": "6",
        "server": "home", "winner": "away", "broken": True,
        "points": "HL|B2|", "break_points": 0, "set_points": 1,
        "match_points": 0}])
    monkeypatch.setattr(a, "rank_games", lambda games: [{
        **games[0], "density": 2, "tags": ["1个盘点"]}])
    monkeypatch.setattr(a, "set_pairs", lambda mid: [])

    draft = a.assemble(slug="x", home="Alexandra Eala", away="Elena-Gabriela Ruse",
                       event="Cincinnati", year=2026, fixture="北京时间",
                       flashscore_id="4CYI9Ick")
    assert draft["_match"]["flashscore_id"] == "4CYI9Ick"
    # 数据图头像在 stats 块之后机械补上：这两位在已发 spec 里认过，走索引复用
    # （不摸网——conftest 把现抓关了）。去掉它之后其余字段要原样。
    assert draft["stats"]["a"].pop("headshot").startswith("assets/players/headshots/")
    assert draft["stats"]["b"].pop("headshot").startswith("assets/players/headshots/")
    assert draft["stats"] == {"a": {"aces": 0}, "b": {"aces": 0}}
    assert draft["_hit_data"][0]["label"] == "总分差"
    assert draft["_turning_points"][0]["density"] == 2
    # 文案起草已随模型通道移除：editorial 不再产，只出声
    assert "editorial" not in draft
    assert any("文案起草已随模型通道移除" in n for n in draft["_notes"])


class _Entry:
    """rank_map 只吃 `.name` / `.rank`，给个最小 RankEntry 形状。"""

    def __init__(self, name: str, rank: int):
        self.name = name
        self.rank = rank


def test_build_background聚合H2H近况排名热点(tool, monkeypatch):
    """四个机械源要一起进 background：H2H + 近况（从 hit_data 拎）+ 排名 + 中文热点。"""
    a = tool
    monkeypatch.setattr(a, "fetch_rankings", lambda: type("R", (), {
        "atp": [_Entry("Alexandra Eala", 140)],
        "wta": [_Entry("Jessica Pegula", 9)],
    })())
    monkeypatch.setattr(a, "fetch_zh_hot", lambda **kw: type("H", (), {
        "hits": [{"word": "郑钦文状态怎么了", "source": "微博热搜",
                  "terms": ("eala",), "matched": ("伊埃拉",)}],
        "scanned": 232,
    })())

    hit = [
        {"label": "交手记录", "detail": "Eala A. 0 : 1 Pegula J."},
        {"label": "近况", "detail": "Eala A. 最近 5 场 4 胜（WWWLW）；Pegula J. 最近 5 场 3 胜（WLWLW）"},
        {"label": "总分差", "detail": "净差 4 分"},  # 狠数据不进 background，只进 facts
    ]
    text, notes = a.build_background("Alexandra Eala", "Jessica Pegula", hit)
    assert "交手记录：Eala A. 0 : 1 Pegula J." in text
    assert "近况：Eala A. 最近 5 场 4 胜" in text
    assert "排名：伊埃拉 世界第 140；佩古拉 世界第 9" in text
    assert "中文热搜：郑钦文状态怎么了（微博热搜）" in text
    assert "总分差" not in text, "狠数据只进 facts，不进 background——背景是「这个人」，不是「这个比分」"
    assert not notes, f"四个源都成功，不该有失败 note：{notes}"


def test_build_background读取生产ZhHot对象而不只认测试字典(tool, monkeypatch):
    """真实 ``fetch_zh_hot`` 返回 ``ZhHot`` dataclass。

    旧测试只塞 dict，导致生产对象走到 ``h.get`` 必炸，草稿里的中文热点背景长期
    静默降级。用真实类型钉住边界，不能再让测试桩和生产接口分叉。
    """
    from tennislive.research.zh_trends import ZhHot

    a = tool
    monkeypatch.setattr(a, "fetch_zh_hot", lambda **kw: type("H", (), {
        "hits": [ZhHot(source="微博热搜", word="伊埃拉晋级",
                       rank=8, heat="热", url="https://example.test/hot",
                       terms=("eala",), matched=("伊埃拉",))],
        "scanned": 232,
    })())
    text, notes = a.build_background("Alexandra Eala", "Jessica Pegula", [])
    assert "中文热搜：伊埃拉晋级（微博热搜）" in text
    assert not any("AttributeError" in note for note in notes)


def test_build_background排名源挂了不拖垮(tool, monkeypatch):
    """一个源挂了只写 note，背景仍返回能拿到的部分——退化要出声不静默。"""
    a = tool
    monkeypatch.setattr(a, "fetch_rankings", lambda: (_ for _ in ()).throw(ConnectionError("down")))
    monkeypatch.setattr(a, "fetch_zh_hot",
                        lambda **kw: type("H", (), {"hits": [], "scanned": 0})())
    hit = [{"label": "交手记录", "detail": "Eala A. 1 : 0 Pegula J."}]
    text, notes = a.build_background("Alexandra Eala", "Jessica Pegula", hit)
    assert "交手记录" in text, "排名挂了 H2H 还得在"
    assert any("排名没成" in n for n in notes), "排名失败要出声"


def test_build_background热点撞不上不是抓挂了(tool, monkeypatch):
    """中文热榜上没这两位是常态，note 要把「撞不上」和「抓挂了」分开说。"""
    a = tool
    monkeypatch.setattr(a, "fetch_rankings",
                        lambda: type("R", (), {"atp": [], "wta": []})())
    monkeypatch.setattr(a, "fetch_zh_hot",
                        lambda **kw: type("H", (), {"hits": [], "scanned": 232})())
    _, notes = a.build_background("Alexandra Eala", "Jessica Pegula", [])
    assert any("扫 232 条" in n and "没有撞上" in n for n in notes), (
        "扫了 232 条却没撞上，note 要说清是「扫了但没有」，别和「抓挂了」混在一起")


def test_assemble给source_url写进草稿(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])
    monkeypatch.setattr(a, "set_pairs", lambda mid: [])

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick",
                       source_url="https://youtube.com/watch?v=abc")
    assert draft["source_url"] == "https://youtube.com/watch?v=abc", (
        "source_url 是 render 硬要求，编排器探测集锦时拿到就该写进草稿")
    # 没给 source_url 时不该有这键（render 会明确报错，比空值更响）
    draft2 = a.assemble(slug="y", home="A E", away="B R", event="C", year=2026,
                        fixture="", flashscore_id="4CYI9Ick")
    assert "source_url" not in draft2


def test_assemble文案起草已移除_不产editorial且出声(tool, monkeypatch):
    """2026-10-12 模型通道整体移除后，assemble 不再起草文案：草稿里没有
    `editorial`，notes 里必须明说这一步没了——不许把缺 editorial 的草稿
    装成「本来就没配」。"""
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])
    monkeypatch.setattr(a, "set_pairs", lambda mid: [])

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick")
    assert "editorial" not in draft
    assert any("文案起草已随模型通道移除" in n for n in draft["_notes"])


def test_assemble没给对齐材料segments留空(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])
    monkeypatch.setattr(a, "set_pairs", lambda mid: [])

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick")
    assert "segments" not in draft, (
        "没给逐分+比分板就没有机械对齐的窗口；读字幕起草窗口的那条模型路已移除，"
        "不许凭空生成 segments")


def test_assemble机械对齐优先于读字幕(tool, monkeypatch, tmp_path):
    """给了 pbp + scoreboard 就走 align_points 机械对齐出 segments，标
    `_segments_source`。旁白原来由文案起草喂进来；那一步已随模型通道移除，
    窗口照样按锚点出骨架、旁白留空给终审。"""
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])

    # 合成逐分：B 发球被 A 破发（第 3 分是破发点 40-0）
    def _pt(pa, pb, winner="A"):
        return {"setNumber": 1, "gameNumber": 1, "server": "B", "pointWinner": winner,
                "scoreAfterPoint": {"gameScore": {"teamAScore": pa, "teamBScore": pb}}}
    pbp = tmp_path / "pbp.json"
    pbp.write_text(json.dumps({"raw": {"points": [
        _pt("15", "0"), _pt("30", "0"), _pt("40", "0"), _pt("G", "0")]}},
        ensure_ascii=False), encoding="utf-8")
    sb = tmp_path / "scoreboard.json"
    sb.write_text(json.dumps([{"t": 10.0, "score": "0 0 40 0"}], ensure_ascii=False),
                  encoding="utf-8")

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick",
                       pbp_path=str(pbp), scoreboard_path=str(sb))
    assert draft.get("_segments_source", "").startswith("align_points"), (
        "机械对齐的 segments 要标出来源，别和读字幕那条路混")
    assert len(draft["segments"]) >= 4, "冷开场 + 三个 beat 至少 4 段"
    assert draft["segments"][0]["narration"] == "", "冷开场不配旁白"
    assert any("窗口机械对齐" in n for n in draft["_notes"])


def test_assemble封面抓到写portrait(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])

    # 打桩封面反查 + 抓取两个模块（都在 assemble 函数内 import）
    fake_pbp = type("M", (), {"find_match": staticmethod(
        lambda session, players, since, until: ("1017", 2026, "LS061", {}))})()
    fake_cover = type("M", (), {"fetch_cover": staticmethod(
        lambda *a, **kw: (0, "已存封面（4700×2957）"))})()
    monkeypatch.setitem(sys.modules, "fetch_match_pbp", fake_pbp)
    monkeypatch.setitem(sys.modules, "fetch_wta_cover_photo", fake_cover)
    # requests 要 mock 成**模块**（有 Session 这个类属性），不是实例——
    # `import requests` 拿到的必须是模块，requests.Session() 才调得动。
    monkeypatch.setitem(sys.modules, "requests",
                        type("requests", (), {"Session": staticmethod(lambda: object())})())

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick", cover=True)
    assert draft["cover"]["portrait"]["image"].endswith("x-cover.jpg"), (
        "抓到了封面要写进 cover.portrait.image")
    assert any("封面官方实拍" in n for n in draft["_notes"])


def test_assemble封面没抓到留空出声(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])

    fake_pbp = type("M", (), {"find_match": staticmethod(
        lambda session, players, since, until: ("1017", 2026, "LS061", {}))})()
    fake_cover = type("M", (), {"fetch_cover": staticmethod(
        lambda *a, **kw: (2, "稿子还没挂"))})()
    monkeypatch.setitem(sys.modules, "fetch_match_pbp", fake_pbp)
    monkeypatch.setitem(sys.modules, "fetch_wta_cover_photo", fake_cover)
    monkeypatch.setitem(sys.modules, "requests",
                        type("requests", (), {"Session": staticmethod(lambda: object())})())

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick", cover=True)
    assert "portrait" not in draft.get("cover", {}), "抓不到就留空，别硬塞"
    assert any("封面没抓到" in n for n in draft["_notes"]), "抓不到要出声"


def test_ATP比赛查不到WTA封面不许杀掉整份草稿(tool, monkeypatch):
    """Medvedev–Damm #1206 的真实回归：WTA find_match 用 SystemExit 报空。

    这发生在 spec 已经完成文案/窗口之后，必须只记 note，不能让进程退出、跳过
    pending 草稿提交。ATP 没有 WTA 官方赛后稿头图是正常降级，不是生产失败。
    """
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: None)
    fake_pbp = type("M", (), {"find_match": staticmethod(
        lambda *args, **kwargs: (_ for _ in ()).throw(
            SystemExit("WTA 窗口里没有 medvedev/damm")))})()
    monkeypatch.setitem(sys.modules, "fetch_match_pbp", fake_pbp)
    monkeypatch.setitem(sys.modules, "requests",
                        type("requests", (), {"Session": staticmethod(lambda: object())})())

    draft = a.assemble(
        slug="medvedev-damm", home="Daniil Medvedev", away="Martin Damm",
        event="Winston-Salem", year=2026, fixture="", flashscore_id=None,
        cover=True, source_url=(
            "https://www.tennistv.com/videos/4566516/"
            "winston-salem-2026-r2-medvedev-damm-short-highlights"),
    )

    assert draft["slug"] == "medvedev-damm"
    assert draft["source_url"].startswith("https://www.tennistv.com/")
    assert any("SystemExit" in note and "封面抓取没成" in note
               for note in draft["_notes"])


def test_main写出草稿文件(tool, monkeypatch, tmp_path, capsys):
    a = tool
    monkeypatch.setattr(a, "assemble", lambda **kw: {
        "_draft": True, "slug": kw["slug"], "cover": {"matchup": []},
        "_notes": ["flashscore id：4CYI9Ick（给定）"]})
    # ⚠️ DRAFT_DIR 是 import 时按 __file__ 算好的**绝对路径**——不改它的话，
    # 这条测试会把 demo.draft.json 真写进仓库的 specs/reels/pending/。
    monkeypatch.setattr(a, "DRAFT_DIR", tmp_path / "pending")
    monkeypatch.setattr(sys, "argv", [
        "assemble_spec.py", "--slug", "demo", "--home", "A E", "--away", "B R",
        "--write"])
    rc = a.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "草稿 →" in out
    assert (tmp_path / "pending" / "demo.draft.json").is_file(), (
        "--write 要把草稿真的落在 DRAFT_DIR（pending/）里")


def test_main默认不落盘(tool, monkeypatch, tmp_path, capsys):
    a = tool
    monkeypatch.setattr(a, "assemble", lambda **kw: {
        "_draft": True, "slug": kw["slug"], "cover": {"matchup": []},
        "_notes": []})
    monkeypatch.setattr(a, "DRAFT_DIR", tmp_path / "pending")
    monkeypatch.setattr(sys, "argv", [
        "assemble_spec.py", "--slug", "demo", "--home", "A E", "--away", "B R"])
    rc = a.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "没落盘" in out and "草稿 →" not in out, (
        "默认必须只打印不写文件——手动控制要先看后写，别默认就把草稿落进仓库")
    assert not (tmp_path / "pending").exists(), "默认不落盘，连草稿目录都不该建"


def test_草稿目录钉在pending不许漏回specs正下方(tool):
    """specs/reels/ 正下方被一批**非递归** `glob("*.json")` 的判据测试扫着，
    `.draft.json` 会被 `*.json` 命中——2026-08-18 一份草稿把 main CI 红过
    2 小时（specs/reels/pending/README.md 记着来路）。所以草稿只许落
    pending/，而且存量一份都不许漏在外面。"""
    a = tool
    assert a.DRAFT_DIR.parts[-3:] == ("specs", "reels", "pending"), a.DRAFT_DIR
    repo = Path(__file__).resolve().parents[1]
    strays = sorted((repo / "specs" / "reels").glob("*.draft.json"))
    assert not strays, (
        f"specs/reels/ 正下方混进了草稿（会打红非递归 glob 的判据）：{strays}")
