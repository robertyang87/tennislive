"""PushPlus（pushplus.plus）微信推送：把每日内容推到你自己的微信.

用于「不自动发文，但每天把排版好的内容推到微信里，人工一键转发」的轻量方案。
注册 pushplus 后关注其公众号即可收到消息。

环境变量 / GitHub Secrets：
    PUSHPLUS_TOKEN   pushplus 的 token
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

URL = "https://www.pushplus.plus/send"


class PushPlusError(RuntimeError):
    pass


def push(title: str, html_content: str, token: str | None = None, timeout: int = 30) -> None:
    token = token or os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        raise PushPlusError("缺少 PUSHPLUS_TOKEN（请在环境变量或 GitHub Secrets 中配置）")
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
