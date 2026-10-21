"""配音自动判据及真实音频解码兼容性（不下载模型、不合成语音）。"""
import shutil
import subprocess
import sys
import types
import wave

import pytest

pytest.importorskip("pypinyin")
import voice_auto_review as auto  # noqa: E402


def test_转写按拼音比_换字表的同音字不算错():
    r = auto.compare_transcript("关注网球时插，时插归我，好球归你。", "关注网球时差,时差归我,好球归你。")
    assert r["ok"] and r["substituted"] == 0


def test_漏读两个字就红():
    r = auto.compare_transcript("决胜盘连下最后四局。", "决胜盘连下四局。")
    assert not r["ok"] and r["deleted"] == 2


def test_句尾被截也红():
    assert not auto.compare_transcript("她救下两个盘点，还连发两记Ace。", "她救下两个盘点，还连")["ok"]


def test_一句话拆进两段合成要报():
    spec = {"segments": [{"narration": "决赛对安德列娃，第二盘四比五落后，"},
                         {"narration": "她救下两个盘点。"}, {"narration": ""},
                         {"narration": "完了。"}]}
    assert [s["segment"] for s in auto.split_sentences(spec)] == [1]


def _entry(text, marks):
    return {"request": {"text": text}, "marks": marks}


def _m(text, start, end):
    return {"text": text, "offset": int(start * 1e7), "duration": int((end - start) * 1e7)}


def test_人名中间停太久要红_标点处停不算():
    marks = [_m("赢了", 0.0, 0.3), _m("萨巴", 0.3, 0.6), _m("伦卡", 0.95, 1.2), _m("然后", 1.6, 1.9)]
    r = auto.pause_and_speed(_entry("赢了萨巴伦卡，然后", marks), ["萨巴伦卡"])
    assert [x["span"] for x in r["inner_pauses"]] == ["萨巴伦卡"]
    marks[2] = _m("伦卡", 0.62, 1.2)
    assert auto.pause_and_speed(_entry("赢了萨巴伦卡，然后", marks), ["萨巴伦卡"])["pause_ok"]


def test_比分中间停顿也算():
    marks = [_m("六", 0.0, 0.2), _m("比", 0.5, 0.7), _m("四", 0.7, 0.9)]
    assert not auto.pause_and_speed(_entry("六比四", marks), [])["pause_ok"]


def test_语速超上限要红():
    text = "一二三四五六七八九十" * 2
    r = auto.pause_and_speed(_entry(text, [_m(text, 0.0, 2.5)]), [])
    assert r["cps"] == 8.0 and not r["speed_ok"]


def test_多音字目标跳过换字表已换掉的字位():
    targets = auto.poly_targets("今天他重新发球。")
    chars = {t["char"] for t in targets}
    assert "重" in chars and "发" in chars
    assert all(t["wrong"] for t in targets)


def test_非默认读音是A档_点名字落在默认读音是B档():
    tiers = {t["char"]: t["tier"] for t in auto.poly_targets("他的头发很长，银行门口。")}
    assert tiers["发"] == "A" and tiers["行"] == "A" and tiers["长"] == "B"


def test_B档只有高置信错读才红_A档量不出也红():
    a = {"tier": "A", "verdict": "uncertain", "runs": []}
    b_unc = {"tier": "B", "verdict": "uncertain", "runs": []}
    b_bad = {"tier": "B", "verdict": "misread", "runs": [{"verdict": "misread", "confidence": "high"}]}
    assert not auto.poly_ok(a) and auto.poly_ok(b_unc) and not auto.poly_ok(b_bad)


def test_转写里的阿拉伯数字按读数或逐位都认():
    assert auto.compare_transcript("二零二六赛季，WTA一千赛全部收官。", "2026赛季,WTA1000赛全部收官。")["ok"]
    assert auto.compare_transcript("决赛七十五分钟横扫莱巴金娜。", "决赛75分钟,横扫来8斤。")["ok"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required")
def test_asr_decodes_real_stereo_mp3_without_pyav_path_adapter(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    # Distinct tones in the two channels reveal accidental stereo flattening,
    # incorrect sample-rate handling, or dropping one input channel.
    t = np.arange(22050) / 44100
    stereo = np.column_stack((0.15 * np.sin(2 * np.pi * 440 * t),
                              0.10 * np.sin(2 * np.pi * 880 * t)))
    wav = tmp_path / "stereo.wav"
    with wave.open(str(wav), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(44100)
        f.writeframes((stereo * 32767).astype("<i2").tobytes())
    mp3 = tmp_path / "actual.mp3"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(wav),
                    "-b:a", "96k", str(mp3)], check=True)
    calls = []

    class FakeWhisper:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, audio, **kwargs):
            # Passing a path here would hit the incompatible PyAV API.
            assert isinstance(audio, np.ndarray)
            assert audio.dtype == np.float32 and audio.ndim == 1
            assert 7920 <= len(audio) <= 8080  # 0.5 seconds at 16 kHz
            assert np.isfinite(audio).all()
            spectrum = np.abs(np.fft.rfft(audio))
            frequency = np.fft.rfftfreq(len(audio), 1 / 16000)
            peaks = frequency[np.argsort(spectrum)[-2:]]
            assert sorted(peaks) == pytest.approx([440, 880], abs=3)
            assert 0.04 < float(np.sqrt(np.mean(audio ** 2))) < 0.11
            assert kwargs["language"] == "zh" and kwargs["beam_size"] == 5
            assert not kwargs["vad_filter"] and not kwargs["condition_on_previous_text"]
            assert "穆霍娃" in kwargs["initial_prompt"]
            assert "不能把这句原文塞进提示" not in kwargs["initial_prompt"]
            calls.append(audio)
            return iter([types.SimpleNamespace(text="第一句。"),
                         types.SimpleNamespace(text=" 第二句。")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=FakeWhisper))
    result = auto.run_asr([{"id": "actual", "mp3": mp3,
                            "request": {"text": "不能把这句原文塞进提示"}}],
                          "small", ["穆霍娃"])
    assert result == {"actual": "第一句。 第二句。"}
    assert len(calls) == 1
