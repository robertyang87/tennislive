"""名人堂致辞复用赛后开麦版式，但不得伪造比赛、对手或冷开场。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_interview_request as request_builder  # noqa: E402
import build_interview_clip as clip_builder  # noqa: E402
import interview_source_gate as gate  # noqa: E402
from check_interview_landed import bilingual_lead_ok  # noqa: E402


def _request() -> dict:
    return {
        "slug": "federer-ithf-2026-induction-speech",
        "url": "https://www.youtube.com/watch?v=fQXTNAnY0zE",
        "source": "Tennis Channel",
        "source_title": (
            "Roger Federer International Tennis Hall of Fame Induction Speech | "
            "ITHF 2026"
        ),
        "requested_content_type": "ceremony",
        "ceremony_subtype": "hall_of_fame_induction",
        "interview_kind": "名人堂入选致辞",
        "event": "2026 国际网球名人堂入选典礼",
        "featured_player": "费德勒",
        "subject": {
            "id": "2026:ithf:induction:roger-federer",
            "event": "2026 国际网球名人堂入选典礼",
            "name": "费德勒",
            "role": "入选者",
        },
        "opening": {"kind": "none", "why": "按编辑决定从完整致辞第一句开始"},
        "cover": {
            "frame_at": 30.0,
            "title": ["名人堂叫作 Fame", "但成名从不是目标"],
            "sub": "费德勒 · 完整入选致辞",
            "tag": "2026 纽波特 · 费德勒",
        },
        "takeaway": {"close": {"point": "这仍不是告别", "ask": "哪句话最打动你？"}},
        "push": {"matchup": "费德勒", "summary": "费德勒名人堂完整致辞", "auto": True},
    }


def test_官方名人堂入选致辞标题被识别为ceremony():
    assert gate.explicit_title_type(_request()["source_title"]) == "ceremony"


def test_名人堂正式契约绑定人物而不是伪造比赛():
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    assert spec["interview_kind"] == "名人堂入选致辞"
    assert spec["match"] == {}
    assert spec["subject"]["name"] == "费德勒"
    assert spec["source_verification"]["subject_id"] == spec["subject"]["id"]
    assert gate.content_identity_id(spec) == spec["subject"]["id"]
    assert len(gate.validate_source_contract(spec)) == 64


def test_名人堂人物身份被篡改会使L0失效():
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    spec["subject"]["name"] = "另一位球员"
    with pytest.raises(gate.SourceContractError, match="L0 attestation"):
        gate.validate_source_contract(spec)


def test_名人堂顶栏不需要对手和比分(monkeypatch):
    monkeypatch.setattr(clip_builder, "_measure_at", lambda kind, size, text: len(text) * size)
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    assert clip_builder.header_lines(spec) == (
        "2026 国际网球名人堂入选典礼",
        "费德勒 · 名人堂入选致辞",
    )


def test_已核验入选典礼可以按编辑决定不用冷开场(tmp_path):
    spec = request_builder.build_spec(_request(), ["谢谢大家"], duration=900.0)
    ok, detail = bilingual_lead_ok(tmp_path / "missing.ass", spec)
    assert ok and "显式例外" in detail


def test_一次性重建标记会让已有spec重新进入队列(tmp_path, monkeypatch):
    request_dir = tmp_path / "requests"
    specs = tmp_path / "specs"
    output = tmp_path / "output"
    request_dir.mkdir()
    specs.mkdir()
    (output / "demo").mkdir(parents=True)
    path = request_dir / "demo.json"
    path.write_text(
        '{"slug":"demo","url":"https://youtu.be/x","_rebuild_once":true}',
        encoding="utf-8",
    )
    (specs / "demo.json").write_text("{}", encoding="utf-8")
    (output / "demo" / "cap_asr.json3").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(request_builder, "SPECS", specs)
    monkeypatch.setattr(request_builder, "OUTDIR", output)
    assert request_builder.is_pending(path)


def test_人工请求在翻译前与渲染使用同一套语气词清理(tmp_path, monkeypatch):
    import build_interview_clip
    import draft_interview_spec

    path = tmp_path / "demo.json"
    path.write_text('{"slug":"demo","url":"https://youtu.be/x"}', encoding="utf-8")
    monkeypatch.setattr(
        request_builder,
        "_transcribe_request",
        lambda url, directory, model: ([{"t": 0.0, "text": "Um hello"}], 2.0),
    )
    monkeypatch.setattr(
        build_interview_clip,
        "segment",
        lambda words, start, end, budget=None: [
            {"a": 0.0, "b": 1.0, "en": "Um hello"}
        ],
    )
    seen = []

    def fake_translate(rows, chat, max_zh_chars=None):
        seen.extend(row["text"] for row in rows)
        assert max_zh_chars is None
        return ["你好"]

    monkeypatch.setattr(draft_interview_spec, "translate", fake_translate)
    monkeypatch.setattr(request_builder, "build_spec", lambda req, zh, duration: {})
    request_builder._build_one(path, object(), write=False)
    assert seen == ["Hello"]


def test_人工请求渲染优先复用已持久化的第一份ASR(tmp_path, monkeypatch):
    cap = {
        "events": [{
            "tStartMs": 1000,
            "segs": [{"utf8": "Hello", "tOffsetMs": 250}],
        }]
    }
    (tmp_path / "cap_asr.json3").write_text(
        __import__("json").dumps(cap), encoding="utf-8"
    )
    monkeypatch.setattr(
        clip_builder.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("已有第一份 ASR 时不应再下载 YouTube 字幕"),
    )
    words = clip_builder.fetch_words(
        "https://youtu.be/fQXTNAnY0zE", tmp_path, {"asr_model": "small.en"}
    )
    assert words == [(1.25, "Hello")]


def test_长致辞翻译提示会硬性限制单行中文长度():
    import draft_interview_spec

    prompt = draft_interview_spec._translation_system_prompt(13)
    assert "最多 13 个字符" in prompt
    assert "不得通过漏译事实来缩短" in prompt
