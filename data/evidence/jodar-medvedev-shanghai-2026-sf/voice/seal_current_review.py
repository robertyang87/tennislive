"""Native byte identity binding only. Does not change finite review status or process audio."""
import argparse,json,hashlib,math,datetime,zipfile,shutil,sys
from pathlib import Path
O=Path(__file__).resolve().parent;R=Path('/workspace/tennislive-efficiency');SLUG='jodar-medvedev-shanghai-2026-sf';E=R/'data/evidence'/SLUG/'voice';S=R/'specs/reels'/f'{SLUG}.json'
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
  if p.name in ['reference-allowlist.json','reference-provenance.json','focused-reference-provenance.json','wei-reference-provenance.json','target-reference-dictionary.json']:continue
  if p.name=='root-direct-review.json'and(E/p.name).exists():continue
  (E/p.name).write_text(json.dumps(finite(json.loads(p.read_text())),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 for n in ['FINAL_REVIEW.md','seal_current_review.py']:shutil.copyfile(O/n,E/n)
def validate():
 B=rd('bindings.json');rep=rd('report.json');spec=json.loads(S.read_text());want={f'voice_{i:02d}.mp3':(x.get('_edit_id',f'segment_{i}'),x['narration'])for i,x in enumerate(spec['segments'])if str(x.get('narration')or'').strip()}
 if spec.get('outro',True):want['voice_outro.mp3']=('outro',NARRATION)
 assert set(want)=={b['output_name']for b in B};assert rep['human_listening_claimed']is False and rep['all_mechanical_components_passed']is False
 for b in B:
  eid,text=want[b['output_name']];assert eid==b['edit_id']and speakable(text)==b['tts_text'];assert sha(b['native_audio'])==b['audio_sha256']and sha(b['native_marks'])==b['marks_sha256']
  assert all(b['request'][k]==v for k,v in {'backend':'edge','voice':'zh-CN-YunjianNeural','rate':'+6%','pitch':'+0Hz','style':'','styledegree':''}.items())
 bundle=next(p for p in O.glob('input-bundle-*.zip')if sha(p)==rep['bundle_sha256']);assert bundle.stat().st_size==rep['bundle_bytes'];reuse=rd('brand-whole-request-review-reuse.json');assert reuse['complete_text_request_profile_MP3_marks_identical']and reuse['prior_archive_sha256']=='62e251159d925a0d1aae0dbbaab84eb29e78acb9606fba88166499fcfea6f2a7'
 assert len(rep['occurrences'])==89 and rep['body_calibrated_low_supported_positions']==77 and rep['body_direct_finite_low_supported_positions']==12 and rep['pending_count']==0
 for row in rd('direct-current-review.json')['occurrences']:
  for im in row['actually_viewed_images']:assert sha(im['path'])==im['sha256']
 root=E/'root-direct-review.json'
 assert root.exists(),'Independent root direct observation required for current bounded context assessment'
 if root.resolve()!=(O/root.name).resolve():shutil.copyfile(root,O/root.name)
 rr=rd('root-direct-review.json');assert rr['bundle_sha256']==rep['bundle_sha256']
 for im in rr['plots_actually_viewed']:assert sha(im['path'])==im['sha256']
 prov={**rd('reference-provenance.json'),**rd('focused-reference-provenance.json'),**rd('wei-reference-provenance.json')};assert len(prov)==56
 for ap,m in prov.items():assert sha(ap)==m['audio_sha256']and sha(Path(ap).with_suffix('.json'))==m['marks_sha256']
 return B,rep,bundle
p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');p.add_argument('--film',type=Path);p.add_argument('--run-id',type=int);p.add_argument('--native-archive',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();B,rep,bundle=validate()
if a.prepare_only:
 wr('seal-preparation.json',{'created_at':now(),'status':'finite_current5_review_waiting_actual_native_movie','bundle_sha256':rep['bundle_sha256'],'current_spec_sha256_provisional':sha(S),'actual_native_voice_requests':6,'newly_reviewed_requests':5,'exact_brand_reuse_requests':1,'pending_count':rep['pending_count'],'pending':rep['pending'],'old_brand_review_archive_cross_reference_only':True,'film_sha256':None,'final_archive_created':False,'human_listening_claimed':False});sync();print('PREPARED current6 identity; 77calibrated+12direct;12raw mechanical pending preserved; film binding pending');raise SystemExit()
assert all([a.film,a.run_id,a.native_archive,a.output]);assert not a.output.exists(),'Never overwrite sealed evidence';film=a.film.resolve();arcpath=a.native_archive.resolve();arc=json.loads(arcpath.read_text());fh=sha(film);assert arc['slug']==SLUG and arc['run_id']==a.run_id and arc['film_sha256']==fh;ids=[]
for b in B:
 fn=b['output_name'];mn=fn.replace('.mp3','.words.json');assert arc['files'][fn]==b['audio_sha256']and arc['files'][mn]==b['marks_sha256'];ids.append({'edit_id':b['edit_id'],'output_name':fn,'marks_name':mn,'audio_sha256':b['audio_sha256'],'marks_sha256':b['marks_sha256'],'matches_actual_native_archive':True,'newly_reviewed':b['edit_id']!='outro','old_exact_whole_request_review_reused':b['edit_id']=='outro'})
D=arcpath.parent
for n in ['render_inputs.json','qc_attestation.json','subtitles.ass','topbar.ass']:assert sha(D/n)==arc['files'][n]
qc=json.loads((D/'qc_attestation.json').read_text());ri=json.loads((D/'render_inputs.json').read_text());rm=json.loads((D/'render.json').read_text());assert qc['status']=='pass'and qc['film_sha256']==fh and qc['film_bytes']==film.stat().st_size and qc['spec_sha256']==sha(S)and qc['ass_sha256']==sha(D/'subtitles.ass')and qc['render_inputs_sha256']==sha(D/'render_inputs.json');assert ri['spec_sha256']==sha(S)and ri['film_sha256']==fh and ri['film_bytes']==film.stat().st_size
assert rm['film_sha256']==fh and rm['film_bytes']==film.stat().st_size and rm['tts_bundle']['bundle_sha256']==rep['bundle_sha256']and rm['tts_bundle']['request_count']==6 and rm['tts_bundle']['mode']=='strict_import'and rm['tts_bundle']['strict_reused']is True
note={'post_upload_render_metadata_sha256':sha(D/'render.json'),'native_captured_render_metadata_sha256':arc['files']['render.json'],'same_render_metadata_bytes':sha(D/'render.json')==arc['files']['render.json'],'scope':'Post-upload render metadata may add delivery fields; native QC/render_inputs/ASS exactly matched archive and actual film/bundle identities independently validated.'};wr('render-metadata-identity-note.json',note)
binding={'bound_at':now(),'status':'current_native_movie_exact_voice_inputs_bound_with_finite_limits_preserved','film_sha256':fh,'film_bytes':film.stat().st_size,'run_id':a.run_id,'bundle_sha256':rep['bundle_sha256'],'bundle_bytes':rep['bundle_bytes'],'spec_sha256':sha(S),'subtitles_ass_sha256':sha(D/'subtitles.ass'),'topbar_ass_sha256':sha(D/'topbar.ass'),'render_inputs_sha256':sha(D/'render_inputs.json'),'native_qc_sha256':sha(D/'qc_attestation.json'),'native_input_archive_sha256':sha(arcpath),'native_qc_status':qc['status'],'actual_native_voice_inputs':ids,'prior_brand_review_cross_reference':'brand-whole-request-review-reuse.json','prior_control_archive_embedded':False,'speech_reaudited_or_resynthesized_after_render':False,'human_listening_claimed':False,'full_phonetic_or_all_tone_pass_claimed':False,'pending_count':rep['pending_count'],'pending':rep['pending'],'metadata_identity_only_no_audio_processing':True,'post_upload_render_note':note};wr('final-film-input-binding.json',binding)
rep.update(final_movie_binding_pending=False,film_sha256=fh,film_bytes=film.stat().st_size,run_id=a.run_id,current_spec_sha256=sha(S),final_film_input_binding='final-film-input-binding.json');wr('report.json',rep);cap=rd('capsule-input-manifest.json');cap.update(final_movie_binding_pending=False,actual_film_sha256=fh,actual_run_id=a.run_id,current_spec_sha256=sha(S));wr('capsule-input-manifest.json',cap)
with(O/'FINAL_REVIEW.md').open('a')as f:f.write(f'\n电影声音输入字节绑定：film `{fh}`；run `{a.run_id}`；spec `{sha(S)}`。6组原MP3/marks精确匹配native manifest，不改写原机械12项pending及有限图读结论，不增加人听/全音素/视觉通过声明。\n')
files=[];excluded={'external-artifact-manifest.json','archive-entry-manifest.json'}
for q in sorted(O.rglob('*')):
 if not q.is_file()or'__pycache__'in q.parts or'native-cache'in q.parts or'native-check'in q.parts or q.name in excluded or q.suffix.lower()in['.mp4','.mkv','.mov','.webm']:continue
 if q.suffix.lower()=='.zip'and q!=bundle:continue
 files.append((q,'current-match-voice/'+str(q.relative_to(O))))
files.extend([(arcpath,'actual-native/native_input_archive.json'),(S,'actual-native/current-spec.json')])
for n in ['render_inputs.json','qc_attestation.json','subtitles.ass','topbar.ass','render.json']:files.append((D/n,'actual-native/'+('post-upload-render.json'if n=='render.json'else n)))
entries=[{'path':n,'sha256':sha(q),'bytes':q.stat().st_size}for q,n in files];wr('archive-entry-manifest.json',entries)
with zipfile.ZipFile(a.output,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for q,n in files:z.write(q,n)
 z.write(O/'archive-entry-manifest.json','current-match-voice/archive-entry-manifest.json')
with zipfile.ZipFile(a.output)as z:
 assert z.testzip()is None
 for t in entries:assert hashlib.sha256(z.read(t['path'])).hexdigest()==t['sha256']
assert sha(film)==fh and sha(S)==binding['spec_sha256'];manifest={'created_at':now(),'status':'current_match_voice_evidence_bound_actual_native_movie_finite_limits_preserved','local_archive':str(a.output.resolve()),'sha256':sha(a.output),'bytes':a.output.stat().st_size,'entry_count':len(entries)+1,'bundle_sha256':rep['bundle_sha256'],'bundle_bytes':rep['bundle_bytes'],'film_sha256':fh,'run_id':a.run_id,'spec_sha256':sha(S),'native_input_archive_sha256':sha(arcpath),'actual_native_voice_requests':6,'exact_brand_reused_requests':1,'newly_reviewed_requests':5,'new_current_calibrated_low_positions':77,'new_current_direct_low_positions':12,'finite_pending_count':0,'pending':rep['pending'],'raw_mechanical_pending_retained':12,'old_control_archive_embedded':False,'old_review_archive_sha256':rd('brand-whole-request-review-reuse.json')['prior_archive_sha256'],'old_review_archive_bytes':17470976,'old_review_archive_url':rd('brand-whole-request-review-reuse.json')['prior_archive_url'],'human_listening_claimed':False,'full_phonetic_or_all_tone_pass_claimed':False,'no_loudness_PCM_gain_silence_operations':True,'publication_upload_pending':True};wr('external-artifact-manifest.json',manifest);sync();print(json.dumps(manifest,ensure_ascii=False))
