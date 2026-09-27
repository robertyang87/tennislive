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


def test_不闪避那条分支现场声不乘BED_LOUD(monkeypatch):
    """片尾关掉、一句旁白都没有时，render 混音走的是 `-vn -c:a aac` 那条不闪避的分支，
    现场声原样转码——按 `BED_LOUD` 0.72 算会把成片估轻 2.85 dB，反过来误报（评审
    2026-09-27 nit）。源片 −58.5：乘 0.72 是 −61.4（死），原样是 −58.5（不死）。"""
    seg = reel.Segment(8.0, 18.0, None, "")
    assert reel._mix_ducks({"outro": False}, [seg]) is False
    assert reel._mix_ducks({}, [seg]) is True                         # 片尾口播开着
    assert reel._mix_ducks({"outro": False, "cover": {"narration": "一句。"}}, [seg]) is True
    assert reel._mix_ducks({"outro": False}, [reel.Segment(8.0, 18.0, None, "一句。")]) is True
    assert reel._seg_bed_gain(seg, ducked=False) == 1.0
    assert reel._seg_bed_gain(seg) == reel.BED_LOUD
    probe = {**_probe(QUIET_PLAN), "duration": 30.0, "scene_cuts": [], "point_ends": [],
             "width": 1920, "height": 1080, "fps": "25/1", "fps_value": 25.0}
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: ({"U": probe}, []))
    for outro, want in ((True, True), (False, False)):
        spec = {"slug": "t", "source_url": "U", "outro": outro,
                "segments": [{"start": 8.0, "end": 18.0, "quote": "Wow\n哇"}]}
        segs = reel.parse_segments(spec, {"": Path("x")}, "")
        buf = io.StringIO()
        with redirect_stdout(buf):
            got = reel.probe_dry_run(spec, segs)
        assert got is want and ("按实测源片响度重放 QC" in buf.getvalue()) is want, \
            (outro, buf.getvalue())


def test_流式读PCM和一次读完逐块一样(monkeypatch):
    """`measure` 按块流式读 PCM（8678 秒那条源片整条读进内存要顶到约 1.1 GB）——
    读法换了，逐块的数一个都不许变，管道一次只吐几百字节也一样。"""
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(3)
    # 末尾不满一口（7 块）但够 3 块整——流式那条路最容易把这几块丢掉
    pcm = (rng.standard_normal(8000 * 7 + 1234) * 3000).astype(np.int16).tobytes()

    class Trickle(io.BytesIO):
        def read(self, n=-1):
            return super().read(min(n, 333) if n and n > 0 else 333)

    monkeypatch.setattr(pa, "STREAM_BLOCKS", 7)
    for stream in (io.BytesIO(pcm), Trickle(pcm)):
        levels, total = pa.stream_block_levels(stream)
        assert total == len(pcm)
        assert levels == pa.block_levels(pcm)


def test_音轨比画面晚开始的源片_逐块响度按文件时间轴对齐(tmp_path):
    """容器里音轨比画面晚开始（audio start_time > 0）时，裸 PCM 的第 0 个样本是音轨
    自己的第一个样本，而 render 的 `-ss` 按**文件时间轴**寻址——量出来整条错开
    start_time 那么多（实测 56ms，比 ALIGN_SLACK 还宽）。`aresample=first_pts=0` 补齐。"""
    np = pytest.importorskip("numpy")
    sr = 44100
    x = np.zeros(sr * 6)
    x[int(2.0 * sr):int(2.0 * sr) + 4] = 0.9                  # 一记咔哒，别的全是数字静音
    wav = tmp_path / "click.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.stack([x, x], 1) * 32767).astype(np.int16).tobytes())
    src = tmp_path / "late_audio.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=64x64:rate=10:duration=6",
            "-itsoffset", "0.08", "-i", str(wav), "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "128k", str(src))
    start = float(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
         "stream=start_time", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True, check=True).stdout.strip())
    assert start > pa.BLOCK_SECONDS / 2, f"夹具失效：音轨没有晚开始（{start}）"
    # render 那一路：`-ss` 输入寻址切一段，咔哒落在文件时间轴的哪儿
    cut = tmp_path / "cut.mp4"
    _ffmpeg("-ss", "1.000", "-i", str(src), "-t", "2.000", "-map", "0:v:0", "-map", "0:a:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ar", reel.AUDIO_RATE,
            str(cut))
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(cut), "-map", "0:a:0", "-ac", "1",
                          "-ar", reel.AUDIO_RATE, "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    click = 1.0 + int(np.argmax(np.abs(np.frombuffer(raw, np.int16)))) / int(reel.AUDIO_RATE)
    _spans, record = pa.measure(src, quietest_gain=reel.QUIETEST_BED_GAIN)
    loud = [i for i, db in enumerate(pa.decode_levels(record)) if math.isinf(db)]
    assert math.floor(click / pa.BLOCK_SECONDS) in loud, (click, loud)


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


