#!/usr/bin/env python3
"""多音字声学比对：合成器在这句话里，把这个字读成了哪个读音？

账号所有者 2026-09-27：「配音 tts 里的多音字最好在生成语音时候替换成同音的字」。
换字表在 `src/tennislive/video/pronounce.py`；**这个工具是进表的门槛**——
「原句量出来读错、换字之后量出来读对」才进。沙箱合得了 edge-tts
（`tennislive.localca`），没有 ASR、不靠耳朵，全靠同一把嗓子的对照。

    python3 tools/measure_polyphone.py --word 柏林 \\
        --sentence "两年前柏林揭幕战，塞伦多洛两盘赢了鲁德。" \\
        --intended bo2 --wrong bai3 --rate +6% --brief
    # --orig-char 伯   量「换成伯之后」读成什么（换字候选就这么验）

依赖：`pip install -e ".[polyphone]"`（librosa、praat-parselmouth、numpy、edge-tts、
pypinyin）＋ ffmpeg。`tools/check_polyphones.py --measure` 调的就是这里的 `measure()`。

## 校准（2026-09-27，云见 +6% 和 +22% 各一遍，`calibrate.py` 那 23 句）

    句子                                  +6%              +22%          依据
    柏林1「两年前柏林揭幕战」             misread −0.33    misread −0.33  账号所有者 09-25 听出 bǎi
    柏林1 换成「伯」                      correct 1.00     correct 1.00   dA 0.0（与「博」同一段音频）
    硬地2「这是她第一个硬地决赛」          misread −0.31    unreliable     账号所有者 08-02 听出 de
    硬地。（单说）                        misread −1.00    misread −1.00  与「的」逐采样相同 dB 0.0
    硬地2 换成「帝」                      correct 1.00     correct 1.00
    冠军 / 长度 / 主角 / 教练 / 调头       correct（对照组，high/medium）
    一场(比) / 种子                       unreliable / uncertain（3-3 变调、换字改了邻字轻声——量不了就说量不了）

留一自测（每个参考字拿其余参考字去判）237 次：对 214、弃权 19、**判反 4**；
最终判决（ORIG）在校准集上**一次都没判反**——分不开的时候它说 uncertain /
unreliable，不猜。之后三批普查（127 处，`pronounce.py` 各条 evidence 就是它们）
同样只在「原句读错、换字读对」都量出来之后才进表。

⚠️ **量的是 edge-tts（生产 09-04 起就是它：Azure 试用到期），不是 Azure**。
⚠️ 参考字要「只有那一个读音」的常用字（`suggest_homophones` 按 GB2312 一级字 ＋
pypinyin 单读音挑）；没有这种字的读音（轻声 de、zhe、děi）只能拿近似字当代理，
结论降一档看。

---

Acoustic polyphone check for the production edge-tts voice.

Question: in sentence S (exactly as sent to TTS, i.e. speakable() output),
does the voice read polyphone C inside word W with the INTENDED reading?

Method (no ASR, no ears; everything synthesised with the SAME voice/rate):
  ORIG     = S as written
  A-refs   = S with C replaced by 2-3 unambiguous homophones of the INTENDED
             reading (--ok-char 博勃驳)
  B-refs   = S with C replaced by 2-3 unambiguous homophones of the WRONG
             reading (--bad-char 摆佰百)
The rest of the sentence is identical text, so a full-utterance DTW (MFCC
c1-c12 + deltas, 10 ms hop) pins the alignment, and distances are read only
over the target syllable window (from edge-tts WordBoundary; the tightest
token among the variants is carried into the others through the DTW path):
  spec = mean euclidean distance of standardised MFCC+delta along the path
  f0   = mean |dF0| in semitones (Praat AC pitch; each utterance centred on
         its own median), 10% trimmed
  comb = spec/2.0 + f0/1.0   (2.0 / 1.0 = typical same-reading spread)
Score = (dB - dA)/(dB + dA) with dA/dB = nearest A/B reference by `comb`.
  score >= +0.2 -> correct, <= -0.2 -> misread, else uncertain.
Leave-one-out self-test: each reference is classified against the others by
the same rule. If a reference lands on the wrong side or inside the margin,
this sentence/reference set cannot separate the two readings (tone-3 sandhi,
a rare char the voice reads differently...) -> verdict "unreliable". One
outlier per side is dropped automatically if the side keeps >=1 reference and
at least two self-test probes remain.
"near_identical_to": ORIG is within clip(0.5 x same-reading spread, 0.15,
0.4) comb units of a reference -> the synthesiser produced effectively the
same audio (same phoneme input); that is the strongest evidence either way,
and it overrides "unreliable" when that side's own self-test passed.
"far_from_both": ORIG is further than half the A-B distance from BOTH sides
-> a third reading, or the substitution changed a neighbour's reading
(种子 -> 肿子: 子 loses its neutral tone); confidence is capped at "low".
confidence: high = decided + identical audio + self-test passed on both
sides; medium = |score| >= 0.3 with a clean two-sided self-test, or identical
audio with a one-sided self-test; low = everything else that is decided.
A single char per side is auto-augmented with 2 same-reading homophones
(GB2312 level-1, single-reading per pypinyin) unless --no-augment.

Needs: edge-tts (+ tennislive.localca in the sandbox), ffmpeg, numpy, librosa,
praat-parselmouth, pypinyin.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO_SRC = str(Path(__file__).resolve().parents[1] / "src")
# 合成结果按 (文本, 音色, 语速, 音调) 缓存；**不落进仓库**（output/ 是跟踪的）。
CACHE = Path(os.environ.get(
    "POLYPHONE_CACHE", str(Path.home() / ".cache" / "tennislive" / "polyphone")))
SR = 16000
HOP = 160           # 10 ms
WIN = 400           # 25 ms
PAD_S = 0.04        # pad the estimated syllable window by 40 ms each side

_ca_done = False


def _trust_ca() -> None:
    global _ca_done
    if _ca_done:
        return
    if REPO_SRC not in sys.path:
        sys.path.insert(0, REPO_SRC)
    try:
        import contextlib
        import io
        from tennislive.localca import trust_local_proxy_ca
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            trust_local_proxy_ca()
    except Exception:  # noqa: BLE001  (runner: no proxy CA, nothing to do)
        pass
    _ca_done = True


# ---------------------------------------------------------------- synthesis
def synth(text: str, voice: str, rate: str, pitch: str = "+0Hz") -> tuple[Path, list[dict]]:
    """edge-tts, cached on (text, voice, rate, pitch). Returns (mp3, marks)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256("\x1f".join([text, voice, rate, pitch]).encode()).hexdigest()[:24]
    mp3, js = CACHE / f"{key}.mp3", CACHE / f"{key}.json"
    if mp3.is_file() and js.is_file() and mp3.stat().st_size > 0:
        return mp3, json.loads(js.read_text(encoding="utf-8"))
    _trust_ca()
    import edge_tts

    async def one() -> list[dict]:
        marks: list[dict] = []
        with mp3.open("wb") as fh:
            async for c in edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                                boundary="WordBoundary").stream():
                if c.get("type") == "audio" and c.get("data"):
                    fh.write(c["data"])
                elif c.get("type") == "WordBoundary":
                    marks.append({"offset": c["offset"], "duration": c["duration"],
                                  "text": c["text"]})
        return marks

    last = None
    final_mp3 = mp3
    mp3 = mp3.with_name(f"{key}.{os.getpid()}.part.mp3")   # parallel callers
    for attempt in range(4):
        try:
            marks = asyncio.run(one())
            if mp3.stat().st_size > 0:
                tmpj = js.with_name(f"{key}.{os.getpid()}.part.json")
                tmpj.write_text(json.dumps(marks, ensure_ascii=False), encoding="utf-8")
                os.replace(mp3, final_mp3)
                os.replace(tmpj, js)
                return final_mp3, marks
        except Exception as e:  # noqa: BLE001
            last = e
        import time
        time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"edge-tts failed for {text!r}: {last}")


