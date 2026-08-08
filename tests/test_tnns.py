"""TnnsSource：真实响应字段按 tools/probe_tnns.py 探到的样本核对.

fixture 里前三场（Jodar/Musetti、Rinderknech/Tiafoe、Sabalenka/Zhang）是
2026-08-07 真实抓到的响应，其余几场（walkover/live/scheduled/doubles/
unknown-sid）是手写构造的——真实样本里从来没见过已判出结果之外的状态，
这一点在 `tnns.py` 模块 docstring 里写清楚了，别当成核实过的形状。
"""

import json
from datetime import date
from pathlib import Path

import pytest

from tennislive.models import MatchStatus, Tour
from tennislive.sources.base import SourceError
from tennislive.sources.tnns import TnnsSource

RAW_TEXT = (Path(__file__).parent / "fixtures" / "tnns_matches_sample.json").read_text(
    encoding="utf-8"
)


@pytest.fixture
def source(monkeypatch) -> TnnsSource:
    src = TnnsSource()
    monkeypatch.setattr(src, "_fetch_raw_json", lambda: RAW_TEXT)
    return src


def test_atp_finished_straight_sets(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if x.match_id == "73252916")
    assert m.tour == Tour.ATP
    assert m.tournament.name == "ATP TOUR"  # 占位符，见模块 docstring
    assert m.status == MatchStatus.FINISHED
    assert m.winner == 0
    assert m.home[0].name == "Rafael Jodar"
    assert m.home[0].country == "ESP"
    assert m.home[0].seed == 20
    assert m.away[0].country == "ITA"
    assert [s.display() for s in m.sets] == ["6-4", "6-3"]


def test_retired_inferred_from_incomplete_final_set(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if x.match_id == "73252910")
    assert m.status == MatchStatus.RETIRED
    assert m.status.is_final
    assert m.note == "对手退赛"
    assert m.winner == 0  # Rinderknech 两盘局数都领先


def test_wta_match_from_sid_2(source):
    """sid=2 是 WTA 的证据：Sabalenka/Zhang 都是真实女子球员."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if x.match_id == "73255996")
    assert m.tour == Tour.WTA
    assert m.tournament.name == "WTA TOUR"
    assert m.winner == 0
    assert m.away[0].country == "CHN"


def test_missing_country_field_is_left_none_not_guessed(source):
    """Sabalenka 那条真实数据里 f 字段整个不存在——不许瞎编一个国籍."""
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if x.match_id == "73255996")
    assert m.home[0].name == "Aryna Sabalenka"
    assert m.home[0].country is None


def test_walkover_has_zero_sets(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if x.match_id == "90000001")
    assert m.status == MatchStatus.WALKOVER
    assert m.note == "不战而胜"
    assert m.sets == []


def test_live_has_no_winner_yet(source):
    matches = source.fetch_day(date(2026, 8, 7))
    m = next(x for x in matches if x.match_id == "90000002")
    assert m.status == MatchStatus.LIVE
    assert m.winner is None


def test_qualifier_seed_marker_is_not_a_numeric_seed(source):
    """"s":"Q" 是资格赛标记，不是种子号——种子号只认数字."""
    matches = source.fetch_day(date(2026, 8, 8))
    m = next(x for x in matches if x.match_id == "90000003")
    assert m.status == MatchStatus.SCHEDULED
    assert m.sets == []
    assert m.winner is None
    assert m.home[0].seed is None


def test_beijing_date_window_excludes_next_day(source):
    day7 = source.fetch_day(date(2026, 8, 7))
    assert not any(m.match_id == "90000003" for m in day7)
    day8 = source.fetch_day(date(2026, 8, 8))
    assert any(m.match_id == "90000003" for m in day8)


def test_doubles_shaped_entry_is_skipped(source):
    """双打结构没验证过（p 长度不是 2），只认单打，跳过而不是瞎解析."""
    matches = source.fetch_day(date(2026, 8, 7))
    assert not any(m.match_id == "90000004" for m in matches)


def test_unknown_sid_is_skipped(source):
    """sid 只验证过 1/2 两个值，出现别的值不猜，跳过."""
    matches = source.fetch_day(date(2026, 8, 7))
    assert not any(m.match_id == "90000005" for m in matches)


def test_missing_playwright_raises_source_error(monkeypatch):
    """没装 playwright 时要报 SourceError，跟"这台机器没有这个源"是一回事."""
    src = TnnsSource()

    def _boom():
        raise SourceError("tnns 需要 playwright（pip install -e '.[webrender]'），这台机器没装")

    monkeypatch.setattr(src, "_fetch_raw_json", _boom)
    with pytest.raises(SourceError, match="playwright"):
        src.fetch_day(date(2026, 8, 7))


def test_no_all_matches_key_raises_source_error(monkeypatch):
    src = TnnsSource()
    monkeypatch.setattr(src, "_fetch_raw_json", lambda: json.dumps({"generated_at": "x"}))
    with pytest.raises(SourceError, match="all_matches"):
        src.fetch_day(date(2026, 8, 7))


def test_malformed_json_raises_source_error(monkeypatch):
    src = TnnsSource()
    monkeypatch.setattr(src, "_fetch_raw_json", lambda: "<!doctype html>not json")
    with pytest.raises(SourceError):
        src.fetch_day(date(2026, 8, 7))
