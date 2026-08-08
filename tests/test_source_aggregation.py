from datetime import date

from conftest import make_match
from tennislive.sources.base import SourceError


class _Source:
    def __init__(self, name, matches):
        self.name = name
        self.matches = matches

    def fetch_day(self, _date):
        return self.matches


class _FailingSource:
    def __init__(self, name, message="failed"):
        self.name = name
        self.message = message

    def fetch_day(self, _date):
        raise SourceError(self.message)


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
    assert sinner.data_sources == ["espn", "sofascore"]
    assert sinner.schedule_time_status == "cross-verified"


def test_fetch_day_marks_conflicting_times(monkeypatch):
    from datetime import timedelta

    import tennislive.sources as sources

    espn_match = make_match(match_id="espn-1")
    sofa_match = make_match(
        match_id="sofa-1", start_utc=espn_match.start_utc + timedelta(hours=2)
    )
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _Source("espn", [espn_match]),
            _Source("sofascore", [sofa_match]),
        ],
    )

    day = sources.fetch_day(date(2026, 7, 16))

    assert len(day.matches) == 1
    assert day.matches[0].schedule_time_status == "conflict"
    assert set(day.matches[0].time_observations) == {"espn", "sofascore"}


def test_fetch_day_merges_missing_time_with_backup_time(monkeypatch):
    import tennislive.sources as sources

    no_time = make_match(match_id="espn-1", start_utc=None)
    with_time = make_match(match_id="sofa-1")
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _Source("espn", [no_time]),
            _Source("sofascore", [with_time]),
        ],
    )

    day = sources.fetch_day(date(2026, 7, 16))

    assert len(day.matches) == 1
    assert day.matches[0].start_utc == with_time.start_utc
    assert day.matches[0].schedule_time_status == "single-source"


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


def test_fetch_day_falls_back_to_tnns_tier_only_when_regular_chain_is_wiped_out(
    monkeypatch,
):
    """常规链（ESPN/SofaScore/Flashscore/WtaLive）全灭，才轮到 TNNS 那一档.

    这正是账号所有者要的场景（"不能把鸡蛋都放一个篮子，如果前面都失败"）：
    `make_fallback_chain` 只有在 `used_sources` 空的时候才会被调用——
    `TnnsSource` 要真开浏览器过 Cloudflare 挑战，一次 25~30 秒，不能让
    每一次 `fetch_day()` 都背上这个代价。
    """
    import tennislive.sources as sources

    fallback_match = make_match(match_id="tnns-1")
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _FailingSource("espn"),
            _FailingSource("sofascore"),
            _FailingSource("flashscore"),
            _FailingSource("wta-live"),
        ],
    )
    monkeypatch.setattr(
        sources,
        "make_fallback_chain",
        lambda: [_Source("tnns", [fallback_match])],
    )

    day = sources.fetch_day(date(2026, 7, 16))

    assert day.source == "tnns"
    assert len(day.matches) == 1
    assert day.matches[0].match_id == "tnns-1"


def test_fetch_day_never_calls_fallback_tier_when_a_regular_source_succeeds(
    monkeypatch,
):
    """常规链只要有一个成功，就不该付 TNNS 那三十秒的代价."""
    import tennislive.sources as sources

    espn_match = make_match(match_id="espn-1")
    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [
            _Source("espn", [espn_match]),
            _FailingSource("sofascore"),
        ],
    )

    def _boom():
        raise AssertionError("常规链有源成功时不该调用 make_fallback_chain")

    monkeypatch.setattr(sources, "make_fallback_chain", _boom)

    day = sources.fetch_day(date(2026, 7, 16))

    assert day.source == "espn"
    assert len(day.matches) == 1


def test_fetch_day_raises_when_both_tiers_are_wiped_out(monkeypatch):
    import tennislive.sources as sources

    monkeypatch.setattr(
        sources,
        "make_source_chain",
        lambda _prefer=None: [_FailingSource("espn", "网络超时")],
    )
    monkeypatch.setattr(
        sources,
        "make_fallback_chain",
        lambda: [_FailingSource("tnns", "Cloudflare 挑战没过")],
    )

    try:
        sources.fetch_day(date(2026, 7, 16))
        raise AssertionError("两档都失败时应该抛 SourceError")
    except SourceError as exc:
        assert "espn" in str(exc)
        assert "tnns" in str(exc)
