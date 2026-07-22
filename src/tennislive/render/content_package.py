"""生成可直接审核发布的小红书单场内容包。"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
from datetime import date, datetime
from pathlib import Path

from ..content_ops import ContentPick
from ..digest import Digest
from ..qa import run_checks
from ..timeutil import WEEKDAY_ZH
from .hotspot import (
    hotspot_post,
    hotspot_reasons,
    hotspot_title_candidates,
)
from .pushmsg import to_copy_page
from .story import schedule_insight
from .titles import cover_fact_bundle, cover_highlights

logger = logging.getLogger(__name__)


class ContentGenerationError(RuntimeError):
    pass


def _json_default(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _pinned_comment(pick: ContentPick) -> str:
    match = pick.match
    if pick.kind == "preview":
        return "赛前先留一个具体判断：你认为这场最关键的胜负变量是什么？"
    if "爆冷" in hotspot_reasons(match):
        return "如果只选一个转折点，你会选哪一盘、哪一局？为什么？"
    return "抛开最终比分，这场最值得记住的比赛细节是什么？"


def _render_cards(
    pick: ContentPick,
    *,
    outdir: Path,
    today: date,
    headline: str,
) -> list[Path]:
    cards_dir = outdir / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    date_label = f"{today.month}.{today.day} · {WEEKDAY_ZH[today.weekday()]}"
    theme = os.environ.get("TENNISLIVE_THEME", "dark")
    try:
        from .webcards import generate_match_deck

        cover_visual = None
        visual_cache = outdir / ".cover-visual-cache"
        if os.environ.get("TENNISLIVE_COVER_VISUAL_FETCH", "off").lower() in {
            "1", "on", "true",
        }:
            from ..research.visual_sources import resolve_match_cover_visual

            cover_visual, cover_report = resolve_match_cover_visual(
                pick.match, visual_cache
            )
            (outdir / "cover_visual.json").write_text(
                json.dumps(cover_report, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        rendered = generate_match_deck(
            pick.match,
            headline=headline,
            today=today,
            date_label=date_label,
            kind=pick.kind,
            theme=theme,
            cover_visual=cover_visual,
        )
        from .image_output import save_social_image

        paths: list[Path] = []
        for index, (card_kind, image) in enumerate(rendered, 1):
            path = save_social_image(
                image, cards_dir / f"card_{index:02d}_{card_kind}"
            )
            paths.append(path)
        shutil.rmtree(visual_cache, ignore_errors=True)
        return paths
    except Exception as exc:
        # 本地或精简环境没有 Chromium 时，复用晨报的 Pillow 回退卡组。
        logger.warning("HTML 卡组渲染失败，改用 Pillow 兜底：%s", exc)
        from .cards import generate_cards

        digest = Digest(
            today=today,
            results=[pick.match] if pick.kind == "result" else [],
            schedule=[] if pick.kind == "result" else [pick.match],
        )
        return generate_cards(digest, cards_dir)


def generate_content_package(
    pick: ContentPick,
    *,
    outdir: Path,
    today: date,
    generated_at: datetime,
) -> dict:
    """生成标题、正文、置顶评论、事实、质检和统一卡组。"""
    outdir.mkdir(parents=True, exist_ok=True)
    digest = Digest(
        today=today,
        results=[pick.match] if pick.kind == "result" else [],
        schedule=[] if pick.kind == "result" else [pick.match],
    )
    from .xiaohongshu import decorate_title

    raw_titles = hotspot_title_candidates(pick.match)
    titles = [decorate_title(digest, candidate) for candidate in raw_titles]
    headline = raw_titles[0]
    post = hotspot_post(pick.match, title=titles[0])
    cover_copy = (
        cover_highlights(digest)
        if pick.kind == "result"
        else (headline, schedule_insight(pick.match))
    )
    fatal, warns = run_checks(
        digest, headline, post, cover_copy=cover_copy
    )
    (outdir / "qa.txt").write_text(
        "\n".join(
            ["[FATAL] " + item for item in fatal]
            + ["[WARN] " + item for item in warns]
        )
        or "OK",
        encoding="utf-8",
    )
    if fatal:
        raise ContentGenerationError("；".join(fatal))

    (outdir / "title_candidates.txt").write_text(
        "\n".join(titles), encoding="utf-8"
    )
    (outdir / "xiaohongshu.txt").write_text(post, encoding="utf-8")
    (outdir / "pinned_comment.txt").write_text(
        _pinned_comment(pick), encoding="utf-8"
    )
    (outdir / "copy.html").write_text(to_copy_page(post), encoding="utf-8")
    facts = {
        "kind": pick.kind,
        "generated_at": generated_at.isoformat(),
        "selection_score": pick.score,
        "selection_reasons": hotspot_reasons(pick.match),
        "match": pick.match,
        "cover": {
            "main": cover_copy[0],
            "secondary": cover_copy[1],
            "evidence": cover_fact_bundle(pick.match),
        },
    }
    (outdir / "facts.json").write_text(
        json.dumps(facts, default=_json_default, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    cards = _render_cards(
        pick,
        outdir=outdir,
        today=today,
        headline=headline,
    )
    item = {
        "kind": pick.kind,
        "match_id": pick.match.match_id,
        "title": titles[0],
        "cover_headline": headline,
        "title_candidates": titles,
        "text": post,
        "pinned_comment": _pinned_comment(pick),
        "cards": [_relative(path) for path in cards],
        "selection_score": pick.score,
        "reasons": hotspot_reasons(pick.match),
        "package_dir": _relative(outdir),
    }
    (outdir / "package.json").write_text(
        json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return item
