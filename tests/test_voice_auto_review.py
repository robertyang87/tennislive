"""配音自动听审的纯函数判据（不合成、不转写；runner 上的实测在 research/voice-auto-calib）。"""
import pytest

pytest.importorskip("pypinyin")
import voice_auto_review as auto  # noqa: E402


def test_转写按拼音比_换字表的同音字不算错():
    r = auto.compare_transcript("关注网球时插，时插归我，好球归你。", "关注网球时差,时差归我,好球归你。")
    assert r["ok"] and r["substituted"] == 0


def test_漏读两个字就红():
    r = auto.compare_transcript("决胜盘连下最后四局。", "决胜盘连下四局。")
    assert not r["ok"] and r["deleted"] == 2


def test_句尾被截也红():
    assert not auto.compare_transcript("她救下两个盘点，还连发两记Ace。", "她救下两个盘点，还连")["ok"]


def test_一句话拆进两段合成要报():
    spec = {"segments": [{"narration": "决赛对安德列娃，第二盘四比五落后，"},
                         {"narration": "她救下两个盘点。"}, {"narration": ""},
                         {"narration": "完了。"}]}
    assert [s["segment"] for s in auto.split_sentences(spec)] == [1]


def _entry(text, marks):
    return {"request": {"text": text}, "marks": marks}


def _m(text, start, end):
    return {"text": text, "offset": int(start * 1e7), "duration": int((end - start) * 1e7)}


def test_人名中间停太久要红_标点处停不算():
    marks = [_m("赢了", 0.0, 0.3), _m("萨巴", 0.3, 0.6), _m("伦卡", 0.95, 1.2), _m("然后", 1.6, 1.9)]
    r = auto.pause_and_speed(_entry("赢了萨巴伦卡，然后", marks), ["萨巴伦卡"])
    assert [x["span"] for x in r["inner_pauses"]] == ["萨巴伦卡"]
    marks[2] = _m("伦卡", 0.62, 1.2)
    assert auto.pause_and_speed(_entry("赢了萨巴伦卡，然后", marks), ["萨巴伦卡"])["pause_ok"]


def test_比分中间停顿也算():
    marks = [_m("六", 0.0, 0.2), _m("比", 0.5, 0.7), _m("四", 0.7, 0.9)]
    assert not auto.pause_and_speed(_entry("六比四", marks), [])["pause_ok"]


def test_语速超上限要红():
    text = "一二三四五六七八九十" * 2
    r = auto.pause_and_speed(_entry(text, [_m(text, 0.0, 2.5)]), [])
    assert r["cps"] == 8.0 and not r["speed_ok"]


def test_多音字目标跳过换字表已换掉的字位():
    targets = auto.poly_targets("今天他重新发球。")
    chars = {t["char"] for t in targets}
    assert "重" in chars and "发" in chars
    assert all(t["wrong"] for t in targets)


def test_非默认读音是A档_点名字落在默认读音是B档():
    tiers = {t["char"]: t["tier"] for t in auto.poly_targets("今天他重新发球。")}
    assert tiers["重"] == "A" and tiers["发"] == "B"


def test_B档只有高置信错读才红_A档量不出也红():
    a = {"tier": "A", "verdict": "uncertain", "runs": []}
    b_unc = {"tier": "B", "verdict": "uncertain", "runs": []}
    b_bad = {"tier": "B", "verdict": "misread", "runs": [{"verdict": "misread", "confidence": "high"}]}
    assert not auto.poly_ok(a) and auto.poly_ok(b_unc) and not auto.poly_ok(b_bad)


def test_转写里的阿拉伯数字按读数或逐位都认():
    assert auto.compare_transcript("二零二六赛季，WTA一千赛全部收官。", "2026赛季,WTA1000赛全部收官。")["ok"]
    assert auto.compare_transcript("决赛七十五分钟横扫莱巴金娜。", "决赛75分钟,横扫来8斤。")["ok"]
