"""「网球有故事」这一栏还留在生产线上的那几件事。

图文知识帖（静态四宫格卡）那条线 2026-09-15 停产，`generate_knowledge_package`
连同它的选题校验、正文拼装、配图预检一起删掉了——工作流 `knowledge-adhoc.yml`
和 CLI 入口已经先一步拿掉，删的时候生产调用方是 0。

剩下的两拨各有真实调用方，别再当成知识帖的零件一起清：

- 栏目名与标题：`render/webcards.py` 拿 `knowledge_column` 印在卡的台头上，
  `tests/test_platform_title_limits.py` 拿两个标题函数卡小红书 20 字位 /
  公众号 64 字。
- `knowledge_push_html_from_parts`：**视频解说片和采访线的微信推送正文都从
  这儿出**（`video/explainer.py`、`publish/pushplus.py`），和知识帖无关。
"""

from __future__ import annotations

import html

from ..digest import Digest
from .tournament_story import TournamentStory
from .xiaohongshu import xhs_title_len

# 栏目名印在标题上——读者只看标题，承诺印不出来这个栏目对外就不存在。
# 见 docs/columns.md 与 docs/column-operations.md 的 R4。
# 2026-09-15 起只剩「网球有故事」一个知识栏目（「历史上的今天」停产，选题和
# 分支一起拿掉了），所以这里是一个常量，不是一张按 slug 分派的表。
_COLUMN_NAME = "网球有故事"
_COLUMN_EMOJI = "📖"


def knowledge_column(story: TournamentStory) -> str:
    """这条故事对外挂在哪个栏目下."""
    return _COLUMN_NAME


def knowledge_title(story: TournamentStory, digest: Digest) -> str:
    day = f"{digest.today.month}.{digest.today.day}"
    trivia_hooks = {
        "scoring-history": "网球为什么是15、30、40？",
        "yellow-ball": "网球为什么从白色变黄？",
        "longest-match": "最长一场网球，到底打了多久？",
        "hawkeye": "误判催生网球鹰眼",
        "golden-slam": "金满贯到底有多难？",
        "surfaces": "三种场地，真像三项运动？",
        "big-three": "三巨头统治了多少年？",
        "china-tennis": "中国网球，从哪一冠开始？",
        # 兜底的「X 的故事」在这条上尤其糟：「签表上那个 WC的故事」——
        # 既丢了空格，也把全篇最硬的那个数字留在了标题外面。
        "wildcard": "第125名靠外卡拿了温网",
    }
    if story.kind == "player":
        hook = f"{story.title}，不只是一场比分"
    elif story.kind == "trivia":
        hook = trivia_hooks.get(story.slug, f"{story.title}，你真懂吗？")
    else:
        hook = f"为什么要记住{story.title}？"
    column = knowledge_column(story)
    prefix = f"{_COLUMN_EMOJI}{day}{column}｜"
    if xhs_title_len(prefix + hook) > 20:
        if story.kind == "player":
            short_name = story.title.rsplit("·", 1)[-1]
            hook = f"{short_name}的来路"
        else:
            hook = f"{story.title}的故事"
    if xhs_title_len(prefix + hook) > 20:
        hook = story.title
    return prefix + hook


def knowledge_wechat_title(story: TournamentStory, digest: Digest) -> str:
    """Use a distinct, fully preserved title for WeChat image posts."""
    title = (
        f"{digest.today.month}.{digest.today.day}"
        f"{knowledge_column(story)}｜{story.title}"
    )
    if len(title) > 64:
        raise ValueError(f"公众号图片消息标题超长: {len(title)} > 64")
    return title


def knowledge_push_html_from_parts(
    *,
    date,
    image_urls: list[str],
    xhs_text: str,
    copy_url: str,
    badge: str = "小红书知识帖",
    extra_action: tuple[str, str] | None = None,
) -> str:
    """The push body itself, given the pieces.

    Split out so the explainer video can send the same layout instead of
    growing its own — the badge, the per-image "didn't load?" fallback, the
    copy page button and the long-press hint are the parts that make a push
    usable on a phone, and they were worth having in one place.

    ⚠️ **知识帖和解说片两条线的微信正文都从这儿出**。AI 生成合成内容标识
    原来就是加在这一处的（别在两个调用方各加一遍），**2026-08-15 起不加了**，
    见 `ai_disclosure` 顶上那段。
    """
    lines = xhs_text.strip().splitlines()
    title = html.escape(lines[0] if lines else "")
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    # One block, not paragraph divs: the body has to be readable *and* liftable
    # in a single long-press. Splitting it into elements made copying a drag-
    # across-the-whole-screen job, and pairing pretty paragraphs with a second
    # copyable copy of the same text just sent everything twice. pre-wrap keeps
    # the blank lines between beats, so it reads the same and selects as one.
    body_block = (
        '<div style="color:#7a8580;font-size:12px;margin:0 0 8px;">'
        "👇 正文全文如下，长按整段即可复制</div>"
        '<div style="font-size:15px;line-height:1.85;white-space:pre-wrap;'
        'word-break:break-word;margin:0 0 4px;">'
        f"{html.escape(body)}</div>"
    )
    images = []
    for index, card_url in enumerate(image_urls, 1):
        images.append(
            f'<img src="{card_url}" data-src="{card_url}" width="100%" '
            f'alt="{title} · 第{index}页" referrerpolicy="no-referrer" '
            'style="width:100%;border-radius:6px;margin:0 0 10px;display:block;" />'
            f'<div style="text-align:center;margin:0 0 16px;"><a href="{card_url}" '
            'style="color:#087747;font-size:13px;text-decoration:none;">'
            f'第{index}张未显示？点此打开原图</a></div>'
        )
    action = ""
    if extra_action:
        href, label = extra_action
        action = (
            f'<a href="{href}" style="display:block;background-color:#102d23;'
            'color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;'
            'padding:13px 16px;border-radius:6px;margin:0 0 7px;">'
            f'{html.escape(label)}</a>'
        )
    return f"""<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
<div style="max-width:680px;margin:0 auto;background-color:#ffffff;border-top:5px solid #ff2442;padding:18px 16px 22px;">
  <div style="display:inline-block;background-color:#e7f5ea;color:#087747;font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px;">{badge} · {date.month}.{date.day}</div>
  <div style="font-size:23px;line-height:1.38;font-weight:800;color:#102d23;margin:10px 0 14px;">{title}</div>
  {''.join(images)}
  {body_block}
  <div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>
  {action}<a href="{copy_url}" style="display:block;background-color:#ff2442;color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;border-radius:6px;margin:0 0 7px;">分别复制标题 / 正文 / 置顶评论</a>
  <div style="text-align:center;color:#7a8580;font-size:12px;">图片长按保存</div>
</div>
</div>"""
