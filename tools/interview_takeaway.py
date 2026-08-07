#!/usr/bin/env python3
"""赛后开麦：把**提炼的原料**从转写里量出来，别每次现想。

    PYTHONPATH=src python3 tools/interview_takeaway.py --spec specs/interviews/<slug>.json

账号所有者 2026-08-05：「以后赛后开麦，要找总结提炼下。」

来路是视频号那条判定——「二次创作部分**信息增量不足**，如素材简单增加标题、
字幕」。补的办法是往片子里加两张解读卡（见 `build_interview_clip.check_takeaway`），
而这个工具管的是那两张卡**写什么**。

### 为什么是「量」不是「想」

一段场上采访六成是套话。想一个观点出来，写的人当天状态好就有、不好就没有，
而且**没法验**。可**套话的分布本身是信息**，它就在我们已经有的那份转写里：

    商竣程 2026-08-05 蒙特利尔第二轮，他自己说了 154 个词
      healthy  4 次 ｜ happy 4 次 ｜ win **1** 次
      而那 1 次是「如果还能赢下几场球，那就再好不过了」

「赢了世界前十的那一晚，他谈的不是赢球」——这句判断**是数出来的**，
可核、可复算，而且下一条片子照样数得出来。

### 它只给原料，不给结论

选哪个数、怎么解读，是编辑判断，机械挡不住（CLAUDE.md 里那几条「故意没有
测试」的规矩说的就是这件事）。所以这儿只打印五样东西，结论自己写：

1. **他说了多少**（对比主持人问了多少）——答得短本身就是态度
2. **词频**（去掉功能词，只数他说的）
3. **他没说什么**——一张固定的观察表，说 0 次也打印。
   **缺席是信息，而缺席不会自己从频次榜上跳出来**
4. **转折之后那几句**——`but` / `actually` / `to be honest` / `honestly`
   后面那半句，落点最常藏在这儿
5. **每一问他答了多少词**——哪个问题他不想答，一眼看得出

⚠️ **主持人和球员靠 `>>` 分**。那是 YouTube 自动字幕给每个说话人第一个词加的
前缀，我们自己跑 ASR 时要手工补上（CLAUDE.md 记过）。**补错了这里全错**，
所以第一件事是把分出来的轮次打印出来让人对一眼——分错了看一眼就知道，
而不是拿一份错的词频去写卡。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 功能词：数出来只会说明这是英语。**不含 win / healthy / happy 这类**——
# 那正是要数的东西。
_STOP = frozenset("""
a an the and or but so if then than that this these those there here
i you he she it we they me him her us them my your his its our their
is am are was were be been being do does did done have has had having
of in on at to for from with by about into over after before again
not no yes very just really so too also more most much many few
what which who whom whose when where why how
will would can could shall should may might must
well yeah yes okay ok know like kind sort mean thing things lot bit
s t re ve ll d m o k y
""".split())

# **一张固定的观察表**：这些词每次都打印，说了几次就写几次，**说 0 次也写**。
#
# ⚠️ 这一节才是这个工具真正的价值。频次榜只能显示**出现过**的词，而
# 「他一次都没提赢球」这种事**在榜上是看不见的**——它长得和「我没往下翻」
# 一模一样。这个仓库为「空结果 ≠ 不存在」栽过很多次，这是同一个形状：
# **缺席是信息，但缺席不会自己跳出来。**
_WATCH = {
    "赢球": ("win", "wins", "won", "winning", "beat", "victory"),
    "冠军/头衔": ("title", "trophy", "champion", "championship", "final"),
    "健康/身体": ("healthy", "health", "injury", "injured", "body", "fit"),
    "情绪": ("happy", "happily", "enjoy", "enjoyed", "fun", "proud", "emotional"),
    "自我要求": ("level", "better", "improve", "work", "learn", "process"),
    "团队/家人": ("team", "coach", "family", "everyone", "support", "fans"),
    "下一场": ("next", "tomorrow", "recover", "rest", "ready"),
}

_PIVOT = re.compile(
    r"\b(but|although|though|actually|honestly|to be honest|"
    r"the truth is|more importantly|most importantly)\b", re.I)


def turns(lines: list[dict]) -> list[dict]:
    """按 `>>` 切说话轮次。返回 [{who, text, words, start}]。

    ⚠️ **`who` 是推的，不是标的**：第一个轮次一律当主持人（场上采访永远是
    主持人先开口），之后交替。真实采访里主持人偶尔会插一句「right」而不带
    `>>`，那种会被并进球员那一轮——所以要人对一眼，见模块开头。
    """
    out: list[dict] = []
    for ln in lines:
        en = (ln.get("en") or "").strip()
        if not en:
            continue
        if en.startswith(">>") or not out:
            out.append({"text": "", "start": ln.get("a", 0.0)})
            en = en.lstrip("> ").strip()
        out[-1]["text"] = (out[-1]["text"] + " " + en).strip()
    for i, t in enumerate(out):
        t["who"] = "主持人" if i % 2 == 0 else "球员"
        t["words"] = len(t["text"].split())
    return out


def _spoken_turns(lines: list[dict], marks: list[str] | None) -> list[dict]:
    """有 `cap_*.json3` 就用它的 `>>`（那才是标过的），否则退回 `lines`。

    **两条路都要出声**：退回去和标过长得一模一样，而退回去的分轮是猜的。
    """
    if marks is None:
        print("⚠️ 没找到带 `>>` 的转写，按字幕行猜说话轮次——**词频可能把主持人"
              "的话算进球员头上**。想准就把 `cap_*.json3` 放进 outdir。")
        return turns(lines)
    out: list[dict] = []
    for seg in marks:
        if seg.startswith(">>") or not out:
            out.append({"text": "", "start": 0.0})
            seg = seg.lstrip("> ").strip()
        out[-1]["text"] = (out[-1]["text"] + " " + seg).strip()
    for i, t in enumerate(out):
        t["who"] = "主持人" if i % 2 == 0 else "球员"
        t["words"] = len(t["text"].split())
    return out


def report(spec: dict, outdir: Path) -> str:
    lines_p = outdir / "lines.json"
    if not lines_p.exists():
        raise SystemExit(
            f"{lines_p} 不在——先跑 `--stage subs` 把转写切出来。\n"
            "（这个工具只读已经有的产物，不联网、不下源片。）")
    lines = json.loads(lines_p.read_text(encoding="utf-8"))

    # ⚠️ **按 spec 的 `start`/`end` 掐头去尾。** `cap_*.json3` 是**整条源片**的
    # 转写，而这个报告说的是**这条片子**——两者只在 spec 没剪的时候才一样。
    # 萨巴伦卡那条把主持人那句听不清的收场白剪掉了（`end: 63.7`，那一轮
    # 从 63.80 起），不掐的话主持人算出来是 143 词、实际片子里只有 119——
    # **而表头就印着「采访 63.7 秒」**，读的人没有第二个地方可以对。
    # 又一次「查产物，不查信号」：产物是这条片子，不是那份转写。
    lo, hi = spec["start"], spec["end"]
    marks = None
    for cap in sorted(outdir.glob("cap_*.json3")):
        ev = json.loads(cap.read_text(encoding="utf-8")).get("events") or []
        words = [s.get("utf8", "") for e in ev
                 if lo <= e.get("tStartMs", 0) / 1000 <= hi
                 for s in (e.get("segs") or [])]
        joined = " ".join(w.strip() for w in words if w.strip())
        if ">>" in joined:
            marks = re.split(r"(?=>>)", joined)
            marks = [m.strip() for m in marks if m.strip()]
            print(f"[原料] 说话轮次按 {cap.name} 的 `>>` 切"
                  f"（只取片内 {lo:.1f}–{hi:.1f} 秒）")
            break

    tt = _spoken_turns(lines, marks)
    his = [t for t in tt if t["who"] == "球员"]
    host = [t for t in tt if t["who"] == "主持人"]
    his_text = " ".join(t["text"] for t in his)

    # 缩写按词干算：`that's` → `that`（在停用表里）、`andre's` → `andre`（留着）。
    # 不这么做的话，榜首会是 that's / he's / i'm 这一串，把真正的词挤下去。
    words = [w.split("'")[0] for w in re.findall(r"[a-z']+", his_text.lower())]
    freq = Counter(w for w in words if w not in _STOP and len(w) > 1)
    seen = Counter(words)

    secs = spec["end"] - spec["start"]
    out = [
        f"# {spec['slug']} 提炼原料",
        "",
        f"采访 {secs:.1f} 秒。**他说了 {sum(t['words'] for t in his)} 个词**，"
        f"主持人问了 {sum(t['words'] for t in host)} 个。",
        "",
        "## ① 说话轮次（先对一眼分得对不对——分错了下面全是错的）",
        "",
    ]
    for i, t in enumerate(tt):
        head = t["text"][:74] + ("…" if len(t["text"]) > 74 else "")
        out.append(f"{i:2d}. **{t['who']}**（{t['words']} 词）{head}")

    out += ["", "## ② 他说得最多的词（去掉功能词）", ""]
    for w, n in freq.most_common(14):
        bar = "█" * n
        out.append(f"    {w:<14}{n:>3}  {bar}")
    out += [
        "",
        "⚠️ **看的是对比，不是绝对值。** 一个词说 4 次不稀奇；稀奇的是"
        "「赢球」这种本该占满整段的词只说了 1 次。",
        "",
        "## ③ 他**没**说什么（这一节才是重点）",
        "",
        "频次榜只列出现过的词——**「一次都没提」在榜上是看不见的**，"
        "它长得和「我没往下翻」一模一样。所以这张表固定打印，说 0 次也写。",
        "",
    ]
    for label, group in _WATCH.items():
        n = sum(seen[w] for w in group)
        hit = "、".join(f"{w}×{seen[w]}" for w in group if seen[w]) or "—"
        flag = "  ← **一次都没提**" if n == 0 else ""
        out.append(f"    {label:<8}{n:>3}   {hit}{flag}")

    out += [
        "",
        "## ④ 转折之后那几句（落点最常在这儿）",
        "",
    ]
    hits = 0
    for t in his:
        for m in _PIVOT.finditer(t["text"]):
            tail = t["text"][m.start():][:120]
            out.append(f"- …{tail}")
            hits += 1
    if not hits:
        out.append("（这段里没有转折词。**不等于没有落点**——"
                   "落点也可能是他被问 A 却答了 B，看 ⑤。）")

    out += ["", "## ⑤ 每一问他答了多少词", ""]
    for i, t in enumerate(tt):
        if t["who"] != "球员":
            continue
        q = tt[i - 1]["text"][:56] if i else "（开场）"
        out.append(f"- 问「{q}…」→ 答 **{t['words']} 词**")
    out += [
        "",
        "---",
        "",
        "把上面挑出来的写进 spec 的 `takeaway`：",
        "",
        "```json",
        '"takeaway": {',
        '  "open":  {"lead": "…他先说了什么…", "point": "「…他的原话…」",',
        '            "facts": ["…上面这些数里能核的那个…"]},',
        '  "close": {"point": "…这句话意味着什么…", "ask": "…一问…"}',
        "}",
        "```",
        "",
        "⚠️ `open.point` 引的那句**必须真在 `zh` 里**，闸在 `check_takeaway`。",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--outdir", help="默认按 slug 在 output/interviews/ 下找")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    outdir = Path(args.outdir) if args.outdir else (
        ROOT / "output/interviews" / spec["slug"])
    print(report(spec, outdir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
