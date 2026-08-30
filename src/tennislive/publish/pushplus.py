"""PushPlus（pushplus.plus）微信推送：把每日内容推到你自己的微信.

用于「不自动发文，但每天把排版好的内容推到微信里，人工一键转发」的轻量方案。
注册 pushplus 后关注其公众号即可收到消息。

环境变量 / GitHub Secrets：
    PUSHPLUS_TOKEN   pushplus 的 token
"""

from __future__ import annotations

import logging
import mimetypes
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from ..cdn import is_jsdelivr, jsdelivr_base

logger = logging.getLogger(__name__)

URL = "https://www.pushplus.plus/send"
ACCESS_KEY_URL = "https://www.pushplus.plus/api/common/openApi/getAccessKey"
UPLOAD_TOKEN_URL = "https://www.pushplus.plus/api/open/userImage/uploadToken"


class PushPlusError(RuntimeError):
    pass


class PushPlusUncertainError(PushPlusError):
    """请求可能已被平台接收，但客户端没有拿到可落账的响应。"""


class _AssetSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.image_sources: list[str] = []
        self.link_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        value = dict(attrs).get("src" if tag == "img" else "href")
        if tag not in {"img", "a"} or not value:
            return
        if not value.startswith(("https://", "http://")):
            return
        (self.image_sources if tag == "img" else self.link_sources).append(value)


def image_sources(html_content: str) -> list[str]:
    """Return unique remote image URLs in their message order."""
    parser = _AssetSourceParser()
    parser.feed(html_content)
    return list(dict.fromkeys(parser.image_sources))


def jsdelivr_link_sources(html_content: str) -> list[str]:
    """Return unique <a href> targets hosted on the jsDelivr GitHub CDN.

    These are the only links a push message can reference that may have been
    committed moments earlier in the same CI run (e.g. the Hot Shots video
    link) -- everything else on the jsDelivr GitHub CDN is either an image
    (already covered by ``image_sources``) or a link to unrelated, older
    content. GitHub Pages links (the copy page) are intentionally excluded:
    Pages deploys lag much further behind a push than jsDelivr's origin
    pull, and blocking the whole notification on that would trade one
    failure mode for a much slower one.
    """
    parser = _AssetSourceParser()
    parser.feed(html_content)
    return list(
        dict.fromkeys(
            url for url in parser.link_sources if is_jsdelivr(url)
        )
    )


# GitHub Release 附件的下载链接（302 → release-assets.githubusercontent.com）。
# ⚠️ 判据宁可窄：只认 `/releases/download/` 这个形状，别把正文里随手贴的
# github.com 链接（issue、commit、run 日志）都拉进发前探活——那些不是
# 本次 run 传上去的东西，探它们只会把无关的 404 变成「取消推送」。
_RELEASE_DOWNLOAD_RE = re.compile(
    r"^https://github\.com/[^/\s]+/[^/\s]+/releases/download/"
)


def release_link_sources(html_content: str) -> list[str]:
    """Return unique ``<a href>`` targets pointing at GitHub Release assets.

    2026-08-13 起成片一律走 Release、不进 git（账号所有者：「所有视频统一走
    Release 路线」），推送里的 ▶ 按钮从 jsDelivr 换成了 Release 下载链接。
    而 ``wait_for_images`` 原来只探 jsDelivr 的 ``<a>``——换链之后**这条线上
    唯一的发前成片探活会静默消失**（CLAUDE.md：成片取不到必须整条不发；
    jsDelivr 时代它是被 ``jsdelivr_link_sources`` 顺带盖住的）。requests
    默认跟 302 重定向，所以探 Release 链接和探 jsDelivr 是同一段代码。
    """
    parser = _AssetSourceParser()
    parser.feed(html_content)
    return list(
        dict.fromkeys(
            url for url in parser.link_sources if _RELEASE_DOWNLOAD_RE.match(url)
        )
    )


