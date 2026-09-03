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
import functools
import json
import re
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

_SYSTEM_RULES = """你是网球短视频账号「网球时差」的编辑，给「赛场之上」栏目起草文案。

账号的硬规矩（照做，别发挥）：

【有球员背景，别纯报比分】
- 文案要有球员的信息背景做支撑：年龄、排名、国籍、种子、H2H、纪录、告别、
  金句——这些让这条片子「说的是这个人」，不是「说的是这个比分」。
- 但背景是**一句带过**，别展开铺陈：身份海报别处已经印着了，钩子再写一遍是
  白占字数。

【有趣生动，引人入胜】
- 用**本次事实包确实存在的数字反差**制造记忆点，不得套用提示词或样片数字。
- 用**悬念层层推进**：把已核实的转折拆成几步，每句留一个「然后呢」。
- 每句旁白 ≤ 35 字，一条一个事实，不堆叠。

【配音断句——旁白是念出来、还要烧成字幕的】
- **两个标点之间的子句 ≤ 16 字**：一行字幕正好 16 格，子句超宽只能从词语
  中间硬切。长句拆成短句，用逗号句号断开。
- **比分一律写汉字**：「六比一」「七比五」，不写「6-1」「7-5」——连字符会被
  读出声。年份、排名、总分这类单个数字照常写阿拉伯数字。
- **顿号只连并列的词**（「周三、周四」「斯瓦泰克、高芙」），不连分句——顿号
  在配音里几乎不停顿，连分句就是一口气冲过去。
- 长定语别前置（「他成了第一个在这个级别打进 4 强的中国男子球员」念着最累），
  把主语挪到句末：「这个级别打进 4 强的中国男子球员，他是第一个。」
- **一句里别串四个以上逗号**：逗号只给短停，连着四个等于没停——念出来是一长串
  短促的顿，没有一个真正的换气点。断成两句，或者把其中一处换成句号。
- **句子的尾巴别留一个两三个字的碎片**：「第四盘，纳沃内从一比二连赢五局，
  六比二。」这一句的字幕会切成「第四盘 纳沃内从1比2连赢5局」＋「6比2」——
  后一屏读起来是半截话。把它并进前一句（「…连赢五局拿下六比二」）就好。

【轮次和名次怎么说】
- 轮次这样说：**决赛、4 强、8 强、16 强**，再往前写「第一轮/第二轮/第三轮」。
- 一个人**走到哪儿**，按这个阶梯说：**冠军、亚军、4 强、8 强、16 强、第几轮**。
  打进决赛没夺冠的，那就是**亚军**——别只说「打进决赛」把结果含糊过去。

【结合比分】
- 旁白讲的事要落到事实包给出的比分和局势上。事实包没有某盘、某局或某个
  盘分，就绝不能为了制造戏剧性补出来。

【事实底线】
- 只写给到的素材里有的事实，不编造比分、不编造球员说的话。
- 给到的背景、金句、纪录，用了就要原样用，别改写数字。
- question、thesis、beats、human_context、narration 都可能进入中文配音：百分比必须
  写成「百分之八十二」，不得写 `82%` 或 `82％`；push 文案可以保留 `%`。

【收尾一问】
- 收尾落在**这一场球有证据的具体悬念**上。问题里的每个比分和数字都必须来自
  本次事实包；不要套用提示词示例，也不要写「还能走多远」这种空话。

只输出一个 json 对象，字段：hook（2 行，每行 ≤10 字符）、question、thesis、
beats（3 段）、human_context（场外切口：金句/纪录/复仇/告别，一段话）、
narration（每段一句，对应 beats）。"""


@functools.lru_cache(maxsize=None)
def system_prompt() -> str:
    """SYSTEM prompt 拼上生产 skill——**拖到第一次要用才读盘**。

    2026-08-27 reel-auto-ready 栽的：它的稀疏检出没有 `skills/`，而这份 prompt
    原来在 **import 那一刻**就去读 SKILL.md——`refresh_reel_cover` 只想借
    `assemble_spec` 里两个和模型无关的小函数，整条 import 链就炸在教材缺席上，
    第一条真实的 pending 草稿因此一次都没被重试过。**import 一个工具不许要求
    磁盘上有教材**；真要起草时教材缺席，这儿仍然当场响。
    """
    return _SYSTEM_RULES + model_instructions("deepseek")


def _spoken_integer(value: int) -> str:
    # 出处只有一份：spec_wording.spoken_integer（promote 那头也用它）
    from spec_wording import spoken_integer  # noqa: PLC0415
    return spoken_integer(value)


