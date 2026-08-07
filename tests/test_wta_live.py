"""WTA 官方前端接口测试：fixture 按 2026-08 实测的真实响应改写（人名/时间保留原样）.

真实字段的三个反直觉之处，都在 `wta_live.py` 的模块 docstring 里写了理由，
这里的测试专门钉住它们：`Winner` 字段不是 1/2、`RoundID` 数字段不可信、
`MatchState` 里 `W`（不战而胜）连 `ResultString` 都是空的。
"""

import json
from datetime import date
from pathlib import Path

import pytest

from tennislive.models import MatchStatus, Tour
from tennislive.sources.wta_live import WtaLiveSource

TOURNAMENTS = json.loads(
    (Path(__file__).parent / "fixtures" / "wta_tournaments_sample.json").read_text(
        encoding="utf-8"
    )
)
MATCHES_BY_TID = json.loads(
    (Path(__file__).parent / "fixtures" / "wta_matches_sample.json").read_text(
        encoding="utf-8"
    )
)


@pytest.fixture
def source(monkeypatch) -> WtaLiveSource:
    src = WtaLiveSource()
    calls = {"tournaments": [], "matches": []}

    def fake_tournaments(d8, d8b):
        calls["tournaments"].append((d8, d8b))
        return TOURNAMENTS["content"]

    def fake_matches(tid, year, d8, d8b):
        calls["matches"].append((tid, year, d8, d8b))
        return MATCHES_BY_TID[str(tid)]["matches"]

    monkeypatch.setattr(src, "_active_tournaments", fake_tournaments)
    monkeypatch.setattr(src, "_matches_of", fake_matches)
    src._calls = calls
    return src


def test_fetch_day_covers_both_active_tournaments(source):
    matches = source.fetch_day(date(2026, 8, 7))
    # 806、2087 各查一次；缺 id 的脏记录必须被跳过，不会触发第三次调用
    assert len(source._calls["matches"]) == 2
    assert {c[0] for c in source._calls["matches"]} == {806, 2087}
    ids = [m.match_id for m in matches]
    assert len(ids) == len(set(ids))


def test_beijing_date_window_excludes_previous_and_next_day(source):
    """LS007（Kalinskaya/Navarro）落在北京 8 月 5 日，查 8 月 7 日不该出现."""
    day7 = source.fetch_day(date(2026, 8, 7))
    assert not any("LS007" in m.match_id for m in day7)
    day5 = source.fetch_day(date(2026, 8, 5))
    assert any("LS007" in m.match_id for m in day5)


def test_finished_straight_sets_winner(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "LS001" in x.match_id)
    assert m.tour == Tour.WTA
    assert m.status == MatchStatus.FINISHED
    assert m.winner == 0
    assert m.home[0].name == "Kamilla Rakhimova"
    assert m.away[0].name == "Venus Williams"
    assert [s.display() for s in m.sets] == ["6-4", "6-1"]


def test_retired_status_and_winner_from_text_not_numeric_code(source):
    """Winner 字段是 '4'——不是常见的 1/2，判据必须来自 ResultString 的文字."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "LS002" in x.match_id)
    assert m.status == MatchStatus.RETIRED
    assert m.status.is_final
    assert m.winner == 0  # Zhang（A）胜，尽管 Winner 数字码是 4 不是常见的 1/2
    assert m.note == "对手退赛"


def test_walkover_before_play_has_no_result_string(source):
    """MatchState=W 的不战而胜，ResultString 是空的——赢家判不出来就留 None."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "2087-2026:LD001" == x.match_id)
    assert m.status == MatchStatus.WALKOVER
    assert m.note == "不战而胜"
    assert m.winner is None  # 空 ResultString 判不出谁赢，宁可留空不猜


def test_walkover_after_match_id_winner_from_text(source):
    """LS003：Winner='7'，ResultString 里赢家是 B（Anisimova），不是数字码字面推的 1."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "LS003" in x.match_id)
    assert m.status == MatchStatus.WALKOVER
    assert m.winner == 1
    assert m.away[0].name == "Amanda Anisimova"


def test_live_match_state_c(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "LS004" in x.match_id)
    assert m.status == MatchStatus.LIVE


def test_scheduled_match_keeps_not_before_directive(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "LS005" in x.match_id)
    assert m.status == MatchStatus.SCHEDULED
    assert m.status_detail == "Starting at"
    assert m.home[0].seed == 13


def test_doubles_roster_and_super_tiebreak_goes_to_loser(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if "LD001" in x.match_id and x.tournament.name == "MONTREAL")
    assert m.is_doubles
    assert [p.name for p in m.home] == ["Xinyu Jiang", "Fang-Hsien Wu"]
    assert [p.name for p in m.away] == ["Marie Bouzkova", "Linda Noskova"]
    assert m.winner == 0
    third = m.sets[2]
    assert (third.home, third.away) == (1, 0)
    assert third.home_tiebreak is None
    assert third.away_tiebreak == 6  # 输方（B）小分，符合 SetScore.display() 的惯例


def test_bye_placeholder_without_opponent_is_skipped(source):
    matches = source.fetch_day(date(2026, 8, 7))
    assert not any("LS006" in m.match_id for m in matches)


def test_round_name_only_trusts_known_text_codes(source):
    """数字 RoundID（'3'/'1'/5）一律不猜；文字码('Q')才解析成中文能认的名字."""
    matches = source.fetch_day(date(2026, 8, 7))
    numeric_round = next(x for x in matches if "LS001" in x.match_id)
    assert numeric_round.round_name is None
    lettered_round = next(x for x in matches if "LS010" in x.match_id)
    assert lettered_round.round_name == "Quarterfinal"


def test_tournament_level_matches_espn_convention(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m1000 = next(x for x in matches if "LS001" in x.match_id)
    assert m1000.tournament.level == "W1000"
