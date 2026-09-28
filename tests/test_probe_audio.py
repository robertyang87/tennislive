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
              cover_estimate=0.0, estimates=None, strict=False, measured=None,
              reprobe=None):
    return pa.digital_silence_findings(
        spec, segments, {"U": probe}, {"": "U"}, gain=reel._seg_bed_gain,
        fade=reel.SEG_FADE, cover_exact=cover_exact, cover_estimate=cover_estimate,
        estimates=estimates or {}, est_err=reel.SPEECH_EST_ERR, strict=strict,
        measured=measured, reprobe=reprobe)


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


#: 源片 11–14.5 秒安静（×0.72 后 −62.4），段 4–18 放在封面 1.2 之后 → 成片 8.2–11.7 安静
TIGHT_PLAN = [(11, -25.0), (3.5, -59.5), (15.5, -25.0)]


def test_旁白尾巴_上包络之外手写硬_自动只报_点估那一截指到check_narration():
    """2026-09-28：渲后「数字静音」红了 16 趟（117 runner 分钟），渲前 0 趟拦住，50 个
    死秒里 37 个在旁白说完之后。旁白**按上包络也说不到**的那一秒，成片里就是现场声本身
    ——手写 spec 硬，自动 spec 只报；点估和上包络之间那一截离线估判不了，只报并给出
    `--check-narration` 的原命令。"""
    seg = reel.Segment(4.0, 18.0, None, "一句三秒多的旁白。")  # 14 秒的段、旁白估 3.5 秒
    probe = _probe([(10, -25.0), (8, -59.5), (12, -25.0)])     # 源 10–18 安静
    spec = {"slug": "t", "segments": [{}]}
    # 上包络 3.5×1.1＋2.2−0.83 ≈ 5.2 秒，安静从段内 6 秒起 → 必红
    hard, soft = _findings(spec, [seg], probe, estimates={0: 3.5}, strict=True)
    assert hard and "上包络也说不到这儿" in hard[0] and "必红" in hard[0], (hard, soft)
    assert "成片第 8 秒" in hard[0], hard
    # 自动产的 spec：同一截只报
    hard, soft = _findings(spec, [seg], probe, estimates={0: 3.5}, strict=False)
    assert not hard and any("上包络也说不到这儿" in s and "只报" in s for s in soft), soft
    # 认领过：降成只报
    claimed = {"slug": "t", "segments": [{pa.CLAIM_KEY: "看过，这一截就要留白"}]}
    hard, soft = _findings(claimed, [seg], probe, estimates={0: 3.5}, strict=True)
    assert not hard and any("已认领" in s for s in soft), soft
    # 点估盖不住、上包络盖得住：只报，并给出 --check-narration 的原命令
    # （估 7.5 秒：点估说到成片 7.9、上包络说到 10.8；安静在成片 8.2–11.7）
    hard, soft = _findings(spec, [seg], _probe(TIGHT_PLAN), estimates={0: 7.5}, strict=True)
    assert not hard, hard
    assert any("大概率红" in s and "render --check-narration --spec specs/reels/t.json" in s
               for s in soft), soft
    # 整段都被人声盖住（估 14 秒）→ 一个字都不报
    hard, soft = _findings(spec, [seg], probe, estimates={0: 14.5}, strict=True)
    assert not hard and not soft, (hard, soft)


def test_合过真语音就按真长度判_点估那一档不再报():
    """`--check-narration` 那一头：真语音说到哪儿是确定的，手写 spec 按它硬。"""
    seg = reel.Segment(4.0, 18.0, None, "一句旁白。")
    probe = _probe(TIGHT_PLAN)                                # 成片 8.2–11.7 安静
    spec = {"slug": "t", "segments": [{}]}
    # 离线估 7.5 秒：只报「大概率」
    hard, soft = _findings(spec, [seg], probe, estimates={0: 7.5}, strict=True)
    assert not hard and soft
    # 真语音说到段内 6.2 秒（成片 7.4）→ 第 9、10 秒整秒安静，必红
    hard, soft = _findings(spec, [seg], probe, estimates={0: 7.5}, strict=True,
                           measured={0: 6.2})
    assert hard and "按真语音，旁白说到段内 6.20s" in hard[0], (hard, soft)
    assert "成片第 9 秒" in hard[0] and "成片第 10 秒" in hard[0], hard
    assert not any("大概率红" in s for s in soft), soft
    # 真语音说满到 13.9 秒 → 什么都不报
    assert _findings(spec, [seg], probe, estimates={0: 7.5}, strict=True,
                     measured={0: 13.9}) == ([], [])


