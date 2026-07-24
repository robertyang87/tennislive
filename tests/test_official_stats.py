from __future__ import annotations

from datetime import datetime, timezone

from tennislive.models import Match, MatchStatus, Player, SetScore, Tournament, Tour
from tennislive.sources.base import SourceError
from tennislive.sources.official_stats import (
    AtpOfficialStats,
    WtaOfficialStats,
    _parse_atp_stats,
    _parse_wta_stats,
    fetch_match_stats_with_fallback,
)


def _match(tour: Tour = Tour.WTA) -> Match:
    return Match(
        match_id="source:1",
        tour=tour,
        tournament=Tournament(
            name="Livesport Prague Open" if tour == Tour.WTA else "Estoril Open",
            tour=tour,
            level="WTA250" if tour == Tour.WTA else "ATP250",
        ),
        home=[Player("Lucie Havlickova")],
        away=[Player("Barbora Krejcikova")],
        status=MatchStatus.FINISHED,
        start_utc=datetime(2026, 7, 23, 15, 47, tzinfo=timezone.utc),
        sets=[SetScore(4, 6), SetScore(2, 6)],
        winner=1,
    )


WTA_TOTAL = {
    "setnum": 0,
    "acesa": 2,
    "acesb": 5,
    "dblflta": 3,
    "dblfltb": 2,
    "ptswon1stserva": 33,
    "ptswon1stservb": 23,
    "ptsplayed1stserva": 48,
    "ptsplayed1stservb": 30,
    "ptstotwonserva": 43,
    "ptstotwonservb": 37,
    "totservplayeda": 78,
    "totservplayedb": 51,
    "breakptsconva": 0,
    "breakptsconvb": 3,
    "breakptsplayeda": 1,
    "breakptsplayedb": 12,
    "totptswona": 57,
    "totptswonb": 72,
}


def test_wta_parser_derives_percentages_and_preserves_match_order():
    stats = _parse_wta_stats(
        [WTA_TOTAL],
        reverse=False,
        source_url="https://api.wtatennis.com/example",
        duration="01:46:33",
    )

    assert (stats.total_points_won.home, stats.total_points_won.away) == (57, 72)
    assert (stats.first_serve_in_pct.home, stats.first_serve_in_pct.away) == (
        62,
        59,
    )
    assert (stats.first_serve_won_pct.home, stats.first_serve_won_pct.away) == (
        69,
        77,
    )
    assert (stats.second_serve_won_pct.home, stats.second_serve_won_pct.away) == (
        33,
        67,
    )
    assert (stats.break_points_won.home, stats.break_points_won.away) == (0, 3)
    assert stats.duration_minutes == 107
    assert stats.winners is None
    assert stats.unforced_errors is None


def test_wta_parser_reverses_api_a_b_to_digest_home_away():
    stats = _parse_wta_stats(
        [WTA_TOTAL],
        reverse=True,
        source_url="https://api.wtatennis.com/example",
    )
    assert (stats.total_points_won.home, stats.total_points_won.away) == (72, 57)
    assert (stats.aces.home, stats.aces.away) == (5, 2)


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload


class _WtaSession:
    def get(self, url, params=None, timeout=30):
        if url.endswith("/tournaments"):
            return _Response(
                {
                    "content": [
                        {
                            "tournamentGroup": {"id": 1082, "name": "PRAGUE"},
                            "year": 2026,
                            "title": "Livesport Prague Open 2026",
                        }
                    ]
                }
            )
        if url.endswith("/tournaments/1082/2026/matches"):
            return _Response(
                {
                    "matches": [
                        {
                            "DrawMatchType": "S",
                            "PlayerNameFirstA": "Lucie",
                            "PlayerNameLastA": "Havlickova",
                            "PlayerNameFirstB": "Barbora",
                            "PlayerNameLastB": "Krejcikova",
                            "MatchID": "LS015",
                            "MatchTimeTotal": "01:46:33",
                        }
                    ]
                }
            )
        if url.endswith("/matches/LS015/stats"):
            return _Response([WTA_TOTAL])
        raise AssertionError(f"unexpected WTA URL: {url}")


def test_wta_public_adapter_discovers_event_and_match_id():
    stats = WtaOfficialStats(session=_WtaSession()).fetch_match_stats(_match())
    assert stats.source == "WTA 官方逐场技术统计"
    assert stats.source_url.endswith("/1082/2026/matches/LS015/stats")
    assert stats.total_points_won.away == 72


def _multiple(percent, dividend, divisor):
    return {"Percent": percent, "Dividend": dividend, "Divisor": divisor}


