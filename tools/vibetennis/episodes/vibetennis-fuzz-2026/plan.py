"""vibetennis EP11 抽筋，多半不是缺盐：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
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
SECTIONS = [(n, n) for n in ("hook", "camps", "pickle", "brake", "stretch", "data", "salt", "back", "end")]
# 每句最短停留（从这句开口到下一句开口）：给这句的动效留够时间
HOLD = {"h0": 4.2, "h1": 4.2, "h2": 4.6, "h3": 6.6, "h4": 3.4,
        "c0": 3.0, "c1": 4.4, "c2": 4.4,
        "p0": 8.4, "p1": 8.0, "p2": 7.4, "p3": 6.8,
        "b0": 3.6, "b1": 6.4, "b2": 6.4, "b3": 6.4, "b4": 6.8,
        "s0": 3.6, "s1": 6.8,
        "d0": 2.4, "d1": 5.6, "d2": 6.4, "d3": 4.8, "d4": 5.2, "d5": 7.0,
        "x0": 2.8, "x1": 9.4, "x2": 3.6, "x3": 5.6,
        "k0": 7.4, "k1": 4.0, "k2": 6.6,
        "n0": 5.0, "n1": 6.6, "n2": 5.0}
MIN_SEC = {}
EV = [("hook", "sinner", "h0", None), ("hook", "fall", "h0", "抽筋"), ("hook", "crowd", "h1", None), ("hook", "salt", "h1", "缺盐"),
      ("hook", "drop", "h2", "腌黄瓜汁"), ("hook", "clock", "h3", "不抽了"), ("hook", "stomach", "h3", "胃里"), ("hook", "q", "h4", None),
      ("camps", "split", "c0", None), ("camps", "wat", "c1", "水和盐"), ("camps", "nerve", "c2", "神经"),
      ("pickle", "lab", "p0", None), ("pickle", "zap", "p0", "电刺激"), ("pickle", "cramp", "p0", "脚底"), ("pickle", "water", "p1", "喝水"),
      ("pickle", "pj", "p1", "喝腌黄瓜汁"), ("pickle", "gut", "p2", None), ("pickle", "flat", "p2", "血液"), ("pickle", "reflex", "p3", "神经反射"),
      ("brake", "dive", "b0", None), ("brake", "spindle", "b1", "肌梭"), ("brake", "gas", "b1", "油门"), ("brake", "gto", "b2", "高尔基"),
      ("brake", "brk", "b2", "刹车"), ("brake", "tired", "b3", "肌肉累了"), ("brake", "storm", "b4", "一直放电"), ("brake", "lock", "b4", "锁死"),
      ("stretch", "go", "s0", None), ("stretch", "flex", "s1", "勾回来"), ("stretch", "relief", "s1", "压住"),
      ("data", "q", "d0", None), ("data", "crowd", "d1", None), ("data", "same", "d2", None), ("data", "fast", "d3", "成绩更快"),
      ("data", "dehyd", "d4", None), ("data", "banana", "d5", "香蕉"),
      ("salt", "turn", "x0", None), ("salt", "kid", "x1", "网球选手"), ("salt", "sweat", "x1", "每小时出汗"), ("salt", "loss", "x1", "汗里丢的钠"),
      ("salt", "fixed", "x2", None), ("salt", "humid", "x3", None),
      ("back", "rg", "k0", "法网"), ("back", "cramp", "k0", "全身抽筋"), ("back", "tension", "k1", "紧张"), ("back", "sh", "k2", None), ("back", "both", "k2", "两样"),
      ("end", "n0", "n0", None), ("end", "p1", "n1", "拉伸"), ("end", "p2", "n1", "补盐"), ("end", "q", "n2", None)]
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
