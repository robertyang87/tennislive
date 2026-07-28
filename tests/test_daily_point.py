from dataclasses import replace
from datetime import date
import json
from pathlib import Path
import subprocess

import pytest
import requests

from tennislive.video.daily_point import (
    PointSelection,
    VideoProbe,
    build_point_ffmpeg_command,
    discover_atp_point,
    discover_official_points_by_tour,
    discover_slam_point,
    discover_tennistv_point,
    discover_tennistv_youtube_point,
    discover_wta_point,
    discover_youtube_search_point,
    generate_yesterday_point,
    is_explicit_single_point,
    is_official_highlights,
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
from tennislive.video.official import (
    OfficialVideoCandidate,
    OfficialVideoMetadata,
    TennisTVHotShotEntry,
)
from tennislive.video.official import ATP_YOUTUBE_CHANNEL_ID, TENNISTV_YOUTUBE_CHANNEL_ID
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


def test_hot_shot_gate_matches_hashtag_and_plural_spellings():
    # WTA tags shorts with #HotShot; _clean folds the hashtag into a
    # spaceless token, which the old \bhot\s+shot\b regex could never match.
    assert is_explicit_single_point("#HotShot: Zheng Qinwen flying forehand")
    assert is_explicit_single_point("Hot Shots: Zheng Qinwen at the net")
    assert is_explicit_single_point("hotshot: Zheng Qinwen lob")
    assert official_best_signal("#HotShot: Zheng Qinwen flying forehand") == (
        1,
        "official-hot-shot",
    )
    assert official_best_signal("Hot Shots: Zheng Qinwen at the net") == (
        1,
        "official-hot-shot",
    )
    assert official_best_signal("hotshot: Zheng Qinwen lob") == (
        1,
        "official-hot-shot",
    )


def test_highlights_gate_accepts_recaps_but_not_montages():
    assert is_official_highlights("Match Highlights: Zheng vs Sabalenka")
    assert is_official_highlights("Zheng v Sabalenka | Highlight | Wimbledon")
    assert not is_official_highlights("Top 10 highlights of the season")
    assert not is_official_highlights("Champions Reel highlights")
    assert not is_official_highlights("Post-match interview")
    assert not is_official_highlights("Hot Shot: Zheng Qinwen forehand")


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
    assert official_best_signal("Match Highlights: Zheng vs Sabalenka") == (
        0,
        "official-highlights",
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
    assert selected.category == "point"


def _highlights_metadata(duration_ms=150_000):
    return _metadata(
        title="Match Highlights: Zheng Qinwen vs Aryna Sabalenka | Wimbledon",
        description="Zheng Qinwen beats Aryna Sabalenka in the Wimbledon semifinals.",
        duration_ms=duration_ms,
    )


def test_official_highlights_recap_is_accepted_as_lower_category(sample_digest):
    selection = select_daily_point(sample_digest, [_highlights_metadata()])

    assert selection is not None
    assert selection.category == "highlights"
    assert selection.consensus_rank == 0
    assert selection.consensus_basis == "official-highlights"
    assert selection.consensus_score == 40
    assert selection.consensus_signals[0]["kind"] == "official-highlights"
    assert selection.consensus_signals[0]["scope"] == "highlights"
    assert "官方比赛集锦" in selection.complete_point_evidence
    assert "0 秒到结尾" in selection.complete_point_evidence


def test_highlights_duration_window_is_wider_but_still_bounded(sample_digest):
    # A recap may run up to 180s while a single point stays capped at 120s.
    assert select_daily_point(sample_digest, [_highlights_metadata(181_000)]) is None
    assert select_daily_point(sample_digest, [_metadata(duration_ms=150_000)]) is None
    assert (
        select_daily_point(sample_digest, [_highlights_metadata(150_000)]) is not None
    )


def test_explicit_point_always_outranks_a_highlights_recap(sample_digest):
    selection = select_daily_point(
        sample_digest, [_highlights_metadata(90_000), _metadata()]
    )

    assert selection is not None
    assert selection.category == "point"
    assert selection.consensus_rank == 3


def test_highlights_copy_caption_and_push_use_neutral_wording(sample_digest):
    selection = select_daily_point(sample_digest, [_highlights_metadata()])
    assert selection is not None

    copy = point_xiaohongshu_copy(selection, date(2026, 7, 16))
    title, _body = copy.split("\n\n")
    assert title.startswith("🎾7.16 昨日好球｜")
    assert "官方集锦" in title
    for banned in ("最佳", "封神", "这一分", "神仙球"):
        assert banned not in copy
    validate_point_copy(copy)

    line1, _line2 = daily_point_module._context_text(selection)
    assert "这一分" not in line1

    push = point_push_html(sample_digest, copy, category="highlights")
    assert "官方集锦，完整回放" in push
    assert "这一分，值得回放" not in push


def test_match_best_label_is_publishable_with_its_own_evidence(sample_digest):
    # rank-2 (Point/Rally of the Match) used to be permanently excluded by a
    # double gate (code + workflow jq) even though it is an official editorial
    # designation; it now publishes with its corroborating fields kept.
    match_best = _metadata(
        title="Rally of the match: Qinwen Zheng vs Aryna Sabalenka",
        description="Official rally of the match.",
    )

    selection = select_daily_point(sample_digest, [match_best])

    assert selection is not None
    assert selection.consensus_rank == 2
    assert selection.consensus_basis == "official-match-best"
    assert selection.consensus_score == 85
    assert selection.consensus_signals[0]["kind"] == "official-best-designation"
    assert selection.consensus_signals[0]["scope"] == "match"


def test_daily_best_still_outranks_match_best_and_hot_shot(sample_digest):
    daily = _metadata()
    match_best = _metadata(
        title="Rally of the match: Qinwen Zheng vs Aryna Sabalenka",
        description="Official rally of the match.",
    )
    hot_shot = _metadata(
        title="Hot Shot: Qinwen Zheng forehand at Wimbledon",
        description="Qinwen Zheng against Aryna Sabalenka.",
    )

    selection = select_daily_point(sample_digest, [hot_shot, match_best, daily])

    assert selection is not None
    assert selection.consensus_rank == 3


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


def test_official_feed_falls_back_to_channel_id_twin_on_404(sample_digest):
    # The playlist_id uploads feed 404s (the datacenter-IP symptom seen in the
    # daily skip run); the fetch must retry the channel_id twin, which mirrors
    # the same uploads, so a blocked primary form doesn't silently drop the
    # whole free YouTube path.
    feed_id = ATP_YOUTUBE_CHANNEL_ID[2:]
    page = f'''<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>{feed_id}</yt:channelId>
      <entry><yt:videoId>abc123</yt:videoId>
        <title>Shot of the day: Jannik Sinner vs Novak Djokovic at Wimbledon</title></entry>
    </feed>'''

    calls: list[str] = []

    def get(url, **_kwargs):
        calls.append(url)
        if "channel_id=" in url:
            return _Response(page)
        raise requests.HTTPError("404 Client Error: Not Found")

    selection = discover_atp_point(
        sample_digest,
        get=get,
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
    # Primary (playlist_id) tried first and 404'd, then the channel_id twin.
    assert any("playlist_id=" in u for u in calls)
    assert any("channel_id=" in u for u in calls)


def test_official_feed_raises_when_both_forms_fail(sample_digest):
    # A persistent failure across both feed forms must propagate (recorded as an
    # error in resolver_attempts), not be swallowed into a false "empty".
    def get(_url, **_kwargs):
        raise requests.HTTPError("404 Client Error: Not Found")

    with pytest.raises(requests.RequestException):
        discover_atp_point(sample_digest, get=get)


def test_tennistv_youtube_discovery_uses_its_own_verified_channel_feed(sample_digest):
    feed_id = TENNISTV_YOUTUBE_CHANNEL_ID[2:]
    page = f'''<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>{feed_id}</yt:channelId>
      <entry><yt:videoId>xyz789</yt:videoId>
        <title>Hot Shot: Jannik Sinner vs Novak Djokovic at Wimbledon</title></entry>
    </feed>'''

    selection = discover_tennistv_youtube_point(
        sample_digest,
        get=lambda *args, **kwargs: _Response(page),
        metadata_fetcher=lambda candidate: replace(
            _metadata(),
            candidate=candidate,
            description=(
                "Official Hot Shot by Jannik Sinner against Novak Djokovic at Wimbledon."
            ),
        ),
    )

    assert selection is not None
    assert selection.metadata.candidate.tour == "ATP"
    assert selection.metadata.candidate.url.endswith("xyz789")


def _hot_shot_entry(title, *, url, city=""):
    return TennisTVHotShotEntry(
        candidate=OfficialVideoCandidate(title, url, tour="ATP"),
        video_id="v1",
        entry_id="e1",
        description="",
        thumbnail_url="",
        published_at="2026-07-15T14:00:00Z",
        duration_ms=20_000,
        city=city,
        year="",
        round_name="",
        series="",
        match_type="",
        entitlement="",
        references=(),
    )


def test_tennistv_unknown_city_does_not_bypass_the_event_check(
    sample_digest, monkeypatch
):
    # An empty card city used to corroborate every match ("" is a substring
    # of everything); an unknown city must stay neutral -- the event check
    # and the player hit still decide.
    no_event = _hot_shot_entry(
        "Hot Shot: Jannik Sinner stuns Novak Djokovic",
        url="https://www.tennistv.com/videos/hot-shot-1",
    )
    with_event = _hot_shot_entry(
        "Hot Shot: Jannik Sinner stuns Novak Djokovic at Wimbledon",
        url="https://www.tennistv.com/videos/hot-shot-2",
    )
    monkeypatch.setattr(
        daily_point_module,
        "parse_tennistv_hot_shot_api_entries",
        lambda _payload: [no_event, with_event],
    )

    class _ApiResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    fetched = []

    def fetcher(candidate, **kwargs):
        fetched.append(candidate.title)
        return replace(
            _metadata(),
            candidate=candidate,
            description="Jannik Sinner against Novak Djokovic at Wimbledon.",
        )

    selection = discover_tennistv_point(
        sample_digest,
        get=lambda *args, **kwargs: _ApiResponse(),
        metadata_fetcher=fetcher,
    )

    assert fetched == ["Hot Shot: Jannik Sinner stuns Novak Djokovic at Wimbledon"]
    assert selection is not None
    assert selection.match.match_id == "m1"


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


def test_equal_consensus_leaders_resolve_to_one_deterministic_pick(sample_digest):
    # A full tie used to skip the whole day even though both clips were
    # individually publishable; it now resolves deterministically
    # (published_at desc, then candidate-URL sha1) in any input order.
    base = _metadata()
    mirror = replace(
        base,
        candidate=replace(
            base.candidate,
            url="https://www.wtatennis.com/videos/456/point-of-the-day-zheng",
        ),
    )

    first = select_daily_point(sample_digest, [base, mirror])
    second = select_daily_point(sample_digest, [mirror, base])

    assert first is not None
    assert first == second
    assert first.metadata.candidate.url in {
        base.candidate.url,
        mirror.candidate.url,
    }


def test_tie_break_prefers_the_newest_published_clip(sample_digest):
    older = _metadata(published_at="2026-07-15T10:00:00Z")
    newer = _metadata(published_at="2026-07-15T18:00:00Z")

    selection = select_daily_point(sample_digest, [older, newer])

    assert selection is not None
    assert selection.published_at == "2026-07-15T18:00:00Z"


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
    assert command.count("-i") == 2
    assert str(daily_point_module.BRAND_ICON_PATH) in command
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


def test_quality_gate_canvas_error_reports_the_real_output_constants(sample_digest):
    # The message must quote OUTPUT_WIDTH x OUTPUT_HEIGHT (1080x1440), not a
    # stale hard-coded 1080x1920.
    selection = _selection(sample_digest)
    expected = f"{daily_point_module.OUTPUT_WIDTH}x{daily_point_module.OUTPUT_HEIGHT}"

    with pytest.raises(VideoPipelineError, match=expected):
        validate_rendered_point(
            selection, VideoProbe(1080, 1920, 28.0, 30.0, "h264", 300_000)
        )


def test_xiaohongshu_copy_is_scannable_multiline_post(sample_digest):
    copy = point_xiaohongshu_copy(_selection(sample_digest), date(2026, 7, 16))
    title, body = copy.split("\n\n")
    lines = [line for line in body.splitlines() if line.strip()]

    # House style: emoji, date, column name, then a short highlight.
    assert title.startswith("🎾7.16 昨日好球｜")
    highlight = title.split("｜", 1)[1]
    assert len(highlight) <= 12
    assert "最佳" in highlight  # rank 3 may claim the day's best
    # Short: a hook line, one context line, the tags -- not a dense block.
    assert 2 <= len(lines) <= 4
    assert len(body) <= 240
    assert body.count("？") <= 1
    assert "赛果" in body
    assert "来源：" not in body
    assert lines[-1].startswith("#")
    validate_point_copy(copy)


def test_xiaohongshu_copy_grounds_title_and_hook_in_official_shot(sample_digest):
    # When the official text names the shot, the short title leads with it and
    # the hook features it as 制胜分 -- not a generic line.
    base = _selection(sample_digest)
    meta = replace(
        base.metadata,
        candidate=replace(
            base.metadata.candidate,
            title="Hot Shot: Carreno Busta hits a one-handed backhand winner",
        ),
    )
    copy = point_xiaohongshu_copy(replace(base, metadata=meta), date(2026, 7, 24))
    title, body = copy.split("\n\n")
    assert title.startswith("🎾7.24 昨日好球｜单手反拍，")
    assert "单手反拍" in body
    assert "制胜分" in body


def test_xiaohongshu_copy_varies_by_clip_not_one_fixed_script(sample_digest):
    base = _selection(sample_digest)
    # Different clips (distinct match id + publish time) should land on
    # different phrasings, so the feed doesn't repeat one canned script.
    variants = {
        point_xiaohongshu_copy(
            replace(base, published_at=f"2026-07-1{i}T0{i}:00:00Z"),
            date(2026, 7, 16),
        ).split("\n\n")[1]
        for i in range(1, 8)
    }
    assert len(variants) >= 3
    # Same clip is still stable across calls.
    again = _selection(sample_digest)
    assert point_xiaohongshu_copy(base, date(2026, 7, 16)) == point_xiaohongshu_copy(
        again, date(2026, 7, 16)
    )


def test_youtube_search_tries_multiple_label_phrasings_per_match(sample_digest):
    calls = []

    def fake_searcher(query, *, tour, limit):
        calls.append((query, tour, limit))
        return []

    discover_youtube_search_point(sample_digest, searcher=fake_searcher)

    # Two yesterday singles (one ATP, one WTA) x two label phrasings each.
    assert len(calls) == 4
    assert all(limit == 8 for _, _, limit in calls)
    queries = [q for q, _tour, _limit in calls]
    assert sum("hot shot" in q for q in queries) == 2
    assert sum("point of the day" in q for q in queries) == 2


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


def test_copy_validator_rejects_extra_body_blocks():
    with pytest.raises(VideoPipelineError, match="标题加一个正文块"):
        validate_point_copy("标题\n\n第一段。\n\n第二段？#网球 #好球 #网球时差")


def test_copy_validator_rejects_single_line_body():
    with pytest.raises(VideoPipelineError, match="2 至 4 行"):
        validate_point_copy("标题\n\n赛果 2-0，就这一分。 #网球 #好球 #网球时差")


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
        lambda _digest, **_kwargs: {"WTA": selection},
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
    assert manifest["category"] == "point"
    assert manifest["consensus"]["score"] >= 100
    assert manifest["consensus"]["signals"][0]["kind"] == "official-best-designation"
    # The copy's grounding is recorded so any shot claim is auditable against
    # the raw official text rather than taken on trust.
    assert manifest["source_description"] == selection.metadata.description
    assert manifest["copy_grounding"]["basis"] in {
        "official-shot",
        "official-match",
        "fallback",
    }
    for public_name in ("xiaohongshu.txt", "copy.html", "push.html"):
        public = (tour_dir / public_name).read_text(encoding="utf-8")
        assert selection.metadata.candidate.url not in public
        assert selection.source_label not in public


def test_manifest_records_shot_grounding_for_audit(sample_digest, tmp_path, monkeypatch):
    base = _selection(sample_digest)
    # Mirror the real Estoril case: the stored title is a generic slug and the
    # shot is named only in the description field.
    meta = replace(
        base.metadata,
        candidate=replace(
            base.metadata.candidate, title="Estoril 2026 R2 Carreno Busta Hot Shot"
        ),
        description="Carreno Busta hits a stunning one-handed backhand winner down the line.",
    )
    selection = replace(base, metadata=meta)
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest, **_kwargs: {"WTA": selection},
    )

    def fake_render(_selection, output_dir):
        output = output_dir / "yesterday-point.mp4"
        output_dir.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        (output_dir / "yesterday-point.zh-CN.srt").write_text("x", encoding="utf-8")
        return output

    monkeypatch.setattr("tennislive.video.daily_point.render_daily_point", fake_render)

    generate_yesterday_point(sample_digest, tmp_path)
    manifest = json.loads(
        (tmp_path / "wta" / "manifest.json").read_text(encoding="utf-8")
    )
    grounding = manifest["copy_grounding"]
    assert grounding["basis"] == "official-shot"
    assert grounding["shot"] == "单手反拍"
    assert grounding["shot_as_winner"] is True
    assert "one-handed backhand" in manifest["source_description"].lower()


def test_highlights_package_manifest_marks_category_and_neutral_push(
    sample_digest, tmp_path, monkeypatch
):
    selection = select_daily_point(sample_digest, [_highlights_metadata()])
    assert selection is not None
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest, **_kwargs: {"WTA": selection},
    )

    def fake_render(_selection, output_dir):
        output = output_dir / "yesterday-point.mp4"
        output_dir.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"video")
        (output_dir / "yesterday-point.zh-CN.srt").write_text("x", encoding="utf-8")
        return output

    monkeypatch.setattr("tennislive.video.daily_point.render_daily_point", fake_render)

    generate_yesterday_point(sample_digest, tmp_path)

    tour_dir = tmp_path / "wta"
    manifest = json.loads((tour_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["category"] == "highlights"
    assert manifest["consensus"]["rank"] == 0
    assert manifest["consensus"]["score"] == 40
    assert manifest["consensus"]["basis"] == "official-highlights"
    assert manifest["consensus"]["signals"][0]["kind"] == "official-highlights"
    assert "官方比赛集锦" in manifest["consensus"]["evidence"]
    # A recap never grounds copy in one shot claim.
    assert manifest["copy_grounding"]["basis"] in {"official-match", "fallback"}
    assert manifest["copy_grounding"]["shot"] == ""
    push_html = (tour_dir / "push.html").read_text(encoding="utf-8")
    assert "官方集锦，完整回放" in push_html
    assert "这一分，值得回放" not in push_html
    xiaohongshu = (tour_dir / "xiaohongshu.txt").read_text(encoding="utf-8")
    assert "官方集锦" in xiaohongshu
    assert "最佳" not in xiaohongshu


def test_discovery_records_per_resolver_attempts_and_failures(
    sample_digest, monkeypatch
):
    # The resolver loop keeps swallowing exceptions so one broken feed cannot
    # sink the others, but each swallowed failure must land in diagnostics so
    # a skip run can persist why every source produced nothing.
    def broken(_digest, **_kwargs):
        raise VideoPipelineError("hub down")

    for name in (
        "discover_tennistv_point",
        "discover_wta_point",
        "discover_wta_youtube_point",
        "discover_atp_point",
        "discover_tennistv_youtube_point",
        "discover_youtube_search_point",
    ):
        monkeypatch.setattr(daily_point_module, name, broken)
    monkeypatch.setattr(
        daily_point_module, "discover_slam_point", lambda _digest, _tour, **_kwargs: None
    )

    diagnostics = {}
    picks = discover_official_points_by_tour(sample_digest, diagnostics=diagnostics)

    assert picks == {}
    attempts = diagnostics["resolver_attempts"]
    assert len(attempts) == 10
    errors = [item for item in attempts if item["status"] == "error"]
    assert len(errors) == 6
    assert all("hub down" in item["error"] for item in errors)
    empty = [item for item in attempts if item["status"] == "empty"]
    assert {item["resolver"] for item in empty} == {
        "discover_slam_point:AO",
        "discover_slam_point:RG",
        "discover_slam_point:WIMBLEDON",
        "discover_slam_point:USOPEN",
    }


def test_generate_records_switch_state_for_honest_skip_reason(
    sample_digest, tmp_path, monkeypatch
):
    monkeypatch.delenv("TENNISLIVE_YESTERDAY_POINT", raising=False)
    diagnostics = {}

    outputs = generate_yesterday_point(
        sample_digest, tmp_path, diagnostics=diagnostics
    )

    assert outputs == {}
    assert diagnostics["enabled"] is False
    assert "resolver_attempts" not in diagnostics


def test_generate_publishes_atp_and_wta_independently(sample_digest, monkeypatch, tmp_path):
    wta_selection = _selection(sample_digest)
    atp_selection = replace(
        wta_selection,
        match=replace(sample_digest.results[0]),
    )
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest, **_kwargs: {"ATP": atp_selection, "WTA": wta_selection},
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
        lambda _digest, **_kwargs: {"WTA": wta_selection},
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


def test_generate_does_not_redo_a_tour_already_marked_done(
    sample_digest, monkeypatch, tmp_path
):
    atp_selection = replace(
        _selection(sample_digest), match=replace(sample_digest.results[0])
    )
    wta_selection = _selection(sample_digest)
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest, **_kwargs: {"ATP": atp_selection, "WTA": wta_selection},
    )
    rendered = []

    def fake_render(_selection, output_dir):
        rendered.append(output_dir.name)
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / "yesterday-point.mp4"
        output.write_bytes(b"video")
        (output_dir / "yesterday-point.zh-CN.srt").write_text("x", encoding="utf-8")
        return output

    monkeypatch.setattr("tennislive.video.daily_point.render_daily_point", fake_render)

    outputs = generate_yesterday_point(
        sample_digest, tmp_path, skip_tours=frozenset({"ATP"})
    )

    assert set(outputs) == {"WTA"}
    assert rendered == ["wta"]


def test_generate_skips_discovery_when_every_tour_already_done(
    sample_digest, monkeypatch, tmp_path
):
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")
    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        lambda _digest, **_kwargs: (_ for _ in ()).throw(
            AssertionError("should not query sources when both tours are already done")
        ),
    )

    outputs = generate_yesterday_point(
        sample_digest, tmp_path, skip_tours=frozenset({"ATP", "WTA"})
    )

    assert outputs == {}


