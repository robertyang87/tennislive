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
                # Timeline subtraction can put an exact boundary one float ULP outside
                # its reviewed interval; normalize far below a single PCM sample.
                start = round(float(seg['start']) + second - float(offsets[index]), 9)
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


def _reviewed_mix_match(source: np.ndarray, landed: np.ndarray,
                        envelope: np.ndarray, gain: float) -> dict | None:
    """Compare the entire second to the native fade, including its quiet prefix.

    Only codec alignment is searched (80 ms), never the fade duration or gain.
    The audible part must itself be nonzero; card silence cannot supply evidence.
    """
    if (len(landed) != RATE or len(source) != RATE + 1280
            or len(envelope) != RATE or not 0 < gain <= 1.35
            or not all(np.all(np.isfinite(a)) for a in (source, landed, envelope))):
        return None
    active = envelope > 0
    if active.sum() < .4 * RATE or np.any(envelope < 0) or np.any(envelope > 1):
        return None
    energy = float(np.dot(landed, landed))
    if energy <= RATE * 10 ** (-75 / 10) or np.mean(landed[active] == 0) > .2:
        return None
    # Weight before correlation: the whole native fade is part of the proof.
    products = np.correlate(source, landed * envelope, mode='valid')
    energies = np.correlate(source * source, envelope * envelope, mode='valid')
    correlations = products / np.sqrt(np.maximum(energies * energy, 1e-40))
    index = int(np.argmax(correlations))
    source_db = 10 * math.log10(max(float(energies[index]) / RATE, 1e-40))
    measured_gain = float(products[index] / max(energies[index], 1e-40))
    if (correlations[index] < .85 or not -75 < source_db < -59
            or np.mean(source[index:index + RATE][active] == 0) > .2
            or measured_gain <= 0
            or abs(20 * math.log10(measured_gain / gain)) > 2):
        return None
    # A correct constant-volume tail must not hide a missing/wrong fade. Check
    # the entire varying-envelope region at the already chosen codec alignment.
    fading = (envelope > 0) & (envelope < 1)
    if fading.sum() >= .04 * RATE:
        fade_reference = source[index:index + RATE][fading] * envelope[fading]
        fade_landed = landed[fading]
        fade_energy = float(np.dot(fade_reference, fade_reference))
        fade_output = float(np.dot(fade_landed, fade_landed))
        fade_product = float(np.dot(fade_reference, fade_landed))
        fade_correlation = fade_product / math.sqrt(max(fade_energy * fade_output, 1e-40))
        fade_gain = fade_product / max(fade_energy, 1e-40)
        if (fade_correlation < .85 or fade_gain <= 0
                or abs(20 * math.log10(fade_gain / gain)) > 2):
            return None
    return {'correlation': float(correlations[index]), 'gain': measured_gain,
            'gain_error_db': 20 * math.log10(measured_gain / gain),
            'source_db': source_db, 'alignment_samples': index - 640}


