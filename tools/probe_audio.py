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
- **时间轴：现场声和画面同一本账，δ 恒为零**（2026-09-28）。评审 2026-09-27 抓过的
  BLOCKING：`acrossfade` 没有 offset，每一路现场声接在前一路**解出来的末尾**上，而 part
  解出来不正好是 `-t` 那么长（`-shortest` 截短 −6~−29 ms／刀，两版 ffmpeg 都有；沙箱 6.1
  还补满最后一帧 +2~+19 ms），第 k 段的现场声就和画面错开 δ_k。原来这里按 δ 的**最坏
  区间**取并集——每个 part 往负那头放宽 1/fps ＋ 1 帧 AAC，十三段之后窗口宽出约 1 秒，
  后段的短静音一律判不死：09-20~27 渲后静音红的 16 趟回放下来，这一项一个就挡掉了一半
  的预判。现在 `dissolve_filtergraph` 在每一路进 `acrossfade` 之前按**样本数**
  （`apad whole_len` ＋ `atrim end_sample`）钉成名义长度，δ 由构造归零，这里按名义起点摆，
  不再取区间。判据 `::test_真cut_segment刀刀截短_溶解钉回名义长度_成片不漂`（真
  `cut_segment` 造出九刀截短，成片的现场声照样落在名义时刻；拆掉那一钉就误报）。
- **量的那一路要和 `-ss` 同一条时间轴**：音轨比画面晚开始的源片（容器里 audio
  start_time > 0），裸 PCM 的第 0 个样本是音轨自己的第一个样本，而 `-ss` 按文件
  时间轴寻址——实测 56ms 的源片整条错开 56ms。`aresample=first_pts=0` 补齐。

**上界只在这几个前提都成立时才是上界**——这是它会不会误报的全部条件，不是一句保证：
① 时间轴按上面那本账（溶解钉回名义长度、first_pts）；② 编码／重采样把响块能量抹开的范围不超过
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
一秒都不低于成片；源片 −58.5 dB（silencedetect 看不见）那一截被预测到。14 段夹具里
第 9→10 段接缝上的溶解尾巴、−2 dB 的响→静边沿各有一秒专门压着——拆掉溶解尾巴、
`ALIGN_SLACK` 归零，各红一条。

## 硬不硬

| 这一秒落在哪 | 处置 |
|---|---|
| 无旁白的视频段（冷开场、原声段、quote 段），实测够得着 | **硬**——实测值，不是估算；封面定长时相位也是确定的 |
| 同上，但封面跟着配音走（相位要等 TTS 才定） | 扫一整个周期，每个相位都红才**硬**，否则只报 |
| 有旁白的段、旁白按**上包络**（`speech_ceiling`）也说不到这儿 | **手写 spec 硬**（2026-09-28），自动 spec 只报 |
| 有旁白的段、按离线**点估**说完之后、上包络之前 | 只报，并给出 `--check-narration` 那条命令——离线估判不了 |
| `--check-narration` 合了真语音（`measured`），按真语音说完之后 | **手写 spec 硬**，自动 spec 只报 |
| 看过、确认要这么剪 | 那一段写 `"_digital_silence_why": "<为什么>"` 认领，降成只报 |
| 老 probe 没有 `audio_levels`、慢放段、mute 段 | 只报一句「这一层没查」＋重 probe 的原命令——「没量」和「量过没事」不许长一样 |

⚠️ 无旁白段对自动产的 spec 同样是硬的——和 `silence_findings` 对无旁白段的口径一致（那一头是
模型，render 红了之后 `repair_reel_spec` 拿 dry-run 当复检闸，改窗口比烧一趟渲染便宜）。

### 旁白尾巴为什么从「只报」改成手写 spec 硬（2026-09-28 返工审计）

R7（f7b2501）把旁白尾巴定成只报，理由是「旁白长度是估的」。审计量出来的账是另一回事：
09-20 ~ 09-27 渲后「数字静音」红了 **16 趟、12 条片子、117 runner 分钟，渲前 0 趟拦住**；
50 个死秒里 **43 个落在有旁白那段的尾巴上**、7 个在无旁白段（按失败 run 的 artifact 里
render.json 记的真封面长逐秒定位；审计按 1.2 秒封面估的「37＋4 个图卡段＋2 个没定位上」，
那几个其实都是封面跟着配音走的片子里的旁白尾巴）。「长度是估的」只说明**点估**判不了，
不说明**上包络**判不了——旁白按最长也说不到的那一秒，成片里就是现场声本身，和无旁白段
一样是实测值。所以分成两截：上包络之外硬、点估与上包络之间只报并指到 `--check-narration`
（真语音一合，这一截也变成确定的，那边同样硬）。

