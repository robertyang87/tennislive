#!/usr/bin/env python3
"""备料批处理：把一场球能机器化的 spec 编辑内容一次性备齐，写成草稿。

无人值守链现在断在「probe 出缩略图墙 → 人写 spec」这一段。工具都齐了但没人
把它们串起来，于是写一条 spec 要人分别去跑：

    find_match_stats_fs --players      反查 flashscore id
    match_stat_hooks --stats-block     数据图 stats.a / stats.b
    match_stat_hooks                   狠数据候选（总分差/一发摆动/破发点/连续保发/H2H）
    find_turning_points                转折局候选
    draft_spec                         钩子/论点/beats/旁白/场外切口

本工具把这五件批处理成 `specs/reels/pending/<slug>.draft.json`，供人终审。

⚠️ **草稿只许落在 `pending/`，不许落在 `specs/reels/` 正下方**：判据测试是
**非递归**的 `Path("specs/reels").glob("*.json")`，`.draft.json` 会被 `*.json`
命中——2026-08-18 一份落在正下方的草稿把 main CI 红了两小时（事故记录在
`specs/reels/pending/README.md`）。`pending/` 已被那批判据豁免且有 README 合同。

⚠️ **只备料，不判稿**：窗口（segments 的 start/end/cx）仍由人从缩略图墙定——
转折局是「第几盘第几局」，映射到视频秒要另写对照，选段错位质检未必拦得住，
这一步不抢。封面（cover.portrait 官方实拍）也留人：`fetch_wta_cover_photo`
要 WTA 的 MatchID/tournament id，不在本工具输入里。

⚠️ **每一层退化都出声**（仓库里「兜底出事不吭声」栽过太多次）：反查不到 id、
stats 块缺必填项、狠数据算不出、没配 DeepSeek key——各自在 notes 里写一句，
草稿仍会写出「能备到的那部分」，缺的留给终审补。**不因为一块失败就把整份丢掉。**

用法：
    python tools/assemble_spec.py --slug eala-ruse --home "Alexandra Eala" \
        --away "Elena-Gabriela Ruse" --event "Cincinnati" --year 2026 \
        --fixture "北京时间 8 月 15 日，WTA1000 辛辛那提第二轮"

    # 已知 flashscore id 就直接给，跳过反查：
    python tools/assemble_spec.py --slug eala-ruse --flashscore-id 4CYI9Ick \
        --home "Alexandra Eala" --away "Elena-Gabriela Ruse" ...

产出 specs/reels/pending/<slug>.draft.json，字段：
    _draft: true          —— 草稿标记；validate_spec 只认 <slug>.json，不会误读
    _match.flashscore_id  —— 反查或给定
    cover.matchup         —— player_zh 译名 + 英文名
    stats                 —— stats.a / stats.b（数据图直接粘）
    editorial             —— draft_spec 的 hook/question/thesis/beats/human_context/narration
    _hit_data             —— 狠数据候选（不是判定）
    _turning_points       —— 转折局候选（不是判定）
    _notes                —— 每个环节的成败，一个字不省
"""

from __future__ import annotations

import argparse
import html
import http.client
import json
import re
import sys
import urllib.error
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fetch_match_stats_fs import FeedUnavailable, StatsError, find_match  # noqa: E402
from match_feed import fs_feed, points, set_pairs  # noqa: E402
from match_stat_hooks import BODY_ONLY, BODY_ONLY_NOTE, collect, stats_block  # noqa: E402
from find_turning_points import _label, rank_games  # noqa: E402
from tennislive.research.brief import Chat  # noqa: E402
from tennislive.zh import player_zh  # noqa: E402
from tennislive.sources.rankings import fetch_rankings, norm_name, rank_map  # noqa: E402
from tennislive.research.zh_trends import fetch_zh_hot  # noqa: E402
from draft_spec import arithmetic_claim_problem, draft_editorial  # noqa: E402
from reel_facts import reconcile_sets, verified_match_fact  # noqa: E402
from reel_timing import speech_seconds  # noqa: E402

TURNING_POINT_TOP = 5
DRAFT_SUFFIX = ".draft.json"
# 草稿落盘的目录。⚠️ 必须是 pending/ 子目录：`specs/reels/` 正下方被一批
# **非递归** `glob("*.json")` 的判据测试扫着，`.draft.json` 会被 `*.json`
# 命中——2026-08-18 已经把 main CI 红过 2 小时（见 pending/README.md）。
DRAFT_DIR = Path(__file__).resolve().parent.parent / "specs" / "reels" / "pending"


#: flashscore 那几块（matchup 归位、stats、狠数据、转折局、抢七小分）读 feed 走
#: `match_feed._get`：HTTP 5xx 和网络抖动**先重试三次**，还不行就抛 **SystemExit**
#: ——那是给命令行用的口径（「被挡还是不存在，别当成没有这场」），而 SystemExit
#: 不是 Exception，原来那几处 `except Exception` **一个都接不住**：上游一次 500
#: 就把整条「自动备料写 spec 草稿」带崩，probe 那一趟切点、缩略图墙全都不提交
#: （2026-09-28 返工审计「上游 HTTP 500」那一类）。备料是给草稿加料，缺一块只该
#: 记一句 note、留在 waiting，不该让 probe 红。判据
#: `test_flashscore_5xx重试之后仍失败_备料降级成只报不拖垮probe`。
#: ⚠️ **matchup 归位那一块不是「缺一块」**：其余几块都按它归好的 home/away 排，它接住
#: 之后不许退回命令行顺序，而是抛 `MatchupOrderUnverified`，让依赖顺序的几块整块不写。
_FEED_ERRORS = (Exception, SystemExit)


class MatchupOrderUnverified(Exception):
    """`matchup_order` 核不出 flashscore 的 home/away——**顺序不认，不是退回命令行**。

    stats 块、狠数据、转折局、逐盘比分这几块全是按 flashscore 的 home/away 排的；
    只要 matchup 没按同一个 home/away 归位，`verified_match_fact` 就会拿 feed 的
    home 比分去配命令行的 matchup[0]，**把赢家印成输家，还标着 result_verified**
    （`verified_result_problem` 拿 `_match` 自己的字段反推，输入错了照样自洽）。
    原来读不到 df_hh_1 就退回命令行顺序、只 print 一句：base 上 SystemExit 穿出去
    让 probe 红（没草稿、没错数据），把它接住之后这条退路就成了「萨巴伦卡 6-4 6-3
    诺斯科娃」——赢的是 flashscore 的 home 诺斯科娃（2026-09-28 复审回放）。
    所以核不出就抛它，由 `assemble` 把依赖顺序的几块整块跳过、草稿留在 waiting。
    判据 `test_df_hh_1读不到时不许出result_verified`。

    `transient`：**没读到**（feed 读失败、这场的记录还没挂出来）＝下一班值得再试，记进
    `_feed_retry`；**认不出**（同姓两个 Wang、同一场给出两种顺序）重读一百遍也一样，不试。"""

    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


# ── flashscore 备料的几块：读失败只报 ＋ 记账，reel-auto-ready 只重跑这几块 ────────
#
# 来路（2026-09-28 复审 D1）：上面那道「读失败只报、草稿留在 waiting」把 probe 从红
# 里救了出来，却把它送进了另一个死角——编排器的 `_already_specced` 认得这份草稿，
# **永不重 probe**；reel-auto-ready 只补封面和视觉证据，**不重跑备料**。于是 flashscore
# 抖一下（df_mh_1 一次 503），这场球就静静躺在 pending 里，直到 PENDING_MAX_AGE 过期
# （回放 `rv2_park_repro.py`：base 上 SystemExit 让 probe 红 → 失败自愈摘 state → 下一班
# 重 probe；分支上草稿照写、留在 waiting，然后再没有人碰它）。重 probe 要重下源片，
# 贵；读 feed 只要几个 HTTP 请求——所以**只重跑便宜的那一半**：
#
#     assemble 读失败（可重试的）→ 草稿记 `_feed_retry`（哪几块、为什么、试过几次）
#     reel-auto-ready 每一班   → `tools/retry_feed_blocks.py` 只重跑这几块，不 probe、不下源片
#     试满 FEED_RETRY_MAX 次仍不通 → 不再试，pipeline_health／run 摘要点名，不静静等到过期
#
# 判据 `tests/test_feed_retry.py`。

