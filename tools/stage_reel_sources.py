#!/usr/bin/env python3
"""把已实际审听的同一份源片字节落到 outdir，保留原始审听证据。

渲染入口先 `require()` 再下载，下载之后 `bind_sources()` 再拿 sha256 对账。
两次下载的 mp4 容器时间戳经常不一样，所以不能把新下载的 SHA 写进旧审听结论：
先落到 `outdir/source_<键>.mp4`，`render()` 见到文件就跳过重下。

有真实审听记录时，优先取 `source_fallbacks` 里本仓库的 source Release，逐字节对 SHA。
不能把不同下载容器重新标成已审听。没有需绑定的源片时，选择器先用
`bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]`。这一档匹配不上
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
import requests
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
    spec_source_fallbacks,
)
from foreground_audio_gate import require  # noqa: E402

BRIEF_FMT = "bv*[height<=1080][vcodec^=avc1]+ba[ext=m4a]"


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


def write_reviews(spec: dict, sources: dict[str, Path], *, root: Path,
                  reviewer: str, method: str = "listened_with_transcript") -> Path:
    """Compatibility name: verify existing evidence; never invent a review."""
    require(spec, root=root, sources=sources)
    return root / "data" / "audio_reviews" / f"{spec.get('slug')}.json"


def reviewed_source_hashes(spec: dict, *, root: Path) -> dict[str, str]:
    """Read hashes only after the native complete-plan/evidence gate passes."""
    require(spec, root=root)
    selected = dict(selected_segments(spec))
    if not selected:
        return {}
    index_path = root / "data/audio_reviews" / f"{spec.get('slug')}.json"
    # The native explicitly approved narration-only mode has its own gate.
    if not index_path.exists():
        return {}
    urls = spec.get("sources") or {"": spec.get("source_url")}
    primary = next(iter(urls))
    result = {}
    for entry in json.loads(index_path.read_text())["segments"]:
        if entry["index"] not in selected:
            continue
        key = str(selected[entry["index"]].get("source", primary))
        packet = json.loads((root / entry["transcript_path"]).read_text())
        digest = packet["source_sha256"]
        if key in result and result[key] != digest:
            raise ValueError("waiting_audio_review：同一源片的审听窗口绑定了不同字节")
        result[key] = digest
    return result


def fetch_reviewed_release(url: str, dest: Path, expected_sha: str) -> None:
    """Fetch a public immutable source asset, verify before replacing a file."""
    if not url.startswith("https://github.com/robertyang87/tennislive/releases/download/source-"):
        raise ValueError("waiting_audio_review：已审听源片备用地址必须是本仓库 source Release")
    partial = dest.with_name(dest.name + ".reviewed.part")
    digest = hashlib.sha256()
    try:
        with requests.get(url, stream=True, timeout=(15, 120)) as response:
            response.raise_for_status()
            with partial.open("wb") as handle:
                for block in response.iter_content(1024 * 1024):
                    handle.write(block)
                    digest.update(block)
        if digest.hexdigest() != expected_sha:
            raise ValueError("waiting_audio_review：备用源片字节不是审听过的版本")
        partial.replace(dest)
    finally:
        partial.unlink(missing_ok=True)


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


def stage_one(key: str, url: str, dest: Path, cookies: list[str], *,
              expected_sha: str | None = None, fallback: str | None = None) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        if expected_sha is not None and _sha(dest) != expected_sha:
            raise ValueError("waiting_audio_review：现存源片字节不是审听过的版本")
        width, height = probe_size(dest)
        print(f"[skip] {key} 已有 {dest.name} {width}×{height}")
        return "already-present"
    if expected_sha is not None and fallback:
        fetch_reviewed_release(fallback, dest, expected_sha)
        return "exact-reviewed-source-release"
    if _exact_format(url, dest, cookies):
        if expected_sha is not None and _sha(dest) != expected_sha:
            raise ValueError("waiting_audio_review：下载的源片字节不是审听过的版本")
        _keep_source(url, dest)
        return "brief-avc1-1080"
    print(f"[fallback] {key} 改走 download()：{url}")
    download(url, dest)
    if expected_sha is not None and _sha(dest) != expected_sha:
        raise ValueError("waiting_audio_review：下载的源片字节不是审听过的版本")
    return "pipeline-download"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--spec", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--reviewer", default="", help="兼容旧参数；不创建或修改审听声明")
    args = parser.parse_args()
    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    urls = spec.get("sources") or {"": spec.get("source_url")}
    root = TOOLS.parent
    hashes = reviewed_source_hashes(spec, root=root)
    fallbacks = spec_source_fallbacks(spec)
    cookies = _cookies()
    notes: dict[str, str] = {}
    sources: dict[str, Path] = {}
    for key, url in urls.items():
        dest = outdir / (f"source_{key}.mp4" if key else "source.mp4")
        notes[key] = stage_one(str(key), str(url), dest, cookies,
                               expected_sha=hashes.get(key), fallback=fallbacks.get(key))
        width, height = probe_size(dest)
        fps_expr, fps_value = resolve_fps(dest)
        print(f"[geometry] {key}: {width}×{height} @ {fps_expr} ({fps_value:.5f}) "
              f"duration-check via ffprobe next")
        sources[key] = dest
    (outdir / "source_fetch.json").write_text(
        json.dumps({"selector_first": BRIEF_FMT, "used": notes},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    index = write_reviews(spec, sources, root=root, reviewer=args.reviewer)
    print(f"[audio-review] {index} 通过 foreground_audio_gate.require")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
