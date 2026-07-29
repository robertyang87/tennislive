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
from .timeutil import beijing_today, parse_date_arg
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


def cmd_digest(args) -> int:
    from .render.terminal import console
    from .render.wechat import article_title, to_html, to_markdown
    from .render.xiaohongshu import plan_post

    d = parse_date_arg(args.date)
    try:
        digest: Digest = build_digest(d, prefer=args.source)
    except SourceError as e:
        console.print(f"[red]抓取失败：{e}[/red]")
        return 1

    # 巡回赛官方 OOP 决定时间是否精确、仅有场序，或尚未发布；
    # ESPN 与 SofaScore 保留为覆盖面和交叉验证来源。
    from .sources.official_schedule import enrich_official_schedules

    digest.source_status.update(enrich_official_schedules(digest))

    from .research.trends import apply_trend_signals

    trend_result = apply_trend_signals(
        digest.results + digest.live + digest.schedule
    )
    # 保留完整信号池，供候选池选题使用：未绑定到当日比赛的相关新闻也是热点。
    digest.trend_signals = list(trend_result.all_signals)
    trend_state = "正常" if trend_result.signals else "降级"
    digest.source_status["实时选题雷达"] = (
        f"{trend_state} · {trend_result.signals} 条信号，"
        f"命中 {trend_result.matched_matches} 场比赛"
    )

    # 焦点复盘依次尝试巡回赛官方逐场接口和已配置的授权备用源。
    # 所有结构化统计均不可用时，渲染层才回退到盘分/局分结构复盘。
    from .render.focus import select_focus_match
    from .sources.official_stats import fetch_match_stats_with_fallback

    focus_match = select_focus_match(digest)
    if focus_match:
        stats_result = fetch_match_stats_with_fallback(focus_match)
        focus_match.stats = stats_result.stats
        digest.source_status.update(stats_result.source_status)
        digest.source_status["焦点复盘数据"] = (
            f"正常 · {focus_match.stats.source}"
            if focus_match.stats is not None
            else "降级 · 所有逐场统计源均未命中，使用比分结构复盘"
        )

    # 头条页（card_01_lead）只在 match.stats 存在时才画技术对比表，否则退化
    # 成纯文字复盘——而文字复盘只该是"真的没有数据"时的兜底。上面这次取数是
    # 按 select_focus_match() 选的，和头条经常不是同一场，所以头条自己也要取。
    from .render.focus import headline_stats_targets

    headline_budget = max(
        1, int(os.environ.get("TENNISLIVE_COVER_HEADLINE_ATTEMPTS", "4") or 4)
    )
    headline_stats_hits = 0
    for candidate in headline_stats_targets(digest, headline_budget):
        if candidate.stats is not None:
            headline_stats_hits += 1
            continue
        try:
            candidate.stats = fetch_match_stats_with_fallback(candidate).stats
        except Exception as e:  # noqa: BLE001 - 统计是增强项，绝不阻断出片
            digest.source_status["头条技术统计"] = f"降级 · {e}"
            continue
        if candidate.stats is not None:
            headline_stats_hits += 1
    digest.source_status["头条技术统计"] = (
        f"正常 · {headline_stats_hits} 场头条候选已接入逐场统计"
        if headline_stats_hits
        else "降级 · 头条候选无逐场统计，头条页使用比分结构复盘"
    )

    # 人工核验的权威媒体摘要优先；未覆盖的比赛使用当前排名、赛事阶段
    # 与晋级目标生成背景看点，不复述上一轮比分或泛化技战术套话。
    from .render.authority import apply_curated_editorial, enrich_schedule_editorial

    curated_count = apply_curated_editorial(digest)
    if curated_count:
        digest.source_status["编辑台媒体看点"] = (
            f"正常 · {curated_count} 场人工核验并保留原文链接"
        )
    from .research.media import apply_media_briefs

    media_count = apply_media_briefs(digest)
    digest.source_status["外媒观点雷达"] = (
        f"正常 · {media_count} 场多源原创摘要"
        if media_count
        else "本期无达到多源证据门槛的事件"
    )
    from .render.narrative import apply_knowledge_angles

    knowledge_count = apply_knowledge_angles(digest)
    digest.source_status["球员与赛事知识库"] = (
        f"正常 · {knowledge_count} 场接入历史背景"
        if knowledge_count
        else "本期焦点暂无直接命中的审核档案"
    )
    try:
        from .render.ai_editorial import enrich_with_github_models

        ai_result = enrich_with_github_models(digest)
        digest.source_status["GitHub Models 数据编辑"] = ai_result.status
    except Exception as e:  # noqa: BLE001
        digest.source_status["GitHub Models 数据编辑"] = f"降级 · {e}"
    enrich_schedule_editorial(digest)

    outdir = Path(args.outdir) / d.isoformat()
    outdir.mkdir(parents=True, exist_ok=True)
    theme = os.environ.get("TENNISLIVE_THEME", "dark")

    # 一次性主页配置包放在 output/profile；内容稳定时不会产生重复提交。
    try:
        from .render.profile import generate_profile_pack

        generate_profile_pack(Path(args.outdir) / "profile")
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]主页配置物料生成失败（跳过）：{e}[/yellow]")

    # 卡片图
    knowledge_story = None
    from .render.tournament_story import adhoc_knowledge_published_on

    if not args.no_cards and adhoc_knowledge_published_on(digest.today):
        # 当天已由手动/热点 ad-hoc 流程发布知识帖：日报不再自动补第二篇，
        # 避免同日重复推送。热点 ad-hoc 不受此限制，仍可随时发。
        console.print(
            "[yellow]今日已由 ad-hoc 流程发布知识帖，日报跳过自动知识帖（避免同日重复）[/yellow]"
        )
    elif not args.no_cards:
        from .render.tournament_story import record_story_selection, story_ranking

        # 排序在生成之前算好：即使这一班次整个失败，也要留下"谁参选了、
        # 各得几分"。只记胜者的话，"今天没有历史今天"和"有但没轮到它"
        # 分不出来——7/25 就是这么丢的。
        ranking = story_ranking(digest)
        selection_error = ""
        try:
            from .render.knowledge import generate_knowledge_package

            knowledge_story = generate_knowledge_package(
                digest,
                outdir / "knowledge",
                theme=theme,
            )
        except Exception as e:  # noqa: BLE001
            selection_error = f"{type(e).__name__}: {e}"
            console.print(
                f"[yellow]每日网球知识生成失败（跳过）：{e}[/yellow]"
            )
        try:
            log_path = record_story_selection(
                outdir,
                digest,
                ranking,
                selected_slug=knowledge_story.slug if knowledge_story else None,
                error=selection_error,
            )
            missed = [r for r in ranking if r["bucket"] == "anniversary"]
            if missed and (
                knowledge_story is None
                or knowledge_story.slug != missed[0]["story_slug"]
            ):
                console.print(
                    f"[yellow]今天有「历史上的今天」参选（{missed[0]['story_slug']}）"
                    f"却没有成稿，拒因见 {log_path}[/yellow]"
                )
        except Exception as e:  # noqa: BLE001 - 诊断不该拖垮当日内容
            console.print(f"[yellow]选题排序未能落盘：{e}[/yellow]")

    card_paths: list[Path] = []
    if not args.no_cards:
        try:
            from .render.cards import generate_cards

            card_paths = generate_cards(digest, outdir / "cards")
        except Exception as e:  # 字体缺失等不阻塞文字内容生成
            console.print(f"[yellow]卡片图生成失败（跳过）：{e}[/yellow]")

    video_paths: list[Path] = []
    daily_video_enabled = (
        os.environ.get("TENNISLIVE_DAILY_VIDEO", "off").casefold() == "on"
    )
    if daily_video_enabled and card_paths:
        try:
            from .render.video_digest import generate_digest_video

            video_paths = [
                generate_digest_video(
                    card_paths,
                    outdir / "video" / "daily-brief.mp4",
                )
            ]
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]竖版视频生成失败（跳过）：{e}[/yellow]")

    if daily_video_enabled:
        try:
            from .video.official import generate_official_video

            official_video = generate_official_video(digest, outdir / "video")
            if official_video:
                video_paths.append(official_video)
                digest.source_status["官方视频雷达"] = "正常 · 已生成中文竖版片段"
        except Exception as e:  # noqa: BLE001
            digest.source_status["官方视频雷达"] = f"降级 · {e}"
            console.print(f"[yellow]官方视频生成失败（跳过）：{e}[/yellow]")
    else:
        digest.source_status["日报视频"] = "关闭 · 日报仅生成图片与文案"

    # 标题：自动选用 + 候选留档
    from .render.titles import (
        cover_fact_bundle,
        cover_highlights,
        daily_lead_match,
        title_candidates,
    )

    title = article_title(digest)
    cover_copy = cover_highlights(digest)
    (outdir / "wechat_title.txt").write_text(title, encoding="utf-8")
    (outdir / "title_candidates.txt").write_text(
        "\n".join(title_candidates(digest)), encoding="utf-8"
    )

    # 公众号
    (outdir / "wechat.md").write_text(to_markdown(digest), encoding="utf-8")
    html = to_html(digest)
    if card_paths:
        # 文末附卡片图占位符；publish wechat 时会上传并替换为微信图片 URL
        content_cards = [p for p in card_paths if "cover" not in p.name]
        html += "\n" + "\n".join(
            f"{{{{IMAGE:{p.name}}}}}" for p in content_cards
        )
    (outdir / "wechat.html").write_text(html, encoding="utf-8")

    # 小红书
    xhs_plan, xhs = plan_post(digest)
    (outdir / "xiaohongshu.txt").write_text(xhs, encoding="utf-8")
    (outdir / "pinned_comment.txt").write_text(
        xhs_plan.pinned_comment, encoding="utf-8"
    )
    _dump_json(xhs_plan, outdir / "xiaohongshu_plan.json")

    # V2 证据资产：来源、逐项事实、选题理由和外媒共识都独立留档。
    # 发布端只消费这些经过审核的摘要，不保存或转载媒体正文。
    from .render.evidence import evidence_artifacts

    for filename, artifact in evidence_artifacts(digest, xhs_plan).items():
        _dump_json(artifact, outdir / filename)

    # 与最近 7 期比较，阻止标题钩子或正文机械复用。固定栏目、日期、标签
    # 和账号签名会被忽略，因此这里只拦真实内容重复。
    from .render.history_dedupe import check_recent_posts

    dedupe = check_recent_posts(
        xhs,
        Path(args.outdir),
        current_date=d,
        history_limit=7,
    )
    _dump_json(
        {
            "passed": dedupe.passed,
            "history_count": dedupe.history_count,
            "reason": dedupe.reason,
            "comparisons": [
                {
                    "date": item.published_on.isoformat(),
                    "title_similarity": item.title_similarity,
                    "opening_similarity": item.opening_similarity,
                    "body_similarity": item.body_similarity,
                    "repeated_phrases": item.repeated_phrases,
                    "triggers": item.triggers,
                }
                for item in dedupe.comparisons
            ],
        },
        outdir / "xiaohongshu_similarity.json",
    )

    # 手机推送模板：文案走独立复制页，卡片图留在消息中便于保存。
    from .render.pushmsg import to_copy_page, to_push_html

    from .render.xiaohongshu import decorate_title

    (outdir / "copy.html").write_text(
        to_copy_page(
            xhs,
            alt_titles=[
                decorate_title(digest, t, category="今日球局")
                for t in title_candidates(digest)[1:]
            ],
            pinned_comment=xhs_plan.pinned_comment,
        ),
        encoding="utf-8",
    )

    (outdir / "push.html").write_text(
        to_push_html(
            digest,
            cards=[p.name for p in card_paths],
            xhs_text=xhs,
            videos=[p.name for p in video_paths],
        ),
        encoding="utf-8",
    )

    # 每期输出覆盖清单，便于快速核对 ATP/WTA 各级别赛事是否被收录。
    from .render.coverage import coverage_report

    (outdir / "coverage.txt").write_text(
        coverage_report(digest), encoding="utf-8"
    )

    # 原始数据
    _dump_json(digest, outdir / "digest.json")
    lead = daily_lead_match(digest)
    if lead is not None:
        _dump_json(
            cover_fact_bundle(lead, source=digest.source),
            outdir / "cover_facts.json",
        )

    # 自动质检（替代人工审核）
    from .qa import run_checks

    fatal, warns = run_checks(digest, title, xhs, cover_copy=cover_copy)
    if not dedupe.passed:
        # 文案查重是风格性提醒，不是事实错误：赛果的时效性与准确性优先，
        # 不能让某一句"看点"复用挡住当天比分、赛程和公众号推送（曾在生产
        # 环境实际触发过整包被 FATAL 阻断、当天日报完全没有推送的事故）。
        warns.append(f"小红书近7期重复度过高: {dedupe.reason}")
    (outdir / "qa.txt").write_text(
        "\n".join(["[FATAL] " + f for f in fatal] + ["[WARN] " + w for w in warns])
        or "OK",
        encoding="utf-8",
    )
    for w in warns:
        console.print(f"[yellow]质检警告：{w}[/yellow]")
    if fatal:
        for f in fatal:
            console.print(f"[red]质检不通过：{f}[/red]")
        return 2  # 非零退出阻断后续自动发布

    # 生成成功后记录"一分钟"故事已使用（30 天冷却），并把昨日最热
    # 但库里还没有故事的胜者记入扩库清单——选题跟着热度走
    try:
        from .render.tournament_story import (
            mark_story_used,
            record_story_wishlist,
        )

        if knowledge_story:
            mark_story_used(knowledge_story.slug, digest.today)
        record_story_wishlist(digest)
        # 保存今日竞猜场次，明早文案里自动开奖
        from .render.xiaohongshu import record_quiz

        record_quiz()
        from .render.editorial_memory import record_daily_focus, record_daily_lead

        record_daily_lead(digest)
        # 焦点复盘和头条经常不是同一场，两份都要记，否则焦点没人拦得住它
        # 连着两天挑中同一场比赛。
        from .render.focus import select_focus_match

        record_daily_focus(select_focus_match(digest), digest.today)
    except Exception as e:  # noqa: BLE001
        logging.getLogger(__name__).warning("故事状态记录失败（不影响生成）: %s", e)

    console.print(f"[green]内容包已生成：{outdir}[/green]")
    console.print(
        f"  赛果 {len(digest.results)} 场 | 进行中 {len(digest.live)} 场 | "
        f"今日赛程 {len(digest.schedule)} 场 | 卡片 {len(card_paths)} 张 | "
        f"数据源 {digest.source}"
    )
    if digest.is_empty:
        console.print("[yellow]提示：当天没有巡回赛比赛，内容为空档说明。[/yellow]")
    return 0


