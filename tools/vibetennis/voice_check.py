#!/usr/bin/env python3
"""vibetennis 中文旁白的出片前检查（全局配音规则 2026-10-06 / 10-19 / 10-20 在这一栏的落点）。

这一栏的配音不走赛场之上那条 render（没有 `voice_auto_review` 要的 TTS 清单包），所以按同样的
意思另起一份、只查拿得到的东西：

1. **完整**：narration.json 每一句都有合成好的 `voice/<file>.mp3`，而且不是空的
2. **不打架**：按 `at` 排好之后，上一句没念完下一句就开口（重叠 > 0.15 秒）算不合格
3. **多音字**：合成文本（`tts`）过一遍 `tools/check_polyphones.py` 的静态分析；报出来的每一处，
   要么在合成文本里换字／改写，要么在这一句写 `"poly_ok": {"<字>": "<怎么确认的>"}` 认领——
   **「静态零提示」不是听过**（全局规则原话），认领要写清是谁、用什么方法确认的

    python3 tools/vibetennis/voice_check.py tools/vibetennis/episodes/<slug>

`qc.py` 对有旁白的中文版自动调它；EP04、EP05 是规则落到这一栏之前推出去的，挂在 `LEGACY`
（多音字、重叠只报不拦；只许减不许加）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

# 规则落到这一栏之前已推的集：多音字、重叠只报不拦（缺配音照样拦）。只许减不许加。
# EP04 n29→n30 实测重叠 0.54s（186.02s 开口时上一句还没念完），已推，不重渲。
LEGACY = frozenset({"vibetennis-federer-54-percent-2026", "vibetennis-court-speed-2026"})
OVERLAP_TOL = 0.15


def speech_end(mp3: Path) -> float:
    """最后一个字念完的时刻。edge-tts 的 mp3 尾巴带约 0.7 秒静音（EP05 r3：4.34s 的文件 3.58s 就念完了），
    拿文件时长判重叠会报一串假的；有同名 .json 词边界就用它。"""
    wb = mp3.with_suffix(".json")
    if wb.is_file():
        words = [w for w in json.loads(wb.read_text(encoding="utf-8")) if w.get("type") == "WordBoundary"]
        if words:
            return max(float(w["off"]) + float(w["dur"]) for w in words)
    return mp3_seconds(mp3)


def mp3_seconds(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def problems(episode: Path) -> tuple[list[str], list[str]]:
    """返回 (不合格, 只报不拦的提示)。"""
    import check_polyphones as cp  # noqa: PLC0415

    nar = json.loads((episode / "narration.json").read_text(encoding="utf-8"))
    lines = sorted(nar["lines"], key=lambda x: float(x["at"]))
    bad: list[str] = []
    notes: list[str] = []
    prev_end, prev_id = -1.0, ""
    for ln in lines:
        mp3 = episode / "voice" / f"{ln['file']}.mp3"
        if not mp3.is_file() or mp3.stat().st_size < 1000:
            bad.append(f"{ln['file']}：没有合成好的配音 {mp3.name}")
            continue
        dur = speech_end(mp3)
        at = float(ln["at"])
        if prev_end - at > OVERLAP_TOL:
            (notes if episode.name in LEGACY else bad).append(f"{ln['file']}：{prev_id} 还没念完（到 {prev_end:.2f}s）它就在 {at:.2f}s 开口")
        prev_end, prev_id = at + dur, ln["file"]
        tts = str(ln.get("tts") or ln.get("text") or "")
        risks, _, _ = cp.analyze(cp.Spoken(ln["file"], tts, str(nar.get("rate") or "")))
        ok = ln.get("poly_ok") or {}
        for r in risks:
            if r.char in ok:
                continue
            msg = f"{ln['file']}：多音字「{r.char}」（{r.word}，该读 {r.intended}）没换字也没认领 —— {tts}"
            (notes if episode.name in LEGACY else bad).append(msg)
    return bad, notes


def main() -> int:
    ep = Path(sys.argv[1]).resolve()
    bad, notes = problems(ep)
    for n in notes:
        print(f"[提示] {n}")
    for b in bad:
        print(f"[不合格] {b}")
    print(f"\n共 {len(bad)} 项不合格")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
