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


def test_flash_card_body_carries_and_escapes_all_text():
    body = flash_card_body(
        "18岁小将爆冷，淘汰头号种子",
        quote="全场起立鼓掌，他说：这不是<终点>",
        source_label="资料：ATP 官方赛报",
        date_label="7.24 · 周五",
    )
    assert "18岁小将爆冷" in body
    assert "淘汰头号种子" in body
    # User-supplied text must be HTML-escaped (no raw angle brackets injected).
    assert "&lt;终点&gt;" in body
    assert "<终点>" not in body
    assert "网球快讯" in body
    assert "资料：ATP 官方赛报" in body
    # It is a cover-class poster (skips the deck overflow gate) and self-framed.
    assert 'class="poster cover knowledge-page"' in body
