#!/usr/bin/env python3
"""Azure DragonHD 高自然度声线试音：现用基线 vs 三个 HD 候选，落 mp3 供人听。

## 来路

抖音七批创作诊断 **7/7 点名「配音像机器播报」**（2026-08-09），账号所有者
授权按最优方式改，并指明「情绪化 tts 也不是真人语音」——2026-08-04 否掉的
是 Azure 标准档的情绪风格（excited/sad 那批，量了三维听下来还是糙），
**不是否掉更高档的声线**。DragonHD 是另一代东西：自适应语调，不靠手工
风格标签（2026-03 起 $22/百万字符——一条片子约一分钱）。

## 判据（每个声都要报，缺一样就是白探）

- **词边界个数**——字幕时间轴的命根子。HD 声要是不给 WordBoundary，
  字幕只能退回按字数摊（会漂），这直接决定它能不能上生产
- 时长/体积——和基线对照，确认 prosody rate 在 HD 上是被吃了还是被忽略
- **最终判据是打开听**（沙箱听不了，所以 mp3 落进 output/voice-samples/hd/
  提交进仓库，发给账号所有者的耳朵）

失败要逐声报、不许整趟崩：HD 声按 region 分批开放（2026-03 起扩到更多
region），当前 region 不支持的报出来并给出路（换 region 或退标准档）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from voice_sample import SAMPLE  # noqa: E402  一句带引语带数字的真旁白

from tennislive.video import azure_tts  # noqa: E402

# (voice, rate, 文件名, 说明)。HD 声给 +0% 的 no-op prosody——它们自适应
# 语调，rate 多半被忽略，但 SSML 形状和生产线保持同一套，差异才可归因于声。
CANDIDATES = [
    ("zh-CN-YunjianNeural", "+6%", "baseline-yunjian",
     "云健 · 现用基线（edge/标准档同源）"),
    ("zh-CN-Yunfan:DragonHDLatestNeural", "+0%", "hd-yunfan",
     "云帆 · DragonHD 最高档（男）"),
    ("zh-CN-Xiaochen:DragonHDLatestNeural", "+0%", "hd-xiaochen",
     "晓辰 · DragonHD 最高档（女）"),
    ("zh-CN-Xiaoxiao:DragonHDFlashLatestNeural", "+0%", "hd-flash-xiaoxiao",
     "晓晓 · HD Flash（快省档）"),
]


def _seconds(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(out)
    except Exception:  # noqa: BLE001
        return 0.0


def main() -> int:
    if not azure_tts.available():
        print(f"探不了：{azure_tts.why_unavailable()}")
        return 1
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else
                  "output/voice-samples/hd")
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"样句 {len(SAMPLE)} 字\n")
    ok = 0
    for voice, rate, stem, label in CANDIDATES:
        dest = outdir / f"{stem}.mp3"
        try:
            marks = azure_tts.synthesize(
                SAMPLE, dest, voice=voice, rate=rate, pitch="+0Hz")
        except Exception as exc:  # noqa: BLE001 逐声报，别整趟崩
            print(f"❌ {label}\n   {voice}: {exc}\n"
                  "   出路：HD 声按 region 分批开放——查 AZURE_SPEECH_REGION "
                  "是否在支持名单里，不在就换 region 或退标准档\n")
            continue
        ok += 1
        secs = _seconds(dest)
        kb = dest.stat().st_size / 1024
        boundary = f"词边界 {len(marks)} 个"
        if not marks:
            boundary += "（⚠️ 没有词边界——字幕只能退按字数摊，会漂，上生产前要掂量）"
        print(f"✅ {label}\n   {voice}  {secs:.1f}s  {kb:.0f}KB  {boundary}\n")
    print(f"{ok}/{len(CANDIDATES)} 个声合成成功。"
          "最终判据是打开听——mp3 在仓库里，发给账号所有者的耳朵。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
