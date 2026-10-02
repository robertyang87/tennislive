"""Owner-approved one-film omission, Zheng–Shi 2026-10-01 only."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path('tools').resolve()))
import winners_ue_gate as G
import render_stat_card as C
import foreground_audio_gate as A


def approved():
    return json.loads(Path('specs/reels/zheng-shi-beijing-2026-r1.json').read_text())


def test_exact_episode_omits_only_two_rows_and_keeps_audio_evidence():
    s = approved()
    assert G.problem(s) is None
    rows = C.usable_rows(s['stats']['a'], s['stats']['b'])
    assert len(rows) == 7
    assert all(not set(row[3:]) & {'winners', 'ue'} for row in rows)
    A.require(s)


@pytest.mark.parametrize('key,value', [
    ('slug', 'sun-lys-beijing-2026-r1'), ('slug', 'nishikori-tiafoe'),
])
def test_no_other_slug(key, value):
    s = approved(); s[key] = value
    assert G.problem(s)


@pytest.mark.parametrize('key,value', [
    ('status', 'scheduled'), ('source_id', '1020_2026_LS082'),
    ('date', '2025-10-01'), ('winner', '施晗'), ('loser', '郑钦文'),
    ('source', 'unverified'), ('winner_result', '6-4 6-4'),
    ('set_scores_home_away', [[6, 7], [6, 4], [2, 6]]),
    ('participants', ['施晗', '郑钦文']),
])
def test_result_identity_must_match(key, value):
    s = approved(); s['_match'][key] = value
    assert G.problem(s)


@pytest.mark.parametrize('key,value', [
    ('result', '6-4 6-4'), ('winner', '施晗'), ('eyebrow', '赛后开麦'),
    ('matchup', [{'name': '施晗', 'name_en': 'Han Shi'},
                 {'name': '郑钦文', 'name_en': 'Qinwen Zheng'}]),
])
def test_cover_must_match(key, value):
    s = approved(); s['cover'][key] = value
    assert G.problem(s)


@pytest.mark.parametrize('side', ['a', 'b'])
@pytest.mark.parametrize('key', ['winners', 'ue'])
@pytest.mark.parametrize('value', [None, 0, 23])
def test_omission_never_allows_unknown_or_new_number(side, key, value):
    s = approved(); s['stats'][side][key] = value
    assert G.problem(s)


@pytest.mark.parametrize('key', list(G.ZHENG_SHI_OMISSION))
def test_exact_approval_provenance_required(key):
    s = approved(); del s['stats']['_winners_ue_omission'][key]
    assert G.problem(s)


def test_no_approval_and_false_stat_evidence_still_fail():
    s = approved(); del s['stats']['_winners_ue_omission']
    assert G.problem(s)
    s = approved(); s['stats']['_winners_ue_evidence'] = {}
    assert G.problem(s)


def test_other_stat_and_audio_gates_are_not_waived():
    s = approved(); del s['stats']['a']['aces']; del s['stats']['b']['aces']
    with pytest.raises(SystemExit):
        C.usable_rows(s['stats']['a'], s['stats']['b'])
    s = deepcopy(approved()); s['segments'][0]['end'] += 0.1
    with pytest.raises(ValueError):
        A.require(s)
