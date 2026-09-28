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
   算起；interview-clip 的 render 预检带 `--require-subs`，subs 判定干净就叫醒 auto-render。
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
        "sha256": clip.transcript_fingerprint(spec, _LINES, out), "results": [row]}),
        encoding="utf-8")


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
                   "en_fixed": {"2": "great match!"}}
#: 经切行进指纹的（`main()` 切行读它们、行一变指纹就变）——
#: `test_转写输入的键和出片那一趟切行读的字段对得上` 钉
_BOUND_VIA_LINES = {"url", "segment_budget_px", "word_fix"}


def test_每个转写输入都绑在判定上_只改它旧判定不作数(tmp_path):
    """`SUBS_INPUT_KEYS` 里的一样改了，subs 的账清零；它要是不绑判定（不进指纹、不进区间、
    也不经切行），判定照旧 ok——render 跳过重量，拿旧配置量的数出片。`whisper_vad_filter`
    就是这么漏的（复审 2026-09-28：2 条 spec 写了它）。表自带自检：新加一样转写输入，
    要在这两份名单里说清它怎么绑。"""
    assert set(clip.SUBS_INPUT_KEYS) == set(_BOUND_DIRECTLY) | _BOUND_VIA_LINES, (
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
        "sha256": clip.transcript_fingerprint(spec, lines, out), "results": rows}),
        encoding="utf-8")


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
                                                  "window": clip.verdict_window(spec)}))
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
    assert f"[空档 VAD] 自动销账 {GAP}" in printed and "没人说话" in printed
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
    for slug in ("needs", "mixed", "clean"):
        spec = {"slug": slug, "opening": {"kind": "none"}, "zh": ["a"],
                "transcript_verified": True, "takeaway": {"close": {"point": "x"}},
                "cover": {"frame_at": 1}}
        (specs / f"{slug}.json").write_text(json.dumps(spec), encoding="utf-8")
        (specs / f"{slug}.xhs.txt").write_text("文案", encoding="utf-8")
    need = f"{interview_preflight.NEEDS_SUBS}当前转写指纹没有第二份 ASR 的分歧量数"
    verdicts = {"needs": [need], "mixed": [need, "字幕（write_ass）：中文超宽"], "clean": []}

    def fake(spec, **kw):
        """和真函数同一个口径开关：缺判定**只在** dispatch 口径（`require_subs=True`）下
        是红，本地默认口径下只是提示（`subtitle_findings` 的 `not_yet`）。原来这里无视
        `require_subs`、一律当红——`_preflight_problems` 把它退回 `spec_problems(spec)`
        （复审 M9）测试照样绿，而真预检下那条只缺判定的 spec 会被当成 ready 投 render，
        红在 interview-clip 的 `--require-subs`，每 70 分钟重投一趟、subs 永远不投。"""
        rows = verdicts[spec["slug"]]
        if kw.get("require_subs") is True:
            return list(rows), []
        need_it = interview_preflight.NEEDS_SUBS
        return ([r for r in rows if need_it not in r],
                [r.replace(need_it, "") for r in rows if need_it in r])
    monkeypatch.setattr(interview_preflight, "spec_problems", fake)
    return p


_NOW = datetime(2026, 9, 28, 4, 0, tzinfo=timezone.utc)


def test_只缺subs判定的先投subs_混着别的红进等待(pick):
    ready, waiting, subs = pick.todo_plan(now=_NOW)
    assert ready == ["clean"] and subs == ["needs"], (ready, subs)
    assert [s for s, _ in waiting] == ["mixed"], waiting
    # 老接口不变：todo_slugs 不把「先投 subs」的混进 render 名单
    assert pick.todo_slugs(now=_NOW)[0] == ["clean"]


def test_subs投过在窗口里不重投_超窗重投_满三趟停_只有转写输入改了才清零(pick):
    at = lambda m: (_NOW + timedelta(minutes=m)).strftime("%FT%TZ")  # noqa: E731
    pick.mark_subs("needs", now=at(0))
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=10))
    assert subs == [] and any("已投 subs" in w[1][0] for w in waiting if w[0] == "needs")
    _, _, subs = pick.todo_plan(now=_NOW + timedelta(minutes=pick.SUBS_STALE_MINUTES + 1))
    assert subs == ["needs"], "投出去超过窗口还没判定：再投一次"
    pick.mark_subs("needs", now=at(50))
    pick.mark_subs("needs", now=at(100))
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=200))
    assert subs == [] and any("预检还是认不出" in w[1][0] for w in waiting if w[0] == "needs"), waiting
    assert json.loads(pick.STATE.read_text())["subs"]["needs"]["tries"] == pick.SUBS_MAX_TRIES
    # 两种卡法都要点名：没交判定，和交了但绑的指纹跟预检重切出来的对不上
    why = next(w[1][0] for w in waiting if w[0] == "needs")
    assert "日志" in why and "second_asr_verdict.json" in why and "--require-subs" in why, why
    path = pick.SPECS / "needs.json"
    # 只改 zh（不动转写）：认领照旧——每次提交 spec 都经 on:push 叫醒 pick，按整份 spec
    # 认的话，还在跑的那趟 subs 会被同 slug 的重投掐掉（cancel-in-progress）
    path.write_text(path.read_text().replace('"a"', '"改过的中文"'), encoding="utf-8")
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=201))
    assert subs == [] and "needs" in dict(waiting), "只改了 zh 就清零重投"
    pick.mark_subs("needs", now=at(10))            # 窗口里：改 zh 也不重投
    _, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=20))
    assert subs == [] and "已投 subs" in dict(waiting)["needs"][0], waiting
    # 改转写输入（这里挪 end）：上一份的认领不算数，次数清零
    spec = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(dict(spec, end=42.0)), encoding="utf-8")
    _, _, subs = pick.todo_plan(now=_NOW + timedelta(minutes=21))
    assert subs == ["needs"], "转写输入改了：上一份的认领不算数"
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
    assert listing.read_text(encoding="utf-8") == "needs\n"
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
    assert subs == ["needs"] and "needs" not in ready, (ready, subs)
    pick.mark_subs("needs", now=_NOW.strftime("%FT%TZ"))
    ready, waiting, subs = pick.todo_plan(now=_NOW + timedelta(minutes=10))
    assert subs == [] and "needs" not in ready and "needs" in dict(waiting)


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
    assert "--require-subs" in pre["run"] and "mode == 'render'" in pre["if"]
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
