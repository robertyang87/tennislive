"""Dynamic metadata seal; --prepare-only never creates a final archive or film hash.

No synthesis, audio processing, workflow or commit. Source/movie media are excluded.
"""
import argparse,copy,datetime,hashlib,json,shutil,sys,zipfile
from pathlib import Path

O=Path(__file__).resolve().parent
R=Path('/workspace/tennislive-efficiency')
SLUG='swiatek-li-wuhan-2026-qf'
D=R/'data/evidence'/SLUG/'pronunciation'
S=R/'specs/reels'/f'{SLUG}.json'
sys.path[:0]=[str(R/'src'),str(R/'tools')]
from tennislive.video.explainer import speakable
from tennislive.video.outro_page import NARRATION

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def read(n):return json.loads((O/n).read_text())
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2))
def stamp():return datetime.datetime.now(datetime.UTC).isoformat()
def strings(x):
    if isinstance(x,str):yield x
    elif isinstance(x,dict):
        for v in x.values():yield from strings(v)
    elif isinstance(x,list):
        for v in x:yield from strings(v)
def outro_rows(x):
    if isinstance(x,dict):
        if x.get('edit_id')=='outro'or any(isinstance(x.get(k),dict)and x[k].get('edit_id')=='outro'for k in['job','target']):return[x]
        return[r for v in x.values()for r in outro_rows(v)]
    if isinstance(x,list):return[r for v in x for r in outro_rows(v)]
    return[]

def preserve_outro_dependencies():
    """Copy exact existing documents, then only the audio reached by outro rows."""
    reuse=read('outro-reuse-conditions.json');queue=[]
    for c in reuse['candidate_checks']:
        assert c['all_exact'];p=Path(c['review_path']);assert sha(p)==c['review_sha256'];queue.append(p)
        for row in c['prior_outro_occurrences']:
            for e in row['evidence']:
                p=Path(e['source']);assert sha(p)==e['source_sha256'];queue.append(p)
    # This unchanged raw outro case supplies the original paired audible controls;
    # an old history document retains its original relative link, not rewritten.
    queue.append(Path('/workspace/scratch/moon3-pronunciation/finite-card-evidence/outro.json'))
    copies={};missing=[]
    while queue:
        p=Path(queue.pop(0))
        if p in copies:continue
        if not p.is_file():missing.append(str(p));continue
        if p.suffix.lower()not in['.json','.mp3','.png']:continue
        h=sha(p);q=O/'reused-whole-outro-artifacts'/f'{h}{p.suffix.lower()}';q.parent.mkdir(exist_ok=True)
        if not q.exists():shutil.copyfile(p,q)
        assert sha(q)==h
        copies[p]={'original_path':str(p),'archive_relative_path':str(q.relative_to(O)),'sha256':h,'bytes':q.stat().st_size,'scope':'Prior whole-outro evidence only; other names/utterances in source documents do not transfer.'}
        if p.suffix.lower()=='.mp3':
            if p.with_suffix('.json').is_file():queue.append(p.with_suffix('.json'))
        elif p.suffix.lower()=='.json':
            try:data=json.loads(p.read_text())
            except (ValueError,UnicodeError):continue
            rows=outro_rows(data)
            for value in strings(rows):
                candidate=Path(value)
                if candidate.suffix.lower()not in['.json','.mp3','.png']:continue
                if candidate.is_absolute():
                    if candidate.is_file():queue.append(candidate)
                else:
                    # Resolve original relative paths without changing source bytes.
                    options=[p.parent/candidate,Path('/workspace/scratch/moon3-pronunciation')/candidate,Path('/workspace/scratch/moon3-pronunciation-qc')/candidate]
                    hit=next((v for v in options if v.is_file()),None)
                    if hit:queue.append(hit)
                    else:missing.append(str(p.parent/candidate))
    out={'copied_exact_existing_artifacts':list(copies.values()),'historical_unresolved_relative_links':sorted(set(missing)),'method':'Copy exact original documents and currently existing dependencies from outro rows only. Missing historical aliases are disclosed; no audio reconstructed.'}
    write('reused-whole-outro-artifact-map.json',out)
    return out