def test_discovery_ledger_records_no_match_gap(sample_digest):
    # A source that fetched a labelled clip but nothing named a yesterday
    # player must leave an auditable "0 matched" line, not a silent skip.
    page = (
        '<a href="/videos/9/point-of-the-day">'
        "Point of the day: Somebody Nobody Watch Now</a>"
    )
    report: list[dict] = []

    selection = discover_wta_point(
        sample_digest,
        get=lambda *args, **kwargs: _Response(page),
        metadata_fetcher=lambda candidate, **kwargs: _metadata(),
        report=report,
    )

    assert selection is None
    assert len(report) == 1
    entry = report[0]
    assert entry["source"] == "WTA 官方视频（官网）"
    assert entry["fetched"] == 1
    assert entry["matched"] == 0
    assert entry["picked"] is False
    assert "0 条命中" in entry["note"]
    assert entry["error"] == ""


def test_discovery_ledger_records_a_picked_line(sample_digest):
    page = (
        '<a href="/videos/123/point-of-the-day-zheng">'
        "Point of the day: Qinwen Zheng Watch Now</a>"
    )
    report: list[dict] = []

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
        report=report,
    )

    assert selection is not None
    assert report[0]["source"] == "WTA 官方视频（官网）"
    assert report[0]["matched"] == 1
    assert report[0]["picked"] is True


