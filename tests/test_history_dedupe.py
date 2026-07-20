from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from tennislive.render.history_dedupe import (
    HistoricalPost,
    check_against_history,
    check_recent_posts,
    load_recent_posts,
)


def _post(day: date, text: str, name: str = "xiaohongshu.txt") -> HistoricalPost:
    return HistoricalPost(day, Path(day.isoformat()) / name, text)


def test_no_history_is_safely_allowed(tmp_path):
    result = check_recent_posts("\U0001f3be7.20|\u4eca\u665a\u6700\u503c\u5f97\u8ffd\u7684\u4e00\u573a\n\n\u90d1\u94a6\u6587\u8fce\u6765\u786c\u4ed7", tmp_path)

    assert result.passed
    assert result.history_count == 0
    assert result.comparisons == ()
    assert "\u5b89\u5168\u653e\u884c" in result.reason


def test_configured_minimum_history_safely_allows_a_thin_sample():
    duplicate = "7.20|\u90d1\u94a6\u6587\u4eca\u665a\u8fce\u786c\u4ed7\n\u4eca\u665a\u5341\u70b9\u534a,\u5148\u628a\u8fd9\u4e00\u573a\u5708\u8d77\u6765\u3002"

    result = check_against_history(
        duplicate,
        [_post(date(2026, 7, 19), duplicate)],
        minimum_history=2,
    )

    assert result.passed
    assert result.history_count == 1
    assert result.comparisons == ()
    assert "1/2" in result.reason


def test_changed_date_and_emoji_do_not_hide_duplicate_copy():
    old = """\U0001f5257.19|\u90d1\u94a6\u6587\u4eca\u665a\u8fce\u786c\u4ed7

\u4eca\u665a\u5341\u70b9\u534a,\u5148\u628a\u8fd9\u4e00\u573a\u5708\u8d77\u6765\u3002
\u90d1\u94a6\u6587\u8981\u51b2\u51fb\u56db\u5f3a,\u5bf9\u9762\u662f\u5927\u6ee1\u8d2f\u51a0\u519b\u3002

#\u90d1\u94a6\u6587 #\u7f51\u7403 #WTA"""
    current = old.replace("\U0001f5257.19", "\U0001f3be7.20").replace("#WTA", "#ATP")

    result = check_against_history(
        current,
        [_post(date(2026, 7, 19), old)],
    )

    assert not result.passed
    assert result.closest is not None
    assert result.closest.title_similarity == 1
    assert "\u6807\u9898\u94a9\u5b50" in result.reason
    assert "\u5f00\u573a" in result.reason


def test_shared_daily_structure_does_not_flag_different_stories():
    old = """\U0001f3c67.19|\u8f9b\u7eb3\u8d5b\u70b9\u9006\u8f6c\u593a\u51a0

\u4eca\u5929\u53ea\u8bb2\u4e09\u4ef6\u4e8b:
\u8f9b\u7eb3\u5728\u6e29\u5e03\u5c14\u767b\u51b3\u8d5b\u633d\u6551\u8d5b\u70b9,\u6700\u7ec8\u4e94\u76d8\u6367\u676f\u3002
\u4e00\u573a\u7403\u770b\u7ec6\u4e00\u70b9
\u4ed6\u7684\u4e00\u53d1\u5f97\u5206\u7387\u548c\u7f51\u524d\u6210\u529f\u7387\u662f\u9006\u8f6c\u5173\u952e\u3002
\u5173\u6ce8 @\u7f51\u7403\u65f6\u5dee|\u7761\u9192\u770b\u61c2\u6628\u591c
#\u7f51\u7403 #ATP #\u7f51\u7403\u65f6\u5dee"""
    current = """\U0001f5257.20|\u90d1\u94a6\u6587\u5e03\u62c9\u683c\u9996\u6218

\u4eca\u5929\u53ea\u8bb2\u4e09\u4ef6\u4e8b:
\u90d1\u94a6\u6587\u4eca\u665a\u8fce\u6218\u6377\u514b\u4e3b\u573a\u7403\u5458,\u63a5\u53d1\u7403\u662f\u7b2c\u4e00\u770b\u70b9\u3002
\u4e00\u573a\u7403\u770b\u7ec6\u4e00\u70b9
\u7ea2\u571f\u4e0a\u7684\u56de\u5408\u8282\u594f\u4f1a\u68c0\u9a8c\u5979\u7684\u53cd\u624b\u7a33\u5b9a\u6027\u3002
\u5173\u6ce8 @\u7f51\u7403\u65f6\u5dee|\u7761\u9192\u770b\u61c2\u6628\u591c
#\u7f51\u7403 #WTA #\u7f51\u7403\u65f6\u5dee"""

    result = check_against_history(current, [_post(date(2026, 7, 19), old)])

    assert result.passed, result.reason
    assert result.closest is not None
    assert result.closest.triggers == ()


