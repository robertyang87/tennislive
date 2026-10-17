import sys
sys.path[:0]=['/workspace/tennislive/tools','/workspace/tennislive/src']
from pathlib import Path
import build_match_reel as r
from tennislive.video.tts_bundle import BundleSession
import preview_reel_captions as p
s=r.load_spec(Path('/workspace/tennislive/specs/reels/kartal-ostapenko-wuhan-2026-sf.json'));r.apply_tts_backend(s)
with BundleSession(input_path='/workspace/research-kartal/runner-tts/tts_bundle.zip',expected_requests=r.reel_tts_requests(s,'zh-CN-YunjianNeural','+6%','+0Hz')):
 sys.argv=['preview_reel_captions.py','--spec','/workspace/tennislive/specs/reels/kartal-ostapenko-wuhan-2026-sf.json','--source','main=/workspace/research-kartal/abL2j0xldOc.mp4','--outdir','/workspace/research-kartal/caption-preview-v4','--max-frames','10'];p.main()