def _response_json(response: requests.Response, action: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise PushPlusError(
            f"{action}返回异常: HTTP {response.status_code}"
        ) from exc
    if not response.ok:
        raise PushPlusError(f"{action}失败: HTTP {response.status_code}")
    return payload


# AccessKey 等可安全重放的辅助请求可以重试；真正发消息的 POST 没有平台幂等键，
# 网络异常/5xx 都可能发生在服务端已经收下之后，必须只发一次并记为 uncertain。
AUXILIARY_ATTEMPTS = 4
AUXILIARY_RETRY_SECONDS = 5.0


# PushPlus 官方返回码表（`/doc/guide/code.html`）里跟开放接口有关的那几个。
#
# **只打印 msg 是不够的：这几个码是几件完全不同的事，出路也完全不同**，
# 而它们的中文写得非常像——「请求未授权」和「请求IP未授权」并排放着，
# 读起来都像「你的凭据不对」，实际一个是后台开关没开、一个是白名单。
#
# 2026-08-04 纳达尔学院那趟拿到的是 **401**，而我当时在日志里写的是
# 「通常是 PUSHPLUS_SECRET_KEY 失效或会员到期」——**两头都错**：令牌无效是
# 903，付费问题是 888。我从「/send 用同一个 token 成功了，所以不是 token 错」
# 推到了「那就是会员到期」，中间那一步是凭空多出来的（CLAUDE.md：
# 「排除了 A 和 B」不等于「就是 C」）。码表就在官网上，查一次的事。
_ACCESS_KEY_HINTS = {
    401: (
        "开放接口功能没启用。它**默认就是禁用的**，要在 PushPlus 后台"
        "「开发设置」里手动打开（官方原话：默认是禁用状态，需要用户手动的"
        "在开发设置中开启）"
    ),
    403: (
        "请求 IP 不在安全 IP 白名单里。⚠️ GitHub Actions runner 的出口 IP "
        "每趟都不一样，白名单这条路对 CI 基本无解"
    ),
    903: (
        "PUSHPLUS_TOKEN 不对，或者给的是「消息token」——getAccessKey 只认"
        "用户token（官方参数说明写着「不支持消息token」）"
    ),
    888: "积分不足，需要充值",
    905: "账户未进行实名认证",
    900: "请求次数过多，账号被限流",
}


def _access_key(token: str, secret_key: str, timeout: int) -> str:
    """取图床的 AccessKey。**网络抖动要重试**——它排在发消息之前，
    一次失败就把整条推送带走，而这一步跟内容对不对没有任何关系。"""
    last = ""
    for attempt in range(AUXILIARY_ATTEMPTS):
        try:
            response = requests.post(
                ACCESS_KEY_URL,
                json={"token": token, "secretKey": secret_key},
                timeout=timeout,
            )
            break
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
            logger.warning("取 AccessKey 第 %d/%d 次失败（%s）",
                           attempt + 1, AUXILIARY_ATTEMPTS, last)
            if attempt + 1 < AUXILIARY_ATTEMPTS:
                time.sleep(AUXILIARY_RETRY_SECONDS)
    else:
        raise PushPlusError(
            f"取 PushPlus AccessKey {AUXILIARY_ATTEMPTS} 次都失败：{last}")
    payload = _response_json(response, "获取 PushPlus AccessKey")
    if payload.get("code") != 200 or not (payload.get("data") or {}).get(
        "accessKey"
    ):
        code = payload.get("code")
        hint = _ACCESS_KEY_HINTS.get(code, "")
        raise PushPlusError(
            f"获取 PushPlus AccessKey 失败: code={code} {payload.get('msg')}"
            + (f"——{hint}" if hint else "")
        )
    return str(payload["data"]["accessKey"])


def _upload_credentials(access_key: str, timeout: int) -> tuple[str, str]:
    response = requests.get(
        UPLOAD_TOKEN_URL,
        headers={"access-key": access_key},
        timeout=timeout,
    )
    payload = _response_json(response, "获取 PushPlus 图片上传凭证")
    data = payload.get("data") or {}
    upload_token = str(data.get("uploadToken") or "")
    upload_url = str(data.get("uploadUrl") or "")
    if payload.get("code") != 200 or not upload_token or not upload_url:
        raise PushPlusError(
            f"获取 PushPlus 图片上传凭证失败: {payload.get('msg')}"
        )
    return upload_url, upload_token


def _local_image_path(source: str, asset_dir: Path) -> Path | None:
    path_parts = [
        part
        for part in Path(unquote(urlparse(source).path)).parts
        if part not in {"/", "\\"}
    ]
    if "output" not in path_parts:
        return None
    root = asset_dir.resolve()
    tail = path_parts[path_parts.index("output") :]
    for offset in range(len(tail)):
        candidate = (root / Path(*tail[offset:])).resolve()
        if candidate != root and root not in candidate.parents:
            continue
        if candidate.is_file():
            return candidate
    return None


def _upload_image(
    path: Path,
    *,
    upload_url: str,
    upload_token: str,
    timeout: int,
) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as image_file:
        response = requests.post(
            upload_url,
            data={"token": upload_token},
            files={"file": (path.name, image_file, content_type)},
            timeout=timeout,
        )
    payload = _response_json(response, f"上传图片 {path.name}")
    if payload.get("errno") != 0 or not payload.get("url"):
        raise PushPlusError(
            f"上传图片 {path.name} 失败: {payload.get('msg', '返回缺少 URL')}"
        )
    return str(payload["url"])


def _pages_image_url(source: str, revision: str) -> str | None:
    """Build a jsDelivr GitHub CDN URL pinned to an exact commit.

    Previously this pointed at GitHub Pages with the commit as a ``?v=``
    query string for cache-busting. The output path is date-based, so the
    same path is reused (with different content) by every ad-hoc run on a
    given day -- and WeChat's own image cache keys off the URL path, not
    the query string, so it kept serving whatever bitmap it first fetched
    for that path and ignored later ``?v=`` updates. Pinning the commit
    into the URL *path* (jsDelivr's ``@<sha>/`` syntax) makes each version
    a genuinely distinct resource, which any path-based cache handles
    correctly.
    """
    parsed = urlparse(source)
    marker = "/output/"
    if marker not in parsed.path:
        return None
    output_path = parsed.path[parsed.path.index(marker) + 1 :]
    repository = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
    owner_repo = repository.split("/", 1)
    if len(owner_repo) != 2:
        return None
    pinned_revision = revision if re.fullmatch(r"[0-9a-fA-F]{7,40}", revision or "") else "main"
    return f"{jsdelivr_base(repository, pinned_revision)}/{output_path}"


def _pushplus_bed_delivery(
    html_content: str,
    sources: list[str],
    root: Path,
    *,
    token: str,
    secret_key: str,
    configured_access_key: str,
    timeout: int,
) -> str:
    """把消息里的图片传到 PushPlus 自己的图床，返回改写后的 HTML。"""
    access_key = (
        _access_key(token, secret_key, timeout)
        if secret_key
        else configured_access_key
    )
    upload_url, upload_token = _upload_credentials(access_key, timeout)
    replacements: dict[str, str] = {}
    for source in sources:
        local_path = _local_image_path(source, root)
        if local_path is None:
            continue
        replacements[source] = _upload_image(
            local_path,
            upload_url=upload_url,
            upload_token=upload_token,
            timeout=timeout,
        )
    if len(replacements) != len(sources):
        raise PushPlusError("PushPlus 原生图床未覆盖全部消息图片")
    for source, replacement in replacements.items():
        html_content = html_content.replace(source, replacement)
    return html_content


def _jsdelivr_delivery(
    html_content: str, sources: list[str], root: Path | None
) -> str:
    """退回钉在 commit 上的 jsDelivr／raw 链接，返回改写后的 HTML。

    **每一张都要映射得上**，缺一张就整条不发——半张图的推送发出去收不回来。
    """
    revision = os.environ.get("TENNISLIVE_ASSET_REV", "main")
    replacements: dict[str, str] = {}
    for source in sources:
        local_path = _local_image_path(source, root) if root else None
        pages_url = _pages_image_url(source, revision)
        if local_path is not None and pages_url:
            replacements[source] = pages_url
    if len(replacements) != len(sources):
        raise PushPlusError(
            "消息图片无法映射到稳定图床，已取消本次推送"
        )
    for source, replacement in replacements.items():
        html_content = html_content.replace(source, replacement)
    return html_content


def prepare_image_delivery(
    html_content: str,
    *,
    asset_dir: str | Path | None,
    token: str,
    timeout: int = 30,
) -> tuple[str, str]:
    """Use PushPlus' image CDN when configured, otherwise a commit-pinned
    jsDelivr URL (see ``_pages_image_url`` for why it's commit-pinned)."""
    sources = image_sources(html_content)
    if not sources:
        return html_content, "none"

    root = Path(asset_dir) if asset_dir else None
    secret_key = os.environ.get("PUSHPLUS_SECRET_KEY", "").strip()
    configured_access_key = os.environ.get("PUSHPLUS_ACCESS_KEY", "").strip()
    provider = "jsdelivr"
    if root and (secret_key or configured_access_key):
        try:
            delivered = _pushplus_bed_delivery(
                html_content,
                sources,
                root,
                token=token,
                secret_key=secret_key,
                configured_access_key=configured_access_key,
                timeout=timeout,
            )
        except PushPlusError as exc:
            # **图床只是个优化，不是这条推送的内容。** 它换来的仅仅是「发之前
            # 不必等 jsDelivr 回源」，而下面那条退路更耐久（钉 commit、永久可取）。
            # 让一个优化的鉴权失败把**唯一真正发消息的那一步**带走，是这个仓库
            # 记过的那个形状的反面：「保护了不重要的那一步，没保护唯一重要的那
            # 一步」——这里更糟，不重要的那一步直接**否决**了重要的那一步。
            # 2026-08-04 纳达尔学院那趟就是这么死的（run 30903125364）：片子渲完、
            # 提交完、复制页第 1 次探活就命中，最后死在「获取 AccessKey：请求未授权」。
            #
            # 退回是安全的：`_jsdelivr_delivery` 自己重做一遍全覆盖检查，
            # 之后 `wait_for_images` 还会逐张探活——发不出半张图的消息。
            #
            # ⚠️ **通道名必须分得出是哪一种 jsdelivr。** 「没配过所以走这条」和
            # 「图床把我拒了所以走这条」在旧口径下都打印 `jsdelivr`，于是一个
            # 坏掉的付费订阅和一个从没开过的功能长得一模一样——正是「兜底出事
            # 的时候不吭声」。
            # ⚠️ **这里不许再自己猜原因。** 上一版在这句里写死了「通常是
            # PUSHPLUS_SECRET_KEY 失效或会员到期」——而真实的码是 401
            # （开放接口没启用），令牌无效是 903、付费问题是 888，两头都猜错了。
            # 原因由 `_ACCESS_KEY_HINTS` 按码给出，这里只负责把它原样带出来。
            logger.error(
                "PushPlus 图床用不了（%s），本次退回 jsDelivr：图片改为钉在 "
                "commit 上的永久链接，代价是发送前要等回源。"
                "返回码含义见 pushplus.plus/doc/guide/code.html。",
                exc,
            )
            provider = "jsdelivr-fallback"
        else:
            # PushPlus 官方图床「图片有效期为 30 天，到期后将自动删除」
            # （/doc/function/image.html 的「使用限制」）。账号所有者 2026-08-04
            # 认领过这个取舍：换来的是发之前不用等 jsDelivr 回源。
            #
            # **但它必须写进日志。** 微信那条消息发出去收不回来，海报到期就变裂图，
            # 而那是一个月之后的事——两条通道当天的日志长得一模一样。将来有人查
            # 「这条老推送的图怎么裂了」，答案得在当天的日志里，而不是靠他重新
            # 把这一整节推理一遍。
            #
            # ⚠️ **位置就是判据的一半：它只能在图真的传上去之后说。** 上一版
            # 写在 `try` 前面（也就是「配了 key 就喊」），于是 2026-08-04
            # 王欣瑜那趟推送的日志里，这句和紧接着那句退回贴在一起：图明明钉在
            # commit 上永久可取，日志却说「到期会变裂图」。而这句话存在的**全部
            # 理由**就是给一个月后来查「这图怎么裂了」的人看的——在一条图永久的
            # run 上喊 30 天，正好把他引到错的答案上，比不吭声更坏。
            # 判据落在 `test_退回jsDelivr那趟不许还喊30天会删图`。
            logger.warning(
                "图片走 PushPlus 图床：官方限制 30 天后自动删除，"
                "这条推送的图到期会变裂图（已认领的取舍，换发送前不必等回源）。"
                "要改回永久可取就清掉 PUSHPLUS_SECRET_KEY / PUSHPLUS_ACCESS_KEY。"
            )
            return delivered, "pushplus"

    return _jsdelivr_delivery(html_content, sources, root), provider


def wait_for_images(
    html_content: str,
    *,
    attempts: int | None = None,
    delay: float | None = None,
    timeout: int = 15,
) -> None:
    """Wait until every remote image and freshly-pushed CDN link is fetchable.

    Images must additionally report an ``image/*`` content type; jsDelivr
    links (e.g. a Hot Shots video the same CI run just committed) and GitHub
    Release download links (成片 2026-08-13 起一律走 Release，不进 git) only
    need to resolve, since their content type varies by asset.
    """
    # Release 附件链接和 jsDelivr 链接同一档待遇：都是**本次 run 刚传上去**、
    # 发出去之前必须确认取得到的东西（成片取不到必须整条不发）。
    pending: list[tuple[str, bool]] = [
        (url, True) for url in image_sources(html_content)
    ] + [
        (url, False)
        for url in jsdelivr_link_sources(html_content)
        + release_link_sources(html_content)
    ]
    if not pending:
        return

    attempt_count = max(
        1,
        min(
            30,
            attempts
            if attempts is not None
            else int(
                os.environ.get(
                    "TENNISLIVE_PUSHPLUS_IMAGE_ATTEMPTS",
                    "20",
                )
            ),
        ),
    )
    retry_delay = max(
        0.0,
        min(
            60.0,
            delay
            if delay is not None
            else float(
                os.environ.get(
                    "TENNISLIVE_PUSHPLUS_IMAGE_RETRY_SECONDS",
                    "15",
                )
            ),
        ),
    )

    for attempt in range(attempt_count):
        unavailable: list[tuple[str, bool]] = []
        for url, is_image in pending:
            try:
                response = requests.get(url, stream=True, timeout=timeout)
                content_type = response.headers.get("Content-Type", "").lower()
                ready = response.ok and (
                    content_type.startswith("image/") if is_image else True
                )
                response.close()
            except requests.RequestException:
                ready = False
            if not ready:
                unavailable.append((url, is_image))
        if not unavailable:
            # The GitHub runner can see a freshly cached jsDelivr asset a few
            # seconds before PushPlus/WeChat's fetch nodes do. Give the
            # immutable revision a short propagation window before posting.
            settle_seconds = min(
                30.0,
                max(
                    0.0,
                    float(
                        os.environ.get(
                            "TENNISLIVE_PUSHPLUS_IMAGE_SETTLE_SECONDS", "0"
                        )
                    ),
                ),
            )
            if settle_seconds:
                time.sleep(settle_seconds)
            return
        pending = unavailable
        if attempt + 1 < attempt_count:
            logger.warning(
                "PushPlus assets are not ready yet (%d remaining, attempt %d/%d)",
                len(pending),
                attempt + 1,
                attempt_count,
            )
            time.sleep(retry_delay)

    raise PushPlusError(
        f"图片或视频尚未同步到 CDN，已取消本次推送（{len(pending)} 项不可访问）"
    )


def push(
    title: str,
    html_content: str,
    token: str | None = None,
    timeout: int = 30,
    *,
    asset_dir: str | Path | None = None,
) -> str:
    token = token or os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        raise PushPlusError("缺少 PUSHPLUS_TOKEN（请在环境变量或 GitHub Secrets 中配置）")
    html_content, image_provider = prepare_image_delivery(
        html_content,
        asset_dir=asset_dir,
        token=token,
        timeout=timeout,
    )
    wait_for_images(html_content)
    # 这是一个不可撤回、平台又没有幂等键的 POST。连接异常、读超时、5xx 并不
    # 证明平台没收下：自动重发会把同一条消息送进微信多次。因此只尝试一次；
    # 没拿到明确的 code=200 + 流水号就交给发布账本记 uncertain，禁止盲重发。
    try:
        resp = requests.post(
            URL,
            json={
                "token": token,
                "title": title[:100],
                "content": html_content,
                "template": "html",
                # 这条模块的产品语义就是“推送到微信”。不继承账号后台的
                # 默认渠道：默认值被改成 App/邮件时，接口照样 code=200，
                # 但用户微信里永远看不到。
                "channel": "wechat",
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise PushPlusUncertainError(
            "PushPlus 消息 POST 发生连接异常，平台是否接收状态不明；"
            "为避免微信重复消息，本次不会自动重发，请按流水号/手机实收人工核验"
        ) from exc
    if resp.status_code >= 500:
        raise PushPlusUncertainError(
            f"PushPlus 消息 POST 返回 HTTP {resp.status_code}，平台是否接收状态不明；"
            "为避免微信重复消息，本次不会自动重发")
    try:
        data = resp.json()
    except ValueError as exc:
        raise PushPlusUncertainError(
            f"PushPlus 消息 POST 返回无法解析的响应（HTTP {resp.status_code}），"
            "平台是否接收状态不明；本次不会自动重发") from exc
    if data.get("code") != 200:
        # 服务端明确拒绝；同样不重发，但错误本身不是“可能已接收”。
        raise PushPlusError(f"PushPlus 推送失败: {data}")
    # **流水号要记下来。** `code == 200` 只保证 **PushPlus 收下了**，不保证
    # 微信真的推到了手机上。2026-08-02 热亚那条就是这样：第 29 步 success、
    # 日志写着「已推送」，账号所有者问了两次「推微信了么」——而我手上一条
    # 可查的东西都没有。返回体里的 `data` 就是这条消息的流水号，PushPlus
    # 拿它查投递状态。
    #
    # ⚠️ **用 print 不用 logger。** 这个模块的 logger 在工作流里**没有配
    # handler**，`logger.info` 一个字都不会出现在日志里——上一版那句
    # 「PushPlus 推送成功（图片通道：…）」**从来没被人看见过**，连图片走的
    # 哪条通道都没人知道。又一次「不吭声」，而且不吭声的正是那条本该出声的
    # 记录。判据 `test_推送成功要把流水号打进日志` 断言的是 **stdout**，
    # 不是 caplog——退回 `logger.info` 时它捕获到的是空字符串。
    receipt = str(data.get("data") or "")
    if not receipt:
        raise PushPlusUncertainError(
            "PushPlus 返回 code=200 但没有流水号，不能证明平台接收了哪一条；"
            "状态不明且不会自动重发")
    print(f"[PushPlus] 收下了：流水号 {receipt or '(返回体里没有)'}"
          f"　投递通道 wechat　图片通道 {image_provider}"
          f"　msg={data.get('msg') or ''}")
    # 官方 OpenAPI 有发送结果查询能力，但不是拿消息 token + 流水号就能查：还要
    # 用户 secretKey、后台启用开放接口，并让请求 IP 通过安全白名单。当前发布
    # 工作流只配置 PUSHPLUS_TOKEN，GitHub Actions 出口 IP 也不固定，所以本趟
    # **没有投递证据**。不能因为查询条件暂时不具备，就反过来说官方没有接口；
    # 更不能把平台接收流水号口头升级成手机送达。
    print("[PushPlus] ⚠️ 这只代表接口收下，**不代表微信推到了手机上**。"
          "官方投递查询还需要 secretKey、开放接口开关和安全 IP 白名单；"
          "当前工作流不具备这些条件，所以手机送达状态仍是 unverified。")
    return receipt