⚠️ **上包络不是 `est + SPEECH_EST_ERR`**：那条带子是按 Azure 拟合的，而 runner 现在走
edge-tts（main 上 09-15 之后 80 份 render.json 全是 `edge-tts`），它慢得和句长成正比——
1595 段里 16 段超出 `est + 2.20`，最坏 +4.85 秒（43 秒的长段）。平移盖不住，要带斜率，
见 `HARD_EST_SLOPE`。

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
#: 编码器／重采样把响块能量抹开的余量：窗口两头各放宽一整块。时间轴的账（溶解钉回
#: 名义长度、first_pts）另算，这一格只管「抹」——成片比量源片时多过三代 AAC，响→静
#: 边沿后面十几毫秒里成片沾到的能量比量出来的多（14 段夹具实测，归零就把上界打穿
#: 0.6~13 dB）。
ALIGN_SLACK = BLOCK_SECONDS
#: 段级认领键：看过、确认这几秒就是要这样剪（写了降成只报）。
CLAIM_KEY = "_digital_silence_why"
#: 旁白**最晚**说到哪儿（硬的那一档用）：真 mp3 ≤ 离线估 ×（1 + 斜率）＋ `est_err`。
#: 2026-09-28 量的：main 上每份 render.json 的 `narration_seconds`（真 mp3 秒数）对
#: **今天的**离线估（含 lead_pause），3921 段——
#:
#: | 后端 | 段数 | 中位 | 最坏 | 超出 est+2.20 | 斜率 0.10 时要的常数 |
#: |---|---|---|---|---|---|
#: | edge-tts（runner 现在走的） | 1595 | +0.55 | **+4.85** | **16** | 1.33 |
#: | azure | 2289 | +0.05 | +2.19 | 0 | 0.85 |
#: | 没记后端 | 37 | +0.78 | +1.43 | 0 | 0.70 |
#:
#: edge-tts 的偏差跟句长成正比（43 秒的长段 +4.85、2 秒的短段 +0.9），光平移盖不住；
#: 斜率 0.10 ＋ `est_err`（2.20）对三档各留 0.87／1.35／1.50 秒余量。azure 的 mp3 尾巴就算
#: 没有那 0.83 秒静音（按 0 算），`1.10·est + 2.20 − TTS_TAIL` 也还比它要的 0.85 宽 0.52 秒。
#: 判据 `tests/test_probe_audio.py::test_上包络盖得住每一段真语音`（冻结最坏的几段）。
HARD_EST_SLOPE = 0.10
#: 真语音「说完了」按多轻算：逐块 RMS 低于它的尾巴算没人说话。成片里旁白是
#: `amix normalize=0` 原样叠上去的，−80 dB 的一块一秒最多贡献门槛能量的 1%，
#: 压不翻一个 −60 的死秒。
VOICE_FLOOR_DB = -80.0
#: 真语音说完之后再让出多少秒才算没人说话：mp3 解码的起点对齐、`adelay` 取整到毫秒、
#: AAC 把最后一个字抹进后面二十来毫秒，一起按 0.1 秒算。
MEASURED_GUARD = 0.1


def speech_ceiling(est: float, est_err: float) -> float:
    """离线估 `est` 秒（含 lead_pause）的旁白，真 mp3 最长可能多长——见 `HARD_EST_SLOPE`。"""
    return est * (1 + HARD_EST_SLOPE) + est_err


def voice_speech_end(path: Path) -> float | None:
    """一条语音文件里真正有声音的最后一刻（秒，从文件第 0 个样本算，含 lead_pause 那段
    `<break>`）。和 QC 同一个量法（8 kHz 单声道逐块 RMS），高于 `VOICE_FLOOR_DB` 的最后
    一块的末尾；解不出来返回 None（调用方退回上包络，**不许**当成没说话）。"""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-map", "0:a:0",
         "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"],
        capture_output=True)
    if proc.returncode or not proc.stdout:
        return None
    levels = block_levels(proc.stdout)
    last = max((i for i, db in enumerate(levels) if db > VOICE_FLOOR_DB), default=-1)
    return (last + 1) * BLOCK_SECONDS


