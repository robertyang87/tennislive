#!/usr/bin/env python3
"""用大模型（DeepSeek）评一条片子的「内容质量」三样——机械测试测不了的那三样。

CLAUDE.md 里白纸黑字写着「有吸引力……这条没有测试，是故意的：机械挡不住」。
那是**机械规则**挡不住；换成一个真的读得懂中文的大模型，它至少能给出一个
**有理由的判断**——不是「守住了」的保证，而是「照着这三个判据读过一遍」的证据。

评三样（判据都从 CLAUDE.md / docs 里抄，不另造）：

  1. **钩子剧情跌宕**：讲的是「过程」（几比几落后、救了几个赛点、连丢几局），
     不是「身份」（排名/年龄/国籍/冠军——那些海报别处已经印着了）。
  2. **封面情绪对题**：这条片子讲什么，封面就要是那个情绪（逆转→扛住那一刻，
     夺冠→捧杯；拿不到就示意，不许拿一张情绪不对的照片凑）。
  3. **小红书风格**：钩子开场 → 单主线 → 互动提问结尾，正文不超 1000 字、
     不堆 emoji、不以通稿导语开头。

⚠️ **这是 judge，不是闸**：默认只打印评级和理由，退出码恒 0（它给的是「该
不该改」的证据，不是「能不能发」的裁决）。要不要把它抬成硬闸是口径选择。

⚠️ **没配密钥就跳过并出声**——退化不许静默（仓库里那条老规矩）。配了
`DEEPSEEK_API_KEY` 才真的问模型。

用法：
    python tools/check_content_quality.py --slug shang-rublev
    python tools/check_content_quality.py --spec specs/reels/x.json
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
        "hook_drama": {"type": "object", "properties": {
            "ok": {"type": "boolean"},
            "why": {"type": "string"},
        }},
        "cover_emotion": {"type": "object", "properties": {
            "ok": {"type": "boolean"},
            "why": {"type": "string"},
        }},
        "xhs_style": {"type": "object", "properties": {
            "ok": {"type": "boolean"},
            "why": {"type": "string"},
        }},
    },
}

SYSTEM = """你是一个网球短视频账号的内容质检员。账号的栏目是「赛场之上」（原创比赛复盘）。
你会收到一条片子的封面钩子、封面文案和（如果有）小红书正文。按下面三条判据逐条评，每条给 ok（true/false）和一句 why（用中文，说清问题或好在哪）：

1. 钩子剧情跌宕：钩子讲的是「过程」（几比几落后、救了几个赛点、连丢几局、逆转），
   而不是把「身份」摆在一起（排名/年龄/国籍/冠军——那些海报别处已经印着，钩子再写是白占字数）。
2. 封面情绪对题：这条片子讲什么，封面就要是那个情绪（逆转→扛住的那一刻，夺冠→捧杯）。
   情绪对不上（比如讲逆转却用一张无关的照片）判 false。
3. 小红书风格：钩子开场、单主线、互动提问结尾；不堆 emoji、不以通稿导语开头、不写空话。

只输出一个 json 对象，字段名固定为 hook_drama / cover_emotion / xhs_style，每项里是 ok 和 why。"""


def load_spec(slug: str | None, spec_path: str | None) -> dict:
    if spec_path:
        p = Path(spec_path)
    elif slug:
        p = Path(f"specs/reels/{slug}.json")
    else:
        raise SystemExit("要给 --slug 或 --spec")
    if not p.is_file():
        raise SystemExit(f"找不到 spec：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def ask_quality(chat: Chat, spec: dict) -> dict | None:
    cover = spec.get("cover") or {}
    hook = "\n".join(str(x) for x in (cover.get("hook") or []))
    # 小红书正文：reel 线的正文落在 specs/reels/<slug>.xhs.txt，和 json 同名。
    xhs = ""
    slug = spec.get("slug") or ""
    if slug:
        xhs_path = Path(f"specs/reels/{slug}.xhs.txt")
        if xhs_path.is_file():
            xhs = xhs_path.read_text(encoding="utf-8")[:1200]
    user = (
        f"封面钩子：\n{hook or '（没有 hook）'}\n\n"
        f"封面文案（winner/result/title/sub）：\n"
        f"  赢家 {cover.get('winner')} 比分 {cover.get('result')}\n"
        f"  标题 {cover.get('title') or cover.get('hook')}\n"
        f"  副标 {cover.get('sub') or ''}\n\n"
        f"小红书正文（截取）：\n{xhs or '（没有 xhs.txt）'}"
    )
    return chat.ask(SYSTEM, user, schema=SCHEMA, max_tokens=1200)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", help="specs/reels/<slug>.json")
    ap.add_argument("--spec", help="spec 路径（不给 slug 时用）")
    args = ap.parse_args()

    spec = load_spec(args.slug, args.spec)
    chat = Chat()
    if not chat.ready:
        print("[跳过] 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，"
              "这一步没法评——退化出声，不是「评过了没问题」")
        return 0

    print(f"通道 {chat.channel}")
    verdict = ask_quality(chat, spec)
    if verdict is None:
        print("[跳过] 模型这步没成（见日志），本条不判")
        return 0

    for key, label in (("hook_drama", "钩子剧情跌宕"),
                       ("cover_emotion", "封面情绪对题"),
                       ("xhs_style", "小红书风格")):
        item = verdict.get(key) or {}
        mark = "ok" if item.get("ok") else "不合格"
        print(f"[{mark}] {label}：{item.get('why', '（模型没给理由）')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
