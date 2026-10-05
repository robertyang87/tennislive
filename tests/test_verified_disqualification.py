"""Default proof is distinct from retirement and incomplete normal results."""
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))
import reel_facts as facts
import versus_poster as poster
from build_match_reel import _expected_topbar_score_line, colorize_topbar_score


def fixture():
    """Synthetic dual-source metadata, not a claim about example domains."""
    match = {
        'status': 'result_verified', 'date': '2026-10-05', 'source_id': 'fixture-default',
        'participants': ['Alice', 'Bob'], 'set_scores_home_away': [[7, 5], [5, 3]],
        'winner': 'Alice', 'loser': 'Bob', 'winner_result': '7-5 5-3 DQ',
    }
    shared = {
        'match_key': match['source_id'], 'match_date': match['date'],
        'participants': match['participants'], 'set_scores_home_away': match['set_scores_home_away'],
        'winner': 'Alice', 'disqualified_player': 'Bob', 'status': 'disqualified', 'terminal': True,
        'checked_at': '2026-10-05T10:00:00Z', 'source_sha256': 'a' * 64, 'source_id': 'fixture',
    }
    match['disqualification_evidence'] = {'disqualified_player': 'Bob', 'best_of': 3, 'sources': [
        dict(shared, provider='Official fixture', source_class='official_result', source_url='https://example.org/result'),
        dict(shared, provider='Independent fixture', source_class='independent_scoreboard', source_url='https://example.net/result'),
    ]}
    return {'_match': match, 'stats': {'tour': 'atp'}, 'cover': {
        'topic': 'ATP500 fixture', 'winner': 'Alice', 'result': '7-5 5-3 DQ',
        'matchup': [{'name': 'Alice'}, {'name': 'Bob'}],
    }}


def test_terminal_default_preserves_incomplete_set_and_explicit_marker():
    s = fixture()
    assert facts.verified_result_problem(s) is None
    assert facts.verified_match_fact([{'name': 'Alice'}, {'name': 'Bob'}], [(7, 5), (5, 3)], 'fixture') is None
    for token in ('DQ', 'Def.', '取消资格'):
        s['_match']['winner_result'] = s['cover']['result'] = f'7-5 5-3 {token}'
        assert facts.verified_result_problem(s) is None
        scores, note = poster._scoreboard_sets(s['cover']['result'], 'cover')
        assert scores == [(7, 5, None), (5, 3, None)]
        assert poster._RETIREMENT_LABEL[note.lower()] == '取消资格'
    assert poster._RETIREMENT_LABEL['ret.'] == '退赛'


def test_default_can_award_winner_who_was_trailing():
    s = fixture()
    s['_match']['winner'], s['_match']['loser'] = 'Bob', 'Alice'
    p = s['_match']['disqualification_evidence']
    p['disqualified_player'] = 'Alice'
    for source in p['sources']:
        source['winner'], source['disqualified_player'] = 'Bob', 'Alice'
    s['_match']['winner_result'] = s['cover']['result'] = '5-7 3-5 DQ'
    s['cover']['winner'] = 'Bob'
    assert facts.verified_result_problem(s) is None


def test_default_cannot_be_relabelled_retirement_or_normal_completion():
    for result in ('7-5 5-3', '7-5 5-3 Ret.'):
        s = fixture()
        s['_match']['winner_result'] = s['cover']['result'] = result
        assert facts.verified_result_problem(s)
    s = fixture()
    s['_match']['retirement_evidence'] = deepcopy(s['_match']['disqualification_evidence'])
    assert facts.verified_result_problem(s)
    s = fixture()
    s['_match'].pop('disqualification_evidence')
    assert facts.verified_result_problem(s)
    s['_match']['status'] = 'pending'
    assert facts.verified_result_problem(s)
    s.pop('_match')
    assert facts.verified_result_problem(s)


def test_default_requires_matching_independent_terminal_proof():
    changes = {'status': 'retired', 'terminal': False, 'disqualified_player': 'Alice',
               'winner': 'Bob', 'match_date': '2026-10-04', 'set_scores_home_away': [[7, 5], [6, 3]],
               'source_sha256': '', 'provider': 'Official fixture', 'source_url': 'https://example.org/other'}
    for key, value in changes.items():
        s = fixture()
        s['_match']['disqualification_evidence']['sources'][1][key] = value
        assert facts.verified_result_problem(s), (key, value)
    s = fixture()
    s['_match']['disqualification_evidence']['sources'].pop()
    assert facts.verified_result_problem(s)
    s = fixture()
    s['_match']['set_scores_home_away'] = [[7, 5], [6, 3]]
    s['_match']['winner_result'] = s['cover']['result'] = '7-5 6-3 DQ'
    for source in s['_match']['disqualification_evidence']['sources']:
        source['set_scores_home_away'] = [[7, 5], [6, 3]]
    assert facts.verified_result_problem(s)


def test_topbar_keeps_default_marker_and_scoreboard_renders_chinese_note(monkeypatch):
    s = fixture()
    line = _expected_topbar_score_line(s)
    assert line == 'Alice 7-5 5-3 DQ Bob'
    assert 'DQ' in colorize_topbar_score(line)
    for player in s['cover']['matchup']:
        player.update(name_en=player['name'], country='USA', rank=10)
    s['cover']['scoreboard'] = {'court': 'Centre Court', 'duration_source': {'url': 'fixture'}}
    monkeypatch.setattr(poster, '_fetch_match_duration', lambda source, where: '1:51')
    # Player assets are unrelated to the terminal-result note being verified.
    monkeypatch.setattr(poster, '_score_row', lambda meta, cells, where, winner: cells)
    html = poster._scoreboard_html(s['cover'])
    assert '取消资格' in html
    assert '退赛' not in html
