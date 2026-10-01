#!/usr/bin/env python3
"""让 DeepSeek 从带时间码的字幕 + 切点，起草带窗口的 segments。

**为什么这一步能自动化，而之前一直说「填窗口靠眼睛」。** 半小时协议里
「填窗口」是全程最紧的一段（「在缩略图墙/记分条上对位」），因为过去判断
「第几秒在讲什么」靠人看画面。但 probe 已经产出了**带时间码的源片字幕**
（`captions.txt`：`秒数<TAB>这一句解说词`）——它把「哪一秒在讲赛点、破发、
救球」**文字化**了。DeepSeek 是纯文本模型，读字幕不用视觉，就能把
「这段旁白讲的事」对到「源片第几秒」上。

⚠️ 这是**起草**，不是定稿。产出的窗口要过机械闸（跨切点、越片尾、死球），
最后账号所有者推完再看。字幕是 YouTube 自动转写，稀疏且带噪音——所以窗口
精度达不到人看缩略图墙的程度，但那正是「一次成型 + 质检兜底」要接受的取舍。

用法：
    python tools/draft_segments.py \
        --captions output/2026-08-13/reel/<slug>/captions.txt \
        --cuts output/2026-08-13/reel/<slug>/probe.json \
        --beats "前段：…\n中段：…\n结局：…" \
        --home 赫瓦林斯卡 --away 布克沙
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tennislive.research.brief import Chat  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "narration": {"type": "string"},
                    "quote": {"type": "string"},
                    "_beat": {"type": "integer"},
                    "_why": {"type": "string"},
                },
                "required": ["start", "end", "narration", "_beat"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}

SYSTEM = """你是网球短视频账号「网球时差」的剪辑，给一条「赛场之上」赛后复盘片排时间轴。

给你一份**带时间码的源片解说字幕**（`秒数: 解说词`）、**镜头切点**（秒数）和封面钩子。
你要产出 segments：挑出这条片子要讲的**关键节点**，每个节点挂到源片正确的时间窗口上。

⚠️ 这是**叙事剪辑**，不是字幕翻译。产出的 segments 是这条片子的**旁白脚本**，
不是把解说词逐句翻成中文。

硬规矩（照做，别发挥）：
- **开场三格，顺序固定**（账号所有者 2026-08-05 定，2026-09-25 重申「是全局的要求」）：
  ① **冷开场**：赢球那一刻（赛点落地／握拳／网前握手），窗口取源片**后段**，
     **narration 写空字符串**——这一段不配中文旁白。解说在这几秒喊出的那句写进
     **quote**：英文原文一行、中文翻译一行（`原文\\n中文`）；这几秒解说没开口就不写 quote。
  ② **一句落点**：这场球最硬的那件事，一句话，**不许复读封面钩子**（钩子已经印在封面上）。
  ③ **坐标**：已核实的北京时间日期＋自然时段（夜里／凌晨／清晨／上午／中午／下午／傍晚／晚上，不强制小时或分钟）、赛事、轮次。
  之后按时间顺序讲：首盘走势 → 中段转折 → 次盘/决胜盘 → 赛点 → 结局。
  **冷开场只是预告，结局要在正文里按时间顺序再放一遍。**
- **只挑 5~8 个节点**（含开场三格），每个节点一段，不要一个球一段、不要逐句翻译。
- **start 必须严格小于 end，且窗口至少 2 秒**。绝不允许 start==end，那是剪不出来的。
- start/end 用字幕里真实出现过的秒数附近，窗口尽量落在两个镜头切点之间，不跨切点。
- **旁白是叙事，不是解说词翻译**：别把解说词逐句翻成中文，旁白要回答「这段发生了什么」。
- **至少两段讲清某一球是怎么打的**：正手还是反手、直线还是斜线、上网截击、把对手调动到
  哪一侧、压在底线哪儿——**球路只用字幕里解说讲到的**，字幕里没讲的不编。
  统计数字（「非受迫失误三十四比十五」）不算球路；「首盘她连一个发球局都没保住」是走势，
  也不算球路。
