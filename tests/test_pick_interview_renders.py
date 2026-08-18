"""tools/pick_interview_renders.py —— 挑待 dispatch 的采访 spec（纯函数半截）。

核心判据：已 render 过的（output/interviews/<slug>/render.json 存在）和已
dispatch 过的都不许再 dispatch——否则定时任务每 30 分钟会把历史采访全部重渲一遍。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch, tmp_path):
    sys.path.insert(0, str(_TOOLS))
    import pick_interview_renders as p  # noqa: PLC0415

    # specs 指到临时目录，造三个：一个已 render、一个正式未 render、一个草稿
    specs = tmp_path / "specs" / "interviews"
    specs.mkdir(parents=True)
    (specs / "a-done.json").write_text("{}")
    (specs / "b-todo.json").write_text("{}")
    (specs / "c-draft.draft.json").write_text("{}")
    monkeypatch.setattr(p, "SPECS", specs)
    monkeypatch.setattr(p, "STATE", tmp_path / "data" / "interview_render_dispatched.json")
    # 已 render 的：a-done（output/interviews/a-done/render.json 存在）
    monkeypatch.setattr(p, "_rendered_slugs",
                        lambda: {"a-done"})
    return p


def test_todo排除已render和草稿(tool):
    """a-done 已 render、c-draft 是草稿，只有 b-todo 该 dispatch。"""
    assert tool.todo_slugs() == ["b-todo"]


def test_mark记录dispatch防重(tool):
    """记录过 dispatch 的 slug 不能再 dispatch（否则每 30 分钟重渲历史）。"""
    tool.STATE.parent.mkdir(parents=True, exist_ok=True)
    tool.STATE.write_text(json.dumps({"slugs": ["b-todo"]}), encoding="utf-8")
    assert tool.todo_slugs() == [], "记录过 dispatch 的不能再 dispatch"
