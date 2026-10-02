"""Retirement proof checks, including the verified Sun–Lys episode."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))
import reel_facts as G
from tennislive.sources import flashscore as native


def fixture():
    """Synthetic metadata fixture; not a claim that example.org published a match."""
    match = {'status':'result_verified','date':'2026-10-01','source_id':'fixture-retirement',
             'participants':['Alice','Bob'],'set_scores_home_away':[[1,6],[0,3]],
             'winner':'Bob','loser':'Alice','winner_result':'6-1 3-0 Ret.'}
    shared = {'match_key':match['source_id'],'match_date':match['date'],
              'participants':match['participants'],'set_scores_home_away':match['set_scores_home_away'],
              'winner':'Bob','retired_player':'Alice','status':'retired','terminal':True,
              'checked_at':'2026-10-01T19:00:00Z','source_sha256':'a'*64,'source_id':'test-fixture'}
    match['retirement_evidence']={'retired_player':'Alice','best_of':3,'sources':[
        dict(shared,provider='Official fixture',source_class='official_result',source_url='https://example.org/official'),
        dict(shared,provider='Independent fixture',source_class='independent_scoreboard',source_url='https://example.net/score')]}
    return {'_match':match,'stats':{'tour':'wta'},'cover':{'topic':'WTA fixture',
            'winner':'Bob','result':'6-1 3-0 Ret.','matchup':[{'name':'Alice'},{'name':'Bob'}]}}


class RetirementChecks(unittest.TestCase):
    def test_actual_sun_official_and_independent_report(self):
        actual=json.loads((HERE/'fixtures/sun_retired_ls082.json').read_text())
        self.assertIsNone(G.verified_result_problem(actual))
        actual['_match']['retirement_evidence']['sources'][1]['winner']='利斯'
        self.assertIsNotNone(G.verified_result_problem(actual))

    def test_truthful_retirement_display(self):
        self.assertIsNone(G.verified_result_problem(fixture()))
        self.assertFalse(native._set_complete(3,0))
        self.assertTrue(native._set_complete(6,1))

    def test_normal_completion_unchanged(self):
        s=fixture();s['_match'].pop('retirement_evidence')
        s['_match']['set_scores_home_away']=[[1,6],[3,6]]
        s['_match']['winner_result']=s['cover']['result']='6-1 6-3'
        self.assertIsNone(G.verified_result_problem(s))
        s['cover']['result']='6-1 6-4';self.assertIsNotNone(G.verified_result_problem(s))

    def test_no_faked_retirement_after_normal_completion(self):
        s=fixture();s['_match']['set_scores_home_away']=[[1,6],[3,6]]
        for e in s['_match']['retirement_evidence']['sources']:e['set_scores_home_away']=[[1,6],[3,6]]
        s['_match']['winner_result']=s['cover']['result']='6-1 6-3 Ret.'
        self.assertIsNotNone(G.verified_result_problem(s))

    def test_retiring_leader_can_lose(self):
        s=fixture();s['_match']['winner']='Alice';s['_match']['loser']='Bob'
        s['_match']['retirement_evidence']['retired_player']='Bob'
        for e in s['_match']['retirement_evidence']['sources']:e['winner']='Alice';e['retired_player']='Bob'
        s['_match']['winner_result']=s['cover']['result']='1-6 0-3 Ret.';s['cover']['winner']='Alice'
        self.assertIsNone(G.verified_result_problem(s))

    def test_wrong_or_incomplete_terminal_proof(self):
        cases={'winner':'Alice','retired_player':'Bob','status':'live','terminal':False,
               'match_key':'another','match_date':'2026-09-30','participants':['Bob','Alice'],
               'set_scores_home_away':[[2,6],[0,3]],'source_sha256':'short','checked_at':'2026-10-01T19:00:00',
               'source_url':'not a URL','provider':'','source_id':''}
        for key,value in cases.items():
            with self.subTest(key=key):
                s=deepcopy(fixture());s['_match']['retirement_evidence']['sources'][1][key]=value
                self.assertIsNotNone(G.verified_result_problem(s))

    def test_suffix_winner_and_metadata_must_match(self):
        for where,key,value in [('cover','result','6-1 3-0'),('cover','result','6-1 4-0 Ret.'),
                                ('cover','winner','Alice'),('_match','winner_result','6-1 3-0'),
                                ('_match','winner','Alice'),('_match','date','2026-09-30')]:
            with self.subTest(where=where,key=key,value=value):
                s=deepcopy(fixture());s[where][key]=value;self.assertIsNotNone(G.verified_result_problem(s))

    def test_independent_provider_and_format_required(self):
        for kind in ('one_source','same_provider','same_host','no_official','wrong_best_of','unfinished_middle'):
            with self.subTest(kind=kind):
                s=deepcopy(fixture());p=s['_match']['retirement_evidence']
                if kind=='one_source':p['sources']=p['sources'][:1]
                elif kind=='same_provider':p['sources'][1]['provider']=p['sources'][0]['provider']
                elif kind=='same_host':p['sources'][1]['source_url']='https://example.org/second'
                elif kind=='no_official':p['sources'][0]['source_class']='independent_scoreboard'
                elif kind=='wrong_best_of':p['best_of']=5
                else:s['_match']['set_scores_home_away']=[[0,3],[1,6]]
                self.assertIsNotNone(G.verified_result_problem(s))

    def test_unverified_draft_behavior_is_not_expanded(self):
        s=fixture();s['_match']['status']='pending'
        self.assertIsNone(G.verified_result_problem(s))


if __name__=='__main__':
    unittest.main()
