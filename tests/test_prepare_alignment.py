"""tools/prepare_alignment.py —— 对齐备料（只测不联网的半截）。

核心判据：`fetch_match_pbp.find_match` 找不到比赛时 raise 的是 **SystemExit**（不是
Exception），`prepare_alignment.fetch_pbp` 必须单独接住它才能走「放宽窗口重试」——
第一次窗口（3 天）找不到就试 7 天，凌晨结束的比赛在 UTC 里常被 3 天窗口卡掉。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def tool(monkeypatch):
    sys.path.insert(0, str(_TOOLS))
    import prepare_alignment as pa  # noqa: PLC0415

    return pa


def test_fetch_pbp接住SystemExit并重试宽窗口(tool, monkeypatch, tmp_path):
    """第一次 3 天窗口找不到（find_match raise SystemExit），要接住再试 7 天窗口，
    而不是让 SystemExit 把脚本带崩（exit 1）。"""
    pa = tool
    calls = []

    def fake_find_match(session, players, since, until):
        calls.append((since.isoformat(), until.isoformat()))
        if len(calls) == 1:
            raise SystemExit(f"{since}–{until} 窗口里没找到")
        return ("1017", 2026, "LS077", {})

    def fake_get(session, path, *a, **kw):
        return {"points": [
            {"setNumber": 1, "gameNumber": 1, "server": "B", "pointWinner": "A",
             "scoreAfterPoint": {"gameScore": {"teamAScore": "15", "teamBScore": "0"}}},
        ]}

    # fetch_pbp 函数内 `from fetch_match_pbp import find_match, get`，打桩到模块上
    import fetch_match_pbp  # noqa: PLC0415

    monkeypatch.setattr(fetch_match_pbp, "find_match", fake_find_match)
    monkeypatch.setattr(fetch_match_pbp, "get", fake_get)

    import datetime

    class _FakeDate(datetime.date):
        @classmethod
        def today(cls):
            return datetime.date(2026, 8, 18)

    monkeypatch.setattr(pa, "date", _FakeDate)

    ok = pa.fetch_pbp("Xiyu Wang", "Maria Timofeeva", tmp_path)
    assert ok is True, "重试 7 天窗口后该找到"
    assert len(calls) == 2, f"该先试 3 天再试 7 天，实际调了 {len(calls)} 次"
    assert (tmp_path / "pbp.json").is_file(), "拿到逐分要写 pbp.json"
