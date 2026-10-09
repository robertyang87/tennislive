#!/usr/bin/env python3
"""Collect source-bound timed ASR evidence for this episode; never mark a review pass.

Run in the authorised GitHub Actions environment, using its existing source
cookie/cache setup. Inputs are a JSON object with sources {key: official URL}
and optional windows {key: [[absolute_start, absolute_end], ...]}. Omitting
windows transcribes the complete source. Results are small JSON files suitable
for git; downloaded video/audio stay outside the result directory.

python docs/production/shanghai-masters-history-2026/collect_audio_evidence.py \
  --plan PLAN.json --outdir docs/production/shanghai-masters-history-2026/audio-evidence

Needs the existing tennislive dependencies, yt-dlp, ffmpeg, faster-whisper.
Evidence must subsequently be inspected and translated by the actual reviewer;
this collector does not create data/audio_reviews or status=complete assertions.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))


def sha(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def provider_captions(url: str, dest: Path) -> dict:
    """Keep the provider's original payload; never convert away word/end timing."""
    from build_match_reel import YTDLP_BASE, _ladder

    binary = shutil.which("yt-dlp")
    if binary is None:
        raise RuntimeError("yt-dlp missing")
    cookie_path = os.environ.get("YT_COOKIES", "")
    cookies = ["--cookies", cookie_path] if cookie_path and Path(cookie_path).is_file() else []
    attempts = []
    for label, extra in _ladder():
        command = [binary, *YTDLP_BASE, "--skip-download", "--write-auto-subs",
                   "--write-subs", "--sub-langs", "en.*,en",
                   "--sub-format", "json3/vtt/best", "-o",
                   str(dest / "provider.%(ext)s"), url, *cookies, *extra]
        result = subprocess.run(command, capture_output=True, text=True)
        files = sorted(dest.glob("provider*.json3")) + sorted(dest.glob("provider*.vtt"))
        attempts.append({"client": label, "returncode": result.returncode,
                         "stderr_tail": result.stderr[-2500:]})
        if files:
            return {"status": "collected", "files": [
                {"file": path.name, "sha256": sha(path), "bytes": path.stat().st_size}
                for path in files], "attempts": attempts}
    return {"status": "not_collected", "attempts": attempts,
            "note": "No successful payload; do not infer that this source has no captions."}


