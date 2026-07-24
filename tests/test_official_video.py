from pathlib import Path

import pytest

from tennislive.video.official import (
    ATP_YOUTUBE_CHANNEL_ID,
    OFFICIAL_YOUTUBE_CHANNEL_IDS,
    OFFICIAL_YOUTUBE_FEEDS,
    TENNISTV_YOUTUBE_CHANNEL_ID,
    OfficialVideoCandidate,
    OfficialVideoMetadata,
    _curated_chinese_cues,
    _montage_starts,
    _source_cues,
    fetch_youtube_video_metadata,
    fetch_tennistv_video_metadata,
    fetch_wta_video_metadata,
    parse_official_youtube_feed,
    parse_official_youtube_feed_entries,
    parse_tennistv_hot_shot_api_entries,
    parse_tennistv_hot_shot_candidates,
    parse_tennistv_hot_shot_entries,
    parse_wta_video_candidates,
    render_wta_video,
    search_official_youtube_candidates,
    select_wta_video_candidate,
)
from tennislive.video.pipeline import VideoPipelineError


def test_wta_video_candidates_are_deduplicated_and_cleaned():
    page = """
    <a href="/videos/42/champions-reel">Champions Reel: Krejcikova wins <b>Athens</b> Watch Now</a>
    <a href="/videos/42/champions-reel">Duplicate</a>
    <a href="/videos/43/hot-shot">Hot shot: Zheng Qinwen forehand Watch Now</a>
    """

    candidates = parse_wta_video_candidates(page)

    assert [candidate.title for candidate in candidates] == [
        "Champions Reel: Krejcikova wins Athens",
        "Hot shot: Zheng Qinwen forehand",
    ]
    assert candidates[0].url == "https://www.wtatennis.com/videos/42/champions-reel"


def test_search_official_youtube_candidates_keeps_only_verified_channel():
    calls = []

    def searcher(query):
        calls.append(query)
        return {
            "entries": [
                {
                    "id": "official-1",
                    "title": "Hot Shot: Sonego leaves everyone stunned",
                    "channel_id": ATP_YOUTUBE_CHANNEL_ID,
                },
                {
                    "id": "random-1",
                    "title": "Hot Shot: copied clip",
                    "channel_id": "not-official",
                },
            ]
        }

    candidates = search_official_youtube_candidates(
        "Sonego leaves everyone stunned", tour="ATP", searcher=searcher
    )

    assert calls == ["ytsearch8:Sonego leaves everyone stunned"]
    assert [candidate.url for candidate in candidates] == [
        "https://www.youtube.com/watch?v=official-1"
    ]


def test_search_official_youtube_candidates_also_trusts_tennistv_channel_for_atp():
    def searcher(_query):
        return {
            "entries": [
                {
                    "id": "tennistv-1",
                    "title": "Hot Shot: Fritz somehow gets this back",
                    "channel_id": TENNISTV_YOUTUBE_CHANNEL_ID,
                },
                {
                    "id": "random-1",
                    "title": "Hot Shot: reposted clip",
                    "channel_id": "not-official",
                },
            ]
        }

    candidates = search_official_youtube_candidates(
        "Fritz somehow gets this back", tour="ATP", searcher=searcher
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.youtube.com/watch?v=tennistv-1"
    ]


def test_search_official_youtube_candidates_does_not_extend_tennistv_trust_to_wta():
    def searcher(_query):
        return {
            "entries": [
                {
                    "id": "tennistv-1",
                    "title": "Hot Shot: not actually a WTA upload",
                    "channel_id": TENNISTV_YOUTUBE_CHANNEL_ID,
                }
            ]
        }

    candidates = search_official_youtube_candidates(
        "irrelevant", tour="WTA", searcher=searcher
    )

    assert candidates == []


