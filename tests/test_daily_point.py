from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import subprocess

import pytest

from tennislive.video.daily_point import (
    PointSelection,
    VideoProbe,
    build_point_ffmpeg_command,
    discover_atp_point,
    discover_slam_point,
    discover_wta_point,
    generate_yesterday_point,
    is_explicit_single_point,
    point_xiaohongshu_copy,
    point_push_html,
    official_best_signal,
    render_daily_point,
    select_daily_point,
    validate_point_copy,
    validate_rendered_point,
    yesterday_matches,
)
from tennislive.video import daily_point as daily_point_module
from tennislive.video.official import OfficialVideoCandidate, OfficialVideoMetadata
from tennislive.video.official import ATP_YOUTUBE_CHANNEL_ID
from tennislive.video.pipeline import VideoPipelineError


def _metadata(
    title="Point of the day: Zheng Qinwen vs Aryna Sabalenka at Wimbledon",
    *,
    description="Zheng Qinwen and Aryna Sabalenka produce the point of the match.",
    published_at="2026-07-15T14:00:00Z",
    duration_ms=28_000,
    width=1920,
    height=1080,
):
    return OfficialVideoMetadata(
        candidate=OfficialVideoCandidate(
            title,
            "https://www.wtatennis.com/videos/123/hot-shot-zheng-qinwen",
        ),
        description=description,
        thumbnail_url="https://images.example/point.jpg",
        playback_url="https://video.example/master.m3u8",
        duration_ms=duration_ms,
        fallback_url="https://video.example/full.mp4",
        published_at=published_at,
        source_width=width,
        source_height=height,
        source_bitrate=3_500_000,
    )


def _selection(sample_digest):
    selected = select_daily_point(sample_digest, [_metadata()])
    assert selected is not None
    return selected


class _Response:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        return None


def test_yesterday_point_requires_proven_beijing_match_date(sample_digest):
    matches = yesterday_matches(sample_digest)

    assert {match.match_id for match in matches} == {"m1", "m2"}
    without_time = replace(sample_digest.results[0], start_utc=None)
    digest = replace(sample_digest, results=[without_time])
    assert yesterday_matches(digest) == []


def test_single_point_gate_rejects_highlight_montages_and_interviews():
    assert is_explicit_single_point("Point of the day: Zheng Qinwen")
    assert is_explicit_single_point("Shot of the match: Zheng Qinwen")
    assert is_explicit_single_point("Hot Shot: Zheng Qinwen forehand")
    assert not is_explicit_single_point("Hot Shot: a 24-shot rally")
    assert not is_explicit_single_point("Best point: Zheng Qinwen")
    assert not is_explicit_single_point("Sensational point: Zheng Qinwen")
    assert not is_explicit_single_point("Match highlights: Zheng vs Sabalenka")
    assert not is_explicit_single_point("Hot Shot top 10 compilation")
    assert not is_explicit_single_point("Post-match interview")


def test_consensus_gate_ranks_daily_match_and_hot_shot_labels():
    assert official_best_signal("Point of the day: Zheng Qinwen") == (
        3,
        "official-daily-best",
    )
    assert official_best_signal("Rally of the match: Zheng vs Sabalenka") == (
        2,
        "official-match-best",
    )
    assert official_best_signal("Play of match: Zheng vs Sabalenka") == (
        2,
        "official-match-best",
    )
    assert official_best_signal("Hot Shot: Zheng Qinwen forehand") == (
        1,
        "official-hot-shot",
    )
    assert official_best_signal("Best point: Zheng Qinwen forehand") is None


def test_selection_needs_official_recent_full_hd_single_point(sample_digest):
    valid = _metadata()
    items = [
        _metadata(title="Match highlights: Zheng vs Sabalenka"),
        _metadata(published_at="2026-07-10T12:00:00Z"),
        _metadata(width=854, height=480),
        _metadata(duration_ms=121_000),
        valid,
    ]

    selection = select_daily_point(sample_digest, items)

    assert selection is not None
    assert selection.metadata == valid
    assert selection.match.match_id == "m2"
    assert selection.source_label == "WTA 官方视频"
    assert selection.consensus_basis == "official-daily-best"
    assert "0 秒到结尾" in selection.complete_point_evidence


