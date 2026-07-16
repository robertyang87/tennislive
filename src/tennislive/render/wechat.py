"""微信公众号文章生成：Markdown（便于编辑）与内联样式 HTML（可直接粘贴/走 API）.

公众号编辑器会剥离 <style> 块，所以 HTML 必须全部内联样式。
"""

from __future__ import annotations

import re

from ..digest import Digest
from ..models import Match, MatchStatus
from ..timeutil import fmt_date_zh, fmt_time_beijing
from ..zh import player_zh
from .common import (
    curate_for_social,
    group_by_tournament,
    is_chinese_involved as _is_chinese_involved,
    match_round_display,
    result_line,
    side_display,
)


def pick_headline(digest: Digest) -> str:
    """标题亮点（全自动）：委托 titles 模块的规则选择."""
    if not (digest.results or digest.schedule):
        return "今日暂无巡回赛比赛"
    from .titles import pick_headline_auto

    return pick_headline_auto(digest)


def article_title(digest: Digest) -> str:
    d = digest.today
    return f"网球晨报 | {d.month}月{d.day}日 {pick_headline(digest)}"


# ---------- Markdown ----------

def to_markdown(digest: Digest) -> str:
    lines: list[str] = []
    lines.append(f"# {article_title(digest)}")
    lines.append("")
    lines.append(f"> {fmt_date_zh(digest.today)}（北京时间）· WTA/ATP 巡回赛每日速报")
    lines.append("")

    focus = [m for m in digest.results + digest.schedule if _is_chinese_involved(m)]
    if focus:
        lines.append("## 🇨🇳 中国军团")
        lines.append("")
        for m in focus:
            g_zh = group_by_tournament([m])[0]
            r = match_round_display(m)
            if m.status.is_final:
                lines.append(f"- **{g_zh.name_zh}**{('·' + r) if r else ''}：{result_line(m)}")
            else:
                t = fmt_time_beijing(m.start_utc)
                lines.append(
                    f"- **{g_zh.name_zh}**{('·' + r) if r else ''}：{t} "
                    f"{side_display(m.home)} vs {side_display(m.away)}"
                )
        lines.append("")

    results = curate_for_social(digest.results)
    live = curate_for_social(digest.live)
    schedule = curate_for_social(digest.schedule)

    if results:
        lines.append(f"## 🏆 最新赛果（{len(results)} 场）")
        lines.append("")
        for group in group_by_tournament(results):
            lines.append(f"### {group.title}")
            lines.append("")
            for m in group.matches:
                r = match_round_display(m)
                prefix = f"**{r}** " if r else ""
                lines.append(f"- {prefix}{result_line(m)}")
            lines.append("")

    if live:
        lines.append(f"## 🔴 正在进行（{len(live)} 场）")
        lines.append("")
        for group in group_by_tournament(live):
            lines.append(f"### {group.title}")
            lines.append("")
            for m in group.matches:
                r = match_round_display(m)
                prefix = f"**{r}** " if r else ""
                score = m.score_display(from_winner=False)
                lines.append(
                    f"- {prefix}{side_display(m.home)} vs {side_display(m.away)}"
                    + (f"　当前 {score}" if score else "")
                )
            lines.append("")

    if schedule:
        lines.append(f"## 📅 今日赛程（{len(schedule)} 场，北京时间）")
        lines.append("")
        for group in group_by_tournament(schedule):
            lines.append(f"### {group.title}")
            lines.append("")
            for m in group.matches:
                r = match_round_display(m)
                suffix = f"　·{r}" if r else ""
                lines.append(
                    f"- `{fmt_time_beijing(m.start_utc)}` "
                    f"{side_display(m.home)} vs {side_display(m.away)}{suffix}"
                )
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*时间均为北京时间；单打全收录，双打仅收录决赛与中国球员场次；"
        "数据来自公开比分接口，以官方为准。*"
    )
    lines.append("")
    return "\n".join(lines)


# ---------- 内联样式 HTML（公众号可直接粘贴） ----------

_S = {
    "h2": (
        "margin:28px 0 14px;padding:8px 14px;font-size:17px;font-weight:bold;"
        "color:#0b3d2e;background:linear-gradient(90deg,#d6f5e3,#ffffff);"
        "border-left:4px solid #16a34a;border-radius:4px;"
    ),
    "h3": (
        "margin:18px 0 8px;font-size:15px;font-weight:bold;color:#111;"
        "padding-bottom:4px;border-bottom:1px dashed #bbb;"
    ),
    "li": "margin:6px 0;font-size:14px;line-height:1.7;color:#333;",
    "meta": "font-size:13px;color:#888;margin:8px 0 20px;",
    "round": "color:#16a34a;font-weight:bold;margin-right:4px;",
    "time": (
        "display:inline-block;min-width:44px;color:#0b63c4;font-weight:bold;"
        "font-family:Menlo,monospace;margin-right:6px;"
    ),
    "footer": "font-size:12px;color:#aaa;margin-top:26px;",
}


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


