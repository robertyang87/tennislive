"""vibetennis 第 5 集时间轴：按 voice/ 实测配音时长排每句旁白的起点（写回 narration.json 的 at），
并生成 r3d/shots.js（镜头分段：每段的起止秒与镜头类型），overlay.py / sfx.py 也读 r3d/timeline.json。

    python3 plan.py

规则：同一段内句间留 GAP；换段留 SEC_GAP；有些句子画面要更久（比如场馆环绕、顶棚打开），用 HOLD 给最短时长。
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
GAP, SEC_GAP, LEAD = 0.35, 0.9, 0.8
# 镜头分段：(段名, 句子列表, 镜头类型)
SECTIONS = [
    ("hook",   ["h0", "h1", "h2"], "lanes_all"),
    ("venues", ["s0", "s1", "s2", "s3"], "venues"),
    ("q",      ["q0"], "lineup"),
    ("slow",   ["p0", "p1", "p2", "p3", "p4", "p5", "p6"], "slow"),
    ("clay",   ["n0", "n1", "n2", "n3"], "lane_RG"),
    ("grass",  ["n4"], "lane_WIM"),
    ("data",   ["d0", "d1", "d2", "d3"], "pillars"),
    ("rev1",   ["r1", "r2"], "pillars_hi"),
    ("hard",   ["k0", "k1", "k2", "k3"], "acryl"),
    ("aoy",    ["k4", "k5", "k6"], "ao_years"),
    ("rev2",   ["r3", "r4", "r5"], "wim"),
    ("rev3",   ["r6", "r7", "r8", "r9"], "years"),
    ("end",    ["e0", "e1", "e2"], "outro"),
]
# 画面需要的最短停留（秒，从这句开口算到下一句开口）
HOLD = {"h2": 4.6, "s0": 6.5, "s1": 4.2, "s2": 4.4, "s3": 4.2, "q0": 3.4, "p1": 3.2, "p2": 4.6,
        "n0": 4.2, "n4": 6.2, "k1": 4.4, "k3": 7.5, "k6": 4.6, "d1": 5.0, "d3": 6.4, "r1": 5.2, "r4": 6.0, "r6": 3.4, "r8": 4.6, "e1": 3.2, "e2": 4.0}

d = json.load(open("narration.json")); byf = {l["file"]: l for l in d["lines"]}
def speech(f):
    wb = json.load(open(f"voice/{f}.json")); return wb[0]["off"], wb[-1]["off"] + wb[-1]["dur"]
t = LEAD; secs = []
for name, lines, kind in SECTIONS:
    s0 = t - (LEAD if name == "hook" else 0.4)
    for f in lines:
        a, b = speech(f); byf[f]["at"] = round(t - a, 3)
        t = t + max(b - a + GAP, HOLD.get(f, 0))
    t += SEC_GAP - GAP
    secs.append({"name": name, "kind": kind, "t0": round(max(0, s0), 3), "t1": round(t - 0.4, 3),
                 "lines": {f: byf[f]["at"] for f in lines}})
for i in range(len(secs) - 1): secs[i]["t1"] = secs[i + 1]["t0"]
TOTAL = round(t + 1.5, 2); secs[-1]["t1"] = TOTAL
json.dump(d, open("narration.json", "w"), ensure_ascii=False, indent=1)
tl = {"total": TOTAL, "sections": secs}
json.dump(tl, open("r3d/timeline.json", "w"), ensure_ascii=False, indent=1)
open("r3d/shots.js", "w").write("// 由 plan.py 生成，别手改\nexport const TL=" + json.dumps(tl, ensure_ascii=False) + ";\nexport const TOTAL=TL.total;\n")
for s in secs: print(f'{s["name"]:7s} {s["kind"]:10s} {s["t0"]:7.2f} → {s["t1"]:7.2f}')
print("TOTAL", TOTAL)
