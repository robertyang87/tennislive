#!/usr/bin/env python3
"""源片逐 0.05 秒响度——probe 那一趟顺手量下来，`--dry-run` 拿它按**成片口径**
重放 `check_reel_landed` 的数字静音闸。

## 来路：渲后 QC 红里的头号，预判一次都没接住

2026-09-06 ~ 09-25 的失败 run 里，「封面之后还有 N 秒是数字静音」（渲完才报）是
**第一大类：20 趟、162.8 runner 分钟**，每趟都先付了一整趟编码。其中 12 趟
`--dry-run` 手里明明有 probe，却一条静音预判都没打出来（日志里
`是静音（≤-60dB）` 0 命中）。两边量的根本不是一件事：

| | 量什么 | 口径 |
|---|---|---|
| probe `silent_audio` | **源片原声**，`silencedetect`（逐采样**峰值**，≥0.8s） | −60 dB |
| QC `per_second_db` | **成片**逐秒 RMS（8 kHz 单声道），现场声已乘 `BED_LOUD=0.72` | −60 dB |

`20·log10(0.72) = −2.85 dB`，于是源片 −60~−57 dB 的一截 probe 看不见、QC 必红；
再加上「峰值高、RMS 低」的一截（两分之间看台安静、偶尔一声咳嗽），probe 同样
看不见。实例：`zhang-cocciaretto-bjk-cup-2026-qf` 冷开场 quote 段红在成片第 3、4 秒
（−61.0 / −64.2 dB ＝ 源片约 −58 / −61），`zheng-paolini-bjk-cup-2026-qf` 的 quote 段红在
第 155 秒（−61.7，源 288.5）——两条的 `silent_audio` 都没有这几截。
`tennis-pipeline-ops`「2026-09-05：而这道预判**结构性地够不着**」那一节把这个
缺口记成「还开着，别忘了」——这里是它的补法。

## 补法：量 QC 量的那个数，按成片的增益和时间轴重放 QC

- **量**（`measure`）：和 `silencedetect` **同一趟 ffmpeg**（一次解码、两个输出），
  另一路解成 QC 同款的 8 kHz 单声道 PCM，逐 0.05 秒算 RMS。要细到亚秒：成片的
  「第 i 秒」落回源片是任意相位的一秒窗口，整秒的格子对不齐——两格求和的上界
  要多出 3 dB，正好把要抓的 −60~−57 那一档抹平。
- **存**（`encode_levels`）：只给**可能落进死秒**的块留数（任何含它的 0.5 秒窗口
  按最轻的音床增益都红不了的块记「响」，按游程压成 `L<块数>`）——一条正常转播的
  集锦只有两分之间真安静的几截留数，落盘几百字节。
- **重放**（`predict_levels` → `check_reel_landed.dead_seconds`）：按封面长度和
  每段的成片起点把成片每一整秒映射回源片，**按上界**算能量（窗口两头各放宽一块、
  压到的块整块算、溶解那 0.18 秒两路都整份算、「响」块当无穷大），乘上这一段真实
  的现场声增益（`BED_LOUD`×音床），再交给 QC 自己的 `dead_seconds`——**同一个
  函数、同一个门槛、同一个起算秒**。上界的意思是：预测「静音」时成片只会更静，
  所以这里红了就不是误报；代价是贴线的那零点几 dB 漏给 QC 兜底。
  两头各放宽一整块（0.05s）而不是几毫秒：AAC 的一帧就有 21ms，响块的能量会被
  编码器和重采样抹进相邻几十毫秒——紧挨着响块的那一秒不许判成静音。

判据 `tests/test_probe_audio.py::test_真跑一遍混音链_预测的静音秒成片里真的静音`：
合成源片把 render 的真音频链（AAC 分段 → `dissolve_filtergraph` → `duck_filtergraph`
→ AAC）跑一遍再用 QC 的 `per_second_db` 量，**没有一秒被预测成静音而实际不是**，
源片 −58.5 dB（silencedetect 看不见）那一截被预测到了。

## 硬不硬（R7：旁白尾巴那一类不做硬闸）

| 这一秒落在哪 | 处置 |
|---|---|
| 无旁白的视频段（冷开场、原声段、quote 段），实测够得着 | **硬**——实测值，不是估算；封面定长时相位也是确定的 |
| 同上，但封面跟着配音走（相位要等 TTS 才定） | 扫一整个周期，每个相位都红才**硬**，否则只报 |
| 有旁白的段、按离线估旁白说完之后的尾巴 | **只报不拦**——旁白长度是估的（±`SPEECH_EST_ERR`），f7b2501 那次把这一类定成「拿真实产物判」；报的时候分「按最长估也盖不住」和「按点估盖不住」两档 |
| 看过、确认要这么剪 | 那一段写 `"_digital_silence_why": "<为什么>"` 认领，降成只报 |
| 老 probe 没有 `audio_levels`、慢放段、mute 段 | 只报一句「这一层没查」——「没量」和「量过没事」不许长一样 |

⚠️ 自动产的 spec 同样是硬的——和 `silence_findings` 对无旁白段的口径一致（那一头是
模型，render 红了之后 `repair_reel_spec` 拿 dry-run 当复检闸，改窗口比烧一趟渲染便宜）。

⚠️ 这套只在 probe（量）和 dry-run（读）两处出现，render 路径一个字节都不多解
（`test_音频那套不许接进出片流程` 那条老规矩：解音轨拖慢出片）。
"""

