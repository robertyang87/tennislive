import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent))
import selective as s

CFG={'sources':[{'name':'Mixed Sport','require_tennis':True}], 'patterns_oncourt':['on-court interview'],
     'patterns_ceremony':[], 'patterns_maybe':['reacts after'], 'exclude':[], 'tennis_markers':['tennis']}

def response():
    answers={}
    for name,choices,choice in [('column',s.demo.COLUMNS,'interview'),('evidence',{'explicit_text','insufficient'},'explicit_text')]:
        answers[name]={'type':'choice','choice':choice,'confidence':1.,'probabilities':{k:float(k==choice) for k in choices}}
    return {'model':s.MODEL,'answers':answers,'usage':{'input_tokens':100,'output_tokens':10}}

class SelectiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.ledger=s.Ledger(Path(self.tmp.name)/'cache.db')
        self.calls=0
    def tearDown(self):
        self.ledger.db.close();self.tmp.cleanup()
    def caller(self,*args):
        self.calls+=1
        return {'status':'ok','response':response(),'elapsed_ms':1}
    def test_baseline_and_sport_and_tail_preserved(self):
        rules=s.collector.compile_rules(CFG)
        self.assertEqual(s.plan({'title':'Football post-match interview','source':'Mixed Sport'},CFG,rules),'existing_sport_gate')
        self.assertEqual(s.plan({'title':'highlights','tail_interview':True},CFG,rules),'preserve_tail_interview')
        self.assertEqual(s.plan({'title':'on-court interview'},CFG,rules),'existing_title_rule')
        self.assertEqual(s.plan({'title':'something','kind':'oncourt'},CFG,rules),'existing_inventory')
    def test_cold_warm_duplicate_and_input_change(self):
        item={'id':'1','title':'Player reacts after victory'}
        with patch.dict(s.os.environ,{'TYPESAFE_API_KEY':'unit-test'}):
            cold=s.run([item,item],CFG,self.ledger,live=True,caller=self.caller)
            warm=s.run([item],CFG,self.ledger,live=True,caller=self.caller)
            changed=s.run([dict(item,title='Player reacts after defeat')],CFG,self.ledger,live=True,caller=self.caller)
        self.assertEqual(cold['api_attempts'],1)
        self.assertEqual(cold['counts']['duplicate_in_batch'],1)
        self.assertEqual(warm['counts'],{'cache_hit':1})
        self.assertEqual(changed['api_attempts'],1)
        self.assertEqual(self.calls,2)
        self.assertEqual(warm['estimated_known_jev_cost_usd'],0)
        self.assertIsNone(cold['savings_vs_current_pipeline_usd'])
        self.assertTrue(all(r['production_action']=='unchanged' for r in cold['records']))
    def test_run_and_daily_budgets(self):
        items=[{'title':'Unclear '+str(i)} for i in range(4)]
        with patch.dict(s.os.environ,{'TYPESAFE_API_KEY':'unit-test'}):
            a=s.run(items,CFG,self.ledger,live=True,max_calls=1,daily_limit=2,caller=self.caller)
            b=s.run(items,CFG,self.ledger,live=True,max_calls=10,daily_limit=2,caller=self.caller)
        self.assertEqual(a['api_attempts'],1);self.assertEqual(a['counts']['run_budget_fallback'],3)
        self.assertEqual(b['api_attempts'],1);self.assertEqual(b['counts']['daily_budget_fallback'],2)
    def test_rate_limit_stops_remaining_requests(self):
        def limited(*args):return {'status':'http_error','http_status':429}
        with patch.dict(s.os.environ,{'TYPESAFE_API_KEY':'unit-test'}):
            r=s.run([{'title':'Unclear '+str(i)} for i in range(4)],CFG,self.ledger,live=True,caller=limited)
        self.assertEqual(r['api_attempts'],1);self.assertEqual(r['counts']['circuit_fallback'],3)
    def test_timeout_circuit(self):
        with patch.dict(s.os.environ,{'TYPESAFE_API_KEY':'unit-test'}):
            r=s.run([{'title':'Unclear '+str(i)} for i in range(5)],CFG,self.ledger,live=True,caller=lambda *args:{'status':'transport_error'})
        self.assertEqual(r['api_attempts'],3);self.assertEqual(r['counts']['circuit_fallback'],2)
    def test_ttl_corruption_and_claim(self):
        key='test';now=s.time.time()
        self.assertEqual(self.ledger.reserve(key,live=True,daily_limit=2)[0],'reserved')
        self.assertEqual(self.ledger.reserve(key,live=True,daily_limit=2)[0],'inflight_fallback')
        self.ledger.finish(key,response())
        self.assertEqual(self.ledger.reserve(key,live=False,daily_limit=2)[0],'cache_hit')
        self.assertEqual(self.ledger.reserve(key,live=False,daily_limit=2,now=now+86401)[0],'would_call')
        self.ledger.db.execute('UPDATE cache SET response=?',('{broken',));self.ledger.db.commit()
        self.assertEqual(self.ledger.reserve(key,live=False,daily_limit=2)[0],'would_call')
    def test_empty_and_oversized_input(self):
        r=s.run([{'title':''},{'title':'x'*70000}],CFG,self.ledger)
        self.assertEqual(r['counts'],{'no_content':1,'invalid_input_fallback':1})
    def test_offline_and_no_key(self):
        with patch.dict(s.os.environ,{'TYPESAFE_API_KEY':''}):
            r=s.run([{'title':'Unclear'}],CFG,self.ledger,live=True,caller=self.caller)
        self.assertEqual(r['counts'],{'missing_key_fallback':1});self.assertEqual(self.calls,0)

if __name__=='__main__':unittest.main()
