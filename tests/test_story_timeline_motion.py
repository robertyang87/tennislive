"""Source/date and compositor boundaries for the reusable interruption scene."""
from copy import deepcopy
import json
import re

import pytest

from tennislive.video.story_timeline_motion import timeline_blocks_html, validate_block


def block():
    return {'kind': 'timeline', 'start': 23.5, 'duration': 11.75,
            'events': [{'date': '2024-02-29', 'label': '起点', 'source': 'https://example.org/start'},
                       {'date': '2024-05-09', 'label': '再出发', 'source': 'https://example.org/end'}],
            'interruption': {'label': '赛程中断', 'source': 'https://example.org/gap'},
            'resume_label': '重新\n出发', 'gap_label': '阶段间隔', 'summary': ['从起点到再出发']}


def test_dry_run_keeps_source_provenance_and_does_not_invent_intermediate_events():
    given = block(); frozen = deepcopy(given)
    normalized = validate_block(given)
    assert given == frozen
    assert len(normalized['events']) == 2
    assert normalized['events'][0]['calendar'] == {'month': '2024.02', 'day': '29'}
    assert normalized['events'][1]['source'] == given['events'][1]['source']
    assert normalized['interruption']['source'] == given['interruption']['source']
    assert normalized['start'] == 23.5 and normalized['duration'] == 11.75


@pytest.mark.parametrize('level', ['block', 'endpoint', 'interruption', 'calendar'])
def test_unknown_fields_fail_in_plan_validation_before_build(level):
    given = block()
    target = {'block': given, 'endpoint': given['events'][0],
              'interruption': given['interruption'],
              'calendar': given['events'][0].setdefault('calendar', {})}[level]
    target['invented_ranking_curve'] = [1, 2, 3]
    with pytest.raises(ValueError): validate_block(given)


@pytest.mark.parametrize('dates', [('2023-02-29', '2024-05-09'),
                                  ('2024-05-09', '2024-02-29'),
                                  ('2024-02-29', '2024-02-29')])
def test_invalid_or_reverse_dates_are_not_turned_into_a_synthetic_schedule(dates):
    given = block()
    for event, value in zip(given['events'], dates): event['date'] = value
    with pytest.raises(ValueError): validate_block(given)


def test_calendar_page_cannot_contradict_endpoint_date():
    given = block(); given['events'][0]['calendar'] = {'month': 'FEB / 2024', 'day': '28'}
    with pytest.raises(ValueError, match='disagrees'): validate_block(given)


@pytest.mark.parametrize('where', ['endpoint', 'interruption'])
def test_missing_evidence_does_not_render_as_a_verified_event(where):
    given = block()
    target = given['events'][0] if where == 'endpoint' else given['interruption']
    del target['source']
    with pytest.raises(ValueError): validate_block(given)


@pytest.mark.parametrize('change', [{'duration': 0}, {'duration': float('nan')}, {'start': -1},
                                  {'start': True}, {'frame': [70, 150, 940, 1000]},
                                  {'frame': [70, 200, 940, 1050]}])
def test_invalid_clock_or_frame_is_rejected_by_dry_run(change):
    with pytest.raises(ValueError): validate_block({**block(), **change})


def test_fragments_are_scoped_safe_and_register_instead_of_replacing_composer_clock():
    given = block(); given['events'][0]['label'] = '</script><b>源事实</b>'
    markup, css, js = timeline_blocks_html(given, 7, lambda _: pytest.fail('no raster needed'))
    assert '&lt;/script&gt;' in markup
    assert '</script>' not in js
    assert 'window.storyRenderers.push(render)' in js
    assert 'window.setConceptTime=' not in js and 'document.body' not in js
    assert '#story-timeline-7' in css and 'id="story-timeline-7"' in markup
    encoded = re.search(r'const d=(.*),root=document', js).group(1)
    metadata = json.loads(encoded)
    assert metadata['start'] == 23.5 and metadata['duration'] == 11.75
    assert metadata['events'][0]['label'] == given['events'][0]['label']
    assert metadata['events'][0]['source'] == given['events'][0]['source']
    assert markup.count('data-story-text') >= 8