from __future__ import annotations

import bisect
import math
import re
import subprocess
from pathlib import Path
from typing import Callable, Sequence

from check_reel_landed import SILENCE_FLOOR_DB, dead_seconds

#: 一块多长（秒）。成片一秒落回源片是任意相位的窗口，边上压到的块要整块算：
#: 0.05 秒时两头各多算一块（均匀底噪下上界高 +0.4 dB）；再粗就把 −60~−61 那一档
#: 抹掉了（失败的 20 趟里死秒的成片读数大半落在 −60.0 ~ −61.5）。
BLOCK_SECONDS = 0.05
#: 和 `check_reel_landed.per_second_db` 同一个采样口径（8 kHz 单声道 s16le）。
RATE = 8000
#: 「一块能不能落进死秒」按多长的窗口判（见 `encode_levels`）。它只影响**查全**：
#: 死秒落回源片是一整秒，里面任何 0.5 秒子窗口的能量都不会比整秒大，所以这把
#: 尺子只会多留块、不会漏掉整秒都安静的那一截。
MASK_WINDOW = 0.5
#: 成片一秒的能量门槛（功率×秒）：QC 判 `≤ -60 dB` 的那一秒，均方 ≤ 10^-6。
FLOOR_ENERGY = 10 ** (SILENCE_FLOOR_DB / 10)
#: 采样全零时的读数，和 `per_second_db` 一致（它对 rms=0 写 −99）。
DIGITAL_SILENCE_DB = -99.0
#: edge-tts 的 mp3 末尾那一截固定静音（`tennis-pipeline-ops`「说到 ＝ 段起点 ＋
#: mp3 时长 − 0.83」，逐段对过）。离线估的是 mp3 时长，真说完要再往前挪这么多。
TTS_TAIL = 0.83
#: 成片音轨相对画面时间轴、以及编码器／重采样抹开能量的余量：窗口两头各放宽
#: 一整块。AAC 一帧 1024 样本（48k 下 21ms），响块旁边几十毫秒会沾上它的能量。
ALIGN_SLACK = BLOCK_SECONDS
#: 段级认领键：看过、确认这几秒就是要这样剪（写了降成只报）。
CLAIM_KEY = "_digital_silence_why"

_ENC_HOW = ("逐 0.05 秒 RMS（8 kHz 单声道，同 check_reel_landed.per_second_db），"
            "dB 向上取整到 0.1；任何含它的 window 秒窗口按 quietest_gain 都红不了"
            "成片的块只记「响」，按游程写成 L<块数>")


# ── 量 ────────────────────────────────────────────────────────────────────────

def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True).stdout
    return bool(out.strip())


def block_levels(pcm: bytes, rate: int = RATE,
                 block: float = BLOCK_SECONDS) -> list[float]:
    """s16le 单声道 PCM → 逐块 RMS（dB，**向上**取整到 0.1——只会把块算响）。
    末尾不满一块的丢掉，和 `per_second_db` 丢掉末尾不满一秒的同一个口径。"""
    import numpy as np  # noqa: PLC0415

    size = int(round(rate * block))
    samples = np.frombuffer(pcm, dtype=np.int16).astype(float) / 32768.0
    count = len(samples) // size
    if not count:
        return []
    rms = np.sqrt((samples[:count * size].reshape(count, size) ** 2).mean(axis=1))
    return [math.ceil(20.0 * math.log10(v) * 10 - 1e-9) / 10 if v > 0
            else DIGITAL_SILENCE_DB for v in rms]


