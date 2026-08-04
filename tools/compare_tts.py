#!/usr/bin/env python3
"""同一段旁白，edge-tts 和 Azure 各渲一份，摆在一起听。

**为什么必须是这个形状。** `tools/probe_azure_tts.py` 已经证明 Azure F0
十个风格全部被服务端接受了——但**那只证明「服务端认了这个标签」**。十个里有
五个的时长和基线几乎一样（narration-relaxed / serious / angry / disgruntled /
cheerful），也就是说光看数字分不出「情绪生效了」和「标签被吃了」。

CLAUDE.md 里那条「速度是能量的，温暖不能」说的就是这件事：**没人能听见一个参数**。
所以这个脚本不下结论，只把两版音频摆在仓库里，让人自己听。

用的是**真旁白**——王欣瑜那条片子里落差最大的三句：

| | 这一句在讲什么 | 想要的语气 |
|---|---|---|
| 冲 | 「她离胜利只剩两局」 | 顶到最上面 |
| 崩 | 「一局就能赢，那一局，一分没拿到」 | 往下掉 |
| 落 | 「抢七输掉了。」 | 全片最慢最低 |

⚠️ **不要拿「你好，欢迎收看」这种句子试**：短句的固定开销占比大、又没有情绪
落点，两版听起来都一样，什么也证明不了。

用法（在 GitHub Actions 上跑，要 `AZURE_SPEECH_KEY` / `AZURE_SPEECH_REGION`）：

    python3 tools/compare_tts.py output/voice-samples
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.video import azure_tts  # noqa: E402

VOICE = "zh-CN-YunjianNeural"

# (标签, 旁白, edge 那版的语速/音高, Azure 那版的风格)
# ⚠️ **edge 那一列就是现在成片里真在用的值**（`specs/reels/wang-kasatkina.json`
# 第 7 / 9 / 10 段），不是另拟的——不然比的是两套文案，不是两条 TTS。
CASES = (
    ("1-冲", "第二盘她一点没停。前五局又破了三次，四比一——她离胜利只剩两局。",
     "+14%", "+3Hz", "sports-commentary-excited"),
    ("2-崩", "然后她连丢四局。追回到六比五，一局就能赢——那一局，一分没拿到。",
     "-3%", "-4Hz", "sad"),
    ("3-落", "抢七输掉了。", "-10%", "-6Hz", "depressed"),
)


def seconds(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "output/voice-samples")
    outdir.mkdir(parents=True, exist_ok=True)

    import edge_tts

    async def edge(text: str, path: Path, rate: str, pitch: str) -> None:
        with path.open("wb") as fh:
            stream = edge_tts.Communicate(text, VOICE, rate=rate,
                                          pitch=pitch).stream()
            async for chunk in stream:
                if chunk.get("type") == "audio" and chunk.get("data"):
                    fh.write(chunk["data"])

    if not azure_tts.available():
        print(f"[对比] Azure 不可用：{azure_tts.why_unavailable()}")
        print("      只渲 edge 那一半没有意义——**对比的前提是两边都在**。")
        return 1

    print(f"[对比] 音色 {VOICE}，{len(CASES)} 组，每组两版\n")
    for label, text, rate, pitch, style in CASES:
        a = outdir / f"比较_{label}_edge.mp3"
        b = outdir / f"比较_{label}_azure_{style}.mp3"
        asyncio.run(edge(text, a, rate, pitch))
        # **Azure 那版不再拧语速音高**：风格自己带节奏，再叠一层就分不清
        # 听到的差别是风格给的还是 prosody 给的。这是这次对比要回答的问题。
        marks = azure_tts.synthesize(text, b, voice=VOICE, rate="+6%",
                                     pitch="+0Hz", style=style)
        print(f"  {label}  {text[:22]}…")
        print(f"     edge  {rate:>5s}/{pitch:<5s}  {seconds(a):5.2f}s")
        print(f"     azure {style:<26s}  {seconds(b):5.2f}s  "
              f"词边界 {len(marks)} 条")
    print("\n两版都在 " + str(outdir) + "，**打开听**——时长表证明不了情绪。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
