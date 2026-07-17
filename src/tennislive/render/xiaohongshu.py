"""小红书文案生成：标题 ≤20 字、正文 ≤1000 字、话题标签.

自动发帖没有官方 API（详见 README），这里生成可直接复制粘贴的内容包，
配合 cards.py 生成的竖版卡片图使用。

正文按预算逐档收缩（先多放，超长就换小配额重新生成），
保证「中国军团 / 焦点赛果 / 今日看点」三个板块都不会被裁空。
"""

from __future__ import annotations

from ..digest import Digest
from ..timeutil import fmt_time_beijing
from .common import (
    curate_for_social,
    group_by_tournament,
    is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)
from .wechat import pick_headline

MAX_BODY = 950  # 小红书正文上限 1000 字，留余量

BASE_TAGS = ["#网球", "#WTA", "#ATP", "#网球时差", "#网球晨报"]

# 逐档收缩的配额：(中国军团, 赛果, 看点)
_QUOTAS = [(6, 10, 8), (5, 8, 6), (4, 6, 4), (3, 4, 3), (2, 3, 2)]


def post_title(digest: Digest) -> str:
    """≤20 字的标题，如 '🎾7.16网球晨报|辛纳进决赛'."""
    d = digest.today
    head = pick_headline(digest)
    title = f"🎾{d.month}.{d.day}网球晨报|{head}"
    if len(title) > 20:
        title = title[:19] + "…"
    return title


def _tags(digest: Digest) -> list[str]:
    from ..zh import player_zh

    tags = list(BASE_TAGS)
    for m in digest.results + digest.schedule:
        if is_chinese_involved(m):
            for p in m.home + m.away:
                zh = player_zh(p.name)
                if zh != p.name and (p.country or "").upper() in ("CHN", "CN"):
                    tag = f"#{zh}"
                    if tag not in tags:
                        tags.append(tag)
    seen_t = set()
    for g in group_by_tournament(digest.results + digest.schedule):
        if g.level in ("GS", "M1000", "W1000", "Finals") and g.name_zh not in seen_t:
            seen_t.add(g.name_zh)
            tag = f"#{g.name_zh}"
            if tag not in tags:
                tags.append(tag)
    return tags[:10]


def _hook(digest: Digest) -> str:
    """开头一句口语化钩子（小红书语气）."""
    head = pick_headline(digest)
    if "夺冠" in head:
        return f"起床刷到大新闻：{head}🏆"
    if "爆冷" in head or "掀翻" in head:
        return f"昨晚网坛炸了个冷门💥 {head}"
    if "止步" in head:
        return f"可惜了😢 {head}，但网球就是这样"
    return "边吃早餐边看，昨夜网坛 3 分钟速览👇"


def _build(digest: Digest, quota: tuple[int, int, int]) -> list[str]:
    cn_cap, res_cap, sched_cap = quota
    d = digest.today
    lines: list[str] = []
    lines.append(_hook(digest))
    lines.append("")
    lines.append(f"📅 {d.month}月{d.day}日 · 北京时间")
    lines.append("")

    focus = [m for m in digest.results + digest.schedule if is_chinese_involved(m)]
    if focus:
        lines.append("🇨🇳 中国军团")
        for m in focus[:cn_cap]:
            g = group_by_tournament([m])[0]
            r = match_round_display(m)
            label = f"{g.name_zh}{('·' + r) if r else ''}"
            # 赛事·轮次 与 对阵比分 分行，手机上更易读
            if m.status.is_final:
                lines.append(f"▪️{label}")
                lines.append(result_line(m))
            else:
                lines.append(f"▪️{fmt_time_beijing(m.start_utc)} {label}")
                lines.append(f"{side_display(m.home)} vs {side_display(m.away)}")
        lines.append("")

    results = [m for m in curate_for_social(digest.results) if m.is_singles]
    if results:
        lines.append("🏆 昨日焦点赛果")
        count = 0
        for group in group_by_tournament(results):
            if count >= res_cap:
                break
            shown_any = False
            for m in group.matches:
                if count >= res_cap:
                    break
                if not shown_any:
                    lines.append(f"—— {group.title} ——")
                    shown_any = True
                r = match_round_display(m)
                if r:
                    lines.append(f"▪️{r}")
                    lines.append(result_line(m))
                else:
                    lines.append(f"▪️{result_line(m)}")
                count += 1
        lines.append("")

    schedule = [m for m in curate_for_social(digest.schedule) if m.is_singles]
    if schedule:
        lines.append("⏰ 今日看点（北京时间）")
        count = 0
        for group in group_by_tournament(schedule):
            if count >= sched_cap:
                break
            for m in group.matches:
                if count >= sched_cap:
                    break
                r = match_round_display(m)
                lines.append(
                    f"▪️{fmt_time_beijing(m.start_utc)} {group.name_zh}"
                    f"{('·' + r) if r else ''}"
                )
                lines.append(
                    f"{side_display(m.home, with_seed=False)}"
                    f" vs {side_display(m.away, with_seed=False)}"
                )
                count += 1
        lines.append("")

    lines.append("你今晚打算熬夜看哪场？评论区聊聊👇")
    lines.append("关注 @网球时差 ⏰ 每天7:30帮你倒好网球时差")
    lines.append("")
    lines.append(" ".join(_tags(digest)))
    return lines


def to_post(digest: Digest) -> str:
    """完整帖子内容：标题 + 正文（一个文本文件，可直接复制）."""
    body_lines = _build(digest, _QUOTAS[0])
    for quota in _QUOTAS[1:]:
        if len("\n".join(body_lines)) <= MAX_BODY:
            break
        body_lines = _build(digest, quota)
    return "\n".join([post_title(digest), ""] + body_lines)