def measure(path: Path, *, quietest_gain: float, floor_db: float = -60.0,
            min_silence: float = 0.8,
            ) -> tuple[list[list[float]] | None, dict | None]:
    """**一趟 ffmpeg** 同时出两样：`silencedetect` 的静音区间，和逐块响度。

    返回 `(silent_audio, audio_levels)`；源片没有音轨时是 `(None, None)`——
    「没音轨」「量过为空」「有区间」三种在 probe.json 里不许长一样。
    两个输出都 `-map 0:a:0`：render 切段取的就是这一路（`cut_segment`）。
    `quietest_gain`：成片里现场声最轻会乘到多少（`BED_LOUD`×最低一档音床），
    存进记录——重放时比它还轻的段（mute）这份数据判不了，要出声说。
    """
    if not _has_audio(path):
        return None, None
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-map", "0:a:0", "-af",
         f"silencedetect=noise={floor_db}dB:d={min_silence}", "-f", "null", "-",
         "-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"],
        capture_output=True)
    if proc.returncode:
        raise RuntimeError("量源片音频失败："
                           + proc.stderr[-600:].decode("utf-8", "replace"))
    err = proc.stderr.decode("utf-8", "replace")
    starts = [float(m) for m in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*(-?[\d.]+)", err)]
    if len(starts) > len(ends):
        # 贴着文件末尾的静音没打 end——终点取音轨自己解出来的长度
        ends.append(len(proc.stdout) / 2 / RATE)
    spans = [[round(a, 2), round(b, 2)] for a, b in zip(starts, ends)]
    return spans, encode_levels(block_levels(proc.stdout), quietest_gain)


# ── 存 ────────────────────────────────────────────────────────────────────────

def encode_levels(levels: Sequence[float], quietest_gain: float,
                  window: float = MASK_WINDOW) -> dict:
    """逐块 dB → probe.json 里 `audio_levels` 那一格（自带 `_how`，读的人不用猜）。

    一块留不留数：存在一个含它的 `window` 秒窗口，能量乘上 `quietest_gain²`
    还落在成片一秒的门槛之下——否则任何一秒只要压到它就红不了，只记「响」。
    """
    k = max(1, int(round(window / BLOCK_SECONDS)))
    energy = [10 ** (db / 10) * BLOCK_SECONDS for db in levels]
    limit = FLOOR_ENERGY / quietest_gain ** 2
    keep = [False] * len(levels)
    if len(levels) <= k:
        keep = [sum(energy) <= limit] * len(levels)
    else:
        run = sum(energy[:k])
        for j in range(len(levels) - k + 1):
            if j:
                run += energy[j + k - 1] - energy[j - 1]
            if run <= limit:
                for b in range(j, j + k):
                    keep[b] = True
    tokens: list[str] = []
    loud = 0
    for db, kept in zip(levels, keep):
        if not kept:
            loud += 1
            continue
        if loud:
            tokens.append(f"L{loud}")
            loud = 0
        tokens.append(f"{db:.1f}")
    if loud:
        tokens.append(f"L{loud}")
    return {"block": BLOCK_SECONDS, "rate": RATE, "window": window,
            "quietest_gain": round(quietest_gain, 4), "blocks": len(levels),
            "db": " ".join(tokens), "_how": _ENC_HOW}


def decode_levels(record: dict | None) -> list[float] | None:
    """`audio_levels` → 逐块 dB（「响」的块是 +inf）。口径对不上、形状不对一律
    返回 None，由调用方当「没量过」——**坏数据不许被读成「很安静」**。"""
    if not isinstance(record, dict):
        return None
    try:
        if abs(float(record["block"]) - BLOCK_SECONDS) > 1e-9 \
                or int(record["rate"]) != RATE:
            return None
        out: list[float] = []
        for token in str(record["db"]).split():
            if token.startswith("L"):
                out.extend([math.inf] * int(token[1:]))
            else:
                out.append(float(token))
        return out if len(out) == int(record["blocks"]) else None
    except (KeyError, TypeError, ValueError):
        return None


def judges(seg, probe: dict | None, gain_value: float) -> bool:
    """这份 probe 判得了这一段没有：量过逐块响度、不是慢放（atempo 的叠接不保
    功率，上界不成立）、增益不比量的时候设想的最轻一档还轻（mute 判不了）。
    `silence_findings` 据此把无旁白段让给这里，同一截静音别报两遍。"""
    if seg.image or seg.speed != 1:
        return False
    record = (probe or {}).get("audio_levels")
    if decode_levels(record) is None:
        return False
    return gain_value >= float(record.get("quietest_gain", math.inf)) - 1e-9


# ── 重放 ──────────────────────────────────────────────────────────────────────

def source_energy(levels: Sequence[float], lo: float, hi: float,
                  slack: float = ALIGN_SLACK) -> float | None:
    """源片 [lo, hi) 这一截能量积分（功率×秒）的**上界**。

    窗口两头各放宽 `slack`、压到的块整块算——块里的能量怎么分布都不会被低估。
    够不着（越界、没量到）返回 None；压到「响」的块返回 inf。
    """
    if hi <= lo:
        return 0.0
    first = max(0, math.floor((lo - slack) / BLOCK_SECONDS + 1e-9))
    last = math.ceil((hi + slack) / BLOCK_SECONDS - 1e-9)
    if lo < -1e-9 or last > len(levels):
        return None
    total = 0.0
    for db in levels[first:last]:
        if math.isinf(db):
            return math.inf
        total += 10 ** (db / 10) * BLOCK_SECONDS
    return total


def film_starts(segments, cover: float) -> list[float]:
    """每段在成片上的起点——和 `dissolve_filtergraph` 的长度账同一笔：溶解吃掉的
    是每段多切的那 `SEG_FADE` 秒尾巴，起点一个不变。"""
    out, t = [], cover
    for seg in segments:
        out.append(t)
        t += seg.length
    return out


def predict_levels(segments, levels_by_source: dict[str, Sequence[float] | None],
                   cover: float, voiced_until: Sequence[float],
                   gain: Callable[[object], float], fade: float,
                   judged: Callable[[object], bool] = lambda seg: True,
                   ) -> list[float]:
    """成片逐秒响度的**上界**预测，形状和 `per_second_db` 的输出一样。

    `voiced_until[k]`：第 k 段在成片上有人声盖着的终点（绝对秒）；无旁白段
    就是它自己的起点。压到人声、整屏证据段、封面、片尾，或者源片没量到、
    `judged` 说判不了的段的秒记 +inf——判不了就当响，**不许**判成静音。
    """
    starts = film_starts(segments, cover)
    end = starts[-1] + segments[-1].length if segments else cover
    out = [math.inf] * max(0, math.ceil(end - 1e-9))

    def piece(k: int, off_lo: float, off_hi: float) -> float | None:
        seg = segments[k]
        if seg.image:
            return 0.0                    # 证据段的底轨是 anullsrc：只在溶解底料里出现
        levels = levels_by_source.get(seg.source)
        if levels is None or not judged(seg):
            return None
        e = source_energy(levels, seg.start + off_lo, seg.start + off_hi)
        return None if e is None else e * gain(seg) ** 2

    for i in range(math.ceil(cover - 1e-9), len(out)):
        if i + 1 > end + 1e-9:
            break                         # 这一秒压到片尾页（口播）了
        energy, ok = 0.0, True
        k = max(0, bisect.bisect_right(starts, i) - 1)
        while ok and k < len(segments) and starts[k] < i + 1:
            a, seg = starts[k], segments[k]
            lo, hi = max(i, a), min(i + 1, a + seg.length)
            if hi > lo:
                if seg.image or lo < voiced_until[k] - 1e-9:
                    ok = False
                    break
                e = piece(k, lo - a, hi - a)
                # 溶解：这一段开头 `fade` 秒里还叠着上一段多切的尾巴（淡出）。
                # 两路都按满增益整份算——三角曲线只会更小，上界不破。
                # 第 0 段叠的是封面的 anullsrc，算 0。
                if e is not None and k and lo < a + fade:
                    prev = segments[k - 1]
                    x_hi = min(hi, a + fade)
                    e2 = piece(k - 1, prev.length + (lo - a), prev.length + (x_hi - a))
                    e = None if e2 is None else e + e2
                if e is None:
                    ok = False
                    break
                energy += e
            k += 1
        if ok:
            out[i] = 10 * math.log10(energy) if energy > 0 else DIGITAL_SILENCE_DB
    return out


def _describe(seg, start: float, second: int, levels, predicted: float,
              gain_value: float) -> str:
    src = seg.start + max(0.0, second - start)
    lo = max(0, math.floor(src / BLOCK_SECONDS))
    window = [db for db in (levels or [])[lo:lo + round(1 / BLOCK_SECONDS)]
              if not math.isinf(db)]
    measured = f"源片这一截最响一块 {max(window):.1f} dB" if window else "源片偏轻"
    return (f"成片第 {second} 秒 ≈ 源 {src:.1f}–{src + 1:.1f}s："
            f"{measured}，×现场声增益 {gain_value:.2f}（{20 * math.log10(gain_value):+.1f} dB）"
            f"→ 成片上界 {predicted:.1f} dB")


def digital_silence_findings(
        spec: dict, segments, probes: dict, urls: dict, *,
        gain: Callable[[object], float], fade: float,
        cover_exact: float | None, cover_estimate: float,
        estimates: dict[int, float], est_err: float) -> tuple[list[str], list[str]]:
    """probe_dry_run 的第 ⑥ 条后半：按成片口径重放数字静音闸，返回 `(硬, 软)`。

    - `cover_exact`：封面定长时的秒数（赛场之上恒为 `COVER_SECONDS`）；跟着
      配音走时传 None，`cover_estimate` 是离线估，从它起扫一整个周期的相位
    - `estimates`：`{段序号: 离线估旁白秒数}`（`narration_estimates` 的口径，
      含 lead_pause）——只用来估「旁白尾巴」那一档，那一档只报不拦；
      `est_err` 是离线估的误差带（`SPEECH_EST_ERR`），分「必红／大概率」两档
    """
    hard: list[str] = []
    soft: list[str] = []
    if not segments:
        return hard, soft
    if spec.get("music"):
        soft.append("  背景音乐烧进片子（spec.music）——音乐会把静音垫起来，"
                    "逐块响度重放这一层不判")
        return hard, soft
    levels_by_source: dict[str, list[float] | None] = {}
    unmeasured: list[str] = []
    for seg in segments:
        if seg.image or seg.source in levels_by_source:
            continue
        probe = probes.get(urls.get(seg.source, ""))
        levels_by_source[seg.source] = decode_levels((probe or {}).get("audio_levels"))
        if probe is not None and levels_by_source[seg.source] is None \
                and probe.get("silent_audio") is not None:
            unmeasured.append(seg.source or "(主源)")
    if unmeasured:
        soft.append(f"  源 {'、'.join(unmeasured)}：逐 0.05 秒响度还没量过（probe 早于"
                    "`audio_levels`）——「源片不算静音、成片这一秒是」那一类这一层没查，"
                    "重跑一趟 mode=probe 就有")
    if not any(levels_by_source.values()):
        return hard, soft

    def judged(seg) -> bool:
        return judges(seg, probes.get(urls.get(seg.source, "")), gain(seg))

    raw = spec.get("segments") or []
    blind = [k for k, seg in enumerate(segments)
             if not seg.image and not seg.narration.strip()
             and levels_by_source.get(seg.source) is not None and not judged(seg)]
    if blind:
        soft.append("  第 " + "、".join(str(k + 1) for k in blind) + " 段（无旁白）："
                    "慢放或 mute，逐块响度的上界不成立，这一层没查")
    options = ([cover_exact] if cover_exact is not None else
               [round(cover_estimate + step / 20, 3) for step in range(20)])
    narrated = [bool(seg.narration.strip()) for seg in segments]
    runs = []
    for cover in options:
        starts = film_starts(segments, cover)
        # 三把尺子：旁白段整段算有人声（只剩无旁白段）／旁白按最长估说完之后／
        # 按点估说完之后。后两把只用来给「旁白尾巴」分档，那一类只报不拦。
        # 整屏证据段的窗口：和 `check_reel_landed.evidence_windows` 同一笔账
        # （那边读 spec 的 `seconds`／`end-start`，这里读解析好的段长，数一样）。
        evidence = [(a, a + seg.length) for a, seg in zip(starts, segments) if seg.image]
        extra = {"bare": None, "sure": est_err, "maybe": 0.0}
        found: dict[str, tuple[set[int], list[float]]] = {}
        for name, err in extra.items():
            voiced = [a if not said else a + seg.length if err is None else
                      a + max(0.0, estimates.get(k, seg.length) + err - TTS_TAIL)
                      for k, (a, seg, said) in enumerate(zip(starts, segments, narrated))]
            table = predict_levels(segments, levels_by_source, cover, voiced,
                                   gain, fade, judged)
            found[name] = (set(dead_seconds(table, math.ceil(cover) + 1, evidence)[0]),
                           table)
        bare, strict = found["bare"]
        sure, sure_table = found["sure"]
        maybe, loose = found["maybe"]
        runs.append((cover, starts, bare, sure - bare, maybe - sure,
                     strict, sure_table, loose))

    # 相位定不下来时（封面跟着配音走），拿**第一个有死秒的相位**来描述——拿离线估
    # 那一个的话，它恰好躲过去就一个字都不报，而别的相位照样会红。
    dead_phases = sum(1 for run in runs if run[2])
    every_phase = dead_phases == len(runs)
    shown = next((run for run in runs if run[2]),
                 next((run for run in runs if run[3] or run[4]), runs[0]))
    cover, starts, bare, sure, maybe, strict, sure_table, loose = shown

    def owner(second: int) -> int:
        return max(range(len(segments)),
                   key=lambda k: min(second + 1, starts[k] + segments[k].length)
                   - max(second, starts[k]))

    grouped: dict[tuple[int, str], list[str]] = {}
    for kind, seconds, table in (("bare", bare, strict), ("sure", sure, sure_table),
                                 ("maybe", maybe, loose)):
        for second in sorted(seconds):
            k = owner(second)
            grouped.setdefault((k, kind), []).append(_describe(
                segments[k], starts[k], second, levels_by_source.get(segments[k].source),
                table[second], gain(segments[k])))
    phase = ("" if cover_exact is not None else
             f"（封面跟着配音走，按封面 {cover:.2f}s 摆的相位"
             + ("；扫过一整个周期，**每个相位都有死秒**）" if every_phase else
                f"；一个周期 {len(runs)} 个相位里 {dead_phases} 个有死秒，"
                "换个相位可能躲得过，所以只报）"))
    for (k, kind), lines in sorted(grouped.items()):
        seg = segments[k]
        head = f"  第 {k + 1} 段 {seg.start:.1f}–{seg.end:.1f}s"
        body = "\n    ".join(lines)
        claim = str((raw[k] if k < len(raw) and isinstance(raw[k], dict) else {})
                    .get(CLAIM_KEY) or "").strip()
        if kind == "sure":
            soft.append(f"{head}（旁白按最长估也说不到这儿）：现场声按成片口径掉到 "
                        f"−60 dB 以下，渲后数字静音闸**必红**{phase}——把旁白写长盖住，"
                        f"或把窗口收在这一截之前（R7：旁白尾巴只报不拦）\n    {body}")
        elif kind == "maybe":
            soft.append(f"{head}（旁白按离线估说完之后）：现场声按成片口径掉到 "
                        f"−60 dB 以下，渲后数字静音闸**大概率红**{phase}——"
                        f"跑一次 --check-narration 拿真时长再看\n    {body}")
        elif claim:
            soft.append(f"{head}（无旁白）：按实测会漏出数字静音{phase}\n    {body}\n"
                        f"    已认领 {CLAIM_KEY}：{claim}")
        elif cover_exact is not None or every_phase:
            hard.append(f"{head}（无旁白）：按实测源片响度重放 QC，渲后数字静音闸"
                        f"**必红**{phase}\n    {body}\n"
                        "    收窗口避开这一截、给这一段配一句旁白盖住，或者看过之后在"
                        f"这一段写 `\"{CLAIM_KEY}\": \"<为什么>\"` 认领")
        else:
            soft.append(f"{head}（无旁白）：按实测会漏出数字静音{phase}\n    {body}")
    return hard, soft
