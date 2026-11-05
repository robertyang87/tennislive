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
SECTIONS = [("hook", "hook"), ("gut", "gut"), ("synth", "micro"), ("poly", "poly"), ("power", "power"), ("spin", "spin"),
            ("tension", "tension"), ("tactics", "tactics"), ("end", "end")]
# 2026-11-05 按所有者「逻辑混乱」重排：来历 → 三样（力量／旋转／磅数）逐样讲、理论当场讲完 → 打法补具体机制
HOLD = {"h0": 5.0, "h1": 4.5, "g1": 5.5, "m0": 8.0, "m1": 6.0, "p0": 7.0, "p1": 6.5, "w0": 8.0, "w1": 4.5, "w2": 6.5, "w3": 4.0, "w4": 3.5,
        "r1": 6.0, "r2": 7.0, "r3": 5.5, "x0": 8.5, "x2": 4.5, "p2": 8.5, "t1": 6.0, "t2": 5.0, "t3": 5.5,
        "k0": 7.5, "k1": 9.0, "k2": 9.0, "k3": 4.5, "k4": 6.5, "e0": 7.5}
MIN_SEC = {"hook": 14.0, "gut": 10.0, "synth": 16.0, "poly": 14.0, "power": 20.0, "spin": 30.0, "tension": 18.0, "tactics": 30.0, "end": 10.0}
EV = [("hook", "drop", "h1", "发球上网"), ("hook", "q", "h2", None),
      ("gut", "bad", "g1", None), ("gut", "swap", "g1", "尼龙"),
      ("synth", "mgut", "m0", "天然肠线"), ("synth", "mmulti", "m0", "多股线"), ("synth", "mmono", "m0", "单丝线"), ("synth", "notch", "m1", "交叉"),
      ("poly", "y1997", "p0", None), ("poly", "y2010", "p0", "2010"), ("poly", "three", "p1", None), ("poly", "tp", "p1", "力量"), ("poly", "tr", "p1", "旋转"), ("poly", "tm", "p1", "磅数"),
      ("power", "hit", "w0", "球撞上"), ("power", "cor", "w0", "恢复系数"), ("power", "big", "w1", None), ("power", "lab", "w2", None), ("power", "loose", "w3", None), ("power", "nofast", "w4", None),
      ("spin", "roll", "r2", "滚起来"), ("spin", "nomore", "r2", "摩擦再大"), ("spin", "snap", "r3", None), ("spin", "patent", "x0", None), ("spin", "slide", "x0", "线能滑开"),
      ("spin", "ban", "x2", None), ("spin", "pro", "p2", "零售商"), ("spin", "con", "p2", "同行"),
      ("tension", "curve", "t1", "线一拉紧"), ("tension", "fly", "t2", None), ("tension", "swap", "t3", "所以"),
      ("tactics", "bars", "k0", "发球上网"), ("tactics", "mech", "k1", None), ("tactics", "dip", "k1", "往下坠"), ("tactics", "pass", "k1", "穿越球"),
      ("tactics", "win", "k2", "2010"), ("tactics", "cred", "k3", None), ("tactics", "conf", "k4", None), ("tactics", "none", "k4", "至今"),
      ("end", "q", "e1", None)]
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
