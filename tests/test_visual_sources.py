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
    monkeypatch.setattr(visual_sources, "_official_archive_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_flickr_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_duckduckgo_candidates", lambda *_args: [])

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
    monkeypatch.setattr(visual_sources, "_official_archive_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_flickr_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_duckduckgo_candidates", lambda *_args: [])
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


def test_official_archive_candidates_keep_only_official_tennis_domains(monkeypatch):
    from tennislive.research import visual_sources

    public = {
        "provider": "bing-web-image",
        "source_url": "https://example.com/tennis/photo",
        "image_url": "https://images.example.com/photo.jpg",
        "credit": "example.com",
        "license": "editorial",
        "width": 1800,
        "height": 1200,
        "relevance": 12,
        "search_text": "player 2026 wimbledon",
        "image_text": "player 2026 wimbledon",
    }
    official = {
        **public,
        "source_url": "https://www.wimbledon.com/en_GB/news/photo.html",
    }
    monkeypatch.setattr(
        visual_sources,
        "_bing_candidates",
        lambda *_args: [public, official],
    )
    monkeypatch.setattr(visual_sources, "_duckduckgo_candidates", lambda *_args: [])

    candidates = visual_sources._official_archive_candidates(
        "player 2026 Wimbledon",
        object(),
    )

    assert len(candidates) == 1
    assert candidates[0]["provider"] == "official-tennis-archive"
    assert candidates[0]["credit"] == "wimbledon.com"


def test_visual_manifest_records_each_provider_run_and_rejection_reason(
    tmp_path,
    monkeypatch,
):
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
    rejected = {
        "provider": "wikimedia-commons",
        "source_url": "https://commons.wikimedia.org/rejected",
        "image_url": "https://upload.wikimedia.org/rejected.jpg",
        "credit": "Photographer",
        "license": "cc-by",
        "width": 1600,
        "height": 1000,
        "relevance": 12,
        "search_text": "wrong person at wrong event",
        "image_text": "wrong person",
    }
    monkeypatch.setattr(
        visual_sources, "_commons_candidates", lambda *_args: [dict(rejected)]
    )
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_official_archive_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_flickr_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_duckduckgo_candidates", lambda *_args: [])

    story = next(item for item in STORIES if item.slug == "umag")
    _selected, manifest = visual_sources.resolve_story_visuals(story, tmp_path)

    providers = {run["provider"] for run in manifest["provider_runs"]}
    assert {
        "wikimedia-commons",
        "openverse",
        "bing-web-image",
        "official-tennis-archive",
        "flickr-public",
        "duckduckgo-web-image",
    } <= providers
    generated = [
        item
        for item in manifest["attempts"]
        if item.get("status") == "generated-visual"
        and item.get("page") in {"story", "explainer", "today"}
    ]
    assert generated
    assert all(
        item["rejection_counts"].get("subject-or-person-mismatch", 0) >= 1
        for item in generated
    )


def test_visual_impact_metadata_rejects_generic_subject_photo():
    from tennislive.research import visual_sources

    generic = {
        "search_text": "john isner nicolas mahut 2010 wimbledon",
        "image_text": "john isner nicolas mahut portrait",
        "source_url": "https://example.com/photo",
        "image_url": "https://example.com/photo.jpg",
    }
    event_scene = {
        **generic,
        "image_text": "john isner nicolas mahut celebrate beside scoreboard after match",
    }

    assert not visual_sources._visual_impact_match(generic, "cover")
    assert visual_sources._visual_impact_match(event_scene, "cover")


def test_named_players_remain_valid_when_iconic_photo_mentions_scoreboard():
    from tennislive.research import visual_sources

    candidate = {
        "search_text": (
            "john isner nicolas mahut 2010 wimbledon court 18 scoreboard "
            "match ceremony"
        ),
        "image_text": (
            "john isner nicolas mahut beside scoreboard after match ceremony"
        ),
    }
    brief = (
        "John Isner Nicolas Mahut",
        ("2010",),
        ("wimbledon", "court 18"),
        True,
    )

    assert visual_sources._candidate_matches(candidate, brief) == (
        True,
        True,
        True,
        True,
    )


def test_numeric_explainer_requires_visible_score_metadata():
    from tennislive.render.tournament_story import STORIES
    from tennislive.research import visual_sources

    story = next(item for item in STORIES if item.slug == "longest-match")
    vague = {
        "search_text": "2010 wimbledon court 18 scoreboard",
        "image_text": "scoreboard during the match",
    }
    exact = {
        **vague,
        "image_text": "final scoreboard showing 70-68",
    }

    assert not visual_sources._visual_claim_match(story, "explainer", vague)
    assert visual_sources._visual_claim_match(story, "explainer", exact)
