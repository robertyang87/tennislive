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
  的现场声增益（`BED_LOUD`×音床；不闪避那条路是 1.0），再交给 QC 自己的
  `dead_seconds`——**同一个函数、同一个门槛、同一个起算秒**。
  两头各放宽一整块（0.05s）而不是几毫秒：AAC 的一帧就有 21ms，响块的能量会被
  编码器和重采样抹进相邻几十毫秒——紧挨着响块的那一秒不许判成静音。
- **时间轴要按 render 的真实账算，不是按名义段长**（`audio_drift`，评审 2026-09-27
  抓的 BLOCKING）：每个 part 的现场声是 `-t {L+尾巴:.3f}` 编成的 AAC 48k，解出来是
  **整数个 1024 样本帧**（`-t 5.18` 解出 5.184s、`7.01` → 7.0187s），而
  `acrossfade` 把每一路接在前一路**解出来的末尾**上——于是第 k 段的现场声比画面、
  旁白、字幕晚 δ_k = Σ_{j<k}（封面算第 0 个 part）每个 part 多出来的那一截。
  画面不截的时候实测 14 段累积到 +159 ms，逐段和「补满」公式对到 0.1 ms。
  **但 δ 只知道区间**：每个 part 都带 `-shortest`，25 / 29.97 fps 下 `-ss` 落在两帧
  之间时画面少一帧，音轨跟着被截短 1~2 帧 AAC（真调 `cut_segment` 量的，三成的刀；
  50/60 fps 一刀没截）——哪一刀会截 dry-run 看不见，所以按 `part_padding` 的区间算，
  这一秒可能对上的源片取所有对齐的并集。越往后的段区间越宽，短的静音就判不死，
  那是漏给 QC 兜底，不是误报。不算 δ 的话，冷开场后半截「源片刚变静」会被判成必红，
  而成片那一秒里还有几十毫秒的响。
- **量的那一路要和 `-ss` 同一条时间轴**：音轨比画面晚开始的源片（容器里 audio
  start_time > 0），裸 PCM 的第 0 个样本是音轨自己的第一个样本，而 `-ss` 按文件
  时间轴寻址——实测 56ms 的源片整条错开 56ms。`aresample=first_pts=0` 补齐。

**上界只在这几个前提都成立时才是上界**——这是它会不会误报的全部条件，不是一句保证：
① 时间轴按上面那本账（δ 的区间、first_pts）；② 编码／重采样把响块能量抹开的范围不超过
`ALIGN_SLACK`（成片比量源片时多过三代 AAC——实测 −2 dB 的响→静边沿，格子后面那块
量源片时是干净的，成片里却抹进来 0.6~13 dB）；③ 增益按 render 那一趟真走的混音分支
（`_mix_ducks`）。render 改了 part 的编码（采样率、编码器、`-t`／`-shortest` 的写法）或者
混音分支，这几条就要跟着改——判据是下面那几条**真跑一遍 render 音频链**的测试，不是
这段话。贴线的那零点几 dB 漏给 QC 兜底。

判据（`tests/test_probe_audio.py`）：
`::test_真跑一遍混音链_预测的静音秒成片里真的静音`（3 段）和
`::test_十几段之后的漂移_段界溶解尾巴_响静边沿_真跑一遍混音链`（14 段）——合成源片把 render
的真音频链（AAC 分段 → `dissolve_filtergraph` → `duck_filtergraph` → AAC）跑一遍，再用
QC 的 `per_second_db` 量：**这两份夹具里**没有一秒被预测成静音而实际不是、给出了数的秒
一秒都不低于成片；源片 −58.5 dB（silencedetect 看不见）那一截被预测到；第 13 段上 +0.2 秒
的漂移、第 9→10 段接缝上的溶解尾巴、三道 −2 dB 的响→静边沿各有一秒专门压着——拆掉 δ、
拆掉溶解尾巴、`ALIGN_SLACK` 归零，各红一条。
`::test_真的cut_segment解出来的音轨长度落在模型的区间里`：δ 区间的两头拿**真的**
`cut_segment`／`_still_to_clip` 量。

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
#: 编码器／重采样把响块能量抹开的余量：窗口两头各放宽一整块。时间轴的账（δ 区间、
#: first_pts）另算，这一格只管「抹」——成片比量源片时多过三代 AAC，响→静边沿后面
#: 十几毫秒里成片沾到的能量比量出来的多（14 段夹具实测，归零就把上界打穿 0.6~13 dB）。
ALIGN_SLACK = BLOCK_SECONDS
#: 段级认领键：看过、确认这几秒就是要这样剪（写了降成只报）。
CLAIM_KEY = "_digital_silence_why"
#: render 的每个 part（封面、分段、证据段、片尾）音轨都是 `-c:a aac -ar 48000`
#: （`build_match_reel.AUDIO_RATE`，测试钉着两边一样），AAC 一帧 1024 个样本。
PART_AUDIO_RATE = 48000
AAC_FRAME = 1024
#: 成片帧率最低能到多少（`resolve_fps` 不认 10 fps 以下）——不知道帧率时按它算
#: δ 往少那头最远能漂多远（`part_padding`）。
SLOWEST_FPS = 10.0

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
    count = len(pcm) // 2 // size
    if not count:
        return []
    samples = np.frombuffer(pcm, dtype=np.int16, count=count * size).astype(float) / 32768.0
    rms = np.sqrt((samples.reshape(count, size) ** 2).mean(axis=1))
    return [math.ceil(20.0 * math.log10(v) * 10 - 1e-9) / 10 if v > 0
            else DIGITAL_SILENCE_DB for v in rms]