# ── 十几段之后：δ 漂移、段界上的溶解尾巴、响→静的边沿 ─────────────────────────
#
# 评审 2026-09-27 的 BLOCKING：每个 part 的现场声解出来是整数个 AAC 帧，`acrossfade`
# 把它们一路接在「解出来的末尾」上，第 k 段的现场声比画面晚 δ_k——老模型按名义
# 起点算，冷开场后半截「源片刚变静」被判成必红，而成片那一秒里还有几十毫秒的响。
#
# 段长是挑过的（下面 `_long_plan` 自检）：
# - 每段 (L+尾巴)×10 的小数 ≥ 0.25：10 fps 的画面尾巴比补满的 AAC 音轨至少晚 4ms，
#   哪个 ffmpeg 的 `-shortest` 都截不到音轨——夹具里的 δ 就是「补满」那一笔（区间上端）
# - 第 2/4/6 段各有一秒的真实起点落在 0.05 秒格子后 0.5~3ms：在格子前 10ms 放一道 −2 dB
#   的响→静边沿。量源片时格子后面那块是干净的，而成片多过三代 AAC，编码器把响的能量
#   往后抹过了格子——ALIGN_SLACK 归零，模型只读格子后面那块，上界就被打穿
LONG_LENS = [4.55, 4.37, 7.01, 4.45, 6.36, 5.41, 4.88, 6.67, 5.29, 4.41, 7.10, 5.77, 4.99, 6.09]
LONG_NARRATED = {1, 5, 8}
LONG_FPS = 10


def _long_plan():
    """段、源片响度的安排、以及每一处专门压着的那一秒。"""
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    segs = [reel.Segment(3.0 + 10 * k, 3.0 + 10 * k + length, None,
                         "这一段有旁白。" if k in LONG_NARRATED else "")
            for k, length in enumerate(LONG_LENS)]
    for length in LONG_LENS:
        assert round((length + fade) * LONG_FPS % 1, 6) >= 0.25, length

    # 夹具的几何**自己算**，不借被测的 `film_starts`／`audio_drift`——否则拆掉 δ 的
    # 那一刀先把夹具摆歪，红在自检上，证明不了模型。画面不截，δ 就是每个 part
    # 「补满最后一帧 AAC」的那一截一路加上去（`-t` 按三位小数写）。
    def filled(t: float) -> float:
        return math.ceil(round(t, 3) * 48000 / 1024 - 1e-9) * 1024 / 48000 - t

    starts, true_delta, t, d = [], [], cover, filled(cover + fade)
    for length in LONG_LENS:
        starts.append(t)
        true_delta.append(d)
        t += length
        d += filled(length + fade)

    def true_src(k: int, second: int) -> float:
        return segs[k].start + second - (starts[k] + true_delta[k])

    loud: list[tuple[float, float, float]] = []          # (源起, 源止, dB)，默认 −25
    # A 冷开场（第 0 段）：−59 dB 那一截 silencedetect 看不见，成片第 3、4 秒必须接住
    loud.append((4.0, 7.4, -59.0))
    # E1 第 13 段：名义窗口前 0.12s 起才静——δ_13 ≈ 0.2s，真实窗口里还有 80ms 的响
    e1 = 74
    s_nom = segs[13].start + e1 - starts[13]
    loud.append((s_nom - 0.12, s_nom - 0.12 + 1.3, -72.0))
    # E2 第 9→10 段的接缝落在第 54 秒里：第 9 段本身静到段尾，多切的尾巴（源 +4.50 起）
    # 是 −20 dB 的响——它只在溶解里出现；第 10 段开头一路静
    e2 = 54
    assert starts[10] + true_delta[10] - e2 > 0.5
    loud.append((segs[9].start + 3.3, segs[9].start + 4.50, -72.0))
    loud.append((segs[9].start + 4.50, segs[9].start + 5.0, -20.0))
    loud.append((segs[10].start - 0.3, segs[10].start + 2.5, -72.0))
    # D 第 12 段通段静：区间漂得再宽，第 68、69 秒也必须接住
    loud.append((segs[12].start - 0.5, segs[12].end + 0.8, -72.0))
    # E3 第 2/4/6 段：−2 dB 的响止于格子 B 前 10ms，真实窗口起点在 B 之后 0.5~3ms
    e3 = {2: 11, 4: 23, 6: 35}
    for k, second in e3.items():
        t0 = true_src(k, second)
        edge = math.floor(t0 / pa.BLOCK_SECONDS + 1e-9) * pa.BLOCK_SECONDS
        assert 0.0005 <= t0 - edge <= 0.003, (k, t0)
        loud.append((edge - 0.5, edge - 0.010, -2.0))
        loud.append((edge - 0.010, edge + 2.6, -72.0))
    return segs, starts, loud, {"must_catch": {3, 4, 68, 69}, "e1": e1, "e2": e2,
                                "e3": set(e3.values())}


