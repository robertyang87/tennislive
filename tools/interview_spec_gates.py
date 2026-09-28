"""赛后开麦两道**只读 spec** 的新闸：收尾卡那一句放不放得下一行、顶栏比分是不是赢家视角。

两道都坐在渲染入口（`build_interview_clip.check_takeaway` / `main()`），也都被
`tools/interview_preflight.py` 在 dispatch 之前跑一遍——**同一份判据，两处调用**，
不抄第二份。

## 一、`takeaway.*.point` 必须一行放得下

来路（2026-09-25/26，两次都是渲完抽帧才看见）：

    jodar-bublik  48a60760  「首秀赢完球 他先谢看台上的费德勒」   折成「…的费 ／ 德勒」
    deminaur      617db353  「落后一盘又被破发 他说只是一直顶住」 折成「…只是一 ／ 直顶住」

卡片是 Chromium 按 CSS 自动折行的。那两次的时候中文可以在任意两个字之间断，
所以一旦超出正文区，折点**只由宽度决定、不由词决定**。两次人工修法一样——收到一行
放得下。CLAUDE.md「卡片是给人扫的」那节写的也是这句：**一条要换行才排得下，就说明
它该被砍成两半或者删掉**。

量法和渲染同一把尺：`SmileySans-Oblique`（CSS 里的 TL Display SC）、
`TAKEAWAY_POINT_PX` 字号、每个字加 `TAKEAWAY_POINT_TRACKING` 的字距，可用宽＝画布
减去左右留白（这几个数就是 `takeaway_html` 的 CSS 用的那几个常量）。
**拿这把尺把上面两条的折点原样复现出来了**（「费 ／ 德勒」「一 ／ 直顶住」，当时的
CSS：任意字间可断、左边距 92、正文区 838px），改短之后的两版量出来 750px，一行放得下。

⭐ 2026-09-27 评审 I2／I3 之后卡片 CSS 变了（`build_interview_clip._CARD_WRAP`）：
`word-break:keep-all` 只在空格、标点、「·」处断，`text-wrap:balance` 把几行匀开，
一个子句本身比栏宽还长才由 `overflow-wrap:anywhere` 在字中间兜底劈开；左边距跟台头
收到 70，正文区 860px。`card_lines` 按这套规则排行——**全库 104 张卡加 4 条长名字
样例真渲过一遍（Chromium 逐字取行），一行／多行的判断 108 张全对，66 张多行卡的每一个
折点逐字一样**。所以报错里印的折点就是卡上会出现的那个。

全库量过（860px，合并 main 那一刻）：104 张卡里 62 张 `point` 超一行，全是已发的——
**已发的不重渲**，挂在 `data/legacy_interview_gates.json` 的 `takeaway_point_wrap`，只许减不许加；
豁免钉在当时那一句上（`points`），改写成另一句就回到正常的闸（`legacy_point_ok`）。
真要两行，在那张卡里写 `"_wrap_ok": "<为什么>"` 认领。

⭐ **「在空格处折成匀称的两行」不算合格**（2026-09-27 复审提的：keep-all 之后超宽卡里
45 张会在空格处干净地折开，剩下的才劈词）——账号所有者 2026-09-27 ~23:00Z 答复：
**一行放得下，写不下就写短**。闸本来就这么判，不放宽。

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
    # 只插一次：`production_preflight.check_request` 逐条请求都会走到这儿
    # （`test_check_request逐条调用不许把sys_path越撑越长`）。
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
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


#: `word-break:keep-all` 下的断点（Chromium 实测）：这些字**之后**可以断……
_BREAK_AFTER = frozenset(" ，。、；：？！…」』）》·")
#: ……这些字**之前**可以断（开引号、开括号跟着下一句走）
_BREAK_BEFORE = frozenset("「『（《")
#: 这些字前面不许断（闭引号、句读不许落到下一行行首）
_NO_BREAK_BEFORE = frozenset("」』）》，。、；：？！…")


def _chunks(text: str) -> list[str]:
    """按 keep-all 的断点把一句切成不可再分的块（块尾的空格留在块里——它挂在行尾不占宽）。"""
    out, cur = [], ""
    for i, ch in enumerate(text):
        if ch in _BREAK_BEFORE and cur and cur[-1] not in _BREAK_BEFORE:
            out.append(cur)
            cur = ""
        cur += ch
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch in _BREAK_AFTER and nxt and nxt not in _NO_BREAK_BEFORE and nxt != " ":
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out


def _fill(text: str, width: float, keep_all: bool) -> tuple[list[str], bool]:
    """贪心排行 → (行, 有没有在字中间劈过)。一块比栏还宽就逐字劈（`overflow-wrap:anywhere`）。"""
    lines, cur, forced = [], "", False
    for chunk in (_chunks(text) if keep_all else list(text)):
        if point_width((cur + chunk).rstrip()) <= width:
            cur += chunk
            continue
        if cur:
            lines.append(cur)
            cur = ""
        while len(chunk) > 1 and point_width(chunk.rstrip()) > width:
            k = len(chunk)
            while k > 1 and point_width(chunk[:k]) > width:
                k -= 1
            lines.append(chunk[:k])
            chunk = chunk[k:]
            forced = True
        cur = chunk
    if cur:
        lines.append(cur)
    return lines, forced


def card_lines(text: str, box: float | None = None, *, keep_all: bool = True) -> list[str]:
    """`.point` 这一句在卡上排成哪几行——照 `_CARD_WRAP` 那套 CSS 排。

    `keep_all=True`（现在的卡）：只在 `_chunks` 的断点处断；能断的时候 `text-wrap:balance`
    把宽度收到「行数不变的最窄」再排一遍（所以两行是匀的）；有一块得在字中间劈开时
    Chromium 不做 balance，照贪心排（实测：「脚踝崴了两周没喘过气她说的还 ／ 是准备好了」）。
    `keep_all=False`：2026-09-27 之前的卡——任意字间可断、不 balance（jodar-bublik、
    deminaur 那两张成片上的折点就是这么来的）。
    """
    box = float(point_box_px() if box is None else box)
    lines, forced = _fill(text, box, keep_all)
    if not keep_all or forced or len(lines) < 2:
        return lines
    lo, hi = 0.0, box
    for _ in range(30):
        mid = (lo + hi) / 2
        got, cut = _fill(text, mid, keep_all)
        if len(got) == len(lines) and not cut:
            hi = mid
        else:
            lo = mid
    return _fill(text, hi, keep_all)[0]


def legacy_point_ok(slug: str, which: str, text: str) -> bool:
    """这张卡是不是豁免表里那张**原样没动**的存量：slug 在表里，而且这张卡的 `point`
    还是量的那一刻那一句（`points`）。改写成另一句（哪怕照样超一行）就回到正常的闸——
    和 `frozen_tail_short` 钉 `end` 同一个道理，「只许减不许加」要管住内容，不只管住名字。"""
    table = legacy_table("takeaway_point_wrap")
    if slug not in (table.get("slugs") or ()):
        return False
    return ((table.get("points") or {}).get(slug) or {}).get(which) == text


def takeaway_point_problems(spec: dict) -> list[str]:
    """每张卡的 `point` 超出一行 → 一条问题（带折点）。豁免表（钉着原句）和 `_wrap_ok` 认领除外。"""
    slug = str(spec.get("slug") or "")
    box = point_box_px()
    out = []
    for which, card in (spec.get("takeaway") or {}).items():
        if not isinstance(card, dict) or not str(card.get("point") or "").strip():
            continue
        if str(card.get("_wrap_ok") or "").strip():
            continue
        text = str(card["point"])
        if legacy_point_ok(slug, which, text):
            continue
        if (w := point_width(text)) > box:
            lines = card_lines(text, box)
            shown = " ／ ".join(ln.strip() for ln in lines)
            _, cut = _fill(text, box, True)
            how = ("有一段没有空格或标点可断，会在字中间劈开" if cut
                   else "会在空格／标点处折开")
            out.append(
                f"`takeaway.{which}.point` 量出来 {w:.0f}px，卡上一行只有 {box}px，"
                f"{how}，排成 {len(lines)} 行「{shown}」。"
                "收到一行放得下（jodar-bublik / deminaur 两次都是这么修的）；"
                "真要两行就在这张卡里写 `_wrap_ok` 说清为什么")
    return out


#: 一盘：`6-4`，后面可以跟一个抢七注脚——只写输家小分的 `7-6(5)`，也可能写全的
#: `7-6(7-5)` / `7-6（10-8）`。**注脚整个吃掉，不许被当成另一盘**：第一版只剥 `(\d+)`，
#: `6-7(5-7) 6-4 6-4` 里的 `5-7` 会被数成赢家丢的第二盘，2:2 → 误判成输家视角。
#: 方括号要看它**站在哪儿**（`_bracket_notes`）：单独一格、分数到 10 的 `[10-8]` 是
#: 抢十代替的决胜盘，算一盘；紧贴在一盘后面的 `6-7[5-7]`、或者到不了 10 分的 `[5-7]`
#: 是那一盘的抢七注脚，不算（review 那条：原来一律算一盘，`6-7[5-7] 6-4 6-4` 数成 2:2 误红）。
_SET = re.compile(r"(\d+)\s*[-–:]\s*(\d+)(\s*[(（]\s*\d+(?:\s*[-–:]\s*\d+)?\s*[)）])?")
_BRACKET = re.compile(r"(\s*)[\[［]\s*(\d+)\s*([-–:])\s*(\d+)\s*[\]］]")
_RETIRED = re.compile(r"ret\.?|退赛|w\.?/?o\.?|walkover|不战而胜", re.I)


#: 复审第三轮 nit：盘分和方括号一样认冒号（`7:6[10:8] 6:4`）——原来 `_BRACKET` 认冒号、
#: 这两个不认，`6:7[8:10]` 的注脚被当成单独一盘（抢七打到 10-8 是合法的），盘数就错了。
_PREV_SET = re.compile(r"(\d+)\s*[-–:]\s*(\d+)\s*$")


def _bracket_notes(score: str) -> str:
    """方括号 → 注脚还是一盘：紧贴前一盘（中间没有空格）、**而且前一盘是抢七盘
    （{7,6}）或 `1-0` 那种抢十占位**的，改写成圆括号注脚，交给 `_SET` 整个吃掉
    （`6-7[5-7]` 是那一盘的抢七小分，`1-0[10-8]` 和 `1-0(10-8)` 一样算一盘）；
    其余一律按单独一格判——到不了 10 分的只可能是抢七小分，删掉；到 10 分的是抢十盘，
    原样留着（`_SET` 会把它当一盘数）。

    ⚠️ 复审 nit（2026-09-27）：原来「紧贴」就一律当注脚，`6-4 3-6[10-8]`（抢十盘直接贴在
    前一盘后面）被当成 3-6 那一盘的注脚，数成 1:1、报成输家视角——假红。"""
    def one(m: re.Match) -> str:
        if m.start() > 0 and not m.group(1):
            prev = _PREV_SET.search(score[:m.start()])
            if prev and {int(prev.group(1)), int(prev.group(2))} in ({6, 7}, {0, 1}):
                return f"({m.group(2)}{m.group(3)}{m.group(4)})"
        if max(int(m.group(2)), int(m.group(4))) < 10:
            return m.group(1)
        return m.group(0)
    return _BRACKET.sub(one, score)


def completed_sets(score: str) -> list[tuple[int, int]]:
    """`push.score` → 打完的盘 [(赢家这边, 对面)]。抢七注脚不算盘；`1-0(10-8)` 这种
    拿抢十代替决胜盘的写法算一盘。"""
    out = []
    for a, b, tb in _SET.findall(_bracket_notes(score)):
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
