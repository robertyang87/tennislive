import sys,json
from pathlib import Path
sys.path.insert(0,'tools');sys.path.insert(0,'src')
import build_interview_request as b
s='sabalenka-noskova-usopen-2026-qf-oncourt'
p=Path('output/interviews')/s/'source.mp4'
b._download_audio=lambda url,workdir:p.resolve()
sys.argv=['build_interview_request.py','--slug',s,'--write']
raise SystemExit(b.main())
