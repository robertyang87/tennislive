import hashlib,json,subprocess,sys,shutil
from pathlib import Path
D=Path(__import__('os').environ['EALA_VOICE_REVIEW_DIR']);R=Path(__file__).resolve().parents[2];slug='eala-shi';E=R/'data/evidence'/slug/'voice';E.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sp=Path(sys.argv[1]);od=Path(sys.argv[2]);spec=json.loads(sp.read_text());film=od/f'{slug}.mp4'
subprocess.run([sys.executable,str(Path(__file__).with_name('consolidate.py')),str(sp)],check=True)
shutil.copytree(D/'evidence',E,dirs_exist_ok=True)
subprocess.run([sys.executable,str(Path(__file__).with_name('bind_final.py')),str(sp),str(od),sys.argv[3]],check=True)
mix=json.loads((D/'final-actual-bindings.json').read_text());qc=json.loads((od/'qc_attestation.json').read_text());inputs=json.loads((od/'render_inputs.json').read_text());render=json.loads((od/'render.json').read_text())
assert sha(film)==mix['film_sha256']==qc['film_sha256']==inputs['film_sha256']
assert film.stat().st_size==mix['film_bytes']==qc['film_bytes']==inputs['film_bytes']
assert sha(sp)==mix['spec_sha256']==qc['spec_sha256']==inputs['spec_sha256']
assert qc['status']=='pass' and sha(od/'subtitles.ass')==qc['ass_sha256'] and sha(od/'render_inputs.json')==qc['render_inputs_sha256']
assert spec.get('outro') is False and not spec.get('cover',{}).get('narration')and float(render.get('outro_seconds',0))==0
review=json.loads((D/'formal-pronunciation-review.json').read_text());assert review['slug']==slug and not review['confident_misread_occurrences'],'Actual reliable pronunciation error remains';expected={b['index']:b for b in review['native_prepared_bindings']['bindings']};actual={b['index']:b for b in mix['bindings']}
assert set(expected)==set(actual)
for i,b in actual.items():assert b['actual_mp3_sha256']==expected[i]['actual_mp3_sha256']and b['text']==expected[i]['text']
assert mix['all_mixed_waveforms_strong_match']and mix['all_production_word_marks_match'],'Final encoded audio or paired marks not fully confirmed'
review.update(final_actual_mix_binding=mix,final_encoded_audio_binding_confirmed=True,final_film_sha256=sha(film))
review['limitations']=[x for x in review['limitations']if'final film AAC/PCM identity is pending'not in x]
(E/'native-cache-pronunciation-review.json').write_text(json.dumps(review,ensure_ascii=False,separators=(',',':'))+'\n')
(E/'final-actual-audio-bindings.json').write_text(json.dumps(mix,ensure_ascii=False,indent=2)+'\n')
diagnostic_path=E/'diagnostic-uncertainty-adjudication.json'
if diagnostic_path.exists():
 diagnostic=json.loads(diagnostic_path.read_text());diagnostic.update(native_pronunciation_review_sha256=sha(E/'native-cache-pronunciation-review.json'),current_formal_spec_sha256=sha(sp),final_film_sha256=sha(film),current_finite_comparison_count=review['comparison_count'],remaining_uncertain_count=review['unresolved_occurrences'],current_reliable_misread_count=review['confident_misread_occurrences'],reviewed_records=review['diagnostic_uncertainty_review_records'])
 diagnostic_path.write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2)+'\n')

