#!/usr/bin/env python3
"""Collect official social images for active match watches."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from tennislive.research.official_social_images import (
    build_manifest,
    deduplicate_candidates,
    discover_post_urls,
    download_candidates,
    extract_page,
    matches_evidence,
    monitor_trigger_ready,
    page_caption,
    persist_selected_result,
    sina_mirror_url,
)


def _active(watch: dict, now: datetime) -> bool:
    start = datetime.fromisoformat(watch["active_from"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(watch["active_until"].replace("Z", "+00:00"))
    return start <= now <= end


def _derive_usopen_xml(url: str) -> str:
    if "/news/articles/" not in url or not url.endswith(".html"):
        return url
    path = url.replace("/news/articles/", "/cms/feeds/news/")
    return path[:-5] + ".xml"


def collect(watch_file: Path, output_root: Path, *, now: datetime | None = None) -> int:
    config = json.loads(watch_file.read_text(encoding="utf-8"))
    now = now or datetime.now(timezone.utc)
    client = requests.Session()
    all_reports = []
    for watch in config.get("watches", []):
        if not watch.get("enabled", True) or not _active(watch, now):
            continue
        should_run, trigger_status = monitor_trigger_ready(watch)
        if not should_run:
            print(f"{watch['id']}: skipped ({trigger_status})")
            continue
        target = output_root / watch["id"]
        candidates, source_status = [], []
        for source in watch.get("sources", []):
            provider, url = source["provider"], source["url"]
            if provider == "official-weibo" and "weibo.com" in url:
                url = sina_mirror_url(url)
            if provider == "usopen-cms":
                url = _derive_usopen_xml(url)
            try:
                response = client.get(
                    url, timeout=25, headers={"User-Agent": "Mozilla/5.0"}
                )
                response.raise_for_status()
                pages = [url]
                if source.get("discover_posts"):
                    pages = discover_post_urls(provider, response.text, url)[: int(source.get("max_posts", 8))]
                source_count = 0
                for page_url in pages:
                    page_response = response if page_url == url else client.get(
                        page_url, timeout=25, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    page_response.raise_for_status()
                    found = extract_page(
                        provider,
                        page_response.text,
                        page_url,
                        source.get("account", "US Open"),
                    )
                    caption = source.get("caption") or page_caption(page_response.text)
                    for item in found:
                        item.caption = caption
                        item.current_match = bool(source.get("verified_for_match"))
                    candidates.extend(found)
                    source_count += len(found)
                source_status.append(
                    {
                        "provider": provider,
                        "url": url,
                        "status": "ok",
                        "pages_checked": len(pages),
                        "candidates": source_count,
                    }
                )
            except (requests.RequestException, ValueError) as exc:
                source_status.append(
                    {
                        "provider": provider,
                        "url": url,
                        "status": "blocked-or-unavailable",
                        "error": str(exc)[:240],
                    }
                )
        downloaded = download_candidates(candidates, target / "images", client)
        # Exact post URLs can be operator-verified. Discovered posts instead need
        # their public caption to mention a configured player/match term.
        evidence_groups = watch.get("evidence_groups") or []
        for item in downloaded:
            item.current_match = item.current_match or matches_evidence(
                item.caption + " " + item.post_url, evidence_groups
            )
        winners = deduplicate_candidates(
            downloaded,
            chinese_priority=watch.get("chinese_player_priority", False),
        )
        report = build_manifest(
            winners,
            minimum_long_edge=int(watch.get("minimum_long_edge", 1600)),
        )
        report.update(
            watch_id=watch["id"],
            players=watch.get("players", []),
            event=watch.get("event", ""),
            checked_at=now.isoformat(),
            source_status=source_status,
            trigger_status=trigger_status,
        )
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        all_reports.append(report)
        if report["status"] == "ready":
            persist_selected_result(report, watch)
        print(f"{watch['id']}: {report['status']} ({len(winners)} unique candidates)")
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "index.json").write_text(
        json.dumps(all_reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--watch-file",
        type=Path,
        default=Path("data/official_social_image_watch.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/official-social-images"),
    )
    args = parser.parse_args()
    return collect(args.watch_file, args.output)


if __name__ == "__main__":
    sys.exit(main())