#: 备料里读 flashscore 的几块——`_feed_retry.blocks` 只许是这几个名字，顺序即依赖：
#: 没有 `match_id` 什么都读不了；`matchup` 核不出，按 home/away 排的后几块一块不许写；
#: `points`（df_mh_1）给逐盘局数，`tiebreaks`（df_sui_1）拿它对抢七小分，赛果事实由这两块算。
FEED_BLOCKS = ("match_id", "matchup", "stats", "hit_data", "points", "tiebreaks")
#: 上游一块没成，下游这一趟**根本没跑**——重跑时要连它们一起。
_FEED_DOWNSTREAM = {
    "match_id": ("matchup", "stats", "hit_data", "points"),
    "matchup": ("stats", "hit_data", "points"),
}
#: reel-auto-ready 最多替一份草稿重跑几次（probe 那一趟不算）。reel-auto-ready 10 分钟
#: 一班（GitHub 会丢 schedule，实际更稀），三次 ≈ 半小时以上——够等过一次 flashscore
#: 抖动；还不通就是源站真出事了，该叫人，不该再悄悄试到过期。
FEED_RETRY_MAX = 3
#: 「没读到」的异常：`match_feed._get` 重试完抛的 SystemExit（5xx／网络／4xx 被挡）、
#: `fetch_match_stats_fs` 的 StatsError（含 `FeedUnavailable`）、裸网络异常。
#: ValueError／KeyError 这类**解析**错不在里面——同一份 feed 重读一遍还是同一个错。
_TRANSIENT_FEED = (SystemExit, StatsError, urllib.error.URLError, TimeoutError,
                   ConnectionError, http.client.HTTPException)


def is_transient_feed_error(exc: BaseException) -> bool:
    """这一块下一班值不值得再读一遍。"""
    if isinstance(exc, MatchupOrderUnverified):
        return exc.transient
    return isinstance(exc, _TRANSIENT_FEED)


def _one_line(exc: BaseException) -> str:
    text = " ".join(x.strip() for x in str(exc).splitlines() if x.strip())
    return f"{type(exc).__name__}: {text}"[:300]


@dataclass
class FeedState:
    """一趟备料读 flashscore 的状态（assemble 和 `retry_feed_blocks` 共用）。"""

    mid: str | None = None
    order_verified: bool = False
    home_zh: str = ""
    away_zh: str = ""
    scores: list = field(default_factory=list)
    tiebreaks: list | None = None
    #: 这一趟逐局表读成了（赛果事实要按它重算）
    scores_read: bool = False
    #: 可重试的失败：块 → 一行错误
    failed: dict = field(default_factory=dict)
    #: 没读通、但重读也一样的块（解析错、按姓认不出、扫完了确实没有）
    dropped: list = field(default_factory=list)

    def fail(self, block: str, exc: BaseException) -> None:
        if is_transient_feed_error(exc):
            self.failed[block] = _one_line(exc)
        else:
            self.dropped.append(block)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _surname(full: str) -> str:
    """英文名取姓（出处只有一份 `tennislive.names.surname_en`：缩写名 `Bu Y.`
    姓在第一个词）。反查 flashscore 用它（find_match 按片段匹配）。"""
    from tennislive.names import surname_en  # noqa: PLC0415
    return surname_en(full) or full


def resolve_match_id(home: str, away: str) -> str | None:
    """按两个球员姓反查 flashscore id。查不到返回 None（不抛，调用方出声）。

    ⚠️ **没读到**（`FeedUnavailable`：近期赛果那几页 5xx／超时）照旧抛——那不是「没有这场」，
    assemble 把它记进 `_feed_retry`，下一班再查。"""
    try:
        mid, _, _ = find_match([_surname(home), _surname(away)])
        return mid or None
    except FeedUnavailable:
        raise
    except StatsError:
        return None


def matchup_order(home: str, away: str, flashscore_id: str) -> list[tuple[str, str]]:
    """matchup 顺序必须跟 flashscore 的 home/away 一致，不是跟命令行传参顺序。

    判据（CLAUDE.md「stats.a 跟 cover.matchup[0] 不是 feed 的 home/away」）：
    `stats_block` 的 a/b 按 flashscore 的 home/away（SH/SI）排，而
    `render_stat_card` 的 a 对应 `cover.matchup[0]`——所以 matchup 顺序也必须按
    flashscore 的 home/away 排。人传 `--home B --away A` 时若照抄，数据图会把
    a 的数字挂在 B 名下、b 的数字挂在 A 名下，**把赢家印成输家**，四道闸一道
    都不响。

    实现：读 `df_hh_1` 的 FH/FK（home/away 英文全名），拿它把两个输入归位。
    **核不出就抛 `MatchupOrderUnverified`**（feed 读不到、没给 FH/FK、按姓认不出
    ——同姓的两个 Wang 就是后一种），不退回命令行顺序：命令行顺序和 feed 的
    home/away 是两回事，拿它顶上会让赛果事实把赢家算反。
    """
    try:
        body = fs_feed("df_hh_1", flashscore_id)
        # ⚠️ 别只 split("~")[0]：FH/FK 在「Last matches」那条记录里（第一条是
        # SA÷N 的计数行），从整份 body 里找才稳。
        # FH/FK repeat for every historical match. A whole-feed dict keeps the
        # oldest meeting, which may reverse home/away (Sabalenka–Noskova 2026).
        # Select the requested match's KP record before reading its participants.
        records = [dict(re.findall(r"([A-Z]{2})÷([^¬~]*)", row))
                   for row in body.split("~")]
        matches = [row for row in records if row.get("KP") == flashscore_id]
        if matches:
            identities = {(row.get("FH"), row.get("FK")) for row in matches}
            if len(identities) != 1:
                raise ValueError("conflicting participant order for requested match")
            f = matches[0]
        else:
            # Legacy minimal feeds can contain one unambiguous identity pair.
            pairs = {(row.get("FH"), row.get("FK")) for row in records
                     if row.get("FH") and row.get("FK")}
            f = dict(zip(("FH", "FK"), next(iter(pairs)))) if len(pairs) == 1 else {}
        fs_home, fs_away = f.get("FH", ""), f.get("FK", "")
    except _FEED_ERRORS as exc:  # noqa: BLE001 —— 读不到就是核不出，不是命令行顺序
        raise MatchupOrderUnverified(
            f"flashscore df_hh_1 没读出本场 home/away（{_one_line(exc)}）",
            transient=is_transient_feed_error(exc)) from exc
    if not fs_home or not fs_away:
        # 读到了、只是这一场的记录还没挂出来——赛后刚打完常见，下一班再读
        raise MatchupOrderUnverified("flashscore df_hh_1 没给本场的 FH/FK", transient=True)
    # 按「谁的姓出现在 flashscore 的 home 里」归位，而不是按整名相等——feed 是
    # 「Baez S.」缩写，命令行是「Sebastian Baez」，整名对不上。
    def side_is(fs_name: str, full: str) -> bool:
        return _surname(full).casefold() in fs_name.casefold()

    # ⚠️ 同姓（王欣瑜/王曦雨、两个 Wang）时两边都会命中 home，`ordered` 会变成
    # `[home, home]`——长度也是 2，静默把 away 吞掉。要求两边各认领一个。
    ordered = []
    for fs_name in (fs_home, fs_away):
        hit_home, hit_away = side_is(fs_name, home), side_is(fs_name, away)
        if hit_home and not hit_away:
            ordered.append((home, player_zh(home)))
        elif hit_away and not hit_home:
            ordered.append((away, player_zh(away)))
    if len(ordered) == 2 and ordered[0][0] != ordered[1][0]:
        return ordered
    raise MatchupOrderUnverified(
        f"按姓认不出 home/away（FH={fs_home!r} FK={fs_away!r}）", transient=False)


def facts_text(hit_data: list[dict]) -> str:
    """把狠数据候选拼成一段喂给 draft_spec 的 facts。

    带 `use: body_only` 的那一条（总分差）在行里注明「只进正文，不进钩子和推送
    标题」——账号所有者 2026-09-13「不要写总分差距了」、09-19「不要把这个放在
    封面的钩子上」。模型只看得见这段文本，边界不写在行里它就不知道。
    """
    if not hit_data:
        return ""

    def line(c: dict) -> str:
        use = f"（{BODY_ONLY_NOTE}）" if c.get("use") == BODY_ONLY else ""
        return f"- {c.get('label', '')}{use}: {c.get('detail', '')}"

    return "\n".join(line(c) for c in hit_data)


def final_set_scores(games: list[dict]) -> list[tuple[int, int]]:
    """从逐局表取每盘最后一局的终场比分，保持盘的出现顺序。

    ``df_mh_1`` 的每局都带该局结束后的 ``home_games/away_games``。自动文案旧版
    只把总分差等统计喂给模型，却没把最基本的最终比分喂进去；真实草稿因此把
    4-6 6-1 6-1 编成了 6-4 3-6 6-4。这里从已经拉过的逐局表机械提取，避免
    再发一份网络请求，也不给模型猜比分的空间。
    """
    latest: dict[str, tuple[int, int]] = {}
    order: list[str] = []
    for game in games:
        key = str(game.get("set") or "").strip()
        if not key:
            continue
        try:
            score = (int(game["home_games"]), int(game["away_games"]))
        except (KeyError, TypeError, ValueError):
            continue
        if key not in latest:
            order.append(key)
        latest[key] = score
    return [latest[key] for key in order]


