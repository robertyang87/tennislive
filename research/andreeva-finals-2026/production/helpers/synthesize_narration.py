from pathlib import Path
import sys,json,subprocess,hashlib
R=Path('/workspace/andreeva-finals-production');REPO=Path('/workspace/tennislive-andreeva');sys.path[:0]=[str(REPO/'tools'),str(REPO/'src')]
import build_match_reel as reel
from tennislive.video.tts_bundle import BundleSession,validate_bundle
import build_native_spec as own
s=own.build();idx=json.loads((R/'source-index.json').read_text());s['sources']={r['key']:r['canonical_url']for r in idx};reel.apply_tts_backend(s)
requests=reel.reel_tts_requests(s,'zh-CN-YunjianNeural','+6%','+0Hz');out=R/'production/narration';out.mkdir(exist_ok=True);bundle=out/'tts_bundle.zip';evidence=[]
(out/'expected-requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n')
with BundleSession(output_path=bundle,expected_requests=requests,metadata={'slug':own.SLUG,'kind':'reel_native_tts','stage':'bounded actual complete narration inputs only; not film QC'})as session:
 for i,r in enumerate(requests):
  p=out/f'voice_{i:02d}.mp3';marks=reel.tts_one(r['text'],p,r['voice'],r['rate'],r['pitch'],r['style'],r['styledegree'],r['lead_pause'])
  dur=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(p)]));spoken=max((m['offset']+m['duration'])/1e7 for m in marks);row={'request':r,'path':str(p),'duration':dur,'word_end':spoken,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};evidence.append(row);print(i,len(r['text']),round(dur,3),round(spoken,3),r['text'],flush=True)
report=validate_bundle(bundle,requests);(out/'bundle-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');(out/'actual-durations.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n');print('Actual frozen',len(evidence),report['bundle_sha256'],flush=True)
