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
from .webcards import _screenshot_pages, knowledge_deck_bodies
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
        "hawkeye": "误判催生网球鹰眼",
        "golden-slam": "金满贯到底有多难？",
        "surfaces": "三种场地，真像三项运动？",
        "big-three": "三巨头统治了多少年？",
        "china-tennis": "中国网球，从哪一冠开始？",
    }
    if story.kind == "player":
        hook = f"{story.title}，不只是一场比分"
    elif story.kind == "trivia":
        hook = trivia_hooks.get(story.slug, f"{story.title}，你真懂吗？")
    else:
        hook = f"为什么要记住{story.title}？"
    prefix = f"📖{day}网球有故事｜"
    if xhs_title_len(prefix + hook) > 20:
        if story.kind == "player":
            short_name = story.title.rsplit("·", 1)[-1]
            hook = f"{short_name}的来路"
        else:
            hook = f"{story.title}的故事"
    if xhs_title_len(prefix + hook) > 20:
        hook = story.title
    return prefix + hook


def _caption_items(story: TournamentStory) -> list[str]:
    items: list[str] = []
    years: set[str] = set()
    for moment in story.moments[:2]:
        year = moment.date.split("-", 1)[0]
        years.add(year)
        item = f"{year}｜{moment.player}：{moment.headline.rstrip('。')}"
        items.append(item if len(item) <= 34 else item[:33].rstrip("，；") + "…")
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
                if clauses and len(candidate) > 28:
                    break
                clauses.append(clause)
            items.append(f"再记一个｜{'，'.join(clauses)}")
    return items[:3]


def _knowledge_question(story: TournamentStory) -> str:
    trivia_questions = {
        "scoring-history": "你第一次学网球记分时，最难理解的是哪一项？",
        "yellow-ball": "如果网球还是白色，你觉得电视上还能看清吗？",
        "longest-match": "一场比赛打到第几小时，你会先撑不住？",
        "hawkeye": "四大满贯只剩法网保留人工司线，红土球印足够可靠吗？",
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
        reply = "我更看重判罚标准一致：红土有球印，但人工找印和解释球印仍可能出错。"
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
        "player": "再看他的关键分，你会看到比分背后的来路。",
        "trivia": "它不是一道考题，而是让你下次看球时多懂一层。",
    }.get(
        story.kind,
        "再看到中央球场，你也会认出赛程背后的历史。",
    )
    question = _knowledge_question(story)
    if story.kind == "trivia":
        opener = f"先别往下滑，猜一下：{story.title.rstrip('？?')}？"
        opening_label = "🧠 先猜"
        answer_label = "🎾 答案"
    elif story.kind == "player":
        opener = f"先别急着看下一场：{story.title}为什么会走到今天？"
        opening_label = "👀 先认识他"
        answer_label = "🎾 故事从这里开始"
    else:
        opener = f"赛程表没告诉你的事：{story.title}为什么值得记住？"
        opening_label = "👀 赛程之外"
        answer_label = "🎾 先记一句"
    return (
        f"{title}\n\n"
        f"{opening_label}\n"
        f"{opener}\n\n"
        f"{answer_label}\n"
        f"{story.hero_fact}\n\n"
        "📍 记住这3点\n"
        f"{bullets}\n\n"
        "💡 我为什么想讲它\n"
        f"{why}\n\n"
        f"💬 {question}\n\n"
        "关注 @网球时差｜把网球故事讲得好懂一点。\n\n"
        f"资料｜{story.source_label}\n\n"
        "#网球 #网球知识 #网球时差 #网球科普 #网球故事"
    )


def knowledge_push_html(
    digest: Digest,
    story: TournamentStory,
    *,
    card_names: list[str],
    xhs_text: str,
) -> str:
    d = digest.today
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
    images = []
    for index, card_name in enumerate(card_names, 1):
        card_url = f"{_CDN}/output/{d.isoformat()}/knowledge/cards/{card_name}"
        images.append(
            f'<img src="{card_url}" data-src="{card_url}" width="100%" '
            f'alt="{title} · 第{index}页" referrerpolicy="no-referrer" '
            'style="width:100%;border-radius:6px;margin:0 0 10px;display:block;" />'
            f'<div style="text-align:center;margin:0 0 16px;"><a href="{card_url}" '
            'style="color:#087747;font-size:13px;text-decoration:none;">'
            f'第{index}张未显示？点此打开原图</a></div>'
        )
    return f"""<div style="background-color:#f6f7f4;color:#17251f;padding:12px 10px;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;">
<div style="max-width:680px;margin:0 auto;background-color:#ffffff;border-top:5px solid #ff2442;padding:18px 16px 22px;">
  <div style="display:inline-block;background-color:#e7f5ea;color:#087747;font-size:12px;font-weight:bold;padding:4px 8px;border-radius:4px;">小红书知识帖 · {d.month}.{d.day}</div>
  <div style="font-size:23px;line-height:1.38;font-weight:800;color:#102d23;margin:10px 0 14px;">{title}</div>
  {''.join(images)}
  {''.join(paragraphs)}
  <div style="border-top:1px solid #e6ebe8;margin:18px 0 12px;"></div>
  <a href="{copy_url}" style="display:block;background-color:#ff2442;color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;padding:13px 16px;border-radius:6px;margin:0 0 7px;">分别复制标题 / 正文 / 置顶评论</a>
  <div style="text-align:center;color:#7a8580;font-size:12px;">资料核对：{source} · 图片长按保存</div>
</div>
</div>"""


