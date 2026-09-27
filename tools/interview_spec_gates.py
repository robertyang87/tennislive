"""赛后开麦两道**只读 spec** 的新闸：收尾卡那一句放不放得下一行、顶栏比分是不是赢家视角。

两道都坐在渲染入口（`build_interview_clip.check_takeaway` / `main()`），也都被
`tools/interview_preflight.py` 在 dispatch 之前跑一遍——**同一份判据，两处调用**，
不抄第二份。

## 一、`takeaway.*.point` 必须一行放得下

来路（2026-09-25/26，两次都是渲完抽帧才看见）：

    jodar-bublik  48a60760  「首秀赢完球 他先谢看台上的费德勒」   折成「…的费 ／ 德勒」
    deminaur      617db353  「落后一盘又被破发 他说只是一直顶住」 折成「…只是一 ／ 直顶住」

卡片是 Chromium 按 CSS 自动折行的：中文可以在任意两个字之间断，所以一旦超出
正文区，折点**只由宽度决定、不由词决定**。两次人工修法一样——收到一行放得下。
CLAUDE.md「卡片是给人扫的」那节写的也是这句：**一条要换行才排得下，就说明它该被
砍成两半或者删掉**。

量法和渲染同一把尺：`SmileySans-Oblique`（CSS 里的 TL Display SC）、
`TAKEAWAY_POINT_PX` 字号、每个字加 `TAKEAWAY_POINT_TRACKING` 的字距，可用宽＝画布
减去左右留白（这几个数就是 `build_takeaway_card` 的 CSS 用的那几个常量）。
**拿这把尺把上面两条的折点原样复现出来了**（「费 ／ 德勒」「一 ／ 直顶住」），
改短之后的两版量出来 750px，一行放得下。

全库量过：103 张卡里 61 张 `point` 超一行（折点几乎全落在词中间：「现 ／ 在」
「菲律 ／ 宾人」「辛 ／ 辛那提」）——**已发的不重渲**，挂在
`data/legacy_interview_gates.json` 的 `takeaway_point_wrap`，只许减不许加。
真要两行（比如有意让折点落在空格上），在那张卡里写 `"_wrap_ok": "<为什么>"` 认领。

## 二、`push.score` 必须是赢家视角

顶栏印的是「赢家 比分 输家」（`header_runs`），比分照着输家视角抄就等于用排版
宣称输的人赢了。来路：`zheng-rybakina-us-open-2026-qf-presser` 857f1fbc 之前
写着 `winner=莱巴金娜`、`push.score=6-3 1-6 4-6`（郑钦文视角）。

⚠️ 没有直接用 `reel_facts.result_direction_problem`：那道闸为「赛场之上」收得
很窄（「赢家一个完赛盘都没拿」才算），**恰好放过了上面这条**——三盘两胜里输家
视角是 1:2，赢家拿了一盘。采访这条线的比分只有一种写法（赢家在前），所以直接
要求「完赛盘里赢家拿的盘数多于输家」；退赛（Ret./退赛/w/o）不判。
全库 102 条 `push.score` 扫过，零命中；上面那条 857f1fbc 之前的版本命中。
认领口：`_score_orientation_why`。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "data" / "legacy_interview_gates.json"
POINT_FONT = ROOT / "assets" / "fonts" / "SmileySans-Oblique.ttf"


def _clip():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_interview_clip as clip  # noqa: PLC0415
    return clip


def legacy_table(kind: str) -> dict:
    """`data/legacy_interview_gates.json` 里某一张豁免表的整份内容（`slugs` 之外可能还记着量的数）。"""
    try:
        data = json.loads(LEGACY.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    table = data.get(kind)
    return table if isinstance(table, dict) else {}


def legacy(kind: str) -> frozenset[str]:
    """`data/legacy_interview_gates.json` 里某一张豁免表（只许减不许加）。"""
    return frozenset(legacy_table(kind).get("slugs") or ())


_POINT_FONT_CACHE: dict[int, object] = {}


def point_width(text: str) -> float:
    """`.point` 这一行在卡片上画出来多宽（px）：字形 advance ＋ 每个字的字距。"""
    clip = _clip()
    size = clip.TAKEAWAY_POINT_PX
    if size not in _POINT_FONT_CACHE:
        from PIL import ImageFont  # noqa: PLC0415
        _POINT_FONT_CACHE[size] = ImageFont.truetype(str(POINT_FONT), size)
    return (_POINT_FONT_CACHE[size].getlength(text)
            + clip.TAKEAWAY_POINT_TRACKING * len(text))


def point_box_px() -> int:
    clip = _clip()
    return clip.CANVAS_W - clip.TAKEAWAY_PAD_LEFT - clip.TAKEAWAY_PAD_RIGHT


def greedy_break(text: str) -> tuple[str, str]:
    """Chromium 在哪儿折这一行（中文任意两字之间可断，贪心排满）。只用来把折点印出来。"""
    box = point_box_px()
    k = len(text)
    while k > 0 and point_width(text[:k].rstrip()) > box:
        k -= 1
    return text[:k], text[k:]


def takeaway_point_problems(spec: dict) -> list[str]:
    """每张卡的 `point` 超出一行 → 一条问题（带折点）。豁免表和 `_wrap_ok` 认领除外。"""
    slug = str(spec.get("slug") or "")
    if slug in legacy("takeaway_point_wrap"):
        return []
    box = point_box_px()
    out = []
    for which, card in (spec.get("takeaway") or {}).items():
        if not isinstance(card, dict) or not str(card.get("point") or "").strip():
            continue
        if str(card.get("_wrap_ok") or "").strip():
            continue
        text = str(card["point"])
        if (w := point_width(text)) > box:
            head, tail = greedy_break(text)
            out.append(
                f"`takeaway.{which}.point` 量出来 {w:.0f}px，卡上一行只有 {box}px，"
                f"会被 Chromium 折成「{head} ／ {tail}」——折点只看宽度不看词。"
                "收到一行放得下（jodar-bublik / deminaur 两次都是这么修的）；"
                "真要两行就在这张卡里写 `_wrap_ok` 说清为什么")
    return out


#: 一盘：`6-4`，后面可以跟一个抢七注脚——只写输家小分的 `7-6(5)`，也可能写全的
#: `7-6(7-5)` / `7-6（10-8）`。**注脚整个吃掉，不许被当成另一盘**：第一版只剥 `(\d+)`，
#: `6-7(5-7) 6-4 6-4` 里的 `5-7` 会被数成赢家丢的第二盘，2:2 → 误判成输家视角。
#: 方括号不算注脚：`[10-8]` 是抢十代替的决胜盘，本来就该算一盘。
_SET = re.compile(r"(\d+)\s*[-–]\s*(\d+)(\s*[(（]\s*\d+(?:\s*[-–:]\s*\d+)?\s*[)）])?")
_RETIRED = re.compile(r"ret\.?|退赛|w\.?/?o\.?|walkover|不战而胜", re.I)


def completed_sets(score: str) -> list[tuple[int, int]]:
    """`push.score` → 打完的盘 [(赢家这边, 对面)]。抢七注脚不算盘；`1-0(10-8)` 这种
    拿抢十代替决胜盘的写法算一盘。"""
    out = []
    for a, b, tb in _SET.findall(score):
        a, b = int(a), int(b)
        if max(a, b) >= 6 or (tb and {a, b} == {0, 1}):
            out.append((a, b))
    return out


def score_orientation_problem(spec: dict) -> str | None:
    """`push.score` 不是赢家视角 → 一句话；没写比分、退赛、认领过都放行。"""
    score = str((spec.get("push") or {}).get("score") or "").strip()
    if not score or _RETIRED.search(score):
        return None
    if str(spec.get("_score_orientation_why") or "").strip():
        return None
    done = completed_sets(score)
    won = sum(a > b for a, b in done)
    lost = sum(b > a for a, b in done)
    if done and won <= lost:
        return (
            f"`push.score`「{score}」里赢家 {spec.get('winner') or '?'} 只拿了 {won} 盘、"
            f"输家拿了 {lost} 盘——顶栏印的是「赢家 比分 输家」，这串比分是输家视角"
            "（zheng-rybakina 857f1fbc 之前就是这么写的）。按赢家视角重写；"
            "真是特殊赛制，写 `_score_orientation_why` 认领")
    return None
