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


def test_prepare_image_delivery_uses_jsdelivr_fallback(tmp_path, monkeypatch):
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "cover.jpg").write_bytes(b"image")
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", "abc1234")

    rendered, provider = prepare_image_delivery(
        '<img src="https://cdn.jsdelivr.net/gh/robertyang87/'
        'tennislive@main/output/2026-07-23/cards/cover.jpg">',
        asset_dir=tmp_path,
        token="token",
    )

    assert provider == "jsdelivr"
    # Pinned to the exact commit (not "@main") so the URL path itself is a
    # distinct resource per version -- avoids caches that key off the path
    # only and ignore query strings.
    #
    # 主机名从配置读，不写死：镜像是可换的（见 tennislive/cdn.py），这条测试
    # 要盯的是「钉住了 commit」，不是「用的哪个入口」。
    from tennislive.cdn import jsdelivr_host

    assert (
        f"https://{jsdelivr_host()}/gh/robertyang87/tennislive@abc1234/"
        "output/2026-07-23/cards/cover.jpg"
    ) in rendered
    assert "@main/" not in rendered
    assert "github.io" not in rendered


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


def test_换镜像之后校验和钉版本都还认得出jsDelivr(monkeypatch):
    """镜像主机名换掉之后，两处按 `cdn.jsdelivr.net` 写死的判据会**悄悄失效**。

    账号所有者反馈国内下载慢，选了「换 jsDelivr 镜像」。主机名从
    `cdn.jsdelivr.net` 换成 `gcore.jsdelivr.net` 之后，原来那两处只认
    `cdn.` 的地方不会报错，只会不匹配：

    · `jsdelivr_link_sources` 返回空 —— 推送前那道「链接可取吗」的校验
      变成一张都不校验，然后把一堆还没就绪的链接发出去
    · `_JSDELIVR_MAIN_RE` 匹配不上 —— 图片全停在 `@main`，钉 commit 那步
      等于没做，同一路径的新旧内容会被微信的图片缓存混起来

    两个都是「兜底出事的时候不吭声」，和补位静音盖住真音轨、
    `-filter_complex` 不打标签就静默失效是同一类。
    """
    from tennislive.cdn import DEFAULT_JSDELIVR_HOST, jsdelivr_host
    from tennislive.publish.pushplus import jsdelivr_link_sources
    from tennislive.render.pushmsg import pin_asset_revision

    assert DEFAULT_JSDELIVR_HOST != "cdn.jsdelivr.net", "这条测试的前提没了"

    rev = "37853825db235e7290df16fe890d00d556327d94"
    for host in ("cdn.jsdelivr.net", DEFAULT_JSDELIVR_HOST, "fastly.jsdelivr.net"):
        url = f"https://{host}/gh/robertyang87/tennislive@main/output/x/a.mp4"
        html = f'<a href="{url}">片子</a><img src="{url[:-4]}.jpg">'

        assert jsdelivr_link_sources(html) == [url], f"{host} 的链接没被收进校验"
        pinned = pin_asset_revision(html, rev)
        assert f"@{rev}/" in pinned, f"{host} 的资源没被钉住版本"
        assert "@main/" not in pinned, f"{host} 还有没钉住的 @main"

    # 环境变量能换镜像，写错的域名要退回默认——发出去一封全是裂图的推送，
    # 比慢一点糟得多。
    monkeypatch.setenv("TENNISLIVE_JSDELIVR_HOST", "fastly.jsdelivr.net")
    assert jsdelivr_host() == "fastly.jsdelivr.net"
    monkeypatch.setenv("TENNISLIVE_JSDELIVR_HOST", "evil.example.com")
    assert jsdelivr_host() == DEFAULT_JSDELIVR_HOST
    monkeypatch.setenv("TENNISLIVE_JSDELIVR_HOST", "")
    assert jsdelivr_host() == DEFAULT_JSDELIVR_HOST


