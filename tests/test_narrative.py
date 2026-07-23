from __future__ import annotations

from datetime import date

from conftest import make_match
from tennislive.models import MatchStatus
from tennislive.render import editorial_memory
from tennislive.render.narrative import preview_angle


def _no_story_match(**overrides):
    """A scheduled singles match with no curated story, media brief, or
    Chinese player — the exact gap where preview_angle used to fall straight
    to mechanical rank/seed facts with no topicality or history signal."""
    defaults = dict(
        home_name="Constant Lestienne", away_name="Zizou Bergs",
        home_country="FRA", away_country="BEL",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
        round_name="Quarterfinals",
    )
    defaults.update(overrides)
    return make_match(**defaults)


def test_preview_angle_cites_real_trend_radar_news_over_mechanical_facts():
    """双方的话题性：自动趋势雷达命中的官方报道优先于机械排名/种子推导."""
    match = _no_story_match(match_id="topical-news")
    match.trend_signals = [
        {
            "kind": "official-news",
            "source": "ATP官方",
            "title": "Bergs building on his breakout season",
            "url": "https://www.atptour.com/example",
            "published_at": "2026-07-22T12:00:00+00:00",
            "traffic": "",
        }
    ]

    angle = preview_angle(match, date(2026, 7, 23))

    assert "ATP官方" in angle and "Bergs building on his breakout season" in angle


def test_preview_angle_falls_back_to_search_heat_then_mechanical_facts():
    """没有官方新闻但搜索热度明显走高时，仍要点出话题性，而不是直接上机械分档."""
    hot = _no_story_match(match_id="topical-search")
    hot.search_heat = 24

    cold = _no_story_match(match_id="topical-cold")
    cold.search_heat = 0

    assert "搜索热度" in preview_angle(hot, date(2026, 7, 23))
    assert "搜索热度" not in preview_angle(cold, date(2026, 7, 23))
    assert preview_angle(cold, date(2026, 7, 23))  # 仍然兜底到机械看点，不为空


def test_preview_angle_uses_account_continuity_before_mechanical_facts(tmp_path, monkeypatch):
    """历史相关：这位球员近期是本账号自己的头条时，续写故事线优先于机械看点."""
    monkeypatch.setattr(
        editorial_memory, "STATE_PATH", tmp_path / "editorial_memory.json"
    )
    from tennislive.digest import Digest

    past = make_match(
        home_name="Constant Lestienne", away_name="Someone Else",
        home_country="FRA", match_id="past-lead",
    )
    editorial_memory.record_daily_lead(Digest(today=date(2026, 7, 20), results=[past]))

    upcoming = _no_story_match(match_id="continuity-next")
    angle = preview_angle(upcoming, date(2026, 7, 23))

    assert "7月20日" in angle and "下一章" in angle
