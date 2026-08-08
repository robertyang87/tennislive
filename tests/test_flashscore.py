"""flashscore.com 全量赛程接口测试：fixture 按 2026-08-07 实测的真实响应改写.

三个反直觉之处都在 `flashscore.py` 的模块 docstring 里写了理由，这里专门
钉住：`AB` 状态码里 `3` 既覆盖正常结束也覆盖退赛/不战而胜（要靠比分形状
反推）、退赛判据是"最后一盘局数够不够"而不是某个专门字段、
challenger-/itf- 前缀不在这条线的覆盖范围内。
"""

from datetime import date
from pathlib import Path

import pytest

from tennislive.models import MatchStatus, Tour
from tennislive.sources.flashscore import FlashscoreSource

FEED_TEXT = (Path(__file__).parent / "fixtures" / "flashscore_feed_sample.txt").read_text(
    encoding="utf-8"
)


@pytest.fixture
def source(monkeypatch) -> FlashscoreSource:
    src = FlashscoreSource()
    calls = []

    def fake_fetch(offset):
        calls.append(offset)
        return FEED_TEXT

    monkeypatch.setattr(src, "_fetch_offset", fake_fetch)
    src._calls = calls
    return src


def test_fetch_day_queries_three_offsets(source):
    matches = source.fetch_day(date(2026, 8, 7))
    assert sorted(source._calls) == [-1, 0, 1]
    ids = [m.match_id for m in matches]
    assert len(ids) == len(set(ids))


def test_challenger_level_is_excluded(source):
    """这条线只认 atp-/wta- 开头的 singles/doubles，challenger-/itf- 不覆盖."""
    matches = source.fetch_day(date(2026, 8, 7))
    assert not any("chalxxxx" in m.match_id for m in matches)


def test_bye_placeholder_without_opponent_is_skipped(source):
    matches = source.fetch_day(date(2026, 8, 7))
    assert not any("byeonly" in m.match_id for m in matches)


def test_beijing_date_window_excludes_next_day(source):
    """Ruud vs Fonseca 的开球时间落在北京 8 月 8 日，查 8 月 7 日不该出现."""
    day7 = source.fetch_day(date(2026, 8, 7))
    assert not any("zNXP4ni2" in m.match_id for m in day7)
    day8 = source.fetch_day(date(2026, 8, 8))
    assert any("zNXP4ni2" in m.match_id for m in day8)


def test_finished_straight_sets(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "S2B6ETB6" in x.match_id)
    assert m.tour == Tour.ATP
    assert m.tournament.name == "Montreal"
    assert m.status == MatchStatus.FINISHED
    assert m.winner == 0
    assert m.home[0].name == "Jodar R."
    assert m.away[0].name == "Musetti L."
    assert [s.display() for s in m.sets] == ["6-4", "6-3"]


def test_retired_inferred_from_incomplete_final_set(source):
    """AB=3 里没有专门的退赛标记，靠最后一盘 0-2 这种打不完的局数反推."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "hAvW0ePG" in x.match_id)
    assert m.status == MatchStatus.RETIRED
    assert m.status.is_final
    assert m.note == "对手退赛"
    assert m.winner == 1  # Rinderknech 两盘局数都领先


def test_walkover_has_zero_sets(source):
    """同样是 AB=3，但一盘局数都没有——不战而胜，不是正常结束."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "8AG3Lx4d" in x.match_id)
    assert m.status == MatchStatus.WALKOVER
    assert m.note == "不战而胜"
    assert m.sets == []


def test_scheduled_has_no_scores(source):
    matches = source.fetch_day(date(2026, 8, 8))
    m = next(x for x in matches if "zNXP4ni2" in x.match_id)
    assert m.status == MatchStatus.SCHEDULED
    assert m.sets == []
    assert m.winner is None


def test_live_match_in_progress(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "YNvdgAME" in x.match_id)
    assert m.status == MatchStatus.LIVE
    assert m.tour == Tour.ATP


def test_super_tiebreak_set_is_not_flagged_as_retired(source):
    """决胜盘超级抢十写成裸的 10-6（不是 1-0 配抢七小分），别误判成没打完."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "I3Icvhxe" in x.match_id)
    assert m.is_doubles
    assert [p.name for p in m.home] == ["Jiang X.", "Wu F."]
    assert [p.name for p in m.away] == ["Bouzkova M.", "Noskova L."]
    assert m.status == MatchStatus.FINISHED
    assert m.winner == 0
    third = m.sets[2]
    assert (third.home, third.away) == (10, 6)
