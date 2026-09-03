"""`tools/slam_feed.py`：美网官方 feed 补 round/court。fixture 的字段形状抄自
probe-blocked run 33726235409 的日志，不是猜的；沙箱里 usopen.org 恒 403，所以真通不通只看 runner。"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location("slam_feed", ROOT / "tools" / "slam_feed.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PLAYERS = {"players": [
    {"last_name": "Zheng", "first_name": "Qinwen", "id": "wta328120", "country": "CHN"},
    {"last_name": "Liutova", "first_name": "K.", "id": "wta335303", "country": "RUS"},
    {"last_name": "Wu", "first_name": "Yibing", "id": "atpw0bh", "country": "CHN"},
    {"last_name": "Wu", "first_name": "Someone", "id": "atpxxxx", "country": "TPE"},
]}


def _m(round_code, opp, *, status="Completed", epoch=1, event="Ladies' Singles", court="Stadium 17"):
    return {"courtName": court, "roundCode": round_code, "roundName": f"Round {round_code}",
            "duration": "2:19", "status": status, "epoch": epoch, "eventName": event,
            "team1": {"lastNameA": "Zheng", "idA": "wta328120", "lastNameB": None},
            "team2": {"lastNameA": opp, "idA": "x", "lastNameB": None}}


def _fetch(urls: dict):
    def fetch(url):
        for k, v in urls.items():
            if url.endswith(k):
                return v
        raise AssertionError(f"没打过桩的 URL：{url}")
    return fetch


def test_按两个姓找到这一场并把轮次写成对外写法():
    t = _tool()
    fetch = _fetch({"players/players.json": PLAYERS,
                    "wta328120_matches.json": [_m("1", "Liutova", epoch=1), _m("2", "Bencic", epoch=2)]})
    res = t.usopen_match(2026, "Zheng", "Liutova", fetch=fetch)
    assert res and res["round"] == "第一轮" and res["court"] == "Stadium 17" and res["duration"] == "2:19"
    assert "wta328120_matches.json" in res["source"]


def test_顶层是list或matches键都认_而且优先打完的那场():
    t = _tool()
    fetch = _fetch({"players/players.json": PLAYERS,
                    "wta328120_matches.json": {"matches": [
                        _m("2", "Bencic", status="Scheduled", epoch=9),
                        _m("2", "Bencic", status="Completed", epoch=5)]}})
    res = t.usopen_match(2026, "Zheng", "Bencic", fetch=fetch)
    assert res and res["status"] == "Completed" and res["epoch_ms"] == 5


def test_同姓两个人要逐个试_对手对得上才算():
    t = _tool()
    fetch = _fetch({"players/players.json": PLAYERS,
                    "atpw0bh_matches.json": [_m("2", "Duckworth", event="Gentlemen's Singles", court="Court 4")],
                    "atpxxxx_matches.json": [_m("1", "Nobody", event="Gentlemen's Singles")]})
    res = t.usopen_match(2026, "Wu", "Duckworth", fetch=fetch)
    assert res and res["court"] == "Court 4" and res["player_id"] == "atpw0bh"


def test_查不到返回None不抛():
    t = _tool()
    fetch = _fetch({"players/players.json": PLAYERS, "wta328120_matches.json": []})
    assert t.usopen_match(2026, "Zheng", "Ghost", fetch=fetch) is None
    assert t.usopen_match(2026, "Ghost", "Phantom", fetch=fetch) is None


def test_轮次映射_资格赛另写_认不出的原样透出去():
    t = _tool()
    assert t.round_label("5", "Quarterfinals", "Ladies' Singles") == "8强"
    assert t.round_label("6", "Semifinals", "Ladies' Singles") == "4强"
    assert t.round_label("7", "Final", "Ladies' Singles") == "决赛"
    assert t.round_label("3", "Round 3", "Ladies' Singles Qualifying") == "资格赛第三轮"
    assert t.round_label("", "Round Robin", "Whatever") == "Round Robin"
    for bad in ("半决赛", "1/4", "四分之一"):
        assert bad not in "".join(t._ROUND_BY_CODE.values()), "对外写法不许回到被废掉的叫法"


def test_只有认得的赛事才查():
    t = _tool()
    assert t.feed_for("US Open") is t.usopen_match
    assert t.feed_for("Cincinnati Open") is None
    assert t.lookup("Cincinnati Open", 2026, "A", "B") is None


def test_feed非200要报成SlamFeedError(monkeypatch):
    t = _tool()

    class R:
        status_code = 403
        content = b"x"
        headers = {}

    monkeypatch.setattr(t.requests, "get", lambda *a, **k: R())
    try:
        t.fetch_json("https://example/x.json")
    except t.SlamFeedError as exc:
        assert "403" in str(exc)
    else:
        raise AssertionError("403 要报出来，不许当成空结果")
