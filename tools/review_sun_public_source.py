"""One fixed public WTA source; local inference evidence, never publication approval."""
import os

for _flag in ("ORT_DISABLE_TELEMETRY", "HF_HUB_DISABLE_TELEMETRY", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
    if os.environ.get(_flag) != "1":
        raise SystemExit(f"{_flag}=1 is required before process startup")

import argparse
import ast
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import importlib.metadata
import json
import math
from pathlib import Path
import re
import signal
import subprocess
import time
from typing import Callable
from urllib.parse import urlsplit
import urllib.request
import wave

PAGE = "https://www.wtatennis.com/videos/4585115/junior-no-1-sun-xinran-advances-on-wta-debut-in-beijing-as-lys-retires"
VIDEO_ID = "6406022752112"
SOURCE_BYTES = 54561507
SOURCE_SHA = "bc607f1100401b0623ebbd90761d5263d024294c2d0daaefd8ead03f1e7ff390"
SOURCE_SECONDS = 204.843333
RESOLVER_SHA = "1b345431dccf751614f88ebfce93f38fce3126e52fa7d7ba42a9f4eb84ae1e04"
BRANCH = "preview/native-asr-sun-20261001"
MODEL_ID = "Systran/faster-whisper-medium.en"
REVISION = "a29b04bd15381511a9af671baec01072039215e3"
MODEL_FILES = {
    "config.json": (2643, "4a1848ebabe7938d9797c15a2e8e4ce1d36e6fd4a43d096ae5955257c67c7962"),
    "model.bin": (1527904330, "11b220779aea4c6f3ce9d2549c8a95ea869ed84066864b999531ef53e594fe5b"),
    "tokenizer.json": (2128466, "929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df"),
    "vocabulary.txt": (422309, "ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf"),
}
WINDOWS = tuple((start, min(start + 30.0, SOURCE_SECONDS)) for start in range(0, 190, 27))
METADATA_BYTES = 2 * 1024 * 1024
FLAGS = {"raw_audio_uploaded": False, "external_asr_api": False, "audio_review_pass": False, "publication_eligible": False}
MEDIA_HOST = "fastly-signed-us-east-1-prod.brightcovecdn.com"
MODEL_HOSTS = frozenset({"huggingface.co", "cdn-lfs.huggingface.co", "cdn-lfs-us-1.huggingface.co", "cdn-lfs-eu-1.huggingface.co", "cas-bridge.xethub.hf.co", "us.aws.cdn.hf.co"})


class Blocked(RuntimeError):
    """Only fixed error codes may leave this process."""


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise Blocked("time_limit")
    return value


@contextmanager
def total_limit(seconds):
    if signal.getitimer(signal.ITIMER_REAL)[0]:
        raise Blocked("existing_timer")
    def expired(*_):
        raise Blocked("time_limit")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def safe_url(url, hosts):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password or parsed.port not in (None, 443):
        error = Blocked("url_not_approved")
        error.safe_host = parsed.hostname if parsed.hostname and re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname) else "redacted"
        raise error


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise Blocked("http_redirect_rejected")


class ModelRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl, MODEL_HOSTS)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_public(url, headers, deadline, *, model=False):
    # No cookie processor, .netrc, account credentials, retries, or alternate source.
    opener = urllib.request.build_opener(ModelRedirect() if model else NoRedirect())
    request = urllib.request.Request(url, headers=headers)
    try:
        response = opener.open(request, timeout=min(25, remaining(deadline)))
        if response.status != 200:
            response.close()
            raise Blocked("public_http_rejected")
        return response
    except Blocked:
        raise
    except Exception:
        raise Blocked("public_http_rejected") from None


def read_metadata(url, headers, deadline):
    payload = bytearray()
    with open_public(url, headers, deadline) as response:
        while block := response.read(65536):
            remaining(deadline)
            if len(payload) + len(block) > METADATA_BYTES:
                raise Blocked("metadata_size_limit")
            payload.extend(block)
    return bytes(payload)


class Response:
    def __init__(self, raw):
        self.text = raw.decode("utf-8")
    def raise_for_status(self):
        pass  # Bounded HTTP reader has already enforced status 200.
    def json(self):
        return json.loads(self.text)


