"""Missing optional statistics must route to evidence, not one compulsory site."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _hooks():
    path = Path(__file__).resolve().parents[1] / "tools" / "match_stat_hooks.py"
    spec = importlib.util.spec_from_file_location("routing_hooks", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("partial", [{}, {"winners": 23}, {"ue": 23}])
def test_missing_or_partial_stats_routes_to_multiple_sources(monkeypatch, capsys, partial):
    hooks = _hooks()
    block = {"a": dict(partial), "b": dict(partial), "_missing_required": [],
             "_has_winners_ue": False}
    monkeypatch.setattr(hooks, "stats_block", lambda match_id: block)
    monkeypatch.setattr(sys, "argv", ["match_stat_hooks.py", "known-match", "--stats-block"])
    assert hooks.main() == 0
    output = capsys.readouterr().out
    for source in ("官方比赛统计", "赛后稿", "MATCH SUMMARY", "mcp_stats.py", "tnns_stats.py"):
        assert source in output
    for status in ("本源缺字段", "暂未收录", "访问受阻", "解析失败"):
        assert status in output
    assert "不默认让用户提供截图" in output
    assert "遇安全验证停止" in output
    assert "先去 TNNS" not in output
    assert "两个源都查过" not in output
    assert "gh workflow run" not in output
    # Evidence-routing must preserve a partially populated data block unchanged.
    assert json.dumps({"a": partial, "b": partial}, ensure_ascii=False, indent=2) in output


def test_complete_stats_remain_immediately_usable(monkeypatch, capsys):
    hooks = _hooks()
    block = {"a": {"winners": 23, "ue": 23}, "b": {"winners": 24, "ue": 26},
             "_missing_required": [], "_has_winners_ue": True}
    monkeypatch.setattr(hooks, "stats_block", lambda match_id: block)
    monkeypatch.setattr(sys, "argv", ["match_stat_hooks.py", "known-match", "--stats-block"])
    assert hooks.main() == 0
    output = capsys.readouterr().out
    assert "这场有，必须填" in output
    assert "按同一场比赛并行补查" not in output
    assert json.dumps({"a": block["a"], "b": block["b"]}, ensure_ascii=False, indent=2) in output
