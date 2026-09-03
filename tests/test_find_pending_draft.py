"""`tools/find_pending_draft.py`：会话开工前先看 pending 草稿，别把同一场球再 probe 一遍。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _tool():
    spec = importlib.util.spec_from_file_location("find_pending_draft", ROOT / "tools" / "find_pending_draft.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _draft(a: str, b: str) -> dict:
    return {"cover": {"matchup": [{"name_en": a}, {"name_en": b}]}}


def test_按两个姓认整词不认子串():
    t = _tool()
    d = _draft("Alexander Zverev", "Lorenzo Sonego")
    assert t.matches(d, "zverev-sonego", ["Zverev", "Sonego"], "")
    assert t.matches(d, "zverev-sonego", ["sonego", "ZVEREV"], ""), "大小写和顺序都不该影响"
    # 第一版的坑：`bublik-j.j.` 切出单字母 `j`，`j in "nothing"` 为真，随便两个姓都命中
    assert not t.matches(_draft("Alexander Bublik", "J.J. Wolf"), "bublik-j.j.", ["Nobody", "Nothing"], "")
    assert not t.matches(d, "zverev-sonego", ["Zverev", "Wolf"], ""), "两个姓要都对得上"
    assert t.matches(d, "zverev-sonego", [], "zver"), "--slug 按子串认"


def test_没找到要出声并且退出码是2(tmp_path, monkeypatch, capsys):
    t = _tool()
    monkeypatch.setattr(t, "PENDING", tmp_path)
    (tmp_path / "x-y.draft.json").write_text(json.dumps(_draft("A X", "B Y")), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Nobody,Nothing"])
    assert t.main() == 2
    out = capsys.readouterr().out
    assert "没有匹配" in out and "扫了 1 份" in out, "「没找到」要说清扫了几份，别和「没查」长得一样"


def test_找到了要把probe目录和卡点一起打出来(tmp_path, monkeypatch, capsys):
    t = _tool()
    monkeypatch.setattr(t, "PENDING", tmp_path)
    monkeypatch.setattr(t, "probe_dirs", lambda slug: [ROOT / "output" / "2026-09-02" / "reel" / slug])
    monkeypatch.setattr(t, "waiting", lambda d: ["赛果源缺 round，不能猜顶栏/比分板"])
    d = _draft("Alexander Zverev", "Lorenzo Sonego")
    d.update({"slug": "zverev-sonego", "source_url": "https://youtu.be/abc", "stats": {"a": {}},
              "_match": {"status": "result_verified", "winner": "兹维列夫", "winner_result": "6-4 3-6 6-3", "loser": "索内戈"},
              "_production": {"received_at": "2026-09-02T06:09:04Z", "event": "US Open"}})
    (tmp_path / "zverev-sonego.draft.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["find_pending_draft", "--who", "Zverev,Sonego"])
    assert t.main() == 0
    out = capsys.readouterr().out
    for needle in ("probe ✅", "output/2026-09-02/reel/zverev-sonego", "result_verified", "6-4 3-6 6-3",
                   "统计 ✅", "缺 round", "youtu.be/abc"):
        assert needle in out, needle
