"""Collect high-resolution, attributable images from official social channels.

This module deliberately separates *publicly retrievable* from *licensed for
republication*.  Every candidate keeps its landing page, account and rights
status; callers must not interpret a successful download as a licence grant.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import shutil
from dataclasses import asdict, dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from PIL import Image

_SINA_RE = re.compile(
    r"https?://(?:wx\d+|tvax\d+)\.sinaimg\.cn/[^/\s\"']+/[A-Za-z0-9]+(?:\.(?:jpg|jpeg|png|webp))?",
    re.I,
)
_X_MEDIA_RE = re.compile(r"https?://pbs\.twimg\.com/media/[^\s\"'<>\\]+", re.I)
_USOPEN_RE = re.compile(
    r"https?://photo-assets\.usopen\.org/images/pics/(?:large|thumb)/[^\s\"'<>]+?\.jpe?g",
    re.I,
)
_UA = "Mozilla/5.0 (compatible; TennisLiveOfficialMedia/1.0; +https://github.com/)"


@dataclass
class OfficialImage:
    provider: str
    account: str
    post_url: str
    image_url: str
    source_page_url: str = ""
    caption: str = ""
    credit: str = "unknown"
    rights_status: str = "public-access-rights-unverified"
    published_at: str = ""
    width: int = 0
    height: int = 0
    sha256: str = ""
    dhash: str = ""
    local_path: str = ""
    current_match: bool = False
    score: float = 0.0
    provenance: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def canonicalize_x_image_url(url: str) -> str:
    """Request the original rendition from Twitter/X's public image CDN."""
    url = html_lib.unescape(url).replace("\\u0026", "&")
    parsed = urlparse(url)
    if parsed.hostname not in {"pbs.twimg.com", "ton.twimg.com"}:
        return url
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["name"] = "orig"
    return urlunparse(parsed._replace(query=urlencode(query)))


def canonicalize_sina_image_url(url: str) -> str:
    """Turn a public Weibo/Sina rendition into its public ``large`` URL."""
    url = html_lib.unescape(url).replace("\\/", "/")
    return re.sub(r"(sinaimg\.cn)/[^/]+/", r"\1/large/", url, count=1, flags=re.I)


def sina_mirror_url(weibo_url_or_id: str) -> str:
    match = re.search(r"(\d{12,})", weibo_url_or_id)
    if not match:
        raise ValueError("Weibo URL must contain the numeric status id")
    return f"https://www.sina.cn/news/detail/{match.group(1)}.html"


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def extract_weibo_sina_images(text: str, post_url: str, *, account: str = "US Open") -> list[OfficialImage]:
    decoded = html_lib.unescape(text).replace("\\/", "/")
    urls = _unique(canonicalize_sina_image_url(url) for url in _SINA_RE.findall(decoded))
    return [
        OfficialImage(
            provider="official-weibo",
            account=account,
            post_url=post_url,
            source_page_url=post_url,
            image_url=url,
        )
        for url in urls
    ]


def extract_x_images(text: str, post_url: str, *, account: str = "US Open") -> list[OfficialImage]:
    decoded = html_lib.unescape(text).replace("\\/", "/").replace("\\u0026", "&")
    urls = _unique(
        canonicalize_x_image_url(url)
        for url in _X_MEDIA_RE.findall(decoded)
    )
    return [
        OfficialImage(
            provider="official-x",
            account=account,
            post_url=post_url,
            source_page_url=post_url,
            image_url=url,
        )
        for url in urls
    ]


