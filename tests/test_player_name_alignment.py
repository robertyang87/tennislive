"""Guard cross-table consistency and persistence through a real offline refresh."""
from tools.audit_player_name_alignment import audit_refresh, audit_repository, audit_tables
from tools.update_player_names import build_review_queue


def test_repository_player_names_survive_next_offline_refresh():
    errors, _warnings = audit_repository()
    assert not errors, "\n".join(errors)


def _snapshot():
    return {"ranking_date": "fixture", "tours": {"ATP": [
        {"rank": 1, "name_en": "Gaël Monfils", "name_zh": "孟菲尔斯",
         "translation_source": "machine-transliteration"}], "WTA": []}}


def test_conflicting_accent_alias_and_user_facing_lookup_are_detected():
    snapshot = _snapshot()
    errors = audit_tables(snapshot, {"entries": {}}, {"Gael Monfils": "错误译名"},
                          build_review_queue(snapshot), lambda _: "孟菲尔斯")
    assert any("conflicting names" in error for error in errors)
    assert any("lookup mismatch" in error for error in errors)


def test_missing_provisional_review_is_detected():
    snapshot = _snapshot()
    queue = build_review_queue(snapshot)
    assert queue["entries"], "fixture must exercise the provisional queue"
    queue["entries"] = []
    errors = audit_tables(snapshot, {"entries": {}}, {}, queue, lambda _: "孟菲尔斯")
    assert any("review queue differs" in error for error in errors)


def test_refresh_name_drift_fails_but_source_upgrade_is_informational():
    before = _snapshot()
    after = _snapshot()
    after["tours"]["ATP"][0]["translation_source"] = "新华社"
    errors, warnings = audit_refresh(before, after)
    assert not errors and warnings
    after["tours"]["ATP"][0]["name_zh"] = "错误译名"
    errors, _ = audit_refresh(before, after)
    assert errors


def test_feed_accent_and_curly_apostrophe_aliases_match_refresh_keys():
    from tennislive.zh import player_zh
    from tools.update_player_names import _normalize

    assert player_zh("Gaël Monfils") == player_zh("Gael Monfils") == "孟菲尔斯"
    assert player_zh("Christopher O’Connell") == player_zh("Christopher O'Connell") == "奥康奈尔"
    assert _normalize("Gaël Monfils") == _normalize("Gael Monfils")
    assert _normalize("Christopher O’Connell") == _normalize("Christopher O'Connell")


def test_controlled_override_survives_curated_dictionary_and_enters_queue(tmp_path, monkeypatch):
    import json
    from tools import update_player_names as sync

    previous = tmp_path / "snapshot.json"
    overrides = tmp_path / "overrides.json"
    previous.write_text(json.dumps({"tours": {"ATP": [{
        "name_en": "Gaël Monfils", "name_zh": "旧译名",
        "translation_source": "curated-media"}], "WTA": []}}), encoding="utf-8")
    overrides.write_text(json.dumps({"entries": {"Gael Monfils": {
        "zh": "孟菲尔斯", "source": "受控音译人工校订", "source_url": ""}}}), encoding="utf-8")
    monkeypatch.setattr(sync, "OUTPUT", previous)
    monkeypatch.setattr(sync, "OVERRIDES", overrides)
    monkeypatch.setattr(sync, "PLAYER_ZH", {"Gael Monfils": "旧译名"})
    monkeypatch.setattr(sync, "RANKING_LIMIT", 1)
    rows = [sync.RankedName("ATP", 1, "Gaël Monfils", "Monfils")]
    women = [sync.RankedName("WTA", 1, "Gael Monfils", "Monfils")]
    rebuilt = sync.build_snapshot(rows, women, ranking_date="fixture", allow_machine=False)
    for entries in rebuilt["tours"].values():
        assert entries[0]["name_zh"] == "孟菲尔斯"
        assert entries[0]["translation_source"] == "受控音译人工校订"
    assert len(sync.build_review_queue(rebuilt)["entries"]) == 2


def test_legacy_cctv_evidence_outweighs_controlled_and_encyclopedia_sources():
    from tools.update_player_names import _store_translation

    lookup = {}
    _store_translation(lookup, "Gael Monfils", ("孟菲尔斯", "央视网", "https://sports.cntv.cn/example"))
    _store_translation(lookup, "Gaël Monfils", ("旧译名", "受控音译人工校订", ""))
    _store_translation(lookup, "Gael Monfils", ("旧译名", "中文百科", "https://zh.wikipedia.org/example"))
    assert len(lookup) == 1
    assert next(iter(lookup.values()))[0] == "孟菲尔斯"