- 除冷开场之外，旁白每段一句，40 字以内，中文。同一段不许既有 narration 又有 quote。
- **旁白里不许出现「解说说」**（账号所有者 2026-09-26）：不要转述「解说说，……」，直接讲那一拍；
  要引解说就放进 quote。
- 字幕里没有对应画面的内容（比如场外背景）挂到最接近它的、讲得通的画面段上。
- _why 一句话说明「这段旁白为什么挂在这个窗口」，方便终审核对。
- **_beat 标这一段服务叙事大纲的第几个 beat**：1、2、3 各对应大纲的第一、二、三段；
  开场三格（冷开场、落点、坐标）不属于任何 beat，写 0。同一个 beat 可以有好几段，
  **第一段**前面会插一张章节卡，所以 beat 的顺序要和大纲一致。

只输出一个 json 对象，字段 segments，每段 {start, end, narration, quote, _beat, _why}；
quote 只在冷开场这类不配旁白的段上写，其余段不写。"""


def _read_captions(path: Path) -> str:
    """captions.txt → 「秒数: 解说词」的文本块。"""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        t, text = line.split("\t", 1)
        try:
            out.append(f"{float(t):.2f}: {text.strip()}")
        except ValueError:
            continue
    return "\n".join(out)


def _read_cuts(probe_json: Path) -> list[float]:
    """probe.json → scene_cuts 列表。"""
    data = json.loads(probe_json.read_text(encoding="utf-8"))
    return [float(x) for x in data.get("scene_cuts") or []]


def draft_segments(chat: Chat, *, captions_text: str, cuts: list[float],
                   beats: str, home: str, away: str, hook: str = "") -> dict | None:
    user = (
        f"这场球：{home} vs {away}。\n"
        f"封面钩子（第 ② 格落点不许复读它）：{hook or '（还没有）'}\n"
        f"源片解说字幕（秒数: 解说词）：\n{captions_text}\n\n"
        f"镜头切点（秒）：{', '.join(f'{c:.2f}' for c in cuts) or '（没有切点数据）'}\n\n"
        f"这条片子的叙事大纲（beats）：\n{beats}\n"
    )
    data = chat.ask(SYSTEM, user, schema=SCHEMA, max_tokens=3000)
    if data is None:
        return None
    return clean_segments(data)


_CJK = re.compile(r"[\u4e00-\u9fff]")


def _bilingual_quote(item: object) -> str | None:
    """一条原声字幕：恰好两行，一行带汉字、一行不带（和 `build_match_reel._bilingual`
    同一个判法——原文可以是纯数字）。合格返回规整后的 `原文\n中文`，不合格返回 None。"""
    if not isinstance(item, str):
        return None
    rows = [x.strip() for x in item.split("\n") if x.strip()]
    if len(rows) != 2 or sorted(bool(_CJK.search(r)) for r in rows) != [False, True]:
        return None
    return "\n".join(rows)


def clean_segments(data: dict, *, min_duration: float = 2.0) -> dict:
    """机械兜底：把模型产出的废段拦掉，不让零长度/超短窗口流进下游。

    ⚠️ 第一次真跑就抓到了：模型会产出大量 start==end 的零长度段和「逐球解说」
    式旁白，直接喂 render 会废。prompt 里已经写了「至少 2 秒」，但**判据宁可
    双保险**——prompt 是软的，这道闸是硬的：start>=end 或窗口 <min_duration
    的段一律丢掉并出声，绝不静默放过。
    """
    segs = data.get("segments") or []
    kept, dropped, bad_quotes = [], 0, 0
    for s in segs:
        try:
            start, end = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            dropped += 1
            continue
        if end - start < min_duration:
            dropped += 1
            continue
        # _beat 只认 0~3 的整数（0＝不属于任何 beat）；别的值一律去掉——章节卡按它
        # 定位，一个错的 beat 号比没有更糟（卡会插到别的段前面）
        beat = s.get("_beat")
        if isinstance(beat, bool) or not isinstance(beat, int) or not 0 <= beat <= 3:
            s = {k: v for k, v in s.items() if k != "_beat"}
        # quote 只留在不配旁白的段上，而且要是「原文\n中文」两行——同一段两个人
        # 同时开口，闪避会把原声压掉（CLAUDE.md「精彩的原声解说」那节）；
        # 空的、单行的、跟旁白叠在一起的一律去掉并记数，别静默放过。
        # ⚠️ 合格的要包成**一元素列表** `["原文\n中文"]`：spec 里 quote 写成字符串走的是
        # 「按标点自动切」那条老路（`build_match_reel._quote_cues` 对字符串返回空），
        # 英文和中文会被切成先后两条单语字幕；列表里的一个元素才是「这一条排两行」
        # 的双语字幕（`explicit_quote_cues`）。存量 162 条带 quote 的段 161 条是列表。
        # ⚠️ 自动链里这份 quote 到不了 spec：`analyze_reel_visuals.apply_story` 只留带旁白的
        # 段，冷开场换成 MiniMax 自己的（钉了 `at` 的双语原声）；这里的清洗是给
        # `draft-segments-verify.yml` 和手工起草用的。自动链里真正的改善是：冷开场
        # narration 为空，就不会作为正文第 2 段留下来、把结局提前重放一遍。
        # schema 要的是字符串，模型偶尔回列表——列表里每一条照样要过双语那一关，
        # 不合格的整段 quote 记进 bad_quotes，不静默丢掉。只有空串／空列表是「这段没原声」。
        if "quote" in s:
            q = s.get("quote")
            items = q if isinstance(q, list) else [q]
            empty = all(isinstance(x, str) and not x.strip() for x in items) or q is None
            cleaned = [_bilingual_quote(x) for x in items]
            if (not empty and all(cleaned)
                    and not str(s.get("narration") or "").strip()):
                s = {**s, "quote": cleaned}
            else:
                if not empty:
                    bad_quotes += 1
                s = {k: v for k, v in s.items() if k != "quote"}
        kept.append(s)
    if dropped:
        # 出声：丢了几段要让终审知道，别把「模型没产」和「被闸拦了」混成一样
        print(f"[clean] 拦掉 {dropped} 段零长度/超短窗口（start>=end 或 <"
              f"{min_duration}s），剩 {len(kept)} 段")
    if bad_quotes:
        print(f"[clean] 去掉 {bad_quotes} 条不合格的 quote（不是「原文\\n中文」两行"
              "——一行英文、一行中文，或者和旁白叠在同一段）")
    return {"segments": kept, "_dropped": dropped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--captions", required=True, type=Path,
                    help="probe 产出的 captions.txt")
    ap.add_argument("--cuts", required=True, type=Path,
                    help="probe.json（读 scene_cuts）")
    ap.add_argument("--beats", required=True, help="叙事大纲（前段/中段/结局）")
    ap.add_argument("--hook", default="", help="封面钩子（两行用「／」连），落点那一格不许复读它")
    ap.add_argument("--home", default="主队")
    ap.add_argument("--away", default="客队")
    args = ap.parse_args()

    chat = Chat()
    if not chat.ready:
        print("[跳过] 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，退化出声")
        return 0
    print(f"通道 {chat.channel}")
    caps = _read_captions(args.captions)
    cuts = _read_cuts(args.cuts)
    if not caps:
        print("[跳过] captions 是空的——这场没拿到自动字幕，窗口退回人工")
        return 0
    draft = draft_segments(chat, captions_text=caps, cuts=cuts,
                           beats=args.beats, home=args.home, away=args.away,
                           hook=args.hook)
    if draft is None:
        print("[跳过] 模型这步没成（见日志），本条不起草窗口")
        return 0
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
