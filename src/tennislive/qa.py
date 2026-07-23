"""发布前自动质检：替代人工审核的最后一道闸.

只做能机器判断的硬检查；返回 (致命问题, 警告) 两级。
致命问题会让 CLI 以非零码退出，从而阻断当天的自动发布步骤。
"""

from __future__ import annotations

import re
from dataclasses import fields

from .digest import Digest
from .models import MatchStats, StatPair
from .timeutil import fmt_time_beijing
from .zh import player_zh


XHS_TITLE_LIMIT = 20
XHS_BODY_TARGET = (450, 650)
XHS_BODY_LIMITS = (300, 800)

_SCORE_CLAIM_RE = re.compile(r"(?<!\d)(\d{1,2})\s*([-:：]|比)\s*(\d{1,2})(?!\d)")
_PERCENT_CLAIM_RE = re.compile(r"(?<!\d)\d+(?:\.\d+)?%")
_SEED_CLAIM_RE = re.compile(r"(?<!\d)(\d{1,3})\s*号种子")
_RANK_CLAIM_RE = re.compile(r"世界第\s*(\d{1,4})(?!\d)")


def _xhs_body(lines: list[str]) -> str:
    """Return the post body without depending on exactly one blank title separator."""
    return "\n".join(lines[1:]).lstrip("\n").rstrip()


def _date_labels(digest: Digest) -> tuple[str, ...]:
    day = digest.today
    return (
        f"{day.month}.{day.day}",
        f"{day.month:02d}.{day.day:02d}",
        f"{day.month}/{day.day}",
        f"{day.month}月{day.day}日",
        f"{day.month}月{day.day}号",
    )


def _is_daily_post(digest: Digest, post: str, first_line: str) -> bool:
    """Distinguish the daily digest from the deliberately short single-match flash."""
    del first_line
    match_count = len(digest.results) + len(digest.live) + len(digest.schedule)
    flash_markers = (
        "刚刚结束，但这场不该只看比分",
        "今晚不必守满所有比赛，先给这一场留时间",
    )
    if match_count == 1 and any(marker in post for marker in flash_markers):
        return False
    daily_markers = (
        "今天只讲",
        "今天先看这一件事",
        "今日网球时差",
        "昨夜焦点",
        "今晚我只圈",
        "今晚只看这三场",
        "今晚焦点",
        "中国球员速报",
    )
    return (
        match_count != 1
        or any(marker in post for marker in daily_markers)
    )


def _scheduled_mentions(digest: Digest, body: str) -> list[str]:
    """Return unique scheduled match ids whose two sides are both named in the copy."""
    mentioned: list[str] = []
    for match in digest.schedule:
        home_names = {p.name for p in match.home} | {player_zh(p.name) for p in match.home}
        away_names = {p.name for p in match.away} | {player_zh(p.name) for p in match.away}
        home_found = any(name and name in body for name in home_names)
        away_found = any(name and name in body for name in away_names)
        if home_found and away_found and match.match_id not in mentioned:
            mentioned.append(match.match_id)
    return mentioned


