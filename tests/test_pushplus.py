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


class _FakeResponse:
    """PushPlus 的接口一律 HTTP 200，真正的结果在 body 的 `code` 里。"""

    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.ok = 200 <= status < 400

    def json(self) -> dict:
        return self._payload


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
    """这条路是**认领过**的（账号所有者 2026-08-04：图一个月后失效可以接受），
    但它必须把代价写进日志。

    PushPlus 官方图床「图片有效期为 30 天，到期后将自动删除」
    （`/doc/function/image.html` 的「使用限制」），而微信那条消息发出去
    收不回来也改不了——满月之后那条推送的海报变裂图。

    要命处在于**这一切一个月后才现形**，当天两条通道的日志长得一模一样。
    将来有人查「这条老推送的图怎么裂了」，答案得在当天的日志里躺着，
    而不是靠他重新把这一整节推理一遍。

    判据只钉「说没说」，不钉措辞——但那个数字和那个变量名得在，
    不然下一个人读到的只是一句没有出处、也没有出路的抱怨。
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
    assert "PUSHPLUS_SECRET_KEY" in said, "没说怎么改回永久可取——留了个没出路的告警"

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


def test_退回jsDelivr那趟不许还喊30天会删图(tmp_path, monkeypatch, caplog):
    """上一条钉了「走成了要说」和「没配过不许吵」，**漏了中间那一头**：
    配了 key、但图床把我拒了。

    2026-08-04 王欣瑜那趟推送（run 30906741325）就掉在这儿，两行贴在一起：

        图片走 PushPlus 图床：官方限制 30 天后自动删除，这条推送的图到期会变裂图
        PushPlus 图床用不了（…请求未授权），本次退回 jsDelivr
        …图片通道 jsdelivr-fallback

    那条片子的图**钉在 commit 上、永久可取**，一天都不会少。而这句告警存在的
    全部理由就是给一个月后来查「这条老推送的图怎么裂了」的人看的——在一条图
    永久的 run 上喊 30 天，**正好把他引到错的答案上**，比不吭声更坏。

    根因是位置：上一版写在 `try` 前面，也就是「配了 key 就喊」，而真正该问的
    是「图有没有真的传上去」。又一次「查产物，不查信号」。
    """
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "cover.jpg").write_bytes(b"image")
    monkeypatch.setenv("PUSHPLUS_SECRET_KEY", "secret")
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", "abc1234")
    # 喂线上那趟真收到的响应（code 401），别手搓异常——手搓证明不了
    # 真实失败长什么样。
    monkeypatch.setattr(
        "tennislive.publish.pushplus.requests.post",
        Mock(return_value=_FakeResponse({"code": 401, "msg": "请求未授权"})),
    )
    html = ('<img src="https://cdn.jsdelivr.net/gh/robertyang87/'
            'tennislive@abc123/output/2026-07-23/cards/cover.jpg">')

    # ⚠️ **必须收在 WARNING**。那句告警就是 WARNING，收在 ERROR 上它根本进不了
    #    caplog——断言会恒真，而恒真的判据和没有判据是同一个毛病。
    with caplog.at_level(logging.WARNING, logger="tennislive.publish.pushplus"):
        rendered, provider = prepare_image_delivery(
            html, asset_dir=tmp_path, token="token")

    assert provider == "jsdelivr-fallback"
    assert "abc1234" in rendered, "退回之后图片没钉到 commit 上，那才真该喊会裂"
    said = "\n".join(r.getMessage() for r in caplog.records)
    assert "退回 jsDelivr" in said, f"连退回都没说，这条测试的前提就没成立：{said!r}"
    assert "30 天" not in said, (
        f"图钉在 commit 上永久可取，日志却还在喊 30 天会删图：{said!r}")


def test_图床鉴权失败不许把整条推送带走(tmp_path, monkeypatch, caplog):
    """图床是**优化**，不是这条推送的内容——它用不了就退回 jsDelivr，别否决推送。

    2026-08-04 纳达尔学院那趟就是这么死的（run 30903125364）：片子渲完 2 分 20 秒、
    提交进 main、复制页第 1 次探活就命中，最后死在
    `获取 PushPlus AccessKey 失败: 请求未授权`——**一条已经做好的片子，
    因为一个可有可无的加速通道没鉴权成功，一个字都没发出去。**

    这是仓库里那条「保护了不重要的那一步，没保护唯一重要的那一步」的反面，
    而且更糟：不重要的那一步直接**否决**了重要的那一步。

    退回是安全的，两道闸还在：`_jsdelivr_delivery` 自己重做全覆盖检查（见下半段），
    发送前 `wait_for_images` 还会逐张探活。
    """
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "cover.jpg").write_bytes(b"image")
    monkeypatch.setenv("PUSHPLUS_SECRET_KEY", "secret")
    monkeypatch.setenv("GITHUB_REPOSITORY", "robertyang87/tennislive")
    monkeypatch.setenv("TENNISLIVE_ASSET_REV", "abc1234")
    # ⚠️ **不手搓那个异常。** 手搓只能证明「接住异常之后会退回」，证明不了
    #    真实失败长什么样、码和出路有没有真的走到日志里。这里让真的
    #    `_access_key` 跑一遍，喂它线上那趟收到的那个响应（code 401）。
    monkeypatch.setattr(
        "tennislive.publish.pushplus.requests.post",
        Mock(return_value=_FakeResponse({"code": 401, "msg": "请求未授权"})),
    )
    html = ('<img src="https://cdn.jsdelivr.net/gh/robertyang87/'
            'tennislive@abc123/output/2026-07-23/cards/cover.jpg">')

    with caplog.at_level(logging.ERROR, logger="tennislive.publish.pushplus"):
        rendered, provider = prepare_image_delivery(
            html, asset_dir=tmp_path, token="token")

    # ① 没抛，而且图片真的改写成了钉 commit 的永久链接
    assert "abc1234" in rendered, f"退回之后图片没钉到 commit 上：{rendered!r}"

    # ② **通道名要分得出是哪一种 jsdelivr。** 「从没配过」和「图床把我拒了」
    #    都打印 `jsdelivr` 的话，一个坏掉的付费订阅和一个没开过的功能长得
    #    一模一样——正是「兜底出事的时候不吭声」。
    assert provider == "jsdelivr-fallback", (
        f"退回之后通道名仍是 {provider!r}，看不出图床出过事")

    # ③ 出声，而且要说得出**是哪个码**和**该去干什么**
    said = "\n".join(r.getMessage() for r in caplog.records)
    assert "退回 jsDelivr" in said, f"悄悄退回了：{said!r}"
    assert "code=401" in said, f"没把返回码带出来，只有一句中文谁也查不了：{said!r}"
    assert "开发设置" in said, f"没说该去干什么——留了个没出路的告警：{said!r}"
    # ⚠️ 反面锚点：**不许再自己猜原因**。上一版这句写死了「PUSHPLUS_SECRET_KEY
    #    失效或会员到期」，而 401 两样都不是（令牌无效是 903、付费是 888）。
    assert "会员到期" not in said, f"又在按猜的原因写诊断：{said!r}"

    # ④ 退回**不等于放行**：映射不上的图片仍然整条不发。
    #    少了这一条，上面那个 try/except 就成了「出事就凑合发」。
    with pytest.raises(PushPlusError):
        prepare_image_delivery(
            '<img src="https://example.com/not-in-this-repo.jpg">',
            asset_dir=tmp_path,
            token="token",
        )


@pytest.mark.parametrize(
    "code, msg, must_say",
    [
        # 官方码表 pushplus.plus/doc/guide/code.html。这四条的中文写得非常像，
        # 而出路完全不同——只转发 msg 的话，读日志的人分不出该去干哪件事。
        (401, "请求未授权", "开发设置"),
        (403, "请求IP未授权", "白名单"),
        (903, "无效的用户令牌", "消息token"),
        (888, "积分不足", "充值"),
    ],
)
def test_取AccessKey失败要报出是哪个码和该去干什么(monkeypatch, code, msg, must_say):
    """「请求未授权」和「请求IP未授权」并排放着，读起来都像「你的凭据不对」。

    实际一个是**后台开关没开**（401），一个是**IP 白名单**（403）；
    而「令牌无效」是 903、「要付钱」是 888——**四件事，四条出路**。

    2026-08-04 我就是只看了 msg，然后从「/send 用同一个 token 成功了」
    推出「那就是会员到期」写进日志——令牌无效和付费问题的码都不是 401，
    两头都猜错了。码表就在官网上。
    """
    monkeypatch.setattr(
        "tennislive.publish.pushplus.requests.post",
        Mock(return_value=_FakeResponse({"code": code, "msg": msg})),
    )
    with pytest.raises(PushPlusError) as caught:
        pushplus._access_key("token", "secret", timeout=1)

    said = str(caught.value)
    assert f"code={code}" in said, f"没报出返回码，出了事没法查表：{said!r}"
    assert must_say in said, f"code={code} 没说出路：{said!r}"


def test_取AccessKey认不出的码也要把码带出来(monkeypatch):
    """码表会长，认不出的码**不许吞掉**——把数字带出来，人还能自己查。

    只打印 msg 的话，一个没见过的码和一个见过的码长得一模一样。
    """
    monkeypatch.setattr(
        "tennislive.publish.pushplus.requests.post",
        Mock(return_value=_FakeResponse({"code": 4242, "msg": "天知道"})),
    )
    with pytest.raises(PushPlusError) as caught:
        pushplus._access_key("token", "secret", timeout=1)
    assert "code=4242" in str(caught.value)
    assert "天知道" in str(caught.value)


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
