"""**能读得到正文的**新闻源。

⚠️ 这个模块存在的唯一理由，是一个差点让「深挖」整条功能报废的发现：

`research/trends.py` 走的是 **Google News RSS**（`site:atptour.com/en/news`
这类查询）。它做发现很好——一次覆盖 ATP / WTA / 四大满贯官网加主流媒体——
但它给的 `link` **不是发布方的地址**，而是一个 Google 的包装页：

    https://news.google.com/rss/articles/CBMickFVX3lxTE1n…?oc=5

这个页面 **590 KB 全是 JS**，真地址一次都没出现在 HTML 里（`atptour` 这个
词在整页里搜不到），`CBMi…` 那串 base64 解出来是不含 URL 的服务端令牌。
也就是说：**照着 Google News 的链接去抓正文，永远抓不到**——而它返回
HTTP 200，抓出来是「0 段正文」，看起来和「这家有付费墙」一模一样。

**又一次「写了不等于跑过」**：要不是拿真数据跑了一趟 `tennislive brief`
去看为什么深挖是 0 条，这条功能会带着测试、带着文档合进去，然后一辈子
不工作——和 `_cut_person(source, …)` 那次一模一样。

所以发现和阅读分成两路：

| 用途 | 源 | 给什么 |
|---|---|---|
| **发现 / 热度** | Google News RSS（`trends.py`，没动） | 覆盖广，包括 ATP/WTA 官网；链接读不了 |
| **阅读 / 深挖** | 这里的发布方原生 RSS | 源少，但**链接是真地址，正文抓得到** |

两路的条目一起进聚类：同一件事共享专名，自然会并成一簇，于是那一簇里
既有官网的标题（撑热度），又有一条读得到的链接（供深挖）。

⚠️ **ATP 和 WTA 官方没有能用的 RSS**，探过一轮，别再试：
`atptour.com/en/rss`、`/en/media/rss-feed/xml-feed` 一律 **403**（和
CLAUDE.md 里「ATP 总站对本环境一律 403」是同一件事）；
`wtatennis.com/rss.xml`、`/feed/rss`、`api.wtatennis.com/tennis/news/rss`
一律 **404**。它们仍然通过 Google News 参与热度，只是读不到正文。
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0"

# 2026-08-05 实测通的四家（连同各自第一条的真实链接一起验过）。
# 加新源之前先拿 `tools/probe_news_feeds.py` 跑一遍：**返回 200 不够，
# 还要 item 数 > 0、link 是发布方域名、而且 `fetch_article` 真能解出段落**。
_FEEDS: tuple[tuple[str, str], ...] = (
    ("BBC Sport", "http://feeds.bbci.co.uk/sport/tennis/rss.xml"),
    ("The Guardian", "https://www.theguardian.com/sport/tennis/rss"),
    ("Sky Sports", "https://www.skysports.com/rss/12040"),
    ("Tennis Majors", "https://www.tennismajors.com/feed/"),
)

# 只收这么新的。和 `trends.py` 的官方新闻窗口一致（72 小时）——热点是
# 有保质期的，一周前的稿子混进来只会把簇搅乱。
FRESH_HOURS = 72


def _published(raw: str) -> datetime | None:
    try:
        stamp = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if stamp is None:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def _parse(content: bytes, source: str, now: datetime) -> list[dict]:
    root = ET.fromstring(content)
    out: list[dict] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title", "") or "").strip()
        url = (item.findtext("link", "") or "").strip()
        stamp = _published(item.findtext("pubDate", "") or "")
        if not title or not url:
            continue
        if stamp and now - stamp > timedelta(hours=FRESH_HOURS):
            continue
        out.append(
            {
                "kind": "official-news",
                "source": source,
                "title": title,
                "url": url,
                "published_at": stamp.isoformat() if stamp else "",
                # 这一位就是这个模块的全部意义：**这条链接读得到正文**。
                "readable": True,
            }
        )
    return out


def fetch_readable_news(
    *, timeout: int = 25, get=None, now: datetime | None = None
) -> tuple[list[dict], dict[str, str]]:
    """发布方原生 RSS → 带**真实链接**的新闻条目。

    返回 `(条目, 每家的状态)`。**状态一定要返回**：一家挂了和一家今天没稿
    在结果里长得一模一样，而这个仓库里「空结果先自证是真空」已经栽过太多次。
    """
    getter = get or requests.get
    stamp = now or datetime.now(timezone.utc)
    items: list[dict] = []
    status: dict[str, str] = {}

    def one(source: str, url: str) -> tuple[str, list[dict], str]:
        try:
            resp = getter(url, headers={"User-Agent": _UA}, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            return source, [], f"取不到（{type(exc).__name__}）"
        code = getattr(resp, "status_code", 0)
        if code != 200:
            return source, [], f"HTTP {code}"
        try:
            rows = _parse(getattr(resp, "content", b"") or b"", source, stamp)
        except ET.ParseError as exc:
            return source, [], f"解析失败（{exc}）"
        return source, rows, f"正常 · {len(rows)} 条"

    with ThreadPoolExecutor(max_workers=len(_FEEDS)) as pool:
        futures = [pool.submit(one, label, url) for label, url in _FEEDS]
        for future in as_completed(futures):
            source, rows, detail = future.result()
            items.extend(rows)
            status[source] = detail
    items.sort(key=lambda row: str(row.get("published_at") or ""), reverse=True)
    return items, status
