"""Guard cross-table consistency and persistence through a real offline refresh."""
from tools.audit_player_name_alignment import (
    audit_refresh,
    audit_repository,
    audit_tables,
)
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


def _review_ledger():
    return {"entries": [{"name_en": "Gael Monfils", "before_zh": "孟菲尔斯",
                         "name_zh": "孟菲尔斯", "changed": False,
                         "status": "verified-media", "evidence": [{
                             "source": "央视网", "source_url": "https://sports.cctv.com/example.shtml",
                             "evidence": "法国网球选手孟菲尔斯晋级。", "source_type": "article-body"}]}]}


def test_review_ledger_without_source_cannot_claim_verified():
    from tools.audit_player_name_alignment import audit_review_records

    ledger = _review_ledger()
    assert not audit_review_records(ledger, lambda _: "孟菲尔斯")
    row = ledger["entries"][0]
    for evidence in ([], [{"evidence": "孟菲尔斯"}], [{"source_url": "https://sports.cctv.com/example.shtml"}],
                     [{"source_url": "https://sports.cctv.com/example.shtml", "evidence": "孟菲尔斯", "source_type": "search-snippet"}]):
        row["evidence"] = evidence
        assert any("verified without usable source evidence" in error
                   for error in audit_review_records(ledger, lambda _: "孟菲尔斯"))


def test_review_rejected_source_cannot_revive_under_https_or_fragment():
    from tools.audit_player_name_alignment import audit_review_records

    ledger = _review_ledger()
    row = ledger["entries"][0]
    row["rejected_evidence"] = [{"source_url": "http://sports.cctv.com/example.shtml#title",
                                 "reason": "同姓的另一个人"}]
    errors = audit_review_records(ledger, lambda _: "孟菲尔斯")
    assert any("rejected evidence revived" in error for error in errors)
    assert any("verified without usable source evidence" in error for error in errors)


def test_review_duplicate_source_cannot_inflate_confirmation():
    from tools.audit_player_name_alignment import audit_review_records

    ledger = _review_ledger()
    row = ledger["entries"][0]
    row["evidence"].append(dict(row["evidence"][0], source_url="http://sports.cctv.com/example.shtml#body"))
    assert any("duplicate evidence URL" in error
               for error in audit_review_records(ledger, lambda _: "孟菲尔斯"))


def test_review_ledger_display_and_changed_flag_follow_actual_runtime():
    from tools.audit_player_name_alignment import audit_review_records

    ledger = _review_ledger()
    ledger["entries"][0]["changed"] = True
    errors = audit_review_records(ledger, lambda _: "新译名")
    assert any("lookup mismatch" in error for error in errors)
    assert any("changed flag mismatch" in error for error in errors)


def test_native_script_evidence_can_use_traditional_identity_characters():
    from tools.audit_player_name_alignment import audit_review_records

    ledger = _review_ledger()
    row = ledger["entries"][0]
    row.update(name_en="Masamichi Imamura", before_zh="今村昌伦", name_zh="今村昌伦", status="verified-native")
    row["evidence"] = [{"source_url": "https://tennis.jp/example", "evidence": "今村昌倫が優勝", "source_type": "native-identity"}]
    assert not audit_review_records(ledger, lambda _: "今村昌伦")



def test_english_identity_records_alone_cannot_verify_chinese_display_name():
    from tools.audit_player_name_alignment import audit_review_records

    for source_type in ("identity-only", "official-english-identity", "identity-api",
                        "english-ranking", "english-match-result", "official-match-api",
                        "official-player-api", "official-identity-api"):
        ledger = _review_ledger()
        row = ledger["entries"][0]
        chinese = row["evidence"][0]
        row["evidence"] = [{"source_url": "https://www.wtatennis.com/players/example",
                            "evidence": "Gael Monfils defeated his opponent.",
                            "source_type": source_type}]
        assert any("verified without usable source evidence" in error
                   for error in audit_review_records(ledger, lambda _: "孟菲尔斯"))
        row["evidence"].append(chinese)
        assert not audit_review_records(ledger, lambda _: "孟菲尔斯")


def test_official_chinese_article_is_not_rejected_by_tour_domain():
    from tools.audit_player_name_alignment import audit_review_records

    ledger = _review_ledger()
    ledger["entries"][0]["evidence"][0]["source_url"] = "https://www.wtatennis.com/zh/news/example"
    assert not audit_review_records(ledger, lambda _: "孟菲尔斯")
