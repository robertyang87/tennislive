from __future__ import annotations

from unittest.mock import Mock

import pytest
import requests

from tennislive.publish.pushplus import PushPlusError, image_sources, wait_for_images


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
