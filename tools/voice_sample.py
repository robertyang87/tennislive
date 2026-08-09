"""Read one paragraph in several voices so a human can pick by ear.

Speed is measurable — characters per second settles the "too slow" half of
the question on its own. Warmth is not. Nobody can tell from a parameter
whether a read sounds mechanical, and the sandbox cannot reach the TTS
service, so the only honest way to choose is to listen to the same sentences
in each candidate and decide.

Runs on Actions, writes the clips into the repo (they are tens of kilobytes)
so they can be pulled out and sent to whoever is choosing, and prints the
duration of each so the speed comparison is on the record next to the audio.

Usage: python tools/voice_sample.py [outdir]
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

# A beat with a quote and a number in it — the two things a flat read ruins.
SAMPLE = (
    "两天后，同一块场地，德约科维奇对阿利亚西姆的四分之一决赛。第三盘开始前，"
    "赛事主管走到场边通知他：屋顶要关了。当时是晚上七点四十。德约当场把话顶了回去——"
    "「我们完全可以在户外再打一整盘。我们是户外赛事。」"
)

# Microsoft's own personality tags for the zh-CN voices, which is the only
# published signal about how each one reads before you hear it.
CANDIDATES = [
    # ⚠️ 档位标签以 explainer.py 的 DEFAULT_RATE 为准（2026-08-09 对过一次：
    # 这里曾把 +28% 标成「现用」，而解说片早定在 +22%——过期标签害人猜错现状）
    # 剪辑片（match-reel）的现用档是 +6%——账号所有者 2026-08-09 问「剪辑片里
    # 6% 可以么」，加 +6/+10 两档进采样表让耳朵裁决；真要换档，段长排布和
    # speech_seconds 的回归系数都按 +6% 标定，要跟着重量
    ("zh-CN-YunjianNeural", "+6%", "云健 · 剪辑片现用档"),
    ("zh-CN-YunjianNeural", "+10%", "云健 · 剪辑片提速候选"),
    ("zh-CN-YunjianNeural", "+14%", "云健 · Passion（体育解说向）"),
    ("zh-CN-YunjianNeural", "+22%", "云健 · 解说片现用档"),
    ("zh-CN-YunjianNeural", "+28%", "云健 · 上一档（已退役）"),
    ("zh-CN-YunjianNeural", "+35%", "云健 · 再快一档（对照上限）"),
    ("zh-CN-YunxiNeural", "+14%", "云希 · Lively/Sunshine（现用嗓，提速）"),
    ("zh-CN-XiaoxiaoNeural", "+14%", "晓晓 · Warm（女声）"),
    ("zh-CN-YunyangNeural", "+14%", "云扬 · Professional（播报向）"),
]


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001 - duration is a nicety, not the point
        return 0.0


async def main() -> int:
    import edge_tts

    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "output/voice-samples")
    outdir.mkdir(parents=True, exist_ok=True)
    chars = len(SAMPLE)
    print(f"样句 {chars} 字\n")
    for index, (voice, rate, label) in enumerate(CANDIDATES):
        name = f"{index:02d}_{voice.split('-')[-1].replace('Neural','')}_{rate.strip('+%')}.mp3"
        path = outdir / name
        await edge_tts.Communicate(SAMPLE, voice, rate=rate).save(str(path))
        secs = _seconds(path)
        speed = f"{chars / secs:.1f} 字/秒" if secs else "时长未知"
        print(f"  {name:34} {secs:5.1f}s  {speed:10}  {label}")
    print(f"\n写入 {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
