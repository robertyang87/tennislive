"""Safe final metadata seal. No synthesis, decoding, gain or PCM comparison."""
import argparse,json,hashlib,datetime,shutil,zipfile,sys,math
from pathlib import Path
O=Path(__file__).resolve().parent;R=Path('/workspace/tennislive-efficiency');SLUG='davidovich-zverev-shanghai-2026-sf';E=R/'data/evidence'/SLUG/'voice-agent';S=R/'specs/reels'/f'{SLUG}.json'
sys.path[:0]=[str(R/'src'),str(R/'tools')]
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(n):return json.loads((O/n).read_text())
def write(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def finite(x):
 if isinstance(x,float)and not math.isfinite(x):return None
 if isinstance(x,dict):return{k:finite(v)for k,v in x.items()}
 if isinstance(x,list):return[finite(v)for v in x]
 return x
def now():return datetime.datetime.now(datetime.UTC).isoformat()
def sync():
 E.mkdir(exist_ok=True,parents=True)
 for p in O.glob('*.json'):
  if p.name.startswith('prior-outro')or p.name in ['reference-allowlist.json','reference-provenance.json','focused-reference-provenance.json','target-reference-dictionary.json']:continue
  if p.name=='root-direct-review.json'and (E/p.name).exists():continue
  raw=p.read_text();data=json.loads(raw);clean=json.dumps(finite(data),ensure_ascii=False,indent=2,allow_nan=False)+'\n';(E/p.name).write_text(clean)
 for n in ['FINAL_REVIEW.md','seal_native_review.py']:shutil.copyfile(O/n,E/n)
def validate():
 B=read('bindings.json');rep=read('report.json');s=json.loads(S.read_text());wanted={f'voice_{i:02d}.mp3':(x.get('_edit_id',f'segment_{i}'),x['narration'])for i,x in enumerate(s['segments'])if str(x.get('narration')or'').strip()}
 if (s.get('cover')or{}).get('narration'):wanted['voice_cover.mp3']=('cover',s['cover']['narration'])
 if s.get('outro',True):wanted['voice_outro.mp3']=('outro',NARRATION)
 assert set(wanted)=={b['output_name']for b in B};checks=[]
 for b in B:
  eid,text=wanted[b['output_name']];assert eid==b['edit_id']and speakable(text)==b['tts_text']
  assert all(b['request'][k]==v for k,v in {'backend':'edge','voice':'zh-CN-YunjianNeural','rate':'+6%','pitch':'+0Hz','style':'','styledegree':''}.items())
  assert sha(b['native_audio'])==b['audio_sha256']and sha(b['native_marks'])==b['marks_sha256'];checks.append({'edit_id':eid,'output_name':b['output_name'],'request_id':b['request_id'],'audio_sha256':b['audio_sha256'],'marks_sha256':b['marks_sha256'],'current_text_and_profile_exact':True})
 bundle=next(p for p in O.glob('input-bundle-*.zip')if sha(p)==rep['bundle_sha256']);assert rep['pending_count']==0 and rep['manual_listening_claimed']is False and rep['all_mechanical_components_passed']is False
 root=E/'root-direct-review.json'
 if root.is_file():shutil.copyfile(root,O/root.name)
 for u in read('agent-direct-review.json')['occurrences']:
  for im in u['actually_viewed_images']:assert sha(im['path'])==im['sha256']
 for im in read('root-direct-review.json')['observations']:assert sha(im['plot'])==im['sha256']
 # Verify all 36 actual controls, including original-first failures and focused refs.
 manifests={**read('reference-provenance.json'),**read('focused-reference-provenance.json')};refs=[]
 for p,m in manifests.items():
  assert sha(p)==m['audio_sha256']and sha(Path(p).with_suffix('.json'))==m['marks_sha256'];refs.append({'audio':p,'audio_sha256':m['audio_sha256'],'marks_sha256':m['marks_sha256'],'text':m['tts_text'],'voice':m['voice'],'rate':m['rate'],'pitch':m['pitch']})
 assert len(refs)==36;write('all-current-control-byte-manifest.json',{'controls':refs,'current_control_count':len(refs),'bundle_sha256':rep['bundle_sha256']})
 return B,rep,checks,bundle
p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');p.add_argument('--film',type=Path);p.add_argument('--run-id',type=int);p.add_argument('--native-archive',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();B,rep,checks,bundle=validate()
if a.prepare_only:
 write('seal-preparation.json',{'created_at':now(),'status':'waiting_actual_final_movie_and_native_manifest','bundle_sha256':rep['bundle_sha256'],'current_spec_sha256_provisional':sha(S),'voice_identity_checks':checks,'film_sha256':None,'final_archive_created':False,'manual_listening_claimed':False});sync();print('PREPARED exact six actual MP3 and marks, 36 controls, finite current evidence; no assumed film SHA');raise SystemExit()
assert all([a.film,a.run_id,a.native_archive,a.output]),'Final seal needs actual film, run, native_input_archive and output path'
film=a.film.resolve();arcpath=a.native_archive.resolve();arc=json.loads(arcpath.read_text());fh=sha(film);assert arc['slug']==SLUG and arc['run_id']==a.run_id and arc['film_sha256']==fh;ident=[]
for b in B:
 fn=b['output_name'];words=fn.replace('.mp3','.words.json');assert arc['files'][fn]==b['audio_sha256']and arc['files'][words]==b['marks_sha256'];ident.append({'edit_id':b['edit_id'],'output_name':fn,'marks_name':words,'MP3_SHA256':b['audio_sha256'],'marks_SHA256':b['marks_sha256'],'both_match_actual_native_archive':True})
for name in ['render_inputs.json','qc_attestation.json','subtitles.ass','topbar.ass','spec.json']:
 q=arcpath.parent/name
 if q.is_file()and name in arc['files']:assert sha(q)==arc['files'][name]
qc=json.loads((arcpath.parent/'qc_attestation.json').read_text());ri=json.loads((arcpath.parent/'render_inputs.json').read_text());render=json.loads((arcpath.parent/'render.json').read_text());ash=sha(arcpath.parent/'subtitles.ass');sh=sha(S)
assert qc['status']=='pass'and qc['spec_sha256']==sh and qc['ass_sha256']==ash and qc['film_sha256']==fh and qc['film_bytes']==film.stat().st_size
assert qc['render_inputs_sha256']==sha(arcpath.parent/'render_inputs.json')
assert ri['spec_sha256']==sh and ri['film_sha256']==fh and ri['film_bytes']==film.stat().st_size and ri['artifacts']['subtitles.ass']==ash
assert render['film_sha256']==fh and render['film_bytes']==film.stat().st_size
assert render['tts_bundle']['bundle_sha256']==rep['bundle_sha256']and render['tts_bundle']['request_count']==6 and render['tts_bundle']['mode']=='strict_import'and render['tts_bundle']['strict_reused']is True
render_note={'current_render_metadata_sha256':sha(arcpath.parent/'render.json'),'native_archive_captured_render_sha256':arc['files']['render.json'],'current_matches_native_captured_render_bytes':sha(arcpath.parent/'render.json')==arc['files']['render.json'],'observation':'Current output render.json is post-upload metadata with added delivery and stage fields; exact original pre-upload render metadata bytes not supplied. Do not claim its byte identity. Native render_inputs, native QC, subtitles ASS and topbar ASS match archive exactly; current render metadata film and strict TTS bundle identities separately validated.','current_render_archive_name':'actual-native-render/post-upload-render.json'}
write('native-render-metadata-identity-note.json',render_note)
binding={'created_at':now(),'status':'six_actual_reviewed_MP3_and_marks_bound_to_final_native_movie','bundle_sha256':rep['bundle_sha256'],'film_sha256':fh,'film_path':str(film),'run_id':a.run_id,'native_input_archive_sha256':sha(arcpath),'current_spec_sha256':sha(S),'current_spec_path':str(S),'current_text_profile_exact_verified':True,'subtitles_ass_sha256':ash,'topbar_ass_sha256':sha(arcpath.parent/'topbar.ass'),'render_inputs_sha256':sha(arcpath.parent/'render_inputs.json'),'native_qc_sha256':sha(arcpath.parent/'qc_attestation.json'),'native_qc_status':qc['status'],'post_upload_render_metadata_identity':render_note,'render_metadata_sha256':sha(arcpath.parent/'render.json'),'native_strict_import_bundle':render['tts_bundle'],'inputs':ident,'human_listening_claimed':False,'final_mix_listened':False,'all_mechanical_components_passed':False,'method':'SHA and manifest metadata identity only; no decoding, PCM comparison or audio processing'}
if (O/'v2-rebind-preparation.json').is_file():
 rebind=read('v2-rebind-preparation.json');assert fh!=rebind['old_film_sha256'],'Visual-blocked historical movie cannot be sealed as v2 current movie'
 rebind.update(status='completed_new_native_movie_byte_binding_same_existing_voice_review',final_native_binding_status='bound_actual_v2_movie',new_film_sha256=fh,new_run_id=a.run_id,new_archive_path=str(a.output.resolve()),review_repeated=False,TTS_resynthesized=False)
 write('v2-rebind-preparation.json',rebind);binding['previous_movie_visual_blocked_history']=rebind
 rep['superseded_visual_blocked_movie']={'film_sha256':rebind['old_film_sha256'],'run_id':rebind['old_run_id'],'old_voice_archive_sha256':rebind['old_voice_archive_sha256'],'old_voice_archive_publishable':False,'old_movie_visual_QC_pass_claimed':False}
write('final-film-input-binding.json',binding);rep.update(review_bundle_sealed=True,film_sha256=fh,run_id=a.run_id,current_spec_sha256=sha(S),final_film_input_binding=binding);write('report.json',rep);write('final-review.json',rep)
v=read('verification.json');v.update(full_movie_binding_pending=False,film_sha256=fh,run_id=a.run_id,current_spec_sha256=sha(S),final_film_input_binding='final-film-input-binding.json');write('verification.json',v)
(O/'current-spec-verification-snapshot.json').write_bytes(S.read_bytes())
with (O/'FINAL_REVIEW.md').open('a')as f:f.write(f'\n最终影片声音输入身份已绑定：film `{fh}`；run `{a.run_id}`；当前 spec `{sha(S)}`。6 份实际 MP3 及 6 份 marks 与 native_input_archive 逐项 SHA 一致；仅元数据身份封印，不新增听审或机械通过结论。\n')
output=a.output.resolve();assert not output.exists(),'Never overwrite a sealed archive';files=[]
for q in sorted(O.rglob('*')):
 if not q.is_file()or '__pycache__'in q.parts or q.name in ['external-artifact-manifest.json','archive-entry-manifest.json']or q.suffix.lower()in ['.mp4','.mov','.mkv','.webm']:continue
 if q.suffix.lower()=='.zip'and q!=bundle:continue
 files.append((q,'voice-review/'+str(q.relative_to(O))))
files +=[(arcpath,'actual-native-render/native_input_archive.json'),(S,'actual-native-render/current-spec.json')]
for name in ['render_inputs.json','qc_attestation.json','render.json','subtitles.ass','topbar.ass']:
 q=arcpath.parent/name
 if q.is_file():files.append((q,'actual-native-render/'+('post-upload-render.json'if name=='render.json'else name)))
entries=[{'path':name,'sha256':sha(q),'bytes':q.stat().st_size}for q,name in files];write('archive-entry-manifest.json',entries)
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for q,name in files:z.write(q,name)
 z.write(O/'archive-entry-manifest.json','voice-review/archive-entry-manifest.json')
with zipfile.ZipFile(output)as z:
 assert z.testzip()is None
 for e in entries:assert hashlib.sha256(z.read(e['path'])).hexdigest()==e['sha256']
assert sha(film)==fh;manifest={'sealed_at':now(),'status':'finite_actual_voice_evidence_bound_to_final_native_movie','local_archive':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'entries':len(entries)+1,'film_sha256':fh,'run_id':a.run_id,'bundle_sha256':rep['bundle_sha256'],'spec_sha256':sha(S),'native_input_archive_sha256':sha(arcpath),'source_or_movie_media_included':False,'all_actual_MP3_marks_controls_and_plots_included':True,'raw_pending_and_failures_retained':True,'mechanical_pending_count':rep['mechanical_pending_count'],'finite_direct_count':rep['body_direct_finite_low_supported_positions'],'human_listening_claimed':False,'all_mechanical_components_passed':False,'full_phonetic_or_all_tone_pass_claimed':False,'publication_upload_pending':True}
write('external-artifact-manifest.json',manifest);sync();print(json.dumps(manifest,ensure_ascii=False))
