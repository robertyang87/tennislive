import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import collect_oncourt_interviews as collector
import jev_production as production
import jev_client as client
import yaml

CFG = {'sources': [{'name': 'Mixed', 'require_tennis': True}],
       'patterns_oncourt': ['on-court interview'], 'patterns_maybe': ['reacts'],
       'exclude': ['podcast'], 'tennis_markers': ['tennis']}


class ProductionTest(unittest.TestCase):
    def test_export_keeps_hard_gates_and_prior_visual_decisions(self):
        rules = collector.compile_rules(CFG)
        src = CFG['sources'][0]
        row = {'id': 'new', 'title': 'tennis reacts'}
        check = lambda r=row, kind='maybe', known={}, verdicts={}, cfg=CFG: collector.jev_candidate_eligible(r, src, kind, known, verdicts, cfg, rules)
        self.assertTrue(check())
        self.assertFalse(check({'id': 'football', 'title': 'reacts'}))
        self.assertFalse(check({'id': 'podcast', 'title': 'tennis reacts podcast'}))
        for kind in ('oncourt', 'ceremony', 'excluded'):
            self.assertFalse(check(kind=kind))
        self.assertFalse(check(known={'new': {}}))
        self.assertFalse(check(verdicts={'new': {'verdict': 'press'}}))
        self.assertFalse(check(cfg=dict(CFG, deny_ids=['new'])))
        self.assertFalse(check(cfg=dict(CFG, allow_ids=['new'])))

    def test_missing_secret_and_kill_switch_make_no_network_requests(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict('os.environ', {}, clear=True), patch.object(collector, 'load_sources', return_value=CFG), patch.object(client.urllib.request, 'build_opener', side_effect=AssertionError('network')) as network:
            items = [{'id': 'new', 'title': 'tennis reacts', 'source': 'Mixed'}]
            result = production.evaluate(items, Path(directory) / 'ledger')
            self.assertEqual(result['activation'], 'missing_secret')
            self.assertEqual(result['api_attempts'], 0)
            self.assertEqual(result['inventory_promotions'], 0)
            result = production.evaluate(items, Path(directory) / 'ledger', enabled=False)
            self.assertEqual(result['activation'], 'disabled')
            network.assert_not_called()

    def test_production_workflow_does_not_block_drafting(self):
        workflow = yaml.safe_load((Path(__file__).resolve().parents[1] / '.github/workflows/oncourt-interviews.yml').read_text())
        jobs = workflow['jobs']
        self.assertEqual(jobs['draft']['needs'], 'collect')
        self.assertEqual(jobs['jev']['needs'], 'collect')
        self.assertEqual(jobs['jev']['permissions'], {'contents': 'read'})
        self.assertEqual(jobs['jev']['concurrency']['group'], 'jev-production-advisory')

    def test_api_payload_has_only_title_and_source(self):
        body = client.build_request({'title': 'tennis reacts', 'source': 'Mixed', 'id': 'private-id', 'url': 'private-url', 'kind': 'maybe'})
        self.assertEqual(set(body['state']), {'title', 'source'})

    def test_collector_exports_unknowns_without_promoting_them(self):
        cfg = dict(CFG, sources=[dict(CFG['sources'][0], url='https://example.invalid')])
        rows = [{'id': 'new', 'title': 'tennis reacts'},
                {'id': 'unknown', 'title': 'tennis mystery'},
                {'id': 'football', 'title': 'reacts'},
                {'id': 'known', 'title': 'tennis reacts'}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'candidates.json'
            with patch.object(collector, 'load_sources', return_value=cfg), patch.object(collector, 'load_store', return_value={'items': {'known': {'title': 'tennis reacts'}}}), patch.object(collector, 'scan', return_value=(rows, 'ok')), patch.object(collector, 'VERDICTS', Path(directory) / 'missing.json'), patch.object(sys, 'argv', ['collector', '--dry-run', '--jev-candidates', str(output)]):
                self.assertEqual(collector.main(), 0)
            self.assertEqual({r['id'] for r in json.loads(output.read_text())['items']}, {'new', 'unknown'})


if __name__ == '__main__':
    unittest.main()
