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
    # 内页缺图不再整题作废：这些页降级为示意图/时间线，题目保留。
    assert manifest["status"] == "pass"
    assert set(manifest["missing_pages"]) == {"story", "explainer", "today"}
    assert set(manifest["degraded_pages"]) == {"story", "explainer", "today"}
    assert all(
        attempt.get("match_level") != "subject-archive"
        for attempt in manifest["attempts"]
    )


def test_bing_visual_search_passes_site_operator_query_bare_without_quotes():
    from types import SimpleNamespace

    from tennislive.research import visual_sources

    captured: list[str] = []

    class _Session:
        def get(self, _url, params=None, timeout=None):
            captured.append(params["q"])
            return SimpleNamespace(text="", raise_for_status=lambda: None)

    site_query = "player photo (site:wtatennis.com OR site:wimbledon.com)"
    visual_sources._bing_candidates(site_query, _Session())
    visual_sources._bing_candidates("plain player query", _Session())

    # site: 运算符串被引号包住会退化成短语文本，实测恒 0 结果——必须裸传。
    assert captured[0] == site_query
    assert captured[1] == '"plain player query" tennis'


def test_curated_special_redirect_width_capped_at_declared_width():
    from tennislive.research.visual_sources import (
        _CURATED_VISUALS,
        _curated_image_request_url,
    )

    story_entry = _CURATED_VISUALS[("longest-match", "story")][0]
    today_entry = _CURATED_VISUALS[("longest-match", "today")][0]

    # MediaWiki 拒绝放大：请求宽度取 min(1600, 条目声明宽度)。
    assert _curated_image_request_url(
        story_entry["image_url"], story_entry["width"]
    ).endswith("width=943")
    assert _curated_image_request_url(
        today_entry["image_url"], today_entry["width"]
    ).endswith("width=1600")
    plain = "https://assets.example.com/photo.jpg?width=1600"
    assert _curated_image_request_url(plain, 900) == plain


def test_curated_download_failure_opens_network_search_and_records_exclusion(
    tmp_path, monkeypatch
):
    """curated 图下载必败时不再逐字节重复：立即放开网络检索并记入排除集。"""
    from PIL import Image

    from tennislive.render.tournament_story import STORIES
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_VISUAL_FETCH", "on")
    monkeypatch.delenv("TENNISLIVE_VISUAL_STRICT", raising=False)
    monkeypatch.setattr(visual_sources, "_official_references", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "_cover_audit",
        lambda _story: {"page": "cover", "status": "selected"},
    )
    network_text = (
        "john isner nicolas mahut playing beside court 18 plaque final "
        "scoreboard showing 70-68 during 2010 wimbledon match"
    )
    monkeypatch.setattr(
        visual_sources,
        "_commons_candidates",
        lambda query, _session: [
            {
                "provider": "wikimedia-commons",
                "source_url": f"https://example.com/net/{abs(hash(query))}",
                "image_url": "https://example.com/net.jpg",
                "credit": "Example Photographer",
                "license": "CC BY-SA 4.0",
                "width": 1200,
                "height": 800,
                "relevance": 30,
                "search_text": network_text,
                "image_text": network_text,
            }
        ],
    )
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_official_archive_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_flickr_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_duckduckgo_candidates", lambda *_args: [])
    curated_urls = visual_sources.curated_source_urls("longest-match")

    def fake_download(candidate, page, query, folder, _session):
        if candidate["source_url"] in curated_urls:
            return None  # MediaWiki 拒绝放大等下载失败
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
    story = next(item for item in STORIES if item.slug == "longest-match")

    selected, manifest = visual_sources.resolve_story_visuals(story, tmp_path)

    assert set(selected) == {"story", "explainer", "today"}
    assert all(
        visual.provider == "wikimedia-commons" for visual in selected.values()
    )
    failed = set(manifest["failed_curated_source_urls"])
    assert failed and failed <= curated_urls
    # curated 存在且无排除集时本来不联网；curated 失败后必须已经放开网络检索
    assert any(
        run["provider"] == "wikimedia-commons" and run["page"] == "story"
        for run in manifest["provider_runs"]
    )


def test_flickr_visual_feed_uses_any_tagmode_and_player_name_tokens_only():
    from types import SimpleNamespace

    from tennislive.research import visual_sources

    captured: dict = {}

    class _Session:
        def get(self, _url, params=None, timeout=None):
            captured.update(params)
            return SimpleNamespace(
                raise_for_status=lambda: None,
                json=lambda: {"items": []},
            )

    visual_sources._flickr_candidates(
        "Mayar Sherif Anna Bondar Hamburg Open 2026 tennis match photo",
        _Session(),
    )

    # 公共 feed 全 AND 匹配 8 个 token 实测恒 0：只留球员姓名 token 且 tagmode=any
    assert captured["tagmode"] == "any"
    assert captured["tags"] == "mayar,sherif"


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
