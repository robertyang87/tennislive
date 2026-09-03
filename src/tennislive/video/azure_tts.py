"""Azure Speech 那条合成路：情绪风格 + 真停顿 + 词边界。

**为什么要有它。** 2026-08-04 在 runner 上把两条路都探了一遍，同一把嗓子
（`zh-CN-YunjianNeural`）、同一段话：

| | Edge 免费端点（`tools/probe_tts_ssml.py`，run 30884267406） | Azure F0（`tools/probe_azure_tts.py`，run 30892017944）|
|---|---|---|
| 词边界 | 有 | **18 条，有** |
| `<break time='1500ms'/>` ×2 | **服务端拒绝** | **生效**：9.07s，比基线多 2.95s ≈ 要的 3s |
| `mstts:express-as` | **四个风格全拒** | **10/10 全通过** |

## 多音字：能修，不能查（run 30893706623）

2026-08-04 账号所有者问「切分词和短句，以及多音字等等，F0 能解决么？」。
不能——F0 只量音高。切词和停顿的判据一直在手上（`words.json`），
**多音字差的是「它实际要读的音」**，而词边界只给字符串：「一发」读 fā 还是
fà，在 `text` 字段里长得一模一样。`tools/probe_azure_phoneme.py` 探了两头：

| | 结果 | |
|---|---|---|
| **查**：`viseme_received` | ❌ **50 条事件，`animation` 全空** | 只有 22 档口型 id，而 fā / fà **嘴形一样**，分不出来 |
| **修**：`<phoneme alphabet='sapi' ph='fa 1'>` | ✅ **生效** | 同一句话只换声调，输出 1.80s / 1.87s——**被静默忽略的话两次应该完全一样** |

所以多音字仍然要**靠耳朵发现**，但发现之后 Azure 上能一劳永逸地钉死；
edge-tts 那条路上唯一的出路是改写句子。⚠️ 「服务端认了这个标签」证明不了
「读出来是对的那个音」，钉完仍然要听一遍。

也就是说「多渲染情绪」这件事，在 edge-tts 上只剩语速音高两个旋钮，在 Azure 上
多了十个风格和真停顿。而我们的量（21 条已发片子合计 8352 字，平均 398 字/条）
**整个跑在 F0 的 50 万字符/月免费额度里**。

## 三条设计上的硬约束

1. **词边界的单位要和 edge-tts 对齐。** 字幕整条线读的是 `{offset, duration,
   text}`，edge-tts 给的是 **100 纳秒**为单位的整数；Azure SDK 的
   `audio_offset` 同样是 100ns 的 tick，但 `duration` 在新版 SDK 里是
   `timedelta`。不换算的话字幕会整体错位——**而且不报错**。
2. **标点边界要剔掉。** edge-tts 的 WordBoundary 不含标点（CLAUDE.md 记过：
   122 个字的旁白只有 109 条事件），字幕那边是按「在原文里 find」对齐的。
   Azure 会另发 `Punctuation` 类型的事件，混进去会让两条路的产物形状不一样。
3. **没配 key 就干脆说没配**，不猜、不半路降级。调用方自己决定是退回 edge-tts
   还是报错——`voice.style` 那种「spec 明确要了情绪风格」的情形必须报错，
   悄悄退回去就是发一条和 spec 说的不一样的片子。
"""
from __future__ import annotations

import html
import logging
import os
import time
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# `zh-CN-YunjianNeural` 实测通过的十个风格（run 30892017944 逐个问过）。
# ⚠️ **这张表是「服务端认」的表，不是「听起来对」的表**：其中五个的时长和基线
# 几乎一样（narration-relaxed / serious / angry / disgruntled / cheerful），
# 用之前要渲出来听。
KNOWN_STYLES = (
    "sports-commentary", "sports-commentary-excited", "narration-relaxed",
    "documentary-narration", "sad", "depressed", "serious", "angry",
    "disgruntled", "cheerful",
)

