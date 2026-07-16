from datetime import date, datetime, timezone

from tennislive.timeutil import (
    beijing_date_to_utc_range,
    fmt_date_zh,
    fmt_time_beijing,
    parse_date_arg,
    to_beijing,
)


def test_to_beijing_from_utc():
    dt = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)
    b = to_beijing(dt)
    assert (b.hour, b.minute) == (20, 30)


def test_naive_treated_as_utc():
    dt = datetime(2026, 7, 15, 23, 0)
    b = to_beijing(dt)
    assert b.day == 16 and b.hour == 7


def test_fmt_time_beijing_none():
    assert fmt_time_beijing(None) == "待定"


def test_fmt_date_zh():
    assert fmt_date_zh(date(2026, 7, 16)) == "2026年7月16日 周四"


def test_parse_date_arg():
    assert parse_date_arg("2026-07-16") == date(2026, 7, 16)
    assert parse_date_arg("today") is not None
    assert (parse_date_arg("tomorrow") - parse_date_arg("today")).days == 1
    assert (parse_date_arg("today") - parse_date_arg("yesterday")).days == 1
    assert (parse_date_arg("+2") - parse_date_arg("today")).days == 2


def test_beijing_day_utc_range():
    start, end = beijing_date_to_utc_range(date(2026, 7, 16))
    assert start == datetime(2026, 7, 15, 16, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 16, 16, 0, tzinfo=timezone.utc)