def test_上包络盖得住每一段真语音():
    """`speech_ceiling` 是硬的那一档的全部前提：它要是比真 mp3 短，一秒还在说话的
    就会被判成死秒。冻结的是 2026-09-28 从 main 上 3921 段真 mp3（render.json 的
    `narration_seconds`）里挑出来**最贴上包络**的几段——edge-tts 是 runner 现在走的
    后端，慢得和句长成正比，平移的 `est + SPEECH_EST_ERR` 盖不住 43 秒那一段。"""
    for backend, slug, index, chars, latin, punct, lead, real in _CEILING_FIXTURE:
        est = reel.speech_seconds("一" * chars + "a" * latin + "，" * punct) + lead
        ceiling = pa.speech_ceiling(est, reel.SPEECH_EST_ERR)
        assert real <= ceiling, (backend, slug, index, real, ceiling)
        # azure 的 mp3 尾巴没量过有多长：按一点静音都没有算，也得盖得住
        if backend != "edge-tts":
            assert real <= ceiling - pa.TTS_TAIL, (backend, slug, index, real, ceiling)
    ests = [(reel.speech_seconds("一" * c + "a" * la + "，" * pu) + le, r)
            for _b, _s, _i, c, la, pu, le, r in _CEILING_FIXTURE]
    # 平移不够：有一段超出 est + SPEECH_EST_ERR（斜率不是凑的）
    assert any(r > e + reel.SPEECH_EST_ERR for e, r in ests), ests
    # 也不许虚高：最贴的那段离上包络不到 1 秒（余量宽得离谱，硬的那一档就接不住东西）
    assert min(pa.speech_ceiling(e, reel.SPEECH_EST_ERR) - r for e, r in ests) < 1.0, ests
    # 老的 silent_audio 那道闸（`silence_risk`）「最长估」也走同一个上包络：43 秒那段
    # 按 est+2.2 说到 40.7 秒，真 mp3 43.3 秒——源片 41~45 秒静音时，平移口径会把还在
    # 说话的 2 秒多算成「必红」（对手写 spec 也是硬的）
    (_lo, _hi, certain, _p), = reel.silence_risk(0.0, 50.0, 38.5, [[41.0, 45.0]])
    assert certain < 2.0, certain


#: (后端, slug, 段序号(0 起), 字, 按词念的拉丁字母, 句读, lead_pause, 真 mp3 秒)——
#: 取法和 `test_match_reel._measured_narration` 一样（字／句读／拉丁三维），按「斜率 0.10
#: 时要的常数」从大到小挑的；`pegula-usopen-2026-qf` 第 6 段是超出 est+2.2 最多的一段（+4.85）。
_CEILING_FIXTURE = [
    ("edge-tts", "pegula-usopen-2026-qf", 7, 119, 0, 19, 0.0, 30.24),
    ("edge-tts", "pegula-usopen-2026-qf", 9, 72, 0, 13, 0.0, 19.512),
    ("edge-tts", "sabalenka-noskova-detail", 9, 54, 3, 10, 0.0, 15.36),
    ("edge-tts", "ruud-zverev-doubles-laver-cup-2026", 3, 78, 0, 10, 0.0, 19.44),
    ("edge-tts", "pegula-usopen-2026-qf", 6, 181, 0, 25, 0.0, 43.344),
    ("edge-tts", "zverev-vandezandschulp-us-open-2026-qf", 7, 85, 0, 9, 0.0, 20.16),
    ("edge-tts", "wong-vallejo-hangzhou-2026-r2", 9, 19, 0, 2, 0.0, 5.592),
    ("edge-tts", "zheng-usopen-icons", 13, 31, 0, 8, 0.0, 9.888),
    ("azure", "osaka-four-slams-2026", 18, 28, 0, 3, 0.0, 7.512),
    ("azure", "chwalinska-townsend-us-open-2026-r1", 9, 66, 0, 8, 0.0, 16.15),
    ("?", "eala-pegula-final", 2, 34, 0, 4, 0.0, 8.808),
]


