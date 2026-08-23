"""赛后开麦 L0 内容身份契约：不联网的正反向判据。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import interview_source_gate as gate  # noqa: E402


def _item(**extra) -> dict:
    row = {
        "id": "vid1",
        "url": "https://example.test/vid1",
        "title": "Alexander Zverev On-Court Interview | Cincinnati 2026",
        "source": "Cincinnati Open",
    }
    row.update(extra)
    return row


def _formal_spec() -> dict:
    verification = gate.candidate_verification(_item(), verdicts={})
    spec = {
        "slug": "zverev-cincinnati-2026-qf",
        "url": "https://example.test/vid1",
        "requested_content_type": "on_court",
        "interview_kind": "赛后场上采访",
        "source_verification": verification,
        "match": {
            "id": "2026:cincinnati:qf:alexander-zverev",
            "event": "辛辛那提大师赛",
            "round": "四分之一决赛",
            "winner": "兹维列夫",
            "loser": "阿特马内",
            "participants": ["兹维列夫", "阿特马内"],
        },
    }
    return gate.finalize_source_contract(spec)


def test_未知频道标题写oncourt也只能待复核():
    got = gate.candidate_verification(_item(source="Unknown Uploads"), verdicts={})
    assert got["status"] == "pending" and got["method"] == "needs_visual_review"


def test_注册官方源且标题明确场上采访可进入生产():
    got = gate.candidate_verification(_item(), verdicts={})
    assert got["status"] == "verified"
    assert got["method"] == "official_explicit_oncourt"


def test_WTA集锦片尾含采访但起点未知只能待复核():
    got = gate.candidate_verification(_item(
        source="WTA", tail_interview=True, duration_s=347,
        title="MATCH HIGHLIGHTS | Cincinnati 2026"), verdicts={})
    assert got["status"] == "pending"
    assert got["method"] == "wta_highlight_tail"
    assert "起点" in got["reason"]


def test_人工判成发布会优先级高于标题规则():
    got = gate.candidate_verification(
        _item(), verdicts={"vid1": {"verdict": "press", "by": "reviewer"}})
    assert got["status"] == "rejected" and got["detected_type"] == "press"


def test_正式契约绑定来源与比赛且改字即失效():
    spec = _formal_spec()
    attestation = gate.validate_source_contract(spec)
    assert len(attestation) == 64

    spec["match"]["loser"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="attestation_sha256"):
        gate.validate_source_contract(spec)


def test_演播室不能靠重新签名伪装成场上采访():
    spec = _formal_spec()
    spec["source_verification"].update({
        "status": "rejected", "detected_type": "studio", "method": "human_visual_verdict",
    })
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="status.*verified|detected_type"):
        gate.validate_source_contract(spec)


def test_轮次或逐场ID仍是unknown不能签成正式来源():
    spec = _formal_spec()
    spec["match"]["round"] = "unknown"
    spec["match"]["id"] = "2026:cincinnati:unknown:alexander-zverev"
    gate.finalize_source_contract(spec)
    with pytest.raises(gate.SourceContractError, match="占位值|unknown"):
        gate.validate_source_contract(spec)