def test_发消息那个POST要重试但被拒绝时不许重发(monkeypatch):
    """**走到这一步之前已经串着等了三轮**：复制页最长 10 分钟、成片 2 分钟、
    图片 5 分钟。而这个 POST 才是唯一真正发消息的动作——原来它**一次重试都
    没有**，一次网络抖动就把前面十几分钟全废掉。

    更荒唐的是 `_upload_image`（传图片，失败了还能退回 jsDelivr）**反而有**
    重试循环：**保护了不重要的那一步，没保护唯一重要的那一步。**

    ⚠️ **但只重试「没送到」。** `code != 200` 是 PushPlus 明确拒绝（token 错、
    内容超限），重发只会把同一条错误消息发很多次——而微信那条消息发出去
    收不回来。判据把这两支分开验。
    """
    import requests as _rq

    from tennislive.publish import pushplus

    monkeypatch.setattr(pushplus.time, "sleep", lambda *_: None)
    monkeypatch.setattr(pushplus, "wait_for_images", lambda *_a, **_k: None)
    monkeypatch.setattr(pushplus, "prepare_image_delivery",
                        lambda html, **_k: (html, "none"))
    monkeypatch.setenv("PUSHPLUS_TOKEN", "t")

    class _Resp:
        def __init__(self, code=200, status=200):
            self.status_code = status
            self._code = code

        def json(self):
            return {"code": self._code, "data": "流水号-123"}

    # ① 前两次网络抖动，第三次成功 → 发出去了，而且只发了一次成功的
    calls = []

    def _flaky(*_a, **_k):
        calls.append(1)
        if len(calls) < 3:
            raise _rq.ConnectionError("boom")
        return _Resp()

    monkeypatch.setattr(pushplus.requests, "post", _flaky)
    pushplus.push("标题", "<p>正文</p>")
    assert len(calls) == 3, f"抖动了两次却没重试到成功：{len(calls)}"

    # ② 5xx 也算「没送到」，要重试
    calls.clear()

    def _five(*_a, **_k):
        calls.append(1)
        return _Resp(status=503) if len(calls) < 2 else _Resp()

    monkeypatch.setattr(pushplus.requests, "post", _five)
    pushplus.push("标题", "<p>正文</p>")
    assert len(calls) == 2, "5xx 没有重试"

    # ③ **服务端明确拒绝：只发一次，不许重发**
    calls.clear()
    monkeypatch.setattr(pushplus.requests, "post",
                        lambda *_a, **_k: (calls.append(1), _Resp(code=903))[1])
    with pytest.raises(pushplus.PushPlusError, match="推送失败"):
        pushplus.push("标题", "<p>正文</p>")
    assert len(calls) == 1, (
        f"被拒绝还重发了 {len(calls)} 次——那是往微信里灌同一条错误消息")

    # ④ 一直不通：报错要说清楚卡在哪一步，别让人以为是内容的问题
    calls.clear()

    def _dead(*_a, **_k):
        calls.append(1)
        raise _rq.ConnectionError("boom")

    monkeypatch.setattr(pushplus.requests, "post", _dead)
    with pytest.raises(pushplus.PushPlusError, match="都没发出去"):
        pushplus.push("标题", "<p>正文</p>")
    assert len(calls) == pushplus.PUSH_ATTEMPTS


def test_推送成功要记下流水号(monkeypatch, caplog):
    """`code == 200` 只保证 **PushPlus 收下了**，不保证微信推到了手机上。

    真出现「接口成功但人没收到」时，没有流水号就什么都查不了——这条
    CLAUDE.md 里记过，一直没做。
    """
    import logging

    from tennislive.publish import pushplus

    monkeypatch.setattr(pushplus, "wait_for_images", lambda *_a, **_k: None)
    monkeypatch.setattr(pushplus, "prepare_image_delivery",
                        lambda html, **_k: (html, "none"))
    monkeypatch.setenv("PUSHPLUS_TOKEN", "t")

    class _Resp:
        status_code = 200

        def json(self):
            return {"code": 200, "data": "abc123-流水号"}

    monkeypatch.setattr(pushplus.requests, "post", lambda *_a, **_k: _Resp())
    with caplog.at_level(logging.INFO):
        pushplus.push("标题", "<p>正文</p>")
    assert "abc123-流水号" in caplog.text, (
        f"成功那行没记流水号，出问题时无从查起：{caplog.text}")
