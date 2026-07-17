from datetime import date

from conftest import make_match


class _Source:
    def __init__(self, name, matches):
        self.name = name
        self.matches = matches

    def fetch_day(self, _date):
        return self.matches


def test_fetch_day_aggregates_and_dedupes(monkeypatch):
    import tennislive.sources as sources

    espn_match = make_match(match_id="espn-1")
    espn_match.home[0].headshot_url = "https://example.com/player.png"
    sofa_match = make_match(match_id="sofa-99")
    sofa_match.home[0].rank = 3
    extra = make_match(
        home_name="Carlos Alcaraz",
        away_name="Alexander Zverev",
        match_id="sofa-extra",
    )
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _Source("espn", [espn_match]),
            _Source("sofascore", [sofa_match, extra]),
        ],
    )

    day = sources.fetch_day(date(2026, 7, 16))

    assert day.source == "espn+sofascore"
    assert day.source_status == {
        "espn": "正常 · 1 场",
        "sofascore": "正常 · 2 场",
    }
    assert len(day.matches) == 2
    sinner = next(m for m in day.matches if m.home[0].name == "Jannik Sinner")
    assert sinner.home[0].headshot_url
    assert sinner.home[0].rank == 3


def test_fetch_day_merges_reversed_full_name_order(monkeypatch):
    import tennislive.sources as sources

    official = make_match(
        home_name="Barbora Krejcikova",
        away_name="Qinwen Zheng",
        match_id="wta:1175:LS005",
    )
    official.tournament.name = "ATHENS"
    official.tournament.level = "WTA250"
    backup = make_match(
        home_name="Barbora Krejcikova",
        away_name="Zheng Qinwen",
        match_id="espn-2",
    )
    backup.tournament.name = "Vanda Pharmaceuticals Athens Open"
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _Source("wta-official", [official]),
            _Source("espn", [backup]),
        ],
    )

    day = sources.fetch_day(date(2026, 7, 16))

    assert len(day.matches) == 1
    assert day.matches[0].tournament.name == "Vanda Pharmaceuticals Athens Open"
    assert day.matches[0].tournament.level == "WTA250"


def test_fetch_day_merges_optional_middle_name(monkeypatch):
    import tennislive.sources as sources

    official = make_match(
        home_name="Eudice Chong",
        away_name="Madeleine Brooks",
        match_id="wta:1175:LD005",
    )
    official.tournament.name = "ATHENS"
    official.tournament.level = "WTA250"
    backup = make_match(
        home_name="Eudice Wong Chong",
        away_name="Madeleine Brooks",
        match_id="espn-middle-name",
    )
    backup.tournament.name = "Vanda Pharmaceuticals Athens Open"
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _Source("wta-official", [official]),
            _Source("espn", [backup]),
        ],
    )

    day = sources.fetch_day(date(2026, 7, 16))

    assert len(day.matches) == 1
    assert day.matches[0].tournament.name == "Vanda Pharmaceuticals Athens Open"
    assert day.matches[0].tournament.level == "WTA250"
