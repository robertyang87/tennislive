"""Multi-source, license-aware visual discovery for knowledge cards."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from PIL import Image

from ..models import Match
from ..render.tournament_story import TournamentStory
from ..video.official import (
    ATP_YOUTUBE_CHANNEL_ID,
    ATP_YOUTUBE_FEED,
    parse_official_youtube_feed_entries,
)
from ..video.pipeline import VideoPipelineError
from .visual_quality import assess_cover_image, classify_cover_scene


_UA = "tennislive/1.0 visual-research (github.com/robertyang87/tennislive)"
_LICENSES = {"cc0", "pdm", "by", "by-sa", "cc-by", "cc-by-sa"}
_PAGES = ("story", "explainer", "today")
_NEGATIVE_PERSON_TERMS = {
    "scoreboard", "results", "bracket", "stadium", "arena",
    "ball", "logo", "poster", "ticket", "building", "map",
}
_WATERMARK_LIBRARY_TERMS = {
    "gettyimages", "getty images", "alamy", "shutterstock", "dreamstime",
    "depositphotos", "istockphoto", "123rf",
}
_BEIJING = ZoneInfo("Asia/Shanghai")
_ATP_MATCH_VIDEO_TERMS = (
    "highlights",
    "hot shot",
    "shot of the day",
    "point of the day",
    "point of the match",
    "rally of the day",
    "rally of the match",
    "best point",
    "match point",
)
_ATP_NON_MATCH_VIDEO_TERMS = (
    "interview",
    "press conference",
    "practice",
    "training",
    "top 10",
    "best of",
    "podcast",
    "preview",
)
_CURATED_VISUALS: dict[tuple[str, str], tuple[dict, ...]] = {
    ("golden-slam", "cover"): (
        {
            "provider": "official-editorial",
            "source_url": "https://www.olympics.com/en/news/tennis-golden-slam-steffi-graf-1988-olympics-gold",
            "image_url": "https://img.olympics.com/images/image/private/t_s_w960/f_auto/primary/vhe08w1mvtsdgzaumrl9",
            "credit": "Olympics.com",
            "license": "公开网页图片 · 非商业资讯引用",
            "width": 960,
            "height": 1440,
            "relevance": 99,
            "search_text": "steffi graf 1988 seoul olympic gold medal tennis champion",
            "image_text": "steffi graf 1988 seoul olympic gold medal tennis champion",
        },
    ),
    ("golden-slam", "story"): (
        {
            "provider": "verified-editorial",
            "source_url": (
                "https://www.lavanguardia.com/deportes/tenis/20190908/"
                "47220597858/historias-del-us-open-rod-laver-us-open-grand-slam.html"
            ),
            "image_url": (
                "https://www.lavanguardia.com/files/original/uploads/2019/09/07/"
                "5fa53698b51d8.jpeg"
            ),
            "credit": "La Vanguardia archive",
            "license": "公开网页图片 · 非商业资讯引用",
            "width": 3000,
            "height": 1726,
            "relevance": 100,
            "search_text": "rod laver 1969 us open forest hills grand slam champion",
            "image_text": "rod laver lifts 1969 us open trophy at forest hills",
        },
    ),
    ("golden-slam", "explainer"): (
        {
            "provider": "verified-editorial",
            "source_url": "https://time.com/4026998/grand-slam-winners/",
            "image_url": (
                "https://gcp-na-images.contentstack.com/v3/assets/"
                "bltea6093859af6183b/bltdf817390a4baa91e/"
                "698862c23c1639329f459a2e/150909-grand-slam-winners-09.jpg"
                "?branch=production"
            ),
            "credit": "TIME archive",
            "license": "公开网页图片 · 非商业资讯引用",
            "width": 2560,
            "height": 1710,
            "relevance": 100,
            "search_text": "steffi graf 1988 us open final grand slam sabatini",
            "image_text": "steffi graf 1988 us open final against gabriela sabatini",
        },
    ),
    ("golden-slam", "today"): (
        {
            "provider": "editorial-archive",
            "source_url": "https://www.tennismagazin.de/news/steffi-graf-golden-slam-seoul-olympia-1988/",
            "image_url": "https://www.tennismagazin.de/content/uploads/2018/09/graff-1024x683.jpg",
            "credit": "tennis MAGAZIN",
            "license": "公开网页图片 · 非商业资讯引用",
            "width": 1024,
            "height": 683,
            "relevance": 99,
            "search_text": "steffi graf 1988 seoul olympic final medal tennis",
            "image_text": "steffi graf 1988 seoul olympic final medal tennis",
        },
    ),
}
_VISUAL_BRIEFS: dict[str, dict[str, tuple[str, tuple[str, ...], tuple[str, ...], bool]]] = {
    # page: (person/subject, exact years, event/location anchors, person required)
    "hawkeye": {
        "cover": ("Hawk Eye", (), ("wimbledon",), False),
        "story": ("Hawk Eye", ("2004",), (), False),
        "explainer": ("Hawk Eye", (), (), False),
        "today": ("electronic line calling", ("2025",), ("wimbledon",), False),
    },
    "golden-slam": {
        "cover": ("Steffi Graf", ("1988",), ("seoul", "olympic"), True),
        "story": ("Rod Laver", ("1969",), ("grand slam", "us open"), True),
        "explainer": ("Steffi Graf", ("1988",), ("grand slam",), True),
        "today": ("Steffi Graf", ("1988",), ("seoul", "olympic"), True),
    },
    "surfaces": {
        "cover": ("center court", (), ("clay",), False),
        "story": ("Australian Open", ("1988",), ("melbourne", "australian open"), False),
        "explainer": ("Rafael Nadal", ("2005",), ("roland garros", "french open"), True),
        "today": ("Rafael Nadal", (), ("roland garros", "french open"), True),
    },
    "big-three": {
        "cover": ("Federer Nadal Djokovic", (), ("tennis",), True),
        "story": ("Federer Nadal", ("2008",), ("wimbledon",), True),
        "explainer": ("Djokovic Nadal", ("2012",), ("australian open", "melbourne"), True),
        "today": ("Federer Nadal Djokovic", (), ("grand slam", "tennis"), True),
    },
    "china-tennis": {
        "cover": ("Li Na", ("2011",), ("roland garros", "french open"), True),
        "story": ("Li Na", ("2011",), ("roland garros", "french open"), True),
        "explainer": ("Wu Yibing", ("2023",), ("dallas",), True),
        "today": ("Zheng Qinwen", ("2024",), ("paris", "olympic"), True),
    },
}
_EVENT_ALIASES = (
    (("us_open", "us-open", "usopen"), ("us open", "flushing meadows")),
    (("french_open", "french-open", "roland_garros", "roland-garros"), ("french open", "roland garros")),
    (("wimbledon",), ("wimbledon",)),
    (("australian_open", "australian-open"), ("australian open", "melbourne")),
    (("olympic", "paris_2024", "paris-2024"), ("olympic", "paris 2024")),
)


@dataclass(frozen=True)
class ResolvedVisual:
    page: str
    path: Path
    provider: str
    source_url: str
    image_url: str
    credit: str
    license: str
    query: str
    relevance: int
    sha256: str
    focus: str = "50% 42%"
    subject_match: bool = False
    year_match: bool = False
    event_match: bool = False
    person_required: bool = False


def _subject(story: TournamentStory) -> str:
    for alias in story.aliases:
        if re.search(r"[a-z]", alias, re.I):
            return alias
    latin = re.sub(r"[^a-z0-9 -]", " ", story.slug, flags=re.I).strip()
    return latin or story.title


def _event_anchors(source_url: str) -> tuple[str, ...]:
    path = unquote(urlparse(source_url).path).lower()
    for needles, anchors in _EVENT_ALIASES:
        if any(needle in path for needle in needles):
            return anchors
    return ()


def _page_anchors(story: TournamentStory) -> dict[str, tuple[str, ...]]:
    if story.kind != "player" or not story.moments:
        return {}
    return {
        "story": _event_anchors(story.moments[0].source_url),
        "today": _event_anchors(story.moments[-1].source_url),
    }


def _briefs(story: TournamentStory) -> dict[str, tuple[str, tuple[str, ...], tuple[str, ...], bool]]:
    if story.slug in _VISUAL_BRIEFS:
        return _VISUAL_BRIEFS[story.slug]
    subject = _subject(story)
    years = tuple(moment.date[:4] for moment in story.moments)
    person_required = story.kind == "player"
    result: dict[str, tuple[str, tuple[str, ...], tuple[str, ...], bool]] = {
        "cover": (subject, years[:1], (), person_required),
    }
    for index, page in enumerate(_PAGES):
        moment = story.moments[min(index, len(story.moments) - 1)] if story.moments else None
        page_years = (moment.date[:4],) if moment else ()
        event_terms = _event_anchors(moment.source_url) if moment else ()
        result[page] = (subject, page_years, event_terms, person_required)
    return result


def _queries(story: TournamentStory) -> dict[str, str]:
    briefs = _briefs(story)
    queries: dict[str, str] = {}
    for page in ("cover", *_PAGES):
        subject, years, event_terms, _person_required = briefs[page]
        context = (
            story.surface,
            story.location.split("·", 1)[0].strip(),
        ) if page == "explainer" and not event_terms else ()
        queries[page] = " ".join(
            filter(None, (subject, *years, event_terms[0] if event_terms else "", *context, "tennis"))
        )
    return queries


def _tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", query.lower())
        if token not in {"tennis", "open", "tour", "atp", "wta"}
    }


def _relevance(query: str, text: str) -> int:
    haystack = text.lower()
    tokens = _tokens(query)
    score = sum(3 for token in tokens if token in haystack)
    years = re.findall(r"\b(?:19|20)\d{2}\b", query)
    score += sum(2 for year in years if year in haystack)
    return score


def _candidate_matches(
    candidate: dict,
    brief: tuple[str, tuple[str, ...], tuple[str, ...], bool],
) -> tuple[bool, bool, bool, bool]:
    subject, years, event_terms, person_required = brief
    text = str(candidate.get("search_text", "")).lower()
    image_text = str(candidate.get("image_text", "") or text).lower()
    subject_tokens = _tokens(subject)
    subject_match = bool(subject_tokens) and all(token in image_text for token in subject_tokens)
    year_match = not years or any(year in text for year in years)
    event_match = not event_terms or any(term in text for term in event_terms)
    negative_visual = any(term in image_text for term in _NEGATIVE_PERSON_TERMS)
    person_match = not person_required or (subject_match and not negative_visual)
    return subject_match, year_match, event_match, person_match


def _official_references(story: TournamentStory, session: requests.Session) -> list[dict]:
    urls = list(dict.fromkeys(
        [story.source_url, *story.evidence_urls, *(m.source_url for m in story.moments)]
    ))
    found: list[dict] = []
    for url in urls[:8]:
        try:
            response = session.get(url, timeout=7)
            response.raise_for_status()
            match = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                response.text,
                re.I,
            ) or re.search(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
                response.text,
                re.I,
            )
            title_match = re.search(r'<title[^>]*>(.*?)</title>', response.text, re.I | re.S)
            description_match = re.search(
                r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)',
                response.text,
                re.I,
            )
            alt_match = re.search(
                r'<meta[^>]+property=["\']og:image:alt["\'][^>]+content=["\']([^"\']+)',
                response.text,
                re.I,
            )
            image_url = match.group(1) if match else ""
            title = re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "")
            description = re.sub(
                r"<[^>]+>", " ", description_match.group(1) if description_match else ""
            )
            alt = re.sub(r"<[^>]+>", " ", alt_match.group(1) if alt_match else "")
            domain = urlparse(url).netloc.removeprefix("www.")
            found.append(
                {
                    "provider": "official-media",
                    "page_url": url,
                    "source_url": url,
                    "image_url": image_url,
                    "credit": domain,
                    "license": "官方媒体 · 非商业资讯引用",
                    "status": "candidate" if image_url else "reference-only",
                    "reason": "官方页面用于事实与事件核验；图片保留机构署名",
                    "search_text": " ".join((title, description, url)).lower(),
                    "image_text": " ".join((alt, image_url)).lower(),
                    "width": 0,
                    "height": 0,
                }
            )
        except requests.RequestException as exc:
            found.append(
                {"provider": "official-page", "page_url": url, "status": "error", "reason": str(exc)[:180]}
            )
    return found


def _commons_candidates(query: str, session: requests.Session) -> list[dict]:
    params = {
        "action": "query",
        "generator": "search",
        # Namespace 6 already limits results to files.  ``filetype:bitmap`` is
        # not a supported Commons search operator and used to make many valid
        # athlete searches return an empty result set.
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 12,
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": 1800,
        "format": "json",
        "formatversion": 2,
    }
    try:
        response = session.get("https://commons.wikimedia.org/w/api.php", params=params, timeout=12)
        response.raise_for_status()
    except requests.RequestException:
        return []
    candidates: list[dict] = []
    for page in response.json().get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        license_code = (meta.get("LicenseShortName") or {}).get("value", "").lower()
        if not any(code in license_code for code in ("cc", "public domain")):
            continue
        text = " ".join(
            (
                page.get("title", ""),
                (meta.get("ImageDescription") or {}).get("value", ""),
                (meta.get("Categories") or {}).get("value", ""),
            )
        )
        candidates.append(
            {
                "provider": "wikimedia-commons",
                "source_url": info.get("descriptionurl", ""),
                "image_url": info.get("thumburl") or info.get("url", ""),
                "credit": (meta.get("Artist") or {}).get("value", "Wikimedia Commons"),
                "license": license_code,
                "width": info.get("thumbwidth") or info.get("width") or 0,
                "height": info.get("thumbheight") or info.get("height") or 0,
                "relevance": _relevance(query, text),
                "search_text": re.sub(r"<[^>]+>", " ", text).lower(),
                # Person validation must use what the image itself is called,
                # not a description that may merely mention the athlete.
                "image_text": " ".join((page.get("title", ""), info.get("url", ""))).lower(),
            }
        )
    return candidates


def _bing_candidates(query: str, session: requests.Session) -> list[dict]:
    """Return public web-image results as a last-resort editorial source.

    Official pages, Commons and Openverse remain preferred.  Bing is useful for
    historical event photographs whose page metadata is too sparse for the
    media-library APIs.  Every result retains its source page and is subjected
    to the same person/year/event relevance checks as the other providers.
    """
    try:
        response = session.get(
            "https://www.bing.com/images/search",
            params={"q": query, "form": "HDRSC2", "first": 1},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []
    candidates: list[dict] = []
    for tag in re.findall(r"<a\b[^>]*\biusc\b[^>]*>", response.text, re.I):
        match = re.search(r'\bm=["\']([^"\']+)["\']', tag, re.I)
        if not match:
            continue
        try:
            item = json.loads(html.unescape(match.group(1)))
        except (TypeError, ValueError):
            continue
        image_url = str(item.get("murl") or "").strip()
        source_url = str(item.get("purl") or "").strip()
        title = str(item.get("t") or item.get("desc") or "").strip()
        if not image_url.startswith("http") or not source_url.startswith("https://"):
            continue
        domain = urlparse(source_url).netloc.removeprefix("www.")
        text = " ".join((title, source_url, image_url)).lower()
        candidates.append(
            {
                "provider": "bing-web-image",
                "source_url": source_url,
                "image_url": image_url,
                "credit": domain or "Public web source",
                "license": "公开网页图片 · 非商业资讯引用",
                "width": int(item.get("ow") or 0),
                "height": int(item.get("oh") or 0),
                "relevance": _relevance(query, text),
                "search_text": text,
                "image_text": text,
            }
        )
    return candidates


def _query_variants(
    brief: tuple[str, tuple[str, ...], tuple[str, ...], bool],
    exact_query: str,
) -> tuple[str, ...]:
    """Search the precise scene first, then broaden only to the exact subject."""
    subject, years, event_terms, _person_required = brief
    variants = [exact_query]
    if years:
        variants.append(" ".join(filter(None, (subject, years[0], "tennis"))))
    if event_terms:
        variants.append(" ".join(filter(None, (subject, event_terms[0], "tennis"))))
    variants.append(" ".join(filter(None, (subject, "tennis"))))
    return tuple(dict.fromkeys(variants))


def _openverse_candidates(query: str, session: requests.Session) -> list[dict]:
    try:
        response = session.get(
            "https://api.openverse.org/v1/images/",
            params={"q": query, "page_size": 12, "mature": "false"},
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []
    candidates: list[dict] = []
    for item in response.json().get("results", []):
        license_code = str(item.get("license", "")).lower()
        if license_code not in _LICENSES:
            continue
        tags = item.get("tags") or []
        tag_text = " ".join(
            str(tag.get("name", "")) if isinstance(tag, dict) else str(tag)
            for tag in tags
        )
        text = " ".join((str(item.get("title", "")), tag_text))
        candidates.append(
            {
                "provider": "openverse",
                "source_url": item.get("foreign_landing_url") or item.get("detail_url") or "",
                "image_url": item.get("thumbnail") or item.get("url") or "",
                "credit": item.get("creator") or item.get("source") or "Openverse",
                "license": license_code,
                "width": item.get("width") or 0,
                "height": item.get("height") or 0,
                "relevance": _relevance(query, text),
                "search_text": text.lower(),
                "image_text": " ".join(
                    (str(item.get("title", "")), str(item.get("url", "")))
                ).lower(),
            }
        )
    return candidates


def _download(candidate: dict, page: str, query: str, folder: Path, session: requests.Session) -> ResolvedVisual | None:
    url = candidate.get("image_url", "")
    source_url = str(candidate.get("source_url", "")).strip()
    credit = re.sub(r"<[^>]+>", "", str(candidate.get("credit", ""))).strip()
    license_name = str(candidate.get("license", "")).strip()
    if not url or not source_url.startswith("https://") or not credit or not license_name:
        return None
    try:
        response = session.get(url, timeout=18)
        response.raise_for_status()
    except requests.RequestException:
        return None
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    digest = hashlib.sha256(response.content).hexdigest()
    path = folder / f"{page}-{digest[:12]}{suffix}"
    path.write_bytes(response.content)
    try:
        with Image.open(path) as image:
            if image.width < 900 or image.height < 540:
                path.unlink(missing_ok=True)
                return None
    except OSError:
        path.unlink(missing_ok=True)
        return None
    return ResolvedVisual(
        page=page,
        path=path,
        provider=candidate["provider"],
        source_url=source_url,
        image_url=url,
        credit=credit,
        license=license_name,
        query=query,
        relevance=int(candidate["relevance"]),
        sha256=digest,
    )


def _cover_audit(story: TournamentStory) -> dict:
    brief = _briefs(story).get("cover", ("", (), (), False))
    title = story.image.name
    credits_file = story.image.parent / "credits.json"
    try:
        credits = __import__("json").loads(credits_file.read_text(encoding="utf-8"))
        title = str((credits.get(story.image.name) or {}).get("title") or title)
    except (OSError, ValueError):
        pass
    candidate = {"search_text": " ".join((title, story.image_credit, story.image_source_url)).lower()}
    subject_match, year_match, event_match, person_match = _candidate_matches(candidate, brief)
    subject, years, event_terms, person_required = brief
    passed = bool(story.image.is_file() and story.image_source_url.startswith("https://"))
    if story.slug in _VISUAL_BRIEFS:
        passed = passed and subject_match and year_match and event_match
    if person_required:
        passed = passed and person_match and year_match and event_match
    return {
        "page": "cover",
        "status": "selected" if passed else "rejected",
        "cached_file": story.image.name,
        "title": title,
        "subject": subject,
        "required_years": list(years),
        "required_event_terms": list(event_terms),
        "person_required": person_required,
        "subject_match": subject_match,
        "year_match": year_match,
        "event_match": event_match,
        "person_match": person_match,
        "reason": "" if passed else "封面未同时满足人物、年份、事件/地点和授权来源要求",
    }


def resolve_story_visuals(story: TournamentStory, folder: Path) -> tuple[dict[str, ResolvedVisual], dict]:
    """Try multiple sources, keep exact licensed images, and audit every fallback."""
    enabled = os.environ.get("TENNISLIVE_VISUAL_FETCH", "off").lower() in {"1", "on", "true"}
    strict = os.environ.get("TENNISLIVE_VISUAL_STRICT", "off").lower() in {"1", "on", "true"}
    folder.mkdir(parents=True, exist_ok=True)
    cover_audit = _cover_audit(story)
    # Rule stories use three distinct, topic-specific deterministic diagrams
    # around one verified cover photo. They do not need weakly matched filler
    # photos merely to increase the photo count.
    required_pages = set() if story.diagram_type else set(_PAGES)
    if cover_audit["status"] != "selected":
        required_pages.add("cover")
    fact_domains = sorted(
        {
            urlparse(url).netloc.removeprefix("www.")
            for url in (story.source_url, *story.evidence_urls, *(m.source_url for m in story.moments))
            if str(url).startswith("https://")
        }
    )
    primary_domains = [
        domain
        for domain in fact_domains
        if not any(name in domain for name in ("wikipedia.org", "wikimedia.org", "openverse.org"))
    ]
    preflight_errors: list[str] = []
    if len(fact_domains) < 2:
        preflight_errors.append("事实输入源少于 2 个独立域名")
    if not primary_domains:
        preflight_errors.append("事实输入缺少赛事、巡回赛、协会或档案馆的一手来源")
    if strict and preflight_errors:
        return {}, {
            "schema_version": 1,
            "status": "fail",
            "story_slug": story.slug,
            "fetch_enabled": enabled,
            "strict": strict,
            "policy": "封面先检；通过后才联网检索内页，候选不足自动换题",
            "selected_count": 0,
            "required_pages": sorted(required_pages),
            "missing_pages": sorted(required_pages),
            "input_domains": fact_domains,
            "primary_domains": primary_domains,
            "providers_queried": [],
            "selected_providers": [],
            "errors": preflight_errors,
            "attempts": [cover_audit],
        }
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    official_references = _official_references(story, session) if enabled else []
    attempts = [dict(reference) for reference in official_references]
    attempts.append(cover_audit)
    selected: dict[str, ResolvedVisual] = {}
    anchors_by_page = _page_anchors(story)
    used_sources = {story.image_source_url}
    used_hashes: set[str] = set()
    if story.image.is_file():
        used_hashes.add(hashlib.sha256(story.image.read_bytes()).hexdigest())
    briefs = _briefs(story)
    for page, query in _queries(story).items():
        required_anchors = anchors_by_page.get(page, ())
        if page == "cover" and cover_audit["status"] == "selected":
            continue
        if story.diagram_type and page != "cover":
            attempts.append(
                {
                    "page": page,
                    "status": "topic-specific-diagram",
                    "reason": "规则主题使用逐页专用示意图，不用弱相关照片填充",
                    "query": query,
                }
            )
            continue
        if not enabled:
            attempts.append(
                {"page": page, "status": "generated-visual", "reason": "规则示意图或联网检索未启用", "query": query}
            )
            continue
        official_candidates = []
        for reference in official_references:
            if reference.get("status") != "candidate":
                continue
            candidate = dict(reference)
            candidate["relevance"] = _relevance(query, candidate.get("search_text", ""))
            official_candidates.append(candidate)
        variants = _query_variants(briefs[page], query)
        fetched: dict[str, list[dict]] = {
            "wikimedia-commons": [],
            "openverse": [],
            "bing-web-image": [],
        }
        curated = list(_CURATED_VISUALS.get((story.slug, page), ()))
        if not curated:
            fetches = []
            with ThreadPoolExecutor(max_workers=min(10, len(variants) * 3)) as pool:
                for variant in variants:
                    fetches.extend(
                        (
                            ("wikimedia-commons", pool.submit(_commons_candidates, variant, session)),
                            ("openverse", pool.submit(_openverse_candidates, variant, session)),
                            ("bing-web-image", pool.submit(_bing_candidates, variant, session)),
                        )
                    )
            for provider, future in fetches:
                try:
                    fetched[provider].extend(future.result())
                except Exception:  # noqa: BLE001 - one media index must not stop the fallback chain
                    continue
        providers = (
            ("curated-editorial", curated),
            ("official-media", official_candidates),
            ("wikimedia-commons", fetched["wikimedia-commons"]),
            ("openverse", fetched["openverse"]),
            ("bing-web-image", fetched["bing-web-image"]),
        )
        candidates = [candidate for _provider, items in providers for candidate in items]
        def _layout_score(item: dict) -> int:
            width = int(item.get("width") or 0)
            height = int(item.get("height") or 0)
            if not width or not height:
                return 0
            return int(height >= width) if page == "cover" else int(width >= height)

        candidates.sort(
            key=lambda item: (_layout_score(item), item["relevance"], item.get("width", 0)),
            reverse=True,
        )
        chosen = None
        exact_candidates: list[tuple[dict, tuple[bool, bool, bool, bool], str]] = []
        archive_candidates: list[tuple[dict, tuple[bool, bool, bool, bool], str]] = []
        seen_candidates: set[tuple[str, str]] = set()
        for candidate in candidates:
            key = (str(candidate.get("source_url", "")), str(candidate.get("image_url", "")))
            if key in seen_candidates:
                continue
            seen_candidates.add(key)
            if candidate["source_url"] in used_sources or candidate["relevance"] < 3:
                continue
            candidate_text = " ".join(
                (
                    str(candidate.get("source_url", "")),
                    str(candidate.get("image_url", "")),
                    str(candidate.get("image_text", "")),
                )
            ).lower()
            if any(term in candidate_text for term in _WATERMARK_LIBRARY_TERMS):
                continue
            matches = _candidate_matches(candidate, briefs[page])
            subject_match, year_match, event_match, person_match = matches
            if not (subject_match and person_match):
                continue
            if page == "cover" and briefs[page][3]:
                image_text = str(candidate.get("image_text", "")).lower()
                scene_terms = (
                    "serve", "forehand", "backhand", "playing", "match", "court",
                    "final", "champion", "trophy", "medal", "olympic", "slam",
                    "interview", "press conference", "celebrat",
                )
                if not any(term in image_text for term in scene_terms):
                    continue
            anchor_match = not required_anchors or any(
                anchor in candidate.get("search_text", "") for anchor in required_anchors
            )
            row = (candidate, matches, "exact-event" if year_match and event_match and anchor_match else "subject-archive")
            (exact_candidates if row[2] == "exact-event" else archive_candidates).append(row)
        eligible_candidates = (
            exact_candidates
            if strict
            else [*exact_candidates, *archive_candidates]
        )
        for candidate, matches, match_level in eligible_candidates:
            subject_match, year_match, event_match, person_match = matches
            downloaded = _download(candidate, page, query, folder, session)
            if downloaded and downloaded.sha256 in used_hashes:
                downloaded.path.unlink(missing_ok=True)
                continue
            if downloaded:
                focus = (
                    "50% 22%"
                    if page == "cover" and briefs[page][3]
                    else "50% 24%" if briefs[page][3] else "50% 38%"
                )
                chosen = replace(
                    downloaded,
                    focus=focus,
                    subject_match=subject_match,
                    year_match=year_match,
                    event_match=event_match,
                    person_required=briefs[page][3],
                )
                candidate["match_level"] = match_level
                break
        if chosen:
            selected[page] = chosen
            used_sources.add(chosen.source_url)
            used_hashes.add(chosen.sha256)
            selected_record = asdict(chosen)
            selected_record.pop("path", None)
            selected_record["cached_file"] = chosen.path.name
            attempts.append(
                {
                    "page": page,
                    "status": "selected",
                    "required_event_terms": list(required_anchors),
                    "match_level": candidate.get("match_level", "exact-event"),
                    **selected_record,
                }
            )
        else:
            attempts.append(
                {
                    "page": page,
                    "status": "generated-visual",
                    "reason": "多源检索后无授权、分辨率和相关性同时达标的照片",
                    "query": query,
                    "required_event_terms": list(required_anchors),
                    "providers": [name for name, _items in providers],
                }
            )
    missing_pages = sorted(required_pages - set(selected))
    status = "pass"
    errors: list[str] = []
    if strict and missing_pages:
        if "cover" in missing_pages:
            errors.append("封面缺少通过人物与场景核验的照片")
        inner_missing = [page for page in missing_pages if page != "cover"]
        if inner_missing:
            errors.append("缺少通过精确核验的页面照片：" + "、".join(inner_missing))
    input_urls = [
        story.source_url,
        *story.evidence_urls,
        *(moment.source_url for moment in story.moments),
        *(visual.source_url for visual in selected.values()),
    ]
    input_domains = sorted(
        {
            urlparse(url).netloc.removeprefix("www.")
            for url in input_urls
            if str(url).startswith("https://")
        }
    )
    if strict and len(input_domains) < 2:
        errors.append("事实与图片输入源少于 2 个独立域名")
    if errors:
        status = "fail"
    return selected, {
        "schema_version": 1,
        "status": status,
        "story_slug": story.slug,
        "fetch_enabled": enabled,
        "strict": strict,
        "policy": "官方页面核对事件；Commons/Openverse 多源检索；逐页同时校验人物、年份、赛事/地点、授权、分辨率与唯一性；不足则换题",
        "selected_count": len(selected),
        "required_pages": sorted(required_pages),
        "missing_pages": missing_pages,
        "input_domains": input_domains,
        "providers_queried": (
            []
            if story.diagram_type or not enabled
            else ["curated-editorial", "official-media", "wikimedia-commons", "openverse", "bing-web-image"]
        ),
        "selected_providers": sorted({visual.provider for visual in selected.values()}),
        "errors": errors,
        "attempts": attempts,
    }


def _legacy_resolve_match_cover_visual(
    match: Match,
    folder: Path,
) -> tuple[ResolvedVisual | None, dict]:
    """Resolve an exact-player tennis photo for the daily poster cover.

    This is deliberately deterministic and uses public media indexes available
    to GitHub Actions. It never generates an image and never accepts a generic
    court, logo, scoreboard, or another player as an athlete cover.
    """
    enabled = os.environ.get("TENNISLIVE_COVER_VISUAL_FETCH", "off").lower() in {
        "1", "on", "true",
    }
    folder.mkdir(parents=True, exist_ok=True)
    players = list(match.winner_players() or [])
    for player in match.home + match.away:
        if player not in players:
            players.append(player)
    players = sorted(
        players,
        key=lambda player: (
            player.country == "CHN",
            player.seed is not None,
            -(player.rank or 9999),
        ),
        reverse=True,
    )[:3]
    attempts: list[dict] = []
    report = {
        "schema_version": 1,
        "status": "unavailable",
        "match_id": match.match_id,
        "policy": "仅接受与头条球员姓名精确匹配的赛场人物照片；Commons 与 Openverse 交叉补充；不生成 AI 图片",
        "fetch_enabled": enabled,
        "providers_queried": [],
        "attempts": attempts,
    }
    if not enabled:
        report["status"] = "disabled"
        return None, report

    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    action_terms = (
        "serve", "serving", "forehand", "backhand", "playing", "match",
        "court", "tennis player", "tournament",
    )
    for player in players:
        query = f"{player.name} tennis player"
        brief = (player.name, (), (), True)
        provider_loaders = (
            ("wikimedia-commons", _commons_candidates),
            ("openverse", _openverse_candidates),
        )
        for provider, loader in provider_loaders:
            candidates = loader(query, session)
            if provider not in report["providers_queried"]:
                report["providers_queried"].append(provider)
            candidates.sort(
                key=lambda item: (
                    any(term in str(item.get("search_text", "")).lower() for term in action_terms),
                    item.get("relevance", 0),
                    min(int(item.get("width", 0)), int(item.get("height", 0))),
                ),
                reverse=True,
            )
            for candidate in candidates[:8]:
                subject_match, _year_match, _event_match, person_match = _candidate_matches(
                    candidate, brief
                )
                record = {
                    "player": player.name,
                    "provider": provider,
                    "source_url": candidate.get("source_url", ""),
                    "subject_match": subject_match,
                    "person_match": person_match,
                    "relevance": candidate.get("relevance", 0),
                }
                if not (subject_match and person_match):
                    record["status"] = "rejected"
                    record["reason"] = "图片标题或说明未精确命中头条球员"
                    attempts.append(record)
                    continue
                downloaded = _download(candidate, "daily-cover", query, folder, session)
                if downloaded is None:
                    record["status"] = "rejected"
                    record["reason"] = "图片下载失败或分辨率不足 900x540"
                    attempts.append(record)
                    continue
                visual = replace(
                    downloaded,
                    focus="50% 24%",
                    subject_match=True,
                    person_required=True,
                )
                record.update(
                    {
                        "status": "selected",
                        "credit": visual.credit,
                        "license": visual.license,
                        "cached_file": visual.path.name,
                    }
                )
                attempts.append(record)
                report.update(
                    {
                        "status": "selected",
                        "player": player.name,
                        "provider": provider,
                        "source_url": visual.source_url,
                        "credit": visual.credit,
                        "license": visual.license,
                    }
                )
                return visual, report
    return None, report


def _daily_cover_players(match: Match) -> list:
    """Rank only participants from the lead match, keeping the China angle."""
    winners = list(match.winner_players() or [])
    players = list(match.home + match.away)
    players.sort(
        key=lambda player: (
            player.country == "CHN",
            player in winners,
            player.seed is not None,
            -(player.rank or 9999),
        ),
        reverse=True,
    )
    return players[:3]


def _daily_cover_queries(match: Match, player_name: str) -> tuple[str, ...]:
    event = match.tournament.name
    year = str(match.start_utc.year) if match.start_utc is not None else ""
    opponents = " ".join(
        player.name for player in match.home + match.away if player.name != player_name
    )
    return tuple(
        dict.fromkeys(
            (
                " ".join(
                    filter(
                        None,
                        (player_name, opponents, event, year, "tennis match photo"),
                    )
                ),
                " ".join(
                    filter(
                        None,
                        (
                            player_name,
                            opponents,
                            event,
                            "tennis forehand backhand serving in action",
                        ),
                    )
                ),
            )
        )
    )


def _daily_cover_text(candidate: dict) -> str:
    return " ".join(
        str(candidate.get(key, ""))
        for key in (
            "search_text",
            "image_text",
            "title",
            "alt",
            "caption",
            "source_title",
            "source_description",
            "source_url",
            "image_url",
        )
    ).lower()


def _daily_cover_visual_descriptor(candidate: dict) -> str:
    """Text that describes pixels, excluding URLs and broad article context."""
    return " ".join(
        str(candidate.get(key, ""))
        for key in ("image_text", "alt", "caption", "title", "source_title")
    ).lower()


def _identity_words(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _contains_identity_phrase(text: str, words: tuple[str, ...]) -> bool:
    if not words:
        return False
    normalized = " ".join(_identity_words(text))
    phrase = " ".join(words)
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", normalized))


def _player_name_matches(
    name: str,
    text: str,
    *,
    surname_aliases: tuple[str, ...] | None = None,
) -> bool:
    """Match a full name or an explicit surname at token boundaries.

    A shared given name is never sufficient evidence.  Callers that know the
    full match field can pass only aliases unique to that participant.
    """
    words = _identity_words(name)
    if not words:
        return False
    if _contains_identity_phrase(text, words):
        return True
    aliases = surname_aliases if surname_aliases is not None else (words[-1],)
    return any(
        len(alias) >= 3 and _contains_identity_phrase(text, (alias,))
        for alias in aliases
    )


def _player_identity_aliases(player, participants: list) -> tuple[str, ...]:
    """Return surname/display-surname aliases unique within this match."""
    words = _identity_words(player.name)
    if not words:
        return ()
    aliases = [words[-1]]
    # Official Asian-tour copy commonly uses family-name-first display while
    # normalized feeds may store the same player as given-name first.
    if str(player.country or "").upper() in {"CHN", "HKG", "TPE", "JPN", "KOR"}:
        aliases.append(words[0])
    other_words = {
        token
        for other in participants
        if other is not player
        for token in _identity_words(other.name)
    }
    return tuple(dict.fromkeys(alias for alias in aliases if alias not in other_words))


def _player_identity_matches(player, text: str, participants: list) -> bool:
    return _player_name_matches(
        player.name,
        text,
        surname_aliases=_player_identity_aliases(player, participants),
    )


def _daily_event_terms(name: str, city: str = "") -> tuple[str, ...]:
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", name.casefold()).split())
    aliases: list[str] = []
    compact = normalized.replace(" ", "")
    if "usopen" in compact:
        aliases.extend(("us open", "flushing meadows"))
    if "frenchopen" in compact or "rolandgarros" in compact:
        aliases.extend(("french open", "roland garros"))
    if "australianopen" in compact:
        aliases.extend(("australian open", "melbourne"))
    if "wimbledon" in compact:
        aliases.append("wimbledon")
    if "olympic" in compact:
        aliases.extend(("olympic", "olympics"))
    aliases.extend(sorted(_tokens(city), key=len, reverse=True))
    aliases.extend(sorted(_tokens(name), key=len, reverse=True))
    return tuple(dict.fromkeys(term for term in aliases if term))


def _exact_match_context(match: Match, candidate: dict) -> dict:
    text = _daily_cover_text(candidate)
    participants = [*match.home, *match.away]
    side_names = []
    for side in (match.home, match.away):
        side_names.append(
            any(_player_identity_matches(player, text, participants) for player in side)
        )
    event_terms = _daily_event_terms(
        match.tournament.name,
        match.tournament.city or "",
    )
    event_match = bool(event_terms) and any(term in text for term in event_terms)
    year = str(match.start_utc.year) if match.start_utc is not None else ""
    year_match = bool(year and year in text)
    both_sides_match = all(side_names)
    # A repeated rivalry or annual tournament is not enough to identify one
    # match.  Daily covers must prove both participants, the event and the
    # current edition; otherwise an attractive archive photo can silently
    # replace the match named by the headline.
    exact_match = both_sides_match and event_match and year_match
    return {
        "exact_match": exact_match,
        "both_sides_match": both_sides_match,
        "event_match": event_match,
        "year_match": year_match,
    }


def _daily_cover_metadata_score(
    match: Match,
    candidate: dict,
    scene: dict,
) -> tuple[int, bool, bool]:
    context = _exact_match_context(match, candidate)
    event_match = context["event_match"]
    year_match = context["year_match"]
    scene_points = {
        "match_action": 25,
        "on_court_reaction": 23,
        "solo_trophy": 20,
    }.get(scene["scene"], 0)
    provider_points = {
        "official-atp-youtube": 6,
        "official-match-media": 5,
        "wikimedia-commons": 4,
        "bing-web-image": 3,
        "openverse": 2,
    }.get(str(candidate.get("provider", "")), 1)
    score = 25 + scene_points + provider_points
    if context["exact_match"]:
        score += 15
    if event_match:
        score += 10
    if year_match:
        score += 5
    score += min(5, max(0, int(candidate.get("relevance", 0))))
    return score, event_match, year_match


def _parse_official_feed_time(value: str) -> datetime | None:
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _atp_feed_date_matches(match: Match, published_at: str) -> bool:
    """Accept official uploads from the Beijing match day or following day."""
    if match.start_utc is None:
        return False
    published = _parse_official_feed_time(published_at)
    if published is None:
        return False
    started = match.start_utc
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    match_date = started.astimezone(_BEIJING).date()
    published_date = published.astimezone(_BEIJING).date()
    return published_date in {match_date, match_date + timedelta(days=1)}


def _atp_event_matches(match: Match, text: str) -> bool:
    """Require a meaningful tournament or host-city anchor in official text."""
    normalized = " ".join(re.sub(r"[^a-z0-9]+", " ", text.casefold()).split())
    anchors = _daily_event_terms(
        match.tournament.name,
        match.tournament.city or "",
    )
    return bool(anchors and any(anchor in normalized for anchor in anchors))


def _atp_official_cover_candidates(
    match: Match,
    session: requests.Session,
) -> list[dict]:
    """Discover fresh exact-match images from ATP's verified YouTube feed.

    The RSS publication timestamp proves the current edition; title and
    description must independently name both sides and the event. The image is
    still evaluated later by the common scene, pixel-quality and 3:4 crop gate.
    """
    if getattr(match.tour, "value", str(match.tour)).upper() != "ATP":
        return []
    try:
        response = session.get(ATP_YOUTUBE_FEED, timeout=12)
        response.raise_for_status()
        entries = parse_official_youtube_feed_entries(
            str(response.text),
            channel_id=ATP_YOUTUBE_CHANNEL_ID,
            tour="ATP",
        )
    except (requests.RequestException, VideoPipelineError, TypeError, ValueError):
        return []

    selected: list[dict] = []
    participants = [*match.home, *match.away]
    player_query = " ".join(player.name for player in match.home + match.away)
    for entry in entries:
        source_text = " ".join(
            (
                entry.candidate.title,
                entry.description,
                entry.published_at,
                entry.candidate.url,
            )
        ).lower()
        if not any(term in source_text for term in _ATP_MATCH_VIDEO_TERMS):
            continue
        if any(term in source_text for term in _ATP_NON_MATCH_VIDEO_TERMS):
            continue
        if not all(
            any(_player_identity_matches(player, source_text, participants) for player in side)
            for side in (match.home, match.away)
        ):
            continue
        if not _atp_event_matches(match, source_text):
            continue
        if not _atp_feed_date_matches(match, entry.published_at):
            continue
        candidate = {
            "provider": "official-atp-youtube",
            "source_url": entry.candidate.url,
            "image_url": entry.thumbnail_url,
            "credit": "ATP Tour",
            "license": "official public match media",
            "width": 1280,
            "height": 720,
            "relevance": _relevance(
                f"{player_query} {match.tournament.name}", source_text
            ),
            "search_text": source_text,
            # Preserve only supplied metadata. Pixel QA below must prove that
            # the thumbnail actually contains a prominent athlete.
            "image_text": entry.candidate.title.lower(),
            "source_title": entry.candidate.title,
            "source_description": entry.description,
            "published_at": entry.published_at,
            "official_channel_id": ATP_YOUTUBE_CHANNEL_ID,
        }
        # Keep the same exact-match contract used by every other provider.
        if _exact_match_context(match, candidate)["exact_match"]:
            selected.append(candidate)
    return selected


def _apply_official_maxres_resolution_profile(candidate: dict, audit: dict) -> dict:
    """Recognize YouTube's fixed 1280x720 maxres asset without skipping QA.

    YouTube's highest thumbnail endpoint is capped at 1280x720. Exact ATP feed
    candidates may use that documented profile, while sharpness, contrast,
    information, face count and 3:4 crop safety remain hard requirements.
    """
    if (
        candidate.get("provider") != "official-atp-youtube"
        or candidate.get("official_channel_id") != ATP_YOUTUBE_CHANNEL_ID
        or not re.fullmatch(
            r"https://i\.ytimg\.com/vi/[A-Za-z0-9_-]+/maxresdefault\.jpg",
            str(candidate.get("image_url", "")),
        )
    ):
        return audit
    width = int(audit.get("width", 0))
    height = int(audit.get("height", 0))
    short_side, long_side = sorted((width, height))
    if short_side < 720 or long_side < 1280:
        return audit
    failures = list(audit.get("hard_failures", []))
    if "resolution-below-900x1200" not in failures:
        return audit
    failures.remove("resolution-below-900x1200")
    updated = dict(audit)
    updated["hard_failures"] = failures
    updated["status"] = "pass" if not failures else "fail"
    updated["resolution_profile"] = "official-youtube-maxres-1280x720"
    return updated


_OFFICIAL_TOUR_MEDIA_DOMAINS = (
    "wtatennis.com",
    "atptour.com",
)


class _SocialMetadataParser(HTMLParser):
    """Collect social-card metadata without an extra HTML dependency."""

    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.image_src = ""
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag == "link":
            rel = {part.lower() for part in values.get("rel", "").split()}
            if "image_src" in rel and not self.image_src:
                self.image_src = values.get("href", "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(self.title_parts).strip()


class _WtaVideoHubParser(HTMLParser):
    """Collect WTA video article links and their visible labels."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        href = values.get("href", "").strip()
        if re.search(r"(?:^|/)videos/\d+/", href, re.I):
            self._href = href
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = ""
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href and data.strip():
            self._text.append(data.strip())


