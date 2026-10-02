"""Five exact approved film identities from public production specs; no general bypass."""
import copy,json,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import winners_ue_gate as gate
FIXTURES=json.loads((ROOT/'tests/fixtures/approved_wue_five_films.json').read_text())
SCENARIOS=0

def fixture(slug):
    return copy.deepcopy(FIXTURES[slug])
class Boundaries(unittest.TestCase):
    def check(self,good,value):
        global SCENARIOS
        SCENARIOS+=1
        self.assertIsNone(value) if good else self.assertIsInstance(value,str)
    def test_five_exact_matches(self):
        self.assertEqual(set(gate.APPROVED_WUE_OMISSIONS),set(FIXTURES) | {'yuan-andreeva-beijing-2026-r2'})
        for slug in FIXTURES:self.check(True,gate.problem(fixture(slug)))
    def test_all_match_identity_changes_rejected(self):
        mutations={'status':'scheduled','source':'wrong','source_id':'wrong','date':'2026-10-02','winner_result':'0-0','winner':'wrong','loser':'wrong','participants':['wrong','wrong'],'set_scores_home_away':[[0,0]]}
        for slug in FIXTURES:
            for key,value in mutations.items():
                with self.subTest(slug=slug,key=key):
                    d=fixture(slug);d['_match'][key]=value;self.check(False,gate.problem(d))
    def test_cover_binding_changes_rejected(self):
        for slug in FIXTURES:
            for key,value in [('eyebrow','other'),('winner','wrong'),('result','0-0'),('matchup',[]),('matchup',None)]:
                d=fixture(slug);d['cover'][key]=value;self.check(False,gate.problem(d))
            d=fixture(slug);d['cover']['matchup'].reverse();self.check(False,gate.problem(d))
    def test_omission_record_exact(self):
        for slug in FIXTURES:
            for key,value in [('slug','other'),('source_id','other'),('match_date','2026-10-02'),('fields',['winners']),('decision','allow_missing'),('authorization','unapproved')]:
                d=fixture(slug);d['stats']['_winners_ue_omission'][key]=value;self.check(False,gate.problem(d))
    def test_no_unknown_zero_or_fabricated_evidence(self):
        for slug in FIXTURES:
            for side in ['a','b']:
                for key in ['winners','ue']:
                    for value in [None,0,False,99]:
                        d=fixture(slug);d['stats'][side][key]=value;self.check(False,gate.problem(d))
            d=fixture(slug);d['stats']['_winners_ue_evidence']={};self.check(False,gate.problem(d))
            d=fixture(slug);del d['stats']['a'];self.check(False,gate.problem(d))
    def test_outside_scope_stays_blocked(self):
        d=fixture('zheng-shi-beijing-2026-r1');d['slug']='some-other-film';self.check(False,gate.problem(d))
        del d['stats']['_winners_ue_omission'];d['stats']['allow_missing']=True;self.check(False,gate.problem(d))
    def test_original_zheng_record_unchanged(self):
        self.assertEqual(gate.ZHENG_SHI_OMISSION,gate.APPROVED_WUE_OMISSIONS['zheng-shi-beijing-2026-r1'])
    def test_normal_complete_evidence_still_works(self):
        d=fixture('zheng-shi-beijing-2026-r1');d['slug']='unit-test-unapproved-scope';del d['stats']['_winners_ue_omission']
        d['stats']['a'].update(winners=1,ue=2);d['stats']['b'].update(winners=3,ue=4)
        d['stats']['_winners_ue_evidence']={'provider':'unit-test','method':'page','source_url':'https://example.org/unit-test','period':'Match','checked_at':'2026-10-01T00:00:00Z','match_date':'2026-10-01','winner_result':'7-6(6) 4-6 6-2','matchup':['Qinwen Zheng','Han Shi'],'winners':[1,3],'ue':[2,4]}
        self.check(True,gate.problem(d))
if __name__=='__main__':
    unittest.main()
