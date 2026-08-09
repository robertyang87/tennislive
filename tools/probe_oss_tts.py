#!/usr/bin/env python3
"""开源拟真 TTS（CosyVoice2-0.5B）试音：合样品给账号所有者的耳朵。

## 来路与选型

账号所有者 2026-08-09 拍板走「开源拟真 TTS 自托管（零 key 零费用）」。
选型 **CosyVoice2-0.5B**（阿里 FunAudioLLM）：Apache-2.0 可商用（IndexTTS-2
和 F5-TTS 质量也顶但权重非商用，直接排除）、中文 hard 测试集人声同级、
自带情绪/风格的自然语言指令。**副产品**：它就是零样本克隆引擎——将来
账号所有者录 10 秒，用他自己的声音当 prompt，就是免费的本人声线克隆。

## 本探针只回答三个问题

1. **这引擎在 runner 的 CPU 上跑不跑得动**——RTF（合成用时/音频时长）
   打进日志。RTF ≤3 生产可用（500 字旁白 ≈ 100s 音频 ≈ 5 分钟合成，
   摊进 render 趟里能忍）；RTF 更高就要掂量
2. **声音过不过耳朵**——两版样品（零样本底色版 / 体育解说指令版）落
   mp3 提交进仓库，判据是账号所有者打开听。样品用它自带的 demo prompt
   声（只用于试音）；**生产形态的 prompt 该是账号所有者自己的 10 秒录音**
3. 词边界它不给——那是接入时的活：用管线里现成的 faster-whisper 对
   已知文本做强制对齐补 words.json，这一步不在本探针范围

依赖和模型由工作流那步装（mode=oss），这里只管合成。失败逐段出声。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voice_sample import SAMPLE  # noqa: E402

COSY = Path(os.environ.get("COSYVOICE_DIR", "/tmp/CosyVoice"))
MODEL = os.environ.get("COSY_MODEL_DIR", "/tmp/cosy-model")
sys.path.insert(0, str(COSY))
sys.path.insert(0, str(COSY / "third_party" / "Matcha-TTS"))


def main() -> int:
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else
                  "output/voice-samples/oss")
    outdir.mkdir(parents=True, exist_ok=True)

    print("== 加载模型 ==", flush=True)
    t0 = time.perf_counter()
    import soundfile as sf  # noqa: PLC0415
    import torch  # noqa: PLC0415
    from cosyvoice.cli.cosyvoice import CosyVoice2  # noqa: PLC0415

    cv = CosyVoice2(MODEL, load_jit=False, load_trt=False, fp16=False)
    print(f"模型加载 {time.perf_counter() - t0:.0f}s", flush=True)

    # ⚠️ prompt 传**路径**，不传张量——现在 main 分支的接口（example.py）
    # 就是这么用的：frontend_zero_shot 自己对 prompt_wav 调 load_wav，
    # 传张量进去在任何 torchaudio 版本下都炸。而 load_wav 写的
    # `torchaudio.load(wav, backend='soundfile')` 在 torchaudio 2.9 上
    # 无视 backend、一律转发 torchcodec（2.9 删了内置后端）——所以
    # 工作流把 torchaudio 钉在 <2.9，upstream 的代码原样就能跑。
    prompt_wav = str(COSY / "asset" / "zero_shot_prompt.wav")
    prompt_text = "希望你以后能够做的比我还好呦。"

    jobs = [
        ("oss-cosy2-底色", lambda: cv.inference_zero_shot(
            SAMPLE, prompt_text, prompt_wav, stream=False)),
        # instruct 文本要自带 <|endofprompt|>（example.py 的用法；
        # frontend_instruct2 不会替你补）
        ("oss-cosy2-解说腔", lambda: cv.inference_instruct2(
            SAMPLE, "用充满激情的男性体育解说员的语气朗读<|endofprompt|>",
            prompt_wav, stream=False)),
    ]
    ok = 0
    for stem, gen in jobs:
        try:
            t1 = time.perf_counter()
            chunks = [c["tts_speech"] for c in gen()]
            audio = torch.cat(chunks, dim=1)
            spent = time.perf_counter() - t1
            secs = audio.shape[1] / cv.sample_rate
            wav = outdir / f"{stem}.wav"
            sf.write(str(wav), audio.squeeze(0).numpy(), cv.sample_rate)
            mp3 = wav.with_suffix(".mp3")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav),
                            "-b:a", "48k", str(mp3)], check=True)
            wav.unlink()
            rtf = spent / secs if secs else 999
            verdict = ("生产可用（500 字旁白约 " f"{rtf * 100 / 60:.0f} 分钟）"
                       if rtf <= 3 else "偏慢，接入前要掂量或换推理方案")
            print(f"✅ {stem}: 音频 {secs:.1f}s，合成 {spent:.0f}s，"
                  f"RTF {rtf:.1f} —— {verdict}", flush=True)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            # 完整 traceback 打进日志：只报 message 的话，错在 CosyVoice
            # 内部哪一层根本看不出来（第 5 趟就是这么多跑了一趟才定位的）
            traceback.print_exc()
            print(f"❌ {stem}: {type(exc).__name__}: {exc}", flush=True)
    print(f"{ok}/{len(jobs)} 版样品合成成功。最终判据是账号所有者打开听。")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
