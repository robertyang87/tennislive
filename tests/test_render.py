import re
from datetime import date
from pathlib import Path

from tennislive.digest import Digest
from tennislive.models import MatchStats, MatchStatus, StatPair, Tour
from tennislive.render.common import group_by_tournament, result_line, schedule_line
from tennislive.render.focus import focus_comparison, has_detailed_stats
from tennislive.render.pushmsg import pin_asset_revision, to_copy_page, to_push_html
from tennislive.render.wechat import article_title, to_html, to_markdown
from tennislive.render.xiaohongshu import plan_post, post_title, to_post

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
    from tennislive.render.xiaohongshu import xhs_title_len

    post = to_post(sample_digest)
    title = post_title(sample_digest)
    # V1 §3.1：发布标题与封面主钩子同源（头条候选 ①）+ 日期与 emoji
    d = sample_digest.today
    assert f"{d.month}.{d.day}今日球局｜" in title
    hook = title.split("｜", 1)[1]
    assert hook and "…" not in hook
    assert xhs_title_len(title) <= 20  # 平台口径：半角记 0.5
    assert "#网球" in post
    body = post.split("\n", 2)[2]
    assert len(body) <= 520
    assert "昨夜最值回看" in post
    assert "今晚焦点｜1场" in post
    assert "📝 " in post
    assert "💬 " in post
    assert any(
        phrase in post
        for phrase in ("第一次记住", "哪句赛前提醒", "评论区押一个名字")
    )
    assert "明早一起对答案" in post
    plan, _ = plan_post(sample_digest)
    assert plan.question in plan.pinned_comment
    assert "标准答案" in plan.pinned_comment or "明早回来对照赛果" in plan.pinned_comment
    assert result_line(sample_digest.results[0]) not in post
    assert "ATP 250" not in post and "WTA 250" not in post
    assert "一场球看细一点" not in post
    assert "7:30" not in post
    assert "…" not in post and "..." not in post


def test_quarterfinal_schedule_insight_differs_by_matchup():
    """同一赛事同轮次的多场比赛不能复用同一句"分水岭"套话.

    生产环境曾出现过：一晚 4 场基茨比厄尔公开赛男单八强赛，"今晚焦点"卡片
    里 4 场的看点文案逐字相同，因为四分之一决赛此前是固定文案、不看排名/
    种子差异。
    """
    from tennislive.render.story import schedule_insight

    close = make_match(
        home_name="Mariano Navone", away_name="Quentin Halys",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
        round_name="Quarterfinals",
    )
    close.home[0].rank, close.home[0].seed = 47, None
    close.away[0].rank, close.away[0].seed = 83, None

    lopsided = make_match(
        home_name="Alexander Bublik", away_name="Alex Molcan",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
        round_name="Quarterfinals", match_id="qf2",
    )
    lopsided.home[0].rank, lopsided.home[0].seed = 11, 1
    lopsided.away[0].rank, lopsided.away[0].seed = 81, None

    seeded_only = make_match(
        home_name="Yannick Hanfmann", away_name="Sebastian Baez",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
        round_name="Quarterfinals", match_id="qf3",
    )
    seeded_only.home[0].rank = seeded_only.away[0].rank = None
    seeded_only.home[0].seed, seeded_only.away[0].seed = None, 5

    lines = {
        schedule_insight(close),
        schedule_insight(lopsided),
        schedule_insight(seeded_only),
    }
    assert len(lines) == 3  # 三场不同签况必须产出三句不同的看点
    assert all("四强席位" in line or "抢七" in line or "话语权" in line for line in lines)


def test_quarterfinal_insight_survives_render_layer_truncation_intact():
    """长文案被正文渲染层按标点截断时，剩下的分句不能读起来断在半句.

    生产环境曾实际出现：'卡利尼娜占着25位排名优势，可四强席位近在眼前时，
    压力比排名更说明问题。' 在 xiaohongshu 正文渲染时被截到 34 字上限，
    砍掉了整个收尾分句，只留下不成句的'……可四强席位近在眼前时'。
    现在的模板把第一个分句写成独立完整的句子，被截断也不会读不完。
    """
    from tennislive.render.story import schedule_insight
    from tennislive.render.xiaohongshu import _short

    match = make_match(
        home_name="Tamara Korpatsch", away_name="Anhelina Kalinina",
        home_country="GER", away_country="UKR",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
        round_name="Quarterfinals",
    )
    match.home[0].seed = match.away[0].seed = None
    match.home[0].rank, match.away[0].rank = 81, 56  # 差 25 位，命中 12<=gap<35 分支

    insight = schedule_insight(match)
    for limit in (28, 34):  # 34 = 正文非压缩上限；28 = 压缩模式上限
        truncated = _short(insight, limit)
        assert not truncated.endswith(("可", "但", "时", "而"))  # 不留悬空连接词


def test_neutral_compact_opinion_rotates_by_day():
    """无中国球员的压缩兜底文案必须按日轮换，否则会撞上7天防重复 FATAL 闸门。

    生产环境曾因这句话固定不变，连续多天对同一场无中国球员的比赛
    生成完全相同的兜底文案，被 history_dedupe 判定为复用长句而阻断发布。
    """
    from datetime import date

    from tennislive.render.xiaohongshu import _opinion

    tonight = [sample_digest_match_without_chinese_player()]
    seen = {
        _opinion(None, tonight, compact=True, today=date(2026, 7, day))
        for day in range(21, 28)
    }
    assert len(seen) > 1  # 一周之内不能全是同一句


def sample_digest_match_without_chinese_player():
    return make_match(
        home_name="Tamara Korpatsch", home_country="GER",
        away_name="Julia Stusek", away_country="AUT",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
    )


def test_xhs_preview_replaces_long_player_name_before_shortening(sample_digest, monkeypatch):
    from tennislive.render import xiaohongshu

    match = sample_digest.schedule[0]
    match.home[0].name = "Oleksandra Oliynykova"
    monkeypatch.setattr(
        xiaohongshu,
        "editorial_tonight_focus",
        lambda _matches: [match],
    )
    monkeypatch.setattr(
        xiaohongshu,
        "preview_angle",
        lambda _match, _today: (
            "Oleksandra Oliynykova背着1号种子的签位，首轮先过必须赢这一关"
        ),
    )

    section, _ = xiaohongshu._tonight_section(sample_digest, compact=True)

    assert section is not None
    assert "看点｜他背着1号种子的签位，首轮先过必须赢这一关。" in section.lines
    assert "…。" not in section.lines[-1]


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
    page = to_copy_page(
        xhs,
        alt_titles=["备选钩子一", "测试标题 <1>", ""],
        pinned_comment="只选一边：甲还是乙？",
    )
    push_html = to_push_html(
        sample_digest, cards=["card_00_cover.png"], xhs_text=xhs
    )

    assert "复制标题" in page and "复制正文" in page
    assert "测试标题 &lt;1&gt;" in page
    assert "正文第一行" in page
    # V1 §3.1：备选标题可复制；与主标题重复或为空的候选不重复展示
    assert "备选标题 2" in page and "备选钩子一" in page
    assert "备选标题 3" not in page
    assert "复制评论" in page and "只选一边：甲还是乙？" in page
    assert "copy.html" in push_html
    assert "robertyang87.github.io/tennislive" in push_html
    assert "分别复制标题 / 正文 / 置顶评论" in push_html
    assert "测试标题 &lt;1&gt;" in push_html
    assert "正文第一行" in push_html
    assert push_html.index("card_00_cover.png") < push_html.index("正文第一行")


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
        assert Path(p).stat().st_size > 10_000  # 是实际渲染的图片而非空文件
    names = [p.name for p in paths]
    # 有爆点时大字报钩子卡是第一张（card_00_hook），设计版封面顺延
    assert any("_cover.jpg" in n for n in names)
    assert not any("focus" in name for name in names)
    assert not any("upset" in name or "end" in name for name in names)


def test_social_card_output_uses_high_quality_compact_jpeg(tmp_path):
    from PIL import Image, ImageDraw

    from tennislive.render.image_output import save_social_image

    image = Image.effect_noise((640, 480), 32).convert("RGB")
    ImageDraw.Draw(image).text((24, 24), "TENNIS 7-6 6-4", fill="white")
    lossless = tmp_path / "source.png"
    image.save(lossless, "PNG")

    output = save_social_image(image, tmp_path / "card")

    assert output.suffix == ".jpg"
    assert output.stat().st_size < lossless.stat().st_size
    with Image.open(output) as rendered:
        assert rendered.format == "JPEG"
        assert rendered.size == image.size
        assert not rendered.info.get("progressive")


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
    sample_digest.schedule.append(
        make_match(
            status=MatchStatus.SCHEDULED,
            winner=None,
            sets=(),
            tiebreaks=(),
            match_id="fallback-second-scheduled",
        )
    )

    paths = cards.generate_cards(sample_digest, tmp_path / "cards")
    assert len(paths) >= 3
    names = [p.name for p in paths]
    assert "card_00_cover.jpg" in names
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

    # 次日仍在冷却期：换讲冷知识兜底，不重复也不留白；冷却期满恢复赛事优先
    # （同日重跑不换卡，见 test_story_pick_is_idempotent_within_same_day）
    next_day = Digest(today=date(2026, 7, 18), results=[match])
    second = tournament_story.pick_tournament_story(next_day)
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


def test_relevant_news_alone_surfaces_a_candidate_topic(tmp_path, monkeypatch):
    """News untethered to any scheduled match still lifts its knowledge topic.

    '相关新闻本身也是热点': a rule/record/retirement headline in the global
    trend pool should raise its topic above the bare viral prior even on a day
    with no matching match on the schedule, and outrank a higher-prior
    evergreen that has no news behind it.
    """
    from tennislive.render import tournament_story
    from tennislive.render.tournament_story import (
        _TRIVIA_VIRAL_PRIOR,
        _trivia_topic_score,
        find_story_by_slug,
        tournament_story_candidates,
    )

    monkeypatch.setattr(
        tournament_story, "STATE_PATH", tmp_path / "story_state.json"
    )
    hawkeye = find_story_by_slug("hawkeye")
    prior = _TRIVIA_VIRAL_PRIOR["hawkeye"]

    quiet = Digest(today=date(2026, 7, 24))
    assert _trivia_topic_score(hawkeye, quiet) == prior  # no news, no matches

    news_day = Digest(
        today=date(2026, 7, 24),
        trend_signals=[
            {
                "kind": "official-news",
                "source": "ATP Tour",
                "title": (
                    "Electronic line calling replaces line judges "
                    "at every tour event"
                ),
            }
        ],
    )
    assert _trivia_topic_score(hawkeye, news_day) > prior
    # Even though longest-match (prior 10) outranks hawkeye on a quiet day,
    # the news-hot topic wins when news backs it and nothing backs the rest.
    trivia = [s for s in tournament_story_candidates(news_day) if s.kind == "trivia"]
    assert trivia and trivia[0].slug == "hawkeye"


