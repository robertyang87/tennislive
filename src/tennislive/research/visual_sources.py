"""Multi-source, license-aware visual discovery for knowledge cards."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from PIL import Image

from ..models import Match
from ..render.tournament_story import TournamentStory


_UA = "tennislive/1.0 visual-research (github.com/robertyang87/tennislive)"
_LICENSES = {"cc0", "pdm", "by", "by-sa", "cc-by", "cc-by-sa"}
_PAGES = ("story", "explainer", "today")
_NEGATIVE_PERSON_TERMS = {
    "scoreboard", "results", "draw", "bracket", "stadium", "arena",
    "court", "ball", "logo", "poster", "ticket", "building", "map",
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
    for page in _PAGES:
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
    negative_only = any(term in text for term in _NEGATIVE_PERSON_TERMS) and not any(
        term in text for term in ("player", "woman", "man", "portrait", "serve", "forehand", "backhand", "athlete")
    )
    person_match = not person_required or (subject_match and not negative_only)
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
        "gsrsearch": f"filetype:bitmap {query}",
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
            }
        )
    return candidates


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
    if cover_audit["status"] != "selected":
        preflight_errors.append(cover_audit["reason"])
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
    official_references = (
        _official_references(story, session)
        if enabled and not story.diagram_type
        else []
    )
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
        if story.diagram_type:
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
        providers = (
            ("official-media", official_candidates),
            ("wikimedia-commons", _commons_candidates(query, session)),
            ("openverse", _openverse_candidates(query, session)),
        )
        candidates = [candidate for _provider, items in providers for candidate in items]
        candidates.sort(key=lambda item: (item["relevance"], item.get("width", 0)), reverse=True)
        chosen = None
        for candidate in candidates:
            if candidate["source_url"] in used_sources or candidate["relevance"] < 3:
                continue
            subject_match, year_match, event_match, person_match = _candidate_matches(
                candidate, briefs[page]
            )
            if not (subject_match and year_match and event_match and person_match):
                continue
            if required_anchors and not any(
                anchor in candidate.get("search_text", "")
                for anchor in required_anchors
            ):
                continue
            downloaded = _download(candidate, page, query, folder, session)
            if downloaded and downloaded.sha256 in used_hashes:
                downloaded.path.unlink(missing_ok=True)
                continue
            if downloaded:
                focus = "50% 24%" if briefs[page][3] else "50% 38%"
                chosen = replace(
                    downloaded,
                    focus=focus,
                    subject_match=subject_match,
                    year_match=year_match,
                    event_match=event_match,
                    person_required=briefs[page][3],
                )
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
    if strict and cover_audit["status"] != "selected":
        errors.append(cover_audit["reason"])
    if strict and missing_pages:
        errors.append("缺少通过精确核验的页面照片：" + "、".join(missing_pages))
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
            if story.diagram_type
            else ["official-media", "wikimedia-commons", "openverse"]
        ),
        "selected_providers": sorted({visual.provider for visual in selected.values()}),
        "errors": errors,
        "attempts": attempts,
    }


def resolve_match_cover_visual(
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
