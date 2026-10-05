"""Verify declared natural quiet against the hash-bound source, never text alone.

Called after foreground_audio_gate.verify_final has authenticated the film,
render manifest, review, and timeline. Missing evidence fails closed.
"""
from __future__ import annotations
import hashlib
import json
import math
import subprocess
from pathlib import Path
import numpy as np

RATE = 8000


def pcm(path: Path) -> np.ndarray:
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn',
                             '-ac', '1', '-ar', str(RATE), '-f', 's16le', '-'],
                            capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype='<i2').astype(float) / 32768.0


def matching_quiet(source: np.ndarray, landed: np.ndarray, gain: float = .972) -> bool:
    """One second of nonzero source ambience must survive with its real gain.

    Source includes 80 ms padding at both ends to tolerate codec delay. Correlation
    rules out unrelated added sound; level ratio rules out accidental attenuation.
    -75 dB is intentionally a conservative lower bound, not a new global floor.
    """
    if len(landed) != RATE or len(source) != RATE + 1280:
        return False
    if not np.all(np.isfinite(source)) or not np.all(np.isfinite(landed)):
        return False
    energy = float(np.dot(landed, landed))
    if energy <= RATE * 10 ** (-75 / 10) or np.mean(landed == 0) > .2:
        return False
    # Search every sample: AAC's delay need not be an integer millisecond.
    products = np.correlate(source, landed, mode='valid')
    squares = np.concatenate(([0.], np.cumsum(source * source)))
    energies = squares[RATE:] - squares[:-RATE]
    correlations = products / np.sqrt(np.maximum(energies * energy, 1e-40))
    index = int(np.argmax(correlations))
    if correlations[index] < .85:
        return False
    src = source[index:index + RATE]
    source_db = 10 * math.log10(max(energies[index] / RATE, 1e-40))
    if not -75 < source_db < -59 or np.mean(src == 0) > .2:
        return False
    measured_gain = products[index] / energies[index]
    return measured_gain > 0 and abs(20 * math.log10(measured_gain / gain)) <= 2


def verified_seconds(spec: dict, film: Path, candidates: list[int]) -> list[int]:
    """Return only source-matched seconds inside explicitly declared source spans."""
    if (not candidates or spec.get('music') or spec.get('source_audio')
            or spec.get('audio_effects_review') or spec.get('original_audio_mode')):
        return []
    try:
        from foreground_audio_gate import plan_hash
        from build_match_reel import _mix_ducks
        from types import SimpleNamespace
        # .972 is BED_TIERS['high'] * BED_LOUD, only used by the ducked mix.
        # Use the renderer's predicate; no-voice/outro-disabled films use 1.35.
        if not _mix_ducks(spec, [SimpleNamespace(narration=str(seg.get('narration') or ''),
                                                quote=seg.get('quote'))
                                 for seg in spec['segments']]):
            return []
        binding = json.loads((film.parent / 'audio_review_binding.json').read_text())
        if binding['plan_sha256'] != plan_hash(spec):
            return []
        offsets = binding['timeline']['offsets']
        sources = {}
        final = None
        accepted = []
        for index, seg in enumerate(spec['segments']):
            if (not seg.get('_digital_silence_why') or seg.get('bed') != 'high'
                    or seg.get('narration') or seg.get('mute')
                    or seg.get('speed', 1) != 1 or 'start' not in seg):
                continue
            windows = seg.get('_digital_silence_windows', [])
            if not windows:
                continue
            key = seg.get('source', spec.get('primary', ''))
            relevant = []
            for second in candidates:
                start = float(seg['start']) + second - float(offsets[index])
                end = start + 1
                if (float(seg['start']) <= start and end <= float(seg['end'])
                        and any(float(a) <= start and end <= float(b) for a, b in windows)):
                    relevant.append((second, start))
            if not relevant:
                continue
            if key not in sources:
                path = film.parent / (f'source_{key}.mp4' if key else 'source.mp4')
                # Keys are spec data, not filesystem authority.
                if path.parent.resolve() != film.parent.resolve():
                    return []
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != binding['sources'].get(key):
                    return []
                sources[key] = pcm(path)
            if final is None:
                final = pcm(film)
            for second, start in relevant:
                at = round(start * RATE)
                if matching_quiet(sources[key][at-640:at+RATE+640],
                                  final[second*RATE:(second+1)*RATE]):
                    accepted.append(second)
                    print(f"[自然弱声证据] 成片{second}–{second+1}s ← 源{key} "
                          f"{start:.3f}–{start+1:.3f}s SHA256={binding['sources'][key]}；"
                          "波形相关≥0.85、增益误差≤2dB，原源/成片均非零")
        return sorted(set(accepted))
    except (OSError, ValueError, TypeError, KeyError, IndexError, subprocess.SubprocessError):
        return []
