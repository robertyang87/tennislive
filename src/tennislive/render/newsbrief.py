"""把一份简报渲成**一条**微信消息。

版式的唯一判据：**读者不点开任何链接，也能知道今天发生了什么。**
原来那两条推送不满足它——全是英文标题加链接，内容在链接那一头。

所以顺序是：中文在上、英文在下、链接在最后。

- **中文标题**是这一条的主语，最大的字号
- **要点**每条一行，一条一个事实
- **原标题**压在下面一行、灰色小字——它不是给人读的，是**核实用的**：
  要去查这句话是谁说的，得有原文那一句
- **热度**（几家在报 / 连着几天 / 中文热搜撞上什么）跟在标题旁边，
  它是「为什么这条排在前面」的判据，不写出来就成了一个不透明的排序

⚠️ **底部那段说明不是客套**。今天有没有配模型、有几篇正文没抓到、
摘掉了几条导航页，全印在那儿——这个仓库里「兜底出事的时候不吭声」
栽过太多次，一份**看起来很干净**的简报和一份**真的很干净**的简报
必须能分得开。
"""

from __future__ import annotations

import html as _html
from datetime import date

from ..research.brief import Brief, Story

GREEN = "#087747"
GREY = "#7a8580"
INK = "#20302a"
PANEL = "#f4f8f6"
WARM = "#fdf6ec"


def _esc(text: object) -> str:
    return _html.escape(str(text or ""))


def _attr(text: object) -> str:
    return _html.escape(str(text or ""), quote=True)


def _heat_line(story: Story) -> str:
    """这条为什么排在这儿——把判据摆出来。"""
    heat = story.heat
    bits = [f"{heat.outlets} 家在报"]
    if heat.days_running > 1:
        bits.append(f"连着第 {heat.days_running} 天")
    if heat.zh_words:
        bits.append("中文热搜「" + "、".join(heat.zh_words[:2]) + "」")
    elif heat.trend_hits:
        bits.append(f"撞上 {heat.trend_hits} 条热搜")
    return " · ".join(bits)


def _known_block(story: Story) -> str:
    """撞上人工角度表的那条常青线。

    **和模型给的 `angle` 分开写**，因为两者的可信度完全不同：这一条背后
    有一份能翻的规则书或史料（`source` 那行就是去哪儿翻），模型那条是从
    今天这几篇正文里推的。合成一句会把「可核实」和「像那么回事」混起来，
    而这个仓库里那类混淆的代价一律是发出去之后才发现。
    """
    known = story.known
    if known is None:
        return ""
    done = (
        f'<span style="color:#c0392b;font-size:12px;">· 做过（{_esc(story.known_done_on)}）</span>'
        if story.known_done_on
        else ""
    )
    return (
        f'<div style="margin:8px 0 0;padding:8px 10px;background:#fff;border-radius:8px;'
        f'border-left:3px solid {GREEN};">'
        f'<div style="font-size:12px;color:{GREY};">底下压着的常青线 · '
        f"{_esc(known.label)} {done}</div>"
        f'<div style="font-size:13px;color:{INK};line-height:1.6;margin:2px 0;">'
        f"{_esc(known.evergreen)}</div>"
        f'<div style="font-size:12px;color:{INK};">开场问：{_esc(known.question)}</div>'
        f'<div style="font-size:11px;color:{GREY};">核实：{_esc(known.source)}</div>'
        f"</div>"
    )


def _origin_rows(story: Story, *, limit: int = 4) -> str:
    """原标题那几行：灰色小字 + 链接，核实用。"""
    rows = []
    for head in story.headlines[:limit]:
        title = _esc(head.get("title"))
        source = _esc(head.get("source"))
        url = str(head.get("url") or "")
        if url:
            title = f'<a href="{_attr(url)}" style="color:{GREEN};text-decoration:none;">{title}</a>'
        rows.append(
            f'<div style="margin:2px 0;font-size:12px;color:{GREY};line-height:1.5;">'
            f"{title} · {source}</div>"
        )
    return "".join(rows)


def _deep_block(story: Story, index: int) -> str:
    points = "".join(
        f'<div style="margin:4px 0;color:{INK};font-size:14px;line-height:1.6;">'
        f'<span style="color:{GREEN};">·</span> {_esc(p)}</div>'
        for p in story.points
    )
    why = (
        f'<div style="margin:8px 0 2px;font-size:13px;color:{INK};">'
        f'<b style="color:{GREEN};">为什么值得知道</b>　{_esc(story.why)}</div>'
        if story.why
        else ""
    )
    angle = (
        f'<div style="margin:2px 0 6px;font-size:13px;color:{INK};">'
        f'<b style="color:{GREEN};">可做的角度</b>　{_esc(story.angle)}</div>'
        if story.angle
        else ""
    )
    return (
        f'<div style="margin:0 0 16px;padding:12px;background:{PANEL};border-radius:10px;">'
        f'<div style="font-weight:800;font-size:16px;color:{INK};line-height:1.45;">'
        f'<span style="color:{GREEN};">{index}.</span> {_esc(story.title_zh)}</div>'
        f'<div style="margin:4px 0 8px;font-size:12px;color:{GREY};">🔥 {_heat_line(story)}</div>'
        f"{points}{why}{angle}{_known_block(story)}"
        f'<div style="margin-top:8px;border-top:1px solid #dde7e2;padding-top:6px;">'
        f'<div style="font-size:11px;color:{GREY};margin-bottom:2px;">原文</div>'
        f"{_origin_rows(story)}</div></div>"
    )


