"""统一的数据模型：不同数据源抓取后都归一化为这些结构."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Tour(str, Enum):
    ATP = "ATP"
    WTA = "WTA"


class MatchStatus(str, Enum):
    SCHEDULED = "scheduled"   # 未开始
    LIVE = "live"             # 进行中
    FINISHED = "finished"     # 已完赛（正常结束）
    RETIRED = "retired"       # 对手退赛（比赛中途）
    WALKOVER = "walkover"     # 不战而胜
    CANCELLED = "cancelled"   # 取消
    POSTPONED = "postponed"   # 推迟

    @property
    def is_final(self) -> bool:
        """比赛是否已产生结果."""
        return self in (
            MatchStatus.FINISHED,
            MatchStatus.RETIRED,
            MatchStatus.WALKOVER,
        )


@dataclass
class Player:
    name: str                          # 英文名，如 "Jannik Sinner"
    country: Optional[str] = None      # IOC 三字码，如 "ITA"
    seed: Optional[int] = None         # 种子号
    rank: Optional[int] = None         # 世界排名
    headshot_url: Optional[str] = None # 官网头像图 URL
    player_id: Optional[str] = None    # 数据源内部 ID


@dataclass
class SetScore:
    home: int
    away: int
    home_tiebreak: Optional[int] = None
    away_tiebreak: Optional[int] = None

    def display(self) -> str:
        """如 '7-6(5)' 或 '6-3'（从 home 视角）；决胜盘超级抢十显示 '10-8(抢十)'."""
        # 超级抢十（match tiebreak）：数据源常记为 1-0 + 抢十比分
        if (
            {self.home, self.away} == {1, 0}
            and self.home_tiebreak is not None
            and self.away_tiebreak is not None
        ):
            return f"{self.home_tiebreak}-{self.away_tiebreak}(抢十)"
        s = f"{self.home}-{self.away}"
        # 抢七分数：只标输方小分（惯例）
        if self.home_tiebreak is not None and self.away_tiebreak is not None:
            loser_tb = min(self.home_tiebreak, self.away_tiebreak)
            s += f"({loser_tb})"
        elif self.home_tiebreak is not None:
            s += f"({self.home_tiebreak})"
        elif self.away_tiebreak is not None:
            s += f"({self.away_tiebreak})"
        return s


@dataclass
class StatPair:
    home: float
    away: float


@dataclass
class MatchStats:
    """Detailed match statistics in home/away order."""

    source: str
    source_url: Optional[str] = None
    total_points_won: Optional[StatPair] = None
    service_points_won: Optional[StatPair] = None
    first_serve_in_pct: Optional[StatPair] = None
    first_serve_won_pct: Optional[StatPair] = None
    second_serve_won_pct: Optional[StatPair] = None
    aces: Optional[StatPair] = None
    double_faults: Optional[StatPair] = None
    break_points_won: Optional[StatPair] = None
    break_points_chances: Optional[StatPair] = None
    winners: Optional[StatPair] = None
    unforced_errors: Optional[StatPair] = None
    duration_minutes: Optional[int] = None


@dataclass
class Tournament:
    name: str                          # 英文名，如 "Wimbledon"
    tour: Tour
    level: Optional[str] = None        # GS / M1000 / W1000 / 500 / 250 / Finals / TeamCup
    surface: Optional[str] = None      # Hard / Clay / Grass / Carpet
    city: Optional[str] = None
    country: Optional[str] = None
    tournament_id: Optional[str] = None


@dataclass
class Match:
    match_id: str
    tour: Tour
    tournament: Tournament
    home: list[Player]                 # 单打 1 人，双打 2 人
    away: list[Player]
    status: MatchStatus = MatchStatus.SCHEDULED
    round_name: Optional[str] = None   # 数据源原始轮次名，如 "Round of 16"
    discipline: Optional[str] = None   # 如 "Men's Singles" / "Women's Doubles"
    start_utc: Optional[datetime] = None
    sets: list[SetScore] = field(default_factory=list)
    winner: Optional[int] = None       # 0=home 胜, 1=away 胜, None=未定
    note: Optional[str] = None         # 备注（退赛原因等）
    court: Optional[str] = None
    status_detail: Optional[str] = None  # 直播状态原始描述，如 "Set 3"
    stats: Optional[MatchStats] = None
    editorial_note: Optional[str] = None
    editorial_source: Optional[str] = None
    editorial_url: Optional[str] = None

    @property
    def is_doubles(self) -> bool:
        return len(self.home) > 1 or len(self.away) > 1

    @property
    def is_singles(self) -> bool:
        return not self.is_doubles

    def score_display(self, from_winner: bool = True) -> str:
        """比分串，如 '6-4 3-6 7-6(4)'。from_winner=True 时从胜者视角显示."""
        if not self.sets:
            return ""
        flip = from_winner and self.winner == 1
        parts = []
        for s in self.sets:
            if flip:
                flipped = SetScore(
                    home=s.away,
                    away=s.home,
                    home_tiebreak=s.away_tiebreak,
                    away_tiebreak=s.home_tiebreak,
                )
                parts.append(flipped.display())
            else:
                parts.append(s.display())
        return " ".join(parts)

    def winner_players(self) -> Optional[list[Player]]:
        if self.winner == 0:
            return self.home
        if self.winner == 1:
            return self.away
        return None

    def loser_players(self) -> Optional[list[Player]]:
        if self.winner == 0:
            return self.away
        if self.winner == 1:
            return self.home
        return None


@dataclass
class DailyData:
    """一天的数据快照：已完赛 + 进行中 + 未开始."""
    date_beijing: str                  # 北京时间日期 YYYY-MM-DD
    matches: list[Match] = field(default_factory=list)
    source: Optional[str] = None       # 数据来源名称
    source_status: dict[str, str] = field(default_factory=dict)
    fetched_at_utc: Optional[datetime] = None

    def finished(self) -> list[Match]:
        return [m for m in self.matches if m.status.is_final]

    def live(self) -> list[Match]:
        return [m for m in self.matches if m.status == MatchStatus.LIVE]

    def upcoming(self) -> list[Match]:
        return [m for m in self.matches if m.status == MatchStatus.SCHEDULED]
