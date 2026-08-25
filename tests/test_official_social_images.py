from __future__ import annotations

import json
from pathlib import Path

from tennislive.research.official_social_images import (
    OfficialImage,
    build_manifest,
    canonicalize_x_image_url,
    deduplicate_candidates,
    discover_post_urls,
    extract_instagram_images,
    extract_usopen_cms_images,
    extract_weibo_sina_images,
    extract_x_images,
    matches_evidence,
    monitor_trigger_ready,
    page_caption,
    persist_selected_result,
    sina_mirror_url,
)


def image(provider: str, *, width: int, height: int, dhash: str, current: bool = True) -> OfficialImage:
    return OfficialImage(
        provider=provider,
        account="US Open",
        post_url="https://example.test/post",
        image_url=f"https://example.test/{provider}.jpg",
        width=width,
        height=height,
        dhash=dhash,
        sha256=provider,
        current_match=current,
    )


def test_weibo_mirror_extracts_large_originals_and_deduplicates() -> None:
    html = r"""
    <img src="https://wx1.sinaimg.cn/middle/006Vgdk4ly1igg0r744ydj3334220e81.jpg">
    <img src="https:\/\/wx1.sinaimg.cn\/mw690\/006Vgdk4ly1igg0r744ydj3334220e81.jpg">
    <img src="https://wx2.sinaimg.cn/wap180/006Vgdk4gy1igg0zgz2rtj3224334b29.jpg">
    """
    rows = extract_weibo_sina_images(html, "https://www.sina.cn/news/detail/5335796288587293.html")
    assert [row.image_url for row in rows] == [
        "https://wx1.sinaimg.cn/large/006Vgdk4ly1igg0r744ydj3334220e81.jpg",
        "https://wx2.sinaimg.cn/large/006Vgdk4gy1igg0zgz2rtj3224334b29.jpg",
    ]
    assert sina_mirror_url("https://weibo.com/6342912608/5335796288587293").endswith(
        "/5335796288587293.html"
    )


def test_x_original_and_profile_post_discovery() -> None:
    url = canonicalize_x_image_url("https://pbs.twimg.com/media/ABC.jpg?format=jpg&name=small")
    assert "name=orig" in url
    rows = extract_x_images(
        r'"media_url_https":"https:\/\/pbs.twimg.com\/media\/GzABC?format=jpg&name=small"',
        "https://x.com/usopen/status/1234567890",
    )
    assert len(rows) == 1
    assert "format=jpg" in rows[0].image_url and "name=orig" in rows[0].image_url
    links = discover_post_urls(
        "official-x",
        r'href="https:\/\/x.com\/usopen\/status\/1234567890"',
        "https://x.com/usopen",
    )
    assert links == ["https://x.com/usopen/status/1234567890"]
    assert discover_post_urls(
        "official-instagram", 'href="/p/ABC_123/"', "https://www.instagram.com/usopen/"
    ) == ["https://www.instagram.com/p/ABC_123/"]


def test_instagram_selects_public_image_renditions_and_caption() -> None:
    html = """
    <meta property="og:description" content="Zheng Qinwen wins qualifying round one">
    <script type="application/ld+json">
    {"image": [
      {"url": "https://scontent.cdninstagram.com/a.jpg", "width": 640, "height": 800},
      {"url": "https://scontent.cdninstagram.com/b.jpg", "width": 1440, "height": 1800}
    ]}
    </script>
    """
    rows = extract_instagram_images(html, "https://www.instagram.com/p/ABC/")
    assert {(row.width, row.height) for row in rows} == {(640, 800), (1440, 1800)}
    assert page_caption(html) == "Zheng Qinwen wins qualifying round one"


def test_usopen_cms_normalizes_large_and_keeps_credit() -> None:
    xml = """
    <photo credit="David Nemec/USTA">Photo credit: David Nemec/USTA</photo>
    <image>https://photo-assets.usopen.org/images/pics/thumb/f_USTA2350382.jpg</image>
    """
    rows = extract_usopen_cms_images(xml, "https://www.usopen.org/gallery.xml")
    assert rows[0].image_url.endswith("/pics/large/f_USTA2350382.jpg")
    assert rows[0].credit.startswith("David Nemec/USTA")


