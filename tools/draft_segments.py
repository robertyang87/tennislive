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
                    "_why": {"type": "string"},
                },
                "required": ["start", "end", "narration"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}

SYSTEM = """你是网球短视频账号「网球时差」的剪辑，给一条 60~90 秒的赛后复盘片排时间轴。

给你一份**带时间码的源片解说字幕**（`秒数: 解说词`）和**镜头切点**（秒数）。
你要产出 segments：挑出这条片子要讲的**关键节点**，每个节点挂到源片正确的时间窗口上。

⚠️ 这是**叙事剪辑**，不是字幕翻译。产出的 segments 是这条片子的**旁白脚本**，
不是把解说词逐句翻成中文。

硬规矩（照做，别发挥）：
- **只挑 5~8 个节点**，覆盖一条复盘片的完整叙事弧：
  冷开场（最抓人的那一分/赛点/逆转瞬间）→ 坐标（谁在哪儿打、第几轮）→
  首盘走势 → 中段转折 → 次盘/决胜盘 → 赛点 → 结局/落点。
  每个节点一段，不要一个球一段、不要逐句翻译。
- **start 必须严格小于 end，且窗口至少 2 秒**。绝不允许 start==end，那是剪不出来的。
- start/end 用字幕里真实出现过的秒数附近，窗口尽量落在两个镜头切点之间，不跨切点。
- **旁白是叙事，不是解说词翻译**：写「首盘她连一个发球局都没保住」，不要写
  「她压线」「哦球出界了」这种逐球解说。旁白要能回答「这段走势发生了什么」。
- 旁白每段一句，40 字以内，中文。
- 字幕里没有对应画面的内容（比如场外背景）挂到最接近它的、讲得通的画面段上。
- _why 一句话说明「这段旁白为什么挂在这个窗口」，方便终审核对。

只输出一个 json 对象，字段 segments，每段 {start, end, narration, _why}。"""


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
                   beats: str, home: str, away: str) -> dict | None:
    user = (
        f"这场球：{home} vs {away}。\n"
        f"源片解说字幕（秒数: 解说词）：\n{captions_text}\n\n"
        f"镜头切点（秒）：{', '.join(f'{c:.2f}' for c in cuts) or '（没有切点数据）'}\n\n"
        f"这条片子的叙事大纲（beats）：\n{beats}\n"
    )
    data = chat.ask(SYSTEM, user, schema=SCHEMA, max_tokens=3000)
    if data is None:
        return None
    return clean_segments(data)


def clean_segments(data: dict, *, min_duration: float = 2.0) -> dict:
    """机械兜底：把模型产出的废段拦掉，不让零长度/超短窗口流进下游。

    ⚠️ 第一次真跑就抓到了：模型会产出大量 start==end 的零长度段和「逐球解说」
    式旁白，直接喂 render 会废。prompt 里已经写了「至少 2 秒」，但**判据宁可
    双保险**——prompt 是软的，这道闸是硬的：start>=end 或窗口 <min_duration
    的段一律丢掉并出声，绝不静默放过。
    """
    segs = data.get("segments") or []
    kept, dropped = [], 0
    for s in segs:
        try:
            start, end = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            dropped += 1
            continue
        if end - start < min_duration:
            dropped += 1
            continue
        kept.append(s)
    if dropped:
        # 出声：丢了几段要让终审知道，别把「模型没产」和「被闸拦了」混成一样
        print(f"[clean] 拦掉 {dropped} 段零长度/超短窗口（start>=end 或 <"
              f"{min_duration}s），剩 {len(kept)} 段")
    return {"segments": kept, "_dropped": dropped}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--captions", required=True, type=Path,
                    help="probe 产出的 captions.txt")
    ap.add_argument("--cuts", required=True, type=Path,
                    help="probe.json（读 scene_cuts）")
    ap.add_argument("--beats", required=True, help="叙事大纲（前段/中段/结局）")
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
                           beats=args.beats, home=args.home, away=args.away)
    if draft is None:
        print("[跳过] 模型这步没成（见日志），本条不起草窗口")
        return 0
    print(json.dumps(draft, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
