from tennislive.models import MatchStatus
from tennislive.render.venue_assets import venue_asset_for_match

from conftest import make_match


def test_venue_asset_matches_specific_event_alias():
    match = make_match(
        tournament="Generali Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )

    asset = venue_asset_for_match(match)

    assert asset is not None
    assert asset.slug == "kitzbuhel"
    assert asset.image.is_file()
    assert asset.artist and asset.license and asset.source_url


def test_venue_asset_does_not_match_generic_open_name():
    match = make_match(
        tournament="Example Open",
        status=MatchStatus.SCHEDULED,
        winner=None,
        sets=(),
        tiebreaks=(),
    )

    assert venue_asset_for_match(match) is None