def score_fact(scores: list[tuple[int, int]], home_zh: str, away_zh: str) -> str:
    if not scores:
        return ""
    rendered = " ".join(f"{home}-{away}" for home, away in scores)
    return f"比赛最终比分（Flashscore 主队 {home_zh} 在前、客队 {away_zh} 在后）：{rendered}"


_SCORE_PAIR = re.compile(r"(?<!\d)([0-7])\s*[-:：]\s*([0-7])(?!\d)")


def editorial_score_problem(editorial: dict, scores: list[tuple[int, int]]) -> str | None:
    """拦住模型在 thesis/单句旁白里编出一整套错误盘分。

    单个 ``3-3`` 可能是局分，不能据此报错；只有同一字段写出至少完整盘数时才
    当作最终比分声明。允许主客两种书写方向，其余完整序列一律退回待修，不进入
    后续窗口和自动发布链。
    """
    if len(scores) < 2:
        return None
    allowed = {tuple(scores), tuple((b, a) for a, b in scores)}
    texts = [str(editorial.get("thesis") or "")]
    texts.extend(str(x) for x in (editorial.get("narration") or []) if x)
    for text in texts:
        found = [(int(a), int(b)) for a, b in _SCORE_PAIR.findall(text)]
        if len(found) < len(scores):
            continue
        windows = {tuple(found[i:i + len(scores)])
                   for i in range(len(found) - len(scores) + 1)}
        if windows.isdisjoint(allowed):
            expected = " ".join(f"{a}-{b}" for a, b in scores)
            claimed = " ".join(f"{a}-{b}" for a, b in found)
            return f"模型写出的完整盘分 {claimed} 与逐局表 {expected} 不一致"
    return None


def total_points_fact(stats: dict, matchup: list[dict]) -> str:
    """把总得分的方向写成不可误读的一句话，避免模型只看到 ``净差 11`` 猜反。"""
    try:
        a = int(stats["a"]["pts_won"])
        b = int(stats["b"]["pts_won"])
        a_name = str(matchup[0]["name"])
        b_name = str(matchup[1]["name"])
    except (KeyError, IndexError, TypeError, ValueError):
        return ""
    if a == b:
        return f"全场总得分：{a_name} {a}，{b_name} {b}，两人持平"
    leader, trailer = (a_name, b_name) if a > b else (b_name, a_name)
    return (f"全场总得分：{a_name} {a}，{b_name} {b}；{leader}比{trailer}"
            f"多 {abs(a - b)} 分。禁止写成{trailer}总分领先。"
            "这个数只供核对方向，不写进钩子和推送标题")


def editorial_total_points_problem(
    content: dict, stats: dict, matchup: list[dict], scores: list[tuple[int, int]],
) -> str | None:
    """拦住总分领先者写反，包括无主语的「多拿 N 分却输了」。

    #1207 的真实草稿同时出现「56 比 67 落后 11 分」和「总分领先」。仅检查
    数字是否出现不够，必须把球员、领先方向和比赛胜负一起机械核对。
    """
    try:
        a = int(stats["a"]["pts_won"])
        b = int(stats["b"]["pts_won"])
        names = [str(matchup[0]["name"]), str(matchup[1]["name"])]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    if a == b:
        return None
    leader_idx = 0 if a > b else 1
    trailer_idx = 1 - leader_idx
    leader, trailer = names[leader_idx], names[trailer_idx]

    def _texts(value):
        if isinstance(value, dict):
            for nested in value.values():
                yield from _texts(nested)
        elif isinstance(value, (list, tuple)):
            for nested in value:
                yield from _texts(nested)
        elif value is not None:
            yield str(value)

    texts = list(_texts(content))
    trailer_leads = re.compile(
        rf"{re.escape(trailer)}.{{0,24}}(?:总分.{{0,6}}领先|多拿\s*{abs(a-b)}\s*分|"
        rf"净胜\s*{abs(a-b)}\s*分)"
    )
    leader_trails = re.compile(
        rf"{re.escape(leader)}.{{0,24}}(?:总分.{{0,6}}落后|少拿\s*{abs(a-b)}\s*分)"
    )
    for text in texts:
        if trailer_leads.search(text) or leader_trails.search(text):
            return f"总得分方向写反：应为{leader}领先{trailer} {abs(a-b)}分"

    # 若总分领先者同时赢下比赛，「多拿 N 分却输了」这种无主语钩子也一定错。
    if scores:
        a_sets = sum(x > y for x, y in scores)
        b_sets = sum(y > x for x, y in scores)
        winner_idx = 0 if a_sets > b_sets else 1 if b_sets > a_sets else None
        if winner_idx == leader_idx:
            upside_down = re.compile(
                rf"(?:多拿\s*{abs(a-b)}\s*分|总分.{{0,6}}领先|净胜\s*{abs(a-b)}\s*分)"
                r".{0,18}(?:却|反而).{0,8}(?:输|落败|出局)"
            )
            if any(upside_down.search(text) for text in texts):
                return f"总分领先者{leader}也是比赛赢家，不能写成“领先却输球”"
    return None


def scene_cut_segments(cuts_path: str, narration: list[str]) -> list[dict]:
    """无字幕时从 probe 的完整镜头表机械选可容纳旁白的高光窗口。

    不猜具体比分发生在哪一秒，也不跨镜头硬切：按时间三等分选各区间里最长的
    单镜头，窗口只承担通用赛况旁白。逐分+比分板对齐仍是更高优先级路径。
    """
    probe = json.loads(Path(cuts_path).read_text(encoding="utf-8"))
    duration = float(probe.get("duration") or 0)
    cuts = sorted({float(x) for x in (probe.get("scene_cuts") or [])
                   if 0 < float(x) < duration})
    lines = [str(x).strip() for x in narration if str(x).strip()]
    if duration <= 0 or not lines:
        return []
    bounds = [0.0, *cuts, duration]
    scenes = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    picked: list[tuple[float, float]] = []
    last_end = -1.0
    for index, line in enumerate(lines):
        need = speech_seconds(line) + 0.8
        lo = duration * index / len(lines)
        hi = duration * (index + 1) / len(lines)
        candidates = [s for s in scenes if s[0] >= last_end and
                      s[1] - s[0] >= need]
        in_band = [s for s in candidates if (s[0] + s[1]) / 2 >= lo and
                   (s[0] + s[1]) / 2 <= hi]
        pool = in_band or candidates
        if not pool:
            return []
        target = (lo + hi) / 2
        scene = min(pool, key=lambda s: (abs((s[0] + s[1]) / 2 - target),
                                         -(s[1] - s[0])))
        picked.append(scene)
        last_end = scene[1]
    segments = []
    for beat, (line, (start, end)) in enumerate(zip(lines, picked, strict=True), 1):
        need = speech_seconds(line) + 0.8
        center = (start + end) / 2
        seg_start = max(start + 0.05, center - need / 2)
        seg_end = min(end - 0.05, seg_start + need)
        seg_start = max(start + 0.05, seg_end - need)
        segments.append({
            "start": round(seg_start, 2), "end": round(seg_end, 2),
            "narration": line, "fit": "crop", "_beat": beat,
            "_why": "无字幕源：按 probe 镜头切点选单镜头高光窗口；不跨切点",
        })
    return segments


