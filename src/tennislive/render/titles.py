"""标题全自动生成与选择：用可解释评分挑当天最值得点击的故事."""

from __future__ import annotations

from dataclasses import dataclass

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from .common import is_chinese_involved, match_round_display
from .rating import find_upset, match_score, top_results, top_schedule
from .story import china_summary, chinese_side_won, is_chinese_player


@dataclass(frozen=True)
class _Candidate:
    text: str
    score: int
    kind: str


def _cn_side(players) -> bool:
    return any(is_chinese_player(p) for p in players)


def _flat_round(m) -> str:
    return (match_round_display(m) or "").replace("·", "")


def _cn_match_headline(m) -> str | None:
    w = m.winner_players()
    if not w:
        return None
    r = _flat_round(m)
    if chinese_side_won(m):
        cn_winner = next((p for p in w if is_chinese_player(p)), w[0])
        if r.endswith("决赛") and "半" not in r and "四" not in r:
            return f"{player_zh(cn_winner.name)}夺冠！"
        return f"{player_zh(cn_winner.name)}晋级{r or '下一轮'}"
    loser = next(
        (p for p in (m.loser_players() or []) if is_chinese_player(p)), None
    )
    if loser is not None:
        return f"{player_zh(loser.name)}止步{r or '本轮'}"
    return None


def _cn_candidates(digest: Digest) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for m in digest.results:
        if not is_chinese_involved(m):
            continue
        text = _cn_match_headline(m)
        if not text:
            continue
        positive = chinese_side_won(m)
        base = 300 if positive and m.is_singles else 215 if positive else 70
        candidates.append(_Candidate(text, base + match_score(m), "china"))

    for m in digest.schedule:
        if not (is_chinese_involved(m) and m.is_singles):
            continue
        p = next((p for p in m.home + m.away if is_chinese_player(p)), None)
        if p is None:
            continue
        t = fmt_time_beijing(m.start_utc)
        when = f"{t}出战" if t != "待定" else "今日出战"
        candidates.append(
            _Candidate(f"{player_zh(p.name)}{when}", 270 + match_score(m), "china")
        )

    summary = china_summary(digest)
    if summary:
        wins = sum(
            1 for m in digest.results if is_chinese_involved(m) and chinese_side_won(m)
        )
        candidates.append(_Candidate(summary, 230 + wins * 18, "china-summary"))
    return candidates


def cn_headline(digest: Digest) -> str | None:
    candidates = _cn_candidates(digest)
    return max(candidates, key=lambda c: c.score).text if candidates else None


def upset_headline(digest: Digest) -> str | None:
    m = find_upset(digest.results)
    if m is None:
        return None
    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w or not l:
        return None
    return f"爆冷！{player_zh(w.name)}掀翻{player_zh(l.name)}"


def star_headline(digest: Digest) -> str | None:
    for m in top_results([x for x in digest.results if x.is_singles], 3):
        if is_chinese_involved(m):
            continue  # 中国角度另有候选
        w = m.winner_players()
        if w:
            from .common import group_by_tournament

            g = group_by_tournament([m])[0]
            r = _flat_round(m)
            if r == "决赛":
                return f"{player_zh(w[0].name)}问鼎{g.name_zh}"
            return f"{player_zh(w[0].name)}晋级{g.name_zh}{r or ''}"
    tonight = top_schedule([x for x in digest.schedule if x.is_singles], 1)
    if tonight:
        m = tonight[0]
        a = player_zh(m.home[0].name)
        b = player_zh(m.away[0].name)
        return f"今晚焦点：{a}对阵{b}"
    return None


def title_candidates(digest: Digest) -> list[str]:
    """去重后的候选列表，按故事价值评分排序."""
    candidates = _cn_candidates(digest)
    upset = upset_headline(digest)
    if upset:
        m = find_upset(digest.results)
        candidates.append(_Candidate(upset, 200 + (match_score(m) if m else 0), "upset"))
    star = star_headline(digest)
    if star:
        candidates.append(_Candidate(star, 150, "star"))

    seen: set[str] = set()
    out: list[str] = []
    for candidate in sorted(candidates, key=lambda c: c.score, reverse=True):
        h = candidate.text
        if h and h not in seen:
            seen.add(h)
            out.append(h)
    if not out:
        out.append("每日赛程赛果速览")
    return out


