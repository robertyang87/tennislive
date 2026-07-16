"""ESPN 解析器测试：fixture 按 2026-07 实测的真实接口结构编写."""

import json
from datetime import date
from pathlib import Path

import pytest

from tennislive.models import MatchStatus, Tour
from tennislive.sources.espn import EspnSource

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "espn_scoreboard_sample.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture
def source(monkeypatch) -> EspnSource:
    src = EspnSource()
    calls = []

    def fake_fetch(league, d8):
        calls.append((league, d8))
        return FIXTURE

    monkeypatch.setattr(src, "_fetch_scoreboard", fake_fetch)
    src._calls = calls
    return src


def test_fetch_day_parses_and_dedupes(source):
    # 2026-07-15 UTC 11:00 = 北京 19:00 → 属于北京时间 7 月 15 日
    matches = source.fetch_day(date(2026, 7, 15))
    # atp+wta 两个 league、各 2 天 = 4 次请求
    assert len(source._calls) == 4
    ids = [m.match_id for m in matches]
    assert len(ids) == len(set(ids))
    # 179002 是 7-14 的比赛（北京 17:00），不属于 7-15
    assert not any("179002" in i for i in ids)
    assert len(matches) == 3


def test_dedup_ignores_league_dependent_uid(source):
    """合办赛事同一场比赛在 atp/wta 接口里 uid 联赛段不同（l:851/l:900），
    去重键必须是 事件ID:比赛ID 而非 uid."""
    matches = source.fetch_day(date(2026, 7, 15))
    for m in matches:
        assert m.match_id.startswith("306-2026:"), m.match_id


def test_singles_result(source):
    matches = source.fetch_day(date(2026, 7, 15))
    m = next(x for x in matches if "178001" in x.match_id)
    assert m.tour == Tour.WTA
    assert m.status == MatchStatus.FINISHED
    assert m.winner == 0
    assert m.home[0].name == "Qinwen Zheng"
    assert m.home[0].country == "CHN"
    assert m.home[0].seed == 5  # curatedRank 是赛事种子号，不是世界排名
    assert m.away[0].country == "ROM"  # ESPN 用非 IOC 的 rom 码
    assert [s.display() for s in m.sets] == ["6-4", "3-6", "7-6(4)"]
    assert m.round_name == "Quarterfinal"
    assert m.discipline == "Women's Singles"
    assert m.court == "Center Court"


def test_doubles_roster(source):
    matches = source.fetch_day(date(2026, 7, 15))
    m = next(x for x in matches if "178705" in x.match_id)
    assert m.is_doubles
    assert [p.name for p in m.home] == ["Mana Ayukawa", "Kanako Morisaki"]
    assert [p.name for p in m.away] == ["Ya Hsin Lee", "Ye Qiu Yu"]
    assert m.winner == 1
    assert m.away[1].country == "CHN"


def test_tour_derived_from_grouping(source):
    """合办赛事：即使从 wta 接口拿到，男子项目也归 ATP."""
    matches = source.fetch_day(date(2026, 7, 15))
    m = next(x for x in matches if "179001" in x.match_id)
    assert m.tour == Tour.ATP
    assert m.status == MatchStatus.SCHEDULED
    assert m.home[0].seed == 2


def test_retired_status(source):
    matches = source.fetch_day(date(2026, 7, 14))
    m = next(x for x in matches if "179002" in x.match_id)
    assert m.status == MatchStatus.RETIRED
    assert m.status.is_final
    assert m.winner == 0