# 栏目的**基调**。账号所有者 2026-08-04 问「以后所有配音都能自适应情绪么？」，
# 答案分三层：每段都能带风格（额度够——已发 21 条合计 8352 字，F0 免费额度
# 50 万字符/月）；**按文本自动判情绪不做**（判错了不吭声，而且它会把「机器猜的」
# 伪装成「你想清楚了」，和 `mixed_fps` / `silent_source` / `rank: null` 是同一族）；
# **按栏目定基调可以做，因为栏目是已知的，情绪不是**。
#
# 它顺带修掉一个真问题：王欣瑜那条 11 段里只有 3 段带风格，落差全堆在交界处。
# 有了基调就是「基调 ＋ 三个重音」，而不是「三个人轮流念」。
#
# ⚠️ **这两个是十个里时长真的变了的那一档。** 另外五个
# （narration-relaxed / serious / angry / disgruntled / cheerful）实测时长和
# 基线几乎一样——「服务端认」不等于「听起来对」，别把它们设成基调。
# ⚠️ **表里没有的栏目不给基调，而且要出声**：「没配基调」和「配了但没生效」
# 长得一模一样，这个仓库为这种沉默栽过很多次。
# 栏目的**基调**。⚠️ **这张表里的空串是「实测之后决定不设」，不是「没人顾上」**
# ——认领这一步把「想清楚了」和「凑合一下」分开，和 `mixed_fps` / `silent_source`
# / `rank: null` 一个形状。
#
# ## 赛场之上：三趟实测之后决定**不设**
#
# 拿王欣瑜那条量的（同一条 spec，只换基调，段级三段每次都一字不差地复现
# 219.2 / 104.6 / 89.4 Hz——**这本身就是「段级永远赢」的实据**）：
#
# | 基调 | 不带风格 8 段 | 语速 | 6→7 接缝 | 8→9 接缝 | run |
# |---|---|---|---|---|---|
# | **无** | **115–128 Hz** | 3.81–5.36 | 91 Hz | **~10 Hz** | 30901860950 |
# | sports-commentary 0.5 | 160–182 | 3.95–5.72 | ~37 | ~76 | 30908840916 |
# | sports-commentary 1.0 | 184–188 | 4.07–5.77 | ~31 | ~79 | 30908370179 |
# | documentary-narration 0.5 | 94–109 | 3.66–4.83 | ~110 | **~0** | 30909219864 |
#
# **接缝消不掉，只能换位置。** 事后看是个几何事实：这条片子的两个重音在**相反
# 方向**（excited 219 在上，sad / depressed 89–105 在下），单个基调只能靠近一边。
# 而**不设基调时的 115–128 本来就落在两者中间**——自然音色就是最优解。
#
# 顺带两条：`sports-commentary` 两档都把第 4 段推到 5.7 字/秒，超过存量最快的
# 5.24；`documentary-narration` 把基调压到比 sad 还低，**直接把那个重音抹掉了**。
#
# ⚠️ 这条结论**只对「双向情绪弧」成立**。全片一个方向的片子（比如通篇肃穆）
# 仍然可能受益，那时再测。
#
# ## 网球有故事：本来要上 `documentary-narration`，**跟着一起撤了**
#
# 那个栏目讲一个人的来路、没有段级重音，所以没有上面那个接缝问题，风格名和用途
# 也对得上——纸面上完全说得通，我一度把它留在表里「等听」。
#
# ⚠️ **2026-08-04 账号所有者听完王欣瑜那条之后撤掉了**：「配音真的是太粗细了，
# **还是不要改成那种情绪化的，还用原来的那种配音**。但是就是断句和气口要分开
# 就行。」那句话否的是**这个机制**，不是那三个具体的风格名——所以一条**没人
# 听过**的基调不该在这时候留在表里等着被套上去。
#
# **两个栏目现在都是「实测/听过之后决定不设」，不是「还没顾上」。** 情绪走
# 另外两条不改音色的路：**断句**（标点，唯一的停顿杠杆，见 CLAUDE.md）和
# **气口**（`lead_pause`，真 `<break>`）。
#
# 机制本身全留着（`base_style_for` / `styledegree` / 韵律报告）——上面那张四行
# 实测表是它唯一的用处：**证明了段级永远赢，也证明了基调消不掉接缝只能换位置**。
# 以后真要给某个栏目上基调，先渲一条让人听，`_heard` 那道闸是同一个道理。
COLUMN_BASE_STYLE = {
    "赛场之上": ("", ""),    # 三趟实测之后决定不设，见上表
    "网球有故事": ("", ""),  # 账号所有者 8/4 撤掉，见上
}


