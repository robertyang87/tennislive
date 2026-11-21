from pathlib import Path
import json,sys,tempfile,concurrent.futures
R=Path('/workspace/tennislive-sparse');O=Path('/workspace/davis-cup-preview-2026');sys.path[:0]=[str(R/'tools'),str(R/'src')]
import voice_auto_review as v
S=json.loads((O/'story.json').read_text())
with tempfile.TemporaryDirectory() as d:
 entries=v.load_bundle(O/'tts_bundle.zip',Path(d))
 if '--asr' in sys.argv:
  old=json.loads((O/'asr-small.json').read_text()) if (O/'asr-small.json').exists() else {}
  result={e['id']:old[e['id']] for e in entries if e['id'] in old}
  pending=[e for e in entries if e['id'] not in result]
  if pending:result.update(v.run_asr(pending,'small',v._names(S)))
  (O/'asr-small.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  for e in entries:
   c=v.compare_transcript(e['request']['text'],result[e['id']]);print(e['id'][-10:],c['ok'],result[e['id']],flush=True)
 else:
  pairs=[(e,t) for e in entries for t in v.poly_targets(e['request']['text'])]
  def measure(et):
   e,t=et;m=v.measure_target(e,t);print(e['id'][-8:],t['word'],m['verdict'],flush=True);return {'id':e['id'],'target':m}
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(measure,pairs))
  (O/'polyphone-precheck.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
