"""probe 量源片逐块响度，`--dry-run` 按成片口径重放 QC 的数字静音闸（`tools/probe_audio.py`）。

来路：2026-09-06 ~ 09-25 渲后「封面之后还有 N 秒是数字静音」红了 20 趟（162.8 runner
分钟），是失败 run 里的头号；有 probe 的 12 趟 dry-run 一条静音预判都没打出来——probe
的 `silencedetect` 量的是源片峰值（−60 dB），QC 数的是成片逐秒 RMS（现场声 ×0.72），
源片 −60~−57 dB 那一截两边对不上。
"""
from __future__ import annotations

import io
import math
import subprocess
import sys
import wave
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_match_reel as reel  # noqa: E402
import check_reel_landed as qc  # noqa: E402
import probe_audio as pa  # noqa: E402

G = 20 * math.log10(reel.BED_LOUD)       # −2.85 dB
BLOCKS_PER_S = round(1 / pa.BLOCK_SECONDS)


def _levels(plan: list[tuple[float, float]]) -> list[float]:
    """[(秒数, dB)] → 逐块 dB（合成的「量出来的」数）。"""
    out: list[float] = []
    for seconds, db in plan:
        out += [db] * round(seconds * BLOCKS_PER_S)
    return out


def _probe(plan) -> dict:
    return {"url": "U", "silent_audio": [],
            "audio_levels": pa.encode_levels(_levels(plan), reel.QUIETEST_BED_GAIN)}


def _findings(spec: dict, segments, probe: dict, *, cover_exact=reel.COVER_SECONDS,
              cover_estimate=0.0, estimates=None):
    return pa.digital_silence_findings(
        spec, segments, {"U": probe}, {"": "U"}, gain=reel._seg_bed_gain,
        fade=reel.SEG_FADE, cover_exact=cover_exact, cover_estimate=cover_estimate,
        estimates=estimates or {}, est_err=reel.SPEECH_EST_ERR)


# 源片：0–10 响（−25），10–14 是 −58.5（silencedetect 看不见，×0.72 后 −61.4），
# 14–30 响。
QUIET_PLAN = [(10, -25.0), (4, -58.5), (16, -25.0)]


def test_无旁白段按实测重放_必红就硬_认领降成只报():
    seg = reel.Segment(8.0, 18.0, None, "")                  # 冷开场：没旁白
    hard, soft = _findings({"segments": [{}]}, [seg], _probe(QUIET_PLAN))
    assert hard and "（无旁白）" in hard[0] and "必红" in hard[0], (hard, soft)
    # 成片第 4、5 秒 ≈ 源 10.8–12.8，封面 1.2s 起：源 10.0 落在成片 3.2
    assert "成片第 4 秒" in hard[0] and "成片第 5 秒" in hard[0], hard
    claimed = {"segments": [{pa.CLAIM_KEY: "看过，这两秒就是要留白"}]}
    hard2, soft2 = _findings(claimed, [seg], _probe(QUIET_PLAN))
    assert not hard2 and any("已认领" in s for s in soft2), (hard2, soft2)
    # 源片 −56.5（×0.72 → −59.4）够不着 −60：一个字都不许报
    loud = [(10, -25.0), (4, -56.5), (16, -25.0)]
    assert _findings({"segments": [{}]}, [seg], _probe(loud)) == ([], [])


def test_旁白尾巴只报不拦_分必红和大概率两档():
    """R7：旁白尾巴那一类不做硬闸（f7b2501「拿真实产物判」）——实测够得着也只报，
    但要说清是「按最长估也盖不住」还是「按点估盖不住」。"""
    seg = reel.Segment(4.0, 18.0, None, "一句三秒多的旁白。")  # 14 秒的段、旁白 3.5 秒
    probe = _probe([(10, -25.0), (8, -59.5), (12, -25.0)])
    hard, soft = _findings({"segments": [{}]}, [seg], probe, estimates={0: 3.5})
    assert not hard, hard
    assert any("最长估也说不到这儿" in s and "必红" in s for s in soft), soft
    # 整段都被人声盖住（估 14 秒）→ 一个字都不报
    hard, soft = _findings({"segments": [{}]}, [seg], probe, estimates={0: 14.5})
    assert not hard and not soft, (hard, soft)


def test_判不了就出声_老probe_慢放_mute_音乐():
    seg = reel.Segment(8.0, 18.0, None, "")
    old = {"url": "U", "silent_audio": []}                       # 早于 audio_levels
    hard, soft = _findings({"segments": [{}]}, [seg], old)
    assert not hard and any("还没量过" in s for s in soft), soft
    for blind in (reel.Segment(8.0, 12.0, None, "", speed=0.5),
                  reel.Segment(8.0, 18.0, None, "", mute=True)):
        hard, soft = _findings({"segments": [{}]}, [blind], _probe(QUIET_PLAN))
        assert not hard and any("这一层没查" in s for s in soft), (blind, soft)
    hard, soft = _findings({"segments": [{}], "music": {"file": "x"}}, [seg],
                           _probe(QUIET_PLAN))
    assert not hard and any("背景音乐" in s for s in soft)


