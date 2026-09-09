"""Regression for QC crashing on generated title cards (run 34328318645)."""
import importlib.util
from pathlib import Path

import pytest


def test_generated_cards_advance_timeline_without_source_audio_windows():
    path = Path(__file__).resolve().parents[1] / "tools" / "check_reel_landed.py"
    module_spec = importlib.util.spec_from_file_location("landed_cards", path)
    landed = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(landed)
    spec = {"segments": [
        {"start": 157.12, "end": 163.23},
        {"title_card": {"title": "决胜盘"}, "seconds": 3.2},
        {"stat_card": True, "seconds": 10},
        {"image": "evidence.jpg", "seconds": 4, "narration": "证据"},
        {"start": 122.17, "end": 125.49},
    ]}
    windows = landed.quiet_windows(spec, 1.2)
    assert len(windows) == 2
    assert windows[0] == pytest.approx((1.2, 6.11, 157.12))
    assert windows[1] == pytest.approx((24.51, 3.32, 122.17))
    evidence = landed.evidence_windows(spec, 1.2)
    assert len(evidence) == 3
    assert evidence[-1] == pytest.approx((20.51, 24.51))
