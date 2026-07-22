from __future__ import annotations


def test_player_visual_queries_include_exact_event_anchors():
    from tennislive.render.tournament_story import STORIES
    from tennislive.research.visual_sources import _page_anchors, _queries

    story = next(item for item in STORIES if item.slug == "alcaraz")
    anchors = _page_anchors(story)
    queries = _queries(story)

    assert "us open" in queries["story"].lower()
    assert "french open" in queries["today"].lower()
    assert "us open" in anchors["story"]
    assert "french open" in anchors["today"]


def test_event_anchor_parser_covers_majors_and_olympics():
    from tennislive.research.visual_sources import _event_anchors

    assert "roland garros" in _event_anchors(
        "https://example.com/2024_French_Open_Mens_singles"
    )
    assert "us open" in _event_anchors(
        "https://example.com/news/2022-us-open-final"
    )
    assert "olympic" in _event_anchors(
        "https://example.com/paris-2024/olympic-tennis-final"
    )


def test_golden_slam_curated_inner_photos_match_exact_events():
    from tennislive.render.tournament_story import STORIES
    from tennislive.research.visual_sources import (
        _CURATED_VISUALS,
        _briefs,
        _candidate_matches,
    )

    story = next(item for item in STORIES if item.slug == "golden-slam")
    briefs = _briefs(story)
    for page in ("story", "explainer", "today"):
        candidate = _CURATED_VISUALS[(story.slug, page)][0]
        subject, year, event, person = _candidate_matches(candidate, briefs[page])
        assert subject and year and event and person, page


def test_resolved_visual_manifest_is_json_serializable(tmp_path, monkeypatch):
    import json

    from PIL import Image

    from tennislive.render.tournament_story import STORIES
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_VISUAL_FETCH", "on")
    monkeypatch.setattr(visual_sources, "_official_references", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "_commons_candidates",
        lambda query, _session: [
            {
                "provider": "wikimedia-commons",
                "source_url": f"https://example.com/{abs(hash(query))}",
                "image_url": "https://example.com/image.jpg",
                "credit": "Example Photographer",
                "license": "CC BY-SA 4.0",
                "width": 1200,
                "height": 800,
                "relevance": 9,
                "search_text": query.lower(),
            }
        ],
    )
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])

    def fake_download(candidate, page, query, folder, _session):
        path = folder / f"{page}.jpg"
        Image.new("RGB", (1200, 800), "white").save(path)
        return visual_sources.ResolvedVisual(
            page=page,
            path=path,
            provider=candidate["provider"],
            source_url=candidate["source_url"],
            image_url=candidate["image_url"],
            credit=candidate["credit"],
            license=candidate["license"],
            query=query,
            relevance=candidate["relevance"],
            sha256=page * 16,
        )

    monkeypatch.setattr(visual_sources, "_download", fake_download)
    story = next(item for item in STORIES if item.slug == "umag")
    selected, manifest = visual_sources.resolve_story_visuals(story, tmp_path)

    assert set(selected) == {"story", "explainer", "today"}
    json.dumps(manifest)
    selected_attempts = [
        item for item in manifest["attempts"] if item.get("status") == "selected"
    ]
    assert all("cached_file" in item and "path" not in item for item in selected_attempts)


def test_strict_visual_mode_rejects_subject_archive_photos(tmp_path, monkeypatch):
    from tennislive.render.tournament_story import STORIES
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_VISUAL_STRICT", "on")
    monkeypatch.setattr(visual_sources, "_official_references", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "_cover_audit",
        lambda _story: {"page": "cover", "status": "selected"},
    )
    archive = {
        "provider": "wikimedia-commons",
        "source_url": "https://example.com/archive",
        "image_url": "https://example.com/archive.jpg",
        "credit": "Example Photographer",
        "license": "CC BY-SA 4.0",
        "width": 1200,
        "height": 800,
        "relevance": 9,
        "search_text": "correct player, wrong year and tournament",
        "image_text": "correct player portrait",
    }
    monkeypatch.setattr(
        visual_sources,
        "_commons_candidates",
        lambda *_args: [dict(archive)],
    )
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "_candidate_matches",
        lambda *_args: (True, False, False, True),
    )

    def unexpected_download(*_args):
        raise AssertionError("strict mode must not download subject-archive candidates")

    monkeypatch.setattr(visual_sources, "_download", unexpected_download)
    story = next(item for item in STORIES if item.slug == "umag")

    selected, manifest = visual_sources.resolve_story_visuals(story, tmp_path)

    assert selected == {}
    assert manifest["status"] == "fail"
    assert set(manifest["missing_pages"]) == {"story", "explainer", "today"}
    assert all(
        attempt.get("match_level") != "subject-archive"
        for attempt in manifest["attempts"]
    )
