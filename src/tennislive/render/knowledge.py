"""Standalone daily tennis knowledge package.

The morning digest should answer "what happened / what to watch"; this package
keeps the slower historical context as a separate shareable post.
"""

from __future__ import annotations

import html
import hashlib
import json
import os
import shutil
from pathlib import Path

from ..digest import Digest
from ..research.visual_sources import resolve_story_visuals
from ..timeutil import WEEKDAY_ZH
from .pushmsg import to_copy_page
from .knowledge_visual_qa import evaluate_knowledge_visuals
from .tournament_story import (
    TournamentStory,
    tournament_story_candidates,
)
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


_FORBIDDEN_COPY_BOILERPLATE = (
    "先别往下滑",
    "🧠 先猜",
    "🎾 答案",
    "记住这3点",
    "我为什么想讲它",
)


def _copy_mode(story: TournamentStory, digest: Digest) -> int:
    seed = f"{digest.today.isoformat()}:{story.slug}".encode("utf-8")
    return hashlib.sha256(seed).digest()[0] % 5


def _story_opening(story: TournamentStory, digest: Digest) -> tuple[str, str, str]:
    """Rotate human openings without asking a canned quiz question."""
    mode = _copy_mode(story, digest)
    first = story.moments[0] if story.moments else None
    year = first.date[:4] if first else story.founded.replace("始于 ", "")
    openings = (
        (
            "🎬 把时间拨回那一刻",
            f"{year}年，{first.player if first else story.title}迎来了{first.headline if first else '关键一章'}。"
            f"{first.detail if first else story.hero_fact}",
            "历史不是背景板，它就在这一分之后拐了弯。",
        ),
        (
            "⚡ 先看这个反差",
            f"有些纪录靠十几年慢慢累积，{story.title}却把难度压缩进一次机会里。",
            story.hero_fact,
        ),
        (
            "👤 先记住这个人",
            f"那一年，{first.player if first else story.title}"
            f"{('只有' + first.age) if first and first.age else '站到了故事中央'}。",
            first.detail if first else story.hero_fact,
        ),
        (
            "🔎 比结果更有意思的事",
            f"比分会被下一轮覆盖，但{story.title}留下的那条线，后来一直延伸到今天。",
            story.hero_fact,
        ),
        (
            "🕰️ 今天回看，仍然离谱",
            f"把时间拉回{year}年，这件事当时已经够难；放到今天看，它反而更难复制。",
            story.hero_fact,
        ),
    )
    return openings[mode]


def _golden_slam_copy(story: TournamentStory, digest: Digest) -> str:
    title = knowledge_title(story, digest)
    question = _knowledge_question(story)
    return (
        f"{title}\n\n"
        "1988年，格拉芙先后赢下澳网、法网、温网和美网。\n"
        "抵达汉城时，19岁的她只差最后一扇门。\n\n"
        "决赛对面还是萨巴蒂尼。\n"
        "几周前的美网决赛，两人刚打满三盘；这一次，格拉芙用两个6比3结束比赛。\n\n"
        "真正夸张的，不只是五项冠军都拿到了。\n\n"
        "四大满贯横跨硬地、红土和草地；\n"
        "奥运会却四年才来一次。\n"
        "状态、身体和赛历必须在同一年严丝合缝地对上。\n\n"
        "拉沃尔1969年完成公开赛时代男子唯一一次年度全满贯；\n"
        "格拉芙又往前走了一步。直到今天，年度金满贯仍只有她一人。\n\n"
        f"💬 {question}\n\n"
        "关注 @网球时差｜把比分背后的来路讲给你听。\n\n"
        f"资料｜{story.source_label}\n\n"
        "#网球 #格拉芙 #金满贯 #网球历史 #网球时差"
    )


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
        reply = "有人记住冠军，有人记住输掉以后重新站起来的那一场。你是哪一种？"
    else:
        reply = "说一场、一个人或一个瞬间都可以，我更想听你自己的看球记忆。"
    return f"{question}\n\n{reply}"


