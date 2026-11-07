"""vibetennis EP10 德约为什么是接发之王：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
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
SECTIONS = [(n, n) for n in ("hook", "race", "read", "split", "slide", "data", "end")]
# 每句最短停留（从这句开口到下一句开口）：给这句的动效留够时间
HOLD = {"h0": 5.2, "h1": 5.4, "h2": 3.6, "h3": 3.6, "h4": 4.4, "h5": 3.8,
        "r0": 6.6, "r1": 4.6, "r2": 5.0, "r3": 5.4, "r4": 6.0, "r5": 5.6,
        "e0": 3.4, "e1": 6.4, "e2": 5.6, "e3": 6.8, "e4": 4.6,
        "s0": 2.8, "s1": 4.4, "s2": 5.4, "s3": 7.0, "s4": 4.2,
        "d0": 4.6, "d1": 4.8, "d2": 7.2, "d3": 5.6,
        "k0": 3.0, "k1": 6.0, "k2": 7.6, "k3": 6.0, "k4": 7.4, "k5": 5.8, "k6": 4.2,
        "n0": 3.6, "n1": 5.2, "n2": 5.6}
MIN_SEC = {}
EV = [("hook", "serve", "h0", "费德勒发球"), ("hook", "ret", "h1", "正手"), ("hook", "run", "h2", None), ("hook", "crown", "h3", None),
      ("hook", "board", "h4", None), ("hook", "r7", "h4", "第7"), ("hook", "q", "h5", None),
      ("race", "tl", "r0", None), ("race", "fly", "r0", "六七百"), ("race", "react", "r1", None), ("race", "jump", "r2", "起跳"),
      ("race", "land", "r3", None), ("race", "racket", "r3", "0.19"), ("race", "fork", "r4", "判断"), ("race", "guess", "r5", "猜好"),
      ("read", "body", "e0", None), ("read", "toss", "e1", "抛球"), ("read", "arm", "e1", "持拍手臂"), ("read", "gaze", "e2", None),
      ("read", "sacc", "e3", "提前跳"), ("read", "title", "e4", None),
      ("split", "go", "s0", None), ("split", "hop", "s1", "分腿垫步"), ("split", "race", "s2", None), ("split", "spring", "s3", "拉长"),
      ("split", "title", "s4", None),
      ("slide", "slide", "d0", "滑步"), ("slide", "grip", "d1", "静摩擦"), ("slide", "kin", "d2", "滑动摩擦"), ("slide", "comp", "d3", None),
      ("data", "board", "k0", None), ("data", "sum", "k1", "四项"), ("data", "all", "k2", None), ("data", "hard", "k2", "硬地"),
      ("data", "act", "k2", "现役"), ("data", "y11", "k3", None), ("data", "deep", "k4", None), ("data", "h2h", "k5", None), ("data", "last", "k6", None),
      ("end", "n0", "n0", None), ("end", "p1", "n1", "看懂"), ("end", "p2", "n1", "起跳"), ("end", "p3", "n1", "回得"), ("end", "q", "n2", None)]
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
