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
                        envelope: np.ndarray, gain: float, *,
                        attenuated_ambience: bool = False) -> dict | None:
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
    weak_db = source_db + (20 * math.log10(gain) if attenuated_ambience else 0)
    if (correlations[index] < .85 or not -75 < weak_db < -59
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


def _plain_source(seg: dict, *, narration: bool = False) -> bool:
    return (bool({'start', 'end'} <= seg.keys())
            and not any(seg.get(k) for k in ('image', 'stat_card', 'title_card', 'mute'))
            and float(seg.get('speed', 1)) == 1
            and seg.get('audio_tail') in (None, 'silence')
            and (narration or not seg.get('narration')))


def _complete_voice_pair(spec: dict, film: Path, index: int,
                         offset: float, final: np.ndarray) -> dict | None:
    """Authenticate an actual current native pair and its entire landed utterance.

    Never synthesize, infer a missing marks file, or accept a declared speech end.
    The normal atomic content cache or an exact adjacent native ZIP is required.
    """
    import os
    import re
    import zipfile
    from build_match_reel import _seg_voice, _tts_content_key, speakable
    from probe_audio import voice_speech_end

    seg = spec['segments'][index]
    render = json.loads((film.parent / 'render.json').read_text())
    if render.get('narration_backend') not in ('edge', 'edge-tts'):
        return None  # Azure base styles need their own exact native-key mapping.
    rate, pitch, style, degree, lead = _seg_voice(seg, index)
    if style or degree:
        return None
    spoken = speakable(str(seg.get('narration') or ''))
    key = _tts_content_key(spoken, str(render['narration_voice']),
                           rate or str(render['narration_rate']), pitch or '+0Hz',
                           style, degree, lead)
    voice = film.parent / f'voice_{index:02d}.mp3'
    marks_path = voice.with_suffix('.words.json')
    cache = Path(os.environ.get('TENNISLIVE_TTS_CACHE',
                 str(Path.home() / '.cache' / 'tennislive-tts'))).expanduser()
    pair = voice.with_suffix('.native.zip')
    if not pair.is_file():
        pair = cache / f'{key}-edge-v2.zip'
    with zipfile.ZipFile(pair) as bundle:
        audio = bundle.read('audio.mp3')
        marks = json.loads(bundle.read('marks.json'))
    if (not audio or voice.read_bytes() != audio
            or json.loads(marks_path.read_text()) != marks or not isinstance(marks, list)
            or not marks):
        return None
    normalize = lambda text: re.sub(r'[^a-z0-9\u3400-\u9fff]', '', str(text).casefold())
    previous = 0.
    for mark in marks:
        if not isinstance(mark, dict) or not str(mark.get('text') or '').strip():
            return None
        a, duration = mark.get('offset'), mark.get('duration')
        if (isinstance(a, bool) or isinstance(duration, bool)
                or not isinstance(a, (int, float)) or not isinstance(duration, (int, float))
                or not math.isfinite(a) or not math.isfinite(duration)
                or a < previous or duration <= 0):
            return None
        previous = a + duration
    if normalize(''.join(m['text'] for m in marks)) != normalize(spoken):
        return None
    original = pcm(voice)
    if previous / 1e7 > len(original) / RATE + .08:
        return None
    end = voice_speech_end(voice)
    if end is None or end <= 0:
        return None
    # Strong full-utterance identity is measured again in this immutable AAC.
    # Search only +/-80ms codec alignment, preserving unit narration gain.
    at = round(offset * RATE)
    lo, hi = max(0, at - 640), min(len(final), at + len(original) + 640)
    sample = final[lo:hi]
    if len(sample) < len(original):
        return None
    energy = float(np.dot(original, original))
    if energy <= RATE * 10 ** (-60 / 10):
        return None
    products = np.correlate(sample, original, mode='valid')
    squares = np.concatenate(([0.], np.cumsum(sample * sample)))
    energies = squares[len(original):] - squares[:-len(original)]
    correlations = products / np.sqrt(np.maximum(energies * energy, 1e-40))
    best = int(np.argmax(correlations))
    voice_gain = float(products[best] / energy)
    def channels(path):
        result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                                 '-show_entries', 'stream=channels', '-of', 'json', str(path)],
                                check=True, capture_output=True, text=True)
        return int(json.loads(result.stdout)['streams'][0]['channels'])
    voice_channels, film_channels = channels(voice), channels(film)
    if voice_channels not in (1, 2) or film_channels not in (1, 2):
        return None
    # Native amix expands a mono TTS centre into stereo at -3dB. Our proof's
    # mono decoder must account for that real channel conversion, not fit a
    # free gain or incorrectly reject every valid mono voice/stereo master.
    expected_voice_gain = 1 / math.sqrt(2) if (voice_channels, film_channels) == (1, 2) else 1.
    residual = math.sqrt(max(float(energies[best]) - products[best] ** 2 / energy, 0)
                         / max(float(energies[best]), 1e-40))
    if (correlations[best] < .95 or voice_gain <= 0
            or abs(20 * math.log10(voice_gain / expected_voice_gain)) > 2 or residual > .32
            or abs(lo + best - at) > 640):
        return None
    return {'word_end': previous / 1e7, 'acoustic_end': end, 'pcm': original,
            'mp3_sha256': hashlib.sha256(audio).hexdigest(),
            'paired_zip_sha256': hashlib.sha256(pair.read_bytes()).hexdigest(),
            'word_marks_sha256': hashlib.sha256(marks_path.read_bytes()).hexdigest(),
            'voice_correlation': float(correlations[best]), 'voice_gain': voice_gain}


