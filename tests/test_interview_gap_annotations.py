import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest

from tools import build_interview_clip as clip


def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(clip, 'ROOT', tmp_path)
    work = tmp_path / 'work'; work.mkdir()
    (work / 'cap_asr.json3').write_text(json.dumps({'events': [
        {'tStartMs': 0, 'dDurationMs': 3000, 'segs': [{'utf8': 'out today'}]},
        {'tStartMs': 6000, 'dDurationMs': 2000, 'segs': [{'utf8': 'Com sabeu'}]},
    ]}))
    source = 'a' * 64
    proof = {'source_sha256': source, 'window': [3, 6],
             'status': 'uncertain speech identity, applause supported',
             'method': 'ASR plus AudioSet, no human listening claim',
             'evidence': {'first': {'result': {'results': [{'model': 'medium'}]}},
                          'second': {'result': {'results': [{'model': 'tiny'}]}},
                          'audioset': {'result': []}}}
    path = tmp_path / 'review.json'; path.write_text(json.dumps(proof))
    annotation = {'start': 3, 'end': 6, 'kind': 'applause_with_indistinct_voices',
                  'source_sha256': source,
                  'evidence': {'path': 'review.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
                  'why': 'Keep complete original audio and explicitly label unresolved voices; no listening or silence attestation.'}
    spec = {'slug': 'sample', 'url': 'https://youtu.be/sample', 'start': 0, 'end': 8,
            'asr_model': 'small', 'whisper_model': 'medium',
            'source_verification': {'evidence': [{'kind': 'actual_source_file', 'sha256': source}]},
            'caption_gap_annotations': [annotation]}
    lines = [{'a': 0, 'b': 4.4, 'en': 'out today.'}, {'a': 6, 'b': 8, 'en': 'Com sabeu.'}]
    return spec, lines, work


@pytest.mark.parametrize('bad', ['overlap_speech', 'wrong_source', 'stale_proof', 'outside', 'long', 'speech_label'])
def test_conservative_events_reject_unbound_or_hidden_speech(monkeypatch, tmp_path, bad):
    spec, _, work = setup(monkeypatch, tmp_path)
    row = spec['caption_gap_annotations'][0]
    if bad == 'overlap_speech': row['start'] = 2.5
    elif bad == 'wrong_source': row['source_sha256'] = 'b' * 64
    elif bad == 'stale_proof': (tmp_path / 'review.json').write_text('{}')
    elif bad == 'outside': row['end'] = 9
    elif bad == 'long': row['start'] = 0
    elif bad == 'speech_label': row['kind'] = 'verified_silence'
    with pytest.raises(SystemExit): clip.conservative_gap_annotations(spec, work)


def test_event_is_separate_from_words_and_cuts_only_caption_hold(monkeypatch, tmp_path):
    spec, lines, work = setup(monkeypatch, tmp_path)
    monkeypatch.setattr(clip, 'wants_topbar', lambda _: False)
    old = copy.deepcopy(lines)
    original_cap = (work / 'cap_asr.json3').read_bytes()
    clip.write_ass(lines, ['今天到场', '大家知道'], 0, work / 'out.ass', spec, duration=8)
    text = (work / 'out.ass').read_text()
    assert '0:00:00.00,0:00:03.00,EN' in text
    assert '0:00:03.00,0:00:06.00,EN,,0,0,0,,[Applause and indistinct voices]' in text
    assert lines == old
    assert (work / 'cap_asr.json3').read_bytes() == original_cap


def test_lexical_speech_still_blocks_event_resolution(monkeypatch, tmp_path):
    spec, lines, work = setup(monkeypatch, tmp_path)
    def attest(words):
        (work / clip.GAP_VAD_ATTESTATION).write_text(json.dumps({
            'status': 'pass', 'method': 'silero_vad_plus_dual_asr_coverage',
            'sha256': clip.transcript_fingerprint(spec, lines, work), 'url': clip.verdict_source(spec),
            'results': [{'key': '3.0-6.0', 'status': 'speech_detected',
                         'second_asr_words': words, 'speech_seconds': .55}]}))
    attest(['new', 'actual', 'sentence'])
    assert clip.auto_gap_closures(spec, lines, work) == {}
    attest([])
    result = clip.auto_gap_closures(spec, lines, work)['3.0-6.0']
    assert '保守声音事件标注' in result
    assert '未认证静音' in result
    assert '0.550s' in result


def test_annotation_changes_fingerprint_without_changing_asr(monkeypatch, tmp_path):
    spec, lines, work = setup(monkeypatch, tmp_path)
    original = clip.transcript_fingerprint(spec, lines, work)
    spec['caption_gap_annotations'][0]['why'] += ' Additional explicit uncertainty.'
    assert original != clip.transcript_fingerprint(spec, lines, work)


def test_film_revision_tracks_event_but_not_review_prose(monkeypatch, tmp_path):
    from tools import interview_revision
    spec, _, _ = setup(monkeypatch, tmp_path)
    first = interview_revision.content_sha256(spec)
    spec['caption_gap_annotations'][0]['why'] += ' Review clarification.'
    assert interview_revision.content_sha256(spec) == first
    spec['caption_gap_annotations'][0]['end'] = 5.5
    assert interview_revision.content_sha256(spec) != first


def test_landed_qc_requires_actual_bilingual_event_not_just_extra_count(monkeypatch, tmp_path):
    from tools import check_interview_landed as qc
    spec, lines, work = setup(monkeypatch, tmp_path)
    spec['zh'] = ['今天到场', '大家知道']
    monkeypatch.setitem(sys.modules, 'build_interview_clip', clip)
    monkeypatch.setattr(clip, 'wants_topbar', lambda _: False)
    ass = work / 'out.ass'
    clip.write_ass(lines, spec['zh'], 0, ass, spec, duration=8)
    assert qc.bilingual_body_ok(ass, spec)[0]
    ass.write_text(ass.read_text().replace('[Applause and indistinct voices]', 'fabricated speech'))
    assert not qc.bilingual_body_ok(ass, spec)[0]