def _is_official_tour_media_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").casefold()
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in _OFFICIAL_TOUR_MEDIA_DOMAINS
    )


def _high_resolution_official_image_url(url: str) -> str:
    """Upgrade social-card thumbnails while restoring their original ratio."""
    parsed = urlparse(html.unescape(url))
    hostname = (parsed.hostname or "").casefold()
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if hostname == "photoresources.wtatennis.com":
        try:
            current_width = int(query.get("width", "0") or 0)
        except ValueError:
            current_width = 0
        query["width"] = str(max(2000, current_width))
        # WTA OG metadata normally requests a forced 1200x630 social crop.
        # Width-only requests expose the full source aspect ratio instead.
        query.pop("height", None)
    elif hostname.endswith("atptour.com") and "width" in query:
        try:
            current_width = int(query.get("width", "0") or 0)
        except ValueError:
            current_width = 0
        query["width"] = str(max(2000, current_width))
        query.pop("height", None)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _wta_video_hub_candidates(
    match: Match,
    session: requests.Session,
) -> list[dict]:
    """Discover exact-match WTA video pages before opening article metadata.

    The public hub is the primary source. WTA's official video sitemap is a
    freshness fallback because newly published highlights can reach the
    sitemap several hours before a cached hub page. Both sources only discover
    article URLs; the article's own metadata remains the acceptance proof.
    """
    discovered: list[tuple[str, str]] = []
    for hub_url in (
        "https://www.wtatennis.com/videos",
        "https://www.wtatennis.com/videos/highlights",
    ):
        try:
            response = session.get(hub_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            continue
        parser = _WtaVideoHubParser()
        try:
            parser.feed(response.text)
        except (TypeError, ValueError):
            continue
        discovered.extend(
            (urljoin(str(response.url or hub_url), href), label)
            for href, label in parser.links
        )

    sitemap_url = "https://www.wtatennis.com/sitemap/videos.xml"
    try:
        response = session.get(sitemap_url, timeout=20)
        response.raise_for_status()
        for value in re.findall(r"<loc>\s*([^<]+?/videos/\d+/[^<]+)\s*</loc>", response.text, re.I):
            discovered.append((html.unescape(value.strip()), ""))
    except requests.RequestException:
        pass

    candidates: list[dict] = []
    participants = [*match.home, *match.away]
    seen: set[str] = set()
    for source_url, label in discovered:
        source_url = source_url.strip()
        if source_url in seen or not _is_official_tour_media_url(source_url):
            continue
        seen.add(source_url)
        discovery_text = " ".join((label, unquote(urlparse(source_url).path))).lower()
        side_matches = [
            any(
                _player_identity_matches(player, discovery_text, participants)
                for player in side
            )
            for side in (match.home, match.away)
        ]
        if not all(side_matches):
            continue
        candidates.append(
            {
                "provider": "wta-video-hub",
                "source_url": source_url,
                "image_url": "",
                "credit": "wtatennis.com",
                "license": "WTA 官方公开页面图片 · 资讯引用",
                "width": 0,
                "height": 0,
                "relevance": _relevance(
                    " ".join(player.name for player in match.home + match.away),
                    discovery_text,
                ),
                "search_text": discovery_text,
                "image_text": discovery_text,
                "discovered_via": "wta-video-hub",
            }
        )
    return candidates


def _expand_official_source_candidate(
    match: Match,
    candidate: dict,
    session: requests.Session,
) -> dict | None:
    """Expand an exact WTA/ATP result into its high-resolution OG image.

    Only the source page's own head metadata may establish the match. Generic
    tournament and scores pages therefore cannot borrow the players from the
    search query and masquerade as an exact-match photograph.
    """
    source_url = str(candidate.get("source_url", "")).strip()
    if not source_url.startswith("https://") or not _is_official_tour_media_url(source_url):
        return None
    try:
        response = session.get(source_url, timeout=12)
        response.raise_for_status()
    except requests.RequestException:
        return None
    final_url = str(response.url or source_url)
    if not _is_official_tour_media_url(final_url):
        return None

    parser = _SocialMetadataParser()
    try:
        parser.feed(response.text)
    except (TypeError, ValueError):
        return None
    meta = parser.meta
    image_url = next(
        (
            meta.get(key, "").strip()
            for key in (
                "og:image:secure_url",
                "og:image",
                "twitter:image",
                "twitter:image:src",
            )
            if meta.get(key, "").strip()
        ),
        parser.image_src,
    )
    if not image_url:
        return None
    title = meta.get("og:title") or meta.get("twitter:title") or parser.title
    description = (
        meta.get("og:description")
        or meta.get("twitter:description")
        or meta.get("description")
        or ""
    )
    image_alt = meta.get("og:image:alt") or meta.get("twitter:image:alt") or ""
    # Deliberately omit candidate.search_text: it may include the search query,
    # while only the official page itself can prove this is the same match.
    # The dated official media path is useful edition evidence. WTA highlight
    # titles often name both players and the event but omit the calendar year.
    source_text = " ".join(
        (title, description, image_alt, final_url, html.unescape(image_url))
    ).lower()
    def meta_int(key: str) -> int:
        match_value = re.search(r"\d+", meta.get(key, ""))
        return int(match_value.group()) if match_value else 0

    expanded = {
        **candidate,
        "provider": "official-match-media",
        "source_url": final_url,
        "image_url": _high_resolution_official_image_url(
            urljoin(final_url, html.unescape(image_url))
        ),
        "credit": (urlparse(final_url).hostname or "Official tour media").removeprefix("www."),
        "license": "官方公开页面图片 · 资讯引用",
        "width": meta_int("og:image:width"),
        "height": meta_int("og:image:height"),
        "relevance": _relevance(
            f"{' '.join(player.name for player in match.home + match.away)} "
            f"{match.tournament.name}",
            source_text,
        ),
        "search_text": source_text,
        "image_text": " ".join((image_alt, title, image_url)).lower(),
        "source_title": title,
        "source_description": description,
        "expanded_from_provider": candidate.get("provider", ""),
    }
    if not _exact_match_context(match, expanded)["exact_match"]:
        return None
    return expanded


def _daily_editorial_candidates(
    match: Match,
    player_name: str,
    session: requests.Session,
) -> list[dict]:
    """Extract exact-player social images from match-linked editorial pages."""
    urls = [match.editorial_url, *match.schedule_source_urls]
    candidates: list[dict] = []
    for url in dict.fromkeys(str(item or "").strip() for item in urls):
        if not url.startswith("https://") or "news.google." in url:
            continue
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            continue
        image_match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
            response.text,
            re.I,
        ) or re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            response.text,
            re.I,
        )
        if not image_match:
            continue
        title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.I | re.S)
        description_match = re.search(
            r'<meta[^>]+(?:property|name)=["\'](?:og:description|description)["\'][^>]+content=["\']([^"\']+)',
            response.text,
            re.I,
        )
        alt_match = re.search(
            r'<meta[^>]+property=["\']og:image:alt["\'][^>]+content=["\']([^"\']+)',
            response.text,
            re.I,
        )
        title = re.sub(r"<[^>]+>", " ", title_match.group(1) if title_match else "")
        description = re.sub(
            r"<[^>]+>", " ", description_match.group(1) if description_match else ""
        )
        alt = re.sub(r"<[^>]+>", " ", alt_match.group(1) if alt_match else "")
        text = " ".join((title, description, alt, url)).lower()
        if not all(token in text for token in _tokens(player_name)):
            continue
        domain = urlparse(url).netloc.removeprefix("www.")
        candidates.append(
            {
                "provider": "official-match-media",
                "source_url": url,
                "image_url": _high_resolution_official_image_url(
                    urljoin(url, html.unescape(image_match.group(1)))
                ),
                "credit": domain,
                "license": "公开网页图片 · 资讯引用",
                "width": 0,
                "height": 0,
                "relevance": _relevance(f"{player_name} {match.tournament.name}", text),
                "search_text": text,
                "image_text": " ".join((player_name, alt, title)).lower(),
            }
        )
    return candidates


