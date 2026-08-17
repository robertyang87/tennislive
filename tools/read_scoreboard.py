#!/usr/bin/env python3
"""用 MiniMax 视觉读记分条条带（score_*.jpg），输出「时间码 → 比分」序列。

## 为什么是这条链的命门

「配音和视频不脱节」的唯一可靠信号是**比分数字**——逐分数据有每一分的
`gameScore`（15/30/40），比分板画面烧着同样的 15/30/40。两者对齐，就能把
「赛点那一分」从「逐分第 N 分」定位到「视频第 X 秒」。

但「读比分板数字」是视觉活。probe 已经产出了给**人**读比分的素材——
`score_*.jpg`（裁出记分条那一块、放大到能读、每格烧时间码的缩略图墙）。
这个工具把「人读」换成「MiniMax 读」。

⚠️ 只读、只输出，不改任何东西。读出来的比分序列是**候选**，要和逐分数据的
比分序列对齐之后才算数（见 docs/scoreboard-alignment.md §3）。

用法：
    MINIMAX_API_KEY=... python tools/read_scoreboard.py \
        --dir output/2026-08-15/reel/wangxiyu-timofeeva \
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
    "你是网球记分员。给你一张网球比赛转播的记分条条带图（多个格子并排，"
    "每个格子里是放大的记分条，左上角烧着这一帧的时间码，形如 `13.7s`）。\n"
    "读每个格子：时间码是多少秒、这一帧记分条显示的双方比分是什么。\n"
    "⚠️ 记分条比分通常是「局分 盘分」或「局分 小分」的格式，比如"
    " `1-2`（局分）配 `15-30`（小分），或者三盘比 `6 4 0 / 4 6 2`。"
    "照格子原样读，读不清的格子跳过，别编。\n"
    "只输出一个 json 数组，每项 {t: 时间码数字, score: \"读到的比分原文\"}。"
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
    ap.add_argument("--dir", required=True, type=Path,
                    help="probe 产物目录（含 score_*.jpg）")
    ap.add_argument("--out", default="", help="把比分序列写进这个 json 文件")
    args = ap.parse_args()

    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        print("[跳过] 没配 MINIMAX_API_KEY 环境变量，退化出声")
        return 2

    sheets = sorted(args.dir.glob("score_*.jpg"))
    if not sheets:
        print(f"[跳过] {args.dir} 里没有 score_*.jpg")
        return 2

    all_rows: list[dict] = []
    for sheet in sheets:
        print(f"读 {sheet.name} …")
        rows = _ask(sheet, key)
        if rows is None:
            print(f"  ⚠️ {sheet.name} 没读出 json，跳过")
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
