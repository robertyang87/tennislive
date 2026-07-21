"""Standalone daily tennis knowledge package.

The morning digest should answer "what happened / what to watch"; this package
keeps the slower historical context as a separate shareable post.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

from ..digest import Digest
from ..timeutil import WEEKDAY_ZH
from .pushmsg import to_copy_page
from .tournament_story import TournamentStory, pick_tournament_story
from .webcards import _screenshot_pages, tournament_story_body
from .xiaohongshu import xhs_title_len


_REPO = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")
_CDN = f"https://cdn.jsdelivr.net/gh/{_REPO}@main"
_OWNER, _REPO_NAME = _REPO.split("/", 1)
_PAGES = os.environ.get(
    "TENNISLIVE_PAGES_URL", f"https://{_OWNER}.github.io/{_REPO_NAME}"
).rstrip("/")


def _date_label(d) -> str:
    return f"{d.month}.{d.day} · {WEEKDAY_ZH[d.weekday()]}"


def knowledge_title(story: TournamentStory, digest: Digest) -> str:
    day = f"{digest.today.month}.{digest.today.day}"
    trivia_hooks = {
        "otd-0725": "18岁第一冠，从乌马格开始",
        "otd-0803": "郑钦文巴黎摘金的那一天",
        "otd-0820": "3小时49分，决赛打到极限",
        "otd-0909": "19岁高芙，主场圆梦夜",
        "scoring-history": "网球为什么是15、30、40？",
        "yellow-ball": "网球为什么从白色变黄？",
        "longest-match": "最长一场网球，到底打了多久？",
        "hawkeye": "一场误判，催生了网球鹰眼",
        "golden-slam": "金满贯到底有多难？",
        "surfaces": "三种场地，真像三项运动？",
        "big-three": "三巨头统治了多少年？",
        "china-tennis": "中国网球，从哪一冠开始？",
    }
    if story.kind == "player":
        emoji, hook = "👤", f"{story.title}，不只是一场比分"
    if story.kind == "trivia":
        emoji, hook = "👀", trivia_hooks.get(story.slug, f"{story.title}，你真懂吗？")
    if story.kind not in ("player", "trivia"):
        emoji, hook = "🏟️", f"为什么要记住{story.title}？"
    prefix = f"{emoji}{day}｜"
    if xhs_title_len(prefix + hook) > 20:
        suffix = "的来路" if story.kind == "player" else "的故事"
        hook = f"{story.title}{suffix}"
    if xhs_title_len(prefix + hook) > 20:
        hook = story.title
    return prefix + hook


def _caption_items(story: TournamentStory) -> list[str]:
    items: list[str] = []
    years: set[str] = set()
    for moment in story.moments[:2]:
        year = moment.date.split("-", 1)[0]
        years.add(year)
        items.append(f"{year}｜{moment.player}：{moment.headline.rstrip('。')}")
    for fact in story.facts:
        if len(items) >= 3:
            break
        if any(year in fact for year in years):
            continue
        if fact not in items:
            first_sentence = fact.split("。", 1)[0].strip()
            clauses: list[str] = []
            for clause in first_sentence.split("，"):
                candidate = "，".join([*clauses, clause])
                if clauses and len(candidate) > 38:
                    break
                clauses.append(clause)
            items.append(f"再记一个｜{'，'.join(clauses)}")
    return items[:3]


def _knowledge_question(story: TournamentStory) -> str:
    trivia_questions = {
        "scoring-history": "你第一次学网球记分时，最难理解的是哪一项？",
        "yellow-ball": "如果网球还是白色，你觉得电视上还能看清吗？",
        "longest-match": "一场比赛打到第几小时，你会先撑不住？",
        "hawkeye": "关键分上，你更信主裁第一判断，还是鹰眼回放？",
        "golden-slam": "金满贯和世界第一，你觉得哪个更难？",
        "surfaces": "硬地、红土、草地只能选一种看，你选哪块？",
        "big-three": "三巨头时代，你最先站谁？",
        "china-tennis": "中国网球哪个瞬间，你到现在还记得？",
    }
    if story.kind == "player":
        return f"你第一次记住{story.title}，是哪一场球？"
    if story.kind == "trivia":
        return trivia_questions.get(
            story.slug, "读完这张卡，你最想把哪一条讲给球友听？"
        )
    return f"提到{story.title}，你最先想到哪位冠军？"


def knowledge_pinned_comment(story: TournamentStory) -> str:
    question = _knowledge_question(story)
    if story.slug == "hawkeye":
        reply = "我先站鹰眼：关键分可以输，但最好别输给一次看错。"
    elif story.kind == "player":
        reply = "我先不设标准答案，想看看大家记住的是同一场，还是不同的瞬间。"
    else:
        reply = "我先把答案留给评论区：说一场、一个人或一个瞬间都算。"
    return f"{question}\n\n{reply}"


def knowledge_copy(story: TournamentStory, digest: Digest) -> str:
    title = knowledge_title(story, digest)
    items = _caption_items(story)
    number_icons = ("1️⃣", "2️⃣", "3️⃣")
    bullets = "\n".join(
        f"{number_icons[index]} {item}" for index, item in enumerate(items)
    )
    why = {
        "player": "下次再看到这位球员站上关键分，你看的就不只是一场胜负，而是一段走到今天的路。",
        "trivia": "冷知识不是背答案。它会让下一次判罚、换场或关键分，多一层看得懂的乐趣。",
    }.get(
        story.kind,
        "下次镜头扫过中央球场，你看到的不只是一站赛程，还有那些在这里发生过的冠军故事。",
    )
    question = _knowledge_question(story)
    if story.kind == "trivia":
        opener = f"先别往下滑，猜一下：{story.title.rstrip('？?')}？"
        opening_label = "🧠 先猜一下"
        answer_label = "🎾 答案藏在这段历史里"
    elif story.kind == "player":
        opener = f"先别急着看下一场：{story.title}为什么会走到今天？"
        opening_label = "👀 先认识一个人"
        answer_label = "🎾 故事要从这里说起"
    else:
        opener = f"赛程表没告诉你的事：{story.title}为什么值得记住？"
        opening_label = "👀 先看赛程外"
        answer_label = "🎾 先记住这一句话"
    return (
        f"{title}\n\n"
        f"{opening_label}\n"
        f"{opener}\n\n"
        f"{answer_label}\n"
        f"{story.hero_fact}\n\n"
        "📍 3个记忆点\n"
        f"{bullets}\n\n"
        "💡 为什么今天还值得聊？\n"
        f"{why}\n\n"
        "💬 轮到你\n"
        f"{question}\n\n"
        "我是 @网球时差｜每天多懂一点，再去看下一场。\n\n"
        f"资料核对：{story.source_label}\n\n"
        "#网球 #网球知识 #网球时差 #网球科普 #网球故事"
    )


def knowledge_push_html(
    digest: Digest,
    story: TournamentStory,
    *,
    card_name: str,
    xhs_text: str,
) -> str:
    d = digest.today
    card_url = f"{_CDN}/output/{d.isoformat()}/knowledge/cards/{card_name}"
    copy_url = f"{_PAGES}/output/{d.isoformat()}/knowledge/copy.html"
    lines = xhs_text.strip().splitlines()
    title = html.escape(lines[0] if lines else knowledge_title(story, digest))
    body_start = 2 if len(lines) > 1 and not lines[1].strip() else 1
    body = "\n".join(lines[body_start:]).strip()
    paragraphs = []
    for paragraph in body.split("\n\n"):
        safe = "<br/>".join(html.escape(line) for line in paragraph.splitlines())
        paragraphs.append(
            '<div style="font-size:15px;line-height:1.85;margin:0 0 13px;">'
            f"{safe}</div>"
        )
    source = html.escape(story.source_label)
    return f"""<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