def test_resolver_attempts_fold_in_fetched_matched_counts(sample_digest, monkeypatch):
    # An erroring source is recorded as an error; a source that fetched clips
    # but matched nothing carries fetched/matched so "empty" separates a real
    # no-material day (fetched N, matched 0) from a broken feed (fetched 0).
    import tennislive.video.daily_point as dp

    def boom(_digest, report=None):
        raise dp.VideoPipelineError("feed HTTP 500")

    def gap(_digest, report=None):
        dp._record_source(report, "STUB", fetched=5, matched=0, picked=False)
        return None

    monkeypatch.setattr(dp, "discover_tennistv_point", boom)
    for name in (
        "discover_wta_point",
        "discover_wta_youtube_point",
        "discover_atp_point",
        "discover_tennistv_youtube_point",
        "discover_youtube_search_point",
    ):
        monkeypatch.setattr(dp, name, gap)
    monkeypatch.setattr(
        dp, "discover_slam_point", lambda _digest, _tour, report=None: None
    )

    diagnostics: dict = {}
    picks = dp.discover_official_points_by_tour(sample_digest, diagnostics=diagnostics)

    assert picks == {}
    attempts = diagnostics["resolver_attempts"]
    errored = [a for a in attempts if a.get("status") == "error"]
    assert errored and errored[0]["source"] == dp._SRC_TENNISTV
    assert "feed HTTP 500" in errored[0]["error"]
    # The five non-raising stubs each folded in fetched=5/matched=0 -- the
    # signal that separates a real gap from a broken source.
    gaps = [
        a
        for a in attempts
        if a.get("status") == "empty" and a.get("fetched") == 5 and a.get("matched") == 0
    ]
    assert len(gaps) == 5


def test_generate_threads_diagnostics(sample_digest, tmp_path, monkeypatch):
    monkeypatch.setenv("TENNISLIVE_YESTERDAY_POINT", "on")

    def fake_discover(_digest, *, diagnostics=None):
        assert diagnostics is not None
        diagnostics["resolver_attempts"] = [
            {"resolver": "stub", "source": "STUB", "status": "empty",
             "fetched": 0, "matched": 0}
        ]
        return {}

    monkeypatch.setattr(
        "tennislive.video.daily_point.discover_official_points_by_tour",
        fake_discover,
    )

    diagnostics: dict = {}
    outputs = generate_yesterday_point(
        sample_digest, tmp_path, diagnostics=diagnostics
    )

    assert outputs == {}
    assert diagnostics["enabled"] is True
    assert diagnostics["resolver_attempts"][0]["source"] == "STUB"
