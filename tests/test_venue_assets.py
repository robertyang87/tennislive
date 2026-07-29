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
    city/country 一直是空的，所以按城市写别名永远命不中：罗马那站叫
    "ATV Bancomat Tennis Open"，写 "rome" 没有任何作用；Båstad 那站叫
    "Nordea Open" 同理。
    """
    from tennislive.models import Match, MatchStatus, Player, Tour, Tournament
    from tennislive.render.venue_assets import venue_asset_for_match

    # (赛事名, 期望命中的 slug) —— 全部取自真实 digest 里出现过的写法
    cases = [
        ("Palermo Ladies Open", "palermo"),
        ("Enka Open", "istanbul"),
        ("Unicredit Iasi Open", "iasi"),
        # ATV = Antico Tiro a Volo（罗马），不是 Associazione Tennis Verona
        ("ATV Bancomat Tennis Open", "rome-atv"),
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


def _fetch_tool():
    import importlib.util
    from pathlib import Path

    tool = Path(__file__).resolve().parents[1] / "tools" / "fetch_venues.py"
    spec = importlib.util.spec_from_file_location("fetch_venues", tool)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_credits_point_at_the_file_currently_pinned_in_venues():
    """credits 记的 Commons 文件名，必须就是 VENUES 里钉的那一张。

    换图时最容易漏这一步：旧 credits 字段是齐全的，只是指向上一张图，
    于是不会被 load_venue_assets() 丢弃，而是照常生效并印错署名和许可。
    缺出处只是不显示，错出处是把别人的作品记到另一个人名下。
    加拿大站和法网这次换图就各踩了一次。
    """
    import json

    from tennislive.render.venue_assets import ASSETS, CREDITS

    module = _fetch_tool()
    credits = json.loads(CREDITS.read_text(encoding="utf-8"))

    mismatched = []
    for out_name, pinned_title, _term in module.VENUES:
        if not pinned_title or not (ASSETS / out_name).is_file():
            continue
        recorded = (credits.get(out_name) or {}).get("title")
        if not recorded:
            continue
        if module._norm_title(recorded) != module._norm_title(pinned_title):
            mismatched.append(f"{out_name}: credits={recorded} 但 VENUES 钉的是 {pinned_title}")
    assert not mismatched, "credits 指向了别的文件：\n" + "\n".join(mismatched)


def test_backfill_credits_rewrites_a_stale_entry_not_just_a_missing_one():
    """backfill 要能改掉过期的出处，不只是补空的。

    原来只判断"字段是否齐全"，换图之后旧记录字段齐全、内容全错，直接跳过。
    """
    import json

    module = _fetch_tool()
    calls = []

    def fake_imageinfo(titles):
        calls.append(titles[0])
        return [{
            "title": titles[0], "license": "CC BY-SA 4.0",
            "artist": "New Author", "page": "https://commons.wikimedia.org/wiki/x",
        }]

    module.imageinfo = fake_imageinfo

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "a.jpg").write_bytes(b"x")
        (out / "credits.json").write_text(json.dumps({
            "a.jpg": {
                "title": "File:Old One.jpg", "license": "CC BY 3.0",
                "artist": "Old Author", "page": "https://example.invalid/old",
            }
        }), encoding="utf-8")

        failed = module.backfill_credits(out, [("a.jpg", "File:New One.jpg", None)])

        assert not failed, failed
        assert calls == ["File:New One.jpg"]
        written = json.loads((out / "credits.json").read_text(encoding="utf-8"))
        assert written["a.jpg"]["title"] == "File:New One.jpg"
        assert written["a.jpg"]["artist"] == "New Author"


def test_backfill_credits_leaves_a_matching_entry_alone():
    """名字对得上就别动它——每跑一次都重查 API 是白白撞限流。"""
    import json
    import tempfile
    from pathlib import Path

    module = _fetch_tool()
    calls = []

    def fake_imageinfo(titles):
        calls.append(titles[0])
        return []

    module.imageinfo = fake_imageinfo

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "a.jpg").write_bytes(b"x")
        entry = {
            "title": "File:Same_One.jpg", "license": "CC BY-SA 4.0",
            "artist": "A", "page": "https://commons.wikimedia.org/wiki/x",
        }
        (out / "credits.json").write_text(json.dumps({"a.jpg": entry}), encoding="utf-8")

        # 下划线 / 空格差异不算换图
        failed = module.backfill_credits(out, [("a.jpg", "File:Same One.jpg", None)])

        assert not failed and calls == []
        written = json.loads((out / "credits.json").read_text(encoding="utf-8"))
        assert written["a.jpg"] == entry


def test_official_media_credits_survive_a_fetch_rebuild():
    """官方媒体来源的图，credits 不能被 fetch_set() 冲掉。

    fetch_set() 每次都从零重建 credits.json，只留 VENUES 里认得的条目。
    埃斯托里尔的中央球场来自赛事官网、不在 Commons，如果只把文件放进
    assets/ 而不在 OFFICIAL_VENUES 登记，跑一次 CI 出处就没了——和 umag
    当初丢 credits 是同一个坑。
    """
    import json
    import tempfile
    from pathlib import Path

    module = _fetch_tool()
    assert module.OFFICIAL_VENUES, "OFFICIAL_VENUES 空了？"
    name, credit = next(iter(module.OFFICIAL_VENUES.items()))

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / name).write_bytes(b"x")
        # 盘上那份出处是错的，重建时要以 OFFICIAL_VENUES 为准
        (out / "credits.json").write_text(
            json.dumps({name: {"title": "旧的", "license": "?",
                               "artist": "?", "page": "?"}}), encoding="utf-8")

        failed = module.fetch_set(out, [(name, None, None)], min_width=100)

        assert not failed, failed
        written = json.loads((out / "credits.json").read_text(encoding="utf-8"))
        assert written[name] == credit


def test_official_media_records_source_url_and_marks_licence_unverified():
    """授权不做检索闸门，但来源必须留痕。

    CLAUDE.md：许可名、作者、来源 URL 全程记录（缺失记 unknown / unverified），
    发布前的权利判断由人工检验环节负责。所以官方媒体这一档不许把 license
    编成一个看起来已核实的名字。
    """
    module = _fetch_tool()
    for name, credit in module.OFFICIAL_VENUES.items():
        assert credit["page"].startswith("http"), f"{name} 没记来源 URL"
        assert credit["artist"], f"{name} 没记来源方"
        assert "unverified" in credit["license"], (
            f"{name} 的 license 写成了 {credit['license']!r}——官方媒体这一档"
            "没有经过权利核实，不能写成已核实的样子"
        )


# 还没换到中心球场全景的站点数。**只许降不许升**——加新站时要么带着球场照来，
# 要么明确把这个数字调高，让"又退回地标了"变成一次显式的决定而不是悄悄发生。
LANDMARK_BUDGET = 2


def test_every_venue_declares_what_kind_of_shot_it_is():
    """背景图一律要中心球场全景；还没换到的必须显式挂账，不能沉默。

    这条是用户定的：「背景都要找中心球场全景的照片」。地标（帕特农、竞技场、
    山谷）只能当**临时**兜底，不是终点——而兜底最麻烦的地方是它不报错：
    地点对、画面还挺好看，扫过去不觉得有什么不对，直到有人问一句"为啥不用
    中心球场"（洛斯卡沃斯和孟菲斯就各这样待了好几版）。

    所以每条都要声明 shot，非 centre-court 的必须写清楚卡在哪儿，并且总数
    只许降不许升。
    """
    import json

    from tennislive.render.venue_assets import MANIFEST

    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = [
        f"{row.get('slug')}: shot 只能是 centre-court / landmark，现在是 {row.get('shot')!r}"
        for row in rows if row.get("shot") not in {"centre-court", "landmark"}
    ]
    problems += [
        f"{row.get('slug')}: 还是地标，但没写 todo（卡在哪儿）"
        for row in rows if row.get("shot") == "landmark" and not row.get("todo")
    ]
    assert not problems, "\n".join(problems)

    pending = sorted(r["slug"] for r in rows if r["shot"] != "centre-court")
    assert len(pending) <= LANDMARK_BUDGET, (
        f"待换成中心球场的站点从 {LANDMARK_BUDGET} 涨到了 {len(pending)}：{pending}。"
        "新站要带着球场照来；确实拿不到就显式调高 LANDMARK_BUDGET 并说明原因"
    )


def test_sites_with_a_real_court_photo_do_not_fall_back_to_a_landmark():
    """能拿到球场照的站，manifest 不许再指回城市地标。

    地标本身是合法的兜底——伊斯坦布尔的老城眼下确实还
    没找到能用的球场照。但**兜底一旦生效就很难
    发现它已经过期了**：洛斯卡沃斯用埃尔阿尔科海蚀拱用了好几版，画面漂亮、
    地点也对，只是它不是球场；直到有人问"为啥不用中心球场"才发现赛事官网
    自己的媒体库里一直挂着 Estadio Alejandro Burillo 的实拍。

    所以把"已经找到球场照"这件事钉下来。这两站的图都不在 Commons，来自赛事
    官方媒体库，而 VENUES 里 pinned 字段是 None——也就是说 fetch_venues.py
    重跑时不会去 Commons 重取，唯一能把它换掉的是有人改 manifest。这条测试
    就是那时候会响的铃。
    """
    import json

    from tennislive.render.venue_assets import ASSETS, MANIFEST

    # slug -> 必须仍然是这张球场照（换成别的球场照请连同理由一起改这里）
    court_photos = {
        "los-cabos": "los-cabos-estadio-alejandro-burillo.jpg",
        "memphis": "memphis-leftwich-stadium-court.jpg",
        # 汉堡这张来自 Commons，但同样容易被换回去：关键词搜索翻不到它
        # （标题里一个相关词都没有，是按 Category:Am Rothenbaum 列出来的）
        "hamburg": "hamburg-rothenbaum-centre-court.jpg",
        # 格施塔德这张藏在官网 sitemap 列出的 /infos/le-village-le-stade/ 里
        # ——wp-json 被 401 挡着，按关键词也搜不到（文件名是 EFG-SOG23-3）
        "gstaad": "gstaad-roy-emerson-arena.jpg",
        # 雅典钉住的理由不是构图，是**赛事本身容易搞错**：manifest 这条对的是
        # WTA 250 的 Athens Open（7 月、露天、Olympic Tennis Centre），
        # 不是 ATP 的 Hellenic Championship（11 月、室内、Telekom Center）。
        # 我已经在这上面栽过一次，钉住免得第二次
        "athens": "athens-olympic-tennis-centre.jpg",
    }
    rows = {row["slug"]: row for row in json.loads(MANIFEST.read_text(encoding="utf-8"))}

    problems = []
    for slug, image in court_photos.items():
        row = rows.get(slug)
        if row is None:
            problems.append(f"{slug}: manifest 里整条不见了")
        elif row.get("image") != image:
            problems.append(f"{slug}: 现在指的是 {row.get('image')}，应为球场照 {image}")
        elif not (ASSETS / image).is_file():
            problems.append(f"{slug}: {image} 不在盘上")
    assert not problems, "球场照被换回地标或丢了：\n" + "\n".join(problems)


def test_backfill_drops_credits_for_images_no_longer_on_disk():
    """图删掉之后，它的 credits 也要清掉。

    换站名（estoril-coast → estoril-centre-court）后旧条目会指着一个不存在的
    文件。它不印错什么，但会破坏"每个 credits 条目都在 VENUES 里登记"这条
    不变量，下次真有图漏登记时反而看不出来。
    """
    import json
    import tempfile
    from pathlib import Path

    module = _fetch_tool()
    module.imageinfo = lambda titles: []

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "here.jpg").write_bytes(b"x")
        entry = {"title": "File:Here.jpg", "license": "CC0", "artist": "A",
                 "page": "https://commons.wikimedia.org/wiki/File:Here.jpg"}
        (out / "credits.json").write_text(json.dumps({
            "here.jpg": entry,
            "gone.jpg": {"title": "File:Gone.jpg", "license": "CC0",
                         "artist": "B", "page": "https://example.invalid/gone"},
        }), encoding="utf-8")

        module.backfill_credits(out, [("here.jpg", "File:Here.jpg", None)])

        written = json.loads((out / "credits.json").read_text(encoding="utf-8"))
        assert set(written) == {"here.jpg"}
        assert written["here.jpg"] == entry


def test_attribution_md_is_generated_from_credits():
    """署名页要和 credits.json 逐字一致——手写的那一版一定会过期。

    换图时 credits.json 有好几条测试盯着，`ATTRIBUTION.md` 一条都没有，
    于是它悄悄留下了三条指向早就删掉的文件的记录（kitzbuhel-panorama /
    prague-castle-panorama / estoril-coast）——署名页写着三张不存在的图的
    作者和许可，而真正在用的那几张一个字都没有。

    这和「换文件名要 grep 整个仓库包括 .md」是同一个毛病，只是靠人记住挡不住
    第四次。现在这个 .md 由 render_attribution() 生成，这条测试是那把锁：
    改了图就重跑 `python tools/fetch_venues.py`，或直接调 write_attribution()。
    """
    from tennislive.render.venue_assets import ASSETS, CREDITS
    import json

    module = _fetch_tool()
    credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    on_disk = {p.name for p in ASSETS.glob("*.jpg")} | {p.name for p in ASSETS.glob("*.png")}
    expected = module.render_attribution(credits, on_disk)
    actual = (ASSETS / "ATTRIBUTION.md").read_text(encoding="utf-8")

    assert actual == expected, (
        "ATTRIBUTION.md 和 credits.json 对不上了。它是生成的，不要手改——"
        "跑 tools/fetch_venues.py，或 write_attribution(assets/venues)"
    )


def test_attribution_md_never_credits_a_file_that_is_gone():
    """署名页里不许出现盘上没有的文件。

    上一条已经能挡住绝大部分，但它比的是"和生成器一致"；万一生成器本身被改
    坏（比如不再按 on_disk 过滤），这条仍然会响。**错的出处比没有出处更糟**：
    它把某个人的作品记在一张根本没发出去的图上。
    """
    import re

    from tennislive.render.venue_assets import ASSETS

    text = (ASSETS / "ATTRIBUTION.md").read_text(encoding="utf-8")
    named = re.findall(r"^## `([^`]+)`", text, flags=re.M)
    assert named, "署名页一条记录都没有？"
    missing = [n for n in named if not (ASSETS / n).is_file()]
    assert not missing, f"署名页记着这些图，但它们已经不在盘上：{missing}"


def test_canada_picks_the_city_that_actually_hosts_that_tour_that_year():
    """加拿大站一个赛事名、两座城市，男女每年互换——挑错就在卡上印错城市。

    2025 年男子在多伦多、女子在蒙特利尔；2026 年反过来。只按赛事名匹配的话
    两条都命中，`max()` 随便挑一条，就有一半的概率印错。和「ATV Bancomat
    印成维罗纳」是同一类错，区别是**这个错每年会自己翻面**，靠人肉盯不住。
    """
    from datetime import datetime, timezone

    from tennislive.models import Match, MatchStatus, Player, Tour, Tournament
    from tennislive.render.venue_assets import venue_asset_for_match

    def _match(tour: Tour, year: int | None):
        return Match(
            match_id="x", tour=tour,
            tournament=Tournament(name="National Bank Open presented by Rogers", tour=tour),
            home=[Player(name="A")], away=[Player(name="B")],
            status=MatchStatus.SCHEDULED, round_name="R32", discipline="Singles",
            start_utc=None if year is None else datetime(year, 8, 5, tzinfo=timezone.utc),
            sets=[], winner=None,
        )

    cases = [
        (Tour.ATP, 2026, "canada-montreal"),
        (Tour.WTA, 2026, "canada-toronto"),
        (Tour.ATP, 2025, "canada-toronto"),
        (Tour.WTA, 2025, "canada-montreal"),
    ]
    wrong = []
    for tour, year, expected in cases:
        got = venue_asset_for_match(_match(tour, year))
        if got is None or got.slug != expected:
            wrong.append(f"{tour.value} {year} -> {got.slug if got else None}（应为 {expected}）")
    assert not wrong, "加拿大挑错城市：\n" + "\n".join(wrong)

    # 拿不到年份时**宁可不给图**：卡上的 location 是要印出来的，
    # 印错城市比没有背景图糟。
    assert venue_asset_for_match(_match(Tour.ATP, None)) is None
