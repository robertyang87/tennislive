import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from tennislive.video.pipeline import (
    GitHubModelsTranslator,
    RightsError,
    VideoPipelineError,
    burn_subtitles,
    load_rights_manifest,
    localize_video,
    parse_srt,
    render_srt,
    translate_cues,
)


SRT = """1
00:00:00,000 --> 00:00:01,500
He saved 2 break points.

2
00:00:01,500 --> 00:00:03,000
That changed the match.
"""


class FakeTranslator:
    def translate(self, cues):
        return {
            cues[0].index: "他挽救了2个破发点。",
            cues[1].index: "这改变了比赛走势。",
        }


def _write_inputs(tmp_path: Path, **overrides):
    video = tmp_path / "interview.mp4"
    video.write_bytes(b"local authorized video")
    subtitles = tmp_path / "interview.en.srt"
    subtitles.write_text(SRT, encoding="utf-8")
    rights = {
        "asset_id": "interview-1",
        "source_file": video.name,
        "rights_basis": "written_permission",
        "rights_holder": "Rights holder",
        "allow_translation": True,
        "allow_republish": True,
        "source_url": "https://example.com/interview",
        "license": "",
        "permission_reference": "permission-email-2026-07-20",
        "attribution": "Video: Rights holder",
        "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
        "expires_at": "2027-07-20",
        "notes": "test",
    }
    rights.update(overrides)
    rights_path = tmp_path / "rights.json"
    rights_path.write_text(json.dumps(rights), encoding="utf-8")
    return video, subtitles, rights_path


def test_srt_round_trip_and_translation_preserve_timing():
    cues = parse_srt(SRT)
    translated = translate_cues(cues, FakeTranslator())

    assert len(cues) == 2
    assert translated[0].text == "他挽救了2个破发点。"
    assert translated[0].start_ms == 0
    assert translated[1].end_ms == 3000
    assert parse_srt(render_srt(translated)) == translated


def test_srt_rejects_overlapping_cues():
    overlapping = SRT.replace("00:00:01,500 --> 00:00:03,000", "00:00:01,400 --> 00:00:03,000")

    with pytest.raises(VideoPipelineError, match="overlaps"):
        parse_srt(overlapping)


def test_rights_manifest_is_bound_to_video_and_checksum(tmp_path):
    video, _, rights_path = _write_inputs(tmp_path)

    manifest = load_rights_manifest(rights_path, video, today=date(2026, 7, 20))

    assert manifest.asset_id == "interview-1"
    other = tmp_path / "other.mp4"
    other.write_bytes(video.read_bytes())
    with pytest.raises(RightsError, match="source_file"):
        load_rights_manifest(rights_path, other, today=date(2026, 7, 20))


def test_rights_manifest_rejects_expired_and_no_derivatives(tmp_path):
    video, _, expired_path = _write_inputs(tmp_path, expires_at="2026-07-19")
    with pytest.raises(RightsError, match="expired"):
        load_rights_manifest(expired_path, video, today=date(2026, 7, 20))

    video, _, nd_path = _write_inputs(
        tmp_path,
        rights_basis="creative_commons",
        license="CC BY-ND 4.0",
        permission_reference="",
    )
    with pytest.raises(RightsError, match="NoDerivatives"):
        load_rights_manifest(nd_path, video, today=date(2026, 7, 20))


def test_github_models_translator_supports_mock_http():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"1": "他挽救了2个破发点。", "2": "这改变了比赛走势。"},
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }

    calls = []

    def post(*args, **kwargs):
        calls.append((args, kwargs))
        return Response()

    translator = GitHubModelsTranslator(token="test-token", post=post)
    result = translator.translate(parse_srt(SRT))

    assert result[1] == "他挽救了2个破发点。"
    assert calls[0][1]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0][1]["json"]["temperature"] == 0.1


def test_translation_rejects_changed_numeric_facts():
    class HallucinatingTranslator:
        def translate(self, cues):
            return {1: "他挽救了3个破发点。", 2: "这改变了比赛走势。"}

    with pytest.raises(VideoPipelineError, match="changed numeric facts"):
        translate_cues(parse_srt(SRT), HallucinatingTranslator())


def test_localize_video_without_burn_writes_srt_and_rights_audit(tmp_path):
    video, subtitles, rights_path = _write_inputs(tmp_path)
    outdir = tmp_path / "output"

    audit = localize_video(
        video_path=video,
        subtitle_path=subtitles,
        rights_path=rights_path,
        output_dir=outdir,
        translator=FakeTranslator(),
        burn=False,
    )

    localized = outdir / "interview.zh-CN.srt"
    assert "挽救了2个破发点" in localized.read_text(encoding="utf-8")
    assert audit["outputs"]["video"] is None
    assert (outdir / "attribution.txt").read_text(encoding="utf-8") == "Video: Rights holder\n"
    saved_audit = json.loads((outdir / "rights-audit.json").read_text(encoding="utf-8"))
    assert saved_audit["source_sha256"] == hashlib.sha256(video.read_bytes()).hexdigest()
    assert saved_audit["rights"]["permission_reference"] == "permission-email-2026-07-20"


def test_burn_subtitles_calls_ffmpeg_without_a_shell(tmp_path, monkeypatch):
    video, subtitles, _ = _write_inputs(tmp_path)
    output = tmp_path / "localized.mp4"
    commands = []
    monkeypatch.setattr("tennislive.video.pipeline.shutil.which", lambda _: "ffmpeg")

    def runner(command, check):
        commands.append((command, check))
        output.write_bytes(b"rendered")

    assert burn_subtitles(video, subtitles, output, runner=runner) == output.resolve()
    command, check = commands[0]
    assert check is True
    assert command[0] == "ffmpeg"
    assert "-vf" in command
    assert "subtitles=filename=" in command[command.index("-vf") + 1]
    assert all(not isinstance(part, Path) for part in command)
