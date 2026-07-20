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
    from tennislive.render.titles import pick_headline_auto
    from tennislive.render.xiaohongshu import xhs_title_len

    post = to_post(sample_digest)
    title = post_title(sample_digest)
    # V1 §3.1：发布标题与封面主钩子同源（头条候选 ①）+ 日期与 emoji
    d = sample_digest.today
    assert f"{d.month}.{d.day}｜" in title
    hook = title.split("｜", 1)[1]
    assert pick_headline_auto(sample_digest).startswith(hook.rstrip("…"))
    assert xhs_title_len(title) <= 20  # 平台口径：半角记 0.5
    assert "#网球" in post
    body = post.split("\n", 2)[2]
    assert len(body) <= 1000
    assert "今天先看这一件事" in post
    assert "今晚只看这三场" in post
    assert "📝 我的一票" in post
    assert "💬 留个答案" in post
    assert "发球还是接发" in post or "只选一边" in post
    assert "明早用赛果和胜负手" in post
    assert result_line(sample_digest.results[0]) not in post
    assert "ATP 250" not in post and "WTA 250" not in post
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
    page = to_copy_page(xhs, alt_titles=["备选钩子一", "测试标题 <1>", ""])
    push_html = to_push_html(
        sample_digest, cards=["card_00_cover.png"], xhs_text=xhs
    )

    assert "复制标题" in page and "复制正文" in page
    assert "测试标题 &lt;1&gt;" in page
    assert "正文第一行" in page
    # V1 §3.1：备选标题可复制；与主标题重复或为空的候选不重复展示
    assert "备选标题 2" in page and "备选钩子一" in page
    assert "备选标题 3" not in page
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
    # 有爆点时大字报钩子卡是第一张（card_00_hook），设计版封面顺延
    assert any("_cover.png" in n for n in names)
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
    assert sum("_cover.png" in n for n in names) == 1
    assert not any("hook" in n for n in names)
    assert names[0] == "card_00_cover.png"


def test_daily_deck_caps_optional_pages_at_seven(sample_digest, monkeypatch):
    from copy import deepcopy

    from tennislive.render import webcards
    from tennislive.render.tournament_story import STORIES
    from tennislive.sources.rankings import Rankings

    digest = deepcopy(sample_digest)
    digest.today = date(2026, 7, 20)  # 周一，同时触发排名页
    digest.results.extend(
        make_match(
            home_name=f"Player {index}",
            away_name=f"Opponent {index}",
            match_id=f"extra-{index}",
        )
        for index in range(6)
    )
    digest.results[0].stats = MatchStats(
        source="licensed-test",
        total_points_won=StatPair(80, 70),
    )
    digest.rankings = Rankings()
    monkeypatch.setattr(webcards, "pick_tournament_story", lambda _digest: STORIES[0])
    monkeypatch.setattr(
        webcards, "_screenshot_pages", lambda pages, _theme: pages
    )

    pages = webcards.generate_deck(digest, "07.20 · 周一")
    kinds = [kind for kind, _body in pages]
    assert len(kinds) == 7
    assert kinds.count("cover") == 1
    assert "focus" not in kinds


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
    champion = decorate_title(digest, "跌至世界第85，西西帕斯终于捧杯")
    assert champion == "🏆7.20｜跌至世界第85，西西帕斯终于捧杯"
    assert xhs_title_len(champion) <= 20

    assert decorate_title(digest, "爆冷：黑马掀翻头号种子").startswith("💥")
    assert decorate_title(digest, "袁悦今日出战").startswith("🔥")
    assert decorate_title(digest, "每日赛程赛果速览").startswith("🎾")

    # 超预算的钩子被裁剪并加省略号，总长仍在预算内
    long_hook = "这是一个非常非常长的钩子标题肯定放不下二十个字"
    trimmed = decorate_title(digest, long_hook)
    assert trimmed.endswith("…") and xhs_title_len(trimmed) <= 20


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
    assert story.source_label in body


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


def test_cover_promotes_overnight_lead_and_multiple_highlights(sample_digest):
    from tennislive.render import webcards

    body = webcards.cover_body(
        sample_digest,
        "fallback headline",
        "fallback secondary",
        "07.16 · 周四",
    )

    assert "Overnight Lead · 昨夜头条" in body
    assert "郑钦文" in body  # 同级比赛由固定 +35 中国相关性决定头条
    assert "China Focus · 中国焦点" in body
    assert "Tonight · 今晚必看" in body
    assert body.count('class="cover-highlight"') == 2


def test_tonight_reason_uses_editorial_label(sample_digest):
    from tennislive.render import webcards

    body = webcards.tonight_body(sample_digest.schedule, "07.16 · 周四")

    assert "<span>看点</span>" in body
    assert "数据" not in body
    assert "icons/" not in body  # icons are embedded so CI rendering is self-contained
    assert "data:image/svg+xml;base64" in body


def test_cover_uses_historical_hook_for_ranked_comeback():
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

    headline, secondary = cover_result_hook(match)

    assert headline == "跌至世界第85，西西帕斯终于捧杯"
    assert "世界第3" in secondary
    assert "两进大满贯决赛" in secondary
    assert "反弹信号" in secondary


def test_tonight_card_separates_bilingual_player_lines(sample_digest):
    from tennislive.render import webcards

    body = webcards.tonight_body(sample_digest.schedule, "07.16 · 周四")

    assert '<span class="en">Carlos Alcaraz</span>' in body
    assert "class=\"names\"" in body
    assert '<b class="tour-level">大满贯</b>' in body
    assert body.index('class="tour-level"') < body.index("温布尔登")


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