def resolve_match_cover_visual(
    match: Match,
    folder: Path,
) -> tuple[ResolvedVisual | None, dict]:
    """Select the strongest action-led image from the headline match."""
    enabled = os.environ.get("TENNISLIVE_COVER_VISUAL_FETCH", "off").lower() in {
        "1",
        "on",
        "true",
    }
    strict = os.environ.get("TENNISLIVE_COVER_VISUAL_STRICT", "on").lower() in {
        "1",
        "on",
        "true",
    }
    minimum_score = int(os.environ.get("TENNISLIVE_COVER_VISUAL_MIN_SCORE", "72"))
    max_downloads = int(os.environ.get("TENNISLIVE_COVER_VISUAL_DOWNLOADS", "10"))
    folder.mkdir(parents=True, exist_ok=True)
    players = _daily_cover_players(match)
    attempts: list[dict] = []
    report = {
        "schema_version": 2,
        "status": "unavailable",
        "match_id": match.match_id,
        "match_players": [player.name for player in match.home + match.away],
        "candidate_players": [player.name for player in players],
        "china_priority": True,
        "policy": (
            "只接受能同时证明双方球员与当届赛事的头条比赛现场图；中国球员优先；"
            "比赛动作、场内情绪和单人举杯优先，至少须有像素验证的突出人物；"
            "赛前合照、摆拍、发布会和多人颁奖照直接淘汰；多源候选全部评分后择优"
        ),
        "fetch_enabled": enabled,
        "strict": strict,
        "minimum_score": minimum_score,
        "providers_queried": [],
        "attempts": attempts,
    }
    if not enabled:
        report["status"] = "disabled"
        return None, report

    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    provider_loaders = (
        ("wikimedia-commons", _commons_candidates),
        ("openverse", _openverse_candidates),
        ("bing-web-image", _bing_candidates),
    )
    pool: list[tuple[object, str, dict]] = []
    atp_official_enabled = os.environ.get(
        "TENNISLIVE_COVER_ATP_OFFICIAL", "off"
    ).lower() in {"1", "on", "true"}
    atp_official = (
        _atp_official_cover_candidates(match, session)
        if atp_official_enabled
        else []
    )
    report["atp_official_enabled"] = atp_official_enabled
    report["atp_official_candidates"] = len(atp_official)
    if atp_official_enabled:
        report["providers_queried"].append("official-atp-youtube")
    if atp_official and players:
        official_query = _daily_cover_queries(match, players[0].name)[0]
        pool.extend((players[0], official_query, item) for item in atp_official)
    wta_official_enabled = os.environ.get(
        "TENNISLIVE_COVER_WTA_OFFICIAL", "off"
    ).lower() in {"1", "on", "true"}
    wta_hub_candidates = (
        _wta_video_hub_candidates(match, session)
        if wta_official_enabled
        else []
    )
    report["wta_official_enabled"] = wta_official_enabled
    if wta_official_enabled:
        report["providers_queried"].append("wta-video-hub")
    if wta_hub_candidates:
        hub_query = " ".join(player.name for player in match.home + match.away)
        pool.extend((players[0], hub_query, item) for item in wta_hub_candidates)
    report["wta_video_hub_candidates"] = len(wta_hub_candidates)
    search_jobs: list[tuple[object, str, str, object]] = []
    for player in players:
        queries = _daily_cover_queries(match, player.name)
        direct = _daily_editorial_candidates(match, player.name, session)
        if direct and "official-match-media" not in report["providers_queried"]:
            report["providers_queried"].append("official-match-media")
        pool.extend((player, queries[0], item) for item in direct)
        for query in queries:
            for provider, loader in provider_loaders:
                if provider not in report["providers_queried"]:
                    report["providers_queried"].append(provider)
                search_jobs.append((player, query, provider, loader))

    def fetch_job(job):
        player, query, provider, loader = job
        worker_session = requests.Session()
        worker_session.headers.update({"User-Agent": _UA})
        return player, query, provider, loader(query, worker_session)

    with ThreadPoolExecutor(max_workers=min(8, len(search_jobs) or 1)) as executor:
        for player, query, provider, items in executor.map(fetch_job, search_jobs):
            for item in items:
                item = dict(item)
                item["provider"] = provider
                pool.append((player, query, item))

    expanded_urls: set[str] = set()
    expanded_count = 0
    for player, query, candidate in list(pool):
        source_url = str(candidate.get("source_url", "")).strip()
        if source_url in expanded_urls or not _is_official_tour_media_url(source_url):
            continue
        expanded_urls.add(source_url)
        expanded = _expand_official_source_candidate(match, candidate, session)
        if expanded is None:
            continue
        pool.append((player, query, expanded))
        expanded_count += 1
    if expanded_count:
        report["providers_queried"].append("official-match-media")
    report["official_pages_checked"] = len(expanded_urls)
    report["official_pages_expanded"] = expanded_count

    candidates: list[tuple[object, str, dict, dict, int, bool, bool]] = []
    participants = [*match.home, *match.away]
    seen: set[str] = set()
    for player, query, candidate in pool:
        identity = str(candidate.get("image_url") or candidate.get("source_url") or "")
        if not identity or identity in seen:
            continue
        seen.add(identity)
        candidate_text = _daily_cover_text(candidate)
        subject_match = _player_identity_matches(player, candidate_text, participants)
        negative_visual = any(
            term in _daily_cover_visual_descriptor(candidate)
            for term in _NEGATIVE_PERSON_TERMS
        )
        person_match = subject_match and not negative_visual
        context = _exact_match_context(match, candidate)
        scene = classify_cover_scene(_daily_cover_visual_descriptor(candidate))
        metadata_score, event_match, year_match = _daily_cover_metadata_score(
            match, candidate, scene
        )
        china_bonus = 6 if player.country == "CHN" else 0
        metadata_score += china_bonus
        record = {
            "player": player.name,
            "provider": candidate.get("provider", ""),
            "source_url": candidate.get("source_url", ""),
            "subject_match": subject_match,
            "person_match": person_match,
            "both_sides_match": context["both_sides_match"],
            "exact_match": context["exact_match"],
            "event_match": event_match,
            "year_match": year_match,
            "scene": scene["scene"],
            "china_priority_bonus": china_bonus,
            "scene_evidence": {
                "motion": scene["motion_terms"],
                "reaction": scene["reaction_terms"],
                "trophy": scene["trophy_terms"],
                "rejected": scene["rejected_terms"],
            },
            "metadata_score": metadata_score,
        }
        hard_failures: list[str] = []
        if not (subject_match and person_match):
            hard_failures.append("headline-match-player-mismatch")
        if not context["exact_match"]:
            hard_failures.append("not-the-exact-headline-match")
        if scene["scene"] == "static_or_group":
            hard_failures.append("static-or-group-photo")
        if any(term in _daily_cover_text(candidate) for term in _WATERMARK_LIBRARY_TERMS):
            hard_failures.append("watermarked-stock-library")
        if hard_failures:
            record.update(status="rejected", hard_failures=hard_failures)
            attempts.append(record)
            continue
        candidates.append(
            (player, query, candidate, record, metadata_score, event_match, year_match)
        )

    candidates.sort(
        key=lambda item: (
            item[4],
            min(int(item[2].get("width", 0)), int(item[2].get("height", 0))),
            int(item[2].get("width", 0)) * int(item[2].get("height", 0)),
        ),
        reverse=True,
    )
    qualified: list[tuple[float, ResolvedVisual, dict]] = []
    for player, query, candidate, record, metadata_score, event_match, year_match in candidates[:max_downloads]:
        downloaded = _download(candidate, "daily-cover", query, folder, session)
        if downloaded is None:
            record.update(
                status="rejected",
                hard_failures=["download-failed-or-resolution-below-900x540"],
            )
            attempts.append(record)
            continue
        audit = _apply_official_maxres_resolution_profile(
            candidate,
            assess_cover_image(downloaded.path),
        )
        total_score = round(metadata_score + float(audit.get("score", 0)), 1)
        failures = list(audit.get("hard_failures", []))
        prominent_faces = int(audit.get("prominent_faces", 0) or 0)
        if prominent_faces < 1 and "no-prominent-face" not in failures:
            failures.append("no-prominent-face")
        if record["scene"] == "unknown" and prominent_faces:
            # Pixel evidence proves a person is prominent; it does not claim
            # an action that the source metadata never described.
            record["scene"] = "prominent_person"
            record["scene_evidence"]["pixel"] = [
                f"{prominent_faces} prominent face(s)",
                *[str(value) for value in audit.get("face_detectors", [])],
            ]
        if total_score < minimum_score:
            failures.append(f"quality-score-below-{minimum_score}")
        record.update(
            {
                "status": "qualified" if not failures else "rejected",
                "quality": audit,
                "quality_score": total_score,
                "hard_failures": failures,
                "cached_file": downloaded.path.name,
            }
        )
        attempts.append(record)
        if failures:
            downloaded.path.unlink(missing_ok=True)
            continue
        visual = replace(
            downloaded,
            focus=str(audit.get("focus", "50% 28%")),
            subject_match=True,
            year_match=year_match,
            event_match=event_match,
            person_required=True,
        )
        qualified.append((total_score, visual, record))

    if not qualified:
        report["errors"] = [
            "没有找到同时满足当场比赛、运动场景、画质和竖版安全裁切的照片"
        ]
        return None, report

    qualified.sort(key=lambda item: item[0], reverse=True)
    selected_score, selected, selected_record = qualified[0]
    selected_record["status"] = "selected"
    for _score, visual, record in qualified[1:]:
        record["status"] = "rejected"
        record["reason"] = "quality-score-lower-than-selected"
        visual.path.unlink(missing_ok=True)
    report.update(
        {
            "status": "selected",
            "selected_player": selected_record["player"],
            "exact_match": selected_record["exact_match"],
            "both_sides_match": selected_record["both_sides_match"],
            "scene": selected_record["scene"],
            "quality_score": selected_score,
            "quality": selected_record["quality"],
            "event_match": selected.event_match,
            "year_match": selected.year_match,
            "provider": selected.provider,
            "source_url": selected.source_url,
            "credit": selected.credit,
            "license": selected.license,
            "focus": selected.focus,
        }
    )
    return selected, report
