#!/usr/bin/env python3
"""赛后讲话冷开场（lead_in）的备料助手：找同场集锦、选结尾解说窗口、解析字幕。

原来这一步全自动：定位同场比赛结尾 → 逐条翻译解说 → 写进 spec 的 `lead_in`。
翻译一步已于 2026-10-12 随模型通道整体移除，自动配字幕不再发生；本工具保留
机械部分（哪条 spec 缺 lead_in、窗口怎么选、字幕怎么解析），CLI 只报告待人工
处理的清单，双语字幕由终审人工配。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from build_interview_clip import CAPTION_LANGS, pick_caption  # noqa: E402

SPECS = ROOT / "specs" / "interviews"
WINDOW_SECONDS = 12.0
MAX_CUE_GAP = 12.0
LEAD_IN_CONTENT_TYPES = frozenset({"on_court", "farewell"})


def needs_lead_in(spec: dict) -> bool:
    """这条正式 spec 是否应补一段同场比赛结尾。"""
    opening = spec.get("opening") or {}
    return (
        not spec.get("lead_in")
        and opening.get("kind") == "none"
        and spec.get("requested_content_type") in LEAD_IN_CONTENT_TYPES
    )


def parse_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for event in data.get("events") or []:
        a = float(event.get("tStartMs") or 0) / 1000
        dur = float(event.get("dDurationMs") or 0) / 1000
        text = " ".join(
            str(seg.get("utf8") or "").strip() for seg in (event.get("segs") or [])
        ).strip()
        if text and not text.startswith("["):
            rows.append(
                {
                    "a": round(a, 2),
                    "b": round(a + max(dur, 0.8), 2),
                    "en": text,
                }
            )
    return sorted(rows, key=lambda row: (row["a"], row["b"]))


def select_window(
    cues: list[dict], duration: float, seconds: float = WINDOW_SECONDS
) -> tuple[float, float, list[dict]] | None:
    """取靠近片尾的最后一段解说；窗口≤40s，且至少两条有效英文 cue。"""
    valid = [c for c in cues if 0 <= c["a"] < c["b"] <= duration + 1]
    if len(valid) < 2:
        return None
    end = min(duration, valid[-1]["b"])
    start_floor = max(0.0, end - min(seconds, 39.5))
    tail: list[dict] = [valid[-1]]
    for cue in reversed(valid[:-1]):
        if cue["b"] <= start_floor:
            break
        if tail[0]["a"] - cue["b"] > MAX_CUE_GAP:
            break
        tail.insert(0, cue)
    chosen = [c for c in tail if c["b"] > start_floor and c["a"] < end]
    if len(chosen) < 2 or sum(len(c["en"].split()) for c in chosen) < 6:
        return None
    while seconds == WINDOW_SECONDS and len(chosen) > 1 and end - chosen[0]["a"] > 15:
        chosen.pop(0)
    if seconds == WINDOW_SECONDS and (len(chosen) < 2 or end - chosen[0]["a"] > 15):
        return None
    start = max(0.0, chosen[0]["a"])
    normalized = []
    prev_b = start
    for cue in chosen:
        a, b = max(start, cue["a"], prev_b), min(end, cue["b"])
        if b <= a:
            continue
        normalized.append({**cue, "a": round(a, 2), "b": round(b, 2)})
        prev_b = b
    if len(normalized) < 2:
        return None
    return round(start, 2), round(end, 2), normalized


def _download_subtitles(url: str, directory: Path) -> Path:
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--js-runtimes",
        "node",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        # 和第一份转写走**同一个出处**：`en` 是 YouTube 的改写轨，
        # 措辞被润色过、逐词时间戳是摊出来的。见 `pick_caption` 上面那段。
        CAPTION_LANGS,
        "--sub-format",
        "json3",
        "-o",
        str(directory / "lead_%(id)s"),
        url,
    ]
    cookies = os.environ.get("YT_COOKIES") or ""
    if cookies and Path(cookies).is_file():
        cmd[1:1] = ["--cookies", cookies]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    files = sorted(directory.glob("lead_*.json3"))
    if proc.returncode or not files:
        tail = (proc.stderr or proc.stdout or "没有输出").strip().splitlines()[-1]
        raise RuntimeError(f"同场集锦拿不到英文字幕：{tail[:180]}")
    return pick_caption(files)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--slug", default="", help="只看一个 slug；默认扫全部缺 lead_in 的正式 spec"
    )
    args = ap.parse_args()

    paths = (
        [SPECS / f"{args.slug}.json"]
        if args.slug
        else sorted(p for p in SPECS.glob("*.json") if not p.name.endswith(".draft.json"))
    )
    targets: list[Path] = []
    for path in paths:
        if not path.is_file():
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        if needs_lead_in(spec):
            targets.append(path)

    # 自动配冷开场（模型翻译解说字幕）已随模型通道移除：这里只报清单，
    # 双语字幕留给终审人工配——别悄悄当作「没有待办」。
    for path in targets:
        print(f"待配冷开场：{path.stem}")
    print(f"缺 lead_in 的正式 spec {len(targets)} 条，待人工配双语冷开场。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
