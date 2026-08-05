"""tennislive 命令行入口.

用法示例（时间均为北京时间）：
    tennislive today                     # 今日赛程+赛果总览
    tennislive results --date yesterday  # 昨日赛果
    tennislive schedule --date tomorrow  # 明日赛程
    tennislive live                      # 进行中的比赛
    tennislive digest                    # 生成今日内容包（公众号+小红书+卡片图）
    tennislive publish wechat --dir output/2026-07-16 [--publish]
    tennislive publish pushplus --dir output/2026-07-16
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .digest import Digest, build_digest
from .models import Match, MatchStatus
from .sources import SourceError, fetch_day
from .timeutil import parse_date_arg
from .cdn import jsdelivr_base

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)


def _dump_json(obj, path: Path) -> None:
    def default(o):
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        return str(o)

    path.write_text(
        json.dumps(obj, default=default, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------- 查询类命令 ----------

def cmd_day(args, statuses: list[MatchStatus] | None, title: str) -> int:
    from .render.terminal import console, render_matches

    d = parse_date_arg(args.date)
    try:
        data = fetch_day(d, prefer=args.source)
    except SourceError as e:
        console.print(f"[red]抓取失败：{e}[/red]")
        return 1
    matches = data.matches
    if statuses is not None:
        matches = [m for m in matches if m.status in statuses]
    if args.json:
        print(
            json.dumps(
                [dataclasses.asdict(m) for m in matches],
                default=str,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    render_matches(matches, f"{d.isoformat()} {title}（数据源: {data.source}）")
    return 0


def cmd_today(args) -> int:
    from .render.terminal import console, render_day_summary

    d = parse_date_arg(args.date)
    try:
        data = fetch_day(d, prefer=args.source)
    except SourceError as e:
        console.print(f"[red]抓取失败：{e}[/red]")
        return 1
    if args.json:
        print(
            json.dumps(
                [dataclasses.asdict(m) for m in data.matches],
                default=str,
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    render_day_summary(d.isoformat(), data.finished(), data.live(), data.upcoming())
    return 0


# ---------- 内容生成 ----------

def cmd_knowledge_adhoc(args) -> int:
    """按指定 slug 单独生成一篇知识帖，不占用当天常规知识帖的位置。

    可指定 slug 从预先写好、事实核验过的选题池里精确选取；留空 --slug
    则复用常规每日流程同一套自动选题逻辑
    （tournament_story.tournament_story_candidates）——按当日真实赛事/
    球员热度、时效性与冷却期排序候选，逐个尝试配图，配图不达标的候选
    自动跳过换下一个，直到找到能完整发布的选题为止，无需人工挑 slug。
    知识帖要求可核实的事实与已授权配图，不支持凭空生成全新话题。
    """
    from .render.knowledge import generate_knowledge_package
    from .render.terminal import console
    from .render.tournament_story import (
        find_story_by_slug,
        mark_adhoc_knowledge_published,
        mark_story_used,
    )

    story = None
    if args.slug:
        story = find_story_by_slug(args.slug)
        if story is None:
            console.print(f"[red]未找到 slug 为 “{args.slug}” 的选题。[/red]")
            return 2
        if not story.image.exists():
            console.print(f"[red]选题 “{args.slug}” 缺少配图素材：{story.image}[/red]")
            return 2

    d = parse_date_arg(args.date)
    try:
        digest: Digest = build_digest(d, prefer=args.source)
    except SourceError as e:
        console.print(f"[red]抓取失败：{e}[/red]")
        return 1

    outdir = Path(args.outdir)
    try:
        generated = generate_knowledge_package(digest, outdir, theme=args.theme, story=story)
    except Exception as e:  # noqa: BLE001 - surface the real reason before failing
        console.print(f"[red]知识帖生成失败：{e}[/red]")
        detail_path = outdir / "visual_sources.json"
        if detail_path.is_file():
            console.print(f"[yellow]失败详情（{detail_path}）：[/yellow]")
            console.print(detail_path.read_text("utf-8"))
        return 2
    if generated is None:
        reason = f"{outdir}" if args.slug else "没有找到时效匹配、配图达标的候选选题（已按热度试遍候选池）"
        console.print(f"[red]知识帖生成失败：{reason}[/red]")
        return 2

    mark_story_used(generated.slug, digest.today)
    # A deliberate/hotspot ad-hoc post claims today's knowledge slot so the
    # daily digest won't auto-select a second, unrelated knowledge post on top
    # of it. Ad-hoc itself never checks this marker — a hotspot can always ship.
    mark_adhoc_knowledge_published(digest.today)
    console.print(f"[green]知识帖已生成：{outdir}（slug={generated.slug}）[/green]")
    return 0


def cmd_flash_card(args) -> int:
    """生成一张"单图快讯卡"（及时新闻 → 一张图即时输出），并附小红书文案。

    快讯卡不套四卡知识帖模板、不需要外部球员照，因此能当天快速产出。事实
    由调用方提供（本命令不编造）。涉及敏感社会/政治/法律/医疗话题的新闻，
    默认拦截并提示转人工复核，除非显式 --force。
    """
    from .render.flashcard import generate_flash_card
    from .render.sensitivity import sensitive_category
    from .render.terminal import console

    category = sensitive_category(
        args.headline, args.event, args.punch, args.who
    )
    if category and not args.force:
        console.print(
            f"[yellow]该快讯命中敏感类别（{category}），默认转人工复核，未生成。"
            f"确认无误可加 --force 强制生成。[/yellow]"
        )
        return 3

    d = parse_date_arg(args.date)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    try:
        card_path = generate_flash_card(
            args.headline,
            event=args.event,
            when=args.when,
            where=args.where,
            who=args.who,
            punch=args.punch,
            source_label=args.source_label,
            date_label=f"{d.month}.{d.day}",
            out_path=outdir / "flash-card.jpg",
            theme=args.theme,
        )
    except Exception as e:  # noqa: BLE001 - surface the real reason
        console.print(f"[red]快讯卡渲染失败：{e}[/red]")
        return 2

    meta = "｜".join(
        part
        for part in (
            f"🗓 {args.when}" if args.when else "",
            f"📍 {args.where}" if args.where else "",
            f"👤 {args.who}" if args.who else "",
        )
        if part
    )
    question = args.question or "你怎么看这件事？评论区聊聊。"
    copy = "\n\n".join(
        part
        for part in (
            args.headline,
            meta,
            args.event,
            args.punch,
            f"💬 {question}",
            "关注 @网球时差｜第一时间把网球场内外的故事讲给你听。",
            "#网球 #网球快讯 #网球时差",
        )
        if part
    )
    (outdir / "flash_copy.txt").write_text(copy, encoding="utf-8")
    if category:
        console.print(f"[yellow]注意：该快讯属敏感类别（{category}），已按 --force 生成。[/yellow]")
    console.print(f"[green]快讯卡已生成：{card_path}（文案：{outdir / 'flash_copy.txt'}）[/green]")
    return 0


def cmd_flash_radar(args) -> int:
    """自动扫描场外网球新闻，筛出可发候选进待发队列。

    比赛新闻（有比分/击败/晋级/夺冠等）留给日报，不在此重复；场外新闻再过
    敏感度闸门，敏感话题转人工。候选只携带新闻源已有的真实字段（标题、来源、
    链接、时间），时间/地点/人物/事件的细化由人工用 flash-card 补全后再发。
    """
    import dataclasses as _dc
    import html as _html

    from .render.terminal import console
    from .research.news_flash import offcourt_flash_candidates
    from .research.trends import fetch_trend_signals

    d = parse_date_arg(args.date)
    signals, status = fetch_trend_signals()
    signal_dicts = [_dc.asdict(s) for s in signals]
    candidates = offcourt_flash_candidates(signal_dicts, limit=args.max)

    outdir = Path(args.outdir) / d.isoformat() / "flash_radar"
    outdir.mkdir(parents=True, exist_ok=True)
    _dump_json(
        {
            "date": d.isoformat(),
            "source_status": status,
            "count": len(candidates),
            "candidates": candidates,
        },
        outdir / "flash_radar_queue.json",
    )

    if not candidates:
        console.print("[yellow]本次没有可发的场外新闻候选[/yellow]")
        return 0

    items = "".join(
        f'<div style="margin:0 0 12px;">'
        f'<a href="{_html.escape(c["url"], quote=True)}" '
        'style="color:#087747;font-weight:600;text-decoration:none;">'
        f'{_html.escape(c["title"])}</a>'
        f'<div style="color:#7a8580;font-size:12px;">{_html.escape(c["source"])}</div>'
        "</div>"
        for c in candidates
    )
    push_html = (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:10px;">'
        f'<div style="font-weight:800;font-size:17px;margin:0 0 12px;">'
        f"场外网球快讯候选 · {d.month}.{d.day}（{len(candidates)} 条）</div>"
        f"{items}"
        '<div style="color:#7a8580;font-size:12px;margin-top:10px;">'
        "挑一条用 tennislive flash-card 补全时间/地点/人物/事件后成稿。</div></div>"
    )
    (outdir / "flash_radar_push.html").write_text(push_html, encoding="utf-8")

    if not args.no_cards:
        from .render.flashcard import generate_flash_card

        for index, c in enumerate(candidates[: args.draft_cards]):
            try:
                generate_flash_card(
                    c["title"],
                    source_label=(
                        f'资料：{c["source"]} · 网球时差整理'
                        if c["source"]
                        else "资料：网球时差整理"
                    ),
                    date_label=f"{d.month}.{d.day}",
                    out_path=outdir / f"draft_{index:02d}.jpg",
                    theme=args.theme,
                )
            except Exception as e:  # noqa: BLE001
                console.print(f"[yellow]草稿卡渲染失败（跳过）：{e}[/yellow]")

    console.print(
        f"[green]场外快讯候选已生成：{outdir}（{len(candidates)} 条待人工成稿）[/green]"
    )
    return 0


def cmd_explainer(args) -> int:
    """为一个知识选题生成 AI 旁白解说视频（前因后果 / 技术原理 / 当今现状）。

    适合抽象、拿不到合格真实照片的知识点（如鹰眼/计分制）。解说词由该选题
    已核验的事实改写而成，画面为文字卡与示意图，不伪造真实赛场影像。
    """
    from .render.terminal import console
    from .render.tournament_story import find_story_by_slug
    from .video.explainer import ExplainerVideoError, generate_explainer_video

    story = find_story_by_slug(args.slug)
    if story is None:
        console.print(f"[red]未找到 slug 为 “{args.slug}” 的选题。[/red]")
        return 2
    d = parse_date_arg(args.date)
    try:
        out = generate_explainer_video(
            story,
            args.outdir,
            theme=args.theme,
            **{k: v for k, v in (("voice", args.voice), ("rate", args.rate),
                                 ("pitch", args.pitch)) if v},
        )
    except ExplainerVideoError as e:
        console.print(f"[red]解说视频生成失败：{e}[/red]")
        return 2

    # Leave a push body beside the video so `publish pushplus` can send the
    # slides to WeChat; the MP4 itself cannot play inline in a push.
    from .video.explainer import (
        explainer_push_html,
        explainer_script,
        explainer_xiaohongshu,
    )

    # 只要 to_copy_page：复制页可达性由 `publish pushplus` 在提交之后探，
    # 不在这儿探。见 drop_dead_copy_button 的注释。
    from .render.pushmsg import to_copy_page

    outdir = Path(args.outdir)
    segments = explainer_script(story)
    xhs_text = explainer_xiaohongshu(story, segments, f"{d.month}.{d.day}")
    (outdir / "xiaohongshu.txt").write_text(xhs_text, encoding="utf-8")
    (outdir / "copy.html").write_text(to_copy_page(xhs_text), encoding="utf-8")

    # 这里**不探**复制页。渲染排在提交之前，那一刻 copy.html 还没进仓库，
    # Pages 必然取不到——在这儿探等于每次都把按钮拿掉，连 main 上本来能用的
    # 也一起拿掉（2026-07-29 蒂姆那条推送就是这么少了按钮的，run 30432435525）。
    # 闸装在 `publish pushplus` 里，那一步跑在提交之后，见 drop_dead_copy_button。
    (outdir / "push.html").write_text(
        explainer_push_html(segments, outdir, date=d, xhs_text=xhs_text),
        encoding="utf-8",
    )
    (outdir / "wechat_title.txt").write_text(
        f"{story.title}｜{segments[0].title}", encoding="utf-8"
    )
    console.print(f"[green]解说视频已生成：{out}[/green]")
    return 0


def cmd_brief(args) -> int:
    """**一份简报，一条推送。**

    这条命令替掉的是原来那两条微信（「场外网球快讯候选」＋「今日选题候选」）。
    它们的毛病不是各自做得不好，是**合起来仍然读不出内容**：一条是 8 条英文
    标题加链接，另一条大多数日子是空的。

    现在一趟做完：扫信号 → 摘掉官网导航页 → 聚簇 → 按热度排 → 前 N 条抓正文
    出中文要点 → 其余至少给中译标题 → 渲一份 HTML。

    ⚠️ **空产也要写出产物**。一条热点都没有的日子，`brief.json` 里的
    `source_status` / `notes` / `dropped_nav` 才是当天唯一能查的东西——
    「今天没热点」和「抓取全挂了」在推送正文里长得一模一样。
    """
    import dataclasses as _dc

    from .render.newsbrief import render_brief_html
    from .render.terminal import console
    from .research.brief import Chat, build_brief
    from .research.newsfeeds import fetch_readable_news
    from .research.topic_radar import previous_slugs
    from .research.trends import fetch_trend_signals
    from .research.zh_trends import fetch_zh_hot

    d = parse_date_arg(args.date)
    signals, status = fetch_trend_signals()
    signal_dicts = [_dc.asdict(s) for s in signals]
    # 官方新闻那一路才是选题来源；大众热搜（足球运动员、流行歌手）只当热度
    # 加成，混进簇里只会把它搅乱——这条口径和原来的 topic-radar 一致。
    news = [s for s in signal_dicts if str(s.get("kind") or "") == "official-news"]
    trends_only = [s for s in signal_dicts if str(s.get("kind") or "") == "search-trend"]
    # ⚠️ **发现和阅读是两路**。上面那一路走 Google News，覆盖广（含 ATP/WTA
    # 官网）但链接是读不了的包装页；这一路是发布方原生 RSS，源少但链接是
    # 真地址、正文抓得到。两路一起进聚类，同一件事自然并成一簇——于是那一簇
    # 既有官网标题撑热度，又有一条读得到的链接供深挖。详见 newsfeeds.py。
    readable, readable_status = fetch_readable_news()
    news.extend(readable)
    status.update(readable_status)
    zh = fetch_zh_hot()
    zh_dicts = [h.as_dict() for h in zh.hits]
    status.update(zh.status)

    chat = Chat()
    if not chat.ready:
        # **默认那条不许悄悄走。** 没有 token 时这份简报没有中译也没有要点，
        # 而它看起来和「今天新闻少」一模一样。
        console.print(
            "[yellow]没配 ANTHROPIC_API_KEY：本次没有中译也没有要点，"
            "简报退回「只有英文标题和热度」。[/yellow]"
        )

    brief = build_brief(
        d.isoformat(),
        news=news,
        trend_signals=trends_only,
        zh_signals=zh_dicts,
        zh_scanned=zh.scanned,
        source_status=status,
        prev_slugs=previous_slugs(Path(args.outdir), d.isoformat(), back=args.persist_days),
        deep=args.deep,
        limit=args.max,
        min_sources=args.min_sources,
        chat=chat,
    )

    outdir = Path(args.outdir) / d.isoformat() / "brief"
    outdir.mkdir(parents=True, exist_ok=True)
    _dump_json(brief.as_dict(), outdir / "brief.json")
    (outdir / "brief_push.html").write_text(render_brief_html(brief), encoding="utf-8")

    console.print(
        f"[cyan]新闻 {brief.news_count} 条（摘掉导航页 {len(brief.dropped_nav)} 条）"
        f" → 热点 {len(brief.stories)} 个，深挖 {len(brief.deep_stories)} 个[/cyan]"
    )
    console.print(
        f"[cyan]中文平台扫了 {zh.scanned} 条 → 网球相关 {len(zh_dicts)} 条[/cyan]"
    )
    for story in brief.stories:
        mark = "深" if story.deep else "浅"
        console.print(
            f"  [{mark}] {story.title_zh or story.headlines[0].get('title', '')}"
            f"　{story.heat.outlets} 家 · 分 {story.heat.score}"
            + (f" · {story.note}" if story.note else "")
        )
    # 退化和失败逐条打出来：读日志的人不该再去翻 JSON 才知道今天缺了什么。
    for note in brief.notes:
        console.print(f"[yellow]· {note}[/yellow]")
    if not brief.stories:
        console.print("[yellow]今天没有聚成簇的热点——先看 brief.json 的 source_status[/yellow]")
    return 0


def cmd_topic_radar(args) -> int:
    """把今天扫来的新闻**提炼成选题**（不是快讯）。

    `flash-radar` 做的是「一条新闻 → 一张快讯卡」，讲发生了什么；这条做的是
    `docs/newshook-topics.md` 那个形状：**新闻钩子 + 底下压着的常青线**。

    两步都是机器能做的：同一天里几家在报同一件事才算一个新闻点（聚类），
    再拿这一簇去撞人工维护的角度表（`research/topic_radar.ANGLES`）。
    **撞不上就不猜**——那些进「没对上角度的热点」，让人自己看。
    """
    import dataclasses as _dc
    import html as _html

    from .render.terminal import console
    from .research.topic_radar import (
        distil_topics,
        leftover_terms,
        previous_slugs,
    )
    from .research.trends import fetch_trend_signals
    from .research.zh_trends import fetch_zh_hot

    d = parse_date_arg(args.date)
    signals, status = fetch_trend_signals()
    signal_dicts = [_dc.asdict(s) for s in signals]
    # 只用官方新闻源：search-trend 那一路是大众热搜（足球运动员、流行歌手），
    # 从来做不成网球选题，混进来只会把簇搅乱。
    news = [s for s in signal_dicts if str(s.get("kind") or "") == "official-news"]
    # 大众热搜那一路（search-trend）不做选题来源，但**是舆论热度的证据**：
    # 撞上说明这件事溢出了网球圈。只当加成，不能靠它把没人报的东西顶上来。
    trends_only = [s for s in signal_dicts if str(s.get("kind") or "") == "search-trend"]
    # 中文平台热搜（微博/抖音/小红书/微信）。**这是「舆论热点」判断原来最大的
    # 洞**：读者在中文平台上，而热度原来完全由英文媒体的家数决定。中文那边
    # 炸了而英文没报的事，整套一点都看不见。
    zh = fetch_zh_hot()
    zh_dicts = [h.as_dict() for h in zh.hits]
    status.update(zh.status)
    prev = previous_slugs(Path(args.outdir), d.isoformat(), back=args.persist_days)
    topics, leftover = distil_topics(
        news, min_sources=args.min_sources, limit=args.max,
        trend_signals=trends_only, zh_signals=zh_dicts, prev_slugs=prev,
    )

    outdir = Path(args.outdir) / d.isoformat() / "topic_radar"
    outdir.mkdir(parents=True, exist_ok=True)
    _dump_json(
        {
            "date": d.isoformat(),
            "source_status": status,
            "news_signals": len(news),
            "trend_signals": len(trends_only),
            # 中文热搜**自己单独列一栏**，不只是当热度加成：中文平台上热而
            # 一家英文媒体都没报的事（郑钦文相关最典型），既撞不上簇也撞不上
            # 角度，只有这一栏能让它被看见。
            "zh_scanned": zh.scanned,
            "zh_hot": zh_dicts,
            "zh_near_miss": zh.near,
            "count": len(topics),
            "topics": [t.as_dict() for t in topics],
            # 空产要自证：一条候选都没有时，得能分清是「今天没热点」还是
            # 「热点都没撞上表里的角度」。后者说明该往 ANGLES 里补一条。
            "unmatched_clusters": len(leftover),
            "unmatched_terms": [
                {"term": t, "clusters": n} for t, n in leftover_terms(leftover)
            ],
        },
        outdir / "topic_radar_queue.json",
    )

    console.print(
        f"[cyan]新闻信号 {len(news)} 条 → 选题候选 {len(topics)} 个"
        f"，没对上角度的热点簇 {len(leftover)} 个[/cyan]"
    )
    console.print(
        f"[cyan]中文平台扫了 {zh.scanned} 条 → 网球相关 {len(zh_dicts)} 条"
        f"（差一点的 {len(zh.near)} 条）[/cyan]"
    )
    for h in zh.hits:
        console.print(f"  中 {h.source} #{h.rank} {h.word} · 命中 {'、'.join(h.matched)}")
    if not topics:
        console.print("[yellow]今天没有对上角度的选题候选[/yellow]")
        if leftover:
            console.print(
                "[yellow]但有 "
                f"{len(leftover)} 个热点簇没对上——看 unmatched_terms，"
                "该往 ANGLES 里补角度了[/yellow]"
            )

    # 中文平台那一栏**独立于选题候选**：一条候选都没有、中文那边却热着，
    # 是最该被看见的情况，不是「今天没东西」。
    zh_block = ""
    if zh_dicts:
        rows = "".join(
            f'<div style="margin:3px 0;"><a href="{_html.escape(h["url"], quote=True)}" '
            'style="color:#087747;text-decoration:none;">'
            f'{_html.escape(h["word"])}</a>'
            f'<span style="color:#7a8580;"> · {_html.escape(h["source"])} '
            f'第 {h["rank"]} 位 · 命中 {_html.escape("、".join(h["matched"]))}</span></div>'
            for h in zh_dicts
        )
        zh_block = (
            '<div style="margin:0 0 18px;padding:10px;background:#fdf6ec;'
            'border-radius:8px;">'
            '<div style="font-weight:800;font-size:15px;">中文平台上的网球热词 '
            f'<span style="color:#7a8580;font-weight:400;font-size:12px;">'
            f'扫 {zh.scanned} 条 / 中 {len(zh_dicts)} 条</span></div>'
            f"{rows}"
            '<div style="color:#7a8580;font-size:12px;margin-top:6px;">'
            "这一栏不经过角度表——中文那边热而英文媒体没报的事，只有这儿看得见。"
            "</div></div>"
        )
    if not topics and not zh_block:
        return 0

    blocks = []
    for t in topics:
        done = (
            f'<span style="color:#c0392b;">· 做过（{_html.escape(t.published_on)}）</span>'
            if t.published_on
            else ""
        )
        heads = "".join(
            f'<div style="margin:2px 0;"><a href="{_html.escape(h["url"], quote=True)}" '
            'style="color:#087747;text-decoration:none;">'
            f'{_html.escape(h["title"])}</a>'
            f'<span style="color:#7a8580;"> · {_html.escape(h["source"])}</span></div>'
            for h in t.as_dict()["headlines"][:4]
        )
        blocks.append(
            '<div style="margin:0 0 18px;padding:10px;background:#f4f8f6;border-radius:8px;">'
            f'<div style="font-weight:800;font-size:16px;">{_html.escape(t.angle.label)} '
            f'<span style="color:#7a8580;font-weight:400;font-size:12px;">'
            f"{len(t.sources)} 家在报"
            + (f" · 连着第 {t.heat.days_running} 天" if t.heat and t.heat.days_running > 1 else "")
            + (f" · 撞上 {t.heat.trend_hits} 条热搜" if t.heat and t.heat.trend_hits else "")
            + (
                f" · 中文热搜 {_html.escape('、'.join(t.heat.zh_words))}"
                if t.heat and t.heat.zh_words else ""
            )
            + f"</span> {done}</div>"
            f'<div style="margin:6px 0;color:#20302a;">{_html.escape(t.angle.evergreen)}</div>'
            f'<div style="color:#7a8580;font-size:12px;">核实：'
            f"{_html.escape(t.angle.source)}</div>"
            f'<div style="color:#20302a;font-size:13px;margin:6px 0;">开场问：'
            f"{_html.escape(t.angle.question)}</div>"
            f"{heads}</div>"
        )
    push_html = (
        '<div style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;padding:10px;">'
        f'<div style="font-weight:800;font-size:17px;margin:0 0 12px;">'
        f"今日选题候选 · {d.month}.{d.day}（{len(topics)} 个"
        # 候选 0 个、中文平台却热着，是最该被看见的情况——标题里就要说出来，
        # 否则一句「0 个」会让人直接划走。
        + (f"，另有中文热词 {len(zh_dicts)} 条" if not topics and zh_dicts else "")
        + "）</div>"
        f"{''.join(blocks)}{zh_block}"
        '<div style="color:#7a8580;font-size:12px;margin-top:10px;">'
        # 这儿是 HTML，不是 Markdown——原来写的 `**事实一条都没核**` 在微信里
        # 就是四个星号，渲出来看一眼就发现了。
        "角度是人工表里对上的，<b>事实一条都没核</b>——按「核实」那行去翻原始出处。"
        "</div></div>"
    )
    (outdir / "topic_radar_push.html").write_text(push_html, encoding="utf-8")
    for t in topics:
        mark = f"（做过 {t.published_on}）" if t.published_on else ""
        heat = t.heat
        extra = (
            f" · 连着第 {heat.days_running} 天" if heat and heat.days_running > 1 else ""
        ) + (f" · 撞上 {heat.trend_hits} 条热搜" if heat and heat.trend_hits else "") + (
            f" · 中文热搜「{'、'.join(heat.zh_words)}」" if heat and heat.zh_words else ""
        )
        console.print(
            f"  ★ {t.angle.label}{mark} · {len(t.sources)} 家在报{extra}"
        )
    return 0


def cmd_coverage(args) -> int:
    """只出「数据源与赛事覆盖」这一张报告，不生成任何内容包。

    这段原来长在 `cmd_digest`（日报生成器）里，`probe.yml` 于是要靠
    `tennislive digest --no-cards` 顺带把它带出来——**为了一张覆盖率报告，
    跑一整套日报**。2026-07-31 日报停产、`cmd_digest` 删掉，把它抽出来独立成
    命令：抓一天数据、写一张 coverage.txt，就这些。
    """
    from .digest import build_digest
    from .render.coverage import coverage_report
    from .render.terminal import console

    d = parse_date_arg(args.date)
    try:
        # **`fetch_day` 给的是 `DailyData`，`coverage_report` 要的是 `Digest`。**
        # 第一版直接把 `fetch_day` 的结果传下去了，本地跑不到（沙箱没网），
        # 一上 runner 就 `AttributeError: 'DailyData' object has no attribute
        # 'results'`（run 30653131605）。**「写了」不等于「跑过」**——这条这次
        # 是靠 CI 抓到的，不是靠我自己。
        digest = build_digest(d, prefer=args.source)
    except SourceError as exc:
        console.print(f"[red]{d} 抓取失败：{exc}[/red]")
        return 1
    report = coverage_report(digest)
    outdir = Path(args.outdir) / d.isoformat()
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / "coverage.txt"
    path.write_text(report, encoding="utf-8")
    console.print(report)
    console.print(f"[green]已写[/green] {path}")
    return 0


def cmd_content(args) -> int:
    """统一内容雷达：自动选择完赛热点或赛前焦点并生成完整待发布包。"""
    import re
    from datetime import timedelta

    from .content_ops import prune_state, select_content
    from .render.content_package import (
        ContentGenerationError,
        generate_content_package,
    )
    from .render.terminal import console
    from .timeutil import beijing_today, now_beijing

    today = beijing_today()
    now = now_beijing()
    manifest_path = Path(args.manifest) if args.manifest else None
    if manifest_path and manifest_path.exists():
        manifest_path.unlink()

    matches = []
    for requested in (
        today - timedelta(days=1),
        today,
        today + timedelta(days=1),
    ):
        try:
            matches.extend(fetch_day(requested, prefer=args.source).matches)
        except SourceError as exc:
            console.print(f"[yellow]{requested} 抓取失败：{exc}[/yellow]")
    if not matches:
        console.print("[red]无数据，跳过[/red]")
        return 1

    # 同源跨日接口可能返回同一场；优先保留已完赛和信息更完整的版本。
    priority = {
        MatchStatus.SCHEDULED: 0,
        MatchStatus.LIVE: 1,
        MatchStatus.FINISHED: 2,
        MatchStatus.RETIRED: 2,
        MatchStatus.WALKOVER: 2,
    }
    deduped: dict[tuple[str, str], Match] = {}
    for match in matches:
        key = (match.tour.value, match.match_id)
        current = deduped.get(key)
        if current is None or priority.get(match.status, -1) > priority.get(
            current.status, -1
        ):
            deduped[key] = match
    matches = list(deduped.values())

    from .research.trends import apply_trend_signals

    trend_result = apply_trend_signals(matches, now=now)
    console.print(
        f"趋势雷达 {trend_result.signals} 条信号，"
        f"命中 {trend_result.matched_matches} 场比赛"
    )

    state_path = Path("data/content_state.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state: dict[str, str] = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    state = prune_state(state, today=today)

    legacy_ids: set[str] = set()
    legacy_path = Path("data/flash_state.json")
    if legacy_path.exists():
        legacy_ids = set(json.loads(legacy_path.read_text(encoding="utf-8")))

    picks = select_content(
        matches,
        now=now,
        state=state,
        legacy_result_ids=legacy_ids,
    )
    if not picks:
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        console.print("本轮没有达到规则的待发布内容")
        return 0

    items = []
    stamp = now.strftime("%H%M")
    for index, pick in enumerate(picks):
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", pick.match.match_id)[-32:]
        package_dir = (
            Path(args.outdir)
            / today.isoformat()
            / "queue"
            / f"{pick.kind}_{stamp}_{index:02d}_{safe_id}"
        )
        try:
            item = generate_content_package(
                pick,
                outdir=package_dir,
                today=today,
                generated_at=now,
            )
        except ContentGenerationError as exc:
            console.print(f"[red]内容质检未通过：{exc}[/red]")
            return 2
        items.append(item)
        state[pick.key] = today.isoformat()
        label = "完赛热点" if pick.kind == "result" else "赛前焦点"
        console.print(f"[green]{label} · {item['title']}[/green]")

    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "generated_at": now.isoformat(),
                    "date": today.isoformat(),
                    "items": items,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    console.print(f"已生成 {len(items)} 个完整待发布内容包")
    return 0


# ---------- 发布 ----------

def cmd_publish_wechat(args) -> int:
    from .publish.wechat_mp import (
        WeChatError,
        publish_article,
        publish_image_post,
    )
    from .render.terminal import console

    d = Path(args.dir)
    title_f = d / "wechat_title.txt"
    title = (
        title_f.read_text(encoding="utf-8").strip() if title_f.exists() else "网球晨报"
    )
    cards_dir = d / "cards"
    cards = sorted(
        path
        for path in cards_dir.glob("card_*.*")
        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    )

    try:
        if args.style == "pic":
            # 小红书式图片消息：竖版卡片轮播 + 文案
            xhs_f = d / "xiaohongshu.txt"
            if not cards:
                console.print(f"[red]{cards_dir} 里没有卡片图[/red]")
                return 1
            content = ""
            if xhs_f.exists():
                lines = xhs_f.read_text(encoding="utf-8").splitlines()
                content = "\n".join(lines[2:]) if len(lines) > 2 else ""
            result = publish_image_post(
                title=title,
                content=content,
                images=cards,
                do_publish=args.publish,
            )
        else:
            html_f = d / "wechat.html"
            if not html_f.exists():
                console.print(f"[red]{html_f} 不存在，请先运行 tennislive digest[/red]")
                return 1
            cover = next((p for p in cards if "cover" in p.name), None)
            if cover is None:
                console.print("[red]找不到封面卡片（图文消息必须有封面）[/red]")
                return 1
            content_images = [p for p in cards if "cover" not in p.name]
            result = publish_article(
                title=title,
                html_content=html_f.read_text(encoding="utf-8"),
                cover_image=cover,
                content_images=content_images,
                digest=title,
                do_publish=args.publish,
            )
    except WeChatError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    console.print(f"[green]公众号操作成功：{result}[/green]")
    if not args.publish:
        console.print("已存入草稿箱。加 --publish 可直接发布。")
    return 0


def cmd_publish_pushplus(args) -> int:
    from .publish.pushplus import PushPlusError, push
    from .render.pushmsg import (
        copy_page_fingerprint,
        drop_dead_copy_button,
        pin_asset_revision,
    )
    from .render.terminal import console

    d = Path(args.dir)
    title_f = d / "wechat_title.txt"
    xhs_f = d / "xiaohongshu.txt"
    # 优先用手机推送专用模板；老目录没有时回退公众号 HTML
    push_f, html_f = d / "push.html", d / "wechat.html"
    src = push_f if push_f.exists() else html_f
    if not src.exists():
        console.print(f"[red]{src} 不存在，请先运行 tennislive digest[/red]")
        return 1
    title = "网球时差"
    if xhs_f.exists():
        xhs_lines = xhs_f.read_text(encoding="utf-8").splitlines()
        title = next((line.strip() for line in xhs_lines if line.strip()), title)
    elif title_f.exists():
        title = title_f.read_text(encoding="utf-8").strip() or title
    html = src.read_text(encoding="utf-8")
    # 兼容旧模板：去掉图片占位符
    import re

    html = re.sub(r"\{\{IMAGE:[^}]+\}\}", "", html)
    html = pin_asset_revision(html, os.environ.get("TENNISLIVE_ASSET_REV", ""))
    # 发之前探一次复制页，取不到就摘掉那个按钮。**这一步跑在提交之后**，
    # 所以是唯一能给出真实答案的时刻；渲染那会儿文件还没进仓库，探必然失败。
    # 装在这里，解说片 / 知识帖 / 赛程包三条线一起护住。
    # 拿本地 copy.html 的标题当指纹：线上那份必须是**这一版**才放按钮。
    # 只探可达会漏掉「Pages 上还是旧包」——旧内容照样 200，比死链更难发现。
    expect = copy_page_fingerprint(d / "copy.html")
    html, live_copy = drop_dead_copy_button(html, expect=expect)
    if live_copy:
        console.print(f"[green]复制页可达且是这一版[/green] {live_copy}")
    else:
        console.print(
            "[yellow]复制页取不到或还是旧版，本次不放该按钮；正文已整段渲染在"
            "消息里，可长按复制[/yellow]"
        )
    try:
        push(title, html, asset_dir=d)
    except PushPlusError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    console.print("[green]已推送到微信（PushPlus）[/green]")
    return 0


def cmd_publish_flash(args) -> int:
    """提交图片后发送内容包，固定资源版本以绕开 CDN 旧图缓存。"""
    import html
    import re

    from .publish.pushplus import PushPlusError, push
    from .render.terminal import console

    manifest = Path(args.manifest)
    if not manifest.exists():
        console.print(f"[red]{manifest} 不存在[/red]")
        return 1
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    if not items:
        console.print("没有待发送热点")
        return 0

    repository = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
    revision = os.environ.get("TENNISLIVE_ASSET_REV", "main")
    if revision != "main" and not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
        revision = "main"
    asset_root = f"{jsdelivr_base(repository, revision)}/"

    sent = 0
    for item in items:
        title = str(item.get("title") or "网球热点")
        raw_text = str(item.get("text") or "")
        lines = raw_text.splitlines()
        if lines and lines[0].strip() == title:
            lines = lines[2:] if len(lines) > 1 and not lines[1].strip() else lines[1:]
        text_html = "<br/>".join(html.escape(line) for line in lines)
        cards = item.get("cards") or ([item.get("card")] if item.get("card") else [])
        image_html = "".join(
            f'<img src="{html.escape(asset_root + str(card).lstrip("/"))}" '
            'style="width:100%;border-radius:10px;display:block;margin:0 0 12px;" />'
            for card in cards
        )
        candidates = " / ".join(item.get("title_candidates") or [])
        pinned = str(item.get("pinned_comment") or "")
        review = (
            '<div style="color:#65756d;font-size:12px;margin-top:12px;">'
            f"备选标题：{html.escape(candidates)}<br/>"
            f"置顶评论：{html.escape(pinned)}</div>"
        )
        prefix = "⏰" if item.get("kind") == "preview" else "⚡"
        try:
            push(
                f"{prefix}{title}",
                image_html + text_html + review,
                asset_dir=Path.cwd(),
            )
            sent += 1
        except PushPlusError as exc:
            console.print(f"[red]{exc}[/red]")
            return 1
    console.print(f"[green]已发送 {sent} 条内容待发布包到微信[/green]")
    return 0


# ---------- 授权视频中文化 ----------

def cmd_video(args) -> int:
    """Translate local, rights-cleared subtitles and optionally burn them."""
    from .video import GitHubModelsTranslator, VideoPipelineError, localize_video

    try:
        translator = GitHubModelsTranslator(model=args.model)
        audit = localize_video(
            video_path=Path(args.video),
            subtitle_path=Path(args.subtitles),
            rights_path=Path(args.rights),
            output_dir=Path(args.outdir),
            translator=translator,
            bilingual=args.bilingual,
            burn=not args.no_burn,
            overwrite=args.overwrite,
            ffmpeg_bin=args.ffmpeg,
        )
    except VideoPipelineError as exc:
        print(f"视频中文化失败：{exc}", file=sys.stderr)
        return 2
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0


# ---------- 入口 ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tennislive",
        description="WTA/ATP 巡回赛每日赛程赛果（北京时间）：CLI 查询 + 公众号/小红书内容生成",
    )
    p.add_argument("--version", action="version", version=f"tennislive {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")

    sub = p.add_subparsers(dest="command")

    def add_common(sp, with_date=True):
        if with_date:
            sp.add_argument(
                "--date",
                default="today",
                help="日期：YYYY-MM-DD / today / yesterday / tomorrow / ±N（北京时间，默认 today）",
            )
        sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")
        sp.add_argument("--json", action="store_true", help="输出 JSON 而非表格")

    sp = sub.add_parser("today", help="今日总览（赛果+进行中+赛程）")
    add_common(sp)

    sp = sub.add_parser("schedule", help="赛程（未开赛）")
    add_common(sp)

    sp = sub.add_parser("results", help="赛果（已完赛）")
    add_common(sp)

    sp = sub.add_parser("live", help="进行中的比赛")
    add_common(sp, with_date=False)

    sp = sub.add_parser("content", help="内容雷达：自动选择完赛热点和赛前焦点")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")
    sp.add_argument(
        "--manifest",
        help="写出本批待发布清单；工作流提交图片后再据此发送",
    )

    sp = sub.add_parser(
        "coverage", help="数据源与赛事覆盖报告（只出一张 coverage.txt）"
    )
    sp.add_argument("--date", default="today")
    sp.add_argument("--source", default="auto")
    sp.add_argument("--outdir", default="output")
    sp = sub.add_parser(
        "knowledge-adhoc",
        help="按指定 slug 单独生成一篇知识帖（不占用当天常规知识帖位置）",
    )
    sp.add_argument(
        "--slug",
        default="",
        help="选题池里的 slug（见 tournament_story.py 的 STORIES）；留空则按当日热度/时效自动选题并在配图不达标时自动换下一个候选",
    )
    sp.add_argument("--date", default="today", help="基准日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output/knowledge_adhoc", help="输出目录")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")
    sp.add_argument(
        "--theme", choices=["dark", "light"], default="dark", help="卡片主题（默认 dark）"
    )

    sp = sub.add_parser(
        "flash-card",
        help="单图快讯卡：一条及时网球新闻 → 一张品牌图 + 小红书文案（敏感话题默认转人工）",
    )
    sp.add_argument("--headline", required=True, help="新闻钩子标题")
    sp.add_argument("--event", required=True, help="具体事件：到底发生了什么（由调用方核实）")
    sp.add_argument("--when", default="", help="时间（如 2010 温网 / 昨夜）")
    sp.add_argument("--where", default="", help="地点（如 温布尔登 18 号球场）")
    sp.add_argument("--who", default="", help="人物（如 伊斯内尔 vs 马胡）")
    sp.add_argument("--punch", default="", help="引爆金句/一句话钩子（可选）")
    sp.add_argument(
        "--source-label",
        dest="source_label",
        default="资料：网球时差整理",
        help="底部小字来源署名",
    )
    sp.add_argument("--question", default="", help="结尾互动问题（留空用默认）")
    sp.add_argument("--date", default="today", help="日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output/flash_card", help="输出目录")
    sp.add_argument(
        "--theme", choices=["dark", "light"], default="dark", help="卡片主题（默认 dark）"
    )
    sp.add_argument(
        "--force",
        action="store_true",
        help="敏感话题默认拦截转人工；确认无误后加此项强制生成",
    )

    sp = sub.add_parser(
        "brief",
        help="网球热点简报：扫新闻 → 聚热点 → 抓正文出中文要点 → 一份 HTML（一条推送）",
    )
    sp.add_argument("--date", default="today", help="日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出根目录（默认 output/）")
    sp.add_argument("--max", type=int, default=12, help="简报里最多列几个热点（默认 12）")
    sp.add_argument(
        "--deep",
        type=int,
        default=5,
        help="深挖几个（抓正文出中文要点，默认 5；其余只给中译标题）",
    )
    sp.add_argument(
        "--min-sources",
        dest="min_sources",
        type=int,
        default=2,
        help="几家在报才算一个热点（默认 2；同一家发两条不算两家）",
    )
    sp.add_argument(
        "--persist-days",
        dest="persist_days",
        type=int,
        default=1,
        help="往前看几天判断「连着第几天在报」（默认 1）",
    )

    sp = sub.add_parser(
        "topic-radar",
        help="[底层工具] 只出选题候选队列，不推送；日常走 brief",
    )
    sp.add_argument("--date", default="today", help="日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出根目录（默认 output/）")
    sp.add_argument("--max", type=int, default=5, help="选题候选上限（默认 5）")
    sp.add_argument(
        "--min-sources",
        dest="min_sources",
        type=int,
        default=2,
        help="几家在报才算一个新闻点（默认 2；同一家发两条不算两家）",
    )
    sp.add_argument(
        "--persist-days",
        dest="persist_days",
        type=int,
        default=1,
        help="往前看几天判断「连着第几天在报」（默认 1）",
    )

    sp = sub.add_parser(
        "flash-radar",
        help="[底层工具] 只出场外快讯候选队列与草稿卡，不推送；日常走 brief",
    )
    sp.add_argument("--date", default="today", help="日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出根目录（默认 output/）")
    sp.add_argument("--max", type=int, default=8, help="候选上限（默认 8）")
    sp.add_argument(
        "--draft-cards",
        dest="draft_cards",
        type=int,
        default=3,
        help="渲染前 N 条草稿卡供预览（默认 3）",
    )
    sp.add_argument("--no-cards", action="store_true", help="只出候选清单，不渲染草稿卡")
    sp.add_argument(
        "--theme", choices=["dark", "light"], default="dark", help="卡片主题（默认 dark）"
    )

    sp = sub.add_parser(
        "explainer",
        help="AI 旁白解说视频（前因后果/技术原理/现状），适合抽象、难配图的知识点",
    )
    sp.add_argument("--slug", required=True, help="知识选题 slug（见 STORIES）")
    sp.add_argument("--date", default="today", help="日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output/explainer", help="输出目录")
    sp.add_argument(
        "--theme", choices=["dark", "light"], default="dark", help="幻灯主题（默认 dark）"
    )
    sp.add_argument(
        "--voice", default=None, help="edge-tts 中文语音（默认云健，语气偏解说）"
    )
    sp.add_argument("--rate", default=None, help="语速，如 +22%%（默认 +22%%）")
    sp.add_argument("--pitch", default=None, help="音高，如 +2Hz（默认 +0Hz）")

    sp = sub.add_parser("video", help="中文化本地且已授权的视频素材")
    sp.add_argument("--video", required=True, help="本地视频文件；不接受 URL")
    sp.add_argument("--subtitles", required=True, help="本地原文 SRT 字幕")
    sp.add_argument("--rights", required=True, help="与视频绑定的授权清单 JSON")
    sp.add_argument("--outdir", required=True, help="中文字幕、成片与授权审计输出目录")
    sp.add_argument("--model", help="GitHub Models 模型，默认 openai/gpt-4.1")
    sp.add_argument("--bilingual", action="store_true", help="生成原文+中文双语字幕")
    sp.add_argument("--no-burn", action="store_true", help="只生成 SRT，不调用 ffmpeg")
    sp.add_argument("--overwrite", action="store_true", help="覆盖已存在的输出文件")
    sp.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件名或路径")

    pub = sub.add_parser("publish", help="发布内容")
    pub_sub = pub.add_subparsers(dest="channel")
    spw = pub_sub.add_parser("wechat", help="公众号：上传素材并创建草稿")
    spw.add_argument("--dir", required=True, help="digest 生成的内容目录，如 output/2026-07-16")
    spw.add_argument("--publish", action="store_true", help="创建草稿后直接提交发布")
    spw.add_argument(
        "--style",
        choices=["pic", "article"],
        default="pic",
        help="pic=图片消息（小红书式竖图+文字，默认）；article=传统图文",
    )
    spp = pub_sub.add_parser("pushplus", help="通过 PushPlus 推送到自己微信")
    spp.add_argument("--dir", required=True, help="digest 生成的内容目录")
    spc = pub_sub.add_parser("content", help="发送已提交的内容待发布包")
    spc.add_argument("--manifest", required=True, help="content 生成的批次清单 JSON")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))

    if args.command == "today":
        return cmd_today(args)
    if args.command == "schedule":
        return cmd_day(args, [MatchStatus.SCHEDULED], "赛程")
    if args.command == "results":
        return cmd_day(
            args,
            [MatchStatus.FINISHED, MatchStatus.RETIRED, MatchStatus.WALKOVER],
            "赛果",
        )
    if args.command == "live":
        args.date = "today"
        return cmd_day(args, [MatchStatus.LIVE], "进行中")
    if args.command == "content":
        return cmd_content(args)
    if args.command == "coverage":
        return cmd_coverage(args)
    if args.command == "knowledge-adhoc":
        return cmd_knowledge_adhoc(args)
    if args.command == "flash-card":
        return cmd_flash_card(args)
    if args.command == "brief":
        return cmd_brief(args)
    if args.command == "topic-radar":
        return cmd_topic_radar(args)
    if args.command == "flash-radar":
        return cmd_flash_radar(args)
    if args.command == "explainer":
        return cmd_explainer(args)
    if args.command == "video":
        return cmd_video(args)
    if args.command == "publish":
        if args.channel == "wechat":
            return cmd_publish_wechat(args)
        if args.channel == "pushplus":
            return cmd_publish_pushplus(args)
        if args.channel == "content":
            return cmd_publish_flash(args)
        build_parser().parse_args(["publish", "--help"])
        return 1

    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
