from datetime import date
from pathlib import Path

from tennislive.digest import Digest
from tennislive.models import MatchStats, MatchStatus, StatPair
from tennislive.render.common import group_by_tournament, result_line, schedule_line
from tennislive.render.focus import focus_comparison, has_detailed_stats
from tennislive.render.pushmsg import pin_asset_revision, to_copy_page, to_push_html
from tennislive.render.wechat import article_title, to_html, to_markdown
from tennislive.render.xiaohongshu import post_title, to_post

from conftest import make_match


def test_result_line_winner_perspective():
    m = make_match(winner=1, sets=((4, 6), (3, 6)), tiebreaks=())
    line = result_line(m)
    # 胜者（德约科维奇）在前，比分从胜者视角
    assert line.startswith("🇷🇸 [5]德约科维奇 2-0")
    assert "6-4 6-3" in line


def test_result_line_with_tiebreak():
    m = make_match()
    line = result_line(m)
    assert "辛纳" in line and "7-6(3)" in line


def test_schedule_line_beijing_time():
    m = make_match(status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=())
    # 12:30 UTC = 20:30 北京
    assert schedule_line(m).startswith("20:30")


def test_group_by_tournament_orders_gs_first():
    gs = make_match(tournament="Wimbledon", match_id="a")
    small = make_match(tournament="Nordea Open Bastad", match_id="b")
    groups = group_by_tournament([small, gs])
    assert groups[0].name_en == "Wimbledon"
    assert "大满贯" in groups[0].title


def test_wechat_markdown(sample_digest):
    md = to_markdown(sample_digest)
    assert "中国军团" in md          # 郑钦文在赛果里 → 中国军团板块
    assert "昨夜焦点赛果" in md
    assert "今晚焦点" in md
    assert "郑钦文" in md
    assert "北京时间" in md


def test_wechat_html_inline_styles_only(sample_digest):
    html = to_html(sample_digest)
    assert "<style" not in html      # 公众号会剥离 style 块，必须全内联
    assert 'style="' in html
    assert "郑钦文" in html


def test_wechat_title_length(sample_digest):
    assert len(article_title(sample_digest)) <= 64


def test_xhs_post(sample_digest):
    post = to_post(sample_digest)
    title = post_title(sample_digest)
    assert title.startswith(
        f"{sample_digest.today.month}月{sample_digest.today.day}日｜"
    )
    assert len(title) <= 20
    assert "#网球" in post
    body = post.split("\n", 2)[2]
    assert len(body) <= 1000
    assert "一场球看细一点" not in post
    assert "7:30" not in post


def test_professional_focus_is_published_only_with_detailed_stats(sample_digest):
    match = sample_digest.results[1]
    assert not has_detailed_stats(match)
    assert "焦点复盘" not in to_markdown(sample_digest)

    match.stats = MatchStats(
        source="Sportradar 授权网球数据",
        aces=StatPair(7, 3),
        double_faults=StatPair(2, 5),
        first_serve_won_pct=StatPair(76, 61),
        break_points_won=StatPair(4, 1),
        break_points_chances=StatPair(8, 4),
    )

    assert has_detailed_stats(match)
    assert "一场球看细一点" in to_post(sample_digest)
    assert "焦点复盘" in to_markdown(sample_digest)


def test_push_copy_page_and_button(sample_digest):
    xhs = "测试标题 <1>\n\n正文第一行\n正文第二行"
    page = to_copy_page(xhs)
    push_html = to_push_html(
        sample_digest, cards=["card_00_cover.png"], xhs_text=xhs
    )

    assert "复制标题" in page and "复制正文" in page
    assert "测试标题 &lt;1&gt;" in page
    assert "正文第一行" in page
    assert "copy.html" in push_html
    assert "robertyang87.github.io/tennislive" in push_html
    assert "打开并复制文案" in push_html
    assert "正文第一行" not in push_html


