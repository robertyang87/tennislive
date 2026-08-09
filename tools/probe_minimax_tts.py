#!/usr/bin/env python3
"""MiniMax 托管 TTS（speech-02-hd / speech-2.5-hd）试音。

## 来路

账号所有者 2026-08-09 给了 MiniMax 的 API key（「可以用这个试试」）——
这是配音「机器感」问题的托管候选，和自托管的 CosyVoice2 并行试音。
2026-08-09 在沙箱实测过一轮：`api.minimaxi.com/v1/t2a_v2`、Bearer 认证、
**不需要 GroupId**（sk- 新式 key），返回 hex 编码的 MP3；同一段 100 字
旁白单次合成 **4.5~5.4 秒**（含网络往返），五个声线一次全成。

## 事实与口径

- **key 一律走 `MINIMAX_API_KEY` 环境变量**，不进仓库不进日志。
  runner 上用 Actions secret；没配就报出来退出，不装作探过
- **它也有 10 秒声音克隆**（托管版），和 CosyVoice 的零样本克隆是
  同一个卖点的两种形态：一个免费自托管、一个按字符计费但快且稳
- **词边界它不给**——接入时和 CosyVoice 同一个方案：faster-whisper
  对已知文本强制对齐补 words.json。字幕线在那之前不受影响
- 试音声线是挑过的体育解说向男声；情绪参数（voice_setting.emotion）
  先不动——账号所有者 2026-08-04 对「情绪化配音」的否决记在 CLAUDE.md，
  要试也是他点头之后
"""

from __future__ import annotations

import binascii
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voice_sample import SAMPLE  # noqa: E402

URL = "https://api.minimaxi.com/v1/t2a_v2"

# (model, voice_id, speed, 文件名干)
JOBS = [
    ("speech-2.5-hd-preview", "male-qn-jingying", 1.0, "mm25-精英青年音"),
    ("speech-02-hd", "male-qn-jingying", 1.0, "mm02-精英青年音"),
    ("speech-02-hd", "presenter_male", 1.0, "mm02-男主持"),
    ("speech-02-hd", "audiobook_male_1", 1.0, "mm02-有声书男1"),
    ("speech-02-hd", "male-qn-badao", 1.1, "mm02-霸道青年音-1.1x"),
]


def synth(key: str, model: str, voice: str, speed: float) -> tuple[bytes | None, float, str | None]:
    body = {
        "model": model,
        "text": SAMPLE,
        "voice_setting": {"voice_id": voice, "speed": speed, "vol": 1.0, "pitch": 0},
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
    }
    t0 = time.perf_counter()
    r = requests.post(URL, json=body, timeout=60,
                      headers={"Authorization": f"Bearer {key}",
                               "Content-Type": "application/json"})
    spent = time.perf_counter() - t0
    j = r.json()
    st = j.get("base_resp", {})
    if st.get("status_code") != 0:
        # 4xx/配额/声线名错全在 status_msg 里——只报状态码等于让下一个人再跑一趟
        return None, spent, f"{st.get('status_code')}: {st.get('status_msg')}"
    return binascii.unhexlify(j["data"]["audio"]), spent, None


def main() -> int:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        print("❌ 没配 MINIMAX_API_KEY，什么都没探。runner 上配 Actions secret；"
              "本地 export 一下再跑。")
        return 1
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "output/voice-samples/minimax")
    outdir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for model, voice, speed, stem in JOBS:
        audio, spent, err = synth(key, model, voice, speed)
        if err:
            print(f"❌ {stem}（{model}）：{err}", flush=True)
            continue
        p = outdir / f"{stem}.mp3"
        p.write_bytes(audio)
        print(f"✅ {stem}: {len(audio) / 1024:.0f} KB，API 用时 {spent:.1f}s", flush=True)
        ok += 1
    print(f"{ok}/{len(JOBS)} 版样品合成成功。最终判据是账号所有者打开听。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
