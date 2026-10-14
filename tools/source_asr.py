#!/usr/bin/env python3
"""源片解说的英文转写：两档 faster-whisper（small.en / medium.en，逐词时间码），给原声审听交叉核对用。

来路（2026-10-12 `wangxiyu-wangxinyu-wuhan-2026-r1`）：原声审听闸要求每个保留窗口都有一份
转写证据，那一条是在一个临时分支上手搓工作流跑出来的，等了 10 分钟——而那时源片
probe 都已经跑完了。现在 `source-asr.yml` 跟 probe **并行**跑（probe 用上 Release 存档时
自动派发），会话写 spec 的时候两份转写已经在 `data/source_asr/<视频 id>/` 里了。

⚠️ 这只是**转写**，不是审听结论：哪句留、字幕怎么写、`foreground_english` 照旧由写 spec 的人
对照两份结果定（`tools/foreground_audio_gate.py` 的口径不变）。

用法::

    python tools/source_asr.py --source source.mp4 --model small.en --out small.en.json \
        [--from 0] [--to 300]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MODELS = ("small.en", "medium.en")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def shift(segments: list[dict], offset: float) -> list[dict]:
    """转写的是截出来的那一段：时间码加回源片绝对秒，和 spec 的 start/end 同一把尺子。"""
    if not offset:
        return segments
    out = []
    for s in segments:
        s = dict(s, start=round(s["start"] + offset, 2), end=round(s["end"] + offset, 2))
        s["words"] = [dict(w, s=round(w["s"] + offset, 2), e=round(w["e"] + offset, 2))
                      for w in s.get("words") or []]
        out.append(s)
    return out


def transcribe(source: Path, model_name: str, clip_from: float = 0.0,
               clip_to: float = 0.0) -> tuple[list[dict], float]:
    """用 faster-whisper 自带的 PyAV 解码（runner 上不用另装 ffmpeg），区间在内存里切。"""
    from faster_whisper import WhisperModel, decode_audio  # runner 上才装

    rate = 16000
    audio = decode_audio(str(source), sampling_rate=rate)
    audio = audio[int(clip_from * rate):(int(clip_to * rate) if clip_to else None)]
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, info = model.transcribe(audio, language="en", word_timestamps=True,
                                  vad_filter=False, beam_size=5,
                                  condition_on_previous_text=False)
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "avg_logprob": round(s.avg_logprob, 3), "no_speech_prob": round(s.no_speech_prob, 3),
            "words": [{"w": w.word, "s": round(w.start, 2), "e": round(w.end, 2),
                       "p": round(w.probability, 3)} for w in (s.words or [])]}
           for s in segs]
    return out, float(info.duration)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--model", required=True, choices=MODELS)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--from", dest="clip_from", type=float, default=0.0)
    ap.add_argument("--to", dest="clip_to", type=float, default=0.0)
    args = ap.parse_args()

    segments, duration = transcribe(args.source, args.model, args.clip_from, args.clip_to)

    doc = {"model": args.model, "source_sha256": sha256(args.source),
           "clip": [args.clip_from, args.clip_to or None], "duration": duration,
           "segments": shift(segments, args.clip_from)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{args.model}: {len(segments)} 句 → {args.out}")
    for s in doc["segments"]:
        print(f"{s['start']:7.2f}-{s['end']:7.2f} [{s['no_speech_prob']:.2f}] {s['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