# 旗帜 emoji（一对区域指示符）→ 旗帜小图。
# Windows 浏览器/编辑器不渲染旗帜 emoji（只显示字母码），HTML 版统一换成图片；
# 走公众号 API 发布时 publish 模块会把这些外链图转存为微信素材。
_FLAG_PAIR_RE = re.compile("([\U0001F1E6-\U0001F1FF])([\U0001F1E6-\U0001F1FF])")
FLAG_IMG_STYLE = (
    "width:20px;height:15px;display:inline-block;vertical-align:-2px;"
    "margin-right:3px;border-radius:2px;"
)


def _flag_img(match: re.Match) -> str:
    iso2 = "".join(chr(ord(c) - 0x1F1E6 + ord("a")) for c in match.groups())
    return (
        f'<img src="https://flagcdn.com/40x30/{iso2}.png" '
        f'alt="{iso2.upper()}" style="{FLAG_IMG_STYLE}" />'
    )


def _emoji_flags_to_img(html: str) -> str:
    return _FLAG_PAIR_RE.sub(_flag_img, html)


def to_html(digest: Digest) -> str:
    parts: list[str] = []
    parts.append(
        f'<p style="{_S["meta"]}">{_esc(fmt_date_zh(digest.today))}（北京时间）'
        f"· WTA/ATP 巡回赛每日速报</p>"
    )

    def emit_group_matches(matches: list[Match], mode: str) -> None:
        for group in group_by_tournament(matches):
            parts.append(f'<h3 style="{_S["h3"]}">{_esc(group.title)}</h3>')
            parts.append('<ul style="margin:0;padding-left:18px;">')
            for m in group.matches:
                r = match_round_display(m)
                round_html = (
                    f'<span style="{_S["round"]}">{_esc(r)}</span>' if r else ""
                )
                if mode == "result":
                    body = _esc(result_line(m))
                elif mode == "live":
                    score = m.score_display(from_winner=False)
                    body = _esc(
                        f"{side_display(m.home)} vs {side_display(m.away)}"
                        + (f"　当前 {score}" if score else "")
                    )
                else:
                    body = (
                        f'<span style="{_S["time"]}">{_esc(fmt_time_beijing(m.start_utc))}</span>'
                        + _esc(f"{side_display(m.home)} vs {side_display(m.away)}")
                    )
                parts.append(f'<li style="{_S["li"]}">{round_html}{body}</li>')
            parts.append("</ul>")

    focus = [m for m in digest.results + digest.schedule if _is_chinese_involved(m)]
    if focus:
        parts.append(f'<h2 style="{_S["h2"]}">🇨🇳 中国军团</h2>')
        parts.append('<ul style="margin:0;padding-left:18px;">')
        for m in focus:
            g = group_by_tournament([m])[0]
            r = match_round_display(m)
            label = f"{g.name_zh}{('·' + r) if r else ''}："
            if m.status.is_final:
                body = _esc(label + result_line(m))
            else:
                body = _esc(
                    f"{label}{fmt_time_beijing(m.start_utc)} "
                    f"{side_display(m.home)} vs {side_display(m.away)}"
                )
            parts.append(f'<li style="{_S["li"]}">{body}</li>')
        parts.append("</ul>")

    results = curate_for_social(digest.results)
    live = curate_for_social(digest.live)
    schedule = curate_for_social(digest.schedule)

    if results:
        parts.append(f'<h2 style="{_S["h2"]}">🏆 最新赛果（{len(results)} 场）</h2>')
        emit_group_matches(results, "result")
    if live:
        parts.append(f'<h2 style="{_S["h2"]}">🔴 正在进行（{len(live)} 场）</h2>')
        emit_group_matches(live, "live")
    if schedule:
        parts.append(
            f'<h2 style="{_S["h2"]}">📅 今日赛程（{len(schedule)} 场，北京时间）</h2>'
        )
        emit_group_matches(schedule, "schedule")

    parts.append(
        f'<p style="{_S["footer"]}">时间均为北京时间；单打全收录，双打仅收录决赛与'
        f"中国球员场次；数据来自公开比分接口，以官方为准。</p>"
    )
    return _emoji_flags_to_img("\n".join(parts))
