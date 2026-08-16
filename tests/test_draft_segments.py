"""tools/draft_segments.py —— DeepSeek 从字幕+切点起草带窗口的 segments。

只测**不联网**的半截：字幕/切点的读取、prompt 是否把字幕和切点喂进去、
无 key/无字幕时的退化出声。真调 DeepSeek 不测。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _tool():
    sys.path.insert(0, str(_TOOLS))
    import draft_segments as ds  # noqa: PLC0415

    return ds


def test_read_captions解析时间码(tmp_path):
    ds = _tool()
    p = tmp_path / "captions.txt"
    p.write_text("0.08\tBen Shelton\n13.76\t>> Despite a narrow start\n"
                 "\n27.51\t>> [cheering]\n", encoding="utf-8")
    got = ds._read_captions(p)
    assert "0.08: Ben Shelton" in got
    assert "13.76: >> Despite a narrow start" in got
    assert "27.51: >> [cheering]" in got
    # 空行要跳过
    assert got.count("\n") == 2


def test_read_cuts读scene_cuts(tmp_path):
    ds = _tool()
    p = tmp_path / "probe.json"
    p.write_text('{"scene_cuts": [6.8, 8.96, 11.96], "duration": 100}',
                 encoding="utf-8")
    assert ds._read_cuts(p) == [6.8, 8.96, 11.96]


def test_draft_segments把字幕切点beats喂进prompt(monkeypatch, tmp_path):
    ds = _tool()
    captured = {}

    class FakeChat:
        def ask(self, system, user, *, schema, max_tokens):
            captured.update(user=user, schema=schema, max_tokens=max_tokens)
            return {"segments": [{"start": 1.0, "end": 3.0, "narration": "一句"}]}

    got = ds.draft_segments(FakeChat(), captions_text="0.08: Ben",
                            cuts=[6.8, 8.96], beats="前段：…", home="甲", away="乙")
    assert "0.08: Ben" in captured["user"], "字幕要进 prompt"
    assert "6.80" in captured["user"], "切点要进 prompt"
    assert "前段：…" in captured["user"], "beats 要进 prompt"
    assert captured["schema"] is ds.SCHEMA
    assert got["segments"][0]["narration"] == "一句"


def test_main无key跳过出声(monkeypatch, capsys, tmp_path):
    ds = _tool()

    class NotReady:
        ready = False

    monkeypatch.setattr(ds, "Chat", lambda: NotReady())
    monkeypatch.setattr(sys, "argv", [
        "draft_segments.py", "--captions", str(tmp_path / "c.txt"),
        "--cuts", str(tmp_path / "p.json"), "--beats", "前段"])
    assert ds.main() == 0
    assert "跳过" in capsys.readouterr().out


def test_main字幕空跳过出声(monkeypatch, capsys, tmp_path):
    ds = _tool()
    caps = tmp_path / "c.txt"
    caps.write_text("", encoding="utf-8")
    cuts = tmp_path / "p.json"
    cuts.write_text('{"scene_cuts": []}', encoding="utf-8")

    class Ready:
        ready = True
        channel = "deepseek · test"

    monkeypatch.setattr(ds, "Chat", lambda: Ready())
    monkeypatch.setattr(sys, "argv", [
        "draft_segments.py", "--captions", str(caps),
        "--cuts", str(cuts), "--beats", "前段"])
    assert ds.main() == 0
    out = capsys.readouterr().out
    assert "captions 是空的" in out, "没有字幕要出声，别静默退回人工"


def test_clean_segments拦掉零长度和超短窗口():
    ds = _tool()
    got = ds.clean_segments({"segments": [
        {"start": 30.96, "end": 30.96, "narration": "零长度"},
        {"start": 1.0, "end": 1.5, "narration": "太短"},
        {"start": 222.32, "end": 224.8, "narration": "正常"},
    ]})
    assert len(got["segments"]) == 1, "零长度和 <2s 的段要拦掉，只留正常段"
    assert got["segments"][0]["narration"] == "正常"
    assert got["_dropped"] == 2, "拦掉几段要记下来，别静默"


def test_clean_segments坏字段也不放过():
    ds = _tool()
    got = ds.clean_segments({"segments": [
        {"narration": "没有 start/end"},
        {"start": "abc", "end": 10.0, "narration": "start 不是数"},
    ]})
    assert got["segments"] == []
    assert got["_dropped"] == 2
