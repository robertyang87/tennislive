"""vibetennis 器材三部曲 ③ 球：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
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
SECTIONS = [(n, n) for n in ("hook", "origin", "make", "color", "impact", "lab", "dial", "now", "future", "end")]
# 每句最短停留（从这句开口到下一句开口）：给这句的动效留够时间
HOLD = {"h0": 3.8, "h1": 6.4, "h2": 3.4, "h3": 4.0, "o0": 5.0, "o1": 4.0, "o2": 4.0, "o4": 4.2,
        "m0": 6.2, "m1": 4.2, "m2": 4.6, "m3": 5.2, "m4": 4.2, "m6": 6.0, "c1": 5.2, "c2": 4.4,
        "p0": 4.8, "p1": 5.4, "p2": 7.8, "p4": 6.2, "p6": 4.8, "r1": 7.6, "r2": 5.2, "r3": 4.4, "r4": 8.6,
        "d1": 4.4, "d2": 7.6, "d3": 7.8, "d5": 6.2, "d6": 5.2, "n1": 5.0, "n4": 6.4, "n5": 4.6,
        "f1": 4.8, "f3": 7.0, "f5": 5.6, "e0": 3.0, "e1": 3.8, "e2": 4.0, "e3": 6.0, "e4": 4.6}
MIN_SEC = {}
EV = [("hook", "spin", "h0", None), ("hook", "specs", "h1", "重量"), ("hook", "rk", "h2", None), ("hook", "q", "h3", None),
      ("origin", "leather", "o0", None), ("origin", "rubber", "o1", None), ("origin", "cloth", "o2", None), ("origin", "melton", "o3", None),
      ("origin", "hollow", "o4", None),
      ("make", "press", "m0", None), ("make", "heat", "m0", "150"), ("make", "join", "m1", None), ("make", "gas", "m1", "充进气"),
      ("make", "pr", "m2", None), ("make", "felt", "m3", None), ("make", "cross", "m3", "错开"), ("make", "steam", "m4", None),
      ("make", "pl", "m5", None), ("make", "sweater", "m6", "毛衣"),
      ("color", "wb", "c0", None), ("color", "tv", "c1", None), ("color", "yel", "c1", "黄色"), ("color", "wim", "c2", None),
      ("impact", "str", "p0", None), ("impact", "wall", "p1", None), ("impact", "squash", "p1", "压扁"), ("impact", "bub", "p2", "往里一翻"),
      ("impact", "air", "p3", None), ("impact", "serve", "p3", "一记发球"), ("impact", "fluff", "p4", None), ("impact", "bald", "p4", "磨秃"),
      ("impact", "cold", "p5", None), ("impact", "alt", "p6", None),
      ("lab", "lon", "r0", None), ("lab", "drop", "r1", None), ("lab", "half", "r1", "一半多"), ("lab", "press", "r2", None),
      ("lab", "wear", "r3", None), ("lab", "nine", "r4", None), ("lab", "wim", "r4", "温网"), ("lab", "two", "r5", "提前两局"),
      ("dial", "big", "d0", None), ("dial", "vote", "d1", None), ("dial", "types", "d2", None), ("dial", "t3", "d2", "3号球"),
      ("dial", "race", "d3", None), ("dial", "init", "d4", None), ("dial", "court", "d5", None), ("dial", "fire", "d5", "每秒"), ("dial", "knob", "d6", None),
      ("now", "complain", "n0", None), ("now", "q1", "n1", None), ("now", "q2", "n2", None), ("now", "weeks", "n3", None), ("now", "atp", "n4", None), ("now", "one", "n5", None),
      ("future", "pile", "f0", None), ("future", "fill", "f1", None), ("future", "none", "f2", None), ("future", "grind", "f3", None),
      ("future", "nest", "f3", "巢鼠"), ("future", "split", "f4", None), ("future", "two", "f5", None),
      ("end", "tri", "e0", None), ("end", "sr", "e1", None), ("end", "ball", "e2", None), ("end", "rule", "e3", None), ("end", "q", "e4", None)]
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
    # 合成文本里原样有这几个字就直接用；没有（数字改写成汉字等）才按字幕原文的字位去对
    key = s if (EST or s in byf[f]["tts"]) else byf[f]["tts"][byf[f]["text"].find(s):byf[f]["text"].find(s) + len(s)] if s in byf[f]["text"] else s
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
