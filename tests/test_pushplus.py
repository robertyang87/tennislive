from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest
import requests

from tennislive.publish import pushplus
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


def test_走pushplus图床要先说清楚30天会删图(tmp_path, monkeypatch, caplog):
    """这条分支**默认走不到**，走到了必须出声。

    PushPlus 官方图床「图片有效期为 30 天，到期后将自动删除」
    （`/doc/function/image.html` 的「使用限制」），而微信那条消息发出去
    收不回来也改不了——满月之后每一条历史推送的海报一起变裂图。
    退路那条钉在 commit sha 上指向仓库，git 里的东西不会消失。

    也就是说这个「优化」的代价要**一个月后**才现形：日志上它和正常那条
    长得一模一样。这个仓库里那类不吭声的兜底已经栽过太多次，所以这里
    宁可吵一句。判据只钉「说没说」，不钉措辞——但那两个数字得在，
    不然下一个人读到的只是一句没有判据的抱怨。
    """
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "cover.jpg").write_bytes(b"image")
    monkeypatch.setenv("PUSHPLUS_SECRET_KEY", "secret")
    monkeypatch.setattr(
        "tennislive.publish.pushplus._access_key", Mock(return_value="access"))
    monkeypatch.setattr(
        "tennislive.publish.pushplus._upload_credentials",
        Mock(return_value=("https://upload.example/", "upload-token")))
    monkeypatch.setattr(
        "tennislive.publish.pushplus._upload_image",
        Mock(return_value="https://pic.pushplus.plus/1/cover.jpg@p"))
    html = ('<img src="https://cdn.jsdelivr.net/gh/robertyang87/'
            'tennislive@abc123/output/2026-07-23/cards/cover.jpg">')

    with caplog.at_level(logging.WARNING, logger="tennislive.publish.pushplus"):
        _, provider = prepare_image_delivery(
            html, asset_dir=tmp_path, token="token")
    assert provider == "pushplus"
    said = "\n".join(r.message for r in caplog.records)
    assert "30 天" in said, f"走了会删图的那条路却没出声：{said!r}"
    assert "PUSHPLUS_SECRET_KEY" in said, "没说怎么退回去——报错要说出路"

    # 反过来：默认那条路**不许**吵。一条恒真的告警和没有告警一样没用，
    # 而且它会把真正该看见的那次淹掉。
    caplog.clear()
    monkeypatch.delenv("PUSHPLUS_SECRET_KEY")
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", "abc1234")
    with caplog.at_level(logging.WARNING, logger="tennislive.publish.pushplus"):
        _, provider = prepare_image_delivery(
            html, asset_dir=tmp_path, token="token")
    assert provider == "jsdelivr"
    assert not [r for r in caplog.records if "30 天" in r.message]


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


def test_推送成功要把流水号打进日志(monkeypatch, capsys):
    """**`code == 200` 只说明 PushPlus 收下了，不说明微信送到了人手机上。**

    2026-08-02 热亚那条：第 29 步 success、日志写着「已推送」，账号所有者
    问了两次「推微信了么」——而我手上**一条可查的东西都没有**，因为返回体
    整个被丢掉了，只留下一句没有主语的「推送成功」。

    返回体的 `data` 就是这条消息的流水号，PushPlus 拿它查投递状态。判据钉两头：
    流水号要出现在 **stdout**（不是 `logger`——这个模块的 logger 在工作流里
    没有 handler，`logger.info` 一个字都不会出现，上一版那句「图片通道」
    就从来没被人看见过），而且要**明说「这只代表接口收下」**，别让下一个人
    再把它读成「送达了」。
    """
    monkeypatch.setattr(pushplus, "prepare_image_delivery",
                        Mock(return_value=("<p>hi</p>", "jsdelivr")))
    monkeypatch.setattr(pushplus, "wait_for_images", Mock())
    monkeypatch.setattr(requests, "post", Mock(return_value=Mock(
        status_code=200,
        json=Mock(return_value={"code": 200, "msg": "请求成功",
                                "data": "abc123def456"}))))

    pushplus.push("标题", "<p>hi</p>", token="t")

    out = capsys.readouterr().out
    assert "abc123def456" in out, f"流水号没进日志：{out!r}"
    # 反面：不许只说「成功」就完事——那正是这次查不下去的原因
    assert "只代表接口收下" in out, f"没说清 200 意味着什么：{out!r}"
