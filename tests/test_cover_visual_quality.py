from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from PIL import Image

from conftest import make_match


def test_scene_classifier_rejects_prematch_group_even_when_player_is_named():
    from tennislive.research.visual_quality import classify_cover_scene

    result = classify_cover_scene(
        "Yuan Yue and opponent pose for a pre-match group photo before tennis action"
    )

    assert result["scene"] == "static_or_group"
    assert result["rejected_terms"]


def test_scene_classifier_accepts_match_action_and_on_court_reaction():
    from tennislive.research.visual_quality import classify_cover_scene

    action = classify_cover_scene("Yuan Yue hits a forehand during the match")
    reaction = classify_cover_scene("Yuan Yue celebrates after winning on court")

    assert action["scene"] == "match_action"
    assert reaction["scene"] == "on_court_reaction"


def test_daily_cover_keeps_chinese_opponent_as_valid_priority():
    from tennislive.research.visual_sources import _daily_cover_players

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        winner=0,
    )

    players = _daily_cover_players(match)

    assert players[0].name == "Yuan Yue"
    assert {player.name for player in players} == {"Nikola Bartunkova", "Yuan Yue"}


def test_exact_match_context_requires_both_sides_event_and_current_year():
    from tennislive.research.visual_sources import _exact_match_context

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        tournament="Prague Open",
    )
    exact = _exact_match_context(
        match,
        {
            "search_text": (
                "Bartunkova comes from a set down to beat Yuan at Prague Open 2026"
            )
        },
    )
    old_edition = _exact_match_context(
        match,
        {
            "search_text": (
                "Nikola Bartunkova plays Yuan Yue at Prague Open 2025"
            )
        },
    )
    wrong_event = _exact_match_context(
        match,
        {
            "search_text": (
                "Nikola Bartunkova plays Yuan Yue at China Open 2026"
            )
        },
    )

    assert exact["exact_match"]
    assert old_edition["both_sides_match"]
    assert old_edition["event_match"]
    assert not old_edition["year_match"]
    assert not old_edition["exact_match"]
    assert wrong_event["both_sides_match"]
    assert wrong_event["year_match"]
    assert not wrong_event["event_match"]
    assert not wrong_event["exact_match"]


def test_exact_match_context_does_not_reuse_shared_first_name_for_both_sides():
    from tennislive.research.visual_sources import _exact_match_context

    match = make_match(
        home_name="Alexander Zverev",
        away_name="Alexander Bublik",
        home_country="GER",
        away_country="KAZ",
        tournament="Hamburg Open",
    )

    shared_first_name_only = _exact_match_context(
        match,
        {"search_text": "Alexander plays at Hamburg Open 2026"},
    )
    exact = _exact_match_context(
        match,
        {"search_text": "Zverev faces Bublik at Hamburg Open 2026"},
    )
    substring = _exact_match_context(
        match,
        {"search_text": "Zverevian faces Bublik at Hamburg Open 2026"},
    )

    assert not shared_first_name_only["both_sides_match"]
    assert not shared_first_name_only["exact_match"]
    assert exact["exact_match"]
    assert not substring["both_sides_match"]
    assert not substring["exact_match"]


def test_exact_match_context_recognizes_us_open_event_phrase():
    from tennislive.research.visual_sources import _exact_match_context

    match = make_match(
        home_name="Jannik Sinner",
        away_name="Novak Djokovic",
        tournament="US Open",
    )

    context = _exact_match_context(
        match,
        {
            "search_text": (
                "Jannik Sinner faces Novak Djokovic at the US Open 2026"
            )
        },
    )

    assert context["event_match"]
    assert context["exact_match"]


