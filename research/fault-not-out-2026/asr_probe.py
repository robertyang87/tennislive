"""短窗口逐段探人声：faster-whisper medium.en，2 秒一窗、带提示词，专门找主裁/司线/电子司线的单词喊声。只打印，不入库。"""
import subprocess, sys, tempfile, os
from faster_whisper import WhisperModel
m = WhisperModel("medium.en", device="cpu", compute_type="int8")
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) < 3: continue
    vid, a, b = p[0], float(p[1]), float(p[2])
    src = os.path.join(os.environ["RUNNER_TEMP"], vid + ".mp4")
    if not os.path.exists(src):
        subprocess.run(["curl","-sSLf","--retry","3","-o",src,f"https://github.com/robertyang87/tennislive/releases/download/source-{vid}/{vid}.mp4"],check=True)
    t = a
    while t < b:
        w = tempfile.mktemp(suffix=".wav")
        subprocess.run(["ffmpeg","-v","error","-y","-ss",str(t),"-t","2.5","-i",src,"-ac","1","-ar","16000",w],check=True)
        segs,_ = m.transcribe(w, language="en", vad_filter=False, beam_size=5, word_timestamps=True,
                              initial_prompt="Tennis umpire calls: Fault. Foot fault. Out. Let. Second serve.")
        txt = " ".join(f"{x.word.strip()}@{t+x.start:.2f}" for s in segs for x in (s.words or []))
        print(f"{vid} {t:7.2f} | {txt}", flush=True)
        t += 2.0