def fetch_tennistv_cover(
    source_url: str, event: str, out: Path, *, get=None,
) -> str:
    """从 Tennis TV 页面取赛事匹配的官方头图，并请求 4000px 原图。

    Tennis TV 会给新比赛挂旧站资料图：Medvedev–Damm 页实际挂的是
    ``2026-Washington-Damm.jpg``。高清、官方都不等于本场；文件名不含当前赛事
    的关键词就拒绝，不能让「资料图」冒充「本场实拍」。
    """
    if "tennistv.com" not in urlparse(source_url).netloc.casefold():
        raise ValueError("不是 Tennis TV 链接")
    if get is None:
        import requests  # noqa: PLC0415
        get = requests.get
    page_response = get(
        source_url, headers={"User-Agent": "tennislive/0.1"}, timeout=30)
    page_response.raise_for_status()
    page = html.unescape(str(page_response.text))
    patterns = [
        r'itemprop=["\']thumbnailUrl["\'][^>]+content=["\']([^"\']+)',
        r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
    ]
    image_url = next((m.group(1) for pattern in patterns
                      if (m := re.search(pattern, page, re.IGNORECASE))), "")
    if not image_url.startswith("https://"):
        raise ValueError("Tennis TV 页面没有官方头图")
    event_tokens = [x for x in re.split(r"[^a-z0-9]+", event.casefold())
                    if len(x) >= 3]
    image_key = urlparse(image_url).path.casefold()
    if event_tokens and not all(token in image_key for token in event_tokens):
        raise ValueError(
            f"Tennis TV 头图不是本场赛事（{Path(urlparse(image_url).path).name}"
            f" 不匹配 {event}），拒绝资料图")
    parsed = urlparse(image_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop("height", None)
    query["width"] = "4000"
    image_url = urlunparse(parsed._replace(query=urlencode(query)))
    response = get(image_url, headers={"User-Agent": "tennislive/0.1"}, timeout=30)
    response.raise_for_status()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(response.content)
    from PIL import Image, ImageOps  # noqa: PLC0415
    with Image.open(out) as raw:
        width, height = ImageOps.exif_transpose(raw).size
    if width < 1080 or height < 1440:
        out.unlink(missing_ok=True)
        raise ValueError(f"Tennis TV 头图只有 {width}×{height}，撑不满封面")
    return f"Tennis TV 本场官方页面头图（ATP Media，{width}×{height}）"


def _rank_line(name_en: str, lookup: dict[str, int]) -> str:
    """查即时世界排名，拼「X 世界第 N」。查不到（前 150 外/榜上没有）返回空串。"""
    r = lookup.get(norm_name(name_en))
    return f"{player_zh(name_en)} 世界第 {r}" if r is not None else ""


def upset_cover_brief(matchup: list[dict], scores: list[tuple[int, int]]) -> dict | None:
    """爆冷封面优先讲明星输家的情绪，而不是默认只追赢家庆祝。

    沿用选题层的爆冷口径：赢家排名比输家低至少 30 位；“明星球员”收窄为
    世界前 20。缺排名或赛果不完整时不猜，返回 None。

    ⚠️ **拍输家拍他在拼，不拍他垮掉**（账号所有者 2026-08-15 arango-venus：
    封面换成大威，否掉的是 152.5s 低头垮掉那一帧，选的是 240.5s 零比四落后
    仍在握拳那一帧）。原来这里要的是「失落、落寞」的近景——正好是被否的那一种。
    口味规则全文在 `.claude/skills/tennis-owner-taste/SKILL.md`「封面选图」。
    """
    if len(matchup) != 2 or not scores:
        return None
    a_sets = sum(a > b for a, b in scores)
    b_sets = sum(b > a for a, b in scores)
    if a_sets == b_sets:
        return None
    winner_idx = 0 if a_sets > b_sets else 1
    loser_idx = 1 - winner_idx
    winner, loser = matchup[winner_idx], matchup[loser_idx]
    try:
        winner_rank, loser_rank = int(winner["rank"]), int(loser["rank"])
    except (KeyError, TypeError, ValueError):
        return None
    if loser_rank > 20 or winner_rank - loser_rank < 30:
        return None
    return {
        "reason": f"爆冷：世界第{winner_rank}击败世界第{loser_rank}",
        "preferred_subject": loser.get("name") or loser.get("name_en"),
        "preferred_moment": "本场落后或失利时仍在拼的高清近景（握拳、咬牙、怒吼、奋力击球），不要低头垮掉的那一帧",
        # 闸比的是这个键（`analyze_reel_visuals.COVER_MOMENTS` 里的枚举），不是上面那句中文
        "preferred_moment_key": "loser_fighting",
        "fallback_subject": winner.get("name") or winner.get("name_en"),
        "fallback_moment": "本场获胜后庆祝的高清近景",
        "fallback_moment_key": "winner_celebration",
        "requirements": ["必须是本场", "优先官方原图", "不得用旧赛资料图"],
    }


def _hot_line(hits, home: str, away: str) -> str:
    """中文热搜里撞上这两位球员的，拼一句。撞不上返回空串。

    榜上没有这两位是常态（一轮扫 232 条，通常 0～1 条网球），不是抓挂了——
    「撞不上」和「抓挂了」在 _notes 里分开报，由 build_background 负责。
    """
    home_zh = player_zh(home).casefold()
    away_zh = player_zh(away).casefold()
    home_s = _surname(home).casefold()
    away_s = _surname(away).casefold()

    def field(row, name: str, default):
        """同时读生产 dataclass 和测试/旧缓存里的 dict。

        ``fetch_zh_hot`` 的真实返回项是 ``ZhHot``，不是 dict。旧实现只在单测的
        dict 桩上通过，线上每次都会在 ``h.get`` 抛 ``AttributeError``，于是中文
        热点背景稳定降级。边界处兼容两种序列化形状，调用方不再猜生产对象类型。
        """
        if isinstance(row, dict):
            return row.get(name, default)
        return getattr(row, name, default)

    for h in hits:
        terms = field(h, "terms", ()) or ()
        word = str(field(h, "word", "") or "")
        source = str(field(h, "source", "") or "")
        hay = (" ".join(terms) + " " + word).casefold()
        if any(n and n in hay for n in (home_zh, away_zh, home_s, away_s)):
            return f"中文热搜：{word}（{source}）"
    return ""


def build_background(home: str, away: str, hit_data: list[dict]) -> tuple[str, list[str]]:
    """聚合球员信息背景：H2H + 近况（从 hit_data 拎）+ 排名 + 中文热点。

    这是账号所有者「不光只是 H2H，还有前几轮的战国、当前的热点，都要作为信息
    背景，查全了」的落点。返回 (背景文本, 每源成败 notes)。**每源失败不拖垮
    整体**——一个源挂了只写一句 note，背景仍返回能拿到的部分（仓库里「兜底
    出事不吭声」栽过太多次，这里每个源要么给内容、要么给失败原因）。

    年龄/生日、纪录/里程碑、金句这三类**没有机械源**：年龄要球员档案、纪录要
    全称断言双源、金句要赛后采访人工转写——它们由 editorial 的 human_context
    调研补，不在本函数范围内（写进 _notes 提醒终审）。
    """
    parts: list[str] = []
    notes: list[str] = []

    # ① H2H + 近况：已经从 collect() 进 hit_data 了，拎出来即可（不另发请求）。
    for label in ("交手记录", "近况"):
        c = next((c for c in hit_data if c.get("label") == label), None)
        if c:
            parts.append(f"{label}：{c['detail']}")

    # ② 排名：ESPN rankings（只到前 150；掉出去 = 榜上看不见，不是「没排名」）。
    try:
        ranks = fetch_rankings()
        lookup = {**rank_map(ranks.atp), **rank_map(ranks.wta)}
        lines = [ln for ln in (_rank_line(home, lookup), _rank_line(away, lookup)) if ln]
        if lines:
            parts.append("排名：" + "；".join(lines))
        else:
            notes.append("排名：两位都不在榜单前 150（见 lookup_player_meta 的说明，"
                         "掉出榜单≠没有排名，终审要写排名的话去 ATP/WTA 官网查）")
    except Exception as exc:  # noqa: BLE001 —— 排名失败不拖垮背景
        notes.append(f"⚠️ 排名没成（{type(exc).__name__}: {exc}）")

    # ③ 中文热点：两位球员是否正在中文平台热榜上。
    try:
        res = fetch_zh_hot(top=60)
        hit_line = _hot_line(res.hits, home, away)
        if hit_line:
            parts.append(hit_line)
        else:
            notes.append(f"中文热点：扫 {res.scanned} 条，没有撞上这两位球员")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"⚠️ 中文热点没成（{type(exc).__name__}: {exc}）")

    return ("\n".join(parts) if parts else ""), notes


def _matchup_block(draft: dict, home: str, away: str, feed: FeedState,
                   notes: list[str]) -> None:
    """`matchup`：按 df_hh_1 的 home/away 把 `cover.matchup` 归位。

    ⚠️ 拿到 id 就立刻重排 matchup——stats.a 跟的是 flashscore 的 home，而
    render_stat_card 的 a 跟 cover.matchup[0]，顺序不一致数据图会把赢家印成输家
    （CLAUDE.md 记过的坑）。归位是**搬动已有的两条**（按英文名认），不重建——
    重跑时它们身上已经挂着排名、国别。"""
    try:
        ordered = matchup_order(home, away, feed.mid)
    except MatchupOrderUnverified as exc:
        # 顺序核不出：matchup 照原样留着（只是两个名字，不带任何归属），而按 feed
        # home/away 排的几块（stats、狠数据、转折局、逐盘比分 → 赛果事实）一块都不写
        # ——写了就是把 feed home 的数挂在命令行 matchup[0] 名下。草稿留在 waiting
        # （「结构化赛果尚未 verified」）。
        feed.order_verified = False
        notes.append(
            f"⚠️ matchup 顺序没核上 flashscore 的 home/away（{exc}）——stats 块"
            "／狠数据／转折局／赛果事实都按 feed 的 home/away 排，顺序不认就"
            "一块都不写（写了会把赢家印成输家），草稿留在 waiting；df_hh_1 "
            "恢复后重跑备料")
        if exc.transient:
            feed.failed["matchup"] = str(exc)[:300]
        else:
            feed.dropped.append("matchup")
        return
    feed.order_verified = True
    feed.home_zh, feed.away_zh = ordered[0][1], ordered[1][1]
    pair = (draft.get("cover") or {}).get("matchup") or []
    before = [str(p.get("name") or "") for p in pair]
    by_en = {norm_name(str(p.get("name_en") or "")): p for p in pair}
    draft.setdefault("cover", {})["matchup"] = [
        {**by_en.get(norm_name(en), {}), "name": zh, "name_en": en} for en, zh in ordered]
    if [x[1] for x in ordered] != before:
        notes.append("matchup 按 flashscore home/away 重排："
                     + " vs ".join(x[1] for x in ordered))


