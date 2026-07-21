from __future__ import annotations

from datetime import date

from conftest import make_match

from tennislive.digest import Digest
from tennislive.models import MatchStats, MatchStatus, StatPair
from tennislive.qa import check_xhs_post


TITLE = "🎾7.20｜今晚焦点值得守"


def _digest(*, schedule_count: int = 3) -> Digest:
    result = make_match(match_id="result")
    schedule = []
    for index in range(schedule_count):
        schedule.append(
            make_match(
                home_name=f"Home Player {index}",
                away_name=f"Away Player {index}",
                home_country="USA",
                away_country="GBR",
                status=MatchStatus.SCHEDULED,
                winner=None,
                sets=(),
                tiebreaks=(),
                match_id=f"scheduled-{index}",
            )
        )
    return Digest(today=date(2026, 7, 20), results=[result], schedule=schedule)


def _spacious_body(*, matchups: int = 3) -> str:
    blocks = [
        "昨夜最值得记住的，不是整张比分表，而是关键分上的处理方式。",
        "主角在接发端更早站进场内，也让下一拍进攻变得更从容。",
        "🇨🇳 中国球员速报\n今天的中国球员线索单独整理，阅读时更容易找到重点。",
        f"🌙 今晚焦点 · {matchups}场",
    ]
    for index in range(matchups):
        blocks.append(
            f"Home Player {index} vs Away Player {index}\n"
            "这场更值得观察的是发球后的第一拍，以及底线相持中的主动变线。"
        )
    blocks.extend(
        [
            "📝 我的一票\n我会优先看对抗最鲜明的一场，因为比赛走势更有观察价值。",
            "💬 留个答案\n你今晚会守哪一场？也可以说说最想继续追的球员。",
            "这里是网球时差。睡醒看懂昨夜，开赛前只提醒真正值得看的比赛。",
            "这份内容保留明确选择，也给每一条信息留下足够呼吸感和阅读停顿。",
            "赛果负责交代发生了什么，判断负责回答为什么这件事值得被记住。",
            "我们关注球员当下的比赛表现，也持续记录巡回赛正在形成的新故事。",
            "每一条比分、时间和技术数字都应当能够回到当天抓取的原始证据。",
            "#网球 #WTA #ATP #中国网球 #网球时差",
        ]
    )
    return "\n\n".join(blocks)


def _post(body: str, title: str = TITLE) -> str:
    return f"{title}\n\n{body}"


def test_xhs_daily_post_passes_core_publishability_rules():
    fatal, warn = check_xhs_post(_digest(), _post(_spacious_body()))

    assert fatal == []
    assert not any("正文" in item for item in warn)
    assert not any("留白" in item for item in warn)


def test_xhs_daily_title_requires_current_date_and_platform_length():
    digest = _digest()

    missing_date, _ = check_xhs_post(
        digest, _post(_spacious_body(), title="🎾今晚焦点值得守")
    )
    too_long, _ = check_xhs_post(
        digest,
        _post(_spacious_body(), title="🎾7.20｜这是一个明显超过平台预算的超长标题需要阻断"),
    )

    assert any("缺少当日日期" in item for item in missing_date)
    assert any("标题超长" in item for item in too_long)


def test_xhs_flash_requires_date_but_is_exempt_from_daily_body_target():
    match = make_match(
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        match_id="flash",
    )
    digest = Digest(today=date(2026, 7, 20), schedule=[match])
    body = (
        "今晚不必守满所有比赛，先给这一场留时间。\n\n"
        "🌙 今晚焦点\n辛纳 vs 德约科维奇\n\n"
        "💬 留个答案\n你会看这场吗？"
    )

    fatal, warn = check_xhs_post(digest, _post(body))
    no_date, _ = check_xhs_post(digest, _post(body, title="🎾今晚值得守"))

    assert not any("正文过短" in item for item in fatal)
    assert not any("正文低于" in item for item in warn)
    assert any("缺少当日日期" in item for item in no_date)


def test_xhs_one_match_daily_post_still_uses_daily_body_gate():
    digest = Digest(today=date(2026, 7, 20), results=[make_match(match_id="daily-one")])
    body = "🎾 今天先看这一件事\n辛纳赢下关键战。\n\n💬 留个答案\n你怎么看？"

    fatal, _ = check_xhs_post(digest, _post(body))

    assert any("正文过短" in item for item in fatal)


def test_xhs_body_target_warns_but_hard_limits_block():
    digest = _digest()
    short_body = "短正文。\n\n仍有留白。\n\n但内容不足。"
    near_target = ("这一段提供清楚判断和自然停顿。\n\n" * 28).strip()
    overly_dense = ("这是一段用于验证正文绝对上限的内容。\n\n" * 50).strip()

    short_fatal, _ = check_xhs_post(digest, _post(short_body))
    target_fatal, target_warn = check_xhs_post(digest, _post(near_target))
    dense_fatal, _ = check_xhs_post(digest, _post(overly_dense))

    assert any("正文过短" in item for item in short_fatal)
    assert not any("正文" in item for item in target_fatal)
    assert not any("正文" in item for item in target_warn)
    assert any("正文过密" in item for item in dense_fatal)


def test_xhs_tonight_focus_allows_three_to_five_unique_matches():
    three_fatal, _ = check_xhs_post(_digest(schedule_count=3), _post(_spacious_body(matchups=3)))
    five_fatal, _ = check_xhs_post(_digest(schedule_count=5), _post(_spacious_body(matchups=5)))
    six_fatal, _ = check_xhs_post(_digest(schedule_count=6), _post(_spacious_body(matchups=6)))

    assert not any("今晚焦点" in item for item in three_fatal)
    assert not any("今晚焦点" in item for item in five_fatal)
    assert any("今晚焦点超过5场" in item for item in six_fatal)