def test_整屏证据段按QC的口径豁免_跨出窗口的那一秒照样数():
    """image／stat_card／title_card 段的底轨是 anullsrc：口播说完之后整秒落在它窗口
    （两头各 0.3 秒）里的，QC 豁免；跨出窗口、压到下一段安静开头的那一秒，QC 照样数。
    原来整屏段一律整段遮住，那一秒永远判不到（asiad-2026-women-draw 那一类）。"""
    card = reel.Segment(0.0, 4.2, 0.5, "一句口播。", image="card.png")
    tail = reel.Segment(10.5, 16.5, None, "")                  # 无旁白、源片开头就安静
    probe = _probe([(10, -25.0), (8, -70.0), (12, -25.0)])      # 源 10–18 安静
    spec = {"slug": "t", "segments": [{}, {}]}
    # 封面 1.2：卡 1.2–5.4，口播估 1 秒；下一段 5.4 起
    hard, soft = _findings(spec, [card, tail], probe, estimates={0: 1.0}, strict=True)
    text = "\n".join(hard + soft)
    # 第 5 秒 [5, 6)：0.4 秒在卡里、0.6 秒在下一段安静的开头——QC 数它
    assert "成片第 5 秒" in text, text
    # 第 3、4 秒整秒落在卡的窗口里：QC 豁免，这里也不许报
    assert "成片第 3 秒" not in text and "成片第 4 秒" not in text, text


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


def _tail_spec(**extra) -> tuple[dict, dict]:
    """一段 14 秒、旁白估三秒多的手写 spec ＋ 源 10–18 安静的 probe（上包络之外必红）。"""
    spec = {"slug": "t", "source_url": "U",
            "segments": [{"start": 4.0, "end": 18.0, "narration": "一句三秒多的旁白。"}], **extra}
    probe = {**_probe([(10, -25.0), (8, -59.5), (12, -25.0)]), "duration": 30.0,
             "scene_cuts": [], "point_ends": [], "width": 1920, "height": 1080,
             "fps": "25/1", "fps_value": 25.0}
    return spec, probe


def test_dry_run_旁白尾巴手写硬_自动只报(monkeypatch):
    """`--dry-run` 的接线：手写 spec 旁白按上包络也盖不住的那一秒是硬伤（exit 1 那一路），
    自动产的 spec（`_production.status == ready_for_render`）同一截只报。"""
    for auto, want in ((False, True), (True, False)):
        extra = {"_production": {"status": "ready_for_render"}} if auto else {}
        spec, probe = _tail_spec(**extra)
        monkeypatch.setattr(reel, "probes_for_spec", lambda _s, _p=probe: ({"U": _p}, []))
        segs = reel.parse_segments(spec, {"": Path("x")}, "")
        buf = io.StringIO()
        with redirect_stdout(buf):
            got = reel.probe_dry_run(spec, segs)
        assert got is want, (auto, buf.getvalue())
        assert "上包络也说不到这儿" in buf.getvalue(), buf.getvalue()


def test_check_narration按真语音重放_没认领到probe要出声(monkeypatch):
    """`--check-narration`（runner 的 mode=narration 跑的就是它）把真语音长度喂给同一套
    重放：说到段内 2 秒就停的旁白，后面整秒安静的必红；一份 probe 都认领不上时要说「没查」。"""
    spec, probe = _tail_spec()
    segs = reel.parse_segments(spec, {"": Path("x")}, "")
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: ({"U": probe}, []))
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert reel._check_narration_silence(spec, segs, {0: 2.0}, None) is True
    assert "按真语音，旁白说到段内 2.00s" in buf.getvalue(), buf.getvalue()
    with redirect_stdout(io.StringIO()):
        assert reel._check_narration_silence(spec, segs, {0: 13.95}, None) is False
    monkeypatch.setattr(reel, "probes_for_spec", lambda _s: ({}, [""]))
    buf = io.StringIO()
    with redirect_stdout(buf):
        assert reel._check_narration_silence(spec, segs, {0: 2.0}, None) is False
    assert "这一层没查" in buf.getvalue(), buf.getvalue()
    # 接线：`--check-narration` 真的调它，封面配音也合了（封面长度要真长度，不扫相位）
    body = (ROOT / "tools" / "build_match_reel.py").read_text("utf-8")
    start = body.index("    if args.check_narration:")
    cn = body[start:body.index("    if args.dry_run:", start)]
    assert "_check_narration_silence(" in cn and "synth_cover(" in cn and \
        "voice_speech_end(" in cn, "check-narration 没把真语音喂给数字静音重放"