def test_daily_cover_rejects_old_event_photo_with_both_players(monkeypatch, tmp_path):
    from tennislive.research import visual_sources

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        winner=0,
        tournament="Prague Open",
    )
    old_event = {
        "provider": "wikimedia-commons",
        "source_url": "https://example.com/prague-open-2025",
        "image_url": "https://example.com/prague-open-2025.jpg",
        "credit": "Photographer",
        "license": "cc-by",
        "width": 1800,
        "height": 1200,
        "relevance": 20,
        "search_text": (
            "Yuan Yue hits a forehand against Nikola Bartunkova during "
            "the Prague Open 2025 match"
        ),
        "image_text": "Yuan Yue forehand against Nikola Bartunkova",
    }
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setattr(visual_sources, "_commons_candidates", lambda *_args: [old_event])
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_daily_editorial_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_wta_video_hub_candidates", lambda *_args: [])

    def unexpected_download(*_args):
        raise AssertionError("old-edition photos must fail before download")

    monkeypatch.setattr(visual_sources, "_download", unexpected_download)

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is None
    rejected = next(
        item for item in report["attempts"] if item["source_url"] == old_event["source_url"]
    )
    assert rejected["both_sides_match"]
    assert rejected["event_match"]
    assert not rejected["year_match"]
    assert not rejected["exact_match"]
    assert "not-the-exact-headline-match" in rejected["hard_failures"]


def test_daily_workflow_hard_gates_exact_cover_before_commit_and_pushplus():
    from pathlib import Path

    workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")
    gate = workflow.index('and .exact_match == true')
    both_sides = workflow.index('and .both_sides_match == true')
    current_match = workflow.index('and .match_id == $expected_match_id')
    commit = workflow.index('- name: 提交内容到仓库')
    pushplus = workflow.index('- name: PushPlus 推送到微信')

    assert workflow.index('rm -f "$OUT_DIR/cover_visual.json"') < gate
    assert max(gate, both_sides, current_match) < commit < pushplus


def test_pixel_quality_rejects_blank_photo(tmp_path):
    from tennislive.research.visual_quality import assess_cover_image

    path = tmp_path / "blank.jpg"
    Image.new("RGB", (1200, 1600), "white").save(path)

    report = assess_cover_image(path)

    assert report["status"] == "fail"
    assert "low-contrast" in report["hard_failures"]


def test_pixel_quality_rejects_detailed_logo_without_prominent_face(tmp_path):
    from PIL import ImageDraw

    from tennislive.research.visual_quality import assess_cover_image

    path = tmp_path / "logo-card.jpg"
    image = Image.effect_noise((1200, 1600), 48).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.ellipse((300, 420, 900, 1020), outline="white", width=50)
    draw.line((300, 1020, 900, 420), fill="yellow", width=45)
    image.save(path)

    report = assess_cover_image(path)

    assert report["prominent_faces"] == 0
    assert "no-prominent-face" in report["hard_failures"]
    assert report["status"] == "fail"


def test_daily_cover_rejects_prematch_group_before_download(monkeypatch, tmp_path):
    from tennislive.research import visual_sources

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        winner=0,
    )
    group = {
        "provider": "wikimedia-commons",
        "source_url": "https://example.com/group",
        "image_url": "https://example.com/group.jpg",
        "credit": "Photographer",
        "license": "cc-by",
        "width": 1800,
        "height": 1200,
        "relevance": 20,
        "search_text": "yuan yue pre-match group photo before the tennis match",
        "image_text": "yuan yue pre-match group photo",
    }
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setattr(visual_sources, "_commons_candidates", lambda *_args: [group])
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_daily_editorial_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_wta_video_hub_candidates", lambda *_args: [])

    def unexpected_download(*_args):
        raise AssertionError("pre-match group photos must be rejected before download")

    monkeypatch.setattr(visual_sources, "_download", unexpected_download)

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is None
    assert report["status"] == "unavailable"
    assert any(
        "static-or-group-photo" in item.get("hard_failures", [])
        for item in report["attempts"]
    )


