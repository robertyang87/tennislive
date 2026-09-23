import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import collect_oncourt_interviews as collector
import jev_review_queue as queue
import verify_oncourt_sample as visual

ITEM = {'id': 'abcdefghijk', 'title': 'Player reacts after victory',
        'source': 'Official', 'url': 'https://www.youtube.com/watch?v=abcdefghijk',
        'discovered_at': '2026-09-23T00:00:00+00:00', 'duration_s': 120}
CFG = {'sources': [{'name': 'Official', 'verified': True, 'provenance': 'official', 'url': 'https://example.invalid'}],
       'patterns_oncourt': [], 'patterns_maybe': ['reacts'], 'exclude': [], 'tennis_markers': []}


def suggestion():
    return {'review_queue': [dict(ITEM, jev={'suggestion': 'interview', 'confidence': 1})]}


def make_queue(tmp_path):
    path = tmp_path / 'queue.json'
    state = queue.read_queue(path)
    queue.merge_report(state, suggestion(), {})
    path.write_text(json.dumps(state))
    return path, state


def test_duplicate_suggestions_preserve_progress_and_final_decisions(tmp_path):
    path, state = make_queue(tmp_path)
    state['items'][ITEM['id']]['last_frames_at'] = 'already-reviewed'
    result = queue.merge_report(state, suggestion(), {})
    assert result['unchanged'] == 1
    assert state['items'][ITEM['id']]['last_frames_at'] == 'already-reviewed'
    prior = copy.deepcopy(state)
    report = suggestion()
    report['review_queue'][0]['title'] = 'Changed title'
    queue.merge_report(state, report, {ITEM['id']: {'verdict': 'press'}})
    assert state == prior


def test_approval_must_be_visual_bound_and_from_trusted_source(tmp_path):
    path, state = make_queue(tmp_path)
    verdict = {'verdict': 'oncourt', 'method': 'human_visual_verdict', 'by': 'reviewer',
               'evidence': ['frame evidence inspected'], 'jev_input_sha256': queue.identity(ITEM)}
    assert not queue.approved_items(path, {}, CFG)
    assert len(queue.approved_items(path, {ITEM['id']: verdict}, CFG)) == 1
    for changed in ({'verdict': 'press'}, {'method': 'jev'}, {'evidence': []}, {'jev_input_sha256': 'stale'}):
        assert not queue.approved_items(path, {ITEM['id']: dict(verdict, **changed)}, CFG)
    assert not queue.approved_items(path, {ITEM['id']: verdict}, dict(CFG, deny_ids=[ITEM['id']]))
    state['items'][ITEM['id']]['item']['url'] = 'https://example.invalid/different'
    path.write_text(json.dumps(state))
    assert not queue.approved_items(path, {ITEM['id']: verdict}, CFG)


def test_optional_export_failure_does_not_prevent_main_inventory_write(tmp_path, monkeypatch):
    monkeypatch.setattr(collector, 'load_sources', lambda: dict(CFG, patterns_oncourt=['on-court']))
    monkeypatch.setattr(collector, 'load_store', lambda: {'items': {}})
    monkeypatch.setattr(collector, 'scan', lambda *a: ([dict(ITEM, title='Player on-court interview')], 'ok'))
    monkeypatch.setattr(collector, 'ROOT', tmp_path)
    monkeypatch.setattr(collector, 'STORE', tmp_path / 'inventory.json')
    monkeypatch.setattr(collector, 'VERDICTS', tmp_path / 'verdicts.json')
    monkeypatch.setattr(sys, 'argv', ['collector', '--jev-candidates', str(tmp_path)])
    assert collector.main() == 0
    assert ITEM['id'] in json.loads((tmp_path / 'inventory.json').read_text())['items']


def test_reviewed_suggestion_reenters_collector_without_rescan(tmp_path, monkeypatch):
    path, state = make_queue(tmp_path)
    (tmp_path / 'data').mkdir()
    path.rename(tmp_path / 'data/jev_review_queue.json')
    verdict_path = tmp_path / 'verdicts.json'
    verdict_path.write_text(json.dumps({'verdicts': {ITEM['id']: {'verdict': 'oncourt',
        'method': 'human_visual_verdict', 'by': 'reviewer', 'evidence': ['actual frames'],
        'jev_input_sha256': queue.identity(ITEM)}}}))
    monkeypatch.setattr(collector, 'load_sources', lambda: CFG)
    monkeypatch.setattr(collector, 'load_store', lambda: {'items': {}})
    monkeypatch.setattr(collector, 'scan', lambda *a: ([], 'no-match'))
    monkeypatch.setattr(collector, 'ROOT', tmp_path)
    monkeypatch.setattr(collector, 'VERDICTS', verdict_path)
    monkeypatch.setattr(collector, 'STORE', tmp_path / 'inventory.json')
    monkeypatch.setattr(sys, 'argv', ['collector'])
    assert collector.main() == 0
    row = json.loads((tmp_path / 'inventory.json').read_text())['items'][ITEM['id']]
    assert row['kind'] == 'oncourt'
    assert row['discovery_method'] == 'jev_human_visual_review'
    assert row['jev_input_sha256'] == queue.identity(ITEM)
    assert row['discovered_at'] == ITEM['discovered_at']


def test_visual_worker_consumes_queue_and_retains_failed_frames(tmp_path, monkeypatch):
    path, state = make_queue(tmp_path)
    verdicts = tmp_path / 'verdicts.json'
    verdicts.write_text('{"verdicts": {}}')
    monkeypatch.setattr(visual, 'VERDICTS', verdicts)
    monkeypatch.setattr(visual, 'fetch_frames', lambda row: (row, [b'not-an-image'], 'ok'))
    monkeypatch.setattr(visual, 'frame_sheets', lambda *a: [])
    assert visual.prepare_jev_review(path, tmp_path / 'frames', 5) == 0
    record = json.loads((tmp_path / 'frames/index.json').read_text())[0]
    assert record['status'] == 'waiting_frames' and record['frame_count'] == 0
    assert json.loads(verdicts.read_text()) == {'verdicts': {}}
    state = queue.read_queue(path)
    assert state['items'][ITEM['id']]['status'] == 'pending_visual_review'
    assert state['items'][ITEM['id']]['last_frames_at']


def test_frame_queue_rotates_and_does_not_treat_site_posters_as_video_frames(tmp_path):
    path, state = make_queue(tmp_path)
    second = dict(ITEM, id='zyxwvutsrqp')
    queue.merge_report(state, {'review_queue': [dict(second, jev={'suggestion': 'interview'})]}, {})
    state['items'][ITEM['id']]['last_frames_at'] = '2026-09-23T01:00:00Z'
    assert queue.review_items(state, {}, 1)[0]['id'] == second['id']
    assert queue.review_items(state, {second['id']: {'verdict': 'press'}}, 1)[0]['id'] == ITEM['id']


def test_malformed_queue_rows_cannot_crash_primary_collector(tmp_path):
    path = tmp_path / 'queue.json'
    for row in ({}, {'item': {}}, {'item': dict(ITEM, source=[])}, {'item': ITEM, 'discovered_at': None}):
        path.write_text(json.dumps({'version': 1, 'items': {ITEM['id']: row}}))
        assert queue.approved_items(path, {}, CFG) == []
