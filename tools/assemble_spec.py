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
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fetch_match_stats_fs import StatsError, find_match  # noqa: E402
from match_feed import fs_feed, points, set_pairs  # noqa: E402
from match_stat_hooks import collect, stats_block  # noqa: E402
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


def _surname(full: str) -> str:
    """英文全名取最后一个词当姓。反查 flashscore 用它（find_match 按片段匹配）。"""
    words = (full or "").strip().split()
    return words[-1] if words else full


def resolve_match_id(home: str, away: str) -> str | None:
    """按两个球员姓反查 flashscore id。查不到返回 None（不抛，调用方出声）。"""
    try:
        mid, _, _ = find_match([_surname(home), _surname(away)])
        return mid or None
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
    读不到就退回命令行顺序（出声，别静默）。
    """
    try:
        body = fs_feed("df_hh_1", flashscore_id)
        # ⚠️ 别只 split("~")[0]：FH/FK 在「Last matches」那条记录里（第一条是
        # SA÷N 的计数行），从整份 body 里找才稳。
        f = dict(re.findall(r"(F[HK])÷([^¬]*)", body))
        fs_home, fs_away = f.get("FH", ""), f.get("FK", "")
    except Exception as exc:  # noqa: BLE001 —— 网络失败就退回命令行顺序
        print(f"[matchup] flashscore df_hh_1 读不到（{exc}），退回命令行顺序")
        fs_home = fs_away = ""
    if not fs_home or not fs_away:
        print("[matchup] flashscore 没给 FH/FK，退回命令行顺序")
        return [(home, player_zh(home)), (away, player_zh(away))]
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
    print(f"[matchup] 按姓认不出 home/away（FH={fs_home!r} FK={fs_away!r}），退回命令行顺序")
    return [(home, player_zh(home)), (away, player_zh(away))]


def facts_text(hit_data: list[dict]) -> str:
    """把狠数据候选拼成一段喂给 draft_spec 的 facts。"""
    if not hit_data:
        return ""
    return "\n".join(f"- {c.get('label', '')}: {c.get('detail', '')}" for c in hit_data)


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
            f"多 {abs(a - b)} 分。禁止写成{trailer}总分领先")


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
        "preferred_moment": "本场失利后失落、落寞或难以置信的高清近景",
        "fallback_subject": winner.get("name") or winner.get("name_en"),
        "fallback_moment": "本场获胜后庆祝的高清近景",
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
             background: str = "") -> dict:
    background_param = background
    notes: list[str] = []
    feed_home_zh, feed_away_zh = player_zh(home), player_zh(away)
    authoritative_scores: list[tuple[int, int]] = []
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
    mid = flashscore_id or resolve_match_id(home, away)
    if mid:
        draft["_match"] = {"flashscore_id": mid}
        notes.append(f"flashscore id：{mid}"
                     + ("（给定）" if flashscore_id else "（按球员姓反查）"))
        # ⚠️ 拿到 id 就立刻重排 matchup——stats.a 跟的是 flashscore 的 home，
        # 而 render_stat_card 的 a 跟 cover.matchup[0]，顺序不一致数据图会
        # 把赢家印成输家（CLAUDE.md 记过的坑）。
        ordered = matchup_order(home, away, mid)
        feed_home_zh, feed_away_zh = ordered[0][1], ordered[1][1]
        if [x[1] for x in ordered] != [player_zh(home), player_zh(away)]:
            notes.append("matchup 按 flashscore home/away 重排："
                         + " vs ".join(x[1] for x in ordered))
        supplied = {
            norm_name(home): {"country": home_country or None, "rank": home_rank},
            norm_name(away): {"country": away_country or None, "rank": away_rank},
        }
        draft["cover"]["matchup"] = [
            {"name": zh, "name_en": en, **supplied.get(norm_name(en), {})}
            for en, zh in ordered]
    else:
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

    if mid:
        # ② stats 块（数据图）。
        try:
            blk = stats_block(mid)
        except Exception as exc:  # noqa: BLE001 —— 网络/格式都别拖垮整份草稿
            notes.append(f"⚠️ stats 块没成（{type(exc).__name__}: {exc}）")
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

        # ③ 狠数据候选。
        try:
            hit = collect(mid, player_zh(home), player_zh(away))
            draft["_hit_data"] = hit["candidates"]
            draft["_durations"] = hit["durations"]
            notes.append(f"狠数据候选 {len(hit['candidates'])} 条"
                         + ("" if hit["candidates"] else "（分盘统计字段可能没铺全）"))
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ 狠数据没成（{type(exc).__name__}: {exc}）")

        # ④ 转折局候选。
        try:
            match_games = points(mid)
            authoritative_scores = final_set_scores(match_games)
            ranked = rank_games(match_games)
            draft["_turning_points"] = [
                {"label": _label(g, player_zh(home), player_zh(away)),
                 "density": g["density"], "tags": g["tags"]}
                for g in ranked[:TURNING_POINT_TOP]
            ]
            notes.append(f"转折局候选 {len(ranked)} 局，取前 {TURNING_POINT_TOP}")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ 转折局没成（{type(exc).__name__}: {exc}）")

    # 抢七小分＋补上抢七盘的洞：df_mh_1 不列抢七那一局，final_set_scores 对
    # 抢七盘只能取到 6-6（老链上带抢七的比赛整场判不出赢家）；df_sui_1 的
    # IG/IH 把两件事一次补齐（语义与判据见 reel_facts.reconcile_sets）。
    authoritative_tiebreaks: list[tuple[int, int] | None] | None = None
    if mid and authoritative_scores:
        try:
            reconciled = reconcile_sets(authoritative_scores, set_pairs(mid))
            if reconciled:
                authoritative_scores, authoritative_tiebreaks = reconciled
            else:
                notes.append("⚠️ df_sui_1 的每盘数字和逐局表对不上，"
                             "抢七小分没拿到（对不上就不猜）")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"⚠️ 抢七小分没拿到（{type(exc).__name__}: {exc}）——"
                         "带抢七的比赛会过不了 result_verified/小分闸，属于该红")

    match_fact = verified_match_fact(
        draft.get("cover", {}).get("matchup", []), authoritative_scores,
        str(mid or ""), tiebreaks=authoritative_tiebreaks)
    if match_fact:
        draft["_match"] = match_fact
        draft["cover"].update({
            "winner": match_fact["winner"],
            "result": match_fact["winner_result"],
        })
        notes.append(
            f"赛果事实闸：{match_fact['winner']} "
            f"{match_fact['winner_result']} {match_fact['loser']}（赢家视角）")
    elif mid:
        notes.append("⚠️ 逐局数据不足以确定赢家和逐盘比分；不生成正式 spec")

    cover_brief = upset_cover_brief(
        draft.get("cover", {}).get("matchup", []), authoritative_scores)
    if cover_brief:
        draft["_cover_brief"] = cover_brief
        notes.append(
            "爆冷封面：优先明星输家赛后失落高清近景；找不到再退赢家庆祝照")

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
                seg = draft_segments(chat, captions_text=caps, cuts=cuts,
                                     beats=beats, home=player_zh(home),
                                     away=player_zh(away))
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
                     background=args.background)

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
