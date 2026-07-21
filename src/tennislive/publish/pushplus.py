"""PushPlus（pushplus.plus）微信推送：把每日内容推到你自己的微信.

用于「不自动发文，但每天把排版好的内容推到微信里，人工一键转发」的轻量方案。
注册 pushplus 后关注其公众号即可收到消息。

环境变量 / GitHub Secrets：
    PUSHPLUS_TOKEN   pushplus 的 token
"""

from __future__ import annotations

import logging
import os
import time
from html.parser import HTMLParser

import requests

logger = logging.getLogger(__name__)

URL = "https://www.pushplus.plus/send"


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


def wait_for_images(
    html_content: str,
    *,
    attempts: int = 6,
    delay: float = 3.0,
    timeout: int = 15,
) -> None:
    """Wait until every remote image is fetchable before PushPlus snapshots it."""
    pending = image_sources(html_content)
    if not pending:
        return

    for attempt in range(max(1, attempts)):
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
            return
        pending = unavailable
        if attempt + 1 < max(1, attempts):
            time.sleep(max(0.0, delay))

    raise PushPlusError(
        f"图片尚未同步到 CDN，已取消本次推送（{len(pending)} 张不可访问）"
    )


def push(title: str, html_content: str, token: str | None = None, timeout: int = 30) -> None:
    token = token or os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        raise PushPlusError("缺少 PUSHPLUS_TOKEN（请在环境变量或 GitHub Secrets 中配置）")
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
    logger.info("PushPlus 推送成功")
