from __future__ import annotations

from datetime import date

from conftest import make_match
from tennislive.models import MatchStatus
from tennislive.render import editorial_memory
from tennislive.render.narrative import preview_angle


def _no_story_match(**overrides):
    """A scheduled singles match with no curated story, media brief, or
    Chinese player — the exact gap where preview_angle used to fall straight
    to mechanical rank/seed facts with no topicality or history signal."""
    defaults = dict(
        home_name="Constant Lestienne", away_name="Zizou Bergs",
        home_country="FRA", away_country="BEL",
        status=MatchStatus.SCHEDULED, winner=None, sets=(), tiebreaks=(),
        round_name="Quarterfinals",
    )
    defaults.update(overrides)
    return make_match(**defaults)


def test_preview_angle_ignores_tournament_wide_news_not_about_this_match():
    """双方的话题性不能来自"挂错比赛"的通稿式条目.

    生产环境曾实际出现：apply_trend_signals() 把同一批 Tennis.com 赛程列表
    条目（'Kempen / Panova vs Zaar / Zimmermann · Quarterfinal · WTA Hamburg'）
    无差别地挂到当天汉堡站的每一场比赛上，包括跟这批标题完全无关的对阵。
    这类条目对单场比赛只贡献很低的热度分（未命中具体球员），不该被当成
    "这场有真实话题度"的证据——话题性判断必须看热度分而不是标题是否存在。
    """
    match = _no_story_match(match_id="topical-tournament-wide")
    match.trend_signals = [
        {
            "kind": "official-news",
            "source": "Tennis.com",
            "title": "Kempen / Panova vs Zaar / Zimmermann · Quarterfinal · WTA Hamburg",
            "url": "https://www.tennis.com/example",
            "published_at": "2026-07-23T06:00:00+00:00",
            "traffic": "",
        }
    ]
    match.media_heat = 2  # 未命中具体球员时的真实相关性权重（见 apply_trend_signals）

    angle = preview_angle(match, date(2026, 7, 23))

    assert "Kempen" not in angle and "Zaar" not in angle
    assert "话题度" not in angle  # 热度不够，应落回机械看点而非话题性声明


def test_preview_angle_cites_topicality_from_heat_score_not_raw_headline():
    """双方的话题性：真正命中球员、热度分明显走高时才给话题性提示，且不引用原始外文标题.

    不直接拼接外部标题：标题长度不可控、可能不含中文标点，会被正文渲染层
    按标点/空格截断成读不完的碎片（同样在生产环境实际出现过）。
    """
    hot = _no_story_match(match_id="topical-hot-media")
    hot.media_heat = 24
    hot.trend_signals = [
        {
            "kind": "official-news",
            "source": "ATP官方",
            "title": "This exact headline text must never appear verbatim in the output",
            "url": "https://www.atptour.com/example",
            "published_at": "2026-07-22T12:00:00+00:00",
            "traffic": "",
        }
    ]

    cold = _no_story_match(match_id="topical-cold")
    cold.search_heat = 0

    hot_angle = preview_angle(hot, date(2026, 7, 23))
    assert "话题度" in hot_angle
    assert "This exact headline text" not in hot_angle  # 绝不逐字引用外部标题

    cold_angle = preview_angle(cold, date(2026, 7, 23))
    assert "话题度" not in cold_angle
    assert cold_angle  # 仍然兜底到机械看点，不为空


def test_preview_angle_uses_account_continuity_before_mechanical_facts(tmp_path, monkeypatch):
    """历史相关：这位球员近期是本账号自己的头条时，续写故事线优先于机械看点."""
    monkeypatch.setattr(
        editorial_memory, "STATE_PATH", tmp_path / "editorial_memory.json"
    )
    from tennislive.digest import Digest

    past = make_match(
        home_name="Constant Lestienne", away_name="Someone Else",
        home_country="FRA", match_id="past-lead",
    )
    editorial_memory.record_daily_lead(Digest(today=date(2026, 7, 20), results=[past]))

    upcoming = _no_story_match(match_id="continuity-next")
    angle = preview_angle(upcoming, date(2026, 7, 23))

    assert "7月20日" in angle and "下一章" in angle
