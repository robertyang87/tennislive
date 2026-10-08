"""Inspect the source ASS rather than accepting a declared native cold open."""
import copy

import pytest

from tools import check_interview_landed as ci
from tools.interview_source_gate import finalize_source_contract


def verified_spec():
    url = "https://www.youtube.com/watch?v=nativeTest1"
    spec = {"slug": "native-opening-demo", "url": url, "start": 100.0, "end": 160.0,
            "requested_content_type": "on_court", "interview_kind": "赛后场上采访",
            "opening": {"kind": "match_end", "lead_in": 15.0,
                        "why": "Actual native match point, celebration and commentary precede the interview."},
            "match": {"id": "test-match", "event": "Test event", "round": "Final",
                      "winner": "Winner", "loser": "Loser", "participants": ["Winner", "Loser"]},
            "source_verification": {"source_id": "youtube:nativeTest1", "source_url": url,
                                    "source": "Official event", "status": "verified",
                                    "detected_type": "on_court", "method": "human_visual_verdict",
                                    "evidence": [{"kind": "visual_verdict", "note": "Fixture source verified."}]}}
    return finalize_source_contract(spec)


def write_body(tmp_path, *, styles=("EN", "ZH"), before=True):
    path = tmp_path / "native-opening-demo.ass"
    a, b = ("0:00:02.00", "0:00:05.00") if before else ("0:00:20.00", "0:00:25.00")
    path.write_text("\n".join(f"Dialogue: 0,{a},{b},{s},,0,0,0,,Match point" for s in styles))
    return path


def test_native_opening_reads_the_actual_body_ass(tmp_path):
    spec = verified_spec()
    write_body(tmp_path)
    ok, detail = ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)
    assert ok and "原生前 15s" in detail
    # The file for a standalone lead cannot substitute for the native body.
    (tmp_path / "native-opening-demo.ass").rename(tmp_path / "_lead.ass")
    assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)[0]


@pytest.mark.parametrize("styles,before", [(('EN',), True), (('ZH',), True),
                                          ((), True), (('EN', 'ZH'), False)])
def test_native_opening_rejects_missing_or_post_opening_subtitles(tmp_path, styles, before):
    write_body(tmp_path, styles=styles, before=before)
    assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", verified_spec())[0]


def test_native_opening_rejects_mismatched_and_cross_cut_cues(tmp_path):
    spec = verified_spec()
    body = write_body(tmp_path)
    body.write_text("Dialogue: 0,0:00:14.00,0:00:17.00,EN,,0,0,0,,Match result\n"
                    "Dialogue: 0,0:00:14.00,0:00:17.00,ZH,,0,0,0,,赛果\n")
    assert ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)[0]
    body.write_text(body.read_text().replace("17.00,ZH", "15.00,ZH"))
    assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)[0]


@pytest.mark.parametrize("change", ["status", "url", "signature"])
def test_native_opening_requires_a_live_source_contract(tmp_path, change):
    spec = verified_spec()
    write_body(tmp_path)
    assert ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)[0]
    if change == "status":
        spec["source_verification"]["status"] = "needs_review"
    elif change == "url":
        spec["url"] = "https://www.youtube.com/watch?v=otherSource"
    else:
        spec["source_verification"]["attestation_sha256"] = "0" * 64
    assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)[0]


@pytest.mark.parametrize("duration", [0, -1, True, float('nan'), float('inf'), 41, 60])
def test_native_opening_rejects_invalid_duration(tmp_path, duration):
    spec = verified_spec()
    write_body(tmp_path)
    spec["opening"]["lead_in"] = duration
    assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", spec)[0]


def test_real_missing_independent_lead_is_not_hidden_by_native_subtitles(tmp_path):
    spec = verified_spec()
    write_body(tmp_path)
    for altered in ({"kind": "none", "why": "Independent interview source"},
                    {"kind": "match_end", "lead_in": 15, "why": ""},
                    {"kind": "unknown", "lead_in": 15, "why": "Unverified opening"}):
        bad = copy.deepcopy(spec)
        bad["opening"] = altered
        assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", bad)[0]
    explicit = copy.deepcopy(spec)
    explicit["lead_in"] = {"subs": []}
    assert not ci.bilingual_lead_ok(tmp_path / "_lead.ass", explicit)[0]