def test_selection_rejects_unofficial_and_unlinked_video(sample_digest):
    unofficial = replace(
        _metadata(),
        candidate=OfficialVideoCandidate(
            "Hot Shot: Zheng Qinwen", "https://random.example/video/1"
        ),
    )
    unlinked = _metadata(
        title="Hot Shot: Iga Swiatek",
        description="Iga Swiatek produces the point of the day.",
    )

    assert select_daily_point(sample_digest, [unofficial, unlinked]) is None


def test_selection_accepts_official_hot_shot_without_best_designation(sample_digest):
    generic = _metadata(
        title="Hot Shot: Zheng Qinwen forehand winner at Wimbledon",
        description="Zheng Qinwen vs Aryna Sabalenka produce an incredible point.",
    )

    selected = select_daily_point(sample_digest, [generic])
    assert selected is not None
    assert selected.consensus_basis == "official-hot-shot"
    assert selected.consensus_rank == 1


def test_match_best_is_not_publishable_without_clip_specific_corroboration(
    sample_digest,
):
    match_best = _metadata(
        title="Rally of the match: Qinwen Zheng vs Aryna Sabalenka",
        description="Official rally of the match.",
    )

    assert select_daily_point(sample_digest, [match_best]) is None

    supported_match = replace(
        sample_digest.results[1],
        media_heat=14,
        trend_signals=[
            {
                "kind": "official-news",
                "source": "Reuters",
                "title": "Zheng and Sabalenka light up the semifinal",
                "url": "https://reuters.example/tennis/zheng-sabalenka",
                "published_at": "2026-07-15T16:00:00+00:00",
            }
        ],
    )
    supported_digest = replace(
        sample_digest,
        results=[sample_digest.results[0], supported_match],
    )

    # General match/player coverage is not evidence about this exact rally.
    assert select_daily_point(supported_digest, [match_best]) is None


def test_selection_accepts_verified_atp_official_channel_candidate(sample_digest):
    metadata = replace(
        _metadata(),
        candidate=OfficialVideoCandidate(
            "Shot of the day: Jannik Sinner vs Novak Djokovic at Wimbledon",
            "https://www.youtube.com/watch?v=verified-atp",
            tour="ATP",
        ),
        description="Jannik Sinner and Novak Djokovic produce the shot of the day.",
    )

    selection = select_daily_point(sample_digest, [metadata])

    assert selection is not None
    assert selection.source_label == "ATP Tour 官方视频"


def test_selection_rejects_video_from_the_wrong_tour(sample_digest):
    wrong_tour = replace(
        _metadata(),
        candidate=OfficialVideoCandidate(
            "Shot of the day: Qinwen Zheng wins an incredible point",
            "https://www.youtube.com/watch?v=verified-atp",
            tour="ATP",
        ),
    )

    assert select_daily_point(sample_digest, [wrong_tour]) is None


def test_selection_rejects_ambiguous_one_player_match_link(sample_digest):
    duplicate = replace(
        sample_digest.results[1],
        match_id="m2-later",
        away=[replace(sample_digest.results[1].away[0], name="Iga Swiatek")],
    )
    digest = replace(
        sample_digest,
        results=[*sample_digest.results, duplicate],
    )
    one_player = _metadata(
        title="Point of the day: Zheng Qinwen at Wimbledon",
        description="Official point of the day at Wimbledon.",
    )

    assert select_daily_point(digest, [one_player]) is None


def test_selection_accepts_unique_one_player_plus_event_link(sample_digest):
    one_player = _metadata(
        title="Point of the day: Zheng Qinwen at Wimbledon",
        description="Official point of the day at Wimbledon.",
    )

    selection = select_daily_point(sample_digest, [one_player])

    assert selection is not None
    assert selection.match.match_id == "m2"


