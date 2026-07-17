from datetime import date, datetime, timezone

from tennislive.digest import Digest
from tennislive.models import MatchStatus
from tennislive.render.ai_editorial import enrich_with_github_models

from conftest import make_match


class _Response:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _digest():
    result = make_match(
        home_name="Nuno Borges",
        away_name="Grigor Dimitrov",
        tournament="Nordea Open",
        sets=((6, 2), (6, 3)),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 16, 12, tzinfo=timezone.utc),
    )
    scheduled = make_match(
        home_name="Nuno Borges",
        away_name="Luciano Darderi",
        tournament="Nordea Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
        start_utc=datetime(2026, 7, 17, 12, tzinfo=timezone.utc),
        match_id="qf-1",
    )
    return Digest(
        today=date(2026, 7, 17),
        results=[result],
        schedule=[scheduled],
        source="espn",
    )


def test_github_models_rewrite_is_applied_from_existing_evidence(monkeypatch):
    digest = _digest()

    def fake_post(*args, **kwargs):
        assert kwargs["json"]["model"] == "openai/gpt-4.1"
        return _Response('{"qf-1":"博尔热斯上一轮直落两盘，仅丢5局，状态更利落。"}')

    monkeypatch.setattr("tennislive.render.ai_editorial.requests.post", fake_post)
    result = enrich_with_github_models(digest, token="test-token")

    assert result.applied == 1
    assert digest.schedule[0].editorial_source == "数据编辑"
    assert "直落两盘" in digest.schedule[0].editorial_note


def test_github_models_rejects_numbers_not_present_in_evidence(monkeypatch):
    digest = _digest()
    monkeypatch.setattr(
        "tennislive.render.ai_editorial.requests.post",
        lambda *args, **kwargs: _Response(
            '{"qf-1":"博尔热斯上一轮轰出12记Ace，发球表现非常强势。"}'
        ),
    )

    result = enrich_with_github_models(digest, token="test-token")

    assert result.applied == 0
    assert digest.schedule[0].editorial_note is None
