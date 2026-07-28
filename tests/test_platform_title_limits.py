from datetime import date

import pytest

from tennislive.digest import Digest
from tennislive.publish.wechat_mp import WeChatError, validate_wechat_title
from tennislive.render.knowledge import knowledge_title, knowledge_wechat_title
from tennislive.render.tournament_story import STORIES
from tennislive.render.xiaohongshu import xhs_title_len


def test_every_knowledge_story_has_platform_safe_titles():
    digest = Digest(today=date(2026, 7, 23))

    for story in STORIES:
        assert xhs_title_len(knowledge_title(story, digest)) <= 20
        assert len(knowledge_wechat_title(story, digest)) <= 64


def test_解说片的台头也不超过二十字():
    """解说片的 `topic` 就是它的标题——印在每一屏卡上，也是发出去那条的题。

    知识帖那一栏早就卡着小红书的 20 字（上面那条测试），解说片这一栏一直没卡，
    只是碰巧都在线内：立这条闸门时十四条全部 ≤20（最长的 `roof` 正好 20.0）。
    **全绿的时候立闸门，才不用建祖父名单**——`test_explainer_budget` 那条就是
    在全红的时候立的，只能退而求其次搞成棘轮。

    半角记 0.5，和小红书一致，所以「发球 25 秒」这种带数字的不吃亏。
    """
    from tennislive.video.explainer import _OPENINGS

    over = {
        slug: (round(xhs_title_len(spec["topic"]), 1), spec["topic"])
        for slug, spec in _OPENINGS.items()
        if xhs_title_len(spec.get("topic", "")) > 20
    }

    assert not over, "这些片子的台头超过 20 字：\n  " + "\n  ".join(
        f"{slug} {n} 字：{t}" for slug, (n, t) in sorted(over.items()))


def test_每条片子都有台头():
    """没有台头的卡片，`topic_html` 会整段消失——静默降级，渲出来才看得见。"""
    from tennislive.video.explainer import _OPENINGS

    missing = [slug for slug, spec in _OPENINGS.items() if not spec.get("topic", "").strip()]

    assert not missing, f"这些片子没写 topic：{'、'.join(missing)}"


def test_wechat_rejects_overlong_title_instead_of_truncating():
    title = "网" * 65

    with pytest.raises(WeChatError, match="公众号标题超长"):
        validate_wechat_title(title)


def test_wechat_keeps_valid_title_unchanged():
    title = "7.23网球有故事｜11小时5分钟"

    assert validate_wechat_title(title) == title
