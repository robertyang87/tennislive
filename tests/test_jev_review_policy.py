import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import jev_production as production
import jev_review_queue as queue
import jev_selective as selective
import jev_review_policy as policy
import verify_oncourt_sample as visual

CFG = {'sources': [{'name': 'Official', 'verified': True, 'provenance': 'official', 'fetch': 'tennistv'}],
       'patterns_oncourt': [], 'patterns_maybe': [], 'exclude': ['press conference'], 'tennis_markers': []}
ITEM = {'id': 'tennistv:123', 'source': 'Official', 'title': 'Player reacts',
        'url': 'https://www.tennistv.com/videos/123/rome-player-interview'}


def test_url_hint_reuses_metadata_without_network_and_never_approves(tmp_path):
    with patch.object(production.collector, 'load_sources', return_value=CFG), patch('urllib.request.build_opener', side_effect=AssertionError('network')):
        result = production.evaluate([ITEM], tmp_path/'cache')
        disabled = production.evaluate([ITEM], tmp_path/'cache', enabled=False)
        assert not disabled['review_queue']
    assert result['api_attempts'] == 0
    assert result['counts'] == {'source_url_review': 1}
    assert result['review_queue'][0]['review_reason'] == 'source_url_hint'
    assert result['inventory_promotions'] == 0
    state = {'version': 1, 'items': {}}
    assert queue.merge_report(state, result, {})['added'] == 1
    path = tmp_path/'queue.json';path.write_text(json.dumps(state))
    assert queue.approved_items(path, {}, CFG) == []
    assert queue.merge_report(state, result, {})['unchanged'] == 1
    state = {'version': 1, 'items': {}}
    assert queue.merge_report(state, result, {ITEM['id']: {'verdict': 'press'}})['added'] == 0


def test_url_hint_rejects_spoofs_and_preserves_existing_gates():
    for url in ['https://www.tennistv.com.evil.test/videos/123/rome-interview',
                'https://evil.test/videos/123/rome-interview',
                'https://www.tennistv.com/videos/999/rome-interview',
                'https://www.tennistv.com/videos/123/press-conference-interview',
                'https://www.tennistv.com/videos/123/rome?interview=true']:
        assert policy.source_url_hint(dict(ITEM, url=url), CFG) is None
    assert policy.source_url_hint(dict(ITEM, url='https://www.tennistv.com/videos/123/rome_round-2-post-match-interview'), CFG)
    rules = selective.collector.compile_rules(CFG)
    assert selective.plan(dict(ITEM, kind='oncourt'), CFG, rules) == 'existing_inventory'
    assert selective.plan(ITEM, dict(CFG, deny_ids=[ITEM['id']]), rules) == 'existing_deny_id'
    assert selective.plan(dict(ITEM, title='press conference'), CFG, rules) == 'existing_title_rule'
    assert policy.source_url_hint(dict(ITEM, unofficial=True), CFG) is None


def test_uncertain_is_bounded_trusted_and_does_not_change_approval(tmp_path):
    items = [dict(ITEM, id=str(i), url='https://example.invalid') for i in range(8)]
    rows = [dict(id=str(i), suggestion='uncertain', decision='api_ok') for i in range(8)]
    report = {'records': rows, 'total': 8, 'counts': {}, 'api_attempts': 0}
    with patch.object(production.collector, 'load_sources', return_value=CFG), patch.object(selective, 'run', return_value=report):
        result = production.evaluate(items, tmp_path/'cache')
    assert len(result['review_queue']) == result['review_uncertain'] == 2
    assert result['review_deferred'] == 6
    assert policy.review_reason(dict(ITEM, source='Unknown'), rows[0], CFG) is None
    state = {'version': 1, 'items': {}}
    assert queue.merge_report(state, result, {})['added'] == 2
    path=tmp_path/'queue.json';path.write_text(json.dumps(state))
    assert queue.approved_items(path, {}, CFG) == []


def test_site_reviews_are_visible_as_waiting_not_poster_approvals(tmp_path, monkeypatch):
    state={'version':1,'items':{}}
    report={'review_queue':[dict(ITEM, review_reason='source_url_hint', jev={'decision':'source_url_review'})]}
    queue.merge_report(state, report, {})
    path=tmp_path/'queue.json';path.write_text(json.dumps(state))
    verdicts=tmp_path/'verdicts.json';verdicts.write_text('{"verdicts":{}}')
    monkeypatch.setattr(visual,'VERDICTS',verdicts)
    monkeypatch.setattr(visual,'fetch_frames',lambda _: (_ for _ in ()).throw(AssertionError('no poster fetch')))
    monkeypatch.setattr(visual,'frame_sheets',lambda *args: [])
    visual.prepare_jev_review(path,tmp_path/'frames',5)
    rows=json.loads((tmp_path/'frames/waiting-sites.json').read_text())
    assert rows[0]['status']=='waiting_video_frames'
    assert json.loads((tmp_path/'frames/index.json').read_text())==[]
    assert json.loads(verdicts.read_text())=={'verdicts':{}}
