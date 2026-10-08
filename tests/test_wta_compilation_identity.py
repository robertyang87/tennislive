"""WTA day compilations contain distinct matches without Flashscore IDs."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_match_reel as reel
import promote_reel_draft as promote

DAY4 = "https://www.youtube.com/watch?v=EuPUtfm-pA0"


def spec(slug, source_id, *, url=DAY4, status="result_verified", source="official_wta"):
    return {"slug": slug, "cover": {"eyebrow": "赛场之上"}, "source_url": url,
            "_match": {"status": status, "source": source, "source_id": source_id}}


def write(root, data):
    (root / (data["slug"] + ".json")).write_text(json.dumps(data), encoding="utf-8")


def test_verified_full_wta_ids_allow_distinct_day4_matches(tmp_path):
    # Actual event/year/match IDs for the three already verified China Open matches.
    write(tmp_path, spec("sun", "1020_2026_LS041"))
    write(tmp_path, spec("rybakina", "1020_2026_LS032"))
    zheng = spec("zheng", "1020_2026_LS035")
    assert promote._compilation_only(zheng, "yt:EuPUtfm-pA0", "sun", tmp_path)
    assert promote._compilation_only(zheng, "yt:EuPUtfm-pA0", "rybakina", tmp_path)
    assert reel.duplicate_match_problem(zheng, tmp_path) is None


def test_same_official_match_still_blocked_after_changing_video_url(tmp_path):
    write(tmp_path, spec("published", "1020_2026_LS035"))
    draft = spec("different-view", "1020_2026_LS035", url="https://youtu.be/newhighlight")
    assert "wta:1020_2026_LS035" in promote._match_keys(draft)
    assert not promote._compilation_only(draft, "wta:1020_2026_LS035", "published", tmp_path)
    assert reel.duplicate_match_problem(draft, tmp_path)


@pytest.mark.parametrize("source_id", ["", None, "LS035", "1020_LS035", "1020_2026_LS35",
                                       "1020_2026_ls035", "x1020_2026_LS035", "1020_2026_LS035-extra"])
def test_missing_or_noncanonical_wta_id_does_not_prove_a_different_match(tmp_path, source_id):
    write(tmp_path, spec("published", "1020_2026_LS041"))
    draft = spec("draft", source_id)
    assert promote._official_wta_id(draft) == ""
    assert reel.duplicate_match_problem(draft, tmp_path)


@pytest.mark.parametrize("status,source", [("pending", "official_wta"),
                                            ("result_verified", "news_report"),
                                            ("", "official_wta")])
def test_unverified_or_unofficial_wta_id_cannot_bypass_video_collision(tmp_path, status, source):
    write(tmp_path, spec("published", "1020_2026_LS041"))
    draft = spec("draft", "1020_2026_LS035", status=status, source=source)
    assert not promote._compilation_only(draft, "yt:EuPUtfm-pA0", "published", tmp_path)
    assert reel.duplicate_match_problem(draft, tmp_path)


def test_prior_match_also_needs_verified_full_identity(tmp_path):
    write(tmp_path, spec("published", "LS041"))
    draft = spec("draft", "1020_2026_LS035")
    assert reel.duplicate_match_problem(draft, tmp_path)


def test_different_event_or_year_does_not_claim_this_day_compilation(tmp_path):
    write(tmp_path, spec("published", "1020_2026_LS041"))
    assert reel.duplicate_match_problem(spec("other-year", "1020_2025_LS035"), tmp_path)
    assert reel.duplicate_match_problem(spec("other-event", "1021_2026_LS035"), tmp_path)


def test_existing_flashscore_identity_protection_is_preserved(tmp_path):
    prior = spec("published", "1020_2026_LS041")
    prior["_match"]["flashscore_id"] = "sameFS01"
    write(tmp_path, prior)
    draft = spec("draft", "1020_2026_LS035")
    draft["_match"]["flashscore_id"] = "sameFS01"
    assert not promote._compilation_only(draft, "yt:EuPUtfm-pA0", "published", tmp_path)
    assert reel.duplicate_match_problem(draft, tmp_path)
    draft["_match"]["flashscore_id"] = "otherFS2"
    assert promote._compilation_only(draft, "yt:EuPUtfm-pA0", "published", tmp_path)
    assert not promote._compilation_only(draft, "fs:sameFS01", "published", tmp_path)