def native_resolver(path):
    # Load only unchanged native WTA definitions; do not import the renderer or APIs.
    path = Path(path)
    if path.is_symlink() or not path.is_file() or sha(path) != RESOLVER_SHA:
        raise Blocked("native_resolver_sha_mismatch")
    names = {"WTA_ACCOUNT", "WTA_PLAYER", "_BC_GUID", "_DESCRIPTION", "_THUMBNAIL", "_DATE_PUBLISHED", "_POLICY_KEY", "OfficialVideoCandidate", "OfficialVideoMetadata", "_response_text", "_decode_json_string", "fetch_wta_video_metadata"}
    nodes = [n for n in ast.parse(path.read_text()).body if getattr(n, "name", None) in names or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    namespace = {"dataclass": dataclass, "html": html, "json": json, "re": re, "Callable": Callable, "VideoPipelineError": Blocked, "__name__": __name__}
    # Native default get is never used: every request receives the bounded adapter.
    namespace["requests"] = type("NoDefaultHTTP", (), {"get": None})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "pinned-native-wta-resolver", "exec"), namespace)
    return namespace


def resolve_source(resolver, deadline):
    player = "https://players.brightcove.net/6041795521001/te01Hqw71_default/index.min.js"
    api = f"https://edge.api.brightcove.com/playback/v1/accounts/6041795521001/videos/{VIDEO_ID}"
    def get(target, headers=None, timeout=25):
        if target not in {PAGE, player, api}:
            raise Blocked("resolver_endpoint_not_approved")
        if any(k.lower() in {"cookie", "authorization"} for k in (headers or {})):
            raise Blocked("account_auth_forbidden")
        response = Response(read_metadata(target, headers or {}, deadline))
        if target == PAGE:
            match = resolver["_BC_GUID"].search(html.unescape(response.text))
            if not match or match.group("guid") != VIDEO_ID:
                raise Blocked("source_video_id_mismatch")
        if target == api and str(response.json().get("id", "")) != VIDEO_ID:
            raise Blocked("source_video_id_mismatch")
        return response
    candidate = resolver["OfficialVideoCandidate"]("Sun Xinran vs. Eva Lys, Beijing R1", PAGE)
    meta = resolver["fetch_wta_video_metadata"](candidate, get=get, timeout=25)
    if (meta.source_width, meta.source_height) != (1280, 720) or abs(meta.duration_ms / 1000 - SOURCE_SECONDS) > 0.1:
        raise Blocked("source_metadata_mismatch")
    # Native ranking chooses highest progressive MP4. HLS is never fetched.
    url = meta.fallback_url or meta.playback_url
    safe_url(url, {MEDIA_HOST})
    return url