asr_path=E/'complete-speech-asr-input-manifest.json'
if asr_path.exists():
 asr=json.loads(asr_path.read_text());assert sha(asr['path'])==asr['sha256'];by_edit={b['edit_id']:b for b in review['native_prepared_bindings']['bindings']}
 for part in asr['parts']:
  b=by_edit[part['edit_id']];a=actual[b['index']];assert part['actual_mp3_sha256']==a['actual_mp3_sha256'];part.update(index=b['index'],actual_rendered_voice_path=a['actual_voice_path'],final_film_timeline_offset_s=a['timeline_offset_s'],actual_film_waveform_binding=a['mixed_waveform_binding'])
 asr.update(final_film_sha256=sha(film),current_formal_spec_sha256=sha(sp),final_encoded_film_binding_status='all_current_strong_waveform_matches_to_exact_current_native_zip_audio',human_listening_claimed=False,asr_used_to_prove_tones=False)
 asr_path.write_text(json.dumps(asr,ensure_ascii=False,indent=2)+'\n')
manifest={'schema':'tennislive.final-audio-review-manifest.v3','slug':slug,'status':'actual_native_aac_pcm_binding_confirmed_with_pronunciation_limits','pronunciation_status':review['status'],'pronunciation_release_pass_claimed':False,'human_listening_claimed':False,'asr_used_to_prove_tones':False,'film_sha256':sha(film),'film_bytes':film.stat().st_size,'spec_sha256':sha(sp),'render_json_sha256':sha(od/'render.json'),'qc_attestation_sha256':sha(od/'qc_attestation.json'),'render_inputs_sha256':sha(od/'render_inputs.json'),'subtitles_ass_sha256':sha(od/'subtitles.ass'),'native_full_mix_pcm':mix['native_full_mix_pcm'],'actual_voice_count':len(actual),'all_actual_mp3_exact_native_zip_and_reviewed_audio':True,'all_production_word_marks_exact_native_cache':True,'all_mixed_waveforms_strong_match':True,'pronunciation_occurrence_counts':review['occurrence_counts'],'pronunciation_comparison_count':review['comparison_count'],'pronunciation_comparison_counts':review['comparison_counts'],'unresolved_occurrences':review['unresolved_occurrences'],'confident_misread_occurrences':review['confident_misread_occurrences'],'all_enumerated_polyphones_covered':review['all_enumerated_polyphones_covered'],'exclusions':{'brand_outro':False,'cover_narration':False},'method':'Fresh current full-sentence native ZIP audio+paired marks; finite same-voice/rate calibrated MFCC/F0 controls. Current AAC waveforms correlated with exact native speech, entire native-channel/rate PCM hashed. Final QC/ASS/render inputs/spec identities bind the same film. All uncertain/no-reference/low-confidence cases remain explicit; no historical episode evidence substituted.','evidence':{n:{'path':str(E/n),'sha256':sha(E/n)}for n in ['native-cache-pronunciation-review.json','native-voice-freeze.json','final-actual-audio-bindings.json']}}
if review.get('same_episode_exact_unchanged_control_reuse'):manifest['same_episode_exact_unchanged_control_reuse']=review['same_episode_exact_unchanged_control_reuse']
manifest['current_reliable_misread_count']=review['confident_misread_occurrences'];manifest['remaining_uncertain_count']=review['unresolved_occurrences'];manifest['raw_misread_diagnostic_limit_count']=len(review.get('diagnostic_uncertainty_review_records',[]))
for name in ['voice-word-sidecar-restoration.json','fresh-native-control-file-manifest.json','final-result-content-mapping.json','diagnostic-uncertainty-adjudication.json','raw-misread-boundary-diagnostics.json','edge-endpoint-migration-provenance.json','complete-speech-asr-input-manifest.json','complete-speech-word-recognition-support.json','native-asr-large-v3-zh.json','native-asr-turbo-zh.json','same-sentence-name-diagnostic-raw.json','same-sentence-name-diagnostic-review.json','unchanged-current-utterance-reuse.json','scope.json']:
 if (E/name).exists():manifest['evidence'][name]={'path':str(E/name),'sha256':sha(E/name)}
(E/'final-audio-review-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'manifest':str(E/'final-audio-review-manifest.json'),'voices':len(actual),'film_sha256':sha(film),'unresolved_occurrences':review['unresolved_occurrences'],'confident_misread_occurrences':review['confident_misread_occurrences']},ensure_ascii=False))
