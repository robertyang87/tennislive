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


# ── 活动 tag：截止到 2026-10-31，所有视频正文必须带 #网球中国赛季来了 #网球时间到 ──
from datetime import date  # noqa: E402

from tennislive.render.hashtags import (  # noqa: E402
    CAMPAIGN_TAGS,
    with_campaign_tags,
)

_IN = date(2026, 9, 23)


def test_活动期内视频正文必带两个活动tag_且总数不超过上限():
    reel = "正文。\n\n#赫瓦林斯卡 #奥利尼科娃 #新加坡网球公开赛 #赛场之上 #网球时差"
    out = with_campaign_tags(reel, _IN)
    assert out.splitlines()[-1] == (
        "#赫瓦林斯卡 #奥利尼科娃 #网球时差 #网球中国赛季来了 #网球时间到")
    assert hashtag_count(out) == MAX_HASHTAGS


def test_挤位置先挤泛词_账号名和选题tag留着():
    explainer = "正文。\n\n#网球 #网球时差 #郑钦文 #武网 #网球冷知识"
    tags = with_campaign_tags(explainer, _IN).splitlines()[-1]
    assert tags == "#网球时差 #郑钦文 #武网 #网球中国赛季来了 #网球时间到"


def test_已经写了活动tag的不重复_没有tag行的补一行():
    out = with_campaign_tags("正文 #网球时间到\n\n#中网", _IN)
    assert out.count("#网球时间到") == 1
    assert out.endswith("#中网 #网球中国赛季来了 #网球时间到")
    assert with_campaign_tags("只有正文", _IN).endswith("\n\n" + " ".join(CAMPAIGN_TAGS))


def test_十月三十一日还带_十一月一日起自动失效():
    text = "正文。\n\n#中网"
    assert "#网球时间到" in with_campaign_tags(text, date(2026, 10, 31))
    assert with_campaign_tags(text, date(2026, 11, 1)) == text


def test_挤掉网球时不会误伤网球时差():
    out = with_campaign_tags("正文\n\n#网球 #网球时差 #a #b #c", _IN).split()
    assert out[-5:] == ["#网球时差", "#a", "#b", "#网球中国赛季来了", "#网球时间到"]


def test_三条视频线的出口都接了活动tag():
    # 竖版短片／采访片走 push_reel，解说片走 explainer_xiaohongshu——少接一处就有一条线漏。
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    assert "with_campaign_tags(copy_text)" in (root / "tools/push_reel.py").read_text(encoding="utf-8")
    assert "return with_campaign_tags(" in (root / "src/tennislive/video/explainer.py").read_text(encoding="utf-8")