def _pair_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _numeric_evidence(digest: Digest) -> tuple[set[str], set[str], set[str], set[str], str]:
    """Collect only evidence we can deterministically trace to the normalized digest."""
    score_pairs: set[str] = set()
    times: set[str] = set()
    seeds: set[str] = set()
    ranks: set[str] = set()
    source_fragments: list[str] = []

    for match in digest.results + digest.live + digest.schedule:
        for player in match.home + match.away:
            if player.seed is not None:
                seeds.add(str(player.seed))
            if player.rank is not None:
                ranks.add(str(player.rank))

        if match.start_utc is not None:
            times.add(fmt_time_beijing(match.start_utc))
        for item in match.sets:
            score_pairs.update(
                {
                    f"{item.home}-{item.away}",
                    f"{item.away}-{item.home}",
                    f"{item.home}比{item.away}",
                    f"{item.away}比{item.home}",
                }
            )
        if match.sets:
            home_sets = sum(item.home > item.away for item in match.sets)
            away_sets = sum(item.away > item.home for item in match.sets)
            score_pairs.update(
                {
                    f"{home_sets}-{away_sets}",
                    f"{away_sets}-{home_sets}",
                    f"{home_sets}比{away_sets}",
                    f"{away_sets}比{home_sets}",
                }
            )

        source_fragments.extend(
            value
            for value in (match.note, match.status_detail, match.editorial_note)
            if value
        )
        if match.stats is not None:
            for field in fields(MatchStats):
                value = getattr(match.stats, field.name)
                if isinstance(value, StatPair):
                    left, right = _pair_text(value.home), _pair_text(value.away)
                    score_pairs.update(
                        {f"{left}:{right}", f"{right}:{left}", f"{left}：{right}", f"{right}：{left}"}
                    )
                    source_fragments.extend((left, right))
                    if field.name.endswith("_pct"):
                        source_fragments.extend((f"{left}%", f"{right}%"))
                elif isinstance(value, (int, float)):
                    source_fragments.append(_pair_text(value))

    # The cover layer has a small reviewed historical profile allowlist. Keep
    # those claims traceable without treating arbitrary generated history as data.
    from .render.titles import cover_fact_bundle, daily_lead_match

    lead = daily_lead_match(digest)
    if lead is not None:
        historical = cover_fact_bundle(lead).get("historical_profile")
        if historical:
            peak_rank = historical.get("peak_rank")
            if peak_rank is not None:
                ranks.add(str(peak_rank))
            source_fragments.extend(
                str(value)
                for value in historical.values()
                if value is not None
            )
        from .render.context import historical_context

        context = historical_context(lead, digest.today)
        if context:
            source_fragments.extend(
                [context.summary, context.continuity]
                + [value for value, _label in context.facts]
            )
            for value, _label in context.facts:
                rank_match = re.search(r"世界第(\d+)", value)
                if rank_match:
                    ranks.add(rank_match.group(1))
    return score_pairs, times, seeds, ranks, "\n".join(source_fragments)


def _numeric_claim_errors(digest: Digest, post: str) -> list[str]:
    """Reject high-confidence unsupported score, time, percentage, seed and rank claims."""
    score_pairs, times, seeds, ranks, source_text = _numeric_evidence(digest)
    errors: list[str] = []
    for match in _SCORE_CLAIM_RE.finditer(post):
        left, sep, right = match.groups()
        raw = match.group(0).replace(" ", "")
        normalized = f"{left}{sep}{right}"
        if sep in (":", "：") and normalized in times:
            continue
        if normalized in score_pairs or raw in source_text or normalized in source_text:
            continue
        errors.append(f"小红书出现无数据依据的比分/时间: {raw}")
    for match in _PERCENT_CLAIM_RE.finditer(post):
        claim = match.group(0)
        if claim not in source_text:
            errors.append(f"小红书出现无数据依据的百分比: {claim}")
    for match in _SEED_CLAIM_RE.finditer(post):
        number = match.group(1)
        if number not in seeds and match.group(0) not in source_text:
            errors.append(f"小红书出现无数据依据的种子序号: {match.group(0)}")
    for match in _RANK_CLAIM_RE.finditer(post):
        number = match.group(1)
        if number not in ranks and match.group(0) not in source_text:
            errors.append(f"小红书出现无数据依据的世界排名: {match.group(0)}")
    return list(dict.fromkeys(errors))


