#!/usr/bin/env python3
"""把 spec 的源片落到 outdir，并按这些字节重写前景原声审听。

渲染入口先 `require()` 再下载，下载之后 `bind_sources()` 再拿 sha256 对账。
两次下载的 mp4 容器时间戳经常不一样，所以审听必须绑在**这一趟要编码的那份文件**上：
先落到 `outdir/source_<键>.mp4`，`render()` 见到文件就跳过重下。

选择器先用任务书的 `bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]`。这一档匹配不上
（没有 avc1、或者八个 client 都过不了）时，退回 `build_match_reel.download()`，
并在 `outdir/source_fetch.json` 里记下用了哪一档。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import reviewed_effects_mode  # noqa: E402
from build_match_reel import (  # noqa: E402
    MIN_SOURCE_H,
    YTDLP_BASE,
    _keep_source,
    _ladder,
    download,
    probe_size,
    resolve_fps,
)
from foreground_audio_gate import SCHEMA, plan_hash, require  # noqa: E402

BRIEF_FMT = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]"
NARRATION_REASON = (
    "这一段是中文旁白。审听窗口里没有要另配双语字幕的前景英文口播；"
    "现场声留在旁白下面。"
)


def _sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def selected_segments(spec: dict) -> list[tuple[int, dict]]:
    """和 `foreground_audio_gate.inspect` 同一批窗口：有 start/end、不是静图。"""
    effects = reviewed_effects_mode.enabled(spec)
    rows: list[tuple[int, dict]] = []
    for index, seg in enumerate(spec.get("segments") or []):
        if str(seg.get("narration") or "").strip() and seg.get("quote"):
            raise ValueError(f"第{index + 1}段同时有旁白和原声")
        if ("start" in seg and "end" in seg and not seg.get("image")
                and (not effects or reviewed_effects_mode.raw_segment(seg))):
            rows.append((index, seg))
    return rows


def _inside(start: float, end: float, at: float, until: float) -> tuple[float, float]:
    """原声句子的绝对时间必须落在选用窗口里面，探出一点闸就拒。"""
    a = max(float(start) + float(at), float(start))
    b = min(float(start) + float(until), float(end))
    if not a < b:
        raise ValueError(f"原声字幕 {at}–{until} 落不进 {start}–{end}")
    return a, b


def utterances_for(seg: dict) -> list[dict]:
    raw = seg.get("quote")
    if not raw:
        return []
    rows = [{"text": raw}] if isinstance(raw, str) else list(raw)
    start, end = float(seg["start"]), float(seg["end"])
    duration = end - start
    spoken: list[dict] = []
    for i, row in enumerate(rows):
        if isinstance(row, str):
            at, until, text = 0.0, duration, row
        else:
            at = float(row["at"])
            until = float(row["end"]) if "end" in row else (
                float(rows[i + 1]["at"]) if i + 1 < len(rows) else duration)
            text = str(row.get("text") or "")
        en, zh = (text.split("\n", 1) + [""])[:2]
        if not en.strip() or not zh.strip():
            raise ValueError(f"原声字幕缺中或英：{text!r}")
        a, b = _inside(start, end, at, until)
        spoken.append({"start": a, "end": b, "en": en.strip(), "zh": zh.strip()})
    return spoken


def write_reviews(spec: dict, sources: dict[str, Path], *, root: Path,
                  reviewer: str, method: str = "listened_with_transcript") -> Path:
    """逐段写审听包，索引的 plan_sha256 按当前 spec 算。返回索引路径。"""
    slug = str(spec.get("slug") or "")
    urls = spec.get("sources") or {"": spec.get("source_url")}
    primary = next(iter(urls))
    folder = root / "data" / "audio_reviews" / slug
    folder.mkdir(parents=True, exist_ok=True)
    hashes = {key: _sha(path) for key, path in sources.items()}
    now = datetime.now(timezone.utc).isoformat()
    entries = []
    for index, seg in selected_segments(spec):
        key = str(seg.get("source", primary))
        spoken = utterances_for(seg)
        packet = {
            "source_url": urls[key],
            "source_sha256": hashes[key],
            "method": method,
            "reviewer": reviewer,
            "reviewed_at": now,
            "reviewed_from": float(seg["start"]),
            "reviewed_to": float(seg["end"]),
            "status": "complete",
            "uncertain_spans": [],
            "foreground_english": spoken,
        }
        if not spoken:
            packet["no_foreground_english_reason"] = NARRATION_REASON
        path = folder / f"{index:02d}-{key}.json"
        path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        rel = path.relative_to(root).as_posix()
        entries.append({
            "index": index,
            "transcript_path": rel,
            "transcript_sha256": _sha(path),
        })
    review = {
        "schema": SCHEMA,
        "plan_sha256": plan_hash(spec),
        "segments": entries,
    }
    index_path = root / "data" / "audio_reviews" / f"{slug}.json"
    index_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    require(spec, root=root, sources=sources)
    return index_path


def _cookies() -> list[str]:
    jar = os.environ.get("YT_COOKIES", "").strip()
    if jar and Path(jar).is_file():
        print(f"[cookies] 用 {jar}")
        return ["--cookies", jar]
    return []


def _exact_format(url: str, dest: Path, cookies: list[str]) -> bool:
    binary = shutil.which("yt-dlp") or shutil.which("yt_dlp")
    if not binary:
        print("[fail] 找不到 yt-dlp，跳过任务书那一档选择器")
        return False
    for label, extra in _ladder():
        proc = subprocess.run(
            [binary, *YTDLP_BASE, "--no-warnings", "-f", BRIEF_FMT,
             "--merge-output-format", "mp4", *cookies, *extra,
             "-o", str(dest), url],
            capture_output=True, text=True)
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            try:
                width, height = probe_size(dest)
            except (OSError, ValueError):
                dest.unlink(missing_ok=True)
                print(f"[fail] {label} 下到了文件，ffprobe 读不出视频")
                continue
            if height < MIN_SOURCE_H:
                dest.unlink(missing_ok=True)
                print(f"[低画质] {label} 任务书选择器只有 {width}×{height}")
                continue
            print(f"[ok] {label} 任务书选择器 {width}×{height}，"
                  f"{dest.stat().st_size / 1e6:.1f} MB")
            return True
        dest.unlink(missing_ok=True)
        why = " | ".join(
            line.strip() for line in (proc.stderr or "").splitlines()
            if line.startswith("ERROR"))[:240] or (proc.stderr or "")[-240:]
        print(f"[fail] {label} 任务书选择器：{why}")
    return False


def stage_one(key: str, url: str, dest: Path, cookies: list[str]) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        width, height = probe_size(dest)
        print(f"[skip] {key} 已有 {dest.name} {width}×{height}")
        return "already-present"
    if _exact_format(url, dest, cookies):
        _keep_source(url, dest)
        return "brief-avc1-1080"
    print(f"[fallback] {key} 改走 download()：{url}")
    download(url, dest)
    return "pipeline-download"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--reviewer", default="cursor cloud agent")
    args = parser.parse_args()
    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    urls = spec.get("sources") or {"": spec.get("source_url")}
    cookies = _cookies()
    notes: dict[str, str] = {}
    sources: dict[str, Path] = {}
    for key, url in urls.items():
        dest = outdir / (f"source_{key}.mp4" if key else "source.mp4")
        notes[key] = stage_one(str(key), str(url), dest, cookies)
        width, height = probe_size(dest)
        fps_expr, fps_value = resolve_fps(dest)
        print(f"[geometry] {key}: {width}×{height} @ {fps_expr} ({fps_value:.5f}) "
              f"duration-check via ffprobe next")
        sources[key] = dest
    (outdir / "source_fetch.json").write_text(
        json.dumps({"selector_first": BRIEF_FMT, "used": notes},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    root = TOOLS.parent
    index = write_reviews(spec, sources, root=root, reviewer=args.reviewer)
    print(f"[audio-review] {index} 通过 foreground_audio_gate.require")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