def _film(tmp_path, segs, loud, voices: dict[int, float]):
    """合成源片 → render 的音频链（和 `cut_segment` 同一组音频参数的 AAC 分段、真
    `dissolve_filtergraph`、真 `duck_filtergraph`）→ 成片。返回 `(源片, 成片)`。"""
    np = pytest.importorskip("numpy")
    sr = 44100
    rng = np.random.default_rng(11)
    dur = max(s.end for s in segs) + 5.0
    n = int(dur * sr)
    mono = rng.standard_normal(n)
    spec = np.fft.rfft(mono)
    spec[int(3500 / (sr / 2) * len(spec)):] = 0
    mono = np.fft.irfft(spec, n)
    mono /= np.sqrt((mono ** 2).mean())
    env = np.full(n, 10 ** (-25 / 20))
    for lo, hi, db in loud:
        env[int(round(lo * sr)):int(round(hi * sr))] = 10 ** (db / 20)
    audio = np.clip(mono * env, -1, 1)
    wav = tmp_path / "src.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.stack([audio, audio], 1) * 32767).astype(np.int16).tobytes())
    src = tmp_path / "src.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=64x64:rate={LONG_FPS}:duration={dur}",
            "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(src))
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    parts = [tmp_path / "part_cover.mp4"]
    _ffmpeg("-f", "lavfi", "-i", f"color=black:size=64x64:rate={LONG_FPS}:duration={cover + fade}",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", f"{cover + fade:.3f}", "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "160k", "-ar", reel.AUDIO_RATE, "-shortest", str(parts[0]))
    for i, s in enumerate(segs):
        tail = fade if i < len(segs) - 1 else 0.0
        parts.append(tmp_path / f"part_{i:02d}.mp4")
        _ffmpeg("-ss", f"{s.start:.3f}", "-i", str(src), "-t", f"{s.length + tail:.3f}",
                "-filter_complex", "[0:v]null[vout]", "-shortest", "-map", "[vout]",
                "-map", "0:a:0", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                "-ar", reel.AUDIO_RATE, str(parts[-1]))
    joined = tmp_path / "joined.mp4"
    _ffmpeg(*[a for p in parts for a in ("-i", str(p))],
            "-filter_complex", reel.dissolve_filtergraph([cover] + [s.length for s in segs], fade),
            "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", reel.AUDIO_RATE,
            str(joined))
    starts = pa.film_starts(segs, cover)
    filters, labels, ins = [], [], []
    for n_in, (k, secs) in enumerate(sorted(voices.items()), start=1):
        voice = tmp_path / f"voice_{k}.mp3"
        _ffmpeg("-f", "lavfi", "-i", f"sine=frequency=300:duration={secs}",
                "-af", "volume=0.3", "-ar", "24000", "-c:a", "libmp3lame", str(voice))
        ins += ["-i", str(voice)]
        off = int(starts[k] * 1000)
        filters.append(f"[{n_in}:a]adelay={off}|{off}[v{k}]")
        labels.append(f"[v{k}]")
    mixed = tmp_path / "mixed.mp4"
    _ffmpeg("-i", str(joined), *ins, "-filter_complex", reel.duck_filtergraph(filters, labels),
            "-map", "0:v:0", "-map", "[out]", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "192k", "-ar", reel.AUDIO_RATE, "-shortest", str(mixed))
    return src, mixed