def load_wav(mp3: Path) -> np.ndarray:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


# ---------------------------------------------------------------- features
def features(y: np.ndarray) -> dict:
    import librosa
    mf = librosa.feature.mfcc(y=y, sr=SR, n_mfcc=13, n_fft=512, hop_length=HOP,
                              win_length=WIN, n_mels=40, fmin=50, fmax=7600)
    mf = mf[1:]                                   # drop c0 (loudness)
    d = librosa.feature.delta(mf, width=5)
    spec = np.vstack([mf, d]).T                   # (frames, 24)
    import parselmouth
    snd = parselmouth.Sound(y.astype(np.float64), sampling_frequency=SR)
    # Praat autocorrelation pitch: pYIN rejects ~90% of frames of this low,
    # creaky male voice (measured: 6.8% voiced); Praat with a 0.25 voicing
    # threshold tracks it cleanly (教 148->101 Hz falling vs 交 ~140 Hz level).
    pit = snd.to_pitch_ac(time_step=HOP / SR, pitch_floor=50, pitch_ceiling=350,
                          voicing_threshold=0.25, silence_threshold=0.01,
                          octave_jump_cost=0.5)
    ts = pit.xs()
    hz = pit.selected_array["frequency"]
    frame_t = np.arange(spec.shape[0]) * HOP / SR
    f0 = np.interp(frame_t, ts, hz, left=0.0, right=0.0)
    # interp across a voiced/unvoiced edge would invent pitch; mark those
    near = np.interp(frame_t, ts, (hz > 0).astype(float), left=0.0, right=0.0)
    f0[near < 0.999] = np.nan
    rms = librosa.feature.rms(y=y, frame_length=WIN, hop_length=HOP, center=True)[0]
    n = min(len(spec), len(f0), len(rms))
    f0 = f0[:n]
    st = 12 * np.log2(f0 / 100.0)                 # semitones re 100 Hz (NaN if unvoiced)
    return {"spec": spec[:n], "st": st, "rms": rms[:n]}