def test_daily_cover_compares_all_sources_and_selects_best(monkeypatch, tmp_path):
    from tennislive.research import visual_sources

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        winner=0,
        tournament="Prague Open",
    )
    low = {
        "provider": "wikimedia-commons",
        "source_url": "https://example.com/low",
        "image_url": "https://example.com/low.jpg",
        "credit": "Low Photographer",
        "license": "cc-by",
        "width": 1400,
        "height": 1000,
        "relevance": 5,
        "search_text": "yuan yue tennis serving in action at the us open",
        "image_text": "yuan yue serving",
    }
    high = {
        "provider": "openverse",
        "source_url": "https://example.com/high",
        "image_url": "https://example.com/high.jpg",
        "credit": "High Photographer",
        "license": "cc-by",
        "width": 1800,
        "height": 2400,
        "relevance": 10,
        "search_text": (
            "yuan yue against nikola bartunkova at prague open 2026 "
            "hits a forehand during the match"
        ),
        "image_text": "yuan yue hits a forehand",
    }
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setattr(visual_sources, "_commons_candidates", lambda *_args: [low])
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [high])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_daily_editorial_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_wta_video_hub_candidates", lambda *_args: [])

    def fake_download(candidate, page, query, folder, _session):
        path = folder / ("high.jpg" if "high" in candidate["image_url"] else "low.jpg")
        Image.effect_noise((1200, 1600), 32).convert("RGB").save(path)
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
            sha256=path.stem,
        )

    monkeypatch.setattr(visual_sources, "_download", fake_download)
    monkeypatch.setattr(
        visual_sources,
        "assess_cover_image",
        lambda path: {
            "status": "pass",
            "score": 35 if path.name == "high.jpg" else 28,
            "quality_score": 15,
            "crop_score": 20 if path.name == "high.jpg" else 13,
            "hard_failures": [],
            "prominent_faces": 1,
            "face_detectors": ["test-fixture"],
            "focus": "64% 26%",
        },
    )

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is not None, report
    assert visual.source_url == "https://example.com/high"
    assert report["selected_player"] == "Yuan Yue"
    assert set(report["providers_queried"]) >= {
        "wikimedia-commons",
        "openverse",
        "bing-web-image",
    }


def test_official_video_source_expands_to_full_size_exact_match_og_image():
    from tennislive.research.visual_sources import (
        _exact_match_context,
        _expand_official_source_candidate,
    )

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        away_country="CHN",
        tournament="Prague Open",
    )
    source_url = "https://www.wtatennis.com/videos/999/bartunkova-yuan-prague-highlights"
    html = """
        <html><head>
        <meta content="Bartunkova vs. Yuan: Prague Open 2026 highlights"
              property="og:title">
        <meta property="og:description"
              content="Nikola Bartunkova plays Yue Yuan at the Prague Open 2026.">
        <meta property="og:image"
              content="https://photoresources.wtatennis.com/photo-resources/a/frame.JPG?width=640&amp;height=360">
        <meta property="og:image:alt"
              content="Yue Yuan hits a forehand against Nikola Bartunkova in Prague">
        <meta property="og:image:width" content="640">
        <meta property="og:image:height" content="360">
        </head></html>
    """
    response = SimpleNamespace(url=source_url, text=html, raise_for_status=lambda: None)
    session = SimpleNamespace(get=lambda *_args, **_kwargs: response)

    expanded = _expand_official_source_candidate(
        match,
        {
            "provider": "bing-web-image",
            "source_url": source_url,
            "image_url": "https://bing.example/thumbnail.jpg",
            "search_text": "search query text must not establish the match",
        },
        session,
    )

    assert expanded is not None
    assert expanded["provider"] == "official-match-media"
    assert expanded["image_url"].endswith("frame.JPG?width=2000")
    assert "height=" not in expanded["image_url"]
    assert _exact_match_context(match, expanded)["exact_match"]


def test_wta_video_hub_uses_official_sitemap_as_freshness_fallback():
    from tennislive.research.visual_sources import _wta_video_hub_candidates

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        away_country="CHN",
        tournament="Prague Open",
    )
    exact_url = (
        "https://www.wtatennis.com/videos/4539959/"
        "bartunkova-comes-from-a-set-down-to-beat-yuan-on-prague-main-draw-debut"
    )
    responses = {
        "https://www.wtatennis.com/videos": """
            <a href="/videos/4540293/oliynykova-beats-schunk">Watch</a>
        """,
        "https://www.wtatennis.com/videos/highlights": """
            <a href="/videos/4540272/bejlek-wins-in-prague">Watch</a>
        """,
        "https://www.wtatennis.com/sitemap/videos.xml": f"""
            <urlset>
              <url><loc>{exact_url}</loc></url>
              <url><loc>https://www.wtatennis.com/videos/1/yuan-beats-sherif</loc></url>
            </urlset>
        """,
    }

    def get(url, **_kwargs):
        return SimpleNamespace(
            url=url,
            text=responses[url],
            raise_for_status=lambda: None,
        )

    candidates = _wta_video_hub_candidates(match, SimpleNamespace(get=get))

    assert [candidate["source_url"] for candidate in candidates] == [exact_url]
    assert candidates[0]["provider"] == "wta-video-hub"