def _validate_story_for_publish(story: TournamentStory, digest: Digest) -> None:
    """Fail closed when a story contains unsupported or logically stale claims."""
    errors: list[str] = []
    claims = "\n".join((story.hero_fact, *story.facts))
    if not story.source_url.startswith("https://"):
        errors.append("主来源必须是 HTTPS")
    if "截至" in claims and str(digest.today.year) not in claims:
        errors.append("时效性结论必须包含生成年份")
    forbidden = (
        "目前只剩法网",
        "主裁第一判断，还是鹰眼",
        "技术没有替比赛做决定",
    )
    for phrase in forbidden:
        if phrase in claims:
            errors.append(f"存在范围或角色不清的表述：{phrase}")
    if story.slug == "hawkeye":
        required = ("2D", "3D", "四大满贯中", "实时电子司线", str(digest.today.year))
        for phrase in required:
            if phrase not in claims:
                errors.append(f"鹰眼事实缺少必要范围：{phrase}")
        if len(story.evidence_urls) < 4:
            errors.append("鹰眼故事至少需要四个交叉核验来源")
    if errors:
        raise ValueError("知识帖事实校验失败：" + "；".join(errors))


def _knowledge_evidence(story: TournamentStory, digest: Digest) -> dict:
    source_urls = list(dict.fromkeys(
        [
            story.source_url,
            *story.evidence_urls,
            *(moment.source_url for moment in story.moments),
            story.image_source_url,
        ]
    ))
    source_urls = [url for url in source_urls if url]
    claims = [
        {
            "type": "hero",
            "text": story.hero_fact,
            "source_urls": source_urls[:2] or [story.source_url],
        }
    ]
    for index, fact in enumerate(story.facts):
        if story.slug == "hawkeye":
            mapping = (
                source_urls[:2],
                [url for url in source_urls if "usopen.org" in url or "sony.com" in url],
                [url for url in source_urls if "wimbledon.com" in url or "lequipe.fr" in url],
            )
            urls = mapping[index] if index < len(mapping) else source_urls[:1]
        else:
            urls = source_urls[:1]
        claims.append({"type": "fact", "text": fact, "source_urls": urls})
    claims.extend(
        {
            "type": "moment",
            "date": moment.date,
            "text": f"{moment.player}：{moment.headline}。{moment.detail}",
            "source_urls": [moment.source_url],
        }
        for moment in story.moments
    )
    return {
        "schema_version": 1,
        "generated_for": digest.today.isoformat(),
        "story_slug": story.slug,
        "scope": "已核验事实；观点与互动问题不作为事实结论",
        "claims": claims,
        "sources": source_urls,
    }


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
    _validate_story_for_publish(story, digest)
    outdir = Path(outdir)
    cards_dir = outdir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old in cards_dir.glob("card_*.*"):
        if old.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            old.unlink()

    date_label = _date_label(digest.today)
    question = _knowledge_question(story)
    images = _screenshot_pages(
        knowledge_deck_bodies(
            story,
            date_label,
            question=question,
            year=digest.today.year,
        ),
        theme,
    )
    from .image_output import save_social_image

    card_stems = {
        "knowledge": "card_00_knowledge",
        "story": "card_01_story",
        "explainer": "card_02_explainer",
        "today": "card_03_today",
    }
    card_paths = [
        save_social_image(image, cards_dir / card_stems[kind])
        for kind, image in images
    ]

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
            card_names=[path.name for path in card_paths],
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
                "card_count": len(card_paths),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (outdir / "evidence.json").write_text(
        json.dumps(_knowledge_evidence(story, digest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return story
