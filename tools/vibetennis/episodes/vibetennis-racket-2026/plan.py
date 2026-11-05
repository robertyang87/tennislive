"""vibetennis 器材三部曲 ② 球拍的演变：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
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
SECTIONS = [("hook", "hook"), ("wood", "wood"), ("metal", "metal"), ("oversize", "oversize"), ("sweet", "sweet"),
            ("twist", "twist"), ("carbon", "carbon"), ("rules", "rules"), ("style", "style"), ("end", "end")]
# 每句最短停留（从这句开口到下一句开口）：给 motion.md 里这句的动效留够时间
HOLD = {"h0": 4.6, "h1": 4.6, "h2": 4.2, "h3": 3.6, "w0": 6.0, "w1": 4.6, "w2": 4.2, "w3": 5.0, "m0": 6.8, "m1": 7.4, "m2": 5.2,
        "m3": 4.0, "m4": 3.6, "o0": 4.0, "o1": 4.8, "o2": 4.2, "o3": 7.2, "o4": 4.2, "s0": 4.0, "s1": 9.5, "s2": 3.6, "s3": 4.8,
        "t0": 7.4, "t1": 5.4, "t2": 5.8, "t3": 3.4, "c0": 5.4, "c1": 4.4, "c2": 5.8, "c3": 9.6, "c4": 6.6, "c5": 5.6,
        "r0": 4.6, "r1": 8.2, "y0": 5.8, "y1": 5.0, "y2": 5.0, "y3": 6.4, "e0": 5.4, "e1": 5.6, "e2": 3.4}
MIN_SEC = {"hook": 18.0, "wood": 18.0, "metal": 24.0, "oversize": 22.0, "sweet": 20.0, "twist": 20.0, "carbon": 34.0,
           "rules": 12.0, "style": 20.0, "end": 12.0}
# 画面事件钉在旁白上：某句开口、或这句里某几个字开口那一刻（motion.md 逐句表）
EV = [("hook", "hit", "h0", None), ("hook", "fly", "h1", "球的左右"), ("hook", "row", "h2", None), ("hook", "q", "h3", None),
      ("wood", "lt", "w0", None), ("wood", "bend", "w0", "弯出来"), ("wood", "years", "w1", None), ("wood", "scan", "w2", "约"),
      ("wood", "crack", "w3", "妥协"), ("metal", "hole", "m0", "孔边"), ("metal", "patent", "m1", None), ("metal", "lift", "m1", "两道梁"),
      ("metal", "join", "m2", None), ("metal", "alu", "m3", "三格"), ("metal", "same", "m4", "还是"),
      ("oversize", "patent", "o0", None), ("oversize", "cop", "o1", "不震手"), ("oversize", "hits", "o2", "拍面正中"),
      ("oversize", "stretch", "o3", "拉长"), ("oversize", "area", "o4", "四成"),
      ("sweet", "split", "s0", "三个点"), ("sweet", "p1", "s1", "回弹"), ("sweet", "p2", "s1", "振动最小"), ("sweet", "p3", "s1", "不震手"),
      ("sweet", "node", "s2", "节点"), ("sweet", "grip", "s3", None),
      ("twist", "split", "t0", None), ("twist", "hitboth", "t0", "打偏时"), ("twist", "speed", "t1", "明显变慢"), ("twist", "court", "t2", None),
      ("twist", "out", "t3", "飞长"), ("carbon", "scale", "c0", None), ("carbon", "y1980", "c1", None), ("carbon", "noah", "c2", None),
      ("carbon", "micro", "c3", None), ("carbon", "wave", "c3", "振动频率"), ("carbon", "heat", "c4", None), ("carbon", "serve", "c4", "发球"),
      ("carbon", "stack", "c5", "挥拍重量"), ("carbon", "grow", "c5", "挥速"), ("rules", "box", "r0", "定上限"), ("rules", "shrink", "r1", "29"),
      ("rules", "dims", "r1", "只管尺寸"), ("rules", "strike", "r1", "不管多重"), ("style", "quote", "y0", None), ("style", "power", "y0", "力量"),
      ("style", "sim", "y1", None), ("style", "real", "y2", None), ("style", "puzzle", "y3", None), ("end", "replay", "e0", "打偏的代价"),
      ("end", "glass", "e1", None), ("end", "ball", "e2", None)]
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
