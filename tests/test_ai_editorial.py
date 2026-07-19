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
        round_name="Quarterfinals",
    )
    return Digest(
        today=date(2026, 7, 17),
        results=[result],
        schedule=[scheduled],
        source="espn",
    )


def test_github_models_rewrite_is_applied_from_current_context(monkeypatch):
    digest = _digest()

    def fake_post(*args, **kwargs):
        assert kwargs["json"]["model"] == "openai/gpt-4.1"
        payload = kwargs["json"]["messages"][1]["content"]
        assert "四强席位" in payload
        assert "上一轮" not in payload
        return _Response('{"qf-1":"博尔热斯与达德里争夺四强席位，这场决定谁继续前进。"}')

    monkeypatch.setattr("tennislive.render.ai_editorial.requests.post", fake_post)
    result = enrich_with_github_models(digest, token="test-token")

    assert result.applied == 1
    assert digest.schedule[0].editorial_source == "背景编辑"
    assert "争夺四强席位" in digest.schedule[0].editorial_note


def test_github_models_rejects_numbers_not_present_in_context(monkeypatch):
    digest = _digest()
    monkeypatch.setattr(
        "tennislive.render.ai_editorial.requests.post",
        lambda *args, **kwargs: _Response(
            '{"qf-1":"世界第12的博尔热斯与达德里争夺四强席位。"}'
        ),
    )

    result = enrich_with_github_models(digest, token="test-token")

    assert result.applied == 0
    assert digest.schedule[0].editorial_note is None
