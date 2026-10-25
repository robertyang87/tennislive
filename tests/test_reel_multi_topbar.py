"""A title run must never label an earlier round as its final matchup."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_match_reel as B
import render_inputs as RI


def recipe():
    nodes = {
        'r1': {'line1': '2026 WTA250 大阪 首轮', 'winner': '西尼亚科娃',
               'loser': '斯特恩斯', 'result': '6-4 0-6 4-0 Ret.',
               'source': 'https://api.wtatennis.com/tennis/tournaments/405/2026/matches?states=C'},
        'qf': {'line1': '2026 WTA250 大阪 1/4决赛', 'winner': '西尼亚科娃',
               'loser': '斯托亚纳', 'result': '6-1 6-2',
               'source': 'https://api.wtatennis.com/tennis/tournaments/405/2026/matches?states=C'},
        'final': {'line1': '2026 WTA250 大阪 决赛', 'winner': '西尼亚科娃',
                  'loser': '克鲁格', 'result': '6-1 6-0',
                  'source': 'https://api.wtatennis.com/tennis/tournaments/405/2026/matches?states=C'},
    }
    spec = {'sources': {key: f'https://example.org/{key}.mp4' for key in nodes},
            'segments': [{'source': 'r1', 'start': 100, 'end': 105},
                         {'title_card': '进入八强', 'seconds': 3, 'narration': '继续前进'},
                         {'source': 'qf', 'start': 200, 'end': 207},
                         {'source': 'final', 'start': 300, 'end': 304}],
            'cover': {'eyebrow': '赛场之上', 'layout': 'solo', 'winner': '西尼亚科娃',
                      'result': '6-1 6-0', 'topic': 'WTA250 大阪 决赛 · 西尼亚科娃 VS 克鲁格',
                      'matchup': [{'name': '西尼亚科娃'}, {'name': '克鲁格'}]},
            'topbar': {'line1': '2026 WTA250 大阪 决赛', 'line2': '西尼亚科娃 6-1 6-0 克鲁格'},
            'topbar_by_source': nodes}
    segments = [B.Segment(100, 105, .5, '', source='r1'),
                B.Segment(0, 3, .5, '继续前进', image='native-card.jpg', full_canvas=True),
                B.Segment(200, 207, .5, '', source='qf'),
                B.Segment(300, 304, .5, '', source='final')]
    return spec, segments


def dialogues(path):
    rows = []
    for line in path.read_text().splitlines():
        if line.startswith('Dialogue:'):
            bits = line.split(',', 9)
            rows.append((bits[1], bits[2], bits[3], re.sub(r'\{[^}]*\}', '', bits[9])))
    return rows


def test_headers_follow_three_real_match_windows_and_skip_full_canvas_card(tmp_path):
    spec, segments = recipe()
    result = B.write_segment_topbar_ass(spec, segments, 2, tmp_path/'multi.ass',
                                       default_lines=tuple(spec['topbar'].values()))
    rows = dialogues(result)
    assert len(rows) == 6
    assert rows[0][:3] == ('0:00:02.00', '0:00:07.00', 'HEAD')
    assert rows[1][:3] == ('0:00:02.00', '0:00:07.00', 'BODY')
    assert '斯特恩斯' in rows[1][3] and '克鲁格' not in rows[1][3]
    assert rows[2][:2] == ('0:00:10.00', '0:00:17.00')
    assert '斯托亚纳' in rows[3][3] and '斯特恩斯' not in rows[3][3]
    assert rows[4][:2] == ('0:00:17.00', '0:00:21.00')
    assert '克鲁格' in rows[5][3] and '斯托亚纳' not in rows[5][3]
    # No actual event is active over the native card at 7..10 seconds.
    assert {r[:2] for r in rows} == {('0:00:02.00','0:00:07.00'),
                                    ('0:00:10.00','0:00:17.00'),
                                    ('0:00:17.00','0:00:21.00')}


def test_absent_map_preserves_original_single_header_ass_bytes(tmp_path):
    spec, segments = recipe(); spec.pop('topbar_by_source')
    lines = ('2026 WTA250 大阪 决赛', '西尼亚科娃 6-1 6-0 克鲁格')
    old = B.write_topbar_ass(lines, 2, 21, tmp_path/'old.ass', pulse_at=[15.0])
    new = B.write_segment_topbar_ass(spec, segments, 2, tmp_path/'new.ass',
                                    default_lines=lines, pulse_at=[15.0])
    assert old.read_bytes() == new.read_bytes()


@pytest.mark.parametrize('mutation', ['missing_source','unknown_source','missing_opponent','unknown_opponent',
                                       'missing_evidence','manual_line2','invalid_score','invalid_topline'])
def test_bad_map_fails_before_encoding(mutation):
    spec, _ = recipe(); mapping = spec['topbar_by_source']
    if mutation == 'missing_source': mapping.pop('qf')
    elif mutation == 'unknown_source': mapping['ghost'] = deepcopy(mapping['r1'])
    elif mutation == 'missing_opponent': mapping['qf'].pop('loser')
    elif mutation == 'unknown_opponent': mapping['qf']['loser'] = 'Unknown'
    elif mutation == 'missing_evidence': mapping['qf']['source'] = ''
    elif mutation == 'manual_line2': mapping['qf']['line2'] = '错误的决赛对手'
    elif mutation == 'invalid_score': mapping['qf']['result'] = '2-0'
    elif mutation == 'invalid_topline': mapping['qf']['line1'] = '大阪比赛'
    with pytest.raises(B.ReelError): B._source_topbar_lines(spec)


def test_missing_map_entry_is_rejected_by_native_spec_validation_itself():
    spec, _ = recipe(); spec['topbar_by_source'].pop('qf')
    with pytest.raises(B.ReelError, match='source coverage mismatch'):
        B.validate_spec(spec)


def test_new_match_header_is_part_of_actual_render_input_projection():
    spec, _ = recipe(); before = RI.project(spec)
    spec['topbar_by_source']['qf']['result'] = '6-2 6-2'
    assert before != RI.project(spec)
    spec['topbar_by_source']['_r1'] = spec['topbar_by_source'].pop('r1')
    assert '_r1' in RI.project(spec)['topbar_by_source']


def test_source_header_notes_cannot_become_rendered_text(tmp_path):
    spec, segments = recipe()
    original = B.write_segment_topbar_ass(spec, segments, 2, tmp_path/"before.ass",
                                        default_lines=tuple(spec["topbar"].values())).read_bytes()
    spec["topbar_by_source"]["r1"]["_why"] = "ignored private annotation with unrelated opponent"
    spec["topbar_by_source"]["r1"]["_line1"] = "must never override the actual header"
    after = B.write_segment_topbar_ass(spec, segments, 2, tmp_path/"after.ass",
                                     default_lines=tuple(spec["topbar"].values())).read_bytes()
    assert after == original
