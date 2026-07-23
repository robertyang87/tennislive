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


def test_wechat_rejects_overlong_title_instead_of_truncating():
    title = "网" * 65

    with pytest.raises(WeChatError, match="公众号标题超长"):
        validate_wechat_title(title)


def test_wechat_keeps_valid_title_unchanged():
    title = "7.23网球有故事｜11小时5分钟"

    assert validate_wechat_title(title) == title
