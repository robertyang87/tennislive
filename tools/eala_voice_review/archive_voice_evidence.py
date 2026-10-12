import hashlib,json,sys,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2];D=Path(__import__('os').environ['EALA_VOICE_REVIEW_DIR']);slug='eala-shi';E=R/'data/evidence'/slug/'voice'
seal=json.loads((E/'final-audio-review-manifest.json').read_text());assert seal['all_mixed_waveforms_strong_match']and seal['all_production_word_marks_exact_native_cache']
asset=Path(sys.argv[1])if len(sys.argv)>1 else D/f'{slug}-voice-evidence.zip';asset.parent.mkdir(parents=True,exist_ok=True);manifest_path=E/'voice-evidence-archive-manifest.json';members=[]
with zipfile.ZipFile(asset,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
 for p in sorted(E.rglob('*')):
  if not p.is_file()or p==manifest_path:continue
  relative=p.relative_to(E);data=p.read_bytes();z.writestr(str(relative),data);members.append({'member':str(relative),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
tag='reel-'+slug;url=f'https://github.com/robertyang87/tennislive/releases/download/{tag}/{asset.name}'
record={'schema':'tennislive.actual-voice-evidence-archive.v1','slug':slug,'status':'archive_prepared_pending_remote_upload','asset_path':str(asset),'asset_name':asset.name,'asset_sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'asset_bytes':asset.stat().st_size,'intended_release_tag':tag,'intended_remote_url':url,'remote_url_verified':False,'final_film_sha256':seal['film_sha256'],'spec_sha256':seal['spec_sha256'],'actual_current_voice_count':seal['actual_voice_count'],'final_finite_control_count':seal['pronunciation_comparison_count'],'unresolved_occurrences':seal['unresolved_occurrences'],'pronunciation_release_pass_claimed':False,'human_listening_claimed':False,'asr_used_to_prove_tones':False,'members':members,'method':'Exact current native MP3/paired ZIP, fresh reference MP3+marks, all finite calibration raw records and diagnostic limits, full-film PCM hash and QC identities. Nonfinal current-episode raw history explicitly separated and never promoted to current pronunciation pass. Archive excludes its own manifest to avoid circular identity.'}
manifest_path.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:record[k]for k in ['status','asset_path','asset_sha256','asset_bytes','intended_release_tag','intended_remote_url']},ensure_ascii=False,indent=2))
