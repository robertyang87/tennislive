from pathlib import Path

from tennislive.video.official import (
    OfficialVideoCandidate,
    OfficialVideoMetadata,
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