def test_xhs_plan_post_tightens_copy_after_compact_still_runs_long(monkeypatch):
    from tennislive.render import xiaohongshu
    from tennislive.render.xiaohongshu import XhsPostPlan, XhsSection

    digest = _digest(schedule_count=5)
    tonight_lines: list[str] = []
    for index in range(5):
        if index:
            tonight_lines.append("")
        tonight_lines.extend(
            [
                f"⏰ 18:{index}0｜布拉格公开赛·女单第一轮",
                f"Home Player {index} vs Away Player {index}",
                "看点：" + "这是一句很长但仍然基于赛程身份的看点。" * 3,
            ]
        )
    long_plan = XhsPostPlan(
        title=TITLE,
        hook=("昨夜比赛不少，但头条其实很清楚。",),
        lead_match_id="result",
        lead_score=1,
        lead_reasons=(),
        sections=(
            XhsSection("🎾 今天先看这一件事", ("头条结果说明。" * 8,)),
            XhsSection("🇨🇳 中国球员速报", ("袁悦17:00出战。", "高馨妤预计 18:30*出战。")),
            XhsSection("🌙 今晚焦点 · 5场", tuple(tonight_lines)),
            XhsSection("🎯 一场球看细一点", ("技术统计很长。" * 12,)),
        ),
        opinion="我会先看第一场。" + "这里继续展开很多主观看法。" * 10,
        question="如果只给中国球员一句赛前提醒，你会写什么？",
        pinned_comment="",
        signature="关注 @网球时差｜下一篇，用赛果和胜负手把这条故事接着讲完。",
        tags=("#网球", "#网球时差", "#WTA", "#ATP", "#中国网球", "#布拉格公开赛", "#汉堡公开赛"),
        evidence=(),
    )
    monkeypatch.setattr(
        xiaohongshu, "build_post_plan", lambda _digest, compact=False: long_plan
    )

    plan, post = xiaohongshu.plan_post(digest)
    body = post.split("\n", 2)[2]

    assert len(body) <= xiaohongshu.MAX_BODY
    assert "🎯 一场球看细一点" not in post
    assert "🌙 今晚焦点｜3场" in post
    assert plan.signature == "关注 @网球时差｜明早一起对答案。"


def test_xhs_rejects_black_square_and_unbroken_database_layout():
    digest = _digest()
    black_square, _ = check_xhs_post(
        digest, _post(_spacious_body().replace("🌙", "■", 1))
    )
    dense_lines = "\n".join(f"连续信息行{index}" for index in range(8))
    dense_layout, _ = check_xhs_post(
        digest, _post(dense_lines + "\n\n" + _spacious_body())
    )

    assert any("黑方块" in item for item in black_square)
    assert any("连续信息行过多" in item for item in dense_layout)


def test_xhs_numeric_claims_must_trace_to_digest_evidence(sample_digest):
    from tennislive.render.xiaohongshu import to_post

    supported, _ = check_xhs_post(sample_digest, to_post(sample_digest))
    invented_score, _ = check_xhs_post(
        sample_digest, to_post(sample_digest) + "\n\n补充比分：6-1。"
    )
    invented_percent, _ = check_xhs_post(
        sample_digest, to_post(sample_digest) + "\n\n接发得分率达到67%。"
    )
    invented_rank, _ = check_xhs_post(
        sample_digest, to_post(sample_digest) + "\n\n目前已经来到世界第85。"
    )

    assert not any("无数据依据" in item for item in supported)
    assert any("6-1" in item for item in invented_score)
    assert any("67%" in item for item in invented_percent)
    assert any("世界第85" in item for item in invented_rank)


def test_xhs_editorial_note_can_supply_numeric_evidence():
    digest = _digest(schedule_count=1)
    digest.schedule[0].editorial_note = "上一轮在对手二发上拿到67%。"
    body = _spacious_body(matchups=1) + "\n\n权威看点：上一轮在对手二发上拿到67%。"

    fatal, _ = check_xhs_post(digest, _post(body))

    assert not any("67%" in item for item in fatal)


def test_xhs_official_stats_can_supply_percentage_evidence():
    digest = _digest(schedule_count=1)
    digest.results[0].stats = MatchStats(
        source="licensed",
        first_serve_won_pct=StatPair(67, 59),
    )
    body = _spacious_body(matchups=1) + "\n\n技术统计：一发得分率达到67%。"

    fatal, _ = check_xhs_post(digest, _post(body))

    assert not any("67%" in item for item in fatal)


def test_xhs_reviewed_historical_profile_supplies_peak_rank_evidence():
    match = make_match(
        home_name="Stefanos Tsitsipas",
        away_name="Felix Auger-Aliassime",
        winner=0,
        match_id="tsitsipas-final",
        round_name="Final",
    )
    match.home[0].rank = 85
    digest = Digest(today=date(2026, 7, 20), results=[match])
    body = (
        "刚刚结束，但这场不该只看比分。\n\n"
        "🎾 先说结果\n西西帕斯夺冠。\n"
        "他曾高居世界第3，也两次打进大满贯决赛。"
    )

    fatal, _ = check_xhs_post(digest, _post(body, title="🏆7.20｜西西帕斯终于捧杯"))

    assert not any("世界第3" in item for item in fatal)