def test_真语音说完的时刻_按QC同一个量法(tmp_path):
    voice = tmp_path / "v.mp3"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=300:duration=2.0", "-af",
            f"volume=0.3,apad=pad_dur={pa.TTS_TAIL}", "-t", f"{2.0 + pa.TTS_TAIL}",
            "-ar", "24000", "-c:a", "libmp3lame", str(voice))
    end = pa.voice_speech_end(voice)
    assert end is not None and 1.95 <= end <= 2.15, end
    assert pa.voice_speech_end(tmp_path / "missing.mp3") is None


def test_老probe没有逐块响度_照印重probe的原命令(monkeypatch, tmp_path):
    """probe 早于 `audio_levels`（d8fb15b74／#1134 之前、或者从更早的分支拨的）：这一层
    没查——要说，而且把重 probe 的命令原样印出来（slug 取老 probe 所在的目录，区间、
    记分条框照抄）。只报不拦。"""
    old = {"url": "U", "silent_audio": [], "clip_from": 120, "clip_to": 400,
           "scorebox": "40,905,600,1012"}
    seg = reel.Segment(8.0, 18.0, None, "")
    cmd = pa.reprobe_command("U", "old-slug", old, "claude/x")
    assert cmd == ("gh workflow run match-reel.yml --ref claude/x -f mode=probe "
                   "-f slug=old-slug -f url=U -f clip_from=120 -f clip_to=400 "
                   "-f scorebox=40,905,600,1012"), cmd
    hard, soft = _findings({"slug": "t", "segments": [{}]}, [seg], old, strict=True,
                           reprobe={"U": cmd})
    assert not hard and any("还没量过" in s and cmd in s for s in soft), soft
    # build_match_reel 那一头：slug 取老 probe 所在的目录名，分支取 GITHUB_REF_NAME
    folder = tmp_path / "output" / "2026-09-27" / "reel" / "src-slug"
    folder.mkdir(parents=True)
    (folder / "probe.json").write_text('{"url": "U", "silent_audio": []}', "utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REF_NAME", "claude/y")
    got = reel._reprobe_commands({"slug": "t", "source_url": "U"}, {"U": old}, {"": "U"})
    assert got["U"].startswith("gh workflow run match-reel.yml --ref claude/y -f mode=probe "
                               "-f slug=src-slug -f url=U"), got
    # 接线：probe 那一趟把给了的 --scorebox 记进 probe.json，下次重跑照抄得到
    body = (ROOT / "tools" / "build_match_reel.py").read_text("utf-8")
    assert '"scorebox": args.scorebox or None,' in body


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


# ── 十几段之后：段界上的溶解尾巴、响→静的边沿 ──────────────────────────────────
#
# 现场声的时间轴 2026-09-28 起和画面同一本账：`dissolve_filtergraph` 在每一路进
# `acrossfade` 之前按样本数钉回名义长度，part 解出来长短不齐（`-shortest` 截短、6.1
# 补满最后一帧）不再累成 δ。钉得住钉不住，由下面 `test_真cut_segment刀刀截短…` 用真
# `cut_segment` 造出来的截短压着；这一条只管溶解尾巴和编码器抹开的边沿。
#
# 专门压着的几处：
# - E3 几段各挑一秒，它的起点落在 0.05 秒格子后 0~3ms（从所有没旁白、还空着的段里挑）：
#   在格子前 10ms 放一道 −2 dB 的响→静边沿。量源片时格子后面那块是干净的，而成片
#   多过三代 AAC，编码器把响的能量往后抹过了格子——ALIGN_SLACK 归零，模型只读
#   格子后面那块，上界就被打穿。⚠️ 不靠挪源片起点的毫秒零头去凑：这个夹具的 part
#   走 `[0:v]null`（没有 `fps=` 归一），BtbN 上 `-ss` 不落在帧上时 part 的画面从 0.1s
#   起，xfade 那条链整个断掉（成片只剩 17 秒画面）
# - E2 第 9→10 段的接缝：上一段多切的溶解尾巴是响的，它只在溶解里出现
LONG_LENS = [4.55, 4.37, 7.01, 4.45, 6.36, 5.41, 4.88, 6.67, 5.29, 4.41, 7.10, 5.77, 4.99, 6.09]
LONG_NARRATED = {1, 5, 8}
LONG_FPS = 10
LONG_SOURCE_SECONDS = 3.0 + 10 * len(LONG_LENS) + 5.0
#: E3 那一截源片离别处摆好的响度至少这么远：E2 第 10 段开头的静要盖住上界放宽的那一块。
E3_CLEAR = 0.5
#: 截短那条夹具：名义窗口外沿离响的起点留多远（ALIGN_SLACK 一块 ＋ 压到的块整块算 ＋ 20ms）
E1_GAP = 0.12


