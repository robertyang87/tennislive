import hashlib,json,shutil,sys,os,math
from pathlib import Path
from collections import Counter
D=Path(os.environ['EALA_VOICE_REVIEW_DIR']);R=Path(__file__).resolve().parents[2]; slug='eala-shi'; E=D/'evidence';E.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
specpath=Path(sys.argv[1]);spec=json.loads(specpath.read_text());prep=json.loads((D/'native-bindings.json').read_text());job=json.loads((D/'native-job.json').read_text())
assert spec.get('outro') is False and not spec.get('cover',{}).get('narration')
formal={s['_edit_id']:(i,s)for i,s in enumerate(spec['segments'])if s.get('narration')}
assert set(formal)==set(b['edit_id']for b in prep['bindings']),'Actual utterance membership changed; prepare and audit again.'
initial_indices={b['edit_id']:b['index']for b in prep['bindings']}
for b in prep['bindings']:
 i,segment=formal[b['edit_id']]
 assert segment['narration']==b['display_text'],'Frozen display narration changed; prepare and audit again.'
 assert (segment.get('voice')or{}).get('rate','+6%')==b['rate']and (segment.get('voice')or{}).get('pitch','+0Hz')==b['pitch']
 b.update(index=i,label=f'第 {i+1} 段',window_seconds=float(segment['seconds'])if'seconds'in segment else float(segment['end'])-float(segment['start']))
 b['headroom_seconds']=b['window_seconds']-b['mp3_duration_seconds']
 assert sha(b['bound_snapshot_path'])==b['actual_mp3_sha256']
 assert sha(b['marks_snapshot_path'])==b['actual_marks_sha256']
 assert sha(b['native_zip_snapshot_path'])==b['native_zip_sha256']
