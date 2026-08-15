"""tools/check_content_quality.py —— LLM 内容质量 judge。

只测**不联网**的半截：schema 形状、prompt 是否把钩子和正文喂进去、无密钥时
退化出声。真调 DeepSeek 不测（和 test_news_brief 一个理由：网络零真请求）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


def _tool():
    sys.path.insert(0, str(Path("tools").resolve()))
    import check_content_quality as cq  # noqa: PLC0415

    return cq


def test_schema钉死三个判据字段():
    cq = _tool()
    keys = set((cq.SCHEMA.get("properties") or {}).keys())
    assert keys == {"hook_drama", "cover_emotion", "xhs_style"}, (
        "评的三样是钩子剧情跌宕 / 封面情绪对题 / 小红书风格，字段名不许漂"
    )


def test_ask_quality把钩子和正文喂进prompt(tmp_path):
    cq = _tool()
    slug = "demo"
    (tmp_path / "demo.xhs.txt").write_text("这是一段小红书正文", encoding="utf-8")
    # ask_quality 按 specs/reels/<slug>.xhs.txt 找正文，这里 monkeypatch 掉路径
    spec = {"slug": slug, "cover": {
        "hook": ["第一行钩子", "第二行钩子"],
        "winner": "甲", "result": "6-0 6-0", "title": "标题", "sub": "副标"}}
    captured = {}

    class FakeChat:
        def ask(self, system, user, *, schema, max_tokens):
            captured.update(system=system, user=user, schema=schema,
                            max_tokens=max_tokens)
            return {"hook_drama": {"ok": True, "why": "好"},
                    "cover_emotion": {"ok": True, "why": "对"},
                    "xhs_style": {"ok": True, "why": "是"}}

    monkeypatch_path = tmp_path / "specs" / "reels"
    monkeypatch_path.mkdir(parents=True)
    (monkeypatch_path / "demo.xhs.txt").write_text("这是一段小红书正文",
                                                    encoding="utf-8")
    import pathlib
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.chdir(tmp_path)  # 让 specs/reels/<slug>.xhs.txt 相对路径落到 tmp

    verdict = cq.ask_quality(FakeChat(), spec)
    assert verdict["hook_drama"]["ok"] is True
    assert "第一行钩子" in captured["user"]
    assert "第二行钩子" in captured["user"]
    assert "这是一段小红书正文" in captured["user"]
    assert captured["schema"] is cq.SCHEMA


def test_main无密钥跳过并出声(monkeypatch, capsys):
    cq = _tool()

    class NotReady:
        ready = False

    monkeypatch.setattr(cq, "load_spec",
                        lambda slug, spec_path: {"slug": "x", "cover": {}})
    monkeypatch.setattr(cq, "Chat", lambda: NotReady())
    monkeypatch.setattr(sys, "argv", ["check_content_quality.py", "--slug", "x"])
    rc = cq.main()
    assert rc == 0
    out = capsys.readouterr().out
    assert "跳过" in out and "退化出声" in out, (
        "没配密钥必须说「跳过」，不许静默——「评过了」和「没评」长得一样"
    )
