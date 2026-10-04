from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import build_interview_clip as clip


def spec():
    return {'start': 0, 'end': 100, 'asr_model': 'small', 'whisper_model': 'medium',
            'transcript_languages': [{'start': 0, 'end': 45, 'language': 'en'},
                                     {'start': 45, 'end': 100, 'language': 'ca'}]}


@pytest.mark.parametrize('mutation', ['gap', 'overlap', 'out_of_order', 'tail_gap',
                                      'beyond_end', 'empty', 'nan', 'bool', 'language',
                                      'first_english_model', 'second_english_model'])
def test_invalid_language_windows_fail_before_asr(mutation):
    item = spec()
    if mutation == 'gap': item['transcript_languages'][1]['start'] = 46
    elif mutation == 'overlap': item['transcript_languages'][1]['start'] = 44
    elif mutation == 'out_of_order': item['transcript_languages'].reverse()
    elif mutation == 'tail_gap': item['transcript_languages'][1]['end'] = 99
    elif mutation == 'beyond_end': item['transcript_languages'][1]['end'] = 101
    elif mutation == 'empty': item['transcript_languages'] = []
    elif mutation == 'nan': item['transcript_languages'][0]['start'] = float('nan')
    elif mutation == 'bool': item['transcript_languages'][0]['start'] = False
    elif mutation == 'language': item['transcript_languages'][0]['language'] = 'translate'
    elif mutation == 'first_english_model': item['asr_model'] = 'small.en'
    elif mutation == 'second_english_model': item['whisper_model'] = 'medium.en'
    with pytest.raises(SystemExit): clip.transcript_language_windows(item)


def test_explicit_languages_crop_original_audio_and_keep_native_words(monkeypatch):
    calls, commands = [], []
    monkeypatch.setattr(clip.subprocess, 'run', lambda cmd, **kw: commands.append((cmd, kw)))
    class Model:
        def transcribe(self, path, **kwargs):
            calls.append((path, kwargs))
            text = 'original English' if kwargs['language'] == 'en' else 'moltes gràcies'
            words = [SimpleNamespace(start=1.25, end=2.0, word=text)]
            return iter([SimpleNamespace(words=words)]), None
    result = clip.transcribe_source_words(Model(), Path('/source/audio.wav'), spec())
    assert result == [(1.25, 2.0, 'original English'), (46.25, 47.0, 'moltes gràcies')]
    assert [kw['language'] for _, kw in calls] == ['en', 'ca']
    assert all(kw['task'] == 'transcribe' for _, kw in calls)
    assert all(kw['word_timestamps'] is True for _, kw in calls)
    assert [cmd[cmd.index('-ss') + 1] for cmd, _ in commands] == ['0.0', '45.0']
    assert [cmd[cmd.index('-t') + 1] for cmd, _ in commands] == ['45.0', '55.0']
    assert all(kw['check'] is True for _, kw in commands)
    assert all(path != '/source/audio.wav' for path, _ in calls)


def test_default_english_path_is_preserved():
    calls = []
    class Model:
        def transcribe(self, path, **kwargs):
            calls.append((path, kwargs))
            return iter([SimpleNamespace(words=[SimpleNamespace(start=4, end=5, word='hello')])]), None
    assert clip.transcribe_source_words(Model(), Path('/audio.wav'),
                                        {'start': 0, 'end': 10}) == [(4.0, 5.0, 'hello')]
    assert calls[0][0] == '/audio.wav'
    assert calls[0][1]['language'] == 'en' and calls[0][1]['task'] == 'transcribe'


def test_language_boundaries_invalidate_transcript_and_subs_cache(tmp_path):
    original = spec()
    changed = copy.deepcopy(original)
    changed['transcript_languages'][0]['end'] = 44
    changed['transcript_languages'][1]['start'] = 44
    lines = [{'en': 'same source words'}]
    assert clip.transcript_fingerprint(original, lines, tmp_path) != clip.transcript_fingerprint(changed, lines, tmp_path)
    assert 'transcript_languages' in clip.SUBS_INPUT_KEYS


def test_identical_models_still_fail_for_multilingual_input(tmp_path):
    item = spec()
    item['whisper_model'] = 'small'
    with pytest.raises(SystemExit, match='同一个模型跑两遍'):
        clip.verify_transcript(item, [], tmp_path)


def test_mixed_language_gap_report_does_not_claim_english_only(tmp_path):
    item = dict(spec(), slug='mixed', url='https://youtu.be/source')
    report = clip.probe_gap_speech(item, [(60, 64)], [(61, 'gràcies')], tmp_path)
    text = report.read_text()
    assert '多语模型' in text
    assert '英语专用' not in text
    assert '可能漏了原文或发生时间边界漂移' in text
    assert 'ASR 空词不能证明静音' in text