def test_tennistv_hot_shot_cards_keep_match_metadata_and_drop_montages():
    page = r'''
    <article data-slider-props='{ "title": "Borges leaves his opponent applauding",
      "videoUrl": "/videos/12/mallorca-2026-qf-borges-hot-shot", "videoId": "12",
      "mediaId": "0_entry", "description": "Nuno Borges produces a winner in the Mallorca quarter-final.",
      "videoType": "hotshots", "metadataCity": "Mallorca", "metadataYear": "2026",
      "metadataRound": "QF", "metadataSeries": "250", "matchType": "singles",
      "durationSecs": "28", "entitlement": "free", "references": "ATP_MATCH:8994_2026_MS004" }'></article>
    <article data-slider-props='{ "title": "Mallorca 2026 Hot Shot Countdown",
      "videoUrl": "/videos/13/countdown", "videoId": "13", "mediaId": "0_count",
      "description": "Top ten shots", "videoType": "features", "tags": "video-type:features" }'></article>
    '''
    entries = parse_tennistv_hot_shot_entries(page)
    assert len(entries) == 1
    assert entries[0].candidate.url.endswith("/videos/12/mallorca-2026-qf-borges-hot-shot")
    assert entries[0].duration_ms == 28_000
    assert entries[0].references == ("ATP_MATCH:8994_2026_MS004",)
    assert parse_tennistv_hot_shot_candidates(page) == [entries[0].candidate]