def check_xhs_post(digest: Digest, post: str) -> tuple[list[str], list[str]]:
    """Apply deterministic Xiaohongshu publishability and mobile-readability checks."""
    fatal: list[str] = []
    warn: list[str] = []
    lines = post.splitlines()
    if not lines or not lines[0].strip():
        return ["小红书标题为空"], []

    from .render.hashtags import MAX_HASHTAGS, hashtag_count
    from .render.xiaohongshu import xhs_title_len

    xhs_title = lines[0].strip()
    title_len = xhs_title_len(xhs_title)
    if title_len > XHS_TITLE_LIMIT:
        fatal.append(f"小红书标题超长: {title_len:g} > {XHS_TITLE_LIMIT}")

    body = _xhs_body(lines)
    tag_count = hashtag_count(post)
    if tag_count > MAX_HASHTAGS:
        fatal.append(
            f"小红书话题标签超过{MAX_HASHTAGS}个: {tag_count}"
        )
    daily = _is_daily_post(digest, post, xhs_title)
    if not any(label in xhs_title for label in _date_labels(digest)):
        fatal.append("小红书标题缺少当日日期")
    if not body:
        fatal.append("小红书正文为空")
        return fatal, warn

    if daily:
        body_len = len(body)
        hard_min, hard_max = XHS_BODY_LIMITS
        target_min, target_max = XHS_BODY_TARGET
        if body_len < hard_min:
            fatal.append(f"小红书正文过短: {body_len} < {hard_min}")
        elif body_len < target_min:
            warn.append(f"小红书正文低于建议区间: {body_len} < {target_min}")
        elif body_len > hard_max:
            fatal.append(f"小红书正文过密: {body_len} > {hard_max}")
        elif body_len > target_max:
            warn.append(f"小红书正文高于建议区间: {body_len} > {target_max}")

        blank_lines = sum(not line.strip() for line in body.splitlines())
        if blank_lines < 3:
            warn.append(f"小红书段落留白不足: 仅 {blank_lines} 个空行")

        longest_run = 0
        run = 0
        for line in body.splitlines():
            if line.strip():
                run += 1
                longest_run = max(longest_run, run)
            else:
                run = 0
        if longest_run > 6:
            fatal.append(f"小红书连续信息行过多: {longest_run} > 6")
        elif longest_run > 4:
            warn.append(f"小红书连续信息行偏多: {longest_run} > 4")

        long_lines = [line for line in body.splitlines() if xhs_title_len(line) > 48]
        if long_lines:
            warn.append(f"小红书存在手机端过长行: {len(long_lines)} 行")

        tonight_count = len(_scheduled_mentions(digest, body))
        if tonight_count > 5:
            fatal.append(f"小红书今晚焦点超过5场: {tonight_count} > 5")

    if "■" in post or "□" in post:
        fatal.append("小红书使用黑方块式数据库列表符号")
    if daily:
        dense_rows = sum(
            line.count("｜") + line.count("·") >= 4 for line in body.splitlines()
        )
        if dense_rows:
            warn.append(f"小红书数据库式分隔符过密: {dense_rows} 行")

    fatal.extend(_numeric_claim_errors(digest, post))
    return list(dict.fromkeys(fatal)), list(dict.fromkeys(warn))


def run_checks(
    digest: Digest,
    title: str,
    xhs_post: str,
    *,
    cover_copy: tuple[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    fatal: list[str] = []
    warn: list[str] = []

    # 数据完整性
    for m in digest.results:
        if m.winner is None and m.status.value not in ("cancelled", "postponed"):
            warn.append(f"已完赛但无胜者: {m.match_id} {m.home[0].name} vs {m.away[0].name}")
        if m.winner is not None and not m.sets and m.status.value == "finished":
            warn.append(f"已完赛但无比分: {m.match_id}")
    bad_names = [
        p.name
        for m in digest.results + digest.schedule
        for p in m.home + m.away
        if not p.name or p.name.strip() in ("?", "")
    ]
    if bad_names:
        fatal.append(f"存在空球员名 {len(bad_names)} 个")

    # 标题与文案长度
    if not title.strip():
        fatal.append("标题为空")
    if len(title) > 64:
        fatal.append(f"公众号标题超长: {len(title)} > 64")
    xhs_fatal, xhs_warn = check_xhs_post(digest, xhs_post)
    fatal.extend(xhs_fatal)
    warn.extend(xhs_warn)

    # ATP/WTA 前 300 中文名优先；缺失只进入告警，不能拖住时效性发布。
    singles_players = [
        p
        for m in digest.results + digest.live + digest.schedule
        for p in m.home + m.away
        if m.is_singles
    ]
    top_300_untranslated = sorted(
        {
            player.name
            for player in singles_players
            if player.rank is not None
            and 1 <= player.rank <= 300
            and player_zh(player.name) == player.name
        }
    )
    if top_300_untranslated:
        warn.append(
            "前300球员中文名待异步补充: " + "、".join(top_300_untranslated)
        )
    names = {player.name for player in singles_players}
    untranslated = [n for n in names if player_zh(n) == n]
    if names:
        ratio = len(untranslated) / len(names)
        if ratio > 0.7:
            warn.append(
                f"单打球员译名覆盖率偏低: {1 - ratio:.0%}（可扩充 zh/players.py）"
            )

    if digest.is_empty:
        warn.append("当天无巡回赛比赛（休赛日），内容为空档说明")

    if cover_copy is not None:
        from .render.titles import cover_fact_errors, daily_lead_match

        lead = daily_lead_match(digest)
        if lead is not None:
            fatal.extend(cover_fact_errors(lead, *cover_copy))
    return fatal, warn