def tail_contact_sheets(source: Path, dest: Path, duration: float, tail: float) -> dict:
    """Exact-seek 1080p candidates one second apart; commit compact timestamp walls."""
    from PIL import Image, ImageDraw, ImageFont

    seconds = list(range(max(0, int(duration-tail)), max(0, int(duration))))
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 24) if font_path.is_file() else ImageFont.load_default()
    walls = []
    with tempfile.TemporaryDirectory(prefix="shanghai-tail-frames-") as directory:
        for chunk_index in range(0, len(seconds), 40):
            chunk = seconds[chunk_index:chunk_index+40]
            wall = Image.new("RGB", (1920, ((len(chunk)+3)//4)*300), "#071225")
            for index, second in enumerate(chunk):
                frame = Path(directory)/"frame.jpg"
                # Input seek plus accurate_seek discards the keyframe lead-in.
                # Avoid decoding each complete source again for every candidate.
                subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                                "-ss", str(second), "-accurate_seek", "-i", str(source), "-frames:v", "1",
                                "-q:v", "2", str(frame)], check=True)
                with Image.open(frame) as raw:
                    tile = raw.convert("RGB").resize((480, 270), Image.Resampling.LANCZOS)
                x, y = (index%4)*480, (index//4)*300
                wall.paste(tile, (x, y))
                ImageDraw.Draw(wall).text((x+10, y+273), f"SOURCE {second:.2f}s", font=font, fill="white")
            path = dest/f"tail-contact-{chunk_index//40:02d}.jpg"
            wall.save(path, quality=92)
            walls.append({"file": path.name, "source_seconds": chunk})
    return {"method": "ffmpeg input seek with accurate_seek; one source second per candidate",
            "tail_seconds": tail, "walls": walls,
            "note": "Contact walls aid EDL inspection; they do not establish full-point boundaries alone."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--plan", type=Path)
    inputs.add_argument("--manifest", type=Path)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--models", nargs=2, default=["small.en", "medium.en"])
    parser.add_argument("--only", nargs="+", help="Only these source IDs, in this order")
    parser.add_argument("--cpu-threads", type=int, default=2)
    parser.add_argument("--tail-seconds", type=float, default=45)
    args = parser.parse_args()
    if args.models[0] == args.models[1]:
        parser.error("Independent ASR evidence needs two different models")
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        videos = [row for row in manifest["videos"]
                  if "youtube.com/" in row.get("url", "") or "youtu.be/" in row.get("url", "")]
        plan = {"sources": {row["id"]: row["url"] for row in videos}}
    else:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    sources = plan["sources"]
    if args.only:
        sources = {key: sources[key] for key in args.only}
    if not sources or not all(re.fullmatch(r"[a-z0-9-]+", key) for key in sources):
        parser.error("sources must be nonempty with safe lowercase source keys")

    from tennislive.localca import trust_local_proxy_ca
    trust_local_proxy_ca()
    from build_match_reel import download, probe_duration, probe_size
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps

    args.outdir.mkdir(parents=True, exist_ok=True)
    models = {name: WhisperModel(name, device="cpu", compute_type="int8",
                                cpu_threads=args.cpu_threads, num_workers=2)
              for name in args.models}
    with tempfile.TemporaryDirectory(prefix="shanghai-audio-evidence-") as temporary:
        work = Path(temporary)
        for key, url in sources.items():
            source_dir = args.outdir/key
            source_dir.mkdir(parents=True, exist_ok=True)
            source = download(url, work / f"source-{key}.mp4")
            source_hash = sha(source)
            duration = probe_duration(source)
            width, height = probe_size(source)
            metadata = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=codec_name,codec_type,width,height,r_frame_rate,sample_rate,channels:format=duration,size",
                "-of", "json", str(source)], text=True))
            write(source_dir/"source.json", {
                "source_url": url, "source_sha256": source_hash,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata,
                "provider_captions": provider_captions(url, source_dir),
                "status": "collected_awaiting_evidence_review",
            })
            windows = plan.get("windows", {}).get(key, [[0, duration]])
            for index, pair in enumerate(windows):
                start, end = map(float, pair)
                if not 0 <= start < end <= duration + .01:
                    raise ValueError(f"{key}: window {pair} outside 0–{duration}")
                audio = work / f"{key}-{index:02d}.wav"
                subprocess.run([
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(start), "-i", str(source), "-t", str(end-start),
                    "-vn", "-ac", "1", "-ar", "16000", str(audio),
                ], check=True)
                common = {
                    "source_url": url, "source_sha256": source_hash,
                    "source_dimensions": [width, height], "source_duration": duration,
                    "window": [start, end], "audio_sha256": sha(audio),
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                    "status": "collected_awaiting_evidence_review",
                    "timecode_basis": "absolute_source_seconds",
                }
                outputs = {}
                for name, model in models.items():
                    segments, info = model.transcribe(
                        str(audio), language="en", beam_size=5,
                        word_timestamps=True, vad_filter=False,
                        condition_on_previous_text=False,
                    )
                    rows = []
                    for segment in segments:
                        rows.append({
                            "start": start + segment.start, "end": start + segment.end,
                            "text": segment.text.strip(),
                            "avg_logprob": segment.avg_logprob,
                            "no_speech_prob": segment.no_speech_prob,
                            "words": [{"start": start + word.start,
                                       "end": start + word.end,
                                       "word": word.word, "probability": word.probability}
                                      for word in segment.words or []],
                        })
                    payload = {**common, "method": "faster_whisper_raw_asr",
                               "model": name, "language": info.language,
                               "language_probability": info.language_probability,
                               "vad_filter": False, "segments": rows}
                    dest = source_dir / f"window-{index:02d}-{name}.json"
                    write(dest, payload)
                    outputs[name] = rows
                    print(f"{key} {start:.2f}–{end:.2f} {name}: {dest}")
                    for row in rows:
                        print(f"  {row['start']:.2f}–{row['end']:.2f} {row['text']}")
                samples = decode_audio(str(audio), sampling_rate=16000)
                speech = get_speech_timestamps(samples, VadOptions(), sampling_rate=16000)
                token_lists = [re.findall(r"[a-z0-9]+", " ".join(
                    row["text"] for row in outputs[name]).lower()) for name in args.models]
                matcher = difflib.SequenceMatcher(None, *token_lists, autojunk=False)
                findings = [{"kind": tag, "first": token_lists[0][a:b],
                             "second": token_lists[1][c:d]}
                            for tag, a, b, c, d in matcher.get_opcodes() if tag != "equal"]
                write(source_dir / f"window-{index:02d}-crosscheck.json", {
                    **common, "models": args.models,
                    "token_similarity": matcher.ratio(), "differences": findings,
                    "speech_vad": [{"start": start + row["start"]/16000,
                                    "end": start + row["end"]/16000} for row in speech],
                    "review_note": "Inspect both timed transcripts, source captions and VAD. "
                                   "Agreement does not certify a human listening pass. "
                                   "Unresolved wording or timing remains blocked.",
                })
            if args.tail_seconds > 0:
                write(source_dir/"tail-contact.json", tail_contact_sheets(
                    source, source_dir, duration, args.tail_seconds))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
