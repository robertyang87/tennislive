"""数据源抽象基类与 HTTP 工具."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..models import Match

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def make_session(extra_headers: dict[str, str] | None = None) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }
    )
    if extra_headers:
        session.headers.update(extra_headers)
    return session


class SourceError(Exception):
    """数据源抓取失败（网络错误、被封、结构变化等）."""


class TennisSource(ABC):
    """数据源接口：给定北京时间的一天，返回该天的所有 ATP/WTA 比赛."""

    name: str = "base"

    @abstractmethod
    def fetch_day(self, d: date) -> list[Match]:
        """抓取北京时间日期 d 当天的全部比赛（按比赛开始时间的北京日期归属）.

        失败时抛出 SourceError。
        """
        raise NotImplementedError