def test_trend_radar_exposes_full_signal_pool_including_unmatched_news():
    """apply_trend_signals returns every fetched signal, matched or not."""
    from tennislive.research.trends import TrendSignal, apply_trend_signals

    unmatched = TrendSignal(
        kind="official-news",
        source="WTA",
        title="Some off-court tennis headline",
        url="https://wtatennis.com/news/x",
        published_at="2026-07-24T00:00:00+00:00",
    )

    result = apply_trend_signals([], signals=[unmatched])

    assert result.signals == 1
    assert result.matched_matches == 0
    assert [s["title"] for s in result.all_signals] == [
        "Some off-court tennis headline"
    ]


def test_all_story_fact_roles_are_valid_marker_roles():
    """Every story's declared fact role must resolve to a real marker.

    A typo like ``fact_roles=("record", ...)`` where ``record`` isn't a known
    role would raise ``ValueError`` the moment that page renders. This guards
    the whole STORIES table so a bad role can never ship again.
    """
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import _semantic_marker_for_text

    for story in STORIES:
        for index, role in enumerate(story.fact_roles):
            if not role:
                continue
            # Must not raise for any real story beat text.
            _semantic_marker_for_text(
                "示例事实文本", index, story_kind=story.kind, role=role
            )


def test_knowledge_card_facts_never_hard_truncate_mid_clause():
    """Card copy must break on a clause boundary, never slice a clause in half.

    A mid-clause slice silently drops the fact's tail — often the punch-line
    number — and fakes a full stop that evades the copy validator. This guards
    every STORY so an over-budget fact can't quietly ship a chopped card; the
    fix for a failure is to tighten the fact, not to widen the card.
    """
    from tennislive.render import webcards
    from tennislive.render.tournament_story import STORIES

    marks = webcards._CLAUSE_MARKS

    def hard_cut(text: str, limit: int) -> bool:
        clean = " ".join(text.split())
        if len(clean) <= limit:
            return False
        window = clean[: limit + 1]
        cut = max(window.rfind(mark) for mark in marks)
        if cut >= max(16, limit // 2):
            return False
        return not [
            pos
            for mark in marks
            if 0 <= (pos := clean.find(mark, limit)) <= limit + 16
        ]

    # Per-page card limits (see webcards._knowledge_* body builders).
    fact_limit = {"player": 38, "tournament": 42, "trivia": 40}
    offenders: list[str] = []
    for story in STORIES:
        # golden-slam swaps in its own explainer facts, so its raw facts
        # never reach a card — exclude them from the fact check.
        if story.slug != "golden-slam":
            limit = fact_limit.get(story.kind, 40)
            for index, fact in enumerate(story.facts):
                if hard_cut(fact, limit):
                    offenders.append(f"{story.slug} fact[{index}]@{limit}")
        if hard_cut(story.hero_fact, 62):
            offenders.append(f"{story.slug} hero_fact@62")
        for index, moment in enumerate(story.moments):
            if index < 2 and hard_cut(moment.detail, 50):
                offenders.append(f"{story.slug} moment[{index}].detail@50")
            if index == len(story.moments) - 1 and hard_cut(moment.detail, 48):
                offenders.append(f"{story.slug} moment[{index}].detail@48")
    assert offenders == [], f"card copy hard-truncates mid-clause: {offenders}"


def test_adhoc_knowledge_marker_gates_daily_but_never_adhoc(tmp_path, monkeypatch):
    """Ad-hoc marks today's knowledge slot; the daily flow reads it, ad-hoc doesn't."""
    from tennislive.render import tournament_story

    monkeypatch.setattr(
        tournament_story, "STATE_PATH", tmp_path / "story_state.json"
    )
    today = date(2026, 7, 24)

    assert tournament_story.adhoc_knowledge_published_on(today) is False

    # A regular cooldown mark must not be mistaken for an ad-hoc publish.
    tournament_story.mark_story_used("big-three", today)
    assert tournament_story.adhoc_knowledge_published_on(today) is False

    tournament_story.mark_adhoc_knowledge_published(today)
    assert tournament_story.adhoc_knowledge_published_on(today) is True
    # Only today is claimed; a different day is still open.
    assert tournament_story.adhoc_knowledge_published_on(date(2026, 7, 25)) is False
    # The reserved marker coexists with the slug cooldown, not clobbering it.
    assert tournament_story._load_state().get("big-three") == today.isoformat()


def test_trivia_candidates_follow_live_topic_then_viral_prior(tmp_path, monkeypatch):
    from tennislive.render import tournament_story

    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    match = make_match(
        tournament="Some Unknown Cup",
        home_name="Player One",
        away_name="Player Two",
    )

    evergreen = tournament_story.tournament_story_candidates(
        Digest(today=date(2026, 7, 23), results=[match])
    )
    assert next(story for story in evergreen if story.kind == "trivia").slug == "longest-match"

    match.media_heat = 30
    match.search_heat = 25
    match.trend_signals = [
        {
            "kind": "official-news",
            "source": "Wimbledon",
            "title": "Electronic line calling and Hawk-Eye explained",
        },
        {
            "kind": "search-trend",
            "source": "Google Trends",
            "title": "Hawk-Eye tennis",
        },
    ]
    topical = tournament_story.tournament_story_candidates(
        Digest(today=date(2026, 7, 23), results=[match])
    )
    assert next(story for story in topical if story.kind == "trivia").slug == "hawkeye"


def test_trivia_topic_score_recognises_chinese_player_without_text_signal():
    from tennislive.render import tournament_story

    match = make_match(
        tournament="Some Unknown Cup",
        home_name="Zheng Qinwen",
        away_name="Player Two",
    )
    match.home[0].country = "CHN"
    match.search_heat = 20
    digest = Digest(today=date(2026, 7, 23), results=[match])
    china = next(story for story in tournament_story.STORIES if story.slug == "china-tennis")
    longest = next(
        story for story in tournament_story.STORIES if story.slug == "longest-match"
    )

    assert tournament_story._trivia_topic_score(
        china, digest
    ) > tournament_story._trivia_topic_score(longest, digest)


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

    # workflow 重试不会把同一天同一场比赛重复计数
    tournament_story.record_story_wishlist(digest)
    wishlist = json.loads((tmp_path / "story_wishlist.json").read_text("utf-8"))
    assert wishlist["flavio cobolli"]["hits"] == 1
    assert len(wishlist["flavio cobolli"]["evidence"]) == 1

    # 旧版已经产生的重复记录也会在下一次运行时归一化
    entry = wishlist["flavio cobolli"]
    entry["hits"] = 3
    entry["evidence"] *= 3
    (tmp_path / "story_wishlist.json").write_text(
        json.dumps(wishlist, ensure_ascii=False), encoding="utf-8"
    )
    tournament_story.record_story_wishlist(digest)
    repaired = json.loads((tmp_path / "story_wishlist.json").read_text("utf-8"))
    assert repaired["flavio cobolli"]["hits"] == 1
    assert len(repaired["flavio cobolli"]["evidence"]) == 1


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


def test_single_cover_no_hook_page(tmp_path, sample_digest):
    """V1 唯一封面：卡组不再输出钩子页，封面有且只有一张（P0 规则测试）."""
    from tennislive.render.cards import generate_cards

    names = [p.name for p in generate_cards(sample_digest, tmp_path / "cards")]
    assert sum("_cover.jpg" in n for n in names) == 1
    assert not any("hook" in n for n in names)
    assert names[0] == "card_00_cover.jpg"


def test_daily_deck_keeps_result_pages_before_optional_pages(sample_digest, monkeypatch):
    from copy import deepcopy

    from tennislive.render import webcards
    from tennislive.render.titles import daily_lead_match
    from tennislive.sources.rankings import Rankings

    digest = deepcopy(sample_digest)
    digest.today = date(2026, 7, 20)  # 周一，同时触发排名页
    digest.schedule.append(
        make_match(
            status=MatchStatus.SCHEDULED,
            winner=None,
            sets=(),
            tiebreaks=(),
            match_id="second-scheduled",
        )
    )
    digest.results.extend(
        make_match(
            home_name=f"Player {index}",
            away_name=f"Opponent {index}",
            match_id=f"extra-{index}",
        )
        for index in range(6)
    )
    lead = daily_lead_match(digest)
    assert lead is not None
    lead.stats = MatchStats(
        source="licensed-test",
        total_points_won=StatPair(80, 70),
    )
    digest.rankings = Rankings()
    monkeypatch.setattr(
        webcards, "_screenshot_pages", lambda pages, _theme: pages
    )

    pages = webcards.generate_deck(digest, "07.20 · 周一")
    kinds = [kind for kind, _body in pages]
    assert len(kinds) == 7
    assert kinds.count("cover") == 1
    assert kinds[1] == "lead"
    assert "focus" in kinds
    assert "scoreboard" in kinds and "results2" in kinds


def test_daily_deck_skips_unrelated_story_and_excludes_lead_from_scoreboard(
    sample_digest, monkeypatch
):
    from tennislive.render import webcards
    from tennislive.render.titles import daily_lead_match

    scoreboard_match_ids: list[str] = []
    original_scoreboard = webcards.scoreboard_body

    def capture_scoreboard(matches, *args, **kwargs):
        scoreboard_match_ids.extend(match.match_id for match in matches)
        return original_scoreboard(matches, *args, **kwargs)

    monkeypatch.setattr(webcards, "scoreboard_body", capture_scoreboard)
    monkeypatch.setattr(
        webcards, "_screenshot_pages", lambda pages, _theme: pages
    )

    pages = webcards.generate_deck(sample_digest, "07.16 · 周四")
    kinds = [kind for kind, _body in pages]
    assert kinds[:2] == ["cover", "lead"]
    assert "story" not in kinds

    lead = daily_lead_match(sample_digest)
    assert lead is not None and lead.match_id not in scoreboard_match_ids


def test_profile_pack_has_ready_to_use_assets(tmp_path):
    from PIL import Image

    from tennislive.render.profile import generate_profile_pack

    paths = generate_profile_pack(tmp_path / "profile")
    assert {path.name for path in paths} == {
        "bio.txt", "pinned_plan.md", "background.png"
    }
    assert "一觉醒来" in (tmp_path / "profile" / "bio.txt").read_text("utf-8")
    with Image.open(tmp_path / "profile" / "background.png") as image:
        assert image.size == (1080, 720)


def test_historical_context_turns_profile_facts_into_human_background():
    from tennislive.render.context import historical_context

    match = make_match(
        home_name="Stefanos Tsitsipas",
        away_name="Alexander Shevchenko",
        home_country="GRE",
        away_country="KAZ",
        round_name="Final",
    )
    match.home[0].rank = 85

    context = historical_context(match, date(2026, 7, 20))

    assert context is not None
    assert "两进大满贯决赛" in context.summary
    assert "比分只是故事的新一页" in context.summary
    assert "世界第85" not in context.summary
    assert ("世界第3", "生涯最高") in context.facts
    assert context.source_url.startswith("https://www.atptour.com/")


def test_historical_context_uses_curated_player_origin_story():
    from tennislive.render.context import historical_context

    match = make_match(
        home_name="Qinwen Zheng",
        away_name="Player Two",
        home_country="CHN",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )

    context = historical_context(match, date(2026, 7, 20))

    assert context is not None
    assert "李娜" in context.summary and "奥运金牌" in context.summary
    assert context.source_url


def test_editorial_memory_connects_a_players_next_appearance(tmp_path, monkeypatch):
    from tennislive.render import editorial_memory
    from tennislive.render.context import historical_context

    monkeypatch.setattr(
        editorial_memory, "STATE_PATH", tmp_path / "editorial_memory.json"
    )
    past = make_match(
        home_name="Alex Example",
        away_name="Player Two",
        match_id="past-match",
    )
    editorial_memory.record_daily_lead(
        Digest(today=date(2026, 7, 19), results=[past])
    )
    upcoming = make_match(
        home_name="Alex Example",
        away_name="Player Three",
        match_id="next-match",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )

    context = historical_context(upcoming, date(2026, 7, 20))

    assert context is not None
    assert "7月19日" in context.summary
    assert "下一章" in context.summary
    assert context.source_label == "网球时差历史内容记录"


def test_meaning_whitelist_downgrades_without_evidence():
    """意义句白名单：证据不足降级为结果句；退赛/爆冷/逆转可机械验证."""
    from tennislive.models import MatchStatus
    from tennislive.render.titles import _whitelist_meaning, cover_result_hook

    plain = make_match(
        home_name="Player One", away_name="Player Two",
        sets=((6, 4), (6, 3)), tiebreaks=(),
    )
    assert _whitelist_meaning(plain) is None  # 干净直落两盘：无意义句可证
    main, _ = cover_result_hook(plain)
    assert "晋级" in main  # 降级为准确结果句

    retired = make_match(
        home_name="Player One", away_name="Player Two",
        status=MatchStatus.RETIRED,
    )
    line = _whitelist_meaning(retired)
    assert line is not None and "退赛" in line
    assert "伤" not in line  # 不得推断退赛原因

    comeback = make_match(
        home_name="Player One", away_name="Player Two",
        sets=((4, 6), (6, 3), (6, 4)), tiebreaks=(),
    )
    assert "逆转" in (_whitelist_meaning(comeback) or "")


def test_deciding_set_requires_level_score_before_last_set():
    from tennislive.render.rating import deciding_set_tiebreak, went_to_deciding_set
    from tennislive.render.titles import _whitelist_meaning

    straight_sets = make_match(
        sets=((6, 4), (6, 4), (7, 6)),
        tiebreaks=(None, None, (7, 5)),
    )
    assert not went_to_deciding_set(straight_sets)
    assert deciding_set_tiebreak(straight_sets) is None
    assert "决胜盘" not in (_whitelist_meaning(straight_sets) or "")

    three_setter = make_match(
        sets=((6, 4), (4, 6), (7, 6)),
        tiebreaks=(None, None, (10, 8)),
    )
    assert went_to_deciding_set(three_setter)
    assert deciding_set_tiebreak(three_setter) == "抢七"
    assert "决胜盘抢七" in (_whitelist_meaning(three_setter) or "")

    five_setter = make_match(
        sets=((6, 4), (4, 6), (6, 3), (3, 6), (1, 0)),
        tiebreaks=(None, None, None, None, None),
    )
    assert went_to_deciding_set(five_setter)
    assert deciding_set_tiebreak(five_setter) == "抢十"


def test_meaning_whitelist_bo5_straight_sets_is_not_deciding_set():
    """五盘制 3-0（末盘抢七）没有决胜盘，不得声称"决胜盘抢七"."""
    from tennislive.render.titles import _whitelist_meaning

    sweep = make_match(
        home_name="Player One", away_name="Player Two",
        sets=((7, 6), (6, 4), (7, 6)), tiebreaks=((7, 3), None, (7, 5)),
    )
    assert _whitelist_meaning(sweep) is None

    # 真正打满决胜盘（3-2）且末盘抢七时仍然生效
    distance = make_match(
        home_name="Player One", away_name="Player Two",
        sets=((6, 4), (4, 6), (6, 4), (4, 6), (7, 6)),
        tiebreaks=(None, None, None, None, (7, 5)),
    )
    line = _whitelist_meaning(distance)
    assert line is not None and "决胜盘抢七" in line


def test_meaning_whitelist_final_says_champion_not_advance():
    """决赛场景措辞：冠军是"夺冠"，不是"晋级"."""
    from tennislive.models import MatchStatus
    from tennislive.render.titles import _whitelist_meaning

    retired_final = make_match(
        home_name="Player One", away_name="Player Two",
        round_name="Final", status=MatchStatus.RETIRED,
    )
    line = _whitelist_meaning(retired_final)
    assert line is not None and "夺冠" in line and "晋级" not in line

    comeback_final = make_match(
        home_name="Player One", away_name="Player Two",
        round_name="Final", sets=((4, 6), (6, 3), (6, 4)), tiebreaks=(),
    )
    assert "逆转夺冠" in (_whitelist_meaning(comeback_final) or "")


def test_title_layer_has_no_cn_bypass():
    """V1 §2.2 也约束标题候选层：常规中国胜场不压过大满贯决赛头条."""
    from tennislive.render.titles import title_candidates

    routine_cn = make_match(
        tournament="Prague Open", round_name="Round of 32",
        home_name="Qinwen Zheng", home_country="CHN",
        away_name="Player Two", away_country="USA", match_id="cn-r32",
    )
    routine_cn.tournament.level = "WTA250"
    routine_cn.home[0].seed = routine_cn.away[0].seed = None
    slam_final = make_match(
        tournament="Wimbledon", round_name="Final", match_id="gs-final",
    )
    slam_final.tournament.level = "GS"
    digest = Digest(
        today=date(2026, 7, 17), results=[routine_cn, slam_final], schedule=[]
    )
    cands = title_candidates(digest)
    assert "郑钦文" not in cands[0]  # 头条是大满贯决赛，不是常规中国胜场
    assert any("郑钦文" in c for c in cands)  # 中国角度仍在三候选之内


def test_china_weight_is_fixed_35_no_bypass():
    """中国相关性固定 +35（与爆冷同级），无"永远第一"旁路."""
    from tennislive.render.rating import match_score

    cn = make_match(home_name="Qinwen Zheng", home_country="CHN",
                    away_name="Player Two", away_country="USA")
    non = make_match(home_name="Player One", home_country="ITA",
                     away_name="Player Two", away_country="USA")
    assert match_score(cn) - match_score(non) == 35

    # 常规轮次的中国比赛不应压过大满贯决赛（旁路已删）
    slam_final = make_match(
        tournament="Wimbledon", round_name="Final",
        home_name="Player One", away_name="Player Two", match_id="f",
    )
    slam_final.tournament.level = "GS"
    routine_cn = make_match(
        tournament="Swiss Open", round_name="Round of 32",
        home_name="Qinwen Zheng", home_country="CHN",
        away_name="Player Two", match_id="r32",
    )
    routine_cn.tournament.level = "ATP250"
    assert match_score(slam_final) > match_score(routine_cn)


def test_cover_title_and_post_share_one_headliner():
    """封面、候选标题和小红书正文必须使用同一个 V1 头条选择器。"""
    import re

    from tennislive.render.titles import daily_lead_match, title_candidates
    from tennislive.render.webcards import cover_body
    from tennislive.render.xiaohongshu import build_post_plan, post_title

    slam_final = make_match(
        tournament="Wimbledon", round_name="Final",
        home_name="Jannik Sinner", away_name="Novak Djokovic", match_id="slam",
    )
    slam_final.tournament.level = "GS"
    routine_cn = make_match(
        tournament="Swiss Open", round_name="Round of 32",
        home_name="Qinwen Zheng", home_country="CHN",
        away_name="Player Two", match_id="routine-cn",
    )
    routine_cn.tournament.level = "WTA250"
    digest = Digest(
        today=date(2026, 7, 20), results=[slam_final, routine_cn]
    )

    assert daily_lead_match(digest) is slam_final
    assert build_post_plan(digest).lead_match_id == slam_final.match_id
    assert "辛纳" in title_candidates(digest)[0]
    assert "辛纳" in post_title(digest)
    body = cover_body(digest, *title_candidates(digest)[:2], "07.20")
    assert "辛纳" in re.search(r'class="focus">(.*?)</div>', body).group(1)


def test_cover_headline_breaks_after_balanced_punctuation_and_keeps_last_two_glyphs():
    from tennislive.render.webcards import _cover_headline_html

    rendered = _cover_headline_html("时隔16个月，西西帕斯再夺冠")

    assert rendered.count('class="headline-line"') == 2
    assert re.sub(r"<[^>]+>", "", rendered) == "时隔16个月，西西帕斯再夺冠"
    assert "，</span></span><span class=\"headline-line\">西西帕斯" in rendered
    assert '<span class="headline-keep headline-tail">夺冠</span>' in rendered


def test_cover_headline_without_punctuation_still_prevents_a_one_character_tail():
    from tennislive.render.webcards import _cover_headline_html

    rendered = _cover_headline_html("这一场胜利让所有人重新记住郑钦文")

    assert rendered.count('class="headline-line"') == 1
    assert '<span class="headline-keep headline-tail">钦文</span>' in rendered


def test_cover_headline_keeps_brackets_and_closing_punctuation_with_text_and_escapes_html():
    from tennislive.render.webcards import _cover_headline_html

    rendered = _cover_headline_html("这一场（决赛）谁能赢？<")

    assert '<span class="headline-keep">（决</span>' in rendered
    assert '<span class="headline-keep">赛）</span>' in rendered
    assert "&lt;" in rendered
    assert "<script" not in rendered


def test_cover_applies_china_weight_instead_of_input_order():
    import re

    from tennislive.render.titles import cover_highlights, daily_lead_match
    from tennislive.render.webcards import cover_body

    global_match = make_match(
        home_name="Jannik Sinner", away_name="Novak Djokovic", match_id="global"
    )
    chinese_match = make_match(
        home_name="Qinwen Zheng", home_country="CHN",
        away_name="Aryna Sabalenka", away_country="BLR", match_id="china",
    )
    digest = Digest(
        today=date(2026, 7, 20), results=[global_match, chinese_match]
    )

    assert daily_lead_match(digest) is chinese_match
    body = cover_body(digest, *cover_highlights(digest), "07.20")
    assert "郑钦文" in re.search(r'class="focus">(.*?)</div>', body).group(1)


def test_cover_china_focus_uses_chinese_outcome_instead_of_full_score():
    from tennislive.render.webcards import cover_body

    lead = make_match(match_id="lead")
    chinese_final = make_match(
        home_name="Player One",
        away_name="Qinwen Zheng",
        away_country="CHN",
        winner=0,
        round_name="Final",
        match_id="china-final",
    )
    digest = Digest(today=date(2026, 7, 20), results=[lead, chinese_final])

    body = cover_body(digest, "今日头条", "可靠副标题", "7.20 · 周一")

    assert "郑钦文 止步男单决赛" in body
    assert "郑钦文 6-4" not in body

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


def test_decorated_title_date_emoji_and_budget():
    """发布标题带日期与内容匹配的 emoji，且不超过小红书 20 字预算."""
    from tennislive.render.xiaohongshu import decorate_title, xhs_title_len

    digest = Digest(today=date(2026, 7, 20))
    champion = decorate_title(digest, "时隔16个月，西西帕斯再夺冠")
    assert champion == "🏆7.20｜时隔16个月，西西帕斯再夺冠"
    assert xhs_title_len(champion) <= 20

    assert decorate_title(digest, "爆冷：黑马掀翻头号种子").startswith("💥")
    assert decorate_title(digest, "袁悦今日出战").startswith("🔥")
    assert decorate_title(digest, "每日赛程赛果速览").startswith("🎾")

    # 超预算的钩子改写成完整短句，不发布半句话或省略号。
    long_hook = "这是一个非常非常长的钩子标题肯定放不下二十个字"
    trimmed = decorate_title(digest, long_hook)
    assert "…" not in trimmed and "..." not in trimmed
    assert xhs_title_len(trimmed) <= 20


def test_story_pick_is_idempotent_within_same_day(tmp_path, monkeypatch):
    """同日重跑不换卡：当天已定的故事在重新生成时被直接复用."""
    from dataclasses import replace

    from tennislive.render import tournament_story

    monkeypatch.setattr(tournament_story, "STATE_PATH", tmp_path / "story_state.json")
    fake_img = tmp_path / "img.jpg"
    fake_img.write_bytes(b"\xff\xd8fake")
    monkeypatch.setattr(
        tournament_story,
        "STORIES",
        tuple(replace(s, image=fake_img) for s in tournament_story.STORIES),
    )

    won = make_match(
        tournament="Plava Laguna Croatia Open Umag",
        home_name="Qinwen Zheng",
        away_name="Player Two",
        winner=0,
    )
    digest = Digest(today=date(2026, 7, 18), results=[won])
    first = tournament_story.pick_tournament_story(digest)
    assert first is not None
    tournament_story.mark_story_used(first.slug, digest.today)
    again = tournament_story.pick_tournament_story(digest)
    assert again is not None and again.slug == first.slug


def test_player_story_card_uses_spotlight_branding(tmp_path):
    from dataclasses import replace

    from tennislive.render import webcards
    from tennislive.render.tournament_story import STORIES

    story = next(s for s in STORIES if s.kind == "player")
    fake_img = tmp_path / "player.jpg"
    fake_img.write_bytes(b"\xff\xd8fake")
    body = webcards.tournament_story_body(replace(story, image=fake_img), "07.18 星期六")

    assert "球员特写" in body and "赛事档案" not in body
    assert story.source_label not in body
    assert story.source_url.startswith("https://")


def test_story_card_uses_spacious_single_flow(tmp_path):
    from dataclasses import replace

    from tennislive.render import webcards
    from tennislive.render.tournament_story import STORIES

    story = next(s for s in STORIES if s.slug == "yellow-ball")
    fake_img = tmp_path / "story.jpg"
    fake_img.write_bytes(b"\xff\xd8fake")
    body = webcards.tournament_story_body(
        replace(story, image=fake_img), "07.20 · 周一"
    )

    assert "story-meta" not in body
    assert "story-timeline" not in body
    assert body.count('class="story-copy"') == 3
    assert body.count("<li>") == 3
    assert "1972" in body and "1986" in body
    assert "为什么会改变" in body
    assert body.count("网球有故事") == 2
    assert "网球冷知识" not in body


def test_knowledge_package_is_standalone_post(tmp_path, sample_digest, monkeypatch):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render import knowledge
    from tennislive.render.tournament_story import STORIES

    fake_img = tmp_path / "story.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(next(s for s in STORIES if s.slug == "umag"), image=fake_img)
    monkeypatch.setenv("TENNISLIVE_VISUAL_FETCH", "off")
    monkeypatch.setenv("TENNISLIVE_VISUAL_STRICT", "off")
    monkeypatch.setattr(
        knowledge,
        "_screenshot_pages",
        lambda pages, _theme: [
            (kind, Image.new("RGB", (1080, 1440), "black"))
            for kind, _body in pages
        ],
    )

    selected = knowledge.generate_knowledge_package(
        sample_digest,
        tmp_path / "knowledge",
        story=story,
    )

    assert selected is story
    card_names = (
        "card_00_knowledge.jpg",
        "card_01_story.jpg",
        "card_02_explainer.jpg",
        "card_03_today.jpg",
    )
    assert all(
        (tmp_path / "knowledge" / "cards" / card_name).exists()
        for card_name in card_names
    )
    xhs = (tmp_path / "knowledge" / "xiaohongshu.txt").read_text("utf-8")
    push = (tmp_path / "knowledge" / "push.html").read_text("utf-8")
    copy = (tmp_path / "knowledge" / "copy.html").read_text("utf-8")
    pinned = (tmp_path / "knowledge" / "pinned_comment.txt").read_text("utf-8")
    assert xhs.startswith("📖")
    assert any(label in xhs for label in ("🎬", "⚡", "👤", "🔎", "🕰️"))
    assert "先猜" not in xhs and "记住这3点" not in xhs
    assert "💬 " in xhs
    assert "今天单独讲一个网球知识点" not in xhs
    assert story.hero_fact in xhs
    assert story.source_label not in xhs
    assert all(f"/knowledge/cards/{card_name}" in push for card_name in card_names)
    assert push.count("<img ") == 4
    assert "第1张未显示？点此打开原图" in push
    assert 'referrerpolicy="no-referrer"' in push
    assert "/knowledge/copy.html" in push
    assert "分别复制标题 / 正文 / 置顶评论" in push
    assert "记住这3点" not in push
    assert pinned in copy
    story_data = __import__("json").loads(
        (tmp_path / "knowledge" / "story.json").read_text("utf-8")
    )
    evidence = __import__("json").loads(
        (tmp_path / "knowledge" / "evidence.json").read_text("utf-8")
    )
    visual_qa = __import__("json").loads(
        (tmp_path / "knowledge" / "visual_qa.json").read_text("utf-8")
    )
    assert story_data["card_count"] == 4
    assert evidence["story_slug"] == story.slug
    assert evidence["claims"] and evidence["sources"]
    visual_sources = __import__("json").loads(
        (tmp_path / "knowledge" / "visual_sources.json").read_text("utf-8")
    )
    assert visual_qa["status"] == "pass"
    assert visual_qa["photo_uses"] == 1
    assert len(visual_qa["rendered_cards"]) == 4
    assert visual_sources["status"] == "pass"
    assert not (tmp_path / "knowledge" / "visuals").exists()


def test_knowledge_adhoc_push_links_point_at_its_own_output_dir(
    tmp_path, sample_digest, monkeypatch
):
    """An ad-hoc post's push.html must reference its own cards/copy page.

    A hardcoded "knowledge" segment here would silently point every
    knowledge-adhoc push at whatever story the same-day daily digest wrote
    to output/<date>/knowledge/ instead of the story actually being pushed.
    """
    from dataclasses import replace

    from PIL import Image

    from tennislive.render import knowledge
    from tennislive.render.tournament_story import STORIES

    fake_img = tmp_path / "story.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(next(s for s in STORIES if s.slug == "umag"), image=fake_img)
    monkeypatch.setenv("TENNISLIVE_VISUAL_FETCH", "off")
    monkeypatch.setenv("TENNISLIVE_VISUAL_STRICT", "off")
    monkeypatch.setattr(
        knowledge,
        "_screenshot_pages",
        lambda pages, _theme: [
            (kind, Image.new("RGB", (1080, 1440), "black"))
            for kind, _body in pages
        ],
    )

    # A same-day daily digest post already sitting in the sibling
    # "knowledge" directory, with the same card filenames but different
    # (wrong, if ever referenced by the adhoc push) content.
    sibling = tmp_path / "knowledge" / "cards"
    sibling.mkdir(parents=True)
    for card_name in (
        "card_00_knowledge.jpg",
        "card_01_story.jpg",
        "card_02_explainer.jpg",
        "card_03_today.jpg",
    ):
        Image.new("RGB", (1080, 1440), "red").save(sibling / card_name)

    knowledge.generate_knowledge_package(
        sample_digest,
        tmp_path / "knowledge_adhoc",
        story=story,
    )

    push = (tmp_path / "knowledge_adhoc" / "push.html").read_text("utf-8")
    assert "/knowledge_adhoc/cards/card_00_knowledge.jpg" in push
    assert "/knowledge_adhoc/copy.html" in push
    assert "/knowledge/cards/" not in push
    assert "/knowledge/copy.html" not in push


def test_knowledge_deck_uses_one_verified_photo_and_structured_inner_pages(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.knowledge_visual_qa import evaluate_knowledge_visuals
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    fake_img = tmp_path / "alcaraz.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(next(s for s in STORIES if s.slug == "alcaraz"), image=fake_img)
    bodies = knowledge_deck_bodies(
        story,
        "07.21 · 周二",
        question="你第一次记住他，是哪一场球？",
        year=2026,
    )

    import re

    assert sum(
        len(re.findall(r'data-photo-source="[^"]+"', body))
        for _kind, body in bodies
    ) == 1
    assert 'class="knowledge-cover-bg"' in bodies[0][1]
    assert "--knowledge-cover-focus:50% 22%" in bodies[0][1]
    assert 'class="knowledge-photo' not in bodies[0][1]
    assert 'data-visual="narrative-timeline"' in bodies[1][1]
    assert 'data-visual="player-explainer"' in bodies[2][1]
    assert 'data-visual="history-timeline"' in bodies[3][1]
    assert evaluate_knowledge_visuals(story, bodies)["status"] == "pass"


def test_public_cards_and_copy_hide_source_credits_but_evidence_keeps_urls(sample_digest):
    from tennislive.render.knowledge import _knowledge_evidence, knowledge_copy
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import cover_body, knowledge_deck_bodies

    story = next(item for item in STORIES if item.slug == "golden-slam")
    cover = cover_body(
        sample_digest,
        "时隔16个月，西西帕斯再夺冠",
        "把这一夜留在记忆里",
        "07.16 · 周四",
        cover_visual={
            "path": story.image,
            "credit": "Example Photographer",
            "license": "非商业资料引用",
            "source_url": "https://example.com/photo",
        },
    )
    deck = knowledge_deck_bodies(
        story,
        "07.16 · 周四",
        question="金满贯和世界第一，你觉得哪个更难？",
        year=2026,
    )
    public_outputs = [
        cover,
        *(body for _kind, body in deck),
        knowledge_copy(story, sample_digest),
        to_markdown(sample_digest),
        to_html(sample_digest),
        to_post(sample_digest),
    ]
    forbidden = (
        "摄影/图源",
        "图源：",
        "来源：",
        "资料｜",
        "资料：",
        "资料核对",
        "非商业资料引用",
        "官方资料 ↗",
        "赛事官方历史",
    )

    assert all(
        marker not in output for output in public_outputs for marker in forbidden
    )
    evidence = _knowledge_evidence(story, sample_digest)
    assert evidence["sources"]
    assert all(url.startswith("https://") for url in evidence["sources"])


def test_visual_qa_rejects_internal_generation_labels(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.knowledge_visual_qa import evaluate_knowledge_visuals
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    fake_img = tmp_path / "story.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(next(s for s in STORIES if s.slug == "umag"), image=fake_img)
    bodies = knowledge_deck_bodies(
        story,
        "07.21 · 周二",
        question="你最想去现场看哪一场？",
        year=2026,
    )
    bodies[2] = (bodies[2][0], bodies[2][1].replace("</div>", "程序生成信息图</div>", 1))

    report = evaluate_knowledge_visuals(story, bodies)

    assert report["status"] == "fail"
    assert any("生产描述：程序生成" in error for error in report["errors"])


def test_visual_qa_rejects_reused_inner_page_photo(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.knowledge_visual_qa import evaluate_knowledge_visuals
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    fake_img = tmp_path / "story.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(next(s for s in STORIES if s.slug == "umag"), image=fake_img)
    bodies = knowledge_deck_bodies(
        story,
        "07.21 · 周二",
        question="你最想见证谁的第一冠？",
        year=2026,
    )
    duplicated = list(bodies)
    source = story.image_source_url
    duplicated[1] = (
        "story",
        duplicated[1][1].replace(
            'data-visual="narrative-timeline"',
            'data-visual="narrative-timeline"><div class="knowledge-photo" '
            f'data-photo-source="{source}"',
            1,
        ),
    )

    report = evaluate_knowledge_visuals(story, duplicated)
    assert report["status"] == "fail"
    assert any("重复使用" in error for error in report["errors"])


def test_knowledge_deck_accepts_three_distinct_licensed_page_photos(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.knowledge_visual_qa import evaluate_knowledge_visuals
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    cover = tmp_path / "cover.jpg"
    Image.new("RGB", (1200, 800), "white").save(cover)
    story = replace(next(s for s in STORIES if s.slug == "umag"), image=cover)
    page_visuals = {}
    for index, page in enumerate(("story", "explainer", "today"), 1):
        path = tmp_path / f"{page}.jpg"
        Image.new("RGB", (1200, 800), (index * 30, 90, 120)).save(path)
        page_visuals[page] = {
            "path": path,
            "source_url": f"https://example.com/{page}",
            "credit": f"Photographer {index}",
            "license": "CC BY-SA 4.0",
            "focus": "50% 30%",
        }

    bodies = knowledge_deck_bodies(
        story,
        "07.21 · 周二",
        question="你最想见证谁的第一冠？",
        year=2026,
        page_visuals=page_visuals,
    )
    report = evaluate_knowledge_visuals(
        story,
        bodies,
        page_visuals=page_visuals,
    )

    assert report["status"] == "pass"
    assert report["photo_uses"] == 4
    assert len(set(report["photo_sources"])) == 4
    assert len(report["resolved_visuals"]) == 3


def test_hawkeye_knowledge_deck_uses_official_process_and_current_scope(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    fake_img = tmp_path / "hawkeye.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(next(s for s in STORIES if s.slug == "hawkeye"), image=fake_img)

    pages = knowledge_deck_bodies(
        story,
        "07.21 · 周二",
        question="四大满贯只剩法网保留人工司线，红土球印足够可靠吗？",
        year=2026,
    )
    kinds = [kind for kind, _body in pages]
    combined = "\n".join(body for _kind, body in pages)

    assert kinds == ["knowledge", "story", "explainer", "today"]
    assert "2D VISION" in combined and "X / Y / Z" in combined
    assert "8–12台" in combined and "最高340fps" in combined
    assert "实时电子司线" in combined and "四大满贯中" in combined
    assert "主裁第一判断" not in combined
    assert "技术没有替比赛做决定" not in combined


def test_longest_match_deck_uses_event_specific_visuals_and_large_facts(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.knowledge_visual_qa import evaluate_knowledge_visuals
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    fake_img = tmp_path / "isner-mahut.jpg"
    Image.new("RGB", (1200, 800), "white").save(fake_img)
    story = replace(
        next(s for s in STORIES if s.slug == "longest-match"),
        image=fake_img,
        image_source_url="https://www.wimbledon.com/en_GB/about/history/2010s",
        image_credit="Wimbledon archive",
        diagram_type="marathon",
    )

    pages = knowledge_deck_bodies(
        story,
        "07.23 · 周四",
        question="如果没有抢十，你愿意再看一场11小时的比赛吗？",
        year=2026,
    )
    combined = "\n".join(body for _kind, body in pages)

    assert [kind for kind, _body in pages] == [
        "knowledge",
        "story",
        "explainer",
        "today",
    ]
    assert 'class="marathon-story-visual"' in pages[1][1]
    assert 'class="marathon-scoreline"' in pages[2][1]
    assert 'class="marathon-records"' in pages[2][1]
    assert 'class="marathon-today-visual"' in pages[3][1]
    assert "6月22日" in combined and "6月24日" in combined
    assert "11:05" in combined and "183" in combined and "216" in combined
    assert "70-68" in combined and "2022" in combined and "10分抢十" in combined
    assert not re.search(r"<(?:i|small)[^>]*>\s*0[1-9]\s*</", combined)
    assert evaluate_knowledge_visuals(story, pages)["status"] == "pass"


def test_hawkeye_publish_validation_rejects_stale_scope(sample_digest):
    from dataclasses import replace

    import pytest

    from tennislive.render.knowledge import _validate_story_for_publish
    from tennislive.render.tournament_story import STORIES

    story = next(s for s in STORIES if s.slug == "hawkeye")
    stale = replace(
        story,
        facts=story.facts[:-1] + ("目前只剩法网仍保留人工司线。",),
    )

    with pytest.raises(ValueError, match="事实校验失败"):
        _validate_story_for_publish(stale, sample_digest)


def test_longest_match_story_uses_official_cross_checked_facts():
    from urllib.parse import urlparse

    from tennislive.render.tournament_story import STORIES

    story = next(s for s in STORIES if s.slug == "longest-match")
    evidence_domains = {urlparse(url).netloc for url in story.evidence_urls}
    all_sources = (
        story.source_url,
        *story.evidence_urls,
        *(moment.source_url for moment in story.moments),
    )
    facts = "\n".join(story.facts)

    assert story.diagram_type == "marathon"
    assert story.hero_marker == "2010"
    assert evidence_domains == {
        "www.wimbledon.com",
        "www.itftennis.com",
        "www.usopen.org",
    }
    assert all("wikipedia.org" not in url for url in all_sources)
    assert "50-50" in facts and "47-47" not in facts
    assert "183 局" in facts and "8 小时 11 分钟" in facts
    assert "113 记 ACE" in facts
    assert "直接催生" not in facts
    assert "领先两分" in facts


def test_story_selection_evidence_records_viral_and_live_signals(sample_digest):
    from tennislive.render.tournament_story import STORIES, story_selection_evidence

    story = next(s for s in STORIES if s.slug == "longest-match")
    evidence = story_selection_evidence(story, sample_digest)

    assert evidence["viral_prior"] == 10.0
    assert evidence["topic_score"] >= evidence["viral_prior"]
    assert evidence["live_relevance_score"] >= 0
    assert "selection_basis" in evidence


def test_knowledge_titles_are_specific_and_fit_xiaohongshu(sample_digest):
    from tennislive.render.knowledge import knowledge_copy, knowledge_title
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.xiaohongshu import xhs_title_len

    titles = {story.slug: knowledge_title(story, sample_digest) for story in STORIES}

    assert all(xhs_title_len(title) <= 20 for title in titles.values())
    assert "很多人会答错" not in "\n".join(titles.values())
    assert "网球有故事｜误判催生网球鹰眼" in titles["hawkeye"]
    assert "的来路" in titles["alcaraz"]

    hawkeye = next(story for story in STORIES if story.slug == "hawkeye")
    post = knowledge_copy(hawkeye, sample_digest)
    assert "🧠 先猜" not in post and "🎾 答案" not in post
    assert "2004｜" in post and "2006｜" in post
    assert not any(marker in post for marker in ("①", "②", "③", "④"))
    assert "2D 视觉处理与 3D 三角测量" in post
    assert "回放动画数秒内生成" not in post
    assert "四大满贯只剩法网保留人工司线" in post
    assert "今天单独讲一个网球知识点" not in post


def test_all_knowledge_stories_use_semantic_markers_without_ordinals(tmp_path):
    from dataclasses import replace

    from PIL import Image

    from tennislive.render.knowledge_visual_qa import evaluate_knowledge_visuals
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    image = tmp_path / "story.jpg"
    Image.new("RGB", (1200, 800), "white").save(image)
    forbidden = ("三道窄门", "三次转折", "三个坐标", "把这件事放回历史")
    for source in STORIES:
        story = replace(
            source,
            image=image,
            image_source_url=f"https://example.com/{source.slug}",
            image_credit="Example archive",
        )
        bodies = knowledge_deck_bodies(
            story,
            "07.22 · 周三",
            question="这段历史里，你最想记住哪个瞬间？",
            year=2026,
        )
        combined = "\n".join(body for _kind, body in bodies)
        assert 'class="semantic-marker' in combined, story.slug
        assert not re.search(r"<(?:i|small)[^>]*>\s*0[1-9]\s*</", combined), story.slug
        assert not any(marker in combined for marker in ("①", "②", "③", "④")), story.slug
        assert not any(phrase in combined for phrase in forbidden), story.slug
        for marker in re.findall(
            r'data-marker-kind="year"[^>]*>.*?<small>([^<]+)</small>',
            combined,
            flags=re.DOTALL,
        ):
            assert re.fullmatch(r"(?:18|19|20)\d{2}", marker), (story.slug, marker)
        assert evaluate_knowledge_visuals(story, bodies)["status"] == "pass", story.slug


def test_semantic_year_marker_keeps_full_year_next_to_chinese_text():
    from tennislive.render.webcards import _semantic_marker_for_text

    marker = _semantic_marker_for_text("1988年的格拉芙夺得奥运金牌", 0)

    assert 'data-marker-kind="year"' in marker
    assert "<small>1988</small>" in marker
    assert "<small>88</small>" not in marker


def test_cover_rejects_abbreviated_year_marker(tmp_path):
    from dataclasses import replace

    import pytest
    from PIL import Image

    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import knowledge_deck_bodies

    image = tmp_path / "story.jpg"
    Image.new("RGB", (1200, 800), "white").save(image)
    story = replace(
        next(story for story in STORIES if story.slug == "golden-slam"),
        image=image,
        hero_marker="88",
    )

    with pytest.raises(ValueError, match="四位年份"):
        knowledge_deck_bodies(
            story,
            "07.22 · 周三",
            question="哪一冠最难？",
            year=2026,
        )


def test_all_knowledge_copy_is_plain_mobile_first_and_not_numbered():
    from tennislive.render.knowledge import (
        _validate_copy_for_publish,
        knowledge_copy,
    )
    from tennislive.render.tournament_story import STORIES

    digest = Digest(today=date(2026, 7, 22))
    for story in STORIES:
        copy = knowledge_copy(story, digest)
        _validate_copy_for_publish(copy)
        assert not any(marker in copy for marker in ("①", "②", "③", "④")), story.slug
        assert "💬" in copy, story.slug
        assert len([part for part in copy.split("\n\n") if part.strip()]) >= 6, story.slug


def test_knowledge_story_openings_vary_by_date_and_story_kind():
    from datetime import timedelta

    from tennislive.render.knowledge import _story_opening
    from tennislive.render.tournament_story import STORIES

    representatives = {
        kind: next(story for story in STORIES if story.kind == kind)
        for kind in ("player", "tournament", "trivia")
    }
    for kind, story in representatives.items():
        labels = {
            _story_opening(
                story,
                Digest(today=date(2026, 7, 22) + timedelta(days=offset)),
            )[0]
            for offset in range(14)
        }
        assert len(labels) >= 3, kind


def test_golden_slam_weak_scoreboard_cover_is_rejected_in_strict_mode(monkeypatch, tmp_path):
    from tennislive.render.tournament_story import STORIES
    from tennislive.research.visual_sources import resolve_story_visuals

    monkeypatch.setenv("TENNISLIVE_VISUAL_STRICT", "on")
    story = next(story for story in STORIES if story.slug == "golden-slam")

    visuals, report = resolve_story_visuals(story, tmp_path / "visuals")

    assert not visuals
    assert report["status"] == "fail"
    assert report["providers_queried"] == []  # cover-first rejection avoids wasted requests
    assert any("封面" in error for error in report["errors"])


def test_golden_slam_cover_uses_graf_1988_as_headline_year():
    from tennislive.render.tournament_story import STORIES
    from tennislive.render.webcards import _knowledge_cover_body

    story = next(story for story in STORIES if story.slug == "golden-slam")
    body = _knowledge_cover_body(story, "7.22 · 周三")

    assert "<b>1988</b>" in body
    assert "<b>1969</b>" not in body


def test_knowledge_copy_rotates_structure_and_bans_quiz_boilerplate(sample_digest):
    from dataclasses import replace
    from datetime import timedelta

    from tennislive.render.knowledge import knowledge_copy
    from tennislive.render.tournament_story import STORIES

    story = next(story for story in STORIES if story.slug == "hawkeye")
    copies = {
        knowledge_copy(story, replace(sample_digest, today=sample_digest.today + timedelta(days=day)))
        for day in range(7)
    }
    combined = "\n".join(copies)

    assert len(copies) >= 3
    assert all(phrase not in combined for phrase in ("先别往下滑", "🧠 先猜", "🎾 答案", "记住这3点"))


def test_knowledge_special_copy_uses_xhs_emoji_rhythm_and_at_most_five_tags(
    sample_digest,
):
    from tennislive.render.hashtags import hashtag_count
    from tennislive.render.knowledge import (
        _KNOWLEDGE_EMOJI_MARKERS,
        _validate_copy_for_publish,
        knowledge_copy,
    )
    from tennislive.render.tournament_story import STORIES

    for slug in ("golden-slam", "longest-match"):
        story = next(story for story in STORIES if story.slug == slug)
        copy = knowledge_copy(story, sample_digest)
        _validate_copy_for_publish(copy)
        body = "\n".join(copy.splitlines()[1:])
        markers = {
            marker for marker in _KNOWLEDGE_EMOJI_MARKERS if marker in body
        }

        assert 3 <= len(markers) <= 8
        assert hashtag_count(copy) <= 5


def test_knowledge_generation_switches_topic_after_visual_preflight_failure(
    tmp_path, sample_digest, monkeypatch
):
    from dataclasses import replace
    import json

    from PIL import Image

    from tennislive.render import knowledge
    from tennislive.render.tournament_story import STORIES

    cover = tmp_path / "cover.jpg"
    Image.new("RGB", (1200, 800), "white").save(cover)
    rejected = replace(next(s for s in STORIES if s.slug == "golden-slam"), image=cover)
    selected = replace(next(s for s in STORIES if s.slug == "umag"), image=cover)
    monkeypatch.setattr(
        knowledge,
        "tournament_story_candidates",
        lambda _digest: [rejected, selected],
    )

    def fake_resolve(story, _folder):
        if story.slug == rejected.slug:
            return {}, {
                "status": "fail",
                "errors": ["封面人物不匹配"],
                "missing_pages": ["story", "explainer", "today"],
                "attempts": [],
            }
        return {}, {"status": "pass", "attempts": [], "errors": []}

    monkeypatch.setattr(knowledge, "resolve_story_visuals", fake_resolve)
    monkeypatch.setattr(
        knowledge,
        "_screenshot_pages",
        lambda pages, _theme: [
            (kind, Image.new("RGB", (1080, 1440), "black")) for kind, _body in pages
        ],
    )

    result = knowledge.generate_knowledge_package(sample_digest, tmp_path / "knowledge")
    sources = json.loads((tmp_path / "knowledge" / "visual_sources.json").read_text("utf-8"))

    assert result.slug == selected.slug
    assert sources["rejected_candidates"][0]["story_slug"] == rejected.slug


def test_knowledge_generation_retries_same_topic_with_failed_sources_excluded(
    tmp_path, sample_digest, monkeypatch
):
    from dataclasses import replace
    import json

    from PIL import Image

    from tennislive.render import knowledge
    from tennislive.render.tournament_story import STORIES

    cover = tmp_path / "cover.jpg"
    Image.new("RGB", (1200, 800), "white").save(cover)
    selected = replace(next(s for s in STORIES if s.slug == "umag"), image=cover)
    monkeypatch.setattr(
        knowledge,
        "tournament_story_candidates",
        lambda _digest: [selected],
    )
    monkeypatch.setenv("TENNISLIVE_VISUAL_RETRIES_PER_TOPIC", "2")
    resolver_calls = []

    def fake_resolve(_story, _folder, *, excluded_source_urls=None):
        excluded = set(excluded_source_urls or ())
        resolver_calls.append(excluded)
        source = (
            "https://media.example/good.jpg"
            if excluded
            else "https://media.example/bad.jpg"
        )
        return {}, {
            "schema_version": 1,
            "status": "pass",
            "attempts": [{"status": "selected", "source_url": source}],
            "errors": [],
        }

    qa_results = iter(
        [
            {"status": "fail", "errors": ["image mismatch"]},
            {"status": "pass", "errors": []},
            {"status": "pass", "errors": [], "rendered_cards": []},
        ]
    )
    monkeypatch.setattr(knowledge, "resolve_story_visuals", fake_resolve)
    monkeypatch.setattr(
        knowledge,
        "evaluate_knowledge_visuals",
        lambda *_args, **_kwargs: next(qa_results),
    )
    monkeypatch.setattr(
        knowledge,
        "_screenshot_pages",
        lambda pages, _theme: [
            (kind, Image.new("RGB", (1080, 1440), "black"))
            for kind, _body in pages
        ],
    )

    result = knowledge.generate_knowledge_package(
        sample_digest,
        tmp_path / "knowledge",
    )
    sources = json.loads(
        (tmp_path / "knowledge" / "visual_sources.json").read_text("utf-8")
    )

    assert result.slug == selected.slug
    assert resolver_calls == [
        set(),
        {"https://media.example/bad.jpg"},
    ]
    assert sources["recovery"]["status"] == "recovered"
    assert sources["selection_evidence"]["same_topic_attempt"] == 2


def test_knowledge_generation_exhaustion_keeps_diagnostics_not_stale_publish_files(
    tmp_path, sample_digest, monkeypatch
):
    from dataclasses import replace
    import json

    from PIL import Image
    import pytest

    from tennislive.render import knowledge
    from tennislive.render.tournament_story import STORIES

    cover = tmp_path / "cover.jpg"
    Image.new("RGB", (1200, 800), "white").save(cover)
    candidate = replace(next(s for s in STORIES if s.slug == "umag"), image=cover)
    outdir = tmp_path / "knowledge"
    outdir.mkdir()
    (outdir / "push.html").write_text("stale", "utf-8")
    monkeypatch.setattr(
        knowledge,
        "tournament_story_candidates",
        lambda _digest: [candidate],
    )
    monkeypatch.setenv("TENNISLIVE_VISUAL_RETRIES_PER_TOPIC", "2")
    monkeypatch.setattr(
        knowledge,
        "resolve_story_visuals",
        lambda *_args, **_kwargs: (
            {},
            {
                "status": "fail",
                "errors": ["no exact image"],
                "missing_pages": ["story"],
                "attempts": [],
            },
        ),
    )

    with pytest.raises(ValueError, match="自动恢复已耗尽"):
        knowledge.generate_knowledge_package(sample_digest, outdir)

    failure = json.loads((outdir / "visual_sources.json").read_text("utf-8"))
    assert failure["status"] == "fail"
    assert failure["same_topic_attempt_limit"] == 2
    assert len(failure["attempts"]) == 2
    assert not (outdir / "push.html").exists()


def test_cover_promotes_overnight_lead_and_multiple_highlights(sample_digest):
    from tennislive.render import webcards

    body = webcards.cover_body(
        sample_digest,
        "fallback headline",
        "fallback secondary",
        "07.16 · 周四",
    )

    assert "MATCH POINT · 今日头条" in body
    assert "郑钦文" in body  # 同级比赛由固定 +35 中国相关性决定头条
    assert "China Focus · 中国焦点" in body
    assert "Tonight · 今晚必看" in body
    assert body.count('class="cover-highlight"') == 2


def test_cover_uses_verified_athlete_photo_as_full_bleed_background(
    sample_digest, tmp_path
):
    from PIL import Image

    from tennislive.render.webcards import cover_body

    photo = tmp_path / "athlete.jpg"
    Image.new("RGB", (1600, 1200), "white").save(photo)
    body = cover_body(
        sample_digest,
        "辛纳逆转晋级",
        "把比赛拖进自己的节奏",
        "7.16 · 周四",
        cover_visual={
            "path": photo,
            "source_url": "https://example.com/athlete",
            "credit": "Verified Photographer",
            "license": "CC BY 4.0",
            "focus": "62% 24%",
        },
    )

    assert 'class="cover-bg"' in body
    assert "--cover-focus:62% 24%" in body
    assert 'data-photo-source="https://example.com/athlete"' not in body
    assert "Verified Photographer" not in body
    assert "CC BY 4.0" not in body
    assert "cover-subject" not in body


def test_cover_moves_compact_copy_opposite_the_detected_face(
    sample_digest, tmp_path
):
    from PIL import Image

    from tennislive.render.webcards import cover_body

    photo = tmp_path / "athlete.jpg"
    Image.new("RGB", (1600, 1200), "white").save(photo)

    person_right = cover_body(
        sample_digest,
        "这场逆转为什么值得记住",
        "副标题不再堆在人物脸部附近",
        "7.16 · 周四",
        cover_visual={"path": photo, "focus": "68% 24%"},
    )
    person_left = cover_body(
        sample_digest,
        "这场逆转为什么值得记住",
        "副标题不再堆在人物脸部附近",
        "7.16 · 周四",
        cover_visual={"path": photo, "focus": "31% 60%"},
    )

    assert "cover-text-left" in person_right
    assert 'data-cover-text-side="left"' in person_right
    assert 'data-cover-focus-x="68.0"' in person_right
    assert "cover-text-right" in person_left
    assert 'data-cover-text-side="right"' in person_left
    assert person_right.index('class="cover-secondary"') > person_right.index(
        'class="cover-lower"'
    )
    assert 'class="cover-date"' not in person_right
    assert 'class="focus-label"' not in person_right
    assert "MATCH POINT · 今日头条" in person_right


def test_cover_focus_fallback_still_uses_a_deterministic_safe_layout(
    sample_digest, tmp_path
):
    from PIL import Image

    from tennislive.render.webcards import cover_body

    photo = tmp_path / "athlete.jpg"
    Image.new("RGB", (1600, 1200), "white").save(photo)
    body = cover_body(
        sample_digest,
        "今日头条",
        "",
        "7.16 · 周四",
        cover_visual={"path": photo, "focus": "center"},
    )

    assert "cover-text-left" in body
    assert 'data-cover-focus-x="50.0"' in body
    assert 'data-cover-focus-y="28.0"' in body


def test_daily_cover_visual_requires_exact_player_match(monkeypatch, tmp_path):
    from PIL import Image

    from tennislive.research import visual_sources

    match = make_match(home_name="Jannik Sinner", away_name="Novak Djokovic")
    cached = tmp_path / "resolved.jpg"
    Image.new("RGB", (1400, 1000), "white").save(cached)

    monkeypatch.setenv("TENNISLIVE_COVER_VISUAL_FETCH", "on")
    monkeypatch.setattr(
        visual_sources,
        "_commons_candidates",
        lambda _query, _session: [
            {
                "provider": "wikimedia-commons",
                "source_url": "https://example.com/sinner",
                "image_url": "https://example.com/sinner.jpg",
                "credit": "Photographer",
                "license": "cc-by",
                "width": 1400,
                "height": 1000,
                "relevance": 12,
                "search_text": (
                    "jannik sinner serves during the wimbledon 2026 match "
                    "against novak djokovic"
                ),
                "image_text": "jannik sinner serves during the match",
            }
        ],
    )
    monkeypatch.setattr(visual_sources, "_openverse_candidates", lambda *_args: [])
    monkeypatch.setattr(visual_sources, "_bing_candidates", lambda *_args: [])
    monkeypatch.setattr(
        visual_sources,
        "assess_cover_image",
        lambda _path: {
            "status": "pass",
            "score": 35,
            "quality_score": 15,
            "crop_score": 20,
            "hard_failures": [],
            "focus": "62% 24%",
            "prominent_faces": 1,
        },
    )
    monkeypatch.setattr(
        visual_sources,
        "_download",
        lambda candidate, page, query, folder, session: visual_sources.ResolvedVisual(
            page=page,
            path=cached,
            provider=candidate["provider"],
            source_url=candidate["source_url"],
            image_url=candidate["image_url"],
            credit=candidate["credit"],
            license=candidate["license"],
            query=query,
            relevance=candidate["relevance"],
            sha256="abc",
        ),
    )

    visual, report = visual_sources.resolve_match_cover_visual(match, tmp_path)

    assert visual is not None and visual.subject_match
    assert report["status"] == "selected"
    assert report["selected_player"] == "Jannik Sinner"
    assert report["scene"] == "match_action"
    assert report["quality_score"] >= 72


def test_tonight_reason_uses_editorial_label(sample_digest):
    from tennislive.render import webcards

    sample_digest.schedule[0].editorial_source = "WTA 官方报道"
    sample_digest.schedule[0].editorial_url = "https://example.test/wta-preview"
    body = webcards.tonight_body(sample_digest.schedule, "07.16 · 周四")

    assert "<span>看点</span>" in body
    assert "<span>媒体</span>" not in body
    assert "WTA 官方报道" not in body
    assert "数据" not in body
    assert "icons/" not in body  # icons are embedded so CI rendering is self-contained
    assert "data:image/svg+xml;base64" in body


def test_tonight_page_uses_event_landmark_and_chinese_marker():
    from tennislive.render import webcards

    match = make_match(
        home_name="Qinwen Zheng",
        away_name="Maria Sakkari",
        home_country="CHN",
        away_country="GRE",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Athens Open",
        match_id="athens-focus",
    )
    match.tournament.level = "WTA250"
    match.court = "Center Court"

    body = webcards.tonight_body([match], "07.20 · 周一")

    assert "雅典 · 希腊" in body
    assert "--page-bg:url('data:image/jpeg;base64," in body
    assert "中国选手" in body
    assert body.count('class="card pick"') == 1


def test_tonight_page_does_not_invent_tbd_from_same_event_anchor():
    from datetime import datetime, timezone

    from tennislive.render import webcards

    anchor = make_match(
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Prague Open",
        start_utc=datetime(2026, 7, 20, 12, 30, tzinfo=timezone.utc),
        match_id="athens-anchor",
    )
    focus = make_match(
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Athens Open",
        start_utc=None,
        match_id="athens-tbd",
    )

    body = webcards.tonight_body([anchor, focus], "07.20 · 周一")

    assert "待定" in body
    assert "预计 22:15*" not in body


def test_tonight_page_keeps_tbd_without_event_anchor():
    from tennislive.render import webcards

    focus = make_match(
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Example Open",
        start_utc=None,
        match_id="unanchored-tbd",
    )

    body = webcards.tonight_body([focus], "07.20 · 周一")

    assert "待定" in body
    assert "*为预计时间" not in body


def test_tonight_page_marks_official_unlisted_as_waiting_for_oop():
    from tennislive.render import webcards

    focus = make_match(
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Example Open",
        start_utc=None,
        match_id="official-unlisted",
    )
    focus.schedule_time_status = "official-unlisted"

    body = webcards.tonight_body([focus], "07.20 · 周一")

    assert "待官方排期" in body


def test_five_match_tonight_page_hides_court_headers_to_protect_footer():
    from tennislive.render import webcards

    matches = []
    for index in range(5):
        match = make_match(
            status=MatchStatus.SCHEDULED,
            winner=None,
            sets=(),
            tiebreaks=(),
            tournament="Generali Open",
            match_id=f"kitzbuhel-{index}",
        )
        match.court = "Center Court" if index < 3 else "Grandstand"
        matches.append(match)

    body = webcards.tonight_body(matches, "07.20 · 周一")

    assert 'class="court-label"' not in body


def test_deck_splits_tonight_focus_by_event_and_has_no_china_page(
    sample_digest, monkeypatch
):
    from copy import deepcopy

    from tennislive.render import webcards

    digest = deepcopy(sample_digest)
    prague = make_match(
        home_name="Qinwen Zheng",
        away_name="Maria Sakkari",
        home_country="CHN",
        away_country="GRE",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Prague Open",
        tour=Tour.WTA,
        match_id="prague-focus",
    )
    digest.schedule.append(prague)
    digest.schedule.extend(
        [
            make_match(
                home_name="Linda Noskova",
                away_name="Marketa Vondrousova",
                home_country="CZE",
                away_country="CZE",
                status=MatchStatus.SCHEDULED,
                winner=None,
                sets=(),
                tiebreaks=(),
                tournament="Prague Open",
                tour=Tour.WTA,
                match_id="prague-second",
            ),
            make_match(
                home_name="Jannik Sinner",
                away_name="Novak Djokovic",
                status=MatchStatus.SCHEDULED,
                winner=None,
                sets=(),
                tiebreaks=(),
                tournament="Wimbledon",
                match_id="wimbledon-second",
            ),
        ]
    )
    monkeypatch.setattr(
        webcards, "editorial_tonight_focus", lambda _matches: digest.schedule
    )
    monkeypatch.setattr(webcards, "_screenshot_pages", lambda pages, _theme: pages)

    pages = webcards.generate_deck(digest, "07.20 · 周一")
    kinds = [kind for kind, _body in pages]
    tonight_pages = [body for kind, body in pages if kind.startswith("tonight")]

    assert "china" not in kinds
    assert len(tonight_pages) == 2
    assert all(
        not ("Prague Open" in body and "温布尔登" in body)
        for body in tonight_pages
    )


def test_deck_keeps_atp_and_wta_draws_of_same_event_on_one_page(
    sample_digest, monkeypatch
):
    from copy import deepcopy

    from tennislive.render import webcards

    digest = deepcopy(sample_digest)
    wta = make_match(
        home_name="Qinwen Zheng",
        away_name="Iga Swiatek",
        home_country="CHN",
        away_country="POL",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        tournament="Wimbledon",
        tour=Tour.WTA,
        match_id="wta-wimbledon",
    )
    digest.schedule.append(wta)
    monkeypatch.setattr(
        webcards, "editorial_tonight_focus", lambda _matches: digest.schedule
    )
    monkeypatch.setattr(webcards, "_screenshot_pages", lambda pages, _theme: pages)

    pages = webcards.generate_deck(digest, "07.20 · 周一")
    tonight_pages = [body for kind, body in pages if kind.startswith("tonight")]

    assert len(tonight_pages) == 1
    assert "Carlos Alcaraz" in tonight_pages[0]
    assert "Qinwen Zheng" in tonight_pages[0]


def test_cover_uses_sourced_wait_for_historical_comeback():
    from tennislive.render.titles import cover_result_hook

    match = make_match(
        home_name="Stefanos Tsitsipas",
        away_name="Alexander Shevchenko",
        home_country="GRE",
        away_country="KAZ",
        round_name="Final",
        tournament="Swiss Open Gstaad",
    )
    match.home[0].rank = 85
    match.editorial_note = "时隔16个月，西西帕斯再次赢得巡回赛冠军。"
    match.editorial_url = "https://example.test/sourced-recap"

    headline, secondary = cover_result_hook(match)

    assert headline == "时隔16个月，西西帕斯再夺冠"
    assert "两进大满贯决赛" in secondary
    assert "新的起点" in secondary
    assert "世界第85" not in headline + secondary


def test_tonight_card_separates_bilingual_player_lines(sample_digest):
    from tennislive.render import webcards

    body = webcards.tonight_body(sample_digest.schedule, "07.16 · 周四")

    assert '<span class="en">Carlos Alcaraz</span>' in body
    assert "class=\"names\"" in body
    assert '<b class="event-level">大满贯</b>' in body
    assert '<b class="event-surface">草地</b>' in body
    assert body.index("温布尔登") < body.index('class="event-level"')


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


def test_focus_comparison_omits_incomplete_winners_error_pair():
    match = make_match()
    match.stats = MatchStats(
        source="partial-test",
        total_points_won=StatPair(80, 74),
        winners=StatPair(31, 27),
        unforced_errors=None,
    )

    comparison = focus_comparison(match)

    assert ("总得分", "80", "74") in comparison.rows
    assert not any(label == "制胜分 / 非受迫" for label, _left, _right in comparison.rows)


def test_focus_comparison_supports_five_set_grand_slam_match():
    match = make_match(
        sets=((6, 4), (3, 6), (7, 6), (4, 6), (6, 3)),
        tiebreaks=(None, None, (7, 5), None, None),
    )

    comparison = focus_comparison(match)

    assert len(comparison.rows) == 8
    assert comparison.rows[-2][0] == "第四盘"
    assert comparison.rows[-1] == ("第五盘", "6", "3")


def test_title_candidates_always_exactly_three(sample_digest):
    """V1 §3.1：任何场景稳定输出 3 个候选，每个 ≤20 字."""
    from tennislive.render.titles import title_candidates

    rich = title_candidates(sample_digest)
    assert len(rich) == 3 and len(set(rich)) == 3
    assert all(len(t) <= 20 for t in rich)

    empty = title_candidates(Digest(today=date(2026, 7, 21)))
    assert len(empty) == 3 and len(set(empty)) == 3
    assert all(len(t) <= 20 for t in empty)


def test_fatal_qa_blocks_publish(sample_digest):
    """V1 §0/§4：FATAL 质检必须能触发停发（cli 依 fatal 非空返回 2 阻断发布）."""
    from tennislive.qa import run_checks

    fatal, _ = run_checks(sample_digest, "", "标题\n\n正文")
    assert any("标题为空" in f for f in fatal)  # 空标题 = FATAL

    sample_digest.results[0].home[0].name = "?"
    fatal2, _ = run_checks(sample_digest, "正常标题", "标题\n\n正文")
    assert any("空球员名" in f for f in fatal2)


def test_cover_facts_trace_back_to_match_evidence():
    """V1 §5.1：主副标题的完整数字声明必须出现在结构化证据包。"""
    from tennislive.render.titles import (
        cover_fact_bundle,
        cover_fact_errors,
        cover_result_hook,
    )

    m = make_match(
        home_name="Qinwen Zheng", home_country="CHN",
        away_name="Aryna Sabalenka", away_country="BLR",
        sets=((4, 6), (6, 3), (7, 6)), tiebreaks=(None, None, (10, 8)),
    )
    main, secondary = cover_result_hook(m)
    bundle = cover_fact_bundle(m, source="espn")
    assert bundle["source"] == "espn"
    assert not cover_fact_errors(m, main, secondary)
    assert "83" not in bundle["allowed_numbers"]
    assert "封面数字无证据: 83" in cover_fact_errors(
        m, f"{main}，世界第83", secondary
    )

    historical = make_match(
        home_name="Stefanos Tsitsipas",
        away_name="Alexander Shevchenko",
        home_country="GRE",
        away_country="KAZ",
        round_name="Final",
        tournament="Swiss Open Gstaad",
    )
    historical.home[0].rank = 85
    historical_main, historical_secondary = cover_result_hook(historical)
    historical_bundle = cover_fact_bundle(historical)
    assert not cover_fact_errors(
        historical, historical_main, historical_secondary
    )
    assert historical_bundle["historical_profile"] == {
        "peak_rank": 3,
        "legacy": "两进大满贯决赛",
        "source_url": "https://www.atptour.com/en/players/tsitsipas-stefanos/te51/bio",
    }


def test_trajectory_arc_differentiates_cruise_comeback_and_seesaw():
    """'比赛走势'必须按盘与盘之间谁赢谁输区分，而不是同一句话覆盖所有比赛."""
    from tennislive.render.story import trajectory_arc

    cruise = make_match(match_id="cruise", sets=((6, 4), (6, 3)), tiebreaks=())
    assert trajectory_arc(cruise) == "直落2盘，全程没有让对手看到机会"

    comeback = make_match(
        match_id="comeback", sets=((4, 6), (6, 3), (6, 4)), tiebreaks=()
    )
    assert trajectory_arc(comeback) == "先丢一盘，随后连扳2盘完成逆转"

    seesaw = make_match(
        match_id="seesaw", sets=((6, 4), (4, 6), (6, 4)), tiebreaks=()
    )
    assert trajectory_arc(seesaw) == "比赛几度易手，胜负直到最后关键分才见分晓"


def test_insight_body_result_page_has_no_stats_falls_back_to_arc_and_verdict():
    """没有官方技术统计时，第二页只展示走势+编辑锐评，不能伪造一张
    盘数/局数/抢七的"技术对比表"充数——那本质只是比分的换算，不是
    真正的技战术数据（发球/破发/制胜分等），伪装成数据对比会误导读者。"""
    from datetime import date

    from tennislive.render.webcards import insight_body

    match = make_match(sets=((6, 4), (4, 6), (7, 6)), tiebreaks=(None, None, (10, 8)))
    assert match.stats is None
    html_out = insight_body(match, "7.23", "result", date(2026, 7, 23))

    assert "编辑锐评" in html_out
    assert "比赛走势" in html_out  # 走势句块已渲染
    assert "compare-grid" not in html_out and "compare-row" not in html_out
    assert "草地" in html_out  # Wimbledon 场地信息，卡片上此前不曾出现
    assert "完整盘分" not in html_out and "比赛轮次" not in html_out  # 旧的凑数标签已移除


def test_insight_body_result_page_shows_real_stats_table_when_licensed_data_exists():
    """只有当官方/授权数据源提供了真实技战术统计（发球%、ACE、破发、制胜分等）
    时，第二页才展示"专业技术统计"表格——这时表格标题和内容都必须是真数据。"""
    from datetime import date

    from tennislive.models import MatchStats, StatPair
    from tennislive.render.webcards import insight_body

    match = make_match(sets=((6, 4), (4, 6), (7, 6)), tiebreaks=(None, None, (10, 8)))
    match.stats = MatchStats(
        source="ESPN",
        first_serve_won_pct=StatPair(home=72, away=64),
        aces=StatPair(home=12, away=6),
        break_points_won=StatPair(home=4, away=2),
    )
    html_out = insight_body(match, "7.23", "result", date(2026, 7, 23))

    assert "编辑锐评" in html_out
    assert "比赛走势" in html_out
    assert "compare-grid" in html_out and "compare-row" in html_out
    assert "专业技术统计" in html_out
    assert "一发得分率" in html_out and "ACE" in html_out


def test_editor_takeaway_fallback_names_the_actual_players_not_boilerplate():
    """没有权威媒体锐评、也没有追踪中的球员故事时，兜底的"编辑锐评"必须是
    针对这场比赛的具体判断（点名真实球员/轮次），不能是套在哪场比赛都
    通用的空话——那本质上和凑数的技术统计表是同一种问题。"""
    from tennislive.render.narrative import editor_takeaway

    match = make_match(sets=((6, 4), (4, 6), (7, 6)), tiebreaks=(None, None, (10, 8)))
    takeaway = editor_takeaway(match, date(2026, 7, 23))

    assert "我更在意比赛留下的变化" not in takeaway
    assert "辛纳" in takeaway or "德约科维奇" in takeaway  # 点名真实球员之一
    assert takeaway.strip()
