"""Bind lightweight revised-outlook evidence to actual native film; no speech regeneration."""
import argparse,json,hashlib,math,datetime,zipfile,shutil,sys
from pathlib import Path
O=Path(__file__).resolve().parent;R=Path('/workspace/tennislive-efficiency');SLUG='davidovich-zverev-shanghai-2026-sf';E=R/'data/evidence'/SLUG/'final-outlook-update/voice';S=R/'specs/reels'/f'{SLUG}.json'
sys.path[:0]=[str(R/'src'),str(R/'tools')]
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def rd(n):return json.loads((O/n).read_text())
def finite(x):
 if isinstance(x,float)and not math.isfinite(x):return None
 if isinstance(x,dict):return{k:finite(v)for k,v in x.items()}
 if isinstance(x,list):return[finite(v)for v in x]
 return x
def wr(n,x):(O/n).write_text(json.dumps(finite(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def now():return datetime.datetime.now(datetime.UTC).isoformat()
def sync():
 for p in O.glob('*.json'):
  if p.name in ['reference-allowlist.json','reference-provenance.json','focused-reference-provenance.json','target-reference-dictionary.json','prior-published-finite-review.json']:continue
  if p.name=='root-direct-review.json'and (E/p.name).exists():continue
  (E/p.name).write_text(json.dumps(finite(json.loads(p.read_text())),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 for n in ['FINAL_REVIEW.md','seal_changed_review.py']:shutil.copyfile(O/n,E/n)
def validate():
 B=rd('bindings.json');rep=rd('report.json');spec=json.loads(S.read_text());want={f'voice_{i:02d}.mp3':(x.get('_edit_id',f'segment_{i}'),x['narration'])for i,x in enumerate(spec['segments'])if str(x.get('narration')or'').strip()}
 if spec.get('outro',True):want['voice_outro.mp3']=('outro',NARRATION)
 assert set(want)=={b['output_name']for b in B};assert rep['current_finite_pending_count']==0 and rep['human_listening_claimed']is False and rep['all_mechanical_components_passed']is False
 for b in B:
  eid,text=want[b['output_name']];assert eid==b['edit_id']and speakable(text)==b['tts_text'];assert sha(b['native_audio'])==b['audio_sha256']and sha(b['native_marks'])==b['marks_sha256']
  assert all(b['request'][k]==v for k,v in {'backend':'edge','voice':'zh-CN-YunjianNeural','rate':'+6%','pitch':'+0Hz','style':'','styledegree':''}.items())
 bundle=next(p for p in O.glob('input-bundle-*.zip')if sha(p)==rep['new_bundle_sha256']);assert bundle.stat().st_size==rep['new_bundle_bytes']
 reuse=rd('unchanged-five-review-reuse.json');assert len(reuse['reused_whole_requests'])==5
 for r in reuse['reused_whole_requests']:
  b=next(b for b in B if b['edit_id']==r['edit_id']);assert b['audio_sha256']==r['audio_sha256']and b['marks_sha256']==r['marks_sha256']and b['request_id']==r['request_id'];assert r['prior_archive_sha256']=='62e251159d925a0d1aae0dbbaab84eb29e78acb9606fba88166499fcfea6f2a7'and r['prior_archive_bytes']==17470976
 assert len(rep['occurrences'])==32 and rep['calibrated_current_finite_low_positions']==29 and rep['direct_current_finite_low_positions']==3
 for row in rd('changed-direct-review.json')['occurrences']:
  for im in row['actually_viewed_images']:assert sha(im['path'])==im['sha256']
 root=E/'root-direct-review.json';assert root.exists();shutil.copyfile(root,O/root.name);rr=rd(root.name);assert rr['bundle_sha256']==rep['new_bundle_sha256']
 for im in rr['plots_actually_viewed']:assert sha(O/'actual-plots-v1'/im['file'])==im['sha256']
 prov={**rd('reference-provenance.json'),**rd('focused-reference-provenance.json')};assert len(prov)==20
 for ap,m in prov.items():assert sha(ap)==m['audio_sha256']and sha(Path(ap).with_suffix('.json'))==m['marks_sha256']
 return B,rep,bundle
p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');p.add_argument('--film',type=Path);p.add_argument('--run-id',type=int);p.add_argument('--native-archive',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();B,rep,bundle=validate()
if a.prepare_only:
 wr('seal-preparation.json',{'created_at':now(),'status':'new_outlook_finite_review_ready_waiting_actual_revised_movie','bundle_sha256':rep['new_bundle_sha256'],'current_spec_sha256_provisional':sha(S),'actual_native_voice_requests':6,'newly_reviewed_requests':1,'old_five_review_cross_reference_only':True,'old17MB_control_archive_copied':False,'film_sha256':None,'final_archive_created':False,'human_listening_claimed':False});sync();print('PREPARED actual new6-request capsule, exact5 reuse, new1 finite review; no old controls or speech review rerun');raise SystemExit()
assert all([a.film,a.run_id,a.native_archive,a.output]);assert not a.output.exists(),'Never overwrite sealed evidence';film=a.film.resolve();arcpath=a.native_archive.resolve();arc=json.loads(arcpath.read_text());fh=sha(film);assert arc['slug']==SLUG and arc['run_id']==a.run_id and arc['film_sha256']==fh;ids=[]
for b in B:
 fn=b['output_name'];mn=fn.replace('.mp3','.words.json');assert arc['files'][fn]==b['audio_sha256']and arc['files'][mn]==b['marks_sha256'];ids.append({'edit_id':b['edit_id'],'output_name':fn,'marks_name':mn,'audio_sha256':b['audio_sha256'],'marks_sha256':b['marks_sha256'],'matches_actual_native_archive':True,'newly_reviewed':b['edit_id']=='outlook','old_exact_whole_request_review_reused':b['edit_id']!='outlook'})
D=arcpath.parent
for n in ['render_inputs.json','qc_attestation.json','subtitles.ass','topbar.ass']:assert sha(D/n)==arc['files'][n]
qc=json.loads((D/'qc_attestation.json').read_text());ri=json.loads((D/'render_inputs.json').read_text());rm=json.loads((D/'render.json').read_text());assert qc['status']=='pass'and qc['film_sha256']==fh and qc['film_bytes']==film.stat().st_size and qc['spec_sha256']==sha(S)and qc['ass_sha256']==sha(D/'subtitles.ass')and qc['render_inputs_sha256']==sha(D/'render_inputs.json');assert ri['spec_sha256']==sha(S)and ri['film_sha256']==fh and ri['film_bytes']==film.stat().st_size
assert rm['film_sha256']==fh and rm['film_bytes']==film.stat().st_size and rm['tts_bundle']['bundle_sha256']==rep['new_bundle_sha256']and rm['tts_bundle']['request_count']==6 and rm['tts_bundle']['mode']=='strict_import'and rm['tts_bundle']['strict_reused']is True
note={'post_upload_render_metadata_sha256':sha(D/'render.json'),'native_captured_render_metadata_sha256':arc['files']['render.json'],'same_render_metadata_bytes':sha(D/'render.json')==arc['files']['render.json'],'scope':'Post-upload render metadata may add delivery/stage fields; exact pre-upload bytes not claimed. Native QC/render_inputs/ASS match archive exactly; actual film and strict imported bundle validated independently.'}
wr('render-metadata-identity-note.json',note);binding={'bound_at':now(),'status':'current_revised_native_movie_bound_to_exact_five_old_and_one_new_reviewed_voice_inputs','film_sha256':fh,'film_bytes':film.stat().st_size,'run_id':a.run_id,'new_bundle_sha256':rep['new_bundle_sha256'],'bundle_bytes':rep['new_bundle_bytes'],'spec_sha256':sha(S),'subtitles_ass_sha256':sha(D/'subtitles.ass'),'topbar_ass_sha256':sha(D/'topbar.ass'),'render_inputs_sha256':sha(D/'render_inputs.json'),'native_qc_sha256':sha(D/'qc_attestation.json'),'native_input_archive_sha256':sha(arcpath),'native_qc_status':qc['status'],'actual_native_voice_inputs':ids,'prior_five_review_cross_reference':'unchanged-five-review-reuse.json','prior_control_archive_embedded':False,'old_five_pronunciation_reaudited':False,'new_outlook_review_repeated_after_render':False,'human_listening_claimed':False,'all_phonetic_or_all_tone_pass_claimed':False,'metadata_identity_only_no_audio_processing':True,'post_upload_render_note':note};wr('final-film-input-binding.json',binding)
rep.update(final_new_movie_binding_pending=False,film_sha256=fh,film_bytes=film.stat().st_size,run_id=a.run_id,current_spec_sha256=sha(S),final_film_input_binding='final-film-input-binding.json');wr('report.json',rep);cap=rd('capsule-input-manifest.json');cap.update(new_movie_binding_pending=False,actual_revised_film_sha256=fh,actual_revised_run_id=a.run_id,current_spec_sha256=sha(S));wr('capsule-input-manifest.json',cap)
with (O/'FINAL_REVIEW.md').open('a')as f:f.write(f'\n最终修订电影字节绑定：film `{fh}`；run `{a.run_id}`；spec `{sha(S)}`。当前6份原MP3/marks逐项精确匹配 native manifest；旧5沿用原有限审查、只新末段独立复核。此为声音输入身份绑定，不增加人听、全音素或整片视觉通过声明。\n')
files=[];excluded={'prior-published-finite-review.json','external-artifact-manifest.json','archive-entry-manifest.json'}
for q in sorted(O.rglob('*')):
 if not q.is_file()or '__pycache__'in q.parts or'native-cache'in q.parts or'native-check'in q.parts or q.name in excluded or q.suffix.lower()in['.mp4','.mkv','.mov','.webm']:continue
 if q.suffix.lower()=='.zip'and q!=bundle:continue
 files.append((q,'changed-outlook-voice/'+str(q.relative_to(O))))
files.extend([(arcpath,'actual-revised-native/native_input_archive.json'),(S,'actual-revised-native/current-spec.json')])
for n in ['render_inputs.json','qc_attestation.json','subtitles.ass','topbar.ass','render.json']:files.append((D/n,'actual-revised-native/'+('post-upload-render.json'if n=='render.json'else n)))
entries=[{'path':n,'sha256':sha(q),'bytes':q.stat().st_size}for q,n in files];wr('archive-entry-manifest.json',entries)
with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for q,n in files:z.write(q,n)
 z.write(O/'archive-entry-manifest.json','changed-outlook-voice/archive-entry-manifest.json')
with zipfile.ZipFile(a.output)as z:
 assert z.testzip()is None
 for t in entries:assert hashlib.sha256(z.read(t['path'])).hexdigest()==t['sha256']
assert sha(film)==fh and sha(S)==binding['spec_sha256'];manifest={'created_at':now(),'status':'lightweight_revised_outlook_voice_evidence_bound_actual_native_movie','local_archive':str(a.output.resolve()),'sha256':sha(a.output),'bytes':a.output.stat().st_size,'entry_count':len(entries)+1,'new_bundle_sha256':rep['new_bundle_sha256'],'bundle_bytes':rep['new_bundle_bytes'],'film_sha256':fh,'run_id':a.run_id,'spec_sha256':sha(S),'native_input_archive_sha256':sha(arcpath),'actual_native_voice_requests':6,'old_exact_reused_requests':5,'newly_reviewed_requests':1,'new_current_calibrated_low_positions':29,'new_current_direct_low_positions':3,'raw_mechanical_pending_retained':3,'old_control_archive_embedded':False,'old_review_archive_sha256':'62e251159d925a0d1aae0dbbaab84eb29e78acb9606fba88166499fcfea6f2a7','old_review_archive_bytes':17470976,'old_review_archive_url':rd('unchanged-five-review-reuse.json')['reused_whole_requests'][0]['prior_archive_url'],'human_listening_claimed':False,'all_phonetic_or_all_tone_pass_claimed':False,'no_loudness_PCM_gain_silence_operations':True,'publication_upload_pending':True};wr('external-artifact-manifest.json',manifest);sync();print(json.dumps(manifest,ensure_ascii=False))
