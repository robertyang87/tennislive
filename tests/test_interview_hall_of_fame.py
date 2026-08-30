"""名人堂致辞复用赛后开麦版式，但不得伪造比赛、对手或冷开场。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_interview_request as request_builder  # noqa: E402
import build_interview_clip as clip_builder  # noqa: E402
import interview_source_gate as gate  # noqa: E402
from check_interview_landed import bilingual_lead_ok  # noqa: E402


def _request() -> dict:
    return {
        "slug": "federer-ithf-2026-induction-speech",
        "url": "https://www.youtube.com/watch?v=fQXTNAnY0zE",
        "source": "Tennis Channel",
        "source_title": (
            "Roger Federer International Tennis Hall of Fame Induction Speech | "
            "ITHF 2026"
        ),
        "requested_content_type": "ceremony",
        "ceremony_subtype": "hall_of_fame_induction",
        "interview_kind": "名人堂入选致辞",
        "event": "2026 国际网球名人堂入选典礼",
        "featured_player": "费德勒",
        "subject": {
            "id": "2026:ithf:induction:roger-federer",
            "event": "2026 国际网球名人堂入选典礼",
            "name": "费德勒",
            "role": "入选者",
        },
        "opening": {"kind": "none", "why": "按编辑决定从完整致辞第一句开始"},
        "cover": {
            "frame_at": 30.0,
            "title": ["名人堂叫作 Fame", "但成名从不是目标"],
            "sub": "费德勒 · 完整入选致辞",
            "tag": "2026 纽波特 · 费德勒",
        },
        "takeaway": {"close": {"point": "这仍不是告别", "ask": "哪句话最打动你？"}},
        "push": {"matchup": "费德勒", "summary": "费德勒名人堂完整致辞", "auto": True},
    }


def test_官方名人堂入选致辞标题被识别为ceremony():
    assert gate.explicit_title_type(_request()["source_title"]) == "ceremony"


def test_名人堂正式契约绑定人物而不是伪造比赛():
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    assert spec["interview_kind"] == "名人堂入选致辞"
    assert spec["match"] == {}
    assert spec["subject"]["name"] == "费德勒"
    assert spec["source_verification"]["subject_id"] == spec["subject"]["id"]
    assert gate.content_identity_id(spec) == spec["subject"]["id"]
    assert len(gate.validate_source_contract(spec)) == 64


def test_名人堂人物身份被篡改会使L0失效():
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    spec["subject"]["name"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="L0 attestation"):
        gate.validate_source_contract(spec)


def test_名人堂顶栏不需要对手和比分(monkeypatch):
    monkeypatch.setattr(clip_builder, "_measure_at", lambda kind, size, text: len(text) * size)
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    assert clip_builder.header_lines(spec) == (
        "2026 国际网球名人堂入选典礼",
        "费德勒 · 名人堂入选致辞",
    )


def test_已核验入选典礼可以按编辑决定不用冷开场(tmp_path):
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    ok, detail = bilingual_lead_ok(tmp_path / "missing.ass", spec)
    assert ok and "显式例外" in detail
