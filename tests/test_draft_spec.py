"""tools/draft_spec.py —— LLM 起草 spec 编辑内容（只测不联网半截）。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import draft_spec as ds  # noqa: PLC0415

    return ds


def test_schema钉死编辑字段():
    ds = _tool()
    keys = set((ds.SCHEMA.get("properties") or {}).keys())
    assert keys == {"hook", "question", "thesis", "beats", "chapters", "human_context",
                    "narration"}


def test_draft_editorial把fixture和facts喂进prompt():
    ds = _tool()
    captured = {}

    class FakeChat:
        def ask(self, system, user, *, schema, max_tokens):
            captured.update(user=user, schema=schema)
            return {"hook": ["a"], "question": "q", "thesis": "t",
                    "beats": ["b"], "human_context": "h", "narration": ["n"]}

    got = ds.draft_editorial(FakeChat(), home="Eala", away="Pegula",
                             event="Washington", year=2026,
                             fixture="北京时间 8 月 3 日", facts="总分差 9 分",
                             background="Eala 世界第 28；两人交手 Eala 1-0")
    assert "Eala" in captured["user"] and "Pegula" in captured["user"]
    assert "北京时间 8 月 3 日" in captured["user"], "fixture 要进 prompt"
    assert "总分差 9 分" in captured["user"], "狠数据要进 prompt"
    assert "世界第 28" in captured["user"], "球员背景要进 prompt（有背景支撑的文案）"
    assert captured["schema"] is ds.SCHEMA
    assert got["hook"] == ["a"]


def test_main无密钥跳过出声(monkeypatch, capsys):
    ds = _tool()

    class NotReady:
        ready = False

    monkeypatch.setattr(ds, "Chat", lambda: NotReady())
    monkeypatch.setattr(sys, "argv", [
        "draft_spec.py", "--slug", "x", "--home", "A", "--away", "B",
        "--event", "C", "--year", "2026"])
    assert ds.main() == 0
    out = capsys.readouterr().out
    assert "跳过" in out and "退化出声" in out
