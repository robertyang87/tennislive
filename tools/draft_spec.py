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
from reel_skill import model_instructions  # noqa: E402

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
    "required": ["hook", "question", "thesis", "beats", "human_context", "narration"],
    "additionalProperties": False,
}

SYSTEM = """你是网球短视频账号「网球时差」的编辑，给「赛场之上」栏目起草文案。

账号的硬规矩（照做，别发挥）：

【有球员背景，别纯报比分】
- 文案要有球员的信息背景做支撑：年龄、排名、国籍、种子、H2H、纪录、告别、
  金句——这些让这条片子「说的是这个人」，不是「说的是这个比分」。
- 但背景是**一句带过**，别展开铺陈：身份海报别处已经印着了，钩子再写一遍是
  白占字数。

【有趣生动，引人入胜】
- 用**本次事实包确实存在的数字反差**制造记忆点，不得套用提示词或样片数字。
- 用**悬念层层推进**：把已核实的转折拆成几步，每句留一个「然后呢」。
- 每句旁白 ≤ 50 字，一条一个事实，不堆叠。

【结合比分】
- 旁白讲的事要落到事实包给出的比分和局势上。事实包没有某盘、某局或某个
  盘分，就绝不能为了制造戏剧性补出来。

【事实底线】
- 只写给到的素材里有的事实，不编造比分、不编造球员说的话。
- 给到的背景、金句、纪录，用了就要原样用，别改写数字。

【收尾一问】
- 收尾落在**这一场球有证据的具体悬念**上。问题里的每个比分和数字都必须来自
  本次事实包；不要套用提示词示例，也不要写「还能走多远」这种空话。

只输出一个 json 对象，字段：hook（2 行，每行 ≤10 字符）、question、thesis、
beats（3 段）、human_context（场外切口：金句/纪录/复仇/告别，一段话）、
narration（每段一句，对应 beats）。""" + model_instructions("deepseek")


def draft_editorial(chat: Chat, *, home: str, away: str, event: str, year: int,
                    fixture: str, facts: str = "", background: str = "") -> dict | None:
    user = (
        f"这场球：{home} vs {away}，{event} {year}。\n"
        f"赛前信息（fixture）：{fixture}\n"
        f"已核实的狠数据/技术统计（有就用，没有不强凑）：\n{facts or '（没有）'}\n"
        f"球员信息背景（排名/年龄/国籍/H2H/纪录/金句，有就用，别编）：\n"
        f"{background or '（没有）'}\n"
    )
    return chat.ask(SYSTEM, user, schema=SCHEMA, max_tokens=2000)


_PUSH_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "lead": {"type": "string"},
    },
    "required": ["summary", "lead"],
}

_PUSH_SYSTEM = """你是网球短视频账号「网球时差」的推送编辑，给一条「赛场之上」片子写推送。

- `summary`：推送标题，**≤20 字位**（全角 1 字、半角 0.5），一句话把「谁赢了、多硬」
  说清，像「兹维列夫两盘抢七险胜」。别写排名身份（海报已经印着）。
- `lead`：正文第一段，2-4 句，说清这场球的具体过程 + 一个数字反差，别空话。
- 只写给到的素材里有的事实，别编比分、别编球员说的话。""" + model_instructions("deepseek")


def draft_push(chat: Chat, *, editorial: dict, facts: str = "") -> dict | None:
    """从 editorial（question/thesis/beats/narration）+ 狠数据生成 push.summary/lead。

    这是「草稿渲完直接合并推微信」的推送内容缺口——之前 summary/lead 靠终审手写。
    """
    beats = "\n".join(editorial.get("beats", []))
    narration = "\n".join(editorial.get("narration", []))
    user = (
        f"question：{editorial.get('question', '')}\n"
        f"thesis：{editorial.get('thesis', '')}\n"
        f"beats：\n{beats}\n"
        f"旁白：\n{narration}\n"
        f"狠数据：\n{facts or '（没有）'}\n"
    )
    return chat.ask(_PUSH_SYSTEM, user, schema=_PUSH_SCHEMA, max_tokens=800)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--home", required=True)
    ap.add_argument("--away", required=True)
    ap.add_argument("--event", required=True)
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--fixture", default="")
    ap.add_argument("--facts", default="", help="match_stat_hooks 的候选（粘贴）")
    ap.add_argument("--background", default="",
                    help="球员信息背景：排名/年龄/国籍/H2H/纪录/金句（粘贴）")
    args = ap.parse_args()

    chat = Chat()
    if not chat.ready:
        print("[跳过] 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，退化出声")
        return 0
    print(f"通道 {chat.channel}")
    draft = draft_editorial(chat, home=args.home, away=args.away, event=args.event,
                            year=args.year, fixture=args.fixture, facts=args.facts,
                            background=args.background)
    if draft is None:
        print("[跳过] 模型这步没成（见日志），本条不起草")
        return 0
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
