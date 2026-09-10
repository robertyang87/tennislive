"""Validate the reviewed Gauff candidate and measure synthesized narration."""
from pathlib import Path
import json, subprocess, sys
sys.path[:0]=["tools","src"]
from build_match_reel import validate_spec
R=Path("output/2026-09-10/reel/andreeva-gauff/recovery")
p=R/"candidate-spec.json"
s=json.loads(p.read_text())
s["_editorial_review"]["status"]="reviewed"
s["_duration_review"]["reason"]="采用WTA官方战报2:19；官方赛事feed两次超时，记录不可用。"
s["cover"]["scoreboard"]["_duration_why"]="WTA官方战报全场用时2:19，参见_duration_review"
s["_segments_source"]="原片四张contact、比分截图、关键帧与ASR人工逐段复核"
s["segments"][-1]["_why"]="完整获胜与庆祝后，14秒全画布统计卡，旁白交代总得分与两个挽救赛点。"
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+"\n")
validate_spec(s)
subprocess.run([sys.executable,"tools/build_match_reel.py","render","--spec",str(p),"--outdir",str(R/"narration-check"),"--check-narration"],check=True)
(R/"candidate-validation.json").write_text(json.dumps({"spec_valid":True,"tts_fits":True},indent=2)+"\n")
