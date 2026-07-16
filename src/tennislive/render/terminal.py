"""终端渲染：rich 表格展示赛程/赛果（北京时间）."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..models import Match, MatchStatus
from ..timeutil import fmt_date_zh, fmt_time_beijing
from .common import (
    group_by_tournament,
    match_round_display,
    result_line,
    side_display,
    status_display,
)

console = Console()


def _status_style(m: Match) -> str:
    return {
        MatchStatus.LIVE: "bold red",
        MatchStatus.FINISHED: "green",
        MatchStatus.RETIRED: "yellow",
        MatchStatus.WALKOVER: "yellow",
        MatchStatus.SCHEDULED: "cyan",
    }.get(m.status, "white")


def render_matches(matches: list[Match], title: str) -> None:
    """按赛事分组打印比赛列表."""
    if not matches:
        console.print(f"[dim]{title}：暂无比赛[/dim]")
        return

    console.print()
    console.rule(f"[bold]{title}[/bold]")
    for group in group_by_tournament(matches):
        table = Table(
            title=group.title,
            title_style="bold bright_green",
            show_lines=False,
            expand=False,
            pad_edge=True,
        )
        table.add_column("时间(北京)", justify="center", min_width=10)
        table.add_column("轮次", justify="center", min_width=8)
        table.add_column("对阵 / 赛果", justify="left", min_width=40)
        table.add_column("状态", justify="center", min_width=8)

        for m in group.matches:
            if m.status.is_final:
                versus = result_line(m)
            else:
                score = m.score_display(from_winner=False)
                versus = f"{side_display(m.home)} vs {side_display(m.away)}"
                if score:
                    versus += f"  {score}"
            table.add_row(
                fmt_time_beijing(m.start_utc),
                match_round_display(m) or "-",
                versus,
                Text(status_display(m), style=_status_style(m)),
            )
        console.print(table)


def render_day_summary(date_str: str, results: list[Match], live: list[Match], upcoming: list[Match]) -> None:
    from datetime import date as _date

    d = _date.fromisoformat(date_str)
    console.print(f"\n[bold underline]🎾 {fmt_date_zh(d)}（北京时间）[/bold underline]")
    if results:
        render_matches(results, f"赛果（{len(results)} 场）")
    if live:
        render_matches(live, f"进行中（{len(live)} 场）")
    if upcoming:
        render_matches(upcoming, f"未开赛（{len(upcoming)} 场）")
    if not (results or live or upcoming):
        console.print("[dim]当天没有 ATP/WTA 巡回赛比赛。[/dim]")
