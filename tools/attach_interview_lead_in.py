#!/usr/bin/env python3
"""给独立场上采访自动配同场获胜画面、现场解说和中英字幕。

只接受 ``detect_highlights.find_highlight`` 通过的同场官方 1080p 单场集锦；
从集锦末段的官方英文字幕反推最后一段连续解说窗口，再按原时间码逐条翻译。
找不到、只有 720p、没有英文字幕或身份不精确时保留 spec 不动，等待下一轮扫描，
绝不拿另一场/搬运号/静音画面凑数。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from detect_highlights import find_highlight, probe_meta  # noqa: E402
from draft_interview_spec import translate  # noqa: E402
from interview_source_gate import SourceContractError, validate_source_contract  # noqa: E402

SPECS = ROOT / "specs" / "interviews"
WINDOW_SECONDS = 28.0
MAX_CUE_GAP = 12.0


def parse_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for event in data.get("events") or []:
        a = float(event.get("tStartMs") or 0) / 1000
        dur = float(event.get("dDurationMs") or 0) / 1000
        text = " ".join(str(seg.get("utf8") or "").strip()
                        for seg in (event.get("segs") or [])).strip()
        if text and not text.startswith("["):
            rows.append({"a": round(a, 2), "b": round(a + max(dur, 0.8), 2),
                         "en": text})
    return sorted(rows, key=lambda row: (row["a"], row["b"]))


def select_window(cues: list[dict], duration: float,
                  seconds: float = WINDOW_SECONDS) -> tuple[float, float, list[dict]] | None:
    """取靠近片尾的最后一段解说；窗口≤40s，且至少两条有效英文 cue。"""
    valid = [c for c in cues if 0 <= c["a"] < c["b"] <= duration + 1]
    if len(valid) < 2:
        return None
    # 片尾品牌动画通常没有字幕；用最后一条真实解说的终点作为窗口终点。
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
    cmd = ["yt-dlp", "--no-warnings", "--js-runtimes", "node", "--skip-download",
           "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,en",
           "--sub-format", "json3",
           "-o", str(directory / "lead_%(id)s"), url]
    cookies = os.environ.get("YT_COOKIES") or ""
    if cookies and Path(cookies).is_file():
        cmd[1:1] = ["--cookies", cookies]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    files = sorted(directory.glob("lead_*.json3"))
    if proc.returncode or not files:
        tail = (proc.stderr or proc.stdout or "没有输出").strip().splitlines()[-1]
        raise RuntimeError(f"同场集锦拿不到英文字幕：{tail[:180]}")
    return files[-1]


def attach(spec: dict, chat) -> dict:
    validate_source_contract(spec)
    match = spec["match"]
    for key in ("winner_en", "loser_en", "event_search", "year"):
        if not match.get(key):
            raise RuntimeError(f"match.{key} 为空，不能精确搜索同场集锦")
    url, via = find_highlight(
        match["winner_en"], match["loser_en"], match["event_search"],
        int(match["year"]), per=12)
    if not url:
        raise RuntimeError("尚未找到通过官方/同场/1080p 门禁的单场集锦")
    meta = probe_meta(url)
    if not meta or not meta[1]:
        raise RuntimeError("同场集锦时长读取失败")
    channel, duration, height = meta
    with tempfile.TemporaryDirectory() as td:
        cues = parse_json3(_download_subtitles(url, Path(td)))
    window = select_window(cues, float(duration))
    if not window:
        raise RuntimeError("集锦末段没有足够的英文解说字幕，不能满足双语冷开场")
    start, end, selected = window
    zh = translate([{"t": c["a"], "text": c["en"]} for c in selected], chat)
    subs = [{**cue, "zh": cn} for cue, cn in zip(selected, zh)]
    spec["lead_in"] = {
        "url": url,
        "start": start,
        "end": end,
        "subs": subs,
        "why": (f"自动同场核验：{match['winner_en']} vs {match['loser_en']}，"
                f"{match['event_search']} {match['year']}；来源 {channel or via}，"
                f"{height:.0f}p。取官方单场集锦最后一段连续现场解说，随后接场上采访。"),
        "verification": {
            "match_id": match["id"], "channel": channel or via,
            "height": height, "method": "official_exact_match_highlight",
            "winner_en": match["winner_en"], "loser_en": match["loser_en"],
            "event_search": match["event_search"], "year": match["year"],
        },
    }
    return spec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", default="", help="只处理一个 slug；默认扫全部缺 lead_in 的正式 spec")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--max-parallel", type=int, default=4,
                    help="不同比赛并行搜索/取字幕/翻译；同一 spec 只会出现一次")
    args = ap.parse_args()

    from tennislive.research.brief import Chat  # noqa: PLC0415
    chat = Chat()
    if not chat.ready:
        print("::error::没配 DEEPSEEK_API_KEY，冷开场中文字幕无法生成")
        return 2

    paths = ([SPECS / f"{args.slug}.json"] if args.slug
             else sorted(p for p in SPECS.glob("*.json") if not p.name.endswith(".draft.json")))
    targets: list[tuple[Path, dict]] = []
    for path in paths:
        if not path.is_file():
            continue
        spec = json.loads(path.read_text(encoding="utf-8"))
        opening = spec.get("opening") or {}
        if spec.get("lead_in") or opening.get("kind") != "none" \
                or spec.get("requested_content_type") != "on_court":
            continue
        targets.append((path, spec))

    def _one(target: tuple[Path, dict]):
        path, spec = target
        try:
            updated = attach(spec, chat)
        except (RuntimeError, SourceContractError, ValueError) as exc:
            return path, None, str(exc)
        if args.write:
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        return path, updated, ""

    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as pool:
        futures = [pool.submit(_one, target) for target in targets]
        for future in as_completed(futures):
            results.append(future.result())
    failed = sum(updated is None for _, updated, _ in results)
    done = len(results) - failed
    for path, updated, error in results:
        if updated is None:
            print(f"::warning::{path.stem} 冷开场待下一轮：{error}")
        else:
            print(f"✅ {path.stem}：同场获胜画面 + {len(updated['lead_in']['subs'])} 条双语解说")
    print(f"冷开场完成 {done}/{len(targets)}，待重试 {failed}。")
    # 单场显式调用失败要红；批量扫描允许其他比赛继续，失败会继续留在 waiting 清单。
    return 1 if args.slug and failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
