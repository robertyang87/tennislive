import hashlib,json,sys,shutil,datetime,os,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'src')]
import measure_polyphone as mp
job=json.loads(Path(sys.argv[1]).read_text());i=int(sys.argv[2]);t=job['targets'][i];b=t['actual_binding'];orig_synth=mp.synth
def bound(text,voice,rate,pitch='+0Hz'):
 if text==t['sentence'] and voice==b['voice'] and rate==b['rate'] and pitch==b['pitch']:
  p=Path(b['bound_snapshot_path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==b['actual_mp3_sha256'];return p,json.loads(Path(b['marks_snapshot_path']).read_text())
 # Same reference utterance can recur in parallel targets. Hold a per-key
 # process lock until BOTH MP3 and WordBoundary cache members are committed.
 key=hashlib.sha256("\x1f".join([text,voice,rate,pitch]).encode()).hexdigest()[:24]
 lockdir=Path(job['output_dir']).parent/'reference-locks';lockdir.mkdir(exist_ok=True)
 with (lockdir/(key+'.lock')).open('a')as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  return orig_synth(text,voice,rate,pitch)
mp.synth=bound
try:t['acoustic']=mp.measure(t['word'],t['sentence'],t['ok_refs'],t['bad_refs'],b['voice'],b['rate'],char=t['char'],at=t['at'])
except Exception as e:t['acoustic']={'verdict':'error','why':f'{type(e).__name__}: {e}'}
Path(job['output_dir']).mkdir(exist_ok=True,parents=True)
controls=[]
for label,source in t['acoustic'].get('audio',{}).items():
 source=Path(source); destination=Path(job['output_dir']).parent/'reference-audio'/source.name; destination.parent.mkdir(exist_ok=True)
 if not destination.exists():shutil.copy2(source,destination)
 sidecar=source.with_suffix('.json')
 marks_destination=destination.with_suffix('.marks.json')
 if label=='ORIG':marks_destination.write_bytes(Path(b['marks_snapshot_path']).read_bytes())
 elif sidecar.exists():shutil.copy2(sidecar,marks_destination)
 controls.append({'label':label,'mp3_snapshot_path':str(destination),'mp3_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'marks_snapshot_path':str(marks_destination),'marks_sha256':hashlib.sha256(marks_destination.read_bytes()).hexdigest()if marks_destination.exists()else None})
t['control_audio_provenance']=controls
t['measured_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
Path(job['output_dir']).joinpath(f'target-{i:03}.json').write_text(json.dumps(t,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'target':i,'label':t['label'],'char':t['char'],'reading':t['intended'],'wrong':t['wrong'],'verdict':t['acoustic']['verdict'],'confidence':t['acoustic'].get('confidence'),'score':t['acoustic'].get('score'),'near':t['acoustic'].get('near_identical_to')},ensure_ascii=False),flush=True)
