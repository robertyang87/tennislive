#!/usr/bin/env python3
"""探一遍 Azure Speech 的 **F0 免费层**到底给不给情绪风格和 `<break>`。

**为什么不能照文档写。** 微软的文档说 `zh-CN-YunjianNeural` 支持
`sports-commentary` / `sports-commentary-excited` / `sad` 这些风格——但那是
**语音的能力表**，不是**定价层的权限表**。F0 是不是把 `mstts:express-as`
关掉了，文档上没有一句话直说。而这个仓库的规矩是：**量出来，别猜**。

同一天早些时候在免费的 Edge 朗读端点上探过一次（`tools/probe_tts_ssml.py`，
run 30884267406）：`<break/>` 和四个 `express-as` 风格**全部被服务端拒绝**，
能用的只剩 `prosody rate/pitch`。这个脚本问的是同一组问题，换成 Azure。

## 三条和上一个探测同样的纪律

1. **基线一起探。** 上一次在沙箱里跑，七项全 403，看着像「SSML 全被拒」——
   其实**基线也 403**，是那台机器出不去。基线不通就什么结论都不能下。
2. **判据是合成出来的时长，不是返回码。** 服务端对不认识的标签可能静默忽略，
   「接受」和「忽略」返回码一模一样。
3. **词边界要一起验。** 字幕整条线建立在合成器返回的词边界上——Azure 给不给、
   给成什么单位，没验过就不能当它有。这一项比风格更要命：风格没有只是平淡，
   词边界没有是**整条片子没字幕**。

用法（在 GitHub Actions 上跑，要 `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`）：

    python3 tools/probe_azure_tts.py
"""
from __future__ import annotations

import os
import sys
import tempfile

VOICE = "zh-CN-YunjianNeural"
TEXT = "第三盘她又爬到五比三。三个破发点救下两个，第三个没救住。"

# `zh-CN-YunjianNeural` 在文档里挂着的十个风格，一个一个问。
STYLES = ("sports-commentary", "sports-commentary-excited", "narration-relaxed",
          "documentary-narration", "sad", "depressed", "serious", "angry",
          "disgruntled", "cheerful")

SPEAK = (
    "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'"
    " xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
    "<voice name='{voice}'>{inner}</voice></speak>"
)


def main() -> int:
    key = os.environ.get("AZURE_SPEECH_KEY", "").strip()
    region = os.environ.get("AZURE_SPEECH_REGION", "").strip()
    if not key or not region:
        print("[探 Azure] 没有 AZURE_SPEECH_KEY / AZURE_SPEECH_REGION，"
              "这台机器上探不了。")
        return 1
    print(f"[探 Azure] 区域 {region}，音色 {VOICE}")

    import azure.cognitiveservices.speech as speechsdk

    def synth(label: str, ssml: str) -> tuple[float | None, int]:
        """返回 (秒数, 词边界条数)。合成失败返回 (None, 0) 并打印原因。"""
        cfg = speechsdk.SpeechConfig(subscription=key, region=region)
        # **要 mp3**，和 edge-tts 那条路的产物同一种封装，下游 ffmpeg 行为不变。
        cfg.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz48KBitRateMonoMp3)
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        marks: list[dict] = []
        try:
            out = speechsdk.audio.AudioOutputConfig(filename=path)
            syn = speechsdk.SpeechSynthesizer(speech_config=cfg,
                                              audio_config=out)
            syn.synthesis_word_boundary.connect(
                lambda evt: marks.append({"text": evt.text}))
            res = syn.speak_ssml_async(ssml).get()
            if res.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
                detail = ""
                if res.reason == speechsdk.ResultReason.Canceled:
                    c = res.cancellation_details
                    detail = f"{c.reason}: {str(c.error_details)[:110]}"
                print(f"  {label:<34} 拒绝  {detail}")
                return None, 0
            secs = len(res.audio_data) / (48_000 / 8)   # 48 kbps CBR
            print(f"  {label:<34} {secs:6.2f}s  词边界 {len(marks):3d} 条")
            return secs, len(marks)
        finally:
            os.unlink(path)

    print("\n① 基线（只有 prosody，和现在 edge-tts 那条路等价）")
    base, base_marks = synth("baseline rate=+6%", SPEAK.format(
        voice=VOICE, inner=f"<prosody rate='+6%'>{TEXT}</prosody>"))
    if base is None:
        print("\n[探 Azure] **基线就没合成出来**——key/region/网络有问题，"
              "下面任何结论都不作数。")
        return 1
    if not base_marks:
        print("\n⚠️ **一条词边界都没拿到。** 字幕整条线靠它，这一项不通的话"
              "换过去等于所有片子的字幕退回「按字数等比分配」。先查这个再谈风格。")

    print("\n② <break time='1500ms'/> ×2 —— 真停顿（该多出 3 秒）")
    brk, _ = synth("break 1500ms ×2", SPEAK.format(
        voice=VOICE,
        inner=("<prosody rate='+6%'>第三盘她又爬到五比三。"
               "<break time='1500ms'/>三个破发点救下两个，"
               "<break time='1500ms'/>第三个没救住。</prosody>")))

    print(f"\n③ <mstts:express-as> —— {len(STYLES)} 个风格逐个问")
    got: dict[str, float] = {}
    for style in STYLES:
        secs, _ = synth(f"express-as {style}", SPEAK.format(
            voice=VOICE,
            inner=(f"<mstts:express-as style='{style}'>"
                   f"<prosody rate='+6%'>{TEXT}</prosody>"
                   "</mstts:express-as>")))
        if secs is not None:
            got[style] = secs

    print("\n" + "=" * 64)
    print(f"基线 {base:.2f}s，词边界 {base_marks} 条")
    if brk is None:
        print("② break：**服务端拒绝**")
    elif brk - base > 2.0:
        print(f"② break：**生效**（{brk:.2f}s，多出 {brk - base:.2f}s ≈ 要的 3s）"
              " → 停顿可以写进 SSML，不用再靠标点")
    else:
        print(f"② break：**被静默忽略**（{brk:.2f}s，只多 {brk - base:.2f}s）")
    if not got:
        print("③ 十个风格**一个都没通过** → F0 上没有情绪风格，"
              "换过去只换来 break 和词边界，情绪那一半白跑")
    else:
        print(f"③ 通过 {len(got)}/{len(STYLES)} 个：")
        for style, secs in got.items():
            same = "（时长和基线一样，**要打开听过才算数**）" \
                if abs(secs - base) < 0.15 else ""
            print(f"     {style:<28} {secs:6.2f}s {same}")
    print("\n⚠️ 时长只能证明「服务端认了这个标签」，证明不了「听起来真的是那个"
          "情绪」。下一步是拿同一段话渲两版**并排听**，不是看这张表。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