def test_tennistv_hot_shot_api_keeps_publication_and_entitlement_metadata():
    entries = parse_tennistv_hot_shot_api_entries(
        {
            "content": [
                {
                    "id": 4542582,
                    "type": "video",
                    "title": "Estoril 2026 R2 Carreno Busta Hot Shot",
                    "description": "A one-handed backhand winner in Estoril.",
                    "date": "2026-07-23T12:52:00Z",
                    "mediaId": "0_8xmxcesy",
                    "duration": 39,
                    "titleUrlSegment": "estoril-2026-r2-carreno-busta-hot-shot",
                    "tags": [
                        {"label": "entitlement:freemium"},
                        {"label": "video-type:hotshots"},
                        {"label": "match-type:singles"},
                        {"label": "series:250"},
                        {"label": "year:2026"},
                    ],
                    "references": [
                        {"type": "ATP_PLAYER", "sid": "CD85"},
                        {"type": "ATP_MATCH", "sid": "7290_2026_MS009"},
                    ],
                    "thumbnail": {
                        "onDemandUrl": "https://img.example/carreno-busta.jpg"
                    },
                    "metadata": {"city": "Estoril", "round": "R2"},
                },
                {
                    "id": 99,
                    "type": "video",
                    "title": "Estoril 2026 Hot Shot Countdown",
                    "description": "A compilation.",
                    "mediaId": "0_montage",
                    "duration": 400,
                    "tags": [{"label": "video-type:hotshots"}],
                },
            ]
        }
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.published_at == "2026-07-23T12:52:00Z"
    assert entry.duration_ms == 39_000
    assert entry.entitlement == "freemium"
    assert entry.series == "250"
    assert entry.match_type == "singles"
    assert entry.references == (
        "ATP_PLAYER:CD85",
        "ATP_MATCH:7290_2026_MS009",
    )
    assert entry.candidate.url.endswith(
        "/4542582/estoril-2026-r2-carreno-busta-hot-shot"
    )


def test_official_youtube_feed_verifies_channel_identity():
    page = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>official-atp</yt:channelId>
      <entry><yt:videoId>abc123</yt:videoId>
        <title>Shot of the day: Player wins a 30-shot rally</title></entry>
    </feed>"""

    candidates = parse_official_youtube_feed(
        page, channel_id="official-atp", tour="ATP"
    )

    assert candidates == [
        OfficialVideoCandidate(
            "Shot of the day: Player wins a 30-shot rally",
            "https://www.youtube.com/watch?v=abc123",
            tour="ATP",
        )
    ]


def test_all_official_upload_feeds_use_verified_upload_playlist_ids():
    assert set(OFFICIAL_YOUTUBE_CHANNEL_IDS) == {
        "ATP",
        "WTA",
        "AO",
        "RG",
        "WIMBLEDON",
        "USOPEN",
    }
    for tour, channel_id in OFFICIAL_YOUTUBE_CHANNEL_IDS.items():
        assert OFFICIAL_YOUTUBE_FEEDS[tour].endswith(
            "playlist_id=UU" + channel_id[2:]
        )


def test_official_youtube_feed_entries_keep_date_description_and_maxres():
    page = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:media="http://search.yahoo.com/mrss/"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>official-atp</yt:channelId>
      <entry><yt:videoId>exact123</yt:videoId>
        <title>Highlights: Sinner vs Djokovic | Hamburg 2026</title>
        <published>2026-07-21T20:15:00+00:00</published>
        <media:group><media:description>Official match highlights.</media:description></media:group>
      </entry>
    </feed>"""

    entries = parse_official_youtube_feed_entries(
        page, channel_id="official-atp", tour="ATP"
    )

    assert len(entries) == 1
    assert entries[0].published_at == "2026-07-21T20:15:00+00:00"
    assert entries[0].description == "Official match highlights."
    assert entries[0].thumbnail_url == (
        "https://i.ytimg.com/vi/exact123/maxresdefault.jpg"
    )


def test_official_youtube_feed_accepts_live_feed_level_id_without_uc_prefix():
    page = f'''<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
          xmlns:yt="http://www.youtube.com/xml/schemas/2015">
      <yt:channelId>{ATP_YOUTUBE_CHANNEL_ID[2:]}</yt:channelId>
      <link rel="alternate" href="https://www.youtube.com/channel/{ATP_YOUTUBE_CHANNEL_ID}"/>
      <entry><yt:videoId>abc123</yt:videoId>
        <title>Shot of the day: Player wins a 30-shot rally</title></entry>
    </feed>'''

    candidates = parse_official_youtube_feed(
        page, channel_id=ATP_YOUTUBE_CHANNEL_ID, tour="ATP"
    )

    assert candidates[0].url == "https://www.youtube.com/watch?v=abc123"


def test_official_youtube_metadata_selects_best_progressive_hd_format():
    candidate = OfficialVideoCandidate(
        "Shot of the day: Player rally",
        "https://www.youtube.com/watch?v=abc123",
        tour="ATP",
    )

    metadata = fetch_youtube_video_metadata(
        candidate,
        info_fetcher=lambda _url: {
            "channel_id": ATP_YOUTUBE_CHANNEL_ID,
            "description": "Official shot of the day.",
            "thumbnail": "https://i.ytimg.com/vi/abc123/maxresdefault.jpg",
            "duration": 24.5,
            "timestamp": 1784682000,
            "formats": [
                {
                    "url": "https://video.example/480.mp4",
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "width": 854,
                    "height": 480,
                    "tbr": 900,
                },
                {
                    "url": "https://video.example/720.mp4",
                    "vcodec": "avc1",
                    "acodec": "mp4a",
                    "width": 1280,
                    "height": 720,
                    "tbr": 2200,
                },
            ],
        },
    )

    assert metadata.playback_url == "https://video.example/720.mp4"
    assert metadata.duration_ms == 24500
    assert (metadata.source_width, metadata.source_height) == (1280, 720)
    assert metadata.published_at.endswith("+00:00")


def test_tennistv_metadata_uses_entitlement_token_without_browser_state():
    candidate = OfficialVideoCandidate(
        "Borges leaves his opponent applauding",
        "https://www.tennistv.com/videos/4526866/mallorca-2026-qf-nuno-borges-hot-shot",
        tour="ATP",
    )

    class Response:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def get(url, **kwargs):
        if url == candidate.url:
            return Response(
                text='''
                <div data-entry-id="0_p5swvkf4"></div>
                <span itemprop="description" content="Nuno Borges produces a winner."></span>
                <span itemprop="thumbnailUrl" content="https://img.example/frame.jpg?width=1920&amp;height=1080"></span>
                <span itemprop="duration" content="PT28S"></span>
                <span itemprop="uploadDate" content="2026-07-21T10:00:00Z"></span>
                '''
            )
        if "entitlementcheck" in url:
            assert kwargs["headers"]["account"] == "atpmedia"
            assert kwargs["headers"]["Authorization"] == "Bearer jwt"
            return Response(payload={"access_token": "stream-token"})
        assert "api.playback.streamamg.com/v1/entry/0_p5swvkf4" in url
        assert kwargs["headers"]["Authorization"] == "Bearer stream-token"
        assert kwargs["headers"]["x-api-key"]
        return Response(
            payload={
                "media": {"hls": "https://video.example/master.m3u8"},
                "duration": "28",
            }
        )

    metadata = fetch_tennistv_video_metadata(candidate, get=get, jwt_token="jwt")
    assert metadata.duration_ms == 28_000
    assert metadata.source_width == 1920
    assert metadata.source_height == 1080
    assert metadata.playback_url == "https://video.example/master.m3u8"


def test_tennistv_metadata_accepts_current_legacy_duration_shape():
    candidate = OfficialVideoCandidate(
        "Mallorca 2026 QF Nuno Borges Hot Shot",
        "https://www.tennistv.com/videos/4526866/mallorca-hot-shot",
        tour="ATP",
    )

    class Response:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def get(url, **kwargs):
        if url == candidate.url:
            return Response(
                text='''
                <div data-entry-id="0_p5swvkf4"></div>
                <span itemprop="duration" content="T28S"></span>
                <span itemprop="uploadDate" content="2026-07-23T10:00:00Z"></span>
                '''
            )
        if "entitlementcheck" in url:
            return Response(payload={"access_token": "stream-token"})
        return Response(
            payload={
                "media": {"hls": "https://video.example/master.m3u8"},
                "duration": "28",
            }
        )

    metadata = fetch_tennistv_video_metadata(candidate, get=get)

    assert metadata.duration_ms == 28_000


def test_tennistv_metadata_refreshes_access_token_for_unattended_action():
    candidate = OfficialVideoCandidate(
        "Estoril 2026 R2 Carreno Busta Hot Shot",
        "https://www.tennistv.com/videos/4542582/estoril-hot-shot",
        tour="ATP",
    )

    class Response:
        def __init__(self, text="", payload=None):
            self.text = text
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def post(url, **kwargs):
        assert url.endswith("/protocol/openid-connect/token")
        assert kwargs["data"] == {
            "client_id": "tennis-tv-web",
            "grant_type": "refresh_token",
            "refresh_token": "refresh-secret",
        }
        return Response(payload={"access_token": "fresh-jwt"})

    def get(url, **kwargs):
        if url == candidate.url:
            return Response(
                text='''
                <div data-entry-id="0_8xmxcesy"></div>
                <span itemprop="duration" content="T39S"></span>
                <span itemprop="uploadDate" content="2026-07-23T12:52:00Z"></span>
                '''
            )
        if "entitlementcheck" in url:
            assert kwargs["headers"]["Authorization"] == "Bearer fresh-jwt"
            return Response(payload={"access_token": "entry-token"})
        assert kwargs["headers"]["Authorization"] == "Bearer entry-token"
        return Response(
            payload={
                "media": {"hls": "https://video.example/estoril.m3u8"},
                "duration": "39",
            }
        )

    metadata = fetch_tennistv_video_metadata(
        candidate,
        get=get,
        post=post,
        refresh_token="refresh-secret",
    )

    assert metadata.playback_url == "https://video.example/estoril.m3u8"
    assert metadata.duration_ms == 39_000


def test_official_youtube_metadata_rejects_video_from_another_channel():
    candidate = OfficialVideoCandidate(
        "Shot of the day: Player rally",
        "https://www.youtube.com/watch?v=abc123",
        tour="ATP",
    )

    with pytest.raises(VideoPipelineError, match="channel identity mismatch"):
        fetch_youtube_video_metadata(
            candidate,
            info_fetcher=lambda _url: {
                "channel_id": "UCnot-the-official-channel",
                "formats": [],
            },
        )


def test_wta_video_selection_matches_player_in_digest(sample_digest):
    candidates = [
        OfficialVideoCandidate("Unrelated match highlights", "https://example.com/1"),
        OfficialVideoCandidate("Zheng Qinwen post-match interview", "https://example.com/2"),
    ]

    selected = select_wta_video_candidate(sample_digest, candidates)

    assert selected == candidates[1]


def test_wta_video_selection_prefers_final_story_for_same_player(sample_digest):
    candidates = [
        OfficialVideoCandidate("Zheng Qinwen hot shot", "https://example.com/1"),
        OfficialVideoCandidate("Zheng Qinwen final highlights", "https://example.com/2"),
    ]

    selected = select_wta_video_candidate(sample_digest, candidates)

    assert selected == candidates[1]


def test_wta_video_selection_prefers_title_match_over_champions_reel(sample_digest):
    candidates = [
        OfficialVideoCandidate(
            "Champions Reel: How Zheng Qinwen won Athens", "https://example.com/1"
        ),
        OfficialVideoCandidate(
            "Zheng Qinwen rallies to claim Athens title over Sakkari",
            "https://example.com/2",
        ),
    ]

    selected = select_wta_video_candidate(sample_digest, candidates)

    assert selected == candidates[1]


def test_wta_metadata_resolves_public_hls_stream():
    candidate = OfficialVideoCandidate(
        "Champions Reel: Krejcikova wins Athens",
        "https://www.wtatennis.com/videos/42/champions-reel",
    )

    class Response:
        def __init__(self, *, text="", payload=None):
            self.text = text
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def get(url, **kwargs):
        if url == candidate.url:
            return Response(
                text=(
                    '&quot;mediaId&quot;:&quot;6401619474112&quot;,'
                    '&quot;description&quot;:&quot;Ninth career title.&quot;,'
                    '&quot;thumbnailUrl&quot;:&quot;https://img.example/poster.jpg&quot;'
                )
            )
        if "players.brightcove.net" in url:
            return Response(text="const key='BCpk" + "a" * 40 + "';")
        return Response(
            payload={
                "duration": 651285,
                "published_at": "2026-07-15T14:00:00Z",
                "sources": [
                    {
                        "type": "video/mp4",
                        "avg_bitrate": 2_000_000,
                        "width": 1920,
                        "height": 1080,
                        "src": "https://cdn.example/full.mp4",
                    },
                    {
                        "type": "application/x-mpegURL",
                        "src": "https://manifest.example/master.m3u8",
                    },
                ],
            }
        )

    metadata = fetch_wta_video_metadata(candidate, get=get)

    assert metadata.playback_url == "https://manifest.example/master.m3u8"
    assert metadata.fallback_url == "https://cdn.example/full.mp4"
    assert metadata.description == "Ninth career title."
    assert metadata.duration_ms == 651285
    assert metadata.published_at == "2026-07-15T14:00:00Z"
    assert (metadata.source_width, metadata.source_height) == (1920, 1080)


def test_render_wta_video_builds_vertical_ffmpeg_command(tmp_path, monkeypatch):
    metadata = OfficialVideoMetadata(
        candidate=OfficialVideoCandidate("Krejcikova wins Athens", "https://example.com"),
        description="She won her ninth career title.",
        thumbnail_url="https://example.com/poster.jpg",
        playback_url="https://manifest.example/master.m3u8",
        duration_ms=651285,
    )
    calls = []

    class Translator:
        def translate(self, cues):
            return {cue.index: "中文重点" for cue in cues}

    monkeypatch.setattr("tennislive.video.official.shutil.which", lambda _: "ffmpeg")
    monkeypatch.setattr("tennislive.video.official.GitHubModelsTranslator", Translator)

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[-1]).write_bytes(b"mp4")

    output = render_wta_video(metadata, tmp_path, runner=runner)

    assert output.name == "official-highlight.mp4"
    assert (tmp_path / "official-highlight.zh-CN.srt").is_file()
    command, kwargs = calls[0]
    assert "scale=1080:1440" in command[command.index("-filter_complex") + 1]
    assert "0:a?" in command
    assert kwargs["timeout"] == 240


