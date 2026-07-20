from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

from conftest import make_match
from tennislive.digest import Digest
from tennislive.render.evidence import evidence_artifacts
from tennislive.render.narrative import editor_takeaway, preview_angle
from tennislive.research.media import apply_media_briefs, brief_for_match


def _brief_file(tmp_path):
    path = tmp_path / "media_briefs.json"
    path.write_text(
        json.dumps(
            {
                "editions": {
                    "2026-07-20": [
                        {
                            "players": ["Stefanos Tsitsipas", "Raphael Collignon"],
                            "tournament_aliases": ["gstaad"],
                            "headline": "A long wait ends",
                            "consensus": "This title ended a 16-month wait.",
                            "divergence": "One source stressed resilience; another the serve.",
                            "data_point": "He won 72% of second-serve points.",
                            "takeaway": "A new starting point, not proof of a full return.",
                            "sources": [
                                {
                                    "name": "ATP Tour",
                                    "title": "Report",
                                    "url": "https://example.com/atp",
                                    "published_at": "2026-07-19",
                                    "lens": "match context",
                                },
                                {
                                    "name": "AS",
                                    "title": "Analysis",
                                    "url": "https://example.com/as",
                                    "published_at": "2026-07-19",
                                    "lens": "post-match stats",
                                },
                            ],
                        }
                    ]
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def _match():
    return make_match(
        home_name="Stefanos Tsitsipas",
        away_name="Raphael Collignon",
        tournament="ATP Gstaad",
        round_name="Final",
        match_id="gstaad-final",
    )


def test_reviewed_media_brief_matches_both_players_and_edition(tmp_path):
    brief = brief_for_match(_match(), date(2026, 7, 20), path=_brief_file(tmp_path))

    assert brief is not None
    assert brief.consensus == "This title ended a 16-month wait."
    assert brief.source_label == "外媒共识 · ATP Tour / AS"


def test_media_brief_becomes_sourced_editorial_context(tmp_path):
    match = _match()
    digest = Digest(today=date(2026, 7, 20), results=[match], source="espn")

    assert apply_media_briefs(digest, path=_brief_file(tmp_path)) == 1
    assert match.editorial_note == "This title ended a 16-month wait."
    assert match.editorial_url == "https://example.com/atp"


def test_narrative_uses_reviewed_brief_and_has_an_editorial_judgment(monkeypatch, tmp_path):
    path = _brief_file(tmp_path)
    monkeypatch.setattr("tennislive.research.media.DEFAULT_PATH", path)
    monkeypatch.setattr("tennislive.render.narrative.brief_for_match", lambda m, d: brief_for_match(m, d, path=path))

    assert preview_angle(_match(), date(2026, 7, 20)) == "This title ended a 16-month wait."
    assert editor_takeaway(_match(), date(2026, 7, 20)).startswith("A new starting point")


def test_evidence_package_keeps_media_links_separate_from_copy(monkeypatch, tmp_path):
    path = _brief_file(tmp_path)
    match = _match()
    digest = Digest(today=date(2026, 7, 20), results=[match], source="espn")
    monkeypatch.setattr("tennislive.render.evidence.brief_for_match", lambda m, d: brief_for_match(m, d, path=path))
    monkeypatch.setattr("tennislive.render.evidence.synthesis_for_digest", lambda d: {"edition": d.today.isoformat(), "mode": "reviewed-paraphrase", "items": []})

    artifacts = evidence_artifacts(digest, SimpleNamespace(evidence=()))
    manifest = artifacts["source_manifest.json"]

    assert set(artifacts) == {
        "source_manifest.json",
        "fact_ledger.json",
        "editorial_decision.json",
        "media_synthesis.json",
    }
    assert {source["url"] for source in manifest["sources"]} >= {
        "https://example.com/atp",
        "https://example.com/as",
    }
    assert "article bodies" not in json.dumps(artifacts, ensure_ascii=False).casefold()
