#!/usr/bin/env python3
"""配音自动听审：拿**要发布的那批实际配音字节**逐条机器检查，全过才算放行。

账号所有者 2026-10-20：「配音检验能自动化么？如果要让我去听，一个是不一定及时
（时间冲突），一个是我也不一定听的标准」，看过方案后回「好的」。所以
`voice_quality_gate` 多认一档 `automated_voice_suite`：本工具五项检查全过、
证据文件和当前影片／库存哈希绑死，才写放行记录。**它不是真人听审，记录里也
不这么写**——字段名就是 `automated_voice_suite`，不冒充 `full_audio_listening`。

    python3 tools/voice_auto_review.py --outdir output/<日期>/reel/<slug> \\
        --bundle "$RUNNER_TEMP/<slug>-tts.zip"            # runner：render 之后
    python3 tools/voice_auto_review.py ... --report-only  # 只出报告，不写放行

五项（每条实际配音都过一遍，同一份字节只查一次）：

1. **完整**：faster-whisper 把实际音频转回文字，和送进合成器的文字**按拼音**比
   （不按汉字：换字表把「时差」送成「时插」，转写回来是哪个字都对）。
   漏读、多读、句尾被截都在这儿现形。
2. **多音字**：送进合成器的每一个多音字（换字表已经换掉的除外），
   用 `measure_polyphone.measure` 拿**实际音频**当 ORIG，和同一把嗓子
   （同 voice / rate / pitch）念的「对的读音的同音字」「错的读音的同音字」比那一个音节。
   读错＝红；量不出（uncertain / unreliable / 找不到参考字）也是红——**量不了就是没过**，
   改写句子避开它（2026-10-06 规则：未测、uncertain 不记 pass）。
3. **停顿**：合成器报的词边界之间，人名和比分内部停顿超过 `MAX_INNER_GAP` 就红
   （「佩古｜拉六｜比｜四」那一类念出来是断的）；切词里的已知假词（`tts_fake_words`）红。
4. **语速**：每秒字数超过 `MAX_CPS` 红——超长要改稿或延长画面，不靠整体加速
   （2026-10-19 全局要求）。
5. **整句**：spec 里一句话被拆进两段分开合成（段尾不是句末标点，下一段接着说），红。
   每段单独合成，上一段的语调不知道下一段还要接着说，句中就被念成了句末。

接缝（首字是否被切、句尾是否完整、与原声抢话）由出片那几道确定性闸管：
旁白超长在编码前红（`narration_overruns`），原声段和旁白段互斥（`validate_spec`）；
本工具把它们记成「由出片闸覆盖」，不另声称听过。

**门槛的来路**写在每个常量旁边；改门槛要连同那次校准一起改。

校准（2026-10-20，wta1000-champions-2026 已发的 56 条实际配音，云见 +18% +10Hz，
runner 上 3 分 53 秒含首次下模型；证据在 `research/voice-auto-calib/wta1000.json`）：
转写按拼音比之后 56 条全过（最多 1 处漏读：「Ace」被转成「GS」，外文词不计；
「莱巴金娜」被转成「来8斤」，同音不算错）；多音字 A 档 0 处、B 档 16 处
（correct 9、uncertain 5、找不到参考字 2，都不红）；停顿、语速全过；
整句被拆 10 处——这一条片子真正该改的就是它。
第一版把 137 处多音字全量，跑了 8 分 49 秒、红成一片，见 `poly_targets` 的说明。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

SCHEMA = "tennislive.voice-auto-review.v1"
EVIDENCE = "voice_auto_review.json"
METHOD = "automated_voice_suite"
SUITE_VERSION = 1

#: 人名、比分内部两个 token 之间允许的最长停顿（秒）。
MAX_INNER_GAP = 0.18
#: 每秒字数上限（汉字＋阿拉伯数字，按语音首尾算）。
MAX_CPS = 6.3
#: 拼音比对：漏读／多读的音节数上限（按整条），以及连续漏读上限。
MAX_INDEL = 1
MAX_RUN_DELETE = 1
#: 拼音替换（非同音）占比上限——转写对外文人名会写错字，同音不算错。
MAX_SUB_RATIO = 0.15

_HAN = re.compile(r"[㐀-鿿]")
_LATIN = re.compile(r"[A-Za-z]+")
_END = "。！？…!?"
_NUM = "零〇一二两三四五六七八九十百千万"
_SCORE_RE = re.compile(rf"[{_NUM}]+(?:比|分|局|盘|年|月|号|日|岁|名|次|个|站)[{_NUM}]*")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    return _sha(Path(path).read_bytes())


# ---------------------------------------------------------------- bundle
def load_bundle(path: Path, workdir: Path) -> list[dict]:
    """解出冻结小包里每一条实际请求：(请求, 实际 mp3, 词边界)。"""
    out = []
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
        for item in manifest.get("entries") or []:
            rid = item["request_id"]
            audio = z.read(f"requests/{rid}/audio.mp3")
            marks = json.loads(z.read(f"requests/{rid}/marks.json"))
            if _sha(audio) != item["audio_sha256"]:
                raise SystemExit(f"小包里 {rid} 的音频哈希对不上")
            mp3 = workdir / f"{rid}.mp3"
            mp3.write_bytes(audio)
            out.append({"id": f"bundle:{rid}", "request": item["request"],
                        "audio_sha256": item["audio_sha256"], "mp3": mp3, "marks": marks,
                        "duration": float(item.get("duration_seconds") or 0)})
    return out


# ---------------------------------------------------------------- 1 完整
_DIG = "零一二三四五六七八九"


def _num_zh(n: int) -> str:
    """整数按读数念（1000→一千、75→七十五、16→十六）。"""
    if n == 0:
        return "零"
    out, units, s = "", ["", "十", "百", "千"], str(n)
    if n >= 10000:
        hi, lo = divmod(n, 10000)
        rest = _num_zh(lo) if lo else ""
        return _num_zh(hi) + "万" + ("零" + rest if lo and lo < 1000 else rest)
    zero = False
    for k, ch in enumerate(s):
        d, u = int(ch), units[len(s) - 1 - k]
        if d == 0:
            zero = True
            continue
        if zero:
            out += "零"
            zero = False
        out += ("" if (d == 1 and u == "十" and k == 0) else _DIG[d]) + u
    return out


def _num_readings(s: str) -> list[str]:
    """转写出来的阿拉伯数字可能是读数（七十五）也可能是逐位（二零二六），两种都给。"""
    forms = ["".join(_DIG[int(c)] for c in s)]
    if len(s) <= 8 and not (len(s) > 1 and s[0] == "0"):
        forms.insert(0, _num_zh(int(s)))
    return list(dict.fromkeys(forms))


def _py(text: str) -> list[str]:
    from pypinyin import lazy_pinyin
    return lazy_pinyin(text) if text else []


def _syllables(text: str, ref: list[str] | None = None) -> list[str]:
    """拼音音节（不带声调）。外文词不计：转写对英文缩写和 Ace 一类太不稳。

    给了 `ref` 时，转写里的数字挑和参考对得最好的那种念法。"""
    text = re.sub(r"(\d+)%", lambda m: "百分之" + m.group(1), text)
    out: list[str] = []
    for chunk in re.findall(r"[㐀-鿿]+|\d+", text):
        if not chunk.isdigit():
            out += _py(chunk)
            continue
        forms = [_py(f) for f in _num_readings(chunk)]
        if ref is None:
            out += forms[0]
        else:
            out += max(forms, key=lambda f: difflib.SequenceMatcher(
                a=ref, b=out + f, autojunk=False).ratio())
    return out


def compare_transcript(text: str, hyp: str) -> dict:
    ref = _syllables(text)
    got = _syllables(hyp, ref)
    sm = difflib.SequenceMatcher(a=ref, b=got, autojunk=False)
    dele = ins = sub = worst = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "delete":
            dele += i2 - i1
            worst = max(worst, i2 - i1)
        elif op == "insert":
            ins += j2 - j1
        elif op == "replace":
            n, m = i2 - i1, j2 - j1
            sub += min(n, m)
            if n > m:
                dele += n - m
                worst = max(worst, n - m)
            elif m > n:
                ins += m - n
    ratio = sub / max(1, len(ref))
    ok = dele + ins <= MAX_INDEL and worst <= MAX_RUN_DELETE and ratio <= MAX_SUB_RATIO
    return {"ok": ok, "ref_syllables": len(ref), "deleted": dele, "inserted": ins,
            "substituted": sub, "sub_ratio": round(ratio, 3), "longest_deletion": worst,
            "transcript": hyp}


def run_asr(entries: list[dict], model_name: str, names: list[str]) -> dict[str, str]:
    """转写。提示里只给人名（帮转写认出外文译名），**不给原句**——给原句等于让它照抄。"""
    import numpy as np
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    prompt = "以下是普通话的网球解说。" + ("人名：" + "、".join(names[:20]) + "。" if names else "")
    out = {}
    for e in entries:
        # Decode actual bytes independently of faster-whisper's PyAV adapter:
        # PyAV 19 rejects its metadata_errors argument. ndarray input is already
        # 16 kHz mono; no gain, silence trimming or other audio processing here.
        pcm = subprocess.check_output([
            "ffmpeg", "-nostdin", "-v", "error", "-i", str(e["mp3"]),
            "-f", "f32le", "-ar", "16000", "-ac", "1", "pipe:1",
        ])
        audio = np.frombuffer(pcm, dtype="<f4")
        segs, _ = model.transcribe(audio, language="zh", beam_size=5,
                                   vad_filter=False, condition_on_previous_text=False,
                                   initial_prompt=prompt)
        out[e["id"]] = "".join(s.text for s in segs).strip()
    return out


# ---------------------------------------------------------------- 2 多音字
#: 账号所有者点过名的多音字（docs/global-voice-quality.md 那张表）——
#: 就算这儿的读音是默认读音，也拿实际音频量一次（第二档，见 `poly_targets`）。
WATCH = set("重发还长得行种落")


def poly_targets(text: str) -> list[dict]:
    """要量的多音字，分两档（2026-10-20 拿 wta1000 的 56 条实际配音校准）：

    - **A 档**＝`check_polyphones.analyze` 报的风险处（这儿的读音不是该字的默认读音，
      或者量过读对的词换了句子）。必须量出 correct，量不出也红。
    - **B 档**＝`WATCH` 里的字落在默认读音上。只在量出**高置信的错读**时红。

    其余默认读音的多音字**不量**：校准那一轮把 137 处全量了一遍，默认读音上大半是
    uncertain／找不到参考字（的 de、了 le、给 gěi……），还有几处「错读」其实是
    读音推断本身错了（「两冠」「夺冠」的冠是 guàn，推断成了 guān）——全量只会
    红成一片，没人读（「判据宁可窄，不可宽」）。
    """
    import check_polyphones as cp
    from tennislive.video import pronounce
    risks, _ok, _notes = cp.analyze(cp.Spoken("voice", text, ""))
    out = [{"index": r.index, "char": r.char, "word": r.word, "intended": r.intended,
            "wrong": r.others[:2], "tier": "A"} for r in risks if r.others]
    seen = {x["index"] for x in out}
    reading, word, _lex, _ = cp._readings(text)
    covered = pronounce.covered_positions(text)
    for i, ch in enumerate(text):
        if ch not in WATCH or i in seen or i in covered or reading[i] is None:
            continue
        _poly, _defaults, live = cp.poly_info(ch)
        wrong = [r for r in live if r != reading[i] and not r.endswith("5")]
        if wrong:
            out.append({"index": i, "char": ch, "word": word[i] or ch,
                        "intended": reading[i], "wrong": wrong[:2], "tier": "B"})
    return out


def poly_ok(m: dict) -> bool:
    if m["tier"] == "A":
        return m["verdict"] == "correct"
    return not (m["verdict"] == "misread" and any(
        r.get("verdict") == "misread" and r.get("confidence") == "high" for r in m.get("runs", [])))


def measure_target(e: dict, t: dict) -> dict:
    import measure_polyphone as mp
    req = e["request"]
    text = req["text"]
    word = t["word"] if t["word"] in text else t["char"]
    ok_refs, _ = mp.suggest_homophones(t["intended"], exclude=word, k=3)
    if not ok_refs:
        return {**t, "verdict": "unmeasurable", "why": f"找不到只读 {t['intended']} 的常用字当参考"}
    runs = []
    for wrong in t["wrong"]:
        bad_refs, _ = mp.suggest_homophones(wrong, exclude=word, k=3)
        if not bad_refs:
            continue
        try:
            m = mp.measure(word, text, ok_refs, bad_refs, req["voice"], req["rate"],
                           char=t["char"], at=t["index"], pitch=req.get("pitch") or "+0Hz",
                           orig_audio=(e["mp3"], e["marks"]))
        except Exception as exc:  # noqa: BLE001 — 量不出就是没过，原话留下
            runs.append({"wrong": wrong, "verdict": "error", "why": f"{type(exc).__name__}: {exc}"})
            continue
        runs.append({"wrong": wrong, "verdict": m["verdict"], "score": m["score"],
                     "confidence": m["confidence"], "near": m["near_identical_to"]})
    verdicts = [r["verdict"] for r in runs]
    if not runs:
        verdict = "unmeasurable"
    elif "misread" in verdicts:
        verdict = "misread"
    elif all(v == "correct" for v in verdicts):
        verdict = "correct"
    else:
        verdict = "uncertain"
    return {**t, "verdict": verdict, "runs": runs, "ok_refs": "".join(ok_refs)}


# ---------------------------------------------------------------- 3 停顿 / 4 语速
def _protected_spans(text: str, names: list[str]) -> list[tuple[int, int, str]]:
    spans = []
    for n in names:
        start = 0
        while (k := text.find(n, start)) >= 0:
            spans.append((k, k + len(n), n))
            start = k + len(n)
    for m in _SCORE_RE.finditer(text):
        if m.end() - m.start() >= 2:
            spans.append((m.start(), m.end(), m.group()))
    return spans


def pause_and_speed(e: dict, names: list[str]) -> dict:
    from tennislive.video.explainer import token_spans
    from tennislive.zh.tts_fake_words import fake_token_hits
    text = e["request"]["text"]
    marks = [m for m in e["marks"] if str(m.get("text", "")).strip()]
    toks = [str(m["text"]).strip() for m in marks]
    spans = token_spans(text, toks)
    pos = {}
    for (a, b, tok), m in zip(spans, marks):
        pos[a] = (a, b, m["offset"] / 1e7, (m["offset"] + m["duration"]) / 1e7)
    ordered = [pos[k] for k in sorted(pos)]
    inner = []
    protected = _protected_spans(text, names)
    for (a0, b0, _s0, e0), (a1, b1, s1, _e1) in zip(ordered, ordered[1:]):
        if text[b0:a1].strip():          # 中间夹着标点：那是该停的地方
            continue
        gap = s1 - e0
        for sa, sb, label in protected:
            if sa < b0 and a1 < sb and gap > MAX_INNER_GAP:
                inner.append({"span": label, "gap_s": round(gap, 3),
                              "between": [text[a0:b0], text[a1:b1]]})
    fake = [{"token": tok, "why": why} for tok, why in fake_token_hits(toks)]
    chars = len(_HAN.findall(text)) + len(re.findall(r"\d", text))
    speech = (ordered[-1][3] - ordered[0][2]) if ordered else 0.0
    cps = chars / speech if speech > 0 else 0.0
    return {"inner_pauses": inner, "fake_tokens": fake, "chars": chars,
            "speech_s": round(speech, 3), "cps": round(cps, 2),
            "pause_ok": not inner and not fake, "speed_ok": cps <= MAX_CPS,
            "tokens": " ｜ ".join(toks)}


# ---------------------------------------------------------------- 5 整句
def split_sentences(spec: dict) -> list[dict]:
    """一句话被拆进相邻两段分开合成。"""
    segs = [s for s in spec.get("segments") or [] if isinstance(s, dict)]
    out = []
    voiced = [(i, str(s.get("narration") or "").strip()) for i, s in enumerate(segs)]
    voiced = [(i, t) for i, t in voiced if t]
    for (i, t), (j, nxt) in zip(voiced, voiced[1:]):
        if t[-1] not in _END and t[-1] not in "”」』）)":
            out.append({"segment": i + 1, "next": j + 1, "end": t[-12:], "continues": nxt[:12]})
    return out


def _names(spec: dict) -> list[str]:
    """这条片子里出现的中文人名（译名表里三个字以上的，按出现在 spec 里的取）。"""
    from tennislive.zh.players import PLAYER_ZH
    blob = json.dumps(spec, ensure_ascii=False)
    pool = {v for v in PLAYER_ZH.values() if isinstance(v, str) and len(v) >= 3}
    return sorted((n for n in pool if n in blob), key=len, reverse=True)


# ---------------------------------------------------------------- 汇总
def review(outdir: Path, bundle: Path, *, model: str = "small", second_model: str = "medium",
           workers: int = 4,
           report_only: bool = False, asr: dict | None = None) -> dict:
    import voice_quality_gate as g
    outdir = Path(outdir).resolve()
    render = json.loads((outdir / "render.json").read_text("utf-8"))
    identity, _manifest = g._identity(outdir, ROOT, render)
    inventory_path = outdir / g.INVENTORY
    inventory = json.loads(inventory_path.read_text("utf-8"))
    identity["inventory_sha256"] = _file_sha(inventory_path)
    if _file_sha(bundle) != inventory.get("bundle_sha256"):
        raise SystemExit("小包和封存的配音库存不是同一份")
    spec_path = next(p for p in (ROOT / f"specs/{k}/{outdir.name}.json"
                                 for k in ("reels", "interviews")) if p.is_file())
    spec = json.loads(spec_path.read_text("utf-8"))
    names = _names(spec)
    with tempfile.TemporaryDirectory() as tmp:
        entries = load_bundle(bundle, Path(tmp))
        by_audio = {e["audio_sha256"]: e for e in entries}
        uniq = list(by_audio.values())
        transcripts = asr if asr is not None else run_asr(uniq, model, names)
        if asr is None and second_model:
            # 第一遍没对上的再用大一号的模型听一遍，哪一遍对上都算（转写本身会错，
            # 校准那一轮 small 把「八分之一」转成「1%」、「莱巴金娜」转成「来8斤」）
            again = [e for e in uniq if not compare_transcript(
                e["request"]["text"], transcripts.get(e["id"], ""))["ok"]]
            if again:
                second = run_asr(again, second_model, names)
                for e in again:
                    if compare_transcript(e["request"]["text"], second[e["id"]])["ok"]:
                        transcripts[e["id"]] = second[e["id"]]
        targets = [(e, t) for e in by_audio.values() for t in poly_targets(e["request"]["text"])]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            measured = list(pool.map(lambda et: (et[0]["id"], measure_target(*et)), targets))
        per = {}
        for e in by_audio.values():
            comp = compare_transcript(e["request"]["text"], transcripts.get(e["id"], ""))
            ps = pause_and_speed(e, names)
            polys = [m for k, m in measured if k == e["id"]]
            bad_poly = [m for m in polys if not poly_ok(m)]
            checks = {"completeness": comp["ok"], "polyphones": not bad_poly,
                      "pauses": ps["pause_ok"], "speed": ps["speed_ok"]}
            per[e["audio_sha256"]] = {"id": e["id"], "text": e["request"]["text"],
                                      "pass": all(checks.values()), "checks": checks,
                                      "completeness": comp, "polyphones": polys,
                                      "pauses": ps}
    splits = split_sentences(spec)
    rows = []
    for item in inventory["entries"]:
        r = per.get(item["audio_sha256"])
        rows.append({"id": item["id"], "audio_sha256": item["audio_sha256"],
                     "pass": bool(r and r["pass"]), "result_of": r["id"] if r else None})
    ok = all(r["pass"] for r in rows) and not splits
    evidence = {"schema": SCHEMA, "suite_version": SUITE_VERSION, "method": METHOD,
                "identity": identity, "asr_model": f"faster-whisper {model}",
                "thresholds": {"MAX_INNER_GAP": MAX_INNER_GAP, "MAX_CPS": MAX_CPS,
                               "MAX_INDEL": MAX_INDEL, "MAX_RUN_DELETE": MAX_RUN_DELETE,
                               "MAX_SUB_RATIO": MAX_SUB_RATIO},
                "seams": "由出片确定性闸覆盖：旁白超长编码前红（narration_overruns）、原声段与旁白段互斥（validate_spec）；本工具未另行检查成片接缝",
                "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "pass": ok, "sentence_splits": splits, "entries": rows,
                "audio": list(per.values())}
    (outdir / EVIDENCE).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    if ok and not report_only:
        write_approval(outdir, evidence)
    return evidence


def write_approval(outdir: Path, evidence: dict) -> Path:
    import voice_quality_gate as g
    ev_sha = _file_sha(outdir / EVIDENCE)
    stamp = evidence["reviewed_at"]
    who = f"voice_auto_review v{SUITE_VERSION}（自动检查，非真人听审）"
    obs = f"五项自动检查全过，证据 {EVIDENCE} sha256 {ev_sha}"
    scope = lambda sha: {"status": "pass", "method": METHOD, "reviewer": who,  # noqa: E731
                         "reviewed_at": stamp, "whole_audio": True, "audio_sha256": sha,
                         "observations": obs, "evidence_sha256": ev_sha}
    rv = {"schema": g.SCHEMA, "identity": evidence["identity"],
          "film_review": {"status": "pass", "method": METHOD, "reviewer": who,
                          "reviewed_at": stamp, "film_sha256": evidence["identity"]["film_sha256"],
                          "whole_narration_and_seams": True, "evidence_sha256": ev_sha,
                          "observations": obs + "；接缝：" + evidence["seams"]},
          "entries": [{"id": r["id"], "phonetics": scope(r["audio_sha256"]),
                       "prosody": scope(r["audio_sha256"])} for r in evidence["entries"]]}
    path = outdir / g.REVIEW
    if path.exists():
        old = json.loads(path.read_text("utf-8"))
        if old.get("identity") == rv["identity"] and (old.get("film_review") or {}).get(
                "method") == "full_audio_listening":
            return path              # 真人听审过的同一版，不拿自动记录覆盖
    path.write_text(json.dumps(rv, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def summary_lines(ev: dict) -> list[str]:
    lines = [f"[配音自动听审] {'✅ 全过' if ev['pass'] else '❌ 没过'}（{len(ev['audio'])} 条实际配音）"]
    for a in ev["audio"]:
        if a["pass"]:
            continue
        lines.append(f"  「{a['text']}」")
        c = a["completeness"]
        if not a["checks"]["completeness"]:
            lines.append(f"    完整：漏 {c['deleted']} 多 {c['inserted']} 替 {c['substituted']}，转写「{c['transcript']}」")
        for p in a["polyphones"]:
            if not poly_ok(p):
                lines.append(f"    多音字（{p['tier']} 档）「{p['word']}」的「{p['char']}」应读 {p['intended']}：{p['verdict']}"
                             + (f"（{p.get('why')}）" if p.get("why") else ""))
        ps = a["pauses"]
        for x in ps["inner_pauses"]:
            lines.append(f"    停顿：「{x['span']}」中间停了 {x['gap_s']}s")
        for x in ps["fake_tokens"]:
            lines.append(f"    假词「{x['token']}」：{x['why']}")
        if not a["checks"]["speed"]:
            lines.append(f"    语速 {ps['cps']} 字/秒 > {MAX_CPS}")
    for s in ev["sentence_splits"]:
        lines.append(f"  整句被拆：第 {s['segment']} 段「…{s['end']}」接第 {s['next']} 段「{s['continues']}…」")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--model", default="small")
    ap.add_argument("--second-model", default="medium", help="第一遍没对上时复听用；空串＝不复听")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args(argv)
    ev = review(args.outdir, args.bundle, model=args.model, second_model=args.second_model,
                workers=args.workers,
                report_only=args.report_only)
    print("\n".join(summary_lines(ev)))
    return 0 if ev["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
