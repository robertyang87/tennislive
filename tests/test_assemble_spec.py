"""tools/assemble_spec.py —— 备料批处理（只测不联网的半截）。

不联网：assemble 只 mock 掉 `resolve_match_id` / `stats_block` / `collect` /
`points` / `rank_games` / `Chat` / `draft_editorial`，验的是**拼装逻辑和退化出声**，
不是 flashscore/DeepSeek 的真调用。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import assemble_spec as a  # noqa: PLC0415

    return a


def test_surname取最后一个词():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._surname("Alexandra Eala") == "Eala"
    assert mod._surname("Elena-Gabriela Ruse") == "Ruse"
    assert mod._surname("单名") == "单名"


def test_facts_text把狠数据拼成行():
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    txt = mod.facts_text([
        {"label": "总分差", "detail": "甲 60 - 乙 50，净差 10 分"},
        {"label": "破发点兑现", "detail": "6/11（55%）"},
    ])
    assert "- 总分差: 甲 60 - 乙 50，净差 10 分" in txt
    assert "- 破发点兑现: 6/11（55%）" in txt
    assert mod.facts_text([]) == ""


def test_matchup_order按flashscore的home归位(monkeypatch):
    """核心判据：stats.a 跟 flashscore 的 home，而 render_stat_card 的 a 跟
    matchup[0]——所以 matchup 顺序必须跟 flashscore 的 home/away，不是命令行。
    命令行传反了（--home 是 feed 里的 away），数据图会把 a 的数字挂在错的人名下。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # feed 里 home = Baez S.，away = Dimitrov G.；命令行传反了顺序
    monkeypatch.setattr(mod, "fs_feed", lambda name, mid: "FH÷Baez S.¬FK÷Dimitrov G.¬~...")
    ordered = mod.matchup_order("Grigor Dimitrov", "Sebastian Baez", "v51JjQ2D")
    assert [en for en, zh in ordered] == ["Sebastian Baez", "Grigor Dimitrov"], (
        "matchup 顺序必须跟 flashscore 的 home(Baez)/away(Dimitrov)，"
        "不是命令行传入的顺序——否则 stats.a 会挂在 Dimitrov 名下")


def test_matchup_order读不到feed退回命令行顺序(monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("assemble_spec", _TOOLS / "assemble_spec.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def _boom(name, mid):
        raise RuntimeError("net down")

    monkeypatch.setattr(mod, "fs_feed", _boom)
    ordered = mod.matchup_order("A E", "B R", "x")
    assert [en for en, zh in ordered] == ["A E", "B R"], (
        "读不到 feed 就退回命令行顺序——但那时 stats 块也没生成，谈不上错位")


def test_assemble无id时跳过三块并出声(tool, monkeypatch):
    a = tool
    # 反查失败 → 无 id → stats/狠数据/转折局都该跳过，但仍写草稿 + 出声
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: None)

    class NotReady:
        ready = False

    monkeypatch.setattr(a, "Chat", lambda: NotReady())
    draft = a.assemble(slug="x", home="Alexandra Eala", away="Elena-Gabriela Ruse",
                       event="Cincinnati", year=2026, fixture="北京时间",
                       flashscore_id=None)
    assert draft["_draft"] is True
    assert "_match" not in draft
    assert "stats" not in draft and "_hit_data" not in draft
    assert "_turning_points" not in draft
    joined = "\n".join(draft["_notes"])
    assert "没反查到 flashscore id" in joined, "缺 id 必须出声，不许静默"
    assert "文案跳过" in joined or "没配" in joined, "缺 key 也要出声"
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

    captured = {}

    class FakeChat:
        ready = True
        channel = "deepseek · test"

        def ask(self, *a, **kw):
            return {}

    monkeypatch.setattr(a, "Chat", lambda: FakeChat())
    monkeypatch.setattr(a, "draft_editorial",
                        lambda chat, **kw: captured.update(kw) or {
                            "hook": ["a"], "question": "q", "thesis": "t",
                            "beats": ["b"], "human_context": "h", "narration": ["n"]})

    draft = a.assemble(slug="x", home="Alexandra Eala", away="Elena-Gabriela Ruse",
                       event="Cincinnati", year=2026, fixture="北京时间",
                       flashscore_id="4CYI9Ick")
    assert draft["_match"]["flashscore_id"] == "4CYI9Ick"
    assert draft["stats"] == {"a": {"aces": 0}, "b": {"aces": 0}}
    assert draft["_hit_data"][0]["label"] == "总分差"
    assert draft["_turning_points"][0]["density"] == 2
    assert draft["editorial"]["hook"] == ["a"]
    # draft_spec 收到了狠数据当 facts（文案要能用到算出来的数字）
    assert "净差 10 分" in captured["facts"]
    assert captured["fixture"] == "北京时间"


def test_assemble有id但文案失败时不静默(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])
    monkeypatch.setattr(a, "Chat", lambda: type("C", (), {"ready": True, "channel": "x"})())
    monkeypatch.setattr(a, "draft_editorial", lambda chat, **kw: None)

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick")
    assert "editorial" not in draft
    assert any("文案这一步没成" in n for n in draft["_notes"]), (
        "文案失败必须出声，不许把缺 editorial 的草稿当成「本来就没配」")


