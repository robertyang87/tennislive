"""Regression cases from the September 9 production incident. No publication."""
import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_interview_request as builder
import production_cache as cache
import tactical_research as research
from video_sla import finish


def setup_request(tmp_path, monkeypatch, spec, req):
    specs, output = tmp_path / 'specs', tmp_path / 'output'
    specs.mkdir(); output.mkdir()
    path = tmp_path / 'request.json'
    req['slug'] = 'demo'
    path.write_text(json.dumps(req))
    (specs / 'demo.json').write_text(json.dumps(spec))
    (output / 'demo').mkdir()
    (output / 'demo/cap_asr.json3').write_text('{}')
    monkeypatch.setattr(builder, 'SPECS', specs)
    monkeypatch.setattr(builder, 'OUTDIR', output)
    return path, specs / 'demo.json', output / 'demo'


def test_reviewed_spec_is_not_regenerated_from_stale_cover_or_rebuild_flag(tmp_path, monkeypatch):
    path, spec, _ = setup_request(tmp_path, monkeypatch,
        {'transcript_verified': True, 'cover': {'zoom': 1.8}},
        {'cover': {'zoom': 1.1}, '_rebuild_once': True})
    assert not builder.is_pending(path)
    req = json.loads(path.read_text())
    req.update(revision='shorter-v2', expected_spec_sha256=cache.file_digest(spec))
    path.write_text(json.dumps(req))
    assert builder.is_pending(path)
    spec.write_text('{"transcript_verified":true,"cover":{"zoom":2}}')
    assert not builder.is_pending(path), 'stale expected hash must not authorize a new overwrite'


def test_published_marker_protects_even_unreviewed_spec(tmp_path, monkeypatch):
    path, _, out = setup_request(tmp_path, monkeypatch, {}, {'_rebuild_once': True})
    (out / 'pushed.json').write_text('{"status":"accepted"}')
    assert not builder.is_pending(path)


def test_consumed_request_does_not_revert_editorial_changes(tmp_path, monkeypatch):
    req = {'slug': 'demo', 'url': 'https://youtu.be/x', 'cover': {'zoom': 1.5}}
    spec = {'url': req['url'], 'cover': {'zoom': 1.9},
            '_request_origin': {'request_sha256': builder._request_identity(req)}}
    path, _, _ = setup_request(tmp_path, monkeypatch, spec, req)
    assert not builder.is_pending(path)
    req['cover']['zoom'] = 2
    path.write_text(json.dumps(req))
    assert builder.is_pending(path)


def test_corrupt_cache_recomputed_and_changed_inputs_miss():
    calls = []
    def produce():
        calls.append(1); return ['good']
    assert cache.cached_json('example', {'text': 'one'}, produce) == ['good']
    cache.cached_json('example', {'text': 'one'}, produce)
    assert len(calls) == 1
    path = cache.root() / 'example' / (cache.digest({'text': 'one'}) + '.json')
    path.write_text('{"sha256":"wrong","value":["bad"]}')
    assert cache.cached_json('example', {'text': 'one'}, produce) == ['good']
    cache.cached_json('example', {'text': 'two'}, produce)
    assert len(calls) == 3


def test_foreign_host_and_wrapper_are_not_read():
    assert research.allowed('https://www.tennisabstract.com/blog/a')
    assert not research.allowed('https://tennisabstract.com.evil.test/blog/a')
    assert not research.allowed('https://news.google.com/rss/articles/x')


def test_research_does_not_promote_history_or_unmatched_quotes_to_facts():
    identity = {'home': 'Aryna Sabalenka', 'away': 'Linda Noskova', 'event': 'US Open', 'year': 2026}
    url = 'https://braingametennis.com/test'
    claim = {'claim': '接发落点的变化', 'url': url, 'match_verified': True,
             'evidence_excerpt': 'deeper returns',
             'footage': {'source_url': 'https://youtu.be/x', 'start': 10, 'end': 20}}
    packet = {'identity': identity, 'sources': [{'url': url, 'status': 'read', 'excerpts': ['She hit deeper returns.']}], 'claims': [claim]}
    assert '接发落点' in research.verified_context(packet, identity=identity)
    assert not research.verified_context(packet, identity={**identity, 'year': 2025})
    claim['match_verified'] = False
    assert not research.verified_context(packet, identity=identity)
    claim['match_verified'] = True
    claim['evidence_excerpt'] = 'made up'
    assert not research.verified_context(packet, identity=identity)


def test_research_timeout_returns_explicit_fallback(monkeypatch):
    import subprocess
    monkeypatch.setenv('TENNISLIVE_TACTICAL_RESEARCH', '1')
    def slow(*a, **kw):
        assert kw['timeout'] == 2
        raise subprocess.TimeoutExpired(a[0], 2)
    monkeypatch.setattr(research.subprocess, 'run', slow)
    result = research.research(home='A', away='B', event='US Open', year=2026, budget=2)
    assert result['status'] == 'timeout' and result['sources'] == []


def test_preflight_uses_publisher_rules_before_any_video(tmp_path):
    import subprocess
    spec = tmp_path / 'demo.json'
    spec.write_text(json.dumps({'column': '赛后开麦', 'push': {'summary': '赛后回答', 'matchup': '甲 vs 乙'}}))
    copy = tmp_path / 'demo.xhs.txt'
    copy.write_text('正文\n#一 #二 #三 #四 #五 #六')
    command = [sys.executable, 'tools/push_reel.py', '--stage', 'check', '--copy', str(copy),
               '--outdir', str(tmp_path / 'no-video'), '--column', '赛后开麦', '--date', '2026-09-09']
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode and '6 个 tag' in result.stderr
    copy.write_text('正文\n#网球')
    assert subprocess.run(command, capture_output=True).returncode == 0
    assert not (tmp_path / 'no-video').exists()


def test_sla_is_bound_to_new_film_and_keeps_revision_history(tmp_path):
    from datetime import datetime, timezone
    film, meta, spec = tmp_path/'demo.mp4', tmp_path/'render.json', tmp_path/'demo.json'
    film.write_bytes(b'first'); spec.write_text('{}')
    now = datetime(2026, 9, 9, tzinfo=timezone.utc)
    args = dict(received_at='2026-09-09T00:00:00Z', artifact=film, metadata=meta,
                pipeline='interview', slug='demo', spec=spec, now=now)
    first = finish(**args)
    film.write_bytes(b'second')
    second = finish(**args)
    assert first['film_sha256'] != second['film_sha256']
    assert json.loads(meta.read_text())['production_sla_history'] == [first]
