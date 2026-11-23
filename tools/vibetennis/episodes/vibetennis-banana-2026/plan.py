"""vibetennis EP14 不是补钾：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
生成 r3d/timeline.json 和 r3d/shots.js（每段起止秒、每句开口时刻、画面事件时刻）。

    python3 plan.py            # 按 voice/*.json 词边界实测排
    python3 plan.py --estimate # 配音没合成时按每秒 5.2 字估（只给审片包）

卡点（所有者：动画跟 BGM 节拍走，关键时刻落在强拍上）：BGM 用 /workspace/tennis_ep/bgm 的 first.wav（第 0 小节起）＋ loop.wav，
112.8 BPM、一拍 0.531943 s、一小节 2.12777 s。片头「不是补钾」砸下来那一刻（title 段起点 HIT）＝ first.wav 第 8 小节线（满配器进来），
sfx.py 按 TL.beat.hit 反推 BGM 起点。之后每段起点往后对齐到拍点，画面事件（EV）对齐到最近的拍点（最多挪半拍）。
"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
EST = "--estimate" in sys.argv
GAP, SEC_GAP, LEAD = 0.35, 0.9, 0.3
BEAT = 2.127772 / 4
SECTIONS = [(n, n) for n in ("hook", "title", "peel", "salt", "fuel", "proof", "alt", "end")]
HOLD = {"h0": 5.6, "h1": 6.2,
        "t0": 3.4, "t1": 4.2, "t2": 5.6,
        "p0": 4.8, "p1": 6.6, "p2": 3.6, "p3": 7.4, "p4": 5.0,
        "k0": 3.8, "k1": 8.8, "k2": 6.0, "k3": 9.4, "k4": 5.8,
        "g0": 5.8, "g1": 8.2, "g2": 9.6, "g3": 5.2, "g4": 6.2, "g5": 7.0,
        "e0": 5.4, "e1": 11.6, "e2": 11.8, "e3": 6.2, "e4": 10.4, "e5": 9.6,
        "c0": 3.8, "c1": 7.6, "c2": 9.8, "c3": 8.4,
        "n0": 3.2, "n1": 6.2, "n2": 6.2, "n3": 6.0}
PRE_HIT = 1.0   # 钩子最后一句念完到 HIT 留的「静＋起势」
EV = [
      ("hook", "peel", "h0", "抽出一根香蕉"), ("hook", "bite", "h0", "咬一口"),
      ("hook", "myth", "h1", "补钾"), ("hook", "q", "h1", "$end"),
      ("title", "punch", "t0", None), ("title", "gly", "t1", "肌糖原"), ("title", "no", "t2", "并没有试验"),
      ("peel", "size", "p0", "一百一十八克"), ("peel", "cho", "p1", "二十七克碳水"),
      ("peel", "sug", "p1", "十四克糖"), ("peel", "fib", "p1", "三克纤维"), ("peel", "kcal", "p1", "一百零五千卡"),
      ("peel", "k", "p2", "四百二十二毫克"), ("peel", "gi", "p3", "五十一"), ("peel", "ripe", "p3", "过熟"),
      ("peel", "first", "p4", "首先是一块"),
      ("salt", "na", "k0", "其实是钠"), ("salt", "sweat", "k1", "九十分钟骑车"),
      ("salt", "naMg", "k1", "一千五百六十五毫克钠"), ("salt", "kMg", "k1", "一百九十四毫克"),
      ("salt", "cover", "k2", "多过这次钾"), ("salt", "miss", "k2", "补不上那些钠"),
      ("salt", "race", "k3", "血清钾"), ("salt", "nerve", "k3", "神经对肌肉"),
      ("salt", "verdict", "k4", "还没有被证明"),
      ("fuel", "need", "g0", "额外的糖"), ("fuel", "notbx", "g1", "不是在网球场上"),
      ("fuel", "glu", "g1", "更多是血糖"), ("fuel", "guide", "g1", "补贴糖原"),
      ("fuel", "stmt", "g2", "二零二五年"), ("fuel", "lo", "g2", "三十到六十克"),
      ("fuel", "hi", "g3", "六十到九十克"), ("fuel", "win", "g4", "九十秒"),
      ("fuel", "set", "g4", "一百二十秒"), ("fuel", "bar", "g5", "刚够这个起点"),
      ("fuel", "notall", "g5", "不是五盘的全部"),
      ("proof", "mix", "e0", "并不完全一样"), ("proof", "v", "e1", "一九九八年"),
      ("proof", "vres", "e1", "掉得更少"), ("proof", "m", "e2", "二零一二年"),
      ("proof", "mtot", "e2", "百分之六十八"), ("proof", "m1st", "e2", "百分之六十五"),
      ("proof", "mnote", "e2", "还不够累"), ("proof", "mit", "e3", "没有看到表现更好"),
      ("proof", "n", "e4", "十四名男自行车手"), ("proof", "nres", "e4", "没有明显差别"),
      ("proof", "ntime", "e4", "两小时四十一分"), ("proof", "blo", "e5", "更饱"),
      ("proof", "dole", "e5", "香蕉公司资助"), ("proof", "none", "e5", "还没找到"),
      ("alt", "ok", "c0", "可以改"), ("alt", "drink", "c1", "四百五十毫升"),
      ("alt", "date", "c2", "十八克碳水"), ("alt", "chew", "c2", "不一定吃得完"),
      ("alt", "bbc", "c3", "二零一零年"), ("alt", "ask", "c3", "是香蕉"),
      ("end", "again", "n0", None), ("end", "k", "n1", "四百二十二毫克钾"),
      ("end", "cho", "n2", "二十七克碳水"), ("end", "q", "n3", "$end")]
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