def test_video_context_keeps_seed_abbreviation_and_splits_long_sentence():
    metadata = OfficialVideoMetadata(
        candidate=OfficialVideoCandidate("Champions Reel", "https://example.com"),
        description=(
            "No. 3 seed Krejcikova captured her ninth career WTA title, "
            "fourth on outdoor hard courts and first since Wimbledon 2024. "
            "Athens hosted its first WTA event since 1990."
        ),
        thumbnail_url="",
        playback_url="https://example.com/master.m3u8",
        duration_ms=60000,
    )

    cues = _source_cues(metadata, 38)

    assert len(cues) == 4
    assert cues[1].text.startswith("No. 3 seed")
    assert all(cue.text != "No." for cue in cues)
    assert "fourth on outdoor" in cues[2].text


def test_champion_description_becomes_concise_chinese_captions():
    metadata = OfficialVideoMetadata(
        candidate=OfficialVideoCandidate(
            "Champions Reel: How Barbora Krejcikova won Athens 2026",
            "https://example.com",
        ),
        description=(
            "No. 3 seed Barbora Krejcikova captured her ninth career WTA Tour "
            "Driven by Mercedes-Benz title, fourth on outdoor hard courts and first "
            "since Wimbledon 2024. It was the first time a WTA tournament had been "
            "held in Athens since 1990."
        ),
        thumbnail_url="",
        playback_url="https://example.com/master.m3u8",
        duration_ms=60000,
    )

    cues = _curated_chinese_cues(metadata, 38)

    assert cues is not None
    assert [cue.text for cue in cues] == [
        "克雷吉茨科娃｜雅典夺冠之路",
        "生涯第 9 座 WTA 单打冠军",
        "这是她自 2024 年温网后的第一冠",
        "雅典自 1990 年以来首次迎回 WTA 赛事",
    ]


