from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import make_match
from tennislive.research.trends import (
    TrendSignal,
    _parse_news_feed,
    _parse_trend_feed,
    apply_trend_signals,
)
from tennislive.render.hotspot import hotspot_post, hotspot_reasons, hotspot_score


def _signal(kind: str, source: str, title: str, now: datetime, traffic: str = ""):
    return TrendSignal(
        kind=kind,
        source=source,
        title=title,
        url="https://example.com/story",
        published_at=(now - timedelta(hours=2)).isoformat(),
        traffic=traffic,
    )


def test_official_news_and_search_trends_raise_matching_match_only():
    now = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    sherif = make_match(
        home_name="Mayar Sherif",
        away_name="Paula Badosa",
        tournament="WTA Iasi Open",
        match_id="iasi-final",
    )
    other = make_match(
        home_name="Player One",
        away_name="Player Two",
        tournament="Prague Open",
        match_id="prague",
    )
    signals = [
        _signal(
            "official-news",
            "WTA",
            "Sherif wins first WTA title in four years after Badosa retires",
            now,
        ),
        _signal("search-trend", "Google Trends GB", "Paula Badosa tennis", now, "20K+"),
    ]

    result = apply_trend_signals([sherif, other], signals=signals, now=now)

    assert result.matched_matches == 1
    assert sherif.media_heat >= 22
    assert sherif.search_heat > 0
    assert other.media_heat == other.search_heat == 0
    assert {"官网热点", "搜索升温"}.issubset(hotspot_reasons(sherif))
    assert "搜索端开始升温" in hotspot_post(sherif)


def test_trend_heat_is_bounded_and_part_of_hotspot_score():
    now = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    match = make_match(
        home_name="Jannik Sinner",
        away_name="Carlos Alcaraz",
        tournament="Wimbledon",
    )
    baseline = hotspot_score(match)
    signals = [
        _signal("search-trend", f"Google Trends {geo}", "Jannik Sinner tennis", now, "1M+")
        for geo in ("US", "GB", "AU", "HK")
    ]

    apply_trend_signals([match], signals=signals, now=now)

    assert match.search_heat == 35
    assert hotspot_score(match) == baseline + 35


def test_short_player_name_does_not_collide_with_unrelated_search_trend():
    now = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    match = make_match(
        home_name="Ya Hsin Lee",
        away_name="Ena Shibahara",
        tournament="Prague Open",
    )
    unrelated = _signal(
        "search-trend",
        "Google Trends US",
        "Lee County election results",
        now,
        "100K+",
    )

    apply_trend_signals([match], signals=[unrelated], now=now)

    assert match.search_heat == 0


def test_rss_parsers_keep_fresh_official_and_search_signals():
    now = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)
    news_xml = b"""<?xml version="1.0"?><rss><channel><item>
      <title>Sherif beats Badosa in Iasi - WTA Tennis</title>
      <link>https://news.google.com/story</link>
      <pubDate>Tue, 21 Jul 2026 10:00:00 GMT</pubDate>
      <source url="https://www.wtatennis.com">WTA Tennis</source>
    </item></channel></rss>"""
    trend_xml = b"""<?xml version="1.0"?><rss
      xmlns:ht="https://trends.google.com/trends/trendingsearches/daily">
      <channel><item><title>Paula Badosa tennis</title>
      <link>https://trends.google.com/example</link>
      <pubDate>Tue, 21 Jul 2026 11:00:00 GMT</pubDate>
      <ht:approx_traffic>20K+</ht:approx_traffic>
      </item></channel></rss>"""

    news = _parse_news_feed(news_xml, "WTA", now)
    trends = _parse_trend_feed(trend_xml, "GB", now)

    assert news[0].title == "Sherif beats Badosa in Iasi"
    assert news[0].source == "WTA Tennis"
    assert trends[0].traffic == "20K+"
