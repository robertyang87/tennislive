"""把一条新闻链接读成正文纯文本。

**这是「深挖」和「列标题」的分界线。** 原来的两条雷达只拿 RSS 给的
标题、来源、链接——想知道发生了什么就得自己点进去，而那是英文页面、
在微信里点开还得等。要出中文要点，就必须先有正文。

三条是踩出来的：

- **不引第三方解析库**。`requests` 已经在主依赖里，HTML 抽正文这点活
  用标准库正则就够；多一个 `beautifulsoup4` 就多一处「本地装着不等于
  CI 装着」（这个仓库在 playwright / Chromium / cv2 / pyyaml 上栽过四次）。
- **抓不到要出声，而且要说清是哪一条、为什么**。抓不到和「这条没内容」
  长得一模一样——`fetch_article` 因此返回 `(text, note)` 两个值，
  失败时 `text` 为空而 `note` 写着 HTTP 码或异常，让调用方能如实打印。
- **`<p>` 太少就算没读到**。付费墙和同意页都返回 200，正文却只有
  「Subscribe to continue」一句。只看状态码会把它当成读到了。
"""

from __future__ import annotations

import html as _html
import logging
import re

import requests

logger = logging.getLogger(__name__)

# 浏览器 UA。裸 python-requests 的 UA 被不少体育站直接 403——
# 仓库里 ATP 那条「WebFetch 吃 403 时带浏览器 UA 的 urllib 往往能过」
# 说的是同一件事。
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# 整块丢掉的标签：脚本、样式、导航、页脚里的字不是正文，混进去会把
# 「订阅我们的新闻信」当成一条要点喂给模型。
_DROP_BLOCKS = re.compile(
    r"<(script|style|nav|header|footer|aside|form|figure|noscript)\b.*?</\1\s*>",
    re.I | re.S,
)
_PARA = re.compile(r"<p\b[^>]*>(.*?)</p\s*>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# 正文段落的下限。低于它就当没读到——付费墙／Cookie 同意页都返回 200，
# 正文却只有一两句话。
MIN_PARAGRAPHS = 3
# 一条正文最多喂这么多字给模型。整篇长文对「出三五条要点」没有额外价值，
# 而 token 是要花的；截断点取段落边界，别把一句话切一半。
MAX_CHARS = 4000


# Google News RSS 的 `link` 是这个形状的包装页，**正文永远抓不到**：
# 590 KB 全是 JS，真地址一次都没出现在 HTML 里，`CBMi…` 那串 base64 解出来
# 是不含 URL 的服务端令牌。它返回 HTTP 200，抓出来「0 段正文」——和「这家有
# 付费墙」长得一模一样，所以必须**在抓之前就认出来**，否则每条热点都要白花
# 一次请求，还会把真正的原因（源头就读不了）伪装成偶发的抓取失败。
_UNREADABLE_HOSTS = ("news.google.com", "www.google.com/url")


def readable_url(url: str) -> bool:
    """这条链接值不值得去抓正文。"""
    return bool(url) and not any(host in url for host in _UNREADABLE_HOSTS)


def _text_of(fragment: str) -> str:
    """一段 HTML → 纯文本。"""
    return _WS.sub(" ", _html.unescape(_TAG.sub(" ", fragment))).strip()


def extract_paragraphs(markup: str) -> list[str]:
    """HTML → 正文段落列表。

    只认 `<p>`：新闻站的正文段落一律是它，而 `<div>` 里混着导航和推荐位。
    **宁可少抓，不可抓脏**——喂给模型的每一句都会变成要点。
    """
    body = _DROP_BLOCKS.sub(" ", markup or "")
    out: list[str] = []
    for raw in _PARA.findall(body):
        line = _text_of(raw)
        # 一句话短于 40 个字符的多半是图注、署名、栏目名（"Photo: Getty"、
        # "By Reuters"、"Share this"）。正文段落几乎不会这么短。
        if len(line) >= 40:
            out.append(line)
    return out


def clip(paragraphs: list[str], *, max_chars: int = MAX_CHARS) -> str:
    """按段落边界截到 `max_chars` 以内。"""
    kept: list[str] = []
    total = 0
    for para in paragraphs:
        if total + len(para) > max_chars and kept:
            break
        kept.append(para)
        total += len(para)
    return "\n".join(kept)


def fetch_article(
    url: str,
    *,
    timeout: int = 20,
    get=None,
    max_chars: int = MAX_CHARS,
) -> tuple[str, str]:
    """读一条新闻的正文。

    返回 `(正文, 说明)`：**两个都要返回**。只返回正文的话，「抓不到」
    和「这条本来就没内容」在调用方眼里一模一样，而这个仓库里那类
    「兜底出事的时候不吭声」已经栽过太多次。说明在成功时也写
    （读到几段），好让日志能自证它真的读过。
    """
    getter = get or requests.get
    try:
        resp = getter(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "en;q=0.9"},
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001 —— 网络什么都可能抛，抓不到不该中断整轮
        return "", f"取不到（{type(exc).__name__}）"
    status = getattr(resp, "status_code", 0)
    if status != 200:
        return "", f"取不到（HTTP {status}）"
    paragraphs = extract_paragraphs(getattr(resp, "text", "") or "")
    if len(paragraphs) < MIN_PARAGRAPHS:
        # 200 但没有正文：付费墙、同意页、或者这个站的正文不在 <p> 里。
        # 三种都当「没读到」，但要说出段落数，好让人一眼分清是哪一种。
        return "", f"只解出 {len(paragraphs)} 段，当作没读到（付费墙或版式不认）"
    return clip(paragraphs, max_chars=max_chars), f"读到 {len(paragraphs)} 段"
