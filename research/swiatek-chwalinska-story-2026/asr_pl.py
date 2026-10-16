"""临时：波兰语采访逐句转写（合并前删除）。"""
import sys
from faster_whisper import WhisperModel
m=WhisperModel(sys.argv[2],device="cpu",compute_type="int8")
segs,info=m.transcribe(sys.argv[1],language="pl",vad_filter=False)
for s in segs: print(f"{s.start:8.2f} {s.end:8.2f} {s.text.strip()}",flush=True)
