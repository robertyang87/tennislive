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
