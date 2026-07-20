from pathlib import Path

from tennislive.video.official import (
    OfficialVideoCandidate,
    OfficialVideoMetadata,
    _curated_chinese_cues,
    _source_cues,
    fetch_wta_video_metadata,
    parse_wta_video_candidates,
    render_wta_video,
    select_wta_video_candidate,
)


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


def test_wta_video_selection_matches_player_in_digest(sample_digest):
    candidates = [
        OfficialVideoCandidate("Unrelated match highlights", "https://example.com/1"),
        OfficialVideoCandidate("Zheng Qinwen post-match interview", "https://example.com/2"),
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
                "sources": [
                    {"type": "video/mp4", "src": "https://cdn.example/full.mp4"},
                    {
                        "type": "application/x-mpegURL",
                        "src": "https://manifest.example/master.m3u8",
                    },
                ],
            }
        )

    metadata = fetch_wta_video_metadata(candidate, get=get)

    assert metadata.playback_url == "https://manifest.example/master.m3u8"
    assert metadata.description == "Ninth career title."
    assert metadata.duration_ms == 651285


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