def _feed_data_blocks(draft: dict, feed: FeedState, notes: list[str],
                      blocks: set[str]) -> None:
    """`stats`／`hit_data`／`points`／`tiebreaks`：**只跑 `blocks` 里点名的**。

    前提是 matchup 已经按 feed 的 home/away 归位（`feed.order_verified`）。`tiebreaks`
    要 `points` 的逐盘局数——只点了 `tiebreaks` 时逐局表照读（算局数用），但不动已有的
    `_turning_points`。每一块读失败只报一句 note；可重试的记进 `feed.failed`。"""
    mid = feed.mid
    if "stats" in blocks:
        # ② stats 块（数据图）。
        try:
            blk = stats_block(mid)
        except _FEED_ERRORS as exc:  # noqa: BLE001 —— 网络/格式都别拖垮整份草稿
            notes.append(f"⚠️ stats 块没成（{type(exc).__name__}: {exc}）")
            feed.fail("stats", exc)
            blk = None
        if blk is not None:
            draft["stats"] = {"a": blk["a"], "b": blk["b"]}
            if blk["_missing_required"]:
                notes.append("⚠️ stats 块必填项没解出来："
                             + "、".join(blk["_missing_required"]))
            notes.append("制胜分/非受迫失误：" + (
                "这场有，已填进 stats" if blk["_has_winners_ue"]
                else "接口里没有——照 render_stat_card 的 OPTIONAL_FIELDS 留空"))
            # ②′ 数据图头像——没有它 render 最后一步（渲给推送用的数据图）是
            #    SystemExit。已发 spec 里认过的人复用，WTA 现抓，ATP 留空出声
            #    （promote 那头的闸会把草稿留在 waiting）。
            try:
                from headshot_index import resolve_headshots  # noqa: PLC0415
                notes.extend(resolve_headshots(draft))
            except Exception as exc:  # noqa: BLE001 —— 头像失败不拖垮整份草稿
                notes.append(f"⚠️ 数据图头像没补上（{type(exc).__name__}: {exc}）")

    if "hit_data" in blocks:
        # ③ 狠数据候选。
        try:
            # ⚠️ 名字按 **feed 的 home/away** 给（collect 拿 home 的名字去标 SH
            # 那一列的数），不是命令行顺序——matchup 重排过的场次，传命令行顺序
            # 就是把赢家的总分、破发点兑现标在输家名下，还喂进文案 facts。
            hit = collect(mid, feed.home_zh, feed.away_zh)
            draft["_hit_data"] = hit["candidates"]
            draft["_durations"] = hit["durations"]
            notes.append(f"狠数据候选 {len(hit['candidates'])} 条"
                         + ("" if hit["candidates"] else "（分盘统计字段可能没铺全）"))
        except _FEED_ERRORS as exc:  # noqa: BLE001
            notes.append(f"⚠️ 狠数据没成（{type(exc).__name__}: {exc}）")
            feed.fail("hit_data", exc)

    if "points" in blocks or "tiebreaks" in blocks:
        # ④ 转折局候选（逐局表同时给出逐盘局数，赛果事实靠它）。
        try:
            match_games = points(mid)
            feed.scores = final_set_scores(match_games)
            feed.scores_read = True
            if "points" in blocks:
                ranked = rank_games(match_games)
                draft["_turning_points"] = [
                    {"label": _label(g, feed.home_zh, feed.away_zh),
                     "density": g["density"], "tags": g["tags"]}
                    for g in ranked[:TURNING_POINT_TOP]
                ]
                notes.append(f"转折局候选 {len(ranked)} 局，取前 {TURNING_POINT_TOP}")
        except _FEED_ERRORS as exc:  # noqa: BLE001
            notes.append(f"⚠️ 转折局没成（{type(exc).__name__}: {exc}）")
            feed.fail("points" if "points" in blocks else "tiebreaks", exc)

    # 抢七小分＋补上抢七盘的洞：df_mh_1 不列抢七那一局，final_set_scores 对
    # 抢七盘只能取到 6-6（老链上带抢七的比赛整场判不出赢家）；df_sui_1 的
    # IG/IH 把两件事一次补齐（语义与判据见 reel_facts.reconcile_sets）。
    if feed.scores:
        try:
            reconciled = reconcile_sets(feed.scores, set_pairs(mid))
            if reconciled:
                feed.scores, feed.tiebreaks = reconciled
            else:
                notes.append("⚠️ df_sui_1 的每盘数字和逐局表对不上，"
                             "抢七小分没拿到（对不上就不猜）")
        except _FEED_ERRORS as exc:  # noqa: BLE001
            notes.append(f"⚠️ 抢七小分没拿到（{type(exc).__name__}: {exc}）——"
                         "带抢七的比赛会过不了 result_verified/小分闸，属于该红")
            feed.fail("tiebreaks", exc)


def _match_fact_block(draft: dict, feed: FeedState, notes: list[str]) -> None:
    """赛果事实（赢家视角逐盘比分）＋爆冷封面口径——都从 `feed.scores` 机械算。"""
    match_fact = verified_match_fact(
        draft.get("cover", {}).get("matchup", []), feed.scores,
        str(feed.mid or ""), tiebreaks=feed.tiebreaks)
    if match_fact:
        draft["_match"] = match_fact
        draft["cover"].update({
            "winner": match_fact["winner"],
            "result": match_fact["winner_result"],
        })
        notes.append(
            f"赛果事实闸：{match_fact['winner']} "
            f"{match_fact['winner_result']} {match_fact['loser']}（赢家视角）")
    elif feed.mid and feed.order_verified:
        notes.append("⚠️ 逐局数据不足以确定赢家和逐盘比分；不生成正式 spec")

    cover_brief = upset_cover_brief(
        draft.get("cover", {}).get("matchup", []), feed.scores)
    if cover_brief:
        draft["_cover_brief"] = cover_brief
        notes.append(
            "爆冷封面：优先明星输家赛后失落高清近景；找不到再退赢家庆祝照")
    else:
        draft.pop("_cover_brief", None)


def _feed_retry_blocks(failed: dict) -> list[str]:
    """读失败的块 ＋ 因为它没成而这一趟根本没跑的下游，按 `FEED_BLOCKS` 的顺序。"""
    want = set(failed)
    for block in failed:
        want.update(_FEED_DOWNSTREAM.get(block, ()))
    return [b for b in FEED_BLOCKS if b in want]


def record_feed_retry(draft: dict, feed: FeedState, *, tries: int) -> None:
    """把这一趟可重试的失败记进 `_feed_retry`；全读通了就摘掉它。

    形状（机器读，`tools/retry_feed_blocks.py` 和 `pipeline_health` 都认它）::

        "_feed_retry": {"blocks": ["points"],            # 下一班要重跑的块（FEED_BLOCKS 里的名字）
                        "errors": {"points": "SystemExit: …HTTP 503…"},
                        "tries": 0,                      # reel-auto-ready 已经重跑过几次
                        "last_at": "2026-09-28T07:00:00Z"}

    `_` 开头：是给下一班看的账，不进成片；promote 转正时剥掉
    （`render_inputs.GATE_ANNOTATIONS["_feed_retry"]`）。"""
    if not feed.failed:
        draft.pop("_feed_retry", None)
        return
    draft["_feed_retry"] = {
        "blocks": _feed_retry_blocks(feed.failed),
        "errors": {b: feed.failed[b] for b in FEED_BLOCKS if b in feed.failed},
        "tries": tries,
        "last_at": _stamp(),
    }


def _recheck_copy(draft: dict, feed: FeedState, notes: list[str]) -> None:
    """重跑补上了比分／统计之后，拿**同几道机械闸**把已经起草的文案再核一遍。

    probe 那一趟文案是在没有这几块的情况下起草的（`score_fact` / `total_points_fact`
    没喂进去），`editorial_score_problem` 当时拿空比分放行了它。补齐之后不核，就是
    一份没对过比分的文案被自动转正。**只核不重写**：起草那一步走模型，账号所有者
    2026-09-27 定了不再加强模型链——对不上就撤下，草稿留在 waiting，不猜。"""
    matchup = draft.get("cover", {}).get("matchup", [])
    stats = draft.get("stats", {})
    editorial = draft.get("editorial")
    if isinstance(editorial, dict):
        problem = (editorial_score_problem(editorial, feed.scores)
                   or editorial_total_points_problem(editorial, stats, matchup, feed.scores)
                   or arithmetic_claim_problem(editorial))
        if problem:
            draft.pop("editorial", None)
            draft.pop("push", None)
            notes.append(f"⚠️ 备料补齐之后文案对不上：{problem}——撤下 editorial 和 push"
                         "（不重写，草稿留在 waiting）")
            return
    push = draft.get("push")
    if isinstance(push, dict):
        problem = (editorial_total_points_problem(push, stats, matchup, feed.scores)
                   or arithmetic_claim_problem(push))
        if problem:
            draft.pop("push", None)
            notes.append(f"⚠️ 备料补齐之后推送文案{problem}；已撤下 push，禁止发送")


