"""Per-call deterministic width reuse preserves line choices and rejection."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'src'))
import build_interview_clip as C


def _words():
    return [(float(n), 'repeat') for n in range(45)]


def test_default_width_reuses_text_without_changing_any_line(monkeypatch):
    calls = []
    def measured(text):
        calls.append(text)
        return len(text) * 7
    monkeypatch.setattr(C, 'ruler_width', lambda name: measured)
    raw = C.segment(_words(), 0, 46, width=measured, budget=200)
    raw_count = len(calls)
    calls.clear()
    memo = C.segment(_words(), 0, 46, budget=200)
    assert memo == raw
    assert len(calls) < raw_count
    assert len(calls) == len(set(calls))


def test_subsequent_call_and_different_ruler_do_not_share_cached_advances(monkeypatch):
    factor = [1]
    calls = []
    def ruler(name):
        scale = factor[0] * (2 if name == 'noto-40' else 1)
        def width(text):
            calls.append((name, scale, text))
            return len(text) * scale
        return width
    monkeypatch.setattr(C, 'ruler_width', ruler)
    first = C.segment(_words(), 0, 46, budget=100, ruler='inter-46')
    factor[0] = 4
    second = C.segment(_words(), 0, 46, budget=100, ruler='inter-46')
    third = C.segment(_words(), 0, 46, budget=100, ruler='noto-40')
    assert first != second != third
    assert {scale for _, scale, _ in calls} == {1, 4, 8}


def test_explicit_width_is_not_memoized(monkeypatch):
    calls = []
    def custom(text):
        calls.append(text)
        return len(text) * 7
    C.segment(_words(), 0, 46, budget=200, width=custom)
    assert len(calls) > len(set(calls))


def test_single_word_that_exceeds_budget_still_fails_width_gate(monkeypatch):
    monkeypatch.setattr(C, 'ruler_width', lambda name: lambda text: len(text) * 100)
    lines = C.segment([(0, 'Supercalifragilisticexpialidocious')], 0, 5)
    assert len(lines) == 1
    assert C.en_problems(lines)