def test_selection_accepts_unique_east_asian_display_surname(sample_digest):
    prague = replace(
        sample_digest.results[1],
        match_id="prague-yuan",
        tournament=replace(sample_digest.results[1].tournament, name="Prague Open"),
        home=[
            replace(sample_digest.results[1].home[0], name="Yuan Yue", country="CHN")
        ],
        away=[
            replace(
                sample_digest.results[1].away[0],
                name="Nikola Bartunkova",
                country="CZE",
            )
        ],
    )
    digest = replace(sample_digest, results=[sample_digest.results[0], prague])
    metadata = _metadata(
        title="Point of the day: Yuan vs Bartunkova at Prague Open",
        description="Official Point of the Day from Prague Open.",
    )

    selection = select_daily_point(digest, [metadata])

    assert selection is not None
    assert selection.match.match_id == "prague-yuan"


def test_wta_discovery_uses_official_video_hub(sample_digest):
    page = (
        '<a href="/videos/123/point-of-the-day-zheng">'
        "Point of the day: Qinwen Zheng Watch Now</a>"
    )

    selection = discover_wta_point(
        sample_digest,
        get=lambda *args, **kwargs: _Response(page),
        metadata_fetcher=lambda candidate, **kwargs: replace(
            _metadata(),
            candidate=candidate,
            description=(
                "Qinwen Zheng and Aryna Sabalenka produce the official "
                "point of the day at Wimbledon."
            ),
        ),
    )

    assert selection is not None
    assert selection.metadata.candidate.url.startswith("https://www.wtatennis.com/")


def test_atp_discovery_uses_verified_official_channel_feed(sample_digest):
    feed_id = ATP_YOUTUBE_CHANNEL_ID[2:]
    page = f'''<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>{feed_id}</yt:channelId>
      <entry><yt:videoId>abc123</yt:videoId>
        <title>Shot of the day: Jannik Sinner vs Novak Djokovic at Wimbledon</title></entry>
    </feed>'''

    selection = discover_atp_point(
        sample_digest,
        get=lambda *args, **kwargs: _Response(page),
        metadata_fetcher=lambda candidate: replace(
                _metadata(),
                candidate=candidate,
                description=(
                    "Official shot of the day by Jannik Sinner against "
                    "Novak Djokovic at Wimbledon."
                ),
            ),
    )

    assert selection is not None
    assert selection.metadata.candidate.tour == "ATP"


def test_grand_slam_discovery_requires_current_event_and_match_context(sample_digest):
    from tennislive.video.official import OFFICIAL_YOUTUBE_CHANNEL_IDS

    channel_id = OFFICIAL_YOUTUBE_CHANNEL_IDS["WIMBLEDON"]
    page = f'''<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>{channel_id}</yt:channelId>
      <entry><yt:videoId>wim123</yt:videoId>
        <title>Barclays Play of the Day | Wimbledon 2026</title></entry>
    </feed>'''

    selection = discover_slam_point(
        sample_digest,
        "WIMBLEDON",
        get=lambda *args, **kwargs: _Response(page),
        metadata_fetcher=lambda candidate: replace(
            _metadata(),
            candidate=candidate,
            description=(
                "Jannik Sinner and Novak Djokovic contest the official "
                "Play of the Day at Wimbledon 2026."
            ),
        ),
    )

    assert selection is not None
    assert selection.match.match_id == "m1"
    assert selection.source_label == "温网官方视频"


def test_grand_slam_archive_upload_cannot_attach_to_current_match(sample_digest):
    archive = replace(
        _metadata(),
        candidate=OfficialVideoCandidate(
            "Play of the Day: Jannik Sinner vs Novak Djokovic | Wimbledon 2025",
            "https://www.youtube.com/watch?v=archive",
            tour="WIMBLEDON",
        ),
        description="Official Wimbledon 2025 Play of the Day.",
    )

    assert select_daily_point(sample_digest, [archive]) is None


def test_selection_accepts_portrait_hd_official_source(sample_digest):
    portrait = _metadata(width=1080, height=1920)

    selection = select_daily_point(sample_digest, [portrait])

    assert selection is not None


def test_equal_consensus_leaders_are_skipped_instead_of_guessed(sample_digest):
    wta = _metadata(
        title="Point of the day: Qinwen Zheng",
        description="Official point of the day.",
    )
    atp = replace(
        _metadata(
            title="Point of the day: Jannik Sinner",
            description="Official point of the day.",
        ),
        candidate=OfficialVideoCandidate(
            "Point of the day: Jannik Sinner",
            "https://www.youtube.com/watch?v=verified-atp",
            tour="ATP",
        ),
    )

    assert select_daily_point(sample_digest, [wta, atp]) is None


