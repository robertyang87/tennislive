"""vibetennis 第 7 集时间轴：按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
生成 r3d/timeline.json 和 r3d/shots.js（每段的起止秒、镜头类型、每句开口时刻、画面事件时刻）。

    python3 plan.py

音画同步：画面里的关键动作不写死秒数，而是钉在旁白上（EV）——比如「纳什均衡」四个字念出来那一刻标题砸进来，
念到「可看得分率」时天平的光柱才开始升。scene.js 读 sec.ev（相对本段开头的秒数）。
规则：同一段句间留 GAP；换段留 SEC_GAP；HOLD 给某句最短停留（从这句开口算到下一句开口）；MIN_SEC 给整段最短时长。
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
GAP, SEC_GAP, LEAD = 0.35, 0.9, 0.3
SECTIONS = [  # (段名, 镜头类型)；句子按 narration.json 里的 sec 归段
    ("hook", "hook"), ("fast", "arena"), ("pile", "pile"), ("theory", "theory"), ("mix", "balance"),
    ("today", "rain"), ("keypts", "keypoints"), ("latest", "latest"), ("end", "coin")]
HOLD = {"f2": 3.0, "p0": 2.6, "p1": 3.4, "p2": 6.5,          # 「总发外角」要让 6 个发球打完
        "t2": 5.6, "t4": 5.5, "t7": 3.4, "t8": 5.5,                     # 年份环、石头剪刀布两局、螺旋收进均衡点
        "b2": 3.2, "b3": 6.0, "r2": 4.6, "r4": 4.2, "k1": 4.0, "k2": 4.0, "k3": 4.2, "k4": 4.6, "l2": 5.0, "l3": 3.6, "e0": 4.4}
MIN_SEC = {"hook": 9.5, "fast": 9.0, "pile": 14.0, "theory": 34.0, "mix": 17.0, "today": 22.0, "keypts": 22.0, "latest": 15.0, "end": 11.0}
# 画面事件：(段, 事件名, 句子, 句内第几个字开始) —— 取这个字在 TTS 词边界里的开口时刻
EV = [("hook", "slam", "h1", "纳什均衡"), ("hook", "eq", "h1", "诺贝尔"), ("theory", "hands", "t3", None), ("theory", "matrix", "t5", None),
      ("theory", "conv", "t7", None), ("mix", "rise", "b3", None), ("mix", "pour", "b1", None), ("today", "cols", "r2", None), ("today", "tiles", "r3", None),
      ("today", "red", "r4", "只有"), ("keypts", "row0", "k1", None), ("keypts", "row1", "k2", None), ("latest", "res", "l2", None), ("end", "line", "e0", None), ("end", "q", "e1", None)]

d = json.load(open("narration.json")); byf = {l["file"]: l for l in d["lines"]}
def wb(f): return json.load(open(f"voice/{f}.json"))
def speech(f): w = wb(f); return w[0]["off"], w[-1]["off"] + w[-1]["dur"]
def char_time(f, s):  # 句内某几个字的开口时刻（相对这句音频开头）
    w = wb(f); txt = "".join(x["text"] for x in w); i = txt.find(s)
    if i < 0: raise SystemExit(f"{f} 的词边界里找不到「{s}」：{txt}")
    c = 0
    for x in w:
        if c + len(x["text"]) > i: return x["off"]
        c += len(x["text"])
t = LEAD; secs = []
for name, kind in SECTIONS:
    lines = [l["file"] for l in d["lines"] if l["sec"] == name]
    s0 = 0 if name == "hook" else t - 0.4
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
json.dump(d, open("narration.json", "w"), ensure_ascii=False, indent=1)
tl = {"total": TOTAL, "sections": secs}
json.dump(tl, open("r3d/timeline.json", "w"), ensure_ascii=False, indent=1)
open("r3d/shots.js", "w").write("// 由 plan.py 生成，别手改\nexport const TL=" + json.dumps(tl, ensure_ascii=False) + ";\nexport const TOTAL=TL.total;\n")
for s in secs: print(f'{s["name"]:7s} {s["kind"]:10s} {s["t0"]:7.2f} → {s["t1"]:7.2f}  ({s["t1"]-s["t0"]:5.1f}s)  ev={s["ev"]}')
print("TOTAL", TOTAL)