def validate_current():
    bs=read('bindings.json');report=read('report.json');coverage=read('coverage.json');spec=json.loads(S.read_text())
    wanted={s.get('_edit_id',f'segment_{i}'):(i,s['narration'])for i,s in enumerate(spec['segments'])if str(s.get('narration')or'').strip()}
    cover=spec.get('cover')or{}
    if isinstance(cover,dict)and str(cover.get('narration')or'').strip():wanted['cover']=('cover',cover['narration'])
    if spec.get('outro',True):wanted['outro']=('outro',NARRATION)
    assert set(wanted)=={b['edit_id']for b in bs}
    checks=[]
    for b in bs:
        ix,text=wanted[b['edit_id']]
        assert speakable(text)==b['tts_text']
        assert all(b['request'][k]==v for k,v in{'backend':'edge','voice':'zh-CN-YunjianNeural','rate':'+6%','pitch':'+0Hz','style':'','styledegree':''}.items())
        assert sha(b['native_audio'])==b['audio_sha256']and sha(b['native_marks'])==b['marks_sha256']
        checks.append({'edit_id':b['edit_id'],'current_segment_index':ix,'captured_output_name':b['output_name'],'request_id':b['request_id'],'audio_sha256':b['audio_sha256'],'marks_sha256':b['marks_sha256'],'full_text_exact':True})
    bundle=next((p for p in O.glob('input-bundle-*.zip')if sha(p)==report['bundle_sha256']),None);assert bundle
    assert all(b['bundle_sha256']==report['bundle_sha256']for b in bs)
    refs=read('finite-references.json');provenance=read('reference-provenance.json');control_paths={ap for c in refs for k,ap in c['audio'].items()if k!='ORIG'}
    controls=[]
    for ap in sorted(control_paths):
        p=Path(ap);meta=provenance[ap];jp=p.with_suffix('.json')
        assert sha(p)==meta['audio_sha256']and sha(jp)==meta['marks_sha256']
        controls.append({'native_reference_path':str(p),'archive_audio_path':str(p.relative_to(O)),'archive_marks_path':str(jp.relative_to(O)),'audio_sha256':meta['audio_sha256'],'marks_sha256':meta['marks_sha256'],'tts_text':meta['tts_text'],'voice':meta['voice'],'rate':meta['rate'],'pitch':meta['pitch']})
    direct=[]
    for name in report.get('direct_review_files',['root-direct-review-archived.json','agent-direct-review.json']):
        doc=read(name)
        for row in doc['occurrences']:
            assert row['actual_audio_sha256']==next(b['audio_sha256']for b in bs if b['edit_id']==row['edit_id'])
            for im in row['actually_viewed_images']:assert sha(im['path'])==im['sha256']
            direct.append((row['edit_id'],row['index']))
    assert len(set(direct))==len(direct)
    body=[o for o in report['occurrences']if o['edit_id']!='outro'];outro=[o for o in report['occurrences']if o['edit_id']=='outro']
    counts={'voice_requests':len(bs),'actual_mp3_files':len(bs),'actual_native_marks_files':len(bs),'body_positions':len(body),'exact_whole_outro_positions':len(outro),'current_target_positions':len(report['occurrences']),'number_spans':sum(len(b['numbers'])for b in bs),'proper_name_syllable_positions':sum(len(n['targets'])for b in bs for n in b['proper_names']),'actual_current_reference_requests':len(control_paths),'original_mechanical_pending_positions':len(report['original_mechanical_pending_positions']),'direct_finite_interpretations':len(direct),'current_finite_pending_positions':sum(o['status']=='pending'for o in report['occurrences'])}
    assert counts['voice_requests']==len(coverage['utterances'])
    assert counts['original_mechanical_pending_positions']==counts['direct_finite_interpretations']==report['mechanical_pending_count']
    assert counts['current_finite_pending_positions']==report['pending_count']
    assert report['manual_listening_claimed']is False and report['all_mechanical_components_passed']is False
    write('all-current-control-byte-manifest.json',{'current_bundle_sha256':report['bundle_sha256'],'current_reference_count':len(controls),'controls':controls})
    return bs,report,counts,checks,bundle

