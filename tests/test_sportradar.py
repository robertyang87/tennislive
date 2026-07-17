from tennislive.sources.sportradar import SportradarOfficialStats, _parse_stats

from conftest import make_match


def _summary():
    return {
        "sport_event": {
            "id": "sr:sport_event:123",
            "competitors": [
                {
                    "id": "sr:competitor:1",
                    "name": "Dzumhur, Damir",
                    "qualifier": "home",
                },
                {
                    "id": "sr:competitor:2",
                    "name": "Arnaldi, Matteo",
                    "qualifier": "away",
                },
            ],
        },
        "statistics": {
            "totals": {
                "competitors": [
                    {
                        "id": "sr:competitor:1",
                        "statistics": {
                            "points_won": 130,
                            "aces": 2,
                            "double_faults": 1,
                            "first_serve_successful": 83,
                            "first_serve_points_won": 61,
                            "second_serve_successful": 38,
                            "second_serve_points_won": 19,
                            "breakpoints_won": 9,
                            "total_breakpoints": 10,
                            "forehand_winners": 18,
                            "backhand_winners": 11,
                            "forehand_unforced_errors": 14,
                            "backhand_unforced_errors": 11,
                        },
                    },
                    {
                        "id": "sr:competitor:2",
                        "statistics": {
                            "points_won": 129,
                            "aces": 6,
                            "double_faults": 5,
                            "first_serve_successful": 74,
                            "first_serve_points_won": 54,
                            "second_serve_successful": 58,
                            "second_serve_points_won": 33,
                            "breakpoints_won": 7,
                            "total_breakpoints": 11,
                            "forehand_winners": 42,
                            "backhand_winners": 20,
                            "forehand_unforced_errors": 40,
                            "backhand_unforced_errors": 27,
                        },
                    },
                ]
            }
        },
    }


def test_parses_licensed_match_statistics():
    stats = _parse_stats(_summary(), make_match(), "https://api.sportradar.test")

    assert (stats.total_points_won.home, stats.total_points_won.away) == (130, 129)
    assert (stats.aces.home, stats.aces.away) == (2, 6)
    assert (stats.break_points_won.home, stats.break_points_won.away) == (9, 7)
    assert (stats.break_points_chances.home, stats.break_points_chances.away) == (10, 11)
    assert (stats.winners.home, stats.winners.away) == (29, 62)
    assert (stats.unforced_errors.home, stats.unforced_errors.away) == (25, 67)
    assert stats.source == "Sportradar 授权网球数据"


def test_matches_reversed_name_display():
    source = SportradarOfficialStats("test-key")
    match = make_match(home_name="Damir Dzumhur", away_name="Matteo Arnaldi")

    assert source._is_match(_summary(), match)


def test_fetches_event_summary_after_daily_schedule_match(monkeypatch):
    source = SportradarOfficialStats("test-key")
    match = make_match(home_name="Damir Dzumhur", away_name="Matteo Arnaldi")
    daily_row = {"sport_event": _summary()["sport_event"]}
    requested = []

    monkeypatch.setattr(source, "_summaries", lambda _date: [daily_row])

    def event_summary(event_id):
        requested.append(event_id)
        return _summary(), "https://api.sportradar.test/event-summary"

    monkeypatch.setattr(source, "_event_summary", event_summary)

    stats = source.fetch_match_stats(match)

    assert requested == ["sr:sport_event:123"]
    assert stats.total_points_won.home == 130
    assert stats.source_url == "https://api.sportradar.test/event-summary"
