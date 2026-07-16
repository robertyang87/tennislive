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
import sys
from pathlib import Path

from . import __version__
from .digest import Digest, build_digest
from .models import MatchStatus
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
    from .render.xiaohongshu import post_title, to_post

    d = parse_date_arg(args.date)
    try:
        digest: Digest = build_digest(d, prefer=args.source)
    except SourceError as e:
        console.print(f"[red]抓取失败：{e}[/red]")
        return 1

    outdir = Path(args.outdir) / d.isoformat()
    outdir.mkdir(parents=True, exist_ok=True)

    # 卡片图
    card_paths: list[Path] = []
    if not args.no_cards:
        try:
            from .render.cards import generate_cards

            card_paths = generate_cards(digest, outdir / "cards")
        except Exception as e:  # 字体缺失等不阻塞文字内容生成
            console.print(f"[yellow]卡片图生成失败（跳过）：{e}[/yellow]")

    # 公众号
    (outdir / "wechat_title.txt").write_text(article_title(digest), encoding="utf-8")
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
    (outdir / "xiaohongshu.txt").write_text(to_post(digest), encoding="utf-8")

    # 原始数据
    _dump_json(digest, outdir / "digest.json")

    console.print(f"[green]内容包已生成：{outdir}[/green]")
    console.print(
        f"  赛果 {len(digest.results)} 场 | 进行中 {len(digest.live)} 场 | "
        f"今日赛程 {len(digest.schedule)} 场 | 卡片 {len(card_paths)} 张 | "
        f"数据源 {digest.source}"
    )
    if digest.is_empty:
        console.print("[yellow]提示：当天没有巡回赛比赛，内容为空档说明。[/yellow]")
    return 0


# ---------- 发布 ----------

def cmd_publish_wechat(args) -> int:
    from .publish.wechat_mp import WeChatError, publish_article
    from .render.terminal import console

    d = Path(args.dir)
    title_f, html_f = d / "wechat_title.txt", d / "wechat.html"
    if not html_f.exists():
        console.print(f"[red]{html_f} 不存在，请先运行 tennislive digest[/red]")
        return 1
    cards_dir = d / "cards"
    cover = cards_dir / "card_00_cover.png"
    if not cover.exists():
        console.print(f"[red]封面图 {cover} 不存在（公众号文章必须有封面）[/red]")
        return 1
    content_images = sorted(
        p for p in cards_dir.glob("card_*.png") if "cover" not in p.name
    )
    title = (
        title_f.read_text(encoding="utf-8").strip() if title_f.exists() else "网球每日速报"
    )
    try:
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
        console.print("已存入草稿箱，请到公众号后台确认后群发。加 --publish 可直接发布。")
    return 0


def cmd_publish_pushplus(args) -> int:
    from .publish.pushplus import PushPlusError, push
    from .render.terminal import console

    d = Path(args.dir)
    title_f, html_f = d / "wechat_title.txt", d / "wechat.html"
    if not html_f.exists():
        console.print(f"[red]{html_f} 不存在，请先运行 tennislive digest[/red]")
        return 1
    title = (
        title_f.read_text(encoding="utf-8").strip() if title_f.exists() else "网球每日速报"
    )
    html = html_f.read_text(encoding="utf-8")
    # 推送消息里去掉图片占位符
    import re

    html = re.sub(r"\{\{IMAGE:[^}]+\}\}", "", html)
    try:
        push(title, html)
    except PushPlusError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    console.print("[green]已推送到微信（PushPlus）[/green]")
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

    sp = sub.add_parser("digest", help="生成每日内容包（公众号+小红书+卡片图）")
    sp.add_argument("--date", default="today", help="基准日期（北京时间，默认 today）")
    sp.add_argument("--outdir", default="output", help="输出目录（默认 output/）")
    sp.add_argument("--no-cards", action="store_true", help="不生成卡片图")
    sp.add_argument("--source", choices=["espn", "sofascore"], help="优先数据源")

    pub = sub.add_parser("publish", help="发布内容")
    pub_sub = pub.add_subparsers(dest="channel")
    spw = pub_sub.add_parser("wechat", help="公众号：上传素材并创建草稿")
    spw.add_argument("--dir", required=True, help="digest 生成的内容目录，如 output/2026-07-16")
    spw.add_argument("--publish", action="store_true", help="创建草稿后直接提交发布")
    spp = pub_sub.add_parser("pushplus", help="通过 PushPlus 推送到自己微信")
    spp.add_argument("--dir", required=True, help="digest 生成的内容目录")

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
    if args.command == "digest":
        return cmd_digest(args)
    if args.command == "publish":
        if args.channel == "wechat":
            return cmd_publish_wechat(args)
        if args.channel == "pushplus":
            return cmd_publish_pushplus(args)
        build_parser().parse_args(["publish", "--help"])
        return 1

    build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
