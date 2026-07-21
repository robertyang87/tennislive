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

from ..render.tournament_story import TournamentStory


_UA = "tennislive/1.0 visual-research (github.com/robertyang87/tennislive)"
_LICENSES = {"cc0", "pdm", "by", "by-sa", "cc-by", "cc-by-sa"}
_PAGES = ("story", "explainer", "today")
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


def _queries(story: TournamentStory) -> dict[str, str]:
    subject = _subject(story)
    years = [moment.date[:4] for moment in story.moments]
    location = story.location.split("·", 1)[0].strip()
    anchors = _page_anchors(story)
    return {
        "story": " ".join(
            filter(
                None,
                (
                    subject,
                    years[0] if years else "",
                    (anchors.get("story") or ("",))[0],
                    "tennis",
                ),
            )
        ),
        "explainer": " ".join(filter(None, (subject, story.surface, location, "tennis"))),
        "today": " ".join(
            filter(
                None,
                (
                    subject,
                    years[-1] if years else "",
                    (anchors.get("today") or ("",))[0],
                    "tennis",
                ),
            )
        ),
    }


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


def _official_references(story: TournamentStory, session: requests.Session) -> list[dict]:
    urls = list(dict.fromkeys(
        [story.source_url, *story.evidence_urls, *(m.source_url for m in story.moments)]
    ))
    found: list[dict] = []
    for url in urls[:5]:
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
            found.append(
                {
                    "provider": "official-page",
                    "page_url": url,
                    "image_url": match.group(1) if match else "",
                    "status": "reference-only",
                    "reason": "未发现明确再利用许可，不直接下载发布",
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


def resolve_story_visuals(story: TournamentStory, folder: Path) -> tuple[dict[str, ResolvedVisual], dict]:
    """Try multiple sources, keep exact licensed images, and audit every fallback."""
    enabled = os.environ.get("TENNISLIVE_VISUAL_FETCH", "off").lower() in {"1", "on", "true"}
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": _UA})
    attempts = _official_references(story, session) if enabled else []
    selected: dict[str, ResolvedVisual] = {}
    anchors_by_page = _page_anchors(story)
    used_sources = {story.image_source_url}
    used_hashes: set[str] = set()
    if story.image.is_file():
        used_hashes.add(hashlib.sha256(story.image.read_bytes()).hexdigest())
    for page, query in _queries(story).items():
        required_anchors = anchors_by_page.get(page, ())
        if not enabled or (story.diagram_type and page == "explainer"):
            attempts.append(
                {"page": page, "status": "generated-visual", "reason": "规则示意图或联网检索未启用", "query": query}
            )
            continue
        providers = (
            ("wikimedia-commons", _commons_candidates(query, session)),
            ("openverse", _openverse_candidates(query, session)),
        )
        candidates = [candidate for _provider, items in providers for candidate in items]
        candidates.sort(key=lambda item: (item["relevance"], item.get("width", 0)), reverse=True)
        chosen = None
        for candidate in candidates:
            if candidate["source_url"] in used_sources or candidate["relevance"] < 3:
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
                focus = "50% 24%" if story.kind == "player" else "50% 38%"
                chosen = replace(downloaded, focus=focus)
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
    return selected, {
        "schema_version": 1,
        "status": "pass",
        "story_slug": story.slug,
        "fetch_enabled": enabled,
        "policy": "官方页面用于核对；仅下载许可明确且相关性达标的 Commons/Openverse 图片；否则生成事实图解",
        "selected_count": len(selected),
        "attempts": attempts,
    }
