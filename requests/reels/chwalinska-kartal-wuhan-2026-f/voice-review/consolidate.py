"""Consolidate this episode without promoting uncertainty to pronunciation pass."""
from pathlib import Path
import argparse,json,hashlib,datetime
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();job=json.loads((out/'job.json').read_text());records=[];measured=[];unknown=[];wrong=[];supported=[]
for i,t in enumerate(job['targets']):
    path=out/'targets'/f'{i:03}.json'
    if not path.exists():unknown.append(dict(target=i,status='not_measured',edit_id=t['edit_id'],char=t['char'],at=t['at']));continue
    d=json.loads(path.read_text());assert all(d.get(k)==t.get(k) for k in ['sentence','at','char','intended','wrong','ok_refs','bad_refs','actual_binding'])
    r=d['acoustic'];m=dict(target=i,edit_id=t['edit_id'],char=t['char'],at=t['at'],intended=t['intended'],wrong=t['wrong'],verdict=r['verdict'],confidence=r.get('confidence'),score=r.get('score'),path=str(path));records.append(m)
    if r['verdict']!='insufficient_controls':measured.append(m)
    if r['verdict']=='misread' and r.get('confidence') in ['high','medium']:wrong.append(m)
    elif r['verdict']=='correct' and r.get('confidence') in ['high','medium']:supported.append(m)
    else:unknown.append(m)
asr={}
for model in ['small','large-v3-turbo']:
    path=out/f'asr-{model}.json'
    if path.exists():
        d=json.loads(path.read_text());assert d['bundle_sha256']==job['bundle_sha256'];asr[model]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),status=d['status'],input_wav_sha256=d['input_wav_sha256'],tone_evidence=False)
refs=[]
for path in sorted((out/'reference-cache').glob('*')):
    if path.is_file():refs.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size))
result=dict(schema='tennislive.finite-frozen-speech-result.v1',slug=job['slug'],created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),bundle_sha256=job['bundle_sha256'],spec_sha256_at_binding=job['spec_sha256'],bindings=job['bindings'],coverage=job['coverage'],target_results=records,measured=measured,counts=dict(candidate_contrasts=len(job['targets']),target_records=len(records),acoustic_attempts=len(measured),insufficient_controls_not_measured=sum(r['verdict']=='insufficient_controls'for r in records),supported_correct_contrasts=len(supported),confirmed_misread_contrasts=len(wrong),unknown_contrasts=len(unknown),no_independent_reference_branches=len(job['unknown_no_valid_reference'])),supported_correct_contrasts=supported,confirmed_misread_contrasts=wrong,unknown_contrasts=unknown,no_independent_reference_branches=job['unknown_no_valid_reference'],owner_confirmation_reuse=job.get('owner_confirmation_reuse'),asr=asr,reference_artifact_hashes=refs,overall_status='unknown_pending_pronunciation_review' if unknown or job['unknown_no_valid_reference'] else 'finite_acoustic_checks_complete',assistant_listening_claimed=False,new_utterances_human_listening_claimed=False,pronunciation_release_pass_claimed=False,limitations=['ASR character output and native WordBoundary do not establish tone or naturalness.','Dictionary candidate branches are inventory, not observed pronunciation errors.','Machine unknowns remain unknown; any reused owner confirmation is scoped to the exact unchanged complete utterance and actual bytes.','Changed wording, voice,parameters or actual production bytes requires fresh binding and review.'])
(out/'voice-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['counts'],ensure_ascii=False));print('confirmed_wrong',wrong);print('brand_owner_confirmation_reused',bool(job.get('owner_confirmation_reuse')))
