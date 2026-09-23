import collections, hashlib, json, sys, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import jev_selective as selective
import jev_production as production
import jev_review_queue as queue
root=Path(__file__).resolve().parents[2]
out=root/'jev-effect-results';out.mkdir(exist_ok=True)
paths=[root/'data/oncourt_interviews.json',root/'data/oncourt_verify.json']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
inv=json.loads(paths[0].read_text())['items'];verdicts=json.loads(paths[1].read_text())['verdicts']
cfg=selective.collector.load_sources();rules=selective.collector.compile_rules(cfg)
# Existing production inputs, with all decisions intact. No network allowed.
with patch('urllib.request.build_opener',side_effect=AssertionError('baseline must not call network')):
 baseline=production.evaluate(list(inv.values()),out/'baseline.sqlite')
assert baseline['api_attempts']==0
counts=collections.Counter(); pool=[]
for vid,v in sorted(verdicts.items()):
 item=dict(inv.get(vid,{}),id=vid,title=v.get('title',''),source=v.get('source',''))
 item.pop('kind',None) # Explicit counterfactual: title routing before known inventory classification.
 decision=selective.plan(item,cfg,rules);counts[v.get('verdict','unknown')+'|'+decision]+=1
 if decision=='candidate' and vid.startswith('tennistv:') and not item.get('unofficial'):
  pool.append(item)
# Five evenly spaced entries by ID; chosen before seeing model responses.
selected=[pool[round(i*(len(pool)-1)/4)] for i in range(5)]
t=time.monotonic();cold=production.evaluate(selected,out/'challenge.sqlite');cold_ms=round((time.monotonic()-t)*1000,2)
with patch('urllib.request.build_opener',side_effect=AssertionError('warm run must not call network')):
 t=time.monotonic();warm=production.evaluate(selected,out/'challenge.sqlite');warm_ms=round((time.monotonic()-t)*1000,2)
assert cold['api_attempts']<=5 and warm['api_attempts']==0
q={'version':1,'items':{}};merge=queue.merge_report(q,cold,verdicts)
assert not q['items'], 'Previously reviewed material must not be requeued'
assert before=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
rows=[]
for item,result in zip(selected,cold['records']):
 rows.append(dict(id=item['id'],title=item['title'],source=item['source'],reference=verdicts[item['id']],result=result))
report=dict(base_commit='bbd473107a0a8cac9652b3f444a7057e4d922f52',inventory_size=len(inv),baseline=baseline,reference_route_counts=dict(counts),ambiguous_official_pool=len(pool),selection='5 evenly spaced by ID, counterfactual kind removed; historical labels are poster-based, not fresh video review',cold=cold,warm=warm,cold_ms=cold_ms,warm_ms=warm_ms,rows=rows,queue_merge=merge,production_files_unchanged=True,new_approved_candidates=0,renders=0,publishes=0)
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
summary={k:report[k] for k in ['inventory_size','reference_route_counts','ambiguous_official_pool','selection','cold_ms','warm_ms','rows','queue_merge','production_files_unchanged','new_approved_candidates','renders','publishes']}
summary['baseline_counts']=baseline['counts'];summary['cold_counts']=cold['counts'];summary['warm_counts']=warm['counts'];summary['api_attempts']=cold['api_attempts'];summary['known_input_tokens']=cold['known_input_tokens']
print(json.dumps(summary,ensure_ascii=False,indent=2))
