"""`tools/build_outro_master.py` 重出母版必须**现渲**，不许从旧母版转码。

2026-09-03 换片尾 slogan 时栽的：`build_with_voice` 母版在就走「从母版转码」
那条近路，而母版工具调的正是它——输入输出同一个文件，ffmpeg 直接报错；
`--out` 指到别处的话它会**成功**产出一份印着旧文案的「新母版」，不报错。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_母版工具要带fresh现渲_而fresh真的绕过转码近路(tmp_path, monkeypatch):
    from tennislive.video import explainer, outro_page

    # ① 工具真的传了 fresh=True（AST 找那次调用的关键字，注释里提到不算）
    tree = ast.parse((ROOT / "tools" / "build_outro_master.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "build_with_voice"]
    assert calls, "母版工具没调 build_with_voice"
    assert any(k.arg == "fresh" and isinstance(k.value, ast.Constant) and k.value.value is True
               for k in calls[0].keywords), "build_outro_master 没传 fresh=True——重跑出来的还是旧母版"

    # ② 母版在、fresh=True：不许转码，必须走合口播 → 渲页那条路
    fake_master = tmp_path / "master.mp4"
    fake_master.write_bytes(b"old")
    monkeypatch.setattr(outro_page, "MASTER", fake_master)
    calls_seen: list[str] = []

    def fake_synth(segments, outdir, **kw):
        calls_seen.append("tts:" + segments[0].narration)
        p = tmp_path / "v.mp3"
        p.write_bytes(b"mp3")
        return [p]

    monkeypatch.setattr(explainer, "synthesize_narration", fake_synth)
    monkeypatch.setattr(explainer, "_audio_seconds", lambda *a, **k: 3.0)
    monkeypatch.setattr(outro_page, "render_clip",
                        lambda outdir, secs, **kw: calls_seen.append(f"render:{secs}") or kw["dest"])
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: calls_seen.append("transcode") or None)

    dest = tmp_path / "o.mp4"
    outro_page.build_with_voice(tmp_path, chromium="", dest=dest, fps=60.0,
                                audio_rate="48000", preset="slow", crf="12",
                                audio_bitrate="192k", audio_channels=2, fresh=True)
    assert "transcode" not in calls_seen, f"fresh=True 还是从旧母版转码了：{calls_seen}"
    assert calls_seen[0] == "tts:" + outro_page.NARRATION, calls_seen
    assert any(c.startswith("render:") for c in calls_seen), calls_seen

    # ③ 不带 fresh 照旧走近路（那条判据在 test_match_reel 里，这儿只钉方向没反）
    calls_seen.clear()
    outro_page.build_with_voice(tmp_path, chromium="", dest=dest, fps=60.0,
                                audio_rate="48000", preset="slow", crf="12",
                                audio_bitrate="192k", audio_channels=2)
    assert calls_seen == ["transcode"], calls_seen
