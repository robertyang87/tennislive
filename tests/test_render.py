from datetime import date
from pathlib import Path

from tennislive.digest import Digest
from tennislive.models import MatchStats, MatchStatus, StatPair, Tour
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


def test_scoreboard_tournament_level_is_compact_and_precedes_name():
    from tennislive.render.webcards import _result_card

    atp = make_match(tournament="Swiss Open", match_id="atp250")
    atp.tournament.level = "ATP250"
    atp_card = _result_card(
        atp, hero=False, show_tournament=True, tag_upset=False
    )

    wta = make_match(tournament="Miami Open", match_id="wta1000")
    wta.tour = wta.tournament.tour = Tour.WTA
    wta.tournament.level = "W1000"
    wta_card = _result_card(
        wta, hero=False, show_tournament=True, tag_upset=False
    )

    slam = make_match(tournament="Wimbledon", match_id="slam")
    slam.tournament.level = "GS"
    slam_card = _result_card(
        slam, hero=False, show_tournament=True, tag_upset=False
    )

    wta500 = make_match(tournament="Berlin Open", match_id="wta500")
    wta500.tour = wta500.tournament.tour = Tour.WTA
    wta500.tournament.level = "WTA500"
    wta500_card = _result_card(
        wta500, hero=False, show_tournament=True, tag_upset=False
    )

    assert '<b class="tour-level">ATP250</b>' in atp_card
    assert '<b class="tour-level">WTA1000</b>' in wta_card
    assert '<b class="tour-level">WTA500</b>' in wta500_card
    assert '<b class="tour-level">大满贯</b>' in slam_card
    assert "ATP 250" not in atp_card


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


def test_inner_deck_pages_reuse_cover_visual_language(sample_digest):
    from tennislive.render.webcards import _shell, scoreboard_body

    page = _shell(
        scoreboard_body(sample_digest.results, "7.16 · 周四"),
        theme="dark",
    )

    assert "--panel:rgba(3,24,19,.82)" in page
    assert "background:var(--panel)" in page
    assert "font-family:'TL Display SC'" in page
    assert ".poster:not(.cover)::before" in page


def test_cards_fallback_matches_deck_policy(tmp_path, sample_digest, monkeypatch):
    """Pillow 兜底与正式卡组同规：不复活已移除的 focus/upset/end 页。

    ci 曾只在无 playwright 环境跑到兜底路径才暴露此问题；
    这里显式模拟渲染器不可用，让兜底路径在任何环境下都有覆盖。
    """
    from tennislive.render import cards, webcards

    def unavailable(*args, **kwargs):
        raise RuntimeError("simulated: playwright unavailable")

    monkeypatch.setattr(webcards, "generate_deck", unavailable)

    paths = cards.generate_cards(sample_digest, tmp_path / "cards")
    assert len(paths) >= 3
    names = [p.name for p in paths]
    assert "card_00_cover.png" in names
    assert not any(
        kind in name for name in names for kind in ("focus", "upset", "end")
    )

def test_umag_story_has_precise_champion_timeline(tmp_path, monkeypatch):
    from tennislive.render import tournament_story

    # 隔离冷却状态文件，避免仓库 data/ 的真实状态影响断言；
    # 球员名取中性值，避免命中球员特写（其新闻分高于赛事档案）
    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    match = make_match(
        tournament="Plava Laguna Croatia Open Umag",
        home_name="Player One",
        away_name="Player Two",
    )
    story = tournament_story.pick_tournament_story(
        Digest(today=date(2026, 7, 17), results=[match])
    )

    assert story is not None
    assert [moment.date for moment in story.moments] == ["2006-07-30", "2021-07-25"]
    assert "瓦林卡" in story.moments[0].player
    assert "6-2、6-2" in story.moments[1].detail
    assert "44 场" in story.facts[1]


def test_story_cooldown_prevents_repeat(tmp_path, monkeypatch):
    from tennislive.render import tournament_story

    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    match = make_match(
        tournament="Plava Laguna Croatia Open Umag",
        home_name="Player One",
        away_name="Player Two",
    )
    digest = Digest(today=date(2026, 7, 17), results=[match])

    first = tournament_story.pick_tournament_story(digest)
    assert first is not None and first.slug == "umag"
    tournament_story.mark_story_used(first.slug, digest.today)

    # 冷却期内换讲冷知识兜底，不重复也不留白；冷却期满恢复赛事优先
    second = tournament_story.pick_tournament_story(digest)
    assert second is not None and second.slug != "umag"
    assert second.kind == "trivia"
    later = Digest(today=date(2026, 8, 17), results=[match])
    assert tournament_story.pick_tournament_story(later).slug == "umag"


def test_story_slot_never_empty(tmp_path, monkeypatch):
    """没有可讲的赛事/球员时用冷知识兜底；全部冷却时重讲最久远的一条."""
    from tennislive.render import tournament_story

    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    match = make_match(
        tournament="Some Unknown Cup",
        home_name="Player One",
        away_name="Player Two",
    )
    digest = Digest(today=date(2026, 7, 18), results=[match])

    first = tournament_story.pick_tournament_story(digest)
    assert first is not None and first.kind == "trivia"

    # 第一条最早用过，其余冷知识晚一天——全部冷却时应重讲最早那条
    tournament_story.mark_story_used(first.slug, date(2026, 7, 1))
    for story in tournament_story.STORIES:
        if story.kind == "trivia" and story.slug != first.slug:
            tournament_story.mark_story_used(story.slug, date(2026, 7, 2))

    again = tournament_story.pick_tournament_story(digest)
    assert again is not None and again.slug == first.slug