def cover_highlights(digest: Digest) -> tuple[str, str]:
    """Main cover hook plus a distinct secondary proof point."""
    candidates = title_candidates(digest)
    primary = candidates[0]
    secondary = next((h for h in candidates[1:] if h != primary), "")
    if not secondary:
        secondary = "昨夜赛果与今晚重点，一页看懂"
    return primary, secondary


def pick_headline_auto(digest: Digest) -> str:
    return title_candidates(digest)[0]


def flash_headline(m) -> str:
    """单场比赛的闪发标题，如 '郑钦文晋级！雅典公开赛八强'."""
    from .common import group_by_tournament

    g = group_by_tournament([m])[0]
    r = _flat_round(m)
    w = (m.winner_players() or [None])[0]
    l = (m.loser_players() or [None])[0]
    if not w:
        return f"{g.name_zh}{r}战报"
    is_final = r.endswith("决赛") and "半" not in r and "四" not in r
    cn_won = _cn_side(m.winner_players() or [])
    cn_lost = _cn_side(m.loser_players() or [])
    if cn_won:
        # 双打时用中国球员的名字打头
        cn_w = next(
            (p for p in (m.winner_players() or []) if _cn_side([p])), w
        )
        if is_final:
            return f"{player_zh(cn_w.name)}夺冠！{g.name_zh}登顶"
        return f"{player_zh(cn_w.name)}晋级！赢下{g.name_zh}{r or '本轮'}"
    if cn_lost and l is not None:
        return f"{player_zh(l.name)}止步{g.name_zh}{r or '本轮'}"
    if is_final:
        return f"{player_zh(w.name)}问鼎{g.name_zh}"
    return f"{player_zh(w.name)}晋级{g.name_zh}{r or ''}"


def hook_cover(digest: Digest) -> tuple[str, str] | None:
    """大字报封面文案：当日最大事件 -> (主行, 副行)；无爆点返回 None.

    小红书封面 3 秒法则：短句、人名、情绪。比分板做内页，封面只讲一件事。
    优先级：中国球员 > 夺冠 > 爆冷 > 伤退。
    """
    from ..models import MatchStatus
    from .common import group_by_tournament

    def sub_of(m) -> str:
        g = group_by_tournament([m])[0]
        return f"{g.name_zh} {_flat_round(m)} · {m.score_display()}"

    # 中国球员的胜负永远是头条（主行去掉"女单/男单"，副行已有完整信息）
    best_cn, best_cn_score = None, -1
    for m in digest.results:
        if not is_chinese_involved(m) or m.winner is None:
            continue
        text = _cn_match_headline(m)
        if text and match_score(m) > best_cn_score:
            main = text.replace("女单", "").replace("男单", "").replace("女双", "").replace("男双", "")
            best_cn, best_cn_score = (main, sub_of(m)), match_score(m)
    if best_cn:
        return best_cn

    # 夺冠时刻
    for m in top_results([x for x in digest.results if x.is_singles], 5):
        r = _flat_round(m)
        if r.endswith("决赛") and "半" not in r and "四" not in r:
            w = (m.winner_players() or [None])[0]
            if w:
                return f"{player_zh(w.name)}，夺冠。", sub_of(m)

    # 爆冷
    m = find_upset(digest.results)
    if m is not None:
        w = (m.winner_players() or [None])[0]
        l = (m.loser_players() or [None])[0]
        if w and l:
            return f"爆冷。{player_zh(l.name)}出局", sub_of(m)

    # 球星伤退
    for m in top_results([x for x in digest.results if x.is_singles], 5):
        if m.status is MatchStatus.RETIRED:
            l = (m.loser_players() or [None])[0]
            if l and (l.rank or 999) <= 40:
                return f"{player_zh(l.name)}，退赛。", sub_of(m)

    return None
