#!/usr/bin/env python3
"""Synthesize locked story chapters via the shared production TTS helper.

Keep editorial narration separate from pronounce-adjusted spoken text and marks.
No publishing, repository writes or alternative TTS network routes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennislive.video import azure_tts  # noqa: E402
from tennislive.video.explainer import speakable  # noqa: E402
from tennislive.video.tts import tts_one  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synth(text: str, target: Path, *, voice: str, rate: str, pitch: str) -> dict:
    spoken = speakable(text)
    backend = "azure" if azure_tts.available() else "edge"
    marks = tts_one(speakable(text), target, voice, rate, pitch)
    if not marks:
        raise RuntimeError(f"No word boundaries for {target.name}")
    words = target.with_suffix(".words.json")
    words.write_text(json.dumps(marks, ensure_ascii=False, indent=2) + "\n")
    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(target),
    ], text=True).strip())
    if duration <= 0 or not target.stat().st_size:
        raise RuntimeError(f"Empty audio for {target.name}")
    return {
        "audio": target.name, "words": words.name,
        "duration_seconds": duration, "bytes": target.stat().st_size,
        "sha256": sha(target.read_bytes()), "words_sha256": sha(words.read_bytes()),
        "voice": voice, "rate": rate, "pitch": pitch, "backend": backend,
        "text_hash": sha(text.encode()), "spoken_text_hash": sha(spoken.encode()),
        "narration": text, "spoken_text": spoken, "word_count": len(marks),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, default=Path("work/story-narration"))
    parser.add_argument("--voice", default="zh-CN-YunjianNeural")
    parser.add_argument("--rate", default="+22%")
    parser.add_argument("--pitch", default="+0Hz")
    args = parser.parse_args()
    data = json.loads(args.script.read_text())
    chapters = data.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError("Script must contain nonempty chapters")
    ids = [c.get("id", "") for c in chapters]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z0-9_-]+", i) for i in ids):
        raise ValueError("Chapter IDs must be unique safe filenames")
    if any(not isinstance(c.get("narration"), str) or not c["narration"].strip() for c in chapters):
        raise ValueError("Every chapter requires narration")
    args.outdir.mkdir(parents=True, exist_ok=True)
    params = dict(voice=args.voice, rate=args.rate, pitch=args.pitch)
    sample = synth("从深圳到贝尔格莱德，她一步一步走到北京。", args.outdir / "sample.mp3", **params)

    def one(chapter: dict) -> dict:
        result = synth(chapter["narration"], args.outdir / f"{chapter['id']}.mp3", **params)
        return dict(id=chapter["id"], title=chapter.get("title", ""), **result)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(one, chapters))
    manifest = {
        "script_path": str(args.script), "script_sha256": sha(args.script.read_bytes()),
        "sample": sample, "chapters": results, "max_workers": 2,
        "total_narration_seconds": sum(c["duration_seconds"] for c in results),
        "subtitle_policy": "Readable narration preserved separately; words track the actual speakable text.",
        "audio_review": "not_listened", "publishing_performed": False,
    }
    (args.outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Synthesized {len(results)} chapters, {manifest['total_narration_seconds']:.2f}s")


if __name__ == "__main__":
    main()