prep.update(formal_spec_sha256_at_mapping=sha(specpath),mapping_method='Exact frozen display text and voice parameters per edit ID; formal metadata/timing may change without new audio. Current formal indices and windows rebound; initial complete spec SHA retained.')
mapping={'schema':'tennislive.current-native-voice-content-mapping.v1','slug':slug,'initial_complete_spec_sha256':prep['spec_sha256_at_preparation'],'current_formal_spec_sha256':sha(specpath),'initial_native_bindings_sha256':sha(D/'native-bindings.json'),'complete_initial_spec_claimed_unchanged':prep['spec_sha256_at_preparation']==sha(specpath),'stable_identity_method':'Exact stable edit ID, complete display and spoken text, voice/rate/pitch and actual reviewed native MP3/marks/ZIP hashes; indices/windows are metadata mapping, not original-audio identity.','entries':[{'edit_id':b['edit_id'],'initial_segment_index':initial_indices[b['edit_id']],'current_formal_segment_index':b['index'],'actual_mp3_sha256':b['actual_mp3_sha256'],'actual_marks_sha256':b['actual_marks_sha256'],'current_window_seconds':b['window_seconds'],'actual_mp3_duration_seconds':b['mp3_duration_seconds'],'headroom_seconds':b['headroom_seconds']}for b in prep['bindings']],'human_listening_claimed':False}
(E/'final-result-content-mapping.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
rows=[];raw=[]
for i,t in enumerate(job['targets']):
 p=D/'native-targets'/f'target-{i:03}.json'
 if not p.exists():raise RuntimeError(f'Missing fresh result {p}')
 r=json.loads(p.read_text()); assert r['sentence']==t['sentence'] and r['at']==t['at'] and r['wrong']==t['wrong']
 assert r['actual_binding']['actual_mp3_sha256']==t['actual_binding']['actual_mp3_sha256']
 r.update(raw_record_path=str(p),raw_record_sha256=sha(p));rows.append(r);raw.append({'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size})
def diagnostic_limits(r):
 a=r.get('acoustic',{});limits=[]
 if a.get('confidence')not in ('medium','high'):limits.append('Not medium/high relative confidence.')
 if a.get('far_from_both'):limits.append('Actual target is far from both reference classes.')
 if a.get('selftest_pass')is not True or set(a.get('selftest_sides',[]))!={'A','B'}:limits.append('Both-sided LOO self-calibration is not confirmed.')
 if r.get('reference_validity_limited'):limits.append('Declared independent reference validity is limited.')
 if r.get('intended','')[:-1]==r.get('wrong','')[:-1]:
  f0=a.get('features',{}).get('f0',{})
  if any(not isinstance(f0.get(k),(int,float))or not math.isfinite(f0[k])for k in ['d_intended','d_wrong']):limits.append('Same-syllable tone contrast lacks finite F0 distance on both sides; combined MFCC/F0 distance is not comparable.')
 return limits
for r in rows:
 r['review_diagnostic_limits']=diagnostic_limits(r)
 r['relative_verdict_supported']=not r['review_diagnostic_limits']and r['acoustic'].get('verdict')in ('correct','misread')
groups={}
for r in rows+job['unresolved_no_valid_reference']:groups.setdefault((r['sentence'],r['at'],r['actual_binding']['actual_mp3_sha256']),[]).append(r)
occ=[]
for (text,at,h),runs in groups.items():
 a=runs[0];acc=[r.get('acoustic',{})for r in runs]
 wrong=any(q.get('verdict')=='misread'and r.get('relative_verdict_supported')is True for q,r in zip(acc,runs))
 correct=all(q.get('verdict')=='correct'and r.get('relative_verdict_supported')is True for q,r in zip(acc,runs))
 status='confident_misread'if wrong else 'relative_correct_under_calibrated_controls'if correct else'unresolved_calibration_or_reference_limit'
 occ.append({'label':a['label'],'edit_id':a['edit_id'],'text':text,'char':a['char'],'at':at,'intended':a['intended'],'actual_mp3_sha256':h,'reviewed_verdict':status,'runs':[{'wrong':r['wrong'],'check_kind':r['check_kind'],'raw_record_path':r.get('raw_record_path'),'raw_record_sha256':r.get('raw_record_sha256'),'acoustic':r.get('acoustic'),'no_reference_reason':r.get('why'),'reference_validity_limited':r.get('reference_validity_limited'),'review_diagnostic_limits':r.get('review_diagnostic_limits')}for r in runs]})
counts=dict(Counter(o['reviewed_verdict']for o in occ));pending=[o for o in occ if o['reviewed_verdict']=='unresolved_calibration_or_reference_limit'];bad=[o for o in occ if o['reviewed_verdict']=='confident_misread']
coverage=job['coverage']
for c in coverage:
 for p in c['polyphone_occurrences']:p['actually_enumerated']=any(o['text']==c['text']and o['at']==p['at']for o in occ)
report={'schema':'tennislive.actual-pronunciation-review.v3','slug':slug,'status':'confident_misread_detected'if bad else'no_confident_misread_detected_with_calibration_limits'if pending else'finite_controls_supported','pronunciation_release_pass_claimed':False,'human_listening_claimed':False,'asr_used_to_prove_tones':False,'services_used':{'DeepSeek':False,'MiniMax':False},'spec_sha256':sha(specpath),'voice':'zh-CN-YunjianNeural','rate':'+6%','pitch':'+0Hz','native_prepared_bindings':prep,'coverage':coverage,'all_enumerated_polyphones_covered':all(p['actually_enumerated']for c in coverage for p in c['polyphone_occurrences']),'comparison_count':len(rows),'comparison_counts':dict(Counter(r['acoustic']['verdict']for r in rows)),'occurrence_counts':counts,'unresolved_occurrences':len(pending),'confident_misread_occurrences':len(bad),'occurrences':occ,'unresolved_occurrence_details':pending,'confident_misread_details':bad,'comparisons':rows,'diagnostic_uncertainty_review_records':[{'raw_record_path':r['raw_record_path'],'raw_record_sha256':r['raw_record_sha256'],'char':r['char'],'at':r['at'],'sentence':r['sentence'],'raw_verdict':r['acoustic']['verdict'],'raw_confidence':r['acoustic'].get('confidence'),'raw_score':r['acoustic'].get('score'),'review_diagnostic_limits':r['review_diagnostic_limits'],'reviewed_status':'unresolved_diagnostic_limit_not_pronunciation_pass'}for r in rows if r['acoustic'].get('verdict')=='misread'and not r['relative_verdict_supported']],'raw_record_manifest':raw,'no_valid_reference_records':job['unresolved_no_valid_reference'],'method':job['method'],'exclusions':job['exclusions'],'final_encoded_audio_binding_confirmed':False,'limitations':['MFCC/F0 homophone tests are finite relative comparisons, not exhaustive pronunciation certification.','Low confidence, far-from-both, unreliable, uncertain, no refs and reference-limited cases are retained pending.','WordBoundary tokens are tokenizer segmentation, not phoneme ground truth.','This review currently binds native MP3/cache only; final film AAC/PCM identity is pending.']}
reuse_path=D/'unchanged-current-utterance-reuse.json'
if reuse_path.exists():
 reuse=json.loads(reuse_path.read_text());assert set(reuse['changed_edit_ids'])=={'first_set_pressure','long_rally_context'}and len(reuse['unchanged_edit_ids'])==7
 report['same_episode_exact_unchanged_control_reuse']={'manifest_sha256':sha(reuse_path),'reused_raw_record_count':reuse['reused_raw_record_count'],'current_new_comparison_count':len(rows)-reuse['reused_raw_record_count'],'changed_edit_ids':reuse['changed_edit_ids'],'old_changed_utterance_verdicts_promoted':False}
 shutil.copy2(reuse_path,E/reuse_path.name)
(D/'formal-pronunciation-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(E/'native-cache-pronunciation-review.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':'))+'\n')
(E/'native-voice-freeze.json').write_text(json.dumps(prep,ensure_ascii=False,indent=2)+'\n')
audio_manifest=[]
for folder in ['native-speech','reference-audio','native-targets']:
 for source in sorted((D/folder).glob('*')):
  if not source.is_file():continue
  destination=E/folder/source.name;destination.parent.mkdir(exist_ok=True)
  shutil.copy2(source,destination)
  audio_manifest.append({'path':str(destination),'source_path':str(source),'sha256':sha(destination),'bytes':destination.stat().st_size})
(E/'fresh-native-control-file-manifest.json').write_text(json.dumps({'schema':'tennislive.fresh-control-provenance.v1','spec_sha256':sha(specpath),'files':audio_manifest,'method':'Fresh current episode only. Exact native MP3/paired marks, independent same-sentence reference MP3/marks, and all raw calibration records are snapshotted with hashes.'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'voices':len(prep['bindings']),'comparison_count':len(rows),'counts':counts,'pending':len(pending),'confident_misread':len(bad),'spec_sha256':sha(specpath),'report':str(E/'native-cache-pronunciation-review.json')},ensure_ascii=False))