def cmd_schedule_cards(args) -> int:
    """今日赛程卡：按赛事分页、ATP 与 WTA 各自成页、不带看点。"""
    from .render.common import group_by_tournament
    from .render.pushmsg import to_schedule_push_html
    from .render.terminal import console
    from .render.webcards import (
        TOUR_LEVELS,
        generate_schedule_deck,
        schedule_pages,
    )

    d = parse_date_arg(args.date)
    try:
        digest: Digest = build_digest(d, prefer=args.source)
    except SourceError as e:
        console.print(f"[red]抓取失败：{e}[/red]")
        return 1

    # 北京日历会把美洲赛事的比赛日拦腰切断（详见 render.schedule_time 的
    # NEXT_DAY_CUTOFF_HOUR）。把次日 12:00 前的场次补进来，否则整个美东夜场
    # ——包括郑钦文 vs 埃亚拉这种——都会从「今日赛程」里消失。
    from datetime import timedelta

    from .digest import _is_qualifying
    from .render.schedule_time import in_schedule_window, match_key

    known = {match_key(m) for m in digest.schedule}
    carried: list = []
    try:
        next_day = fetch_day(d + timedelta(days=1), prefer=args.source)
        for m in next_day.upcoming():
            if _is_qualifying(m) or not in_schedule_window(m):
                continue
            if match_key(m) in known:
                continue
            known.add(match_key(m))
            carried.append(m)
    except SourceError as e:
        console.print(f"[yellow]次日凌晨场次抓取失败，只出今天：{e}[/yellow]")
    if carried:
        digest.schedule.extend(carried)
        # build_digest 的排名回填只作用于它自己取到的那批；这些是之后追加的，
        # 不补一次就会出现「郑钦文没有排名」，排序也拿不到"top 选手"这一维。
        if digest.rankings is not None:
            from .digest import apply_rankings

            apply_rankings(digest.rankings, carried)
        console.print(f"[cyan]跨日补入[/cyan] {len(carried)} 场（北京次日 12:00 之前开赛）")

    from .sources.official_schedule import enrich_official_schedules

    official = enrich_official_schedules(digest)
    digest.source_status.update(official)
    # 官方 OOP 生效没有必须看得见：时间口径全靠它，静默失败会让整份赛程退回
    # 单源"预计"，而卡上看不出差别。
    for label, state in official.items():
        style = "green" if state.startswith("正常") else "yellow"
        console.print(f"[{style}]官方排期[/{style}] {label} → {state}")
    if not official:
        console.print("[yellow]官方排期 无匹配来源，时间仅有聚合源单源[/yellow]")

    upcoming = digest.schedule
    if not upcoming:
        console.print("[yellow]今天没有未开赛的场次，不出赛程卡[/yellow]")
        return 0

    # 取材口径要能被人核对：哪些赛事进了、哪些被级别挡了、每站列了几场，
    # 全部打出来。只在成功时出声的检查没法证明它真的看过。
    kept, skipped = [], []
    for group in group_by_tournament(upcoming):
        target = kept if group.level in TOUR_LEVELS else skipped
        target.append((group, len(group.matches)))
    for group, count in kept:
        console.print(f"[green]收录[/green] {group.compact_level} · {group.name_zh}（{count} 场）")
    for group, count in skipped:
        console.print(
            f"[yellow]挡掉[/yellow] {group.name_zh}（{count} 场）"
            f"：级别 {group.level or '未识别'}，非巡回赛级别"
        )
    if not kept:
        console.print("[yellow]今天没有巡回赛级别的赛事[/yellow]")
        return 0

    outdir = Path(args.outdir) / d.isoformat() / "schedule"
    cards_dir = outdir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    # 先清干净：页数会随取材变化（收口之后从七页降到四页），不清的话上一轮的
    # card_schedule05..07 会作为陈图留在仓库里，看起来像本期的一部分。
    for stale in cards_dir.glob("card_schedule*.jpg"):
        stale.unlink()
    date_label = f"{d.month}.{d.day}"

    pages = schedule_pages(upcoming, date_label, today=d)
    console.print(f"共 {len(pages)} 页")

    card_paths: list[Path] = []
    try:
        for kind, image in generate_schedule_deck(upcoming, date_label, today=d):
            path = outdir / "cards" / f"card_{kind}.jpg"
            image.convert("RGB").save(path, quality=92)
            card_paths.append(path)
    except Exception as e:  # noqa: BLE001 - 字体/浏览器缺失不该吞掉诊断信息
        console.print(f"[red]赛程卡渲染失败：{e}[/red]")
        return 1

    # 文案的正文必须按"真正上卡的那些场次"写——正文和图对不上，读者一眼看出来
    from .render.pushmsg import live_copy_page_url, to_copy_page
    from .render.schedule_post import pick_lead, schedule_post
    from .render.schedule_time import schedule_time_display
    from .render.webcards import schedule_selection

    selection = schedule_selection(upcoming)
    on_card = [m for _group, ms in selection for m in ms]
    display = schedule_time_display(upcoming, today=d)
    lead = pick_lead(on_card)
    post = schedule_post(d, on_card, display, lead)
    console.print(f"[cyan]标题[/cyan] {post.splitlines()[0]}")

    (outdir / "xiaohongshu.txt").write_text(post, encoding="utf-8")
    (outdir / "copy.html").write_text(to_copy_page(post), encoding="utf-8")

    # 复制页的按钮只在链接确认可达时才放进推送：GitHub Pages 只服务 main，
    # 特性分支上生成的包它取不到，按钮点开就是 404。微信那条消息发出去就
    # 收不回来——宁可不放按钮，也不放一个死链。
    copy_url = live_copy_page_url(d, subdir="schedule")
    if copy_url:
        console.print(f"[green]复制页可达[/green] {copy_url}")
    else:
        console.print(
            "[yellow]复制页尚不可达（Pages 只服务 main），本次推送不放该按钮；"
            "标题与正文已在消息里各自成块，可长按复制[/yellow]"
        )

    events = [f"{group.compact_level}·{group.name_zh}" for group, _ in kept]
    (outdir / "push.html").write_text(
        to_schedule_push_html(
            d, [p.name for p in card_paths], events=events, xhs_text=post,
            copy_url=copy_url,
        ),
        encoding="utf-8",
    )
    console.print(f"[green]已生成 {len(card_paths)} 张赛程卡 → {outdir}[/green]")
    return 0


