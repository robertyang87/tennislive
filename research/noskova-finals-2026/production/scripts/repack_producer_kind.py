from pathlib import Path
import sys,json,hashlib,zipfile,tempfile
P=Path('/workspace/tennislive-noskova');R=Path('/workspace/noskova-finals-production');sys.path.insert(0,str(P/'src'))
from tennislive.video.tts_bundle import BundleSession,read_bundle,validate_bundle
old=P/'assets/reel/noskova-finals-2026/frozen-tts.zip';new=R/'production/canonical-transport-verification/producer-corrected.zip';req=json.load(open(R/'production/tts-requests.json'));manifest,entries=read_bundle(old.read_bytes(),req);metadata=dict(manifest['metadata']);assert 'kind' not in metadata;metadata['kind']='reel_native_tts'
with tempfile.TemporaryDirectory()as temp:
 with BundleSession(output_path=new,expected_requests=req,metadata=metadata)as session:
  for occurrence in manifest['occurrences']:
   request,audio,marks,_,_=entries[occurrence['request_id']];p=Path(temp)/occurrence['output_name'];p.write_bytes(audio);session.capture(request,p,marks)
report=validate_bundle(new,req,decode_audio=True)
with zipfile.ZipFile(old)as a,zipfile.ZipFile(new)as b:
 assert set(a.namelist())==set(b.namelist());members=[]
 for name in a.namelist():
  if name=='manifest.json':continue
  assert a.read(name)==b.read(name),name;members.append({'member':name,'sha256':hashlib.sha256(a.read(name)).hexdigest()})
 am=json.loads(a.read('manifest.json'));bm=json.loads(b.read('manifest.json'));assert bm['metadata'].pop('kind')=='reel_native_tts';assert am==bm
proof={'old_bundle_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'new_bundle_sha256':hashlib.sha256(new.read_bytes()).hexdigest(),'old_bytes':old.stat().st_size,'new_bytes':new.stat().st_size,'request_count':report['request_count'],'metadata_added':{'kind':'reel_native_tts'},'all_other_manifest_values_identical':True,'all24audio_marks_members_byte_identical':members,'method':'NativeBundleSession capture of exact validated old12request audio/marks bytes; no TTS synthesis invoked. Nativevalidate_bundle decoding passed.'};(R/'production/canonical-transport-verification/repack-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in proof.items()if k!='all24audio_marks_members_byte_identical'},ensure_ascii=False))
