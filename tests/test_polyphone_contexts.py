"""A correct historical sentence must not certify new TTS contexts."""
from __future__ import annotations

import sys
import ssl
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import check_polyphones as C


@pytest.fixture
def reference_transport(tmp_path, monkeypatch):
    import measure_polyphone as M
    from tennislive.video import tts
    calls, sleeps, endpoint = [], [], []
    failures = []
    no_audio = type('NoAudioReceived', (Exception,), {'__module__': 'edge_tts.exceptions'})

    class Communicate:
        def __init__(self, text, voice, **kwargs):
            calls.append((text, voice, kwargs))

        async def stream(self):
            yield {'type': 'audio', 'data': b'partial'}
            if failures:
                raise failures.pop(0)
            yield {'type': 'audio', 'data': b'-complete'}
            yield {'type': 'WordBoundary', 'offset': 1, 'duration': 2, 'text': '重打'}

    monkeypatch.setattr(M, 'CACHE', tmp_path / 'reference-cache')
    monkeypatch.setattr(M, '_trust_ca', lambda: None)
    monkeypatch.setattr(M.time, 'sleep', sleeps.append)
    monkeypatch.setattr(tts, '_point_edge_tts_at_live_host', lambda: endpoint.append(True))
    monkeypatch.setitem(sys.modules, 'edge_tts', SimpleNamespace(
        Communicate=Communicate, exceptions=SimpleNamespace(NoAudioReceived=no_audio)))
    monkeypatch.setenv('HTTPS_PROXY', 'http://proxy.test:8080')
    return M, failures, calls, sleeps, endpoint


def test_reference_raw_text_proxy_and_exact_cache_are_preserved(reference_transport):
    M, failures, calls, sleeps, endpoint = reference_transport
    path, marks = M.synth('这一分要重打。', 'fixture', '+6%')
    before = path.read_bytes()
    assert calls == [('这一分要重打。', 'fixture', {
        'rate': '+6%', 'pitch': '+0Hz', 'boundary': 'WordBoundary',
        'proxy': 'http://proxy.test:8080'})]
    assert endpoint == [True] and not sleeps
    assert M.synth('这一分要重打。', 'fixture', '+6%') == (path, marks)
    assert path.read_bytes() == before and len(calls) == 1
    M.synth('这一分要重打。', 'fixture', '+22%')
    assert len(calls) == 2


@pytest.mark.parametrize('failure', [ssl.SSLCertVerificationError('untrusted'),
    type('SkewAdjustmentError', (Exception,), {'__module__': 'edge_tts.exceptions'})('403')])
def test_reference_fatal_failures_stop_without_sleep_or_partial_cache(reference_transport, failure):
    M, failures, calls, sleeps, _ = reference_transport
    failures.append(failure)
    with pytest.raises(RuntimeError):
        M.synth('测试参考。', 'fixture', '+6%')
    assert len(calls) == 1 and sleeps == []
    assert list(M.CACHE.iterdir()) == []


def test_reference_transient_retry_discards_partial_audio(reference_transport):
    M, failures, calls, sleeps, _ = reference_transport
    failures.extend([TimeoutError('timeout'), ConnectionError('disconnected')])
    path, marks = M.synth('测试参考。', 'fixture', '+6%')
    assert len(calls) == 3 and sleeps == [2., 6.]
    assert path.read_bytes() == b'partial-complete'
    assert marks == [{'offset': 1, 'duration': 2, 'text': '重打'}]
    assert not list(M.CACHE.glob('*.part.*'))


def test_reference_exhaustion_never_sleeps_after_last_attempt(reference_transport):
    M, failures, calls, sleeps, _ = reference_transport
    failures.extend([TimeoutError('timeout')] * 3)
    with pytest.raises(RuntimeError):
        M.synth('测试参考。', 'fixture', '+6%')
    assert len(calls) == 3 and sleeps == [2., 6.]
    assert list(M.CACHE.iterdir()) == []


@pytest.mark.parametrize("text", [
    "这一分被判重打。", "一分被判重打。", "回看后判重打。",
    "重打高芙赢分并保发。", "也因灯突然开启重打。", "重打一分。",
    "我要重打这一分。",  # legacy 要重 must not bypass the narrower 重打 evidence
])
def test_replay_historical_sentence_does_not_certify_new_context(text, monkeypatch):
    # Test the evidence selector separately from a subsequently measured homophone fix.
    monkeypatch.setattr(C.pronounce, "covered_positions", lambda _: set())
    lines, risks = C.static_report([C.Spoken("封面", text, "+6%")])
    replay = [r for r in risks if r.char == "重"]
    assert replay and all(r.intended == "chong2" for r in replay)
    assert all(r.context_recheck and not r.lexicon for r in replay)
    assert "新语境未实测" in "\n".join(lines)


