import hashlib, json, os, time
from pathlib import Path
import jev_client as client
import jev_production as production
import jev_selective as selective
import jev_review_queue as review
from interview_source_gate import validate_source_contract
slugs = ['gauff-pegula-cin2026-final', 'zheng-liutova-us-open-2026-r1-interview', 'rybakina-sabalenka-us-open-2026-final-ceremony']
out = Path('/tmp/jev-history-comparison'); out.mkdir()
results=[]
for slug in slugs:
    path = Path('specs/interviews') / (slug + '.json')
    original = path.read_bytes(); spec = json.loads(original)
    src = spec['source_verification']
    item = {'id':slug,'title':src['title'],'source':src['source'],'url':spec['url'],
            'kind':'ceremony' if spec['requested_content_type']=='ceremony' else 'oncourt'}
    started=time.monotonic()
    routed=production.evaluate([item],out/(slug+'.sqlite'))
    routing_ms=round((time.monotonic()-started)*1000,2)
    assert routed['api_attempts']==0
    # A separate diagnostic, explicitly NOT a production override.
    model=client.run_one({'title':item['title'],'source':item['source']},os.environ.get('TYPESAFE_API_KEY'),True,model=selective.MODEL,timeout=8)
    try:
        validate_source_contract(spec)
        l0={'passed':True}
    except Exception as exc:
        l0={'passed':False,'reason':str(exc)}
    digest=hashlib.sha256(original).hexdigest()
    assert path.read_bytes()==original
    result={'slug':slug,'existing_kind':spec['requested_content_type'],'production_route':routed,
            'routing_ms':routing_ms,'diagnostic_only':model,'l0':l0,
            'spec_sha256_before':digest,'spec_sha256_after':digest,
            'render_configuration_changed':False,'renders':0,'publishes':0}
    results.append(result)
    (out/(slug+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    answer=model.get('response',{}).get('answers',{}).get('column',{})
    print(json.dumps({'slug':slug,'baseline_kind':spec['requested_content_type'],'pipeline_api_calls':routed['api_attempts'],'diagnostic_status':model['status'],'diagnostic_ms':model.get('elapsed_ms'),'suggestion':answer.get('choice'),'confidence':answer.get('confidence'),'l0':l0,'spec_unchanged':True},ensure_ascii=False))
(out/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
assert all(r['diagnostic_only']['status']=='ok' for r in results), 'Diagnostic API failure recorded; no automatic retry'