def _atp_team(
    *,
    aces: int,
    double_faults: int,
    first_serve: tuple[int, int, int],
    first_won: tuple[int, int, int],
    second_won: tuple[int, int, int],
    breaks: tuple[int, int, int],
    service_points: tuple[int, int, int],
    total_points: tuple[int, int, int],
):
    return {
        "Sets": [
            {
                "SetNumber": 0,
                "Stats": {
                    "ServiceStats": {
                        "Aces": {"Number": aces},
                        "DoubleFaults": {"Number": double_faults},
                        "FirstServe": _multiple(*first_serve),
                        "FirstServePointsWon": _multiple(*first_won),
                        "SecondServePointsWon": _multiple(*second_won),
                    },
                    "ReturnStats": {
                        "BreakPointsConverted": _multiple(*breaks),
                    },
                    "PointStats": {
                        "TotalServicePointsWon": _multiple(*service_points),
                        "TotalPointsWon": _multiple(*total_points),
                    },
                },
            }
        ]
    }


def test_atp_parser_uses_official_dividends_and_percentages():
    payload = {
        "PlayerTeam1": _atp_team(
            aces=8,
            double_faults=2,
            first_serve=(64, 40, 62),
            first_won=(75, 30, 40),
            second_won=(55, 12, 22),
            breaks=(50, 3, 6),
            service_points=(68, 42, 62),
            total_points=(52, 72, 138),
        ),
        "PlayerTeam2": _atp_team(
            aces=3,
            double_faults=5,
            first_serve=(59, 39, 66),
            first_won=(62, 24, 39),
            second_won=(41, 11, 27),
            breaks=(25, 1, 4),
            service_points=(53, 35, 66),
            total_points=(48, 66, 138),
        ),
    }
    stats = _parse_atp_stats(
        payload,
        reverse=False,
        source_url="https://api.protennislive.com/example",
        duration="02:14",
    )
    assert (stats.total_points_won.home, stats.total_points_won.away) == (72, 66)
    assert (stats.first_serve_in_pct.home, stats.first_serve_in_pct.away) == (
        64,
        59,
    )
    assert (stats.break_points_won.home, stats.break_points_won.away) == (3, 1)
    assert (stats.break_points_chances.home, stats.break_points_chances.away) == (
        6,
        4,
    )
    assert stats.duration_minutes == 134


class _AtpSession:
    def __init__(self, stats_payload):
        self.stats_payload = stats_payload
        self.urls = []

    def get(self, url, timeout=30):
        self.urls.append(url)
        if url.endswith("/Tournaments/calendar"):
            return _Response(
                {
                    "TournamentInfos": [
                        {
                            "TournamentYear": 2026,
                            "TournamentId": 7290,
                            "TournamentName": "Millennium Estoril Open",
                            "TournamentCity": "Estoril",
                        }
                    ]
                }
            )
        if url.endswith("/Results/2026/7290"):
            return _Response(
                {
                    "Matches": [
                        {
                            "MatchId": "MS009",
                            "MatchTime": "02:14",
                            "PlayerTeam1": {
                                "PlayerFirstNameFull": "Lucie",
                                "PlayerLastName": "Havlickova",
                            },
                            "PlayerTeam2": {
                                "PlayerFirstNameFull": "Barbora",
                                "PlayerLastName": "Krejcikova",
                            },
                        }
                    ]
                }
            )
        if url.endswith("/MatchStats/2026/7290/MS009"):
            return _Response(self.stats_payload)
        raise AssertionError(f"unexpected ATP URL: {url}")


def test_atp_adapter_uses_calendar_results_and_match_stats_paths():
    payload = {
        "PlayerTeam1": _atp_team(
            aces=8,
            double_faults=2,
            first_serve=(64, 40, 62),
            first_won=(75, 30, 40),
            second_won=(55, 12, 22),
            breaks=(50, 3, 6),
            service_points=(68, 42, 62),
            total_points=(52, 72, 138),
        ),
        "PlayerTeam2": _atp_team(
            aces=3,
            double_faults=5,
            first_serve=(59, 39, 66),
            first_won=(62, 24, 39),
            second_won=(41, 11, 27),
            breaks=(25, 1, 4),
            service_points=(53, 35, 66),
            total_points=(48, 66, 138),
        ),
    }
    session = _AtpSession(payload)
    stats = AtpOfficialStats("test-token", session=session).fetch_match_stats(
        _match(Tour.ATP)
    )

    assert stats.source == "ATP ProTennisLive 官方技术统计"
    assert stats.source_url.endswith("/MatchStats/2026/7290/MS009")
    assert stats.total_points_won.home == 72
    assert any(url.endswith("/Tournaments/calendar") for url in session.urls)
    assert any(url.endswith("/Results/2026/7290") for url in session.urls)


class _FailingProvider:
    def fetch_match_stats(self, match):
        raise SourceError("temporary failure")


class _WorkingProvider:
    def fetch_match_stats(self, match):
        return _parse_wta_stats(
            [WTA_TOTAL],
            reverse=False,
            source_url="https://backup.example/stats",
        )


def test_provider_chain_continues_after_failure():
    result = fetch_match_stats_with_fallback(
        _match(),
        providers=[
            ("primary", _FailingProvider()),
            ("backup", _WorkingProvider()),
        ],
    )
    assert result.stats is not None
    assert result.stats.source_url == "https://backup.example/stats"
    assert result.source_status["primary"].startswith("降级")
    assert result.source_status["backup"].startswith("正常")