def test_ffmpeg_keeps_full_16_by_9_foreground_without_tracking_crop(
    sample_digest, tmp_path
):
    selection = _selection(sample_digest)
    command = build_point_ffmpeg_command(
        selection,
        tmp_path / "point.mp4",
        tmp_path / "point.srt",
    )
    filters = command[command.index("-filter_complex") + 1]

    assert "[fg]scale=1080:1440:force_original_aspect_ratio=decrease" in filters
    assert "overlay=(W-w)/2:(H-h)/2" in filters
    assert "subtitles=filename=" in filters
    assert "drawtext" not in filters
    assert "drawbox" not in filters
    assert "sendcmd" not in filters
    assert "cropdetect" not in filters
    assert "-ss" not in command
    assert "-t" not in command


def test_render_writes_context_subtitles_and_passes_quality_gate(
    sample_digest, tmp_path, monkeypatch
):
    selection = _selection(sample_digest)
    calls = []
    monkeypatch.setattr("tennislive.video.daily_point.shutil.which", lambda _: "ffmpeg")

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[-1]).write_bytes(b"x" * 250_000)

    output = render_daily_point(
        selection,
        tmp_path,
        runner=runner,
        prober=lambda _: VideoProbe(1080, 1440, 28.0, 30.0, "h264", 250_000),
    )

    assert output.name == "yesterday-point.mp4"
    subtitle = (tmp_path / "yesterday-point.zh-CN.srt").read_text(encoding="utf-8")
    assert " vs " in subtitle
    assert "赛果" in subtitle
    assert not (tmp_path / "source-overlay.txt").exists()
    assert calls[0][1]["timeout"] == 300


