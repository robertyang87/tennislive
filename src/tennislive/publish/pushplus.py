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


# 发消息那个 POST 的重试预算。**只覆盖「没送到」**（网络异常、5xx），
# `code != 200` 是服务端明确拒绝，不重发。
PUSH_ATTEMPTS = 4
PUSH_RETRY_SECONDS = 5.0


def _access_key(token: str, secret_key: str, timeout: int) -> str:
    """取图床的 AccessKey。**网络抖动要重试**——它排在发消息之前，
    一次失败就把整条推送带走，而这一步跟内容对不对没有任何关系。"""
    last = ""
    for attempt in range(PUSH_ATTEMPTS):
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
                           attempt + 1, PUSH_ATTEMPTS, last)
            if attempt + 1 < PUSH_ATTEMPTS:
                time.sleep(PUSH_RETRY_SECONDS)
    else:
        raise PushPlusError(f"取 PushPlus AccessKey {PUSH_ATTEMPTS} 次都失败：{last}")
    payload = _response_json(response, "获取 PushPlus AccessKey")
    if payload.get("code") != 200 or not (payload.get("data") or {}).get(
        "accessKey"
    ):
        raise PushPlusError(f"获取 PushPlus AccessKey 失败: {payload.get('msg')}")
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
    if root and (secret_key or configured_access_key):
        # PushPlus 官方图床「图片有效期为 30 天，到期后将自动删除」
        # （/doc/function/image.html 的「使用限制」）。账号所有者 2026-08-04
        # 认领过这个取舍：换来的是发之前不用等 jsDelivr 回源。
        #
        # **但它必须写进日志。** 微信那条消息发出去收不回来，海报到期就变裂图，
        # 而那是一个月之后的事——两条通道当天的日志长得一模一样。将来有人查
        # 「这条老推送的图怎么裂了」，答案得在当天的日志里，而不是靠他重新
        # 把这一整节推理一遍。
        logger.warning(
            "图片走 PushPlus 图床：官方限制 30 天后自动删除，"
            "这条推送的图到期会变裂图（已认领的取舍，换发送前不必等回源）。"
            "要改回永久可取就清掉 PUSHPLUS_SECRET_KEY / PUSHPLUS_ACCESS_KEY。"
        )
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
            raise PushPlusError(
                "PushPlus 原生图床未覆盖全部消息图片，已取消本次推送"
            )
        for source, replacement in replacements.items():
            html_content = html_content.replace(source, replacement)
        return html_content, "pushplus"

    revision = os.environ.get("TENNISLIVE_ASSET_REV", "main")
    replacements = {}
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
    return html_content, "jsdelivr"


def wait_for_images(
    html_content: str,
    *,
    attempts: int | None = None,
    delay: float | None = None,
    timeout: int = 15,
) -> None:
    """Wait until every remote image and freshly-pushed CDN link is fetchable.

    Images must additionally report an ``image/*`` content type; jsDelivr
    links (e.g. a Hot Shots video the same CI run just committed) only need
    to resolve, since their content type varies by asset.
    """
    pending: list[tuple[str, bool]] = [
        (url, True) for url in image_sources(html_content)
    ] + [(url, False) for url in jsdelivr_link_sources(html_content)]
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
) -> None:
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
    # **这一步必须重试。** 走到这儿之前已经串着等了三轮：复制页最长 10 分钟、
    # 成片 2 分钟、图片 5 分钟——而**这个 POST 才是唯一真正发消息的动作**，
    # 原来一次网络抖动就把前面十几分钟全废掉。更荒唐的是 `_upload_image`
    # （传图片，失败了还能退回 jsDelivr）**反而有**重试循环：
    # **保护了不重要的那一步，没保护唯一重要的那一步。**
    #
    # ⚠️ **只重试「没送到」，不重试「送到了但被拒」。** 网络异常和 HTTP 5xx
    # 说明服务端多半没收下，重发是安全的；而 `code != 200` 是 PushPlus 明确
    # 拒绝（token 错、内容超限），重发只会把同一条错误消息发很多次——
    # 微信那条消息发出去收不回来，宁可一次都不发。
    data: dict = {}
    last = ""
    for attempt in range(PUSH_ATTEMPTS):
        try:
            resp = requests.post(
                URL,
                json={
                    "token": token,
                    "title": title[:100],
                    "content": html_content,
                    "template": "html",
                },
                timeout=timeout,
            )
            if resp.status_code >= 500:
                last = f"HTTP {resp.status_code}"
            else:
                try:
                    data = resp.json()
                except ValueError as e:
                    raise PushPlusError(
                        f"PushPlus 返回异常: HTTP {resp.status_code}") from e
                if data.get("code") != 200:
                    # 服务端明确拒绝：重发只会发出很多条一样的错误消息
                    raise PushPlusError(f"PushPlus 推送失败: {data}")
                break
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        logger.warning("PushPlus 第 %d/%d 次没发出去（%s），%.0fs 后重试",
                       attempt + 1, PUSH_ATTEMPTS, last, PUSH_RETRY_SECONDS)
        if attempt + 1 < PUSH_ATTEMPTS:
            time.sleep(PUSH_RETRY_SECONDS)
    else:
        raise PushPlusError(
            f"PushPlus {PUSH_ATTEMPTS} 次都没发出去（{last}）。"
            "前面等复制页、成片、图片都成功了，卡在最后这一步——重跑即可。")
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
    print(f"[PushPlus] 收下了：流水号 {data.get('data') or '(返回体里没有)'}"
          f"　图片通道 {image_provider}　msg={data.get('msg') or ''}")
    print(f"[PushPlus] ⚠️ 这只代表接口收下。要查微信有没有真的送达，用流水号问："
          f"https://www.pushplus.plus/api/send/queryMessage?token=<TOKEN>&id="
          f"{data.get('data') or '<流水号>'}")
