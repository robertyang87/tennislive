"""vibetennis EP11 阻力危机：时间轴。按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
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
SECTIONS = [(n, n) for n in ("hook", "eiffel", "layer", "golf", "football", "tennis", "fluff", "itf", "end")]
# 每句最短停留（从这句开口到下一句开口）：给这句的动效留够时间
HOLD = {"h0": 3.2, "h1": 9.6, "h2": 3.6, "h3": 4.6, "h4": 6.4,
        "e0": 6.0, "e1": 6.0, "e2": 7.2, "e3": 6.0,
        "l0": 4.6, "l1": 7.8, "l2": 6.8, "l3": 4.4, "l4": 8.0,
        "g0": 3.0, "g1": 6.0, "g2": 5.4,
        "f0": 2.6, "f1": 3.4, "f2": 7.0,
        "t0": 2.4, "t1": 7.4, "t2": 5.8, "t3": 8.6, "t4": 4.4, "t5": 5.0,
        "u0": 5.0, "u1": 5.0, "u2": 5.6,
        "i0": 2.8, "i1": 6.4, "i2": 4.6,
        "n0": 4.8, "n1": 5.4, "n2": 5.0}
MIN_SEC = {}
EV = [("hook", "q", "h0", None), ("hook", "shave", "h1", "剃光"), ("hook", "serve", "h1", "公里"), ("hook", "fork", "h1", "可能只剩"),
      ("hook", "wobble", "h2", None), ("hook", "steady", "h3", None), ("hook", "brake", "h4", "刹车"), ("hook", "stab", "h4", "稳定器"), ("hook", "tower", "h4", "铁塔"),
      ("eiffel", "rise", "e0", None), ("eiffel", "tunnel", "e0", "风洞"), ("eiffel", "drop", "e1", "突然掉"), ("eiffel", "cliff", "e2", None),
      ("eiffel", "name", "e2", "阻力危机"), ("eiffel", "wire", "e3", "细线"),
      ("layer", "zoom", "l0", None), ("layer", "bl", "l0", "边界层"), ("layer", "lam", "l1", "层流"), ("layer", "sep", "l1", "脱开"),
      ("layer", "turb", "l2", "湍流"), ("layer", "narrow", "l3", "变窄"), ("layer", "re", "l4", "雷诺数"),
      ("golf", "g", "g0", None), ("golf", "dimple", "g1", "凹坑"), ("golf", "shift", "g1", "更低的速度"), ("golf", "drive", "g2", "开球"),
      ("football", "f", "f0", None), ("football", "edge", "f1", "悬崖附近"), ("football", "knuckle", "f2", "忽左忽右"),
      ("tennis", "q", "t0", None), ("tennis", "band", "t1", "换算成"), ("tennis", "flip", "t2", "时而"), ("tennis", "flat", "t3", "抹平"),
      ("tennis", "fuzz", "t3", "每根毛"), ("tennis", "cd", "t3", "上下"), ("tennis", "labs", "t4", None), ("tennis", "rally", "t5", "一来一回"),
      ("fluff", "fl", "u0", "毛越蓬"), ("fluff", "pick", "u1", "挑一颗"), ("fluff", "cash", "u2", "温网冠军"),
      ("itf", "i", "i0", None), ("itf", "big", "i1", "标准球"), ("itf", "area", "i2", "迎风面积"),
      ("end", "n0", "n0", None), ("end", "slow", "n1", "慢下来"), ("end", "q", "n2", None)]
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