def download_exact(url, path, size, digest, deadline, *, model=False):
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise Blocked("output_already_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open_public(url, {"User-Agent": "tennislive-public-source-asr/1"}, deadline, model=model) as response, path.open("xb") as output:
        while block := response.read(1024 * 1024):
            remaining(deadline)
            count += len(block)
            if count > size:
                raise Blocked("download_size_limit")
            output.write(block)
    if count != size or sha(path) != digest:
        raise Blocked("download_size_or_sha_mismatch")


def verify_source(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size != SOURCE_BYTES or sha(path) != SOURCE_SHA:
        raise Blocked("source_size_or_sha_mismatch")
    try:
        raw = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration", "-of", "json", str(path)], check=True, capture_output=True, timeout=30)
        probe = json.loads(raw.stdout)
        video = next(x for x in probe["streams"] if x.get("codec_type") == "video")
        if (video["width"], video["height"], video["r_frame_rate"]) != (1280, 720, "25/1") or not any(x.get("codec_type") == "audio" for x in probe["streams"]) or abs(float(probe["format"]["duration"]) - SOURCE_SECONDS) > 0.00001:
            raise Blocked("source_probe_mismatch")
    except Blocked:
        raise
    except Exception:
        raise Blocked("source_probe_failed") from None


def check_model(model_dir):
    for name, (size, digest) in MODEL_FILES.items():
        path = Path(model_dir) / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size or sha(path) != digest:
            raise Blocked("model_size_or_sha_mismatch")


def check_windows(windows):
    if windows != WINDOWS or windows[0][0] != 0 or windows[-1][1] != SOURCE_SECONDS:
        raise Blocked("window_scope_mismatch")
    for start, end in windows:
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= SOURCE_SECONDS or end - start > 30:
            raise Blocked("window_time_limit")


def extract_window(source, dest, start, end):
    if dest.exists() or dest.is_symlink() or not 0 <= start < end <= SOURCE_SECONDS or end - start > 30:
        raise Blocked("clip_scope_mismatch")
    try:
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(start), "-i", str(source), "-t", str(end - start), "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-n", str(dest)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
        if not 44 < dest.stat().st_size <= 961024:
            raise Blocked("clip_size_limit")
        with wave.open(str(dest), "rb") as audio:
            frames = audio.getnframes()
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1, 2, 16000, "NONE") or abs(frames / 16000 - (end - start)) > 0.05:
                raise Blocked("clip_audio_mismatch")
            return audio.readframes(frames), frames
    except Blocked:
        raise
    except Exception:
        raise Blocked("clip_extraction_failed") from None


def absolute_time(value, start, duration):
    if type(value) not in (int, float) or not math.isfinite(value) or value < -0.05 or value > duration + 0.05:
        raise Blocked("inference_timestamp_out_of_window")
    return round(start + min(max(value, 0), duration), 6)


def timing_evidence(local_start, local_end, source_offset, duration):
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (local_start, local_end)):
        raise Blocked("inference_timestamp_non_finite")
    within = 0 <= local_start < local_end <= duration
    return {
        "raw_relative_start": local_start, "raw_relative_end": local_end,
        "raw_source_start": round(source_offset + local_start, 6),
        "raw_source_end": round(source_offset + local_end, 6),
        "source_start": absolute_time(local_start, source_offset, duration) if within else None,
        "source_end": absolute_time(local_end, source_offset, duration) if within else None,
        "timestamp_within_window": within,
        "timing_status": "inferred_pending_review" if within else "out_of_window_pending_review",
    }


def infer(source, model_dir, workdir):
    verify_source(source)  # Exact source bytes checked again before any extraction.
    check_model(model_dir)
    check_windows(WINDOWS)
    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", cpu_threads=1, num_workers=1, local_files_only=True)
    rows = []
    for index, (start, end) in enumerate(WINDOWS, 1):
        clip = workdir / f"window-{index:02d}.wav"
        pcm, frames = extract_window(source, clip, start, end)
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = model.transcribe(audio, language="en", beam_size=5, temperature=0, condition_on_previous_text=False, initial_prompt=None, prefix=None, word_timestamps=True, vad_filter=False)
        items = []
        for segment in segments:
            words = []
            for w in (segment.words or []):
                timing = timing_evidence(w.start, w.end, start, frames / 16000)
                words.append({"word": w.word, **timing, "probability": w.probability, "uncertain": w.probability < 0.8 or not timing["timestamp_within_window"]})
            items.append({"text": segment.text, **timing_evidence(segment.start, segment.end, start, frames / 16000), "avg_logprob": segment.avg_logprob, "no_speech_prob": segment.no_speech_prob, "compression_ratio": segment.compression_ratio, "uncertain": True, "words": words})
        rows.append({"window": index, "source_from": start, "source_to": end, "decoded_seconds": frames / 16000, "segments": items, "empty_output_is_not_silence_proof": not items})
        clip.unlink()
        print(json.dumps({"completed_window": index, "segments": len(items), **FLAGS}), flush=True)
    return rows


def write_json(path, data):
    # Only two fixed JSON artifacts. Never retain media URLs, HTTP errors, or paths.
    if any(data.get(key) is not False for key in FLAGS):
        raise Blocked("artifact_approval_forbidden")
    raw = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if any(x in raw for x in ("/workspace/", "/home/", "/tmp/", "/runner/", "Policy=", "Signature=", "token=", "Cookie", "Authorization")) or any(url != PAGE for url in re.findall(r'https?://[^\s"<>]+', raw)):
        raise Blocked("unsafe_evidence_content")
    if path.name not in {"transcript.json", "evidence.json"} or path.is_symlink():
        raise Blocked("artifact_path_not_approved")
    path.write_text(raw)