def test_dedup_keeps_4000px_weibo_but_merges_usopen_credit() -> None:
    weibo = image("official-weibo", width=4000, height=2667, dhash="0123456789abcdef")
    cms = image("usopen-cms", width=1280, height=720, dhash="0123456789abcdee")
    cms.credit = "David Nemec/USTA"
    winners = deduplicate_candidates([cms, weibo], chinese_priority=True)
    assert len(winners) == 1
    assert winners[0].provider == "official-weibo"
    assert winners[0].credit == "David Nemec/USTA"
    assert {row["provider"] for row in winners[0].provenance} == {"official-weibo", "usopen-cms"}


def test_manifest_refuses_blurry_or_unverified_current_match_image(tmp_path: Path) -> None:
    blurry = image("official-weibo", width=1280, height=720, dhash="1", current=True)
    old = image("official-weibo", width=4000, height=2667, dhash="2", current=False)
    report = build_manifest([blurry, old])
    assert report["status"] == "pending-high-resolution-current-match-image"
    assert report["selected"] is None
    assert report["policy"]["frame_grab_fallback"] is False


def test_current_match_evidence_requires_both_players() -> None:
    groups = [
        ["Zheng Qinwen", "Qinwen Zheng", "郑钦文"],
        ["You Xiaodi", "Xiaodi You", "尤晓迪", "defeats You"],
    ]
    assert matches_evidence("Zheng Qinwen defeats You in qualifying R1", groups)
    assert not matches_evidence("Zheng Qinwen practices before qualifying", groups)


def test_monitor_only_runs_for_rendered_video_with_provisional_cover(tmp_path: Path) -> None:
    spec = tmp_path / "spec.json"
    render = tmp_path / "render.json"
    spec.write_text('{"cover":{"portrait":{"_low_res_why":"waiting for official photo"}}}')
    watch = {
        "trigger": {
            "type": "video-ready-cover-pending",
            "spec": "spec.json",
            "render_manifest": "render.json",
        },
        "result_file": "result.json",
    }
    assert monitor_trigger_ready(watch, tmp_path) == (False, "video-render-not-ready")
    render.write_text("{}")
    assert monitor_trigger_ready(watch, tmp_path) == (True, "video-ready-cover-pending")
    (tmp_path / "result.json").write_text("{}")
    assert monitor_trigger_ready(watch, tmp_path) == (False, "qualified-image-already-found")


def test_ready_result_replaces_provisional_cover_and_stops_monitor(tmp_path: Path) -> None:
    source = tmp_path / "download.jpg"
    source.write_bytes(b"jpeg-placeholder")
    spec = tmp_path / "spec.json"
    spec.write_text(
        '{"slug":"match-slug","cover":{"portrait":'
        '{"frame_at":12.3,"_frame_why":"temporary","_low_res_why":"temporary"}}}'
    )
    watch = {
        "id": "watch-id",
        "trigger": {"spec": "spec.json"},
        "result_file": "result.json",
        "asset_dir": "assets",
    }
    report = {
        "selected": {
            "local_path": str(source),
            "post_url": "https://x.com/usopen/status/1",
            "width": 4000,
            "height": 2667,
            "credit": "USTA",
        },
        "source_status": [],
        "checked_at": "2026-08-25T00:00:00Z",
    }
    result_path = persist_selected_result(report, watch, tmp_path)
    assert result_path == tmp_path / "result.json"
    updated = json.loads(spec.read_text())
    portrait = updated["cover"]["portrait"]
    assert portrait["image"] == "assets/watch-id.jpg"
    assert "frame_at" not in portrait and "_low_res_why" not in portrait
    result = json.loads(result_path.read_text())
    assert result["next_action"] == "dispatch-match-reel-cover"