def _walk_json_images(value: object) -> Iterable[tuple[str, int, int]]:
    if isinstance(value, dict):
        url = value.get("url") or value.get("src") or value.get("display_url")
        if isinstance(url, str) and re.search(r"\.(?:jpe?g|png|webp)(?:\?|$)", url, re.I):
            yield url, int(value.get("width") or value.get("config_width") or 0), int(
                value.get("height") or value.get("config_height") or 0
            )
        for child in value.values():
            yield from _walk_json_images(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json_images(child)


def extract_instagram_images(text: str, post_url: str, *, account: str = "US Open") -> list[OfficialImage]:
    """Extract the largest public rendition exposed in Instagram page metadata."""
    decoded = html_lib.unescape(text).replace("\\/", "/").replace("\\u0026", "&")
    found: list[tuple[str, int, int]] = []
    for raw in re.findall(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", decoded, re.I | re.S):
        try:
            found.extend(_walk_json_images(json.loads(raw)))
        except (ValueError, TypeError):
            continue
    for raw in re.findall(r"(?:display_url|image_url|src)[\"']?\s*[:=]\s*[\"']([^\"']+)", decoded, re.I):
        found.append((raw, 0, 0))
    for raw in re.findall(r"<meta[^>]+property=[\"']og:image[\"'][^>]+content=[\"']([^\"']+)", decoded, re.I):
        found.append((raw, 0, 0))
    by_url: dict[str, tuple[int, int]] = {}
    for url, width, height in found:
        if "cdninstagram.com" not in url and "fbcdn.net" not in url:
            continue
        previous = by_url.get(url, (0, 0))
        if width * height > previous[0] * previous[1]:
            by_url[url] = (width, height)
    return [
        OfficialImage(
            provider="official-instagram",
            account=account,
            post_url=post_url,
            source_page_url=post_url,
            image_url=url,
            width=size[0],
            height=size[1],
        )
        for url, size in by_url.items()
    ]


def extract_usopen_cms_images(text: str, page_url: str) -> list[OfficialImage]:
    decoded = html_lib.unescape(text).replace("\\/", "/")
    urls = _unique(url.replace("/pics/thumb/", "/pics/large/") for url in _USOPEN_RE.findall(decoded))
    credit_match = re.search(r"(?:photo(?:grapher)?|credit)\s*[:：]\s*([^<\n]{2,80})", decoded, re.I)
    credit = re.sub(r"\s+", " ", credit_match.group(1)).strip() if credit_match else "USTA/US Open"
    return [
        OfficialImage(
            provider="usopen-cms",
            account="US Open",
            post_url=page_url,
            source_page_url=page_url,
            image_url=url,
            credit=credit,
        )
        for url in urls
    ]


def extract_page(provider: str, text: str, url: str, account: str = "US Open") -> list[OfficialImage]:
    if provider == "official-weibo":
        return extract_weibo_sina_images(text, url, account=account)
    if provider == "official-x":
        return extract_x_images(text, url, account=account)
    if provider == "official-instagram":
        return extract_instagram_images(text, url, account=account)
    if provider == "usopen-cms":
        return extract_usopen_cms_images(text, url)
    raise ValueError(f"unsupported provider: {provider}")


def page_caption(text: str) -> str:
    """Return the public page description used as match-evidence text."""
    decoded = html_lib.unescape(text).replace("\\/", "/")
    for pattern in (
        r"<meta[^>]+property=[\"']og:description[\"'][^>]+content=[\"']([^\"']+)",
        r"<meta[^>]+name=[\"']description[\"'][^>]+content=[\"']([^\"']+)",
    ):
        match = re.search(pattern, decoded, re.I)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def discover_post_urls(provider: str, text: str, profile_url: str) -> list[str]:
    """Find recent post permalinks exposed by a public official profile page."""
    decoded = html_lib.unescape(text).replace("\\/", "/")
    if provider == "official-x":
        handles = re.findall(r"x\.com/([A-Za-z0-9_]+)/status/(\d+)", decoded, re.I)
        return _unique(f"https://x.com/{handle}/status/{status}" for handle, status in handles)
    if provider == "official-instagram":
        codes = re.findall(
            r"(?:instagram\.com)?/(?:p|reel)/([A-Za-z0-9_-]+)", decoded, re.I
        )
        codes.extend(re.findall(r"[\"']shortcode[\"']\s*:\s*[\"']([A-Za-z0-9_-]+)", decoded))
        return _unique(f"https://www.instagram.com/p/{code}/" for code in codes)
    return [profile_url]


def _dhash(image: Image.Image) -> str:
    pixels = image.convert("L").resize((9, 8)).load()
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | int(pixels[x, y] > pixels[x + 1, y])
    return f"{bits:016x}"


def _hamming(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()


def download_candidates(
    candidates: Iterable[OfficialImage],
    output_dir: Path,
    session: requests.Session | None = None,
) -> list[OfficialImage]:
    output_dir.mkdir(parents=True, exist_ok=True)
    client = session or requests.Session()
    client.headers.update({"User-Agent": _UA})
    downloaded: list[OfficialImage] = []
    for candidate in candidates:
        try:
            response = client.get(candidate.image_url, timeout=20)
            response.raise_for_status()
            if len(response.content) > 30 * 1024 * 1024:
                continue
            image = Image.open(BytesIO(response.content))
            image.load()
        except (requests.RequestException, OSError, ValueError):
            continue
        digest = hashlib.sha256(response.content).hexdigest()
        suffix = ".png" if image.format == "PNG" else ".webp" if image.format == "WEBP" else ".jpg"
        path = output_dir / f"{candidate.provider}-{digest[:12]}{suffix}"
        if not path.exists():
            path.write_bytes(response.content)
        candidate.width, candidate.height = image.size
        candidate.sha256 = digest
        candidate.dhash = _dhash(image)
        candidate.local_path = str(path)
        downloaded.append(candidate)
    return downloaded


def _quality_score(item: OfficialImage, chinese_priority: bool) -> float:
    provider_bonus = {
        "official-weibo": 18 if chinese_priority else 12,
        "official-x": 14,
        "official-instagram": 13,
        "usopen-cms": 11,
    }.get(item.provider, 0)
    pixels = min(item.width * item.height / 1_000_000, 16) * 3
    match_bonus = 30 if item.current_match else 0
    return round(provider_bonus + pixels + match_bonus, 2)


def deduplicate_candidates(
    candidates: Iterable[OfficialImage], *, chinese_priority: bool = False, max_hamming: int = 5
) -> list[OfficialImage]:
    """Keep the best rendition while merging credit and every source trail."""
    groups: list[list[OfficialImage]] = []
    for item in candidates:
        group = next(
            (
                group
                for group in groups
                if item.sha256 and any(item.sha256 == other.sha256 for other in group)
                or item.dhash and any(other.dhash and _hamming(item.dhash, other.dhash) <= max_hamming for other in group)
            ),
            None,
        )
        if group is None:
            groups.append([item])
        else:
            group.append(item)
    winners: list[OfficialImage] = []
    for group in groups:
        for item in group:
            item.score = _quality_score(item, chinese_priority)
        winner = max(group, key=lambda row: (row.score, row.width * row.height))
        credits = [row.credit for row in group if row.credit not in {"", "unknown"}]
        if winner.credit in {"", "unknown"} and credits:
            winner.credit = credits[0]
        winner.provenance = [
            {
                "provider": row.provider,
                "post_url": row.post_url,
                "image_url": row.image_url,
                "width": row.width,
                "height": row.height,
                "credit": row.credit,
            }
            for row in group
        ]
        winners.append(winner)
    return sorted(winners, key=lambda row: row.score, reverse=True)


def mark_current_match(candidates: Iterable[OfficialImage], terms: Iterable[str]) -> None:
    needles = [term.casefold() for term in terms if term.strip()]
    for item in candidates:
        haystack = " ".join((item.caption, item.post_url, item.source_page_url)).casefold()
        item.current_match = bool(needles) and all(needle in haystack for needle in needles)


def matches_evidence(text: str, groups: list[list[str]]) -> bool:
    """Require at least one alias from every evidence group (normally each player)."""
    haystack = text.casefold()
    return bool(groups) and all(
        any(alias.casefold() in haystack for alias in group if alias.strip())
        for group in groups
    )


def monitor_trigger_ready(watch: dict, root: Path = Path(".")) -> tuple[bool, str]:
    """Only monitor after the requested reel is rendered and its cover is provisional."""
    result_file = str(watch.get("result_file", "")).strip()
    if result_file and (root / result_file).is_file():
        return False, "qualified-image-already-found"
    trigger = watch.get("trigger") or {}
    if trigger.get("type") != "video-ready-cover-pending":
        return False, "missing-on-demand-trigger"
    spec_path = root / str(trigger.get("spec", ""))
    render_path = root / str(trigger.get("render_manifest", ""))
    if not spec_path.is_file():
        return False, "video-spec-not-ready"
    if not render_path.is_file():
        return False, "video-render-not-ready"
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, "video-spec-invalid"
    portrait = ((spec.get("cover") or {}).get("portrait") or {})
    provisional = bool(
        portrait.get("frame_at") is not None
        or str(portrait.get("_low_res_why", "")).strip()
        or str(portrait.get("monitor_status", "")) == "pending-high-resolution-photo"
    )
    return (True, "video-ready-cover-pending") if provisional else (
        False,
        "cover-is-not-marked-provisional",
    )


def persist_selected_result(report: dict, watch: dict, root: Path = Path(".")) -> Path | None:
    """Persist the winning original and a stop marker for the scheduled queue."""
    selected = report.get("selected")
    if not isinstance(selected, dict) or not selected.get("local_path"):
        return None
    source = Path(str(selected["local_path"]))
    if not source.is_file():
        return None
    asset_dir = root / str(watch.get("asset_dir", "assets/reel/official-social"))
    asset_dir.mkdir(parents=True, exist_ok=True)
    destination = asset_dir / f"{watch['id']}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    selected = {**selected, "local_path": str(destination.relative_to(root))}
    spec_path_text = str(((watch.get("trigger") or {}).get("spec", "")))
    slug = str(watch.get("slug", ""))
    if spec_path_text:
        spec_path = root / spec_path_text
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            portrait = spec.setdefault("cover", {}).setdefault("portrait", {})
            portrait["image"] = str(destination.relative_to(root))
            portrait["monitor_status"] = "official-high-resolution-photo-found"
            portrait["_photo_why"] = (
                f"按需监控取得本场官方原图；来源 {selected.get('post_url', '')}；"
                f"{selected.get('width', 0)}×{selected.get('height', 0)}；"
                f"署名 {selected.get('credit', 'unknown')}。"
            )
            portrait.pop("frame_at", None)
            portrait.pop("_frame_why", None)
            portrait.pop("_low_res_why", None)
            spec_path.write_text(
                json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            slug = slug or str(spec.get("slug", ""))
        except (OSError, ValueError, TypeError):
            pass
    result = {
        "schema_version": 1,
        "watch_id": watch["id"],
        "status": "ready",
        "selected": selected,
        "source_status": report.get("source_status", []),
        "checked_at": report.get("checked_at", ""),
        "slug": slug,
        "next_action": "dispatch-match-reel-cover" if slug else "manual-cover-review",
    }
    result_path = root / str(
        watch.get(
            "result_file",
            f"data/official_social_image_results/{watch['id']}.json",
        )
    )
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result_path


def build_manifest(
    candidates: Iterable[OfficialImage], *, minimum_long_edge: int = 1600
) -> dict:
    rows = list(candidates)
    qualified = [
        row
        for row in rows
        if max(row.width, row.height) >= minimum_long_edge and row.current_match
    ]
    return {
        "schema_version": 1,
        "status": "ready" if qualified else "pending-high-resolution-current-match-image",
        "policy": {
            "minimum_long_edge": minimum_long_edge,
            "requires_current_match_evidence": True,
            "frame_grab_fallback": False,
            "rights_note": "public access is not a republication licence; verify before publishing",
        },
        "selected": qualified[0].to_dict() if qualified else None,
        "candidates": [row.to_dict() for row in rows],
    }
