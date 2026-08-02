from tennislive.zh import country_flag, country_zh, player_zh
from tennislive.zh.terms import discipline_zh, round_zh
from tennislive.zh.tournaments import (
    tournament_level,
    tournament_surface,
    tournament_zh,
)


def test_player_full_name():
    assert player_zh("Jannik Sinner") == "辛纳"
    assert player_zh("Qinwen Zheng") == "郑钦文"


def test_player_three_token_espn_format():
    """ESPN 把她的名字拆成三段（姓 Ye + 名 Qiu/Yu 各一段），曾无法命中译名表."""
    assert player_zh("Ye Qiu Yu") == "叶秋语"


def test_player_abbreviated():
    assert player_zh("J. Sinner") == "辛纳"
    assert player_zh("Sinner J.") == "辛纳"
    assert player_zh("Shuo Feng") == "冯硕"
    assert player_zh("F. Shuo") == "冯硕"


def test_player_unknown_passthrough():
    assert player_zh("Totally Unknown") == "Totally Unknown"


def test_round_zh():
    assert round_zh("Semifinals") == "半决赛"
    assert round_zh("Round of 16") == "16强赛"
    assert round_zh("Final") == "决赛"
    assert round_zh("SF") == "半决赛"
    assert round_zh("Men's Singles - Round of 16") == "16强赛"


def test_discipline_zh():
    assert discipline_zh("Men's Singles") == "男单"
    assert discipline_zh("Women's Doubles") == "女双"


def test_tournament_zh():
    assert tournament_zh("Wimbledon") == "温布尔登网球锦标赛"
    assert tournament_zh("Mutua Madrid Open") == "马德里公开赛"


def test_tournament_level_by_tour():
    assert tournament_level("Miami Open", "ATP") == "M1000"
    assert tournament_level("Miami Open", "WTA") == "W1000"
    assert tournament_level("Wimbledon", "ATP") == "GS"
    assert tournament_level("Millennium Estoril Open", "ATP") == "ATP250"
    assert tournament_level("Estoril Open", "ATP") == "ATP250"
    assert tournament_level("Palermo", "WTA") == "WTA125"


def test_memphis_classic_is_a_recognized_wta_250():
    """未映射级别的赛事会被整站静默丢出日报（2026-07-25 生产事故）.

    "The Memphis Classic" 当天有 10 场正赛首轮（含王曦雨），但 ESPN 不提供级别，
    本地映射表又没有这个键，级别解析成 None 后 is_tour_focus_match() 直接判否，
    整站连同中国球员的比赛一起从赛程预告里消失，只在 coverage.txt 留下一行
    "待识别赛事"。这是 2026 年重回巡回赛日程的 WTA 250。
    """
    from tennislive.render.rating import TOUR_FOCUS_LEVELS

    assert tournament_level("The Memphis Classic", "WTA") == "WTA250"
    assert tournament_level("The Memphis Classic", "WTA") in TOUR_FOCUS_LEVELS
    assert tournament_zh("The Memphis Classic") == "孟菲斯精英赛"
    # 键用全名而不是 "memphis"：历史上孟菲斯办过 ATP 站，宽泛的键会误伤。
    assert tournament_level("Memphis Open", "ATP") is None


def test_tournament_surface_official_fallbacks():
    assert tournament_surface("Livesport Prague Open") == "Hard"
    assert tournament_surface("MSC Hamburg Ladies Open") == "Clay"
    assert tournament_surface("Generali Open") == "Clay"
    assert tournament_surface("Millennium Estoril Open") == "Clay"
    assert tournament_surface("Wimbledon") == "Grass"


def test_country():
    assert country_zh("SRB") == "塞尔维亚"
    assert country_zh("Italy") == "意大利"
    assert country_flag("CHN") == "🇨🇳"
    assert country_flag("GER") == "🇩🇪"
    assert country_flag("RS") == "🇷🇸"
    assert country_flag("TPE") == ""  # 中华台北不显示旗帜


def test_冠名商在前的赛事名也要认得出级别():
    """**「赛事级别的别名也要按赛事名写」，这一条又中了一次。**

    2026-07-31 那条 daily 的质检报了两站「整站 N 场未收录」，其中温哥华那站
    **含中国球员逯佳境**（run 30623978939）：

        [WARN] 赛事级别未映射，整站 26 场未收录: Odlum Brown VanOpen（含中国球员 逯佳境）
        [WARN] 赛事级别未映射，整站 14 场未收录: Axeria Open 2026 powered by Intaro Sport

    形状和洛斯卡沃斯那次是**反过来的**：那次表里记的是城市名 `los cabos`、
    feed 给的是冠名全名；这次这两站的 feed 名里**一个城市字都没有**——
    `Odlum Brown` 是券商，`AXERIA` / `INTARO` 是保险和体育营销公司。

    级别都由 WTA 官网自证，不是看名字猜的：

    - `wtatennis.com/tournaments/2064/vancouver-125/2026`（与 ATP Challenger 125 合办）
    - `wtatennis.com/tournaments/1163/targu-mures-125/2026`

    ⚠️ 顺带记一条自己的错：我按 `Axeria` 猜它在里昂，查出来是**罗马尼亚的
    特尔古穆列什**。「非空 ≠ 对题」，赛事名同理——猜地点要查。
    """
    from tennislive.zh.tournaments import tournament_level

    for name in ("Odlum Brown VanOpen", "Odlum Brown Vancouver Open",
                 "AXERIA Open 2026 powered by INTARO Sport"):
        assert tournament_level(name, "WTA") == "WTA125", (
            f"{name} 的级别又认不出来了——整站会被当成非巡回赛级别丢掉")

    # ATP 那半边**故意**留空：温哥华的男子赛事是 Challenger，而这个词表里
    # 没有 Challenger 的码位（`atp_token` 只认 M1000 和纯数字）。写 "125"
    # 会解析成 `ATP125`——一个 ATP 巡回赛并不存在的级别。
    # **宁可留着那半边的警告，也别造一个假级别。**
    assert tournament_level("Odlum Brown VanOpen", "ATP") is None, (
        "给 Challenger 编了个 ATP 级别码？那是在制造一个不存在的级别；"
        "要收 Challenger 就先给词表加一个真的 Challenger 码位")


def test_WTA125不在日报的收录门槛里():
    """**映射上了不等于收进日报。** 这两件事一天之内差点被我混为一谈。

    `_unmapped_tournament_warnings` 的措辞是「未映射，整站 N 场未收录」，
    读起来像「映射上就收录了」——不是。日报的门槛是 `TOUR_FOCUS_LEVELS`，
    只有 250 及以上；WTA125 映射之后照样在门外。

    所以这条钉住两件事各归各：**警告消失 ≠ 内容进来了**。真要让 125 站里的
    中国球员进日报，那是改门槛（口径选择），不是补映射表。
    """
    from tennislive.render.rating import LEVEL_PTS, TOUR_FOCUS_LEVELS

    assert "WTA125" not in TOUR_FOCUS_LEVELS, (
        "WTA125 进了收录门槛？那是口径变了，得先确认这是有意的")
    assert "WTA125" not in LEVEL_PTS
    # 门槛本身别被顺手改窄了
    assert {"GS", "M1000", "W1000", "ATP250", "WTA250"} <= TOUR_FOCUS_LEVELS
