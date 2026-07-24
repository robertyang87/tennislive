from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from tennislive.publish.pushplus import (
    PushPlusError,
    image_sources,
    jsdelivr_link_sources,
    prepare_image_delivery,
    wait_for_images,
)


def test_image_sources_keeps_unique_remote_images_in_order():
    html = (
        '<img src="https://cdn.example/a.png">'
        '<img src="data:image/png;base64,abc">'
        '<img alt="b" src="https://cdn.example/b.jpg">'
        '<img src="https://cdn.example/a.png">'
    )

    assert image_sources(html) == [
        "https://cdn.example/a.png",
        "https://cdn.example/b.jpg",
    ]


def test_jsdelivr_link_sources_finds_video_link_but_not_pages_link():
    html = (
        '<a href="https://cdn.jsdelivr.net/gh/robertyang87/tennislive@main/'
        'output/2026-07-24/yesterday-point/yesterday-point.mp4">打开</a>'
        '<a href="https://robertyang87.github.io/tennislive/output/'
        '2026-07-24/yesterday-point/copy.html">复制</a>'
    )

    assert jsdelivr_link_sources(html) == [
        "https://cdn.jsdelivr.net/gh/robertyang87/tennislive@main/"
        "output/2026-07-24/yesterday-point/yesterday-point.mp4"
    ]


def test_wait_for_images_retries_until_hot_shots_video_link_is_ready(monkeypatch):
    unavailable = Mock(ok=False, headers={})
    ready = Mock(ok=True, headers={"Content-Type": "video/mp4"})
    get = Mock(side_effect=[unavailable, ready])
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr("tennislive.publish.pushplus.time.sleep", Mock())

    wait_for_images(
        '<a href="https://cdn.jsdelivr.net/gh/robertyang87/tennislive@main/'
        'output/2026-07-24/yesterday-point/yesterday-point.mp4">打开</a>',
        attempts=2,
        delay=0,
    )

    assert get.call_count == 2


def test_wait_for_images_never_checks_github_pages_links(monkeypatch):
    get = Mock(side_effect=AssertionError("should not fetch a Pages link"))
    monkeypatch.setattr(requests, "get", get)

    wait_for_images(
        '<a href="https://robertyang87.github.io/tennislive/output/'
        '2026-07-24/yesterday-point/copy.html">复制</a>'
    )

    get.assert_not_called()


def test_wait_for_images_blocks_push_when_video_link_never_resolves(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        Mock(side_effect=requests.ConnectionError("not ready")),
    )
    monkeypatch.setattr("tennislive.publish.pushplus.time.sleep", Mock())

    with pytest.raises(PushPlusError, match="取消本次推送"):
        wait_for_images(
            '<a href="https://cdn.jsdelivr.net/gh/robertyang87/tennislive@main/'
            'output/2026-07-24/yesterday-point/yesterday-point.mp4">打开</a>',
            attempts=2,
            delay=0,
        )


def test_wait_for_images_retries_until_cdn_image_is_ready(monkeypatch):
    unavailable = Mock(ok=False, headers={})
    ready = Mock(ok=True, headers={"Content-Type": "image/png"})
    get = Mock(side_effect=[unavailable, ready])
    monkeypatch.setattr(requests, "get", get)
    sleep = Mock()
    monkeypatch.setattr("tennislive.publish.pushplus.time.sleep", sleep)

    wait_for_images(
        '<img src="https://cdn.example/card.png">',
        attempts=2,
        delay=0,
    )

    assert get.call_count == 2
    sleep.assert_called_once_with(0.0)
    unavailable.close.assert_called_once()
    ready.close.assert_called_once()


def test_wait_for_images_blocks_incomplete_push(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        Mock(side_effect=requests.ConnectionError("not ready")),
    )
    monkeypatch.setattr("tennislive.publish.pushplus.time.sleep", Mock())

    with pytest.raises(PushPlusError, match="取消本次推送"):
        wait_for_images(
            '<img src="https://cdn.example/card.png">',
            attempts=2,
            delay=0,
        )


def test_wait_for_images_honors_post_cache_settle_window(monkeypatch):
    ready = Mock(ok=True, headers={"Content-Type": "image/jpeg"})
    monkeypatch.setattr(requests, "get", Mock(return_value=ready))
    sleep = Mock()
    monkeypatch.setattr("tennislive.publish.pushplus.time.sleep", sleep)
    monkeypatch.setenv("TENNISLIVE_PUSHPLUS_IMAGE_SETTLE_SECONDS", "20")

    wait_for_images('<img src="https://cdn.example/card.jpg">')

    sleep.assert_called_once_with(20.0)


def test_wait_for_images_uses_automatic_action_retry_window(monkeypatch):
    unavailable = Mock(ok=False, headers={})
    ready = Mock(ok=True, headers={"Content-Type": "image/jpeg"})
    get = Mock(side_effect=[unavailable, ready])
    monkeypatch.setattr(requests, "get", get)
    sleep = Mock()
    monkeypatch.setattr("tennislive.publish.pushplus.time.sleep", sleep)
    monkeypatch.setenv("TENNISLIVE_PUSHPLUS_IMAGE_ATTEMPTS", "20")
    monkeypatch.setenv("TENNISLIVE_PUSHPLUS_IMAGE_RETRY_SECONDS", "15")

    wait_for_images('<img src="https://cdn.example/card.jpg">')

    assert get.call_count == 2
    sleep.assert_called_once_with(15.0)


def test_prepare_image_delivery_uses_github_pages_fallback(tmp_path, monkeypatch):
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "cover.jpg").write_bytes(b"image")
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", "abc123")

    rendered, provider = prepare_image_delivery(
        '<img src="https://cdn.jsdelivr.net/gh/robertyang87/'
        'tennislive@abc123/output/2026-07-23/cards/cover.jpg">',
        asset_dir=tmp_path,
        token="token",
    )

    assert provider == "github-pages"
    assert (
        "https://robertyang87.github.io/tennislive/output/2026-07-23/"
        "cards/cover.jpg?v=abc123"
    ) in rendered
    assert "cdn.jsdelivr.net" not in rendered


def test_prepare_image_delivery_uploads_every_card_to_pushplus(
    tmp_path, monkeypatch
):
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "cover.jpg").write_bytes(b"image")
    monkeypatch.setenv("PUSHPLUS_SECRET_KEY", "secret")
    monkeypatch.setattr(
        "tennislive.publish.pushplus._access_key",
        Mock(return_value="access"),
    )
    monkeypatch.setattr(
        "tennislive.publish.pushplus._upload_credentials",
        Mock(return_value=("https://upload.example/", "upload-token")),
    )
    upload = Mock(return_value="https://pic.pushplus.plus/1/cover.jpg@p")
    monkeypatch.setattr("tennislive.publish.pushplus._upload_image", upload)

    rendered, provider = prepare_image_delivery(
        '<img src="https://cdn.jsdelivr.net/gh/robertyang87/'
        'tennislive@abc123/output/2026-07-23/cards/cover.jpg">',
        asset_dir=tmp_path,
        token="token",
    )

    assert provider == "pushplus"
    assert "https://pic.pushplus.plus/1/cover.jpg@p" in rendered
    upload.assert_called_once()