def base_style_for(column: str) -> tuple[str, str]:
    """这个栏目的基调 `(风格, styledegree)`。

    ⚠️ **两种空要分开**，调用方靠 `is_registered()` 区分：登记了空串＝实测之后
    决定不设；根本没登记＝还没想过。日志里必须说清是哪一种——
    「没配基调」和「配了但没生效」长得一模一样，这个仓库为这种沉默栽过很多次。
    """
    return COLUMN_BASE_STYLE.get((column or "").strip(), ("", ""))


def is_registered(column: str) -> bool:
    """这个栏目在基调表里出现过没有（哪怕值是「不设」）。"""
    return (column or "").strip() in COLUMN_BASE_STYLE


_ENV_KEY = "AZURE_SPEECH_KEY"
_ENV_REGION = "AZURE_SPEECH_REGION"


class AzureTTSError(RuntimeError):
    """Azure 这条路自己的错，和 edge-tts 那条分开——好让调用方决定退不退。"""


def credentials() -> tuple[str, str]:
    """`(key, region)`，任一为空就返回两个空串。**不抛异常**，让调用方判断。"""
    key = os.environ.get(_ENV_KEY, "").strip()
    region = os.environ.get(_ENV_REGION, "").strip()
    return (key, region) if key and region else ("", "")


#: 显式关掉 Azure、退回 edge-tts 的开关（值写 `edge`）。2026-09-03 仓库的
#: `AZURE_SPEECH_KEY` 突然 401（同一把钥匙 15:31Z 还渲成过一条），而
#: `match-reel.yml` 的 dispatch 表单已经 25 项满了、加不了输入——账号所有者定
#: 「换 edge tts」，于是开关走环境变量，spec 用 `tts_backend: "edge"` 认领
#: （`build_match_reel.apply_tts_backend` 把它落成这个变量）。
_ENV_BACKEND = "TENNISLIVE_TTS_BACKEND"


def forced_off() -> bool:
    """环境里显式写了 `TENNISLIVE_TTS_BACKEND=edge` 就不走 Azure，哪怕钥匙在。"""
    return os.environ.get(_ENV_BACKEND, "").strip().lower() == "edge"


def available() -> bool:
    """key/region 都在，而且 SDK 装得上，而且没被显式关掉。

    ⚠️ **两样都要查。** 只查环境变量的话，在没装 SDK 的机器上会一路走到
    `import` 才炸，而那时可能已经下完几百 MB 源片了（这个仓库栽过三次：
    playwright、Chromium、cv2 都是「本地装着不等于 CI 装着」）。
    """
    if forced_off():
        return False
    if not all(credentials()):
        return False
    try:
        import azure.cognitiveservices.speech  # noqa: F401,PLC0415
    except ImportError:
        return False
    return True


def why_unavailable() -> str:
    """说清楚差哪一样——「没配」「没装」「被关掉」是三条完全不同的出路。"""
    if forced_off():
        return (f"{_ENV_BACKEND}=edge 显式关掉了 Azure（spec 的 `tts_backend` "
                f"或环境变量），这一趟走 edge-tts")
    key, region = credentials()
    if not key or not region:
        missing = [n for n, v in ((_ENV_KEY, key), (_ENV_REGION, region)) if not v]
        return (f"没有 {' / '.join(missing)}——在仓库的 Settings → Secrets and "
                f"variables → **Actions** 里加（加到 Codespaces 那一栏工作流读不到，"
                f"而且不报错）")
    try:
        import azure.cognitiveservices.speech  # noqa: F401,PLC0415
    except ImportError as exc:
        return f"没装 azure-cognitiveservices-speech（{exc}）"
    return ""