def test_assemble没给captions出声跳过窗口(tool, monkeypatch):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])
    monkeypatch.setattr(a, "Chat", lambda: type("C", (), {"ready": True, "channel": "x"})())
    monkeypatch.setattr(a, "draft_editorial", lambda chat, **kw: {"beats": ["b"]})

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick")
    assert "segments" not in draft
    assert any("没给 captions" in n for n in draft["_notes"]), (
        "没给 captions 要出声说明窗口起草跳过，别静默")


def test_assemble给captions跑窗口起草(tool, monkeypatch, tmp_path):
    a = tool
    monkeypatch.setattr(a, "resolve_match_id", lambda h, aw: "4CYI9Ick")
    monkeypatch.setattr(a, "matchup_order",
                        lambda h, aw, mid: [(h, a.player_zh(h)), (aw, a.player_zh(aw))])
    monkeypatch.setattr(a, "stats_block", lambda mid: {
        "a": {}, "b": {}, "_missing_required": [], "_has_winners_ue": False})
    monkeypatch.setattr(a, "collect", lambda mid, h, aw: {"candidates": [], "durations": []})
    monkeypatch.setattr(a, "points", lambda mid: [])
    monkeypatch.setattr(a, "rank_games", lambda games: [])
    monkeypatch.setattr(a, "Chat", lambda: type("C", (), {"ready": True, "channel": "x"})())
    monkeypatch.setattr(a, "draft_editorial",
                        lambda chat, **kw: {"beats": ["前段"]})

    caps = tmp_path / "captions.txt"
    caps.write_text("0.08\tBen\n13.76\tDespite\n", encoding="utf-8")
    cuts = tmp_path / "probe.json"
    cuts.write_text('{"scene_cuts": [6.8, 13.08]}', encoding="utf-8")

    # 打桩 draft_segments 模块里的函数，避免真调 DeepSeek
    fake = type("M", (), {
        "_read_captions": staticmethod(lambda p: "0.08: Ben\n13.76: Despite\n"),
        "_read_cuts": staticmethod(lambda p: [6.8, 13.08]),
        "draft_segments": staticmethod(
            lambda chat, **kw: {"segments": [
                {"start": 0.08, "end": 13.08, "narration": "一段"}], "_dropped": 0}),
    })()
    monkeypatch.setitem(sys.modules, "draft_segments", fake)

    draft = a.assemble(slug="x", home="A E", away="B R", event="C", year=2026,
                       fixture="", flashscore_id="4CYI9Ick",
                       captions_path=str(caps), cuts_path=str(cuts))
    assert draft["segments"][0]["narration"] == "一段"
    assert any("窗口起草 1 段" in n for n in draft["_notes"])


def test_main写出草稿文件(tool, monkeypatch, tmp_path, capsys):
    a = tool
    monkeypatch.setattr(a, "assemble", lambda **kw: {
        "_draft": True, "slug": kw["slug"], "cover": {"matchup": []},
        "_notes": ["flashscore id：4CYI9Ick（给定）"]})
    monkeypatch.setattr(a.Path, "resolve",
                        classmethod(lambda cls: tmp_path.parent / "fake" / "assemble_spec.py"))
    monkeypatch.setattr(sys, "argv", [
        "assemble_spec.py", "--slug", "demo", "--home", "A E", "--away", "B R",
        "--write"])
    rc = a.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "草稿 →" in out


def test_main默认不落盘(tool, monkeypatch, tmp_path, capsys):
    a = tool
    monkeypatch.setattr(a, "assemble", lambda **kw: {
        "_draft": True, "slug": kw["slug"], "cover": {"matchup": []},
        "_notes": []})
    monkeypatch.setattr(a.Path, "resolve",
                        classmethod(lambda cls: tmp_path.parent / "fake" / "assemble_spec.py"))
    monkeypatch.setattr(sys, "argv", [
        "assemble_spec.py", "--slug", "demo", "--home", "A E", "--away", "B R"])
    rc = a.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "没落盘" in out and "草稿 →" not in out, (
        "默认必须只打印不写文件——手动控制要先看后写，别默认就把草稿落进仓库")