def validate():
    check_windows(WINDOWS)
    native_resolver("src/tennislive/video/official.py")
    return {"windows": len(WINDOWS), "source_seconds": SOURCE_SECONDS, "overlap_seconds": 3, **FLAGS}


def run():
    if os.environ.get("GITHUB_REF_NAME") != BRANCH:
        raise Blocked("isolated_branch_required")
    root = Path(os.environ["RUNNER_TEMP"])
    if not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise Blocked("runner_temp_required")
    work = root / "sun-public-asr-work"
    out = root / "sun-public-asr-evidence"
    if work.exists() or work.is_symlink() or out.exists() or out.is_symlink():
        raise Blocked("fresh_runtime_directories_required")
    work.mkdir(); out.mkdir()
    evidence = {"schema": "tennislive.sun-public-source-asr-evidence.v1", "created_at": datetime.now(timezone.utc).isoformat(), "public_source_url": PAGE, "video_id": VIDEO_ID, "source_bytes": SOURCE_BYTES, "source_sha256": SOURCE_SHA, "source_seconds": SOURCE_SECONDS, "resolver_sha256": RESOLVER_SHA, "model": {"id": MODEL_ID, "revision": REVISION, "files": {name: {"bytes": size, "sha256": digest} for name, (size, digest) in MODEL_FILES.items()}}, "telemetry_and_offline_flags": {key: os.environ[key] for key in ("ORT_DISABLE_TELEMETRY", "HF_HUB_DISABLE_TELEMETRY", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}, "status": "not_started", **FLAGS}
    try:
        evidence["stage"] = "resolve_source"
        resolver = native_resolver("src/tennislive/video/official.py")
        deadline = time.monotonic() + 120
        url = resolve_source(resolver, deadline)
        source = work / "source.mp4"
        evidence["stage"] = "download_source"
        download_exact(url, source, SOURCE_BYTES, SOURCE_SHA, deadline)
        verify_source(source)
        evidence["status"] = "exact_source_verified"
        write_json(out / "evidence.json", evidence)
        model_dir = work / "model"; model_dir.mkdir()
        deadline = time.monotonic() + 1200
        for name, (size, digest) in MODEL_FILES.items():
            evidence["stage"] = "model_" + name
            target = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{name}?download=true"
            safe_url(target, {"huggingface.co"})
            download_exact(target, model_dir / name, size, digest, deadline, model=True)
        check_model(model_dir)
        evidence["stage"] = "infer"
        rows = infer(source, model_dir, work)
        transcript = {"schema": "tennislive.sun-asr-transcript-evidence.v1", "public_source_url": PAGE, "source_sha256": SOURCE_SHA, "status": "inference_only_not_human_verified", "language": "en", "windows": rows, "uncertainty_note": "Model output can omit or hallucinate speech. Overlaps remain separate for boundary comparison. Listen to the entire source; empty output does not prove silence.", **FLAGS}
        write_json(out / "transcript.json", transcript)
        evidence.update(status="inference_only_not_human_verified", completed_windows=len(rows), cpu_threads=1, vad_filter=False, transcript_seeding=False, versions={name: importlib.metadata.version(name) for name in ("faster-whisper", "ctranslate2", "onnxruntime", "numpy", "huggingface-hub", "tokenizers", "av")})
    except Exception as exc:
        evidence.update(status="blocked", reason=str(exc) if isinstance(exc, Blocked) else "runner_failed")
        if isinstance(exc, Blocked) and getattr(exc, "safe_host", None):
            evidence["rejected_host"] = exc.safe_host
        write_json(out / "evidence.json", evidence)
        raise Blocked("runner_blocked") from None
    write_json(out / "evidence.json", evidence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    if args.validate:
        print(json.dumps(validate()))
        return
    with total_limit(2400):
        run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "blocked", "reason": "runner_blocked", **FLAGS}), flush=True)
        raise SystemExit(1) from None