def test_十几段之后的漂移_段界溶解尾巴_响静边沿_真跑一遍混音链(tmp_path, monkeypatch):
    """14 段真跑一遍 render 的音频链，QC 的 `per_second_db` 量成片。

    判据三条：**预测成死秒的每一秒成片里真的 ≤ −60**（不误报）；专门安排的必接秒
    （冷开场 −59、第 12 段通段静）一秒不漏；**每一个给出了数的秒都不低于成片读数**
    （上界就是上界，不只在死秒上成立）。
    另外两条自检夹具还在压着该压的地方——**模型拆掉 δ、拆掉上一段的溶解尾巴，
    各自在这份夹具上误报**（第 74 秒 / 第 54 秒成片是响的，拆掉的模型说它死了）。
    `ALIGN_SLACK` 归零那一刀靠第 11/23/35 秒的 −2 dB 边沿：模型只读格子后面那块，
    成片里编码器抹过来的能量把上界打穿（实测 0.6~13 dB）——抹多少和编码器版本有关，
    所以不写成自检，改在反向验证里验。
    """
    pytest.importorskip("numpy")
    segs, starts, loud, marks = _long_plan()
    src, mixed = _film(tmp_path, segs, loud, {k: 3.0 for k in LONG_NARRATED})
    _spans, record = pa.measure(src, quietest_gain=reel.QUIETEST_BED_GAIN)
    levels = pa.decode_levels(record)
    assert levels is not None
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    real = qc.per_second_db(mixed)
    after = math.ceil(cover) + 1
    real_dead = set(qc.dead_seconds(real, after, [])[0])
    whole = [a + s.length if s.narration.strip() else a for a, s in zip(starts, segs)]

    def predict():
        table = pa.predict_levels(segs, {"": levels}, cover, whole, reel._seg_bed_gain,
                                  fade, frame_seconds=1 / LONG_FPS)
        return table, set(qc.dead_seconds(table, after, [])[0])

    table, predicted = predict()
    shown = "\n".join(f"  {i:3d}s 成片 {db:6.1f}  预测上界 {table[i]:6.1f}"
                      for i, db in enumerate(real) if i < len(table))
    assert predicted <= real_dead, f"预测红了、成片没红（误报）：{predicted - real_dead}\n{shown}"
    assert marks["must_catch"] <= predicted, \
        f"该接住的死秒没接住：{marks['must_catch'] - predicted}\n{shown}"
    for i, db in enumerate(table):
        if not math.isinf(db) and i < len(real):
            assert db - real[i] >= -0.05, f"第 {i} 秒上界比成片还低：\n{shown}"

    # 自检一：拆掉 δ（按名义起点摆现场声），第 74 秒被误判成死秒——成片那一秒是响的
    assert marks["e1"] not in real_dead, f"夹具失效：第 {marks['e1']} 秒成片本来就死了\n{shown}"
    with monkeypatch.context() as m:
        m.setattr(pa, "audio_drift", lambda segments, *_a: [(0.0, 0.0)] * len(segments))
        assert marks["e1"] in predict()[1], "夹具失效：不算 δ 也没误报，压不住漂移"
    # 自检二：拆掉上一段多切的溶解尾巴，第 54 秒被误判成死秒——尾巴的响在溶解里
    assert marks["e2"] not in real_dead, f"夹具失效：第 {marks['e2']} 秒成片本来就死了\n{shown}"
    with monkeypatch.context() as m:
        m.setattr(pa, "part_audio_seconds", lambda seg, _fade: seg.length)
        assert marks["e2"] in predict()[1], "夹具失效：不算溶解尾巴也没误报"


def test_真的cut_segment解出来的音轨长度落在模型的区间里(tmp_path, monkeypatch):
    """δ 区间的两头都拿**真的** `cut_segment` / `_still_to_clip` 量：解出来的音轨长
    必须落在 `[T + 最少, T + 最多]`（`part_padding`）。25 fps 下 -ss 落在两帧之间时
    `-shortest` 会按画面尾巴截短音轨——(0.31, 1.86) 那一刀在 ffmpeg 6.1 上比「补满」
    少两帧 AAC；只按「补满」算就是这一刀越界。"""
    src = tmp_path / "src25.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=25:duration=5",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=5",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "128k",
            "-shortest", str(src))
    monkeypatch.setattr(reel, "FPS_EXPR", "25")
    monkeypatch.setattr(reel, "FPS", 25.0)

    def decoded(path: Path) -> float:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                              "-ac", "1", "-ar", reel.AUDIO_RATE, "-f", "s16le", "-"],
                             capture_output=True, check=True).stdout
        return len(raw) / 2 / int(reel.AUDIO_RATE)

    seen = []
    for a, b in ((0.31, 1.86), (1.07, 4.25)):
        seg = reel.Segment(a, b, 0.5, "")
        dest = tmp_path / f"part_{a}.mp4"
        reel.cut_segment(src, seg, dest, 1920, None, tail=reel.SEG_FADE)
        t = seg.length + reel.SEG_FADE
        lo, hi = pa.part_padding(t, 1 / 25)
        got = decoded(dest) - t
        seen.append((a, b, round(got * 1000, 1), round(lo * 1000, 1), round(hi * 1000, 1)))
        assert lo - 1e-4 <= got <= hi + 1e-4, seen
    still = tmp_path / "still.png"
    _ffmpeg("-f", "lavfi", "-i", "color=black:size=1080x1440", "-frames:v", "1", str(still))
    cover = reel._still_to_clip(still, tmp_path / "part_cover.mp4",
                                reel.COVER_SECONDS + reel.SEG_FADE)
    t = reel.COVER_SECONDS + reel.SEG_FADE
    lo, hi = pa.part_padding(t, 1 / 25)
    assert lo - 1e-4 <= decoded(cover) - t <= hi + 1e-4
    assert int(reel.AUDIO_RATE) == pa.PART_AUDIO_RATE
