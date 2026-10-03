"""Two real broadcasts of one match can place their scoreboards differently.

The same source, segment box and probe scan must travel together. An override
must not silently fall back to the primary broadcaster's bottom-left position.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel
import probe_board as pb

OFFICIAL = [86, 827, 554, 988]
SUPPLEMENT = [14, 964, 392, 1072]
URLS = {"official": "https://example.test/official", "supplement": "https://example.test/supplement"}


def spec():
    return {"slug": "new-multisource", "cover": {}, "scorebox": OFFICIAL,
            "sources": URLS, "primary": "official", "segments": [
                {"source": "official", "start": 1, "end": 2, "score_inset": True},
                {"source": "supplement", "start": 1, "end": 2, "score_inset": True,
                 "scorebox": SUPPLEMENT},
                {"source": "official", "start": 2, "end": 3, "score_inset": True}]}


def parse(data):
    return reel.parse_segments(data, {key: Path(key + ".mp4") for key in URLS}, "official")


def board(box, *, present=True):
    edge = box[2] if present else None
    return {"version": 1, "fps": 5, "t0": 0.0, "frames": 30,
            "scans": [{"box": box, "frames": 30, "profiles": {"wta": {
                "present": 30 if present else 0, "unresolved": 0,
                "runs": [[30, edge, edge]]}}}]}


def test_mix_broadcasts_keeps_each_source_anchor_and_does_not_mutate_default():
    data = spec()
    segments = parse(data)
    assert [s.score_inset for s in segments] == [tuple(OFFICIAL), tuple(SUPPLEMENT), tuple(OFFICIAL)]
    assert all(s.score_inset_auto for s in segments)
    assert data["scorebox"] == OFFICIAL
    assert pb.scoreboxes_by_url(data, URLS) == {
        URLS["official"]: [OFFICIAL], URLS["supplement"]: [SUPPLEMENT]}


@pytest.mark.parametrize("bad", [None, [14, 964, 392], [14, 964, 14, 1072],
                               [-1, 964, 392, 1072], [True, 964, 392, 1072]])
def test_bad_override_is_rejected_instead_of_using_good_global_box(bad):
    data = spec()
    data["segments"][1]["scorebox"] = bad
    with pytest.raises(reel.ReelError, match="第 2 段 scorebox"):
        parse(data)


def test_segment_box_without_inset_is_a_dead_key():
    data = spec()
    data["segments"][1]["score_inset"] = False
    with pytest.raises(reel.ReelError, match="死键"):
        parse(data)


def test_fixed_right_edge_uses_override_left_top_bottom():
    data = spec()
    data["segments"][1]["score_inset"] = {"x2": 400}
    segments = parse(data)
    assert segments[1].score_inset == (14, 964, 400, 1072)
    assert not segments[1].score_inset_auto


def test_probe_audits_each_segment_against_its_own_source_box():
    data = spec()
    probes = {URLS["official"]: {"url": URLS["official"], "board": board(OFFICIAL)},
              URLS["supplement"]: {"url": URLS["supplement"], "board": board(SUPPLEMENT)}}
    hard, soft = pb.board_findings(data, parse(data), probes, URLS, profile="wta", tail=0)
    assert hard == [] and soft == []
    # The primary has a board throughout; the supplemental segment has none.
    # Reading the primary's scan instead would wrongly let this film through.
    probes[URLS["supplement"]]["board"] = board(SUPPLEMENT, present=False)
    hard, soft = pb.board_findings(data, parse(data), probes, URLS, profile="wta", tail=0)
    assert len(hard) == 1 and "第 2 段" in hard[0] and "一帧板都没认出" in hard[0]
    assert soft == []


def test_wrong_box_scan_stays_unchecked_and_cannot_be_used_as_override_evidence():
    data = spec()
    probes = {URLS["official"]: {"url": URLS["official"], "board": board(OFFICIAL)},
              URLS["supplement"]: {"url": URLS["supplement"], "board": board(OFFICIAL)}}
    hard, soft = pb.board_findings(data, parse(data), probes, URLS, profile="wta", tail=0)
    assert hard == []  # Preserve the existing missing-scan policy, without claiming a pass.
    assert len(soft) == 1 and "都对不上" in soft[0]


def test_reprobe_uses_source_override_not_primary_broadcast_box(monkeypatch):
    data = spec()
    monkeypatch.setenv("GITHUB_REF_NAME", "codex/test")
    monkeypatch.setattr(reel, "claim_probes", lambda s: ({}, []))
    commands = reel._reprobe_commands(data, {}, URLS)
    assert "-f scorebox=86,827,554,988" in commands[URLS["official"]]
    assert "-f scorebox=14,964,392,1072" in commands[URLS["supplement"]]
    assert "-f scorebox=14,964,392,1072" in pb.reprobe_command(
        data, "supplement", URLS["supplement"], {})