def test_official_video_image_path_can_prove_current_edition_year():
    from tennislive.research.visual_sources import (
        _exact_match_context,
        _expand_official_source_candidate,
    )

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        tournament="Prague Open",
    )
    source_url = (
        "https://www.wtatennis.com/videos/4539959/"
        "bartunkova-comes-from-a-set-down-to-beat-yuan-on-prague-main-draw-debut"
    )
    html = """
        <html><head>
        <meta property="og:title"
              content="Bartunkova comes from a set down to beat Yuan on Prague main-draw debut">
        <meta property="og:description"
              content="Nikola Bartunkova defeated Yuan Yue at the Livesport Prague Open.">
        <meta property="og:image"
              content="https://photoresources.wtatennis.com/wta/photo/2026/07/22/id/Bartunkova-R1.jpg">
        </head></html>
    """
    response = SimpleNamespace(url=source_url, text=html, raise_for_status=lambda: None)
    session = SimpleNamespace(get=lambda *_args, **_kwargs: response)

    expanded = _expand_official_source_candidate(
        match,
        {
            "provider": "wta-video-hub",
            "source_url": source_url,
            "image_url": "",
        },
        session,
    )

    assert expanded is not None
    assert expanded["image_url"].endswith("Bartunkova-R1.jpg?width=2000")
    assert _exact_match_context(match, expanded)["year_match"]
    assert _exact_match_context(match, expanded)["exact_match"]


def test_daily_cover_resolver_expands_wta_hub_candidate(monkeypatch, tmp_path):
    from tennislive.research import visual_sources

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        tournament="Prague Open",
    )
    source_url = (
        "https://www.wtatennis.com/videos/4539959/"
        "bartunkova-comes-from-a-set-down-to-beat-yuan-on-prague-main-draw-debut"
    )
    hub_candidate = {
        "provider": "wta-video-hub",
        "source_url": source_url,
        "image_url": "",
        "search_text": "bartunkova beat yuan in prague",
        "image_text": "",
        "width": 0,
        "height": 0,
        "relevance": 5,
    }
    expanded = {
        **hub_candidate,
        "provider": "official-match-media",
        "image_url": "https://photoresources.wtatennis.com/wta/photo/2026/07/22/id/Bartunkova-R1.jpg?width=2000",
        "search_text": (
            "nikola bartunkova beat yuan yue at the livesport prague open "
            "https://photoresources.wtatennis.com/wta/photo/2026/07/22/id/Bartunkova-R1.jpg"
        ),
        "image_text": "bartunkova-r1.jpg",
        "credit": "wtatennis.com",
        "license": "WTA official",
    }
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_COVER_WTA_OFFICIAL", "on")
    monkeypatch.setattr(visual_sources, "_wta_video_hub_candidates", lambda *_args: [hub_candidate])
    monkeypatch.setattr(visual_sources, "_commons_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_daily_editorial_candidates", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "_expand_official_source_candidate",
        lambda _match, candidate, _session: expanded
        if candidate["source_url"] == source_url
        else None,
    )

    def fake_download(candidate, page, query, folder, _session):
        path = folder / "Bartunkova-R1.jpg"
        Image.effect_noise((1200, 1600), 32).convert("RGB").save(path)
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
            sha256="bartunkova-r1",
        )

    monkeypatch.setattr(visual_sources, "_download", fake_download)
    monkeypatch.setattr(
        visual_sources,
        "assess_cover_image",
        lambda _path: {
            "status": "pass",
            "score": 31,
            "quality_score": 15,
            "crop_score": 16,
            "hard_failures": [],
            "prominent_faces": 1,
            "face_detectors": ["test-fixture"],
            "focus": "50% 28%",
        },
    )

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is not None, report["attempts"]
    assert visual.path.name == "Bartunkova-R1.jpg"
    assert report["provider"] == "official-match-media"
    assert report["wta_video_hub_candidates"] == 1
    assert report["exact_match"]


