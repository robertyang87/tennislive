from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image


def _selected_cover(match, folder):
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "verified-match-cover.jpg"
    Image.effect_noise((1200, 1600), 32).convert("RGB").save(source)
    return SimpleNamespace(path=source), {
        "schema_version": 2,
        "status": "selected",
        "match_id": match.match_id,
        "match_players": [player.name for player in match.home + match.away],
        "selected_player": match.home[0].name,
        "exact_match": True,
        "both_sides_match": True,
    }


def test_strict_cover_does_not_fall_back_when_chromium_render_fails(
    tmp_path, sample_digest, monkeypatch
):
    from tennislive.render import cards, webcards
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_STRICT", "on")
    monkeypatch.setattr(visual_sources, "resolve_match_cover_visual", _selected_cover)

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("simulated chromium failure")

    monkeypatch.setattr(webcards, "generate_deck", unavailable)

    with pytest.raises(RuntimeError, match="严格封面模式下 HTML 卡片渲染失败"):
        cards.generate_cards(sample_digest, tmp_path / "cards")

    assert not list((tmp_path / "cards").glob("card_00_cover.*"))
    report = json.loads((tmp_path / "cover_visual.json").read_text("utf-8"))
    assert report["render_binding"]["status"] == "render_failed"
    assert report["render_binding"]["renderer"] == "html-chromium"


def test_strict_cover_report_binds_verified_asset_to_final_card(
    tmp_path, sample_digest, monkeypatch
):
    from tennislive.render import cards, webcards
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_STRICT", "on")
    monkeypatch.setattr(visual_sources, "resolve_match_cover_visual", _selected_cover)
    monkeypatch.setattr(
        webcards,
        "generate_deck",
        lambda *_args, **_kwargs: [
            ("cover", Image.effect_noise((1080, 1440), 32).convert("RGB"))
        ],
    )

    paths = cards.generate_cards(sample_digest, tmp_path / "cards")

    assert [path.name for path in paths] == ["card_00_cover.jpg"]
    report = json.loads((tmp_path / "cover_visual.json").read_text("utf-8"))
    binding = report["render_binding"]
    assert binding["status"] == "bound"
    assert binding["renderer"] == "html-chromium"
    assert binding["match_id"] == report["match_id"]
    assert binding["selected_asset_sha256"] == report["selected_asset_sha256"]
    assert binding["card_file"] == "cards/card_00_cover.jpg"
    assert binding["card_sha256"] == hashlib.sha256(paths[0].read_bytes()).hexdigest()


def test_strict_cover_reselects_one_coherent_hot_headline(
    tmp_path, sample_digest, monkeypatch
):
    from tennislive.render import cards, rating, webcards
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_STRICT", "on")
    from tennislive.render.titles import daily_lead_match

    primary = daily_lead_match(sample_digest)
    assert primary is not None
    alternate = next(
        match for match in sample_digest.results if match.match_id != primary.match_id
    )
    monkeypatch.setattr(
        rating,
        "lead_story_candidates",
        lambda _digest: [
            SimpleNamespace(match=primary),
            SimpleNamespace(match=alternate),
        ],
    )

    def resolve(match, folder):
        if match.match_id == primary.match_id:
            return None, {
                "status": "unavailable",
                "match_id": match.match_id,
                "errors": ["no-qualified-photo"],
                "providers_queried": ["official-match-media"],
            }
        visual, report = _selected_cover(match, folder)
        report.update(
            headline_hot=True,
            headline_eligible=True,
            quality={
                "status": "pass",
                "hard_failures": [],
            },
            quality_score=90,
        )
        return visual, report

    monkeypatch.setattr(visual_sources, "resolve_match_cover_visual", resolve)
    monkeypatch.setattr(
        webcards,
        "generate_deck",
        lambda digest, *_args, **_kwargs: [
            (
                "cover",
                Image.effect_noise((1080, 1440), 32).convert("RGB"),
            )
        ],
    )

    paths = cards.generate_cards(sample_digest, tmp_path / "cards")

    assert paths[0].name == "card_00_cover.jpg"
    assert sample_digest.lead_match_id == alternate.match_id
    report = json.loads((tmp_path / "cover_visual.json").read_text("utf-8"))
    assert report["match_id"] == alternate.match_id
    assert report["headline_selection"]["status"] == "reselected"
    assert report["headline_selection"]["primary_match_id"] == primary.match_id
    assert report["headline_selection"]["selected_match_id"] == alternate.match_id
    assert report["headline_selection"]["failed_candidates"] == [
        {
            "match_id": primary.match_id,
            "status": "unavailable",
            "errors": ["no-qualified-photo"],
            "providers_queried": ["official-match-media"],
        }
    ]


def test_strict_cover_uses_truthful_branded_fallback_when_no_photo(
    tmp_path, sample_digest, monkeypatch
):
    from tennislive.render import cards, webcards
    from tennislive.research import visual_sources

    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_STRICT", "on")

    def unavailable(_match, _folder):
        return None, {"status": "unavailable", "errors": ["no-qualified-photo"]}

    monkeypatch.setattr(visual_sources, "resolve_match_cover_visual", unavailable)
    monkeypatch.setattr(
        webcards,
        "generate_deck",
        lambda *_args, **_kwargs: [
            ("cover", Image.effect_noise((1080, 1440), 32).convert("RGB"))
        ],
    )

    paths = cards.generate_cards(sample_digest, tmp_path / "cards")

    assert paths[0].name == "card_00_cover.jpg"
    report = json.loads((tmp_path / "cover_visual.json").read_text("utf-8"))
    assert report["status"] == "branded_fallback"
    assert report["fallback_reason"] == "no-qualified-photo"
    assert report["render_binding"]["status"] == "bound"


def test_daily_workflow_never_swallows_digest_failure_and_checks_card_binding():
    workflow = Path(".github/workflows/daily.yml").read_text(encoding="utf-8")

    assert 'exit "$CODE"' in workflow
    assert "continuing so generated materials are not lost" not in workflow
    assert "grep -q '^\\[FATAL\\]'" in workflow
    assert '.render_binding.status == "bound"' in workflow
    assert '.render_binding.card_file == "cards/card_00_cover.jpg"' in workflow
    assert 'sha256sum "$COVER_CARD"' in workflow
