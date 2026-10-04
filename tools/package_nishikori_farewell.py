#!/usr/bin/env python3
"""Package the actual farewell producer output; never attest QC or publish.

The producer recipe supplies measured segment offsets/lengths, artifact hashes,
and eight actual narration units. Missing production evidence is a hard stop.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from urllib.parse import unquote, urlparse

import foreground_audio_gate
import render_inputs

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def local(value: str | Path) -> Path:
    p = Path(value)
    return p if p.is_absolute() else ROOT / p


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=ROOT / "specs/reels/nishikori-career-farewell.json")
    parser.add_argument("--movie", type=Path, required=True)
    parser.add_argument("--poster", type=Path, required=True)
    parser.add_argument("--ass", type=Path, required=True)
    parser.add_argument("--xhs", type=Path, required=True, help="The approved local copy, copied verbatim")
    parser.add_argument("--recipe", type=Path, required=True, help="Actual producer measurements and artifact hashes")
    parser.add_argument("--source-map", type=Path, default=ROOT / "work/publication-assets/compact-native-binding/source-paths-map.json")
    parser.add_argument("--video-url", required=True, help="Canonical planned GitHub Release asset URL; this tool does not upload")
    parser.add_argument("--outdir", type=Path)
    args = parser.parse_args()
    for p in [args.spec, args.movie, args.poster, args.ass, args.xhs, args.recipe, args.source_map]:
        require(p.is_file(), f"Not ready: required production input missing: {p}")
    spec = json.loads(args.spec.read_text())
    recipe = json.loads(args.recipe.read_text())
    edl_path = local(spec["scene_edl_recipe"])
    require(edl_path.is_file(), "The actual scene EDL is missing")
    edl = json.loads(edl_path.read_text())
    slug = spec["slug"]
    require(slug == "nishikori-career-farewell", "This helper only packages the reviewed farewell")
    require(len(spec["segments"]) == 31, "Expected the actual 31-segment final recipe")
    require(recipe.get("spec_sha256") == digest(args.spec), "Producer recipe does not bind the frozen spec bytes")
    require(recipe.get("film_sha256") == digest(args.movie), "Producer recipe does not bind the actual final movie")
    require(recipe.get("subtitles_sha256") == digest(args.ass), "Producer recipe does not bind the final merged ASS")
    require(recipe.get("subtitles_burned") is True, "Producer must record the actual burned subtitle chain")
    timeline = recipe["timeline"]
    offsets, lengths = timeline["offsets"], timeline["lengths"]
    require(len(offsets) == len(lengths) == 31, "Producer must measure every actual segment")
    cover, outro = timeline["cover_seconds"], timeline["outro_seconds"]
    require(cover == outro == 0, "Intro and brand are real segments; do not add another cover/outro")
    cursor = float(cover)
    for i, (seg, offset, length) in enumerate(zip(spec["segments"], offsets, lengths)):
        require(isinstance(offset, (int, float)) and isinstance(length, (int, float)), "Timeline values must be numbers")
        require(math.isfinite(offset) and math.isfinite(length) and length > 0, "Invalid actual segment measurement")
        require(math.isclose(offset, cursor, abs_tol=.001), f"Actual timeline gap/overlap at segment {i}")
        expected = float(seg["seconds"]) if seg.get("image") else (float(seg["end"]) - float(seg["start"])) / float(seg.get("speed") or 1)
        require(math.isclose(length, expected, abs_tol=.001), f"Measured segment {i} differs from the actual source recipe")
        cursor += length
    require(math.isclose(cursor, 323.48, abs_tol=.001), "Unexpected final producer duration; review changes before packaging")
    narration = recipe["narration"]
    require(narration.get("backend") in {"edge", "edge-tts"}, "Must record the actual Edge narration backend")
    units = narration["units"]
    require(len(units) == 8, "Expected eight actual author narration units")
    declared_units = spec["narration_audio_recipe"]
    require(len(declared_units) == len(units), "The consumed narration recipe differs from the spec")
    for actual, declared in zip(units, declared_units):
        require(digest(local(actual["audio"])) == digest(local(declared["audio"]))
                and digest(local(actual["marks"])) == digest(local(declared["marks"])),
                "Producer MP3/marks differ from the declared real inputs")
    narration_seconds: dict[str, float] = {}
    for unit in units:
        i = int(unit["segment"])
        require(0 <= i < 31 and str(spec["segments"][i].get("narration") or "").strip(), "Narration unit must name its actual narrated segment")
        audio, marks = local(unit["audio"]), local(unit["marks"])
        require(audio.is_file() and marks.is_file(), "Actual MP3/marks inputs missing")
        require(unit["audio_sha256"] == digest(audio) and unit["marks_sha256"] == digest(marks), "Actual narration bytes differ from the producer recipe")
        require(float(unit["seconds"]) > 0, "Invalid narration unit")
        narration_seconds[str(i)] = narration_seconds.get(str(i), 0) + float(unit["seconds"])
    require(math.isclose(sum(narration_seconds.values()), 53.304, abs_tol=.01), "Actual author audio duration differs from the reviewed production")
    probe = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(args.movie)]))
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    require((video["width"], video["height"]) == (1080, 1440), "Actual film must be 1080x1440")
    require(video["avg_frame_rate"] in {"25/1", "50/2"}, "Actual film must be 25fps")
    require(int(audio["sample_rate"]) == 48000 and audio["channels"] == 2, "Actual film must carry 48k stereo")
    require(abs(float(probe["format"]["duration"]) - cursor) <= .08, "Actual movie length differs from measured producer axis")
    url = urlparse(args.video_url)
    require(url.scheme == "https" and url.netloc == "github.com" and "/releases/download/" in url.path and not url.query, "Expected the canonical Release URL, not a signed CDN redirect")
    require(unquote(url.path.rsplit("/", 1)[-1]) == slug + ".mp4", "Release asset name must match the packaged movie")
    paths = {key: local(value) for key, value in json.loads(args.source_map.read_text()).items()}
    # Hard source/packet gate runs before output copies or metadata writes.
    required_cues = foreground_audio_gate.require(spec, root=ROOT, sources=paths)
    require(len([s for s in spec["segments"] if "start" in s and "end" in s and not s.get("image")]) == 26, "Expected all 26 original-audio windows")
    out = args.outdir or ROOT / "output/2026-10-04/reel" / slug
    out.mkdir(parents=True, exist_ok=True)
    require(not (out / "qc_attestation.json").exists(), "Existing QC attestation: use a fresh output directory rather than invalidate reviewed bytes")
    require(not (out / "public_asset_verification.json").exists(), "Existing public verification: use a fresh output directory rather than retain stale publication proof")
    movie = out / f"{slug}.mp4"
    for src, target in [(args.movie, movie), (args.poster, out / "poster.jpg"), (args.ass, out / "subtitles.ass"), (args.xhs, out / "xiaohongshu.txt")]:
        if src.resolve() != target.resolve():
            shutil.copyfile(src, target)
    if args.recipe.resolve() != (out / "producer_recipe.json").resolve():
        shutil.copyfile(args.recipe, out / "producer_recipe.json")
    (out / "ffprobe.json").write_text(json.dumps(probe, ensure_ascii=False, indent=2) + "\n")
    foreground_audio_gate.bind_sources(spec, paths, out, root=ROOT)
    foreground_audio_gate.record_timeline(spec, out, cover, offsets, lengths)
    meta = {
        "slug": slug, "cover_seconds": cover, "outro_seconds": outro,
        "segments_seconds": sum(lengths), "film_seconds": float(probe["format"]["duration"]),
        "layout": spec.get("layout") or "full", "narration_backend": "edge",
        "producer_narration_backend": narration["backend"], "narration_units": units, "narration_voice": "zh-CN-YunjianNeural",
        "narration_seconds": narration_seconds, "actual_author_seconds": sum(narration_seconds.values()),
        "film_sha256": digest(movie), "film_bytes": movie.stat().st_size,
        "video_bytes": movie.stat().st_size, "video_url": args.video_url,
        "public_assets_verified": False, "status": "packaged_pending_actual_native_l2",
        "producer_recipe_sha256": digest(out / "producer_recipe.json"),
        "scene_edl_sha256": digest(edl_path),
        "required_english_cue_count": len(required_cues),
    }
    (out / "render.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    render_inputs.record(args.spec, out, movie, ROOT)
    print(json.dumps({"output": str(out), "film_sha256": meta["film_sha256"], "status": "packaged_pending_actual_native_l2", "qc_attestation_created": False, "uploaded": False, "pushed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