def test_official_video_page_is_not_promoted_to_action_and_no_face_is_rejected(
    monkeypatch, tmp_path
):
    from tennislive.research import visual_sources

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        home_country="CZE",
        away_country="CHN",
        tournament="Prague Open",
    )
    candidate = {
        "provider": "official-match-media",
        "source_url": "https://www.wtatennis.com/videos/999/bartunkova-yuan-prague",
        "image_url": "https://photoresources.wtatennis.com/wta/photo/2026/07/22/logo.jpg",
        "credit": "wtatennis.com",
        "license": "official",
        "width": 1600,
        "height": 1200,
        "relevance": 10,
        "search_text": "Bartunkova vs Yuan Prague Open 2026 highlights",
        "image_text": "Bartunkova vs Yuan Prague 2026 highlights",
    }
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setattr(
        visual_sources, "_daily_editorial_candidates", lambda *_args: [candidate]
    )
    monkeypatch.setattr(visual_sources, "_atp_official_cover_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_wta_video_hub_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_commons_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "_expand_official_source_candidate",
        lambda *_args: None,
    )

    def fake_download(item, page, query, folder, _session):
        path = folder / "official-end-card.jpg"
        Image.effect_noise((1200, 1600), 32).convert("RGB").save(path)
        return visual_sources.ResolvedVisual(
            page=page,
            path=path,
            provider=item["provider"],
            source_url=item["source_url"],
            image_url=item["image_url"],
            credit=item["credit"],
            license=item["license"],
            query=query,
            relevance=item["relevance"],
            sha256="official-end-card",
        )

    monkeypatch.setattr(visual_sources, "_download", fake_download)
    monkeypatch.setattr(
        visual_sources,
        "assess_cover_image",
        lambda _path: {
            "status": "fail",
            "score": 20,
            "quality_score": 12,
            "crop_score": 8,
            "hard_failures": ["no-prominent-face"],
            "prominent_faces": 0,
            "face_detectors": [],
            "focus": "50% 28%",
        },
    )

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is None
    attempted = next(
        item for item in report["attempts"] if item["source_url"] == candidate["source_url"]
    )
    assert attempted["scene"] == "unknown"
    assert "no-prominent-face" in attempted["hard_failures"]


def test_generic_official_tournament_page_cannot_borrow_search_query_players():
    from tennislive.research.visual_sources import _expand_official_source_candidate

    match = make_match(
        home_name="Nikola Bartunkova",
        away_name="Yuan Yue",
        tournament="Prague Open",
    )
    source_url = "https://www.wtatennis.com/tournaments/1082/prague/2026/live"
    html = """
        <html><head>
        <meta property="og:title" content="Livesport Prague Open 2026 | WTA Official">
        <meta property="og:description" content="Scores, draws and order of play.">
        <meta property="og:image"
              content="https://photoresources.wtatennis.com/photo-resources/a/event.JPG?width=1200&amp;height=630">
        </head></html>
    """
    response = SimpleNamespace(url=source_url, text=html, raise_for_status=lambda: None)
    session = SimpleNamespace(get=lambda *_args, **_kwargs: response)

    expanded = _expand_official_source_candidate(
        match,
        {
            "provider": "bing-web-image",
            "source_url": source_url,
            "image_url": "https://bing.example/thumbnail.jpg",
            "search_text": (
                "Nikola Bartunkova against Yuan Yue Prague Open 2026 match"
            ),
        },
        session,
    )

    assert expanded is None


def test_atp_official_feed_cover_requires_both_players_event_and_fresh_date():
    from tennislive.research.visual_sources import (
        _atp_official_cover_candidates,
        _exact_match_context,
    )
    from tennislive.video.official import ATP_YOUTUBE_CHANNEL_ID

    match = make_match(
        home_name="Jannik Sinner",
        away_name="Novak Djokovic",
        tournament="Hamburg Open",
        start_utc=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
    )
    match.tournament.city = "Hamburg"
    feed = f"""<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:media="http://search.yahoo.com/mrss/"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>{ATP_YOUTUBE_CHANNEL_ID}</yt:channelId>
      <entry><yt:videoId>exact</yt:videoId>
        <title>Match Highlights: Sinner vs Djokovic | Hamburg 2026</title>
        <published>2026-07-21T20:15:00+00:00</published>
        <media:group><media:description>Jannik Sinner faces Novak Djokovic in Hamburg.</media:description></media:group>
      </entry>
      <entry><yt:videoId>one-player</yt:videoId>
        <title>Hot Shot: Sinner lights up Hamburg</title>
        <published>2026-07-21T20:20:00+00:00</published>
      </entry>
      <entry><yt:videoId>wrong-event</yt:videoId>
        <title>Highlights: Sinner vs Djokovic | Monte Carlo 2026</title>
        <published>2026-07-21T20:25:00+00:00</published>
      </entry>
      <entry><yt:videoId>old-edition</yt:videoId>
        <title>Highlights: Sinner vs Djokovic | Hamburg 2025</title>
        <published>2025-07-21T20:15:00+00:00</published>
      </entry>
    </feed>"""
    response = SimpleNamespace(text=feed, raise_for_status=lambda: None)
    session = SimpleNamespace(get=lambda *_args, **_kwargs: response)

    candidates = _atp_official_cover_candidates(match, session)

    assert len(candidates) == 1
    assert candidates[0]["source_url"].endswith("watch?v=exact")
    assert candidates[0]["image_url"].endswith("exact/maxresdefault.jpg")
    assert candidates[0]["official_channel_id"] == ATP_YOUTUBE_CHANNEL_ID
    assert "during the match" not in candidates[0]["image_text"]
    assert _exact_match_context(match, candidates[0])["exact_match"]


