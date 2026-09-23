import hashlib,json,sys,time,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import jev_production as production
import jev_review_queue as queue
import verify_oncourt_sample as visual
root=Path(__file__).resolve().parents[2];out=root/'jev-optimized-results';out.mkdir(exist_ok=True)
paths=[root/'data/oncourt_interviews.json',root/'data/oncourt_verify.json']
before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
inv=json.loads(paths[0].read_text())['items'];verdicts=json.loads(paths[1].read_text())['verdicts']
ids=['tennistv:4229685','tennistv:4256043','tennistv:4337459','tennistv:4475115','tennistv:4535877']
items=[dict(inv[vid]) for vid in ids]
for item in items:item.pop('kind',None)
with patch('urllib.request.build_opener',side_effect=AssertionError('No network required')):
 start=time.monotonic();report=production.evaluate(items,out/'cache');elapsed=round((time.monotonic()-start)*1000,2)
 baseline=production.evaluate(list(inv.values()),out/'baseline-cache')
assert report['api_attempts']==0 and len(report['review_queue'])==5
assert baseline['api_attempts']==0 and not baseline['review_queue']
existing={'version':1,'items':{}};skip=queue.merge_report(existing,report,verdicts)
assert skip['existing_visual_decisions']==5 and not existing['items']
# A separate counterfactual temporary queue models first discovery; never writes production state.
state={'version':1,'items':{}};merge=queue.merge_report(state,report,{})
path=out/'shadow-queue.json';path.write_text(json.dumps(state))
empty=out/'empty-verdicts.json';empty.write_text('{"verdicts":{}}')
with patch.object(visual,'VERDICTS',empty):visual.prepare_jev_review(path,out/'visual',5)
waiting=json.loads((out/'visual/waiting-sites.json').read_text())
assert len(waiting)==5 and all(r['status']=='waiting_video_frames' for r in waiting)
assert before==[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
summary={'prior_run':35816843109,'same_ids':ids,'before':{'api_calls':5,'review_leads':0,'batch_ms':1097.25,'input_tokens':3196},'after':{'api_calls':0,'review_leads':5,'batch_ms':elapsed,'input_tokens':0},'inventory_replay':{'total':len(inv),'api_calls':baseline['api_attempts'],'review_leads':len(baseline['review_queue'])},'existing_verdicts_preserved':skip,'counterfactual_queue_merge':merge,'site_waiting_actual_video':len(waiting),'new_approved_candidates':0,'production_files_unchanged':True,'renders':0,'publishes':0}
(out/'report.json').write_text(json.dumps({'summary':summary,'routing':report},ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
