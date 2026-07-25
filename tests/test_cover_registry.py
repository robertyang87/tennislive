"""封面渠道台账：记住哪些渠道真取到过现场图，别在死路上循环。"""

from __future__ import annotations

import json
from datetime import date

from tennislive.research.cover_registry import (
    BARREN_RUN_THRESHOLD,
    barren_channels,
    load_registry,
    proven_channels,
    record_cover_run,
    registry_summary,
    should_widen_search,
)


STOCK = ("wikimedia-commons", "openverse", "bing-web-image")


def _report(
    *,
    status="selected",
    provider="official-match-media",
    queried=STOCK,
    candidates=0,
    errors=(),
    match_id="m1",
    **extra,
):
    return {
        "status": status,
        "provider": provider,
        "match_id": match_id,
        "providers_queried": list(queried),
        "provider_results": {
            name: {
                "candidates": candidates,
                "queries": 4,
                "errors": list(errors),
            }
            for name in queried
        },
        **extra,
    }


def test_selected_channel_accumulates_a_track_record(tmp_path):
    path = tmp_path / "registry.json"
    for day in (22, 23, 24):
        record_cover_run(_report(), today=date(2026, 7, day), path=path)

    records = load_registry(path)
    assert records["official-match-media"].selections == 3
    assert records["official-match-media"].last_selected == "2026-07-24"
    assert proven_channels(path) == ("official-match-media",)


def test_barren_needs_repeated_measured_runs_not_just_appearances(tmp_path):
    """只出现在 providers_queried 里不算证据——那时候还没量过产出。

    2026-07-25 之前的报告没有 provider_results，"被查过"和"查了返回 0 张"
    在文件里长得一模一样。拿它当证据会把没量过的源冤枉成没覆盖。
    """
    path = tmp_path / "registry.json"
    unmeasured = {
        "status": "selected",
        "provider": "official-match-media",
        "match_id": "m1",
        "providers_queried": list(STOCK),
    }
    for day in range(20, 20 + BARREN_RUN_THRESHOLD + 2):
        record_cover_run(dict(unmeasured), today=date(2026, 7, day), path=path)

    assert barren_channels(path) == ()
    assert should_widen_search(STOCK, path) is False

    records = load_registry(path)
    assert records["wikimedia-commons"].runs >= BARREN_RUN_THRESHOLD
    assert records["wikimedia-commons"].measured_runs == 0


def test_repeatedly_empty_channels_trigger_a_wider_search(tmp_path):
    """查了几期、没报错、一张都没有 —— 那就是没覆盖，下一期直接扩渠道。"""
    path = tmp_path / "registry.json"
    for day in range(20, 20 + BARREN_RUN_THRESHOLD):
        record_cover_run(_report(candidates=0), today=date(2026, 7, day), path=path)

    assert set(barren_channels(path)) == set(STOCK)
    assert should_widen_search(STOCK, path) is True


def test_a_channel_that_errors_is_broken_not_barren(tmp_path):
    """报错说明源今天调不通，和"这个源没有这位球员的照片"是两件事。"""
    path = tmp_path / "registry.json"
    for day in range(20, 20 + BARREN_RUN_THRESHOLD + 1):
        record_cover_run(
            _report(candidates=0, errors=("ConnectionError: proxy 403",)),
            today=date(2026, 7, day),
            path=path,
        )

    assert barren_channels(path) == ()
    assert should_widen_search(STOCK, path) is False
    assert load_registry(path)["openverse"].last_error.endswith("proxy 403")


def test_retired_channel_never_counts_as_proven(tmp_path):
    """official-atp-YouTube 中选过一次，但缩略图是宣传拼接图，已停用于封面。"""
    path = tmp_path / "registry.json"
    record_cover_run(
        _report(provider="official-atp-youtube"), today=date(2026, 7, 23), path=path
    )
    assert proven_channels(path) == ("official-atp-youtube",)

    records = load_registry(path)
    records["official-atp-youtube"].retired = True
    from tennislive.research.cover_registry import save_registry

    save_registry(records, path)
    assert proven_channels(path) == ()


def test_same_day_rerun_does_not_count_as_fresh_evidence(tmp_path):
    """改完文案同日重出一版，不该让这几个源看起来又被证伪了一次。

    barren 判定靠的是"连着多少期没货"，一天之内跑三遍并不构成三期证据。
    """
    path = tmp_path / "registry.json"
    for _ in range(3):
        record_cover_run(_report(candidates=0), today=date(2026, 7, 25), path=path)

    records = load_registry(path)
    assert records["wikimedia-commons"].runs == 1
    assert records["wikimedia-commons"].measured_runs == 1
    assert records["official-match-media"].selections == 1
    assert barren_channels(path) == ()

    # 同日重跑换了头条比赛，那是一次新的中选，要记上
    record_cover_run(
        _report(candidates=0, match_id="m2"), today=date(2026, 7, 25), path=path
    )
    assert load_registry(path)["official-match-media"].selections == 2


def test_disabled_run_is_not_recorded(tmp_path):
    """封面抓取被关掉的那一期不该在台账里留下"这个源今天没货"的假证据。"""
    path = tmp_path / "registry.json"
    record_cover_run(
        {"status": "disabled", "providers_queried": list(STOCK)},
        today=date(2026, 7, 25),
        path=path,
    )
    assert load_registry(path) == {}


def test_corrupt_registry_degrades_to_empty_memory(tmp_path):
    """台账坏了要当没有台账，不能把出片流程一起带下去。"""
    path = tmp_path / "registry.json"
    path.write_text("{ not json", encoding="utf-8")
    assert load_registry(path) == {}
    record_cover_run(_report(), today=date(2026, 7, 25), path=path)
    assert proven_channels(path) == ("official-match-media",)


def test_shipped_registry_records_the_channel_that_actually_works():
    """随仓库落库的台账：官方赛报头图是唯一真取到过现场图的渠道。"""
    from tennislive.research.cover_registry import REGISTRY_PATH

    assert REGISTRY_PATH.exists(), "封面渠道台账必须随仓库落库，否则每期从零开始"
    records = load_registry()
    assert records["official-match-media"].selections >= 3
    assert records["official-atp-youtube"].retired is True
    assert "official-match-media" in proven_channels()

    summary = registry_summary()
    assert summary["proven"][0] == "official-match-media"
    assert json.dumps(summary, ensure_ascii=False)  # 报告里要能序列化