def build_ssml(text: str, *, voice: str, rate: str, pitch: str,
               style: str = "", styledegree: str = "",
               lead_pause: float = 0.0) -> str:
    """拼 SSML。**文本一定要转义**——旁白里出现 `&` 就会让整段 XML 解析失败。"""
    body = f"<prosody rate='{rate}' pitch='{pitch}'>{html.escape(text)}</prosody>"
    if style:
        degree = f" styledegree='{styledegree}'" if styledegree else ""
        body = f"<mstts:express-as style='{style}'{degree}>{body}</mstts:express-as>"
    if lead_pause > 0:
        body = f"<break time='{int(round(lead_pause * 1000))}ms'/>" + body
    return (
        "<speak version='1.0' xmlns='https://www.w3.org/2001/10/synthesis'"
        " xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
        f"<voice name='{voice}'>{body}</voice></speak>"
    )


def _ticks(value: object) -> int:
    """把 Azure 的时长换算成 **100 纳秒**——edge-tts 那条路用的就是这个单位。

    新版 SDK 的 `duration` 是 `timedelta`，老版给的是毫秒整数。两种都认，
    认不出来就记 0（字幕那边只用 offset 排序，duration 缺了不致命）。
    """
    total = getattr(value, "total_seconds", None)
    if callable(total):
        return int(round(total() * 10_000_000))
    if isinstance(value, (int, float)):
        return int(round(float(value) * 10_000))      # 毫秒 → 100ns
    return 0


# **被挡回来 ≠ 被拒绝，两者的处置相反。**（和 `publish/pushplus.py` 那条
# 「只重试『没送到』」是同一条规矩，只是那儿是 HTTP、这儿是 WebSocket。）
#
# `WebSocket upgrade failed: Too many requests (429)` 是**握手就没握上**——
# 一个字节的音频都没合成，重发是安全的，而且是唯一的出路。而 `401`/`403`
# （密钥错、区域写错）和「这个 voice 不存在」是 Azure **明确拒绝**：
# 重发只会把同一个错误重复四遍，把一次 5 秒的失败拖成 70 秒。
_RETRYABLE = ("429", "too many requests", "throttl", "timeout", "timed out",
              "connection", "reset", "unavailable", "503", "500")
_FATAL = ("401", "403", "forbidden", "unauthorized", "invalid subscription")

# 退避阶梯。**4 次尝试、最长等 65 秒**：Azure 免费档（F0）的神经语音是
# 「20 次请求 / 60 秒」，一条片子有三四十段，`synthesize()` 那个循环是**贴着
# 发的**——所以典型的失败形状是「前二十段顺利、第二十一段开始一路 429」。
# 最后一档 45 秒足够跨过那个 60 秒的窗口。
_BACKOFF = (5.0, 15.0, 45.0)

# ⚠️ **撞过一次限流之后要给后面的调用留间隔**，否则退避完立刻又是一次爆发，
# 下一段照样 429——退避只救得了这一段，救不了这一趟。这个值**只在真被限流
# 之后才从 0 长起来**：配额没问题的时候一秒都不多花，是自适应不是固定节流。
_paced_gap = 0.0
_last_call = 0.0


def _classify(detail: str) -> str:
    """这次失败是「没送到」还是「被拒绝」。判据是错误文本本身，不是猜。"""
    low = detail.lower()
    if any(k in low for k in _FATAL):
        return "fatal"
    if any(k in low for k in _RETRYABLE):
        return "retry"
    return "unknown"


