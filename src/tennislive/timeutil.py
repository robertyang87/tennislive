"""北京时间（Asia/Shanghai）相关的时间工具：全项目统一用这里的函数展示时间."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc

WEEKDAY_ZH = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def now_utc() -> datetime:
    return datetime.now(tz=UTC)


def now_beijing() -> datetime:
    return datetime.now(tz=BEIJING)


def to_beijing(dt: datetime) -> datetime:
    """任意 datetime 转北京时间；naive 时间按 UTC 处理."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(BEIJING)


def beijing_today() -> date:
    return now_beijing().date()

def beijing_yesterday() -> date:
    return beijing_today() - timedelta(days=1)


def fmt_time_beijing(dt: datetime | None) -> str:
    """'14:30'（北京时间）；无时间返回 '待定'."""
    if dt is None:
        return "待定"
    return to_beijing(dt).strftime("%H:%M")


def fmt_date_zh(d: date) -> str:
    """'2026年7月16日 周四'."""
    return f"{d.year}年{d.month}月{d.day}日 {WEEKDAY_ZH[d.weekday()]}"


def fmt_datetime_beijing(dt: datetime | None) -> str:
    """'7月16日 14:30'（北京时间）."""
    if dt is None:
        return "时间待定"
    b = to_beijing(dt)
    return f"{b.month}月{b.day}日 {b.strftime('%H:%M')}"


def parse_date_arg(s: str | None) -> date:
    """解析 CLI 日期参数：支持 YYYY-MM-DD / today / yesterday / tomorrow / ±N."""
    if not s or s == "today":
        return beijing_today()
    if s == "yesterday":
        return beijing_yesterday()
    if s == "tomorrow":
        return beijing_today() + timedelta(days=1)
    if s.lstrip("+-").isdigit() and (s.startswith("+") or s.startswith("-")):
        return beijing_today() + timedelta(days=int(s))
    return date.fromisoformat(s)


def beijing_date_to_utc_range(d: date) -> tuple[datetime, datetime]:
    """北京时间某一天对应的 UTC 时间区间 [start, end)."""
    start_local = datetime(d.year, d.month, d.day, tzinfo=BEIJING)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)