def test_封面跟着配音走_每个相位都红才硬():
    seg = reel.Segment(8.0, 18.0, None, "")
    # 4 秒的安静：成片里任何相位都至少有一整秒落在里面 → 硬
    hard, soft = _findings({"segments": [{}]}, [seg], _probe(QUIET_PLAN),
                           cover_exact=None, cover_estimate=3.3)
    assert hard and "每个相位都有死秒" in hard[0], (hard, soft)
    # 1.4 秒的安静：只有三成的相位能让一整秒（连两头各一块的余量）落进去 → 只报
    short = [(10, -25.0), (1.4, -70.0), (18.6, -25.0)]
    hard, soft = _findings({"segments": [{}]}, [seg], _probe(short),
                           cover_exact=None, cover_estimate=3.3)
    assert not hard and soft and "换个相位可能躲得过" in soft[0], (hard, soft)


def test_逐块响度只给可能落进死秒的块留数_坏数据不许读成安静():
    levels = _levels(QUIET_PLAN)
    rec = pa.encode_levels(levels, reel.QUIETEST_BED_GAIN)
    back = pa.decode_levels(rec)
    assert len(back) == len(levels) == rec["blocks"]
    assert back[210] == -58.5 and math.isinf(back[0]) and math.isinf(back[-1])
    # 一条通篇正常转播音量的源片，落盘只剩一个游程
    loud = pa.encode_levels(_levels([(300, -30.0)]), reel.QUIETEST_BED_GAIN)
    assert loud["db"] == "L6000"
    # 安静的只有那几截：4 秒安静 → 留数的块是那 80 块加两头各一个窗口
    assert rec["db"].count(" ") < 80 + 2 * round(pa.MASK_WINDOW * BLOCKS_PER_S) + 4
    for bad in ({**rec, "blocks": rec["blocks"] + 1}, {**rec, "block": 0.1},
                {**rec, "db": "x"}, None, "L3"):
        assert pa.decode_levels(bad) is None, bad


def test_dry_run接上了逐块重放_无旁白段撞上就红(monkeypatch):
    spec = {"slug": "t", "source_url": "U",
            "segments": [{"start": 8.0, "end": 18.0, "quote": "Wow\n哇"}]}
    probe = {**_probe(QUIET_PLAN), "duration": 30.0, "scene_cuts": [],
             "point_ends": [], "width": 1920, "height": 1080,
             "fps": "25/1", "fps_value": 25.0}
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: ({"U": probe}, []))
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert reel.probe_dry_run(spec, segs) is True, buf.getvalue()
    assert "按实测源片响度重放 QC" in buf.getvalue()
    # 同一截静音 silence_findings 不许再报一遍（无旁白段让给逐块重放）
    s_hard, s_soft = reel.silence_findings(spec, segs, {"U": {**probe, "silent_audio": [
        [9.0, 15.0]]}}, {"": "U"})
    assert not s_hard and not s_soft, (s_hard, s_soft)
    # 接线：probe 那一趟真把它写进 probe.json
    body = (ROOT / "tools" / "build_match_reel.py").read_text("utf-8")
    assert '"audio_levels": audio_levels,' in body


# ── 真跑一遍 render 的音频链 ────────────────────────────────────────────────────