def test_only_retained_sentence_can_use_old_replay_evidence(monkeypatch):
    monkeypatch.setattr(C.pronounce, "covered_positions", lambda _: set())
    _, risks = C.static_report([C.Spoken("旁白", "这一分要重打。", "+6%")])
    assert not any(r.char == "重" for r in risks)
    _, extended = C.static_report([C.Spoken("旁白", "这一分要重打，先恢复比分。", "+6%")])
    assert any(r.char == "重" and r.context_recheck for r in extended)


def test_dei_three_examples_do_not_certify_every_dei_sentence():
    _, risks = C.static_report([C.Spoken("旁白", "四比五，他还得再守一次。", "+6%")])
    assert any(r.char == "得" and r.intended == "dei3" and r.context_recheck for r in risks)
    _, retained = C.static_report([C.Spoken("旁白", "还得再守。", "+6%")])
    assert not any(r.char == "得" for r in retained)


def test_fixed_names_are_not_all_forced_into_context_warnings():
    lines, risks = C.static_report([C.Spoken("旁白", "费德勒拿到了冠军。", "+6%")])
    assert not any(r.context_recheck for r in risks)
    assert "静态筛选不是声学通过" in "\n".join(lines)


def test_reel_coverage_includes_cover_all_narration_and_enabled_outro():
    spec = {"cover": {"narration": "封面重打一分。"}, "segments": [
        {"narration": "第一段。"}, {"narration": ""}, {"narration": "第三段。"},
    ]}
    texts = C.reel_texts(spec)
    assert [s.label for s in texts] == ["封面", "第 1 段", "第 3 段", "片尾"]
    assert C.reel_texts({**spec, "outro": False}) == texts[:-1]


def test_interview_without_cards_still_checks_spoken_outro():
    from tennislive.video.outro_page import NARRATION
    texts = C.interview_texts({}, speech=lambda card: card["lead"])
    assert [(s.label, s.text, s.rate) for s in texts] == [("片尾", NARRATION, "+22%")]
    texts = C.interview_texts({"takeaway_rate": "+6%", "takeaway": {
        "close": {"lead": "下一次会更好。"},
    }}, speech=lambda card: card["lead"])
    assert texts[0].rate == "+6%" and texts[-1].rate == "+22%"


def test_registered_source_episode_checks_actual_opening_beats_and_outro():
    from tennislive.render.tournament_story import find_story_by_slug
    from tennislive.video import explainer as E
    from tennislive.video.outro_page import NARRATION
    story = find_story_by_slug(E._DEFAULT_SLUG)
    assert story is not None
    expected = [E.readable(s.narration) for s in E.explainer_script(story)
                if (s.narration or "").strip()] + [NARRATION]
    texts = C.explainer_texts(E._DEFAULT_SLUG)
    assert [s.text for s in texts] == expected
    assert all(s.rate == "+22%" for s in texts)


def test_cli_missing_dependency_is_unchecked_not_success(monkeypatch, capsys):
    monkeypatch.setattr(C, "pypinyin_available", lambda: False)
    monkeypatch.setattr(C, "spoken_texts", lambda *args: pytest.fail("must not load corpus"))
    assert C.main(["--slug", "demo"]) == 2
    assert "没查" in capsys.readouterr().out


@pytest.mark.parametrize("verdict", [None, "uncertain", "unreliable", "skipped"])
def test_measure_incomplete_results_never_return_success(verdict, monkeypatch):
    risk = C.Risk("旁白", "重打。", 0, "重", "重打", "chong2", "zhong4",
                  ["zhong4"], "+6%", False)
    if verdict:
        risk.measured["verdict"] = verdict
    monkeypatch.setattr(C, "pypinyin_available", lambda: True)
    monkeypatch.setattr(C, "spoken_texts", lambda *args: [C.Spoken("旁白", "重打。", "+6%")])
    monkeypatch.setattr(C, "static_report", lambda *args: (["static check done"], [risk]))
    monkeypatch.setattr(C, "measure_risks", lambda *args, **kwargs: (["not complete"], []))
    assert C.main(["--slug", "demo", "--measure"]) == 2


def test_measure_missing_dependencies_is_not_success_even_with_no_risks(monkeypatch):
    monkeypatch.setattr(C, "pypinyin_available", lambda: True)
    monkeypatch.setattr(C, "spoken_texts", lambda *args: [C.Spoken("旁白", "他赢了。", "+6%")])
    monkeypatch.setattr(C, "static_report", lambda *args: (["static check done"], []))
    monkeypatch.setattr(C, "measure_risks", lambda *args, **kwargs: (["这趟没量：缺依赖"], []))
    assert C.main(["--slug", "demo", "--measure"]) == 2
