"""vibetennis EP13 网中间矮：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
生成 r3d/timeline.json 和 r3d/shots.js（每段起止秒、每句开口时刻、画面事件时刻）。

    python3 plan.py            # 按 voice/*.json 词边界实测排
    python3 plan.py --estimate # 配音没合成时按每秒 5.2 字估（只给审片包）

卡点（所有者：动画跟 BGM 节拍走，关键时刻落在强拍上）：BGM 用 /workspace/tennis_ep/bgm 的 first.wav（第 0 小节起）＋ loop.wav，
112.8 BPM、一拍 0.531943 s、一小节 2.12777 s。片头「悬链线」砸下来那一刻（title 段起点 HIT）＝ first.wav 第 8 小节线（满配器进来），
sfx.py 按 TL.beat.hit 反推 BGM 起点。之后每段起点往后对齐到拍点，画面事件（EV）对齐到最近的拍点（最多挪半拍）。
"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
EST = "--estimate" in sys.argv
GAP, SEC_GAP, LEAD = 0.35, 0.9, 0.3
BEAT = 2.127772 / 4
SECTIONS = [(n, n) for n in ("hook", "title", "strap", "hist", "diag", "margin", "sticks", "end")]
HOLD = {"h0": 4.5, "h1": 6.4, "h2": 5.9,
        "t0": 5.6, "t1": 4.6, "t2": 3.8,
        "s0": 8.4, "s1": 8.0, "s2": 7.0, "s3": 7.2, "s4": 9.6, "s5": 7.2,
        "y0": 7.8, "y1": 7.6, "y2": 6.8, "y3": 8.4, "y4": 6.8, "y5": 6.4, "y6": 4.8,
        "d0": 4.6, "d1": 8.4, "d2": 8.8, "d3": 7.2,
        "m0": 7.4, "m1": 6.6, "m2": 5.2, "m3": 6.4, "m4": 10.6, "m5": 8.6,
        "k0": 5.0, "k1": 8.6, "k2": 4.4,
        "n0": 2.6, "n1": 4.8, "n2": 6.5}
PRE_HIT = 1.0   # 钩子最后一句念完到 HIT 留的「静＋起势」
EV = [("hook", "dip", "h0", "塌下去"), ("hook", "post", "h1", "两端"), ("hook", "mid", "h1", "中间只有"), ("hook", "diff", "h1", "足足"), ("hook", "q", "h1", "$end"),
      ("hook", "loose", "h2", None), ("hook", "rope", "h2", "一根绳子"), ("hook", "curve", "h2", "自然垂下来"), ("hook", "name", "h2", "有个名字"),
      ("title", "yr", "t0", "一六九一"), ("title", "eq", "t0", "数学家们"), ("title", "twist", "t1", None), ("title", "tear", "t1", "不是"), ("title", "ans", "t2", None), ("title", "strap", "t2", "白带子"),
      ("strap", "tense", "s0", "绷紧"), ("strap", "kn", "s0", "张力"), ("strap", "lb", "s0", "大约"), ("strap", "loose", "s1", "先松开"), ("strap", "c99", "s1", "大约九十九"), ("strap", "d8", "s1", "比两端"),
      ("strap", "pull", "s2", "往下一拉"), ("strap", "c914", "s2", "九十一点四"), ("strap", "d77", "s2", "又是"), ("strap", "half", "s3", "一半"), ("strap", "other", "s3", "另一半"),
      ("strap", "chain", "s4", None), ("strap", "point", "s4", "中间被"), ("strap", "kink", "s4", "折出"), ("strap", "v", "s5", "浅浅的"), ("strap", "quote", "s5", "它不是"),
      ("hist", "y1874", "y0", "一八七四"), ("hist", "y1877", "y1", None), ("hist", "size", "y1", "场地尺寸"), ("hist", "p5", "y1", "可网柱"), ("hist", "c33", "y1", "中间三英尺"),
      ("hist", "pass", "y2", "沿边线"), ("hist", "volley", "y2", "冲到网前"), ("hist", "down", "y3", "一截一截"), ("hist", "y1878", "y3", "一八七八"), ("hist", "y1880", "y3", "一八八零"),
      ("hist", "y1882", "y4", None), ("hist", "today", "y4", "一直用到"), ("hist", "pass2", "y5", "降低网柱"), ("hist", "q", "y6", None),
      ("diag", "court", "d0", None), ("diag", "corner", "d1", None), ("diag", "pyth", "d1", "勾股定理"), ("diag", "hyp", "d1", "斜线是"), ("diag", "plus", "d1", "多出"),
      ("diag", "cross", "d2", None), ("diag", "dtl", "d2", "沿边线打"), ("diag", "cc", "d2", "斜线从"), ("diag", "both", "d3", None), ("diag", "safe", "d3", "所以"),
      ("margin", "model", "m0", "按模型"), ("margin", "v", "m0", "时速"), ("margin", "land", "m0", "落在"), ("margin", "cc", "m1", None), ("margin", "dtl", "m1", "沿线只有"),
      ("margin", "win", "m2", None), ("margin", "spin", "m3", "加上上旋"), ("margin", "mcp", "m4", None), ("margin", "pcc", "m4", "斜线占"), ("margin", "pdtl", "m4", "沿线只有"),
      ("margin", "ue", "m5", None), ("margin", "ue19", "m5", "百分之十九"), ("margin", "ue11", "m5", "平均"),
      ("sticks", "dbl", "k0", None), ("sticks", "posts", "k0", "网柱"), ("sticks", "sticks", "k1", "各插"), ("sticks", "d914", "k1", "零点九一四"), ("sticks", "lift", "k1", "撑到"), ("sticks", "rule", "k2", None),
      ("end", "again", "n0", None), ("end", "quote", "n1", None), ("end", "q", "n2", None)]
CPS = 5.2
d = json.load(open("narration.json")); byf = {l["file"]: l for l in d["lines"]}
PUNCT = "，。：；？！、—"
def wb(f):
    if EST:
        out, t = [], 0.08
        for ch in byf[f]["text"]:
            if ch in PUNCT: t += 0.25; continue
            out.append({"off": t, "dur": 1 / CPS, "text": ch}); t += 1 / CPS
        return out
    return [w for w in json.load(open(f"voice/{f}.json")) if w.get("type", "WordBoundary") == "WordBoundary"]
def speech(f): w = wb(f); return w[0]["off"], w[-1]["off"] + w[-1]["dur"]
def char_time(f, s):
    if s == "$end": return speech(f)[1]
    w = wb(f); txt = "".join(x["text"] for x in w)
    key = s
    i = txt.find(key.replace("%", ""))
    if i < 0: raise SystemExit(f"{f} 的词边界里找不到「{s}」：{txt}")
    c = 0
    for x in w:
        if c + len(x["text"]) > i: return x["off"]
        c += len(x["text"])
t = LEAD; secs = []; HIT = None
for name, kind in SECTIONS:
    lines = [l["file"] for l in d["lines"] if l["sec"] == name]
    if name == "hook": s0 = 0
    elif name == "title":
        s0 = t - GAP + PRE_HIT - SEC_GAP + 0.4; HIT = s0   # 钩子最后一句念完 → 静＋起势 → HIT
    else:
        s0 = t - 0.4; s0 = HIT + math.ceil((s0 - HIT) / BEAT - 1e-6) * BEAT
    if name != "hook": t = s0 + 0.5
    for f in lines:
        a, b = speech(f); byf[f]["at"] = round(t - a, 3)
        t = t + max(b - a + GAP, HOLD.get(f, 0))
    t = t + SEC_GAP - GAP
    secs.append({"name": name, "kind": kind, "t0": round(max(0, s0), 3), "t1": round(t - 0.4, 3), "lines": {f: byf[f]["at"] for f in lines}, "ev": {}})
for i in range(len(secs) - 1): secs[i]["t1"] = secs[i + 1]["t0"]
TOTAL = round(t + 1.8, 2); secs[-1]["t1"] = TOTAL
snap = lambda x: HIT + round((x - HIT) / BEAT) * BEAT
for sec, ev, f, word in EV:
    s = next(x for x in secs if x["name"] == sec)
    tt = byf[f]["at"] + (char_time(f, word) if word else speech(f)[0])
    s["ev"][ev] = round(snap(tt) - s["t0"], 3)
if not EST: json.dump(d, open("narration.json", "w"), ensure_ascii=False, indent=1)
tl = {"total": TOTAL, "estimate": EST, "beat": {"hit": round(HIT, 4), "p": BEAT}, "sections": secs}
json.dump(tl, open("r3d/timeline.json", "w"), ensure_ascii=False, indent=1)
open("r3d/shots.js", "w").write("// 由 plan.py 生成，别手改\nexport const TL=" + json.dumps(tl, ensure_ascii=False) + ";\nexport const TOTAL=TL.total;\n")
for s in secs: print(f'{s["name"]:8s} {s["t0"]:7.2f} → {s["t1"]:7.2f}  ({s["t1"]-s["t0"]:5.1f}s)  ev={s["ev"]}')
print("TOTAL", TOTAL, "HIT", round(HIT, 3), "（估算）" if EST else "")
