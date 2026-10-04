"""Declared profiles must agree with the existing broadcast calibration."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as b


def _spec(declared, *, enabled=True, line="2026 WTA1000 北京 第二轮"):
    return {"scoreboard_profile": declared, "topbar": {"line1": line},
            "segments": [{"score_inset": enabled}]}


@pytest.mark.parametrize("declared", ["wta", "wta_left"])
@pytest.mark.parametrize("enabled", [True, False])
def test_declared_wta_keeps_existing_output(declared, enabled):
    assert b.scoreboard_profile(_spec(declared, enabled=enabled)) == (
        "wta" if enabled else None)


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("declared", ["unknown", "", None, {}, []])
def test_unknown_declarations_fail_even_without_inset(declared, enabled):
    with pytest.raises(b.ReelError, match="未标定"):
        b.scoreboard_profile(_spec(declared, enabled=enabled))


@pytest.mark.parametrize("enabled", [True, False])
def test_calibrated_conflict_fails_even_without_inset(enabled):
    with pytest.raises(b.ReelError, match="冲突"):
        b.scoreboard_profile(_spec("atp", enabled=enabled))


def test_declaration_cannot_invent_calibration():
    with pytest.raises(b.ReelError, match="冲突"):
        b.scoreboard_profile(_spec("wta_left", line="2026 戴维斯杯"))


def test_declared_band_profile_retains_band_output():
    spec = _spec("band-legacy", line="2026 ATP250 成都站")
    spec["layout"] = "band"
    assert b.scoreboard_profile(spec) == "band-legacy"
