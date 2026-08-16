#!/usr/bin/env python3
"""用 MiniMax M3 视觉，从候选封面帧里按「情绪对不对题」挑一张。

CLAUDE.md 的选图判据：「这条片子讲什么，封面就要是那个情绪——讲逆转就找他
扛住的那一刻，讲夺冠就找捧杯」。这条一直是人工终审，MiniMax M3 有视觉
（probe_minimax_vision 实测确认），这一环能自动化了。

⚠️ 只做「从候选里挑」，不生成候选。候选是**封面大图（`cover.portrait`）的
候选**——官方高清实拍为主（`fetch_wta_cover_photo.py` 抓 WTA 赛后稿头图，
或 highlights 页的集锦头图 `?width=4000`），不是 `pick_cover_frames.py` 的
产物。⚠️ `pick_cover_frames.py` 是给**抠图**（`cover.versus.top/bottom`）用的，
判据是正脸/上身直立/表情清楚，和封面大图的「情绪对不对题」是两回事——别混。
视觉模型做的是最后一跳：按情绪打分选。

⭐ 封面**一定要高清大图**（账号所有者 2026-08-16）。在情绪挑选之前先过一道
原生分辨率闸：短边低于 `MIN_COVER_SIDE` 的帧直接剔除并出声，全都不达标就
非零退出、明说「去拿真实照片」，**不许硬挑一张软的**。

    为什么落在「原生分辨率」而不是清晰度：清晰度换帧解决不了、锐化还能刷分
    （CLAUDE.md「选图」一节量过），而分辨率一眼就分得出「真实照片」和「压缩
    转播抽帧」——官方高清图通常 ≥ 2K，转播流抽帧上限就是 1920×1080 且还是
    压缩过的。1080 是「高清」的硬下限，也是竖版海报（1080×1440）短边的量；
    低于它连「高清」都不算，遑论「大图」。

用法：
    MINIMAX_API_KEY=... python tools/pick_cover_frame.py \
        --frames /tmp/cand/000.jpg,/tmp/cand/001.jpg \
        --angle "逆转：决胜盘二比五落后，连救五个赛点反超"
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.minimaxi.com/v1/chat/completions"
MODEL = "MiniMax-M3"
MIN_COVER_SIDE = 1080  # 封面短边下限（px）。低于它连「高清」都不算（见 docstring）


def _size(p: Path) -> tuple[int, int]:
    """读真实像素尺寸（PIL 只读头部，不加载全图），不信扩展名/文件名。"""
    from PIL import Image  # noqa: PLC0415
    with Image.open(p) as im:
        return im.size  # (宽, 高)


def hd_gate(frames: list[Path]) -> tuple[list[Path], list[tuple[Path, str]]]:
    """高清闸：短边低于 MIN_COVER_SIDE 的剔掉并出声。返回 (过闸的, 被拒的)。"""
    keep, drop = [], []
    for p in frames:
        try:
            w, h = _size(p)
        except Exception as exc:  # noqa: BLE001 —— 读不了尺寸的帧不该静默放过
            drop.append((p, f"读不出尺寸：{exc}"))
            continue
        if min(w, h) < MIN_COVER_SIDE:
            drop.append((p, f"短边 {min(w, h)}px 不够高清（要 ≥ {MIN_COVER_SIDE}）"))
        else:
            keep.append(p)
    return keep, drop


def pick(frames: list[Path], angle: str, key: str) -> int | None:
    """返回 0-based 序号。模型答不出整数就 None（不猜）。"""
    content: list[dict] = [{
        "type": "text",
        "text": (f"下面是这场比赛的 {len(frames)} 张候选封面帧。"
                 f"这场要讲的主题是：{angle}。\n"
                 "哪一张的**情绪**最贴这个主题？只回答一个 1 到 "
                 f"{len(frames)} 的数字，别的什么都别写。"),
    }]
    for p in frames:
        b64 = base64.b64encode(p.read_bytes()).decode()
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 50,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as fh:
        data = json.loads(fh.read())
    answer = data["choices"][0]["message"]["content"]
    m = re.search(r"\b([1-9])\b", answer)
    if not m:
        return None
    idx = int(m.group(1)) - 1
    return idx if 0 <= idx < len(frames) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--frames", required=True,
                    help="候选帧路径，逗号分隔")
    ap.add_argument("--angle", required=True,
                    help="这场要讲的情绪主题，如「逆转：决胜盘二比五落后连救五赛点」")
    args = ap.parse_args()

    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        print("没配 MINIMAX_API_KEY 环境变量，退出")
        return 2
    frames = [Path(p.strip()) for p in args.frames.split(",") if p.strip()]
    missing = [p for p in frames if not p.is_file()]
    if missing:
        print(f"找不到帧：{missing}")
        return 2

    keep, drop = hd_gate(frames)
    for p, why in drop:
        print(f"  丢弃 {p.name}：{why}")
    if not keep:
        print("候选里没有一张高清大图——去拿真实照片，别硬挑一张软的。")
        return 3

    idx = pick(keep, args.angle, key)
    if idx is None:
        print("模型没答出一个合法序号（不猜），自己看一眼候选帧。")
        return 1
    print(f"挑中第 {idx + 1} 张：{keep[idx]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