def test_atp_official_feed_cover_still_runs_common_visual_gate(monkeypatch, tmp_path):
    from tennislive.research import visual_sources

    match = make_match(
        home_name="Jannik Sinner",
        away_name="Novak Djokovic",
        tournament="Hamburg Open",
        start_utc=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
    )
    candidate = {
        "provider": "official-atp-youtube",
        "source_url": "https://www.youtube.com/watch?v=exact",
        "image_url": "https://i.ytimg.com/vi/exact/maxresdefault.jpg",
        "credit": "ATP Tour",
        "license": "official public match media",
        "width": 1280,
        "height": 720,
        "relevance": 20,
        "search_text": (
            "match highlights jannik sinner vs novak djokovic hamburg open "
            "2026-07-21t20:15:00+00:00"
        ),
        "image_text": "match highlights sinner vs djokovic",
    }
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_COVER_ATP_OFFICIAL", "on")
    monkeypatch.setattr(
        visual_sources, "_atp_official_cover_candidates", lambda *_args: [candidate]
    )
    monkeypatch.setattr(visual_sources, "_wta_video_hub_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_commons_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_daily_editorial_candidates", lambda *_args: [])

    def fake_download(item, page, query, folder, _session):
        path = folder / "atp-maxres.jpg"
        Image.effect_noise((1280, 960), 32).convert("RGB").save(path)
        return visual_sources.ResolvedVisual(
            page=page,
            path=path,
            provider=item["provider"],
            source_url=item["source_url"],
            image_url=item["image_url"],
            credit=item["credit"],
            license=item["license"],
            query=query,
            relevance=item["relevance"],
            sha256="atp-maxres",
        )

    audits = []

    def fake_audit(path):
        audits.append(path)
        return {
            "status": "pass",
            "score": 30,
            "quality_score": 13,
            "crop_score": 17,
            "hard_failures": [],
            "prominent_faces": 1,
            "face_detectors": ["test-fixture"],
            "focus": "62% 27%",
        }

    monkeypatch.setattr(visual_sources, "_download", fake_download)
    monkeypatch.setattr(visual_sources, "assess_cover_image", fake_audit)

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is not None
    assert visual.provider == "official-atp-youtube"
    assert audits == [visual.path]
    assert report["exact_match"]
    assert report["scene"] == "prominent_person"
    assert "official-atp-youtube" in report["providers_queried"]


def test_atp_maxres_profile_only_adjusts_fixed_resolution_failure():
    from tennislive.research.visual_sources import (
        _apply_official_maxres_resolution_profile,
    )
    from tennislive.video.official import ATP_YOUTUBE_CHANNEL_ID

    candidate = {
        "provider": "official-atp-youtube",
        "official_channel_id": ATP_YOUTUBE_CHANNEL_ID,
        "image_url": "https://i.ytimg.com/vi/exact123/maxresdefault.jpg",
    }
    audit = {
        "status": "fail",
        "width": 1280,
        "height": 720,
        "hard_failures": ["resolution-below-900x1200", "too-dark"],
    }

    adjusted = _apply_official_maxres_resolution_profile(candidate, audit)

    assert adjusted["resolution_profile"] == "official-youtube-maxres-1280x720"
    assert adjusted["hard_failures"] == ["too-dark"]
    assert adjusted["status"] == "fail"
    assert audit["hard_failures"] == ["resolution-below-900x1200", "too-dark"]
