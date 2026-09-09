"""Full-match H:MM must not be parsed as media M:SS."""
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("text, seconds", [
    ("4:28", 16080),
    ("0:49", 2940),
    ("2:05:30", 7530),
])
def test_full_match_duration_seconds(text, seconds):
    path = Path(__file__).resolve().parents[1] / "tools" / "promote_reel_draft.py"
    spec = importlib.util.spec_from_file_location("promote_duration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._match_duration_seconds(text) == seconds