def test_exact_long_line_is_reported_for_explanation():
    reused = "\u4eca\u665a\u5341\u70b9\u534a,\u5148\u628a\u8fd9\u573a\u4e2d\u56fd\u7403\u5458\u7684\u5173\u952e\u6218\u5708\u8d77\u6765\u3002"
    old = f"7.19|\u7ea2\u571f\u51b3\u6218\n\n{reused}\n\u4e00\u53d1\u7a33\u5b9a\u6027\u4f1a\u51b3\u5b9a\u6bd4\u8d5b\u8d70\u5411\u3002"
    current = f"7.20|\u4eca\u665a\u786c\u4ed7\n\n{reused}\n\u63a5\u53d1\u7403\u9700\u8981\u5c3d\u5feb\u8fdb\u5165\u8282\u594f\u3002"

    result = check_against_history(current, [_post(date(2026, 7, 19), old)])

    assert not result.passed
    assert result.closest.repeated_phrases == (reused,)
    assert reused in result.reason


def test_loader_uses_only_latest_seven_before_current_date(tmp_path):
    start = date(2026, 7, 8)
    for offset in range(12):
        day = start + timedelta(days=offset)
        folder = tmp_path / day.isoformat()
        folder.mkdir()
        (folder / "xiaohongshu.txt").write_text(
            f"{day.month}.{day.day}|\u7b2c{offset}\u671f", encoding="utf-8"
        )
    (tmp_path / "not-a-date").mkdir()

    posts = load_recent_posts(tmp_path, before=date(2026, 7, 20))

    assert len(posts) == 7
    assert posts[0].published_on == date(2026, 7, 19)
    assert posts[-1].published_on == date(2026, 7, 13)


def test_result_and_comparison_order_are_deterministic():
    history = [
        _post(date(2026, 7, 18), "7.18|\u8428\u5df4\u4f26\u5361\u8fc7\u5173\n\u4e24\u76d8\u6bd4\u8d5b\u90fd\u5728\u63a5\u53d1\u73af\u8282\u62c9\u5f00\u5dee\u8ddd\u3002"),
        _post(date(2026, 7, 19), "7.19|\u8f9b\u7eb3\u593a\u51a0\n\u51b3\u8d5b\u5728\u957f\u56de\u5408\u91cc\u5efa\u7acb\u4e86\u660e\u663e\u4f18\u52bf\u3002"),
    ]
    text = "7.20|\u90d1\u94a6\u6587\u51fa\u6218\n\u4eca\u665a\u7684\u91cd\u70b9\u662f\u5979\u5982\u4f55\u5904\u7406\u5bf9\u624b\u7684\u53d8\u7ebf\u3002"

    first = check_against_history(text, history)
    second = check_against_history(text, list(reversed(history)))

    assert first == second
    assert [item.published_on for item in first.comparisons] == [
        date(2026, 7, 19),
        date(2026, 7, 18),
    ]
