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
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

logger = logging.getLogger(__name__)

URL = "https://www.pushplus.plus/send"
ACCESS_KEY_URL = "https://www.pushplus.plus/api/common/openApi/getAccessKey"
UPLOAD_TOKEN_URL = "https://www.pushplus.plus/api/open/userImage/uploadToken"


class PushPlusError(RuntimeError):
    pass


class _ImageSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        src = dict(attrs).get("src")
        if src and src.startswith(("https://", "http://")):
            self.sources.append(src)


def image_sources(html_content: str) -> list[str]:
    """Return unique remote image URLs in their message order."""
    parser = _ImageSourceParser()
    parser.feed(html_content)
    return list(dict.fromkeys(parser.sources))


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


def _access_key(token: str, secret_key: str, timeout: int) -> str:
    response = requests.post(
        ACCESS_KEY_URL,
        json={"token": token, "secretKey": secret_key},
        timeout=timeout,
    )
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
    parsed = urlparse(source)
    marker = "/output/"
    if marker not in parsed.path:
        return None
    output_path = parsed.path[parsed.path.index(marker) + 1 :]
    repository = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
    owner_repo = repository.split("/", 1)
    if len(owner_repo) != 2:
        return None
    owner, repo = owner_repo
    return (
        f"https://{owner}.github.io/{repo}/{output_path}"
        f"?v={revision or 'main'}"
    )


def prepare_image_delivery(
    html_content: str,
    *,
    asset_dir: str | Path | None,
    token: str,
    timeout: int = 30,
) -> tuple[str, str]:
    """Use PushPlus' image CDN when configured, otherwise GitHub Pages."""
    sources = image_sources(html_content)
    if not sources:
        return html_content, "none"

    root = Path(asset_dir) if asset_dir else None
    secret_key = os.environ.get("PUSHPLUS_SECRET_KEY", "").strip()
    configured_access_key = os.environ.get("PUSHPLUS_ACCESS_KEY", "").strip()
    if root and (secret_key or configured_access_key):
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
    return html_content, "github-pages"


def wait_for_images(
    html_content: str,
    *,
    attempts: int | None = None,
    delay: float | None = None,
    timeout: int = 15,
) -> None:
    """Wait until every remote image is fetchable before PushPlus snapshots it."""
    pending = image_sources(html_content)
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
        unavailable: list[str] = []
        for url in pending:
            try:
                response = requests.get(url, stream=True, timeout=timeout)
                content_type = response.headers.get("Content-Type", "").lower()
                ready = response.ok and content_type.startswith("image/")
                response.close()
            except requests.RequestException:
                ready = False
            if not ready:
                unavailable.append(url)
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
                "PushPlus images are not ready yet (%d remaining, attempt %d/%d)",
                len(pending),
                attempt + 1,
                attempt_count,
            )
            time.sleep(retry_delay)

    raise PushPlusError(
        f"图片尚未同步到 CDN，已取消本次推送（{len(pending)} 张不可访问）"
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
    try:
        data = resp.json()
    except ValueError as e:
        raise PushPlusError(f"PushPlus 返回异常: HTTP {resp.status_code}") from e
    if data.get("code") != 200:
        raise PushPlusError(f"PushPlus 推送失败: {data}")
    logger.info("PushPlus 推送成功（图片通道：%s）", image_provider)