def test_wishlist_records_uncovered_hot_winners(tmp_path, monkeypatch):
    """昨日热门胜者不在故事库时记入扩库清单；库内球员不重复记."""
    import json

    from tennislive.render import tournament_story

    monkeypatch.setattr(
        tournament_story, "WISHLIST_PATH", tmp_path / "story_wishlist.json"
    )
    covered = make_match(
        tournament="Wimbledon",
        home_name="Jannik Sinner",
        away_name="Player Two",
        winner=0,
        match_id="a",
    )
    uncovered = make_match(
        tournament="Wimbledon",
        home_name="Flavio Cobolli",
        away_name="Player Four",
        winner=0,
        match_id="b",
    )
    digest = Digest(today=date(2026, 7, 19), results=[covered, uncovered])

    tournament_story.record_story_wishlist(digest)
    wishlist = json.loads((tmp_path / "story_wishlist.json").read_text("utf-8"))

    assert "flavio cobolli" in wishlist
    assert wishlist["flavio cobolli"]["hits"] == 1
    assert wishlist["flavio cobolli"]["evidence"][0]["tournament"] == "Wimbledon"
    assert not any("sinner" in key for key in wishlist)  # 库内球员不进清单

    # 再次记录累计热度
    tournament_story.record_story_wishlist(digest)
    wishlist = json.loads((tmp_path / "story_wishlist.json").read_text("utf-8"))
    assert wishlist["flavio cobolli"]["hits"] == 2


def test_dramatic_loser_is_a_headliner(tmp_path, monkeypatch):
    """带伤退赛/遭爆冷的输球方与胜者同级：热度属于比赛事件，不只属于赢家."""
    import json

    from dataclasses import replace

    from tennislive.models import MatchStatus
    from tennislive.render import tournament_story

    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    monkeypatch.setattr(
        tournament_story, "WISHLIST_PATH", tmp_path / "story_wishlist.json"
    )
    fake_img = tmp_path / "img.jpg"
    fake_img.write_bytes(b"\xff\xd8fake")
    monkeypatch.setattr(
        tournament_story,
        "STORIES",
        tuple(replace(s, image=fake_img) for s in tournament_story.STORIES),
    )

    # 德约带伤退赛输球 + 乌马格赛事进行中：输球方的球员特写应压过赛事档案
    retired = make_match(
        tournament="Plava Laguna Croatia Open Umag",
        home_name="Player One",
        away_name="Novak Djokovic",
        winner=0,
        status=MatchStatus.RETIRED,
    )
    digest = Digest(today=date(2026, 7, 20), results=[retired])

    story = tournament_story.pick_tournament_story(digest)
    assert story is not None and story.slug == "djokovic"

    # 扩库清单也记录高事件性比赛的输球方（库外球员），并标注原因
    retired2 = make_match(
        tournament="Wimbledon",
        home_name="Player One",
        away_name="Stan Wawrinka",
        winner=0,
        status=MatchStatus.RETIRED,
        match_id="w1",
    )
    tournament_story.record_story_wishlist(
        Digest(today=date(2026, 7, 20), results=[retired2])
    )
    wishlist = json.loads((tmp_path / "story_wishlist.json").read_text("utf-8"))
    assert "stan wawrinka" in wishlist
    assert "伤退惜败" in wishlist["stan wawrinka"]["evidence"][0]["note"]


def test_player_story_newsworthiness_ranking(tmp_path, monkeypatch):
    from dataclasses import replace

    from tennislive.models import MatchStatus
    from tennislive.render import tournament_story

    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    # 用同一张假图激活全部故事（本地没有 assets/players 时球员特写会被跳过）
    fake_img = tmp_path / "img.jpg"
    fake_img.write_bytes(b"\xff\xd8fake")
    monkeypatch.setattr(
        tournament_story,
        "STORIES",
        tuple(replace(s, image=fake_img) for s in tournament_story.STORIES),
    )

    # 昨日赢球的球员特写（3 分）压过进行中的赛事档案（2 分）
    won = make_match(
        tournament="Plava Laguna Croatia Open Umag",
        home_name="Qinwen Zheng",
        away_name="Player Two",
        winner=0,
    )
    story = tournament_story.pick_tournament_story(
        Digest(today=date(2026, 7, 18), results=[won])
    )
    assert story is not None and story.slug == "zheng-qinwen"
    assert story.kind == "player"

    # 球员仅出场（赛程 1 分）时，赛事档案（2 分）优先
    scheduled = make_match(
        tournament="Plava Laguna Croatia Open Umag",
        home_name="Iga Swiatek",
        away_name="Player Two",
        status=MatchStatus.SCHEDULED,
        winner=None,
    )
    story = tournament_story.pick_tournament_story(
        Digest(today=date(2026, 7, 18), schedule=[scheduled])
    )
    assert story is not None and story.slug == "umag"


def test_player_story_card_uses_spotlight_branding(tmp_path):
    from dataclasses import replace

    from tennislive.render import webcards
    from tennislive.render.tournament_story import STORIES

    story = next(s for s in STORIES if s.kind == "player")
    fake_img = tmp_path / "player.jpg"
    fake_img.write_bytes(b"\xff\xd8fake")
    body = webcards.tournament_story_body(replace(story, image=fake_img), "07.18 星期六")

    assert "球员特写" in body and "赛事档案" not in body
    assert story.source_label in body


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
