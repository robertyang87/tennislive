#!/usr/bin/env python3
"""探 Azure Speech 给不给**音素级**的东西——多音字唯一能自动查的那条路。

## 为什么要探这个

2026-08-04 账号所有者问：「切分词和短句，以及多音字等等，F0 能解决么？」

不能。三样东西三个判据，而前两样我们已经有了：

| | 判据 | 有没有 |
|---|---|---|
| 切分词 | `words.json` 的 `text` —— 合成器自己报的切词 | ✅ |
| 短句停顿 | 相邻词边界之间的空档 | ✅ |
| **多音字** | **需要它实际要读的音** | ❌ |

词边界只给**字符串**。「一发」读 fā 还是 fà、「书写」读 shū xiě 还是 shūxiě、
「了」读 le 还是 liǎo——`text` 字段里全是同一个汉字，**读对读错长得一模一样**。
这正是这个仓库反复记的那类毛病：不吭声。

Azure 上有两个 edge-tts 完全没有的东西，一个管查一个管修：

- **`viseme_received` 事件**：口型 id + `animation`（JSON）。如果那份 JSON 里带
  音素/拼音，多音字就从「只能听」变成「能量」
- **`<phoneme alphabet=… ph=…>`**：直接把读音钉死。查出来读错了才有得修——
  **只有查没有修，等于知道它坏了但没办法**

## 三条纪律（和另外两个探测脚本一样）

1. **基线一起探。** 基线不通，下面任何结论都不作数（沙箱那次七项全 403，
   看着像「SSML 全被拒」，其实是那台机器出不去）
2. **判据是产物，不是返回码。** `<phoneme>` 拼错了 Azure 是**静默忽略**的——
   合成照样成功，只是没按你说的读。所以要拿**两个不同读音**渲出来比时长/音频，
   一样就说明它根本没生效
3. **空事件要自证是真空。** viseme 一条都没有，可能是服务端不发，也可能是
   要显式打开（`cfg.set_property` / 输出格式）。两种都试过再下结论

用法（在 GitHub Actions 上跑，要 `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`）：

    python3 tools/probe_azure_phoneme.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

VOICE = "zh-CN-YunjianNeural"

SPEAK = (
    "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'"
    " xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
    "<voice name='{voice}'>{inner}</voice></speak>"
)

# 拿真旁白里出问题的那几个词。**别用「你好」试**——多音字的风险点全在术语上。
#
# 「一发」的「发」：fā（发球）/ fà（头发）。切词报告里它在第 4 段被切成
# `二 ｜ 发`，孤立之后读错的风险最大。
POLY = "一发只赢一半，二发只赢三分之一。"


def main() -> int:
    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        print("[探音素] 没有 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION，这台机器上探不了。")
        return 1
    print(f"[探音素] 区域 {region}，音色 {VOICE}")

    import azure.cognitiveservices.speech as speechsdk

    def synth(label: str, ssml: str, *, want_viseme: bool = False):
        """返回 (秒数, 词边界数, viseme 列表)。失败返回 (None, 0, [])。"""
        cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        cfg.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3)
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        words: list[str] = []
        visemes: list[dict] = []
        try:
            out = speechsdk.audio.AudioOutputConfig(filename=path)
            syn = speechsdk.SpeechSynthesizer(speech_config=cfg, audio_config=out)
            syn.synthesis_word_boundary.connect(lambda e: words.append(e.text))
            if want_viseme:
                syn.viseme_received.connect(lambda e: visemes.append({
                    "offset": getattr(e, "audio_offset", 0),
                    "id": getattr(e, "viseme_id", None),
                    "animation": str(getattr(e, "animation", "") or ""),
                }))
            res = syn.speak_ssml_async(ssml).get()
            if res.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                detail = ""
                if res.reason == speechsdk.ResultReason.Canceled:
                    c = res.cancellation_details
                    detail = f"{c.reason}: {str(c.error_details)[:140]}"
                print(f"  {label:<38} 拒绝  {detail}")
                return None, 0, []
            secs = len(res.audio_data) / (48_000 / 8)      # 48 kbps CBR
            print(f"  {label:<38} {secs:6.2f}s  词边界 {len(words):3d}  "
                  f"viseme {len(visemes):4d}")
            return secs, len(words), visemes
        finally:
            os.unlink(path)

    print("\n① 基线（只有 prosody）")
    base, base_words, _ = synth("baseline", SPEAK.format(
        voice=VOICE, inner=f"<prosody rate='+6%'>{POLY}</prosody>"))
    if base is None:
        print("\n[探音素] **基线就没合成出来**，下面任何结论都不作数。")
        return 1

    print("\n② viseme 事件里有没有音素")
    _, _, vis = synth("baseline + viseme", SPEAK.format(
        voice=VOICE, inner=f"<prosody rate='+6%'>{POLY}</prosody>"),
        want_viseme=True)
    animated = [v for v in vis if v["animation"].strip()]
    print(f"     其中带 animation 的 {len(animated)} 条")
    if animated:
        # **原样打出来**——字段名靠猜是这个仓库栽过的坑，让接口自己报
        print(f"     第一条 animation（前 300 字）：{animated[0]['animation'][:300]}")
        try:
            blob = json.loads(animated[0]["animation"])
            print(f"     解出来的顶层键：{sorted(blob)[:12]}")
        except (ValueError, TypeError):
            print("     ⚠️ animation 不是 JSON，得按字符串处理")
    elif vis:
        print("     ⚠️ 有 viseme 但 animation 全空 —— 只有口型 id，**没有音素**。"
              "\n        口型 id 是 22 档嘴形，中文多音字（fā/fà）嘴形一样，"
              "分不出来。这条路到此为止。")
    else:
        print("     ⚠️ **一条 viseme 都没有。** 空不等于不存在——"
              "先确认是不是要显式打开，别急着下结论。")

    print("\n③ <phoneme> 能不能把读音钉死")
    # 判据不是「它接受了」，是**两个不同读音渲出来不一样**。
    # 拼错的 ph 值 Azure 静默忽略，那和「生效了」返回码一模一样。
    fa1, _, _ = synth("phoneme fa1（发球，对）", SPEAK.format(
        voice=VOICE,
        inner=("<prosody rate='+6%'>一"
               "<phoneme alphabet='sapi' ph='fa 1'>发</phoneme>"
               "只赢一半。</prosody>")))
    fa4, _, _ = synth("phoneme fa4（头发，故意读错）", SPEAK.format(
        voice=VOICE,
        inner=("<prosody rate='+6%'>一"
               "<phoneme alphabet='sapi' ph='fa 4'>发</phoneme>"
               "只赢一半。</prosody>")))

    print("\n" + "=" * 66)
    print(f"基线 {base:.2f}s，词边界 {base_words} 条")
    if not vis:
        print("② viseme：**一条都没有**")
    elif animated:
        print(f"② viseme：**{len(animated)} 条带 animation** → 上面那段 JSON 里"
              "如果有音素/拼音，多音字就能自动查")
    else:
        print(f"② viseme：{len(vis)} 条，**animation 全空**（只有口型 id，"
              "分不出 fā/fà）→ 多音字自动查这条路**不通**")
    if fa1 is None and fa4 is None:
        print("③ phoneme：**服务端拒绝** → 读音钉不死，只能靠改写句子")
    elif fa1 is None or fa4 is None:
        print("③ phoneme：**一个通一个不通** → 有语法要求，读一眼上面的拒绝原因")
    elif abs(fa1 - fa4) < 0.02:
        print(f"③ phoneme：⚠️ **两个声调渲出来一样长**（{fa1:.2f}s / {fa4:.2f}s）"
              "——多半是被静默忽略了。**不能据此说它生效**，"
              "\n     下一步：把这两个 mp3 落下来听，或者换成长度差别更大的两个音")
    else:
        print(f"③ phoneme：**生效**（{fa1:.2f}s vs {fa4:.2f}s，差 "
              f"{abs(fa1 - fa4):.2f}s）→ 多音字读错了有救")
    print("\n⚠️ 这三项都只证明「服务端认」，证明不了「听起来对」。"
          "真要用之前仍然要渲出来听一遍。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
