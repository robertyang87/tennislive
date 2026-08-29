from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_interview_landed import bilingual_lead_ok

def spec(kind="farewell", status="verified", method="official_explicit_farewell"):
    return {
        "requested_content_type": kind,
        "opening": {"kind": "none"},
        "source_verification": {"status": status, "method": method},
    }

def test_verified_official_farewell_may_skip_separate_lead(tmp_path):
    ok, detail = bilingual_lead_ok(tmp_path / "missing.ass", spec())
    assert ok and "显式例外" in detail

def test_ordinary_interview_still_requires_lead(tmp_path):
    ok, _ = bilingual_lead_ok(tmp_path / "missing.ass", spec(kind="on_court"))
    assert not ok

def test_unverified_farewell_still_requires_lead(tmp_path):
    ok, _ = bilingual_lead_ok(tmp_path / "missing.ass", spec(status="pending"))
    assert not ok
