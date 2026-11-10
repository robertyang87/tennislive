"""vibetennis EP12 抢七轮发：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
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
SECTIONS = [(n, n) for n in ("hook", "rule", "edge", "math", "why", "soccer", "data", "end")]
# 每句最短停留（从这句开口到下一句开口）：给这句的动效留够时间
HOLD = {"h0": 5.0, "h1": 5.6, "h2": 6.4, "h3": 7.2, "h4": 4.0,
        "r0": 4.4, "r1": 9.4,
        "e0": 7.0, "e1": 7.0, "e2": 6.2,
        "m0": 3.0, "m1": 9.6, "m2": 6.4, "m3": 6.6, "m4": 9.6, "m5": 6.4, "m6": 6.4,
        "w0": 8.0, "w1": 4.6, "w2": 8.4, "w3": 8.8, "w4": 7.4, "w5": 5.0,
        "f0": 7.0, "f1": 5.4, "f2": 6.6, "f3": 6.0,
        "d0": 9.4, "d1": 7.4,
        "n0": 7.6, "n1": 6.4, "n2": 4.6}
MIN_SEC = {}
EV = [("hook", "pts", "h0", "多赢"), ("hook", "lose", "h0", "却输掉"), ("hook", "tb", "h1", None), ("hook", "tb3", "h1", "最后一个"),
      ("hook", "order", "h2", None), ("hook", "one", "h2", "只发一分"), ("hook", "two", "h2", "连发两分"), ("hook", "why", "h3", None), ("hook", "seq", "h3", "数列"),
      ("hook", "same", "h3", "前四位"), ("hook", "q2", "h4", None),
      ("rule", "game", "r0", None), ("rule", "tb", "r1", None), ("rule", "ch", "r1", "每打"),
      ("edge", "pct", "e0", None), ("edge", "dj", "e0", "德约"), ("edge", "fd", "e0", "费德勒"), ("edge", "abab", "e1", None), ("edge", "chase", "e1", "一直在追"), ("edge", "abba", "e2", None),
      ("math", "m0", "m0", None), ("math", "calc", "m1", None), ("math", "r1", "m1", "一人一分"), ("math", "r2", "m1", "也是"), ("math", "model", "m2", None), ("math", "key", "m2", "秘密"),
      ("math", "ex", "m3", None), ("math", "fill", "m3", "全打完"), ("math", "twelve", "m4", None), ("math", "after", "m4", "每两分"), ("math", "race", "m5", None),
      ("math", "more", "m5", "对手只发"), ("math", "pct", "m6", None),
      ("why", "sw", "w0", None), ("why", "cnt", "w0", "只换"), ("why", "ch", "w1", None), ("why", "build", "w2", None), ("why", "ab", "w2", "得到"), ("why", "abba2", "w2", "再接上"),
      ("why", "tm", "w3", None), ("why", "hist", "w3", "论文"), ("why", "layer", "w4", None), ("why", "econ", "w4", "经济学家"), ("why", "tennis", "w5", None), ("why", "split", "w5", "第五位"),
      ("soccer", "q", "f0", None), ("soccer", "pk", "f0", "点球"), ("soccer", "s60", "f1", None), ("soccer", "ifab", "f2", None), ("soccer", "stop", "f2", "又决定"), ("soccer", "big", "f3", None),
      ("data", "d", "d0", None), ("data", "res", "d0", "先发和后发"), ("data", "blog", "d1", None),
      ("end", "n0", "n0", None), ("end", "tip", "n1", None), ("end", "q", "n2", None)]
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