def retry_feed_blocks(draft: dict) -> str:
    """reel-auto-ready 的一班：**只重跑 `_feed_retry.blocks` 里那几块**——不 probe、
    不下源片、不碰模型。原地改 `draft`，返回这一班的结果：

    | 返回 | 意思 |
    |---|---|
    | `none` | 没有账（或账是空的），什么都没做 |
    | `exhausted` | 已经试满 `FEED_RETRY_MAX` 次，这一班不再读——该叫人了 |
    | `healed` | 这一趟全读通了，`_feed_retry` 摘掉 |
    | `dropped` | 读到了，但剩下的是**重读也一样**的错（解析错、按姓认不出、扫完了确实没有这场）——照旧只写 note、从账上划掉，草稿留在 waiting 等人 |
    | `retry` | 还有没读通的，`tries`＋1，下一班再来 |
    | `gave_up` | 这一趟刚好试满、仍没读通（`exhausted_at` 记上时刻）|"""
    ledger = draft.get("_feed_retry")
    if not isinstance(ledger, dict) or not ledger.get("blocks"):
        return "none"
    tries = int(ledger.get("tries") or 0)
    if tries >= FEED_RETRY_MAX:
        return "exhausted"
    blocks = {b for b in ledger.get("blocks") or () if b in FEED_BLOCKS}
    pair = (draft.get("cover") or {}).get("matchup") or []
    if len(pair) != 2 or not all(p.get("name_en") for p in pair):
        raise ValueError("草稿 cover.matchup 不是两位带英文名的球员，没法重跑备料")
    home, away = (str(p["name_en"]) for p in pair)
    feed = FeedState(mid=(draft.get("_match") or {}).get("flashscore_id") or None,
                     order_verified="matchup" not in blocks and "match_id" not in blocks,
                     home_zh=str(pair[0].get("name") or ""),
                     away_zh=str(pair[1].get("name") or ""))
    notes = [f"── 备料重跑 第 {tries + 1}/{FEED_RETRY_MAX} 次（{_stamp()}）："
             + "、".join(b for b in FEED_BLOCKS if b in blocks)]
    if "match_id" in blocks:
        try:
            mid = resolve_match_id(home, away)
        except FeedUnavailable as exc:
            mid = None
            feed.fail("match_id", exc)
            notes.append(f"⚠️ flashscore 近期赛果仍没读到（{_one_line(exc)}）")
        if mid:
            feed.mid = mid
            draft["_match"] = {**(draft.get("_match") or {}), "flashscore_id": mid}
            notes.append(f"flashscore id：{mid}（按球员姓反查）")
        elif "match_id" not in feed.failed:
            feed.dropped.append("match_id")
            notes.append("⚠️ 扫完了近期赛果，确实没有这一场——不再重跑")
    elif not feed.mid:
        feed.dropped.append("match_id")
        notes.append("⚠️ 账上没记 match_id，草稿里却没有 _match.flashscore_id——没法重跑")
    if feed.mid and "matchup" in blocks:
        _matchup_block(draft, home, away, feed, notes)
    if feed.mid and feed.order_verified:
        _feed_data_blocks(draft, feed, notes, blocks - {"match_id", "matchup"})
        if feed.scores_read:
            _match_fact_block(draft, feed, notes)
        if feed.scores_read or "stats" in blocks:
            _recheck_copy(draft, feed, notes)
    record_feed_retry(draft, feed, tries=tries + 1)
    if feed.failed:
        status = "gave_up" if tries + 1 >= FEED_RETRY_MAX else "retry"
    else:
        status = "dropped" if feed.dropped else "healed"
    if status == "gave_up":
        draft["_feed_retry"]["exhausted_at"] = draft["_feed_retry"]["last_at"]
        notes.append(f"⚠️ flashscore 备料重跑 {FEED_RETRY_MAX} 次仍没读到："
                     + "、".join(draft["_feed_retry"]["blocks"])
                     + "——不再自动重跑，pipeline_health 会点名")
    elif status == "healed":
        notes.append("备料重跑读通了，_feed_retry 摘掉")
    elif status == "dropped":
        notes.append("⚠️ 备料重跑读到了，但 " + "、".join(dict.fromkeys(feed.dropped))
                     + " 是重读也一样的错——从账上划掉，草稿留在 waiting 等人")
    draft["_notes"] = [*(draft.get("_notes") or []), *notes]
    return status


