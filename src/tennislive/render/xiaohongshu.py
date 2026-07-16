"""小红书文案生成：标题 ≤20 字、正文 ≤1000 字、话题标签.

自动发帖没有官方 API（详见 README），这里生成可直接复制粘贴的内容包，
配合 cards.py 生成的竖版卡片图使用。
"""

from __future__ import annotations

from ..digest import Digest
from ..models import Match
from ..timeutil import fmt_time_beijing
from ..zh import player_zh
from .common import group_by_tournament, match_round_display, result_line, side_display
from .wechat import _is_chinese_involved, pick_headline

MAX_BODY = 950  # 小红书正文上限 1000 字，留些余量

BASE_TAGS = ["#网球", "#WTA", "#ATP", "#网球比分", "#每日赛报"]


def post_title(digest: Digest) -> str:
    """≤20 字的标题，如 '🎾7.16网球速报|辛纳进决赛'."""
    d = digest.today
    head = pick_headline(digest)
    title = f"🎾{d.month}.{d.day}网球速报|{head}"
    if len(title) > 20:
        title = title[:19] + "…"
    return title


def _tags(digest: Digest) -> list[str]:
    tags = list(BASE_TAGS)
    for m in digest.results + digest.schedule:
        if _is_chinese_involved(m):
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


def to_post(digest: Digest) -> str:
    """完整帖子内容：标题 + 正文 + 标签（一个文本文件，可直接复制）."""
    lines: list[str] = []
    d = digest.today
    lines.append(post_title(digest))
    lines.append("")
    lines.append(f"📅 {d.month}月{d.day}日 · 北京时间")
    lines.append("")

    body_budget = MAX_BODY

    focus = [m for m in digest.results + digest.schedule if _is_chinese_involved(m)]
    if focus:
        lines.append("🇨🇳 中国军团")
        for m in focus[:6]:
            g = group_by_tournament([m])[0]
            r = match_round_display(m)
            if m.status.is_final:
                lines.append(f"▪️{g.name_zh}{('·' + r) if r else ''} {result_line(m)}")
            else:
                lines.append(
                    f"▪️{g.name_zh}{('·' + r) if r else ''} "
                    f"{fmt_time_beijing(m.start_utc)} {side_display(m.home)} vs {side_display(m.away)}"
                )
        lines.append("")

    if digest.results:
        lines.append("🏆 昨日焦点赛果")
        count = 0
        for group in group_by_tournament(digest.results):
            if count >= 10:
                break
            shown_any = False
            for m in group.matches:
                if m.is_doubles:
                    continue  # 文案篇幅有限，只放单打，双打看图
                if count >= 10:
                    break
                if not shown_any:
                    lines.append(f"—— {group.title} ——")
                    shown_any = True
                r = match_round_display(m)
                lines.append(f"▪️{(r + ' ') if r else ''}{result_line(m)}")
                count += 1
        lines.append("")

    if digest.schedule:
        lines.append("⏰ 今日看点（北京时间）")
        count = 0
        for group in group_by_tournament(digest.schedule):
            if count >= 8:
                break
            for m in group.matches:
                if m.is_doubles or count >= 8:
                    continue
                r = match_round_display(m)
                lines.append(
                    f"▪️{fmt_time_beijing(m.start_utc)} {group.name_zh}"
                    f"{('·' + r) if r else ''} {side_display(m.home, with_seed=False)}"
                    f" vs {side_display(m.away, with_seed=False)}"
                )
                count += 1
        lines.append("")

    lines.append("完整赛程赛果看图片～")
    lines.append("")
    lines.append(" ".join(_tags(digest)))

    # 控制正文长度（标题行不计入正文）
    body = "\n".join(lines[2:])
    while len(body) > body_budget and len(lines) > 6:
        # 从"今日看点"往前裁剪
        for i in range(len(lines) - 4, 2, -1):
            if lines[i].startswith("▪️"):
                del lines[i]
                break
        else:
            break
        body = "\n".join(lines[2:])

    return "\n".join(lines)
