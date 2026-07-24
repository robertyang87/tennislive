from datetime import datetime, timezone

from tennislive.research.news_flash import (
    is_match_report,
    is_offcourt_news,
    offcourt_flash_candidates,
)

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


def test_match_reports_are_not_offcourt():
    # Result verbs and scorelines -> match news (belongs in the daily digest).
    assert is_match_report("Alcaraz beats Sinner 6-4 7-6(3) to reach the final")
    assert is_match_report("18岁小将爆冷淘汰头号种子，晋级四强")
    assert is_match_report("Swiatek saves 2 match points to advance to the semifinal")
    assert not is_offcourt_news("Djokovic defeats Nadal in Rome")


def test_offcourt_news_is_detected():
    # Retirements, rules, governance, tech, honours, personnel -> off-court.
    assert is_offcourt_news("ATP to use electronic line calling at all tour events")
    assert is_offcourt_news("Roger Federer announces retirement from tennis")
    assert is_offcourt_news("网球名人堂公布本年度入选名单")
    assert is_offcourt_news("大满贯统一决胜盘抢十规则")


def test_offcourt_candidates_filter_match_sensitive_and_dedupe():
    signals = [
        {  # match report -> excluded
            "kind": "official-news",
            "source": "ATP",
            "title": "Sinner beats Alcaraz 7-5 6-4 in Cincinnati final",
            "url": "u1",
            "published_at": "2026-07-24T08:00:00+00:00",
        },
        {  # off-court, non-sensitive -> kept
            "kind": "official-news",
            "source": "ATP",
            "title": "ATP announces electronic line calling across all events",
            "url": "u2",
            "published_at": "2026-07-24T09:00:00+00:00",
        },
        {  # off-court but sensitive (doping) -> excluded (routed to human review)
            "kind": "official-news",
            "source": "ITIA",
            "title": "Player suspended after positive doping test",
            "url": "u3",
            "published_at": "2026-07-24T09:30:00+00:00",
        },
        {  # general search-trend (non-tennis) -> excluded outright
            "kind": "search-trend",
            "source": "Google Trends GB",
            "title": "taylor swift",
            "url": "u2b",
            "published_at": "2026-07-24T10:00:00+00:00",
        },
        {  # duplicate off-court headline -> collapsed
            "kind": "official-news",
            "source": "WTA",
            "title": "ATP announces electronic line calling across all events",
            "url": "u2c",
            "published_at": "2026-07-24T10:30:00+00:00",
        },
        {  # stale -> excluded on freshness
            "kind": "official-news",
            "source": "WTA",
            "title": "WTA unveils new season calendar",
            "url": "u4",
            "published_at": "2026-07-01T00:00:00+00:00",
        },
    ]

    candidates = offcourt_flash_candidates(signals, now=NOW, max_age_hours=48)

    assert [c["url"] for c in candidates] == ["u2"]