def assemble(*, slug: str, home: str, away: str, event: str, year: int,
             fixture: str, flashscore_id: str | None,
             round_name: str = "", court: str = "",
             home_country: str = "", away_country: str = "",
             home_rank: int | None = None, away_rank: int | None = None,
             received_at: str = "",
             captions_path: str | None = None,
             cuts_path: str | None = None,
             pbp_path: str | None = None,
             scoreboard_path: str | None = None,
             cover: bool = False,
             source_url: str = "",
             background: str = "", tactical_packet: dict | None = None) -> dict:
    from tactical_research import start_research, verified_context
    research_job = start_research(home=home, away=away, event=event, year=year) if tactical_packet is None else None
    background_param = background
    notes: list[str] = []
    feed = FeedState(home_zh=player_zh(home), away_zh=player_zh(away))
    draft: dict = {
        "_draft": True,
        "slug": slug,
        "_column": "reel",
        "cover": {
            "matchup": [
                {"name": player_zh(home), "name_en": home,
                 "country": home_country or None, "rank": home_rank},
                {"name": player_zh(away), "name_en": away,
                 "country": away_country or None, "rank": away_rank},
            ],
        },
        "_production": {
            "kind": "orchestrated_reel",
            "received_at": received_at,
            "event": event,
            "year": year,
            "round": round_name,
            "court": court,
        },
    }
    # source_url 是 render 的硬要求（load_spec 里「既没有 sources 也没有
    # source_url」就报错）。编排器探测集锦时已经拿到 url，这里接住写进草稿，
    # 草稿才够得上「能渲染」的最小形状。
    if source_url:
        draft["source_url"] = source_url

    # ① flashscore id：给了就用，没给就反查。
    mid = flashscore_id
    if not mid:
        try:
            mid = resolve_match_id(home, away)
        except FeedUnavailable as exc:
            mid = None
            feed.fail("match_id", exc)
            notes.append(f"⚠️ flashscore 近期赛果没读到（{_one_line(exc)}）——这不是「没有这场」，"
                         "id 没反查成，stats 块 / 狠数据 / 转折局本轮跳过")
    feed.mid = mid
    if mid:
        draft["_match"] = {"flashscore_id": mid}
        notes.append(f"flashscore id：{mid}"
                     + ("（给定）" if flashscore_id else "（按球员姓反查）"))
        _matchup_block(draft, home, away, feed, notes)
    elif "match_id" not in feed.failed:
        notes.append("⚠️ 没反查到 flashscore id——stats 块 / 狠数据 / 转折局"
                     "都依赖它，这三块本轮跳过。用 tools/match_feed.py find 拿到 id "
                     "后补进 _match.flashscore_id 重跑。")

    # 封面选人要在抓图前就有排名。爆冷场不是默认追赢家：世界前 20 被低至少
    # 30 位的对手淘汰时，优先找明星输家赛后失落的当场高清近景。
    try:
        current_ranks = fetch_rankings()
        lookup = {**rank_map(current_ranks.atp), **rank_map(current_ranks.wta)}
        for player in draft["cover"]["matchup"]:
            rank = lookup.get(norm_name(player.get("name_en", "")))
            if rank is not None and player.get("rank") is None:
                player["rank"] = rank
    except Exception as exc:  # noqa: BLE001 —— 排名失败不能拖垮整份草稿
        notes.append(f"⚠️ 封面排名没成（{type(exc).__name__}: {exc}）")

    if mid and feed.order_verified:
        _feed_data_blocks(draft, feed, notes, {"stats", "hit_data", "points", "tiebreaks"})
    _match_fact_block(draft, feed, notes)
    record_feed_retry(draft, feed, tries=0)
    if feed.failed:
        notes.append(
            "⚠️ flashscore 备料没读到：" + "、".join(draft["_feed_retry"]["blocks"])
            + f"——记进 _feed_retry，reel-auto-ready 下一班只重跑这几块（不 probe、"
            f"不下源片），最多 {FEED_RETRY_MAX} 次")
    authoritative_scores = feed.scores
    feed_home_zh, feed_away_zh = feed.home_zh, feed.away_zh

    # Research is optional and timeboxed. A saved packet can carry reviewed,
    # timecoded claims; freshly discovered articles are not automatically facts.
    tactical = tactical_packet if tactical_packet is not None else research_job.result()
    draft["_tactical_research"] = tactical
    notes.append(f"技战术资料：{tactical.get('status', 'provided')}；未核观点不进入旁白")

    # ⑤ 文案（DeepSeek）。facts 用上面算出的狠数据候选喂，background 自动聚合
    #    H2H + 近况 + 排名 + 中文热点（账号所有者：「不光只是 H2H，还有前几轮的
    #    战国、当前的热点，都要作为信息背景，查全了」）。--background 给了就
    #    优先用命令行那份，跳过自动聚合（终审手填时用）。
    chat = Chat()
    if not chat.ready:
        notes.append("⚠️ 没配 DEEPSEEK_API_KEY / ANTHROPIC_API_KEY，文案跳过——"
                     "钩子/论点/beats/旁白留给终审手写。")
    else:
        notes.append(f"文案通道 {chat.channel}")
        hit = draft.get("_hit_data", [])
        if background_param:
            background = background_param
            notes.append("背景用命令行 --background 传入，跳过自动聚合")
        else:
            background, bg_notes = build_background(home, away, hit)
            notes.extend(bg_notes)
            notes.append("背景聚合：H2H/近况/排名/中文热点已备齐（年龄/纪录/金句"
                         "要 human_context 调研补，见 spec 合同）")
        editorial_facts = facts_text(hit)
        exact_score = score_fact(authoritative_scores, feed_home_zh, feed_away_zh)
        if exact_score:
            editorial_facts = f"- {exact_score}\n{editorial_facts}".rstrip()
        points_fact = total_points_fact(
            draft.get("stats", {}), draft.get("cover", {}).get("matchup", []))
        if points_fact:
            editorial_facts = f"- {points_fact}\n{editorial_facts}".rstrip()
        tactical_facts = verified_context(tactical, identity={"home": home, "away": away, "event": event, "year": year})
        if tactical_facts:
            editorial_facts += "\n" + tactical_facts
        draft["editorial"] = draft_editorial(
            chat, home=home, away=away, event=event, year=year,
            fixture=fixture, facts=editorial_facts, background=background)
        if draft["editorial"] is None:
            draft.pop("editorial", None)
            notes.append("⚠️ 文案这一步没成（模型或网络），editorial 留空")
        else:
            score_problem = editorial_score_problem(
                draft["editorial"], authoritative_scores)
            points_problem = editorial_total_points_problem(
                draft["editorial"], draft.get("stats", {}),
                draft.get("cover", {}).get("matchup", []), authoritative_scores)
            problem = score_problem or points_problem or arithmetic_claim_problem(
                draft["editorial"])
            if problem:
                # 数字方向是机械事实，先把具体错误喂回模型重写一次；仍错就撤稿。
                corrected_facts = (f"{editorial_facts}\n- 上一稿错误：{problem}。"
                                   "本次必须按上面的精确比分和总得分方向重写")
                retry = draft_editorial(
                    chat, home=home, away=away, event=event, year=year,
                    fixture=fixture, facts=corrected_facts, background=background)
                retry_problem = (editorial_score_problem(
                    retry or {}, authoritative_scores)
                                 or editorial_total_points_problem(
                                     retry or {}, draft.get("stats", {}),
                                     draft.get("cover", {}).get("matchup", []),
                                     authoritative_scores)
                                 or arithmetic_claim_problem(retry or {}))
                if retry and not retry_problem:
                    draft["editorial"] = retry
                    notes.append(f"文案事实校验发现首稿错误（{problem}），重写后通过")
                else:
                    problem = retry_problem or problem
                    draft.pop("editorial", None)
                    notes.append(f"⚠️ {problem}；重写仍未通过，已撤下 editorial")
            # 推送文案（summary/lead）也自动起草。自动编排产出的新片默认认领
            # `push.auto=true`：render 的 QC 全绿后直接叫醒 auto-push-reel，
            # 不再停在人工审片。只有用户对某一条明确要求「不要发布」时，才在
            # 正式 spec 里删掉 auto 并写 `_no_auto_why`；不能让默认值静默回到关。
            if "editorial" not in draft:
                notes.append("⚠️ editorial 因事实不一致已撤下，推送文案与窗口同步跳过")
            else:
                try:
                    from draft_spec import draft_push
                    push = draft_push(chat, editorial=draft["editorial"],
                                      facts=editorial_facts)
                    if push and push.get("summary"):
                        push_problem = (editorial_total_points_problem(
                            push, draft.get("stats", {}),
                            draft.get("cover", {}).get("matchup", []),
                            authoritative_scores)
                            or arithmetic_claim_problem(push))
                        if push_problem:
                            notes.append(
                                f"⚠️ 推送文案{push_problem}；已撤下 push，禁止发送")
                        else:
                            push["auto"] = True
                            draft["push"] = push
                            notes.append(
                                "推送文案已通过事实校验；默认开启 QC 后自动推送")
                    else:
                        notes.append("⚠️ 推送文案起草没成，留终审")
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"⚠️ 推送文案没成（{type(exc).__name__}: {exc}）")

    # ⑥ 窗口（机械对齐优先：逐分+比分板 → 骨架）。给了 pbp + scoreboard 才跑——
    #    这是「配音不脱节」的正路（docs/scoreboard-alignment.md）：逐分数据是内容、
    #    比分板是定位，align_points 把「赛点/破发点那一分」定位到视频秒，再按 9 屏
    #    模板生成 segments 草稿、旁白按 beats 挂。没给就走下面的 DeepSeek 读字幕
    #    （draft_segments）那条老路。
    if pbp_path and scoreboard_path:
        try:
            from align_points import align as _align_points, point_states as _pt_states
            from align_points import screen_anchors, segment_skeleton
            pbp = json.loads(Path(pbp_path).read_text(encoding="utf-8"))
            raw = pbp.get("raw") or pbp
            # ⚠️ 别叫 `points`——模块顶有 `from match_feed import points`，这里
            # 再赋一个局部 `points` 会把它变成整函数作用域的局部变量，④ 转折局
            # 那步的 `points(mid)` 就 UnboundLocalError 了（Python 作用域规则）。
            pbp_points = raw.get("points") or []
            reads = json.loads(Path(scoreboard_path).read_text(encoding="utf-8"))
            states = _pt_states(pbp_points)
            aligned = _align_points(reads, states)
            anchors = screen_anchors(states, aligned)
            narration = (draft.get("editorial") or {}).get("narration", [])
            segs = segment_skeleton(anchors, narration)
            if segs:
                # 收口：窗口要能直接 render——至少装得下旁白（speech_seconds）
                # 且不跨切点（probe.json 的 scene_cuts）。这是「草稿渲完直接
                # 合并推微信」的窗口硬闸（账号所有者：「做好视频直接 merge 推」）。
                cuts = []
                if cuts_path:
                    try:
                        cuts = json.loads(Path(cuts_path).read_text(
                            encoding="utf-8")).get("scene_cuts", [])
                    except (OSError, ValueError):
                        cuts = []
                try:
                    from align_points import finalize_windows
                    segs = finalize_windows(segs, cuts, speech_seconds=speech_seconds)
                    notes.append(f"窗口收口：按旁白时长 + {len(cuts)} 个切点收")
                except Exception as exc:  # noqa: BLE001
                    notes.append(f"⚠️ 窗口收口没成（{type(exc).__name__}: {exc}）")
                draft["segments"] = segs
                draft["_segments_source"] = "align_points（逐分+比分板机械对齐）"
                notes.append(f"窗口机械对齐 {len(segs)} 段（align_points），"
                             f"锚点 {anchors}")
            else:
                notes.append("⚠️ 机械对齐没产出窗口（比分板读太少？），segments 留空")
        except Exception as exc:  # noqa: BLE001 —— 机械对齐失败不拖垮整份草稿
            notes.append(f"⚠️ 机械对齐没成（{type(exc).__name__}: {exc}）")

    # ⑥′ 窗口起草（DeepSeek 读字幕+切点）。只在「没走机械对齐」且给了 captions +
    #    cuts（probe 产物）时才跑——probe 之前这两个文件不存在，跳过并在 notes 出声。
    if captions_path and cuts_path and "segments" not in draft and draft.get("editorial"):
        try:
            from draft_segments import _read_captions, _read_cuts, draft_segments
            caps = _read_captions(Path(captions_path))
            cuts = _read_cuts(Path(cuts_path))
            if not caps:
                notes.append("⚠️ captions 是空的，窗口起草跳过（退回人工）")
            elif not chat.ready:
                notes.append("⚠️ 没配 key，窗口起草跳过")
            else:
                beats = "\n".join(
                    (draft.get("editorial") or {}).get("beats", []))
                hook = (draft.get("editorial") or {}).get("hook") or []
                seg = draft_segments(chat, captions_text=caps, cuts=cuts,
                                     beats=beats, home=player_zh(home),
                                     away=player_zh(away),
                                     hook="／".join(str(x) for x in hook)
                                     if isinstance(hook, list) else str(hook))
                if seg and seg.get("segments"):
                    draft["segments"] = seg["segments"]
                    notes.append(f"窗口起草 {len(seg['segments'])} 段"
                                 + (f"，拦掉 {seg.get('_dropped', 0)} 段废窗口"
                                    if seg.get("_dropped") else ""))
                else:
                    notes.append("⚠️ 窗口起草没成（模型或全被闸拦掉），segments 留空")
        except Exception as exc:  # noqa: BLE001 —— 窗口起草失败不拖垮整份草稿
            notes.append(f"⚠️ 窗口起草没成（{type(exc).__name__}: {exc}）")
    elif "segments" not in draft:
        notes.append("⚠️ 没给 captions 或字幕不可读，字幕窗口起草跳过")

    # ⑥″ Tennis TV 短集锦常常根本没有字幕轨。probe 已经给了完整镜头表时，
    # 不应把这当作永久人工阻塞：选三个互不跨切点、足够装下旁白的高光镜头。
    # 这条只做通用赛况画面，优先级低于逐分对齐和字幕语义窗口。
    if cuts_path and "segments" not in draft and draft.get("editorial"):
        try:
            segs = scene_cut_segments(
                cuts_path, (draft.get("editorial") or {}).get("narration", []))
            if segs:
                draft["segments"] = segs
                draft["_segments_source"] = "probe.scene_cuts（无字幕机械兜底）"
                notes.append(f"无字幕窗口兜底 {len(segs)} 段：全部单镜头且装得下旁白")
            else:
                notes.append("⚠️ probe 镜头都短于旁白，无法生成无字幕窗口")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ 无字幕窗口兜底没成（{type(exc).__name__}: {exc}）")

    # ⑦ 封面官方实拍（可选，--cover 触发）。WTA 场次才有这条官方路：英文名
    #    反查 WTA MatchID → 抓赛后稿头图。抓得到就写 cover.portrait.image，
    #    抓不到（稿子没挂/没实拍）就留空出声——封面是 cover_photo_problem 硬闸
    #    管的，抓错比不抓更糟，宁可留空让 render 前闸走抽帧认领。
    if cover:
        cover_done = False
        if source_url and "tennistv.com" in urlparse(source_url).netloc.casefold():
            try:
                out = Path(f"assets/reel/{slug}-cover.jpg")
                note = fetch_tennistv_cover(source_url, event, out)
                draft.setdefault("cover", {})["portrait"] = {
                    "image": str(out),
                    "_portrait_why": "Tennis TV 本场官方页面关联的 ATP Media 高清图",
                }
                notes.append(f"封面官方实拍：{note}")
                cover_done = True
            except Exception as exc:  # noqa: BLE001
                notes.append(f"⚠️ Tennis TV 官方头图没成（{type(exc).__name__}: {exc}）")
        if cover_done:
            pass
        else:
            try:
                import requests
                from datetime import timedelta

                from fetch_match_pbp import find_match as wta_find_match
                from fetch_wta_cover_photo import fetch_cover
                session = requests.Session()
                today = date.today()
                event_id, wyear, match_id, _row = wta_find_match(
                    session, [_surname(home), _surname(away)],
                    today - timedelta(days=2), today)
                # city slug：WTA 官网赛事 URL 用城市小写（多伦多=toronto、
                # 辛辛那提=cincinnati）。⚠️ 之前硬编码 "cincinnati"，换别的赛事就
                # 会抓错站——用 event 小写拼，覆盖所有 WTA 场次。
                city_slug = (event or "").strip().lower().replace(" ", "-")
                out = Path(f"assets/reel/{slug}-cover.jpg")
                code, note = fetch_cover(str(event_id), str(wyear), city_slug,
                                         match_id, [_surname(home), _surname(away)],
                                         out, today)
                notes.append(f"封面官方实拍：{note}")
                if code == 0:
                    draft.setdefault("cover", {})["portrait"] = {
                        "image": str(out), "_portrait_why": "WTA 官方赛后稿头图，自动抓取"}
                else:
                    notes.append("⚠️ 封面没抓到（稿子没挂或没有实拍），portrait 留空，"
                                 "render 前 cover_photo_problem 闸会要求认领 frame_at/_frame_why")
            # `fetch_match_pbp.find_match` 用 SystemExit 表示「WTA 窗口里没这场」。
            # ATP 比赛（2026-08-26 Medvedev–Damm）必然走到这里；SystemExit 不属于
            # Exception，旧代码因此在**草稿已经备好之后**把整个 probe job杀掉。
            # 没有 WTA 官方封面只是可预期降级，不能抹掉 spec、字幕和缩略图产物。
            except (Exception, SystemExit) as exc:  # noqa: BLE001
                notes.append(f"⚠️ 封面抓取没成（{type(exc).__name__}: {exc}）——"
                             "portrait 留空，终审或 render 前再补")

    draft["_notes"] = notes
    return draft


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--home", required=True, help="英文全名，如 Alexandra Eala")
    ap.add_argument("--away", required=True, help="英文全名，如 Elena-Gabriela Ruse")
    ap.add_argument("--event", default="")
    ap.add_argument("--year", type=int, default=0)
    ap.add_argument("--round", dest="round_name", default="",
                    help="赛果源给出的轮次；自动 formal/topbar 不从标题猜")
    ap.add_argument("--court", default="",
                    help="赛果源给出的场地；缺失时正式提升停在 waiting")
    ap.add_argument("--home-country", default="")
    ap.add_argument("--away-country", default="")
    ap.add_argument("--home-rank", type=int, default=None)
    ap.add_argument("--away-rank", type=int, default=None)
    ap.add_argument("--received-at", default="",
                    help="orchestrate 确认生产输入的 UTC 时刻；用于过期闸和 SLO")
    ap.add_argument("--fixture", default="", help="赛前信息，进文案 prompt")
    ap.add_argument("--flashscore-id", default=None,
                    help="已知 flashscore id 就跳过反查")
    ap.add_argument("--captions", default=None,
                    help="probe 产出的 captions.txt（给了就跑窗口起草）")
    ap.add_argument("--cuts", default=None,
                    help="probe.json（读 scene_cuts，配 --captions 用）")
    ap.add_argument("--pbp", default=None,
                    help="fetch_match_pbp --json 落盘的 pbp.json（配 --scoreboard 走机械对齐）")
    ap.add_argument("--scoreboard", default=None,
                    help="read_scoreboard.py 落盘的 scoreboard.json（配 --pbp 走机械对齐）")
    ap.add_argument("--cover", action="store_true",
                    help="试抓 WTA 官方实拍封面（抓不到就留空出声，不硬来）")
    ap.add_argument("--source-url", default="",
                    help="源片 URL（render 硬要求，编排器探测集锦时拿到）")
    ap.add_argument("--background", default="",
                    help="球员背景（排名/年龄/H2H/纪录/金句），有就喂给文案")
    ap.add_argument("--tactical-packet", type=Path, help="已读报道与经同场/时间码核验的技战术观点 JSON")
    ap.add_argument("--write", action="store_true",
                    help="把草稿落盘到 specs/reels/pending/<slug>.draft.json；不给就只打印")
    args = ap.parse_args()

    draft = assemble(slug=args.slug, home=args.home, away=args.away,
                     event=args.event, year=args.year, fixture=args.fixture,
                     flashscore_id=args.flashscore_id,
                     round_name=args.round_name, court=args.court,
                     home_country=args.home_country,
                     away_country=args.away_country,
                     home_rank=args.home_rank, away_rank=args.away_rank,
                     received_at=args.received_at,
                     captions_path=args.captions, cuts_path=args.cuts,
                     pbp_path=args.pbp, scoreboard_path=args.scoreboard,
                     cover=args.cover, source_url=args.source_url,
                     background=args.background,
                     tactical_packet=json.loads(args.tactical_packet.read_text()) if args.tactical_packet else None)

    print(json.dumps(draft, ensure_ascii=False, indent=2))
    if not args.write:
        print("\n（干跑，没落盘。要写进仓库加 --write。）")
        return 0

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    out = DRAFT_DIR / f"{args.slug}{DRAFT_SUFFIX}"
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n草稿 → {out}")
    print("\n窗口（segments）和封面（cover.portrait 官方实拍）留给终审补，"
          "见草稿 _notes 里每个环节的成败。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