def test_pin_asset_revision_only_rewrites_valid_jsdelivr_main_urls():
    html = (
        '<img src="https://cdn.jsdelivr.net/gh/robertyang87/tennislive@main/'
        'output/2026-07-17/cards/card_00_cover.png">'
        '<img src="https://example.com/image.png">'
    )
    revision = "a1b2c3d4e5f6789012345678901234567890abcd"

    pinned = pin_asset_revision(html, revision)

    assert f"tennislive@{revision}/output/" in pinned
    assert "https://example.com/image.png" in pinned
    assert pin_asset_revision(html, "abc123") == html
    assert pin_asset_revision(html, "not-a-commit") == html


def test_cards_generation(tmp_path, sample_digest):
    from tennislive.render.cards import generate_cards

    paths = generate_cards(sample_digest, tmp_path / "cards")
    assert len(paths) >= 3  # 封面 + 赛果页 + 赛程页
    for p in paths:
        assert Path(p).stat().st_size > 10_000  # 是实际渲染的 PNG 而非空文件
    names = [p.name for p in paths]
    assert "card_00_cover.png" in names
    assert not any("focus" in name for name in names)
    assert not any("upset" in name or "end" in name for name in names)


def test_umag_story_has_precise_champion_timeline():
    from tennislive.render.tournament_story import pick_tournament_story

    match = make_match(tournament="Plava Laguna Croatia Open Umag")
    story = pick_tournament_story(
        Digest(today=date(2026, 7, 17), results=[match])
    )

    assert story is not None
    assert [moment.date for moment in story.moments] == ["2006-07-30", "2021-07-25"]
    assert "瓦林卡" in story.moments[0].player
    assert "6-2、6-2" in story.moments[1].detail
    assert "44 场" in story.facts[1]


def test_coverage_report_lists_tour_level(sample_digest):
    from tennislive.render.coverage import coverage_report

    sample_digest.results[0].tournament.level = "GS"
    report = coverage_report(sample_digest)
    assert "ATP GS" in report
    assert "总场次" in report


def test_focus_comparison_prefers_detailed_official_stats():
    match = make_match()
    match.stats = MatchStats(
        source="Sportradar 授权网球数据",
        source_url="https://api.sportradar.com/tennis/trial/v3/en/sport_events/example/summary.json",
        total_points_won=StatPair(130, 129),
        first_serve_in_pct=StatPair(68, 54),
        first_serve_won_pct=StatPair(73, 73),
        second_serve_won_pct=StatPair(49, 52),
        aces=StatPair(2, 6),
        double_faults=StatPair(3, 3),
        break_points_won=StatPair(9, 7),
        break_points_chances=StatPair(10, 11),
        winners=StatPair(29, 62),
        unforced_errors=StatPair(25, 67),
        duration_minutes=222,
    )

    comparison = focus_comparison(match)

    assert comparison.rows[0] == ("总得分", "130", "129")
    assert ("一发成功率", "68%", "54%") in comparison.rows
    assert ("破发兑现", "9/10", "7/11") in comparison.rows
    assert ("制胜分 / 非受迫", "29 / 25", "62 / 67") in comparison.rows
    assert comparison.duration_label == "3小时42分"
    assert "总得分只差1分" in comparison.verdict
    assert "少犯42次" in comparison.verdict


def test_focus_comparison_keeps_score_fallback_without_stats():
    comparison = focus_comparison(make_match())
    assert comparison.rows[0][0] == "盘数"
    assert comparison.rows[1][0] == "总局数"
    assert any(row[0] == "首盘" for row in comparison.rows)
    assert comparison.source_label is None


def test_focus_comparison_supports_five_set_grand_slam_match():
    match = make_match(
        sets=((6, 4), (3, 6), (7, 6), (4, 6), (6, 3)),
        tiebreaks=(None, None, (7, 5), None, None),
    )

    comparison = focus_comparison(match)

    assert len(comparison.rows) == 8
    assert comparison.rows[-2][0] == "第四盘"
    assert comparison.rows[-1] == ("第五盘", "6", "3")