<div style="max-width:680px;margin:0 auto;background-color:#ffffff;border-top:5px solid #ff2442;padding:18px 16px 22px;">
  <div style="display:inline-block;background-color:#e7f5ea;color:#087747;font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px;">小红书知识帖 · {d.month}.{d.day}</div>
  <div style="font-size:23px;line-height:1.38;font-weight:800;color:#102d23;margin:10px 0 14px;">{title}</div>
  <img src="{card_url}" style="width:100%;border-radius:6px;margin:0 0 16px;display:block;" />
  {''.join(paragraphs)}
  <div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>
  <a href="{copy_url}" style="display:block;background-color:#ff2442;color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;border-radius:6px;margin:0 0 7px;">分别复制标题 / 正文 / 置顶评论</a>
  <div style="text-align:center;color:#7a8580;font-size:12px;">资料核对：{source} · 图片长按保存</div>
</div>
</div>"""


def generate_knowledge_package(
    digest: Digest,
    outdir: str | Path,
    *,
    theme: str = "dark",
    story: TournamentStory | None = None,
) -> TournamentStory | None:
    story = story or pick_tournament_story(digest)
    if story is None:
        return None
    outdir = Path(outdir)
    cards_dir = outdir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old in cards_dir.glob("card_*.*"):
        if old.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            old.unlink()

    date_label = _date_label(digest.today)
    image = _screenshot_pages(
        [("knowledge", tournament_story_body(story, date_label))],
        theme,
    )[0][1]
    from .image_output import save_social_image

    card_path = save_social_image(image, cards_dir / "card_00_knowledge")

    xhs_text = knowledge_copy(story, digest)
    pinned_comment = knowledge_pinned_comment(story)
    (outdir / "xiaohongshu.txt").write_text(xhs_text, encoding="utf-8")
    (outdir / "pinned_comment.txt").write_text(pinned_comment, encoding="utf-8")
    (outdir / "wechat_title.txt").write_text(
        f"每日网球知识：{story.title}", encoding="utf-8"
    )
    (outdir / "copy.html").write_text(
        to_copy_page(xhs_text, pinned_comment=pinned_comment), encoding="utf-8"
    )
    (outdir / "push.html").write_text(
        knowledge_push_html(
            digest,
            story,
            card_name=card_path.name,
            xhs_text=xhs_text,
        ),
        encoding="utf-8",
    )
    (outdir / "story.json").write_text(
        json.dumps(
            {
                "slug": story.slug,
                "title": story.title,
                "kind": story.kind,
                "source_label": story.source_label,
                "source_url": story.source_url,
                "image": str(story.image),
                "image_credit": story.image_credit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return story
