#!/usr/bin/env python3
"""用 DeepSeek 给一条「赛场之上」片子起草 spec 的**编辑内容**，不写窗口。

无人值守链最后一块。probe 出缩略图/切点之后、写 spec 之前，最花人的是编辑内容
（钩子、旁白、human_context、editorial 合同的 question/thesis/beats）——这些是
「贴近比赛事实 + 有吸引力」的主体，机械写不了，但 DeepSeek 能起草一版。

⚠️ **这是起草，不是定稿**：产出交给现有的机械闸（validate_spec / _hit_data /
栏目登记 / 全称断言双源）校验，最后账号所有者推微信后自己看。LLM 没配密钥就
跳过出声，退化不许静默。

⚠️ 只起草编辑内容，**不写 segments 窗口**（start/end/cx）——窗口由机械工具从
逐分数据/切点提候选（find_turning_points 提转折局、scene_cuts 提切点、
point_ends 提死球），不靠 DeepSeek：它是纯文本模型，没有视觉，分析不了视频。
真正需要视觉的环节只剩**封面情绪终审**（讲逆转就找他扛住那一刻），那是
`pick_cover_frame.py`（MiniMax M3 视觉）的事，不是文本 LLM 能兜的。

用法：
    python tools/draft_spec.py --slug eala-pegula --home Eala --away Pegula \
        --event Washington --year 2026 --fixture "北京时间 8 月 3 日…"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tennislive.research.brief import Chat  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "hook": {"type": "array", "items": {"type": "string"}},
        "question": {"type": "string"},
        "thesis": {"type": "string"},
        "beats": {"type": "array", "items": {"type": "string"}},
        "human_context": {"type": "string"},
        "narration": {"type": "array", "items": {"type": "string"}},
    },
}

SYSTEM = """你是网球短视频账号「网球时差」的编辑，给「赛场之上」栏目起草内容。
账号的硬规矩（照做，别发挥）：
- 钩子讲**过程**（几比几落后、救了几个赛点、连丢几局、逆转），不是把**身份**
  （排名/年龄/国籍/冠军）摆在一起——身份海报别处已经印着了。
- 每条旁白都要能回答「前段走势 / 中段转折 / 结局回应」三问，按时间顺序。
- 事实必须能落到比赛记录里，不编造比分、不夸大。
- 收尾落在一问上（互动），不要「还能走多远」这种空话。
- 钩子每行 ≤ 10 个字符（中文算一个字）。
只输出一个 json 对象，字段：hook（2 行）、question、thesis、beats（3 段）、
human_context、narration（每段一句，对应 beats）。"""


def draft_editorial(chat: Chat, *, home: str, away: str, event: str, year: int,
                    fixture: str, facts: str = "") -> dict | None:
    user = (
        f"这场球：{home} vs {away}，{event} {year}。\n"
        f"赛前信息（fixture）：{fixture}\n"
        f"已核实的狠数据/技术统计（有就用，没有不强凑）：\n{facts or '（没有）'}\n"
    )
    return chat.ask(SYSTEM, user, schema=SCHEMA, max_tokens=2000)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--fixture", default="")
    ap.add_argument("--facts", default="", help="match_stat_hooks 的候选（粘贴）")
    args = ap.parse_args()

    chat = Chat()
    if not chat.ready:
        print("[跳过] 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，退化出声")
        return 0
    print(f"通道 {chat.channel}")
    draft = draft_editorial(chat, home=args.home, away=args.away, event=args.event,
                            year=args.year, fixture=args.fixture, facts=args.facts)
    if draft is None:
        print("[跳过] 模型这步没成（见日志），本条不起草")
        return 0
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