def cmd_yesterday_point(args) -> int:
    """Generate the independent, source-audited yesterday-point package(s).

    ATP and WTA are discovered and published independently under
    ``atp/`` and ``wta/`` subdirectories; either tour can pass or skip on
    its own. A tour that already passed in an earlier run today (e.g. an
    earlier retry pass) is left untouched and not re-pushed -- only a tour
    still missing its clip is retried. This is what lets the workflow run
    several times a day and have whichever tour's video shows up first get
    pushed immediately, while the other keeps retrying independently.
    """
    from datetime import datetime, timezone

    from .render.terminal import console
    from .video.daily_point import generate_yesterday_point

    d = parse_date_arg(args.date)
    output_dir = Path(args.outdir) / d.isoformat() / "yesterday-point"
    output_dir.mkdir(parents=True, exist_ok=True)
    already_done: set[str] = set()
    for tour in ("ATP", "WTA"):
        manifest_path = output_dir / tour.lower() / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
        if existing.get("status") == "pass":
            already_done.add(tour)

    diagnostics: dict = {}
    try:
        digest = build_digest(d, prefer=args.source)
        videos = generate_yesterday_point(
            digest,
            output_dir,
            skip_tours=frozenset(already_done),
            diagnostics=diagnostics,
        )
    except Exception as exc:  # noqa: BLE001
        (output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "project": "yesterday-point",
                    "published_for": d.isoformat(),
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        console.print(f"[red]昨日好球生成失败：{exc}[/red]")
        return 1

    # The reason must state what actually happened: with the switch off no
    # source was ever queried, and claiming "已查询各源" would be a false
    # audit trail.
    if diagnostics.get("enabled") is False:
        skip_reason = (
            "TENNISLIVE_YESTERDAY_POINT 开关未开启，本期未查询任何官方视频源；"
            "在工作流或环境变量中设为 on 后才会开始检索。"
        )
    else:
        skip_reason = (
            "已查询 Tennis TV Hot Shots、ATP/WTA 官方 YouTube、"
            "WTA 官网及四大满贯官方频道；仍没有同时满足昨日赛事、"
            "官方单分或集锦标签、完整回合和日期匹配的视频。"
            "若 Tennis TV 卡片为 freemium，请配置 TENNISTV_JWT；"
            "Action 不会读取浏览器登录态。本期会在下一次重试班次继续检索。"
        )
    tour_status: dict[str, str] = {}
    for tour in ("ATP", "WTA"):
        if tour in already_done:
            tour_status[tour] = "pass"
            console.print(f"[green]{tour} 昨日好球此前已生成，本次不重复生成/推送[/green]")
            continue
        if tour in videos:
            tour_status[tour] = "pass"
            console.print(f"[green]{tour} 昨日好球已生成：{videos[tour]}[/green]")
            continue
        tour_dir = output_dir / tour.lower()
        tour_dir.mkdir(parents=True, exist_ok=True)
        (tour_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "status": "skipped",
                    "project": "yesterday-point",
                    "tour": tour,
                    "published_for": d.isoformat(),
                    "reason": skip_reason,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        # skip 也要把诊断落盘：每路 resolver 试了什么、为什么失败。这份
        # skip.json 会被工作流提交回仓库，避免"视频静默消失"只能翻已过期
        # 的 Actions 日志。
        (tour_dir / "skip.json").write_text(
            json.dumps(
                {
                    "status": "skipped",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "project": "yesterday-point",
                    "tour": tour,
                    "published_for": d.isoformat(),
                    "switch_enabled": diagnostics.get("enabled"),
                    "reason": skip_reason,
                    "resolver_attempts": diagnostics.get("resolver_attempts", []),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        tour_status[tour] = "skipped"
        console.print(f"[yellow]{tour} 昨日好球跳过：本期没有可验证的官方完整回合[/yellow]")

    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "status": "pass" if (videos or already_done) else "skipped",
                "project": "yesterday-point",
                "published_for": d.isoformat(),
                "tours": tour_status,
                "fresh_tours": sorted(videos),
                # Per-source discovery ledger in one place: which official
                # source fetched how many clips, how many matched yesterday,
                # and each resolver's outcome. Lets a skip run separate a real
                # no-material day (fetched N, matched 0) from a broken source
                # (fetched 0 / error), and is what the workflow surfaces to the
                # Actions summary.
                "resolver_attempts": diagnostics.get("resolver_attempts", []),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    attempts = diagnostics.get("resolver_attempts", [])
    if attempts and not videos and not already_done:
        for item in attempts:
            detail = item.get("note") or item.get("error") or item.get("status", "")
            console.print(
                f"[dim]· {item.get('source', item.get('resolver', ''))}："
                f"抓取{item.get('fetched', '-')}/命中{item.get('matched', '-')}"
                f"（{detail}）[/dim]"
            )
    return 0


# ---------- 闪发（即时战报） ----------

def cmd_flash(args) -> int:
    """检测传播窗口内的重点比赛，生成小红书单场内容包.

    用 data/flash_state.json 去重，适合高频定时运行。
    """
    import os
    from datetime import timedelta

    from .render.hotspot import (
        hotspot_candidates,
        hotspot_post,
        hotspot_reasons,
        hotspot_score,
        hotspot_title_candidates,
    )
    from .render.terminal import console
    from .timeutil import beijing_today, now_beijing

    today = beijing_today()
    manifest_path = Path(args.manifest) if args.manifest else None
    if manifest_path and manifest_path.exists():
        manifest_path.unlink()
    matches = []
    for d in (today - timedelta(days=1), today):
        try:
            matches.extend(fetch_day(d, prefer=args.source).matches)
        except SourceError as e:
            console.print(f"[yellow]{d} 抓取失败：{e}[/yellow]")
    if not matches:
        console.print("[red]无数据，跳过[/red]")
        return 1

    state_path = Path("data/flash_state.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state: dict[str, str] = {}
    if state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    # 清理两天前的记录
    cutoff = (today - timedelta(days=2)).isoformat()
    state = {k: v for k, v in state.items() if v >= cutoff}

    now = now_beijing()
    new = [
        m
        for m in hotspot_candidates(matches, now=now)
        if m.match_id not in state
    ]
    if not new:
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        console.print("没有新完赛的重点比赛")
        return 0

    outdir = Path(args.outdir) / today.isoformat() / "flash"
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%H%M")
    published = 0
    manifest_items = []
    for i, m in enumerate(new):
        titles = hotspot_title_candidates(m)
        headline = titles[0]
        card = outdir / f"flash_{stamp}_{i:02d}.jpg"
        try:
            from .render.cards import generate_flash_card

            card = generate_flash_card(m, card, headline)
        except Exception as e:
            console.print(f"[yellow]战报卡生成失败（跳过图片）：{e}[/yellow]")
            card = None
        text = hotspot_post(m)
        (outdir / f"flash_{stamp}_{i:02d}.txt").write_text(text, encoding="utf-8")

        card_ref = None
        if card is not None:
            try:
                card_ref = card.resolve().relative_to(Path.cwd().resolve()).as_posix()
            except ValueError:
                card_ref = card.as_posix()
        manifest_items.append(
            {
                "match_id": m.match_id,
                "title": headline,
                "title_candidates": titles,
                "text": text,
                "card": card_ref,
                "hotspot_score": hotspot_score(m),
                "reasons": hotspot_reasons(m),
            }
        )

        # 自动发布（配置了才执行）
        if not args.no_publish and os.environ.get("PUSHPLUS_TOKEN"):
            try:
                from .publish.pushplus import push

                push(f"⚡{headline}", text.replace("\n", "<br/>"))
                published += 1
            except Exception as e:
                console.print(f"[yellow]PushPlus 失败：{e}[/yellow]")
        wechat_mode = os.environ.get("WECHAT_MODE", "off")
        if (
            not args.no_publish
            and card is not None
            and os.environ.get("WECHAT_APPID")
            and wechat_mode != "off"
        ):
            try:
                from .publish.wechat_mp import publish_image_post

                publish_image_post(
                    title=f"⚡{headline}"[:64],
                    content=text,
                    images=[card],
                    do_publish=(wechat_mode == "publish"),
                )
                published += 1
            except Exception as e:
                console.print(f"[yellow]公众号闪发失败：{e}[/yellow]")

        state[m.match_id] = today.isoformat()
        console.print(f"[green]⚡ {headline}[/green]")

    if manifest_path:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "generated_at": now.isoformat(),
                    "date": today.isoformat(),
                    "items": manifest_items,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    console.print(f"闪发 {len(new)} 条（发布动作 {published} 次）")
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
    from .render.pushmsg import drop_dead_copy_button, pin_asset_revision
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
    html, live_copy = drop_dead_copy_button(html)
    if live_copy:
        console.print(f"[green]复制页可达[/green] {live_copy}")
    else:
        console.print(
            "[yellow]复制页取不到，本次不放该按钮；正文已整段渲染在消息里，"
            "可长按复制[/yellow]"
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

    sp = sub.add_parser("flash", help="即时战报：检测刚完赛的重点比赛并闪发")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")
    sp.add_argument("--no-publish", action="store_true", help="只生成不发布")
    sp.add_argument(
        "--manifest",
        help="写出本批待发布清单；工作流提交图片后再据此发送",
    )

    sp = sub.add_parser("content", help="内容雷达：自动选择完赛热点和赛前焦点")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")
    sp.add_argument(
        "--manifest",
        help="写出本批待发布清单；工作流提交图片后再据此发送",
    )

    sp = sub.add_parser("digest", help="生成每日内容包（公众号+小红书+卡片图）")
    sp.add_argument("--date", default="today", help="基准日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--no-cards", action="store_true", help="不生成卡片图")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")

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
        "topic-radar",
        help="把今天的新闻提炼成选题候选（新闻钩子 + 底下的常青线），不是快讯",
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
        help="自动扫描场外网球新闻，筛出可发候选进待发队列（比赛新闻归日报，敏感转人工）",
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

    sp = sub.add_parser(
        "schedule-cards", help="今日赛程卡：按赛事分页、ATP/WTA 分开、无看点"
    )
    sp.add_argument("--date", default="today", help="基准日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")

    sp = sub.add_parser("point", help="生成独立的昨日好球完整回合视频包")
    sp.add_argument("--date", default="today", help="发布日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先赛果数据源")

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
    spf = pub_sub.add_parser("flash", help="发送已提交的热点待发布包")
    spf.add_argument("--manifest", required=True, help="flash 生成的批次清单 JSON")
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
    if args.command == "flash":
        return cmd_flash(args)
    if args.command == "content":
        return cmd_content(args)
    if args.command == "digest":
        return cmd_digest(args)
    if args.command == "knowledge-adhoc":
        return cmd_knowledge_adhoc(args)
    if args.command == "flash-card":
        return cmd_flash_card(args)
    if args.command == "topic-radar":
        return cmd_topic_radar(args)
    if args.command == "flash-radar":
        return cmd_flash_radar(args)
    if args.command == "explainer":
        return cmd_explainer(args)
    if args.command == "schedule-cards":
        return cmd_schedule_cards(args)
    if args.command == "point":
        return cmd_yesterday_point(args)
    if args.command == "video":
        return cmd_video(args)
    if args.command == "publish":
        if args.channel == "wechat":
            return cmd_publish_wechat(args)
        if args.channel == "pushplus":
            return cmd_publish_pushplus(args)
        if args.channel == "flash":
            return cmd_publish_flash(args)
        if args.channel == "content":
            return cmd_publish_flash(args)
        build_parser().parse_args(["publish", "--help"])
        return 1

    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
