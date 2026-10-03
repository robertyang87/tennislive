from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import versus_poster


def cover():
    return {
        'eyebrow': '赛场之上', 'winner': '纳达尔队', 'result': '4-3',
        'matchup': [
            {'name': '纳达尔队', 'name_en': 'Team Rafa', 'country': None, 'rank': None},
            {'name': '穆雷队', 'name_en': 'Team Murray', 'country': None, 'rank': None},
        ],
        'scoreboard': {'court': 'Rafa Nadal Academy Center Court',
                       'result_format': 'team_exhibition',
                       'duration_unavailable_why': '官方六场加赛报道未记录活动总用时；集锦时长不能代替。'},
    }


def test_team_result_keeps_court_and_scores_without_invented_duration(monkeypatch):
    item = cover()
    monkeypatch.setattr(versus_poster, '_fetch_match_duration',
                        lambda *args: pytest.fail('unrecorded duration must not be fetched'))
    assert versus_poster.solo_scoreboard_shape_error(item) is None
    html = versus_poster._scoreboard_html(item)
    assert '团体比分' in html
    assert 'Rafa Nadal Academy Center Court' in html
    assert 'TEAM RAFA' in html and 'TEAM MURRAY' in html
    assert '纳达尔队' in html and '穆雷队' in html
    assert 'scoreboard-duration' not in html
    assert '>4</span>' in html and '>3</span>' in html


@pytest.mark.parametrize('mutation', ['format', 'reason', 'player', 'country', 'rank', 'sets', 'loser'])
def test_team_exception_cannot_hide_ordinary_match_duration(mutation):
    item = cover()
    if mutation == 'format':
        del item['scoreboard']['result_format']
    elif mutation == 'reason':
        item['scoreboard']['duration_unavailable_why'] = ''
    elif mutation == 'player':
        item['matchup'][0]['name'] = '纳达尔'
    elif mutation == 'country':
        item['matchup'][0]['country'] = 'ESP'
    elif mutation == 'rank':
        item['matchup'][0]['rank'] = 1
    elif mutation == 'sets':
        item['result'] = '6-3 6-4'
    elif mutation == 'loser':
        item['result'] = '3-4'
    assert versus_poster.solo_scoreboard_shape_error(item)


def test_recorded_team_duration_still_fetches_real_source(monkeypatch):
    item = cover()
    item['scoreboard']['duration_source'] = {'url': 'https://example.com/event.json'}
    calls = []
    def fetch(source, where):
        calls.append(copy.deepcopy(source))
        return '2:30'
    monkeypatch.setattr(versus_poster, '_fetch_match_duration', fetch)
    html = versus_poster._scoreboard_html(item)
    assert calls == [{'url': 'https://example.com/event.json'}]
    assert '2:30' in html and 'scoreboard-duration' in html


def test_explicit_invalid_duration_source_cannot_be_ignored():
    item = cover()
    item['scoreboard']['duration_source'] = {}
    assert versus_poster.solo_scoreboard_shape_error(item)


def test_team_english_labels_do_not_change_player_name_abbreviation():
    assert versus_poster._english_display(
        '纳达尔', {'name_en': 'Rafael Nadal', 'country': 'ESP', 'rank': None}, 'player'
    ) == 'R. NADAL'
    assert versus_poster._english_display(
        '纳达尔队', cover()['matchup'][0], 'team'
    ) == 'TEAM RAFA'
