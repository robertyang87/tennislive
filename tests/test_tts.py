"""合语音只有一份出处（`src/tennislive/video/tts.py`，review 路线 ⑥ 第二刀）。

在这之前 reel 和解说片各一套：reel 那套有 Azure 优先、edge-tts 重试、内容缓存；
解说片那套只有 edge-tts、一次重试都没有——而采访线的解读卡口播走的正是后者。
edge-tts 重试那一整套的判据在 tests/test_reel_narration.py（喂假模块真跑），
这儿钉共享模块自己的四头：缓存、错误类型、要风格没 Azure 必须报错、出处只有一份。
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tennislive.video import azure_tts, tts  # noqa: E402


def _fake_synth(calls):
    def synth(text, path, voice, rate, pitch, style, styledegree, lead_pause, *, error):
        calls.append(text)
        path.write_bytes(b"mp3")
        return [{"offset": 0, "duration": 1, "text": text}]
    return synth


def test_同文同参数命中缓存不重合成_错误类型按调用方给的抛(tmp_path, monkeypatch):
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path / "cache"))
    calls: list[str] = []
    a = tts.tts_one("一句", tmp_path / "a.mp3", "v", "+0%", synth=_fake_synth(calls))
    b = tts.tts_one("一句", tmp_path / "b.mp3", "v", "+0%", synth=_fake_synth(calls))
    assert a == b and calls == ["一句"], "第二次要命中缓存"
    assert (tmp_path / "b.mp3").read_bytes() == b"mp3"
    tts.tts_one("另一句", tmp_path / "c.mp3", "v", "+0%", synth=_fake_synth(calls))
    assert calls == ["一句", "另一句"]

    class MyError(RuntimeError):
        pass

    def boom(*a, error, **k):
        raise error("坏了")

    with pytest.raises(MyError, match="坏了"):
        tts.tts_one("再一句", tmp_path / "d.mp3", "v", "+0%", synth=boom, error=MyError)


def test_要风格或气口而没有Azure必须报错不许悄悄退回edge(tmp_path, monkeypatch):
    """spec 明确要了 `voice.style` / `lead_pause` 却没有 Azure：悄悄退回 edge-tts
    等于发一条和 spec 说的不一样的片子——这个仓库最常见的那种坏。"""
    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path / "cache"))
    monkeypatch.setattr(azure_tts, "available", lambda: False)

    class MyError(RuntimeError):
        pass

    with pytest.raises(MyError, match="只有 Azure 那条路有"):
        tts.tts_one("一句", tmp_path / "a.mp3", "v", "+0%", style="excited", error=MyError)
    with pytest.raises(MyError, match="lead_pause"):
        tts.tts_one("一句", tmp_path / "a.mp3", "v", "+0%", lead_pause=0.3, error=MyError)


def test_解说片那条线真的走共享模块_并落words_json(tmp_path, monkeypatch):
    """解说片和采访线的 `synthesize_narration` 从此走 `tts.tts_one`——它们因此
    拿到重试和缓存。⚠️ 缓存命中那条路只拷 mp3，words.json 得由调用方落。"""
    from tennislive.video import explainer as E

    monkeypatch.setenv("TENNISLIVE_TTS_CACHE", str(tmp_path / "cache"))
    seen = []

    def fake(text, path, voice, rate, pitch="+0Hz", style="", styledegree="",
             lead_pause=0.0, *, synth=None, error=tts.TTSError):
        seen.append((text, voice, rate, pitch, error))
        path.write_bytes(b"mp3")
        return [{"offset": 0, "duration": 1, "text": text}]

    monkeypatch.setattr(tts, "tts_one", fake)
    seg = E.ExplainerSegment(kind="x", label="y", title="", narration="第一句。")
    paths = E.synthesize_narration([seg], tmp_path / "v", voice="V", rate="+1%", pitch="+2Hz")
    assert seen and seen[0][1:] == ("V", "+1%", "+2Hz", E.ExplainerVideoError)
    words = json.loads(paths[0].with_suffix(".words.json").read_text(encoding="utf-8"))
    assert words and words[0]["text"] == seen[0][0]


def test_三条出片线里edge_tts的Communicate只许出现在共享模块():
    """出处只有一份：`edge_tts.Communicate(` 不许再出现在 reel / 解说片 / 采访
    这三条出片线里（`tools/voice_sample.py` 那类试音/探针脚本不在此列——它们
    不出片）。写两处必分叉：解说片那份三周里一直没有重试，就是分叉的样子。"""
    files = [ROOT / "tools" / "build_match_reel.py",
             ROOT / "tools" / "build_interview_clip.py",
             *sorted((ROOT / "src" / "tennislive" / "video").glob("*.py"))]
    offenders = []
    for path in files:
        if path.name == "tts.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "Communicate":
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert not offenders, f"这几处自己在调 edge_tts.Communicate：{offenders}"
    shared = (ROOT / "src" / "tennislive" / "video" / "tts.py").read_text(encoding="utf-8")
    assert "edge_tts.Communicate(" in shared, "共享模块自己得真的在合，不然判据是空的"