def test_champions_reel_samples_the_whole_source():
    metadata = OfficialVideoMetadata(
        candidate=OfficialVideoCandidate("Champions Reel: Krejcikova wins Athens", "x"),
        description="",
        thumbnail_url="",
        playback_url="https://example.com/master.m3u8",
        duration_ms=651_285,
    )

    starts = _montage_starts(metadata, 38)

    assert starts[0] == 2.0
    assert len(starts) == 4
    assert starts[-1] == 641.785


def test_champions_reel_render_uses_four_segments(tmp_path, monkeypatch):
    metadata = OfficialVideoMetadata(
        candidate=OfficialVideoCandidate("Champions Reel: Krejcikova wins Athens", "x"),
        description=(
            "No. 3 seed Barbora Krejcikova captured her ninth career WTA Tour title, "
            "first since Wimbledon 2024. It was the first time a WTA tournament had "
            "been held in Athens since 1990."
        ),
        thumbnail_url="",
        playback_url="https://example.com/master.m3u8",
        duration_ms=651_285,
    )
    calls = []
    monkeypatch.setattr("tennislive.video.official.shutil.which", lambda _: "ffmpeg")

    def runner(command, **kwargs):
        calls.append(command)
        Path(command[-1]).write_bytes(b"mp4")

    render_wta_video(metadata, tmp_path, runner=runner)

    command = calls[0]
    assert command.count("-i") == 4
    filters = command[command.index("-filter_complex") + 1]
    assert "concat=n=4:v=1:a=1" in filters
    assert "BorderStyle=1" in filters
    assert "BackColour=&H00000000" in filters
    assert "MarginV=28" in filters
