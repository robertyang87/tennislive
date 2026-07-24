from tennislive.render.flashcard import flash_card_body
from tennislive.render.sensitivity import is_sensitive_topic, sensitive_category


def test_light_sporting_news_is_not_flagged_sensitive():
    # Upsets, records, milestones, comebacks, injury retirements — the bread
    # and butter of a tennis flash card — must stay auto-eligible.
    assert not is_sensitive_topic("18岁小将爆冷淘汰头号种子，全场沸腾")
    assert not is_sensitive_topic("Alcaraz saves 3 match points to reach the final")
    assert not is_sensitive_topic("郑钦文生涯首进大师赛决赛，创中国球员纪录")
    assert not is_sensitive_topic("赛会一号种子因伤退赛")


def test_sensitive_topics_are_flagged_with_category():
    assert sensitive_category("WTA gender testing rules spark debate") == "gender"
    assert sensitive_category("媒体误用诺斯科娃照片配跨性别检测新闻") == "gender"
    assert sensitive_category("球员药检呈阳性被临时禁赛") == "doping"
    assert sensitive_category("Star player arrested over assault allegation") == (
        "legal_scandal"
    )
    assert sensitive_category("传奇名宿去世，享年 80 岁") == "tragedy_health"


def test_sensitivity_gate_matches_across_combined_parts():
    # The classifier scans headline + snippet together.
    assert is_sensitive_topic("赛场乌龙", "背后是跨性别参赛资格争议")


def test_flash_card_body_carries_structured_fields_and_escapes_text():
    body = flash_card_body(
        "18岁小将爆冷，淘汰头号种子",
        event="决胜盘抢七 10-8，他救回 3 个赛点后完成逆转 <绝杀>。",
        when="昨夜",
        where="辛辛那提 中央球场",
        who="小将 vs 头号种子",
        punch="全场起立鼓掌整整两分钟。",
        source_label="资料：ATP 官方赛报",
        date_label="7.24 · 周五",
    )
    assert "18岁小将爆冷" in body
    # Structured meta strip is present with labels and values.
    for token in ("时间", "昨夜", "地点", "辛辛那提 中央球场", "人物", "决胜盘抢七 10-8"):
        assert token in body
    assert "全场起立鼓掌整整两分钟。" in body
    # User-supplied text must be HTML-escaped (no raw angle brackets injected).
    assert "&lt;绝杀&gt;" in body
    assert "<绝杀>" not in body
    assert "网球快讯" in body
    assert "资料：ATP 官方赛报" in body
    # It is a cover-class poster (skips the deck overflow gate) and self-framed.
    assert 'class="poster cover knowledge-page"' in body


def test_flash_card_body_omits_blank_meta_cells():
    body = flash_card_body(
        "纪录诞生",
        event="一场超长对决刷新历史。",
        when="2010",
        source_label="资料：官方",
        date_label="7.24",
    )
    assert "时间" in body and "2010" in body
    # Blank where/who must not render empty labels.
    assert "地点" not in body and "人物" not in body
