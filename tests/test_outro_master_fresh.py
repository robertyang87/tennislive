"""`tools/build_outro_master.py` 重出母版必须**现渲**，不许从旧母版转码。

2026-09-03 换片尾 slogan 时栽的：`build_with_voice` 母版在就走「从母版转码」
那条近路，而母版工具调的正是它——输入输出同一个文件，ffmpeg 直接报错；
`--out` 指到别处的话它会**成功**产出一份印着旧文案的「新母版」，不报错。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

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


def _ff(*args: str) -> None:
    import subprocess  # noqa: PLC0415
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def _stream_md5(path: Path, stream: str) -> str:
    import subprocess  # noqa: PLC0415
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", f"0:{stream}", "-c", "copy",
         "-f", "md5", "-"], check=True, capture_output=True, text=True).stdout.strip()


def _first_frame_rgb(path: Path) -> tuple[int, int, int]:
    import subprocess  # noqa: PLC0415
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-frames:v", "1", "-vf", "scale=1:1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True).stdout
    return raw[0], raw[1], raw[2]


def _fake_master(dest: Path, colour: str, frames: int, tone: int) -> None:
    _ff("-f", "lavfi", "-i", f"color=c={colour}:s=64x64:r=60",
        "-f", "lavfi", "-i", f"sine=frequency={tone}:sample_rate=48000",
        "-frames:v", str(frames), "-t", f"{frames / 60:.3f}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2", str(dest))


@pytest.mark.parametrize("picture_frames", [30, 29])
def test_母版只换画面时口播逐字节沿用_画面照样现渲(tmp_path, monkeypatch, picture_frames):
    """`--keep-voice`（2026-09-27 修片尾推镜抖动时加的）：只改动效、不改口播时，
    画面**现渲**（`render_clip` 不给 `layers` ＝ 现起 Chromium），口播那一轨从旧母版
    `-c copy`——逐字节不动，「每条片子结尾一模一样的那一下」不用去赌 TTS 这次合得一样。

    三件事一起钉：① 音轨 md5 和旧母版相同；② 画面是新渲的（不是旧母版转码）；
    ③ 帧数对不上就报错、旧母版原样留着（参数化的 29 帧那一组）。
    """
    import shutil  # noqa: PLC0415

    assert shutil.which("ffmpeg"), "没有 ffmpeg，这条判据跑不了：apt install ffmpeg"
    sys.path.insert(0, str(ROOT / "tools"))
    import build_outro_master as bom  # noqa: PLC0415

    master = tmp_path / "outro_master.mp4"
    _fake_master(master, "red", 30, tone=330)
    old_bytes = master.read_bytes()
    old_audio = _stream_md5(master, "a")

    seen: list[dict] = []

    def fake_render_clip(outdir, seconds, **kw):
        seen.append(kw)
        # ⚠️ 音调**必须和旧母版不一样**：同一个音调编出来的 aac 逐字节相同，下面那句
        # md5 断言就成了恒真——把 `-map 1:a:0` 改成拿新画面自带的音轨照样绿（反向验证撞上的）
        _fake_master(kw["dest"], "blue", picture_frames, tone=550)
        return kw["dest"]

    monkeypatch.setattr(bom.outro_page, "render_clip", fake_render_clip)
    monkeypatch.setattr(bom, "_chromium_executable", lambda: "")
    monkeypatch.setattr(bom.localca, "trust_local_proxy_ca", lambda **k: None)
    monkeypatch.setattr(sys, "argv", ["build_outro_master.py", "--keep-voice", "--out", str(master)])

    if picture_frames != 30:
        with pytest.raises(SystemExit, match="帧"):
            bom.main()
        assert master.read_bytes() == old_bytes, "帧数对不上还是把母版改写了"
        return

    assert bom.main() == 0
    assert seen and seen[0].get("layers") is None, (
        f"画面没有现渲（render_clip 拿到了现成的层 / 根本没调）：{seen}")
    assert _stream_md5(master, "a") == old_audio, "口播那一轨不是旧母版逐字节搬过来的"
    r, g, b = _first_frame_rgb(master)
    assert b > 150 and r < 80, f"画面还是旧母版的（首帧 {(r, g, b)}）——那是转码，不是现渲"
    assert not (tmp_path / "_outro_master_work").exists(), "工作目录没清掉"
