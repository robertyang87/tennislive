from tennislive.render.hashtags import (
    MAX_HASHTAGS,
    hashtag_count,
    limit_hashtags,
)


def test_limit_hashtags_keeps_first_five_unique_tags():
    text = (
        "正文。\n\n"
        "#网球 #WTA #ATP #中国网球 #网球时差 #温网 #网球"
    )

    limited = limit_hashtags(text)

    assert hashtag_count(limited) == MAX_HASHTAGS
    assert "#温网" not in limited
    assert limited.count("#网球") == 2  # #网球 + #网球时差


def test_limit_hashtags_handles_tags_attached_to_body_copy():
    limited = limit_hashtags(
        "你站谁？#网球 #WTA #ATP #中国网球 #网球时差 #温网"
    )

    assert hashtag_count(limited) == 5
    assert limited.endswith("#网球时差")
