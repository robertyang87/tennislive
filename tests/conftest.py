from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from tennislive.digest import Digest
from tennislive.models import Match, MatchStatus, Player, SetScore, Tour, Tournament


def make_match(
    home_name="Jannik Sinner",
    away_name="Novak Djokovic",
    home_country="ITA",
    away_country="SRB",
    status=MatchStatus.FINISHED,
    winner=0,
    sets=((6, 4), (7, 6)),
    tiebreaks=(None, (7, 3)),
    tournament="Wimbledon",
    tour=Tour.ATP,
    round_name="Semifinals",
    discipline="Men's Singles",
    start_utc=datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc),
    match_id="m1",
) -> Match:
    set_scores = []
    for i, (h, a) in enumerate(sets):
        tb = tiebreaks[i] if i < len(tiebreaks) and tiebreaks[i] else (None, None)
        set_scores.append(
            SetScore(home=h, away=a, home_tiebreak=tb[0], away_tiebreak=tb[1])
        )
    return Match(
        match_id=match_id,
        tour=tour,
        tournament=Tournament(name=tournament, tour=tour),
        home=[Player(name=home_name, country=home_country, seed=1)],
        away=[Player(name=away_name, country=away_country, seed=5)],
        status=status,
        round_name=round_name,
        discipline=discipline,
        start_utc=start_utc,
        sets=set_scores,
        winner=winner,
    )


@pytest.fixture
def sample_digest() -> Digest:
    finished = make_match()
    finished_zheng = make_match(
        home_name="Qinwen Zheng",
        away_name="Aryna Sabalenka",
        home_country="CHN",
        away_country="BLR",  # 中立身份场景不影响测试
        tournament="Wimbledon",
        tour=Tour.WTA,
        round_name="Semifinals",
        discipline="Women's Singles",
        winner=0,
        sets=((6, 3), (6, 4)),
        tiebreaks=(None, None),
        match_id="m2",
    )
    upcoming = make_match(
        home_name="Carlos Alcaraz",
        away_name="Alexander Zverev",
        home_country="ESP",
        away_country="GER",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        round_name="Final",
        start_utc=datetime(2026, 7, 16, 13, 0, tzinfo=timezone.utc),
        match_id="m3",
    )
    return Digest(
        today=date(2026, 7, 16),
        results=[finished, finished_zheng],
        live=[],
        schedule=[upcoming],
        source="espn",
    )
