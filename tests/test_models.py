from tennislive.models import MatchStatus, SetScore

from conftest import make_match


def test_set_display_plain():
    assert SetScore(6, 4).display() == "6-4"


def test_set_display_tiebreak_marks_loser_points():
    assert SetScore(7, 6, home_tiebreak=7, away_tiebreak=3).display() == "7-6(3)"
    assert SetScore(6, 7, home_tiebreak=5, away_tiebreak=7).display() == "6-7(5)"


def test_score_display_from_winner_flips_when_away_wins():
    m = make_match(winner=1, sets=((4, 6), (3, 6)), tiebreaks=())
    assert m.score_display(from_winner=True) == "6-4 6-3"
    assert m.score_display(from_winner=False) == "4-6 3-6"


def test_status_is_final():
    assert MatchStatus.FINISHED.is_final
    assert MatchStatus.RETIRED.is_final
    assert MatchStatus.WALKOVER.is_final
    assert not MatchStatus.LIVE.is_final
    assert not MatchStatus.SCHEDULED.is_final


def test_winner_players():
    m = make_match(winner=0)
    assert m.winner_players()[0].name == "Jannik Sinner"
    assert m.loser_players()[0].name == "Novak Djokovic"