def knowledge_copy(story: TournamentStory, digest: Digest) -> str:
    if story.slug == "golden-slam":
        return _golden_slam_copy(story, digest)
    title = knowledge_title(story, digest)
    items = _caption_items(story)
    moment_icons = ("①", "②", "③")
    moments = "\n\n".join(
        f"{moment_icons[index]} {item}" for index, item in enumerate(items)
    )
    question = _knowledge_question(story)
    opening_label, opener, bridge = _story_opening(story, digest)
    timeline_labels = ("🎾 三个镜头", "📍 把它放回历史", "🧩 这条线怎么走到今天")
    timeline_label = timeline_labels[_copy_mode(story, digest) % len(timeline_labels)]
    return (
        f"{title}\n\n"
        f"{opening_label}\n"
        f"{opener}\n\n"
        f"{bridge}\n\n"
        f"{timeline_label}\n"
        f"{moments}\n\n"
        f"💬 {question}\n\n"
        "关注 @网球时差｜把比分背后的来路讲给你听。\n\n"
        f"资料｜{story.source_label}\n\n"
        "#网球 #网球知识 #网球时差 #网球科普 #网球故事"
    )


def _validate_copy_for_publish(copy: str) -> None:
    repeated = [phrase for phrase in _FORBIDDEN_COPY_BOILERPLATE if phrase in copy]
    if repeated:
        raise ValueError("知识帖文案仍含固定模板话术：" + "、".join(repeated))


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
    candidates = [story] if story is not None else tournament_story_candidates(digest)
    candidates = [candidate for candidate in candidates if candidate is not None]
    if not candidates:
        return None
    outdir = Path(outdir)
    cards_dir = outdir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old in cards_dir.glob("card_*.*"):
        if old.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            old.unlink()
    visuals_dir = outdir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)
    for old in visuals_dir.iterdir():
        if old.is_file():
            old.unlink()

    rejected_candidates: list[dict] = []
    selected_story: TournamentStory | None = None
    page_visuals = {}
    visual_sources: dict = {}
    max_attempts = max(1, int(os.environ.get("TENNISLIVE_VISUAL_CANDIDATES", "6")))
    for candidate in candidates[:max_attempts]:
        _validate_story_for_publish(candidate, digest)
        for old in visuals_dir.iterdir():
            if old.is_file():
                old.unlink()
        candidate_visuals, candidate_report = resolve_story_visuals(candidate, visuals_dir)
        if candidate_report.get("status") == "pass":
            selected_story = candidate
            page_visuals = candidate_visuals
            visual_sources = candidate_report
            break
        rejected_candidates.append(
            {
                "story_slug": candidate.slug,
                "title": candidate.title,
                "errors": candidate_report.get("errors", []),
                "missing_pages": candidate_report.get("missing_pages", []),
            }
        )
    if selected_story is None:
        failure = {
            "schema_version": 1,
            "status": "fail",
            "policy": "精确人物/年份/赛事/地点/授权素材不足时自动换题；候选耗尽则停止发布",
            "rejected_candidates": rejected_candidates,
            "errors": ["候选故事均未通过素材生产性预检"],
            "attempts": [],
        }
        (outdir / "visual_sources.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise ValueError("知识帖素材预检失败：候选故事均没有完整高质量图片包")
    story = selected_story
    visual_sources["rejected_candidates"] = rejected_candidates
    (outdir / "visual_sources.json").write_text(
        json.dumps(visual_sources, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    date_label = _date_label(digest.today)
    question = _knowledge_question(story)
    bodies = knowledge_deck_bodies(
        story,
        date_label,
        question=question,
        year=digest.today.year,
        page_visuals=page_visuals,
    )
    visual_qa = evaluate_knowledge_visuals(
        story,
        bodies,
        page_visuals=page_visuals,
    )
    (outdir / "visual_qa.json").write_text(
        json.dumps(visual_qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if visual_qa["status"] != "pass":
        raise ValueError("知识帖视觉校验失败：" + "；".join(visual_qa["errors"]))
    images = _screenshot_pages(bodies, theme)
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
    visual_qa = evaluate_knowledge_visuals(
        story,
        bodies,
        card_paths,
        page_visuals=page_visuals,
    )
    (outdir / "visual_qa.json").write_text(
        json.dumps(visual_qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if visual_qa["status"] != "pass":
        raise ValueError("知识帖渲染校验失败：" + "；".join(visual_qa["errors"]))
    # The four compressed cards and source manifest are durable artifacts.
    # Raw downloads are only a render cache and would otherwise bloat Git daily.
    shutil.rmtree(visuals_dir, ignore_errors=True)

    xhs_text = knowledge_copy(story, digest)
    _validate_copy_for_publish(xhs_text)
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
                "visual_qa": "visual_qa.json",
                "visual_sources": "visual_sources.json",
                "resolved_visual_count": len(page_visuals),
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