def _noise(rng, seconds: float, db: float, sr: int, clicks: bool = False):
    import numpy as np  # noqa: PLC0415

    n = int(seconds * sr)
    mono = rng.standard_normal(n)
    spec = np.fft.rfft(mono)
    spec[int(3500 / (sr / 2) * len(spec)):] = 0      # 限带：8 kHz 口径下 RMS 就是 db
    mono = np.fft.irfft(spec, n)
    mono *= 10 ** (db / 20) / np.sqrt((mono ** 2).mean())
    if clicks:           # RMS 低、每 0.3 秒一记 −50 dB 的咔哒——silencedetect 看不见
        for k in range(0, n, int(0.3 * sr)):
            mono[k:k + 20] += 10 ** (-50 / 20) * 1.4
    return np.stack([mono, mono], axis=1)


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def test_真跑一遍混音链_预测的静音秒成片里真的静音(tmp_path):
    """合成源片 → probe 那一趟的 `measure` → render 的真音频链（AAC 分段多切溶解底料
    → `dissolve_filtergraph` → `duck_filtergraph` 混旁白 → AAC）→ QC 的 `per_second_db`。

    判据两头：**预测成硬红的每一秒成片里真的 ≤ −60**（上界，不误报）；无旁白段里
    真的死掉的秒全都预测到了（−58.5 那一截 silencedetect 看不见，这里要看得见）。
    """
    np = pytest.importorskip("numpy")
    sr = 44100
    rng = np.random.default_rng(7)
    plan = [(6, -25.0, False), (3, -58.5, False), (1, -30.0, False),
            (3, -56.5, False), (3, -30.0, False), (3, -59.7, False),
            (2, -28.0, False), (3, -63.0, True), (6, -28.0, False)]
    audio = np.concatenate([_noise(rng, s, db, sr, c) for s, db, c in plan])
    wav = tmp_path / "src.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes())
    src = tmp_path / "src.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=64x64:rate=10:duration={len(audio) / sr}",
            "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(src))

    spans, record = pa.measure(src, quietest_gain=reel.QUIETEST_BED_GAIN)
    assert not any(lo < 8.5 and hi > 6.5 for lo, hi in spans), \
        f"源片 −58.5 那一截 silencedetect 本来就看不见，这条合成素材失效了：{spans}"
    levels = pa.decode_levels(record)
    assert levels is not None

    segs = [reel.Segment(4.0, 12.0, None, ""),                        # 冷开场，无旁白
            reel.Segment(14.0, 24.5, None, "这一句旁白说三秒多一点。"),
            reel.Segment(16.0, 20.0, None, "")]                        # 无旁白
    cover, fade, voice_secs = reel.COVER_SECONDS, reel.SEG_FADE, 3.8
    lengths = [cover] + [s.length for s in segs]
    parts = [tmp_path / "part_cover.mp4"]
    _ffmpeg("-f", "lavfi", "-i", f"color=black:size=64x64:rate=10:duration={cover + fade}",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", f"{cover + fade}", "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(parts[0]))
    for i, s in enumerate(segs):
        tail = fade if i < len(segs) - 1 else 0.0
        parts.append(tmp_path / f"part_{i}.mp4")
        _ffmpeg("-ss", f"{s.start:.3f}", "-i", str(src), "-t", f"{s.length + tail:.3f}",
                "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
                str(parts[-1]))
    joined = tmp_path / "joined.mp4"
    _ffmpeg(*[a for p in parts for a in ("-i", str(p))],
            "-filter_complex", reel.dissolve_filtergraph(lengths, fade),
            "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(joined))
    voice = tmp_path / "voice.mp3"
    _ffmpeg("-f", "lavfi", "-i", f"sine=frequency=300:duration={voice_secs - pa.TTS_TAIL}",
            "-af", f"volume=0.3,apad=pad_dur={pa.TTS_TAIL}", "-t", f"{voice_secs}",
            "-ar", "24000", "-c:a", "libmp3lame", str(voice))
    off = int((cover + segs[0].length) * 1000)
    mixed = tmp_path / "mixed.mp4"
    _ffmpeg("-i", str(joined), "-i", str(voice), "-filter_complex",
            reel.duck_filtergraph([f"[1:a]adelay={off}|{off}[v1]"], ["[v1]"]),
            "-map", "0:v:0", "-map", "[out]", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-ar", "48000", "-shortest", str(mixed))
    real = qc.per_second_db(mixed)
    after = math.ceil(cover) + 1
    real_dead = set(qc.dead_seconds(real, after, [])[0])

    starts = pa.film_starts(segs, cover)
    whole = [a + s.length if s.narration.strip() else a for a, s in zip(starts, segs)]
    strict = pa.predict_levels(segs, {"": levels}, cover, whole, reel._seg_bed_gain, fade)
    predicted = set(qc.dead_seconds(strict, after, [])[0])

    table = "\n".join(f"  {i:3d}s 成片 {db:6.1f}  预测上界 {strict[i]:6.1f}"
                      for i, db in enumerate(real) if i < len(strict))
    assert predicted <= real_dead, f"预测红了、成片没红（误报）：{predicted - real_dead}\n{table}"
    bare = {i for i in real_dead
            if any(a <= i and i + 1 <= a + s.length and not s.narration.strip()
                   for a, s in zip(starts, segs))}
    assert bare <= predicted, f"无旁白段真死了却没预测到：{bare - predicted}\n{table}"
    assert {4, 5} <= predicted, f"源片 −58.5 那一截（成片 4、5 秒）没接住\n{table}"
    assert 8 not in real_dead and 8 not in predicted, f"−56.5 对照组不该红\n{table}"
    for i in predicted:
        assert strict[i] - real[i] >= -0.05, f"第 {i} 秒上界比成片还低：{table}"
