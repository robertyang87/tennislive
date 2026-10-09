"""The owner approved one exact Asian Games film, never unknown W/UE as zero."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import winners_ue_gate as G


def approved():
    return json.loads((ROOT / "specs/reels/wang-xiyu-eala-asian-games-2026-sf.json").read_text())


def test_exact_match_keeps_unknown_rows_absent():
    s = approved()
    assert G.problem(s) is None
    assert s["stats"]["_winners_ue_omission"] == G.WANG_EALA_OMISSION
    for side in ("a", "b"):
        assert not {"winners", "ue"} & s["stats"][side].keys()
    assert s["stats"]["a"]["pts_won"] == 98
    assert s["stats"]["b"]["pts_won"] == 88


@pytest.mark.parametrize("key,value", [
    ("status", "scheduled"), ("source", "official_wta"),
    ("source_id", "TEN.W.SINGLES-----------.FNL-.000100--"),
    ("date", "2026-01-10"), ("date", "2026-10-02"),
    ("winner_result", "5-7 7-5 6-4"), ("winner_result", "6-3 3-6 2-6"),
    ("winner", "王欣瑜"), ("winner", "伊埃拉"), ("loser", "王曦雨"),
    ("participants", ["伊埃拉", "王曦雨"]),
    ("set_scores_home_away", [[6, 3], [3, 6], [2, 6]]),
])
def test_match_identity_date_and_score_cannot_drift(key, value):
    s = approved(); s["_match"][key] = value
    assert G.problem(s)


@pytest.mark.parametrize("key,value", [
    ("eyebrow", "赛后开麦"), ("winner", "王欣瑜"), ("result", "6-3 3-6 2-6"),
    ("matchup", []),
    ("matchup", [{"name": "伊埃拉", "name_en": "Alexandra Eala"},
                 {"name": "王曦雨", "name_en": "Xiyu Wang"}]),
    ("matchup", [{"name": "王曦雨", "name_en": "Xinyu Wang"},
                 {"name": "伊埃拉", "name_en": "Alexandra Eala"}]),
    ("matchup", [{"name": "王曦雨", "name_en": "Xiyu Wang"}]),
])
def test_cover_requires_two_correct_ordered_players(key, value):
    s = approved(); s["cover"][key] = value
    assert G.problem(s)


@pytest.mark.parametrize("side", ["a", "b"])
@pytest.mark.parametrize("key", ["winners", "ue"])
@pytest.mark.parametrize("value", [None, 0, 24, False, "0"])
def test_omission_never_allows_unknown_zero_or_invented_numbers(side, key, value):
    s = approved(); s["stats"][side][key] = value
    assert G.problem(s)


@pytest.mark.parametrize("side", ["a", "b"])
@pytest.mark.parametrize("value", [None, [], 0])
def test_both_statistics_columns_must_be_objects(side, value):
    s = approved(); s["stats"][side] = value
    assert G.problem(s)


@pytest.mark.parametrize("side", ["a", "b"])
def test_missing_statistics_column_is_rejected_without_crashing(side):
    s = approved(); del s["stats"][side]
    assert G.problem(s)


def test_third_non_player_column_is_not_silently_filtered():
    s = approved(); s["cover"]["matchup"].append(None)
    assert G.problem(s)


@pytest.mark.parametrize("key", list(G.WANG_EALA_OMISSION))
def test_exact_approval_record_is_required(key):
    s = approved(); del s["stats"]["_winners_ue_omission"][key]
    assert G.problem(s)


@pytest.mark.parametrize("slug", [
    "wang-xinyu-eala-auckland-2026-sf", "wang-xiyu-eala-asian-games-2026-final",
    "zheng-shi-beijing-2026-r1", "nishikori-tiafoe-tokyo-2026-r1",
    "shang-baez-beijing-2026-r1", "zverev-norrie-beijing-2026-r1",
    "sun-lys-beijing-2026-r1", "unapproved-film",
])
def test_wang_record_cannot_authorize_other_slugs_even_preapproved_ones(slug):
    s = approved(); s["slug"] = slug
    assert G.problem(s)
    s["stats"]["_winners_ue_omission"]["slug"] = slug
    assert G.problem(s)


def test_no_approval_or_false_complete_evidence_still_fails():
    s = approved(); del s["stats"]["_winners_ue_omission"]
    assert G.problem(s)
    s = approved(); s["stats"]["_winners_ue_evidence"] = {}
    assert G.problem(s)


def test_approval_constant_does_not_change_when_episode_is_mutated():
    original = deepcopy(G.WANG_EALA_OMISSION)
    s = approved(); s["stats"]["_winners_ue_omission"]["fields"].append("aces")
    assert G.problem(s)
    assert G.WANG_EALA_OMISSION == original
