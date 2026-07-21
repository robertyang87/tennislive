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
    trend_state = "正常" if trend_result.signals else "降级"
    digest.source_status["实时选题雷达"] = (
        f"{trend_state} · {trend_result.signals} 条信号，"
        f"命中 {trend_result.matched_matches} 场比赛"
    )

    # 只通过已配置的数据许可 API 补充专业统计。没有 API key 时保留基础
    # 比分页，不在 GitHub Actions 中抓取 ATP/WTA/TDI 官网页面。
    from .render.focus import select_focus_match
    from .sources.sportradar import SportradarOfficialStats

    focus_match = select_focus_match(digest)
    licensed_stats = SportradarOfficialStats.from_env()
    if focus_match and licensed_stats:
        try:
            focus_match.stats = licensed_stats.fetch_match_stats(focus_match)
            digest.source_status["Sportradar 技术统计"] = "正常 · 1 场授权统计"
        except SourceError as e:
            digest.source_status["Sportradar 技术统计"] = f"降级 · {e}"
    elif focus_match:
        digest.source_status["专业技术统计"] = (
            "未配置 · 设置 SPORTRADAR_API_KEY 后启用授权赛后统计"
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
    if not args.no_cards:
        try:
            from .render.knowledge import generate_knowledge_package

            knowledge_story = generate_knowledge_package(
                digest,
                outdir / "knowledge",
                theme=theme,
            )
        except Exception as e:  # noqa: BLE001
            console.print(
                f"[yellow]每日网球知识生成失败（跳过）：{e}[/yellow]"
            )

    card_paths: list[Path] = []
    if not args.no_cards:
        try:
            from .render.cards import generate_cards

            card_paths = generate_cards(digest, outdir / "cards")
        except Exception as e:  # 字体缺失等不阻塞文字内容生成
            console.print(f"[yellow]卡片图生成失败（跳过）：{e}[/yellow]")

    video_paths: list[Path] = []
    if card_paths:
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

    try:
        from .video.official import generate_official_video

        official_video = generate_official_video(digest, outdir / "video")
        if official_video:
            video_paths.append(official_video)
            digest.source_status["官方视频雷达"] = "正常 · 已生成中文竖版片段"
    except Exception as e:  # noqa: BLE001
        digest.source_status["官方视频雷达"] = f"降级 · {e}"
        console.print(f"[yellow]官方视频生成失败（跳过）：{e}[/yellow]")

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
                decorate_title(digest, t) for t in title_candidates(digest)[1:]
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
        fatal.append(f"小红书近7期重复度过高: {dedupe.reason}")
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
        from .render.editorial_memory import record_daily_lead

        record_daily_lead(digest)
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
        card = outdir / f"flash_{stamp}_{i:02d}.png"
        try:
            from .render.cards import generate_flash_card

            generate_flash_card(m, card, headline)
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
    cards = sorted(cards_dir.glob("card_*.png"))

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
    from .render.pushmsg import pin_asset_revision
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
    try:
        push(title, html)
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
    asset_root = f"https://cdn.jsdelivr.net/gh/{repository}@{revision}/"

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
            push(f"{prefix}{title}", image_html + text_html + review)
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