def reprobe_command(url: str, slug: str, probe: dict | None, ref: str) -> str:
    """把一条老 probe 按原样重跑一遍的命令（区间、记分条框照抄上一趟）。
    `ref` 要含 d8fb15b74（#1134）——从那一版起 probe 才写 `audio_levels`。"""
    probe = probe or {}
    parts = [f"gh workflow run match-reel.yml --ref {ref} -f mode=probe",
             f"-f slug={slug}", f"-f url={url}"]
    for key in ("clip_from", "clip_to", "scorebox"):
        if probe.get(key) not in (None, ""):
            parts.append(f"-f {key}={probe[key]}")
    return " ".join(parts)
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
    是每段多切的那 `SEG_FADE` 秒尾巴，起点一个不变。画面、旁白 adelay、字幕和
    现场声（溶解前每一路钉回名义长度，见 `dissolve_filtergraph`）都是这一本账。"""
    out, t = [], cover
    for seg in segments:
        out.append(t)
        t += seg.length
    return out


def part_audio_seconds(seg, fade: float) -> float:
    """第 k 个 part 的音轨里**有真声**的那一截多长：段长 ＋ 多切的溶解底料。
    底料是源片 `seg.end` 之后那 `fade` 秒，它在下一段开头那次溶解里淡出——
    **下一段开头那一秒里有它**（上一段的尾巴），重放时不许漏。再往后是补齐的零。
    末段不留尾巴时（片尾关掉）真声只到段长，按 `L + fade` 算只会多算，上界不破。"""
    return seg.length + fade


def predict_levels(segments, levels_by_source: dict[str, Sequence[float] | None],
                   cover: float, voiced_until: Sequence[float],
                   gain: Callable[[object], float], fade: float,
                   judged: Callable[[object], bool] = lambda seg: True) -> list[float]:
    """成片逐秒响度的**上界**预测，形状和 `per_second_db` 的输出一样。

    `voiced_until[k]`：第 k 段在成片上有人声盖着的终点（绝对秒，画面时间轴）；
    无旁白段就是它自己的起点。压到人声、封面、片尾，或者源片没量到、
    `judged` 说判不了的段的秒记 +inf——判不了就当响，**不许**判成静音。
    整屏证据段在人声之外按 anullsrc 算零，豁免交给 `dead_seconds` 的证据窗口（QC 口径）。

    现场声按成片时间轴摆：第 k 个 part 的音轨从成片起点开始（溶解前钉回名义长度，
    δ 恒为零），本地第 t 秒是源片 `seg.start + t`，一直到 `L + fade`（再往后是补齐的
    零）——溶解那一段两路都在，三角曲线的权重 ≤ 1，所以**各自整份相加**就是上界。
    """
    starts = film_starts(segments, cover)
    end = starts[-1] + segments[-1].length if segments else cover
    out = [math.inf] * max(0, math.ceil(end - 1e-9))

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
        """这一秒压到人声（旁白按画面时间轴 adelay）——判不了。

        整屏证据段（image／stat_card／title_card）**不整段遮**，和 QC 同一个口径
        （2026-09-28）：它的底轨是 anullsrc，旁白说完之后就是真的零；整秒落在它的窗口
        （两头各 0.3 秒）里的，`dead_seconds` 按 QC 自己的 `in_ev` 豁免，跨出窗口的那
        一秒（证据段口播说完 ＋ 下一段安静的开头）QC 照样数，这里也得数——原来整段一遮，
        那一秒永远判不到。"""
        for k, (a, seg) in enumerate(zip(starts, segments)):
            lo, hi = max(i, a), min(i + 1, a + seg.length)
            if hi > lo and lo < voiced_until[k] - 1e-9:
                return True
        return False

    for i in range(math.ceil(cover - 1e-9), len(out)):
        if i + 1 > end + 1e-9:
            break                         # 这一秒压到片尾页（口播）了
        if masked(i):
            continue
        energy, ok = 0.0, True
        # 封面 part 的底轨是 anullsrc，能量 0，不用算。
        for k, (a, seg) in enumerate(zip(starts, segments)):
            # 这个 part 的本地时间里，哪一截落进成片 [i, i+1)。
            # 过了 `part_audio_seconds` 就是补齐的零——源片后面那一截根本没切进来；
            # 它之前那 `fade` 秒是溶解底料，落在下一段开头（上一段的尾巴也算这里）。
            local_lo = max(0.0, i - a)
            local_hi = min(part_audio_seconds(seg, fade), i + 1 - a)
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
    """`start` 是这一段在成片上的起点（现场声和画面同一个起点）。"""
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
        estimates: dict[int, float], est_err: float, strict: bool = False,
        measured: dict[int, float] | None = None,
        reprobe: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """probe_dry_run 的第 ⑥ 条后半：按成片口径重放数字静音闸，返回 `(硬, 软)`。

    - `cover_exact`：封面定长时的秒数（赛场之上恒为 `COVER_SECONDS`；`--check-narration`
      合过封面配音时是真长度）；跟着配音走又没合过时传 None，`cover_estimate` 是离线估，
      从它起扫一整个周期的相位
    - `estimates`：`{段序号: 离线估旁白秒数}`（`narration_estimates` 的口径，含 lead_pause）
    - `est_err`：离线估的误差带（`SPEECH_EST_ERR`）；上包络见 `speech_ceiling`
    - `strict`：旁白尾巴那两档（上包络／真语音）硬不硬——手写的 spec 硬，自动 spec 只报
    - `measured`：`{段序号: 真语音说到段内第几秒}`（`--check-narration` 合过真语音时给，
      `voice_speech_end` 的口径）；给了就不再报「点估」那一档
    - `reprobe`：`{源片 URL: 重 probe 的原命令}`，老 probe 没有 `audio_levels` 时照印
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
            unmeasured.append(seg.source)
    if unmeasured:
        lines = [f"  源 {'、'.join(k or '(主源)' for k in unmeasured)}：逐 0.05 秒响度还没量过"
                 "（probe 早于 `audio_levels`——d8fb15b74／#1134 起 probe 才写这一格，更早的"
                 "probe、以及从更早的分支拨的 probe 都没有）。按成片口径重放数字静音这一层"
                 "**没查**（09-20~27 渲后数字静音红 16 趟，渲前 0 趟拦住）。重 probe 一趟就有："]
        for key in unmeasured:
            url = urls.get(key, "")
            lines.append("    " + ((reprobe or {}).get(url) or
                                   f"gh workflow run match-reel.yml --ref <分支> -f mode=probe "
                                   f"-f slug=<slug> -f url={url}"))
        soft.append("\n".join(lines))
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

    def spoken_to(kind: str, k: int, seg) -> float | None:
        """第 k 段旁白在这一把尺子下说到段内第几秒；None＝整段算有人声。"""
        est = estimates.get(k, seg.length)
        if kind == "bare":
            return None
        if kind == "measured" and measured is not None and k in measured:
            return measured[k] + MEASURED_GUARD
        if kind == "maybe":
            return max(0.0, est - TTS_TAIL)
        return max(0.0, speech_ceiling(est, est_err) - TTS_TAIL)    # sure／没量到的 measured

    # 尺子：旁白段整段算有人声（只剩无旁白段）／旁白按上包络说完之后／按点估说完之后；
    # 合过真语音（`--check-narration`）时后两把换成「按真语音说完之后」一把——真长度在手，
    # 上包络只会更松（它要是比真语音短，反倒会把还在说话的一秒判成静音）。
    kinds = ["bare", "measured"] if measured is not None else ["bare", "sure", "maybe"]
    runs = []
    for cover in options:
        starts = film_starts(segments, cover)
        # 整屏证据段的窗口：和 `check_reel_landed.evidence_windows` 同一笔账
        # （那边读 spec 的 `seconds`／`end-start`，这里读解析好的段长，数一样）。
        evidence = [(a, a + seg.length) for a, seg in zip(starts, segments) if seg.image]
        found: dict[str, tuple[set[int], list[float]]] = {}
        for kind in kinds:
            voiced = []
            for k, (a, seg, said) in enumerate(zip(starts, segments, narrated)):
                to = spoken_to(kind, k, seg) if said else 0.0
                voiced.append(a + seg.length if to is None else a + to)
            table = predict_levels(segments, levels_by_source, cover, voiced,
                                   gain, fade, judged)
            found[kind] = (set(dead_seconds(table, math.ceil(cover) + 1, evidence)[0]),
                           table)
        # 每一档只记「上一档没有、这一档才冒出来的」秒：bare ⊆ sure ⊆ maybe；bare ⊆ measured
        tiers: dict[str, tuple[set[int], list[float]]] = {}
        seen: set[int] = set()
        for kind in kinds:
            seconds, table = found[kind]
            tiers[kind] = (seconds - seen, table)
            seen |= seconds
        runs.append((cover, starts, tiers))

    # 相位定不下来时（封面跟着配音走），每一档各自数「几个相位有死秒」；描述拿**第一个
    # 有死秒的相位**——拿离线估那一个的话，它恰好躲过去就一个字都不报，而别的相位照样会红。
    phases_with = {kind: sum(1 for run in runs if run[2][kind][0]) for kind in kinds}
    shown = next((run for kind in kinds for run in runs if run[2][kind][0]), runs[0])
    cover, starts, tiers = shown

    def owner(second: int, kind: str) -> int:
        """这一秒记在哪一段名下：压得最多的那段；旁白尾巴那几档记在压到它的**有旁白**
        那段名下（是那一段的旁白说完了才露出来的，改也改那一段）。"""
        overlap = {k: min(second + 1, starts[k] + segments[k].length) - max(second, starts[k])
                   for k in range(len(segments))}
        pool = [k for k, v in overlap.items() if v > 0]
        said = [k for k in pool if narrated[k]]
        return max(said if kind != "bare" and said else pool or list(overlap),
                   key=lambda k: overlap[k])

    def phase(kind: str) -> str:
        if cover_exact is not None:
            return ""
        n = phases_with[kind]
        return (f"（封面跟着配音走，按封面 {cover:.2f}s 摆的相位"
                + ("；扫过一整个周期，**每个相位都有死秒**）" if n == len(runs) else
                   f"；一个周期 {len(runs)} 个相位里 {n} 个有死秒，"
                   "换个相位可能躲得过，所以只报）"))

    slug = str(spec.get("slug") or "<slug>")
    check_cmd = (f"python3 tools/build_match_reel.py render --check-narration "
                 f"--spec specs/reels/{slug}.json")
    grouped: dict[tuple[int, str], list[str]] = {}
    for kind in kinds:
        seconds, table = tiers[kind]
        for second in sorted(seconds):
            k = owner(second, kind)
            grouped.setdefault((k, kind), []).append(_describe(
                segments[k], starts[k], second,
                levels_by_source.get(segments[k].source), table[second], gain(segments[k])))
    for (k, kind), lines in sorted(grouped.items(), key=lambda item: (
            item[0][0], kinds.index(item[0][1]))):
        seg = segments[k]
        head = f"  第 {k + 1} 段 {seg.start:.1f}–{seg.end:.1f}s"
        body = "\n    ".join(lines)
        claim = str((raw[k] if k < len(raw) and isinstance(raw[k], dict) else {})
                    .get(CLAIM_KEY) or "").strip()
        decided = cover_exact is not None or phases_with[kind] == len(runs)
        if kind == "bare":
            where, cure = "（无旁白）", ("收窗口避开这一截、给这一段配一句旁白盖住")
            if claim:
                soft.append(f"{head}{where}：按实测会漏出数字静音{phase(kind)}\n    {body}\n"
                            f"    已认领 {CLAIM_KEY}：{claim}")
            elif decided:
                hard.append(f"{head}{where}：按实测源片响度重放 QC，渲后数字静音闸"
                            f"**必红**{phase(kind)}\n    {body}\n"
                            f"    {cure}，或者看过之后在这一段写 "
                            f"`\"{CLAIM_KEY}\": \"<为什么>\"` 认领")
            else:
                soft.append(f"{head}{where}：按实测会漏出数字静音{phase(kind)}\n    {body}")
            continue
        if kind == "maybe":
            soft.append(f"{head}（旁白按离线点估说完之后）：现场声按成片口径掉到 −60 dB "
                        f"以下，渲后数字静音闸**大概率红**{phase(kind)}——离线估判不了这一截，"
                        f"拿真语音长度重放一遍（约 1 分钟，要联网；手写 spec 在那儿按真长度是硬的）：\n"
                        f"    {check_cmd}\n"
                        f"    （或 match-reel.yml mode=narration；本地精简 worktree 先 "
                        f"`python3 tools/probe_sources.py materialize specs/reels/{slug}.json`）\n    {body}")
            continue
        if kind == "sure":
            where = ("（旁白按上包络也说不到这儿：离线估 "
                     f"{estimates.get(k, 0.0):.1f}s ×{1 + HARD_EST_SLOPE:.2f} ＋ {est_err}s）")
        else:
            where = (f"（按真语音，旁白说到段内 {measured.get(k, 0.0):.2f}s）"
                     if measured and k in measured else "（按上包络，这一段没合出真语音）")
        line = (f"{head}{where}：现场声按成片口径掉到 −60 dB 以下，渲后数字静音闸"
                f"**必红**{phase(kind)}\n    {body}")
        cure = ("把旁白写长盖住、或把窗口收在这一截之前；看过确认要这么剪就在这一段写 "
                f"`\"{CLAIM_KEY}\": \"<为什么>\"` 认领")
        if claim:
            soft.append(f"{line}\n    已认领 {CLAIM_KEY}：{claim}")
        elif strict and decided:
            hard.append(f"{line}\n    {cure}（手写 spec 硬闸，2026-09-28：渲后这一类红了 16 趟、"
                        "渲前 0 趟拦住）")
        else:
            soft.append(f"{line}\n    {cure}" + ("" if strict else "（自动产的 spec 只报）"))
    return hard, soft
