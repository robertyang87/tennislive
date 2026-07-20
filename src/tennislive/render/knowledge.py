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
    if story.kind == "player":
        return f"{day}｜一分钟认识：{story.title}"
    if story.kind == "trivia":
        return f"{day}｜这个网球知识，很多人会答错"
    return f"{day}｜为什么{story.title}值得记住"


def _compact_items(story: TournamentStory) -> list[str]:
    items: list[str] = []
    years: set[str] = set()
    for moment in story.moments[:2]:
        year = moment.date.split("-", 1)[0]
        years.add(year)
        items.append(f"{year}：{moment.player}，{moment.headline}。{moment.detail}")
    for fact in story.facts[:2]:
        if any(year in fact for year in years):
            continue
        if fact not in items:
            items.append(fact)
    return items[:3]


def knowledge_copy(story: TournamentStory, digest: Digest) -> str:
    title = knowledge_title(story, digest)
    items = _compact_items(story)
    bullets = "\n".join(f"· {item}" for item in items)
    why = {
        "player": "看球员不只看比分。把这些节点记住，下一次看到TA站上关键分，情绪就有来处。",
        "trivia": "冷知识不是背答案，是帮你把比赛里的规则、传统和现场细节连起来。",
    }.get(
        story.kind,
        "看赛程不只看对阵。知道一站赛事的来历，中央球场、红土和冠军名单就都有了故事感。",
    )
    question = {
        "player": f"你第一次记住{story.title}，是哪一场？",
        "trivia": "你还想看哪条网球冷知识？",
    }.get(story.kind, f"这站赛事你最先想到哪位冠军？")
    return (
        f"{title}\n\n"
        "今天单独讲一个网球知识点。\n"
        "不赶赛程，慢慢把背景补上。\n\n"
        f"{story.hero_fact}\n\n"
        f"{bullets}\n\n"
        "为什么值得懂？\n"
        f"{why}\n\n"
        f"资料：{story.source_label}\n\n"
        f"{question}\n\n"
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
    title = html.escape(knowledge_title(story, digest))
    hero = html.escape(story.hero_fact)
    source = html.escape(story.source_label)
    return f"""<style>
@media (prefers-color-scheme: dark) {{
  .tlk-card {{ background-color:#10201a !important;color:#e2e9e5 !important; }}
  .tlk-title {{ color:#d6ff00 !important; }}
  .tlk-muted {{ color:#93a39b !important; }}
}}
</style>
<div class="tlk-card" style="background-color:#f4f7f5;color:#1c2b26;border-radius:12px;padding:14px 16px;font-size:15px;line-height:1.85;">
  <div class="tlk-title" style="font-size:18px;font-weight:bold;color:#0b3d2e;">🎾 每日网球知识 · {d.month}月{d.day}日</div>
  <div style="font-size:16px;font-weight:bold;margin:4px 0 10px;">{title}</div>
  <img src="{card_url}" style="width:100%;border-radius:8px;margin:6px 0;display:block;" />
  <div style="margin:10px 0;">{hero}</div>
  <a href="{copy_url}" style="display:block;background-color:#0a7d43;color:#ffffff;text-align:center;text-decoration:none;font-weight:bold;padding:12px 16px;border-radius:8px;margin:10px 0;">打开并复制知识文案</a>
  <div class="tlk-muted" style="color:#5f6f68;font-size:13px;">资料：{source} · 图片长按保存，可单独发小红书/公众号贴图。</div>
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
    for old in cards_dir.glob("card_*.png"):
        old.unlink()

    date_label = _date_label(digest.today)
    image = _screenshot_pages(
        [("knowledge", tournament_story_body(story, date_label))],
        theme,
    )[0][1]
    card_path = cards_dir / "card_00_knowledge.png"
    image.save(card_path, "PNG")

    xhs_text = knowledge_copy(story, digest)
    (outdir / "xiaohongshu.txt").write_text(xhs_text, encoding="utf-8")
    (outdir / "wechat_title.txt").write_text(
        f"每日网球知识：{story.title}", encoding="utf-8"
    )
    (outdir / "copy.html").write_text(to_copy_page(xhs_text), encoding="utf-8")
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