def verified_native_ambience_seconds(spec: dict, film: Path, candidates: list[int],
                                     *, root: Path | None = None) -> list[int]:
    """Prove continuous source joins and measured post-narration ambience.

    This adds evidence models, not a lower silence threshold. Source identity,
    the immutable native review/film/ASS, actual gain, full-second correlation and
    nonzero samples are required. An unfinished/missing voice pair stays blocked.
    """
    if (not candidates or any(spec.get(k) for k in
            ('music', 'source_audio', 'audio_effects_review', 'original_audio_mode'))):
        return []
    try:
        from foreground_audio_gate import ROOT, verify_final
        from build_match_reel import BED_LOUD, BED_TIERS, _mix_ducks
        from types import SimpleNamespace
        import zipfile

        binding = json.loads((film.parent / 'audio_review_binding.json').read_text())
        timeline = binding['timeline']
        cover = float(timeline['cover_seconds'])
        verify_final(spec, film.parent / 'subtitles.ass', cover, root=root or ROOT, film=film)
        segments = spec['segments']
        offsets, lengths = timeline['offsets'], timeline['lengths']
        if len(offsets) != len(segments) or len(lengths) != len(segments):
            return []
        cursor = cover
        for offset, length in zip(offsets, lengths):
            if not math.isclose(float(offset), cursor, abs_tol=1e-8):
                return []
            cursor += float(length)
        ducked = _mix_ducks(spec, [SimpleNamespace(narration=str(s.get('narration') or ''),
                                                  quote=s.get('quote')) for s in segments])
        urls = spec.get('sources') or {'': spec.get('source_url')}
        primary = next(iter(urls))
        final, sources, voices, accepted = pcm(film), {}, {}, []
        for second in sorted(set(candidates)):
            if not isinstance(second, int) or isinstance(second, bool):
                continue
            lo, hi = float(second), float(second + 1)
            pieces = [i for i in range(len(segments))
                      if float(offsets[i]) < hi and float(offsets[i]) + float(lengths[i]) > lo]
            if not pieces:
                continue
            first, last = pieces[0], pieces[-1]
            if (lo < float(offsets[first])
                    or hi > float(offsets[last]) + float(lengths[last])):
                continue
            if not all(_plain_source(segments[i], narration=True) for i in pieces):
                continue
            key = str(segments[first].get('source', primary))
            gain = (BED_LOUD if ducked else 1.) * BED_TIERS.get(segments[first].get('bed'), 1.)
            mapping = float(segments[first]['start']) - float(offsets[first])
            if any(str(segments[i].get('source', primary)) != key
                   or not math.isclose(float(segments[i]['start']) - float(offsets[i]), mapping, abs_tol=1e-8)
                   or not math.isclose((BED_LOUD if ducked else 1.) * BED_TIERS.get(segments[i].get('bed'), 1.), gain)
                   for i in pieces):
                continue
            if any(not math.isclose(float(segments[a]['end']), float(segments[b]['start']), abs_tol=1e-8)
                   for a, b in zip(pieces, pieces[1:])):
                continue
            narrated = [i for i in pieces if segments[i].get('narration')]
            # A join containing any narration is not a plain continuous-source proof.
            if len(pieces) > 1 and narrated:
                continue
            kind = 'continuous_source_join'
            voice_proof = None
            if narrated:
                kind = 'measured_post_narration_tail'
                i = narrated[0]
                if i not in voices:
                    try:
                        voices[i] = _complete_voice_pair(spec, film, i, float(offsets[i]), final)
                    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, EOFError):
                        voices[i] = None
                voice_proof = voices[i]
                elapsed = lo - float(offsets[i])
                if (voice_proof is None or elapsed < voice_proof['word_end'] + .04
                        or elapsed < voice_proof['acoustic_end']):
                    continue
                voice_tail = voice_proof['pcm'][max(0, round(elapsed * RATE)):
                                                max(0, round((elapsed + 1) * RATE))]
                # Actual decoded cache, including residual tail, must be below -80dB.
                if any(np.mean(block * block) > 1e-8
                       for block in np.array_split(voice_tail, max(1, math.ceil(len(voice_tail) / 160)))
                       if len(block)):
                    continue
            elif len(pieces) < 2:
                continue  # The existing single-source verifiers already cover this.
            if key not in sources:
                path = film.parent / (f'source_{key}.mp4' if key else 'source.mp4')
                if path.parent.resolve() != film.parent.resolve():
                    return []
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if digest != binding['sources'].get(key):
                    return []
                sources[key] = pcm(path)
            mapped = mapping + lo
            at = round(mapped * RATE)
            indices = np.arange(at - 640, at + RATE + 640)
            valid = ((indices >= round(float(segments[first]['start']) * RATE))
                     & (indices < round(float(segments[last]['end']) * RATE))
                     & (indices >= 0) & (indices < len(sources[key])))
            reference = np.zeros(RATE + 1280)
            reference[valid] = sources[key][indices[valid]]
            proof = _reviewed_mix_match(reference, final[second * RATE:(second + 1) * RATE],
                                        np.ones(RATE), gain,
                                        attenuated_ambience=bool(narrated))
            if proof is not None:
                accepted.append(second)
                details = (f"；全句MP3={voice_proof['mp3_sha256']}、"
                           f"配对ZIP={voice_proof['paired_zip_sha256']}、"
                           f"voice相关={voice_proof['voice_correlation']:.6f}"
                           if voice_proof else '')
                print(f"[原生弱声完整秒证据] 成片{second}–{second+1}s {kind} ← 源{key} "
                      f"{mapped:.3f}–{mapped+1:.3f}s SHA256={binding['sources'][key]}；"
                      f"相关={proof['correlation']:.6f}、gain={gain:.6f}、"
                      f"增益误差={proof['gain_error_db']:.3f}dB、非零{details}")
        return accepted
    except (OSError, ValueError, TypeError, KeyError, IndexError, StopIteration,
            subprocess.SubprocessError, ImportError):
        return []


def quiet_window_has_source_proof(lo: int, hi: int, verified: set[int]) -> bool:
    """A short quiet-window floor proxy cannot override every actual-second proof."""
    return hi > lo and all(second in verified for second in range(lo, hi))