def verified_reviewed_mix_seconds(spec: dict, film: Path, candidates: list[int],
                                  *, root: Path | None = None) -> list[int]:
    """Prove actual retained ambience from a complete, immutable source review.

    This does not amend declared quiet windows or any rendering evidence. The
    existing final-audio gate must authenticate the complete review, source
    identities, film, ASS and original timeline first. Only plain native mixes
    and a silent evidence-card -> source boundary can be reconstructed here.
    """
    if (not candidates or spec.get('music') or spec.get('source_audio')
            or spec.get('audio_effects_review') or spec.get('original_audio_mode')):
        return []
    try:
        from foreground_audio_gate import ROOT, verify_final
        from build_match_reel import BED_LOUD, BED_TIERS, SEG_FADE, _mix_ducks
        from check_reel_landed import evidence_windows
        from types import SimpleNamespace
        binding = json.loads((film.parent / 'audio_review_binding.json').read_text())
        timeline = binding['timeline']
        cover = float(timeline['cover_seconds'])
        verify_final(spec, film.parent / 'subtitles.ass', cover,
                     root=root or ROOT, film=film)
        segments = spec['segments']
        offsets, lengths = timeline['offsets'], timeline['lengths']
        # Independently reject a coherently rebound but non-native timeline.
        cursor = cover
        for offset, length in zip(offsets, lengths):
            if not math.isclose(float(offset), cursor, abs_tol=1e-8):
                return []
            cursor += float(length)
        ducked = _mix_ducks(spec, [SimpleNamespace(narration=str(s.get('narration') or ''),
                                                 quote=s.get('quote')) for s in segments])
        cards = evidence_windows(spec, cover)
        urls = spec.get('sources') or {'': spec.get('source_url')}
        primary = next(iter(urls))
        sources, final, accepted = {}, None, []
        for i, seg in enumerate(segments):
            if (not {'start', 'end'} <= seg.keys() or seg.get('image')
                    or seg.get('stat_card') or seg.get('title_card')
                    or seg.get('narration') or seg.get('mute')
                    or float(seg.get('speed', 1)) != 1
                    or seg.get('audio_tail') not in (None, 'silence')):
                continue
            offset, end = float(offsets[i]), float(offsets[i]) + float(lengths[i])
            key = str(seg.get('source', primary))
            gain = (BED_LOUD if ducked else 1.) * BED_TIERS.get(seg.get('bed'), 1.)
            for second in candidates:
                if not isinstance(second, int) or isinstance(second, bool):
                    continue
                lo, hi = float(second), float(second + 1)
                # Outgoing video/card fades and adjacent-video joins need a
                # two-source model and are deliberately outside this verifier.
                if hi > end or hi <= offset:
                    continue
                previous = segments[i - 1] if i else {}
                previous_is_card = bool(previous.get('image') or previous.get('stat_card')
                                        or previous.get('title_card'))
                touches_fade = lo < offset + SEG_FADE and previous_is_card
                if touches_fade:
                    if (not previous.get('narration')
                            or (lo < offset and not any(a <= lo and offset <= b for a, b in cards))):
                        continue
                    if hi - max(lo, offset) < .4:
                        continue
                elif lo < offset:
                    continue
                if key not in sources:
                    path = film.parent / (f'source_{key}.mp4' if key else 'source.mp4')
                    if path.parent.resolve() != film.parent.resolve():
                        return []
                    with path.open('rb') as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    if digest != binding['sources'].get(key):
                        return []
                    sources[key] = pcm(path)
                if final is None:
                    final = pcm(film)
                mapped = float(seg['start']) + lo - offset
                at = round(mapped * RATE)
                indices = np.arange(at - 640, at + RATE + 640)
                # Codec padding must never read outside the reviewed segment.
                valid = ((indices >= round(float(seg['start']) * RATE))
                         & (indices < round(float(seg['end']) * RATE))
                         & (indices >= 0) & (indices < len(sources[key])))
                reference = np.zeros(RATE + 1280)
                reference[valid] = sources[key][indices[valid]]
                times = lo + np.arange(RATE) / RATE
                envelope = (np.clip((times - offset) / SEG_FADE, 0., 1.)
                            if touches_fade else np.ones(RATE))
                proof = _reviewed_mix_match(reference,
                                            final[second * RATE:(second + 1) * RATE],
                                            envelope, gain)
                if proof is not None:
                    accepted.append(second)
                    print(f"[完整原声波形证据] 成片{second}–{second+1}s ← 源{key} "
                          f"SHA256={binding['sources'][key]}；原生fade={SEG_FADE}s；"
                          f"相关={proof['correlation']:.6f}、"
                          f"增益误差={proof['gain_error_db']:.3f}dB、"
                          f"编码对齐={proof['alignment_samples']}样本；非零")
        return sorted(set(accepted))
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration,
            subprocess.SubprocessError):
        return []
