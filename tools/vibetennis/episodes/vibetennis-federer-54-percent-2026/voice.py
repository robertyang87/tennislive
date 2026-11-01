"""vibetennis 第 4 集中文配音：TTS 人声轨与中文版混音（不加底部配音字幕：所有者 2026-11-01「不用再多加多余的字幕。就用画面上当前的一些文案」）。

账号所有者 2026-11-01：「中文版的加上中文的配音……就是有 TTS 的，跟 EP 三一样的」。声线与语速同 EP03
（edge-tts zh-CN-YunjianNeural +18%）；配音稿 narration.json（text 为字幕原文，tts 为合成文本，多音字换同音字）；
合成在 GitHub Actions runner 上做（会话沙箱连不上 speech.platform.bing.com），产物 voice/nNN.mp3 ＋ 词边界 voice/nNN.json。
混音同 EP03：人声 -16 LUFS、音效 -22、BGM -26，人声开口时 BGM 再压 8 dB（sidechain），整片之后归一到 -14 LUFS。

    python3 voice.py        # 先跑过 sfx.py（要 sfx/sfx_only.wav 与 sfx/bgm_bed.wav）
产物：voice/schedule.json（每句实际落位，留作核对）、sfx/sfx_bed_zh.wav（assemble 中文版用）
"""
import json, os, re, subprocess
import numpy as np, soundfile as sf
from scipy import signal
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
SR = 48000; GAP = 0.25; PUNCT = "，。：；？！、"
d = json.load(open("narration.json")); L = d["lines"]

def dec(p):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)

def lufs(x):
    tmp = "sfx/_m.wav"; sf.write(tmp, x.astype(np.float32), SR, subtype="FLOAT")
    e = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    os.remove(tmp); return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1])

def phrases(text, words, t0):
    """按标点切成 ≤16 字的短句；每句的起止时刻从 TTS 词边界按字位查"""
    marks = []; c = 0
    for w in words:
        n = len(w["text"]); marks.append((c, t0 + w["off"], t0 + w["off"] + w["dur"])); c += n
    def at(ci, end=False):
        best = marks[0]
        for m in marks:
            if m[0] <= ci: best = m
        return best[2] if end else best[1]
    body = [ch for ch in text if ch not in PUNCT]
    chunks, cur = [], ""
    for ch in text:
        cur += ch
        if ch in PUNCT and len(cur.strip(PUNCT)) >= 4: chunks.append(cur); cur = ""
    if cur.strip(PUNCT): chunks.append(cur)
    merged = []
    for ch in chunks:
        if merged and len((merged[-1] + ch).strip(PUNCT)) <= 16: merged[-1] += ch
        else: merged.append(ch)
    out, ci = [], 0
    for ch in merged:
        n = len([x for x in ch if x not in PUNCT]); out.append({"t0": round(at(ci), 3), "t1": round(at(ci + n - 1, True), 3), "text": ch.rstrip("，、：；")}); ci += n
    return out

sched, prev = [], 0.0
total = int(190 * SR); V = np.zeros((total, 2))
for i, l in enumerate(L):
    wb = [w for w in json.load(open(f"voice/n{i:02d}.json")) if w["type"] == "WordBoundary"]
    s0 = wb[0]["off"]; sp = wb[-1]["off"] + wb[-1]["dur"]
    start = max(l["at"], prev + GAP - s0); prev = start + sp
    a = dec(f"voice/n{i:02d}.mp3"); k = int(start * SR); V[k:k + len(a)] += a[:total - k]
    sched.append({"i": i, "start": round(start, 3), "speech_from": round(start + s0, 3), "speech_to": round(start + sp, 3), "late": round(start - l["at"], 3), "text": l["text"], "phrases": phrases(l["text"], wb, start)})
json.dump(sched, open("voice/schedule.json", "w"), ensure_ascii=False, indent=1)
print("late max %.2f s" % max(s["late"] for s in sched))

sfx = sf.read("sfx/sfx_only.wav")[0]; bgm = sf.read("sfx/bgm_bed.wav")[0]
n = min(len(sfx), len(bgm), total); V, sfx, bgm = V[:n], sfx[:n], bgm[:n]
V *= 10 ** ((-16 - lufs(V)) / 20); sfx *= 10 ** ((-22 - lufs(sfx)) / 20); bgm *= 10 ** ((-26 - lufs(bgm)) / 20)
# sidechain：人声包络（50 ms 起、300 ms 释放）→ BGM 最多再压 8 dB
env = np.abs(V).max(1); win = int(0.05 * SR); env = np.convolve(env, np.ones(win) / win, "same")
on = (env > 10 ** (-40 / 20)).astype(np.float64)
rel = signal.lfilter([1 - np.exp(-1 / (0.3 * SR))], [1, -np.exp(-1 / (0.3 * SR))], on)
duck = 10 ** (-8 * np.clip(np.maximum(on, rel), 0, 1) / 20)
mix = V + sfx + bgm * duck[:, None]
sf.write("sfx/sfx_bed_zh.wav", mix.astype(np.float32), SR, subtype="FLOAT")
print("voice/sfx/bgm LUFS:", round(lufs(V), 1), round(lufs(sfx), 1), round(lufs(bgm), 1), "mix", round(lufs(mix), 1))
