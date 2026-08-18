#!/usr/bin/env python3
"""用 MiniMax 视觉读比分板，输出「时间码 → 比分」序列。

## 为什么是这条链的命门

「配音和视频不脱节」的唯一可靠信号是**比分数字**——逐分数据有每一分的
`gameScore`（15/30/40），比分板画面烧着同样的 15/30/40。两者对齐，就能把
「赛点那一分」从「逐分第 N 分」定位到「视频第 X 秒」。

## 抽帧是机械的，识别是视觉的（账号所有者 2026-08-17 定的分工）

「让 MiniMax 按 Claude 那种方式抽帧、定格、识别比分」——**抽帧**是机械的：
probe 已经每隔 N 秒从源片抽一帧、烧上时间码、拼成 `contact_*.jpg`（整帧缩略
图墙）。**识别**是视觉的：MiniMax 在**整帧画面里自己找比分板**、读数字，
不依赖人工裁好的记分条条带（`score_*.jpg` 那个「左下 42%」的固定框是给人
看的，不一定框得准，而且不是自动检测的）。

⚠️ 只读、只输出，不改任何东西。读出来的比分序列是**候选**，要和逐分数据的
比分序列对齐之后才算数（见 docs/scoreboard-alignment.md §3）。

用法：
    MINIMAX_API_KEY=... python tools/read_scoreboard.py \
        --frames output/2026-08-15/reel/wangxiyu-timofeeva/contact_00.jpg \
        --frames output/2026-08-15/reel/wangxiyu-timofeeva/contact_01.jpg \
        --out /tmp/scoreboard.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.minimaxi.com/v1/chat/completions"
MODEL = "MiniMax-M3"

SYSTEM = (
    "你是网球记分员。给你一张网球比赛转播画面的缩略图墙（多个格子并排，"
    "每个格子是完整的一帧画面，左上角烧着这一帧的时间码，形如 `13.7s`）。\n"
    "在每个格子的**画面里自己找比分板**（通常在画面角落，深色底、上面有双方"
    "名字和比分数字），读出**局分**和**小分**两样。\n"
    "⚠️ 局分 = 这一盘双方各赢几局（如 2-0，读不清留空）；小分 = 这一局双方"
    "各拿几分（0/15/30/40，如 0-40，读不清留空）。两样分开读，别混、别编。\n"
    "只输出一个 json 数组，每项 {t: 时间码数字, games: \"局分如 2-0\", "
    "points: \"小分如 0-40\"}。读不清哪样就哪样空串，别漏掉格子。"
)


def _ask(image: Path, key: str) -> list[dict] | None:
    b64 = base64.b64encode(image.read_bytes()).decode()
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": SYSTEM},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        "max_tokens": 2000,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as fh:
        data = json.loads(fh.read())
    text = data["choices"][0]["message"]["content"]
    # 模型可能包在 ```json 里，剥掉
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # 有些模型直接给数组文本
        import re
        m = re.search(r"\[.*\]", text, re.S)
        if not m:
            return None
        parsed = json.loads(m.group(0))
    return parsed if isinstance(parsed, list) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--frames", required=True, type=Path, nargs="+",
                    help="整帧缩略图墙（contact_*.jpg），可给多张")
    ap.add_argument("--out", default="", help="把比分序列写进这个 json 文件")
    args = ap.parse_args()

    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        print("[跳过] 没配 MINIMAX_API_KEY 环境变量，退化出声")
        return 2

    frames = [p for p in args.frames if p.is_file()]
    if not frames:
        print("[跳过] 给的帧都不存在")
        return 2

    all_rows: list[dict] = []
    for frame in frames:
        print(f"读 {frame.name} …")
        rows = _ask(frame, key)
        if rows is None:
            print(f"  ⚠️ {frame.name} 没读出 json，跳过")
            continue
        print(f"  {len(rows)} 个格子")
        all_rows.extend(rows)

    if args.out:
        Path(args.out).write_text(
            json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"比分序列 → {args.out}（共 {len(all_rows)} 格）")
    else:
        print(json.dumps(all_rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
