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
# 第 2 版（20 句）：旁白只讲结论，句间的留白给特效——HOLD 按每个镜头的动画需要的时长给（从这句开口算到下一句开口）
HOLD = {"h1": 5.5, "f0": 4.6, "f1": 4.6, "p0": 13.5,                    # p0：6 个外角发球打完（shotPile 每球 ≥2.2 s）
        "t1": 7.5, "t3": 8.0, "t5": 6.6, "t8": 6.8,                    # 年份环 ≥7 s；石头剪刀布两局各 ≥3.5 s；矩阵铺开 6 s 后螺旋才收
        "b0": 6.2, "b3": 8.0,                                          # 光点倒进托盘 5 s；光柱升起再停稳
        "r1": 7.0, "r2": 5.8, "r4": 7.5,                               # 光点暴雨落地 → 两根光柱 → 1,056 块方砖、56 块变红
        "k0": 6.6, "k3": 6.2, "l1": 5.6, "l2": 7.0, "e0": 5.0}
MIN_SEC = {"hook": 9.0, "fast": 9.0, "pile": 14.0, "theory": 29.0, "mix": 14.5, "today": 20.0, "keypts": 13.0, "latest": 13.0, "end": 10.0}
# 画面事件：(段, 事件名, 句子, 句内第几个字开始) —— 取这个字在 TTS 词边界里的开口时刻
EV = [("hook", "slam", "h1", "纳什均衡"), ("hook", "eq", "h1", "诺贝尔"), ("theory", "hands", "t3", None), ("theory", "matrix", "t5", None),
      ("theory", "conv", "t8", None), ("mix", "pour", "b0", None), ("mix", "rise", "b3", "两边"), ("today", "cols", "r2", None), ("today", "tiles", "r4", None),
      ("today", "red", "r4", "偏离"), ("keypts", "row0", "k0", "局点"), ("keypts", "row1", "k0", "破发点"), ("latest", "res", "l2", None), ("end", "line", "e0", None), ("end", "q", "e1", None)]

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