#: 流式读 PCM 时一口读多少块（60 秒）。整条读进内存再转 float64，8678 秒那条
#: 源片（仓库里 probe 过最长的，usq-2026-kei14）会在 probe runner 上顶到约 1.1 GB
#: （评审 2026-09-27 nit）；按块流式算，峰值只剩这一口。
STREAM_BLOCKS = 1200


def stream_block_levels(stream, rate: int = RATE,
                        block: float = BLOCK_SECONDS) -> tuple[list[float], int]:
    """从管道流式读 s16le 单声道 PCM，逐块算 RMS。返回 `(逐块 dB, 总字节数)`——
    和一次读完喂给 `block_levels` 的结果**逐块一样**（测试钉着）。"""
    size_bytes = int(round(rate * block)) * 2
    want = size_bytes * STREAM_BLOCKS
    levels: list[float] = []
    carry = b""
    total = 0
    while True:
        chunk = stream.read(want - len(carry))
        if not chunk:
            break
        total += len(chunk)
        carry += chunk
        if len(carry) >= want:
            levels.extend(block_levels(carry[:want], rate, block))
            carry = carry[want:]
    whole = len(carry) // size_bytes * size_bytes
    if whole:
        levels.extend(block_levels(carry[:whole], rate, block))
    return levels, total


