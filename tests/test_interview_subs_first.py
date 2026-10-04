"""赛后开麦：render 之前先要 subs 那一趟在**当前转写指纹**上交的判定（2026-09-28）。

来路（返工审计 rework_audit_0928）：9/20~9/28 有 6 趟 `interview-clip` render 红在
「字幕空档没销账／转写分歧超阈」——alcaraz-fritz ×3、tien-cobolli ×2、chwalinska-mertens ×1，
25.4 runner-分钟，**0/6 在 dispatch 之前拦得住**，其中 4 趟是 interview-auto-render 投的。
第二份 ASR 的结论只活在 runner 上：9/27 起它挪进了 `mode=subs`、报告也进了仓库，
可自动链照样直接投 render，而 dispatch 前的离线预检在没有字幕缓存时只报一句 ⚠️。

这里钉四件事，每件都反向验证过：

1. `build_interview_clip.subs_verdict`：按仓库里的判定（`second_asr_verdict.json` 的量数、
   `gap_vad_attestation.json` 的 VAD 证据，都绑 `transcript_fingerprint`——`SUBS_INPUT_KEYS`
   里每一样都要绑得上，第二份的 VAD 开关关掉也进指纹）给出
   ok／needs_subs／red——量过和没量过分得开，认领（不进指纹）量完再写照样作数；
   `start`/`end` 不进指纹，所以分歧量数另绑区间（`window`），空档证据里**没有那一行**
   （区间挪了、键变了）是缺判定不是红——红只留给 `speech_detected`（复审 2026-09-28）；
2. `--stage verify` 在判定 ok 时**不重量**（第二份 ASR 不是确定性的），VAD 自动销账留理由；
3. `interview_preflight` 的 dispatch 口径（`require_subs`）把缺缓存、缺判定记成带
   `NEEDS_SUBS` 的红；`pick_interview_renders` 只卡在这一类上的先投 subs；
4. 两条工作流的接线：auto-render 投 subs、记账、探针数它当活、投 render 时 SLA 从那趟 subs
   算起；interview-clip 的 render 预检**只对自动链派发的 run** 开 `--require-subs`
   （`--dispatched-by`，2026-09-28 会话决定：手动重渲缺判定只提示、同一个 job 里现量），
   subs 判定干净就叫醒 auto-render。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_interview_clip as clip  # noqa: E402
import interview_preflight as pf  # noqa: E402

GAP = "1.0-6.0"


# ---------------------------------------------------------------- subs_verdict

def _outdir(tmp_path: Path) -> Path:
    """一份字幕缓存：0~1 秒一句、6~7 秒一句，中间 5 秒空档（键 `1.0-6.0`）。"""
    out = tmp_path / "out"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cap_asr.json3").write_text(json.dumps({"events": [
        {"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "Thank you"}]},
        {"tStartMs": 6000, "dDurationMs": 1000, "segs": [{"utf8": "great match"}]},
    ]}), encoding="utf-8")
    return out


_LINES = [{"a": 0.0, "b": 1.0, "en": "Thank you"}, {"a": 6.0, "b": 7.0, "en": "great match"}]
_SPEC = {"slug": "demo", "url": "https://example.test/x", "start": 0.0, "end": 8.0,
         "asr_model": "small.en", "whisper_model": "medium.en"}


def _attest(spec: dict, out: Path, status: str, secs: float = 0.0,
            words: list[str] | None = None) -> None:
    row = {"key": GAP, "start": 1.0, "end": 6.0, "speech_seconds": secs,
           "second_asr_words": words or [], "transcript_covered": False,
           "caption_timeline_covered": False, "status": status}
    row["reason"] = clip.gap_row_reason(row, "medium.en")
    (out / clip.GAP_VAD_ATTESTATION).write_text(json.dumps({
        "status": "pass", "method": "silero_vad_plus_dual_asr_coverage",
        "sha256": clip.transcript_fingerprint(spec, _LINES, out), "url": spec["url"],
        "results": [row]}), encoding="utf-8")


def test_没量过是缺判定_量过就按量数判(tmp_path):
    out = _outdir(tmp_path)
    spec = dict(_SPEC)
    got = clip.subs_verdict(spec, _LINES, out)
    assert got.state == "needs_subs" and not got.reds, got
    assert any(clip.SECOND_ASR_VERDICT in p for p in got.pending), got.pending
    assert any(GAP in p for p in got.pending), "没有 VAD 证据的空档要点名"

    clip.record_second_asr(spec, _LINES, out, 0.05, 300, 290)
    _attest(spec, out, "no_speech")
    got = clip.subs_verdict(spec, _LINES, out)
    assert got.state == "ok", got
    assert any("没人说话，自动销账" in n for n in got.notes), "VAD 自动销账要带着理由"


def test_VAD听到人声是红_人销过的账优先(tmp_path):
    out = _outdir(tmp_path)
    spec = dict(_SPEC)
    clip.record_second_asr(spec, _LINES, out, 0.05, 300, 290)
    _attest(spec, out, "speech_detected", 2.1)
    got = clip.subs_verdict(spec, _LINES, out)
    assert got.state == "red" and any(GAP in r for r in got.reds), got
    # 人听过、写了结论：不管 VAD 怎么说，都算销了（机器不覆盖人）
    got = clip.subs_verdict(dict(spec, caption_gaps_ok={GAP: "听过：全场在笑"}), _LINES, out)
    assert got.state == "ok", got


def test_分歧超闸是红_量完再认领照样作数_认领低于实测照红(tmp_path):
    out = _outdir(tmp_path)
    spec = dict(_SPEC, caption_gaps_ok={GAP: "听过"})
    clip.record_second_asr(spec, _LINES, out, 0.159, 750, 651)
    got = clip.subs_verdict(spec, _LINES, out)
    assert got.state == "red" and "15.9%" in got.reds[0], got
    assert "output/interviews/demo/transcript_diff.md" in got.reds[0] or "/demo/" in got.reds[0]
    claimed = dict(spec, transcript_disagree_ok={"rate": 0.159, "why": "逐处看过：虚词"})
    assert clip.subs_verdict(claimed, _LINES, out).state == "ok"
    low = dict(spec, transcript_disagree_ok={"rate": 0.15, "why": "逐处看过"})
    got = clip.subs_verdict(low, _LINES, out)
    assert got.state == "red" and "还高" in got.reds[0], got


def test_改了en_fixed指纹就变_旧判定不作数(tmp_path):
    out = _outdir(tmp_path)
    spec = dict(_SPEC, caption_gaps_ok={GAP: "听过"})   # 只看分歧那一半
    clip.record_second_asr(spec, _LINES, out, 0.02, 300, 300)
    _attest(spec, out, "no_speech")
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"
    fixed = dict(spec, en_fixed={"2": "great match!"})
    lines = [dict(_LINES[0]), dict(_LINES[1], en="great match!")]
    got = clip.subs_verdict(fixed, lines, out)
    assert got.state == "needs_subs" and any(clip.SECOND_ASR_VERDICT in p for p in got.pending), got


def test_人工核过且指纹没变不要量数(tmp_path):
    out = _outdir(tmp_path)
    spec = dict(_SPEC, transcript_verified=True, caption_gaps_ok={GAP: "听过"})
    (out / clip.VERIFY_FP).write_text(json.dumps({
        "sha256": clip.transcript_fingerprint(spec, _LINES, out), "status": "pass"}))
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"


#: 不经切行、直接绑在判定上的转写输入 → 换成的另一个值（指纹或区间要跟着变）
_BOUND_DIRECTLY = {"asr_model": "base.en", "whisper_model": "large-v3",
                   "whisper_vad_filter": False, "start": 0.5, "end": 9.0,
                   "transcript_languages": [{"start": 0, "end": 8, "language": "en"}],
                   "en_fixed": {"2": "great match!"}}
#: 经切行进指纹的（`main()` 切行读它们、行一变指纹就变）——
#: `test_转写输入的键和出片那一趟切行读的字段对得上` 钉
_BOUND_VIA_LINES = {"url", "segment_budget_px", "word_fix"}
# 需要源字节和模型交叉证据的输入，另在 test_interview_gap_annotations 真核旧判定失效。
_BOUND_WITH_EVIDENCE = {"caption_gap_annotations"}


def test_每个转写输入都绑在判定上_只改它旧判定不作数(tmp_path):
    """`SUBS_INPUT_KEYS` 里的一样改了，subs 的账清零；它要是不绑判定（不进指纹、不进区间、
    也不经切行），判定照旧 ok——render 跳过重量，拿旧配置量的数出片。`whisper_vad_filter`
    就是这么漏的（复审 2026-09-28：2 条 spec 写了它）。表自带自检：新加一样转写输入，
    要在这两份名单里说清它怎么绑。"""
    assert set(clip.SUBS_INPUT_KEYS) == set(_BOUND_DIRECTLY) | _BOUND_VIA_LINES | _BOUND_WITH_EVIDENCE, (
        "新加的转写输入要说清它怎么绑判定")
    out = _outdir(tmp_path)
    spec = dict(_SPEC)
    clip.record_second_asr(spec, _LINES, out, 0.02, 300, 300)
    _attest(spec, out, "no_speech")
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"
    for key, value in _BOUND_DIRECTLY.items():
        got = clip.subs_verdict(dict(spec, **{key: value}), _LINES, out)
        assert got.state == "needs_subs" and not got.reds, (key, got)


def test_VAD开关默认开着时指纹和加它之前一字不差():
    """`whisper_vad_filter` 只在关掉时进指纹：默认（不写或写 true）的指纹钉死在加它之前
    的值上——一改全量，仓库里所有 `verify_fingerprint.json` 一起作废、重渲全要重量。"""
    import tempfile  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as td:
        out = _outdir(Path(td))
        pinned = "09b1d46302f77b0bf9e35823e4da7d5a88318c27d957f0df9e3b6700725d889b"
        assert clip.transcript_fingerprint(_SPEC, _LINES, out) == pinned
        assert clip.transcript_fingerprint(dict(_SPEC, whisper_vad_filter=True),
                                           _LINES, out) == pinned
        assert clip.transcript_fingerprint(dict(_SPEC, whisper_vad_filter=False),
                                           _LINES, out) != pinned


def _three_captions(tmp_path: Path) -> Path:
    """复审那份 startcase：0~1、10~11、16~17 秒各一句，中间两段静默。"""
    out = tmp_path / "out3"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cap_asr.json3").write_text(json.dumps({"events": [
        {"tStartMs": t * 1000, "dDurationMs": 1000, "segs": [{"utf8": w}]}
        for t, w in ((0, "and the winner"), (10, "Thank you"), (16, "great match"))]}),
        encoding="utf-8")
    return out


def _lines(spec: dict, out: Path) -> list[dict]:
    lines = clip.segment(clip.cached_words(spec["url"], out, spec), spec["start"], spec["end"],
                         ruler=clip.segment_ruler(spec))
    clip.strip_hesitation_lines(lines)
    return lines


def _attest_all(spec: dict, lines: list[dict], out: Path, status: str = "no_speech") -> None:
    rows = [{"key": clip.gap_key(*g), "start": g[0], "end": g[1], "speech_seconds": 0.0,
             "second_asr_words": [], "transcript_covered": False,
             "caption_timeline_covered": False, "status": status}
            for g in clip.caption_gaps(spec, out)]
    (out / clip.GAP_VAD_ATTESTATION).write_text(json.dumps({
        "status": "pass", "method": "silero_vad_plus_dual_asr_coverage",
        "sha256": clip.transcript_fingerprint(spec, lines, out), "url": spec["url"],
        "results": rows}), encoding="utf-8")


@pytest.mark.parametrize("moved", [{"start": 5.0}, {"end": 15.5}, {"start": 4.0, "end": 15.0}])
def test_挪start或end进证过的静默_是缺判定不是红(tmp_path, moved):
    """`start`/`end` 不进指纹：挪进一段 VAD 证过的静默，行一字不差、指纹一字不差，空档的
    边界却跟着挪、键变了——证据里**没有那一行**。那是「没量过」（再投一趟 subs，VAD 重新
    作证），不是「量出来有人声」。判成红的话，一段机器销得掉的静默就得人去听、去认领，
    手动 render 还会停在 `--require-subs` 那道预检上（2026-09-28 复审 startcase／endcase）。"""
    out = _three_captions(tmp_path)
    spec = {"slug": "demo", "url": "https://example.test/x", "start": 3.0, "end": 14.0,
            "asr_model": "small.en", "whisper_model": "medium.en"}
    lines = _lines(spec, out)
    clip.record_second_asr(spec, lines, out, 0.02, 4, 4)
    _attest_all(spec, lines, out)
    assert clip.subs_verdict(spec, lines, out).state == "ok"
    moved_spec = dict(spec, **moved)
    moved_lines = _lines(moved_spec, out)
    assert [x["en"] for x in moved_lines] == [x["en"] for x in lines]
    assert clip.transcript_fingerprint(moved_spec, moved_lines, out) == \
        clip.transcript_fingerprint(spec, lines, out), "前提：挪区间指纹不变"
    got = clip.subs_verdict(moved_spec, moved_lines, out)
    assert got.state == "needs_subs" and got.reds == [], got
    assert any("空档键变了" in p for p in got.pending), got.pending
    # 真听到人声的那一行照旧是红——红只留给证据里记着 speech_detected 的
    _attest_all(moved_spec, moved_lines, out, status="speech_detected")
    got = clip.subs_verdict(moved_spec, moved_lines, out)
    assert got.state == "red" and got.reds, got


def test_分歧量数绑区间_挪了区间老量数不作数(tmp_path):
    """第二份 ASR 只比 `[start, end]` 里的词。`end` 伸进一段没有自动字幕的尾巴，行和指纹都
    不变，那一截话却可能只在第二份里——旧区间量的分歧率不能替新区间放行，render 的 verify
    也就不能凭它跳过重量。`verify_fingerprint.json` 的 pass 同理（老产物没记区间 → 缺判定）。"""
    out = _outdir(tmp_path)
    spec = dict(_SPEC, caption_gaps_ok={GAP: "听过"})
    clip.record_second_asr(spec, _LINES, out, 0.02, 300, 300)
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"
    longer = dict(spec, end=12.0)
    assert clip.transcript_fingerprint(longer, _LINES, out) == \
        clip.transcript_fingerprint(spec, _LINES, out)
    got = clip.subs_verdict(longer, _LINES, out)
    assert got.state == "needs_subs" and any("区间" in p for p in got.pending), got
    fp = clip.transcript_fingerprint(spec, _LINES, out)
    (out / clip.SECOND_ASR_VERDICT).unlink()
    (out / clip.VERIFY_FP).write_text(json.dumps({"sha256": fp, "status": "pass"}))
    assert clip.subs_verdict(spec, _LINES, out).state == "needs_subs", "没记区间的 pass 不作数"
    (out / clip.VERIFY_FP).write_text(json.dumps({"sha256": fp, "status": "pass",
                                                  "window": clip.verdict_window(spec),
                                                  "url": spec["url"]}))
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"
    assert clip.subs_verdict(longer, _LINES, out).state == "needs_subs"


# ---------------------------------------------------------------- --stage verify

def _drive_verify(monkeypatch, tmp_path: Path, spec: dict, gaps: list) -> dict:
    """直接跑 `main()` 的 verify 分支，网络和 whisper 换成替身（同 test_interview_cover_first）。"""
    calls: dict = {"verify": 0}
    for name in ("check_source_contract", "check_topline_format", "check_opening",
                 "check_lead_in", "check_trail_in", "check_copy_page",
                 "check_human_quote", "storyboard_sheet"):
        monkeypatch.setattr(clip, name, lambda *a, **k: None)
    monkeypatch.setattr(clip, "OUTDIR", tmp_path / "out")
    monkeypatch.setattr(clip, "fetch_words", lambda *a, **k: [])
    monkeypatch.setattr(clip, "segment", lambda *a, **k: [dict(x) for x in _LINES])
    monkeypatch.setattr(clip, "caption_gaps", lambda *a, **k: list(gaps))

    def fake_verify(*a, **k):
        calls["verify"] += 1

    monkeypatch.setattr(clip, "verify_transcript", fake_verify)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_interview_clip.py", "--spec", str(spec_path),
                                      "--stage", "verify"])
    try:
        calls["rc"] = clip.main()
    except SystemExit as exc:
        calls["exit"] = str(exc)
    return calls


def test_判定ok时verify不重量_补落pass指纹让render认(monkeypatch, tmp_path, capsys):
    """第二份 ASR 不是确定性的（tien-cobolli 同一个指纹 40e2f923 两趟量出 2.7%／3.9%）：
    自动链凭 subs 的判定投了 render，render 再量一遍只会让放行过的片子随机红一次。"""
    spec = dict(_SPEC, transcript_disagree_ok={"rate": 0.14, "why": "逐处看过"})
    out = tmp_path / "out" / "demo"
    out.mkdir(parents=True)
    # 缺判定：照常跑第二份 ASR
    got = _drive_verify(monkeypatch, tmp_path, spec, [])
    assert got["verify"] == 1 and got.get("rc") == 0, got
    # 落的 pass 带着区间：区间不进指纹，`subs_verdict` 拿它认「量的是不是这一段」
    window = json.loads((out / clip.VERIFY_FP).read_text(encoding="utf-8")).get("window")
    assert window == clip.verdict_window(spec), window
    (out / clip.VERIFY_FP).unlink()
    # subs 量到 13.5%（超闸门），人随后认领了 14%——判定 ok：不重量，补落 pass 指纹
    clip.record_second_asr(spec, _LINES, out, 0.135, 300, 280)
    got = _drive_verify(monkeypatch, tmp_path, spec, [])
    assert got["verify"] == 0 and got.get("rc") == 0, got
    assert "跳过第二份 ASR" in capsys.readouterr().out
    assert clip.transcript_auto_verified(spec, _LINES, out), "render 那一步认的 pass 指纹没落"
    assert json.loads((out / clip.VERIFY_FP).read_text(encoding="utf-8")).get("window") \
        == clip.verdict_window(spec), "补落的 pass 也要带区间"
    # 判定红（认领低于实测）：照常重量——不许拿红判定当跳过的理由
    got = _drive_verify(monkeypatch, tmp_path, dict(spec, transcript_disagree_ok={
        "rate": 0.13, "why": "逐处看过"}), [])
    assert got["verify"] == 1, got


def test_人核过也要补空档的VAD证据_空档销过才跳过(monkeypatch, tmp_path):
    """`transcript_verified` 只管分歧那一半。空档还缺当前指纹的 VAD 证据时照样跑第二份 ASR——
    不然 subs 那一趟永远补不上证据，自动链只能一趟趟重投。"""
    spec = dict(_SPEC, transcript_verified=True)
    out = tmp_path / "out" / "demo"
    out.mkdir(parents=True)
    (out / clip.VERIFY_FP).write_text(json.dumps({
        "sha256": clip.transcript_fingerprint(spec, _LINES, out), "status": "pass"}))
    got = _drive_verify(monkeypatch, tmp_path, spec, [(1.0, 6.0)])
    assert got["verify"] == 1 and got.get("rc") == clip.VERIFY_FINDINGS_EXIT, got
    got = _drive_verify(monkeypatch, tmp_path, dict(spec, caption_gaps_ok={GAP: "听过：掌声"}),
                        [(1.0, 6.0)])
    assert got["verify"] == 0 and got.get("rc") == 0, got
    # 一处 VAD 听到了人声（red）＋一处挪区间之后新出现、证据里没有的键：state 是 red，
    # 可那处新键同样要这一趟去补——判 pending，不判 state
    _attest(spec, out, "speech_detected", 2.1)
    got = _drive_verify(monkeypatch, tmp_path, spec, [(1.0, 6.0), (6.5, 9.0)])
    assert got["verify"] == 1 and got.get("rc") == clip.VERIFY_FINDINGS_EXIT, got
    # 只剩那处听到人声的：证据齐了，人核过的分歧不重量，红照报
    got = _drive_verify(monkeypatch, tmp_path, spec, [(1.0, 6.0)])
    assert got["verify"] == 0 and got.get("rc") == clip.VERIFY_FINDINGS_EXIT, got


def test_自动销过账的空档subs和verify日志不再喊没销账(monkeypatch, tmp_path, capsys):
    """复审第四轮：`main()` 每一档都喊一遍没销账的空档，原来只减人销的账（`_unresolved_gaps`）——
    VAD 证据已经自动销掉、闸也放行了的空档，subs／verify 日志照样印「⚠️ 空档没销账」。"""
    spec = dict(_SPEC)
    out = tmp_path / "out" / "demo"
    out.mkdir(parents=True)
    clip.record_second_asr(spec, _LINES, out, 0.02, 300, 300)
    _attest(spec, out, "no_speech")
    got = _drive_verify(monkeypatch, tmp_path, spec, [(1.0, 6.0)])
    printed = capsys.readouterr().out
    assert got.get("rc") == 0, got
    assert "空档没销账" not in printed, "闸放行了的空档，日志还说没销账"
    assert f"`{GAP}`：VAD 自动销账" in printed, printed
    # VAD 听到了人声：照旧喊
    _attest(spec, out, "speech_detected", 2.1)
    _drive_verify(monkeypatch, tmp_path, spec, [(1.0, 6.0)])
    assert "⚠️ 空档没销账" in capsys.readouterr().out


def _fake_faster_whisper(monkeypatch, words: list[tuple[float, float, str]]) -> None:
    """一个假的 faster_whisper：转写给定的词，VAD 一段人声都没有。"""
    word_objs = [types.SimpleNamespace(start=a, end=b, word=w) for a, b, w in words]

    class Model:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, *a, **k):
            return [types.SimpleNamespace(words=word_objs)], None

    pkg = types.ModuleType("faster_whisper")
    pkg.WhisperModel = Model
    audio = types.ModuleType("faster_whisper.audio")
    audio.decode_audio = lambda *a, **k: [0.0] * 16
    vad = types.ModuleType("faster_whisper.vad")
    vad.VadOptions = lambda **k: k
    vad.get_speech_timestamps = lambda *a, **k: []
    for name, mod in (("faster_whisper", pkg), ("faster_whisper.audio", audio),
                      ("faster_whisper.vad", vad)):
        monkeypatch.setitem(sys.modules, name, mod)


def test_verify超闸也先落量数_VAD自动销账写理由(monkeypatch, tmp_path, capsys):
    """量数排在认领那道闸会抛之前落盘——「量过、超了」和「没量过」要分得开。"""
    out = _outdir(tmp_path)
    monkeypatch.setattr(clip, "yt_download", lambda url, dest, fmt, spec: dest)
    # 第二份只听到一半的词 → 分歧 50%，远超闸门
    _fake_faster_whisper(monkeypatch, [(0.1, 0.4, "Thank"), (0.5, 0.9, "you")])
    spec = dict(_SPEC)
    with pytest.raises(clip.ReviewFindings):
        clip.verify_transcript(spec, _LINES, out)
    rec = json.loads((out / clip.SECOND_ASR_VERDICT).read_text(encoding="utf-8"))
    assert rec["sha256"] == clip.transcript_fingerprint(spec, _LINES, out)
    assert rec["rate"] > clip.TRANSCRIPT_MAX_DISAGREE and rec["first_words"] == 4
    printed = capsys.readouterr().out
    assert f"[空档] VAD 自动销账 {GAP}" in printed and "没人说话" in printed
    gaps_md = (out / "caption_gaps.md").read_text(encoding="utf-8")
    assert "VAD 自动销账" in gaps_md and "**否**" not in gaps_md, (
        "VAD 销掉的空档在报告里还印「否」——报告说没销、闸却放行了")
    got = clip.subs_verdict(spec, _LINES, out)
    assert got.state == "red" and "50.0%" in got.reds[0], got


# ---------------------------------------------------------------- 预检（dispatch 口径）

def _spec_with_cache(monkeypatch, tmp_path) -> dict:
    """一条合成采访 ＋ 仓库外的字幕缓存（和 test_interview_preflight 的 `_full_spec` 同形）。"""
    try:
        pf._require_env()
    except pf.PreflightUnavailable as exc:
        pytest.skip(f"量宽度的环境不全：{exc}")
    spec = {"slug": "subs-first-fixture", "url": "https://example.test/oncourt",
            "start": 0.0, "end": 6.0, "asr_model": "small.en",
            "event": "2026 美网 1/4决赛", "winner": "莱巴金娜", "interview_kind": "赛后场上采访",
            "push": {"matchup": "郑钦文 vs 莱巴金娜", "score": "3-6 6-1 6-4"},
            "zh": ["非常感谢大家", "这是一场精彩的比赛"]}
    out = tmp_path / "output" / "interviews"
    (out / spec["slug"]).mkdir(parents=True)
    words = [(1.0, "Thank"), (1.3, "you"), (1.6, "so"), (1.9, "much."),
             (4.0, "It"), (4.3, "was"), (4.6, "a"), (4.9, "great"), (5.2, "match")]
    (out / spec["slug"] / "cap_asr.json3").write_text(json.dumps({"events": [
        {"tStartMs": int(t * 1000), "dDurationMs": 250, "segs": [{"utf8": w}]}
        for t, w in words]}), encoding="utf-8")
    monkeypatch.setattr(pf, "OUTPUT", out)
    return spec


def _lines_as_main(spec: dict, work: Path) -> list[dict]:
    """`main()` 算指纹那一刻的行：缓存 → 切行 → en_fixed → 去犹豫音。"""
    lines = clip.segment(clip.cached_words(spec["url"], work, spec), spec["start"], spec["end"],
                         ruler=clip.segment_ruler(spec))
    clip.strip_hesitation_lines(lines)
    return lines


def test_预检dispatch口径_缺缓存缺判定都算红带NEEDS_SUBS(monkeypatch, tmp_path):
    spec = _spec_with_cache(monkeypatch, tmp_path)
    out = pf.OUTPUT / spec["slug"]
    bad, notes = pf.subtitle_findings(spec)                  # 本地 CLI 默认口径：只提示
    assert bad == [] and any(clip.SECOND_ASR_VERDICT in n for n in notes), (bad, notes)
    bad, _ = pf.subtitle_findings(spec, require_subs=True)
    assert bad and all(b.startswith(pf.NEEDS_SUBS) for b in bad), bad

    # 判定落库（绑当前指纹）、干净：dispatch 口径也放行
    lines = _lines_as_main(spec, out)
    clip.record_second_asr(spec, lines, out, 0.03, 9, 9)
    assert pf.subtitle_findings(spec, require_subs=True)[0] == []

    # 判定是红的：两种口径都是红
    clip.record_second_asr(spec, lines, out, 0.3, 9, 6)
    for strict in (False, True):
        bad, _ = pf.subtitle_findings(spec, require_subs=strict)
        assert bad and all(b.startswith(pf.SUBS_RED) for b in bad), (strict, bad)

    # 仓库里连字幕缓存都没有：dispatch 口径下是 NEEDS_SUBS 的红，不是一句 ⚠️
    shutil.rmtree(out)
    bad, _ = pf.subtitle_findings(spec, require_subs=True)
    assert len(bad) == 1 and bad[0].startswith(pf.NEEDS_SUBS) and "字幕缓存" in bad[0], bad
    assert pf.subtitle_findings(spec)[0] == []


def test_自动链dispatch前的预检走dispatch口径_不打桩(monkeypatch, tmp_path):
    """不打桩 `spec_problems`：一条有字幕缓存、没有 subs 判定的 spec，`pick_interview_renders`
    dispatch 之前那道预检必须报出 `NEEDS_SUBS`——和 interview-clip render 那一趟的
    `--require-subs` 同一个结论。退回本地默认口径（复审 M9）的话，只缺判定的 spec 在 pick
    眼里是干净的、投 render，runner 上 `--require-subs` 却红，每 70 分钟重投一趟 render，
    `mode=subs` 永远不投——两边口径一分叉就是死锁。"""
    import pick_interview_renders as p  # noqa: PLC0415

    spec = _spec_with_cache(monkeypatch, tmp_path)
    monkeypatch.setattr(p, "PROBE", False)
    got, partial = p._preflight_problems(spec["slug"], spec)
    assert not partial and any(pf.NEEDS_SUBS in g for g in got), got
    runner, _ = pf.subtitle_findings(spec, require_subs=True)
    assert runner and all(r.startswith(pf.NEEDS_SUBS) for r in runner), runner


def test_预检结论缓存的键跟着subs判定变(monkeypatch, tmp_path):
    """一趟 subs 落了新判定、字幕缓存一个字节没变——键不变的话，探针会拿「当时还缺判定」
    那份旧结论一直顶到北京日期翻过去。"""
    out = tmp_path / "output" / "interviews"
    (out / "p").mkdir(parents=True)
    (out / "p" / "cap_asr.json3").write_text('{"events": []}', encoding="utf-8")
    monkeypatch.setattr(pf, "OUTPUT", out)
    before = pf.caption_fingerprint("p")
    (out / "p" / clip.SECOND_ASR_VERDICT).write_text('{"rate": 0.02}', encoding="utf-8")
    after = pf.caption_fingerprint("p")
    assert before != after and any(clip.SECOND_ASR_VERDICT in c for c in after)
    work = tmp_path / "work"
    work.mkdir()
    assert pf._materialize_captions("p", work)
    assert (work / clip.SECOND_ASR_VERDICT).is_file(), "预检读不到判定，就判不了指纹"


def test_已发的采访_当前判定一条都不红():
    """存量扫描：HEAD 上已推送（有 pushed.json）的采访，按它们仓库里的判定重判——
    **0 条红**。needs_subs（发出去之后又改过转写、或者 verify 指纹那一代之前的老片）
    不是红：重渲时自动链会先投 subs，不需要豁免表。"""
    try:
        pf._require_env()
    except pf.PreflightUnavailable as exc:
        pytest.skip(f"量宽度的环境不全：{exc}")
    listing = subprocess.run(["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD",
                              "--", "output/interviews/"], capture_output=True, text=True)
    if listing.returncode != 0:
        pytest.skip("git 用不了")
    published = sorted({ln.split("/")[2] for ln in listing.stdout.splitlines()
                        if ln.endswith("/pushed.json")})
    if not published:
        pytest.skip("HEAD 里没有已推送的采访")
    red = []
    for slug in published:
        path = ROOT / "specs" / "interviews" / f"{slug}.json"
        if not path.is_file():
            continue
        bad, _ = pf.subtitle_findings(json.loads(path.read_text(encoding="utf-8")),
                                      require_subs=True)
        red += [f"{slug}：{b.splitlines()[0]}" for b in bad if b.startswith(pf.SUBS_RED)]
    assert red == [], red


# ---------------------------------------------------------------- picker

@pytest.fixture()
def pick(monkeypatch, tmp_path):
    import interview_preflight  # noqa: PLC0415
    import pick_interview_renders as p  # noqa: PLC0415

    specs = tmp_path / "specs"
    specs.mkdir()
    for name, attr in (("SPECS", specs), ("OUTPUT", tmp_path / "output"),
                       ("STATE", tmp_path / "state.json"),
                       ("VERDICT_CACHE", tmp_path / "cache" / "verdicts.json")):
        monkeypatch.setattr(p, name, attr)
    monkeypatch.setattr(p, "_rendered_slugs", lambda: set())
    monkeypatch.setattr(p, "validate_source_contract", lambda s: None)
    monkeypatch.setattr(p, "check_lead_in", lambda s: None)
    monkeypatch.setattr(p, "_VERDICTS", None)
    monkeypatch.setattr(p, "_VERDICTS_DIRTY", False)
    monkeypatch.setattr(p, "_UNKNOWN", [])
    monkeypatch.setattr(p, "PROBE", False)
    for slug in ("needs", "mixed", "enfix", "clean"):
        spec = {"slug": slug, "url": f"https://example.test/{slug}", "start": 0.0, "end": 30.0,
                "opening": {"kind": "none"}, "zh": ["a"],
                "transcript_verified": True, "takeaway": {"close": {"point": "x"}},
                "cover": {"frame_at": 1}}
        (specs / f"{slug}.json").write_text(json.dumps(spec), encoding="utf-8")
        (specs / f"{slug}.xhs.txt").write_text("文案", encoding="utf-8")
    need = f"{interview_preflight.NEEDS_SUBS}当前转写指纹没有第二份 ASR 的分歧量数"
    # mixed：缺判定＋中文超宽（不碰转写，不挡 subs——D2）；enfix：缺判定＋`en_fixed` 挂错行（碰转写，挡）
    verdicts = {"needs": [need], "mixed": [need, "字幕（出片那一趟 write_ass 会红在这儿）：中文超宽"],
                "enfix": [need, f"{interview_preflight.EN_FIXED_RED}（键是 **1 起** 的行号）：第 3 行"],
                "clean": []}

    p._VERDICTS_FIXTURE = verdicts          # 测试按 slug 改预检结论用

    def fake(spec, **kw):
        """和真函数同一个口径开关：缺判定**只在** dispatch 口径（`require_subs=True`）下
        是红，本地默认口径下只是提示（`subtitle_findings` 的 `not_yet`）。原来这里无视
        `require_subs`、一律当红——`_preflight_problems` 把它退回 `spec_problems(spec)`
        （复审 M9）测试照样绿，而真预检下那条只缺判定的 spec 会被当成 ready 投 render，
        红在 interview-clip 的 `--require-subs`，每 70 分钟重投一趟、subs 永远不投。"""
        rows = verdicts.get(spec["slug"], [])
        if kw.get("require_subs") is True:
            return list(rows), []
        need_it = interview_preflight.NEEDS_SUBS
        return ([r for r in rows if need_it not in r],
                [r.replace(need_it, "") for r in rows if need_it in r])
    monkeypatch.setattr(interview_preflight, "spec_problems", fake)
    return p


_NOW = datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)


def test_缺subs判定的先投subs_中文封面的红不挡_碰转写的红才挡(pick):
    """D2（2026-09-28）：中文超宽这类不碰转写指纹的红不挡 subs（subs 那两档只报不拦）；
    `en_fixed` 挂错行碰的是转写本身——subs 自己也会死在那儿，挡。三份名单两两不相交。"""
    ready, waiting, subs = pick.todo_plan(now=_NOW)
    assert ready == ["clean"] and subs == ["mixed", "needs"], (ready, subs)
    assert [s for s, _ in waiting] == ["enfix"], waiting
    assert not (set(ready) & set(subs) or set(ready) & set(dict(waiting))
                or set(subs) & set(dict(waiting))), "一条 slug 一趟只许投一样"
    # 老接口不变：todo_slugs 不把「先投 subs」的混进 render 名单
    assert pick.todo_slugs(now=_NOW)[0] == ["clean"]


def test_片尾板那道红挡subs_改end区间就变():
    """复审第四轮：「已知带片尾板的源上 `end` 离最后一个词太远」那道红（`subtitle_findings` 报
    `片尾板：…`，pick 前面再加「预检：」）要改的是 `end`——第二份 ASR 量的区间跟着变，先投的那趟
    subs 白跑（5~8 分钟一趟 runner）。和 `en_fixed` 挂错行同一类：挡 subs。中文超宽照旧不挡。"""
    import pick_interview_renders as p  # noqa: PLC0415

    need = f"{pf.NEEDS_SUBS}当前转写指纹没有第二份 ASR 的分歧量数"
    tail = "预检：片尾板：`end` 在最后一个词之后 9.4 秒，源片带片尾板——收到词尾后 1.5 秒以内，或写 `_end_why`"
    assert not p.wants_subs([need, tail]), "片尾板的红不挡 subs：改完 end 那一趟就白量了"
    assert p.subs_blockers([need, tail]) == [tail]
    assert p.wants_subs([need, "预检：字幕（出片那一趟 write_ass 会红在这儿）：中文超宽"])


def test_subs投过在窗口里不重投_超窗重投_满三趟停_只有转写输入改了才清零(pick):
    at = lambda m: (_NOW + timedelta(minutes=m)).strftime("%FT%TZ")  # noqa: E731
    pick.mark_subs("needs", now=at(0))
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=10))
    assert "needs" not in subs and any("已投 subs" in w[1][0] for w in waiting if w[0] == "needs")
    _, _, subs = pick.todo_plan(now=_NOW + timedelta(minutes=pick.SUBS_STALE_MINUTES + 1))
    assert "needs" in subs, "投出去超过窗口还没判定：再投一次"
    pick.mark_subs("needs", now=at(80))
    pick.mark_subs("needs", now=at(160))
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=300))
    assert "needs" not in subs and any("预检还是认不出" in w[1][0]
                                       for w in waiting if w[0] == "needs"), waiting
    assert json.loads(pick.STATE.read_text())["subs"]["needs"]["tries"] == pick.SUBS_MAX_TRIES
    # 两种卡法都要点名：没交判定，和交了但绑的指纹跟预检重切出来的对不上
    why = next(w[1][0] for w in waiting if w[0] == "needs")
    assert "日志" in why and "second_asr_verdict.json" in why and "--require-subs" in why, why
    path = pick.SPECS / "needs.json"
    # 只改 zh（不动转写）：认领照旧——每次提交 spec 都经 on:push 叫醒 pick，按整份 spec
    # 认的话，还在跑的那趟 subs 会被同 slug 的重投掐掉（cancel-in-progress）
    path.write_text(path.read_text().replace('"a"', '"改过的中文"'), encoding="utf-8")
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=301))
    assert "needs" not in subs and "needs" in dict(waiting), "只改了 zh 就清零重投"
    pick.mark_subs("needs", now=at(10))            # 窗口里：改 zh 也不重投
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=20))
    assert "needs" not in subs and "已投 subs" in dict(waiting)["needs"][0], waiting
    # 改转写输入（这里挪 end）：上一份的认领不算数，次数清零
    spec = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(dict(spec, end=42.0)), encoding="utf-8")
    _, _, subs = pick.todo_plan(now=_NOW + timedelta(minutes=21))
    assert "needs" in subs, "转写输入改了：上一份的认领不算数"
    pick.mark_subs("needs", now=at(22))
    assert json.loads(pick.STATE.read_text())["subs"]["needs"]["tries"] == 1


def test_render的SLA起点从先投的那趟subs算起(pick, monkeypatch, capsys):
    """先投 subs 换来的 render，10 分钟成片时钟从那趟 subs 派发算起——原来一律取投 render
    那一刻，subs 那一跳（派发、5~8 分钟、叫醒）整段不进 SLA（复审 2026-09-28）。只认同一份
    转写输入、晚于上一次 render 派发、`SUBS_SLA_MINUTES` 以内的；其余取现在。"""
    at = lambda m: (_NOW + timedelta(minutes=m)).strftime("%FT%TZ")  # noqa: E731
    now = _NOW + timedelta(minutes=12)
    assert pick.render_received_at("needs", now=now) == at(12), "没投过 subs：现在"
    pick.mark_subs("needs", now=at(0))
    assert pick.render_received_at("needs", now=now) == at(0)
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py", "--received-at", "needs",
                                      "--at", at(12)])
    assert pick.main() == 0 and capsys.readouterr().out.strip() == at(0), "CLI 和函数同一个结论"
    late = _NOW + timedelta(minutes=pick.SUBS_SLA_MINUTES + 1)
    assert pick.render_received_at("needs", now=late) == late.strftime("%FT%TZ"), (
        "隔太久：中间多半隔着人（判定红了、人改完才投的 render）")
    pick.mark_one("needs", now=at(5))       # 那趟 subs 之后已经投过一次 render：不是它换来的
    assert pick.render_received_at("needs", now=now) == at(12)
    pick.mark_subs("clean", now=at(0))
    assert pick.render_received_at("clean", now=now) == at(0)
    path = pick.SPECS / "clean.json"        # 转写输入改了：那趟 subs 量的不是这一版
    path.write_text(json.dumps(dict(json.loads(path.read_text()), end=42.0)), encoding="utf-8")
    assert pick.render_received_at("clean", now=now) == at(12)


def test_转写输入的键和出片那一趟切行读的字段对得上():
    """`SUBS_INPUT_KEYS` 漏一个，改那个字段就不清零；多一个（比如 zh），改中文就清零重投。
    按 `main()` 真正读的字段钉：切行（segment 的参数）、订正、两份 ASR 的模型和 VAD 开关。"""
    import inspect  # noqa: PLC0415

    src = inspect.getsource(clip.main)
    seg = src[src.index("lines = segment("):src.index("strip_hesitation_lines(lines)")]
    for key in ("url", "start", "end", "segment_budget_px", "word_fix", "en_fixed"):
        assert f'spec["{key}"]' in seg or f'spec.get("{key}")' in seg, key
        assert key in clip.SUBS_INPUT_KEYS, key
    assert {"asr_model", "whisper_model", "whisper_vad_filter"} <= set(clip.SUBS_INPUT_KEYS)
    assert not {"zh", "cover", "push", "takeaway", "caption_gaps_ok",
                "transcript_disagree_ok"} & set(clip.SUBS_INPUT_KEYS)
    base = dict(_SPEC, zh=["一"])
    assert clip.transcript_inputs_sha(base) == clip.transcript_inputs_sha(dict(base, zh=["二"]))
    assert clip.transcript_inputs_sha(base) != clip.transcript_inputs_sha(dict(base, end=9.0))


def test_main把先投subs的写进文件_stdout名单只有render(pick, monkeypatch, capsys, tmp_path):
    listing = tmp_path / "subs.txt"
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py", "--subs-list", str(listing)])
    assert pick.main() == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("待 dispatch") and "needs" in lines[0]
    assert lines[1:] == ["clean"], lines
    assert listing.read_text(encoding="utf-8") == "mixed\nneeds\n"
    monkeypatch.setattr(sys, "argv", ["pick_interview_renders.py", "--mark-subs", "needs",
                                      "--at", "2026-09-28T04:00:00Z"])
    assert pick.main() == 0
    rec = json.loads(pick.STATE.read_text())["subs"]["needs"]
    assert rec["at"] == "2026-09-28T04:00:00Z" and rec["tries"] == 1


def test_探针拿缓存里的缺判定结论_投过subs就不叫醒全量(pick, monkeypatch):
    """探针（系统 python3，没 PIL）判不了指纹：拿上一趟全量记下的结论；那份结论是
    「缺 subs 判定」时，subs 刚投过就不算活（不叫醒全量），过了窗口才算。"""
    import interview_preflight  # noqa: PLC0415

    monkeypatch.setattr(pick, "_code_fingerprint", lambda: "code")
    monkeypatch.setattr(interview_preflight, "caption_fingerprint", lambda slug: [])
    pick.todo_plan(now=_NOW)                                  # 全量那一趟：记结论
    pick.save_verdicts()

    def unavailable(s, **kw):
        raise interview_preflight.PreflightUnavailable("缺 PIL")
    monkeypatch.setattr(interview_preflight, "spec_problems", unavailable)
    monkeypatch.setattr(interview_preflight, "probe_problems", lambda s: ([], ["量宽度"]))
    monkeypatch.setattr(pick, "PROBE", True)
    monkeypatch.setattr(pick, "_VERDICTS", None)
    ready, _, subs = pick.todo_plan(now=_NOW)
    assert "needs" in subs and "needs" not in ready, (ready, subs)
    pick.mark_subs("needs", now=_NOW.strftime("%FT%TZ"))
    ready, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=10))
    assert "needs" not in subs and "needs" not in ready and "needs" in dict(waiting)


def test_撞车合并时本趟投的subs账不丢():
    from merge_orchestration_state import merge_interview_states  # noqa: PLC0415

    base = {"slugs": [], "at": {}, "spec_sha256": {}}
    ours = dict(base, subs={"a": {"at": "2026-09-28T04:00:00Z", "inputs_sha256": "x", "tries": 1}})
    theirs = {"slugs": ["z"], "at": {"z": "2026-09-28T03:00:00Z"}, "spec_sha256": {"z": "y"},
              "subs": {"b": {"at": "2026-09-28T03:30:00Z", "inputs_sha256": "w", "tries": 2}}}
    merged = merge_interview_states(base, ours, theirs)
    assert merged["subs"] == {**theirs["subs"], **ours["subs"]} and merged["slugs"] == ["z"]
    newer = dict(theirs, subs={"a": {"at": "2026-09-28T05:00:00Z", "inputs_sha256": "x2",
                                     "tries": 1}})
    assert merge_interview_states(base, ours, newer)["subs"] == newer["subs"], "远端更新的让远端"


# ---------------------------------------------------------------- 工作流接线

def _wf(name: str) -> list[dict]:
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    return next(iter(doc["jobs"].values()))["steps"]


def _run(name: str, step: str) -> str:
    return next(str(s["run"]) for s in _wf(name) if s.get("name") == step)


def test_auto_render按名单投subs_投成了才记_没过闸的不投(tmp_path):
    body = _run("interview-auto-render.yml", "dispatch 未 render 的正式 spec（每 slug 一个 run，并行）")
    for path in ("/tmp/todo.txt", "/tmp/subs.txt", "/tmp/request-failed.txt",
                 "/tmp/subs-dispatched.md"):
        body = body.replace(path, str(tmp_path / Path(path).name))
    subs_file = tmp_path / "subs.txt"
    stubs = (
        'python() { case "$*" in\n'
        f'  *--mark-subs*) echo "MARKSUBS $3 $5" ;;\n'
        f'  *--mark-one*) echo "MARK $3" ;;\n'
        f'  *--subs-list*) printf "待 dispatch 0 条：\\n"; printf "needs\\nblocked\\n" > {subs_file} ;;\n'
        '  *) : ;; esac; }\n'
        'gh() { echo "GH $*"; [ "${GH_FAIL:-}" = 1 ] && return 1; return 0; }\n'
        'git() { if [ "$1 $2 $3" = "diff --cached --quiet" ]; then return 0; fi; echo "GIT $*"; }\n')
    (tmp_path / "request-failed.txt").write_text("requests/x.json\tblocked\t没过闸\n",
                                                 encoding="utf-8")
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    ran = subprocess.run(["bash", "-eo", "pipefail", "-c", stubs + body], cwd=tmp_path,
                         env=env, capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0, ran.stderr + ran.stdout
    assert "GH workflow run interview-clip.yml --ref main -f slug=needs -f mode=subs" \
        in ran.stdout.splitlines(), ran.stdout
    assert "MARKSUBS needs" in ran.stdout
    assert "slug=blocked" not in ran.stdout and "[跳过] blocked" in ran.stdout
    assert "mode=render" not in ran.stdout, "名单里没有 render 的，一条都不许投"
    assert "needs" in (tmp_path / "summary.md").read_text(encoding="utf-8")
    ran = subprocess.run(["bash", "-eo", "pipefail", "-c", stubs + body], cwd=tmp_path,
                         env={**env, "GH_FAIL": "1"}, capture_output=True, text=True, timeout=30)
    assert ran.returncode == 0 and "MARKSUBS" not in ran.stdout, "投失败的不许记（先投后记）"


def test_auto_render投render的SLA起点取pick给的_记账取真正的派发时刻(tmp_path):
    """`received_at` 要走 `--received-at`（先投过 subs 的从那趟算起），而 `--mark-one` 记的
    得是真正的派发时刻——70 分钟的重投窗口按它算，拿往前拨过的起点记，长一点的 render
    还没落地就会被重投。pick 取不到起点也不许把整趟打红：退回现在。"""
    body = _run("interview-auto-render.yml", "dispatch 未 render 的正式 spec（每 slug 一个 run，并行）")
    for path in ("/tmp/todo.txt", "/tmp/subs.txt", "/tmp/request-failed.txt",
                 "/tmp/subs-dispatched.md"):
        body = body.replace(path, str(tmp_path / Path(path).name))
    subs_file = tmp_path / "subs.txt"
    stubs = (
        'python() { case "$*" in\n'
        '  *--received-at*) [ "${RA_FAIL:-}" = 1 ] && return 1; echo "2026-09-28T03:48:00Z" ;;\n'
        '  *--mark-subs*) echo "MARKSUBS $3 $5" ;;\n'
        '  *--mark-one*) echo "MARK $3 $5" ;;\n'
        f'  *--subs-list*) printf "待 dispatch 1 条：\\nready\\n"; : > {subs_file} ;;\n'
        '  *) : ;; esac; }\n'
        'gh() { echo "GH $*"; return 0; }\n'
        'git() { if [ "$1 $2 $3" = "diff --cached --quiet" ]; then return 0; fi; echo "GIT $*"; }\n')
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    for fail, want in (("", "2026-09-28T03:48:00Z"), ("1", None)):
        ran = subprocess.run(["bash", "-eo", "pipefail", "-c", stubs + body], cwd=tmp_path,
                             env={**env, "RA_FAIL": fail}, capture_output=True, text=True,
                             timeout=30)
        assert ran.returncode == 0, ran.stderr + ran.stdout
        out = ran.stdout.splitlines()
        gh = next(ln for ln in out if "mode=render" in ln)
        mark = next(ln for ln in out if ln.startswith("MARK "))
        dispatched = mark.split()[2]
        assert gh.startswith("GH workflow run interview-clip.yml --ref main -f slug=ready "), gh
        received = gh.rsplit("received_at=", 1)[1]
        if want:
            assert received == want and dispatched != want, (gh, mark)
        else:
            assert received == dispatched, "取不到起点就用现在"
        assert datetime.strptime(dispatched, "%Y-%m-%dT%H:%M:%SZ"), mark


def test_auto_render探针把先投subs的当成活(tmp_path):
    """探针 stdout 那份 render 名单是空的，可有一条要先投 subs——不叫醒全量，这条就一直没人投。"""
    root = tmp_path / "repo"
    (root / "tools").mkdir(parents=True)
    (root / "specs" / "interviews").mkdir(parents=True)
    shutil.copy(ROOT / "tools" / "interview_draft_hold.py", root / "tools")
    (root / "tools" / "build_interview_request.py").write_text("print(0)\n", encoding="utf-8")
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    (root / "tools" / "pick_interview_renders.py").write_text(
        "import sys\n"
        "if '--probe' in sys.argv:\n"
        "    print('待 dispatch 0 条：')\n"
        "    open(sys.argv[sys.argv.index('--subs-list') + 1], 'w').write('needs\\n')\n"
        "elif '--stale' in sys.argv:\n"
        "    print('投出去超过 70 分钟还没有当前成片的：0 条')\n", encoding="utf-8")
    gate = next(s for s in _wf("interview-auto-render.yml") if s.get("name") == "没活就早退")
    body = str(gate["run"]).replace("/tmp/", f"{scratch}/")
    out = tmp_path / "gh_output"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.update({"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(tmp_path / "s.md"),
                "HOME": str(tmp_path / "home")})
    ran = subprocess.run(["bash", "-e", "-c", body], cwd=root, env=env,
                         capture_output=True, text=True, timeout=120)
    assert ran.returncode == 0, ran.stderr
    assert "work=true" in out.read_text(encoding="utf-8"), ran.stdout
    assert "待先跑 subs=1" in ran.stdout


def test_interview_clip的render预检要subs判定_subs干净就叫醒auto_render():
    steps = _wf("interview-clip.yml")
    pre = next(s for s in steps if "tools/interview_preflight.py" in str(s.get("run")))
    assert "mode == 'render'" in pre["if"]
    # 派发者决定口径（2026-09-28）：不再对每一趟 render 无条件 `--require-subs`
    assert '--dispatched-by "$DISPATCHED_BY"' in pre["run"] and "--require-subs" not in pre["run"]
    assert pre["env"]["DISPATCHED_BY"] == "${{ github.triggering_actor }}"
    names = [s.get("name") for s in steps]
    verify = names.index("第二份 ASR 交叉校验并提交报告（subs）")
    assert steps[verify].get("id") == "subs_verify"
    run = str(steps[verify]["run"])
    # 「只报了要人核的发现」那一支在写 clean 之前就 exit 0：有发现不叫醒
    assert run.index('if [ "$STATUS" = 3 ]') < run.index("clean=true")
    wake = steps[names.index("叫醒自动出片（subs 交了干净的判定）")]
    assert wake["if"].count("steps.subs_verify.outputs.clean == 'true'") == 1
    assert "mode == 'subs'" in wake["if"] and "github.ref_name == 'main'" in wake["if"]
    assert "gh workflow run interview-auto-render.yml --ref main" in wake["run"]
    assert names.index("叫醒自动出片（subs 交了干净的判定）") > verify


# ---------------------------------------------------------------- 手动重渲（2026-09-28 会话决定）
#
# 时效第一：已发的采访判定大多没记区间和源（老产物），`--require-subs` 对每一趟 render 都开的话，
# 手动重渲一条要先多拨一趟 `mode=subs`（取字幕约 1 分钟＋第二份 ASR 3~5 分钟，工作流顶上那张表）。现在只对**自动链 pick 派发的** run 开；
# 手动拨的缺判定只提示，「转写交叉校验」那一步在同一个 job 里现量第二份 ASR。

@pytest.mark.parametrize("actor, auto", [("github-actions[bot]", True), ("robertyang87", False),
                                         ("", False)])
def test_render预检只对自动链派发的开dispatch口径_手动拨的缺判定只提示(
        monkeypatch, tmp_path, capsys, actor, auto):
    """不打桩 `spec_problems`：同一条有字幕缓存、没有 subs 判定的 spec，按 interview-clip 那一步
    的真命令行（`--dispatched-by <github.triggering_actor>`）跑 `main()`——自动链派发的报
    `NEEDS_SUBS` 的红，个人拨的（和认不出的）只提示；**已经量出来的红两边都红**。"""
    spec = _spec_with_cache(monkeypatch, tmp_path)
    path = tmp_path / f"{spec['slug']}.json"
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    def run() -> list[str]:
        capsys.readouterr()
        pf.main(["--spec", str(path), "--skip-copy", "--dispatched-by", actor])
        return capsys.readouterr().out.splitlines()

    out = run()
    needs = [ln for ln in out if ln.startswith("❌ " + pf.NEEDS_SUBS)]
    assert bool(needs) == auto, out
    if not auto:
        assert any(ln.startswith("⚠️") and clip.SECOND_ASR_VERDICT in ln for ln in out), out
        assert any("现量第二份 ASR" in ln for ln in out), "手动那一支要说清转写在哪儿验"
    # 量出来的红（分歧 30%、没认领）：谁拨的都红——手动放行的只是「还没量」
    work = pf.OUTPUT / spec["slug"]
    clip.record_second_asr(spec, _lines_as_main(spec, work), work, 0.3, 9, 6)
    assert any(ln.startswith("❌ " + pf.SUBS_RED) for ln in run())


def test_认自动链派发者和看板的无人值守同一个判法():
    """`picker_dispatched` 和 `build_dashboard_snapshot.is_unattended`（workflow_dispatch 那一支）
    必须同一个结论——那边 2026-09-27 实测过编排链派发的 interview-clip 36337385713 的
    `triggering_actor` 是 `github-actions[bot]`、会话拨的是个人登录名。"""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "dash_for_subs_first", ROOT / "tools" / "build_dashboard_snapshot.py")
    dash = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dash)
    for login, kind in (("github-actions[bot]", "Bot"), ("robertyang87", "User")):
        run = {"event": "workflow_dispatch", "triggering_actor": {"login": login, "type": kind}}
        assert pf.picker_dispatched(login) is dash.is_unattended(run), login
    assert pf.picker_dispatched(None) is False and pf.picker_dispatched("  ") is False, \
        "认不出按手动算：那一支照样验转写，按自动算会把人挡在门外"


def test_手动拨的render照样在同一个job里验转写_自动链仍用GITHUB_TOKEN派发():
    """手动那一支靠的是「转写交叉校验」那一步：它只看 mode、不看有没有判定（判定不是 ok 时
    `--stage verify` 现量第二份 ASR，`test_判定ok时verify不重量_补落pass指纹让render认` 钉着
    代码那一半），排在预检之后、剪片之前，faster-whisper 和模型缓存在 render 这一档照装。
    自动链那一支靠 pick 用仓库自带的 token 派发——换成个人 PAT，派发者就不是 [bot] 了。"""
    steps = _wf("interview-clip.yml")
    names = [s.get("name") for s in steps]
    pre = next(i for i, s in enumerate(steps) if "tools/interview_preflight.py" in str(s.get("run")))
    at = names.index("转写交叉校验")
    verify = steps[at]
    assert verify["if"].strip() == "github.event.inputs.mode == 'render'", verify["if"]
    assert "--stage verify" in verify["run"]
    assert pre < at < names.index("剪 + 烧字幕")
    deps = steps[names.index("装依赖")]["run"]
    assert 'if [ "$MODE" = "render" ]; then EXTRA_ASR="faster-whisper"' in deps
    assert "mode == 'render'" in steps[names.index("缓存第二份 ASR 模型")]["if"]
    auto = next(s for s in _wf("interview-auto-render.yml")
                if "gh workflow run interview-clip.yml" in str(s.get("run")))
    assert auto["env"]["GH_TOKEN"] in ("${{ secrets.GITHUB_TOKEN }}", "${{ github.token }}")


# ---------------------------------------------------------------- 复审第三轮（2026-09-28）

def test_换了源片判定不作数_没记源的老量数也不作数(monkeypatch, tmp_path):
    """nit 1：写 `asr_model` 的 spec，第一份转写读仓库里的 `cap_asr.json3`、不看 URL——同一个区间换
    一条源片，行一字不差、指纹一字不差（复审在 tien-cobolli 上复现过），判定却照旧 ok、render
    跳过重量，拿旧片子量的数给新片子出片。量数、pass、空档证据都记源，`subs_verdict` 一处认；
    没记源的老量数 → 缺判定（重量一趟，老行为）。人核过那一支只在 pass 记了源而对不上时不认。"""
    out = _outdir(tmp_path)
    spec = dict(_SPEC)
    clip.record_second_asr(spec, _LINES, out, 0.02, 300, 300)
    _attest(spec, out, "no_speech")
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"
    swapped = dict(spec, url="https://example.test/another-video")
    assert clip.transcript_fingerprint(swapped, _LINES, out) == \
        clip.transcript_fingerprint(spec, _LINES, out), "前提：换源指纹不变"
    got = clip.subs_verdict(swapped, _LINES, out)
    assert got.state == "needs_subs" and not got.reds, got
    assert any("源" in p for p in got.pending) and any(GAP in p for p in got.pending), got.pending
    # 没记源的老量数、老 pass：不算
    fp = clip.transcript_fingerprint(spec, _LINES, out)
    rec = json.loads((out / clip.SECOND_ASR_VERDICT).read_text(encoding="utf-8"))
    rec.pop("url")
    (out / clip.SECOND_ASR_VERDICT).write_text(json.dumps(rec), encoding="utf-8")
    assert clip.subs_verdict(spec, _LINES, out).state == "needs_subs", "没记源的老量数不许放行"
    (out / clip.SECOND_ASR_VERDICT).unlink()
    (out / clip.VERIFY_FP).write_text(json.dumps({"sha256": fp, "status": "pass",
                                                  "window": clip.verdict_window(spec)}))
    assert clip.subs_verdict(spec, _LINES, out).state == "needs_subs", "没记源的老 pass 不许放行"
    # 人核过：老 pass 没记源照旧认（人的标记）；记了源而对不上＝人核的是换源之前那条
    human = dict(spec, transcript_verified=True)
    assert clip.subs_verdict(human, _LINES, out).state == "ok"
    (out / clip.VERIFY_FP).write_text(json.dumps({"sha256": fp, "status": "pass",
                                                  "url": spec["url"]}))
    assert clip.subs_verdict(dict(swapped, transcript_verified=True), _LINES, out).state \
        == "needs_subs"
    # ⚠️ 上一句红的其实是空档证据（它记的是旧源，换源后那处空档成了缺判定），不是人核那一支——
    # 拿掉「pass 记的源要对得上」那个条件它照样绿（复审第四轮）。空档由人销账（或者没有空档）时，
    # 挡着的**只剩**这一个条件
    closed = dict(human, caption_gaps_ok={GAP: "人听过：掌声"})
    assert clip.subs_verdict(closed, _LINES, out).state == "ok"
    got = clip.subs_verdict(dict(closed, url=swapped["url"]), _LINES, out)
    assert got.state == "needs_subs" and any("源" in p for p in got.pending), (
        "人核的是换源之前那条片子，换了源照样凭「人核过」放行", got)
    # render 的 verify：换源之后不跳过、真重量
    rundir = tmp_path / "out" / "demo"
    rundir.mkdir(parents=True)
    clip.record_second_asr(spec, _LINES, rundir, 0.02, 300, 300)
    got = _drive_verify(monkeypatch, tmp_path, spec, [])
    assert got["verify"] == 0 and got.get("rc") == 0, got
    assert json.loads((rundir / clip.VERIFY_FP).read_text(encoding="utf-8"))["url"] == spec["url"]
    got = _drive_verify(monkeypatch, tmp_path, swapped, [])
    assert got["verify"] == 1, "换了源片还跳过重量——拿旧片子量的数出片"
    # 人核过的那一支同理：pass 记的是旧源，render 不许凭「人核过」跳过第二份 ASR
    # （`transcript_verified and recorded == fp and not verdict.pending` 那一跳）
    (rundir / clip.VERIFY_FP).write_text(json.dumps({
        "sha256": clip.transcript_fingerprint(spec, _LINES, rundir), "status": "pass",
        "url": spec["url"]}))
    got = _drive_verify(monkeypatch, tmp_path, dict(spec, transcript_verified=True), [])
    assert got["verify"] == 0, "对照：同一条源、人核过，照旧跳过"
    got = _drive_verify(monkeypatch, tmp_path, dict(swapped, transcript_verified=True), [])
    assert got["verify"] == 1, "人核的是换源之前那条片子，render 还凭「人核过」跳过重量"


def test_subs那一趟落的判定都记着源_下一趟不再缺判定(monkeypatch, tmp_path):
    """绑源不能变成死循环：一趟新的 subs（`verify_transcript` 那条路）落的量数和空档证据都带 `url`，
    下一趟预检就认得出——不会因为「没记源」一趟趟重投。"""
    out = _outdir(tmp_path)
    monkeypatch.setattr(clip, "yt_download", lambda url, dest, fmt, spec: dest)
    _fake_faster_whisper(monkeypatch, [(0.1, 0.4, "Thank"), (0.5, 0.9, "you"),
                                       (6.1, 6.5, "great"), (6.5, 6.9, "match")])
    spec = dict(_SPEC)
    clip.verify_transcript(spec, _LINES, out)
    assert json.loads((out / clip.SECOND_ASR_VERDICT).read_text(encoding="utf-8"))["url"] \
        == spec["url"]
    assert json.loads((out / clip.GAP_VAD_ATTESTATION).read_text(encoding="utf-8"))["url"] \
        == spec["url"]
    assert clip.subs_verdict(spec, _LINES, out).state == "ok"


def _timeline_rows(spec: dict, out: Path) -> None:
    """三种自动销账各一行：VAD 证的静默、双 ASR 的边界漂移、字幕时间轴盖住（VAD 其实听到了人声）。"""
    rows = [
        {"key": "1.0-6.0", "start": 1.0, "end": 6.0, "speech_seconds": 1.8,
         "second_asr_words": ["we", "played"], "transcript_covered": False,
         "caption_timeline_covered": True, "status": "caption_timeline_covered"},
        {"key": "8.0-11.0", "start": 8.0, "end": 11.0, "speech_seconds": 0.0,
         "second_asr_words": [], "transcript_covered": False,
         "caption_timeline_covered": False, "status": "no_speech"},
        {"key": "12.0-15.0", "start": 12.0, "end": 15.0, "speech_seconds": 2.4,
         "second_asr_words": ["great", "match"], "transcript_covered": True,
         "caption_timeline_covered": False, "status": "transcript_covered"},
    ]
    (out / clip.GAP_VAD_ATTESTATION).write_text(json.dumps({
        "status": "pass", "method": "silero_vad_plus_dual_asr_coverage",
        "sha256": clip.transcript_fingerprint(spec, _LINES, out), "url": spec["url"],
        "results": rows}), encoding="utf-8")


def test_字幕时间轴销账照实写人声和词_只有VAD证的静默才叫VAD自动销账(tmp_path):
    """D1：`caption_timeline_covered` 那一种照旧自动销账（老行为），可报告不许读起来像 VAD 证过
    没人说话——仓库里 32 行这一类有 14 行 VAD 测到了人声。理由里印人声秒数和听到的词，标签按依据分；
    caption_gaps.md 和核对表印的是同一句。"""
    out = _outdir(tmp_path)
    spec = dict(_SPEC)
    _timeline_rows(spec, out)
    auto = clip.auto_gap_closures(spec, _LINES, out)
    assert set(auto) == {"1.0-6.0", "8.0-11.0", "12.0-15.0"}, "销不销账照旧"
    timeline, quiet, drift = auto["1.0-6.0"], auto["8.0-11.0"], auto["12.0-15.0"]
    assert quiet.startswith("VAD 自动销账") and "没人说话" in quiet
    for text, secs, words in ((timeline, "1.800s", "we played"), (drift, "2.400s", "great match")):
        assert "VAD 自动销账" not in text and "没人说话，自动销账" not in text, text
        assert secs in text and words in text, text
        assert "不是 VAD 证明没人说话" in text, text
    assert timeline.startswith("字幕时间轴自动销账") and drift.startswith("双 ASR 自动销账")
    gaps_md = clip.probe_gap_speech(spec, [(1.0, 6.0), (8.0, 11.0)], [], out, auto=auto)
    body = gaps_md.read_text(encoding="utf-8")
    section = body[body.index("1.0–6.0"):body.index("8.0–11.0")]
    assert "字幕时间轴自动销账" in section and "VAD 自动销账" not in section, section
    assert "1.800s" in section and "we played" in section
    assert "VAD 自动销账" in body[body.index("8.0–11.0"):]
    sheet = clip.review_sheet(dict(spec, zh=["谢谢", "好比赛"]), _LINES, out).read_text(
        encoding="utf-8")
    row = next(ln for ln in sheet.splitlines() if "1.0–6.0 秒" in ln)
    assert "字幕时间轴自动销账" in row and "VAD 自动销账" not in row and "1.800s" in row, row
    notes = clip.subs_verdict(dict(spec, caption_gaps_ok={}), _LINES, out).notes
    assert not any(n.startswith("空档") and "VAD 自动销账" in n for n in notes), notes


def _drive_main(monkeypatch, tmp_path: Path, spec: dict, stage: str,
                raise_in: dict[str, BaseException] | None = None) -> dict:
    """真跑 `main()`，网络、whisper、下载换成替身；`raise_in` 里点名的闸抛那个异常。"""
    calls: dict = {"verify": 0}
    for name in ("check_source_contract", "check_tennistv_logo", "check_topline_format",
                 "check_score_orientation", "check_opening", "check_lead_in", "check_trail_in",
                 "check_copy_page", "check_copy_bilingual", "check_cover_hook", "check_taste",
                 "check_taste_extra", "check_human_quote", "storyboard_sheet", "write_ass",
                 "review_sheet", "report_takeaway_polyphones"):
        monkeypatch.setattr(clip, name, lambda *a, **k: None)
    for name, exc in (raise_in or {}).items():
        def boom(*a, _exc=exc, **k):
            raise _exc
        monkeypatch.setattr(clip, name, boom)
    monkeypatch.setattr(clip, "OUTDIR", tmp_path / "out")
    monkeypatch.setattr(clip, "fetch_words", lambda *a, **k: [])
    monkeypatch.setattr(clip, "segment", lambda *a, **k: [dict(x) for x in _LINES])
    monkeypatch.setattr(clip, "caption_gaps", lambda *a, **k: [])

    def fake_verify(*a, **k):
        calls["verify"] += 1
    monkeypatch.setattr(clip, "verify_transcript", fake_verify)
    monkeypatch.setattr(clip, "render", lambda *a, **k: pytest.fail("不该走到编码"))
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_interview_clip.py", "--spec", str(spec_path),
                                      "--stage", stage])
    try:
        calls["rc"] = clip.main()
    except SystemExit as exc:
        calls["exit"] = str(exc)
    return calls


@pytest.mark.parametrize("stage", ["subs", "verify"])
def test_subs和verify两档里出片那排闸只报不拦_L0和切行照旧拦(monkeypatch, tmp_path, capsys, stage):
    """D2：subs 要能和写中文、挑封面、写小红书正文并行跑。缺 xhs（`check_copy_page`）、封面重点词
    不在标题里、中文排不进去——都不碰转写指纹，只交转写判定的两档**只报不拦**；L0（下错了源）、
    人工引语对不上照旧拦（`en_fixed` 挂错行那道也在切行之后、不分档）。render／cover 那几档一道都不放。"""
    spec = dict(_SPEC, zh=["谢谢", "好比赛"])
    got = _drive_main(monkeypatch, tmp_path, spec, stage, {
        "check_copy_page": SystemExit("缺 specs/interviews/demo.xhs.txt"),
        "write_ass": SystemExit("中文超宽 952px")})
    assert got.get("rc") == 0 and "exit" not in got, got
    printed = capsys.readouterr().out
    assert "缺 specs/interviews/demo.xhs.txt" in printed and "中文超宽 952px" in printed, printed
    assert got["verify"] == (1 if stage == "verify" else 0), "verify 那一档照样量第二份 ASR"
    got = _drive_main(monkeypatch, tmp_path, spec, stage, {
        "check_cover_hook": ValueError("cover.title 缺了")})
    assert got.get("rc") == 0, "崩在出片那排闸上也不许挡住转写判定"
    got = _drive_main(monkeypatch, tmp_path, spec, stage, {
        "check_source_contract": SystemExit("L0：演播室采访")})
    assert got.get("exit") == "L0：演播室采访", got
    got = _drive_main(monkeypatch, tmp_path, spec, stage, {
        "check_human_quote": SystemExit("人工引语对不上：第 2 行")})
    assert got.get("exit") == "人工引语对不上：第 2 行", got


@pytest.mark.parametrize("stage", ["render", "cover", "sheet"])
def test_出片那几档出片那排闸照旧拦(monkeypatch, tmp_path, stage):
    spec = dict(_SPEC, zh=["谢谢", "好比赛"], cover={"frame_at": 1})
    got = _drive_main(monkeypatch, tmp_path, spec, stage, {
        "check_copy_page": SystemExit("缺 specs/interviews/demo.xhs.txt")})
    assert got.get("exit") == "缺 specs/interviews/demo.xhs.txt", got
    if stage == "render":
        got = _drive_main(monkeypatch, tmp_path, spec, stage,
                          {"write_ass": SystemExit("中文超宽 952px")})
        assert got.get("exit") == "中文超宽 952px", got


def _fresh(pick, slug: str = "fresh", **extra) -> Path:
    """刚转正、只有转写输入的 spec：中文、解读卡、封面、小红书正文、开场认领都还没有。"""
    body = {"slug": slug, "url": f"https://example.test/{slug}", "start": 0.0, "end": 30.0,
            "asr_model": "small.en", **extra}
    path = pick.SPECS / f"{slug}.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def test_转写输入齐了就先投subs_不等中文封面文案(pick):
    """D2：原来缺中文／封面／小红书正文，预检整个不跑，「缺 subs 判定」判不出来——第二份 ASR 排在
    所有文字工作之后。现在有 url／start／end 就投 subs；render 照旧要当前指纹上 ok 的判定。"""
    import interview_preflight  # noqa: PLC0415

    need = f"{interview_preflight.NEEDS_SUBS}当前转写指纹没有第二份 ASR 的分歧量数"
    pick._VERDICTS_FIXTURE["fresh"] = [need]
    _fresh(pick)
    ready, waiting, subs = pick.todo_plan(now=_NOW)
    assert "fresh" in subs and "fresh" not in ready and "fresh" not in dict(waiting), (ready, subs)
    # 没有转写输入（连 url 都没有）：不投 subs，预检也不跑
    pick._VERDICTS_FIXTURE["bare"] = [need]
    (pick.SPECS / "bare.json").write_text(json.dumps({"slug": "bare"}), encoding="utf-8")
    ready, waiting, subs = pick.todo_plan(now=_NOW)
    assert "bare" not in subs and "bare" in dict(waiting)
    assert not any(interview_preflight.NEEDS_SUBS in m for m in dict(waiting)["bare"])
    # L0 红：挡（下错了源，量出来的是别的片子）
    real = pick.validate_source_contract

    def l0(spec):
        if spec.get("slug") == "fresh":
            raise pick.SourceContractError("演播室采访")
        return real(spec)
    pick.validate_source_contract = l0
    try:
        _, waiting, subs = pick.todo_plan(now=_NOW)
    finally:
        pick.validate_source_contract = real
    assert "fresh" not in subs and any(pick.L0_MISSING in m for m in dict(waiting)["fresh"])
    # 判定交上来、ok 了：还缺中文那几样 → 进等待，不投 render 也不再投 subs
    pick._VERDICTS_FIXTURE["fresh"] = []
    ready, waiting, subs = pick.todo_plan(now=_NOW)
    assert "fresh" not in subs and "fresh" not in ready and "zh" in "、".join(dict(waiting)["fresh"])


def test_不重复投_在跑的subs不重投_改中文封面不掐它_render在跑不投subs_发布过的不投(pick):
    import interview_preflight  # noqa: PLC0415

    need = f"{interview_preflight.NEEDS_SUBS}当前转写指纹没有第二份 ASR 的分歧量数"
    pick._VERDICTS_FIXTURE["fresh"] = [need]
    path = _fresh(pick)
    pick.mark_subs("fresh", now=_NOW.strftime("%FT%TZ"))
    # 在跑的那趟窗口里：补中文、封面、文案都不重投（不碰转写输入）
    body = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(dict(body, zh=["一"], cover={"frame_at": 3},
                                    takeaway={"close": {"point": "x"}})), encoding="utf-8")
    (pick.SPECS / "fresh.xhs.txt").write_text("文案", encoding="utf-8")
    ready, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=30))
    assert "fresh" not in subs and "fresh" not in ready, (ready, subs)
    assert "已投 subs" in dict(waiting)["fresh"][0]
    # render 在跑（刚投、窗口里）：同 slug 投 subs 会把它掐掉——不投
    pick.mark_one("needs", now=_NOW.strftime("%FT%TZ"))
    _, _, subs = pick.todo_plan(now=_NOW + timedelta(minutes=5))
    assert "needs" not in subs
    # 发布过的（有 pushed.json、没有修订）：缺判定也不投
    pushed = pick.OUTPUT / "mixed" / "pushed.json"
    pushed.parent.mkdir(parents=True)
    pushed.write_text(json.dumps({"film_sha256": "x"}), encoding="utf-8")
    ready, waiting, subs = pick.todo_plan(now=_NOW)
    assert "mixed" not in subs and "mixed" not in ready


def test_探针见还缺中文的spec判不了转写那一半_算活_投过subs就不算(pick, monkeypatch):
    """探针（没 PIL）判不了转写指纹。一条还缺中文、封面的 spec，原来探针直接把它算成「等人」——
    全量那一趟不醒，subs 就一直没人投。现在没有同一份输入的全量结论就算「可能要先投 subs」，
    叫醒全量；刚投过 subs 的不算活。"""
    import interview_preflight  # noqa: PLC0415

    _fresh(pick)
    monkeypatch.setattr(pick, "_code_fingerprint", lambda: "code")
    monkeypatch.setattr(interview_preflight, "caption_fingerprint", lambda slug: [])

    def unavailable(s, **kw):
        raise interview_preflight.PreflightUnavailable("缺 PIL")
    monkeypatch.setattr(interview_preflight, "spec_problems", unavailable)
    monkeypatch.setattr(interview_preflight, "probe_problems",
                        lambda s: (["check_copy_page：缺 xhs"], ["量宽度"]))
    monkeypatch.setattr(pick, "PROBE", True)
    ready, _, subs = pick.todo_plan(now=_NOW)
    assert "fresh" in subs and "fresh" not in ready, (ready, subs)
    pick.mark_subs("fresh", now=_NOW.strftime("%FT%TZ"))
    ready, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=10))
    assert "fresh" not in subs and "fresh" in dict(waiting)


def test_subs重投窗口长于interview_clip的job超时():
    """nit 2：subs 跑在 interview-clip 同一个 job 里，而那条工作流 cancel-in-progress——重投窗口
    比 job 超时短，一趟慢的 subs 还在跑就被重投的那趟掐掉（和 `STALE_MINUTES` 同一条规矩，
    原来写的是 40 对 65）。按 YAML 读，不按注释里的数。"""
    import pick_interview_renders as p  # noqa: PLC0415
    import yaml  # noqa: PLC0415

    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "interview-clip.yml").read_text(
        encoding="utf-8"))
    assert doc["concurrency"]["cancel-in-progress"] is True
    timeouts = [int(job["timeout-minutes"]) for job in doc["jobs"].values()]
    assert timeouts and p.SUBS_STALE_MINUTES > max(timeouts), (p.SUBS_STALE_MINUTES, timeouts)
    assert p.SUBS_SLA_MINUTES < p.SUBS_STALE_MINUTES, "SLA 窗口不跟着重投窗口放宽"


def test_subs那一趟只提交自己那一格():
    """D2 的前提：subs 和人改 spec、别的 slug 的派发并行跑，它提交的只能是
    `output/interviews/<slug>/`——碰到 spec 或别人的产物就是撞车。按 YAML 找出 auto-render 那样
    派发的 subs（`mode=subs`，`push` 取默认 false）会跑的每一步——`if` 按这组输入求值；引用的
    那一步这一档根本不跑，它的 `outcome` 就是 `skipped`、`outputs` 是空的；其余判不了的
    （`env.*`、`always()`、跑了的那一步的输出）一律当会跑——它们的 `git add` 只许 add 那一格。"""
    import re  # noqa: PLC0415

    ran: dict[str, bool] = {}

    def may_run(cond: str) -> bool:
        if not cond:
            return True
        expr = (cond.replace("github.event.inputs.mode", "'subs'")
                .replace("github.event.inputs.push", "'false'")
                .replace("github.ref_name", "'main'"))

        def step_ref(m: re.Match) -> str:
            sid, field = m.group(1), m.group(2)
            if ran.get(sid) is False:
                return "'skipped'" if field in ("outcome", "conclusion") else "''"
            return "__unknown__"
        expr = re.sub(r"steps\.([\w\-]+)\.(outcome|conclusion|outputs\.[\w\-]+)", step_ref, expr)
        expr = re.sub(r"env\.[\w\-]+", "__unknown__", expr)
        expr = re.sub(r"__unknown__\s*(?:==|!=)\s*'[^']*'", "True", expr)
        expr = re.sub(r"\b(?:always|failure|success)\(\)", "True", expr)
        return bool(eval(expr.replace("&&", " and ").replace("||", " or ")))  # noqa: S307

    steps = _wf("interview-clip.yml")
    adds = []
    for step in steps:
        runs = may_run(str(step.get("if") or ""))
        if step.get("id"):
            ran[str(step["id"])] = runs
        if not runs:
            continue
        body = str(step.get("run", ""))
        dirs = re.findall(r'^\s*(?:D|OUTDIR)="([^"]+)"', body, re.M)
        # 只在 render 档才赋值的变量（封面自动换帧改过的 spec，`$AUTOPICK_SPEC`）：subs 那一档
        # 它恒为空串，`git add` 碰不到 spec。只认紧跟在 `if [ "$MODE" = "render" ] && …; then`
        # 下面那一行的赋值——守卫一拆，它就回到「不许 add」那一堆里
        render_only = re.findall(
            r'^\s*if \[ "\$MODE" = "render" \] && [^\n]*; then\n\s*(\w+)="specs/', body, re.M)
        for ln in body.splitlines():
            code = ln.split(" #", 1)[0].strip()
            if code.startswith("#") or "git add" not in code:
                continue
            adds.append((step.get("name"), code[code.index("git add"):], dirs, render_only))
    assert adds, "扫描面坏了：subs 那一档一个 git add 都没抠到"
    assert {name for name, _, _, _ in adds} >= {"提交成片", "第二份 ASR 交叉校验并提交报告（subs）"}, adds
    ran.clear()
    assert not may_run("github.event.inputs.push == 'true' && steps.x.outputs.found == 'true'")
    for name, ln, dirs, render_only in adds:
        assert dirs and all(d.startswith("output/interviews/") for d in dirs), (name, dirs)
        targets = [t for t in ln.split()[2:] if not t.startswith("-")]
        allowed = {"$D", "$REC", "$OUTDIR", *(f"${v}" for v in render_only)}
        assert targets and all(t.strip('"') in allowed for t in targets), (name, ln)


def test_subs账判定交上来就删_投render那一下删_撞车合并带着删(pick):
    """nit 4：render 那一份从来不删；`subs` 这一份的 `tries` 只在「同一份转写输入还缺判定」时有用，
    判定交上来了（红了等人、ok 了投 render）、spec 没了就删——只删过了重投窗口的（窗口里那趟可能
    还在跑）；ok 且这一趟要投 render 的留着给 SLA 起点，`mark_one` 投出去那一刻删。"""
    from merge_orchestration_state import merge_interview_states  # noqa: PLC0415

    at = lambda m: (_NOW + timedelta(minutes=m)).strftime("%FT%TZ")  # noqa: E731
    for slug in ("needs", "mixed", "clean", "enfix"):
        pick.mark_subs(slug, now=at(0))
    (pick.SPECS / "enfix.json").unlink()                     # spec 没了
    pick._VERDICTS_FIXTURE["mixed"] = ["字幕（出片那一趟 write_ass 会红在这儿）：中文超宽"]  # 判定交了
    late = _NOW + timedelta(minutes=pick.SUBS_STALE_MINUTES + 5)
    ready, _, _ = pick.todo_plan(now=late)
    assert "clean" in ready
    assert pick.sync_subs_state(now=late) == ["enfix", "mixed"]
    book = json.loads(pick.STATE.read_text())["subs"]
    assert set(book) == {"needs", "clean"}, "还缺判定的、要投 render 的（SLA 起点）留着"
    pick.mark_one("clean", now=at(80))
    assert "clean" not in json.loads(pick.STATE.read_text())["subs"], "投了 render 就用完了"
    # 窗口里的不删：那趟可能还在跑
    pick.mark_subs("mixed", now=at(100))
    pick.todo_plan(now=_NOW + timedelta(minutes=110))
    pick.sync_subs_state(now=_NOW + timedelta(minutes=110))
    assert "mixed" in json.loads(pick.STATE.read_text())["subs"]
    # 撞车合并：本趟删的带过去；远端这一条又投过一趟（更新）就听远端的
    rec = {"at": at(0), "inputs_sha256": "x", "tries": 1}
    base = {"slugs": [], "at": {}, "spec_sha256": {}, "subs": {"a": rec, "b": rec}}
    ours = dict(base, subs={})
    theirs = dict(base, subs={"a": rec, "b": dict(rec, at=at(90), tries=2)})
    merged = merge_interview_states(base, ours, theirs)
    assert merged["subs"] == {"b": theirs["subs"]["b"]}, merged["subs"]


def test_同一份转写输入投满次数停下_账上标parked_pipeline_health列出来(pick, tmp_path, monkeypatch):
    """nit 3：原来停下之后只在 auto-render 的 stderr（等待名单）里印一行，不翻日志看不见，而停下的
    原因（下不动源片、判定绑的指纹对不上）自动链修不好。pick 全量那一趟标 `parked`，pipeline-health
    读标记列进报告和告警（次数上限只在 pick 定义一次）；不再停着的摘掉标记。"""
    sys.path.insert(0, str(ROOT))
    from tools import pipeline_health as ph  # noqa: PLC0415

    at = lambda m: (_NOW + timedelta(minutes=m)).strftime("%FT%TZ")  # noqa: E731
    for i in range(pick.SUBS_MAX_TRIES):
        pick.mark_subs("needs", now=at(i * 80))
    now = _NOW + timedelta(minutes=pick.SUBS_MAX_TRIES * 80 + 1)
    _, waiting, subs = pick.todo_plan(now=now)
    assert "needs" not in subs and "预检还是认不出" in dict(waiting)["needs"][0]
    pick.sync_subs_state(now=now)
    assert json.loads(pick.STATE.read_text())["subs"]["needs"].get("parked") is True
    alerts = ph.parked_interview_subs(pick.STATE)
    assert len(alerts) == 1 and "needs" in alerts[0] and f"{pick.SUBS_MAX_TRIES} 趟" in alerts[0]
    report, got = ph.render_report([], [], (0, 0, 0.0), [], None, parked_subs=alerts)
    assert "采访 subs 停着" in report and alerts[0] in got
    assert ph.alert_keys(alerts) == ["interview-subs:needs"]
    body = (ROOT / "tools" / "pipeline_health.py").read_text(encoding="utf-8")
    call = body[body.index("report, alerts = render_report("):]
    assert "parked_interview_subs()" in call[:300], "main() 没把停下的 subs 传给报表——等于没装"
    wf = (ROOT / ".github" / "workflows" / "pipeline-health.yml").read_text(encoding="utf-8")
    checkout = wf.split("actions/checkout@v4", 1)[1].split("- name:", 1)[0]
    assert "data/interview_render_dispatched.json" in checkout, "稀疏检出没带状态文件：读不到＝没有"
    # 转写输入改了：不再停着，标记摘掉
    path = pick.SPECS / "needs.json"
    path.write_text(json.dumps(dict(json.loads(path.read_text()), end=42.0)), encoding="utf-8")
    pick.todo_plan(now=now)
    pick.sync_subs_state(now=now)
    assert "parked" not in json.loads(pick.STATE.read_text())["subs"]["needs"]
    assert ph.parked_interview_subs(pick.STATE) == []


def test_转写判定红着的记下从哪一刻起_超过6小时pipeline_health列出来(pick):
    """2026-09-28 会话决定（F3）：subs 交了红的判定，auto-render 只把它放进 stderr 的等待名单
    （那一趟 subs 退出码 3 是绿的、也不叫醒谁），不翻日志看不见。全量那一趟判红时记 `subs_red`
    （`since`＝第一次见它红，同一份转写输入接着红不动；转写输入改了重新算；不红了删掉），
    pipeline-health 按 `since` 超过 6 小时才列，键只认 slug（「红着已 N 小时」每班都长）。"""
    import interview_preflight  # noqa: PLC0415

    sys.path.insert(0, str(ROOT))
    from tools import pipeline_health as ph  # noqa: PLC0415

    at = lambda h: (_NOW + timedelta(hours=h)).strftime("%FT%TZ")  # noqa: E731
    spec = json.loads((pick.SPECS / "needs.json").read_text(encoding="utf-8"))
    (pick.SPECS / "red.json").write_text(json.dumps(dict(spec, slug="red")), encoding="utf-8")
    (pick.SPECS / "red.xhs.txt").write_text("文案", encoding="utf-8")
    pick._VERDICTS_FIXTURE["red"] = [f"{interview_preflight.SUBS_RED}第二份 ASR 在当前转写指纹上"
                                     "量到：分歧 30.0%（闸门 12%），没有认领"]
    _, waiting, subs = pick.todo_plan(now=_NOW)
    assert "red" in dict(waiting) and "red" not in subs
    assert pick.sync_waiting_marks(now=_NOW) is True
    book = json.loads(pick.STATE.read_text(encoding="utf-8"))["subs_red"]
    assert set(book) == {"red"} and book["red"]["since"] == at(0) and "30.0%" in book["red"]["why"]
    # 一小时后还红着、转写输入没变：`since` 不动
    pick.todo_plan(now=_NOW + timedelta(hours=1))
    pick.sync_waiting_marks(now=_NOW + timedelta(hours=1))
    assert json.loads(pick.STATE.read_text(encoding="utf-8"))["subs_red"]["red"]["since"] == at(0)
    assert ph.interview_subs_red_waiting(now=_NOW + timedelta(hours=5), path=pick.STATE) == []
    alerts = ph.interview_subs_red_waiting(now=_NOW + timedelta(hours=7), path=pick.STATE)
    assert len(alerts) == 1 and alerts[0].startswith(ph.SUBS_RED_WAITING + "red（"), alerts
    assert "7 小时" in alerts[0] and "30.0%" in alerts[0]
    later = ph.interview_subs_red_waiting(now=_NOW + timedelta(hours=30), path=pick.STATE)
    assert ph.alert_keys(alerts) == ph.alert_keys(later) == ["interview-subs-red:red"]
    report, got = ph.render_report([], [], (0, 0, 0.0), [], None, subs_red=alerts)
    assert "采访转写判定红着超过 6 小时" in report and alerts[0] in got
    # 人改了转写输入（区间），还是红（要重量）：从这一刻重新算
    (pick.SPECS / "red.json").write_text(json.dumps(dict(spec, slug="red", end=42.0)),
                                         encoding="utf-8")
    pick.todo_plan(now=_NOW + timedelta(hours=8))
    pick.sync_waiting_marks(now=_NOW + timedelta(hours=8))
    assert json.loads(pick.STATE.read_text(encoding="utf-8"))["subs_red"]["red"]["since"] == at(8)
    # 认领够了、不红了：账上删掉，pipeline-health 不再列
    pick._VERDICTS_FIXTURE["red"] = []
    pick.todo_plan(now=_NOW + timedelta(hours=9))
    pick.sync_waiting_marks(now=_NOW + timedelta(hours=9))
    assert "subs_red" not in json.loads(pick.STATE.read_text(encoding="utf-8"))
    assert ph.interview_subs_red_waiting(now=_NOW + timedelta(days=3), path=pick.STATE) == []
    body = (ROOT / "tools" / "pipeline_health.py").read_text(encoding="utf-8")
    call = body[body.index("report, alerts = render_report("):]
    assert "subs_red=interview_subs_red_waiting()" in call[:500], "main() 没把红着的转写传给报表"
    wf = (ROOT / ".github" / "workflows" / "interview-auto-render.yml").read_text(encoding="utf-8")
    assert "--sync-subs" in wf, "记账只在全量那一趟（--sync-subs）跑"
    src = (ROOT / "tools" / "pick_interview_renders.py").read_text(encoding="utf-8")
    sync = src[src.index("        if args.sync_subs:"):]
    assert "sync_waiting_marks()" in sync[:400], "--sync-subs 没调 sync_waiting_marks——等于没装"


def test_红着的转写那本账撞车合并不丢_远端动过听远端的():
    from merge_orchestration_state import merge_interview_states  # noqa: PLC0415

    base = {"slugs": [], "at": {}, "spec_sha256": {}}
    row = {"since": "2026-09-28T04:00:00Z", "inputs_sha256": "i", "why": "分歧 30%"}
    merged = merge_interview_states(base, {**base, "subs_red": {"red": row}},
                                    {**base, "slugs": ["x"], "at": {"x": "t"}})
    assert merged["subs_red"] == {"red": row} and merged["slugs"] == ["x"]
    # 本趟删掉（不红了）：带过去
    merged = merge_interview_states({**base, "subs_red": {"red": row}}, base,
                                    {**base, "subs_red": {"red": row}})
    assert "subs_red" not in merged
    # 远端自己改过这一条（更早的 since）：听远端的
    older = dict(row, since="2026-09-28T03:00:00Z")
    merged = merge_interview_states(base, {**base, "subs_red": {"red": row}},
                                    {**base, "subs_red": {"red": older}})
    assert merged["subs_red"] == {"red": older}


def test_停着的那条探针判不了就叫醒全量_全量判过缓存命中就不再叫醒(pick, monkeypatch):
    """复审第四轮：停着（parked）的一条还缺中文，人修好原因、手动投了 mode=subs、判定落了——判定文件
    在预检缓存的键里（`caption_fingerprint`），探针缓存不命中、退回「判不了转写那一半」。原来
    `_subs_block` 照旧按次数判 parked、探针不算活：全量那一趟不醒，`--sync-subs` 跑不到，parked 标记
    一直挂着、pipeline-health 一直喊。现在探针判不了的停着那条算活（只叫醒全量）；全量判过、缓存
    命中之后，真还停着的探针不再叫醒它（不会每 10 分钟逼一趟全量）。"""
    import interview_preflight  # noqa: PLC0415

    _fresh(pick)
    monkeypatch.setattr(pick, "_code_fingerprint", lambda: "code")
    monkeypatch.setattr(interview_preflight, "caption_fingerprint", lambda slug: [])
    at = lambda m: (_NOW + timedelta(minutes=m)).strftime("%FT%TZ")  # noqa: E731
    for i in range(pick.SUBS_MAX_TRIES):
        pick.mark_subs("fresh", now=at(i * 80))
    now = _NOW + timedelta(minutes=pick.SUBS_MAX_TRIES * 80 + 1)

    def unavailable(s, **kw):
        raise interview_preflight.PreflightUnavailable("缺 PIL")
    monkeypatch.setattr(interview_preflight, "spec_problems", unavailable)
    monkeypatch.setattr(interview_preflight, "probe_problems",
                        lambda s: (["check_copy_page：缺 xhs"], ["量宽度"]))
    monkeypatch.setattr(pick, "PROBE", True)
    _, waiting, subs = pick.todo_plan(now=now)
    assert "fresh" in subs, ("停着的那条探针判不了还不算活：全量不醒，parked 永远摘不掉", waiting)
    # 全量判过（还缺判定＝真还停着）、缓存命中：探针不再叫醒
    need = f"{interview_preflight.NEEDS_SUBS}当前转写指纹没有第二份 ASR 的分歧量数"
    pick._verdicts()["fresh"] = {"key": pick.verdict_key("fresh"),
                                 "missing": ["check_copy_page：缺 xhs", need]}
    _, waiting, subs = pick.todo_plan(now=now)
    assert "fresh" not in subs and "预检还是认不出" in dict(waiting)["fresh"][0], (subs, waiting)


def test_auto_render全量那一趟带sync_subs_探针不带():
    body = _run("interview-auto-render.yml", "dispatch 未 render 的正式 spec（每 slug 一个 run，并行）")
    assert "pick_interview_renders.py --subs-list /tmp/subs.txt --sync-subs" in body
    gate = _run("interview-auto-render.yml", "没活就早退")
    assert "--sync-subs" not in gate, "探针不提交，不许改状态文件"
