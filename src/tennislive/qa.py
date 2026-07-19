"""发布前自动质检：替代人工审核的最后一道闸.

只做能机器判断的硬检查；返回 (致命问题, 警告) 两级。
致命问题会让 CLI 以非零码退出，从而阻断当天的自动发布步骤。
"""

from __future__ import annotations

from .digest import Digest
from .zh import player_zh


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
    lines = xhs_post.splitlines()
    if lines and len(lines[0]) > 20:
        warn.append(f"小红书标题超长: {len(lines[0])} > 20")
    body = "\n".join(lines[2:]) if len(lines) > 2 else ""
    if len(body) > 1000:
        fatal.append(f"小红书正文超长: {len(body)} > 1000")

    # 译名覆盖率（信息性）
    names = {
        p.name
        for m in digest.results + digest.schedule
        for p in m.home + m.away
        if m.is_singles
    }
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