def measure(path: Path, *, quietest_gain: float, floor_db: float = -60.0,
            min_silence: float = 0.8,
            ) -> tuple[list[list[float]] | None, dict | None]:
    """**一趟 ffmpeg** 同时出两样：`silencedetect` 的静音区间，和逐块响度。

    返回 `(silent_audio, audio_levels)`；源片没有音轨时是 `(None, None)`——
    「没音轨」「量过为空」「有区间」三种在 probe.json 里不许长一样。
    两个输出都 `-map 0:a:0`：render 切段取的就是这一路（`cut_segment`）。
    `quietest_gain`：成片里现场声最轻会乘到多少（`BED_LOUD`×最低一档音床），
    存进记录——重放时比它还轻的段（mute）这份数据判不了，要出声说。
    PCM 按块**流式**读（`stream_block_levels`），不把整条音轨攥在内存里；
    stderr（silencedetect 的输出）落临时文件，免得两个管道互相堵死。
    """
    import tempfile  # noqa: PLC0415

    if not _has_audio(path):
        return None, None
    with tempfile.TemporaryFile() as err_file:
        proc = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
             "-map", "0:a:0", "-af",
             f"silencedetect=noise={floor_db}dB:d={min_silence}", "-f", "null", "-",
             # `first_pts=0`：音轨比画面晚开始的源片（容器里 audio start_time > 0），
             # 裸 PCM 第 0 个样本是音轨自己的第一个样本，而 render 的 `-ss` 按**文件
             # 时间轴**寻址——不补齐就整条错开 start_time 那么多（实测 56ms 的源片
             # 错开 56ms，比 ALIGN_SLACK 还宽）。silencedetect 按帧 pts 报时，本来就对。
             "-map", "0:a:0", "-af", "aresample=first_pts=0",
             "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"],
            stdout=subprocess.PIPE, stderr=err_file)
        try:
            levels, total = stream_block_levels(proc.stdout)
        finally:
            proc.stdout.close()
            code = proc.wait()
        err_file.seek(0)
        err = err_file.read().decode("utf-8", "replace")
    if code:
        raise RuntimeError("量源片音频失败：" + err[-600:])
    starts = [float(m) for m in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*(-?[\d.]+)", err)]
    if len(starts) > len(ends):
        # 贴着文件末尾的静音没打 end——终点取音轨自己解出来的长度
        ends.append(total / 2 / RATE)
    spans = [[round(a, 2), round(b, 2)] for a, b in zip(starts, ends)]
    return spans, encode_levels(levels, quietest_gain)


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
    是每段多切的那 `SEG_FADE` 秒尾巴，起点一个不变。**这是画面（以及旁白 adelay、
    字幕）的时间轴**；现场声还要再晚 `audio_drift` 那么多。"""
    out, t = [], cover
    for seg in segments:
        out.append(t)
        t += seg.length
    return out


def aac_padding(seconds: float) -> float:
    """一个 part 按 `-t {seconds:.3f}` 编成 AAC 48k 之后，解出来**最多**比名义长多少秒。

    AAC 一帧 1024 个样本，编码器把最后一帧补零补满，解码不裁——于是解出来是整数帧：
    `-t 5.18` → 5.184s、`7.01` → 7.0187s、`4.55` → 4.5653s（评审 2026-09-27 实测）。
    `-t` 按三位小数写，这一笔零头也算进来。
    """
    cut = round(seconds, 3)
    frames = math.ceil(cut * PART_AUDIO_RATE / AAC_FRAME - 1e-9)
    return frames * AAC_FRAME / PART_AUDIO_RATE - seconds


def part_padding(seconds: float, frame_seconds: float) -> tuple[float, float]:
    """一个 part 解出来比名义 `seconds` 长多少秒：`(最少, 最多)`，最少可以是负的。

    - **最多** `aac_padding`：`-t` 截到 `seconds`，最后一帧补满。
    - **最少**：每个 part 都带 `-shortest`，音频不越过视频那一路的尾巴。视频是
      `fps=` 之后按 `-t` 截的，`-ss` 落在两帧之间时会少一帧，尾巴 ≥ `seconds − 1/fps`；
      音频截到不越过它的整帧，再少一帧 AAC。

    实测（2026-09-27，真调 `cut_segment`，25 / 29.97 / 50 / 60 fps 各 12 刀）：解出来
    落在 `[seconds − 24.7ms, seconds + aac_padding]`；25 和 29.97 fps 有三成的刀比
    「补满」少 1~2 帧 AAC，50/60 fps 一刀都没少——**哪一刀会少，dry-run 看不见**
    （取决于 `-ss` 的相位和 ffmpeg 版本的 `-shortest` 实现），所以按区间算。
    """
    hi = aac_padding(seconds)
    lo = -(frame_seconds + AAC_FRAME / PART_AUDIO_RATE)
    return min(lo, hi), hi


def part_audio_seconds(seg, fade: float) -> float:
    """第 k 个 part 的音轨里**有真声**的那一截多长：段长 ＋ 多切的溶解底料。
    底料是源片 `seg.end` 之后那 `fade` 秒，它在下一段开头那次溶解里淡出——
    **下一段开头那一秒里有它**（上一段的尾巴），重放时不许漏。再往后是补齐的零。
    末段不留尾巴时（片尾关掉）真声只到段长，按 `L + fade` 算只会多算，上界不破。"""
    return seg.length + fade


def audio_drift(segments, cover: float, fade: float,
                frame_seconds: float) -> list[tuple[float, float]]:
    """第 k 段的现场声在成片上比画面晚多少秒：`[(δ_k 最少, δ_k 最多), …]`。

    `acrossfade` 没有 offset，每一路都接在前一路**解出来**的末尾上（见
    `dissolve_filtergraph` 的长度账），所以 δ_k = 封面 part 的补齐 + Σ_{j<k} 第 j 段的
    补齐（`part_padding`）。第 k 段之前的 part 都不是末段，尾巴一律是 `fade`。
    旁白是在拼好之后按名义起点 `adelay` 上去的，**不漂**；只有现场声漂。
    """
    lo, hi = part_padding(cover + fade, frame_seconds)
    out = []
    for seg in segments:
        out.append((lo, hi))
        d_lo, d_hi = part_padding(seg.length + fade, frame_seconds)
        lo, hi = lo + d_lo, hi + d_hi
    return out


def predict_levels(segments, levels_by_source: dict[str, Sequence[float] | None],
                   cover: float, voiced_until: Sequence[float],
                   gain: Callable[[object], float], fade: float,
                   judged: Callable[[object], bool] = lambda seg: True,
                   *, frame_seconds: float = 1 / SLOWEST_FPS) -> list[float]:
    """成片逐秒响度的**上界**预测，形状和 `per_second_db` 的输出一样。

    `voiced_until[k]`：第 k 段在成片上有人声盖着的终点（绝对秒，画面时间轴）；
    无旁白段就是它自己的起点。压到人声、整屏证据段、封面、片尾，或者源片没量到、
    `judged` 说判不了的段的秒记 +inf——判不了就当响，**不许**判成静音。

    现场声按**真实的音频时间轴**摆：第 k 个 part 的音轨从成片 `起点 + δ_k` 开始，
    本地第 t 秒是源片 `seg.start + t`，一直到 `L + fade`（再往后是补齐的零）——溶解
    那一段两路都在，三角曲线的权重 ≤ 1，所以**各自整份相加**就是上界。δ_k 只知道
    区间（`audio_drift`），这一秒可能对上的源片取**所有对齐的并集**。
    `frame_seconds`：成片一帧多长（`1/fps`），决定 δ 往少那头能漂多远；不知道就按
    `resolve_fps` 认的最低帧率算最坏。
    """
    starts = film_starts(segments, cover)
    end = starts[-1] + segments[-1].length if segments else cover
    out = [math.inf] * max(0, math.ceil(end - 1e-9))
    drift = audio_drift(segments, cover, fade, frame_seconds)

    def piece(k: int, local_lo: float, local_hi: float) -> float | None:
        """第 k 个 part 自己时间轴上 [lo, hi) 这一截（×增益²）的能量上界。"""
        seg = segments[k]
        if seg.image:
            return 0.0                    # 证据段的底轨是 anullsrc：一个样本都是零
        levels = levels_by_source.get(seg.source)
        if levels is None or not judged(seg):
            return None
        e = source_energy(levels, seg.start + local_lo, seg.start + local_hi)
        return None if e is None else e * gain(seg) ** 2

    def masked(i: int) -> bool:
        """这一秒压到人声（旁白按画面时间轴 adelay）或整屏证据段——判不了。"""
        for k, (a, seg) in enumerate(zip(starts, segments)):
            lo, hi = max(i, a), min(i + 1, a + seg.length)
            if hi > lo and (seg.image or lo < voiced_until[k] - 1e-9):
                return True
        return False

    for i in range(math.ceil(cover - 1e-9), len(out)):
        if i + 1 > end + 1e-9:
            break                         # 这一秒压到片尾页（口播）了
        if masked(i):
            continue
        energy, ok = 0.0, True
        # 封面 part 的底轨是 anullsrc，能量 0，不用算。
        for k, (a, seg, (d_lo, d_hi)) in enumerate(zip(starts, segments, drift)):
            # 这个 part 的本地时间里，哪一截可能落进成片 [i, i+1)：音轨最晚在
            # a+d_hi 接上、最早在 a+d_lo 接上，两头各取最宽的那一种。
            # 过了 `part_audio_seconds` 就是补齐的零——源片后面那一截根本没切进来；
            # 它之前那 `fade` 秒是溶解底料，落在下一段开头（上一段的尾巴也算这里）。
            local_lo = max(0.0, i - (a + d_hi))
            local_hi = min(part_audio_seconds(seg, fade), i + 1 - (a + d_lo))
            if local_hi <= local_lo:
                continue
            e = piece(k, local_lo, local_hi)
            if e is None:
                ok = False
                break
            energy += e
        if ok:
            out[i] = 10 * math.log10(energy) if energy > 0 else DIGITAL_SILENCE_DB
    return out


def _describe(seg, start: float, second: int, levels, predicted: float,
              gain_value: float) -> str:
    """`start` 是这一段现场声在成片上的起点（画面起点 + δ_k）。"""
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
        estimates: dict[int, float], est_err: float,
        frame_seconds: float = 1 / SLOWEST_FPS) -> tuple[list[str], list[str]]:
    """probe_dry_run 的第 ⑥ 条后半：按成片口径重放数字静音闸，返回 `(硬, 软)`。

    - `frame_seconds`：成片一帧多长（主源 probe 的帧率按 `resolve_fps` 折算），
      给 `audio_drift` 定 δ 的区间；不知道就按最低帧率算最坏

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
                                   gain, fade, judged, frame_seconds=frame_seconds)
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
    drift = [hi for _lo, hi in audio_drift(segments, cover, fade, frame_seconds)]

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
                segments[k], starts[k] + drift[k], second,
                levels_by_source.get(segments[k].source), table[second], gain(segments[k])))
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
