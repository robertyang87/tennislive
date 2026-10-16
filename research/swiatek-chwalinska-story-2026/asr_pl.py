"""临时：波兰语采访两档逐词转写（small / medium），格式同 tools/source_asr.py（合并前删除）。"""
import json, sys, hashlib, subprocess
from pathlib import Path
from faster_whisper import WhisperModel
src, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
sha = hashlib.sha256(Path(src).read_bytes()).hexdigest()
subprocess.run(["ffmpeg","-v","error","-y","-i",src,"-ac","1","-ar","16000","a.wav"],check=True)
m = WhisperModel(model, device="cpu", compute_type="int8")
segs, info = m.transcribe("a.wav", language="pl", word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
rows = []
for s in segs:
    rows.append({"start": round(s.start,2), "end": round(s.end,2), "text": s.text, "avg_logprob": s.avg_logprob, "no_speech_prob": s.no_speech_prob,
                 "words": [{"w": w.word, "s": round(w.start,2), "e": round(w.end,2), "p": round(w.probability,3)} for w in (s.words or [])]})
    print(f"{s.start:8.2f} {s.end:8.2f} {s.text.strip()}", flush=True)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"model": model, "language": "pl", "source_sha256": sha, "clip": None, "duration": info.duration, "segments": rows}, ensure_ascii=False, indent=1) + "\n")
