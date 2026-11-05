"""vibetennis 器材三部曲 ① 拍线的演变：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
生成 r3d/timeline.json 和 r3d/shots.js（每段的起止秒、镜头类型、每句开口时刻、画面事件时刻）。

    python3 plan.py            # 有 voice/*.json 词边界就按实测排
    python3 plan.py --estimate # 配音还没合成时，按每秒 5.2 个字估（只给审片包用，正式渲染必须实测）

规则同 EP06：同一段句间留 GAP；换段留 SEC_GAP；HOLD 给某句最短停留（从这句开口算到下一句开口）；MIN_SEC 给整段最短时长。
画面事件（EV）钉在旁白上：某句开口、或这句里某几个字开口那一刻。BGM 卡点等选定曲子再做（sfx 阶段）。
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
EST = "--estimate" in sys.argv
GAP, SEC_GAP, LEAD = 0.35, 0.9, 0.3
SECTIONS = [("hook", "hook"), ("gut", "gut"), ("synth", "synth"), ("spaghetti", "spaghetti"), ("poly", "poly"),
            ("power", "power"), ("tension", "tension"), ("tactics", "tactics"), ("end", "end")]
HOLD = {"h0": 5.0, "h1": 4.5, "g1": 6.0, "g2": 3.5, "m0": 8.0, "m1": 6.0, "x0": 6.0, "x1": 6.5, "x3": 6.5, "p0": 4.5, "p1": 4.0, "p4": 5.0,
        "w0": 6.5, "t1": 6.0, "t2": 5.0, "t3": 5.5, "k0": 7.5, "k1": 4.5, "k2": 5.0, "k3": 5.0, "e0": 6.0}
MIN_SEC = {"hook": 14.0, "gut": 15.0, "synth": 22.0, "spaghetti": 26.0, "poly": 24.0, "power": 8.0, "tension": 22.0, "tactics": 24.0, "end": 10.0}
EV = [("hook", "drop", "h1", "发球上网"), ("hook", "q", "h2", None), ("gut", "hit", "g1", "球撞上"), ("gut", "cor", "g2", "恢复系数"),
      ("synth", "swap", "s1", "尼龙"), ("synth", "micro", "m0", None), ("synth", "mgut", "m0", "羊肠线"),
      ("synth", "mmulti", "m0", "多股线"), ("synth", "mmono", "m0", "单丝线"), ("synth", "notch", "m1", "交叉"), ("spaghetti", "patent", "x0", None), ("spaghetti", "slide", "x1", "线能滑开"), ("spaghetti", "ban", "x2", "国际网联"),
      ("spaghetti", "roll", "x3", None), ("poly", "y1997", "p0", None), ("poly", "y2010", "p1", None), ("poly", "pro", "p2", "有实验"),
      ("poly", "con", "p3", None), ("poly", "snap", "p4", "线能不能"), ("power", "bars", "w0", "实验室"), ("tension", "curve", "t1", None),
      ("tension", "fly", "t2", "磅数"), ("tension", "swap", "t3", None), ("tactics", "bars", "k0", "发球上网"), ("tactics", "band", "k1", None),
      ("tactics", "conf", "k2", None), ("tactics", "none", "k3", None), ("end", "q", "e1", None)]
CPS = 5.2  # 估算语速（字/秒），只给 --estimate 用
d = json.load(open("narration.json")); byf = {l["file"]: l for l in d["lines"]}
PUNCT = "，。：；？！、—"
def wb(f):
    if EST:  # 估：每个非标点字 1/CPS 秒，标点停 0.25 秒
        out, t = [], 0.08
        for ch in byf[f]["text"]:
            if ch in PUNCT: t += 0.25; continue
            out.append({"off": t, "dur": 1 / CPS, "text": ch}); t += 1 / CPS
        return out
    return [w for w in json.load(open(f"voice/{f}.json")) if w.get("type", "WordBoundary") == "WordBoundary"]
def speech(f): w = wb(f); return w[0]["off"], w[-1]["off"] + w[-1]["dur"]
def char_time(f, s):
    w = wb(f); txt = "".join(x["text"] for x in w)
    key = s if EST else byf[f]["tts"][byf[f]["text"].find(s):byf[f]["text"].find(s) + len(s)] if s in byf[f]["text"] else s
    i = txt.find(key)
    if i < 0: raise SystemExit(f"{f} 的词边界里找不到「{s}」：{txt}")
    c = 0
    for x in w:
        if c + len(x["text"]) > i: return x["off"]
        c += len(x["text"])
t = LEAD; secs = []
for name, kind in SECTIONS:
    lines = [l["file"] for l in d["lines"] if l["sec"] == name]
    s0 = 0 if name == "hook" else t - 0.4
    if name != "hook": t = s0 + 0.5
    for f in lines:
        a, b = speech(f); byf[f]["at"] = round(t - a, 3)
        t = t + max(b - a + GAP, HOLD.get(f, 0))
    t = max(t, s0 + MIN_SEC.get(name, 0)) + SEC_GAP - GAP
    secs.append({"name": name, "kind": kind, "t0": round(max(0, s0), 3), "t1": round(t - 0.4, 3), "lines": {f: byf[f]["at"] for f in lines}, "ev": {}})
for i in range(len(secs) - 1): secs[i]["t1"] = secs[i + 1]["t0"]
TOTAL = round(t + 1.5, 2); secs[-1]["t1"] = TOTAL
for sec, ev, f, word in EV:
    s = next(x for x in secs if x["name"] == sec)
    tt = byf[f]["at"] + (char_time(f, word) if word else speech(f)[0])
    s["ev"][ev] = round(tt - s["t0"], 3)
if not EST: json.dump(d, open("narration.json", "w"), ensure_ascii=False, indent=1)
tl = {"total": TOTAL, "estimate": EST, "sections": secs}
json.dump(tl, open("r3d/timeline.json", "w"), ensure_ascii=False, indent=1)
open("r3d/shots.js", "w").write("// 由 plan.py 生成，别手改\nexport const TL=" + json.dumps(tl, ensure_ascii=False) + ";\nexport const TOTAL=TL.total;\n")
for s in secs: print(f'{s["name"]:10s} {s["t0"]:7.2f} → {s["t1"]:7.2f}  ({s["t1"]-s["t0"]:5.1f}s)  ev={s["ev"]}')
print("TOTAL", TOTAL, "（估算）" if EST else "")