def sync_metadata():
    D.mkdir(parents=True,exist_ok=True);copied=[];protected=[]
    # Root-owned source declarations and stable PNG remain untouched.
    for p in sorted(O.glob('*.json')):
        if p.name.startswith(('draft-','preparation','CURRENT_PREPARATION','static-editorial','prior-outro')):continue
        if p.name in['external-artifact-manifest.json']and not read('report.json').get('review_bundle_sealed'):continue
        dst=D/p.name
        if p.name in['root-direct-review.json','root-number-review.json']and dst.exists():protected.append(p.name);continue
        shutil.copyfile(p,dst);copied.append(p.name)
    for name in['FINAL_REVIEW.md','seal_native_review.py']:
        shutil.copyfile(O/name,D/name);copied.append(name)
    return {'copied_files':copied,'preserved_root_owned_files':protected,'destination':str(D)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--film',type=Path)
    parser.add_argument('--run-id',type=int)
    parser.add_argument('--native-archive',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--recovery-run-id',type=int)
    parser.add_argument('--recovery-provenance',type=Path)
    a=parser.parse_args()
    if bool(a.recovery_run_id) != bool(a.recovery_provenance): parser.error('Recovery metadata requires both --recovery-run-id and --recovery-provenance')
    if not a.prepare_only and not all([a.film,a.run_id,a.native_archive,a.output]):parser.error('Seal requires actual --film, --run-id, --native-archive and --output; no assumed film SHA.')
    bs,report,counts,checks,bundle=validate_current();reuse=preserve_outro_dependencies()
    if a.prepare_only:
        prep={'created_at':stamp(),'status':'prepared_waiting_actual_final_film_run_and_native_archive','bundle_sha256':report['bundle_sha256'],'observed_spec_sha256_provisional_not_final':sha(S),'dynamic_counts':counts,'voice_identity_checks':checks,'final_spec_sha256_will_be_read_at_seal':True,'film_sha256':None,'final_archive_created':False,'manual_listening_claimed':False,'all_mechanical_components_passed':False}
        write('seal-preparation.json',prep);synced=sync_metadata();write('metadata-sync.json',synced);print(json.dumps({'preparation':prep,'sync':synced},ensure_ascii=False));return
    # Seal actual final bytes only after the final file paths/run are supplied.
    film=a.film.resolve();arcpath=a.native_archive.resolve();assert film.is_file()and arcpath.is_file()
    arc=json.loads(arcpath.read_text());fh=sha(film);assert arc['film_sha256']==fh and arc['run_id']==a.run_id and arc['slug']==SLUG
    inputs=[]
    for b in bs:
        fn=b['output_name'];words=fn.replace('.mp3','.words.json')
        assert arc['files'][fn]==b['audio_sha256']and arc['files'][words]==b['marks_sha256']
        available={}
        for name,want in[(fn,b['audio_sha256']),(words,b['marks_sha256'])]:
            local=arcpath.parent/name;available[name]={'local_native_copy_present':local.is_file(),'local_copy_hash_verified':sha(local)==want if local.is_file()else None}
            if local.is_file():assert sha(local)==want
        inputs.append({'edit_id':b['edit_id'],'output_name':fn,'native_marks_name':words,'actual_mp3_sha256':b['audio_sha256'],'actual_marks_sha256':b['marks_sha256'],'both_match_final_native_archive_manifest':True,'optional_local_native_copies':available})
    binding={'metadata_bound_at':stamp(),'status':'all_dynamic_actual_mp3_and_marks_match_final_native_input_archive','bundle_sha256':report['bundle_sha256'],'film_path':str(film),'film_sha256':fh,'run_id':a.run_id,'native_input_archive_path':str(arcpath),'native_input_archive_sha256':sha(arcpath),'current_spec_path':str(S),'current_spec_sha256':sha(S),'current_full_request_texts_still_exact_match_frozen':True,'dynamic_counts':counts,'current_input_identities':inputs,'method':'bound_input_review_not_human_listening','manual_listening_claimed':False,'human_review_claimed':False,'whole_final_mix_listened':False,'all_mechanical_components_passed':False,'movie_or_source_media_in_evidence_archive':False}
    if a.recovery_run_id is not None:
        assert a.recovery_run_id != a.run_id and a.recovery_provenance.is_file()
        recovery=json.loads(a.recovery_provenance.read_text())
        assert recovery['original_run_id']==a.run_id and recovery['recovery_run_id']==a.recovery_run_id
        assert recovery['original_run_conclusion']=='failure' and recovery['actual_native_qc']=='pass'
        assert recovery['original_head_sha']==arc['head_sha'] and recovery['original_film_sha256']==fh
        assert recovery['original_film_bytes']==film.stat().st_size
        assert all(recovery[k]is True for k in ['same_spec_bytes','same_all_native_input_artifacts','same_original_render_inputs_bytes','same_movie_bytes_no_reencoding'])
        binding.update(native_origin_render_run_id=a.run_id,original_native_run_success_claimed=False,original_run_failure_preserved=True,separate_recovery_qc_run_id=a.recovery_run_id,recovery_provenance_path=str(a.recovery_provenance.resolve()),recovery_provenance_sha256=sha(a.recovery_provenance),recovery_provenance=recovery,same_existing_movie_and_input_bytes_not_reencoded=True)
    write('final-film-input-binding.json',binding)
    report.update(review_bundle_sealed=True,film_sha256=fh,run_id=a.run_id,current_spec_sha256=binding['current_spec_sha256'],final_film_input_binding=binding,current_final_film_binding_status='bound_actual_final_native_movie_same_frozen_voice')
    write('report.json',report);write('final-review.json',report)
    verify=read('verification.json');verify.update(current_spec_sha256=binding['current_spec_sha256'],review_bundle_sealed=True,final_film_input_binding='final-film-input-binding.json',final_film_sha256=fh);write('verification.json',verify)
    (O/'current-spec-verification-snapshot.json').write_bytes(S.read_bytes())
    with (O/'FINAL_REVIEW.md').open('a')as f:f.write(f'\n最终声音身份封印：film `{fh}`；run `{a.run_id}`；当前spec `{binding["current_spec_sha256"]}`。动态{counts["actual_mp3_files"]}份原MP3与{counts["actual_native_marks_files"]}份marks逐项匹配native archive。此为元数据绑定，不新增听审或机械通过声明。\n')
    if a.recovery_run_id is not None:
        with (O/'FINAL_REVIEW.md').open('a')as f:f.write(f'原 native run `{a.run_id}` 结论仍为 failure；独立 recovery QC run `{a.recovery_run_id}` 对同一原电影与输入完成实际 QC，未重编码。原失败及恢复 provenance 原文保留。\n')
    write('artifact-scope.json',{'bundle_sha256':report['bundle_sha256'],'film_sha256':fh,'spec_sha256':binding['current_spec_sha256'],'dynamic_counts':counts,'directory_map':{str(O):'pronunciation/'},'prior_outro_dependency_map':'pronunciation/reused-whole-outro-artifact-map.json','original_mechanical_pending_retained':True,'direct_AI_low_support_separate_from_mechanical':True,'no_source_or_movie_media':True,'manual_listening_claimed':False,'all_mechanical_components_passed':False})
    output=a.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    excluded={'external-artifact-manifest.json','metadata-sync.json','archive-entry-manifest.json'};video={'.mp4','.mkv','.mov','.webm','.avi','.m4v'}
    files=[]
    for p in sorted(O.rglob('*')):
        if not p.is_file()or p==output or '__pycache__'in p.parts or '.git'in p.parts or '.part.'in p.name:continue
        if p.name in excluded or p.suffix.lower()in video:continue
        if p.suffix.lower()=='.zip'and p!=bundle:continue
        files.append((p,'pronunciation/'+str(p.relative_to(O))))
    files.extend([(arcpath,'native-final-render/native_input_archive.json'),(S,'native-final-render/current-spec.json')])
    for name in ['render_inputs.json','qc_attestation.json']:
        p=arcpath.parent/name
        if p.is_file():
            assert sha(p)==arc['files'][name]
            files.append((p,'native-final-render/'+name))
    if a.recovery_provenance:files.append((a.recovery_provenance,'native-final-render/recovery_provenance.json'))
    for rel in['tools/measure_polyphone.py','tools/check_polyphones.py','src/tennislive/video/pronounce.py']:
        files.append((R/rel,'code-snapshot/'+rel))
    entry_manifest=[{'path':name,'sha256':sha(p),'bytes':p.stat().st_size}for p,name in files]
    write('archive-entry-manifest.json',entry_manifest)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6)as z:
        for p,name in files:z.write(p,name)
        z.write(O/'archive-entry-manifest.json','pronunciation/archive-entry-manifest.json')
    with zipfile.ZipFile(output)as z:
        assert z.testzip()is None
        for item in entry_manifest:assert hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256']
        assert not any(Path(n).suffix.lower()in video for n in z.namelist())
    manifest={'sealed_at':stamp(),'status':'finite_current_actual_voice_review_complete_low_support_bound_to_actual_native_movie','bundle_sha256':report['bundle_sha256'],'film_sha256':fh,'spec_sha256':binding['current_spec_sha256'],'run_id':a.run_id,'native_input_archive_sha256':sha(arcpath),'local_archive':str(output),'sha256':sha(output),'bytes':output.stat().st_size,'dynamic_counts':counts,'all_actual_controls_and_raw_failures_preserved':True,'original_mechanical_pending_preserved':counts['original_mechanical_pending_positions'],'direct_finite_low_support_separate':counts['direct_finite_interpretations'],'first_viewed_plot_bytes_preserved_without_overwrite':True,'manual_listening_claimed':False,'human_review_claimed':False,'whole_final_mix_listened':False,'all_mechanical_components_passed':False,'no_source_or_movie_media':True,'publication_upload_pending':True}
    if a.recovery_run_id is not None:manifest.update(native_origin_render_run_id=a.run_id,original_native_run_success_claimed=False,original_run_failure_preserved=True,separate_recovery_qc_run_id=a.recovery_run_id,recovery_provenance_sha256=sha(a.recovery_provenance),same_existing_movie_and_input_bytes_not_reencoded=True)
    assert sha(S)==binding['current_spec_sha256'] and sha(film)==fh, 'Final spec/movie changed during seal'
    write('external-artifact-manifest.json',manifest);sync_metadata();print(json.dumps(manifest,ensure_ascii=False))

if __name__=='__main__':main()
