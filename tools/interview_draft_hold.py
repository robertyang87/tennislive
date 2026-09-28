#!/usr/bin/env python3
"""「赛后开麦」草稿停着没停着——`promote_interview_draft` 和 auto-render 探针共用的一个判据。

来路（2026-09-28 量的）：`interview-auto-render.yml` 的「没活就早退」原来按**文件数**数草稿
（`find specs/interviews -name '*.draft.json' | wc -l`）。main 上那 4 份草稿自 8/30 起一份都
提升不了——两份挂着 `manual_review_required`（一份等同场集锦的 lead_in、一份 `zh` 被刻意
清空等官方源片），两份是 8/29 温斯顿-塞勒姆的四分之一决赛、早出了 promote 的赛果回看窗口
——可草稿数恒为 4，于是**每一趟**都跑满全量（setup-python、字体、pip、PO-token docker、
promote 抓四天赛果），最后「提升 0 条 / 跳过 4 条」、什么都不提交。9/25~9/28 那 60 趟里
39 趟是这种空转（job 平均 98 秒，早退一趟 9~16 秒）。

所以「这份草稿全量那一趟动不动得了」只判一次、写在这儿：
  * `promote_interview_draft.promote_all` 先过它，停着的直接记跳过、**不去抓赛果**；
  * 探针（系统 python3，没装依赖——这个模块只许用标准库）拿**同一个函数**数「能动的」，
    停着的印一行进日志和 run 摘要，不叫醒全量 job。
标记一去掉（人改完 `zh`、删掉 `manual_review_required`），下一趟探针就数得到它——
没有任何缓存记着「它停过」。

判据全是**不联网**就判得了的：读不了、挂着人工复核、没有译文、来源身份没核成本场
on_court、认不出受访者、建草稿已超出赛果回看窗口。赛果里找不找
得到这场是联网才知道的，那一类照旧算「能动」、交给全量那一趟去查。

用法（探针）：
    python3 tools/interview_draft_hold.py --count-actionable
        stdout：能动的草稿数；stderr：停着的那几份（首行一句总括，其后每份一行）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs" / "interviews"

# 赛果往回看几天（`promote_interview_draft._collect_digests` 用的就是这个数，单一出处在这儿）。
# 赛后采访就是这一两天做的，草稿也超不过候选窗口；3 天是给「夜场跨日 + 赛果源慢半天」留的余量。
DIGEST_DAYS_BACK = 3

# 建草稿那一刻，这场球已经打完：它在赛果里的日子（北京）≤ 建草稿那天（北京）。
# promote 只翻「今天往前 DIGEST_DAYS_BACK 天」，所以建草稿那天早于这个窗口的，
# promote 再也查不到——再多留 1 天余量（赛果按开赛时刻归日，夜场跨日那一下），
# 宁可多空转一天，不许把一份还查得到的草稿停掉。
STALE_AFTER_DAYS = DIGEST_DAYS_BACK + 1

#: `draft_interview_spec` 建草稿时盖的时刻（UTC，ISO 8601）。老草稿没有这个键就不按年龄停。
DRAFTED_AT_KEY = "_drafted_at"

_BEIJING = timedelta(hours=8)


def beijing_today() -> date:
    return (datetime.now(timezone.utc) + _BEIJING).date()


def _surname_en(full: str) -> str:
    """英文全名取姓（feed 里两种形状：`Zverev A.` 姓在前、`Alexander Zverev`
    姓在最后）。缩写名（最后一个词是单字母）取第一个词——reel 的 slug_for 踩过
    同一个坑。"""
    words = re.sub(r"[.]", "", (full or "")).strip().split()
    if not words:
        return ""
    last = words[-1]
    if len(last) == 1:  # "Zverev A." → 姓在开头
        return words[0].casefold()
    return last.casefold()


def interviewee_surname(draft: dict) -> tuple[str, bool]:
    """草稿 → (受访者的姓（小写）, 是不是从标题猜的)。主路读 `_interviewee_en`；
    老草稿没有就退回标题猜（`promote_interview_draft._draft_surname` 负责出声）。"""
    who = (draft.get("_interviewee_en") or "").strip()
    if who:
        return _surname_en(who), False
    title = str(draft.get("source_title") or "")
    m = re.search(r"([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?$",
                  title.split("Interview")[0].strip())
    return (m.group(1) if m else "").casefold(), True


def drafted_day(draft: dict) -> date | None:
    """建草稿那天（北京）。没盖章或读不懂就 None——不按年龄停（宁可多跑一趟全量）。"""
    raw = str(draft.get(DRAFTED_AT_KEY) or "").strip()
    if not raw:
        return None
    try:
        at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return (at.astimezone(timezone.utc) + _BEIJING).date()


def draft_hold_reason(draft: dict, *, today: date | None = None) -> str:
    """这份草稿为什么停着（全量那一趟也动不了它）；能动就返回空串。

    措辞沿用 promote 原来的跳过原因——日志和 run 摘要里认的是同一句话。
    ⚠️ 人工复核排在「没译文」前面：`wang-vekic-singapore-2026-r1-interview` 的 `zh` 是
    被**刻意**清空的，它自己的 `manual_review_required` 里写着「这不是『翻译没成』」——
    原来的顺序先报「翻译没成」，把人写下的真原因盖掉了。
    """
    if draft.get("manual_review_required"):
        return f"已标记人工复核（{draft['manual_review_required']}），不提升"
    if not (draft.get("_zh_draft") or draft.get("zh")):
        return "连译文草稿都没有（翻译没成），等终审"
    verification = draft.get("source_verification") or {}
    if verification.get("status") != "verified" or \
            verification.get("detected_type") != "on_court":
        return "来源身份尚未确认是本场 on_court（不提升）"
    if not interviewee_surname(draft)[0]:
        return "认不出受访者（等终审）"
    made = drafted_day(draft)
    today = today or beijing_today()
    if made is not None and (age := (today - made).days) > STALE_AFTER_DAYS:
        return (f"建于 {made}（北京，{age} 天前），已过 promote 的赛果回看窗口"
                f"（近 {DIGEST_DAYS_BACK + 1} 天）——再也查不到这场，等人处理"
                "（删草稿，或核好赛果另写人工请求）")
    return ""


def scan(specs: Path | None = None, *, today: date | None = None
         ) -> tuple[list[tuple[Path, dict]], list[tuple[Path, str]]]:
    """扫 `specs/interviews/*.draft.json` → (能动的 [(路径, 草稿)], 停着的 [(路径, 原因)])。"""
    actionable: list[tuple[Path, dict]] = []
    held: list[tuple[Path, str]] = []
    for path in sorted((specs or SPECS).glob("*.draft.json")):
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            held.append((path, "读不了"))
            continue
        if not isinstance(draft, dict):
            held.append((path, "读不了"))
            continue
        why = draft_hold_reason(draft, today=today)
        if why:
            held.append((path, why))
        else:
            actionable.append((path, draft))
    return actionable, held


def _clip(text: str, n: int = 90) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--count-actionable", action="store_true",
                    help="stdout 印能动的草稿数；停着的印在 stderr")
    ap.add_argument("--specs", type=Path, default=None, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    actionable, held = scan(args.specs)
    if held:
        names = "、".join(p.name.removesuffix(".draft.json") for p, _ in held)
        print(f"[草稿停着] {len(held)} 份全量那一趟也动不了，不叫醒全量 job：{names}"
              "（标记去掉／改好的，下一趟探针就数得到）", file=sys.stderr)
        for path, why in held:
            print(f"  {path.name}：{_clip(why)}", file=sys.stderr)
    if args.count_actionable:
        print(len(actionable))
    else:
        for path, _ in actionable:
            print(path.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