def synthesize(text: str, path: Path, *, voice: str, rate: str, pitch: str,
               style: str = "", styledegree: str = "",
               lead_pause: float = 0.0) -> list[dict]:
    """合一条语音落到 `path`，返回**和 edge-tts 同形状**的词边界。

    被限流（429）时按 `_BACKOFF` 重试，并把「第几次、等多久、为什么」打进日志
    ——**退路要出声**，不然「今天 Azure 慢」和「这条被限流重试了三次」
    在日志上一模一样。

    Returns:
        `[{"offset": <100ns>, "duration": <100ns>, "text": str}, …]`
    """
    global _paced_gap, _last_call
    import azure.cognitiveservices.speech as speechsdk  # noqa: PLC0415

    key, region = credentials()
    if not key:
        raise AzureTTSError(why_unavailable())

    cfg = speechsdk.SpeechConfig(subscription=key, region=region)
    # **要 mp3，和 edge-tts 那条路同一种封装**，下游 ffmpeg 行为一个字不用改。
    cfg.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3)

    path.parent.mkdir(parents=True, exist_ok=True)
    marks: list[dict] = []
    punctuation = getattr(speechsdk, "SpeechSynthesisBoundaryType", None)
    punct_type = getattr(punctuation, "Punctuation", None) if punctuation else None

    def on_word(evt) -> None:                                  # noqa: ANN001
        # **标点边界剔掉**：edge-tts 的 WordBoundary 不含标点，字幕那边是按
        # 「在原文里 find」对齐的，两条路的产物形状必须一样。
        if punct_type is not None and getattr(evt, "boundary_type", None) == punct_type:
            return
        word = str(getattr(evt, "text", "") or "")
        if not word.strip():
            return
        marks.append({"offset": int(getattr(evt, "audio_offset", 0) or 0),
                      "duration": _ticks(getattr(evt, "duration", 0)),
                      "text": word})

    ssml = build_ssml(text, voice=voice, rate=rate, pitch=pitch, style=style,
                      styledegree=styledegree, lead_pause=lead_pause)

    for attempt in range(len(_BACKOFF) + 1):
        # 上一趟撞过限流的话，这里补足间隔再发。没撞过 `_paced_gap` 是 0，
        # 这一句等于不存在。
        if _paced_gap:
            wait = _paced_gap - (time.monotonic() - _last_call)
            if wait > 0:
                time.sleep(wait)
        marks.clear()
        out = speechsdk.audio.AudioOutputConfig(filename=str(path))
        syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
        syn.synthesis_word_boundary.connect(on_word)
        result = syn.speak_ssml_async(ssml).get()
        _last_call = time.monotonic()

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            break

        detail = ""
        if result.reason == speechsdk.ResultReason.Canceled:
            cancel = result.cancellation_details
            detail = f"{cancel.reason}: {cancel.error_details}"
        kind = _classify(detail)
        if kind == "fatal" or attempt == len(_BACKOFF):
            # 用尽了也要说清是**哪一类**：限流用尽和密钥写错，下一步完全不同。
            why = {"fatal": "Azure 明确拒绝（密钥／区域／权限），重试没有意义",
                   "retry": f"重试 {attempt} 次仍被挡回来",
                   "unknown": "这个错误不在已知的可重试清单里"}[kind]
            raise AzureTTSError(
                f"Azure 合成失败（{result.reason}）{detail}｜{why}")
        pause = _BACKOFF[attempt]
        # 撞上就把后续调用的最小间隔顶到 3 秒（F0 是 20 次/60 秒 ＝ 平均 3 秒
        # 一次）。**只涨不降**：这一趟里再撞第二次说明 3 秒还不够。
        _paced_gap = max(_paced_gap, 3.0) if kind == "retry" else _paced_gap
        logger.warning("Azure 合成被挡回来（%s），%.0fs 后重试第 %d/%d 次；"
                       "此后每次调用之间至少隔 %.0fs。原文：%s",
                       detail or result.reason, pause, attempt + 1,
                       len(_BACKOFF), _paced_gap, text[:18])
        time.sleep(pause)

    if not path.is_file() or path.stat().st_size == 0:
        raise AzureTTSError(f"Azure 说合成成功，但 {path} 是空的")
    return marks


def check_styles(styles: Sequence[str]) -> list[str]:
    """挑出不在实测通过表里的风格名。

    ⚠️ **拼错的风格名 Azure 是静默忽略的**——合成照样成功，只是没有情绪，
    而「拼错了」和「这个风格听起来就是平的」在成片上一模一样。所以在
    **写 spec 的那一刻**就拦下来，不等到听成片。
    """
    return [s for s in styles if s and s not in KNOWN_STYLES]