def test_render_retries_progressive_source_after_hls_failure(
    sample_digest, tmp_path, monkeypatch
):
    selection = _selection(sample_digest)
    calls = []
    monkeypatch.setattr("tennislive.video.daily_point.shutil.which", lambda _: "ffmpeg")

    def runner(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise subprocess.CalledProcessError(1, command)
        Path(command[-1]).write_bytes(b"x" * 250_000)

    render_daily_point(
        selection,
        tmp_path,
        runner=runner,
        prober=lambda _: VideoProbe(1080, 1440, 28.0, 30.0, "h264", 250_000),
    )

    assert selection.metadata.playback_url in calls[0]
    assert selection.metadata.fallback_url in calls[1]


def test_quality_gate_rejects_truncated_or_low_frame_rate(sample_digest):
    selection = _selection(sample_digest)

    with pytest.raises(VideoPipelineError, match="未完整保留"):
        validate_rendered_point(
            selection, VideoProbe(1080, 1440, 19.0, 30.0, "h264", 300_000)
        )
    with pytest.raises(VideoPipelineError, match="帧率过低"):
        validate_rendered_point(
            selection, VideoProbe(1080, 1440, 28.0, 20.0, "h264", 300_000)
        )


def test_xiaohongshu_copy_is_one_plain_mobile_paragraph(sample_digest):
    copy = point_xiaohongshu_copy(_selection(sample_digest), date(2026, 7, 16))
    title, body = copy.split("\n\n")

    assert title == "🎾7.16｜这一分，值回放"
    assert "\n" not in body
    assert len(body) <= 280
    assert body.count("？") == 1
    assert "完整回合" in body
    assert "全场比分" in body
    assert "当日最佳" in body
    assert "来源：" not in body
    assert "先猜" not in body
    validate_point_copy(copy)


def test_burned_in_caption_varies_by_clip_but_is_stable_per_clip(sample_digest):
    selection = _selection(sample_digest)
    other = replace(
        selection,
        published_at="2026-01-01T00:00:00Z",
    )

    first_a, second_a = daily_point_module._context_text(selection)
    first_b, second_b = daily_point_module._context_text(selection)
    first_other, second_other = daily_point_module._context_text(other)

    assert (first_a, second_a) == (first_b, second_b)
    assert (first_a, second_a) != (first_other, second_other)
    for line in (first_a, first_other):
        assert " vs " in line
    for line in (second_a, second_other):
        assert "赛果" in line


def test_copy_validator_rejects_three_body_paragraphs():
    with pytest.raises(VideoPipelineError, match="只有一段"):
        validate_point_copy("标题\n\n第一段。\n\n第二段？#网球 #好球 #网球时差")


def test_copy_validator_rejects_public_source_credit():
    with pytest.raises(VideoPipelineError, match="不得显示"):
        validate_point_copy(
            "标题\n\n完整回合，全场比分2比0。你会重看吗？来源：WTA。"
            "#网球 #好球 #网球时差"
        )


def test_push_html_links_video_and_copy_without_public_credit(sample_digest):
    selection = _selection(sample_digest)
    copy = point_xiaohongshu_copy(selection, date(2026, 7, 16))

    rendered = point_push_html(sample_digest, copy)

    assert "/yesterday-point/yesterday-point.mp4" in rendered
    assert "/yesterday-point/copy.html" in rendered
    assert "来源：" not in rendered


def test_package_keeps_consensus_sources_only_in_manifest(
    sample_digest, tmp_path, monkeypatch
):
    selection = _selection(sample_digest)
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest: {"WTA": selection},
    )

    def fake_render(_selection, output_dir):
        output = output_dir / "yesterday-point.mp4"
        output_dir.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        (output_dir / "yesterday-point.zh-CN.srt").write_text(
            "昨日好球", encoding="utf-8"
        )
        return output

    monkeypatch.setattr(
        "tennislive.video.daily_point.render_daily_point", fake_render
    )

    outputs = generate_yesterday_point(sample_digest, tmp_path)

    assert set(outputs) == {"WTA"}
    tour_dir = tmp_path / "wta"
    manifest = json.loads((tour_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"]["url"].startswith("https://www.wtatennis.com/")
    assert manifest["consensus"]["score"] >= 100
    assert manifest["consensus"]["signals"][0]["kind"] == "official-best-designation"
    for public_name in ("xiaohongshu.txt", "copy.html", "push.html"):
        public = (tour_dir / public_name).read_text(encoding="utf-8")
        assert selection.metadata.candidate.url not in public
        assert selection.source_label not in public


def test_generate_publishes_atp_and_wta_independently(sample_digest, monkeypatch, tmp_path):
    wta_selection = _selection(sample_digest)
    atp_selection = replace(
        wta_selection,
        match=replace(sample_digest.results[0]),
    )
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest: {"ATP": atp_selection, "WTA": wta_selection},
    )

    def fake_render(_selection, output_dir):
        output = output_dir / "yesterday-point.mp4"
        output_dir.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        (output_dir / "yesterday-point.zh-CN.srt").write_text(
            "昨日好球", encoding="utf-8"
        )
        return output

    monkeypatch.setattr("tennislive.video.daily_point.render_daily_point", fake_render)

    outputs = generate_yesterday_point(sample_digest, tmp_path)

    assert set(outputs) == {"ATP", "WTA"}
    for tour_dir_name in ("atp", "wta"):
        tour_dir = tmp_path / tour_dir_name
        assert (tour_dir / "yesterday-point.mp4").exists()
        manifest = json.loads((tour_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "pass"
        push_html = (tour_dir / "push.html").read_text(encoding="utf-8")
        assert f"/yesterday-point/{tour_dir_name}/yesterday-point.mp4" in push_html


def test_generate_skips_only_the_tour_with_no_qualifying_clip(
    sample_digest, monkeypatch, tmp_path
):
    wta_selection = _selection(sample_digest)
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest: {"WTA": wta_selection},
    )

    def fake_render(_selection, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / "yesterday-point.mp4"
        output.write_bytes(b"video")
        (output_dir / "yesterday-point.zh-CN.srt").write_text("x", encoding="utf-8")
        return output

    monkeypatch.setattr("tennislive.video.daily_point.render_daily_point", fake_render)

    outputs = generate_yesterday_point(sample_digest, tmp_path)

    assert set(outputs) == {"WTA"}
    assert not (tmp_path / "atp").exists()
