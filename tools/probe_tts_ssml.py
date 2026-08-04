#!/usr/bin/env python3
"""探一遍 edge-tts 这条**免费**通道到底认哪些 SSML。

**为什么要有这个脚本。** 账号所有者 2026-08-04 问：「当前 tts 在断句和固定搭配的
连读和读音以及文本里显示出的情绪和情感等等，能否在 tts 中体现出来」。

这个问题只有两种答案会被写进 CLAUDE.md——「能，这么写」或者「不能，别再试」——
而两种都必须**量出来**，不能靠读文档：Azure Speech 的文档写着 `zh-CN-YunjianNeural`
支持 `sports-commentary` / `sad` 这些风格，可我们走的**不是 Azure**，是 Edge 朗读
那条免费端点，两者认的 SSML 子集不一样。

## 三个坑，都在这个脚本里挡掉了

1. **`edge_tts` 会把输入 XML 转义**（`escape(remove_incompatible_characters(text))`），
   所以把 `<break/>` 写进旁白只会被**当成字念出来**。要探真 SSML 必须替换
   `mkssml`，也就是这里干的事。
2. **判据是合成出来的时长，不是返回码。** 服务端对不认识的标签是**静默忽略**——
   「接受」和「忽略」返回码一模一样，只有时长会露馅。所以每一项都跟基线比秒数。
3. **基线必须一起探。** 沙箱里跑这个脚本时七项全 403，看着像「SSML 全被拒」，
   其实**基线也 403**——是这台机器的 WebSocket 出不去。基线不通就什么结论都
   不能下（「排除了 A 和 B 不等于就是 C」）。所以基线失败时直接退出并说清楚。

用法（在 GitHub Actions 上跑，沙箱连不上）：

    python3 tools/probe_tts_ssml.py
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile

VOICE = "zh-CN-YunjianNeural"
RATE = "+6%"
# 用真旁白，不用「你好世界」：短句的固定开销占比大，量不出 break 的效果
TEXT = "第三盘她又爬到五比三。三个破发点救下两个，第三个没救住。"

SPEAK = (
    "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'"
    " xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='zh-CN'>"
    "<voice name='{voice}'>{inner}</voice></speak>"
)


def _seconds(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main() -> int:
    import edge_tts
    import edge_tts.communicate as ec

    original_mkssml = ec.mkssml
    inject: dict[str, str | None] = {"body": None}

    def _patched(tc, escaped_text):
        return original_mkssml(tc, escaped_text) if inject["body"] is None \
            else inject["body"]

    ec.mkssml = _patched

    async def synth(label: str, body: str | None) -> float | None:
        inject["body"] = body
        fd, path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        try:
            chunks = 0
            with open(path, "wb") as fh:
                stream = edge_tts.Communicate(TEXT, VOICE, rate=RATE).stream()
                async for chunk in stream:
                    if chunk.get("type") == "audio" and chunk.get("data"):
                        fh.write(chunk["data"])
                        chunks += 1
            if not chunks:
                print(f"  {label:<36} 空音频")
                return None
            secs = _seconds(path)
            print(f"  {label:<36} {secs:6.2f}s")
            return secs
        except Exception as exc:                            # noqa: BLE001
            print(f"  {label:<36} 拒绝  {type(exc).__name__}: {str(exc)[:90]}")
            return None
        finally:
            inject["body"] = None
            os.unlink(path)

    async def run() -> int:
        print(f"[探 SSML] 音色 {VOICE}，语速 {RATE}")
        print("① 基线（库自己拼的 SSML，只有 prosody）")
        base = await synth("baseline", None)
        if base is None:
            print("\n[探 SSML] **基线就没合成出来**——这台机器连不上 TTS，"
                  "下面任何结论都不作数。先修连接再探。")
            return 1

        print("\n② <break/> —— 能不能插真停顿（各加 1.5 秒，共 3 秒）")
        brk = await synth("break 1500ms ×2", SPEAK.format(
            voice=VOICE,
            inner=(f"<prosody rate='{RATE}'>第三盘她又爬到五比三。"
                   "<break time='1500ms'/>三个破发点救下两个，"
                   "<break time='1500ms'/>第三个没救住。</prosody>")))

        print("\n③ <mstts:express-as> —— 情绪风格")
        styles: dict[str, float | None] = {}
        for style in ("sad", "sports-commentary-excited",
                      "narration-relaxed", "cheerful"):
            styles[style] = await synth(f"express-as {style}", SPEAK.format(
                voice=VOICE,
                inner=(f"<mstts:express-as style='{style}'>"
                       f"<prosody rate='{RATE}'>{TEXT}</prosody>"
                       "</mstts:express-as>")))

        print("\n④ prosody —— 已经在用的那个，看它的可调范围")
        pro: dict[str, float | None] = {}
        for rate, pitch in (("-20%", "-8Hz"), ("+6%", "+0Hz"), ("+25%", "+12Hz")):
            pro[f"{rate}/{pitch}"] = await synth(
                f"prosody rate={rate} pitch={pitch}", SPEAK.format(
                    voice=VOICE,
                    inner=f"<prosody rate='{rate}' pitch='{pitch}'>{TEXT}"
                          "</prosody>"))

        print("\n" + "=" * 62)
        print(f"基线 {base:.2f}s")
        if brk is None:
            print("② break：**服务端拒绝**——这条路走不通")
        elif brk - base > 2.0:
            print(f"② break：**生效**（{brk:.2f}s，多出 {brk - base:.2f}s ≈ 要的 3s）"
                  " → 停顿可以写进 SSML")
        else:
            print(f"② break：**被静默忽略**（{brk:.2f}s，只多 {brk - base:.2f}s）"
                  " → 停顿仍然只能靠标点")
        for style, secs in styles.items():
            if secs is None:
                print(f"③ {style}：**服务端拒绝**")
            elif abs(secs - base) < 0.15:
                print(f"③ {style}：**被静默忽略**（{secs:.2f}s，和基线一样）")
            else:
                print(f"③ {style}：时长变了（{secs:.2f}s vs 基线 {base:.2f}s）"
                      "——**要打开听过才算数**，时长变不等于风格对")
        for key, secs in pro.items():
            if secs is not None:
                print(f"④ prosody {key}：{secs:.2f}s")
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