def normalize_editorial_for_speech(value):
    """Remove symbols known to break Chinese TTS from every editorial field."""
    if isinstance(value, dict):
        return {key: normalize_editorial_for_speech(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_editorial_for_speech(item) for item in value]
    if isinstance(value, str):
        value = re.sub(
            r"(?<!\d)(\d{1,3})\s*[%％]",
            lambda found: "百分之" + _spoken_integer(int(found.group(1))),
            value,
        )
        # 比分写成「7-5」进旁白，TTS 会把连字符读出声（「七杠五」）；下游的
        # `readable()` 能把它救成「7比5」，但那是兜底——模型的旁白在源头就该
        # 写成汉字「七比五」（prompt 里也这么要求了，这儿是执法）。两侧最多
        # 两位数（局分/盘分/抢七都够），四位年份「2016-2026」被 (?<!\d) 挡住。
        value = re.sub(
            r"(?<![\d.])(\d{1,2})\s*[-–—−]\s*(\d{1,2})(?![\d.])",
            lambda found: (_spoken_integer(int(found.group(1))) + "比"
                           + _spoken_integer(int(found.group(2)))),
            value,
        )
        # Models occasionally insert an English-style word space between two
        # Chinese words (for example ``今天 他``).  It is audible as an
        # unnatural pause in TTS and should not survive into narration.
        return re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", value)
    return value


_CLAIM_NUMBER = r"(?:\d{1,3}|[零〇一二三四五六七八九十百两]{1,6})"
_LEAD_CLAIM = re.compile(
    rf"(?P<a>{_CLAIM_NUMBER})\s*比\s*(?P<b>{_CLAIM_NUMBER})"
    rf".{{0,16}}?(?:只|仅)?(?:领先|多拿?|净胜)\s*(?P<delta>{_CLAIM_NUMBER})\s*分"
)


def _claim_integer(value: str) -> int:
    if value.isdigit():
        return int(value)
    digits = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3,
              "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    total = current = 0
    for char in value:
        if char in digits:
            current = digits[char]
        elif char in {"十", "百"}:
            total += (current or 1) * {"十": 10, "百": 100}[char]
            current = 0
    return total + current


def arithmetic_claim_problem(content) -> str | None:
    """拒绝“56 比 45 只领先 9 分”一类数字都真但关系为假的文案。"""
    def texts(value):
        if isinstance(value, dict):
            for nested in value.values():
                yield from texts(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                yield from texts(nested)
        elif value is not None:
            yield str(value)

    for text in texts(content):
        for found in _LEAD_CLAIM.finditer(text):
            left = _claim_integer(found.group("a"))
            right = _claim_integer(found.group("b"))
            claimed = _claim_integer(found.group("delta"))
            expected = abs(left - right)
            if claimed != expected:
                return (f"算术关系错误：{found.group('a')}比{found.group('b')}"
                        f"相差{expected}分，不是{found.group('delta')}分")
    return None


def draft_editorial(chat: Chat, *, home: str, away: str, event: str, year: int,
                    fixture: str, facts: str = "", background: str = "") -> dict | None:
    user = (
        f"这场球：{home} vs {away}，{event} {year}。\n"
        f"赛前信息（fixture）：{fixture}\n"
        f"已核实的狠数据/技术统计（有就用，没有不强凑）：\n{facts or '（没有）'}\n"
        f"球员信息背景（排名/年龄/国籍/H2H/纪录/金句，有就用，别编）：\n"
        f"{background or '（没有）'}\n"
    )
    draft = chat.ask(system_prompt(), user, schema=SCHEMA, max_tokens=2000)
    return normalize_editorial_for_speech(draft) if isinstance(draft, dict) else draft


_PUSH_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "lead": {"type": "string"},
    },
    "required": ["summary", "lead"],
}

_PUSH_RULES = """你是网球短视频账号「网球时差」的推送编辑，给一条「赛场之上」片子写推送。

- `summary`：推送标题，**≤20 字位**（全角 1 字、半角 0.5），一句话把「谁赢了、多硬」
  说清，像「兹维列夫两盘抢七险胜」。别写排名身份（海报已经印着）。
- `lead`：正文第一段，2-4 句，说清这场球的具体过程 + 一个数字反差，别空话。
- 只写给到的素材里有的事实，别编比分、别编球员说的话。"""


@functools.lru_cache(maxsize=None)
def push_system_prompt() -> str:
    """和 `system_prompt` 同一条理由：教材拖到要用才读盘。"""
    return _PUSH_RULES + model_instructions("deepseek")


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
    return chat.ask(push_system_prompt(), user, schema=_PUSH_SCHEMA, max_tokens=800)


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
