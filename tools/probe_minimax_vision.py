#!/usr/bin/env python3
"""探测 MiniMax 视觉（M3 多模态）到底怎么调：端点 + model 名实测，不猜。

账号所有者给了 MiniMax key，问能不能拿来做视觉（封面帧终审）。MiniMax M3
2026-06 起支持原生多模态（图片/视频输入），但**端点/模型名/图片传法有几套**
（OpenAI 兼容 / Anthropic 兼容 / MiniMax 原生），不实测就写进生产会踩错。

用法：
    MINIMAX_API_KEY=... python tools/probe_minimax_vision.py --image 某图.jpg

✅ 2026-08-16 实测确认（拿 landaluce-draper 海报试的，模型读对了比分和赛事）：
   端点 `https://api.minimaxi.com/v1/chat/completions`（OpenAI 兼容）
   模型 `MiniMax-M3`
   ⚠️ 默认开思考，要传 `thinking: {"type": "disabled"}` 才给干净答案——
     和 DeepSeek 那条线同一个形状（关掉之后 max_tokens 才只算正文）。

⚠️ key 只走环境变量，绝不进仓库/日志。探到能用的组合就打印出来，供
`pick_cover_frame.py` 照着接。
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

# 候选组合：MiniMax 的 OpenAI 兼容 / 原生两个端点 × 几个可能的 model 名。
# 顺序是「最可能先试」，探到第一个能出视觉结果的组合就停。
CANDIDATES = [
    ("https://api.minimaxi.com/v1/chat/completions", "MiniMax-M3"),
    ("https://api.minimaxi.com/v1/chat/completions", "minimax-m3"),
    ("https://api.minimaxi.com/v1/chat/completions", "abab6.5s-chat"),
    ("https://api.minimax.io/v1/chat/completions", "MiniMax-M3"),
    ("https://api.minimaxi.com/v1/text/chatcompletion_v2", "MiniMax-M3"),
]


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def _ask(endpoint: str, model: str, image_b64: str, key: str) -> str | None:
    """OpenAI 兼容的 chat completions，带一张图 + 一句问题。"""
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "这张图里是什么？一句话回答。"},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
        "max_tokens": 100,
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=60) as fh:
        data = json.loads(fh.read())
    # OpenAI 格式：choices[0].message.content
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return json.dumps(data, ensure_ascii=False)[:300]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--image", required=True, help="测试图片路径")
    args = ap.parse_args()

    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        print("没配 MINIMAX_API_KEY 环境变量，退出（不装作探过）")
        return 2
    img = Path(args.image)
    if not img.is_file():
        print(f"找不到图片：{img}")
        return 2
    b64 = _b64(img)
    print(f"测 {len(CANDIDATES)} 个（端点, model）组合…")
    for endpoint, model in CANDIDATES:
        try:
            ans = _ask(endpoint, model, b64, key)
            print(f"\n✅ 能用：{endpoint}  model={model}")
            print(f"   回答：{ans}")
            return 0
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            print(f"  ✗ {model} @ {endpoint}: HTTP {e.code} {body}")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {model} @ {endpoint}: {type(e).__name__} {e}")
    print("\n全试完没一个通——端点或 model 名不对，去 MiniMax 文档核一遍。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