def _decoded_seconds(path: Path) -> float:
    """这个文件的音轨**解出来**多长（48k 单声道 PCM 数样本）——成片拼接吃的就是它。"""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
                          "-ac", "1", "-ar", reel.AUDIO_RATE, "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return len(raw) / 2 / int(reel.AUDIO_RATE)


def _ffmpeg_version() -> str:
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout
    return (out.splitlines() or ["ffmpeg（版本读不出）"])[0]


def _long_source(tmp_path, name: str, loud: list) -> Path:
    """合成源片：限带白噪，默认 −25 dB，`loud` 里的 (源起, 源止, dB) 覆盖上去。"""
    np = pytest.importorskip("numpy")
    sr = 44100
    n = int(LONG_SOURCE_SECONDS * sr)
    rng = np.random.default_rng(11)
    mono = rng.standard_normal(n)
    spec = np.fft.rfft(mono)
    spec[int(3500 / (sr / 2) * len(spec)):] = 0
    mono = np.fft.irfft(spec, n)
    mono /= np.sqrt((mono ** 2).mean())
    env = np.full(n, 10 ** (-25 / 20))
    for lo, hi, db in loud:
        env[int(round(lo * sr)):int(round(hi * sr))] = 10 ** (db / 20)
    audio = np.clip(mono * env, -1, 1)
    wav = tmp_path / f"{name}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.stack([audio, audio], 1) * 32767).astype(np.int16).tobytes())
    src = tmp_path / f"{name}.mp4"
    _ffmpeg("-f", "lavfi", "-i",
            f"testsrc2=size=64x64:rate={LONG_FPS}:duration={LONG_SOURCE_SECONDS}",
            "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(src))
    return src


def _cover_part(tmp_path, tag: str) -> Path:
    """封面 part：和 `_still_to_clip` 同一组音频参数（anullsrc、`-t`、`-shortest`）。"""
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    dest = tmp_path / f"{tag}_part_cover.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"color=black:size=64x64:rate={LONG_FPS}:duration={cover + fade}",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", f"{cover + fade:.3f}", "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "160k", "-ar", reel.AUDIO_RATE, "-shortest", str(dest))
    return dest


def _part_seconds(seg, last: bool) -> float:
    """这个 part 的名义长度：段长 ＋ 多切的溶解底料（末段不留）。"""
    return seg.length + (0.0 if last else reel.SEG_FADE)


def _seg_part(tmp_path, tag: str, src: Path, k: int, seg, last: bool) -> Path:
    """第 k 段的 part：和 `cut_segment` 同一组音频参数（`-ss`/`-t`/`-shortest`、AAC 48k）。"""
    dest = tmp_path / f"{tag}_part_{k:02d}.mp4"
    _ffmpeg("-ss", f"{seg.start:.3f}", "-i", str(src), "-t", f"{_part_seconds(seg, last):.3f}",
            "-filter_complex", "[0:v]null[vout]", "-shortest", "-map", "[vout]",
            "-map", "0:a:0", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-ar", reel.AUDIO_RATE, str(dest))
    return dest


def _long_plan(tmp_path):
    """段、源片响度的安排、每一处专门压着的那一秒。

    夹具的几何**自己算**，不借被测的 `film_starts`——否则拆掉什么先把夹具摆歪，
    红在自检上，证明不了模型。现场声按名义起点摆（溶解钉回名义长度，δ 恒为零）。
    """
    cover = reel.COVER_SECONDS
    segs = [reel.Segment(3.0 + 10 * k, 3.0 + 10 * k + length, None,
                         "这一段有旁白。" if k in LONG_NARRATED else "")
            for k, length in enumerate(LONG_LENS)]
    starts, t = [], cover
    for seg in segs:
        starts.append(t)
        t += seg.length

    def src_at(k: int, second: int) -> float:
        return segs[k].start + second - starts[k]

    loud: list[tuple[float, float, float]] = []          # (源起, 源止, dB)，默认 −25
    # A 冷开场（第 0 段）：−59 dB 那一截 silencedetect 看不见，成片第 3、4 秒必须接住
    loud.append((4.0, 7.4, -59.0))
    # E2 第 9→10 段的接缝落在第 54 秒里：第 9 段本身静到段尾，多切的尾巴（源 +4.50 起）
    # 是 −20 dB 的响——它只在溶解里出现；第 10 段开头一路静
    e2 = 54
    assert starts[10] - e2 > 0.5, starts[10]
    loud.append((segs[9].start + 3.3, segs[9].start + 4.50, -72.0))
    loud.append((segs[9].start + 4.50, segs[9].start + 5.0, -20.0))
    loud.append((segs[10].start - 0.3, segs[10].start + 2.5, -72.0))
    # D 第 12 段通段静：第 68、69 秒必须接住
    loud.append((segs[12].start - 0.5, segs[12].end + 0.8, -72.0))
    # E3 −2 dB 的响止于格子前 10ms、起点落在格子后 0~3ms 的那一秒。同一段里每一秒离
    # 格子一样远（段起点、成片起点都差整数秒），所以一段至多一处，要多几处只能多几段：
    # **每一段没旁白的都试**，在段里找一秒——离段头 ≥ 1 秒（响的那半秒整个落在这一段
    # 自己身上，不进溶解）、后面还留得下两秒静、这一截源片离上面几处摆好的响度
    # ≥ E3_CLEAR 秒。
    e3: dict[int, int] = {}
    for k, seg in enumerate(segs):
        if k in LONG_NARRATED:
            continue
        first = math.ceil(starts[k] + 1.0 - 1e-9)
        for second in range(first, math.floor(starts[k] + seg.length - 2 + 1e-9) + 1):
            t0 = src_at(k, second)
            edge = math.floor(t0 / pa.BLOCK_SECONDS + 1e-9) * pa.BLOCK_SECONDS
            if t0 - edge > 0.003:
                break                                  # 这一段每一秒都一样，换下一段
            lo, hi = edge - 0.5, edge + 2.6
            if all(hi + E3_CLEAR <= a or b + E3_CLEAR <= lo for a, b, _db in loud):
                e3[k] = second
                loud.append((lo, edge - 0.010, -2.0))
                loud.append((edge - 0.010, hi, -72.0))
                break
    assert len(e3) >= 2, f"夹具失效：找不到两处落在格子后 0~3ms 的秒：{starts}"
    return segs, starts, loud, {"must_catch": {3, 4, 68, 69}, "e2": e2,
                                "e3": set(e3.values())}


def _film(tmp_path, segs, loud, voices: dict[int, float]):
    """合成源片 → render 的音频链（和 `cut_segment` 同一组音频参数的 AAC 分段、真
    `dissolve_filtergraph`、真 `duck_filtergraph`）→ 成片。返回 `(源片, 成片, parts)`。"""
    src = _long_source(tmp_path, "src", loud)
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    parts = [_cover_part(tmp_path, "film")]
    for k, seg in enumerate(segs):
        parts.append(_seg_part(tmp_path, "film", src, k, seg, k == len(segs) - 1))
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
    return src, mixed, parts


def test_十几段之后_段界溶解尾巴_响静边沿_真跑一遍混音链(tmp_path, monkeypatch):
    """14 段真跑一遍 render 的音频链，QC 的 `per_second_db` 量成片。

    判据三条：**预测成死秒的每一秒成片里真的 ≤ −60**（不误报）；专门安排的必接秒
    （冷开场 −59、第 12 段通段静）一秒不漏；**每一个给出了数的秒都不低于成片读数**
    （上界就是上界，不只在死秒上成立）。
    自检：夹具还在压着该压的地方——**模型拆掉上一段的溶解尾巴**就在这份夹具上误报
    （第 54 秒成片是响的，拆掉的模型说它死了）。
    `ALIGN_SLACK` 归零那一刀靠 E3 那几秒的 −2 dB 边沿：模型只读格子后面那块，
    成片里编码器抹过来的能量把上界打穿（实测 0.6~13 dB）——抹多少和编码器版本有关，
    所以不写成自检，改在反向验证里验。
    """
    pytest.importorskip("numpy")
    segs, starts, loud, marks = _long_plan(tmp_path)
    src, mixed, _parts = _film(tmp_path, segs, loud, {k: 3.0 for k in LONG_NARRATED})
    _spans, record = pa.measure(src, quietest_gain=reel.QUIETEST_BED_GAIN)
    levels = pa.decode_levels(record)
    assert levels is not None
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    real = qc.per_second_db(mixed)
    after = math.ceil(cover) + 1
    real_dead = set(qc.dead_seconds(real, after, [])[0])
    whole = [a + s.length if s.narration.strip() else a for a, s in zip(starts, segs)]

    def predict():
        table = pa.predict_levels(segs, {"": levels}, cover, whole, reel._seg_bed_gain, fade)
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
    # 自检：拆掉上一段多切的溶解尾巴，第 54 秒被误判成死秒——尾巴的响在溶解里
    assert marks["e2"] not in real_dead, f"夹具失效：第 {marks['e2']} 秒成片本来就死了\n{shown}"
    with monkeypatch.context() as m:
        m.setattr(pa, "part_audio_seconds", lambda seg, _fade: seg.length)
        assert marks["e2"] in predict()[1], "夹具失效：不算溶解尾巴也没误报"


# ── 生产上真出现的那一头：`-shortest` 刀刀截短——溶解把每一路钉回名义长度 ────────
#
# 真 `cut_segment` 在 25 fps 下，帧上起切、`-t` 落在「帧格 ＋ 0.01s」上的刀，两版
# ffmpeg 都按画面尾巴把音轨截到整帧 AAC（实测 T=4.69 → 4.672、4.73 → 4.7147、5.17 →
# 5.1413，同一刀两版同一个数；`-t` 落在帧格 ＋0.02／＋0.03／＋0 上的刀都不截）。
# 下面九刀全挑这种长度，不钉的话九刀累积把现场声往前拽 ≈0.24 秒（评审 2026-09-27
# 第三轮在 BtbN 真链上量到过同一个方向：第 12 段 −70 ms）。
NEG_LENS = [2.11, 2.43, 2.15, 2.47, 3.43, 2.11, 2.43, 2.15, 2.47, 4.03]
NEG_FPS = 25


def test_真cut_segment刀刀截短_溶解钉回名义长度_成片不漂(tmp_path, monkeypatch):
    """真 `_still_to_clip` ＋ 真 `cut_segment`（画布缩到 48×64 省时间）→ 真
    `dissolve_filtergraph` → 不闪避那条分支的 AAC → QC 的 `per_second_db`。

    末段第 e1 秒的名义窗口（连前面 0.4 s）−72 dB、窗口后 0.12 s 起又是 −25 dB。九刀截短
    （量出来要 ≥ 0.15 s，否则这条夹具压不住东西，跳过并说出量到的数）不钉的话，现场声
    往前漂、这一秒听到的是窗口后面的响，成片不死；**钉住了就是名义窗口，成片死**。判据：
    成片里 e1 真的死了、模型按名义起点接住它、不误报别的秒、每一秒的上界不低于成片、
    第 4 段通段静的那几秒照样接住。反向验证：`dissolve_filtergraph` 拆掉那一钉，成片
    e1 不死，模型的预测就成了误报（红在「预测红了、成片没红」）。
    """
    np = pytest.importorskip("numpy")
    monkeypatch.setattr(reel, "FPS_EXPR", str(NEG_FPS))
    monkeypatch.setattr(reel, "FPS", float(NEG_FPS))
    for name, value in (("VIDEO_W", 48), ("VIDEO_H", 64), ("CROP_W", 48), ("CROP_H", 64)):
        monkeypatch.setattr(reel, name, value)
    cover, fade = reel.COVER_SECONDS, reel.SEG_FADE
    segs = [reel.Segment(3.0 + 6 * k, round(3.0 + 6 * k + length, 3), 0.5, "", track=False)
            for k, length in enumerate(NEG_LENS)]
    starts, t = [], cover                                   # 画面起点自己算
    for seg in segs:
        starts.append(t)
        t += seg.length
    last = len(segs) - 1
    e1 = math.ceil(starts[last] + 1.0)
    assert e1 + 1 <= starts[last] + segs[last].length - 1, (starts[last], e1)
    s_nom = segs[last].start + e1 - starts[last]           # 名义窗口 [s_nom, s_nom+1)

    sr = 44100
    seconds = segs[-1].end + 3.0
    n = int(seconds * sr)
    rng = np.random.default_rng(5)
    spec = np.fft.rfft(rng.standard_normal(n))
    spec[int(3500 / (sr / 2) * len(spec)):] = 0
    mono = np.fft.irfft(spec, n)
    mono /= np.sqrt((mono ** 2).mean())
    env = np.full(n, 10 ** (-25 / 20))
    # 名义窗口前面多静 0.4 s：补满那头（最多 ≈ 0.2 s）够不着前面的响，这一秒不死
    # 只能是截短那头（窗口后 0.12 s 起的响）给的——拆掉负那头就误报
    for lo, hi in ((s_nom - 0.4, s_nom + 1 + E1_GAP),
                   (segs[4].start - 0.5, segs[4].end + 0.8)):     # 第 4 段通段静
        env[int(round(lo * sr)):int(round(hi * sr))] = 10 ** (-72 / 20)
    # 离段头、段尾各 0.5 s（溶解尾巴 ＋ 两头的漂移）以内的整秒：成片真死、必须接住
    must = set(range(math.ceil(starts[4] + 0.5), math.floor(starts[5] - 0.5)))
    assert len(must) >= 2, (starts[4], starts[5])
    audio = np.clip(mono * env, -1, 1)
    wav = tmp_path / "neg.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.stack([audio, audio], 1) * 32767).astype(np.int16).tobytes())
    src = tmp_path / "neg.mp4"
    _ffmpeg("-f", "lavfi", "-i", f"testsrc2=size=64x64:rate={NEG_FPS}:duration={seconds}",
            "-i", str(wav), "-c:v", "libx264", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k", "-shortest", str(src))

    still = tmp_path / "still.png"
    _ffmpeg("-f", "lavfi", "-i", "color=black:size=48x64", "-frames:v", "1", str(still))
    parts = [reel._still_to_clip(still, tmp_path / "part_cover.mp4", cover + fade)]
    for k, seg in enumerate(segs):
        parts.append(reel.cut_segment(src, seg, tmp_path / f"part_{k:02d}.mp4", 64, None,
                                      tail=0.0 if k == last else fade))
    nominal = [cover + fade] + [s.length + (0.0 if k == last else fade)
                                for k, s in enumerate(segs)]
    pads = [_decoded_seconds(p) - t for p, t in zip(parts, nominal)]
    delta_last = sum(pads[:last + 1])                      # 封面 ＋ 前面九段，不钉会漂这么多
    pads_ms = [round(p * 1000, 1) for p in pads]
    if delta_last > -(E1_GAP + 0.03):
        pytest.skip(f"这个 ffmpeg 上九刀没截够：累积 {delta_last * 1000:+.1f} ms，不到 "
                    f"−{(E1_GAP + 0.03) * 1000:.0f} ms（每刀 {pads_ms}；{_ffmpeg_version()}）")

    joined = tmp_path / "joined.mp4"
    _ffmpeg(*[a for p in parts for a in ("-i", str(p))],
            "-filter_complex", reel.dissolve_filtergraph([cover] + [s.length for s in segs], fade),
            "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", reel.AUDIO_RATE,
            str(joined))
    mixed = tmp_path / "mixed.m4a"                          # 不闪避那条分支：原样转码
    _ffmpeg("-i", str(joined), "-vn", "-c:a", "aac", "-b:a", "192k", "-ar", reel.AUDIO_RATE,
            str(mixed))
    real = qc.per_second_db(mixed)
    after = math.ceil(cover) + 1
    real_dead = set(qc.dead_seconds(real, after, [])[0])
    _spans, record = pa.measure(src, quietest_gain=reel.QUIETEST_BED_GAIN)
    levels = pa.decode_levels(record)
    assert levels is not None

    table = pa.predict_levels(segs, {"": levels}, cover, starts,
                              lambda seg: reel._seg_bed_gain(seg, ducked=False), fade)
    predicted = set(qc.dead_seconds(table, after, [])[0])
    shown = f"  每个 part 解出来多出（ms）：{pads_ms}\n" + "\n".join(
        f"  {i:3d}s 成片 {db:6.1f}  预测上界 {table[i]:6.1f}"
        for i, db in enumerate(real) if i < len(table))
    assert predicted <= real_dead, f"预测红了、成片没红（误报）：{predicted - real_dead}\n{shown}"
    assert e1 in real_dead, f"成片第 {e1} 秒没死——现场声还在漂（溶解没钉住）\n{shown}"
    assert e1 in predicted, f"模型按名义起点没接住第 {e1} 秒\n{shown}"
    assert must <= predicted, f"第 4 段通段静的 {sorted(must - predicted)} 秒没接住\n{shown}"
    for i, db in enumerate(table):
        if not math.isinf(db) and i < len(real):
            assert db - real[i] >= -0.05, f"第 {i} 秒上界比成片还低：\n{shown}"
    assert int(reel.AUDIO_RATE) == 48000, "part 的采样率变了：溶解按样本数钉长度，要跟着改"