def _shallow_row(story: Story) -> str:
    """没深挖的那些：中译标题在上，原标题在下。"""
    head = story.headlines[0] if story.headlines else {}
    zh = story.title_zh
    en = _esc(head.get("title"))
    url = str(head.get("url") or "")
    if url:
        en = f'<a href="{_attr(url)}" style="color:{GREEN};text-decoration:none;">{en}</a>'
    # 没译成中文时不留一行空的——直接把原标题提上来当主语，
    # 并且这件事已经在底部的说明里交代过了。
    top = (
        f'<div style="font-size:14px;color:{INK};font-weight:600;line-height:1.5;">{_esc(zh)}</div>'
        if zh
        else ""
    )
    return (
        f'<div style="margin:0 0 10px;">'
        f"{top}"
        f'<div style="font-size:12px;color:{GREY};line-height:1.5;">{en} · '
        f'{_esc(head.get("source"))}　<span>{_heat_line(story)}</span></div>'
        f"</div>"
    )


def _zh_block(brief: Brief) -> str:
    """中文平台上的网球热词。

    **独立于上面的热点列表**：中文那边热而一家英文媒体都没报的事
    （郑钦文相关最典型），既聚不成簇也进不了深挖区，只有这一栏看得见。
    """
    if not brief.zh_hot:
        return ""
    rows = "".join(
        f'<div style="margin:3px 0;font-size:13px;line-height:1.5;">'
        f'<a href="{_attr(h.get("url"))}" style="color:{GREEN};text-decoration:none;">'
        f'{_esc(h.get("word"))}</a>'
        f'<span style="color:{GREY};font-size:12px;"> · {_esc(h.get("source"))} '
        f'第 {_esc(h.get("rank"))} 位</span></div>'
        for h in brief.zh_hot
    )
    return (
        f'<div style="margin:0 0 16px;padding:12px;background:{WARM};border-radius:10px;">'
        f'<div style="font-weight:800;font-size:15px;color:{INK};">中文平台上的网球热词 '
        f'<span style="color:{GREY};font-weight:400;font-size:12px;">'
        f"扫 {brief.zh_scanned} 条 / 中 {len(brief.zh_hot)} 条</span></div>"
        f"{rows}"
        f'<div style="color:{GREY};font-size:12px;margin-top:6px;">'
        "中文这边热、英文媒体还没报的事，只有这一栏看得见。</div></div>"
    )


def _footer(brief: Brief) -> str:
    """今天这份简报是怎么做出来的——**包括没做成的那些**。"""
    lines = list(brief.notes)
    if brief.dropped_nav:
        lines.append(f"摘掉 {len(brief.dropped_nav)} 条官网导航页（不是新闻）")
    failed = [
        f"{r.source}：{r.note}"
        for s in brief.stories
        for r in s.reads
        if not r.ok
    ]
    if failed:
        lines.append("没读到正文：" + "；".join(failed[:4]))
    body = "".join(f"<div>· {_esc(line)}</div>" for line in lines)
    return (
        f'<div style="margin-top:14px;padding-top:10px;border-top:1px solid #dde7e2;'
        f'color:{GREY};font-size:11px;line-height:1.7;">'
        "<div>要点由模型从上面那几篇原文提炼，<b>事实以原文为准</b>；"
        "角度是建议，动手前照「原文」那几行核一遍。</div>"
        f"{body}</div>"
    )


def render_brief_html(brief: Brief) -> str:
    """一份简报 → 一条 PushPlus 消息的正文。"""
    try:
        d = date.fromisoformat(brief.date)
        stamp = f"{d.month}.{d.day}"
    except ValueError:
        stamp = brief.date

    deep = brief.deep_stories
    shallow = brief.brief_stories
    head = (
        f'<div style="font-weight:800;font-size:18px;color:{INK};margin:0 0 4px;">'
        f"网球热点简报 · {stamp}</div>"
        f'<div style="color:{GREY};font-size:12px;margin:0 0 14px;">'
        f"扫了 {brief.news_count} 条官方与媒体新闻、中文平台 {brief.zh_scanned} 条，"
        f"聚出 {len(brief.stories)} 个热点，深挖 {len(deep)} 个。</div>"
    )

    body = "".join(_deep_block(s, i) for i, s in enumerate(deep, 1))
    if shallow:
        body += (
            f'<div style="font-weight:800;font-size:15px;color:{INK};margin:4px 0 10px;">'
            f"其余热点<span style=\"color:{GREY};font-weight:400;font-size:12px;\">"
            f"（只译标题）</span></div>"
            + "".join(_shallow_row(s) for s in shallow)
        )
    if not brief.stories:
        body = (
            f'<div style="padding:12px;background:{PANEL};border-radius:10px;'
            f'color:{INK};font-size:14px;">今天没有聚成簇的热点。'
            "底下那几行说明写着为什么。</div>"
        )

    return (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,'
        'PingFang SC,Helvetica,sans-serif;padding:10px;">'
        f"{head}{body}{_zh_block(brief)}{_footer(brief)}</div>"
    )
