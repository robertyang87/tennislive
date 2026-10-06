#!/usr/bin/env python3
"""Preserve actual Shanghai render inputs before workflow cleanup; no tone pass."""
import argparse
import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.spec.stem != "shanghai-masters-history-2026":
        raise SystemExit("This preservation step is scoped to Shanghai history.")
    here = Path(__file__).parent
    old = json.loads((here / "inventory.json").read_text())
    queue = json.loads((here / "review-queue.json").read_text())
    spec = json.loads(args.spec.read_text())
    render = json.loads((args.outdir / "render.json").read_text())
    records = []
    for i, seg in enumerate(spec["segments"]):
        text = str(seg.get("narration") or "").strip()
        if text:
            records.append({"final_segment_index": i, "text": text,
                            "audio_name": f"voice_{i:02d}.mp3"})
    cover_text = str((spec.get("cover") or {}).get("narration") or "").strip()
    if cover_text:
        records.append({"kind": "cover", "text": cover_text, "audio_name": "voice_cover.mp3"})
    old_outro = next(r for r in old["audio_records"] if r.get("kind") == "outro")
    records.append({"kind": "outro", "text": old_outro["text"], "audio_name": "voice_outro.mp3"})
    missing = [r["audio_name"] for r in records if not (args.outdir / r["audio_name"]).is_file()]
    if missing:
        raise SystemExit("Missing actual production MP3s: " + ", ".join(missing))
    args.output.mkdir(parents=True, exist_ok=True)
    audio_dir = args.output / "audio"
    audio_dir.mkdir(exist_ok=True)
    for r in records:
        src = args.outdir / r["audio_name"]
        shutil.copyfile(src, audio_dir / src.name)
        r["audio_file"] = "audio/" + src.name
        r["audio_sha256"] = sha(src)
        prior = next((x for x in old["audio_records"]
                      if (x.get("final_segment_index") == r.get("final_segment_index")
                          and "final_segment_index" in r)
                      or (r.get("kind") and x.get("kind") == r["kind"])), None)
        r["previous_audio_sha256"] = prior["audio_sha256"] if prior else None
        r["same_sha_as_previous_inventory"] = bool(prior and r["audio_sha256"] == prior["audio_sha256"])
        r["same_narration_as_previous_inventory"] = bool(prior and r["text"] == prior["text"])
        r["previous_evidence_bound_by_sha_and_text"] = bool(
            r["same_sha_as_previous_inventory"] and r["same_narration_as_previous_inventory"])
        words = src.with_suffix(".words.json")
        r["word_boundary_file"] = None
        if words.is_file():
            shutil.copyfile(words, audio_dir / words.name)
            r["word_boundary_file"] = "audio/" + words.name
            r["word_boundary_sha256"] = sha(words)
        r["human_listened"] = False
        r["publishing_voice_pass"] = False
    for name in ("render.json", "render_inputs.json"):
        src = args.outdir / name
        if src.is_file():
            shutil.copyfile(src, args.output / name)
    shutil.copyfile(args.spec, args.output / "rendered-spec.json")
    for item in queue["items"]:
        seg = item["segment"]
        rec = next(r for r in records if
                   (r.get("final_segment_index") == seg if isinstance(seg, int) else r.get("kind") == seg))
        item["previous_source_audio_sha256"] = item["source_audio_sha256"]
        item["source_audio_sha256"] = rec["audio_sha256"]
        item["source_audio_relative"] = rec["audio_file"]
        item["narration"] = rec["text"]
        item["previous_evidence_bound_by_sha_and_text"] = rec["previous_evidence_bound_by_sha_and_text"]
        if not rec["previous_evidence_bound_by_sha_and_text"]:
            item["previous_window_seconds"] = item["source_window_seconds"]
            item["source_window_seconds"] = None
            item["prior_verdict"] = "historical_only_" + item["prior_verdict"]
            item["status"] = "pending_fresh_audio_review"
    queue["rendered_spec_sha256"] = sha(args.spec)
    queue["render_commit"] = os.environ.get("GITHUB_SHA")
    queue["source_generation"] = "actual_rerender_audio"
    dump(args.output / "review-queue.json", queue)
    shutil.copyfile(here / "build_listening_pack.py", args.output / "build_listening_pack.py")
    manifest = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "render_commit": os.environ.get("GITHUB_SHA"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "spec_sha256": sha(args.spec),
        "previous_spec_sha256": old["locked_spec_sha256"],
        "voice": render.get("narration_voice"),
        "rate": render.get("narration_rate"),
        "backend": render.get("narration_backend"),
        "film_file": args.spec.stem + ".mp4",
        "film_sha256": (sha(args.outdir / (args.spec.stem + ".mp4"))
                        if (args.outdir / (args.spec.stem + ".mp4")).is_file() else None),
        "render_metadata_sha256": sha(args.outdir / "render.json"),
        "actual_audio_files": len(records),
        "same_sha_and_text_as_previous": sum(r["previous_evidence_bound_by_sha_and_text"] for r in records),
        "human_listened": False,
        "publishing_voice_pass": False,
        "audio_records": records,
        "note": "Preservation and text/SHA binding only; no pronunciation verdict is promoted."
    }
    dump(args.output / "actual-audio-inventory.json", manifest)
    print(json.dumps({k: manifest[k] for k in (
        "actual_audio_files", "same_sha_and_text_as_previous", "human_listened", "publishing_voice_pass")}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
