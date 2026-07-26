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


def test_every_manifest_entry_actually_loads():
    """manifest 里登记的每一条都必须真的加载出来。

    load_venue_assets() 对"文件不在"和"credits 缺字段"是**静默丢弃**的——
    澳网/法网/温网三张主球场图连同 credits 早就在仓库里，只因为没登记进
    manifest 就一直没人发现；反过来，登记了但文件掉了同样不会有任何动静。
    这条测试把不合格的逐条列出来，不让它继续沉默。
    """
    import json

    from tennislive.render.venue_assets import ASSETS, CREDITS, MANIFEST
    from tennislive.render.venue_assets import load_venue_assets

    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    loaded = {asset.slug for asset in load_venue_assets()}

    problems = []
    for row in rows:
        slug, image = row.get("slug"), row.get("image") or ""
        if slug in loaded:
            continue
        reasons = []
        if not (ASSETS / image).is_file():
            reasons.append("图片文件不在")
        missing = [k for k in ("artist", "license", "page")
                   if not (credits.get(image) or {}).get(k)]
        if missing:
            reasons.append(f"credits 缺 {missing}")
        if not [a for a in row.get("tournament_aliases", ()) if len(a) >= 4]:
            reasons.append("没有长度 >=4 的别名")
        problems.append(f"{slug} ({image}): {'; '.join(reasons) or '原因不明'}")

    assert not problems, "manifest 条目没能加载：\n" + "\n".join(problems)


def test_aliases_match_the_real_tournament_names():
    """别名要对着**赛事名**写——真实数据里 city/country 恒为 None。

    匹配用的 subject 是 _norm("赛事名 城市 国家")，而抓下来的赛程里
    city/country 一直是空的，所以按城市写别名永远命不中：维罗纳那站叫
    "ATV Bancomat Tennis Open"，写 "verona" 没有任何作用；Båstad 那站叫
    "Nordea Open" 同理。
    """
    from tennislive.models import Match, MatchStatus, Player, Tour, Tournament
    from tennislive.render.venue_assets import venue_asset_for_match

    # (赛事名, 期望命中的 slug) —— 全部取自真实 digest 里出现过的写法
    cases = [
        ("Palermo Ladies Open", "palermo"),
        ("Enka Open", "istanbul"),
        ("Unicredit Iasi Open", "iasi"),
        ("ATV Bancomat Tennis Open", "verona"),
        ("EFG Swiss Open Gstaad", "gstaad"),
        ("Nordea Open", "bastad"),
        ("Australian Open", "australian-open"),
        ("Roland Garros", "roland-garros"),
        ("French Open", "roland-garros"),
        ("Wimbledon", "wimbledon"),
        ("The Championships, Wimbledon", "wimbledon"),
    ]
    from tennislive.render.venue_assets import load_venue_assets

    available = {asset.slug for asset in load_venue_assets()}

    misses = []
    for name, expected in cases:
        if expected not in available:
            continue  # 该站的图还没入库，另有测试盯着
        match = Match(
            match_id="x", tour=Tour.ATP,
            # city/country 留空，复刻真实数据的样子
            tournament=Tournament(name=name, tour=Tour.ATP),
            home=[Player(name="A")], away=[Player(name="B")],
            status=MatchStatus.SCHEDULED, round_name="R32",
            discipline="Men's Singles", start_utc=None, sets=[], winner=None,
        )
        got = venue_asset_for_match(match)
        if got is None or got.slug != expected:
            misses.append(f"{name} -> {got.slug if got else None}（应为 {expected}）")
    assert not misses, "别名没命中：\n" + "\n".join(misses)


def test_fetch_tool_registers_every_credited_asset():
    """credits.json 里的每个文件都要在 fetch_venues.VENUES 里登记。

    fetch_set() 会按 VENUES 重建 credits.json，没登记的条目每跑一次 CI 就被
    冲掉一次——umag 的图正在 manifest 里生效，credits 一丢它就整条消失。
    """
    import importlib.util
    import json
    from pathlib import Path

    from tennislive.render.venue_assets import CREDITS

    tool = Path(__file__).resolve().parents[1] / "tools" / "fetch_venues.py"
    spec = importlib.util.spec_from_file_location("fetch_venues", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    registered = {name for name, _pinned, _term in module.VENUES}
    credited = set(json.loads(CREDITS.read_text(encoding="utf-8")))
    orphans = sorted(credited - registered)
    assert not orphans, f"这些图有 credits 但没在 VENUES 里登记，会被冲掉：{orphans}"