def char_window(sentence: str, marks: list[dict], idx: int, nchar: int = 1) -> tuple[float, float, str]:
    """Seconds window of chars [idx, idx+nchar) from WordBoundary tokens.

    Tokens are found sequentially in the text (punctuation has no event).
    Inside a multi-char token the syllables are assumed equally long.
    """
    cursor = 0
    for m in marks:
        tok = m["text"]
        at = sentence.find(tok, cursor)
        if at < 0:
            continue
        cursor = at + len(tok)
        if at <= idx < at + len(tok):
            t0 = m["offset"] / 1e7
            dur = m["duration"] / 1e7
            per = dur / len(tok)
            k = idx - at
            s = t0 + per * k
            e = t0 + per * min(k + nchar, len(tok))
            return s, e, tok
    raise ValueError(f"char {idx} ({sentence[idx:idx+nchar]!r}) not covered by any WordBoundary: "
                     f"{[m['text'] for m in marks]}")


def _dtw_path(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    import librosa
    _, wp = librosa.sequence.dtw(X=A.T, Y=B.T, metric="euclidean",
                                 step_sizes_sigma=np.array([[1, 1], [0, 1], [1, 0]]),
                                 weights_add=np.array([0, 0, 0]),
                                 weights_mul=np.array([1, 1, 1]))
    return wp[::-1]


def compare(fo: dict, fx: dict, win: tuple[float, float]) -> dict:
    """Distances between utterance O and X over O's frames inside `win`.

    Full-utterance DTW (the rest of the sentence is the same text, so it pins
    the alignment), then the local costs are read only inside the window.
    `spec` must already be standardised (see `measure`).
    """
    A, B = fo["z"], fx["z"]
    wp = _dtw_path(A, B)
    i0, i1 = int(win[0] * SR / HOP), int(np.ceil(win[1] * SR / HOP))
    sel = wp[(wp[:, 0] >= i0) & (wp[:, 0] < i1)]
    if len(sel) == 0:
        return {"spec": float("nan"), "f0": float("nan"), "vmis": float("nan"), "frames": 0}
    spec_cost = float(np.mean(np.linalg.norm(A[sel[:, 0]] - B[sel[:, 1]], axis=1)))
    # F0 in semitones, each utterance centred on its own median so a global
    # pitch drift between syntheses is not read as a tone difference.
    so = fo["st"] - np.nanmedian(fo["st"])
    sx = fx["st"] - np.nanmedian(fx["st"])
    po, px = so[sel[:, 0]], sx[sel[:, 1]]
    both = ~np.isnan(po) & ~np.isnan(px)
    one = np.isnan(po) ^ np.isnan(px)
    if both.sum() >= 4:
        diffs = np.abs(po[both] - px[both])
        # trimmed mean: a single octave jump must not decide a tone
        diffs = np.sort(diffs)[: max(1, int(np.ceil(len(diffs) * 0.9)))]
        f0_cost = float(np.mean(diffs))
    else:
        f0_cost = float("nan")
    return {"spec": spec_cost, "f0": f0_cost, "vmis": float(one.mean()),
            "frames": int(len(sel))}


def f0_track(f: dict, win: tuple[float, float]) -> list:
    i0, i1 = int(win[0] * SR / HOP), int(np.ceil(win[1] * SR / HOP))
    st = f["st"] - np.nanmedian(f["st"])
    seg = st[i0:i1]
    return [None if np.isnan(v) else round(float(v), 1) for v in seg[::2]]


# ---------------------------------------------------------------- verdict
#: Global scale of each feature = median distance between two DIFFERENT
#: homophones of the SAME reading at the target syllable (calibration set,
#: +6% and +22%). Used only when a case has one reference per side.
SCALE = {"spec": 2.0, "f0": 1.0}
F0_WEIGHT = 1.0


def combined(d: dict) -> float:
    s = d["spec"] / SCALE["spec"]
    f = d["f0"] / SCALE["f0"] if np.isfinite(d["f0"]) else None
    return float(s + F0_WEIGHT * f) if f is not None else float(s)


def _nn(dist: dict, key: str, A: list[str], B: list[str], feat: str) -> tuple[float, float]:
    da = min((dist[(key, a)][feat] for a in A if a != key), default=float("nan"))
    db = min((dist[(key, b)][feat] for b in B if b != key), default=float("nan"))
    return da, db


def _score(da: float, db: float) -> float:
    """+1 ORIG sits on an intended-reading reference, -1 on a wrong one."""
    if not (np.isfinite(da) and np.isfinite(db)) or da + db <= 0:
        return float("nan")
    return (db - da) / (db + da)


def suggest_homophones(reading: str, exclude: str = "", k: int = 3) -> tuple[list[str], str]:
    """Common chars with exactly one reading `reading` (TONE3, e.g. bo2, de5).

    Tier 1: GB2312 level-1 (the 3755 common chars) with a single reading.
    Tier 2: GB2312 level-2 with a single reading.
    Tier 3: level-1 whose FIRST (dominant) reading is `reading` -- weaker.
    """
    from pypinyin import Style, pinyin
    from pypinyin.pinyin_dict import pinyin_dict

    def level(c: str) -> int:
        try:
            b = c.encode("gb2312")
        except UnicodeEncodeError:
            return 0
        if len(b) != 2:
            return 0
        return 1 if 0xB0 <= b[0] <= 0xD7 else 2 if 0xD8 <= b[0] <= 0xF7 else 0

    tiers: dict[int, list[str]] = {1: [], 2: [], 3: []}
    for cp in pinyin_dict:
        c = chr(cp)
        lv = level(c)
        if not lv or c in exclude:
            continue
        rs = pinyin(c, style=Style.TONE3, heteronym=True, neutral_tone_with_five=True)[0]
        if rs == [reading]:
            tiers[lv].append(c)
        elif lv == 1 and rs and rs[0] == reading:
            tiers[3].append(c)
    out, used = [], []
    for t in (1, 2, 3):
        for c in tiers[t]:
            if len(out) < k:
                out.append(c)
                used.append(t)
    note = {1: "single-reading common", 2: "single-reading level-2", 3: "dominant-reading only"}
    return out, ", ".join(sorted({note[t] for t in used})) or "none found"


def missing_deps() -> list[str]:
    """量之前先问一句缺什么——缺了要**出声**，别让「没量」长得像「量过没问题」。"""
    import importlib.util
    import shutil
    miss = [m for m in ("numpy", "librosa", "parselmouth", "edge_tts", "pypinyin")
            if importlib.util.find_spec(m) is None]
    if not shutil.which("ffmpeg"):
        miss.append("ffmpeg")
    return miss


def measure(word: str, sentence: str, ok: list[str], bad: list[str], voice: str,
            rate: str, char: str | None = None, margin: float = 0.2,
            orig_override: str | None = None, at: int | None = None) -> dict:
    """`at`：多音字在 `sentence` 里的字位。同一个词在句子里出现两次时必须给，
    否则按第一次出现的位置量（原来就是这样）。"""
    if word not in sentence:
        raise ValueError(f"word {word!r} not in sentence")
    if char is None:
        # the polyphone is the char of `word` that can be read like BOTH an
        # intended and a wrong reference (地: di4/de5 <- 帝 di4, 的 de5)
        from pypinyin import Style, pinyin

        def rd(c: str) -> set:
            return set(pinyin(c, style=Style.TONE3, heteronym=True,
                              neutral_tone_with_five=True)[0])
        ra = set().union(*(rd(c) for c in ok if len(c) == 1)) if ok else set()
        rb = set().union(*(rd(c) for c in bad if len(c) == 1)) if bad else set()
        cand = [c for c in word if rd(c) & ra and rd(c) & rb]
        if len(cand) != 1:
            cand = [c for c in word if len(rd(c)) > 1] if not cand else cand
        if len(cand) != 1:
            raise ValueError(f"cannot tell which char of {word!r} is the polyphone "
                             f"(candidates {cand}); pass --char")
        char = cand[0]
    if at is not None:
        if sentence[at:at + len(char)] != char:
            raise ValueError(f"sentence[{at}] is {sentence[at:at + len(char)]!r}, not {char!r}")
        idx = at
    else:
        idx = sentence.index(word) + word.index(char)
    n = len(char)
    for r in ok + bad:
        if len(r) != n:
            raise ValueError(f"reference {r!r} must have len {n} like {char!r} (1:1 rule)")

    def sub(rep: str) -> str:
        return sentence[:idx] + rep + sentence[idx + n:]

    texts = {"ORIG": sentence if orig_override is None else sub(orig_override)}
    A = [f"A:{c}" for c in ok]
    B = [f"B:{c}" for c in bad]
    for c in ok:
        texts[f"A:{c}"] = sub(c)
    for c in bad:
        texts[f"B:{c}"] = sub(c)
    audio, marks, feats, own = {}, {}, {}, {}
    for k, t in texts.items():
        audio[k], marks[k] = synth(t, voice, rate)
        feats[k] = features(load_wav(audio[k]))
        own[k] = char_window(t, marks[k], idx, n)          # (s, e, token)
    # one standardisation for every variant, from speech frames only
    allspec = np.vstack([f["spec"][f["rms"] > 0.1 * np.max(f["rms"])] for f in feats.values()])
    mu, sd = allspec.mean(0), allspec.std(0) + 1e-6
    for f in feats.values():
        f["z"] = (f["spec"] - mu) / sd
    # Syllable window. WordBoundary tokens differ between variants (ORIG
    # 「前柏林」 vs 「前」「博林」), and inside a merged token the even split
    # can land on the neighbour. So take the window from the variant whose
    # token around the target is SHORTEST (the tightest estimate) and carry
    # it into every other variant through the full-utterance DTW path.
    anchor = min(texts, key=lambda k: (len(own[k][2]), k != "ORIG"))
    a0, a1 = own[anchor][0], own[anchor][1]
    wins = {}
    for k in texts:
        if k == anchor or len(own[k][2]) == len(own[anchor][2]):
            s, e = own[k][0], own[k][1]
        else:
            wp = _dtw_path(feats[anchor]["z"], feats[k]["z"])
            i0, i1 = int(a0 * SR / HOP), int(np.ceil(a1 * SR / HOP))
            m = wp[(wp[:, 0] >= i0) & (wp[:, 0] < i1), 1]
            s, e = m.min() * HOP / SR, (m.max() + 1) * HOP / SR
        wins[k] = (max(0.0, s - PAD_S), e + PAD_S, own[k][2])

    keys = list(texts)
    # Neighbour check: the substitution must not change how the NEIGHBOURS are
    # read (种子 has a neutral-tone 子; 肿子/众子 are not words, so their 子 gets
    # a full tone and the references stop being "the same sentence").
    def _is_cjk(ch: str) -> bool:
        return "\u4e00" <= ch <= "\u9fff"
    nb_wins = []
    for j in (idx - 1, idx + n):
        if 0 <= j < len(texts["ORIG"]) and _is_cjk(texts["ORIG"][j]):
            try:
                s_, e_, _ = char_window(texts["ORIG"], marks["ORIG"], j, 1)
                nb_wins.append((s_, e_))
            except ValueError:
                pass
    neighbour = {}
    for k in keys:
        if k == "ORIG" or not nb_wins:
            continue
        neighbour[k] = max(combined(compare(feats["ORIG"], feats[k], w)) for w in nb_wins)
    dist = {}
    for a in keys:
        for b in keys:
            if a != b:
                d = compare(feats[a], feats[b], wins[a][:2])
                d["comb"] = combined(d)
                dist[(a, b)] = d

    # within-reading spread and between-reading contrast, per feature
    def spread(feat: str) -> dict:
        wa = [dist[(x, y)][feat] for x in A for y in A if x != y]
        wb = [dist[(x, y)][feat] for x in B for y in B if x != y]
        bt = [dist[(x, y)][feat] for x in A + B for y in (B if x in A else A)]
        within = float(np.nanmean(wa + wb)) if (wa or wb) else float("nan")
        between = float(np.nanmean(bt))
        return {"within": within, "between": between,
                "separation": between / within if within and np.isfinite(within) else None}

    sep = {f: spread(f) for f in ("spec", "f0", "comb")}

    # leave-one-out self-test: every reference, classified against the others
    def run_loo(A: list[str], B: list[str]) -> dict:
        loo = {}
        for k in A + B:
            if not [a for a in A if a != k] or not [b for b in B if b != k]:
                continue
            da, db = _nn(dist, k, A, B, "comb")
            s = _score(da, db)
            want = "correct" if k in A else "misread"
            got = "correct" if s >= margin else "misread" if s <= -margin else "uncertain"
            loo[k] = {"expect": want, "got": got, "score": round(s, 3)}
        return loo

    loo = run_loo(A, B)
    dropped: list[str] = []
    bad_refs = [k for k, v in loo.items() if v["got"] != v["expect"]]
    if bad_refs:
        # one outlier per side (a rare char the voice reads its own way) may go,
        # if its side keeps >=1 reference and the rest still self-test cleanly
        fa = [k for k in bad_refs if k in A]
        fb = [k for k in bad_refs if k in B]
        if len(fa) <= 1 and len(fb) <= 1 and len(A) - len(fa) >= 1 and len(B) - len(fb) >= 1:
            A2 = [a for a in A if a not in fa]
            B2 = [b for b in B if b not in fb]
            loo2 = run_loo(A2, B2)
            if len(loo2) >= 2 and all(v["got"] == v["expect"] for v in loo2.values()):
                dropped = fa + fb
                A, B, loo = A2, B2, {**loo2, **{k: {**loo[k], "dropped": True} for k in dropped}}
    active = {k: v for k, v in loo.items() if not v.get("dropped")}
    # None = no self-test possible (a single reference per side)
    loo_pass = (all(v["got"] == v["expect"] for v in active.values()) if active else None)
    loo_sides = {("A" if k.startswith("A:") else "B") for k in active}

    per_feat = {}
    for feat in ("spec", "f0", "comb"):
        da, db = _nn(dist, "ORIG", A, B, feat)
        per_feat[feat] = {"d_intended": round(da, 3) if np.isfinite(da) else None,
                          "d_wrong": round(db, 3) if np.isfinite(db) else None,
                          "score": round(_score(da, db), 3) if np.isfinite(_score(da, db)) else None}
    score = per_feat["comb"]["score"]
    if score is None:
        verdict = "uncertain"
    elif score >= margin:
        verdict = "correct"
    elif score <= -margin:
        verdict = "misread"
    else:
        verdict = "uncertain"
    raw = verdict
    if loo_pass is False:
        verdict = "unreliable"
    # (identical-audio override is applied below, once `ident` is known)
    # "identical" = ORIG is closer to a reference than the references of one
    # reading are to each other: the synthesiser produced (almost) the same audio.
    wi = sep["comb"]["within"]
    ident = None
    # threshold: half the same-reading spread, clipped to [0.15, 0.4] comb units
    # (0.15 > resynthesis noise of identical text ~0.05; 0.4 < the closest
    # distinct-homophone pair seen in calibration, 航/ORIG 0.7)
    if np.isfinite(wi) and per_feat["comb"]["d_intended"] is not None:
        thr = float(np.clip(0.5 * wi, 0.15, 0.4))
        if per_feat["comb"]["d_intended"] < thr:
            ident = "intended"
        elif per_feat["comb"]["d_wrong"] is not None and per_feat["comb"]["d_wrong"] < thr:
            ident = "wrong"
    # Identical audio beats an inconsistent OTHER side: if ORIG reproduces a
    # reference of side S sample-for-sample and every self-test probe of side S
    # passed (so S's references agree with each other), ORIG has S's reading
    # even when the other side's references are unusable (no clean tiǎo char,
    # light-tone de has no single-reading char, ...).
    override = None
    if verdict == "unreliable" and ident is not None:
        side = "A" if ident == "intended" else "B"
        probes = [v for k, v in loo.items() if k.startswith(side + ":") and not v.get("dropped")]
        if len(probes) >= 2 and all(v["got"] == v["expect"] for v in probes):
            verdict = "correct" if side == "A" else "misread"
            override = f"ORIG identical to a {side}-reference; {side}-side self-test passed, other side did not"
    if verdict in ("correct", "misread"):
        agree = (ident == "intended") == (verdict == "correct") and ident is not None
        if agree and loo_pass and loo_sides == {"A", "B"}:
            confidence = "high"
        elif override or (agree and loo_pass is None):
            confidence = "medium"
        elif abs(score) >= 0.3 and loo_sides == {"A", "B"}:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        confidence = None
    # ORIG far from BOTH reference sets: it has some third reading, or the
    # substitution changed how the neighbours are read (种子: neutral-tone 子
    # vs full-tone 子 in the non-words 肿子/众子). The score is then not about
    # the question asked -- treat any verdict as a hint only.
    bt = sep["comb"]["between"]
    dmin = min(v for v in (per_feat["comb"]["d_intended"], per_feat["comb"]["d_wrong"])
               if v is not None) if per_feat["comb"]["d_intended"] is not None else None
    far = bool(dmin is not None and np.isfinite(bt) and dmin > 0.5 * bt)
    if far and confidence in ("high", "medium"):
        confidence = "low"
    rnd = lambda v: round(v, 3) if isinstance(v, float) and np.isfinite(v) else v  # noqa: E731
    return {
        "word": word, "char": char, "sentence": sentence, "tts_text": texts["ORIG"],
        "intended_refs": ok, "wrong_refs": bad, "voice": voice, "rate": rate,
        "verdict": verdict, "confidence": confidence, "verdict_raw": raw, "score": score,
        "margin": margin, "near_identical_to": ident, "far_from_both": far,
        "dropped_refs": [k[2:] for k in dropped],
        "override": override,
        "selftest_sides": sorted(loo_sides),
        "features": per_feat,
        "neighbour_shift": {"intended": rnd(min((neighbour[k] for k in A), default=float("nan"))),
                            "wrong": rnd(min((neighbour[k] for k in B), default=float("nan")))},
        "separation": {f: {k: rnd(v) for k, v in s.items()} for f, s in sep.items()},
        "selftest_loo": {k[2:]: v for k, v in loo.items()}, "selftest_pass": loo_pass,
        "distances_from_orig": {k: {kk: rnd(vv) for kk, vv in dist[("ORIG", k)].items()}
                                for k in keys if k != "ORIG"},
        "window_s": [round(wins["ORIG"][0], 3), round(wins["ORIG"][1], 3)],
        "boundary_token": wins["ORIG"][2],
        "window_anchor": anchor,
        "tokens": {k: [m["text"] for m in marks[k]] for k in texts},
        "f0_semitones_window": {k: f0_track(feats[k], wins[k][:2]) for k in keys},
        "audio": {k: str(v) for k, v in audio.items()},
    }


def _chars(s: str) -> list[str]:
    s = s.strip()
    return [x for x in s.split(",") if x] if "," in s else list(s)


def main() -> None:
    ap = argparse.ArgumentParser(description="Acoustic polyphone check (edge-tts)")
    ap.add_argument("--word", required=True, help="word containing the polyphone, e.g. 柏林")
    ap.add_argument("--sentence", required=True,
                    help="sentence exactly as sent to TTS (speakable() output)")
    ap.add_argument("--ok-char", help="homophones of the INTENDED reading, e.g. 博勃驳 "
                    "(give 2-3: the extra ones are the self-test)")
    ap.add_argument("--bad-char", help="homophones of the WRONG reading, e.g. 摆佰百")
    ap.add_argument("--intended", help="pinyin TONE3 of intended reading (bo2); fills --ok-char")
    ap.add_argument("--wrong", help="pinyin TONE3 of wrong reading (bai3, de5); fills --bad-char")
    ap.add_argument("--char", help="the polyphone char inside --word (auto if unique)")
    ap.add_argument("--voice", default="zh-CN-YunjianNeural")
    ap.add_argument("--rate", default="+6%",
                    help="+6%% reels (build_match_reel); +22%% explainers/interviews")
    ap.add_argument("--margin", type=float, default=0.2)
    ap.add_argument("--orig-char", help="(testing) put this char into ORIG instead of --char, "
                    "e.g. check that the speakable() substitute is read as intended")
    ap.add_argument("--brief", action="store_true", help="drop audio paths / F0 tracks")
    ap.add_argument("--no-augment", action="store_true",
                    help="do not add same-reading homophones when only one is given")
    a = ap.parse_args()
    notes = {}
    if not a.ok_char:
        if not a.intended:
            ap.error("give --ok-char or --intended")
        refs, how = suggest_homophones(a.intended, exclude=a.word)
        a.ok_char, notes["ok_refs_from"] = "".join(refs), f"{a.intended}: {how}"
    if not a.bad_char:
        if not a.wrong:
            ap.error("give --bad-char or --wrong")
        refs, how = suggest_homophones(a.wrong, exclude=a.word)
        a.bad_char, notes["bad_refs_from"] = "".join(refs), f"{a.wrong}: {how}"
    ok, bad = _chars(a.ok_char), _chars(a.bad_char)
    if not a.no_augment:
        # one reference per side cannot self-test; add same-reading homophones
        from pypinyin import Style, pinyin
        for side, refs in (("ok", ok), ("bad", bad)):
            if len(refs) == 1 and len(refs[0]) == 1:
                rs = pinyin(refs[0], style=Style.TONE3, heteronym=True,
                            neutral_tone_with_five=True)[0]
                extra, how = suggest_homophones(rs[0], exclude=a.word + refs[0], k=2)
                refs.extend(extra)
                notes[f"{side}_refs_augmented"] = f"{refs[0]}={rs[0]} (+{''.join(extra)}: {how})"
                if len(rs) > 1:
                    notes[f"{side}_ref_warning"] = f"{refs[0]} itself has readings {rs}"
    if not ok or not bad:
        ap.error(f"no reference homophones (ok={ok}, bad={bad}); pass --ok-char/--bad-char")
    r = measure(a.word, a.sentence, ok, bad, a.voice, a.rate, a.char, a.margin, a.orig_char)
    if notes:
        r["ref_notes"] = notes
    if a.brief:
        for k in ("audio", "f0_semitones_window", "tokens"):
            r.pop(k, None)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
