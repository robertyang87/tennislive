import pytest

from tools import fetch_match_stats_fs as stats


def _body(home: str = "", away: str = "", mid: str = "x") -> str:
    if not home and not away:
        return ""
    return f"~AA÷{mid}¬AE÷{home}¬AF÷{away}¬"


def test_find_match三天没命中会继续回看一周(monkeypatch):
    calls = []

    def fake_feed(name: str) -> str:
        offset = int(name.split("_")[2])
        calls.append(offset)
        if offset == -4:
            return _body("Medvedev D.", "Damm M.", "abc123")
        return _body("Other A.", "Player B.", str(offset))

    monkeypatch.setattr(stats, "feed", fake_feed)
    assert stats.find_match(["medvedev", "damm"]) == (
        "abc123", "Medvedev D.", "Damm M.")
    assert set(calls[:3]) == {-1, 0, 1}, "快做场次仍要先走常见三页，别平白拖慢"
    assert -4 in calls, "三页没命中后必须继续回看，不能直接把旧集锦判成无比赛"


def test_find_match单页坏了继续找但全部坏要明确报源站故障(monkeypatch):
    def partly_broken(name: str) -> str:
        offset = int(name.split("_")[2])
        if offset == -1:
            raise stats.StatsError("timeout")
        return _body("Medvedev D.", "Damm M.", "ok")

    monkeypatch.setattr(stats, "feed", partly_broken)
    assert stats.find_match(["medvedev", "damm"], offsets=(-1, 0))[0] == "ok"

    monkeypatch.setattr(stats, "feed", lambda name: (_ for _ in ()).throw(
        stats.StatsError("timeout")))
    with pytest.raises(stats.StatsError, match="全部读取失败"):
        stats.find_match(["medvedev", "damm"], offsets=(-1, 0))
