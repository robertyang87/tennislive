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
