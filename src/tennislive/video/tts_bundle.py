"""Portable, finite snapshots of actual production TTS calls.

A bundle is input evidence, never editorial or publication approval. Unlike the
opportunistic content cache, an explicitly supplied bundle fails closed.
"""
from __future__ import annotations

from contextvars import ContextVar
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

SCHEMA = "tennislive.frozen-tts-bundle.v1"
LIMIT = 32 * 1024 * 1024
_ACTIVE: ContextVar["BundleSession | None"] = ContextVar("tennislive_tts_bundle", default=None)


class TTSBundleError(ValueError):
    """An explicit frozen input is invalid; synthesizing again is not a repair."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise TTSBundleError(f"Invalid bundle JSON: {exc}") from exc


def implementation_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parent
    return {name: _sha((root / name).read_bytes()) for name in
            ("tts.py", "tts_bundle.py", "azure_tts.py", "pronounce.py")}


def validate_request(request: dict) -> dict:
    fields = {"text", "voice", "rate", "pitch", "style", "styledegree",
              "lead_pause", "backend", "cache_key"}
    if not isinstance(request, dict) or set(request) != fields:
        raise TTSBundleError("Request must contain the complete synthesis parameters")
    for name in fields - {"lead_pause"}:
        if not isinstance(request[name], str):
            raise TTSBundleError(f"Invalid synthesis parameter {name}")
    if not request["text"] or not request["voice"] or request["backend"] not in {"edge", "azure"}:
        raise TTSBundleError("Empty text/voice or unsupported TTS backend")
    pause = request["lead_pause"]
    if isinstance(pause, bool) or not isinstance(pause, (int, float)) or not math.isfinite(pause) or pause < 0:
        raise TTSBundleError("Invalid lead_pause")
    # Keep the shared cache's exact key semantics, including 0 versus 0.0.
    from .tts import tts_content_key
    key = tts_content_key(*(request[name] for name in
        ("text", "voice", "rate", "pitch", "style", "styledegree", "lead_pause")))
    if key != request["cache_key"]:
        raise TTSBundleError("Request cache_key does not match its synthesis parameters")
    return dict(request)


def request_id(request: dict) -> str:
    return _sha(_json(validate_request(request)))


def _validate_marks(marks, duration: float) -> None:
    if not isinstance(marks, list) or not marks:
        raise TTSBundleError("Frozen speech must have real nonempty WordBoundary marks")
    previous = -1.0
    for mark in marks:
        if not isinstance(mark, dict) or not isinstance(mark.get("text"), str) or not mark["text"]:
            raise TTSBundleError("Invalid WordBoundary text")
        values = (mark.get("offset"), mark.get("duration"))
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise TTSBundleError("Invalid WordBoundary timing")
        offset, length = values
        if offset < previous or offset < 0 or length <= 0 or (offset + length) / 1e7 > duration + .25:
            raise TTSBundleError("WordBoundary timing is unordered or outside actual speech")
        previous = offset


def _audio_duration(audio: bytes) -> float:
    if not audio:
        raise TTSBundleError("Frozen audio is empty")
    with tempfile.TemporaryDirectory(prefix="tts-bundle-verify-") as folder:
        p = Path(folder) / "speech.mp3"
        p.write_bytes(audio)
        try:
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(p)],
                capture_output=True, check=True, timeout=30)
            info = json.loads(probe.stdout)
            duration = float(info["format"]["duration"])
            if not info.get("streams") or not math.isfinite(duration) or duration <= 0:
                raise ValueError("no finite audio duration")
            # Decode only. No amplitude, loudness, silence, or gain test.
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(p),
                "-map", "0:a:0", "-f", "null", "-"], capture_output=True, check=True, timeout=30)
        except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
            raise TTSBundleError(f"Frozen audio cannot be decoded: {exc}") from exc
    return duration


def read_bundle(path: Path | bytes, expected_requests=None, *, decode_audio=True) -> tuple[dict, dict]:
    """Verify every member before returning any audio or writing any output."""
    try:
        raw = path if isinstance(path, bytes) else Path(path).read_bytes()
        if len(raw) > LIMIT:
            raise TTSBundleError("Frozen bundle exceeds size limit")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or sum(x.file_size for x in z.infolist()) > LIMIT:
                raise TTSBundleError("Duplicate members or oversized frozen bundle")
            manifest = json.loads(z.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
                raise TTSBundleError("Unsupported frozen TTS bundle schema")
            if manifest.get("artifact_kind") != "native_tts_inputs" or manifest.get("quality_approval") is not False:
                raise TTSBundleError("A TTS input bundle cannot claim quality approval")
            if manifest.get("implementation") != implementation_identity():
                raise TTSBundleError("Synthesis implementation differs from the frozen bundle")
            entries = manifest.get("entries")
            if not isinstance(entries, list) or not entries:
                raise TTSBundleError("Frozen bundle has no requests")
            if expected_requests is not None:
                current_ids = {request_id(r) for r in expected_requests}
                frozen_ids = {request_id(e["request"]) for e in entries}
                if current_ids != frozen_ids:
                    raise TTSBundleError("Frozen request set differs from current text/voice/parameters/backend")
            expected_names = {"manifest.json"}
            loaded = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    raise TTSBundleError("Invalid bundle entry")
                req = validate_request(entry["request"])
                rid = request_id(req)
                if entry.get("request_id") != rid or rid in loaded:
                    raise TTSBundleError("Duplicate/mismatched request identity")
                ap, mp = f"requests/{rid}/audio.mp3", f"requests/{rid}/marks.json"
                expected_names.update((ap, mp))
                audio, mark_bytes = z.read(ap), z.read(mp)
                if _sha(audio) != entry.get("audio_sha256") or _sha(mark_bytes) != entry.get("marks_sha256"):
                    raise TTSBundleError("Frozen audio/WordBoundary hash mismatch")
                marks = json.loads(mark_bytes)
                recorded = entry.get("duration_seconds")
                if isinstance(recorded, bool) or not isinstance(recorded, (int, float)) or not math.isfinite(recorded) or recorded <= 0:
                    raise TTSBundleError("Invalid declared frozen duration")
                duration = _audio_duration(audio) if decode_audio else recorded
                if not audio or abs(recorded - duration) > .001:
                    raise TTSBundleError("Frozen duration differs from decoded audio")
                _validate_marks(marks, duration)
                loaded[rid] = (req, audio, marks, mark_bytes, duration)
            if set(names) != expected_names:
                raise TTSBundleError("Unexpected bundle members; no path extraction is permitted")
    except TTSBundleError:
        raise
    except (OSError, zipfile.BadZipFile, EOFError, KeyError, TypeError, ValueError) as exc:
        raise TTSBundleError(f"Invalid frozen TTS bundle: {exc}") from exc
    return manifest, loaded


class BundleSession:
    def __init__(self, *, input_path=None, output_path=None, expected_requests=None, metadata=None):
        self.input_path = Path(input_path) if input_path is not None else None
        self.output_path = Path(output_path) if output_path is not None else None
        if self.input_path is None and self.output_path is None:
            raise TTSBundleError("A bundle input or output path is required")
        self.expected = None if expected_requests is None else {
            request_id(r): validate_request(r) for r in expected_requests}
        if self.input_path is not None and self.expected is None:
            raise TTSBundleError("Strict import requires the complete current request list")
        self.metadata = metadata or {}
        if not isinstance(self.metadata, dict):
            raise TTSBundleError("Bundle metadata must be an object")
        _json(self.metadata)
        self.entries = {}
        self.occurrences = []
        self.seen = set()
        self._token = None
        self._written = False
        self._input_bytes = None
        self.identity = {"schema": SCHEMA, "bundle_sha256": None, "request_count": 0,
            "mode": "strict_import" if self.input_path else "capture_export",
            "strict_reused": False, "artifact_kind": "native_tts_inputs", "quality_approval": False,
            "audio_decoding_verified": True}

    def __enter__(self):
        if _ACTIVE.get() is not None:
            raise TTSBundleError("Nested frozen TTS sessions are not supported")
        if self.input_path is not None:
            try:
                self._input_bytes = self.input_path.read_bytes()
            except OSError as exc:
                raise TTSBundleError(f"Cannot read frozen TTS bundle: {exc}") from exc
            _, self.entries = read_bundle(self._input_bytes, self.expected.values())
            self.identity.update(bundle_sha256=_sha(self._input_bytes), request_count=len(self.entries))
        self._token = _ACTIVE.set(self)
        return self

    def verify_request(self, request: dict):
        rid = request_id(request)
        if self.expected is not None and rid not in self.expected:
            raise TTSBundleError("Actual synthesis differs from expected frozen request list")

    def materialize(self, request: dict, path: Path):
        self.verify_request(request)
        rid = request_id(request)
        if rid not in self.entries:
            raise TTSBundleError("Requested speech is absent from explicitly supplied frozen bundle")
        req, audio, marks, _, _ = self.entries[rid]
        if _json(req) != _json(request):
            raise TTSBundleError("Frozen synthesis parameters do not match actual call")
        path.write_bytes(audio)
        self.seen.add(rid)
        self.occurrences.append({"request_id": rid, "output_name": path.name})
        self.identity["strict_reused"] = True
        # A fresh JSON copy prevents the consumer from mutating another slot.
        return json.loads(json.dumps(marks, ensure_ascii=False))

    def capture(self, request: dict, path: Path, marks: list[dict]):
        if self._written:
            raise TTSBundleError("Cannot add TTS calls after the bundle was finalized")
        rid = request_id(request)
        if self.expected is not None and rid not in self.expected:
            raise TTSBundleError("Actual synthesis differs from expected frozen request list")
        audio = path.read_bytes()
        mark_bytes = _json(marks)
        if rid in self.entries:
            old = self.entries[rid]
            if old[1] != audio or old[3] != mark_bytes:
                raise TTSBundleError("One request returned different audio/marks in this capture session")
        else:
            duration = _audio_duration(audio)
            _validate_marks(marks, duration)
            self.entries[rid] = (dict(request), audio, json.loads(mark_bytes), mark_bytes, duration)
        self.seen.add(rid)
        self.occurrences.append({"request_id": rid, "output_name": path.name})
        self.identity["request_count"] = len(self.entries)

    def write(self):
        if self.input_path is not None:
            if self.seen != set(self.expected):
                raise TTSBundleError("Renderer did not consume all frozen speech requests")
            if self.output_path is not None and not self._written:
                self._atomic_write_bytes(self._input_bytes)
                self._written = True
            return dict(self.identity)
        if self._written:
            return dict(self.identity)
        if not self.entries or (self.expected is not None and set(self.entries) != set(self.expected)):
            raise TTSBundleError("Capture did not produce the complete expected request set")
        entries = []
        for rid, (request, audio, _, mark_bytes, duration) in sorted(self.entries.items()):
            entries.append({"request_id": rid, "request": request, "audio_sha256": _sha(audio),
                "marks_sha256": _sha(mark_bytes), "duration_seconds": duration})
        manifest = {"schema": SCHEMA, "artifact_kind": "native_tts_inputs", "quality_approval": False,
            "implementation": implementation_identity(), "entries": entries,
            "occurrences": self.occurrences, "metadata": self.metadata}
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.output_path.parent, prefix=".tts-bundle-", delete=False) as f:
                temp = Path(f.name)
                with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_STORED) as z:
                    z.writestr("manifest.json", _json(manifest))
                    for rid, (_, audio, _, mark_bytes, _) in sorted(self.entries.items()):
                        z.writestr(f"requests/{rid}/audio.mp3", audio)
                        z.writestr(f"requests/{rid}/marks.json", mark_bytes)
            os.replace(temp, self.output_path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
        self._written = True
        self.identity.update(bundle_sha256=_sha(self.output_path.read_bytes()))
        return dict(self.identity)

    def _atomic_write_bytes(self, raw: bytes):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.output_path.parent, prefix=".tts-bundle-", delete=False) as f:
                temp = Path(f.name)
                f.write(raw)
            os.replace(temp, self.output_path)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    def __exit__(self, typ, value, traceback):
        _ACTIVE.reset(self._token)
        if typ is None:
            self.write()
        return False


def active_session():
    return _ACTIVE.get()


def validate_bundle(path: Path, expected_requests=None, *, decode_audio=True) -> dict:
    """Single public validation/report entry for finite artifact transports."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise TTSBundleError(f"Cannot read frozen TTS bundle: {exc}") from exc
    manifest, entries = read_bundle(raw, expected_requests, decode_audio=decode_audio)
    return {"schema": SCHEMA, "bundle_sha256": _sha(raw),
        "request_count": len(entries), "artifact_kind": "native_tts_inputs",
        "quality_approval": False, "implementation": manifest["implementation"],
        "audio_decoding_verified": bool(decode_audio),
        "validation_level": "complete_decode" if decode_audio else "integrity_and_requests",
        "metadata": manifest.get("metadata", {}), "entries": manifest["entries"]}
